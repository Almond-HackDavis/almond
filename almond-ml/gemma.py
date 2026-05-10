"""Gemma summary generation.

Calls Google's `google-genai` SDK with `gemma-4-31b-it` (configurable via
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

# Google retired the gemma-3 family on the public API; the only Gemma 3-class
# models exposed via google-genai are now Gemma 4. Probed available models:
#   gemma-4-31b-it    (dense 31B — similar size + behavior to old gemma-3-27b-it)
#   gemma-4-26b-a4b-it (MoE, ~26B effective)
# We default to the dense 31B because its outputs are slightly more on-prompt
# for short structured-summary tasks like ours. Override via GEMMA_MODEL env
# var if needed.
DEFAULT_MODEL = "gemma-4-31b-it"
PROMPT_TEMPLATE_VERSION = "2.0.0"

DISCLAIMER = (
    "Almond is a wellness tool, not a medical device. "
    "Consult a licensed clinician for medical concerns."
)

# Minimal prompt template. Anything longer than ~300 chars total has been
# observed to trigger 500 INTERNAL from Google's Gemma endpoint on the free
# AI Studio tier. Keep it tight.
SYSTEM_INSTRUCTION = ""   # No-op; kept as a symbol so the import surface is stable.


@dataclass
class GemmaResult:
    summary: str
    model: str
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION


def _build_user_prompt(*, age: int, sex: str, bmi: float, mean_sleep_min: float,
                       avg_steps: float, avg_kcal: float, avg_exercise_min: float,
                       vitality: float, raw_risk: float) -> str:
    """Tight ~300-char prompt: snapshot + score + single instruction.

    Anything more verbose 500's on the free Gemma AI Studio tier.
    `raw_risk` is intentionally omitted — we don't want the LLM to quote it.
    """
    sex_label = "male" if sex.upper() == "M" else "female"
    sleep_h = mean_sleep_min / 60
    return (
        f"User: {age}yo {sex_label}, BMI {bmi:.1f}, "
        f"{avg_steps:.0f} steps/day, {avg_kcal:.0f} kcal/day active, "
        f"{avg_exercise_min:.0f} min exercise/day, {sleep_h:.1f}h sleep/night. "
        f"Vitality Score: {vitality:.1f}/100.\n\n"
        "Write a warm 3-4 sentence wellness summary. "
        "Mention 1 strength and 1 improvement. No medical advice, no lists."
    )


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
        temperature=0.4,
        max_output_tokens=300,
    )

    log.info("calling Gemma model=%s prompt_chars=%d", model, len(user_prompt))

    # Google's free-tier Gemma endpoint flaps with 500 INTERNAL fairly often.
    # Retry transient 5xx up to 2 times with a short backoff. We do NOT retry
    # 4xx (rate limit, malformed prompt) — those won't get better.
    import time
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=config,
            )
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("Gemma returned an empty response")
            if attempt > 0:
                log.info("Gemma succeeded on retry attempt=%d", attempt + 1)
            return GemmaResult(summary=text, model=model)
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            transient = ("500" in msg) or ("503" in msg) or ("INTERNAL" in msg) or ("UNAVAILABLE" in msg)
            if not transient or attempt == 2:
                break
            sleep_s = 0.6 * (attempt + 1)
            log.warning("Gemma transient error attempt=%d (%s); retrying in %.1fs",
                        attempt + 1, msg[:80], sleep_s)
            time.sleep(sleep_s)

    raise last_exc  # type: ignore[misc]
