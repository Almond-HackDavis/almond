"""MongoDB layer.

* Beanie Document models for the four collections in AGENTS.md (users,
  onboarding, healthkit_uploads, risk_predictions), with the task-mandated
  override that all `_id` values are stored as **strings** (UUID4 hex), not
  BSON ObjectIds. iOS expects string IDs end-to-end.

* `init_db(uri, db_name)` opens a `pymongo.AsyncMongoClient` (NOT motor; motor
  was deprecated 14 May 2026) and registers the documents with Beanie. The
  same function is used at app startup and overridden in tests with a
  mongomock-backed client.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

import pymongo
from beanie import Document, init_beanie
from pydantic import Field
from pymongo import AsyncMongoClient

log = logging.getLogger("almond.db")


def utcnow() -> datetime:
    """Always tz-aware. Never use datetime.utcnow() — it returns naive UTC."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """UUID4 as a 32-char hex string — what we store in `_id` everywhere."""
    return uuid4().hex


# ── Documents ────────────────────────────────────────────────────────────────


class User(Document):
    id: str = Field(default_factory=new_id)
    apple_user_id: str
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "users"
        indexes = [
            pymongo.IndexModel("apple_user_id", unique=True, name="apple_user_id_unique"),
        ]


class Onboarding(Document):
    id: str = Field(default_factory=new_id)
    user_id: str
    age: int
    sex: Literal["M", "F"]
    height_cm: float
    weight_kg: float
    smoking: bool
    diabetes: bool
    family_history_cvd: bool
    race_ethnicity: Optional[str] = None
    systolic_bp: Optional[int] = None
    total_cholesterol: Optional[int] = None
    hdl_cholesterol: Optional[int] = None
    on_bp_medication: Optional[bool] = None
    completed_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "onboarding"
        indexes = [
            pymongo.IndexModel("user_id", unique=True, name="user_id_unique"),
        ]


UploadStatus = Literal["pending", "scoring", "recommending", "done", "failed"]


class HealthKitUpload(Document):
    id: str = Field(default_factory=new_id)
    user_id: str
    uploaded_at: datetime = Field(default_factory=utcnow)
    window_start: datetime
    window_end: datetime
    payload: dict[str, Any]
    status: UploadStatus = "pending"
    claimed_at: Optional[datetime] = None
    claimed_by: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_stage: Optional[str] = None

    class Settings:
        name = "healthkit_uploads"
        indexes = [
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("uploaded_at", pymongo.DESCENDING)],
                name="user_uploaded_desc",
            ),
            pymongo.IndexModel(
                [("status", pymongo.ASCENDING), ("uploaded_at", pymongo.ASCENDING)],
                name="status_uploaded_asc_for_worker_queue",
            ),
        ]


class RiskPrediction(Document):
    id: str = Field(default_factory=new_id)
    user_id: str
    upload_id: str
    computed_at: datetime = Field(default_factory=utcnow)
    scores: dict[str, dict[str, Any]]
    top_drivers: list[dict[str, Any]]
    gemini_recommendation: Optional[dict[str, Any]] = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "risk_predictions"
        indexes = [
            pymongo.IndexModel("upload_id", unique=True, name="upload_id_unique"),
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("computed_at", pymongo.DESCENDING)],
                name="user_computed_desc",
            ),
        ]


DOCUMENT_MODELS: list[type[Document]] = [
    User,
    Onboarding,
    HealthKitUpload,
    RiskPrediction,
]


# ── Lifespan helpers ─────────────────────────────────────────────────────────


_client: Optional[AsyncMongoClient] = None


async def init_db(uri: str, db_name: str) -> AsyncMongoClient:
    """Open a pymongo AsyncMongoClient + register Beanie documents.

    Returns the client so the caller can close it on shutdown.
    """
    global _client
    log.info("connecting to MongoDB at %s (db=%s)", _redact(uri), db_name)
    _client = AsyncMongoClient(uri, uuidRepresentation="standard")
    await init_beanie(database=_client[db_name], document_models=DOCUMENT_MODELS)
    log.info("Beanie initialized with %d document models", len(DOCUMENT_MODELS))
    return _client


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def _redact(uri: str) -> str:
    """Mask the password segment of a Mongo URI for logging."""
    if "@" not in uri or "://" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _pw = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return uri
