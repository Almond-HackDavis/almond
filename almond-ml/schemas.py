"""Pydantic v2 wire schemas for the single sync-pipeline backend.

Two endpoints:

  POST /input   InputRequest    →  OutputDocument
  GET  /output                  →  OutputDocument  (the latest, _id="current")

The wire format is intentionally narrow: validate the outer shape, treat
the per-day arrays as opaque dicts where reasonable, and let `ml.py`
interpret them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── /input request ──────────────────────────────────────────────────────────


class Onboarding(BaseModel):
    age: int = Field(..., ge=18, le=100)
    sex: Literal["M", "F"]
    height_cm: float = Field(..., ge=100.0, le=250.0)
    weight_kg: float = Field(..., ge=30.0, le=250.0)

    smoking: Optional[bool] = None
    diabetes: Optional[bool] = None
    family_history_cvd: Optional[bool] = None
    on_bp_medication: Optional[bool] = None
    race_ethnicity: Optional[Literal["white", "black", "asian", "hispanic", "other"]] = None
    systolic_bp: Optional[int] = Field(None, ge=70, le=250)
    total_cholesterol: Optional[int] = Field(None, ge=80, le=400)
    hdl_cholesterol: Optional[int] = Field(None, ge=10, le=150)


class Samples(BaseModel):
    """HealthKit-derived signals. Inner row shapes are dict[str, Any] —
    `ml.engineer_features` reads the keys it needs and ignores the rest.

    Tier-1 (Cox features + activity bonus): steps_daily, active_energy_daily_kcal,
        exercise_minutes_daily, sleep_sessions.

    Tier-2 (augmentation, NOT in the Cox model — apply published-literature
    multipliers post-hoc):
      * resting_hr_daily        — Jensen 2013 (Eur Heart J).
      * hrv_sdnn                — Hillebrand 2013 (Europace).
      * vo2_max_latest          — FRIEND registry / Kaminsky 2013; also drives fitness_age.
      * walking_hr_avg_daily    — secondary HR signal.

    All Tier-2 fields are optional; the pipeline degrades gracefully if iOS
    lacks any one (the contribution that signal would have made is omitted
    from the average rather than zeroed).
    """

    model_config = ConfigDict(extra="allow")

    # Tier-1
    steps_daily: list[dict[str, Any]] = Field(default_factory=list)
    active_energy_daily_kcal: list[dict[str, Any]] = Field(default_factory=list)
    exercise_minutes_daily: list[dict[str, Any]] = Field(default_factory=list)
    sleep_sessions: list[dict[str, Any]] = Field(default_factory=list)

    # Tier-2 (HealthKit augmentation)
    resting_hr_daily: list[dict[str, Any]] = Field(default_factory=list)
    hrv_sdnn: list[dict[str, Any]] = Field(default_factory=list)
    vo2_max_latest: dict[str, Any] | None = None
    walking_hr_avg_daily: list[dict[str, Any]] = Field(default_factory=list)


class InputRequest(BaseModel):
    onboarding: Onboarding
    samples: Samples


# ── /output document ────────────────────────────────────────────────────────


class ScoreValue(BaseModel):
    """One row of the `scores` block.

    Modeled as a free-form dict to support per-score field shapes that
    don't share a common schema:
      vitality_score:       {value, max}
      nhanes_mortality_2yr: {value, ci_low, ci_high}      (CI fields nullable)

    The route handler builds these dicts explicitly so we can match the
    wire spec exactly without heuristic field-stripping.
    """

    model_config = ConfigDict(extra="allow")

    value: float


class ModelMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())   # allow `model_id`

    model_id: str
    prompt_template_version: str
    llm_model: str
    horizon_months: int


class TopDriver(BaseModel):
    """One contributor to the vitality score. iOS uses this to render
    "what's driving your score" badges. Each driver has a name (e.g.
    `resting_hr`), a human-readable label, and a signed contribution in
    vitality points. Positive = lifting your score, negative = dragging it.
    """

    feature: str
    human_label: str
    value: float                 # the raw signal (e.g. 58.0 bpm)
    contribution_pts: float      # signed vitality-point contribution
    direction: Literal["better", "worse"]


class OutputDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    computed_at: datetime
    input_uploaded_at: datetime
    input_id: str | None = None

    scores: dict[str, dict[str, Any]]
    top_drivers: list[TopDriver] = Field(default_factory=list)
    gemma_summary: str
    disclaimer: str
    model_metadata: ModelMetadata


# ── Standard error envelope ─────────────────────────────────────────────────


class APIError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIErrorResponse(BaseModel):
    error: APIError
