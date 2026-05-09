# almond-ml — backend service

FastAPI + MongoDB JSON-in/JSON-out service for the almond iOS app.

> **Heads up — ML and Gemini are NOT in this repo.** They run as a separate
> offline worker process that polls the `/uploads/*` endpoints below. This
> service handles auth, persistence, and serving JSON to iOS. Nothing more.

## Endpoints

iOS-facing (require a session JWT in `Authorization: Bearer <token>`):

| Method | Path                          | Purpose                                                        |
| ------ | ----------------------------- | -------------------------------------------------------------- |
| POST   | `/auth/login`                 | Exchange an Apple identity token for a session JWT             |
| POST   | `/onboarding`                 | One-shot demographic + clinical questionnaire                  |
| POST   | `/healthkit`                  | Upload raw HealthKit payload (returns `status="pending"`)      |
| GET    | `/risk[?upload_id=...]`       | Latest done prediction, or the prediction for a given upload   |
| GET    | `/history?days=N`             | 7–365 day window of prediction trends                          |

Worker-facing (require `WORKER_API_KEY` in `Authorization: Bearer ...`):

| Method | Path                                | Purpose                                                                |
| ------ | ----------------------------------- | ---------------------------------------------------------------------- |
| GET    | `/uploads?status=pending&limit=10`  | List pending uploads, oldest first                                     |
| GET    | `/uploads/{id}`                     | Full payload + embedded onboarding; atomically claims the upload       |
| POST   | `/uploads/{id}/result`              | Persist scores + drivers + Gemini recommendation; flip upload to done  |
| POST   | `/uploads/{id}/fail`                | Mark the upload as failed with an error reason                         |

Plus `GET /healthz` for liveness probes (does not touch Mongo).

The full request/response shapes live in `schemas.py` — that's the source of
truth, with a couple of overrides over `AGENTS.md` documented in the file's
docstring.

## Local development

```bash
cd almond-ml

# 1. Create a Python 3.12+ virtualenv and install everything.
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Copy the env template and fill in the blanks.
cp .env.example .env
# Generate signing keys:
python -c "import secrets; print('JWT_SIGNING_KEY=' + secrets.token_urlsafe(64))"
python -c "import secrets; print('WORKER_API_KEY=' + secrets.token_urlsafe(48))"
# Set MONGODB_URI to either an Atlas SRV string or `mongodb://localhost:27017`.

# 3. Start the dev server.
uvicorn main:app --reload
```

OpenAPI docs auto-publish at <http://localhost:8000/docs>.

## Tests

```bash
pytest tests/ -q
```

The test suite uses `mongomock-motor` for an in-memory Mongo and a
self-signed RSA keypair to fake Apple's JWKS. No network calls; no Atlas
connection required.

## What lives where

```
almond-ml/
├── main.py              # FastAPI app + lifespan + router wiring
├── schemas.py           # Pydantic v2 — JSON shapes (source of truth)
├── db.py                # Beanie Documents + AsyncMongoClient lifespan
├── auth.py              # Apple JWKS verify + HS256 session JWT
├── routes/              # one router per business domain
├── tests/               # pytest, async, mongomock-motor
├── pyproject.toml
└── .env.example
```

## Things this PR deliberately does not include

- `ml.py`, `gemini.py`, `risk_equations.py` — handled by the offline worker.
- Training notebooks under `training/` — separate PR.
- iOS code under `almond-app/` — different ownership.

## Env vars

See `.env.example`. Five required, one placeholder:

| Var                | Required | What it's for                                          |
| ------------------ | -------- | ------------------------------------------------------ |
| `JWT_SIGNING_KEY`  | yes      | HS256 signing key for the session JWT (32+ chars)      |
| `APPLE_BUNDLE_ID`  | yes      | Audience claim Apple identity tokens must match        |
| `MONGODB_URI`      | yes      | Mongo connection string (Atlas SRV or local)           |
| `MONGODB_DB`       | yes      | Database name (default `almond`)                       |
| `WORKER_API_KEY`   | yes      | Shared bearer token for the offline worker process     |
| `GEMINI_API_KEY`   | no       | Placeholder — NOT read by this PR (worker uses it)     |
