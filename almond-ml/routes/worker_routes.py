"""Worker-facing endpoints.

The offline ML/Gemini worker is a separate Python process (NOT in this repo).
It polls these endpoints with `Authorization: Bearer <WORKER_API_KEY>`. Auth
is intentionally separate from session JWTs.

Flow:

  1. GET /uploads?status=pending&limit=10 → list of pending upload summaries.
  2. GET /uploads/{id} → full payload + embedded onboarding + atomic
     status-flip from pending → scoring with `claimed_at` set.
  3. POST /uploads/{id}/result → persist the prediction, flip status → done.
  4. POST /uploads/{id}/fail → flip status → failed, store the error.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

import pymongo
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import get_worker_auth
from db import HealthKitUpload, Onboarding, RiskPrediction, utcnow
from schemas import (
    WorkerFailRequest,
    WorkerFailResponse,
    WorkerResultRequest,
    WorkerResultResponse,
    WorkerUploadDetail,
    WorkerUploadList,
    WorkerUploadSummary,
)

router = APIRouter(tags=["worker"])


@router.get("/uploads", response_model=WorkerUploadList)
async def list_uploads(
    status_filter: Literal["pending", "scoring", "recommending", "done", "failed"] = Query(
        default="pending", alias="status"
    ),
    limit: int = Query(default=10, ge=1, le=100),
    _worker_id: str = Depends(get_worker_auth),
) -> WorkerUploadList:
    """List uploads in a given status, oldest first.

    Default filter `pending` matches the worker's normal poll loop. The
    `scoring`/`recommending`/`failed` options are for ops/debug visibility.
    """
    docs = (
        await HealthKitUpload.find(HealthKitUpload.status == status_filter)
        .sort([(HealthKitUpload.uploaded_at, pymongo.ASCENDING)])
        .limit(limit)
        .to_list()
    )
    return WorkerUploadList(
        uploads=[
            WorkerUploadSummary(
                upload_id=UUID(d.id),
                user_id=UUID(d.user_id),
                uploaded_at=d.uploaded_at,
            )
            for d in docs
        ]
    )


@router.get("/uploads/{upload_id}", response_model=WorkerUploadDetail)
async def get_upload(
    upload_id: UUID,
    worker_id: str = Depends(get_worker_auth),
) -> WorkerUploadDetail:
    """Atomic claim — only succeeds for an upload currently in `pending`.

    Once claimed, status flips to `scoring` and `claimed_at` / `claimed_by`
    are set so a second worker polling concurrently won't double-process.
    """
    upload_id_hex = upload_id.hex

    # Atomic find_one_and_update — race-safe.
    # NB: Beanie 2.x renamed `get_motor_collection` → `get_pymongo_collection`.
    coll = HealthKitUpload.get_pymongo_collection()
    raw = await coll.find_one_and_update(
        {"_id": upload_id_hex, "status": "pending"},
        {"$set": {"status": "scoring", "claimed_at": utcnow(), "claimed_by": worker_id}},
        return_document=pymongo.ReturnDocument.AFTER,
    )

    # If the atomic claim missed (already claimed or wrong id), fall back to a
    # plain read — return current state if it exists, 404 otherwise.
    if raw is None:
        existing = await HealthKitUpload.get(upload_id_hex)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "upload_not_found", "message": "No such upload", "details": {}}},
            )
        upload = existing
    else:
        upload = HealthKitUpload.model_validate(raw)

    onboarding_doc = await Onboarding.find_one(Onboarding.user_id == upload.user_id)
    onboarding_dict = (
        onboarding_doc.model_dump(mode="json", exclude={"id"})
        if onboarding_doc is not None
        else None
    )

    return WorkerUploadDetail(
        upload_id=UUID(upload.id),
        user_id=UUID(upload.user_id),
        uploaded_at=upload.uploaded_at,
        window_start=upload.window_start,
        window_end=upload.window_end,
        payload=upload.payload,
        onboarding=onboarding_dict,
        status=upload.status,
    )


@router.post("/uploads/{upload_id}/result", response_model=WorkerResultResponse)
async def submit_result(
    upload_id: UUID,
    req: WorkerResultRequest,
    _worker_id: str = Depends(get_worker_auth),
) -> WorkerResultResponse:
    upload_id_hex = upload_id.hex

    upload = await HealthKitUpload.get(upload_id_hex)
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "upload_not_found", "message": "No such upload", "details": {}}},
        )

    existing = await RiskPrediction.find_one(RiskPrediction.upload_id == upload_id_hex)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "prediction_already_exists",
                    "message": "A prediction has already been submitted for this upload",
                    "details": {"prediction_id": existing.id},
                }
            },
        )

    pred = RiskPrediction(
        user_id=upload.user_id,
        upload_id=upload_id_hex,
        scores=req.scores,
        top_drivers=req.top_drivers,
        gemini_recommendation=req.gemini_recommendation,
        model_metadata=req.model_metadata,
    )
    await pred.insert()

    upload.status = "done"
    await upload.save()

    return WorkerResultResponse(prediction_id=UUID(pred.id))


@router.post("/uploads/{upload_id}/fail", response_model=WorkerFailResponse)
async def submit_fail(
    upload_id: UUID,
    req: WorkerFailRequest,
    _worker_id: str = Depends(get_worker_auth),
) -> WorkerFailResponse:
    upload_id_hex = upload_id.hex

    upload = await HealthKitUpload.get(upload_id_hex)
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "upload_not_found", "message": "No such upload", "details": {}}},
        )

    upload.status = "failed"
    upload.failure_reason = req.error
    upload.failure_stage = req.stage
    await upload.save()

    return WorkerFailResponse(upload_id=UUID(upload.id), status="failed")
