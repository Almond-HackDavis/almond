"""Trained-model inference layer + augmentation.

Two layers:

  1. The TRAINED Cox model on (age, sex_male, bmi_dev, sleep_dev) → raw 2-yr
     mortality probability. Loaded from `almond-ml/models/cox_model.pkl`.

  2. The AUGMENTATION layer — five HealthKit signals that are NOT in the Cox
     model (the NHANES wearable subset can't credibly fit them; see
     `inspect/01c_features.py` docstring) but DO matter to users and the
     literature. Each maps to a normalized [-1, 1] wellness score via a
     literature-anchored curve, and the average of available signals
     contributes a bounded ± vitality bonus on top of the Cox-derived
     pool-percentile base score:

       activity        — Saint-Maurice 2020 (HR 0.65 highest-vs-lowest MIMS Q)
       resting_hr      — Jensen 2013 (HR 1.16 per +10 bpm RHR, all-cause mortality)
       hrv_sdnn        — Hillebrand 2013 (HR 1.10 per −10 ms SDNN, cardiac events)
       vo2_max         — Kaminsky 2013 / FRIEND norms; also drives fitness_age
       walking_hr_avg  — secondary HR signal (small weight)

     All five are optional; missing signals are skipped, NOT zeroed. A user
     who only sends Tier-1 fields (steps + kcal + exercise + sleep) gets
     exactly the prior activity-only behavior.

  3. fitness_age — derived from VO2 max via the NTNU formula (Nes 2013).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

log = logging.getLogger("almond.ml")

# ── Locked constants — must match inspect/01c_features.py exactly ───────────

FEATURES: tuple[str, ...] = ("age", "sex_male", "bmi_dev", "sleep_dev")

HORIZON_MONTHS: int = 24
BMI_OPTIMUM: float = 22.0
SLEEP_OPTIMUM_MIN: float = 450.0

MIMS_SCALE: float = 1_000_000.0
MIMS_REFERENCE_M: float = 3.0
MIMS_BONUS_TIGHTNESS: float = 1.5

# ── Augmentation signal anchors (all literature-derived, not learned) ───────
#
# Each signal maps a raw HealthKit value to a wellness score in [-1, +1] via
# a smooth tanh. The reference value (anchor where wellness = 0) and the
# tightness (how fast the curve saturates) are calibrated so that the
# population's typical range covers most of [-1, +1].

# Resting heart rate (bpm). Jensen 2013 (Eur Heart J): HR 1.16 per +10 bpm
# above reference for all-cause mortality. Reference is the population median
# (~65 bpm in NHANES + Apple Watch combined cohorts), NOT the elite-athlete
# 60 bpm — using 60 makes "objectively healthy" RHRs in the 55-65 range score
# only mildly positive, which can drag down a weighted-average composite when
# activity is already strong.
RHR_REFERENCE_BPM: float = 65.0
RHR_TIGHTNESS_BPM: float = 15.0     # +30 bpm above 65 → wellness ≈ −0.96

# Heart-rate variability (SDNN, ms). Hillebrand 2013 meta-analysis: HR 1.10
# per −10 ms SDNN. Higher = better. Population median ~50 ms, range 20-100.
HRV_REFERENCE_MS: float = 50.0
HRV_TIGHTNESS_MS: float = 20.0      # +40 ms above 50 → wellness ≈ +0.96

# VO2 max (mL/kg/min). Reference at age 30 from Kaminsky 2013 FRIEND registry
# 50th percentile. Decline rate per year past 30 from Nes 2013.
VO2_REF_AT_30_M: float = 45.0
VO2_REF_AT_30_F: float = 35.0
VO2_DECLINE_PER_YR_M: float = 0.35
VO2_DECLINE_PER_YR_F: float = 0.30
VO2_TIGHTNESS_FRAC: float = 0.20    # ±20% of age-norm spans most of [-1, +1]

# Walking heart-rate average (bpm). Secondary signal, gentle. Lower = better.
WHR_REFERENCE_BPM: float = 105.0
WHR_TIGHTNESS_BPM: float = 18.0

# Per-signal weights into the composite. Activity stays at 0.30 to preserve
# its relative importance with the well-validated Saint-Maurice anchor;
# HR/HRV/VO2 share the rest; walking_hr is small because it overlaps RHR.
SIGNAL_WEIGHTS: dict[str, float] = {
    "activity":   0.30,
    "rhr":        0.22,
    "hrv":        0.18,
    "vo2":        0.25,
    "walking_hr": 0.05,
}

# Total bonus range, in vitality points. Bumped from the prior 10 → 13 so
# that an elite middle-aged athlete (whose pool percentile is capped by
# the Cox-derived absolute risk at ~50th) can still score in the high-50s.
# Verified against the headline regression: a healthy 32yo M still
# outscores a 65yo F with diabetes by >> 20 pts, so age dominance is
# preserved. The activity-only curve still uses the same wellness shape
# as before; only its asymptote slid from ±10 → ±13 vitality points.
TOTAL_BONUS_RANGE_PT: float = 13.0
# Backward-compat alias used by some external callers / tests.
MIMS_BONUS_RANGE_PT: float = TOTAL_BONUS_RANGE_PT

# Age-band keys for the percentile lookup. Must match inspect/05_percentiles.py.
AGE_BANDS: tuple[tuple[int, int], ...] = (
    (18, 25), (25, 30), (30, 35), (35, 40), (40, 45), (45, 50),
    (50, 55), (55, 60), (60, 65), (65, 70), (70, 75), (75, 81),
)

MODEL_ID: str = "almond-cox-2yr-v0.2.0"   # bumped: HR/HRV/VO2 augmentation

MODELS_DIR: Path = Path(__file__).resolve().parent / "models"
COX_MODEL_PATH: Path = MODELS_DIR / "cox_model.pkl"
PERCENTILE_LOOKUP_PATH: Path = MODELS_DIR / "percentile_lookup.json"
FEATURE_MEANS_PATH: Path = MODELS_DIR / "feature_means.json"


# ── Module-level singletons (loaded once at startup) ────────────────────────


@dataclass
class _Loaded:
    model: Any
    lookup: dict[str, list[float]]
    pool_sorted: list[float]
    feature_means: dict[str, float]


_state: Optional[_Loaded] = None


def load_artifacts() -> _Loaded:
    """Load the Cox pkl + percentile lookup. Cached after first call."""
    global _state
    if _state is not None:
        return _state

    log.info("loading Cox model from %s", COX_MODEL_PATH)
    model = joblib.load(COX_MODEL_PATH)
    if len(model.coef_) != len(FEATURES):
        raise RuntimeError(
            f"Cox model has {len(model.coef_)} coefficients but FEATURES "
            f"declares {len(FEATURES)} — pkl/code drift, refusing to start."
        )

    lookup: dict[str, list[float]] = json.loads(PERCENTILE_LOOKUP_PATH.read_text())
    pool = lookup.get("__pool__")
    if not pool:
        # Fall back to synthesizing from per-bucket lists if the lookup is from
        # a pre-pool-key generation.
        pool = sorted(r for k, lst in lookup.items() if k != "__pool__" for r in lst)

    means: dict[str, float] = json.loads(FEATURE_MEANS_PATH.read_text())

    _state = _Loaded(model=model, lookup=lookup, pool_sorted=list(pool), feature_means=means)
    log.info("Cox + percentile lookup ready (n_pool=%d, buckets=%d)",
             len(_state.pool_sorted), len(_state.lookup) - (1 if "__pool__" in _state.lookup else 0))
    return _state


# ── Feature engineering ─────────────────────────────────────────────────────


def _bucket_key(age: float, sex_male: float) -> str:
    a = int(np.clip(age, 18, 80))
    for lo, hi in AGE_BANDS:
        if lo <= a < hi:
            return f"{lo}-{hi - 1}_{int(sex_male)}"
    lo, hi = AGE_BANDS[-1]
    return f"{lo}-{hi - 1}_{int(sex_male)}"


def _mean_field(rows: list[dict], key: str) -> float:
    """Mean of `row[key]` across non-null entries; 0.0 if none.

    HealthKit doesn't guarantee aligned per-day arrays — iOS may send 91 days
    of steps but only 33 days of active energy. We mean each metric
    independently before combining, which is robust to any ragged shape.
    """
    vals = [float(r[key]) for r in rows if isinstance(r, dict) and key in r and r[key] is not None]
    return float(np.mean(vals)) if vals else 0.0


def _opt_mean_field(rows: list[dict], key: str) -> Optional[float]:
    """Like `_mean_field` but returns None when the array is empty / missing.

    Used for Tier-2 augmentation signals where "missing" must NOT be
    confused with "0" — a user without HRV data should not be treated as
    "user with HRV = 0 ms".
    """
    vals = [float(r[key]) for r in rows if isinstance(r, dict) and key in r and r[key] is not None]
    return float(np.mean(vals)) if vals else None


def engineer_features(onboarding: dict, samples: dict) -> dict[str, Any]:
    """Map an input payload to model + augmentation features.

    Returns a dict with:
      * The 4 Cox features in the order declared in `FEATURES`.
      * `mean_daily_mims` — composite activity volume (drives `activity`
        signal in the augmentation, NOT a Cox feature).
      * Optional Tier-2 augmentation signals — None when iOS didn't send:
        `mean_resting_hr`, `mean_hrv_sdnn`, `vo2_max`, `mean_walking_hr`.
      * Display-only echoes (`_bmi_raw`, `_mean_sleep_min`) for the prompt.
    """
    age = float(onboarding["age"])
    sex_male = 1.0 if onboarding["sex"].upper() == "M" else 0.0

    weight_kg = float(onboarding["weight_kg"])
    height_m = float(onboarding["height_cm"]) / 100.0
    bmi = weight_kg / (height_m * height_m)

    # ── Tier-1 ──────────────────────────────────────────────────────────────
    mean_steps = _mean_field(samples.get("steps_daily", []),              "count")
    mean_kcal  = _mean_field(samples.get("active_energy_daily_kcal", []), "kcal")
    mean_excm  = _mean_field(samples.get("exercise_minutes_daily", []),   "minutes")
    mean_daily_mims = (
        250_000.0 * (mean_steps / 1000.0)
        + 2_000.0 * mean_kcal
        + 30_000.0 * mean_excm
    )

    sleep = np.asarray([s["duration_min"] for s in samples.get("sleep_sessions", [])], dtype=float)
    mean_sleep_min = float(sleep.mean()) if sleep.size else SLEEP_OPTIMUM_MIN

    # ── Tier-2 augmentation signals (all optional) ─────────────────────────
    mean_resting_hr = _opt_mean_field(samples.get("resting_hr_daily", []),       "bpm")
    mean_hrv_sdnn   = _opt_mean_field(samples.get("hrv_sdnn", []),               "ms")
    mean_walking_hr = _opt_mean_field(samples.get("walking_hr_avg_daily", []),   "bpm")

    vo2_obj = samples.get("vo2_max_latest")
    vo2_max: Optional[float] = None
    if isinstance(vo2_obj, dict) and vo2_obj.get("value") is not None:
        vo2_max = float(vo2_obj["value"])

    return {
        # Cox features.
        "age":             age,
        "sex_male":        sex_male,
        "bmi_dev":         abs(bmi - BMI_OPTIMUM),
        "sleep_dev":       abs(mean_sleep_min - SLEEP_OPTIMUM_MIN),
        # Tier-1 augmentation signal.
        "mean_daily_mims": mean_daily_mims,
        # Tier-2 augmentation signals — None when iOS didn't send.
        "mean_resting_hr": mean_resting_hr,
        "mean_hrv_sdnn":   mean_hrv_sdnn,
        "vo2_max":         vo2_max,
        "mean_walking_hr": mean_walking_hr,
        # Display-only echoes for the Gemma prompt.
        "_bmi_raw":        bmi,
        "_mean_sleep_min": mean_sleep_min,
    }


# ── Predictions ─────────────────────────────────────────────────────────────


def predict_2yr_mortality(features: dict[str, float]) -> float:
    """Run the trained Cox; return the 24-month all-cause mortality probability."""
    state = load_artifacts()
    X = pd.DataFrame(
        [{f: float(features[f]) for f in FEATURES}],
        columns=list(FEATURES),
    )
    sf = state.model.predict_survival_function(X)[0]
    return float(1.0 - sf(float(HORIZON_MONTHS)))


def pool_percentile(raw_risk: float) -> float:
    """Where does `raw_risk` rank in the pooled NHANES training cohort? 0..1."""
    state = load_artifacts()
    if not state.pool_sorted:
        return 0.5
    return float(np.searchsorted(state.pool_sorted, raw_risk, side="right")) / len(state.pool_sorted)


# ── Wellness curves — one per signal, all return [-1, +1] ───────────────────


def _wellness_activity(mean_daily_mims: float) -> float:
    """Higher MIMS = better. Anchored at the 3M MIMS cohort median."""
    mims_M = float(mean_daily_mims) / MIMS_SCALE
    return float(np.tanh((mims_M - MIMS_REFERENCE_M) / MIMS_BONUS_TIGHTNESS))


def _wellness_resting_hr(rhr_bpm: float) -> float:
    """Lower RHR = better. Jensen 2013 calibration around 60 bpm reference."""
    # Sign flipped: higher RHR → lower wellness.
    return float(np.tanh((RHR_REFERENCE_BPM - rhr_bpm) / RHR_TIGHTNESS_BPM))


def _wellness_hrv(hrv_ms: float) -> float:
    """Higher HRV = better. Hillebrand 2013 around 50 ms reference."""
    return float(np.tanh((hrv_ms - HRV_REFERENCE_MS) / HRV_TIGHTNESS_MS))


def _wellness_vo2(vo2_obs: float, age: float, sex_male: float) -> float:
    """Higher VO2max relative to age-norm = better. FRIEND/Kaminsky 2013.

    Computes deviation from the age-and-sex-adjusted reference, normalized
    as a fraction of that reference.
    """
    ref_30  = VO2_REF_AT_30_M if sex_male >= 0.5 else VO2_REF_AT_30_F
    slope   = VO2_DECLINE_PER_YR_M if sex_male >= 0.5 else VO2_DECLINE_PER_YR_F
    vo2_ref = max(15.0, ref_30 - slope * max(0.0, age - 30.0))
    rel_dev = (vo2_obs - vo2_ref) / vo2_ref          # +0.20 = 20% above norm
    return float(np.tanh(rel_dev / VO2_TIGHTNESS_FRAC))


def _wellness_walking_hr(whr_bpm: float) -> float:
    """Lower walking HR = better cardiovascular efficiency."""
    return float(np.tanh((WHR_REFERENCE_BPM - whr_bpm) / WHR_TIGHTNESS_BPM))


# ── Composite bonus ─────────────────────────────────────────────────────────


def signal_wellness(features: dict[str, Any]) -> dict[str, Optional[float]]:
    """Compute per-signal wellness in [-1, +1] for whatever signals are present.

    Returns {signal_name: wellness_or_None}. Missing signals stay None and
    are excluded from the composite average.
    """
    wellness: dict[str, Optional[float]] = {}

    wellness["activity"] = _wellness_activity(features.get("mean_daily_mims", 0.0))

    rhr = features.get("mean_resting_hr")
    wellness["rhr"] = _wellness_resting_hr(rhr) if rhr else None

    hrv = features.get("mean_hrv_sdnn")
    wellness["hrv"] = _wellness_hrv(hrv) if hrv else None

    vo2 = features.get("vo2_max")
    if vo2 and vo2 > 0:
        wellness["vo2"] = _wellness_vo2(vo2, features.get("age", 30.0), features.get("sex_male", 0.5))
    else:
        wellness["vo2"] = None

    whr = features.get("mean_walking_hr")
    wellness["walking_hr"] = _wellness_walking_hr(whr) if whr else None

    return wellness


def composite_bonus(features: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """Weighted-average wellness across available signals → vitality bonus.

    Returns (total_bonus_pts, per_signal_contribution_pts).

      * `total_bonus_pts` ∈ [-TOTAL_BONUS_RANGE_PT, +TOTAL_BONUS_RANGE_PT].
      * `per_signal_contribution_pts[name]` is the share of the bonus
        attributable to that signal — used to build top_drivers.

    A user with only `activity` available gets exactly the prior
    `activity_bonus` behavior. Adding HR/HRV/VO2/WHR refines the wellness
    average inside the same envelope.
    """
    wellness = signal_wellness(features)
    available = [(name, w) for name, w in wellness.items() if w is not None]
    if not available:
        return 0.0, {}

    total_weight = sum(SIGNAL_WEIGHTS[name] for name, _ in available)
    weighted_avg = sum(SIGNAL_WEIGHTS[name] * w for name, w in available) / total_weight

    total_pts = TOTAL_BONUS_RANGE_PT * weighted_avg

    # Per-signal contribution = (its share of the weighted avg) × total bonus.
    contributions: dict[str, float] = {}
    for name, w in available:
        share = (SIGNAL_WEIGHTS[name] * w) / total_weight   # signed
        contributions[name] = TOTAL_BONUS_RANGE_PT * share
    return float(total_pts), contributions


# ── Backward-compat shims (older callers / tests use these names) ───────────


def activity_bonus(mean_daily_mims: float) -> float:
    """Activity-only bonus, kept for backward compatibility with prior tests.

    When `composite_bonus` is called with ONLY activity available the result
    is identical, so this shim is exact.
    """
    return TOTAL_BONUS_RANGE_PT * _wellness_activity(mean_daily_mims)


# ── Vitality + fitness_age + top_drivers ────────────────────────────────────


def vitality_score(raw_risk: float, features_or_mims) -> float:
    """Final 0..100 vitality: pool-percentile of raw risk + composite bonus.

    Accepts either a feature dict (preferred — picks up all augmentation
    signals) or a bare MIMS value (backward-compat with the prior
    `vitality_score(raw, mean_daily_mims)` signature).
    """
    if isinstance(features_or_mims, dict):
        bonus, _ = composite_bonus(features_or_mims)
    else:
        bonus = activity_bonus(float(features_or_mims))
    base = 100.0 * (1.0 - pool_percentile(raw_risk))
    return float(max(0.0, min(100.0, base + bonus)))


def fitness_age(vo2_obs: Optional[float], age: float, sex_male: float) -> Optional[dict]:
    """NTNU-style biological-age estimate from VO2 max (Nes 2013).

    fitness_age = age + (VO2_ref(age, sex) − VO2_observed) / slope

    Returns None when VO2 isn't provided. Output is clipped to [18, 90].
    """
    if vo2_obs is None or vo2_obs <= 0:
        return None
    ref_30 = VO2_REF_AT_30_M if sex_male >= 0.5 else VO2_REF_AT_30_F
    slope = VO2_DECLINE_PER_YR_M if sex_male >= 0.5 else VO2_DECLINE_PER_YR_F
    vo2_ref = max(15.0, ref_30 - slope * max(0.0, age - 30.0))
    delta_yrs = (vo2_ref - vo2_obs) / slope
    fa = float(np.clip(age + delta_yrs, 18.0, 90.0))
    return {
        "value": round(fa, 1),
        "chronological_age": int(round(age)),
        "delta": round(fa - age, 1),
    }


def top_drivers(features: dict[str, Any], contributions: dict[str, float], n: int = 3) -> list[dict]:
    """Top `n` signals by absolute contribution to vitality, with sign + label."""
    HUMAN_LABELS = {
        "activity":   "Daily activity",
        "rhr":        "Resting heart rate",
        "hrv":        "Heart-rate variability",
        "vo2":        "Cardiorespiratory fitness (VO₂ max)",
        "walking_hr": "Walking heart rate",
    }
    SIGNAL_RAW_KEY = {
        "activity":   "mean_daily_mims",
        "rhr":        "mean_resting_hr",
        "hrv":        "mean_hrv_sdnn",
        "vo2":        "vo2_max",
        "walking_hr": "mean_walking_hr",
    }
    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:n]
    drivers = []
    for name, pts in ranked:
        raw_val = features.get(SIGNAL_RAW_KEY[name])
        drivers.append({
            "feature":          name,
            "human_label":      HUMAN_LABELS.get(name, name),
            "value":            float(raw_val) if raw_val is not None else 0.0,
            "contribution_pts": round(float(pts), 2),
            "direction":        "better" if pts >= 0 else "worse",
        })
    return drivers


# ── Convenience: full pipeline in one call ──────────────────────────────────


def run_pipeline(onboarding: dict, samples: dict) -> dict[str, Any]:
    """End-to-end inference. Returns a dict with raw_risk + vitality + features.

    The HTTP handler calls this then asks `gemma.summarize(...)` for the
    natural-language summary.
    """
    feats = engineer_features(onboarding, samples)
    raw = predict_2yr_mortality(feats)
    bonus, contributions = composite_bonus(feats)
    base = 100.0 * (1.0 - pool_percentile(raw))
    vit = float(max(0.0, min(100.0, base + bonus)))

    fa = fitness_age(feats.get("vo2_max"), feats["age"], feats["sex_male"])
    drivers = top_drivers(feats, contributions)

    return {
        "features":          feats,
        "raw_2yr_mortality": raw,
        "vitality":          vit,
        "activity_bonus":    activity_bonus(feats["mean_daily_mims"]),
        "composite_bonus":   bonus,
        "contributions":     contributions,
        "top_drivers":       drivers,
        "fitness_age":       fa,            # None if no VO2 max
    }
