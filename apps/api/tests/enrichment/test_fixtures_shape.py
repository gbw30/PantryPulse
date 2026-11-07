# covers: V1-A10, V1-A11
"""Recorded provider fixtures keep the shape the enrichment clients parse (W1-D01)."""

import csv
import io
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(relative: str) -> dict:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


def test_census_geocode_fixture_has_tract():
    recorded = _load("census/geocode-batch-fl.json")
    assert recorded["recorded"]["kind"] == "live_response"
    rows = list(csv.reader(io.StringIO(recorded["response"]["body"])))
    matched = [row for row in rows if len(row) >= 12 and row[2] == "Match"]
    assert len(matched) >= 8, "the spike geocodes about 10 public buildings"
    for row in matched:
        lon, lat = (float(v) for v in row[5].split(","))
        assert 24 < lat < 31.1 and -87.7 < lon < -79.9  # Florida
        state, county, tract = row[8], row[9], row[10]
        assert state == "12" and len(county) == 3 and len(tract) == 6


def test_census_geocode_fixture_lists_unmatched_address():
    recorded = _load("census/geocode-batch-fl.json")
    rows = list(csv.reader(io.StringIO(recorded["response"]["body"])))
    assert ["13", "99999 Nonexistent Pantry Rd, Tallahassee, FL, 32301", "No_Match"] in rows


# test_acs_fixture_has_poverty_and_snap (wave-1 W1-D01) is blocked by CR-w1-data-1: the
# Census Data API now refuses keyless requests, so no poverty/SNAP response can be recorded
# without a key. This test pins the recorded refusal the ACS client must report as unknown.
def test_acs_keyless_request_redirects_to_missing_key():
    recorded = _load("census/acs-missing-key.json")
    assert recorded["recorded"]["kind"] == "live_response"
    assert recorded["response"]["status"] == 302
    assert recorded["response"]["location"].endswith("/data/missing_key.html")


def test_google_fixture_is_documented_example_not_live():
    recorded = _load("google/route-matrix-documented.json")
    assert recorded["recorded"]["kind"] == "documented_example"
    elements = json.loads(recorded["response"]["body"])
    assert {"originIndex", "destinationIndex", "status", "condition"} <= set(elements[0])
    assert any(e.get("condition") == "ROUTE_EXISTS" and e["duration"].endswith("s")
               for e in elements)
