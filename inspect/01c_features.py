"""Phase 1 · Step 1C — engineer 8 features, join mortality, build survival arrays.

Reads inspect/data/cohort_gh.csv and paxday_gh_valid.csv (from 1B) plus the
mortality .dat files (from 1A). Produces:

  X (DataFrame): one row per subject, 8 columns in the AGENTS.md locked order:
      age, sex_male, bmi,
      mean_daily_mims, sd_daily_mims,
      mean_sleep_min, sd_sleep_min,
      mean_wake_wear_min

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

FEATURES: tuple[str, ...] = (
    "age",
    "sex_male",
    "bmi",
    "mean_daily_mims",
    "sd_daily_mims",
    "mean_sleep_min",
    "sd_sleep_min",
    "mean_wake_wear_min",
)

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
    """Cohort + per-subject wearable summary → one row per subject with 8 features."""
    # CSV roundtripping turns the bool valid_day into "True"/"False" strings —
    # coerce defensively so `paxday[paxday['valid_day']]` filters correctly.
    if paxday["valid_day"].dtype == object:
        paxday = paxday.copy()
        paxday["valid_day"] = paxday["valid_day"].astype(str).str.lower().eq("true")

    valid = paxday[paxday["valid_day"]]
    wearable = aggregate_wearable(valid)

    feats = cohort.merge(wearable, on="SEQN", how="inner")
    keep = ["SEQN", "cycle"] + list(FEATURES)
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
    print(f"events / 8 features (rule of thumb):  {n_events / 8:.1f} per feature")
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
