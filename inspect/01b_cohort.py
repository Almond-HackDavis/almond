"""Phase 1 · Step 1B — sentinel cleanup, valid-day filter, adult cohort.

Reads the XPT files downloaded by 01a_download.py, cleans the SAS numeric-
missing sentinel (~5.4e-79 → 0.0) on PAXDAY numerics, applies the Karas
2022 / Smirnova 2020 valid-day rule, drops subjects without BMI, drops
under-18s, and reports the survivors per cycle.

Filter rules (must all be true to keep a subject):
  - PAXSTS == 1                                    (reliable PAM monitor; PAXHD)
  - per-day: PAXWWMD ≥ 600 AND PAXQFD == 0         (≥10 h wake-wear, no flag)
  - subject has ≥4 valid days
  - age ≥ 18 (RIDAGEYR)
  - non-null BMXBMI

Persists the per-subject cohort to inspect/data/cohort_gh.csv and the
filtered PAXDAY to inspect/data/paxday_gh_valid.csv so 1C can read them
directly without re-running the filter chain.

Run:

    inspect/.venv/bin/python inspect/01b_cohort.py
"""
from __future__ import annotations

from importlib.machinery import SourceFileLoader
from pathlib import Path

import pandas as pd

# Reuse 1A's loaders + manifest without making this a package. The leading
# digit in 01a_download.py prevents a normal `import` so we hand-load it.
_a = SourceFileLoader(
    "a01", str(Path(__file__).resolve().parent / "01a_download.py")
).load_module()
CYCLES, DATA_DIR, load_xpt = _a.CYCLES, _a.DATA_DIR, _a.load_xpt


# ── Constants — Karas 2022 / Smirnova 2020 wear standard ─────────────────────

VALID_DAY_MIN_WAKE_WEAR = 600   # ≥10 h of wake-wear minutes
VALID_DAY_MIN_DAYS      = 4     # ≥4 valid days per subject
ADULT_MIN_AGE           = 18

# SAS numeric-missing sentinel ≈ 5.397605e-79. Anything strictly below this
# threshold is the sentinel (real PAM minute values are > 1e-3 in practice).
SAS_SENTINEL_THRESHOLD  = 1e-70

# PAXDAY numeric columns that need sentinel cleanup BEFORE any arithmetic.
PAXDAY_NUMERIC_COLS = (
    "PAXAISMD",  # daily MIMS sum (activity volume)
    "PAXWWMD",   # wake-wear minutes
    "PAXSWMD",   # sleep-wear minutes
    "PAXNWMD",   # non-wear minutes
    "PAXUMD",    # unknown minutes
    "PAXLXSD",   # log MIMS
    "PAXQFD",    # quality flag (0 = OK)
    "PAXMTSD",   # MIMS triaxial
)


# ── Cleanup + filter primitives ──────────────────────────────────────────────

