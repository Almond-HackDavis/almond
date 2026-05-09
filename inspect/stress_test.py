"""Stress-test the Cox model + hybrid vitality formula across personas.

Generates a wide grid of synthetic personas covering age × sex × lifestyle,
plus targeted edge cases. For each persona it computes:

    raw_2yr_risk_pct     — direct Cox prediction
    vitality_hybrid      — current 60/40 hybrid (the new live formula)
    vitality_pure_abs    — for diagnostics: 100 × (1 − raw_risk)
    vitality_pure_peer   — for diagnostics: 100 × (1 − bucket_pct/100)

It then checks two intuitive monotonicity invariants and reports any
violations:

    A. Within the SAME age + sex, a lifestyle ranked "elite" must outscore
       "healthy_avg" must outscore "sedentary" must outscore "frail".

    B. Across age, holding lifestyle fixed at "healthy_avg", a younger
       person must outscore an older person.

Usage:

    inspect/.venv/bin/python inspect/stress_test.py

Exit code is the number of violations across both invariants (so the
script can be wired into CI later — `./stress_test.py` returns 0 iff the
model still produces intuitive orderings).
"""
from __future__ import annotations

import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import numpy as np
import pandas as pd

INSPECT = Path(__file__).resolve().parent
_g = SourceFileLoader("g02", str(INSPECT / "02_gemini.py")).load_module()

FEATURES = _g.FEATURES
BMI_OPTIMUM = _g.BMI_OPTIMUM
SLEEP_OPTIMUM_MIN = _g.SLEEP_OPTIMUM_MIN
HORIZON_MONTHS = _g.HORIZON_MONTHS

model, _ = _g.load_cox()
lookup = _g.load_percentile_lookup()


# ── Persona grid ────────────────────────────────────────────────────────────

# Lifestyle profiles map directly to the 5 model features. `bmi` and
# `mean_sleep_min` are the human-readable versions; we apply the J-shape
# transform inline before predicting.
LIFESTYLE_PROFILES = {
    "elite":       dict(bmi=22.0, mean_daily_mims=5_000_000, mean_sleep_min=480),
    "healthy_avg": dict(bmi=24.0, mean_daily_mims=3_500_000, mean_sleep_min=445),
    "sedentary":   dict(bmi=30.0, mean_daily_mims=1_800_000, mean_sleep_min=400),
    "frail":       dict(bmi=20.0, mean_daily_mims=  600_000, mean_sleep_min=550),
}

LIFESTYLE_RANK = {"elite": 0, "healthy_avg": 1, "sedentary": 2, "frail": 3}

AGES = (22, 28, 35, 45, 55, 65, 75)
SEXES = (("F", 0), ("M", 1))


def features_from_profile(age: float, sex_male: int, profile: dict) -> dict:
    return {
        "age":             float(age),
        "sex_male":        float(sex_male),
        "bmi_dev":         abs(profile["bmi"] - BMI_OPTIMUM),
        "sleep_dev":       abs(profile["mean_sleep_min"] - SLEEP_OPTIMUM_MIN),
        "mean_daily_mims": float(profile["mean_daily_mims"]),
    }


def predict_raw(feats: dict) -> float:
    X = pd.DataFrame([{f: float(feats[f]) for f in FEATURES}], columns=list(FEATURES))
    sf = model.predict_survival_function(X)[0]
    return float(1.0 - sf(float(HORIZON_MONTHS)))


def vitality_hybrid(raw_risk: float, age: float, sex_male: float, mean_daily_mims: float) -> float:
    return _g.vitality_from_percentile(raw_risk, age, sex_male, lookup,
                                        mean_daily_mims=mean_daily_mims)


def vitality_pure_abs(raw_risk: float) -> float:
    return float(max(0.0, min(100.0, 100.0 * (1.0 - raw_risk))))


