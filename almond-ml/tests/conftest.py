"""Shared pytest fixtures.

Three big jobs:

  1. **Mongo backend** — swap pymongo's AsyncMongoClient for mongomock-motor's
     async mock. Beanie accepts either; the test app initializes against the
     mock at module-startup.

  2. **Apple JWKS** — mint an in-memory RSA keypair, monkey-patch
     `auth.get_jwks_client` so PyJWKClient returns our public key, and expose
     a fixture that builds Apple-style identity tokens with arbitrary claims.

  3. **TestClient** — `httpx.AsyncClient` (FastAPI's TestClient via httpx) wired
     to the app instance so individual tests just call `client.post(...)`.

Order matters: env vars are set in `_env` before any module imports `auth.py`.
"""
from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
import jwt
import mongomock
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mongomock_motor import AsyncMongoMockClient

# Beanie 2.x passes `authorizedCollections=True, nameOnly=True` to
# `list_collection_names()` for performance. mongomock 4.x doesn't accept those
# kwargs and raises TypeError. Swallow unknown kwargs so the underlying
# pure-Python implementation runs.
_orig_list_collection_names = mongomock.Database.list_collection_names


def _patched_list_collection_names(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    kwargs.pop("authorizedCollections", None)
    kwargs.pop("nameOnly", None)
    return _orig_list_collection_names(self, *args, **kwargs)


mongomock.Database.list_collection_names = _patched_list_collection_names  # type: ignore[assignment]


# ── Env vars (set BEFORE importing app modules) ──────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _env() -> Iterator[None]:
    os.environ["JWT_SIGNING_KEY"] = secrets.token_urlsafe(64)
    os.environ["APPLE_BUNDLE_ID"] = "com.almond.app.tests"
    os.environ["WORKER_API_KEY"] = "test-worker-key-" + secrets.token_urlsafe(32)
    os.environ["MONGODB_URI"] = "mongodb://localhost:27017"
    os.environ["MONGODB_DB"] = "almond_test"
    yield


# ── RSA keypair for the fake Apple JWKS ──────────────────────────────────────


@pytest.fixture(scope="session")
def apple_rsa_keypair() -> dict[str, Any]:
    """Generate a 2048-bit RSA keypair once per session.

    Returns a dict with `private_pem`, `public_pem`, `kid`, and a kid+key tuple
    for direct use with PyJWT.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return {
        "private_key": private_key,
        "public_key": public_key,
        "private_pem": private_pem,
        "public_pem": public_pem,
        "kid": "test-apple-kid",
    }


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch, apple_rsa_keypair):
    """Replace `auth.get_jwks_client` with a fake that returns our test public key.

    PyJWKClient normally calls Apple's JWKS endpoint over the network. This
    monkey-patch makes `verify_apple_token` use the in-memory keypair instead.
    """
    import auth  # imported here so env vars are set first

    class _FakeSigningKey:
        def __init__(self, key):
            self.key = key

    class _FakeJWKSClient:
        def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
            # We don't even peek at the token's kid — there's only one key in tests.
            return _FakeSigningKey(apple_rsa_keypair["public_key"])

    monkeypatch.setattr(auth, "get_jwks_client", lambda: _FakeJWKSClient())
    # Also drop any cached singleton from a previous test:
    monkeypatch.setattr(auth, "_jwks_client", None)


# ── Apple-style identity-token minting ───────────────────────────────────────


@pytest.fixture
def make_apple_token(apple_rsa_keypair):
    """Factory that mints a fake Apple identity token. Override any claim via kwargs."""

    bundle_id = os.environ["APPLE_BUNDLE_ID"]

    def _make(
        sub: str | None = None,
        audience: str | None = None,
        issuer: str = "https://appleid.apple.com",
        ttl_seconds: int = 600,
        signing_key=None,
        kid: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "iss": issuer,
            "aud": audience if audience is not None else bundle_id,
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
            "iat": int(now.timestamp()),
            "sub": sub or f"apple-sub-{uuid4().hex[:12]}",
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(
            payload,
            signing_key or apple_rsa_keypair["private_pem"],
            algorithm="RS256",
            headers={"kid": kid or apple_rsa_keypair["kid"]},
        )

    return _make


# ── App instance + Beanie initialized against mongomock-motor ────────────────


@pytest_asyncio.fixture
async def app() -> AsyncIterator[Any]:
    """A fresh app + a fresh in-memory Mongo per test. No data leakage between tests."""
    from beanie import init_beanie

    from db import DOCUMENT_MODELS
    from main import create_app

    client = AsyncMongoMockClient()
    db = client["almond_test"]
    await init_beanie(database=db, document_models=DOCUMENT_MODELS)

    fastapi_app = create_app(with_lifespan=False)
    try:
        yield fastapi_app
    finally:
        # mongomock-motor clients have no `close()` to call.
        pass


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    """httpx async client wired to the in-memory app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ── Convenience: a logged-in user ────────────────────────────────────────────


@pytest_asyncio.fixture
async def authed_user(client, make_apple_token) -> dict[str, str]:
    """Signs in via /auth/login and returns {user_id, session_token, apple_sub}."""
    apple_sub = f"apple-sub-{uuid4().hex[:12]}"
    token = make_apple_token(sub=apple_sub)
    resp = await client.post("/auth/login", json={"apple_identity_token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {
        "user_id": body["user_id"],
        "session_token": body["session_token"],
        "apple_sub": apple_sub,
    }


@pytest.fixture
def auth_headers(authed_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {authed_user['session_token']}"}


@pytest.fixture
def worker_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['WORKER_API_KEY']}",
        "X-Worker-Id": "test-worker-1",
    }
