"""POST /onboarding — first submission, conflict, validation."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


VALID_BODY = {
    "age": 32,
    "sex": "M",
    "height_cm": 178.0,
    "weight_kg": 75.5,
    "smoking": False,
    "diabetes": False,
    "family_history_cvd": False,
    "race_ethnicity": "white",
    "systolic_bp": 122,
    "total_cholesterol": None,
    "hdl_cholesterol": None,
    "on_bp_medication": False,
}


async def test_first_onboarding_returns_200_and_persists(client, auth_headers):
    resp = await client.post("/onboarding", json=VALID_BODY, headers=auth_headers)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "onboarding_id" in body
    assert "completed_at" in body


async def test_second_onboarding_returns_409(client, auth_headers):
    first = await client.post("/onboarding", json=VALID_BODY, headers=auth_headers)
    assert first.status_code == 200

    second = await client.post("/onboarding", json=VALID_BODY, headers=auth_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "onboarding_already_submitted"


async def test_login_after_onboarding_signals_no_onboarding_needed(
    client, auth_headers, make_apple_token, authed_user
):
    # Submit onboarding first.
    submit = await client.post("/onboarding", json=VALID_BODY, headers=auth_headers)
    assert submit.status_code == 200

    # Re-login as the SAME Apple user.
    relogin = await client.post(
        "/auth/login",
        json={"apple_identity_token": make_apple_token(sub=authed_user["apple_sub"])},
    )
    assert relogin.status_code == 200
    body = relogin.json()
    assert body["is_new_user"] is False
    assert body["needs_onboarding"] is False


@pytest.mark.parametrize(
    "patch,expected_code",
    [
        ({"age": 12}, 422),                          # under 18
        ({"age": 200}, 422),                         # too old
        ({"sex": "X"}, 422),                         # bad enum
        ({"height_cm": 10.0}, 422),                  # too short
        ({"weight_kg": -5.0}, 422),                  # negative
        ({"systolic_bp": 500}, 422),                 # absurd
    ],
)
async def test_invalid_field_values_return_422(client, auth_headers, patch, expected_code):
    body = {**VALID_BODY, **patch}
    resp = await client.post("/onboarding", json=body, headers=auth_headers)
    assert resp.status_code == expected_code, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


async def test_missing_required_field_returns_422(client, auth_headers):
    body = {**VALID_BODY}
    body.pop("smoking")
    resp = await client.post("/onboarding", json=body, headers=auth_headers)
    assert resp.status_code == 422


async def test_unauth_returns_401(client):
    resp = await client.post("/onboarding", json=VALID_BODY)
    assert resp.status_code == 401
