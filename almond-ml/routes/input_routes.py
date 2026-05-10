"""POST /input — sync Cox + Gemma pipeline.
GET  /output — read the latest "current" output document.

Flow on every POST /input:

  1. Validate the request via `schemas.InputRequest`.
  2. Upsert the raw payload to the `input` collection at _id="current".
  3. Run `ml.run_pipeline(...)` → raw_2yr_mortality + vitality.
  4. Build a Gemma prompt; call `gemma.summarize(...)`. On Gemma failure,
     fall back to a deterministic summary so the request still succeeds.
  5. Upsert the result to the `output` collection at _id="current".
  6. Return the OutputDocument as the HTTP response.

Both `input` and `output` are SINGLETON collections — exactly one row each,
overwritten on every request. There is no history; iOS reads
`output._id="current"` to render the dashboard.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, status

import gemma
import ml
from db import InputRecord, OutputRecord, utcnow
from schemas import InputRequest, ModelMetadata, OutputDocument

log = logging.getLogger("almond.routes.input")

router = APIRouter(tags=["input"])

CURRENT_ID: str = "current"


# ── Handlers ────────────────────────────────────────────────────────────────


@router.post(
    "/input",
    response_model=OutputDocument,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def submit_input(req: InputRequest) -> OutputDocument:
    received_at = utcnow()

    # 1. Upsert the raw payload to input._id="current".
    onboarding_dict = req.onboarding.model_dump()
    samples_dict = req.samples.model_dump()
    await _upsert_input(received_at, onboarding_dict, samples_dict)

    # 2. Run ML pipeline.
    pipe = ml.run_pipeline(onboarding=onboarding_dict, samples=samples_dict)
    raw_risk: float = pipe["raw_2yr_mortality"]
    vitality: float = pipe["vitality"]
    feats: dict[str, Any] = pipe["features"]

    # 3. Call Gemma. Fallback summary on any failure so the score still ships.
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
    #    vitality has `max`, mortality has `ci_low`/`ci_high` (nullable),
    #    fitness_age has chronological_age + delta and is omitted when iOS
    #    didn't send VO2 max.
    scores: dict[str, dict[str, Any]] = {
        "vitality_score":       {"value": round(vitality, 1), "max": 100.0},
        "nhanes_mortality_2yr": {"value": round(raw_risk, 4), "ci_low": None, "ci_high": None},
    }
    if pipe.get("fitness_age") is not None:
        scores["fitness_age"] = pipe["fitness_age"]

    metadata = ModelMetadata(
        model_id=ml.MODEL_ID,
        prompt_template_version=prompt_template_version,
        llm_model=llm_model_used,
        horizon_months=ml.HORIZON_MONTHS,
    )
    out = OutputDocument.model_validate({
        "_id": CURRENT_ID,
        "computed_at": utcnow(),
        "input_uploaded_at": received_at,
        "scores": scores,
        "top_drivers": pipe.get("top_drivers", []),
        "gemma_summary": summary_text,
        "disclaimer": gemma.DISCLAIMER,
        "model_metadata": metadata.model_dump(),
    })

    # 5. Upsert output._id="current".
    await _upsert_output(out)

    return out


@router.get(
    "/output",
    response_model=OutputDocument,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def get_current_output() -> OutputDocument:
    doc = await OutputRecord.get(CURRENT_ID)
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
    """Deterministic backup when Gemma is unavailable. No PII, no medical advice."""
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


async def _upsert_input(received_at, onboarding: dict, samples: dict) -> None:
    """Replace `input._id="current"` with the new payload."""
    coll = InputRecord.get_pymongo_collection()
    await coll.replace_one(
        {"_id": CURRENT_ID},
        {
            "_id": CURRENT_ID,
            "received_at": received_at,
            "onboarding": onboarding,
            "samples": samples,
        },
        upsert=True,
    )


async def _upsert_output(out: OutputDocument) -> None:
    """Replace `output._id="current"` with the new prediction."""
    coll = OutputRecord.get_pymongo_collection()
    await coll.replace_one(
        {"_id": CURRENT_ID},
        {
            "_id": CURRENT_ID,
            "computed_at": out.computed_at,
            "input_uploaded_at": out.input_uploaded_at,
            "scores": out.scores,
            "top_drivers": [d.model_dump() for d in out.top_drivers],
            "gemma_summary": out.gemma_summary,
            "disclaimer": out.disclaimer,
            "model_metadata": out.model_metadata.model_dump(),
        },
        upsert=True,
    )


def _record_to_response(rec: OutputRecord) -> OutputDocument:
    return OutputDocument.model_validate({
        "_id": rec.id,
        "computed_at": rec.computed_at,
        "input_uploaded_at": rec.input_uploaded_at,
        "scores": rec.scores or {},
        "top_drivers": getattr(rec, "top_drivers", None) or [],
        "gemma_summary": rec.gemma_summary,
        "disclaimer": rec.disclaimer,
        "model_metadata": rec.model_metadata,
    })
