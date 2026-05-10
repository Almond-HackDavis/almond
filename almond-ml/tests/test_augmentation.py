"""Comprehensive stress test for the HealthKit-augmentation layer.

Three monotonicity invariants the model must respect across the full grid
of synthetic personas:

  A. WITHIN-PERSON LIFT — for the same demographics + tier-1 lifestyle, a
     better tier-2 signal (lower RHR, higher HRV, higher VO2, lower walking HR)
     must produce a higher vitality score.

  B. ACROSS-AGE — a younger person with the same lifestyle outscores an
     older person, regardless of which augmentation signals are present.

  C. HEADLINE REGRESSION — a healthy 32yo M outscores a 65yo F with diabetes
     by ≥ 20 vitality points (the original UX fix from PR #5).

Plus extremum spot-checks: anorexic athlete, frail elderly with high VO2,
elite endurance athlete with low resting HR, sedentary middle-aged with
poor everything, and a no-tier-2-signals "first-day Apple Watch user" case.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest

import ml


# ── Helpers to build payloads ───────────────────────────────────────────────


def _onboarding(age: int = 35, sex: str = "M", weight: float = 75.0, height: float = 178.0) -> dict:
    return {
        "age": age, "sex": sex,
        "height_cm": height, "weight_kg": weight,
        "smoking": False, "diabetes": False,
        "family_history_cvd": False, "on_bp_medication": False,
        "race_ethnicity": None, "systolic_bp": None,
        "total_cholesterol": None, "hdl_cholesterol": None,
    }


def _samples(*, steps: int = 8000, kcal: int = 400, excm: int = 30, sleep_min: int = 460,
             rhr: Optional[float] = None, hrv: Optional[float] = None,
             vo2: Optional[float] = None, walking_hr: Optional[float] = None) -> dict:
    out: dict[str, Any] = {
        "steps_daily":              [{"date": "2026-05-08", "count": steps}],
        "active_energy_daily_kcal": [{"date": "2026-05-08", "kcal": kcal}],
        "exercise_minutes_daily":   [{"date": "2026-05-08", "minutes": excm}],
        "sleep_sessions":           [{"start": "x", "end": "y", "duration_min": sleep_min}],
    }
    if rhr is not None:
        out["resting_hr_daily"] = [{"date": "2026-05-08", "bpm": rhr}]
    if hrv is not None:
        out["hrv_sdnn"] = [{"timestamp": "2026-05-08T03:00:00Z", "ms": hrv}]
    if vo2 is not None:
        out["vo2_max_latest"] = {"value": vo2, "measured_at": "2026-05-08T11:00:00Z"}
    if walking_hr is not None:
        out["walking_hr_avg_daily"] = [{"date": "2026-05-08", "bpm": walking_hr}]
    return out


def _vitality(persona_kwargs: dict, sample_kwargs: dict) -> float:
    return ml.run_pipeline(_onboarding(**persona_kwargs), _samples(**sample_kwargs))["vitality"]


# ── A. Within-person lift: each signal monotonically helps when better ─────


class TestWithinPersonMonotonicity:

    def test_lower_resting_hr_lifts_score(self):
        """Same person, RHR 50 (athletic) should beat RHR 80 (poor)."""
        better = _vitality({"age": 35}, {"rhr": 50})
        worse  = _vitality({"age": 35}, {"rhr": 80})
        assert better > worse + 1.0, f"RHR 50 ({better}) should beat RHR 80 ({worse})"

    def test_higher_hrv_lifts_score(self):
        better = _vitality({"age": 35}, {"hrv": 90})
        worse  = _vitality({"age": 35}, {"hrv": 25})
        assert better > worse + 1.0

    def test_higher_vo2_lifts_score(self):
        better = _vitality({"age": 35, "sex": "M"}, {"vo2": 55})
        worse  = _vitality({"age": 35, "sex": "M"}, {"vo2": 25})
        assert better > worse + 2.0

    def test_lower_walking_hr_lifts_score(self):
        better = _vitality({"age": 35}, {"walking_hr": 90})
        worse  = _vitality({"age": 35}, {"walking_hr": 130})
        # walking_hr has the smallest weight (0.05), so the gap is small but
        # must still be in the right direction.
        assert better > worse, f"low walking_hr ({better}) should beat high ({worse})"

    def test_all_signals_better_means_higher_score(self):
        better = _vitality({"age": 35}, dict(rhr=50, hrv=90, vo2=55, walking_hr=90, steps=12000, kcal=600, excm=60))
        worse  = _vitality({"age": 35}, dict(rhr=80, hrv=25, vo2=25, walking_hr=130, steps=2000, kcal=120, excm=5))
        assert better > worse + 10.0


# ── B. Across-age monotonicity persists with augmentation ──────────────────


class TestAcrossAgeMonotonicityWithAugmentation:

    def test_younger_outscores_older_same_aug_signals(self):
        sigs = {"rhr": 60, "hrv": 50, "vo2": 38, "walking_hr": 110}
        v25 = _vitality({"age": 25}, sigs)
        v65 = _vitality({"age": 65}, sigs)
        assert v25 > v65, f"25yo ({v25}) should beat 65yo ({v65})"

    def test_old_athlete_does_NOT_overtake_young_average(self):
        """A 70yo elite endurance athlete should still score below a young
        average person — absolute risk dominates pool percentile, augmentation
        only adds ±10 pts."""
        v_young_avg = _vitality({"age": 28}, {"rhr": 65, "hrv": 50, "vo2": 42})
        v_old_elite = _vitality({"age": 70}, {"rhr": 50, "hrv": 90, "vo2": 50, "steps": 14000, "kcal": 700, "excm": 60})
        assert v_young_avg > v_old_elite


# ── C. Headline regression preserved ───────────────────────────────────────


class TestHeadlineRegression:

    def test_32yo_healthy_M_outscores_65yo_diabetic_F_by_20pts(self):
        young = _vitality(
            {"age": 32, "sex": "M", "weight": 75, "height": 178},
            {"steps": 10000, "kcal": 500, "excm": 30, "sleep_min": 460,
             "rhr": 62, "hrv": 60, "vo2": 45, "walking_hr": 105},
        )
        old = _vitality(
            {"age": 65, "sex": "F", "weight": 85, "height": 165},
            {"steps": 2500, "kcal": 150, "excm": 5, "sleep_min": 400,
             "rhr": 78, "hrv": 28, "vo2": 22, "walking_hr": 125},
        )
        assert young > old + 20, f"young={young}, old={old}"


# ── Extremum spot-checks ───────────────────────────────────────────────────


class TestExtremums:

    def test_anorexic_25yo_athlete_with_low_RHR_still_high(self):
        """Low BMI is penalized by Cox (bmi_dev), but elite tier-2 signals
        partially offset → score should be solidly above midpoint."""
        v = _vitality(
            {"age": 25, "sex": "F", "weight": 45, "height": 165},
            dict(steps=15000, kcal=700, excm=70, sleep_min=480,
                 rhr=45, hrv=95, vo2=55, walking_hr=85),
        )
        assert v > 75, f"25yo athletic with elite signals: {v}"

    def test_frail_80yo_with_OK_VO2_low_score(self):
        """Old age dominates; even a decent VO2 can't lift the score above
        midpoint."""
        v = _vitality({"age": 80, "sex": "M"},
                      dict(rhr=70, hrv=30, vo2=25, walking_hr=120,
                           steps=4000, kcal=200, excm=15, sleep_min=380))
        assert v < 50

    def test_elite_50yo_endurance_athlete(self):
        v = _vitality({"age": 50, "sex": "M"},
                      dict(rhr=45, hrv=85, vo2=55, walking_hr=90,
                           steps=14000, kcal=800, excm=80, sleep_min=460))
        assert v > 60, f"elite 50yo athlete: {v}"

    def test_sedentary_45yo_poor_everything(self):
        v = _vitality({"age": 45, "sex": "M", "weight": 105, "height": 175},
                      dict(rhr=82, hrv=22, vo2=20, walking_hr=128,
                           steps=2000, kcal=120, excm=3, sleep_min=380))
        assert v < 40

    def test_first_day_apple_watch_user_no_tier2_signals(self):
        """User just enabled HK; no RHR / HRV / VO2 / walking_hr yet — only
        Tier-1 fields. Pipeline must NOT crash and the score should still
        be reasonable."""
        v = _vitality({"age": 35},
                      dict(steps=8000, kcal=400, excm=30, sleep_min=460))
        assert 0 < v < 100

    def test_partial_tier2_signals(self):
        """Some signals available, some missing — composite uses what's there."""
        v_only_rhr = _vitality({"age": 35}, dict(rhr=55))
        v_no_aug   = _vitality({"age": 35}, {})
        assert v_only_rhr > v_no_aug, f"having RHR=55 should help: {v_only_rhr} vs {v_no_aug}"


