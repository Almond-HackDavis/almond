"""Phase 2 — End-to-end Gemini integration.

Takes a synthetic HealthKit-shape input (the 8 datapoints we're working with),
engineers the 8 Cox features, predicts 2-year all-cause mortality, computes
the user-facing Heart Health Score (1-risk)*100, and asks gemini-2.5-flash
for a structured 3-action recommendation.

Run:

    export GEMINI_API_KEY="<your key>"
    inspect/.venv/bin/python inspect/02_gemini.py

Deps:
    google-genai  (install: `uv pip install -U google-genai`)
    pydantic      (already pulled in by sksurv/sklearn)
    pandas, numpy, joblib  (from 1D)

What it prints:
    1. Loaded model summary.
    2. Engineered 8-feature vector for the synthetic subject.
    3. Cox raw probability + Heart Health Score.
    4. The full prompt sent to Gemini (system instruction + user message).
    5. The structured Gemini response (validated against the Pydantic schema).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError

from google import genai
from google.genai import types

# Load inspect/.env so GEMINI_API_KEY is available without `export`.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass  # python-dotenv optional; rely on shell env if not installed.


# ── Config ───────────────────────────────────────────────────────────────────

INSPECT_DIR = Path(__file__).resolve().parent
MODELS_DIR = INSPECT_DIR / "models"
COX_MODEL_PATH = MODELS_DIR / "cox_model.pkl"
FEATURE_MEANS_PATH = MODELS_DIR / "feature_means.json"

GEMINI_MODEL = "gemini-2.5-flash"
HORIZON_MONTHS = 24
PROMPT_TEMPLATE_VERSION = "1.0.0"

FEATURES: tuple[str, ...] = (
    "age", "sex_male", "bmi",
    "mean_daily_mims", "sd_daily_mims",
    "mean_sleep_min", "sd_sleep_min",
    "mean_wake_wear_min",
)


# ── Cox model loading + prediction ───────────────────────────────────────────

def load_cox() -> tuple[object, dict]:
    """Load the trained Cox model + the training-set feature means."""
    model = joblib.load(COX_MODEL_PATH)
    means = json.loads(FEATURE_MEANS_PATH.read_text())
    return model, means


def predict_2yr_mortality(model, features: dict) -> float:
    """Return the 2-year all-cause mortality probability (0..1)."""
    X = pd.DataFrame(
        [{f: float(features[f]) for f in FEATURES}],
        columns=list(FEATURES),
    )
    sf = model.predict_survival_function(X)[0]
    return float(1.0 - sf(HORIZON_MONTHS))


# ── HealthKit-shape input + feature engineering ──────────────────────────────

@dataclass
class HKInput:
    """Minimal stand-in for the 8 HealthKit datapoints we're working with."""
    date_of_birth: date                              # HKCharacteristic.DateOfBirth
    biological_sex: str                              # HKCharacteristic.BiologicalSex ("M" or "F")
    height_m: float                                  # HKQuantity.Height (latest sample)
    body_mass_kg: float                              # HKQuantity.BodyMass (latest sample)
    step_count_daily: Sequence[float]                # HKQuantity.StepCount, 90 daily totals
    active_energy_daily_kcal: Sequence[float]        # HKQuantity.ActiveEnergyBurned, 90 daily kcal
    exercise_time_daily_min: Sequence[float]         # HKQuantity.AppleExerciseTime, 90 daily min
    sleep_session_durations_min: Sequence[float]     # HKCategory.SleepAnalysis, per-session minutes


