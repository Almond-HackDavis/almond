"""POST /onboarding — one-shot demographic + clinical questionnaire."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_current_user_id
from db import Onboarding, utcnow
from schemas import OnboardingRequest, OnboardingResponse

router = APIRouter(tags=["onboarding"])


@router.post("/onboarding", response_model=OnboardingResponse)
async def submit_onboarding(
    req: OnboardingRequest,
    user_id: str = Depends(get_current_user_id),
) -> OnboardingResponse:
    existing = await Onboarding.find_one(Onboarding.user_id == user_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "onboarding_already_submitted",
                    "message": "User already has an onboarding record",
                    "details": {"onboarding_id": existing.id},
                }
            },
        )

    doc = Onboarding(
        user_id=user_id,
        age=req.age,
        sex=req.sex,
        height_cm=req.height_cm,
        weight_kg=req.weight_kg,
        smoking=req.smoking,
        diabetes=req.diabetes,
        family_history_cvd=req.family_history_cvd,
        race_ethnicity=req.race_ethnicity,
        systolic_bp=req.systolic_bp,
        total_cholesterol=req.total_cholesterol,
        hdl_cholesterol=req.hdl_cholesterol,
        on_bp_medication=req.on_bp_medication,
        completed_at=utcnow(),
    )
    await doc.insert()

    return OnboardingResponse(onboarding_id=UUID(doc.id), completed_at=doc.completed_at)
