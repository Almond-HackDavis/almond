"""Pydantic v2 models — single source of truth for every JSON shape on the wire.

Mirrors AGENTS.md ## API contracts, with these task-mandated overrides:

  1. POST /healthkit response is `{upload_id, received_at, status="pending"}`,
     not `{upload_id, received_at, processed=true}`. Processing is non-blocking;
     the worker fills it in later.
  2. GET /risk supports an optional `?upload_id=` query.
  3. nhanes_mortality_2yr (NOT nhanes_mortality_10yr) per the Phase-1 spec lock.

iOS team: this file is the contract. Add Codable structs that mirror these
1:1 in almond-app/Almond/Networking/.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Common building blocks ───────────────────────────────────────────────────

UploadStatus = Literal["pending", "scoring", "recommending", "done", "failed"]


class APIError(BaseModel):
    """Standard error envelope: {"error": {"code", "message", "details"}}."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIErrorResponse(BaseModel):
    error: APIError


# ── POST /auth/login ─────────────────────────────────────────────────────────


class AuthLoginRequest(BaseModel):
    apple_identity_token: str = Field(..., min_length=20)


class AuthLoginResponse(BaseModel):
    user_id: UUID
    session_token: str
    is_new_user: bool
    needs_onboarding: bool


# ── POST /onboarding ─────────────────────────────────────────────────────────


class OnboardingRequest(BaseModel):
    age: int = Field(..., ge=18, le=100)
    sex: Literal["M", "F"]
    height_cm: float = Field(..., ge=100, le=250)
    weight_kg: float = Field(..., ge=30, le=250)
    smoking: bool
    diabetes: bool
    family_history_cvd: bool
    race_ethnicity: Optional[Literal["white", "black", "asian", "hispanic", "other"]] = None
    systolic_bp: Optional[int] = Field(None, ge=70, le=250)
    total_cholesterol: Optional[int] = Field(None, ge=80, le=400)
    hdl_cholesterol: Optional[int] = Field(None, ge=10, le=150)
    on_bp_medication: Optional[bool] = None


class OnboardingResponse(BaseModel):
    onboarding_id: UUID
    completed_at: datetime


# ── POST /healthkit ──────────────────────────────────────────────────────────


class HealthKitUploadRequest(BaseModel):
    """Outer envelope. `samples` is intentionally typed as `dict` — the backend
    treats it as opaque; only the worker interprets the wearable payload.
    """

    model_config = ConfigDict(extra="allow")  # keep any future fields iOS adds

    uploaded_at: datetime
    window_start: datetime
    window_end: datetime
    samples: dict[str, Any]


class HealthKitUploadResponse(BaseModel):
    """Override of AGENTS.md: returns `status` instead of `processed`.

    iOS should poll GET /risk?upload_id=<id> until `status == "done"`.
    """

    upload_id: UUID
    received_at: datetime
    status: UploadStatus


# ── GET /risk ────────────────────────────────────────────────────────────────


class TopDriver(BaseModel):
    feature: str
    value: float
    population_norm: float
    direction: Literal["worse", "better"]
    weight: float
    human_label: str
    source: Literal["cox", "augmentation"]


class GeminiActionItem(BaseModel):
    finding: str
    action: str
    rationale: str


class GeminiRecommendation(BaseModel):
    summary: str
    actions: list[GeminiActionItem]
    disclaimer: str


class RiskResponseFull(BaseModel):
    """Status == done — the full prediction payload."""

    upload_id: UUID
    status: Literal["done"] = "done"
    computed_at: datetime
    scores: dict[str, dict[str, Any]]
    top_drivers: list[TopDriver]
    gemini_recommendation: Optional[GeminiRecommendation] = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)


class RiskResponsePending(BaseModel):
    """Status != done — iOS should keep polling."""

    upload_id: UUID
    status: Literal["pending", "scoring", "recommending", "failed"]


# Discriminated union for OpenAPI clarity. FastAPI's response_model can use
# either the union directly or branch in the handler — handlers branch.
RiskResponse = RiskResponseFull | RiskResponsePending


# ── GET /history ─────────────────────────────────────────────────────────────


class HistoryResponse(BaseModel):
    user_id: UUID
    days: int
    series: dict[str, list[dict[str, Any]]]


# ── Worker endpoints ─────────────────────────────────────────────────────────


class WorkerUploadSummary(BaseModel):
    upload_id: UUID
    user_id: UUID
    uploaded_at: datetime


class WorkerUploadList(BaseModel):
    uploads: list[WorkerUploadSummary]


class WorkerUploadDetail(BaseModel):
    """Full payload for the worker, with the user's onboarding doc embedded.

    Embedding onboarding saves the worker a second round-trip to look up
    age/sex/etc. when running the Cox model + clinical equations.
    """

    upload_id: UUID
    user_id: UUID
    uploaded_at: datetime
    window_start: datetime
    window_end: datetime
    payload: dict[str, Any]
    onboarding: Optional[dict[str, Any]]
    status: UploadStatus


class WorkerResultRequest(BaseModel):
    """Outer-shape validation only — the worker's contract with iOS for the
    inner shapes is intentionally not enforced here so the worker can iterate
    without breaking the backend.
    """

    scores: dict[str, dict[str, Any]]
    top_drivers: list[dict[str, Any]]
    gemini_recommendation: Optional[dict[str, Any]] = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerResultResponse(BaseModel):
    prediction_id: UUID


class WorkerFailRequest(BaseModel):
    error: str
    stage: Literal["scoring", "recommending"]


class WorkerFailResponse(BaseModel):
    upload_id: UUID
    status: Literal["failed"]
