"""Phase 1 · Step 1C — engineer features, join mortality, build survival arrays.

Reads inspect/data/cohort_gh.csv and paxday_gh_valid.csv (from 1B) plus the
mortality .dat files (from 1A). Produces:

  X (DataFrame): one row per subject, 5 columns in the locked order:
      age, sex_male, bmi_dev, mean_daily_mims, sleep_dev

  Where:
    bmi_dev   = abs(BMI - 22)               # J-shape penalty around the optimum
    sleep_dev = abs(mean_sleep_min - 450)   # J-shape penalty around 7.5 h

  WHY THIS DEPARTS FROM THE ORIGINAL 8-FEATURE VECTOR:
  --------------------------------------------------
  An audit of the original 8-feature Cox model produced perverse coefficients
  (BMI mildly protective, more sleep = more risk, sleep-variability protective,
  more activity = more risk) driven by NHANES-specific confounding:

    * Obesity paradox: frail-elderly with low BMI die more, so linear BMI
      ends up protective. Fixed by `bmi_dev = |BMI − 22|`.
    * Sleep duration confounding: chronically ill subjects oversleep, so
      linear mean_sleep_min ends up risky. Fixed by `sleep_dev = |sleep − 450|`.
    * Activity / MIMS confounding cannot be fixed at the Cox level on this
      dataset. We tried five engineering variants — raw MIMS, MIMS-per-million,
      activity_rate (MIMS / wake-wear-min), age-stratified rate, inactivity
      floor, log10(rate). Every variant produced a near-zero or wrong-signed
      coefficient and **identical** C-index 0.825 — meaning the activity
      signal in NHANES 2011-2014 with 138 events at 24 months is dominated
      by age confounding (older subjects wore the monitor more, registered
      higher-intensity uncoordinated movement, and had more events). The
      papers that DO recover a protective MIMS effect (Saint-Maurice 2020,
      Smirnova 2020) use 6+ year follow-up and 10×+ events.

      Conclusion: **the Cox model takes 4 features (no activity), and
      activity enters the displayed score via a literature-calibrated
      `activity_bonus` heuristic in 02_gemini.py.** The bonus magnitude is
      anchored to Saint-Maurice 2020's HR 0.65 for highest-vs-lowest MIMS
      quintile, mapped to ~10 vitality points.
    * Collinearity in the variability features: ρ=0.70 between sd_daily_mims
      and sd_sleep_min — both are dropped (perverse signs, no useful info
      after the J-shape transforms above).

  Final 4-feature trained model: age, sex_male, bmi_dev, sleep_dev.
  All inference code (02_gemini.py, 04_worker.py) must mirror this engineering.

  y (structured ndarray): one row per subject, fields (event: bool, time: float).
      `time` is months from MEC exam (PERMTH_EXM, not PERMTH_INT — the PAM
      device was issued at the MEC exam, so PERMTH_EXM avoids immortal-time
      bias for accelerometry endpoints).

Horizon convention: `time >= 24 → time = 24, event = False`. The `>=` (not `>`)
treats a subject whose event landed at exactly month 24 as administratively
censored at the horizon — closes the boundary edge case Devin's earlier test
hit and matches the conservative reading of "did the event happen WITHIN 2
years" (strictly less than 24 months).

Persists X and y to inspect/data/{X,y}_gh.csv for 1D.

Run:

    inspect/.venv/bin/python inspect/01c_features.py
"""
from __future__ import annotations

from importlib.machinery import SourceFileLoader
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse 1A's loaders + manifest.
_a = SourceFileLoader(
    "a01", str(Path(__file__).resolve().parent / "01a_download.py")
).load_module()
CYCLES, DATA_DIR, load_mortality = _a.CYCLES, _a.DATA_DIR, _a.load_mortality


# ── Locked feature vector — order matters for the Cox model ─────────────────

