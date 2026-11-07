"""Build the bundled ACS 5-year tract table (CR-w1-data-1, lead-built, Gabriel 2026-11-07).

Input: the Census Bureau's keyless table-based summary files for B17001 (poverty status)
and B22003 (SNAP receipt), pipe-delimited, one row per geography. Only census tracts
(summary level 140, GEO_ID "1400000US" + 11-digit GEOID) are kept.

Output, next to the enrichment services:
- acs5-2024-tracts.csv.gz: geoid,poverty_universe,poverty_below,snap_households,snap_received
  (raw estimates; an empty cell means unknown; a zero universe makes the rate unknown, never 0)
- acs5-2024-tracts.json: provenance (vintage, tables, source URLs, sha256, row count).

Usage: python scripts/build_acs_tracts.py <b17001.dat> <b22003.dat> [out_dir]
"""

import csv
import gzip
import hashlib
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/"
TRACT = "1400000US"
COLUMNS = ("geoid", "poverty_universe", "poverty_below", "snap_households", "snap_received")
TABLES = {"B17001": ("B17001_E001", "B17001_E002"), "B22003": ("B22003_E001", "B22003_E002")}
OUT = Path(__file__).resolve().parents[1] / "app/services/enrichment/data"


def _count(raw: str) -> str:
    """A non-negative integer estimate, or '' (unknown) for blanks and Census sentinels."""
    raw = raw.strip()
    return raw if raw.isdigit() else ""


def read_tracts(lines, fields: tuple[str, str]) -> dict[str, tuple[str, str]]:
    header = next(lines).rstrip("\n").split("|")
    at = [header.index(f) for f in fields]
    out = {}
    for line in lines:
        if line.startswith(TRACT):
            row = line.rstrip("\n").split("|")
            out[row[0][len(TRACT) :]] = tuple(_count(row[i]) if i < len(row) else "" for i in at)
    return out


def build(poverty: dict, snap: dict) -> bytes:
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(COLUMNS)
    for geoid in sorted(poverty.keys() | snap.keys()):
        writer.writerow((geoid, *poverty.get(geoid, ("", "")), *snap.get(geoid, ("", ""))))
    return gzip.compress(text.getvalue().encode(), mtime=0)  # mtime 0: reproducible bytes


def main(b17001: str, b22003: str, out_dir: str | None = None) -> None:
    out = Path(out_dir) if out_dir else OUT
    out.mkdir(parents=True, exist_ok=True)
    with open(b17001) as f:
        poverty = read_tracts(f, TABLES["B17001"])
    with open(b22003) as f:
        snap = read_tracts(f, TABLES["B22003"])
    data = build(poverty, snap)
    (out / "acs5-2024-tracts.csv.gz").write_bytes(data)
    meta = {
        "survey": "American Community Survey 5-year estimates",
        "vintage": "2020-2024",
        "geography": "census tract (2020 boundaries), all states, DC and Puerto Rico",
        "tables": {
            "B17001": "Poverty status in the past 12 months: E001 universe, E002 below poverty",
            "B22003": "Receipt of food stamps/SNAP: E001 households, E002 received SNAP",
        },
        "columns": list(COLUMNS),
        "unknown": "empty cell; a zero universe also means the rate is unknown",
        "source_urls": [f"{BASE}acsdt5y2024-{t.lower()}.dat" for t in TABLES],
        "rows": len(poverty.keys() | snap.keys()),
        "sha256": hashlib.sha256(data).hexdigest(),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "generator": "apps/api/scripts/build_acs_tracts.py",
    }
    (out / "acs5-2024-tracts.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"{meta['rows']} tracts, sha256 {meta['sha256']}")


if __name__ == "__main__":
    main(*sys.argv[1:])