# ── Composite-bonus invariants (unit-level) ────────────────────────────────


class TestCompositeBonusUnit:

    def test_no_signals_returns_zero(self):
        feats = {"age": 35.0, "sex_male": 1.0,
                 "mean_daily_mims": 0.0,    # zero MIMS still counts as activity=0 wellness
                 "mean_resting_hr": None, "mean_hrv_sdnn": None,
                 "vo2_max": None, "mean_walking_hr": None}
        # Note: mean_daily_mims=0 yields wellness ≈ -1, so bonus ≈ -10.
        # To genuinely test "no signals", set mean_daily_mims to the reference.
        feats["mean_daily_mims"] = ml.MIMS_REFERENCE_M * ml.MIMS_SCALE
        bonus, contrib = ml.composite_bonus(feats)
        assert abs(bonus) < 0.5
        assert "activity" in contrib

    def test_all_signals_at_max_caps_at_range(self):
        feats = {
            "age": 35.0, "sex_male": 1.0,
            "mean_daily_mims": 8_000_000,
            "mean_resting_hr": 40,
            "mean_hrv_sdnn":   100,
            "vo2_max":         60,
            "mean_walking_hr": 80,
        }
        bonus, _ = ml.composite_bonus(feats)
        assert bonus <= ml.TOTAL_BONUS_RANGE_PT + 0.01
        assert bonus >= ml.TOTAL_BONUS_RANGE_PT * 0.85   # near the cap

    def test_all_signals_at_min_caps_at_neg_range(self):
        feats = {
            "age": 35.0, "sex_male": 1.0,
            "mean_daily_mims": 200_000,
            "mean_resting_hr": 110,
            "mean_hrv_sdnn":   12,
            "vo2_max":         12,
            "mean_walking_hr": 150,
        }
        bonus, _ = ml.composite_bonus(feats)
        assert bonus <= -ml.TOTAL_BONUS_RANGE_PT * 0.85
        assert bonus >= -ml.TOTAL_BONUS_RANGE_PT - 0.01


