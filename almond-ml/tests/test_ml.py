"""Unit tests for the ML inference layer (no Mongo, no Gemma)."""
from __future__ import annotations

import pytest

import ml


def _onboarding(age: int = 32, sex: str = "M", weight: float = 75.0, height: float = 178.0) -> dict:
    return {
        "age": age, "sex": sex,
        "height_cm": height, "weight_kg": weight,
        "smoking": False, "diabetes": False,
        "family_history_cvd": False, "on_bp_medication": False,
        "race_ethnicity": None, "systolic_bp": None,
        "total_cholesterol": None, "hdl_cholesterol": None,
    }


def _samples(steps: int = 8000, kcal: int = 400, excm: int = 30, sleep_min: int = 460) -> dict:
    return {
        "steps_daily":              [{"date": "2026-05-08", "count": steps}],
        "active_energy_daily_kcal": [{"date": "2026-05-08", "kcal": kcal}],
        "exercise_minutes_daily":   [{"date": "2026-05-08", "minutes": excm}],
        "sleep_sessions":           [{"start": "x", "end": "y", "duration_min": sleep_min}],
    }


class TestEngineerFeatures:
    def test_returns_locked_feature_keys_plus_mims(self):
        f = ml.engineer_features(_onboarding(), _samples())
        for key in ("age", "sex_male", "bmi_dev", "sleep_dev", "mean_daily_mims"):
            assert key in f, f"missing: {key}"

    def test_bmi_dev_is_distance_from_optimum_22(self):
        # height 178cm, weight 75kg → BMI ≈ 23.67 → bmi_dev ≈ 1.67
        f = ml.engineer_features(_onboarding(weight=75.0, height=178.0), _samples())
        assert abs(f["bmi_dev"] - 1.67) < 0.05

    def test_sleep_dev_is_distance_from_optimum_450(self):
        f = ml.engineer_features(_onboarding(), _samples(sleep_min=480))
        assert abs(f["sleep_dev"] - 30) < 0.01
        f2 = ml.engineer_features(_onboarding(), _samples(sleep_min=420))
        assert abs(f2["sleep_dev"] - 30) < 0.01

    def test_sex_male_encoding(self):
        assert ml.engineer_features(_onboarding(sex="M"), _samples())["sex_male"] == 1.0
        assert ml.engineer_features(_onboarding(sex="F"), _samples())["sex_male"] == 0.0


class TestPredict:
    def test_raw_risk_in_unit_interval(self):
        f = ml.engineer_features(_onboarding(), _samples())
        risk = ml.predict_2yr_mortality(f)
        assert 0.0 < risk < 1.0

    def test_younger_lower_risk(self):
        f_young = ml.engineer_features(_onboarding(age=25), _samples())
        f_old = ml.engineer_features(_onboarding(age=70), _samples())
        assert ml.predict_2yr_mortality(f_young) < ml.predict_2yr_mortality(f_old)

    def test_male_higher_risk_than_female_same_age(self):
        f_m = ml.engineer_features(_onboarding(age=50, sex="M"), _samples())
        f_f = ml.engineer_features(_onboarding(age=50, sex="F"), _samples())
        assert ml.predict_2yr_mortality(f_m) > ml.predict_2yr_mortality(f_f)


class TestActivityBonus:
    def test_zero_at_reference(self):
        ref_mims = ml.MIMS_REFERENCE_M * ml.MIMS_SCALE
        assert abs(ml.activity_bonus(ref_mims)) < 1e-6

    def test_positive_above_reference(self):
        assert ml.activity_bonus(5_500_000) > 5.0

    def test_negative_below_reference(self):
        assert ml.activity_bonus(500_000) < -5.0

    def test_capped_at_range(self):
        assert -ml.MIMS_BONUS_RANGE_PT - 0.01 <= ml.activity_bonus(0) <= ml.MIMS_BONUS_RANGE_PT + 0.01
        assert -ml.MIMS_BONUS_RANGE_PT - 0.01 <= ml.activity_bonus(50_000_000) <= ml.MIMS_BONUS_RANGE_PT + 0.01


