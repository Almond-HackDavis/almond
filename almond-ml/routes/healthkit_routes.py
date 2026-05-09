"""HealthKit upload + risk read + history endpoints (iOS-facing).

Override of AGENTS.md: POST /healthkit returns immediately with status="pending".
The offline worker picks up the upload via /uploads/* and POSTs the prediction
back. iOS polls GET /risk?upload_id=<id> until status=="done".
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional
from uuid import UUID

import pymongo
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import get_current_user_id
from db import HealthKitUpload, RiskPrediction, utcnow
from schemas import (
    HealthKitUploadRequest,
    HealthKitUploadResponse,
    HistoryResponse,
    RiskResponse,
    RiskResponseFull,
    RiskResponsePending,
    TopDriver,
)

router = APIRouter(tags=["healthkit"])


@router.post("/healthkit", response_model=HealthKitUploadResponse)
async def upload_healthkit(
    req: HealthKitUploadRequest,
    user_id: str = Depends(get_current_user_id),
) -> HealthKitUploadResponse:
    """Persist the raw payload with status=pending. Worker handles processing."""
    doc = HealthKitUpload(
        user_id=user_id,
        uploaded_at=utcnow(),
        window_start=req.window_start,
        window_end=req.window_end,
        payload=req.samples,
        status="pending",
    )
    await doc.insert()

    return HealthKitUploadResponse(
        upload_id=UUID(doc.id),
        received_at=doc.uploaded_at,
        status="pending",
    )


@router.get("/risk", response_model=RiskResponse)
async def get_risk(
    upload_id: Optional[UUID] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> RiskResponse:
    """Return the most recent done prediction OR the prediction for a given upload.

    * `upload_id` supplied + status != done → return `{upload_id, status}` only.
    * `upload_id` supplied + status == done → return the full prediction.
    * `upload_id` supplied but doesn't belong to this user → 404 (no leak).
    * `upload_id` omitted → most-recent done prediction for the user, or 404.
    """
    if upload_id is not None:
        return await _get_risk_by_upload(upload_id.hex, user_id)
    return await _get_latest_risk(user_id)


async def _get_risk_by_upload(upload_id_hex: str, user_id: str) -> RiskResponse:
    upload = await HealthKitUpload.get(upload_id_hex)
    if upload is None or upload.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "upload_not_found", "message": "No such upload", "details": {}}},
        )

    if upload.status != "done":
        return RiskResponsePending(upload_id=UUID(upload.id), status=upload.status)

    pred = await RiskPrediction.find_one(RiskPrediction.upload_id == upload_id_hex)
    if pred is None:
        # Inconsistent state — upload says done but no prediction. Treat as pending.
        return RiskResponsePending(upload_id=UUID(upload.id), status="scoring")

    return _to_full_response(pred)


async def _get_latest_risk(user_id: str) -> RiskResponse:
    pred = (
        await RiskPrediction.find(RiskPrediction.user_id == user_id)
        .sort([(RiskPrediction.computed_at, pymongo.DESCENDING)])
        .first_or_none()
    )
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "no_predictions_yet", "message": "No completed predictions for user", "details": {}}},
        )
    return _to_full_response(pred)


def _to_full_response(pred: RiskPrediction) -> RiskResponseFull:
    return RiskResponseFull(
        upload_id=UUID(pred.upload_id),
        status="done",
        computed_at=pred.computed_at,
        scores=pred.scores,
        # top_drivers is stored as raw dicts; pydantic v2 coerces.
        top_drivers=[TopDriver(**d) for d in pred.top_drivers],
        gemini_recommendation=pred.gemini_recommendation,  # type: ignore[arg-type]
        model_metadata=pred.model_metadata,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    days: int = Query(default=90, ge=7, le=365),
    user_id: str = Depends(get_current_user_id),
) -> HistoryResponse:
    """Return a `days`-long window of trend data, one entry per prediction."""
    cutoff = utcnow() - timedelta(days=days)
    preds = (
        await RiskPrediction.find(
            RiskPrediction.user_id == user_id,
            RiskPrediction.computed_at >= cutoff,
        )
        .sort([(RiskPrediction.computed_at, pymongo.ASCENDING)])
        .to_list()
    )

    # Build a series-per-score-key. Sample shape kept compatible with AGENTS.md.
    series: dict[str, list[dict]] = {}
    for p in preds:
        date_str = p.computed_at.date().isoformat()
        for score_key, score_payload in (p.scores or {}).items():
            value = (score_payload or {}).get("value")
            if value is None:
                continue
            series.setdefault(score_key, []).append({"date": date_str, "value": value})

    return HistoryResponse(user_id=UUID(user_id), days=days, series=series)