def vitality_pure_peer(raw_risk: float, age: float, sex_male: float) -> float:
    bucket = lookup.get(_g._bucket_key(age, sex_male))
    if not bucket:
        return vitality_pure_abs(raw_risk)
    pct = float(np.searchsorted(bucket, raw_risk, side="right")) / len(bucket)
    return float(max(0.0, min(100.0, 100.0 * (1.0 - pct))))


# ── Build the persona table ─────────────────────────────────────────────────


def build_grid() -> list[dict]:
    personas: list[dict] = []
    for age in AGES:
        for sex_label, sex_male in SEXES:
            for ls_name, profile in LIFESTYLE_PROFILES.items():
                feats = features_from_profile(age, sex_male, profile)
                raw = predict_raw(feats)
                personas.append({
                    "id":         f"{age}{sex_label}_{ls_name}",
                    "age":        age,
                    "sex":        sex_label,
                    "sex_male":   sex_male,
                    "lifestyle":  ls_name,
                    "bmi":        profile["bmi"],
                    "mims":       profile["mean_daily_mims"],
                    "sleep_min":  profile["mean_sleep_min"],
                    "raw_2yr_pct": raw * 100,
                    "v_hybrid":   vitality_hybrid(raw, age, sex_male, profile["mean_daily_mims"]),
                    "v_abs":      vitality_pure_abs(raw),
                    "v_peer":     vitality_pure_peer(raw, age, sex_male),
                })

    # Targeted edge cases.
    edges = [
        ("25F_anorexic_athlete",   25, "F", 0, dict(bmi=16.0, mean_daily_mims=5_500_000, mean_sleep_min=420)),
        ("80M_obese_high_mims",    80, "M", 1, dict(bmi=35.0, mean_daily_mims=4_000_000, mean_sleep_min=450)),
        ("60F_elite_endurance",    60, "F", 0, dict(bmi=22.0, mean_daily_mims=5_200_000, mean_sleep_min=490)),
        ("30M_borderline_high_mims", 30, "M", 1, dict(bmi=28.0, mean_daily_mims=4_500_000, mean_sleep_min=440)),
        ("22F_obese_sedentary",    22, "F", 0, dict(bmi=32.0, mean_daily_mims=1_500_000, mean_sleep_min=380)),
        ("45F_diabetic_sedentary", 45, "F", 0, dict(bmi=33.0, mean_daily_mims=1_200_000, mean_sleep_min=380)),
    ]
    for pid, age, sex_label, sex_male, profile in edges:
        feats = features_from_profile(age, sex_male, profile)
        raw = predict_raw(feats)
        personas.append({
            "id":         pid,
            "age":        age,
            "sex":        sex_label,
            "sex_male":   sex_male,
            "lifestyle":  "edge",
            "bmi":        profile["bmi"],
            "mims":       profile["mean_daily_mims"],
            "sleep_min":  profile["mean_sleep_min"],
            "raw_2yr_pct": raw * 100,
            "v_hybrid":   vitality_hybrid(raw, age, sex_male, profile["mean_daily_mims"]),
            "v_abs":      vitality_pure_abs(raw),
            "v_peer":     vitality_pure_peer(raw, age, sex_male),
        })
    return personas


# ── Invariant checks ────────────────────────────────────────────────────────


def check_within_age_lifestyle(grid: list[dict]) -> list[str]:
    """For each (age, sex), elite > healthy_avg > sedentary > frail by v_hybrid."""
    violations: list[str] = []
    by_demo: dict[tuple[int, int], dict[str, dict]] = {}
    for p in grid:
        if p["lifestyle"] == "edge":
            continue
        by_demo.setdefault((p["age"], p["sex_male"]), {})[p["lifestyle"]] = p

    expected = ["elite", "healthy_avg", "sedentary", "frail"]
    for (age, sex_male), profiles in sorted(by_demo.items()):
        scores = [profiles[l]["v_hybrid"] for l in expected if l in profiles]
        names  = [l for l in expected if l in profiles]
        for i in range(len(scores) - 1):
            if scores[i] < scores[i + 1]:
                violations.append(
                    f"WITHIN_AGE  age={age} sex={'M' if sex_male else 'F'}  "
                    f"{names[i]}={scores[i]:.2f} < {names[i+1]}={scores[i+1]:.2f}  "
                    f"(should be the other way around)"
                )
    return violations


