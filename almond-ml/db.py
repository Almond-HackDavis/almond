"""MongoDB layer.

Two collections, both singleton:

  * `input`   — the latest POST /input payload, _id="current", upserted on
                every request.
  * `output`  — the latest pipeline result, _id="current", upserted right
                after Cox + Gemma run.

iOS reads `output._id="current"` to get the latest dashboard. There is no
history collection, no append-only audit log. If you want history later
add a separate collection (e.g. `output_history`) — don't reuse these.

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
    """The latest POST /input payload. Singleton; _id is always "current".

    Beanie's default `id` factory generates UUIDs; we override to "current"
    in the route handler's upsert so the document is overwritten in place.
    """

    id: str = Field(default_factory=new_id)
    received_at: datetime = Field(default_factory=utcnow)
    onboarding: dict[str, Any]
    samples: dict[str, Any]

    class Settings:
        name = "input"


class OutputRecord(Document):
    """The latest Cox + Gemma prediction. Singleton; _id is always "current"."""

    id: str = Field(default_factory=new_id)
    computed_at: datetime = Field(default_factory=utcnow)
    input_uploaded_at: datetime

    scores: dict[str, dict[str, Any]]
    gemma_summary: str
    disclaimer: str
    model_metadata: dict[str, Any]

    class Settings:
        name = "output"


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