# Cox model features. DO NOT REORDER. Inference code mirrors this exactly.
FEATURES: tuple[str, ...] = (
    "age",
    "sex_male",
    "bmi_dev",
    "sleep_dev",
)

# References used to build the J-shape transforms. Both come from the
# all-cause-mortality literature: optimal BMI ≈ 22 kg/m² (Flegal 2013),
# optimal sleep ≈ 7.5 h = 450 min (Cappuccio 2010 meta-analysis).
BMI_OPTIMUM: float = 22.0
SLEEP_OPTIMUM_MIN: float = 450.0

# MIMS scaling for the post-Cox activity_bonus layer. Raw MIMS values are
# in the millions; we divide by 1M before tanh to get reasonable curvature.
MIMS_SCALE: float = 1_000_000.0
MIMS_REFERENCE_M: float = 3.0             # cohort median (~2.65), rounded
# ±10 pts at the asymptote, anchored to Saint-Maurice 2020's HR 0.65 for
# highest-vs-lowest MIMS quintile (~35% mortality reduction). The Cox itself
# can't honestly fit this from our 138-event subset — we use the published
# effect size to set the bonus magnitude instead of learning it from data.
MIMS_BONUS_RANGE_PT: float = 10.0

HORIZON_MONTHS = 24


# ── Aggregation ──────────────────────────────────────────────────────────────

def aggregate_wearable(paxday_valid: pd.DataFrame) -> pd.DataFrame:
    """Per-subject mean/SD over valid wear-days only.

    Input: PAXDAY rows already restricted to valid days
           (caller should pass `paxday[paxday['valid_day']]`).
    Output: SEQN + 5 wearable feature columns.
    """
    g = paxday_valid.groupby("SEQN")
    out = pd.DataFrame({
        "mean_daily_mims":    g["PAXAISMD"].mean(),
        "sd_daily_mims":      g["PAXAISMD"].std(),
        "mean_sleep_min":     g["PAXSWMD"].mean(),
        "sd_sleep_min":       g["PAXSWMD"].std(),
        "mean_wake_wear_min": g["PAXWWMD"].mean(),
    }).reset_index()
    return out


def build_features(cohort: pd.DataFrame, paxday: pd.DataFrame) -> pd.DataFrame:
    """Cohort + per-subject wearable summary → one row per subject.

    Output columns: SEQN, cycle, *FEATURES, plus the raw `bmi` and
    `mean_sleep_min` columns kept for inspection / debugging.
    """
    # CSV roundtripping turns the bool valid_day into "True"/"False" strings —
    # coerce defensively so `paxday[paxday['valid_day']]` filters correctly.
    if paxday["valid_day"].dtype == object:
        paxday = paxday.copy()
        paxday["valid_day"] = paxday["valid_day"].astype(str).str.lower().eq("true")

    valid = paxday[paxday["valid_day"]]
    wearable = aggregate_wearable(valid)

    feats = cohort.merge(wearable, on="SEQN", how="inner")
    feats["bmi_dev"] = (feats["bmi"].astype(float) - BMI_OPTIMUM).abs()
    feats["sleep_dev"] = (feats["mean_sleep_min"].astype(float) - SLEEP_OPTIMUM_MIN).abs()

    # Persist raw values too so X_gh.csv stays self-describing for debugging
    # and the post-hoc activity_bonus layer can read them directly.
    keep = ["SEQN", "cycle", "bmi", "mean_sleep_min", "mean_daily_mims",
            "mean_wake_wear_min", *FEATURES]
    # De-dup in case bmi/mean_sleep_min are also in FEATURES historically.
    seen: set[str] = set()
    keep = [c for c in keep if not (c in seen or seen.add(c))]
    return feats[keep].copy()


# ── Survival labels ──────────────────────────────────────────────────────────

