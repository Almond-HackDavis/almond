"""Phase 1 · Step 1D — train + validate + persist the 8-feature Cox model.

Reads inspect/data/X_gh.csv and y_gh.csv (from 1C). Runs:

  1. Stratified 75/25 train/test split on the 24-month event indicator.
  2. CoxPHSurvivalAnalysis(alpha=1e-4) fit on train.
  3. Validation:
        - Harrell's C-index on test
        - 200-rep bootstrap SE on C-index
        - 24-month ROC-AUC (binary "died within 2 yrs" classifier)
        - Per-decile calibration table (predicted risk vs observed event rate)
  4. Persists cox_model.pkl, feature_means.json, validation_report.json
     to inspect/models/.
  5. Smoke check: reload pkl, predict on the first test row, assert equal.

The DoD bar is Harrell C ≥ 0.70 on the held-out test split.

Deliberately avoids `cumulative_dynamic_auc` and `integrated_brier_score`
because both call `np.trapz`, which numpy 2.x removed (renamed to
`np.trapezoid`). scikit-survival 0.25.0 still calls the old name and
crashes on a numpy-2 install — this script computes equivalent metrics
manually so it runs against the latest library versions.

Run:

    inspect/.venv/bin/python inspect/01d_train.py

If imports fail, install with:

    inspect/.venv/bin/python -m pip install -U scikit-survival scikit-learn joblib

(or `uv pip install -U scikit-survival scikit-learn joblib` from inspect/.)
"""
from __future__ import annotations

import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored
from sksurv.util import Surv

# Reuse 1C's locked feature order so the saved model coefs are aligned to
# the same column order the inference code will eventually expect.
_c = SourceFileLoader(
    "c01", str(Path(__file__).resolve().parent / "01c_features.py")
).load_module()
FEATURES = _c.FEATURES
HORIZON_MONTHS = _c.HORIZON_MONTHS
DATA_DIR = _c.DATA_DIR

MODELS_DIR = Path(__file__).resolve().parent / "models"
SEED = 42
TEST_SIZE = 0.25
ALPHA = 1e-4           # mild L2 — avoids alpha=0 instability on collinear X
N_BOOTSTRAP = 200
DOD_C_INDEX = 0.70


# ── Load + split ─────────────────────────────────────────────────────────────

def load_xy() -> tuple[pd.DataFrame, np.ndarray]:
    X = pd.read_csv(DATA_DIR / "X_gh.csv")[list(FEATURES)].astype(float)

    y_df = pd.read_csv(DATA_DIR / "y_gh.csv")
    # CSV roundtripping can turn the bool event column into "True"/"False"
    # strings — coerce defensively.
    if y_df["event"].dtype == object:
        y_df["event"] = y_df["event"].astype(str).str.lower().eq("true")
    y = Surv.from_arrays(
        event=y_df["event"].astype(bool).to_numpy(),
        time=y_df["time"].astype(float).to_numpy(),
    )
    return X, y


def split(X: pd.DataFrame, y: np.ndarray):
    return train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=SEED,
        stratify=y["event"].astype(int),
    )


# ── Validation ───────────────────────────────────────────────────────────────

def harrell_c_with_se(model, X_test, y_test) -> tuple[float, float, np.ndarray]:
    """Harrell's C on test + bootstrap SE."""
    risk = model.predict(X_test)               # linear predictor; higher = higher hazard
    c_idx, _, _, _, _ = concordance_index_censored(
        y_test["event"], y_test["time"], risk
    )

    rng = np.random.default_rng(seed=0)
    boot = np.empty(N_BOOTSTRAP)
    n = len(y_test)
    for i in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, n)
        boot[i], _, _, _, _ = concordance_index_censored(
            y_test["event"][idx], y_test["time"][idx], risk[idx]
        )
    return float(c_idx), float(boot.std(ddof=1)), risk


def auc_at_horizon(model, X_test, y_test) -> float:
    """Binary classifier AUC for 'died within HORIZON_MONTHS' on the test set.

    Cleaner than `cumulative_dynamic_auc` for a fixed-horizon problem AND
    avoids the np.trapz issue in sksurv 0.25 + numpy 2.x.
    """
    surv_funcs = model.predict_survival_function(X_test)
    risk_at_horizon = np.array([1.0 - fn(float(HORIZON_MONTHS)) for fn in surv_funcs])
    # With our 1C horizon clip, every test subject either has time<=24+event=True
    # or time==24+event=False — so y_test['event'] is exactly the binary label.
    return float(roc_auc_score(y_test["event"], risk_at_horizon))


