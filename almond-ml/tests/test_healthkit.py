"""POST /healthkit + GET /risk + GET /history — iOS-facing endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _sample_upload_body() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "uploaded_at": now.isoformat(),
        "window_start": (now - timedelta(days=90)).isoformat(),
        "window_end": now.isoformat(),
        "samples": {
            "resting_hr_daily": [{"date": "2026-04-18", "bpm": 62}],
            "steps_daily": [{"date": "2026-04-18", "count": 8243}],
            # Treated as opaque — backend doesn't validate inner shape.
        },
    }


class TestUpload:
    async def test_valid_upload_returns_pending_status(self, client, auth_headers):
        resp = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "pending"
        assert "upload_id" in body
        assert "received_at" in body

    async def test_upload_requires_auth(self, client):
        resp = await client.post("/healthkit", json=_sample_upload_body())
        assert resp.status_code == 401

    async def test_upload_with_extra_top_level_fields_is_accepted(self, client, auth_headers):
        # Outer envelope allows extra fields per ConfigDict(extra="allow").
        body = _sample_upload_body()
        body["client_version"] = "almond-ios/0.1.0"
        resp = await client.post("/healthkit", json=body, headers=auth_headers)
        assert resp.status_code == 200

    async def test_missing_window_field_returns_422(self, client, auth_headers):
        body = _sample_upload_body()
        del body["window_start"]
        resp = await client.post("/healthkit", json=body, headers=auth_headers)
        assert resp.status_code == 422


class TestRiskRead:
    async def test_get_risk_no_uploads_returns_404(self, client, auth_headers):
        resp = await client.get("/risk", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "no_predictions_yet"

    async def test_get_risk_for_pending_upload_returns_status_only(self, client, auth_headers):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]

        resp = await client.get(f"/risk?upload_id={upload_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert "scores" not in body
        assert body["upload_id"] == upload_id

    async def test_get_risk_with_unknown_upload_id_returns_404(self, client, auth_headers):
        unknown = uuid4().hex
        resp = await client.get(f"/risk?upload_id={unknown}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_no_information_leak_across_users(
        self, client, auth_headers, make_apple_token
    ):
        """User A's upload_id must 404 for User B, not 403/200."""
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]

        # Sign in as a different Apple user.
        other_token = make_apple_token(sub=f"apple-other-{uuid4().hex[:8]}")
        login = await client.post("/auth/login", json={"apple_identity_token": other_token})
        other_headers = {"Authorization": f"Bearer {login.json()['session_token']}"}

        resp = await client.get(f"/risk?upload_id={upload_id}", headers=other_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "upload_not_found"

    async def test_get_risk_requires_auth(self, client):
        resp = await client.get("/risk")
        assert resp.status_code == 401


class TestHistory:
    async def test_history_default_window_returns_empty_series_when_no_predictions(
        self, client, auth_headers
    ):
        resp = await client.get("/history?days=30", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == 30
        assert body["series"] == {}

    async def test_history_rejects_out_of_range_days(self, client, auth_headers):
        resp = await client.get("/history?days=5", headers=auth_headers)
        assert resp.status_code == 422

    async def test_history_requires_auth(self, client):
        resp = await client.get("/history")
        assert resp.status_code == 401