def join_mortality(features: pd.DataFrame) -> pd.DataFrame:
    """Left-join per-cycle mortality onto features. ELIGSTAT == 1 only."""
    pieces = []
    for cycle in CYCLES:
        sub = features[features["cycle"] == cycle.name]
        mort = load_mortality(DATA_DIR / cycle.mortality_filename)
        mort = mort[mort["ELIGSTAT"] == 1][["SEQN", "MORTSTAT", "PERMTH_EXM"]]
        merged = sub.merge(mort, on="SEQN", how="inner")
        merged = merged.dropna(subset=["MORTSTAT", "PERMTH_EXM"])
        pieces.append(merged)
    return pd.concat(pieces, ignore_index=True)


def make_survival_arrays(joined: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Apply the 24-month horizon and emit (X, y) ready for sksurv."""
    time = joined["PERMTH_EXM"].astype(float).to_numpy()
    event = (joined["MORTSTAT"] == 1).to_numpy()

    at_or_past = time >= float(HORIZON_MONTHS)
    time = np.where(at_or_past, float(HORIZON_MONTHS), time)
    event = np.where(at_or_past, False, event).astype(bool)

    y = np.zeros(len(joined), dtype=[("event", "?"), ("time", "f8")])
    y["event"] = event
    y["time"] = time

    X = joined[list(FEATURES)].astype(float).reset_index(drop=True)
    return X, y


# ── Verification ─────────────────────────────────────────────────────────────

def main() -> None:
    cohort = pd.read_csv(DATA_DIR / "cohort_gh.csv")
    paxday = pd.read_csv(DATA_DIR / "paxday_gh_valid.csv")

    print("aggregating wearable features per subject …")
    feats = build_features(cohort, paxday)
    print(f"  features built for {len(feats):,} subjects")

    print("joining mortality (per cycle) …")
    joined = join_mortality(feats)
    print(f"  after ELIGSTAT==1 join: {len(joined):,} subjects")

    X, y = make_survival_arrays(joined)

    n_total = len(y)
    n_events = int(y["event"].sum())
    n_at_horizon = int((y["time"] == float(HORIZON_MONTHS)).sum())
    n_event_at_horizon = int(((y["time"] == float(HORIZON_MONTHS)) & y["event"]).sum())
    n_past_horizon = int((y["time"] > HORIZON_MONTHS).sum())

    # Per-cycle event breakdown for sanity.
    by_cycle = (
        joined.assign(_event=y["event"])
        .groupby("cycle")
        .agg(n=("SEQN", "size"), events=("_event", "sum"))
        .reset_index()
    )

    print()
    print("─── 1C verification ────────────────────────────────────────────")
    print(f"X shape:                              {X.shape}")
    print(f"X column order matches FEATURES:      {list(X.columns) == list(FEATURES)}")
    print(f"X dtypes (must all be float64):       {sorted(set(str(d) for d in X.dtypes))}")
    print(f"X NaN cells:                          {int(X.isna().sum().sum())}")
    print()
    print(f"y dtype:                              {y.dtype}")
    print(f"y rows:                               {n_total:,}")
    print(f"events (24-mo deaths):                {n_events:,}")
    print(f"event rate:                           {n_events / n_total * 100:.2f} %")
    print(f"events / {len(FEATURES)} features (rule of thumb): {n_events / len(FEATURES):.1f} per feature")
    print()
    print("boundary checks (both must be 0):")
    print(f"  rows with time > 24:                {n_past_horizon}")
    print(f"  events with time == 24:             {n_event_at_horizon}")
    print()
    print("per-cycle breakdown:")
    print(by_cycle.to_string(index=False))
    print()
    print("per-feature means (sanity check, no obvious garbage):")
    print(X.mean().to_string())
    print()

    x_path = DATA_DIR / "X_gh.csv"
    y_path = DATA_DIR / "y_gh.csv"
    X.to_csv(x_path, index=False)
    pd.DataFrame({"event": y["event"], "time": y["time"]}).to_csv(y_path, index=False)
    print(f"wrote: {x_path.relative_to(DATA_DIR.parent)}")
    print(f"wrote: {y_path.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