def calibration_deciles(model, X_test, y_test, n_buckets: int = 10) -> pd.DataFrame:
    """Per-decile predicted vs observed event rate within the horizon."""
    surv_funcs = model.predict_survival_function(X_test)
    risk_at_horizon = np.array([1.0 - fn(float(HORIZON_MONTHS)) for fn in surv_funcs])
    df = pd.DataFrame({
        "predicted_p": risk_at_horizon,
        "event":       y_test["event"].astype(int),
    })
    df["decile"] = pd.qcut(df["predicted_p"], q=n_buckets, labels=False, duplicates="drop")
    cal = (
        df.groupby("decile")
        .agg(n=("event", "size"),
             predicted_mean=("predicted_p", "mean"),
             observed_rate=("event", "mean"))
        .reset_index()
    )
    return cal


# ── Persist ──────────────────────────────────────────────────────────────────

def persist(model, X_train, c_idx, c_se, auc_h, calibration, n_train, n_test,
            n_ev_train, n_ev_test) -> dict:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    pkl_path = MODELS_DIR / "cox_model.pkl"
    means_path = MODELS_DIR / "feature_means.json"
    report_path = MODELS_DIR / "validation_report.json"

    joblib.dump(model, pkl_path)

    means = {col: float(X_train[col].mean()) for col in FEATURES}
    means_path.write_text(json.dumps(means, indent=2, sort_keys=True) + "\n")

    report = {
        "horizon_months":  HORIZON_MONTHS,
        "n_train":         int(n_train),
        "n_test":          int(n_test),
        "n_events_train":  int(n_ev_train),
        "n_events_test":   int(n_ev_test),
        "concordance":     c_idx,
        "concordance_se":  c_se,
        "auc_at_horizon":  auc_h,
        "passes_dod":      bool(c_idx >= DOD_C_INDEX),
        "dod_threshold":   DOD_C_INDEX,
        "coefficients": [
            {"feature": f, "beta": float(b), "hazard_ratio_per_unit": float(np.exp(b))}
            for f, b in zip(FEATURES, model.coef_)
        ],
        "calibration": calibration.to_dict(orient="records"),
        "training": {
            "alpha":           ALPHA,
            "test_size":       TEST_SIZE,
            "random_state":    SEED,
            "n_bootstrap_se":  N_BOOTSTRAP,
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    return {"pkl": pkl_path, "means": means_path, "report": report_path}


def smoke_check_pkl(model, X_test, pkl_path: Path) -> tuple[float, float]:
    """Load pkl, predict on first test row, return (before, after) for compare."""
    before = float(model.predict(X_test.iloc[:1])[0])
    loaded = joblib.load(pkl_path)
    after = float(loaded.predict(X_test.iloc[:1])[0])
    return before, after


# ── Verification ─────────────────────────────────────────────────────────────

def main() -> None:
    X, y = load_xy()
    X_train, X_test, y_train, y_test = split(X, y)

    print(f"train: {len(X_train):,} rows ({int(y_train['event'].sum()):,} events)")
    print(f"test:  {len(X_test):,} rows ({int(y_test['event'].sum()):,} events)")
    print()

    print(f"fitting CoxPHSurvivalAnalysis(alpha={ALPHA}) …")
    model = CoxPHSurvivalAnalysis(alpha=ALPHA)
    model.fit(X_train, y_train)
    print("  fit complete.")
    print()

    print("validating …")
    c_idx, c_se, _risk = harrell_c_with_se(model, X_test, y_test)
    auc_h = auc_at_horizon(model, X_test, y_test)
    cal = calibration_deciles(model, X_test, y_test)
    print(f"  Harrell C-index : {c_idx:.4f}  (bootstrap SE {c_se:.4f})")
    print(f"  AUC @ 24 months : {auc_h:.4f}")
    print()

    coefs = pd.DataFrame({
        "feature": FEATURES,
        "beta":    [float(b) for b in model.coef_],
        "HR/unit": [float(np.exp(b)) for b in model.coef_],
    })
    print("coefficients (signs to sanity-check):")
    print(coefs.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
    print()

    print("decile calibration (predicted_mean ≈ observed_rate is the goal):")
    print(cal.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()

    paths = persist(
        model, X_train, c_idx, c_se, auc_h, cal,
        n_train=len(X_train), n_test=len(X_test),
        n_ev_train=int(y_train["event"].sum()),
        n_ev_test=int(y_test["event"].sum()),
    )

    before, after = smoke_check_pkl(model, X_test, paths["pkl"])
    print("smoke check: reload pkl + predict first test row")
    print(f"  pre-save  prediction: {before:+.6f}")
    print(f"  post-load prediction: {after:+.6f}")
    print(f"  identical:            {before == after}")
    print()

    print("─── 1D summary ────────────────────────────────────────────────")
    pass_mark = "✅" if c_idx >= DOD_C_INDEX else "❌"
    print(f"  Harrell C : {c_idx:.4f} ± {c_se:.4f}   "
          f"{pass_mark}  DoD threshold {DOD_C_INDEX}")
    print(f"  AUC @ 24mo: {auc_h:.4f}")
    print(f"  Pkl reload: {'OK' if before == after else 'FAIL'}")
    print()
    for k, p in paths.items():
        print(f"  wrote {k:>6}: {p.relative_to(MODELS_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
