"""Single-user iOS-facing API. One input doc, one output doc, both singletons.

Architecture:

    iOS  ──hourly POST /input─→  upserts almond.input  (_id="current", dirty=True)
                                          │
                                          ▼
                                  04_worker.py polls; when dirty=True,
                                  runs Cox + Gemini and upserts almond.output
                                          │
                                          ▼
    iOS  ─────GET /output──────→  reads almond.output (_id="current")

Both collections hold exactly one document at all times (after the first
POST). The iOS engineer never deals with IDs — input is identified by being
*the* input, output by being *the* output. Hourly re-POSTs replace the
input contents in place; the worker writes a fresh prediction over the same
output _id.

Run:

    inspect/.venv/bin/uvicorn 06_api:app --port 8000 --app-dir inspect
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


SINGLETON_ID = "current"


# ── Pydantic shapes for the iOS contract ─────────────────────────────────────

class Onboarding(BaseModel):
    age: int = Field(..., ge=18, le=100)
    sex: str = Field(..., pattern="^[MF]$")
    height_cm: float = Field(..., ge=100, le=250)
    weight_kg: float = Field(..., ge=30, le=250)
    # Optional clinical fields — accepted now even though the current 4-feature
    # Cox model doesn't use them. Keeps the contract stable as we add features.
    smoking: Optional[bool] = None
    diabetes: Optional[bool] = None
    family_history_cvd: Optional[bool] = None
    race_ethnicity: Optional[str] = None
    systolic_bp: Optional[int] = None
    total_cholesterol: Optional[int] = None
    hdl_cholesterol: Optional[int] = None
    on_bp_medication: Optional[bool] = None


class InputRequest(BaseModel):
    onboarding: Onboarding
    samples: dict[str, Any]   # opaque to the API; the worker reads it


class InputAck(BaseModel):
    status: str
    received_at: datetime


# ── Lifespan: open + close one Mongo client per process ──────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "almond")
    if not uri:
        raise RuntimeError("MONGODB_URI not set in inspect/.env")
    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    app.state.mongo = client
    app.state.db = client[db_name]
    yield
    client.close()


app = FastAPI(
    title="almond — single-user iOS bridge",
    version="0.2.0",
    description="POST /input upserts the singleton input. GET /output reads the singleton output.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    db = app.state.db
    in_doc  = db["input"].find_one({"_id": SINGLETON_ID}, {"last_uploaded_at": 1, "dirty": 1})
    out_doc = db["output"].find_one({"_id": SINGLETON_ID}, {"computed_at": 1})
    return {
        "ok": True,
        "db": db.name,
        "input": {
            "exists": in_doc is not None,
            "last_uploaded_at": in_doc.get("last_uploaded_at") if in_doc else None,
            "dirty": in_doc.get("dirty") if in_doc else None,
        },
        "output": {
            "exists": out_doc is not None,
            "computed_at": out_doc.get("computed_at") if out_doc else None,
        },
    }


@app.post("/input", response_model=InputAck)
def upsert_input(req: InputRequest) -> InputAck:
    """iOS calls this every hour while the app is open. Replaces the singleton.

    The doc is marked `dirty=True`; the worker picks it up on its next poll
    (within ~2 s), runs Cox + Gemini, and upserts the singleton output.
    """
    now = datetime.now(timezone.utc)
    app.state.db["input"].update_one(
        {"_id": SINGLETON_ID},
        {"$set": {
            "onboarding":       req.onboarding.model_dump(),
            "samples":          req.samples,
            "last_uploaded_at": now,
            "dirty":            True,
        }},
        upsert=True,
    )
    return InputAck(status="ok", received_at=now)


@app.get("/input")
def get_input() -> dict:
    doc = app.state.db["input"].find_one({"_id": SINGLETON_ID})
    if doc is None:
        raise HTTPException(status_code=404, detail={"error": "no_input_yet"})
    return doc


@app.get("/output")
def get_output() -> dict:
    """Returns the current prediction. 404 until the worker has run at least once."""
    doc = app.state.db["output"].find_one({"_id": SINGLETON_ID})
    if doc is None:
        in_doc = app.state.db["input"].find_one({"_id": SINGLETON_ID}, {"dirty": 1})
        if in_doc is None:
            raise HTTPException(status_code=404, detail={"error": "no_input_yet"})
        raise HTTPException(
            status_code=404,
            detail={"error": "not_ready", "dirty": in_doc.get("dirty", True)},
        )
    return doc
