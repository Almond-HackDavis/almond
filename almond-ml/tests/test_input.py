"""End-to-end tests for POST /input + GET /output."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestPostInput:
    async def test_returns_full_output_document(self, client, valid_input_payload):
        resp = await client.post("/input", json=valid_input_payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["_id"] == "current"
        assert "computed_at" in body and "input_uploaded_at" in body
        assert "scores" in body
        assert "vitality_score" in body["scores"]
        assert "nhanes_mortality_2yr" in body["scores"]

        v = body["scores"]["vitality_score"]
        assert 0.0 <= v["value"] <= 100.0
        assert v["max"] == 100.0

        risk = body["scores"]["nhanes_mortality_2yr"]
        assert 0.0 <= risk["value"] <= 1.0
        assert risk.get("ci_low") is None
        assert risk.get("ci_high") is None

        assert body["gemma_summary"].startswith("Stubbed summary")
        assert "Almond is a wellness tool" in body["disclaimer"]

        meta = body["model_metadata"]
        assert meta["model_id"] == "almond-cox-2yr-v0.1.0"
        assert meta["llm_model"] == "gemma-3-27b-it"
        assert meta["horizon_months"] == 24
        assert meta["prompt_template_version"]

    async def test_persists_singleton_current_doc(self, client, valid_input_payload):
        first = await client.post("/input", json=valid_input_payload)
        assert first.status_code == 200

        get_after = await client.get("/output")
        assert get_after.status_code == 200
        get_body = get_after.json()
        assert get_body["_id"] == "current"
        assert get_body["scores"]["vitality_score"]["value"] == first.json()["scores"]["vitality_score"]["value"]

    async def test_second_input_overwrites_current(self, client, valid_input_payload):
        first = await client.post("/input", json=valid_input_payload)
        assert first.status_code == 200

        # Second submission with a younger user → expect different scores.
        second_payload = {**valid_input_payload}
        second_payload["onboarding"] = {**valid_input_payload["onboarding"], "age": 22}
        second = await client.post("/input", json=second_payload)
        assert second.status_code == 200

        # /output reads the latest.
        latest = await client.get("/output")
        assert latest.status_code == 200
        latest_body = latest.json()

        # Younger user → lower mortality risk → likely higher vitality.
        assert (
            latest_body["scores"]["vitality_score"]["value"]
            >= first.json()["scores"]["vitality_score"]["value"] - 0.5
        )

    async def test_validation_error_for_bad_payload(self, client, valid_input_payload):
        bad = {**valid_input_payload}
        bad["onboarding"] = {**valid_input_payload["onboarding"], "age": 12}  # under 18
        resp = await client.post("/input", json=bad)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_missing_samples_top_level_returns_422(self, client, valid_input_payload):
        bad = {"onboarding": valid_input_payload["onboarding"]}
        resp = await client.post("/input", json=bad)
        assert resp.status_code == 422

    async def test_empty_samples_arrays_are_accepted(self, client, valid_input_payload):
        """A user with HK permissions denied → empty arrays. Should still produce a score."""
        empty_samples = {
            **valid_input_payload,
            "samples": {
                "steps_daily": [],
                "active_energy_daily_kcal": [],
                "exercise_minutes_daily": [],
                "sleep_sessions": [],
            },
        }
        resp = await client.post("/input", json=empty_samples)
        assert resp.status_code == 200
        body = resp.json()
        assert 0.0 <= body["scores"]["vitality_score"]["value"] <= 100.0

    async def test_history_copy_is_appended(self, client, valid_input_payload):
        from db import OutputRecord
        await client.post("/input", json=valid_input_payload)
        await client.post("/input", json=valid_input_payload)

        all_outputs = await OutputRecord.find_all().to_list()
        # Expect 2 history copies + 1 "current" singleton = 3 docs.
        ids = [d.id for d in all_outputs]
        assert "current" in ids
        non_current_ids = [i for i in ids if i != "current"]
        assert len(non_current_ids) == 2
        assert all(len(i) == 32 for i in non_current_ids), f"history ids should be UUID hex: {non_current_ids}"


class TestGetOutput:
    async def test_404_when_no_output_yet(self, client):
        resp = await client.get("/output")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "no_output_yet"

    async def test_200_after_post_input(self, client, valid_input_payload):
        await client.post("/input", json=valid_input_payload)
        resp = await client.get("/output")
        assert resp.status_code == 200
        assert resp.json()["_id"] == "current"


class TestHealthz:
    async def test_healthz_returns_ok(self, client):
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
