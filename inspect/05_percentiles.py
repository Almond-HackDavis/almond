"""Phase 3.5 — build the (age × sex) raw-risk percentile lookup.

Loads the trained Cox model + the full NHANES training cohort (X_gh.csv,
8,536 subjects), predicts a 2-year mortality probability for every subject,
and writes both:

    1. lookup[bucket]    — sorted predicted-risk per (age_band × sex_male)
                           bucket, used for the within-bucket peer-percentile
                           component of the hybrid vitality score.

    2. lookup["__pool__"] — sorted predicted-risk pooled across ALL buckets,
                            used for cross-cohort context in
                            vitality_from_hybrid (kept for diagnostics).

The vitality score itself (in 02_gemini.py and 04_worker.py) blends the
absolute raw risk with the within-bucket peer percentile:

    vitality = 100 × [α · (1 − raw_risk) + (1 − α) · (1 − bucket_pct/100)]

with α = 0.6 (60% absolute, 40% peer). This blend prevents the original
inversion where a 65yo woman exceptional within her bucket beat a healthy
32yo man who was only above-average within his bucket.

Run once whenever the Cox model is retrained:

    inspect/.venv/bin/python inspect/05_percentiles.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from importlib.machinery import SourceFileLoader

import joblib
import numpy as np
import pandas as pd

INSPECT_DIR = Path(__file__).resolve().parent
MODELS_DIR = INSPECT_DIR / "models"
DATA_DIR = INSPECT_DIR / "data"

# Load FEATURES from 1C so we always predict on exactly the columns the model
# was trained on, regardless of what extra debug columns X_gh.csv carries.
_c = SourceFileLoader("c01", str(INSPECT_DIR / "01c_features.py")).load_module()
FEATURES = _c.FEATURES
HORIZON_MONTHS = _c.HORIZON_MONTHS

# 5-year age bands. NHANES is top-coded at 80 — anyone older lands in 75-80.
AGE_BANDS: tuple[tuple[int, int], ...] = (
    (18, 25), (25, 30), (30, 35), (35, 40), (40, 45), (45, 50),
    (50, 55), (55, 60), (60, 65), (65, 70), (70, 75), (75, 81),
)

OUTPUT_PATH = MODELS_DIR / "percentile_lookup.json"


def age_band_for(age: float) -> tuple[int, int]:
    """Return the (lo, hi) age band the subject falls into. Clips to [18, 80]."""
    age = int(np.clip(age, 18, 80))
    for lo, hi in AGE_BANDS:
        if lo <= age < hi:
            return (lo, hi)
    return AGE_BANDS[-1]  # 75–80 fallback for top-coded 80


def bucket_key(age_lo: int, age_hi: int, sex_male: int) -> str:
    """Stringified bucket id used as a JSON key."""
    return f"{age_lo}-{age_hi - 1}_{int(sex_male)}"


def main() -> int:
    print("loading Cox model …")
    model = joblib.load(MODELS_DIR / "cox_model.pkl")
    print(f"  {len(model.coef_)} coefficients")

    X_path = DATA_DIR / "X_gh.csv"
    print(f"loading training cohort {X_path.name} …")
    X_full = pd.read_csv(X_path)
    print(f"  {len(X_full):,} subjects")

    # Strict column subset — predict on exactly the model's feature set.
    X = X_full[list(FEATURES)].astype(float)

    print(f"predicting raw 2-yr risk for the cohort …")
    surv_funcs = model.predict_survival_function(X)
    risks = np.array([1.0 - sf(float(HORIZON_MONTHS)) for sf in surv_funcs])
    print(f"  raw risk range: [{risks.min() * 100:.4f}%, {risks.max() * 100:.4f}%]\n")

    lookup: dict[str, list[float]] = {}
    rows: list[dict] = []
    for age_lo, age_hi in AGE_BANDS:
        for sex_male in (0, 1):
            mask = (
                (X_full["age"] >= age_lo)
                & (X_full["age"] < age_hi)
                & (X_full["sex_male"] == sex_male)
            )
            bucket = sorted(risks[mask].tolist())
            key = bucket_key(age_lo, age_hi, sex_male)
            lookup[key] = bucket
            rows.append({
                "bucket": key,
                "n": len(bucket),
                "p10": float(np.percentile(bucket, 10)) if bucket else None,
                "p50": float(np.percentile(bucket, 50)) if bucket else None,
                "p90": float(np.percentile(bucket, 90)) if bucket else None,
            })

    # Pooled cohort — used by the hybrid score for cross-age context.
    lookup["__pool__"] = sorted(risks.tolist())

    OUTPUT_PATH.write_text(json.dumps(lookup) + "\n")  # compact (no indent — file size matters less than read speed but no point pretty-printing 8k floats)
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"wrote {OUTPUT_PATH.relative_to(INSPECT_DIR.parent.parent)}  ({size_kb:.1f} KB)\n")

    print("─── bucket summary (n + p10/p50/p90 of raw risk × 100, %) ────────")
    df = pd.DataFrame(rows)
    df["p10_pct"] = df["p10"] * 100
    df["p50_pct"] = df["p50"] * 100
    df["p90_pct"] = df["p90"] * 100
    print(df[["bucket", "n", "p10_pct", "p50_pct", "p90_pct"]].to_string(
        index=False, float_format=lambda v: f"{v:.3f}"
    ))
    print()
    print(f"total subjects across buckets: {df['n'].sum():,}")
    print(f"smallest bucket:               {df['n'].min()}")
    print(f"largest bucket:                {df['n'].max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
