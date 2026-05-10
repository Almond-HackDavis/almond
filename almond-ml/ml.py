"""Trained-model inference layer.

Loads the Cox model + percentile lookup from `almond-ml/models/` and exposes
two functions:

    predict_2yr_mortality(onboarding, samples) -> raw 2-yr probability
    vitality_score(raw_risk, mean_daily_mims) -> 0..100 score

Feature engineering, J-shape transforms, activity bonus, pool-percentile
formula are all in this file — productionized from the audit-validated
versions in `inspect/02_gemini.py` (which trained and stress-tested them).
The trained Cox uses 4 features: age, sex_male, bmi_dev, sleep_dev. MIMS
is intentionally NOT a Cox feature; it enters the score via
`activity_bonus()` with a magnitude anchored to Saint-Maurice 2020 and a
post-hoc tanh shape — see `inspect/01c_features.py` docstring for why.
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
MIMS_BONUS_RANGE_PT: float = 10.0
MIMS_BONUS_TIGHTNESS: float = 1.5

# Age-band keys for the percentile lookup. Must match inspect/05_percentiles.py.
AGE_BANDS: tuple[tuple[int, int], ...] = (
    (18, 25), (25, 30), (30, 35), (35, 40), (40, 45), (45, 50),
    (50, 55), (55, 60), (60, 65), (65, 70), (70, 75), (75, 81),
)

MODEL_ID: str = "almond-cox-2yr-v0.1.0"

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


def engineer_features(onboarding: dict, samples: dict) -> dict[str, float]:
    """Map an input payload (matching POST /input schema) to (Cox features + raw MIMS).

    Returns a dict with the 4 Cox features in the order declared in `FEATURES`,
    plus the raw `mean_daily_mims` (used by `activity_bonus` but not the model).
    """
    age = float(onboarding["age"])
    sex_male = 1.0 if onboarding["sex"].upper() == "M" else 0.0

    weight_kg = float(onboarding["weight_kg"])
    height_m = float(onboarding["height_cm"]) / 100.0
    bmi = weight_kg / (height_m * height_m)

    # Composite MIMS proxy, calibrated to roughly straddle NHANES PAXDAY mean
    # (~2.67M). Same recipe as inspect/04_worker.py — placeholder until we
    # have ground-truth Apple-Watch-to-MIMS pairs.
    steps = np.asarray([d["count"]   for d in samples.get("steps_daily", [])],              dtype=float)
    kcal  = np.asarray([d["kcal"]    for d in samples.get("active_energy_daily_kcal", [])], dtype=float)
    excm  = np.asarray([d["minutes"] for d in samples.get("exercise_minutes_daily", [])],   dtype=float)
    daily_mims = 250_000.0 * (steps / 1000.0) + 2_000.0 * kcal + 30_000.0 * excm
    mean_daily_mims = float(daily_mims.mean()) if daily_mims.size else 0.0

    sleep = np.asarray([s["duration_min"] for s in samples.get("sleep_sessions", [])], dtype=float)
    mean_sleep_min = float(sleep.mean()) if sleep.size else SLEEP_OPTIMUM_MIN

    return {
        "age":             age,
        "sex_male":        sex_male,
        "bmi_dev":         abs(bmi - BMI_OPTIMUM),
        "sleep_dev":       abs(mean_sleep_min - SLEEP_OPTIMUM_MIN),
        "mean_daily_mims": mean_daily_mims,
        # Display-only echoes for downstream prompt rendering.
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


def activity_bonus(mean_daily_mims: float) -> float:
    """Post-Cox vitality bonus from MIMS via tanh, ±MIMS_BONUS_RANGE_PT.

    Magnitude anchored to Saint-Maurice 2020 (HR 0.65 highest-vs-lowest MIMS
    quintile ≈ ~10 vitality points at the asymptote).
    """
    mims_M = float(mean_daily_mims) / MIMS_SCALE
    delta = (mims_M - MIMS_REFERENCE_M) / MIMS_BONUS_TIGHTNESS
    return float(MIMS_BONUS_RANGE_PT * np.tanh(delta))


def pool_percentile(raw_risk: float) -> float:
    """Where does `raw_risk` rank in the pooled NHANES training cohort? 0..1."""
    state = load_artifacts()
    if not state.pool_sorted:
        return 0.5
    return float(np.searchsorted(state.pool_sorted, raw_risk, side="right")) / len(state.pool_sorted)


def vitality_score(raw_risk: float, mean_daily_mims: float) -> float:
    """Final 0..100 vitality score: pool-percentile of raw risk + activity bonus.

    See `inspect/02_gemini.py::vitality_from_percentile` for the rationale —
    age-monotonicity comes from the pool percentile, activity-sensitivity
    comes from the bonus.
    """
    base = 100.0 * (1.0 - pool_percentile(raw_risk))
    bonus = activity_bonus(mean_daily_mims)
    return float(max(0.0, min(100.0, base + bonus)))


# ── Convenience: full pipeline in one call ──────────────────────────────────


def run_pipeline(onboarding: dict, samples: dict) -> dict[str, Any]:
    """End-to-end inference. Returns a dict with raw_risk + vitality + features.

    The HTTP handler calls this then asks `gemma.summarize(...)` for the
    natural-language summary.
    """
    feats = engineer_features(onboarding, samples)
    raw = predict_2yr_mortality(feats)
    vit = vitality_score(raw, feats["mean_daily_mims"])
    return {
        "features":        feats,
        "raw_2yr_mortality": raw,
        "vitality":        vit,
        "activity_bonus":  activity_bonus(feats["mean_daily_mims"]),
    }