def check_across_age_healthy(grid: list[dict]) -> list[str]:
    """Holding lifestyle=healthy_avg, a younger person should score higher."""
    violations: list[str] = []
    by_sex: dict[int, list[dict]] = {0: [], 1: []}
    for p in grid:
        if p["lifestyle"] == "healthy_avg":
            by_sex[p["sex_male"]].append(p)
    for sex_male, ppl in by_sex.items():
        ppl_sorted = sorted(ppl, key=lambda p: p["age"])
        for i in range(len(ppl_sorted) - 1):
            young, older = ppl_sorted[i], ppl_sorted[i + 1]
            if young["v_hybrid"] < older["v_hybrid"]:
                violations.append(
                    f"ACROSS_AGE  sex={'M' if sex_male else 'F'}  "
                    f"{young['age']}yr={young['v_hybrid']:.2f} < "
                    f"{older['age']}yr={older['v_hybrid']:.2f}  "
                    f"(younger should score higher with the same lifestyle)"
                )
    return violations


def check_user_complaint(grid: list[dict]) -> list[str]:
    """The headline UX failure: 32yo healthy M should beat 65yo sedentary F."""
    violations: list[str] = []
    by_id = {p["id"]: p for p in grid}
    a_id = next((pid for pid in by_id if pid.startswith("35M_") and "healthy_avg" in pid), None) \
        or next((pid for pid in by_id if pid.startswith("28M_") and "healthy_avg" in pid), None)
    b_id = next((pid for pid in by_id if pid.startswith("65F_") and "sedentary" in pid), None)
    if a_id and b_id:
        a, b = by_id[a_id], by_id[b_id]
        if a["v_hybrid"] < b["v_hybrid"]:
            violations.append(
                f"USER_COMPLAINT  {a['id']}({a['v_hybrid']:.2f}) < {b['id']}({b['v_hybrid']:.2f})  "
                f"— healthy young man should outscore sedentary older woman."
            )
    return violations


# ── Driver ──────────────────────────────────────────────────────────────────


def main() -> int:
    grid = build_grid()
    df = pd.DataFrame(grid).sort_values("raw_2yr_pct").reset_index(drop=True)

    print()
    print("=" * 100)
    print("  ALMOND COX + HYBRID VITALITY  STRESS TEST")
    print("=" * 100)
    print(f"  personas: {len(df)}  (grid {len(AGES)}×{len(SEXES)}×{len(LIFESTYLE_PROFILES)} + edge cases)")
    print()
    cols = ["id", "age", "sex", "lifestyle", "bmi", "raw_2yr_pct", "v_hybrid", "v_abs", "v_peer"]
    print(df[cols].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print()

    violations: list[str] = []
    violations += check_user_complaint(grid)
    violations += check_within_age_lifestyle(grid)
    violations += check_across_age_healthy(grid)

    print("=" * 100)
    if violations:
        print(f"  ❌ {len(violations)} VIOLATION(S) — model NOT yet intuitive")
        print("=" * 100)
        for v in violations:
            print(f"  • {v}")
        print()
    else:
        print("  ✅ ALL INVARIANTS HOLD — model produces intuitive orderings")
        print("=" * 100)
        print()

    # Persist a CSV regression fixture next to the model.
    out_csv = INSPECT / "stress_test_results.csv"
    df.to_csv(out_csv, index=False)
    print(f"  wrote {out_csv.relative_to(INSPECT.parent)}  ({len(df)} rows)")
    print()
    return len(violations)


if __name__ == "__main__":
    sys.exit(main())
