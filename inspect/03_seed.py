"""Phase 3 setup — wipe the Atlas `almond` DB and seed synthetic input docs.

Architecture (current, simplified):

    iOS engineer  ─writes→  input collection   (Atlas)
                                  │
                                  ▼
                          04_worker.py reads pending inputs
                                  │
                                  ▼
                          runs Cox + Gemini
                                  │
                                  ▼
                          writes to output collection (Atlas)
                                  │
                                  ▼
    iOS engineer  ←reads─  output collection  (Atlas)

Two collections only: `input` and `output`. No FastAPI backend in this loop —
iOS hits Mongo directly, our worker hits Mongo directly.

This script:
  1. Connects to Atlas (URI from inspect/.env).
  2. Drops every existing collection in the `almond` DB.
  3. Inserts 3 synthetic input docs covering different personas:
       - Persona A: healthy active 32-yo male  (expect Vitality ~99.5+)
       - Persona B: sedentary 65-yo female      (expect noticeably lower)
       - Persona C: very active 45-yo male      (expect high)
  4. Creates an index on input.status for the worker's poll query.

Run:

    inspect/.venv/bin/python inspect/03_seed.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pymongo
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


# ── Synthetic personas (plain dicts — Mongo-friendly, no schema gymnastics) ──

PERSONAS: list[dict[str, Any]] = [
    {
        "label": "A · healthy active 32-yo male",
        "onboarding": {
            "age": 32, "sex": "M", "height_cm": 178, "weight_kg": 75,
            "smoking": False, "diabetes": False, "family_history_cvd": False,
            "race_ethnicity": "white",
            "systolic_bp": 118, "total_cholesterol": 175, "hdl_cholesterol": 58,
            "on_bp_medication": False,
        },
        "activity": {"steps_mean": 9_000, "steps_sd": 1_500,
                     "kcal_mean": 450, "kcal_sd": 80,
                     "exercise_mean": 30, "exercise_sd": 10,
                     "sleep_mean": 430, "sleep_sd": 30},
    },
    {
        "label": "B · sedentary 65-yo female",
        "onboarding": {
            "age": 65, "sex": "F", "height_cm": 162, "weight_kg": 78,
            "smoking": False, "diabetes": True, "family_history_cvd": True,
            "race_ethnicity": "white",
            "systolic_bp": 145, "total_cholesterol": 215, "hdl_cholesterol": 42,
            "on_bp_medication": True,
        },
        "activity": {"steps_mean": 3_500, "steps_sd": 800,
                     "kcal_mean": 150, "kcal_sd": 40,
                     "exercise_mean": 5,  "exercise_sd": 5,
                     "sleep_mean": 390, "sleep_sd": 80},   # high SD = irregular
    },
    {
        "label": "C · very active 45-yo male",
        "onboarding": {
            "age": 45, "sex": "M", "height_cm": 180, "weight_kg": 80,
            "smoking": False, "diabetes": False, "family_history_cvd": False,
            "race_ethnicity": "asian",
            "systolic_bp": 122, "total_cholesterol": 185, "hdl_cholesterol": 60,
            "on_bp_medication": False,
        },
        "activity": {"steps_mean": 11_000, "steps_sd": 2_000,
                     "kcal_mean": 550, "kcal_sd": 100,
                     "exercise_mean": 45, "exercise_sd": 15,
                     "sleep_mean": 440, "sleep_sd": 25},
    },
]


# ── Synthetic samples builder (90-day window) ────────────────────────────────

def build_samples(activity: dict, seed: int, days: int = 90) -> dict:
    """Generate 90 daily HK-shape arrays + 90 sleep sessions."""
    rng = np.random.default_rng(seed=seed)
    end = datetime.now(timezone.utc).date()
    dates = [(end - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]

    steps = rng.normal(activity["steps_mean"], activity["steps_sd"], days).clip(0).astype(int)
    kcal  = rng.normal(activity["kcal_mean"],  activity["kcal_sd"],  days).clip(0)
    excm  = rng.normal(activity["exercise_mean"], activity["exercise_sd"], days).clip(0)
    sleep_dur = rng.normal(activity["sleep_mean"], activity["sleep_sd"], days).clip(180)

    sleep_sessions = []
    for d, dur in zip(dates, sleep_dur):
        # Bedtime around 23:30 with ±1h jitter; end = start + duration.
        bedtime = datetime.fromisoformat(d).replace(
            hour=23, minute=30, tzinfo=timezone.utc
        ) + timedelta(minutes=int(rng.normal(0, 60)))
        wake = bedtime + timedelta(minutes=float(dur))
        sleep_sessions.append({
            "start": bedtime.isoformat(),
            "end":   wake.isoformat(),
            "duration_min": float(dur),
        })

    return {
        "steps_daily":              [{"date": d, "count": int(s)}     for d, s in zip(dates, steps)],
        "active_energy_daily_kcal": [{"date": d, "kcal":  float(k)}   for d, k in zip(dates, kcal)],
        "exercise_minutes_daily":   [{"date": d, "minutes": float(m)} for d, m in zip(dates, excm)],
        "sleep_sessions":           sleep_sessions,
    }


# ── Build one input doc per persona ──────────────────────────────────────────

def build_input_doc(persona: dict, seed: int) -> dict:
    now = datetime.now(timezone.utc)
    user_id = str(uuid4())
    return {
        "_id":           str(uuid4()),
        "user_id":       user_id,
        "persona_label": persona["label"],          # for human inspection only
        "uploaded_at":   now,
        "window_start":  now - timedelta(days=90),
        "window_end":    now,
        "status":        "pending",                 # pending | processing | done | failed
        "claimed_at":    None,
        "claimed_by":    None,
        "onboarding":    persona["onboarding"],
        "samples":       build_samples(persona["activity"], seed=seed),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "almond")
    if not uri:
        print("missing MONGODB_URI in inspect/.env", file=sys.stderr)
        return 1

    print(f"connecting to Atlas …")
    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    print(f"  connected. db={db_name}")

    db = client[db_name]
    existing = db.list_collection_names()
    print(f"  existing collections: {existing or '[none]'}")

    if existing:
        print("dropping all existing collections …")
        for name in existing:
            db.drop_collection(name)
            print(f"  dropped {name}")

    inputs = db["input"]
    outputs = db["output"]

    # Index for the worker's poll query.
    inputs.create_index([("status", pymongo.ASCENDING), ("uploaded_at", pymongo.ASCENDING)],
                        name="ix_status_uploaded")
    outputs.create_index([("input_id", pymongo.ASCENDING)], unique=True, name="ux_input_id")
    print(f"  created indexes")

    print(f"\nseeding {len(PERSONAS)} synthetic input docs …")
    docs = [build_input_doc(p, seed=10 + i) for i, p in enumerate(PERSONAS)]
    inputs.insert_many(docs)
    for d in docs:
        print(f"  ✓ {d['persona_label']}  _id={d['_id'][:8]}…  user_id={d['user_id'][:8]}…")

    print()
    print("─── seed summary ───────────────────────────────")
    print(f"  collections in {db_name}: {db.list_collection_names()}")
    print(f"  input.status=pending count:  {inputs.count_documents({'status': 'pending'})}")
    print(f"  output count:                {outputs.count_documents({})}")
    print(f"\nnext: run `inspect/.venv/bin/python inspect/04_worker.py --once`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