class TestVitalityMonotonicity:
    """Three invariants the user explicitly asked us to never violate again."""

    def test_younger_outscores_older_same_lifestyle(self):
        f25 = ml.engineer_features(_onboarding(age=25), _samples())
        f65 = ml.engineer_features(_onboarding(age=65), _samples())
        v25 = ml.vitality_score(ml.predict_2yr_mortality(f25), f25["mean_daily_mims"])
        v65 = ml.vitality_score(ml.predict_2yr_mortality(f65), f65["mean_daily_mims"])
        assert v25 > v65, f"younger should beat older: 25yo={v25}, 65yo={v65}"

    def test_more_active_outscores_less_active_same_age(self):
        f_active   = ml.engineer_features(_onboarding(age=35), _samples(steps=14000, kcal=600, excm=60))
        f_inactive = ml.engineer_features(_onboarding(age=35), _samples(steps=2000,  kcal=120, excm=5))
        v_active   = ml.vitality_score(ml.predict_2yr_mortality(f_active),   f_active["mean_daily_mims"])
        v_inactive = ml.vitality_score(ml.predict_2yr_mortality(f_inactive), f_inactive["mean_daily_mims"])
        assert v_active > v_inactive, f"more active should beat less: {v_active} vs {v_inactive}"

    def test_user_complaint_resolution(self):
        """32yo healthy man must outscore 65yo sedentary woman."""
        young_healthy = ml.engineer_features(
            _onboarding(age=32, sex="M", weight=75, height=178),
            _samples(steps=10000, kcal=500, excm=30, sleep_min=460),
        )
        old_sedentary = ml.engineer_features(
            _onboarding(age=65, sex="F", weight=85, height=165),
            _samples(steps=2500, kcal=150, excm=5, sleep_min=400),
        )
        v_young = ml.vitality_score(ml.predict_2yr_mortality(young_healthy), young_healthy["mean_daily_mims"])
        v_old   = ml.vitality_score(ml.predict_2yr_mortality(old_sedentary), old_sedentary["mean_daily_mims"])
        assert v_young > v_old + 20, f"headline regression: young={v_young}, old={v_old}"


class TestRunPipeline:
    def test_returns_full_dict(self):
        out = ml.run_pipeline(_onboarding(), _samples())
        for key in ("features", "raw_2yr_mortality", "vitality", "activity_bonus"):
            assert key in out
        assert 0.0 <= out["vitality"] <= 100.0
        assert 0.0 < out["raw_2yr_mortality"] < 1.0


class TestRaggedHealthKitArrays:
    """HealthKit doesn't guarantee aligned per-day arrays — iOS routinely sends
    91 days of steps but 33 days of active energy. The pipeline must NOT crash
    on this; it must mean each metric independently before combining."""

    def test_ragged_arrays_no_crash(self):
        ragged = {
            "steps_daily":              [{"date": f"2026-05-{d:02d}", "count": 8000 + d * 50} for d in range(1, 92)],   # 91 days
            "active_energy_daily_kcal": [{"date": f"2026-05-{d:02d}", "kcal":  400 + d * 5}   for d in range(1, 34)],   # 33 days
            "exercise_minutes_daily":   [{"date": f"2026-05-{d:02d}", "minutes": 30 + d}      for d in range(1, 50)],   # 49 days
            "sleep_sessions":           [{"start": "x", "end": "y", "duration_min": 460}     for _ in range(60)],
        }
        out = ml.run_pipeline(_onboarding(), ragged)
        assert 0.0 < out["raw_2yr_mortality"] < 1.0
        assert 0.0 <= out["vitality"] <= 100.0

    def test_ragged_equivalence_to_aligned(self):
        """Mathematical guarantee: for aligned arrays, the new scalar-mean path
        produces the same MIMS as the prior per-day-then-mean computation."""
        aligned = _samples(steps=8000, kcal=400, excm=30, sleep_min=460)
        feats = ml.engineer_features(_onboarding(), aligned)
        # 250k * (8000/1000) + 2k * 400 + 30k * 30 = 2_000_000 + 800_000 + 900_000 = 3_700_000
        assert abs(feats["mean_daily_mims"] - 3_700_000.0) < 1.0

    def test_one_metric_empty(self):
        """If iOS sends no exercise minutes (HK denied that permission),
        the pipeline still produces a valid score."""
        partial = {
            "steps_daily":              [{"date": "2026-05-08", "count": 8000}],
            "active_energy_daily_kcal": [{"date": "2026-05-08", "kcal":  400}],
            "exercise_minutes_daily":   [],
            "sleep_sessions":           [{"start": "x", "end": "y", "duration_min": 460}],
        }
        out = ml.run_pipeline(_onboarding(), partial)
        assert 0.0 < out["raw_2yr_mortality"] < 1.0
