"""Single-user worker. One input doc, one output doc, both singletons.

Polls Atlas. When `almond.input._id="current"` has `dirty=True`, runs Cox
+ Gemini and upserts the prediction over `almond.output._id="current"`.
Then flips the input's `dirty` flag back to False.

Run modes:

    inspect/.venv/bin/python inspect/04_worker.py                     # poll loop, default 2s
    inspect/.venv/bin/python inspect/04_worker.py --once              # one pass then exit
    inspect/.venv/bin/python inspect/04_worker.py --poll-interval 5

Env vars (read from inspect/.env via python-dotenv):
    GEMINI_API_KEY  — required
    MONGODB_URI     — required (Atlas SRV string)
    MONGODB_DB      — default `almond`
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

import numpy as np
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from google import genai

# Reuse 02's primitives — same load_cox / predict / Gemini call as the demo.
_g = SourceFileLoader(
    "g02", str(Path(__file__).resolve().parent / "02_gemini.py")
).load_module()
load_cox                  = _g.load_cox
predict_2yr_mortality     = _g.predict_2yr_mortality
load_percentile_lookup    = _g.load_percentile_lookup
vitality_from_percentile  = _g.vitality_from_percentile
build_user_prompt         = _g.build_user_prompt
call_gemini               = _g.call_gemini
FEATURES                  = _g.FEATURES
PROMPT_TEMPLATE_VERSION   = _g.PROMPT_TEMPLATE_VERSION
GEMINI_MODEL              = _g.GEMINI_MODEL
HORIZON_MONTHS            = _g.HORIZON_MONTHS

MODEL_ID = "almond-cox-2yr-v0.1.0"
SINGLETON_ID = "current"


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--once", action="store_true", help="one pass then exit")
    p.add_argument("--poll-interval", type=int, default=2, help="seconds between polls (default 2)")
    return p.parse_args()


# ── Wire-format → 4 Cox features + 1 activity_bonus signal ──────────────────

def features_from_doc(doc: dict) -> dict:
    """Map the input doc's onboarding + samples → the model's feature dict.

    Aggregates each signal independently so per-signal arrays don't have to
    match length (real HK reads frequently don't — e.g. 90 days of steps,
    39 of active energy, 0 of exercise time).
    """
    onboarding = doc["onboarding"]
    samples = doc.get("samples", {})

    age = float(onboarding["age"])
    sex_male = 1.0 if onboarding["sex"] == "M" else 0.0
    bmi_raw = float(onboarding["weight_kg"]) / (float(onboarding["height_cm"]) / 100.0) ** 2

    steps = np.asarray([d["count"]   for d in samples.get("steps_daily", [])],              dtype=float)
    kcal  = np.asarray([d["kcal"]    for d in samples.get("active_energy_daily_kcal", [])], dtype=float)
    excm  = np.asarray([d["minutes"] for d in samples.get("exercise_minutes_daily", [])],   dtype=float)
    mean_steps = float(steps.mean()) if steps.size else 0.0
    mean_kcal  = float(kcal.mean())  if kcal.size  else 0.0
    mean_excm  = float(excm.mean())  if excm.size  else 0.0
    mean_daily_mims = (
        250_000.0 * (mean_steps / 1000.0)
        + 2_000.0  * mean_kcal
        + 30_000.0 * mean_excm
    )

    sleep = np.asarray([s["duration_min"] for s in samples.get("sleep_sessions", [])], dtype=float)
    mean_sleep = float(sleep.mean()) if sleep.size else _g.SLEEP_OPTIMUM_MIN

    return {
        "age":             age,
        "sex_male":        sex_male,
        "bmi_dev":         abs(bmi_raw - _g.BMI_OPTIMUM),
        "sleep_dev":       abs(mean_sleep - _g.SLEEP_OPTIMUM_MIN),
        "mean_daily_mims": mean_daily_mims,
    }


def hk_summary(doc: dict) -> dict:
    """Per-day means + raw bmi/sleep used in the Gemini user prompt."""
    onboarding = doc.get("onboarding") or {}
    samples = doc.get("samples", {})
    steps = [d["count"]   for d in samples.get("steps_daily", [])]
    kcal  = [d["kcal"]    for d in samples.get("active_energy_daily_kcal", [])]
    excm  = [d["minutes"] for d in samples.get("exercise_minutes_daily", [])]
    sleep = [s["duration_min"] for s in samples.get("sleep_sessions", [])]

    if onboarding.get("height_cm") and onboarding.get("weight_kg"):
        bmi = float(onboarding["weight_kg"]) / (float(onboarding["height_cm"]) / 100.0) ** 2
    else:
        bmi = _g.BMI_OPTIMUM

    return {
        "avg_steps":         float(np.mean(steps)) if steps else 0.0,
        "avg_kcal":          float(np.mean(kcal))  if kcal  else 0.0,
        "avg_exercise_min":  float(np.mean(excm))  if excm  else 0.0,
        "avg_sleep_min":     float(np.mean(sleep)) if sleep else _g.SLEEP_OPTIMUM_MIN,
        "bmi":               bmi,
    }


# ── Output doc construction ─────────────────────────────────────────────────

def build_output_doc(input_doc: dict, raw_risk: float, vitality: float, recommendation: Any) -> dict:
    return {
        "_id":           SINGLETON_ID,
        "computed_at":   datetime.now(timezone.utc),
        "input_uploaded_at": input_doc.get("last_uploaded_at"),
        "scores": {
            "vitality_score":       {"value": vitality, "max": 100},
            "nhanes_mortality_2yr": {"value": raw_risk, "ci_low": None, "ci_high": None},
        },
        "gemini_recommendation": recommendation.model_dump(),
        "model_metadata": {
            "model_id":                MODEL_ID,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            "gemini_model":            GEMINI_MODEL,
            "horizon_months":          HORIZON_MONTHS,
        },
    }


# ── One pass: read singleton input, write singleton output ─────────────────

def run_once(db, model, lookup, gen_client) -> str:
    """One pass over the singleton input. Returns a status string."""
    in_doc = db["input"].find_one({"_id": SINGLETON_ID})
    if in_doc is None:
        return "no_input"
    if not in_doc.get("dirty", True):
        return "clean"

    print("  ◀ singleton input is dirty, processing …", flush=True)
    try:
        features = features_from_doc(in_doc)
        raw_risk = predict_2yr_mortality(model, features)
        vitality = vitality_from_percentile(
            raw_risk, features["age"], features["sex_male"], lookup
        )
        print(f"    cox: raw={raw_risk*100:.3f}%  vitality={vitality:.1f}", flush=True)

        prompt = build_user_prompt(features, raw_risk, vitality, hk_summary(in_doc))
        recommendation = call_gemini(gen_client, prompt)
        print(f"    gemini: {recommendation.summary[:80]}…", flush=True)

        out_doc = build_output_doc(in_doc, raw_risk, vitality, recommendation)
        db["output"].update_one({"_id": SINGLETON_ID}, {"$set": out_doc}, upsert=True)

        # Mark input clean so we don't reprocess until the next iOS POST.
        db["input"].update_one(
            {"_id": SINGLETON_ID},
            {"$set": {"dirty": False, "last_processed_at": out_doc["computed_at"]}},
        )
        print(f"  ▶ wrote output (computed_at={out_doc['computed_at'].isoformat()})", flush=True)
        return "done"
    except Exception as e:
        print(f"  ✕ failed: {e}", flush=True)
        db["input"].update_one(
            {"_id": SINGLETON_ID},
            {"$set": {
                "dirty":          False,   # don't loop on a poison pill
                "failure_reason": str(e)[:500],
                "failed_at":      datetime.now(timezone.utc),
            }},
        )
        return "failed"


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    uri     = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "almond")
    missing = [n for n, v in (("GEMINI_API_KEY", api_key), ("MONGODB_URI", uri)) if not v]
    if missing:
        print(f"missing env: {', '.join(missing)} — set in inspect/.env", file=sys.stderr)
        return 1

    print(f"db:   {db_name}")
    print(f"mode: {'once' if args.once else f'poll every {args.poll_interval}s'}\n")

    print("loading Cox model …")
    model, _means = load_cox()
    print(f"  {len(model.coef_)} coefficients")
    print("loading percentile lookup …")
    lookup = load_percentile_lookup()
    print(f"  {len(lookup)} bucket entries\n")

    print("connecting to Atlas …")
    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    db = client[db_name]
    print(f"  connected.\n")

    print("initializing Gemini client …")
    gen_client = genai.Client(api_key=api_key)
    print(f"  model: {GEMINI_MODEL}\n")

    if args.once:
        status = run_once(db, model, lookup, gen_client)
        print(f"\nstatus: {status}")
        return 0

    print(f"polling every {args.poll_interval}s (Ctrl-C to stop) …\n")
    last_status = None
    try:
        while True:
            status = run_once(db, model, lookup, gen_client)
            if status != last_status and status in ("clean", "no_input"):
                # Print this transition once, not every poll.
                print(f"  ({status}; sleeping {args.poll_interval}s)", flush=True)
            last_status = status
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nstopped by user.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
