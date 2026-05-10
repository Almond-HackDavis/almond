"""POST /input — sync Cox + Gemma pipeline (append-only).
GET  /output — read the most recently computed output document.

Flow on every POST /input:

  1. Validate the request via `schemas.InputRequest`.
  2. INSERT a new doc in `input` with a UUID hex `_id` and `received_at`.
  3. Run `ml.run_pipeline(...)` → raw_2yr_mortality + vitality + augmentation.
  4. Build a Gemma prompt; call `gemma.summarize(...)`. On Gemma failure,
     fall back to a deterministic summary so the request still succeeds.
  5. INSERT a new doc in `output` with its own UUID hex `_id`, an
     `input_id` foreign key pointing back at the input row, and a
     `computed_at` timestamp.
  6. Return the OutputDocument as the HTTP response.

The `input` and `output` collections are append-only — older rows are
NEVER overwritten. Every POST /input creates exactly two new rows and
returns the freshly-computed output as the HTTP response (so iOS gets
its correlated output synchronously). `GET /output` queries the latest
by `computed_at desc` so the dashboard always sees the most recent
prediction. `output.input_id` is the FK that lets us trace any score
back to the exact payload that produced it.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pymongo
from fastapi import APIRouter, HTTPException, status

import gemma
import ml
from db import InputRecord, OutputRecord, new_id, utcnow
from schemas import InputRequest, ModelMetadata, OutputDocument

log = logging.getLogger("almond.routes.input")

router = APIRouter(tags=["input"])


# ── Handlers ────────────────────────────────────────────────────────────────


@router.post(
    "/input",
    response_model=OutputDocument,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def submit_input(req: InputRequest) -> OutputDocument:
    received_at = utcnow()

    # 1. INSERT a new audit row into `input`. UUID id, never overwrites.
    onboarding_dict = req.onboarding.model_dump()
    samples_dict = req.samples.model_dump()
    input_id = await _insert_input(received_at, onboarding_dict, samples_dict)

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
        "_id": new_id(),
        "computed_at": utcnow(),
        "input_uploaded_at": received_at,
        "input_id": input_id,
        "scores": scores,
        "top_drivers": pipe.get("top_drivers", []),
        "gemma_summary": summary_text,
        "disclaimer": gemma.DISCLAIMER,
        "model_metadata": metadata.model_dump(),
    })

    # 5. INSERT a new audit row into `output`. UUID id, never overwrites.
    await _insert_output(out)

    return out


@router.get(
    "/output",
    response_model=OutputDocument,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def get_current_output() -> OutputDocument:
    """Return the most recently computed output (by `computed_at desc`).
    404s with `error.code = "no_output_yet"` when the user hasn't run
    any inputs yet — iOS should render an empty state."""
    doc = (
        await OutputRecord.find()
        .sort([(OutputRecord.computed_at, pymongo.DESCENDING)])
        .first_or_none()
    )
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


async def _insert_input(received_at, onboarding: dict, samples: dict) -> str:
    """Append a new input row. Returns the UUID hex `_id` so the caller
    can stash it on the matching output row as a foreign key."""
    rec = InputRecord(
        received_at=received_at,
        onboarding=onboarding,
        samples=samples,
    )
    await rec.insert()
    return rec.id


async def _insert_output(out: OutputDocument) -> None:
    """Append a new output row keyed by the UUID `out.id` already minted
    by the route handler. `input_id` carries the FK to the input row."""
    rec = OutputRecord(
        id=out.id,
        input_id=out.input_id or "",
        computed_at=out.computed_at,
        input_uploaded_at=out.input_uploaded_at,
        scores=out.scores,
        top_drivers=[d.model_dump() for d in out.top_drivers],
        gemma_summary=out.gemma_summary,
        disclaimer=out.disclaimer,
        model_metadata=out.model_metadata.model_dump(),
    )
    await rec.insert()


def _record_to_response(rec: OutputRecord) -> OutputDocument:
    return OutputDocument.model_validate({
        "_id": rec.id,
        "computed_at": rec.computed_at,
        "input_uploaded_at": rec.input_uploaded_at,
        "input_id": getattr(rec, "input_id", None),
        "scores": rec.scores or {},
        "top_drivers": getattr(rec, "top_drivers", None) or [],
        "gemma_summary": rec.gemma_summary,
        "disclaimer": rec.disclaimer,
        "model_metadata": rec.model_metadata,
    })
