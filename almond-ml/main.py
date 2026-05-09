"""FastAPI app entry — thin, just lifespan + router wiring.

Run locally:

    cd almond-ml
    uvicorn main:app --reload

Tests build their own app instance via `create_app()` and override the lifespan
to point at a mongomock-backed AsyncMongoClient.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from db import close_db, init_db
from routes import auth_routes, healthkit_routes, onboarding_routes, worker_routes

log = logging.getLogger("almond")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open Mongo at startup, close at shutdown."""
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "almond")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Copy .env.example to .env and fill it in."
        )
    await init_db(uri, db_name)
    try:
        yield
    finally:
        await close_db()


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    """Build the FastAPI app. Tests pass `with_lifespan=False`."""
    kwargs = {"lifespan": lifespan} if with_lifespan else {}
    app = FastAPI(
        title="almond backend",
        version="0.1.0",
        description=(
            "JSON in / JSON out service for the almond iOS app. ML inference "
            "and Gemini recommendations are handled by a separate offline "
            "worker process out of scope for this repo."
        ),
        **kwargs,  # type: ignore[arg-type]
    )

    app.include_router(auth_routes.router)
    app.include_router(onboarding_routes.router)
    app.include_router(healthkit_routes.router)
    app.include_router(worker_routes.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, bool]:
        """Liveness probe — does NOT touch Mongo, intentionally."""
        return {"ok": True}

    # Uniform error envelope. AGENTS.md → ## Error responses.
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail), "details": {}}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request body failed schema validation",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    return app


app = create_app()
