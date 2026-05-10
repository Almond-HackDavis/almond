# almond-ml — sync Cox + Gemma pipeline

Single-purpose FastAPI service. iOS sends an input payload; the server
runs the trained Cox model and a Gemma-generated summary, persists the
result to MongoDB, and returns it.

## Endpoints

| Method | Path       | Purpose                                                                                            |
| ------ | ---------- | -------------------------------------------------------------------------------------------------- |
| POST   | `/input`   | Run Cox + Gemma synchronously, persist `outputs._id="current"` + a history copy, return the result |
| GET    | `/output`  | Read the latest `outputs._id="current"` (no recompute)                                             |
| GET    | `/healthz` | Liveness probe — does NOT touch Mongo or the Cox model                                             |

There is no auth, no separate worker, no polling. The pipeline runs end-to-end
inside `POST /input` (~3-5s wall-clock, dominated by the Gemma call).

## Wire shapes

`POST /input` request:

```json
{
  "onboarding": {
    "age": 28,
    "sex": "M",
    "height_cm": 178.0,
    "weight_kg": 75.0,
    "smoking": false,
    "diabetes": false,
    "family_history_cvd": false,
    "on_bp_medication": false,
    "race_ethnicity": null,
    "systolic_bp": null,
    "total_cholesterol": null,
    "hdl_cholesterol": null
  },
  "samples": {
    "steps_daily": [{ "date": "2026-05-08", "count": 3626 }],
    "active_energy_daily_kcal": [{ "date": "2026-05-08", "kcal": 412 }],
    "exercise_minutes_daily": [{ "date": "2026-05-08", "minutes": 32 }],
    "sleep_sessions": [
      {
        "start": "2026-05-07T23:00:00Z",
        "end": "2026-05-08T07:00:00Z",
        "duration_min": 480
      }
    ]
  }
}
```

Response (also what `GET /output` returns once any input has been processed):

```json
{
  "_id": "current",
  "computed_at": "2026-05-09T23:55:14.123Z",
  "input_uploaded_at": "2026-05-09T23:55:11.456Z",
  "scores": {
    "vitality_score": { "value": 72.4, "max": 100 },
    "nhanes_mortality_2yr": { "value": 0.018, "ci_low": null, "ci_high": null }
  },
  "gemma_summary": "Your Vitality Score of 72.4 reflects a solid foundation of healthy habits — your sleep duration is right around the recommended window and your activity volume is in a healthy range for someone your age. ...",
  "disclaimer": "Almond is a wellness tool, not a medical device. Consult a licensed clinician for medical concerns.",
  "model_metadata": {
    "model_id": "almond-cox-2yr-v0.1.0",
    "prompt_template_version": "2.0.0",
    "llm_model": "gemma-4-31b-it",
    "horizon_months": 24
  }
}
```

## How the score is computed

1. `engineer_features()` builds the 4-feature Cox vector from the request:
   `age`, `sex_male`, `bmi_dev = |BMI − 22|`, `sleep_dev = |mean_sleep_min − 450|`.
   It also computes `mean_daily_mims` from steps + active energy + exercise minutes.
2. `predict_2yr_mortality()` runs the trained Cox (`models/cox_model.pkl`) and returns
   the 24-month all-cause mortality probability.
3. `vitality_score()` blends:
   - `base = 100 × (1 − pool_percentile(raw_risk))` against the NHANES
     training cohort, ensuring the score is age-monotonic.
   - `activity_bonus = ±10 × tanh((MIMS_M − 3.0) / 1.5)` anchored to
     Saint-Maurice 2020's effect size for highest-vs-lowest MIMS quintile.
4. `gemma.summarize()` builds a 4-6 sentence wellness paragraph from the
   numbers + a short user snapshot. If Gemma is unavailable the service
   falls back to a deterministic summary so the request still succeeds.

The model itself was trained and stress-tested in `inspect/`. See
`inspect/01c_features.py` for the data-driven justification of the 4-feature
set + activity bonus design, and `inspect/stress_test.py` for the 62-persona
regression suite.

## Local development

```bash
cd almond-ml

uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

cp .env.example .env
# Set MONGODB_URI to mongodb://localhost:27017 (or your Atlas string)
# Set GEMMA_API_KEY to your Google AI Studio key

uvicorn main:app --reload
```

Hit `http://localhost:8000/docs` for the OpenAPI explorer.

## Tests

```bash
pytest tests/ -q
```

The test suite uses `mongomock-motor` for an in-memory Mongo and monkey-patches
`gemma.summarize` to return a fixed string — no Google API key needed.

## File layout

```
almond-ml/
├── main.py                  # FastAPI app + lifespan
├── schemas.py               # Pydantic v2 wire shapes
├── db.py                    # Beanie Documents + Mongo client lifespan
├── ml.py                    # Cox load + predict + vitality + activity bonus
├── gemma.py                 # Gemma summary call
├── routes/input_routes.py   # POST /input + GET /output
├── tests/                   # pytest async + mongomock + stub Gemma
├── models/                  # cox_model.pkl, percentile_lookup.json, feature_means.json
├── pyproject.toml
└── .env.example
```

## Trade-offs we accepted

- **Sync, not async.** The pipeline runs in the request handler. Latency is
  dominated by the Gemma call (~2-4s). For a hackathon demo this is the
  simplest possible architecture — no worker process, no queue, no polling.
- **Singleton "current" document.** `outputs._id="current"` is upserted on
  every request so iOS reads one row to render the dashboard. We also append
  a UUID-keyed history copy to `outputs` for charts / replay.
- **Gemma fallback.** If the LLM call fails, we serve a deterministic summary
  so the score still gets persisted. The `model_metadata.llm_model` field
  records `"fallback-deterministic-v0"` in that case.

## Out of scope for this PR

- Auth (Sign in with Apple, JWTs)
- iOS app code
- AGENTS.md spec reconciliation — separate `docs:` PR will update the spec
  to describe the simplified sync-pipeline architecture
