"""MongoDB layer.

Two collections:

  * `inputs`   — append-only audit log of every POST /input payload.
                 _id is a UUID4 hex string, stamped at insert time.

  * `outputs`  — the prediction documents. Two write patterns:
      - the "current" singleton row (_id="current") is upserted on every
        request so iOS can read the latest with one round-trip.
      - a copy is also appended with a UUID id for history / replay.

Uses pymongo's `AsyncMongoClient` (motor was deprecated 14 May 2026) and
Beanie 2.x for document mapping.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pymongo
from beanie import Document, init_beanie
from pydantic import Field
from pymongo import AsyncMongoClient

log = logging.getLogger("almond.db")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


# ── Documents ────────────────────────────────────────────────────────────────


class InputRecord(Document):
    """Audit log of every POST /input received. Append-only."""

    id: str = Field(default_factory=new_id)
    received_at: datetime = Field(default_factory=utcnow)
    onboarding: dict[str, Any]
    samples: dict[str, Any]

    class Settings:
        name = "inputs"
        indexes = [
            pymongo.IndexModel("received_at", name="received_at"),
        ]


class OutputRecord(Document):
    """One Cox + Gemma prediction. Two coexisting write patterns:

      * `id == "current"` — singleton, upserted on every request. iOS reads
        this to render the latest dashboard.
      * `id` == UUID4 hex — append-only history for charts / replay.

    Both use the same `Settings.name = "outputs"`. The two row classes are
    plain doc-shape twins; the choice happens at the call site in
    routes/input_routes.py.
    """

    id: str = Field(default_factory=new_id)
    computed_at: datetime = Field(default_factory=utcnow)
    input_uploaded_at: datetime
    input_id: Optional[str] = None

    scores: dict[str, dict[str, Any]]
    gemma_summary: str
    disclaimer: str
    model_metadata: dict[str, Any]

    class Settings:
        name = "outputs"
        indexes = [
            pymongo.IndexModel("computed_at", name="computed_at_desc",
                               expireAfterSeconds=None),
        ]


DOCUMENT_MODELS: list[type[Document]] = [InputRecord, OutputRecord]


# ── Lifespan helpers ────────────────────────────────────────────────────────


_client: Optional[AsyncMongoClient] = None


async def init_db(uri: str, db_name: str) -> AsyncMongoClient:
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
    if "@" not in uri or "://" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return uri
