"""Visual stress grid for the Cox + augmentation pipeline.

Runs a wide matrix of synthetic personas through `ml.run_pipeline` and prints
a human-readable table so you can eyeball whether the scoring is intuitive
across ages, sexes, lifestyles, and tier-2 signal combinations.

Three invariant checks at the end:
  A. WITHIN-AGE lifestyle ordering: elite > healthy > sedentary > frail
  B. ACROSS-AGE monotonicity: same lifestyle, younger > older
  C. HEADLINE: 32yo M healthy outscores 65yo F diabetic-sedentary by >= 20 pts

Run:

    cd almond-ml
    .venv/bin/python stress_grid.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))  # make imports work from any cwd

import ml


# ── Persona construction ────────────────────────────────────────────────────

# Each lifestyle bundle is "a version of a Tier-1 lifestyle + typical tier-2
# signals for that lifestyle." That lets us make fair apples-to-apples
# comparisons within a given age × sex cell.
LIFESTYLE_BUNDLES = {
    "elite":       dict(steps=12500, kcal=650, excm=60, sleep=465,
                        rhr=50,  hrv=85, vo2=55, walking_hr=90),
    "healthy_avg": dict(steps=8500,  kcal=450, excm=30, sleep=455,
                        rhr=62,  hrv=55, vo2=38, walking_hr=105),
    "sedentary":   dict(steps=3500,  kcal=200, excm=8,  sleep=420,
                        rhr=74,  hrv=32, vo2=24, walking_hr=120),
    "frail":       dict(steps=1500,  kcal=100, excm=2,  sleep=540,
                        rhr=80,  hrv=22, vo2=18, walking_hr=130),
}

AGES = (22, 28, 35, 45, 55, 65, 75)
SEXES = (("F", 0), ("M", 1))


def _onboarding(age: int, sex: str, weight: float = 75.0, height: float = 178.0) -> dict:
    return {
        "age": age, "sex": sex,
        "height_cm": height, "weight_kg": weight,
        "smoking": False, "diabetes": False,
        "family_history_cvd": False, "on_bp_medication": False,
        "race_ethnicity": None, "systolic_bp": None,
        "total_cholesterol": None, "hdl_cholesterol": None,
    }


def _samples(**b: Any) -> dict:
    s: dict[str, Any] = {
        "steps_daily":              [{"date": "2026-05-08", "count":   b["steps"]}],
        "active_energy_daily_kcal": [{"date": "2026-05-08", "kcal":    b["kcal"]}],
        "exercise_minutes_daily":   [{"date": "2026-05-08", "minutes": b["excm"]}],
        "sleep_sessions":           [{"start":"x","end":"y","duration_min": b["sleep"]}],
    }
    if b.get("rhr") is not None:
        s["resting_hr_daily"] = [{"date": "2026-05-08", "bpm": b["rhr"]}]
    if b.get("hrv") is not None:
        s["hrv_sdnn"] = [{"timestamp": "2026-05-08T03:00:00Z", "ms": b["hrv"]}]
    if b.get("vo2") is not None:
        s["vo2_max_latest"] = {"value": b["vo2"], "measured_at": "2026-05-08T11:00:00Z"}
    if b.get("walking_hr") is not None:
        s["walking_hr_avg_daily"] = [{"date": "2026-05-08", "bpm": b["walking_hr"]}]
    return s


def run_one(age: int, sex: str, lifestyle: str) -> dict:
    bundle = LIFESTYLE_BUNDLES[lifestyle]
    out = ml.run_pipeline(_onboarding(age, sex), _samples(**bundle))
    fa = out.get("fitness_age")
    return {
        "age": age,
        "sex": sex,
        "lifestyle": lifestyle,
        "raw_2yr_pct": out["raw_2yr_mortality"] * 100,
        "vitality": out["vitality"],
        "composite_bonus": out["composite_bonus"],
        "fitness_age": fa["value"] if fa else None,
        "fitness_delta": fa["delta"] if fa else None,
        "top1": out["top_drivers"][0]["feature"] if out["top_drivers"] else None,
    }


# ── Main table ──────────────────────────────────────────────────────────────


def main() -> int:
    rows = []
    for age in AGES:
        for sex, _ in SEXES:
            for lifestyle in LIFESTYLE_BUNDLES:
                rows.append(run_one(age, sex, lifestyle))

    # Edge-case personas (tier-2 skewed).
    edge_cases = [
        ("25F anorexic-athlete (BMI 16)", {"age": 25, "sex": "F", "weight": 45, "height": 165},
         dict(steps=15000, kcal=700, excm=70, sleep=480, rhr=45, hrv=95, vo2=55, walking_hr=85)),
        ("30M weekend warrior",           {"age": 30, "sex": "M"},
         dict(steps=11000, kcal=550, excm=50, sleep=430, rhr=55, hrv=65, vo2=48, walking_hr=95)),
        ("45F post-diagnosis sedentary",  {"age": 45, "sex": "F", "weight": 95, "height": 162},
         dict(steps=2500, kcal=150, excm=5, sleep=380, rhr=82, hrv=22, vo2=19, walking_hr=128)),
        ("60M desk-bound exec",           {"age": 60, "sex": "M", "weight": 92, "height": 178},
         dict(steps=4000, kcal=220, excm=10, sleep=420, rhr=72, hrv=32, vo2=28, walking_hr=118)),
        ("70F elite endurance",           {"age": 70, "sex": "F"},
         dict(steps=13000, kcal=600, excm=70, sleep=470, rhr=52, hrv=75, vo2=40, walking_hr=92)),
        ("22M couch potato no tier-2",    {"age": 22, "sex": "M", "weight": 95, "height": 175},
         dict(steps=2000, kcal=100, excm=3, sleep=380)),   # no RHR / HRV / VO2 / walking_hr
        ("40F first-day Apple Watch",     {"age": 40, "sex": "F"},
         dict(steps=7000, kcal=350, excm=25, sleep=450)),  # no tier-2
    ]

    edges = []
    for label, persona, bundle in edge_cases:
        out = ml.run_pipeline(_onboarding(**persona), _samples(**bundle))
        fa = out.get("fitness_age")
        edges.append({
            "label": label,
            "age": persona["age"],
            "sex": persona["sex"],
            "raw_2yr_pct": out["raw_2yr_mortality"] * 100,
            "vitality": out["vitality"],
            "composite_bonus": out["composite_bonus"],
            "fitness_age": fa["value"] if fa else None,
            "fitness_delta": fa["delta"] if fa else None,
            "top1": out["top_drivers"][0]["feature"] if out["top_drivers"] else None,
        })

    # ── Print table ─────────────────────────────────────────────────────────

    print()
    print("═" * 108)
    print("  ALMOND COX + HEALTHKIT-AUGMENTATION STRESS GRID")
    print("═" * 108)
    print()
    print(f"{'age':>3} {'sex':>3} {'lifestyle':<14} | "
          f"{'raw%':>6} {'bonus':>6} {'vitality':>9} | "
          f"{'fit_age':>7} {'Δyr':>5} | top driver")
    print("─" * 108)
    for r in rows:
        fa_str    = f"{r['fitness_age']:>7.1f}" if r["fitness_age"] is not None else "     — "
        delta_str = f"{r['fitness_delta']:>+5.1f}" if r["fitness_delta"] is not None else "    —"
        print(f"{r['age']:>3} {r['sex']:>3} {r['lifestyle']:<14} | "
              f"{r['raw_2yr_pct']:>5.2f}% {r['composite_bonus']:>+6.2f} {r['vitality']:>9.1f} | "
              f"{fa_str} {delta_str} | {r['top1']}")

    print()
    print("─── edge cases ──────────────────────────────────────────────────────────────────────────")
    for e in edges:
        fa_str    = f"{e['fitness_age']:>7.1f}" if e["fitness_age"] is not None else "     — "
        delta_str = f"{e['fitness_delta']:>+5.1f}" if e["fitness_delta"] is not None else "    —"
        print(f"{e['label']:<34s} age={e['age']:<3} sex={e['sex']} | "
              f"{e['raw_2yr_pct']:>5.2f}% {e['composite_bonus']:>+6.2f} {e['vitality']:>6.1f} | "
              f"{fa_str} {delta_str} | {e['top1']}")

    # ── Invariant checks ────────────────────────────────────────────────────

    violations: list[str] = []

    # A. WITHIN-AGE: elite > healthy_avg > sedentary > frail
    order = ["elite", "healthy_avg", "sedentary", "frail"]
    by_cell: dict[tuple, dict[str, float]] = {}
    for r in rows:
        by_cell.setdefault((r["age"], r["sex"]), {})[r["lifestyle"]] = r["vitality"]
    for (age, sex), cell in by_cell.items():
        scores = [cell[l] for l in order if l in cell]
        for i in range(len(scores) - 1):
            if scores[i] < scores[i + 1]:
                violations.append(
                    f"WITHIN_AGE age={age} sex={sex}: {order[i]}={scores[i]:.1f} < {order[i+1]}={scores[i+1]:.1f}"
                )

    # B. ACROSS-AGE: healthy_avg, younger > older (per sex)
    for sex, _ in SEXES:
        by_age = sorted([(r["age"], r["vitality"]) for r in rows
                         if r["lifestyle"] == "healthy_avg" and r["sex"] == sex])
        for i in range(len(by_age) - 1):
            (a1, v1), (a2, v2) = by_age[i], by_age[i + 1]
            if v1 < v2:
                violations.append(f"ACROSS_AGE sex={sex}: age {a1}={v1:.1f} < age {a2}={v2:.1f}")

    # C. HEADLINE: 32yo M healthy > 65yo F diabetic-sedentary by >= 20 pts
    head_young = [r for r in rows if r["age"] == 35 and r["sex"] == "M" and r["lifestyle"] == "healthy_avg"][0]
    head_old   = [r for r in rows if r["age"] == 65 and r["sex"] == "F" and r["lifestyle"] == "sedentary"][0]
    delta = head_young["vitality"] - head_old["vitality"]
    if delta < 20:
        violations.append(f"HEADLINE: 35M healthy={head_young['vitality']:.1f} "
                          f"vs 65F sedentary={head_old['vitality']:.1f} → only Δ={delta:.1f} (need ≥ 20)")

    # ── Verdict ─────────────────────────────────────────────────────────────
    print()
    print("═" * 108)
    if violations:
        print(f"  ❌ {len(violations)} INVARIANT VIOLATION(S)")
        print("═" * 108)
        for v in violations:
            print(f"  • {v}")
    else:
        print("  ✅ ALL INVARIANTS HOLD")
        print(f"  • within-age lifestyle ordering: {len(by_cell)} cells × 3 pairs each — all consistent")
        print(f"  • across-age monotonicity:       healthy_avg progression clean for both sexes")
        print(f"  • headline delta:                35M healthy − 65F sedentary = {delta:.1f} pts")
        print("═" * 108)
    print()
    return len(violations)


if __name__ == "__main__":
    sys.exit(main())
