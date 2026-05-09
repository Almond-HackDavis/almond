Single source of truth for engineers and AI coding agents building **almond** — the HackDavis 2026 long-term health-risk app. Specifies the exact tech stack, API JSON schemas, database tables, mono-repo layout (`almond-app/` and `almond-ml/`), and git workflow so multiple contributors don't step on each other. **Read "The Daddy Rule" below before opening a PR.**

## The Daddy Rule (READ FIRST — applies to every contributor, human or agent)

1. **Nobody pushes directly to `main`.** Ever. Not even hotfixes.
2. **All work happens on feature branches** named `feat/<short-desc>`, `fix/<short-desc>`, `chore/<short-desc>`, `deps/<short-desc>`, or `docs/<short-desc>`.
3. **All changes merge via Pull Request to `main`.** No exceptions.
4. **Only Deniz (the Godfather) merges PRs.** When your branch is ready, open a PR and explicitly tag **`@3arii`** in the PR description with the message: **`Ready for review and merge — please squash & merge.`** Do not click "merge" yourself.
5. **Do not self-approve, do not bypass branch protection, do not force-push to `main`.**
6. **If your PR has merge conflicts**: rebase your branch on the latest `main` *locally*, push the rebased branch with `--force-with-lease` (never plain `--force`), and re-tag `@3arii`. Do not resolve conflicts in the GitHub web UI.
7. **AI coding agents specifically**: your task ends when the PR is open and `@3arii` has been tagged. **Stop.** Do not attempt to merge, do not approve PRs, do not loop.

> The cost of waiting 10 minutes for Deniz to merge is much lower than the cost of a broken `main` during a hackathon. When in doubt, ask in the team chat before changing anything load-bearing — schemas, the Gemini prompt, the DB shape, the dependency list.

## Project

- **Name**: `almond`
- **GitHub remote**: `github.com/Almond-HackDavis/almond`
- **Local path**: this directory (the repo root)
- **Bundle ID (iOS)**: `com.almond.app`
- **Tagline**: wearable-driven long-term health-risk app — ML on NHANES + Apple Watch HealthKit data, with Gemini-personalized recommendations

## What we're building

