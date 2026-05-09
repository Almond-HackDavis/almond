"""Auth: Apple identity-token verification, session JWT issuance, dependencies."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


pytestmark = pytest.mark.asyncio


class TestAppleLogin:
    async def test_valid_token_creates_user_and_returns_session_jwt(self, client, make_apple_token):
        token = make_apple_token(sub="apple-stable-sub-123")
        resp = await client.post("/auth/login", json={"apple_identity_token": token})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_new_user"] is True
        assert body["needs_onboarding"] is True
        assert body["user_id"]
        assert body["session_token"]

    async def test_repeat_login_returns_existing_user(self, client, make_apple_token):
        token = make_apple_token(sub="apple-stable-sub-456")
        first = await client.post("/auth/login", json={"apple_identity_token": token})
        assert first.status_code == 200
        first_body = first.json()

        # Second login with the same Apple sub.
        token2 = make_apple_token(sub="apple-stable-sub-456")
        second = await client.post("/auth/login", json={"apple_identity_token": token2})
        assert second.status_code == 200
        second_body = second.json()

        assert second_body["user_id"] == first_body["user_id"]
        assert second_body["is_new_user"] is False

    async def test_wrong_audience_returns_401(self, client, make_apple_token):
        token = make_apple_token(sub="apple-sub", audience="com.someone-else.app")
        resp = await client.post("/auth/login", json={"apple_identity_token": token})

        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "wrong_audience"

    async def test_expired_token_returns_401(self, client, make_apple_token):
        token = make_apple_token(sub="apple-sub", ttl_seconds=-3600)  # expired 1h ago
        resp = await client.post("/auth/login", json={"apple_identity_token": token})

        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "apple_token_expired"

    async def test_wrong_signing_key_returns_403(self, client, make_apple_token):
        # Sign with a *different* RSA key — JWKS will yield ours, signature won't match.
        rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rogue_pem = rogue_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = make_apple_token(sub="apple-sub", signing_key=rogue_pem)

        resp = await client.post("/auth/login", json={"apple_identity_token": token})

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "bad_signature"

    async def test_malformed_token_returns_401(self, client):
        resp = await client.post(
            "/auth/login", json={"apple_identity_token": "not-a-real-jwt-just-some-string"}
        )
        # Pydantic min_length passes (>20 chars), but JWT parsing fails downstream.
        assert resp.status_code == 401, resp.text


class TestSessionJWTDependency:
    """Coverage for `auth.get_current_user_id` via a protected endpoint."""

    PROTECTED_PATH = "/onboarding"
    MINIMAL_PAYLOAD = {
        "age": 30,
        "sex": "M",
        "height_cm": 178,
        "weight_kg": 75.5,
        "smoking": False,
        "diabetes": False,
        "family_history_cvd": False,
    }

    async def test_missing_authorization_header_returns_401(self, client):
        resp = await client.post(self.PROTECTED_PATH, json=self.MINIMAL_PAYLOAD)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "missing_token"

    async def test_valid_session_jwt_passes(self, client, auth_headers):
        resp = await client.post(self.PROTECTED_PATH, json=self.MINIMAL_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200, resp.text

    async def test_expired_session_jwt_returns_401(self, client):
        # Mint an expired session JWT manually with the right signing key.
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "fake-user-id",
            "iss": "almond",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, os.environ["JWT_SIGNING_KEY"], algorithm="HS256")
        resp = await client.post(
            self.PROTECTED_PATH,
            json=self.MINIMAL_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "session_expired"

    async def test_session_jwt_signed_with_wrong_key_returns_403(self, client):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "fake-user-id",
            "iss": "almond",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, "definitely-not-the-real-signing-key" * 2, algorithm="HS256")
        resp = await client.post(
            self.PROTECTED_PATH,
            json=self.MINIMAL_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "bad_signature"

    async def test_non_bearer_scheme_returns_401(self, client):
        resp = await client.post(
            self.PROTECTED_PATH,
            json=self.MINIMAL_PAYLOAD,
            headers={"Authorization": "Basic abc:def"},
        )
        assert resp.status_code == 401
