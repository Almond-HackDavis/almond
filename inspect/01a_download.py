"""Phase 1 · Step 1A — NHANES G + H download + load.

Pulls the 12 NHANES XPT files (DEMO, BMX, PAXHD, PAXDAY × cycles G + H) and
the 2 NCHS Public-Use Linked Mortality .dat files needed for the 24-month
all-cause mortality Cox model. Downloads are idempotent and atomic
(skips files already on disk; writes to .part then renames so a Ctrl-C
mid-download never leaves a half-written XPT in place).

Verification at the bottom: prints a summary table covering every file's
row/column counts, unique SEQN counts, mortality eligibility + death totals.

Run:

    inspect/.venv/bin/python inspect/01a_download.py

(or activate the venv first and run plain `python inspect/01a_download.py`).

Deps: pandas, requests — both already present in inspect/.venv from the
existing inspection notebook. No version pins; uses whatever you have.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

# ── Paths ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "data"

NHANES_URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}.xpt"
MORTALITY_URL = (
    "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/"
    "linked_mortality/NHANES_{cycle}_MORT_2019_PUBLIC.dat"
)


# ── Manifest ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Cycle:
    name: str           # 'G' or 'H'
    start_year: int     # 2011 or 2013 — URL path uses cycle-start year
    mort_cycle: str     # '2011_2012' or '2013_2014' — mortality URL pairs them

    @property
    def xpt_codes(self) -> list[str]:
        return [f"DEMO_{self.name}", f"BMX_{self.name}",
                f"PAXHD_{self.name}", f"PAXDAY_{self.name}"]

    @property
    def mortality_filename(self) -> str:
        return f"NHANES_{self.mort_cycle}_MORT_2019_PUBLIC.dat"


CYCLES: tuple[Cycle, ...] = (
    Cycle(name="G", start_year=2011, mort_cycle="2011_2012"),
    Cycle(name="H", start_year=2013, mort_cycle="2013_2014"),
)


# ── Download ─────────────────────────────────────────────────────────────────

def download(url: str, dest: Path, *, chunk_size: int = 1 << 16) -> Path:
    """Idempotent + atomic download. Skips if file already exists with size > 0."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {dest.name} …", end="", flush=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if "html" in ctype:
            raise RuntimeError(
                f"Got HTML from {url} — CDC sometimes serves 404s as a page; "
                f"check the URL pattern."
            )
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    tmp.rename(dest)
    print(f" {dest.stat().st_size / 1024:.1f} KB")
    return dest


def download_all(data_dir: Path) -> dict[str, Path]:
    """Download every XPT + mortality file across both cycles."""
    paths: dict[str, Path] = {}
    for cycle in CYCLES:
        print(f"cycle {cycle.name} ({cycle.start_year}-{cycle.start_year + 1})")
        for code in cycle.xpt_codes:
            url = NHANES_URL.format(year=cycle.start_year, name=code)
            paths[f"{code}.xpt"] = download(url, data_dir / f"{code}.xpt")
        mort_url = MORTALITY_URL.format(cycle=cycle.mort_cycle)
        paths[cycle.mortality_filename] = download(mort_url, data_dir / cycle.mortality_filename)
    return paths


# ── Load ─────────────────────────────────────────────────────────────────────

def load_xpt(path: Path) -> pd.DataFrame:
    """Read an NHANES XPT (SAS-XPORT) file into a DataFrame with int64 SEQN."""
    df = pd.read_sas(path, format="xport", encoding="utf-8")
    if "SEQN" in df.columns:
        df["SEQN"] = df["SEQN"].astype("int64")
    return df


# Fixed-width column layout for NCHS Public-Use Linked Mortality files (2019).
# Positions are 1-indexed inclusive per NCHS readme; converted to 0-indexed
# half-open below. Field meanings:
#   SEQN          — NHANES respondent id
#   ELIGSTAT      — 1=eligible for linkage, 2=under-18 ineligible, 3=ineligible
#   MORTSTAT      — 0=assumed alive, 1=assumed deceased
#   UCOD_LEADING  — 3-digit leading underlying cause-of-death recode
#   DIABETES      — diabetes flag on death certificate
#   HYPERTEN      — hypertension flag on death certificate
#   PERMTH_INT    — months from interview to death/censoring
#   PERMTH_EXM    — months from MEC exam to death/censoring (use this one for
#                   accelerometry: PAX device was issued at the MEC exam, so
#                   PERMTH_EXM avoids immortal-time bias)
MORT_LAYOUT: tuple[tuple[str, int, int, str], ...] = (
    ("SEQN",         1,  6,  "Int64"),
    ("ELIGSTAT",    15, 15,  "Int64"),
    ("MORTSTAT",    16, 16,  "Int64"),
    ("UCOD_LEADING",17, 19,  "string"),
    ("DIABETES",    20, 20,  "Int64"),
    ("HYPERTEN",    21, 21,  "Int64"),
    ("PERMTH_INT",  43, 45,  "Int64"),
    ("PERMTH_EXM",  46, 48,  "Int64"),
)


def load_mortality(path: Path) -> pd.DataFrame:
    """Read a NHANES_{cycle}_MORT_2019_PUBLIC.dat fixed-width file."""
    names    = [c[0] for c in MORT_LAYOUT]
    colspecs = [(c[1] - 1, c[2]) for c in MORT_LAYOUT]
    df = pd.read_fwf(path, colspecs=colspecs, names=names, dtype=str, na_values=["", "."])
    for col, _s, _e, dtype in MORT_LAYOUT:
        if dtype == "Int64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        else:
            df[col] = df[col].astype("string").str.strip()
    return df


# ── Verification ─────────────────────────────────────────────────────────────

def summarize(paths: dict[str, Path]) -> pd.DataFrame:
    """Build the verification table — one row per downloaded file."""
    rows = []
    for cycle in CYCLES:
        for code in cycle.xpt_codes:
            p = paths[f"{code}.xpt"]
            df = load_xpt(p)
            rows.append({
                "cycle": cycle.name,
                "kind":  "xpt",
                "file":  p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "rows":  len(df),
                "cols":  df.shape[1],
                "unique_seqn": df["SEQN"].nunique() if "SEQN" in df.columns else None,
                "eligible":     None,
                "deaths_total": None,
                "deaths_24mo":  None,
            })
        mp = paths[cycle.mortality_filename]
        m = load_mortality(mp)
        elig_mask  = m["ELIGSTAT"] == 1
        death_mask = elig_mask & (m["MORTSTAT"] == 1)
        in_window  = death_mask & (m["PERMTH_EXM"] <= 24)
        rows.append({
            "cycle": cycle.name,
            "kind":  "mortality",
            "file":  mp.name,
            "size_kb": round(mp.stat().st_size / 1024, 1),
            "rows":  len(m),
            "cols":  m.shape[1],
            "unique_seqn":  m["SEQN"].nunique(),
            "eligible":     int(elig_mask.sum()),
            "deaths_total": int(death_mask.sum()),
            "deaths_24mo":  int(in_window.sum()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    print(f"data dir: {DATA_DIR}")
    print()
    paths = download_all(DATA_DIR)
    print()
    print("─── 1A verification ────────────────────────────────────────────────")
    summary = summarize(paths)
    pd.set_option("display.max_columns", 14)
    pd.set_option("display.width", 160)
    print(summary.to_string(index=False))
    print()
    total_bytes = sum(p.stat().st_size for p in paths.values())
    print(f"total files on disk: {len(paths)} (expected 14 = 12 XPT + 2 .dat)")
    print(f"total size:          {total_bytes / (1024 * 1024):.1f} MB")


if __name__ == "__main__":
    main()