A passive long-term health-risk app. The user wears their Apple Watch normally, fills out a 30-second onboarding form once, and the app continuously computes long-term risk scores (10-year cardiovascular event risk, 10-year diabetes risk, fitness age, AHA Life's Essential 8, NHANES-trained mortality risk) using the Watch's HealthKit data. A trained ML model plus published clinical risk equations produce the scores; Gemini turns the score breakdown into specific, personalized lifestyle recommendations.

## Architecture (two components, no more)

1. **iPhone app** (`almond-app/`, Swift / SwiftUI) — Sign in with Apple, onboarding form, HealthKit reader, risk-score display, recommendation display, trend charts.
2. **Python service** (`almond-ml/`, FastAPI + ML + Gemini) — receives HealthKit data, runs ML model + clinical risk equations, calls Gemini, persists to SQLite. Owns training notebooks too (offline → produces the model artifact).
3. **No watchOS app.** The Apple Watch passively fills HealthKit; we don't write any Swift on the watch side. (A complication is a post-MVP stretch goal, not in this build.)

There is **no separate web dashboard** in this build — everything is in the iPhone app.

## Locked tech stack — do not substitute without an approved PR

| Layer | Tech | Notes |
|---|---|---|
| iOS app | Swift 5.9+, SwiftUI, HealthKit, Sign in with Apple | iOS 17+ minimum, watchOS 10+ minimum (no watch app code, but data must reach iPhone) |
| Backend framework | FastAPI (Python 3.11+) | Single `main.py` entry point inside `almond-ml/` |
| Backend deps | `fastapi`, `uvicorn[standard]`, `pydantic`, `beanie`, `motor`, `pyjwt[crypto]`, `google-generativeai`, `numpy`, `pandas`, `scikit-survival`, `scipy`, `python-multipart` | Pinned in `almond-ml/pyproject.toml` |
| Database | MongoDB (Atlas free tier `M0`, or local `mongod` for dev) | Single database `almond`. No Postgres. No Redis. No external KV. |
| ML model | scikit-survival `CoxPHSurvivalAnalysis` trained on NHANES + accelerometer + linked NDI mortality | Saved as `almond-ml/models/cox_model.pkl` + `almond-ml/models/feature_means.json` for imputation defaults |
| ML training | Python notebooks in `almond-ml/training/` (offline) | Output is the `.pkl` artifact + the JSON; reproducible with a fixed seed |
| LLM | `gemini-2.5-flash` via `google-generativeai` SDK | Pin model name in code; use `response_mime_type="application/json"` |
| Hosting | Railway (free tier) | Fly.io as fallback. **Do not introduce AWS / GCP / Azure.** |
| Auth | Sign in with Apple → backend issues a JWT session token (HS256 signed with `JWT_SIGNING_KEY`) | No email/password, no Google OAuth, no Firebase Auth |

**Adding any dependency requires its own PR** with the prefix `deps:` and the Godfather's approval.

## Mono-repo layout

```
almond/
├── almond-app/                 # iOS Engineer's territory — every Swift file lives here
│   ├── Almond.xcodeproj
│   ├── Almond/
│   │   ├── AlmondApp.swift
│   │   ├── Auth/               # Sign in with Apple flow
│   │   ├── Onboarding/         # the 30-second form
│   │   ├── HealthKit/          # HK reads + upload scheduling
│   │   ├── Dashboard/          # scores, drivers, recommendation, charts
│   │   └── Networking/         # API client — MUST mirror almond-ml/schemas.py 1:1
│   └── ...
├── almond-ml/                  # Godfather's territory — every Python file lives here
│   ├── main.py                 # FastAPI app + route handlers (thin)
│   ├── schemas.py              # Pydantic models — SOURCE OF TRUTH for API JSON
│   ├── db.py                   # Beanie Document models + Motor client init
│   ├── auth.py                 # Sign in with Apple verification + JWT issuance
│   ├── ml.py                   # Cox model load + feature engineering + augmentation
│   ├── risk_equations.py       # ASCVD, Framingham, FINDRISC, LE8 (pure functions, no IO)
│   ├── gemini.py               # Gemini prompt template + call + retry
│   ├── models/                 # Pickled ML artifacts (committed; <10 MB total)
│   ├── training/               # NHANES training notebooks (offline)
│   │   ├── 01_download_nhanes.ipynb
│   │   ├── 02_features.ipynb
│   │   └── 03_train_cox.ipynb
│   ├── tests/                  # pytest smoke tests
│   ├── pyproject.toml
│   └── .env.example
├── AGENTS.md                   # copy of this spec, lives at repo root
├── README.md
└── .gitignore
```

**There are exactly two top-level code folders: `almond-app/` and `almond-ml/`.** No `shared/`, no `common/`, no `backend/` — Python lives in one place, Swift lives in the other. The schema source of truth is `almond-ml/schemas.py`; iOS mirrors those Pydantic models in its `Networking/` layer.

## End-to-end workflow

1. **First launch** — user taps "Sign in with Apple." iOS receives an Apple identity token, sends `POST /auth/login`. Backend verifies the token against Apple's JWKS, creates a `users` row if new, returns a session JWT.
2. **Onboarding form** (only for new users — backend signals via `needs_onboarding: true`) — user fills the 30-second form. iOS sends `POST /onboarding`. Backend stores baseline.
3. **Background sync** — every time the app opens AND on a 4-hour `BGAppRefreshTask`, iOS pulls the last 90 days of HealthKit data and sends `POST /healthkit`.
4. **Backend processing** (synchronous within the request, ~2–4 seconds expected):
   1. Validate the payload against `schemas.HealthKitUpload`
   2. Persist raw payload to the `healthkit_uploads` collection
   3. Compute features (averages, trends, sleep regularity, fragmentation) — `ml.engineer_features()`
   4. Run NHANES Cox model → 10-year mortality / CVD hazard — `ml.predict_cox()`
   5. Apply augmentation rules for HR / HRV / VO2 max — `ml.apply_augmentation()`
   6. Compute clinical equations (ASCVD, Framingham, FINDRISC, LE8) — `risk_equations.compute_all()`
   7. Identify top 3 risk drivers — `ml.top_drivers()`
   8. Call Gemini with structured prompt — `gemini.recommend()`
   9. Persist to the `risk_predictions` and `gemini_recommendations` collections
5. **Display** — iOS calls `GET /risk` for the latest scores + recommendation, and `GET /history?days=90` for the trend tab.

## API contracts (JSON — DO NOT CHANGE WITHOUT A SCHEMA-CHANGE PR)

All endpoints return `application/json`. All require `Authorization: Bearer <session-jwt>` except `POST /auth/login`. Timestamps are ISO-8601 UTC with `Z` suffix throughout. Empty data is sent as `[]`, not omitted.

### `POST /auth/login`

**Request:**
```json
{
  "apple_identity_token": "<JWT from Sign in with Apple>"
}
```

**Response 200:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_token": "<JWT signed by backend, HS256>",
  "is_new_user": true,
  "needs_onboarding": true
}
```

### `POST /onboarding`

**Request:**
```json
{
  "age": 32,
  "sex": "M",
  "height_cm": 178,
  "weight_kg": 75.5,
  "smoking": false,
  "diabetes": false,
  "family_history_cvd": false,
  "race_ethnicity": "white",
  "systolic_bp": 122,
  "total_cholesterol": null,
  "hdl_cholesterol": null,
  "on_bp_medication": false
}
```

| Field | Type | Required | Allowed |
|---|---|---|---|
| `age` | int | ✅ | 18–100 |
| `sex` | str | ✅ | `"M"`, `"F"` |
| `height_cm` | float | ✅ | 100–250 |
| `weight_kg` | float | ✅ | 30–250 |
| `smoking` | bool | ✅ | — |
| `diabetes` | bool | ✅ | — |
| `family_history_cvd` | bool | ✅ | — |
| `race_ethnicity` | str | ❌ | `"white"`, `"black"`, `"asian"`, `"hispanic"`, `"other"`, `null` |
| `systolic_bp` | int | ❌ | 70–250 mmHg, `null` |
| `total_cholesterol` | int | ❌ | 80–400 mg/dL, `null` |
| `hdl_cholesterol` | int | ❌ | 10–150 mg/dL, `null` |
| `on_bp_medication` | bool | ❌ | — |

**Response 200:**
```json
{
  "onboarding_id": "...",
  "completed_at": "2026-04-19T14:32:00Z"
}
```

### `POST /healthkit`

**Request:**
```json
{
  "uploaded_at": "2026-04-19T14:32:00Z",
  "window_start": "2026-01-19T00:00:00Z",
  "window_end": "2026-04-19T00:00:00Z",
  "samples": {
    "resting_hr_daily":         [{"date": "2026-04-18", "bpm": 62}],
    "hrv_sdnn":                 [{"timestamp": "2026-04-18T03:14:00Z", "ms": 45.2}],
    "vo2_max_latest":           {"value": 38.2, "measured_at": "2026-04-15T11:00:00Z"},
    "steps_daily":              [{"date": "2026-04-18", "count": 8243}],
    "exercise_minutes_daily":   [{"date": "2026-04-18", "minutes": 32}],
    "active_energy_daily_kcal": [{"date": "2026-04-18", "kcal": 412}],
    "sleep_sessions": [
      {
        "start": "2026-04-18T23:14:00Z",
        "end": "2026-04-19T07:02:00Z",
        "duration_min": 468,
        "efficiency": 0.92,
        "stages": {"deep_min": 80, "rem_min": 90, "core_min": 220, "awake_min": 38}
      }
    ],
    "wrist_temp_nightly":       [{"date": "2026-04-18", "delta_c": 0.3}],
    "walking_hr_avg_daily":     [{"date": "2026-04-18", "bpm": 95}],
    "afib_detected": false,
    "afib_episodes": []
  }
}
```

Constraints: `bpm`, `count`, `minutes`, `kcal`, all `*_min` fields are non-negative integers. `ms`, `value`, `efficiency`, `delta_c` are floats. `vo2_max_latest` may be `null` if Apple hasn't computed one yet.

**Response 200:**
```json
{
  "upload_id": "...",
  "received_at": "2026-04-19T14:32:01Z",
  "processed": true
}
```

If `processed == true`, iOS may immediately call `GET /risk`.

### `GET /risk`

No query parameters. Returns the most recent prediction for the authenticated user.

**Response 200:**
```json
{
  "computed_at": "2026-04-19T14:32:02Z",
  "scores": {
    "ascvd_10yr":             {"value": 5.1, "raw_value": 4.2, "augmented_value": 5.1, "category": "low"},
    "framingham_10yr_cvd":    {"value": 6.4, "category": "low"},
    "findrisc_10yr_diabetes": {"value": 12, "max": 26, "category": "elevated"},
    "life_essential_8":       {"value": 71, "max": 100, "category": "moderate"},
    "fitness_age":            {"value": 41, "chronological_age": 32, "delta": 9},
    "nhanes_mortality_10yr":  {"value": 3.2, "ci_low": 1.8, "ci_high": 5.1}
  },
  "top_drivers": [
    {"feature": "sleep_regularity_index", "value": 58,   "population_norm": 75, "direction": "worse", "weight": 0.35, "human_label": "Sleep regularity"},
    {"feature": "vo2_max",                "value": 31.2, "population_norm": 42, "direction": "worse", "weight": 0.28, "human_label": "Cardiorespiratory fitness"},
    {"feature": "resting_hr_trend",       "value": 6,    "population_norm": 0,  "direction": "worse", "weight": 0.18, "human_label": "Resting heart rate trend"}
  ],
  "gemini_recommendation": {
    "summary": "Your sleep regularity is the biggest single contributor to your elevated risk.",
    "actions": [
      {
        "finding": "Your bedtime varies by ±2.6 hours across the past 30 days.",
        "action": "Anchor bedtime to a 30-minute window every night, weekends included.",
        "rationale": "Sleep regularity is independently linked to cardiovascular mortality even when total sleep is adequate."
      },
      {"finding": "...", "action": "...", "rationale": "..."},
      {"finding": "...", "action": "...", "rationale": "..."}
    ],
    "disclaimer": "These suggestions don't replace a physician's review."
  }
}
```

### `GET /history?days=90`

**Query params:** `days` (int, default `90`, range `7–365`)

**Response 200:**
```json
{
  "user_id": "...",
  "days": 90,
  "series": {
    "ascvd_10yr":       [{"date": "2026-04-18", "value": 5.0}],
    "fitness_age":      [{"date": "2026-04-18", "value": 41}],
    "resting_hr_daily": [{"date": "2026-04-18", "bpm": 62}],
    "vo2_max":          [{"date": "2026-04-18", "value": 38.2}],
    "sleep_regularity": [{"date": "2026-04-18", "value": 58}]
  }
}
```

## Error responses

All errors return:

```json
{"error": {"code": "string_code", "message": "human-readable", "details": {}}}
```

with HTTP status:

| Status | When |
|---|---|
| 400 | Schema validation failed (Pydantic raises) |
| 401 | Missing or invalid `Authorization` header |
| 403 | Token expired |
| 404 | Resource not found (e.g. no risk computed yet) |
| 409 | Conflict (e.g. onboarding already submitted) |
| 422 | Apple identity token failed verification |
| 500 | Unhandled server error (must be logged) |
| 502 | Gemini API failed |
| 503 | ML model not loaded |

## Database schema

Defined in `almond-ml/db.py` using Beanie `Document` models on top of Motor (async MongoDB driver). Beanie is initialized in the FastAPI lifespan handler (`init_beanie(database=client.almond, document_models=[...])`); collections and indexes are created on app startup. **Do not write raw migration scripts** — schema changes happen by editing the Document classes and (if needed) writing an idempotent backfill in `almond-ml/scripts/`.

Object IDs use Mongo's native `ObjectId` for the document `_id` (exposed as `id` in API responses); cross-collection references are stored as `ObjectId` fields, not embedded. JSON-shaped payloads (`scores`, `top_drivers`, `payload`, `response`) are stored as native BSON sub-documents — **no stringified JSON blobs**.

| Collection | Fields |
|---|---|
| `users` | `_id` (ObjectId), `apple_user_id` (str, unique index), `created_at` (datetime) |
| `onboarding` | `_id` (ObjectId), `user_id` (ObjectId, indexed), `age` (int), `sex` (str), `height_cm` (float), `weight_kg` (float), `smoking` (bool), `diabetes` (bool), `family_history_cvd` (bool), `race_ethnicity` (str nullable), `systolic_bp` (int nullable), `total_cholesterol` (int nullable), `hdl_cholesterol` (int nullable), `on_bp_medication` (bool nullable), `completed_at` (datetime) |
| `healthkit_uploads` | `_id` (ObjectId), `user_id` (ObjectId, indexed), `uploaded_at` (datetime, indexed desc), `window_start` (datetime), `window_end` (datetime), `payload` (sub-document — full request body as BSON) |
| `risk_predictions` | `_id` (ObjectId), `user_id` (ObjectId, indexed), `upload_id` (ObjectId), `computed_at` (datetime, indexed desc), `scores` (sub-document), `top_drivers` (array of sub-documents). Compound index on `(user_id, computed_at desc)` for `GET /risk` and `GET /history` |
| `gemini_recommendations` | `_id` (ObjectId), `prediction_id` (ObjectId, indexed), `prompt_template_version` (str), `prompt_full` (str), `response` (sub-document), `model_name` (str), `latency_ms` (int) |

## Gemini prompt contract

The prompt template lives in `almond-ml/gemini.py` as the constant `PROMPT_TEMPLATE` plus `PROMPT_TEMPLATE_VERSION` (semver string). **Bump the version on every prompt change** so we can diff outputs over time.

Hard requirements for the prompt:

1. The model is identified as a "wellness coach, not a doctor."
2. The structured score JSON is injected inline (not paraphrased).
3. The user's demographics from onboarding are injected.
4. The model must return JSON via `response_mime_type="application/json"`.
5. The output schema is exactly `{"summary": str, "actions": [{"finding": str, "action": str, "rationale": str}, ×3], "disclaimer": str}`.
6. The prompt explicitly forbids medical claims and requires the disclaimer string.
7. If Gemini returns malformed JSON, the backend retries once, then returns a 502.

## Code ownership

| Path | Owner | Notes |
|---|---|---|
| `almond-app/` | iOS Engineer | Networking layer must mirror `almond-ml/schemas.py` byte-for-byte |
| `almond-ml/` | **Deniz (Godfather)** | All Python — backend, ML, training, Gemini |
| `AGENTS.md`, `README.md`, `.gitignore`, root config | **Deniz (Godfather)** | Cross-cutting; Godfather approves all changes |

**The iOS Engineer never edits `almond-ml/`. Deniz never edits `almond-app/`.** If a cross-cutting change is needed (e.g. a new field added to a schema requires a matching iOS model), open one PR that touches both, and explicitly call out the cross-cut in the description so the reviewer can confirm both sides match.

## Git workflow specifics

### Branch naming

`<type>/<short-kebab-desc>`. Type is one of:

- `feat/` — new feature
- `fix/` — bug fix
- `chore/` — config or refactor with no behavior change
- `deps/` — dependency change only
- `docs/` — documentation / spec / comments only

Examples: `feat/onboarding-form`, `fix/healthkit-timezone`, `deps/scikit-survival-bump`.

### Commit messages

Conventional Commits: `<type>(<scope>): <message>`. Scope is the folder. Examples:

- `feat(almond-app): add onboarding form`
- `fix(almond-ml): handle empty hrv_sdnn array`
- `chore(almond-ml): pin numpy 1.26`

### Pull request template

Every PR description must contain these sections:

```
## What
<one paragraph: what this PR does>

