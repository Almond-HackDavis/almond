"""Worker-facing endpoints: list, claim, result, fail."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio


def _sample_upload_body() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "uploaded_at": now.isoformat(),
        "window_start": (now - timedelta(days=90)).isoformat(),
        "window_end": now.isoformat(),
        "samples": {"steps_daily": [{"date": "2026-04-18", "count": 8243}]},
    }


def _sample_onboarding_body() -> dict:
    return {
        "age": 32,
        "sex": "M",
        "height_cm": 178.0,
        "weight_kg": 75.5,
        "smoking": False,
        "diabetes": False,
        "family_history_cvd": False,
    }


def _sample_result_body() -> dict:
    return {
        "scores": {
            "ascvd_10yr": {"value": 5.1, "category": "low"},
            "framingham_10yr_cvd": {"value": 6.4, "category": "low"},
            "findrisc_10yr_diabetes": {"value": 12, "max": 26, "category": "elevated"},
            "life_essential_8": {"value": 71, "max": 100, "category": "moderate"},
            "fitness_age": {"value": 41, "chronological_age": 32, "delta": 9},
            "nhanes_mortality_2yr": {"value": 0.6, "ci_low": 0.3, "ci_high": 1.1},
        },
        "top_drivers": [
            {
                "feature": "mean_daily_mims",
                "value": 1850000,
                "population_norm": 2540000,
                "direction": "worse",
                "weight": 0.31,
                "human_label": "Daily activity volume",
                "source": "cox",
            }
        ],
        "gemini_recommendation": {
            "summary": "Activity volume is the biggest driver.",
            "actions": [
                {
                    "finding": "Below-average daily activity.",
                    "action": "Add 20 minutes of brisk walking on weekdays.",
                    "rationale": "Low MIMS is independently associated with mortality.",
                }
            ],
            "disclaimer": "These suggestions don't replace a physician's review.",
        },
        "model_metadata": {
            "model_id": "cox_v0.1.0",
            "prompt_template_version": "1.0.0",
            "computed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


class TestWorkerAuth:
    async def test_missing_worker_token_returns_401(self, client):
        resp = await client.get("/uploads")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "missing_worker_token"

    async def test_wrong_worker_token_returns_401(self, client):
        resp = await client.get(
            "/uploads", headers={"Authorization": "Bearer not-the-right-key"}
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_worker_token"

    async def test_session_jwt_does_not_authorize_worker_routes(self, client, auth_headers):
        # An iOS session JWT must NOT pass the worker dependency.
        resp = await client.get("/uploads", headers=auth_headers)
        assert resp.status_code == 401


class TestWorkerListUploads:
    async def test_list_pending_returns_what_was_uploaded(
        self, client, auth_headers, worker_headers
    ):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]

        resp = await client.get("/uploads?status=pending&limit=10", headers=worker_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = [u["upload_id"] for u in body["uploads"]]
        assert upload_id in ids

    async def test_list_default_status_is_pending(self, client, worker_headers):
        resp = await client.get("/uploads", headers=worker_headers)
        assert resp.status_code == 200

    async def test_list_invalid_limit_returns_422(self, client, worker_headers):
        resp = await client.get("/uploads?limit=999", headers=worker_headers)
        assert resp.status_code == 422


class TestWorkerClaimUpload:
    async def test_get_upload_returns_full_payload_and_flips_to_scoring(
        self, client, auth_headers, worker_headers
    ):
        # Set up onboarding so it gets embedded.
        await client.post("/onboarding", json=_sample_onboarding_body(), headers=auth_headers)
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]

        resp = await client.get(f"/uploads/{upload_id}", headers=worker_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["upload_id"] == upload_id
        assert body["payload"]["steps_daily"][0]["count"] == 8243
        assert body["onboarding"] is not None
        assert body["onboarding"]["age"] == 32
        assert body["status"] == "scoring"

        # Subsequent list call should NOT include this upload as pending anymore.
        listing = await client.get("/uploads?status=pending", headers=worker_headers)
        ids = [u["upload_id"] for u in listing.json()["uploads"]]
        assert upload_id not in ids

    async def test_get_unknown_upload_returns_404(self, client, worker_headers):
        from uuid import uuid4
        resp = await client.get(f"/uploads/{uuid4().hex}", headers=worker_headers)
        assert resp.status_code == 404

    async def test_onboarding_is_null_when_user_has_none(
        self, client, auth_headers, worker_headers
    ):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]

        resp = await client.get(f"/uploads/{upload_id}", headers=worker_headers)
        assert resp.status_code == 200
        assert resp.json()["onboarding"] is None


class TestWorkerSubmitResult:
    async def test_submit_result_persists_prediction_and_flips_upload_to_done(
        self, client, auth_headers, worker_headers
    ):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]
        # Worker claims it.
        await client.get(f"/uploads/{upload_id}", headers=worker_headers)

        result_resp = await client.post(
            f"/uploads/{upload_id}/result", json=_sample_result_body(), headers=worker_headers
        )
        assert result_resp.status_code == 200, result_resp.text
        assert "prediction_id" in result_resp.json()

        # iOS-side fetch with the user's session JWT should now return the full prediction.
        risk_resp = await client.get(f"/risk?upload_id={upload_id}", headers=auth_headers)
        assert risk_resp.status_code == 200, risk_resp.text
        body = risk_resp.json()
        assert body["status"] == "done"
        assert "scores" in body
        assert body["scores"]["nhanes_mortality_2yr"]["value"] == 0.6
        assert body["top_drivers"][0]["feature"] == "mean_daily_mims"

    async def test_submit_result_twice_returns_409(
        self, client, auth_headers, worker_headers
    ):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]
        await client.get(f"/uploads/{upload_id}", headers=worker_headers)

        first = await client.post(
            f"/uploads/{upload_id}/result", json=_sample_result_body(), headers=worker_headers
        )
        assert first.status_code == 200

        second = await client.post(
            f"/uploads/{upload_id}/result", json=_sample_result_body(), headers=worker_headers
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "prediction_already_exists"

    async def test_submit_result_for_unknown_upload_returns_404(self, client, worker_headers):
        from uuid import uuid4
        resp = await client.post(
            f"/uploads/{uuid4().hex}/result", json=_sample_result_body(), headers=worker_headers
        )
        assert resp.status_code == 404

    async def test_submit_result_without_gemini_is_accepted(
        self, client, auth_headers, worker_headers
    ):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]
        await client.get(f"/uploads/{upload_id}", headers=worker_headers)

        body = _sample_result_body()
        body["gemini_recommendation"] = None  # worker may submit if Gemini failed
        resp = await client.post(f"/uploads/{upload_id}/result", json=body, headers=worker_headers)
        assert resp.status_code == 200


class TestWorkerSubmitFail:
    async def test_submit_fail_marks_upload_failed(
        self, client, auth_headers, worker_headers
    ):
        upload = await client.post("/healthkit", json=_sample_upload_body(), headers=auth_headers)
        upload_id = upload.json()["upload_id"]
        await client.get(f"/uploads/{upload_id}", headers=worker_headers)

        resp = await client.post(
            f"/uploads/{upload_id}/fail",
            json={"error": "Cox model exploded", "stage": "scoring"},
            headers=worker_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

        # iOS view of the upload reports failed status.
        risk_resp = await client.get(f"/risk?upload_id={upload_id}", headers=auth_headers)
        assert risk_resp.status_code == 200
        assert risk_resp.json()["status"] == "failed"

    async def test_submit_fail_validates_stage(self, client, worker_headers):
        from uuid import uuid4
        resp = await client.post(
            f"/uploads/{uuid4().hex}/fail",
            json={"error": "boom", "stage": "not-a-real-stage"},
            headers=worker_headers,
        )
        assert resp.status_code == 422
