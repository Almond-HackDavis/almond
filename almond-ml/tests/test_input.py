"""End-to-end tests for POST /input + GET /output (append-only history).

The `input` and `output` collections are append-only — every POST /input
inserts new docs with UUID hex `_id`s and never overwrites existing rows.
`GET /output` returns the most recent output (sorted by `computed_at desc`).
Each output row carries `input_id` linking back at the input that
produced it.
"""
from __future__ import annotations

import asyncio
import re

import pytest

pytestmark = pytest.mark.asyncio

UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


class TestPostInput:
    async def test_returns_full_output_document(self, client, valid_input_payload):
        resp = await client.post("/input", json=valid_input_payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Every POST yields a fresh UUID hex `_id`, never the legacy "current".
        assert UUID_HEX_RE.match(body["_id"]), f"unexpected id shape: {body['_id']!r}"
        assert UUID_HEX_RE.match(body["input_id"]), "output should reference its input"
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
        assert meta["model_id"] == "almond-cox-2yr-v0.3.0"
        assert meta["llm_model"] == "gemma-4-31b-it"
        assert meta["horizon_months"] == 24
        assert meta["prompt_template_version"]

    async def test_get_output_returns_latest_post(self, client, valid_input_payload):
        first = await client.post("/input", json=valid_input_payload)
        assert first.status_code == 200

        get_after = await client.get("/output")
        assert get_after.status_code == 200
        get_body = get_after.json()
        # GET /output returns the SAME row that the POST just wrote.
        assert get_body["_id"] == first.json()["_id"]
        assert (
            get_body["scores"]["vitality_score"]["value"]
            == first.json()["scores"]["vitality_score"]["value"]
        )

    async def test_second_input_does_not_overwrite_first(self, client, valid_input_payload):
        first = await client.post("/input", json=valid_input_payload)
        assert first.status_code == 200

        # Force monotonic `computed_at` across the burst — see comment below.
        await asyncio.sleep(0.005)

        # Second submission with a younger user → expect different scores.
        second_payload = {**valid_input_payload}
        second_payload["onboarding"] = {**valid_input_payload["onboarding"], "age": 22}
        second = await client.post("/input", json=second_payload)
        assert second.status_code == 200

        # Distinct UUIDs — append-only, never overwrites.
        assert first.json()["_id"] != second.json()["_id"]
        assert first.json()["input_id"] != second.json()["input_id"]

        # /output reads the latest by computed_at desc.
        latest = await client.get("/output")
        assert latest.status_code == 200
        latest_body = latest.json()
        assert latest_body["_id"] == second.json()["_id"]
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

    async def test_append_only_three_posts_three_rows(self, client, valid_input_payload):
        """Append-only invariant: 3 POSTs → 3 input rows AND 3 output rows,
        each with a distinct UUID id and `output.input_id` pointing at the
        matching input row."""
        from db import InputRecord, OutputRecord

        for _ in range(3):
            resp = await client.post("/input", json=valid_input_payload)
            assert resp.status_code == 200

        all_inputs = await InputRecord.find_all().to_list()
        all_outputs = await OutputRecord.find_all().to_list()

        assert len(all_inputs) == 3
        assert len(all_outputs) == 3

        # All ids are distinct UUID hex strings, never "current".
        input_ids = {rec.id for rec in all_inputs}
        output_ids = {rec.id for rec in all_outputs}
        assert "current" not in input_ids and "current" not in output_ids
        assert all(UUID_HEX_RE.match(i) for i in input_ids)
        assert all(UUID_HEX_RE.match(i) for i in output_ids)
        assert len(input_ids) == 3 and len(output_ids) == 3

        # FK linkage — every output.input_id must refer to an existing input row.
        for rec in all_outputs:
            assert rec.input_id in input_ids


class TestGetOutput:
    async def test_404_when_no_output_yet(self, client):
        resp = await client.get("/output")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "no_output_yet"

    async def test_200_after_post_input(self, client, valid_input_payload):
        post = await client.post("/input", json=valid_input_payload)
        resp = await client.get("/output")
        assert resp.status_code == 200
        # GET /output returns the same UUID `_id` as the POST that produced it.
        assert resp.json()["_id"] == post.json()["_id"]


class TestHealthz:
    async def test_healthz_returns_ok(self, client):
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