## Why
<one paragraph: why this is needed>

## How to test
- <bullet list: steps a reviewer can take>

## API / schema changes
<list any change to almond-ml/schemas.py, almond-ml/db.py, or any JSON contract — or "none">

## Cross-folder changes
<list any file edited outside your owned folder — or "none">

Ready for review and merge — @3arii please squash & merge.
```

### Merge strategy

**Squash & merge.** The Godfather (`@3arii`) performs the merge. Never rebase-merge, never merge commits.

### Conflict resolution

If GitHub flags conflicts on your PR:

1. `git fetch origin main`
2. `git rebase origin/main` on your branch
3. Resolve conflicts in your editor, run tests
4. `git push --force-with-lease` (NOT plain `--force`)
5. Re-tag `@3arii` in a new PR comment

### Branch protection (Godfather to enable on the GitHub repo)

- `main` requires PR review with `@3arii` approval
- No direct pushes to `main`
- No force-push to `main`
- Require linear history
- Require all status checks to pass

## Environment variables

Never commit secrets. `almond-ml/.env.example` lists required keys with placeholder values:

```
GEMINI_API_KEY=                     # https://aistudio.google.com/apikey
JWT_SIGNING_KEY=                    # generate: python -c "import secrets; print(secrets.token_urlsafe(64))"
APPLE_TEAM_ID=                      # from Apple Developer portal
APPLE_BUNDLE_ID=com.almond.app
APPLE_KEY_ID=                       # the key ID for Sign in with Apple
APPLE_PRIVATE_KEY_PATH=             # path to the .p8 file (file itself is gitignored)
MONGODB_URL=mongodb://localhost:27017       # local dev; for prod use the Atlas SRV string
MONGODB_DB_NAME=almond
```

`.env` and `*.p8` are in `.gitignore`. If you add a new secret, add the key (with a placeholder value) to `.env.example` in the same PR.

## What an agent must check with the Godfather before doing

- Adding a Python or Swift dependency
- Changing any Pydantic model in `almond-ml/schemas.py`
- Changing any Beanie `Document` definition (or its indexes) in `almond-ml/db.py`
- Changing the Gemini prompt template
- Choosing a different hosting platform / database / framework
- Working on a feature outside the assigned folder
- Adding any external network call beyond Apple JWKS, Gemini, and the iOS↔backend channel

## Decisions still TBD (Godfather to confirm)

- **iOS Engineer's GitHub handle** — for tagging in cross-folder PRs that need their review
- **PDF export library** — suggestion: `reportlab` server-side, `GET /report/pdf` returns a download URL. Stretch goal, not MVP.
- **watchOS complication** — post-MVP stretch, not in scope for the 36-hour build

## Definition of Done per component

- **`almond-app/`**: builds in Xcode, signs in with Apple, completes onboarding, uploads HealthKit data, displays scores + recommendation + history charts. No Xcode warnings. Manually tested on a real Apple Watch + iPhone (or simulator with seeded HealthKit).
- **`almond-ml/`**: `uvicorn main:app` runs locally against a `mongod` (or Atlas) instance, all five endpoints respond per the schemas above, MongoDB persists across restarts, indexes are created on startup, `pytest almond-ml/tests` passes (uses a throwaway test database name, dropped on teardown), deploys cleanly to Railway with `MONGODB_URL` pointing at Atlas.
- **ML model**: `cox_model.pkl` loads in <1 s, predictions deterministic for fixed inputs, validation concordance index ≥ 0.70 on held-out NHANES split, training notebook reproducible (fixed seed + pinned package versions).
- **Gemini integration**: prompt produces valid JSON every time, no medical-diagnosis language, disclaimer always present, latency <5 s.
