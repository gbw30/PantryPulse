# covers: V1-A10
"""Census batch geocoder client and the bundled ACS tract table (W1-D06)."""

import gzip
import json
import urllib.error
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.enrichment.census import (
    BUNDLED_ACS,
    Address,
    CensusClient,
    CensusUnavailable,
    default_acs,
    load_acs,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "census"
RECORDED = json.loads((FIXTURES / "geocode-batch-fl.json").read_text())


def _addresses() -> list[Address]:
    rows = [line.split(",") for line in RECORDED["request"]["addressFile"].splitlines()]
    return [Address(f"L{row[0]}", *row[1:]) for row in rows]


class Recorded:
    """Replays the S5 live response and keeps the request it was sent."""

    def __init__(self, body: str = RECORDED["response"]["body"]):
        self.body, self.requests = body, []

    def __call__(self, request) -> bytes:
        self.requests.append(request)
        return self.body.encode()


def test_batch_request_matches_the_recorded_call():
    transport = Recorded()
    CensusClient(transport).geocode(_addresses())
    [request] = transport.requests
    assert (request.get_method(), request.full_url) == ("POST", RECORDED["request"]["url"])
    body = request.data.decode()
    assert 'name="benchmark"\r\n\r\nPublic_AR_Current' in body
    assert 'name="vintage"\r\n\r\nCurrent_Current' in body
    # Row ids are positions, so any location ID (even one with a comma) is safe to send.
    assert RECORDED["request"]["addressFile"] in body.replace("\r\n", "\n")


def test_match_parses_longitude_first_and_full_tract_geoid():
    results = CensusClient(Recorded()).geocode(_addresses())
    tallahassee = results["L1"]
    assert (tallahassee.status, tallahassee.latitude, tallahassee.longitude,
            tallahassee.tract_geoid) == ("Exact", Decimal("30.439935"), Decimal("-84.280589"),
                                         "12073000200")


def test_non_exact_match_keeps_the_changed_address_for_review():
    result = CensusClient(Recorded()).geocode(_addresses())["L12"]
    assert result.status == "Non_Exact"
    assert result.matched_address == "100 N ANDREWS AVE, FORT LAUDERDALE, FL, 33301"
    assert result.tract_geoid == "12011042501"


def test_no_match_has_no_coordinates():
    result = CensusClient(Recorded()).geocode(_addresses())["L13"]
    assert (result.status, result.latitude, result.tract_geoid) == ("No_Match", None, None)


def test_html_error_page_is_an_outage():
    with pytest.raises(CensusUnavailable):
        CensusClient(Recorded("<html><body>an error occurred</body></html>")).geocode(
            _addresses())


def test_response_missing_a_row_is_an_outage():
    body = "\n".join(RECORDED["response"]["body"].splitlines()[1:])
    with pytest.raises(CensusUnavailable):
        CensusClient(Recorded(body)).geocode(_addresses())


def test_transport_error_is_an_outage():
    def down(request):
        raise urllib.error.URLError("connection refused")

    with pytest.raises(CensusUnavailable):
        CensusClient(down).geocode(_addresses())


def test_no_addresses_makes_no_call():
    transport = Recorded()
    assert CensusClient(transport).geocode([]) == {}
    assert transport.requests == []


def _acs(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "acs5-2024-tracts.csv.gz"
    path.write_bytes(gzip.compress(
        ("geoid,poverty_universe,poverty_below,snap_households,snap_received\n" + rows).encode()))
    path.with_suffix("").with_suffix(".json").write_text(json.dumps({
        "vintage": "2020-2024", "survey": "ACS 5-year", "tables": ["B17001", "B22003"],
        "generated_at": "2026-11-07T12:00:00Z", "rows": rows.count("\n")}))
    return path


def test_the_bundled_whole_us_table_loads_every_row():
    """CR-w1-data-1 option A: enrichment.v1 reads the lead's committed table, not a fixture."""
    table = default_acs()
    meta = json.loads(BUNDLED_ACS.with_suffix("").with_suffix(".json").read_text())
    assert table is not None and len(table.counts) == meta["rows"] > 80_000
    assert table.year == 2024
    poverty, snap = table.rates("12073000200")  # Leon County, FL
    assert poverty is not None and 0 <= poverty <= 1 and snap is not None and 0 <= snap <= 1
    assert table.source("12073000200") == "ACS 5-year 2024, tract 12073000200"


def test_acs_rates_from_counts(tmp_path):
    table = load_acs(_acs(tmp_path, "12073000200,4000,1000,1500,300\n"))
    assert table.year == 2024
    assert table.rates("12073000200") == (Decimal("0.25000"), Decimal("0.20000"))
    assert table.source("12073000200") == "ACS 5-year 2024, tract 12073000200"
    assert table.fetched_at.isoformat() == "2026-11-07T12:00:00+00:00"


def test_acs_unpublished_or_zero_universe_stays_unknown(tmp_path):
    table = load_acs(_acs(tmp_path, "12073000200,,,1500,300\n12011042501,0,0,0,0\n"))
    assert table.rates("12073000200") == (None, Decimal("0.20000"))
    assert table.rates("12011042501") == (None, None)
    assert table.rates("99999999999") == (None, None)  # tract not in the table


def _corrupt(row_id: str, replacement: str) -> str:
    """The recorded body with one row replaced, as a malformed Census answer."""
    return "\n".join(replacement if line.startswith(f'"{row_id}",') else line
                     for line in RECORDED["response"]["body"].splitlines())


@pytest.mark.parametrize("bad_row", [
    '"1","301 S Monroe St, Tallahassee, FL, 32301","Match","Exact"',  # short: no coordinates
    '"1","301 S Monroe St, Tallahassee, FL, 32301","Match"',  # 3 columns
    '"1","301 S Monroe St, Tallahassee, FL, 32301","Match","Exact","301 S MONROE ST","",'
    '"82850785","R","12","073","000200","3033"',  # empty coordinates
    '"1","301 S Monroe St, Tallahassee, FL, 32301","Match","Exact","301 S MONROE ST","x,y",'
    '"82850785","R","12","073","000200","3033"',  # garbled coordinates
    *(f'"1","301 S Monroe St, Tallahassee, FL, 32301","Match","Exact","301 S MONROE ST",'
      f'"-84.280588998653,30.439935478013","82850785","R",{tract},"3033"' for tract in (
          '"","",""',  # empty tract parts
          '"xy","073","000200"',  # garbled state
          '"12","73","000200"',  # county one digit short (geoid 10 digits)
          '"12","073","0002000"',  # tract one digit long (geoid 12 digits)
          '"1","0730","002000"',  # 11 digits, parts of the wrong length
          '"12","073","00020x"',  # garbled tract
          '"\u0661\u0662","073","000200"',  # Arabic-Indic digits: isdigit() but not ASCII
      )),
])
def test_malformed_match_row_is_unreadable_and_other_rows_are_unaffected(bad_row):
    """#9: a Match row Census could not have meant never crashes and never reads as success."""
    results = CensusClient(Recorded(_corrupt("1", bad_row))).geocode(_addresses())
    bad = results["L1"]
    assert (bad.status, bad.latitude, bad.longitude, bad.tract_geoid) == (
        "Unreadable", None, None, None)
    assert (results["L11"].status, results["L11"].tract_geoid) == ("Exact", "12073000200")
    assert results["L13"].status == "No_Match"
