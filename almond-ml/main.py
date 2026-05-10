"""FastAPI app entry — single sync-pipeline backend.

POST /input  → Cox + Gemma pipeline → write outputs → return result
GET  /output → read the latest "current" output document
GET  /healthz → liveness probe (does NOT touch Mongo or load the Cox model)

Run locally:

    cd almond-ml
    uvicorn main:app --reload

The trained Cox + percentile lookup load lazily on first prediction (see
`ml.load_artifacts`). The Mongo connection opens at startup via the lifespan
handler.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

# Auto-load .env so `uvicorn main:app` works without `source .env` first.
# Best-effort — if python-dotenv isn't installed (e.g. minimal prod image)
# we silently fall back to whatever's already in os.environ.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import ml
from db import close_db, init_db
from routes import input_routes

log = logging.getLogger("almond")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open Mongo + warm the Cox model at startup, close on shutdown."""
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "almond")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Copy .env.example to .env and fill it in."
        )
    await init_db(uri, db_name)
    # Eagerly load the Cox pkl so the first request doesn't pay for cold start.
    ml.load_artifacts()
    try:
        yield
    finally:
        await close_db()


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    """Build the FastAPI app. Tests pass `with_lifespan=False`."""
    kwargs = {"lifespan": lifespan} if with_lifespan else {}
    app = FastAPI(
        title="almond ml service",
        version="0.2.0",
        description=(
            "Sync Cox + Gemma pipeline. POST /input runs ML inference and a "
            "Gemma-generated summary, persists to MongoDB, and returns the "
            "result document."
        ),
        **kwargs,  # type: ignore[arg-type]
    )

    app.include_router(input_routes.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, bool]:
        """Liveness probe — does NOT touch Mongo or the Cox model."""
        return {"ok": True}

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


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