def clean_sas_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Replace SAS numeric-missing sentinel with 0.0 in PAXDAY numerics."""
    out = df.copy()
    for col in PAXDAY_NUMERIC_COLS:
        if col in out.columns:
            mask = out[col].fillna(0) < SAS_SENTINEL_THRESHOLD
            out.loc[mask, col] = 0.0
    return out


def build_cohort_for_cycle(cycle) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """For one cycle: load PAM + DEMO + BMX, apply filters.

    Returns:
        cohort  — one row per surviving subject:
                  SEQN, cycle, age, sex_male, bmi, n_valid_days
        paxday  — sentinel-cleaned PAXDAY restricted to surviving subjects,
                  with a `valid_day` boolean column
        funnel  — counts at each filter step (for the verification table)
    """
    paxhd = load_xpt(DATA_DIR / f"PAXHD_{cycle.name}.xpt")
    paxday = load_xpt(DATA_DIR / f"PAXDAY_{cycle.name}.xpt")
    demo = load_xpt(DATA_DIR / f"DEMO_{cycle.name}.xpt")
    bmx = load_xpt(DATA_DIR / f"BMX_{cycle.name}.xpt")

    n_paxhd_total = len(paxhd)

    # 1. Reliable monitor: PAXSTS == 1
    reliable = set(paxhd.loc[paxhd["PAXSTS"] == 1, "SEQN"].astype("int64"))
    n_reliable = len(reliable)

    # 2. Sentinel cleanup, restrict to reliable, mark valid days
    paxday = clean_sas_sentinels(paxday)
    paxday = paxday[paxday["SEQN"].isin(reliable)].copy()
    paxday["valid_day"] = (
        (paxday["PAXWWMD"] >= VALID_DAY_MIN_WAKE_WEAR)
        & (paxday["PAXQFD"] == 0)
    )

    # 3. ≥4 valid days per subject
    valid_days = (
        paxday.groupby("SEQN")["valid_day"].sum()
        .rename("n_valid_days").reset_index()
    )
    enough_days = valid_days[valid_days["n_valid_days"] >= VALID_DAY_MIN_DAYS]
    n_enough_days = len(enough_days)

    # 4. Demographics + adult filter
    demo_slim = demo[["SEQN", "RIDAGEYR", "RIAGENDR"]].copy()
    demo_slim["age"] = demo_slim["RIDAGEYR"].astype(float)
    demo_slim["sex_male"] = (demo_slim["RIAGENDR"] == 1).astype(int)
    adults = demo_slim[demo_slim["age"] >= ADULT_MIN_AGE][["SEQN", "age", "sex_male"]]

    # 5. BMI required (BMXBMI non-null)
    bmx_slim = bmx[["SEQN", "BMXBMI"]].rename(columns={"BMXBMI": "bmi"}).dropna(subset=["bmi"])

    cohort = (
        enough_days
        .merge(adults, on="SEQN")
        .merge(bmx_slim, on="SEQN")
    )
    cohort.insert(1, "cycle", cycle.name)
    cohort = cohort[["SEQN", "cycle", "age", "sex_male", "bmi", "n_valid_days"]]

    funnel = {
        "cycle":             cycle.name,
        "paxhd_total":       int(n_paxhd_total),
        "reliable_monitor":  int(n_reliable),
        "≥4_valid_days":     int(n_enough_days),
        "+adult_+bmi":       int(len(cohort)),
    }

    # Restrict the returned PAXDAY to subjects who survived all filters,
    # so 1C can use it directly without re-applying anything.
    paxday_kept = paxday[paxday["SEQN"].isin(set(cohort["SEQN"]))].copy()
    return cohort, paxday_kept, funnel


def main() -> None:
    cohorts: list[pd.DataFrame] = []
    paxdays: list[pd.DataFrame] = []
    funnels: list[dict] = []

    for cycle in CYCLES:
        cohort, paxday, funnel = build_cohort_for_cycle(cycle)
        cohorts.append(cohort)
        paxday["cycle"] = cycle.name
        paxdays.append(paxday)
        funnels.append(funnel)

    pooled_cohort = pd.concat(cohorts, ignore_index=True)
    pooled_paxday = pd.concat(paxdays, ignore_index=True)

    # Persist for 1C inspectability — small enough for CSV, no extra deps.
    cohort_path = DATA_DIR / "cohort_gh.csv"
    paxday_path = DATA_DIR / "paxday_gh_valid.csv"
    pooled_cohort.to_csv(cohort_path, index=False)
    pooled_paxday.to_csv(paxday_path, index=False)

    print("─── 1B funnel (per cycle) ──────────────────────────────────────")
    print(pd.DataFrame(funnels).to_string(index=False))
    print()
    print("─── 1B cohort summary (pooled) ─────────────────────────────────")
    print(f"final cohort size:        {len(pooled_cohort):>6}")
    print(f"valid PAXDAY rows kept:   {int(pooled_paxday['valid_day'].sum()):>6}")
    print(f"median age:               {pooled_cohort['age'].median():>6.1f}")
    print(f"% male:                   {pooled_cohort['sex_male'].mean() * 100:>6.1f}")
    print(f"median BMI:               {pooled_cohort['bmi'].median():>6.1f}")
    print(f"median valid days/subj:   {pooled_cohort['n_valid_days'].median():>6.0f}")
    print()
    print(f"wrote: {cohort_path.relative_to(DATA_DIR.parent)}")
    print(f"wrote: {paxday_path.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
