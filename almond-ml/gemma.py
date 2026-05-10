"""Gemma summary generation.

Calls Google's `google-genai` SDK with `gemma-3-27b-it` (configurable via
GEMMA_MODEL env var) to produce a single 4-6 sentence wellness summary
paragraph for the user. Output goes into the `gemma_summary` field of the
final response.

This module is intentionally stateless — the HTTP handler builds the prompt
from the ML pipeline output and passes it in. We do not retain conversation
context between requests.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("almond.gemma")

DEFAULT_MODEL = "gemma-3-27b-it"
PROMPT_TEMPLATE_VERSION = "2.0.0"

DISCLAIMER = (
    "Almond is a wellness tool, not a medical device. "
    "Consult a licensed clinician for medical concerns."
)

SYSTEM_INSTRUCTION = """You are Almond, a friendly wellness coach. You are NOT a medical doctor, you do not diagnose, and you do not prescribe.

You translate a wearable-derived Vitality Score into a single 4-6 sentence summary paragraph that:
  * Opens with what the score means in plain language.
  * Calls out 1-2 specific habits that look strong (sleep duration, activity volume, BMI in range, etc.).
  * Identifies the single biggest improvement lever (sleep regularity, activity volume, BMI distance from 22, etc.) with a concrete suggestion.
  * Stays warm and encouraging — never alarmist.

Hard rules:
  * Never quote the raw 2-year mortality probability or the underlying Cox features by name.
  * Never give medical advice ("see a doctor about your blood pressure", "consider statin therapy", etc.).
  * Never reference specific clinical conditions you can't verify (no "your diabetes risk", "your heart disease").
  * Output ONLY the summary paragraph. No preamble, no JSON, no headers, no lists. Plain text, single paragraph.
"""


@dataclass
class GemmaResult:
    summary: str
    model: str
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION


def _build_user_prompt(*, age: int, sex: str, bmi: float, mean_sleep_min: float,
                       avg_steps: float, avg_kcal: float, avg_exercise_min: float,
                       vitality: float, raw_risk: float) -> str:
    sex_label = "male" if sex.upper() == "M" else "female"
    return f"""USER SNAPSHOT (90-day HealthKit window):
- Age: {age} years
- Sex: {sex_label}
- BMI: {bmi:.1f}
- Steps / day (mean):              {avg_steps:>7,.0f}
- Active energy / day (mean kcal): {avg_kcal:>7.0f}
- Exercise minutes / day (mean):   {avg_exercise_min:>7.1f}
- Sleep / night (mean):            {mean_sleep_min / 60:>7.1f} hours

ALMOND VITALITY SCORE (0-100, higher is better): {vitality:.1f}
This score blends absolute 2-year mortality risk (most weight) with how you
compare to other US adults of the same age and sex, plus a literature-anchored
activity bonus. A 32-year-old healthy person should always outscore a 65-year-old
with diabetes, even if the 65-year-old is exceptional for her age. Tune your
tone accordingly: a low score deserves concrete, pointed advice; a high score
deserves reinforcement.

Underlying 2-year all-cause mortality probability (do NOT quote to user): {raw_risk * 100:.2f}%

Write a single 4-6 sentence summary paragraph for this user. Plain text only — no JSON, no lists, no headers."""


def summarize(
    *,
    age: int,
    sex: str,
    bmi: float,
    mean_sleep_min: float,
    avg_steps: float,
    avg_kcal: float,
    avg_exercise_min: float,
    vitality: float,
    raw_risk: float,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout_s: float = 8.0,
) -> GemmaResult:
    """Call Gemma to produce the summary. Synchronous; raises on failure.

    The HTTP handler should catch exceptions and return a fallback summary
    (or 502) — we deliberately don't swallow errors here so failures are
    visible in tests and logs.
    """
    # Late import so test runs that monkey-patch this function never need the
    # `google-genai` package installed.
    from google import genai
    from google.genai import types

    api_key = api_key or os.environ.get("GEMMA_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMMA_API_KEY (or GEMINI_API_KEY as fallback) must be set."
        )
    model = model or os.environ.get("GEMMA_MODEL") or DEFAULT_MODEL

    client = genai.Client(api_key=api_key)
    user_prompt = _build_user_prompt(
        age=age, sex=sex, bmi=bmi, mean_sleep_min=mean_sleep_min,
        avg_steps=avg_steps, avg_kcal=avg_kcal, avg_exercise_min=avg_exercise_min,
        vitality=vitality, raw_risk=raw_risk,
    )

    config = types.GenerateContentConfig(
        # Gemma models don't accept `system_instruction` in the same way Gemini
        # does — we prepend it inline. (Gemini-3 added native system role; Gemma
        # 3-27b uses the legacy single-prompt format.)
        temperature=0.4,
        max_output_tokens=400,
    )

    full_prompt = SYSTEM_INSTRUCTION + "\n\n" + user_prompt

    log.info("calling Gemma model=%s prompt_chars=%d", model, len(full_prompt))
    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
        config=config,
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemma returned an empty response")

    return GemmaResult(summary=text, model=model)
