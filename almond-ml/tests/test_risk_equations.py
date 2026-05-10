"""Unit tests for the four clinical risk equations.

Each equation is verified two ways:

  1. Sanity / monotonicity — known-direction inputs (e.g. older + smoker +
     diabetic should always score worse than younger + nonsmoker +
     nondiabetic, holding everything else fixed).
  2. Bounds — every output is within the equation's published range, and
     the partial-mode equations expose `mode`, `missing`, `coverage`.

We deliberately avoid asserting on a single literature-quoted numeric
example because the published worked examples in Goff 2013 and
D'Agostino 2008 use different coefficient roundings; instead we lock
the equations against directional invariants that any correct
implementation must satisfy.
"""
from __future__ import annotations

import pytest

import risk_equations as eq


# ── ASCVD Pooled Cohort Equations ───────────────────────────────────────────


class TestASCVD:
    def test_returns_none_outside_age_range(self):
        kw = dict(sex="M", race=None, total_chol=200, hdl=50, sbp=120,
                  on_bp_medication=False, smoking=False, diabetes=False)
        assert eq.ascvd_10yr(age=39, **kw) is None
        assert eq.ascvd_10yr(age=80, **kw) is None
        assert eq.ascvd_10yr(age=55, **kw) is not None

    def test_returns_none_when_required_input_missing(self):
        kw = dict(age=55, sex="M", race=None, total_chol=200, hdl=50, sbp=120,
                  on_bp_medication=False, smoking=False, diabetes=False)
        for missing in ("total_chol", "hdl", "sbp",
                        "on_bp_medication", "smoking", "diabetes"):
            partial = {**kw, missing: None}
            assert eq.ascvd_10yr(**partial) is None, f"{missing} missing should yield None"

    def test_smoker_higher_than_nonsmoker(self):
        kw = dict(age=55, sex="M", race=None, total_chol=200, hdl=50, sbp=120,
                  on_bp_medication=False, diabetes=False)
        assert eq.ascvd_10yr(smoking=True,  **kw) > eq.ascvd_10yr(smoking=False, **kw)

    def test_diabetic_higher_than_nondiabetic(self):
        kw = dict(age=55, sex="M", race=None, total_chol=200, hdl=50, sbp=120,
                  on_bp_medication=False, smoking=False)
        assert eq.ascvd_10yr(diabetes=True, **kw) > eq.ascvd_10yr(diabetes=False, **kw)

    def test_higher_sbp_higher_risk(self):
        kw = dict(age=55, sex="M", race=None, total_chol=200, hdl=50,
                  on_bp_medication=False, smoking=False, diabetes=False)
        assert eq.ascvd_10yr(sbp=160, **kw) > eq.ascvd_10yr(sbp=110, **kw)

    def test_low_hdl_higher_risk(self):
        kw = dict(age=55, sex="M", race=None, total_chol=200, sbp=120,
                  on_bp_medication=False, smoking=False, diabetes=False)
        assert eq.ascvd_10yr(hdl=30, **kw) > eq.ascvd_10yr(hdl=70, **kw)

    def test_older_higher_risk(self):
        kw = dict(sex="M", race=None, total_chol=200, hdl=50, sbp=120,
                  on_bp_medication=False, smoking=False, diabetes=False)
        assert eq.ascvd_10yr(age=70, **kw) > eq.ascvd_10yr(age=45, **kw)

    def test_black_stratum_runs(self):
        # Different stratum, sanity check that it returns a value in range.
        r = eq.ascvd_10yr(age=55, sex="F", race="black", total_chol=200,
                          hdl=50, sbp=120, on_bp_medication=False,
                          smoking=False, diabetes=False)
        assert r is not None and 0.0 < r < 1.0

    def test_within_bounds(self):
        for age in (45, 60, 75):
            for sex in ("M", "F"):
                for race in (None, "black"):
                    r = eq.ascvd_10yr(
                        age=age, sex=sex, race=race,
                        total_chol=200, hdl=50, sbp=120,
                        on_bp_medication=False, smoking=False, diabetes=False,
                    )
                    assert r is not None
                    assert 0.001 <= r <= 0.99


# ── Framingham General CVD ─────────────────────────────────────────────────


class TestFramingham:
    def test_returns_none_outside_age_range(self):
        kw = dict(sex="M", total_chol=200, hdl=50, sbp=120,
                  on_bp_medication=False, smoking=False, diabetes=False)
        assert eq.framingham_cvd_10yr(age=29, **kw) is None
        assert eq.framingham_cvd_10yr(age=75, **kw) is None
        assert eq.framingham_cvd_10yr(age=50, **kw) is not None

    def test_smoker_higher_than_nonsmoker(self):
        kw = dict(age=55, sex="F", total_chol=210, hdl=55, sbp=130,
                  on_bp_medication=False, diabetes=False)
        assert eq.framingham_cvd_10yr(smoking=True, **kw) > eq.framingham_cvd_10yr(smoking=False, **kw)

    def test_treated_bp_shifts_risk(self):
        """Holding SBP fixed, being on BP meds slightly increases the
        modeled risk — D'Agostino's coefficient for treated SBP is larger
        than untreated SBP at the same level."""
        kw = dict(age=55, sex="M", total_chol=200, hdl=50, sbp=140,
                  smoking=False, diabetes=False)
        assert eq.framingham_cvd_10yr(on_bp_medication=True,  **kw) > \
               eq.framingham_cvd_10yr(on_bp_medication=False, **kw)

    def test_within_bounds(self):
        for age in (35, 50, 65):
            for sex in ("M", "F"):
                r = eq.framingham_cvd_10yr(
                    age=age, sex=sex, total_chol=200, hdl=50, sbp=120,
                    on_bp_medication=False, smoking=False, diabetes=False,
                )
                assert r is not None
                assert 0.001 <= r <= 0.99


