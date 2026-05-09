"""POST /auth/login — exchange an Apple identity token for a session JWT."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from auth import issue_session_jwt, verify_apple_token
from db import Onboarding, User
from schemas import AuthLoginRequest, AuthLoginResponse

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=AuthLoginResponse)
async def login(req: AuthLoginRequest) -> AuthLoginResponse:
    apple_sub = await verify_apple_token(req.apple_identity_token)

    # Find-or-create the user. Apple's `sub` is stable per (Apple ID, app),
    # so it's our primary key into the users collection.
    user = await User.find_one(User.apple_user_id == apple_sub)
    is_new_user = user is None
    if is_new_user:
        user = User(apple_user_id=apple_sub)
        await user.insert()

    onboarding_exists = await Onboarding.find_one(Onboarding.user_id == user.id) is not None

    return AuthLoginResponse(
        user_id=UUID(user.id),
        session_token=issue_session_jwt(user.id),
        is_new_user=is_new_user,
        needs_onboarding=not onboarding_exists,
    )
