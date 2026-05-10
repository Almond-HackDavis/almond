"""POST /input — sync Cox + Gemma pipeline.
GET  /output — read the latest "current" output document.

Flow on every POST /input:

  1. Validate the request via `schemas.InputRequest`.
  2. Persist the raw payload to `inputs` (append-only audit log).
  3. Run `ml.run_pipeline(...)` to get raw_2yr_mortality + vitality.
  4. Build a Gemma prompt; call `gemma.summarize(...)` for the user-facing
     summary paragraph. On Gemma failure, fall back to a deterministic
     human-readable string so the request still succeeds.
  5. Upsert the result to `outputs` with `_id="current"`, AND append a
     uuid-keyed history copy. Both share the same document shape.
  6. Return the "current" doc as the HTTP response.

GET /output simply re-reads `outputs._id="current"` and returns it. Useful
for iOS polling without re-running the pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, HTTPException, status

import gemma
import ml
from db import InputRecord, OutputRecord, utcnow
from schemas import (
    InputRequest,
    ModelMetadata,
    OutputDocument,
)

log = logging.getLogger("almond.routes.input")

router = APIRouter(tags=["input"])

CURRENT_OUTPUT_ID: str = "current"


# ── Handlers ────────────────────────────────────────────────────────────────


@router.post(
    "/input",
    response_model=OutputDocument,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def submit_input(req: InputRequest) -> OutputDocument:
    received_at = utcnow()

    # 1. Audit-persist raw payload.
    input_record = InputRecord(
        received_at=received_at,
        onboarding=req.onboarding.model_dump(),
        samples=req.samples.model_dump(),
    )
    await input_record.insert()

    # 2. Run ML pipeline.
    pipe = ml.run_pipeline(
        onboarding=req.onboarding.model_dump(),
        samples=req.samples.model_dump(),
    )
    raw_risk: float = pipe["raw_2yr_mortality"]
    vitality: float = pipe["vitality"]
    feats: dict[str, Any] = pipe["features"]

    # 3. Build Gemma prompt + summary. Falls back gracefully on errors so a
    #    Gemma outage doesn't break the entire request.
    samples_dict = req.samples.model_dump()
    avg_steps = _mean_of(samples_dict.get("steps_daily", []), "count")
    avg_kcal  = _mean_of(samples_dict.get("active_energy_daily_kcal", []), "kcal")
    avg_excm  = _mean_of(samples_dict.get("exercise_minutes_daily", []), "minutes")

    summary_text: str
    llm_model_used: str
    prompt_template_version: str = gemma.PROMPT_TEMPLATE_VERSION
    try:
        result = gemma.summarize(
            age=req.onboarding.age,
            sex=req.onboarding.sex,
            bmi=feats["_bmi_raw"],
            mean_sleep_min=feats["_mean_sleep_min"],
            avg_steps=avg_steps,
            avg_kcal=avg_kcal,
            avg_exercise_min=avg_excm,
            vitality=vitality,
            raw_risk=raw_risk,
        )
        summary_text = result.summary
        llm_model_used = result.model
        prompt_template_version = result.prompt_template_version
    except Exception as exc:
        log.warning("Gemma call failed (%s); using fallback summary", exc)
        summary_text = _fallback_summary(vitality, feats)
        llm_model_used = "fallback-deterministic-v0"

    # 4. Build the output document. Per-score dicts have different shapes —
    #    vitality has `max`, mortality has `ci_low`/`ci_high` (nullable).
    scores: dict[str, dict[str, Any]] = {
        "vitality_score":       {"value": round(vitality, 1), "max": 100.0},
        "nhanes_mortality_2yr": {"value": round(raw_risk, 4), "ci_low": None, "ci_high": None},
    }
    metadata = ModelMetadata(
        model_id=ml.MODEL_ID,
        prompt_template_version=prompt_template_version,
        llm_model=llm_model_used,
        horizon_months=ml.HORIZON_MONTHS,
    )
    out = OutputDocument.model_validate({
        "_id": CURRENT_OUTPUT_ID,
        "computed_at": utcnow(),
        "input_uploaded_at": received_at,
        "scores": scores,
        "gemma_summary": summary_text,
        "disclaimer": gemma.DISCLAIMER,
        "model_metadata": metadata.model_dump(),
    })

    # 5. Persist (upsert "current" + append a uuid history copy).
    await _upsert_current(out, input_id=input_record.id)
    await _append_history(out, input_id=input_record.id)

    return out


@router.get(
    "/output",
    response_model=OutputDocument,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def get_current_output() -> OutputDocument:
    doc = await OutputRecord.get(CURRENT_OUTPUT_ID)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "no_output_yet",
                    "message": "No POST /input has been processed yet.",
                    "details": {},
                }
            },
        )
    return _record_to_response(doc)


# ── Helpers ────────────────────────────────────────────────────────────────


def _mean_of(rows: list[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows if isinstance(r, dict) and key in r and r[key] is not None]
    return float(np.mean(vals)) if vals else 0.0


def _fallback_summary(vitality: float, feats: dict[str, Any]) -> str:
    """Deterministic backup when Gemma is unavailable. No PII, no dynamic data."""
    age = int(feats.get("age", 0))
    if vitality >= 80:
        tone = (
            "Your Vitality Score is strong. Body composition, sleep, and "
            "activity all look like healthy contributors at your age. Keep "
            "the routine you have and consider anchoring sleep timing as the "
            "next compounding upgrade."
        )
    elif vitality >= 50:
        tone = (
            "Your Vitality Score is a healthy middle. Your activity volume "
            "and sleep duration are in a reasonable range; the biggest lever "
            "from here is small, consistent improvements — a 10-minute "
            "walking routine in the evening or a 30-minute earlier bedtime."
        )
    else:
        tone = (
            "Your Vitality Score has room to grow. A daily walking routine "
            "and a consistent 7.5-hour sleep window are the two highest-"
            "impact changes. Start with whichever one you can stack onto an "
            "existing habit this week."
        )
    return tone + f" (Snapshot generated for a {age}-year-old user.)"


async def _upsert_current(out: OutputDocument, *, input_id: str) -> None:
    """Replace `outputs._id="current"` with the new row."""
    coll = OutputRecord.get_pymongo_collection()
    payload = _to_mongo_doc(out, input_id=input_id, override_id=CURRENT_OUTPUT_ID)
    await coll.replace_one({"_id": CURRENT_OUTPUT_ID}, payload, upsert=True)


async def _append_history(out: OutputDocument, *, input_id: str) -> None:
    """Append a UUID-keyed copy so we keep history."""
    history_id = uuid4().hex
    rec = OutputRecord(
        id=history_id,
        computed_at=out.computed_at,
        input_uploaded_at=out.input_uploaded_at,
        input_id=input_id,
        scores=out.scores,
        gemma_summary=out.gemma_summary,
        disclaimer=out.disclaimer,
        model_metadata=out.model_metadata.model_dump(),
    )
    await rec.insert()


def _to_mongo_doc(out: OutputDocument, *, input_id: str, override_id: str) -> dict[str, Any]:
    """Pydantic → BSON-shaped dict for direct collection writes."""
    return {
        "_id": override_id,
        "computed_at": out.computed_at,
        "input_uploaded_at": out.input_uploaded_at,
        "input_id": input_id,
        "scores": out.scores,
        "gemma_summary": out.gemma_summary,
        "disclaimer": out.disclaimer,
        "model_metadata": out.model_metadata.model_dump(),
    }


def _record_to_response(rec: OutputRecord) -> OutputDocument:
    return OutputDocument.model_validate({
        "_id": rec.id,
        "computed_at": rec.computed_at,
        "input_uploaded_at": rec.input_uploaded_at,
        "scores": rec.scores or {},
        "gemma_summary": rec.gemma_summary,
        "disclaimer": rec.disclaimer,
        "model_metadata": rec.model_metadata,
    })