# ── FINDRISC ───────────────────────────────────────────────────────────────


class TestFINDRISC:
    def test_returns_none_under_18(self):
        assert eq.findrisc_partial(age=17, bmi=22, on_bp_medication=False, diabetes=False) is None

    def test_partial_mode_marks_missing(self):
        out = eq.findrisc_partial(age=35, bmi=25, on_bp_medication=False, diabetes=False)
        assert out["mode"] == "partial"
        assert "waist_cm" in out["missing"]
        assert "family_history_diabetes" in out["missing"]
        assert "daily_vegetables" in out["missing"]
        assert 0.0 < out["coverage"] < 1.0

    def test_full_mode_when_all_inputs_supplied(self):
        out = eq.findrisc_partial(
            age=35, bmi=25, on_bp_medication=False, diabetes=False,
            daily_exercise_min=45, waist_cm=85, family_history_diabetes=False,
            daily_vegetables=True,
        )
        assert out["mode"] == "full"
        assert out["missing"] == []
        assert out["coverage"] == 1.0

    def test_obese_higher_score_than_lean(self):
        lean = eq.findrisc_partial(age=55, bmi=22, on_bp_medication=False, diabetes=False)
        obese = eq.findrisc_partial(age=55, bmi=35, on_bp_medication=False, diabetes=False)
        assert obese["score"] > lean["score"]
        assert obese["risk_10yr"] >= lean["risk_10yr"]

    def test_diabetes_proxy_lifts_score(self):
        kw = dict(age=55, bmi=28, on_bp_medication=False)
        no_dm = eq.findrisc_partial(diabetes=False, **kw)
        dm    = eq.findrisc_partial(diabetes=True,  **kw)
        assert dm["score"] > no_dm["score"]

    def test_risk_in_published_bands(self):
        """Every output `risk_10yr` must be one of the band probabilities."""
        bands = {p for _, _, p in eq._FINDRISC_BANDS}
        for age in (25, 45, 65):
            for bmi in (22, 28, 35):
                out = eq.findrisc_partial(age=age, bmi=bmi,
                                          on_bp_medication=False, diabetes=False)
                assert out["risk_10yr"] in bands


# ── Life's Essential 8 ─────────────────────────────────────────────────────


class TestLE8:
    def _full_inputs(self) -> dict:
        return dict(
            bmi=23.0, weekly_exercise_min=200, mean_sleep_min=480,
            smoking=False, total_cholesterol=180, hdl_cholesterol=60,
            sbp=115, on_bp_medication=False, diabetes=False,
        )

    def test_full_mode_returns_high_score(self):
        out = eq.life_essential_8(**self._full_inputs())
        assert out is not None
        assert out["score"] >= 90.0
        assert out["mode"] == "partial"  # diet always missing → always partial
        assert out["coverage"] >= 0.875   # 7/8 components scoreable

    def test_returns_none_when_too_few_components(self):
        # Provide only 3 inputs → fewer than 4 components scoreable
        out = eq.life_essential_8(
            bmi=None, weekly_exercise_min=None, mean_sleep_min=None,
            smoking=False, total_cholesterol=None, hdl_cholesterol=None,
            sbp=None, on_bp_medication=None, diabetes=False,
        )
        assert out is None

    def test_obese_score_lower_than_lean(self):
        lean  = eq.life_essential_8(**{**self._full_inputs(), "bmi": 23})
        obese = eq.life_essential_8(**{**self._full_inputs(), "bmi": 35})
        assert obese["score"] < lean["score"]

    def test_smoker_score_lower(self):
        nonsmoker = eq.life_essential_8(**{**self._full_inputs(), "smoking": False})
        smoker    = eq.life_essential_8(**{**self._full_inputs(), "smoking": True})
        assert smoker["score"] < nonsmoker["score"]

    def test_diabetes_lowers_glucose_component(self):
        nondm = eq.life_essential_8(**{**self._full_inputs(), "diabetes": False})
        dm    = eq.life_essential_8(**{**self._full_inputs(), "diabetes": True})
        assert dm["components"]["glucose"] < nondm["components"]["glucose"]
        assert dm["score"] < nondm["score"]

    def test_score_within_0_to_100(self):
        out = eq.life_essential_8(**self._full_inputs())
        assert 0.0 <= out["score"] <= 100.0
