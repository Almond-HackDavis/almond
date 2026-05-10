"""Test fixtures.

Three responsibilities:

  1. Set env vars before any app module imports so MONGODB_URI / GEMMA_API_KEY
     are populated by the time main.py is loaded.

  2. Replace `pymongo.AsyncMongoClient` with `mongomock_motor.AsyncMongoMockClient`
     for the test lifespan so we don't need a real Mongo. Beanie 2.x accepts
     either client.

  3. Monkey-patch `gemma.summarize()` to return a deterministic string so tests
     don't require the `google-genai` package or a real API key.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import mongomock
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient


# ── Env-var setup ───────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _env() -> Iterator[None]:
    os.environ["MONGODB_URI"] = "mongodb://localhost:27017"
    os.environ["MONGODB_DB"] = "almond_test"
    os.environ["GEMMA_API_KEY"] = "test-key-not-real"
    yield


# Beanie 2.x calls list_collection_names with `authorizedCollections=True,
# nameOnly=True`; mongomock 4.x doesn't accept those kwargs. Drop them.
_orig = mongomock.Database.list_collection_names


def _patched(self, *args, **kwargs):
    kwargs.pop("authorizedCollections", None)
    kwargs.pop("nameOnly", None)
    return _orig(self, *args, **kwargs)


mongomock.Database.list_collection_names = _patched  # type: ignore[assignment]


# ── Stubbed Gemma ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_gemma(monkeypatch):
    import gemma

    def _stub(**kwargs) -> gemma.GemmaResult:
        # Echo a few input numbers so the test can assert on prompt content.
        vit = kwargs.get("vitality", 0.0)
        return gemma.GemmaResult(
            summary=f"Stubbed summary for vitality {vit:.1f}.",
            model="gemma-3-27b-it",
            prompt_template_version=gemma.PROMPT_TEMPLATE_VERSION,
        )

    monkeypatch.setattr(gemma, "summarize", _stub)


# ── App + Mongo + HTTP client ───────────────────────────────────────────────


@pytest_asyncio.fixture
async def app() -> AsyncIterator[Any]:
    """Fresh app + fresh in-memory Mongo per test. No data leaks between tests."""
    from beanie import init_beanie

    from db import DOCUMENT_MODELS
    from main import create_app

    client = AsyncMongoMockClient()
    db = client["almond_test"]
    await init_beanie(database=db, document_models=DOCUMENT_MODELS)

    fastapi_app = create_app(with_lifespan=False)
    yield fastapi_app


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ── Sample payloads ─────────────────────────────────────────────────────────


@pytest.fixture
def valid_input_payload() -> dict:
    """Matches the schema in the README."""
    return {
        "onboarding": {
            "age": 28,
            "sex": "M",
            "height_cm": 178.0,
            "weight_kg": 75.0,
            "smoking": False,
            "diabetes": False,
            "family_history_cvd": False,
            "on_bp_medication": False,
            "race_ethnicity": None,
            "systolic_bp": None,
            "total_cholesterol": None,
            "hdl_cholesterol": None,
        },
        "samples": {
            "steps_daily": [
                {"date": "2026-05-07", "count": 9100},
                {"date": "2026-05-08", "count": 8800},
            ],
            "active_energy_daily_kcal": [
                {"date": "2026-05-07", "kcal": 480},
                {"date": "2026-05-08", "kcal": 412},
            ],
            "exercise_minutes_daily": [
                {"date": "2026-05-07", "minutes": 35},
                {"date": "2026-05-08", "minutes": 32},
            ],
            "sleep_sessions": [
                {"start": "2026-05-06T23:00:00Z", "end": "2026-05-07T07:00:00Z", "duration_min": 480},
                {"start": "2026-05-07T23:00:00Z", "end": "2026-05-08T07:00:00Z", "duration_min": 480},
            ],
        },
    }
