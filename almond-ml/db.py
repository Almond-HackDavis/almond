"""MongoDB layer.

Two append-only collections:

  * `input`   — every POST /input payload, one doc per request.
                _id is a UUID hex string, indexed on `received_at` desc.
  * `output`  — every Cox + Gemma result, one doc per request.
                _id is a UUID hex string. Each row carries `input_id`
                pointing back at the input that produced it. Indexed on
                `computed_at` desc so `GET /output` can read the latest
                with a single key lookup.

iOS reads `GET /output` for the latest single-row dashboard tile (sorted
by `computed_at desc`). History is what powers a temporal dashboard:
vitality_score over time, fitness_age over time, top_drivers churn
between sessions. Older data is never overwritten.

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
    """One POST /input payload. Append-only; UUID hex ids."""

    id: str = Field(default_factory=new_id)
    received_at: datetime = Field(default_factory=utcnow)
    onboarding: dict[str, Any]
    samples: dict[str, Any]

    class Settings:
        name = "input"
        indexes = [
            pymongo.IndexModel(
                [("received_at", pymongo.DESCENDING)],
                name="received_at_desc",
            ),
        ]


class OutputRecord(Document):
    """One Cox + Gemma prediction. Append-only; UUID hex ids.

    `input_id` points back at the InputRecord that produced this output —
    useful for debugging ("which exact payload yielded this score") and
    for the temporal dashboard's drill-down.
    """

    id: str = Field(default_factory=new_id)
    input_id: str
    computed_at: datetime = Field(default_factory=utcnow)
    input_uploaded_at: datetime

    scores: dict[str, dict[str, Any]]
    top_drivers: list[dict[str, Any]] = Field(default_factory=list)
    gemma_summary: str
    disclaimer: str
    model_metadata: dict[str, Any]

    class Settings:
        name = "output"
        indexes = [
            pymongo.IndexModel(
                [("computed_at", pymongo.DESCENDING)],
                name="computed_at_desc",
            ),
            pymongo.IndexModel("input_id", name="input_id"),
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