def engineer_features(hk: HKInput, today: date | None = None) -> dict:
    """Map the 8 HK datapoints to the 8 locked Cox features.

    NOTE: the steps + kcal + exercise → MIMS composite below is a PLACEHOLDER
    calibrated to roughly straddle the NHANES PAXDAY mean (~2.67M MIMS/day).
    Proper empirical calibration belongs in `ml.py` once we have ground-truth
    pairs (Apple Watch raw acc + concurrent NHANES-style MIMS). For Phase 2
    we just need plausible numbers in the right scale so the Cox prediction
    is sensible.
    """
    today = today or date.today()
    age_years = (today - hk.date_of_birth).days / 365.25
    sex_male = 1.0 if hk.biological_sex.upper() == "M" else 0.0
    bmi = hk.body_mass_kg / (hk.height_m ** 2)

    steps = np.asarray(hk.step_count_daily, dtype=float)
    kcal  = np.asarray(hk.active_energy_daily_kcal, dtype=float)
    excm  = np.asarray(hk.exercise_time_daily_min, dtype=float)
    daily_mims = 250_000.0 * (steps / 1000.0) + 2_000.0 * kcal + 30_000.0 * excm

    sleep = np.asarray(hk.sleep_session_durations_min, dtype=float)
    mean_sleep = float(sleep.mean()) if sleep.size else 0.0
    sd_sleep   = float(sleep.std(ddof=1)) if sleep.size > 1 else 0.0

    # Wake-wear time isn't in our HK input list; estimate from sleep duration.
    # NHANES population mean was ~899 min/day; this gives roughly that for a
    # 7-hour sleeper minus a small non-wear allowance.
    wake_wear = float(24 * 60 - mean_sleep - 20.0) if sleep.size else 900.0

    return {
        "age":                age_years,
        "sex_male":           sex_male,
        "bmi":                bmi,
        "mean_daily_mims":    float(daily_mims.mean()),
        "sd_daily_mims":      float(daily_mims.std(ddof=1)) if daily_mims.size > 1 else 0.0,
        "mean_sleep_min":     mean_sleep,
        "sd_sleep_min":       sd_sleep,
        "mean_wake_wear_min": wake_wear,
    }


# ── Gemini response schema (Pydantic) — grammar-constrained decoding ────────

class Action(BaseModel):
    finding: str
    action: str
    rationale: str


class Recommendation(BaseModel):
    summary: str
    actions: list[Action]   # exactly 3 — enforced via prompt, validated post-hoc
    disclaimer: str


# ── Prompt ───────────────────────────────────────────────────────────────────

DISCLAIMER = "Almond is a wellness tool, not a medical device. Consult a licensed clinician for medical concerns."

SYSTEM_INSTRUCTION = f"""You are Almond, a friendly wellness coach. You are NOT a medical doctor, you do not diagnose, and you do not prescribe. You translate a wearable-derived Heart Health Score into 3 small, evidence-based lifestyle suggestions.

Hard rules:
- Output ONLY JSON matching the provided schema. No prose, no markdown, no code fences.
- Exactly 3 items in `actions`.
- Never name a disease, drug, dose, or test result. Use neutral language ("cardiovascular load", "recovery quality", "movement volume", "sleep regularity").
- Never echo raw user identifiers, dates of birth, or device IDs.
- Each `finding` is 1–2 sentences describing what you noticed in the data.
- Each `action` is 1 short, concrete sentence the user can do this week.
- Each `rationale` is 1 sentence citing the broad reason in plain language.
- The `summary` is one warm, encouraging sentence framing the score in context (don't quote the raw probability).
- The `disclaimer` field MUST be the exact string: "{DISCLAIMER}"

Schema:
{{"summary": str, "actions": [{{"finding": str, "action": str, "rationale": str}} x 3], "disclaimer": str}}"""


def build_user_prompt(features: dict, raw_risk: float, score: float, hk_summary: dict) -> str:
    sex_label = "male" if features["sex_male"] == 1.0 else "female"
    return f"""USER SNAPSHOT (90-day HealthKit window):
- Age: {features["age"]:.0f} years
- Sex: {sex_label}
- BMI: {features["bmi"]:.1f}
- Steps / day (mean):              {hk_summary["avg_steps"]:>7,.0f}
- Active energy / day (mean kcal): {hk_summary["avg_kcal"]:>7.0f}
- Exercise minutes / day (mean):   {hk_summary["avg_exercise_min"]:>7.1f}
- Sleep / night (mean):            {features["mean_sleep_min"] / 60:>7.1f} hours
- Sleep variability (SD):          {features["sd_sleep_min"] / 60:>7.1f} hours
- Wake-wear time / day (mean):     {features["mean_wake_wear_min"] / 60:>7.1f} hours

ALMOND HEART HEALTH SCORE (0-100, higher is better): {score:.1f}
Underlying 2-year all-cause mortality probability: {raw_risk * 100:.2f}%

Produce 3 lifestyle actions tied to the strongest improvement levers in this snapshot. Reply with JSON only, exactly matching the schema. No medical claims."""