# ── Fitness age ────────────────────────────────────────────────────────────


class TestFitnessAge:

    def test_high_vo2_gives_younger_fitness_age(self):
        fa = ml.fitness_age(vo2_obs=55, age=40, sex_male=1.0)
        assert fa is not None
        assert fa["value"] < fa["chronological_age"]
        assert fa["delta"] < 0

    def test_low_vo2_gives_older_fitness_age(self):
        fa = ml.fitness_age(vo2_obs=22, age=40, sex_male=1.0)
        assert fa is not None
        assert fa["value"] > fa["chronological_age"]
        assert fa["delta"] > 0

    def test_at_norm_gives_same_age(self):
        # 40yo M norm: 45 - 0.35*10 = 41.5
        fa = ml.fitness_age(vo2_obs=41.5, age=40, sex_male=1.0)
        assert fa is not None
        assert abs(fa["value"] - 40.0) < 1.0

    def test_no_vo2_returns_none(self):
        assert ml.fitness_age(vo2_obs=None, age=40, sex_male=1.0) is None
        assert ml.fitness_age(vo2_obs=0, age=40, sex_male=1.0) is None

    def test_clipped_to_18_90_range(self):
        # Absurd VO2max → should clip, not blow up
        fa_low = ml.fitness_age(vo2_obs=5, age=70, sex_male=0.0)
        assert fa_low is not None and 18 <= fa_low["value"] <= 90
        fa_high = ml.fitness_age(vo2_obs=120, age=22, sex_male=1.0)
        assert fa_high is not None and 18 <= fa_high["value"] <= 90


# ── Top drivers ────────────────────────────────────────────────────────────


class TestTopDrivers:

    def test_returns_three_drivers_for_full_signal_set(self):
        out = ml.run_pipeline(_onboarding(),
                              _samples(rhr=55, hrv=70, vo2=45, walking_hr=95))
        assert len(out["top_drivers"]) == 3

    def test_drivers_have_required_fields(self):
        out = ml.run_pipeline(_onboarding(),
                              _samples(rhr=55, hrv=70, vo2=45, walking_hr=95))
        for d in out["top_drivers"]:
            for k in ("feature", "human_label", "value", "contribution_pts", "direction"):
                assert k in d
            assert d["direction"] in ("better", "worse")

    def test_drivers_ordered_by_absolute_contribution(self):
        out = ml.run_pipeline(_onboarding(),
                              _samples(rhr=50, hrv=90, vo2=55, walking_hr=85))
        contribs = [abs(d["contribution_pts"]) for d in out["top_drivers"]]
        assert contribs == sorted(contribs, reverse=True)


# ── D. Clinical-equation integration ───────────────────────────────────────


def _full_clinical_onboarding(age: int = 55, sex: str = "M",
                              weight: float = 75.0, height: float = 178.0,
                              **clinical) -> dict:
    """Onboarding with full clinical inputs so ASCVD/Framingham/LE8 fire.

    Defaults represent a generally-healthy mid-50s adult; pass kwargs to
    override individual clinical fields for diff tests.
    """
    return {
        "age": age, "sex": sex,
        "height_cm": height, "weight_kg": weight,
        "smoking":            clinical.get("smoking",            False),
        "diabetes":           clinical.get("diabetes",           False),
        "family_history_cvd": clinical.get("family_history_cvd", False),
        "on_bp_medication":   clinical.get("on_bp_medication",   False),
        "race_ethnicity":     clinical.get("race_ethnicity",     None),
        "systolic_bp":        clinical.get("systolic_bp",        118),
        "total_cholesterol":  clinical.get("total_cholesterol",  180),
        "hdl_cholesterol":    clinical.get("hdl_cholesterol",    55),
    }


