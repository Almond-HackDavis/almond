"""Clinically-validated risk equations.

Pure functions, no I/O, no model artifacts. Each function takes its
literature-defined inputs, validates them against the original study's
applicable range, and returns a risk probability or score in the form
the original publication defined.

Sources
-------
* ASCVD Pooled Cohort Equations (Goff 2013, ACC/AHA, Appendix Table A,
  Circulation 129:S49-S73). 10-yr hard atherosclerotic CVD probability.
  Sex × race-stratified (white-or-other vs. black). Applicable: 40-79 y.
* Framingham General CVD (D'Agostino 2008, Circulation 117:743-753).
  10-yr broader CVD probability (CHD + stroke + heart failure + PAD + TIA).
  Sex-stratified (no race). Applicable: 30-74 y.
* FINDRISC (Lindström 2003, Diabetes Care 26:725-731). 10-yr T2DM
  probability via additive point score. Original includes waist, family
  history, vegetable intake; we run a "partial" mode using only the
  inputs we collect (age, BMI, activity, BP meds, prior glucose hx).
* AHA Life's Essential 8 (Lloyd-Jones 2022, Circulation 146:e18-e43).
  0-100 cardiovascular health composite. Eight components averaged
  equally; we run a "partial" mode that omits Diet because we don't
  collect food-frequency data.

Every function returns `None` (or a `mode`-tagged dict) when inputs
are insufficient or out of the study's applicable range. The vitality
pipeline treats `None` the same way it treats Tier-2 augmentation
signals: the component drops out of the weighted average rather than
being zeroed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Literal, Optional


# ─────────────────────────────────────────────────────────────────────────────
# ASCVD Pooled Cohort Equations — Goff 2013, Appendix Table A
# ─────────────────────────────────────────────────────────────────────────────

# Coefficient bundle: (β-vector, mean-of-individual-sum, baseline 10y survival).
# β-vector order:
#   ln_age, ln_age_sq, ln_chol, ln_age_x_ln_chol, ln_hdl, ln_age_x_ln_hdl,
#   ln_sbp_treated, ln_age_x_ln_sbp_treated,
#   ln_sbp_untreated, ln_age_x_ln_sbp_untreated,
#   smoker, ln_age_x_smoker, diabetes
# Zeros indicate "this term not in the published equation for this stratum".

@dataclass(frozen=True)
class _PCEStratum:
    beta: tuple[float, ...]
    mean_sum: float
    s10: float


_PCE_WHITE_FEMALE = _PCEStratum(
    beta=(
        -29.799, 4.884,
        13.540, -3.114,
        -13.578, 3.149,
         2.019, 0.0,
         1.957, 0.0,
         7.574, -1.665,
         0.661,
    ),
    mean_sum=-29.18,
    s10=0.9665,
)

_PCE_BLACK_FEMALE = _PCEStratum(
    beta=(
        17.114, 0.0,
         0.940, 0.0,
       -18.920, 4.475,
        29.291, -6.432,
        27.820, -6.087,
         0.691, 0.0,
         0.874,
    ),
    mean_sum=86.61,
    s10=0.9533,
)

_PCE_WHITE_MALE = _PCEStratum(
    beta=(
        12.344, 0.0,
        11.853, -2.664,
        -7.990, 1.769,
         1.797, 0.0,
         1.764, 0.0,
         7.837, -1.795,
         0.658,
    ),
    mean_sum=61.18,
    s10=0.9144,
)

_PCE_BLACK_MALE = _PCEStratum(
    beta=(
         2.469, 0.0,
         0.302, 0.0,
        -0.307, 0.0,
         1.916, 0.0,
         1.809, 0.0,
         0.549, 0.0,
         0.645,
    ),
    mean_sum=19.54,
    s10=0.8954,
)


def ascvd_10yr(
    *,
    age: float,
    sex: Literal["M", "F"],
    race: Optional[str],          # "black" → black stratum; everything else → white-or-other
    total_chol: Optional[float],  # mg/dL
    hdl: Optional[float],         # mg/dL
    sbp: Optional[float],         # mmHg
    on_bp_medication: Optional[bool],
    smoking: Optional[bool],
    diabetes: Optional[bool],
) -> Optional[float]:
    """Goff 2013 Pooled Cohort Equations → 10-yr hard ASCVD probability.

    Returns `None` outside the published applicable age range (40-79) or
    when any required input is missing. Result is clipped to [0.001, 0.99]
    to keep downstream wellness mapping stable at the extremes.
    """
    if age < 40 or age > 79:
        return None
    required = (total_chol, hdl, sbp, on_bp_medication, smoking, diabetes)
    if any(v is None for v in required):
        return None

    if sex == "F":
        stratum = _PCE_BLACK_FEMALE if race == "black" else _PCE_WHITE_FEMALE
    else:
        stratum = _PCE_BLACK_MALE if race == "black" else _PCE_WHITE_MALE

    ln_age  = log(float(age))
    ln_chol = log(float(total_chol))
    ln_hdl  = log(float(hdl))
    ln_sbp  = log(float(sbp))
    smk     = 1.0 if smoking else 0.0
    dm      = 1.0 if diabetes else 0.0
    treated = bool(on_bp_medication)

    b = stratum.beta
    s = (
        b[0] * ln_age
      + b[1] * (ln_age ** 2)
      + b[2] * ln_chol
      + b[3] * (ln_age * ln_chol)
      + b[4] * ln_hdl
      + b[5] * (ln_age * ln_hdl)
      + (b[6] * ln_sbp + b[7] * (ln_age * ln_sbp) if treated     else 0.0)
      + (b[8] * ln_sbp + b[9] * (ln_age * ln_sbp) if not treated else 0.0)
      + b[10] * smk
      + b[11] * (ln_age * smk)
      + b[12] * dm
    )

    risk = 1.0 - stratum.s10 ** exp(s - stratum.mean_sum)
    return float(min(0.99, max(0.001, risk)))


# ─────────────────────────────────────────────────────────────────────────────
# Framingham General CVD — D'Agostino 2008 (sex-stratified, no race)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _FraminghamStratum:
    b_ln_age: float
    b_ln_chol: float
    b_ln_hdl: float
    b_ln_sbp_treated: float
    b_ln_sbp_untreated: float
    b_smoker: float
    b_diabetes: float
    mean_sum: float
    s10: float


_FRAM_F = _FraminghamStratum(
    b_ln_age=2.32888, b_ln_chol=1.20904, b_ln_hdl=-0.70833,
    b_ln_sbp_treated=2.82263, b_ln_sbp_untreated=2.76157,
    b_smoker=0.52873, b_diabetes=0.69154,
    mean_sum=26.1931, s10=0.95012,
)

_FRAM_M = _FraminghamStratum(
    b_ln_age=3.06117, b_ln_chol=1.12370, b_ln_hdl=-0.93263,
    b_ln_sbp_treated=1.99881, b_ln_sbp_untreated=1.93303,
    b_smoker=0.65451, b_diabetes=0.57367,
    mean_sum=23.9802, s10=0.88936,
)


def framingham_cvd_10yr(
    *,
    age: float,
    sex: Literal["M", "F"],
    total_chol: Optional[float],
    hdl: Optional[float],
    sbp: Optional[float],
    on_bp_medication: Optional[bool],
    smoking: Optional[bool],
    diabetes: Optional[bool],
) -> Optional[float]:
    """D'Agostino 2008 General CVD profile → 10-yr broader CVD probability.

    Broader CVD = CHD + stroke + HF + PAD + TIA. Applicable 30-74 y.
    Returns `None` outside age range or when any required input is missing.
    """
    if age < 30 or age > 74:
        return None
    required = (total_chol, hdl, sbp, on_bp_medication, smoking, diabetes)
    if any(v is None for v in required):
        return None

    stratum = _FRAM_F if sex == "F" else _FRAM_M

    ln_age  = log(float(age))
    ln_chol = log(float(total_chol))
    ln_hdl  = log(float(hdl))
    ln_sbp  = log(float(sbp))
    b_sbp   = stratum.b_ln_sbp_treated if on_bp_medication else stratum.b_ln_sbp_untreated
    smk     = 1.0 if smoking else 0.0
    dm      = 1.0 if diabetes else 0.0

    s = (
        stratum.b_ln_age   * ln_age
      + stratum.b_ln_chol  * ln_chol
      + stratum.b_ln_hdl   * ln_hdl
      + b_sbp              * ln_sbp
      + stratum.b_smoker   * smk
      + stratum.b_diabetes * dm
    )
    risk = 1.0 - stratum.s10 ** exp(s - stratum.mean_sum)
    return float(min(0.99, max(0.001, risk)))


# ─────────────────────────────────────────────────────────────────────────────
# FINDRISC — Lindström 2003 (partial mode by default)
# ─────────────────────────────────────────────────────────────────────────────

# Risk-band lookup from the original paper's discrimination table.
_FINDRISC_BANDS: tuple[tuple[int, int, float], ...] = (
    # (lo_inclusive, hi_exclusive, 10-yr T2D probability)
    (0,  7,  0.01),
    (7,  12, 0.04),
    (12, 15, 0.17),
    (15, 21, 0.33),
    (21, 27, 0.50),
)


def findrisc_partial(
    *,
    age: float,
    bmi: float,
    on_bp_medication: Optional[bool],
    diabetes: Optional[bool],          # used as proxy for "history of high glucose"
    daily_exercise_min: Optional[float] = None,
    waist_cm: Optional[float] = None,           # full-mode only
    family_history_diabetes: Optional[bool] = None,  # full-mode only
    daily_vegetables: Optional[bool] = None,         # full-mode only
) -> Optional[dict]:
    """FINDRISC additive score → 10-yr T2D probability band.

    Always runs in "partial" mode unless the three optional clinical inputs
    (waist, family history of diabetes, daily vegetable intake) are also
    supplied. Returns `{score, risk_10yr, mode, missing}` so iOS can
    surface what would tighten the estimate.
    """
    if age < 18:
        return None

    score = 0
    missing: list[str] = []

    # Age
    if   age < 45: score += 0
    elif age < 55: score += 2
    elif age < 65: score += 3
    else:          score += 4

    # BMI
    if   bmi < 25: score += 0
    elif bmi < 30: score += 1
    else:          score += 3

    # Waist
    if waist_cm is None:
        missing.append("waist_cm")
    else:
        # Sex-specific waist points; we don't have sex here, use the more
        # conservative female cutpoints since the male cutpoints would
        # over-credit borderline waists.
        if   waist_cm < 80: score += 0
        elif waist_cm < 88: score += 3
        else:               score += 4

    # Physical activity (≥30 min/day)
    if daily_exercise_min is None:
        missing.append("daily_exercise_min")
    else:
        score += 0 if daily_exercise_min >= 30 else 2

    # Vegetables / fruit daily
    if daily_vegetables is None:
        missing.append("daily_vegetables")
    else:
        score += 0 if daily_vegetables else 1

    # BP medication
    if on_bp_medication is None:
        missing.append("on_bp_medication")
    else:
        score += 2 if on_bp_medication else 0

    # Hx high glucose (use diabetes as proxy — strict but defensible)
    if diabetes is None:
        missing.append("diabetes")
    else:
        score += 5 if diabetes else 0

    # Family history of diabetes
    if family_history_diabetes is None:
        missing.append("family_history_diabetes")
    else:
        score += 5 if family_history_diabetes else 0

    risk = _FINDRISC_BANDS[0][2]
    for lo, hi, p in _FINDRISC_BANDS:
        if lo <= score < hi:
            risk = p
            break
    else:
        risk = _FINDRISC_BANDS[-1][2]

    # FINDRISC has 8 input slots total. The vitality pipeline scales the
    # equation's wellness contribution by `coverage` so partial-mode results
    # don't outweigh equations we have full data for.
    n_total = 8
    n_filled = n_total - len(missing)
    coverage = n_filled / n_total

    mode = "full" if not missing else "partial"
    return {
        "score":     int(score),
        "risk_10yr": float(risk),
        "mode":      mode,
        "missing":   missing,
        "coverage":  float(coverage),
    }


# ─────────────────────────────────────────────────────────────────────────────
# AHA Life's Essential 8 — Lloyd-Jones 2022 (partial mode by default)
# ─────────────────────────────────────────────────────────────────────────────


def _le8_activity(weekly_min: Optional[float]) -> Optional[float]:
    if weekly_min is None: return None
    if weekly_min >= 150:  return 100.0
    if weekly_min >= 120:  return 90.0
    if weekly_min >= 90:   return 80.0
    if weekly_min >= 60:   return 60.0
    if weekly_min >= 30:   return 40.0
    if weekly_min >= 1:    return 20.0
    return 0.0


def _le8_nicotine(smoking: Optional[bool]) -> Optional[float]:
    """Coarse mapping. Real LE8 distinguishes never/former/current with timing.
    Boolean smoking flag → never=100, current=20 (between current-low and current-heavy).
    """
    if smoking is None: return None
    return 20.0 if smoking else 100.0


def _le8_sleep(mean_sleep_min: Optional[float]) -> Optional[float]:
    if mean_sleep_min is None or mean_sleep_min <= 0:
        return None
    h = mean_sleep_min / 60.0
    if   7 <= h < 9:  return 100.0
    if   9 <= h < 10: return 90.0
    if   6 <= h < 7:  return 70.0
    if (5 <= h < 6) or h >= 10: return 40.0
    if   4 <= h < 5:  return 20.0
    return 0.0


def _le8_bmi(bmi: Optional[float]) -> Optional[float]:
    if bmi is None: return None
    if bmi < 25:    return 100.0
    if bmi < 30:    return 70.0
    if bmi < 35:    return 30.0
    if bmi < 40:    return 15.0
    return 0.0


def _le8_lipids(non_hdl: Optional[float]) -> Optional[float]:
    if non_hdl is None: return None
    if non_hdl < 130: return 100.0
    if non_hdl < 160: return 60.0
    if non_hdl < 190: return 40.0
    if non_hdl < 220: return 20.0
    return 0.0


def _le8_glucose(diabetes: Optional[bool]) -> Optional[float]:
    """Without HbA1c we can only distinguish diabetic vs not. The LE8 paper
    assigns 100 to no-DM with HbA1c<5.7 and ~30 to controlled DM without
    HbA1c info. Use 85 (no-DM, unknown HbA1c) and 30 (DM, unknown HbA1c)."""
    if diabetes is None: return None
    return 30.0 if diabetes else 85.0


def _le8_blood_pressure(sbp: Optional[float], on_bp_med: Optional[bool]) -> Optional[float]:
    if sbp is None or on_bp_med is None: return None
    treated = bool(on_bp_med)
    # Treated patients shift one band down even if their SBP is "normal".
    if not treated and sbp < 120: return 100.0
    if not treated and sbp < 130: return 75.0
    if treated and sbp < 130:     return 50.0
    if sbp < 140:                 return 50.0
    if sbp < 160:                 return 25.0
    return 0.0


def life_essential_8(
    *,
    bmi: Optional[float],
    weekly_exercise_min: Optional[float],
    mean_sleep_min: Optional[float],
    smoking: Optional[bool],
    total_cholesterol: Optional[float],
    hdl_cholesterol: Optional[float],
    sbp: Optional[float],
    on_bp_medication: Optional[bool],
    diabetes: Optional[bool],
) -> Optional[dict]:
    """LE8 cardiovascular health composite, 0-100 scale.

    Diet is unconditionally absent (we don't collect food-frequency data),
    so we run with at most 7 of the 8 components and tag the result mode
    as "partial". Returns `None` if fewer than 4 components are scoreable —
    not enough signal to publish a number.
    """
    non_hdl = None
    if total_cholesterol is not None and hdl_cholesterol is not None:
        non_hdl = float(total_cholesterol) - float(hdl_cholesterol)

    components = {
        "physical_activity": _le8_activity(weekly_exercise_min),
        "nicotine":          _le8_nicotine(smoking),
        "sleep":             _le8_sleep(mean_sleep_min),
        "bmi":               _le8_bmi(bmi),
        "lipids":            _le8_lipids(non_hdl),
        "glucose":           _le8_glucose(diabetes),
        "blood_pressure":    _le8_blood_pressure(sbp, on_bp_medication),
        # "diet":            None,  # unconditionally missing
    }
    available = [v for v in components.values() if v is not None]
    if len(available) < 4:
        return None

    score = sum(available) / len(available)
    # 8 LE8 components total; we never score diet, so max coverage is 7/8.
    coverage = len(available) / 8
    return {
        "score":          float(round(score, 1)),
        "mode":           "partial",          # always partial without diet
        "components":     components,
        "n_scoreable":    len(available),
        "coverage":       float(coverage),
    }