# ── Gemini call (with one retry) ────────────────────────────────────────────

def call_gemini(client: genai.Client, user_prompt: str) -> Recommendation:
    """Call gemini-2.5-flash with grammar-constrained decoding. Retry once on parse fail."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=Recommendation,
        temperature=0.3,
        max_output_tokens=900,
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # latency
    )

    contents = user_prompt
    for attempt in (1, 2):
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        text = (resp.text or "").strip()
        try:
            rec = Recommendation.model_validate_json(text)
            if len(rec.actions) != 3:
                raise ValidationError.from_exception_data(
                    "Recommendation",
                    [{"type": "value_error", "loc": ("actions",), "msg": f"expected exactly 3, got {len(rec.actions)}"}],
                )
            return rec
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == 2:
                print("\n  malformed Gemini response after retry:")
                print(f"  raw text: {text[:500]}")
                raise
            print(f"  parse error (attempt {attempt}), retrying once: {e}")
            contents = (
                user_prompt
                + "\n\nYour previous reply was not valid JSON matching the schema. "
                "Reply ONLY with valid JSON, exactly 3 items in `actions`."
            )


# ── Synthetic input ──────────────────────────────────────────────────────────

def synthetic_hk(seed: int = 42) -> HKInput:
    """A 32-year-old moderately-active male, 90 days of HealthKit-shape signal."""
    rng = np.random.default_rng(seed=seed)
    return HKInput(
        date_of_birth=date(1994, 3, 15),
        biological_sex="M",
        height_m=1.78,
        body_mass_kg=82.0,
        step_count_daily=rng.normal(8_500, 1_500, 90).clip(0).astype(int).tolist(),
        active_energy_daily_kcal=rng.normal(420, 80, 90).clip(0).tolist(),
        exercise_time_daily_min=rng.normal(25, 10, 90).clip(0).tolist(),
        sleep_session_durations_min=rng.normal(425, 35, 90).clip(180).tolist(),
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY env var not set.\n"
            "  Get a key at https://aistudio.google.com/apikey\n"
            "  Then `export GEMINI_API_KEY=...` before running."
        )

    print("loading Cox model …")
    model, means = load_cox()
    print(f"  cox_model.pkl loaded, {len(model.coef_)} coefficients")
    print(f"  feature_means.json loaded for: {list(means.keys())}\n")

    print("building synthetic HealthKit input (32-yo moderately-active male, 90 days) …")
    hk = synthetic_hk()
    features = engineer_features(hk)
    print("  engineered 8-feature vector:")
    for k in FEATURES:
        print(f"    {k:22s} {features[k]:>14.4f}")
    print()

    print("Cox prediction …")
    raw_risk = predict_2yr_mortality(model, features)
    score = (1.0 - raw_risk) * 100.0
    print(f"  raw 2-yr mortality probability: {raw_risk * 100:.4f} %")
    print(f"  Almond Heart Health Score:      {score:.2f} / 100\n")

    hk_summary = {
        "avg_steps":         float(np.mean(hk.step_count_daily)),
        "avg_kcal":          float(np.mean(hk.active_energy_daily_kcal)),
        "avg_exercise_min":  float(np.mean(hk.exercise_time_daily_min)),
    }
    user_prompt = build_user_prompt(features, raw_risk, score, hk_summary)

    print("─── prompt sent to Gemini ──────────────────────────────────────")
    print("[system instruction]")
    print(SYSTEM_INSTRUCTION)
    print()
    print("[user message]")
    print(user_prompt)
    print()

    print("calling gemini-2.5-flash …")
    client = genai.Client(api_key=api_key)
    rec = call_gemini(client, user_prompt)
    print("  response received and validated against schema\n")

    print("─── Gemini structured response ────────────────────────────────")
    print(json.dumps(rec.model_dump(), indent=2))


if __name__ == "__main__":
    main()
