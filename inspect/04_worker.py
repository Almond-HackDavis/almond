"""Phase 3 worker — Atlas-direct. Reads pending inputs, writes outputs.

Talks to MongoDB Atlas only. No FastAPI, no HTTP — iOS hits Atlas directly,
this worker hits Atlas directly. Two collections: `input` and `output`.

Per-doc lifecycle on the `input` side:
    pending → processing → done | failed

The atomic claim uses `find_one_and_update({status: pending}, {$set: {status:
processing, ...}})` so concurrent workers (if we ever run more than one) won't
double-process the same input.

Run modes:

    inspect/.venv/bin/python inspect/04_worker.py --once
    inspect/.venv/bin/python inspect/04_worker.py            # poll loop, default 5s

Env vars (read from inspect/.env via python-dotenv):
    GEMINI_API_KEY  — required
    MONGODB_URI     — required (Atlas SRV string)
    MONGODB_DB      — default `almond`
    WORKER_ID       — default platform.node()
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pymongo
from pymongo import MongoClient, ReturnDocument

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


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--once", action="store_true", help="drain pending then exit")
    p.add_argument("--poll-interval", type=int, default=5, help="seconds between polls (default 5)")
    p.add_argument("--worker-id", default=None, help="overrides WORKER_ID env")
    return p.parse_args()


# ── Wire-format → 8-feature vector (same shape as 03_seed produces) ─────────

def features_from_doc(doc: dict) -> dict:
    """Map an input doc's onboarding + samples → the 5 Cox features.

    Mirrors `02_gemini.engineer_features` and `01c_features.build_features`.
    Three features were dropped relative to the original 8-vector
    (sd_daily_mims, sd_sleep_min, mean_wake_wear_min) — they were collinear
    with kept features and produced perverse coefficients.

    PLACEHOLDER MIMS composite: 250k*(steps/1000) + 2k*kcal + 30k*exercise_min.
    Calibrate to NHANES MIMS scale empirically in a later phase.
    """
    onboarding = doc["onboarding"]
    samples = doc.get("samples", {})

    age = float(onboarding["age"])
    sex_male = 1.0 if onboarding["sex"] == "M" else 0.0
    bmi_raw = float(onboarding["weight_kg"]) / (float(onboarding["height_cm"]) / 100.0) ** 2

    steps = np.asarray([d["count"]   for d in samples.get("steps_daily", [])],              dtype=float)
    kcal  = np.asarray([d["kcal"]    for d in samples.get("active_energy_daily_kcal", [])], dtype=float)
    excm  = np.asarray([d["minutes"] for d in samples.get("exercise_minutes_daily", [])],   dtype=float)
    daily_mims = 250_000.0 * (steps / 1000.0) + 2_000.0 * kcal + 30_000.0 * excm

    sleep = np.asarray([s["duration_min"] for s in samples.get("sleep_sessions", [])], dtype=float)
    mean_sleep = float(sleep.mean()) if sleep.size else _g.SLEEP_OPTIMUM_MIN

    return {
        # Cox features.
        "age":             age,
        "sex_male":        sex_male,
        "bmi_dev":         abs(bmi_raw - _g.BMI_OPTIMUM),
        "sleep_dev":       abs(mean_sleep - _g.SLEEP_OPTIMUM_MIN),
        # Activity signal — feeds activity_bonus, NOT a Cox feature.
        "mean_daily_mims": float(daily_mims.mean()) if daily_mims.size else 0.0,
    }


def hk_summary(doc: dict) -> dict:
    """Per-day means + raw bmi/sleep used in the Gemini user prompt.

    Carries the human-readable raw values (BMI in kg/m², sleep in minutes)
    so the prompt to Gemini shows familiar units rather than the J-shape
    deviations the model uses internally.
    """
    onboarding = doc.get("onboarding") or {}
    samples = doc.get("samples", {})
    steps = [d["count"]   for d in samples.get("steps_daily", [])]
    kcal  = [d["kcal"]    for d in samples.get("active_energy_daily_kcal", [])]
    excm  = [d["minutes"] for d in samples.get("exercise_minutes_daily", [])]
    sleep = [s["duration_min"] for s in samples.get("sleep_sessions", [])]

    bmi: float
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


# ── Output doc construction ──────────────────────────────────────────────────

def build_output_doc(input_doc: dict, raw_risk: float, vitality: float, recommendation: Any) -> dict:
    return {
        "_id":          str(uuid4()),
        "input_id":     input_doc["_id"],
        "user_id":      input_doc["user_id"],
        "computed_at":  datetime.now(timezone.utc),
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


# ── Per-input pipeline ───────────────────────────────────────────────────────

def claim_one(inputs, worker_id: str) -> dict | None:
    """Atomically claim one pending input. Returns the claimed doc or None."""
    return inputs.find_one_and_update(
        {"status": "pending"},
        {"$set": {
            "status":     "processing",
            "claimed_at": datetime.now(timezone.utc),
            "claimed_by": worker_id,
        }},
        return_document=ReturnDocument.AFTER,
        sort=[("uploaded_at", pymongo.ASCENDING)],
    )


def process_one(inputs, outputs, doc: dict, model, lookup, gen_client) -> None:
    """One input → one output. Marks input done on success, failed on error."""
    iid = doc["_id"]
    label = doc.get("persona_label", iid[:8])
    print(f"  ◀ claimed {label}", flush=True)
    stage = "scoring"
    try:
        features = features_from_doc(doc)
        raw_risk = predict_2yr_mortality(model, features)
        vitality = vitality_from_percentile(
            raw_risk, features["age"], features["sex_male"], lookup,
            mean_daily_mims=features.get("mean_daily_mims", 0.0),
        )
        print(f"    cox: raw={raw_risk*100:.3f}%  vitality={vitality:.1f} (percentile-based)", flush=True)

        stage = "recommending"
        prompt = build_user_prompt(features, raw_risk, vitality, hk_summary(doc))
        recommendation = call_gemini(gen_client, prompt)
        print(f"    gemini: {recommendation.summary[:80]}…", flush=True)

        out_doc = build_output_doc(doc, raw_risk, vitality, recommendation)
        outputs.insert_one(out_doc)
        inputs.update_one({"_id": iid}, {"$set": {"status": "done", "completed_at": out_doc["computed_at"]}})
        print(f"  ▶ wrote output _id={out_doc['_id'][:8]}…", flush=True)

    except Exception as e:
        print(f"  ✕ {stage} failed: {e}", flush=True)
        inputs.update_one(
            {"_id": iid},
            {"$set": {
                "status":          "failed",
                "failure_reason":  str(e)[:500],
                "failure_stage":   stage,
                "failed_at":       datetime.now(timezone.utc),
            }},
        )


# ── Main loop ────────────────────────────────────────────────────────────────

def drain(inputs, outputs, model, lookup, gen_client, worker_id: str) -> int:
    """Claim + process every pending input until none remain. Returns count."""
    n = 0
    while True:
        doc = claim_one(inputs, worker_id)
        if doc is None:
            break
        process_one(inputs, outputs, doc, model, lookup, gen_client)
        n += 1
    return n


def main() -> int:
    args = parse_args()

    api_key  = os.environ.get("GEMINI_API_KEY")
    uri      = os.environ.get("MONGODB_URI")
    db_name  = os.environ.get("MONGODB_DB", "almond")
    worker_id = args.worker_id or os.environ.get("WORKER_ID") or platform.node()

    missing = [n for n, v in (("GEMINI_API_KEY", api_key), ("MONGODB_URI", uri)) if not v]
    if missing:
        print(f"missing env: {', '.join(missing)} — set in inspect/.env", file=sys.stderr)
        return 1

    print(f"db:        {db_name}")
    print(f"worker_id: {worker_id}")
    print(f"mode:      {'once' if args.once else f'poll every {args.poll_interval}s'}\n")

    print("loading Cox model …")
    model, _means = load_cox()
    print(f"  {len(model.coef_)} coefficients")
    print("loading percentile lookup …")
    lookup = load_percentile_lookup()
    print(f"  {len(lookup)} (age × sex) buckets\n")

    print("connecting to Atlas …")
    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    db = client[db_name]
    inputs = db["input"]
    outputs = db["output"]
    print(f"  connected. input={inputs.count_documents({})} docs  output={outputs.count_documents({})} docs\n")

    print("initializing Gemini client …")
    gen_client = genai.Client(api_key=api_key)
    print(f"  model: {GEMINI_MODEL}\n")

    if args.once:
        n = drain(inputs, outputs, model, lookup, gen_client, worker_id)
        print(f"\ndone — processed {n} input(s).")
        print(f"final state: input={inputs.count_documents({})}  output={outputs.count_documents({})}  pending={inputs.count_documents({'status': 'pending'})}")
        return 0

    print("entering poll loop (Ctrl-C to stop) …\n")
    try:
        while True:
            n = drain(inputs, outputs, model, lookup, gen_client, worker_id)
            if n == 0:
                print(f"  (no pending; sleeping {args.poll_interval}s)", flush=True)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nstopped by user.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
