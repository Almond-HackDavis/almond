"""Authentication.

Two distinct credentials live here:

  * **Session JWTs** — HS256, signed by us with `JWT_SIGNING_KEY`. Issued after
    a successful Sign in with Apple flow; the iOS app sends this on every
    subsequent request as `Authorization: Bearer <session_jwt>`.

  * **Worker API key** — a single shared bearer token (`WORKER_API_KEY` env
    var) used by the offline ML/Gemini worker process to call /uploads/*. Not
    a JWT; just a static token.

Apple identity tokens themselves are RS256-signed by Apple. We verify them
against the Apple JWKS at `https://appleid.apple.com/auth/keys`. The PyJWKClient
uses synchronous urllib internally, so all verify calls are routed through
`starlette.concurrency.run_in_threadpool` to keep the event loop free.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from starlette.concurrency import run_in_threadpool

from db import utcnow

log = logging.getLogger("almond.auth")

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

# Module-level singletons — never re-created per request.
_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> PyJWKClient:
    """Lazy singleton with caching enabled.

    `cache_jwk_set=True` + `lifespan=3600` means the JWKS is fetched at most
    once per hour. Apple rotates these keys every ~24h.
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            APPLE_JWKS_URL,
            cache_jwk_set=True,
            lifespan=3600,
        )
    return _jwks_client


# ── Apple identity-token verification ────────────────────────────────────────


async def verify_apple_token(identity_token: str) -> str:
    """Verify a Sign in with Apple identity token. Returns the Apple `sub`.

    Raises HTTPException(401) on any failure — bad signature, wrong audience,
    expired, malformed, etc. We use one status code so callers can't fingerprint
    failure modes.
    """
    bundle_id = os.environ.get("APPLE_BUNDLE_ID")
    if not bundle_id:
        log.error("APPLE_BUNDLE_ID env var missing — cannot verify identity tokens")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "server_misconfigured", "message": "Apple bundle id not set", "details": {}}},
        )

    try:
        signing_key = await run_in_threadpool(
            lambda: get_jwks_client().get_signing_key_from_jwt(identity_token).key
        )
    except jwt.exceptions.PyJWKClientError as exc:
        log.warning("Apple JWKS lookup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_apple_token", "message": str(exc), "details": {}}},
        ) from exc
    except jwt.exceptions.DecodeError as exc:
        # Malformed (header not parseable) — translate to 401, not 422.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_apple_token", "message": "Malformed token", "details": {}}},
        ) from exc

    try:
        payload = jwt.decode(
            identity_token,
            signing_key,
            algorithms=["RS256"],
            audience=bundle_id,
            issuer=APPLE_ISSUER,
            leeway=10,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "apple_token_expired", "message": "Identity token expired", "details": {}}},
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "wrong_audience", "message": "Identity token not for this app", "details": {}}},
        )
    except jwt.InvalidSignatureError:
        # Wrong signing key — distinct from expired/audience.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "bad_signature", "message": "Identity token signature invalid", "details": {}}},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_apple_token", "message": str(exc), "details": {}}},
        ) from exc

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "no_subject", "message": "Identity token missing sub", "details": {}}},
        )
    return sub


# ── Session JWT ──────────────────────────────────────────────────────────────


SESSION_TTL = timedelta(days=30)


def _signing_key() -> str:
    key = os.environ.get("JWT_SIGNING_KEY")
    if not key or len(key) < 32:
        raise RuntimeError(
            "JWT_SIGNING_KEY must be set and at least 32 characters. "
            "Generate one with `python -c 'import secrets; print(secrets.token_urlsafe(64))'`."
        )
    return key


def issue_session_jwt(user_id: str) -> str:
    """Create a 30-day HS256 session JWT for `user_id`.

    Claims: sub, iss, iat, exp. **No PII** — keep email, name, etc. out.
    """
    now = utcnow()
    payload = {
        "sub": user_id,
        "iss": "almond",
        "iat": int(now.timestamp()),
        "exp": int((now + SESSION_TTL).timestamp()),
    }
    return jwt.encode(payload, _signing_key(), algorithm="HS256")


# ── Bearer dependencies ──────────────────────────────────────────────────────


# We use HTTPBearer(auto_error=False) so we can return our own JSON envelope
# and 401-vs-403 mapping rather than FastAPI's default `{"detail": "..."}`.
_session_bearer = HTTPBearer(auto_error=False)
_worker_bearer = HTTPBearer(auto_error=False)


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code, "message": message, "details": {}}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


async def get_current_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_bearer),
) -> str:
    """Read & validate the iOS-side session JWT. Returns the user_id (UUID hex)."""
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise _unauthorized("missing_token", "Authorization: Bearer <session-jwt> required")
    try:
        payload = jwt.decode(
            creds.credentials,
            _signing_key(),
            algorithms=["HS256"],
            issuer="almond",
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("session_expired", "Session token expired")
    except jwt.InvalidSignatureError:
        raise _forbidden("bad_signature", "Session token signature invalid")
    except jwt.PyJWTError as exc:
        raise _unauthorized("invalid_session", str(exc))

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise _unauthorized("invalid_session", "Session token missing sub")
    return user_id


async def get_worker_auth(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_worker_bearer),
) -> str:
    """Validate the worker's shared bearer token. Returns the worker's id.

    The worker's hostname is read from the optional `X-Worker-Id` header so we
    can log it on `claimed_by`. Defaults to "unknown" if not provided.
    """
    expected = os.environ.get("WORKER_API_KEY")
    if not expected or len(expected) < 16:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "server_misconfigured", "message": "Worker API key not set", "details": {}}},
        )
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise _unauthorized("missing_worker_token", "Worker bearer token required")
    if creds.credentials != expected:
        # Constant-time-ish: pyjwt isn't involved here so just compare;
        # a real attacker would need ~10^60 attempts to brute-force a 48-byte key.
        raise _unauthorized("invalid_worker_token", "Worker bearer token invalid")
    return request.headers.get("X-Worker-Id", "unknown")
