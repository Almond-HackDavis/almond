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
    ],

    // Tier-2 HealthKit augmentation signals — all optional; pipeline degrades
    // gracefully when iOS hasn't collected them yet.
    "resting_hr_daily": [{ "date": "2026-05-08", "bpm": 58 }],
    "hrv_sdnn": [{ "timestamp": "2026-05-08T03:14:00Z", "ms": 68 }],
    "vo2_max_latest": { "value": 47.5, "measured_at": "2026-05-05T11:00:00Z" },
    "walking_hr_avg_daily": [{ "date": "2026-05-08", "bpm": 102 }]
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
    "vitality_score": { "value": 80.4, "max": 100 },
    "nhanes_mortality_2yr": {
      "value": 0.0019,
      "ci_low": null,
      "ci_high": null
    },
    "fitness_age": { "value": 22.9, "chronological_age": 35, "delta": -12.1 }
  },
  "top_drivers": [
    {
      "feature": "activity",
      "human_label": "Daily activity",
      "value": 4583750.0,
      "contribution_pts": 3.06,
      "direction": "better"
    },
    {
      "feature": "hrv",
      "human_label": "Heart-rate variability",
      "value": 70.0,
      "contribution_pts": 1.78,
      "direction": "better"
    },
    {
      "feature": "vo2",
      "human_label": "Cardiorespiratory fitness (VO₂ max)",
      "value": 47.5,
      "contribution_pts": 1.48,
      "direction": "better"
    }
  ],
  "gemma_summary": "Your Vitality Score of 80.4 reflects a solid foundation — your sleep duration is right around the recommended window and your activity volume is in a healthy range for someone your age. ...",
  "disclaimer": "Almond is a wellness tool, not a medical device. Consult a licensed clinician for medical concerns.",
  "model_metadata": {
    "model_id": "almond-cox-2yr-v0.2.0",
    "prompt_template_version": "2.0.0",
    "llm_model": "gemma-4-31b-it",
    "horizon_months": 24
  }
}
```

## How the score is computed

1. `engineer_features()` builds the 4-feature Cox vector from the request:
   `age`, `sex_male`, `bmi_dev = |BMI − 22|`, `sleep_dev = |mean_sleep_min − 450|`.
   It also computes `mean_daily_mims` from steps + active energy + exercise minutes
   and parses the optional Tier-2 augmentation signals (RHR / HRV / VO2 / walking HR).
2. `predict_2yr_mortality()` runs the trained Cox (`models/cox_model.pkl`) and returns
   the 24-month all-cause mortality probability.
3. `vitality_score()` combines two layers:
   - `base = 100 × (1 − pool_percentile(raw_risk))` against the NHANES
     training cohort, ensuring the score is age-monotonic.
   - `composite_bonus(...)` — a weighted average over whatever augmentation
     signals iOS provided, scaled to ±13 vitality points. Per-signal wellness
     curves are literature-anchored:

     | Signal             | Source                            | Reference                      | Weight |
     | ------------------ | --------------------------------- | ------------------------------ | ------ |
     | `activity` (MIMS)  | Saint-Maurice 2020                | 3.0 M MIMS/day (cohort median) | 0.30   |
     | `rhr` (resting HR) | Jensen 2013 (Eur Heart J)         | 65 bpm                         | 0.22   |
     | `hrv` (SDNN)       | Hillebrand 2013                   | 50 ms                          | 0.18   |
     | `vo2` (VO2 max)    | Kaminsky 2013 / FRIEND + Nes 2013 | age × sex norm                 | 0.25   |
     | `walking_hr`       | secondary                         | 105 bpm                        | 0.05   |

     Signals the user hasn't collected are omitted from the average rather
     than zeroed — a Tier-1-only request ("first-day Apple Watch user") gets
     the same score it would have gotten before this branch landed.

4. `fitness_age` is derived from VO2 max via Nes 2013's NTNU formula:
   `fitness_age = age + (VO2_ref(age, sex) − VO2_observed) / slope`,
   clipped to `[18, 90]`. Omitted from `scores` when iOS hasn't sent VO2.
5. `top_drivers` is the 3 signals with the largest absolute contribution,
   with `direction: "better" | "worse"`. iOS uses it to render badges.
6. `gemma.summarize()` builds a 3-4 sentence wellness paragraph from a
   tight snapshot. If Gemma 500s (free-tier flapping), the SDK retries
   up to 2× with backoff; on final failure the service emits a
   deterministic fallback summary so the request still succeeds.

The trained Cox itself (the 4-feature Cox) was fit and stress-tested in
`inspect/` — see `inspect/01c_features.py` for the data-driven justification
of dropping MIMS/sleep-SD/wake-wear from the training feature set, and
`inspect/stress_test.py` for the original 62-persona regression suite.

The combined Cox + augmentation pipeline has its own stress grid at
`almond-ml/stress_grid.py` — 56 persona cells × (age, sex, lifestyle)
plus 7 targeted edge cases, all three monotonicity invariants verified:

A. Within-age lifestyle ordering (elite > healthy_avg > sedentary > frail).
B. Across-age: same-lifestyle, younger outscores older.
C. Headline: 35M healthy outscores 65F sedentary by ≥ 20 vitality pts.

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