class TestClinicalEquationIntegration:
    def test_equations_fire_with_full_onboarding(self):
        """When SBP/cholesterol/HDL are supplied, ASCVD/Framingham/LE8
        must populate `_eq_*` keys in the features dict."""
        out = ml.run_pipeline(_full_clinical_onboarding(),
                              _samples(steps=8000, kcal=400, excm=30, sleep_min=460))
        feats = out["features"]
        assert feats["_eq_ascvd_risk_10yr"] is not None
        assert feats["_eq_framingham_risk_10yr"] is not None
        assert feats["_eq_le8"] is not None and feats["_eq_le8"]["score"] >= 80

    def test_smoker_lower_vitality_than_nonsmoker(self):
        """ASCVD + Framingham + LE8 all penalize smoking. With identical
        wearable profile, a smoker must score lower than a nonsmoker."""
        sa = _samples(steps=8000, kcal=400, excm=30, sleep_min=460)
        non = ml.run_pipeline(_full_clinical_onboarding(smoking=False), sa)["vitality"]
        smk = ml.run_pipeline(_full_clinical_onboarding(smoking=True),  sa)["vitality"]
        assert smk < non - 1.0, f"smoker {smk} should score lower than nonsmoker {non}"

    def test_high_cholesterol_lowers_vitality(self):
        """Total cholesterol 280 vs 160, holding everything else equal."""
        sa = _samples(steps=8000, kcal=400, excm=30, sleep_min=460)
        low  = ml.run_pipeline(_full_clinical_onboarding(total_cholesterol=160), sa)["vitality"]
        high = ml.run_pipeline(_full_clinical_onboarding(total_cholesterol=280), sa)["vitality"]
        assert high < low, f"high chol {high} should score lower than low chol {low}"

    def test_high_sbp_lowers_vitality(self):
        sa = _samples(steps=8000, kcal=400, excm=30, sleep_min=460)
        norm = ml.run_pipeline(_full_clinical_onboarding(systolic_bp=115), sa)["vitality"]
        hi   = ml.run_pipeline(_full_clinical_onboarding(systolic_bp=165), sa)["vitality"]
        assert hi < norm, f"SBP 165 ({hi}) should score lower than SBP 115 ({norm})"

    def test_diabetic_lower_than_nondiabetic(self):
        sa = _samples(steps=8000, kcal=400, excm=30, sleep_min=460)
        non = ml.run_pipeline(_full_clinical_onboarding(diabetes=False), sa)["vitality"]
        dm  = ml.run_pipeline(_full_clinical_onboarding(diabetes=True),  sa)["vitality"]
        assert dm < non, f"diabetic {dm} should score lower than nondiabetic {non}"

    def test_partial_onboarding_does_not_silently_fire_equations(self):
        """Default onboarding with chol/sbp = None must NOT fire ASCVD or
        Framingham (their published applicability requires the inputs).
        FINDRISC/LE8 may still surface in `_eq_*` for display but should
        not enter composite_bonus (coverage gates them out)."""
        out = ml.run_pipeline(_onboarding(),  # no clinical inputs
                              _samples(steps=8000, kcal=400, excm=30, sleep_min=460))
        feats = out["features"]
        assert feats["_eq_ascvd_risk_10yr"] is None
        assert feats["_eq_framingham_risk_10yr"] is None
        # No equation-named entries in top_drivers when equations didn't fire.
        eq_names = {"ascvd", "framingham", "findrisc", "le8"}
        for d in out["top_drivers"]:
            assert d["feature"] not in eq_names

    def test_equations_can_appear_in_top_drivers_when_dominant(self):
        """A 60yo smoker with high cholesterol + high SBP should have ASCVD
        as one of the top drivers — its contribution should be strongly
        negative."""
        out = ml.run_pipeline(
            _full_clinical_onboarding(
                age=60, sex="M",
                smoking=True, total_cholesterol=280, hdl_cholesterol=35,
                systolic_bp=160, on_bp_medication=False,
            ),
            _samples(steps=4000, kcal=200, excm=10, sleep_min=420),
        )
        eq_names = {"ascvd", "framingham", "findrisc", "le8"}
        eq_drivers = [d for d in out["top_drivers"] if d["feature"] in eq_names]
        assert eq_drivers, "expected at least one clinical equation in top_drivers"
        for d in eq_drivers:
            assert d["direction"] == "worse"
