"""Phase 3 — small iOS-facing API. Wraps Atlas with three HTTP endpoints.

This is the contract iOS hits. The API is a thin shim over MongoDB Atlas:

    iOS  ── POST /input ──────────→  writes to almond.input  (status=pending)
    iOS  ── GET  /output/{id} ────→  reads from almond.output (404 until ready)
    iOS  ── GET  /input/{id} ─────→  reads from almond.input  (status echo)

The 04_worker.py process polls almond.input independently, runs Cox + Gemini,
and writes to almond.output. Both ends talk to the same Atlas cluster so this
API does not need to know about the worker at all — they meet at the DB.

Run:

    inspect/.venv/bin/uvicorn 06_api:app --reload --port 8000 \\
      --app-dir inspect

Env (read from inspect/.env):

    MONGODB_URI   — required, Atlas SRV string
    MONGODB_DB    — default `almond`
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import ASCENDING, MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


# ── Pydantic shapes for the iOS contract ─────────────────────────────────────

class Onboarding(BaseModel):
    """Demographics the iOS engineer collects once at install + onboarding."""
    age: int = Field(..., ge=18, le=100)
    sex: str = Field(..., pattern="^[MF]$")
    height_cm: float = Field(..., ge=100, le=250)
    weight_kg: float = Field(..., ge=30, le=250)
    # Optional fields the worker doesn't currently use — accepted so iOS can
    # bundle them now and we can wire them in later without a contract change.
    smoking: Optional[bool] = None
    diabetes: Optional[bool] = None
    family_history_cvd: Optional[bool] = None
    race_ethnicity: Optional[str] = None
    systolic_bp: Optional[int] = None
    total_cholesterol: Optional[int] = None
    hdl_cholesterol: Optional[int] = None
    on_bp_medication: Optional[bool] = None


class InputRequest(BaseModel):
    """What iOS POSTs to /input. samples is the 90-day HK rollup."""
    user_id: str = Field(..., min_length=1)
    onboarding: Onboarding
    samples: dict[str, Any]   # opaque to the API; the worker reads it


class InputResponse(BaseModel):
    input_id: str
    user_id: str
    status: str
    received_at: datetime


class StatusResponse(BaseModel):
    input_id: str
    user_id: str
    status: str
    uploaded_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


# ── Lifespan: open + close one Mongo client per process ──────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "almond")
    if not uri:
        raise RuntimeError("MONGODB_URI not set in inspect/.env")
    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    db = client[db_name]
    db["input"].create_index([("status", ASCENDING), ("uploaded_at", ASCENDING)],
                             name="ix_status_uploaded")
    db["output"].create_index([("input_id", ASCENDING)], unique=True,
                              name="ux_input_id")
    db["output"].create_index([("user_id", ASCENDING), ("computed_at", ASCENDING)],
                              name="ix_user_computed")
    app.state.mongo = client
    app.state.db = db
    yield
    client.close()


app = FastAPI(
    title="almond — iOS bridge API",
    version="0.1.0",
    description="Thin shim over MongoDB Atlas. iOS POSTs input, polls /output.",
    lifespan=lifespan,
)

# Wide-open CORS — fine for hackathon; tighten for prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    """Liveness probe — confirms the API + Atlas connection."""
    db = app.state.db
    return {
        "ok": True,
        "db": db.name,
        "input_count":  db["input"].estimated_document_count(),
        "output_count": db["output"].estimated_document_count(),
        "pending":      db["input"].count_documents({"status": "pending"}),
    }


@app.post("/input", response_model=InputResponse, status_code=status.HTTP_201_CREATED)
def submit_input(req: InputRequest) -> InputResponse:
    """iOS calls this after assembling the 90-day HealthKit window.

    Inserts a document into `input` with status=pending. The worker picks it
    up on its next poll and writes the result to `output`. iOS should then
    poll `GET /output/{input_id}` until it returns 200.
    """
    now = datetime.now(timezone.utc)
    doc = {
        "_id":          str(uuid4()),
        "user_id":      req.user_id,
        "uploaded_at":  now,
        "status":       "pending",
        "claimed_at":   None,
        "claimed_by":   None,
        "onboarding":   req.onboarding.model_dump(),
        "samples":      req.samples,
    }
    app.state.db["input"].insert_one(doc)
    return InputResponse(
        input_id=doc["_id"],
        user_id=req.user_id,
        status="pending",
        received_at=now,
    )


@app.get("/input/{input_id}", response_model=StatusResponse)
def get_input_status(input_id: str) -> StatusResponse:
    """Returns the status of a previously submitted input — useful for polling.

    Does NOT return the raw payload (privacy + bandwidth). Use /output/{id}
    to fetch the prediction once status flips to 'done'.
    """
    doc = app.state.db["input"].find_one({"_id": input_id})
    if doc is None:
        raise HTTPException(status_code=404, detail={"error": "input_not_found"})
    return StatusResponse(
        input_id=doc["_id"],
        user_id=doc["user_id"],
        status=doc["status"],
        uploaded_at=doc["uploaded_at"],
        completed_at=doc.get("completed_at"),
        failure_reason=doc.get("failure_reason"),
    )


@app.get("/output/{input_id}")
def get_output_for_input(input_id: str) -> dict:
    """Returns the prediction for a given input_id. 404 until the worker
    finishes processing.

    Response shape is the full output document — vitality_score,
    nhanes_mortality_2yr, gemini_recommendation, model_metadata, etc.
    """
    doc = app.state.db["output"].find_one({"input_id": input_id})
    if doc is None:
        # Either truly missing or still pending. Distinguish with input doc lookup.
        in_doc = app.state.db["input"].find_one({"_id": input_id}, {"status": 1})
        if in_doc is None:
            raise HTTPException(status_code=404, detail={"error": "input_not_found"})
        raise HTTPException(
            status_code=404,
            detail={"error": "not_ready", "status": in_doc["status"]},
        )
    return doc


@app.get("/output/latest/{user_id}")
def get_latest_output_for_user(user_id: str) -> dict:
    """Returns the most recent done prediction for a user. 404 if none yet."""
    doc = (
        app.state.db["output"]
        .find({"user_id": user_id})
        .sort("computed_at", -1)
        .limit(1)
    )
    docs = list(doc)
    if not docs:
        raise HTTPException(status_code=404, detail={"error": "no_outputs_for_user"})
    return docs[0]
