# covers: V1-A10
"""Geocoding and ACS enrichment stored on a dataset version (W1-D06).

The geocoder answers from the S5 live recording, replayed per address; the ACS table is a
tiny file in the CR-w1-data-1 format."""

import csv
import io
import json
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

from app.repositories.jobs import TrustedScope, create_queue_engine
from app.schemas.v1_enrichment import LocationAttributesUpdate
from app.services.enrichment.api import egp_blockers, set_location_attributes
from app.services.enrichment.census import CensusClient
from app.services.enrichment.service import run_enrichment
from app.services.presenter_access import AccessError
from tests.enrichment.test_census import _acs
from tests.imports.test_import_postgres import FILES, _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_enrich_test"
RECORDED = json.loads((Path(__file__).parents[1] / "fixtures" / "census" /
                       "geocode-batch-fl.json").read_text())
BY_STREET = {row[1].split(",")[0]: row for row in csv.reader(
    io.StringIO(RECORDED["response"]["body"])) if row}
TALLAHASSEE_TRACT, LAUDERDALE_TRACT = "12073000200", "12011042501"
GAINESVILLE_TRACT = "".join(BY_STREET["201 E University Ave"][8:11])
LOCATIONS = (
    "location_id,name,type,street,city,state,zip,latitude,longitude,poverty_rate,snap_rate\n"
    "H1,North Hub,hub,301 S Monroe St,Tallahassee,FL,32301,,,,\n"
    "P1,Pantry One,pantry,201 E University Ave,Gainesville,FL,32601,,,,\n"
    "P2,Pantry Two,pantry,1 Main St,Lake City,FL,32055,30.1897,-82.6393,,\n"
    "P3,Pantry Three,pantry,99999 Nonexistent Pantry Rd,Tallahassee,FL,32301,,,,\n"
    "P4,Pantry Four,pantry,100 S Andrews Ave,Fort Lauderdale,FL,33301,,,0.3,\n")


class Census:
    """Replays the recorded answer for each address sent, renumbered like the live service."""

    def __init__(self, down: bool = False):
        self.down, self.calls = down, []

    def __call__(self, request) -> bytes:
        if self.down:
            raise TimeoutError("timed out")
        sent = request.data.decode().split("filename=\"addresses.csv\"")[1]
        rows = list(csv.reader(io.StringIO(sent.split("\r\n\r\n", 1)[1].split("\r\n--")[0])))
        self.calls.append([row[1] for row in rows])
        out = io.StringIO()
        for row in rows:
            csv.writer(out).writerow([row[0], *BY_STREET[row[1]][1:]])
        return out.getvalue().encode()


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


@pytest.fixture(scope="module")
def acs(tmp_path_factory):
    from app.services.enrichment.census import load_acs

    return load_acs(_acs(tmp_path_factory.mktemp("acs"),
                         f"{TALLAHASSEE_TRACT},4000,1000,1500,300\n"
                         f"{GAINESVILLE_TRACT},2000,500,,\n"
                         f"{LAUDERDALE_TRACT},1000,100,500,50\n"))


@pytest.fixture
def network(engine, tmp_path):
    outcome = _import(engine, tmp_path, {**FILES, "locations": LOCATIONS})
    assert outcome.ok, outcome.errors
    return outcome


def _enrich(engine, network, acs, census):
    return run_enrichment(engine, network.dataset_version_id, CensusClient(census), acs)


def _location(engine, network, external_id):
    with engine.connect() as conn:
        return conn.execute(sa.text(
            "SELECT * FROM net_locations WHERE dataset_version_id = :v AND external_id = :e"),
            {"v": network.dataset_version_id, "e": external_id}).one()


def _attributes(engine, network):
    from app.services.enrichment.service import location_attributes

    with engine.connect() as conn:
        return {a.location_id: a for a in location_attributes(conn, network.dataset_version_id)}


SCOPE = TrustedScope(uuid.UUID(int=1), "local")


def _rt(engine):
    return SimpleNamespace(engine=engine)


def test_matched_address_stores_coordinates_tract_and_source(engine, network, acs):
    _enrich(engine, network, acs, Census())
    hub = _location(engine, network, "H1")
    assert (hub.latitude, hub.longitude, hub.coordinates_source, hub.tract_geoid) == (
        Decimal("30.439935"), Decimal("-84.280589"), "census_geocoder", TALLAHASSEE_TRACT)
    assert (hub.poverty_rate, hub.snap_rate, hub.acs_year) == (
        Decimal("0.25000"), Decimal("0.20000"), 2024)
    attributes = _attributes(engine, network)["H1"]
    assert (attributes.state, attributes.source, attributes.fetched_at) == (
        "known", f"ACS 5-year 2024, tract {TALLAHASSEE_TRACT}", acs.fetched_at)
    # An unpublished ACS count stays unknown, never 0.
    assert _attributes(engine, network)["P1"].snap_rate is None


def test_unmatched_address_listed_with_fix_hint(engine, network, acs):
    manifest = _enrich(engine, network, acs, Census())
    listed = {u["location_id"]: u for u in manifest["unmatched"]}
    assert set(listed) == {"P3", "P4"}
    assert listed["P3"]["address"] == "99999 Nonexistent Pantry Rd, Tallahassee, FL 32301"
    assert "latitude and longitude" in listed["P3"]["hint"]
    # A Non_Exact match is stored but listed for review with the address Census matched.
    assert "100 N ANDREWS AVE" in listed["P4"]["hint"]
    assert _location(engine, network, "P4").tract_geoid == LAUDERDALE_TRACT
    assert _location(engine, network, "P3").latitude is None
    assert manifest["last_error"] is None


def test_outage_marks_unknown_and_import_still_succeeds(engine, network, acs):
    manifest = _enrich(engine, network, acs, Census(down=True))
    assert manifest["last_error"].startswith("Census geocoder unavailable")
    assert manifest["unmatched"] == []
    hub = _location(engine, network, "H1")
    assert (hub.latitude, hub.tract_geoid, hub.poverty_rate) == (None, None, None)
    assert _attributes(engine, network)["H1"].state == "unknown"
    with engine.connect() as conn:  # the imported version is untouched
        assert conn.scalar(sa.text("SELECT count(*) FROM net_batches WHERE dataset_version_id "
                                   "= :v"), {"v": network.dataset_version_id}) == 3


def test_retry_fills_unknown_fields(engine, network, acs):
    _enrich(engine, network, acs, Census(down=True))
    census = Census()
    _enrich(engine, network, acs, census)
    assert _attributes(engine, network)["H1"].state == "known"
    _enrich(engine, network, acs, census)  # a later retry only sends what is still unknown
    assert census.calls[-1] == ["99999 Nonexistent Pantry Rd"]


def test_given_coordinates_skip_geocoding_call(engine, tmp_path, acs):
    rows = [line.split(",") for line in LOCATIONS.splitlines()]
    for row in rows[1:]:
        row[7:9] = row[7] or "29.0", row[8] or "-82.0"
    located = "\n".join(",".join(row) for row in rows) + "\n"
    outcome = _import(engine, tmp_path, {**FILES, "locations": located})
    census = Census()
    manifest = _enrich(engine, outcome, acs, census)
    assert census.calls == [] and manifest["unmatched"] == []
    census = Census()
    _enrich(engine, _import(engine, tmp_path / "b", {**FILES, "locations": LOCATIONS}), acs,
            census)
    assert "1 Main St" not in census.calls[0]  # P2 gave coordinates


def test_geocoded_locations_get_straight_line_routes(engine, network, acs):
    _enrich(engine, network, acs, Census())
    with engine.connect() as conn:
        pairs = set(conn.execute(sa.text(
            "SELECT f.external_id, t.external_id FROM net_routes r JOIN net_locations f ON "
            "f.id = r.from_location_id JOIN net_locations t ON t.id = r.to_location_id "
            "WHERE r.dataset_version_id = :v"), {"v": network.dataset_version_id}).all())
    assert {("H1", "P1"), ("P2", "P1"), ("H1", "P2")} <= pairs
    assert not any("P3" in pair for pair in pairs)  # still unlocated


def test_egp_blockers_list_unknown_until_manual_value_or_explicit_exclusion(
        engine, network, acs):
    _enrich(engine, network, acs, Census(down=True))
    rt, version = _rt(engine), network.dataset_version_id
    blockers = {b.location_id: b.missing for b in egp_blockers(rt, network.network_id, version)}
    # Hubs never receive, so they never block; P4's CSV poverty_rate is a manual value.
    assert blockers == {"P1": ("poverty_rate", "snap_rate"), "P2": ("poverty_rate", "snap_rate"),
                        "P3": ("poverty_rate", "snap_rate"), "P4": ("snap_rate",)}
    set_location_attributes(rt, SCOPE, network.network_id, "P1", LocationAttributesUpdate(
        poverty_rate=Decimal("0.2"), snap_rate=Decimal("0.1")))
    set_location_attributes(rt, SCOPE, network.network_id, "P2",
                            LocationAttributesUpdate(excluded=True))
    blockers = {b.location_id for b in egp_blockers(rt, network.network_id, version)}
    assert blockers == {"P3", "P4"}
    assert _attributes(engine, network)["P2"].state == "excluded"


def test_manual_override_labeled_manual(engine, network, acs):
    _enrich(engine, network, acs, Census())
    attributes = set_location_attributes(
        _rt(engine), SCOPE, network.network_id, "P1",
        LocationAttributesUpdate(poverty_rate=Decimal("0.4"), snap_rate=Decimal("0.3")))
    assert (attributes.state, attributes.source, attributes.fetched_at, attributes.poverty_rate,
            attributes.snap_rate) == ("manual", "manual", None, Decimal("0.4"), Decimal("0.3"))
    # The looked-up value is kept beside the manual one, not overwritten.
    assert _location(engine, network, "P1").poverty_rate == Decimal("0.25000")
    # A template value is a manual value too.
    assert _attributes(engine, network)["P4"].state == "manual"


def test_unknown_location_is_404(engine, network):
    with pytest.raises(AccessError) as error:
        set_location_attributes(_rt(engine), SCOPE, network.network_id, "NOPE",
                                LocationAttributesUpdate(excluded=True))
    assert (error.value.code, error.value.status) == ("LOCATION_NOT_FOUND", 404)


def test_attribute_and_route_endpoints(engine, network, acs):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    _enrich(engine, network, acs, Census())
    app = create_app()
    app.dependency_overrides[runtime] = lambda: _rt(engine)
    app.dependency_overrides[presenter] = lambda: SimpleNamespace(
        organization_id=uuid.UUID(int=1), actor="local", actor_ref="local")
    client = TestClient(app)
    base = f"/api/v1/networks/{network.network_id}"
    manual = client.put(f"{base}/locations/P3/attributes",
                        json={"poverty_rate": "0.2", "snap_rate": "0.1"})
    assert manual.status_code == 200, manual.text
    assert (manual.json()["state"], manual.json()["source"]) == ("manual", "manual")
    assert client.put(f"{base}/locations/P3/attributes",
                      json={"poverty_rate": "0.2"}).status_code == 422
    assert client.put(f"{base}/locations/NOPE/attributes",
                      json={"excluded": True}).status_code == 404
    routes = client.get(f"{base}/routes")
    assert routes.status_code == 200, routes.text
    assert {"straight_line_estimate"} == {r["method"] for r in routes.json()["routes"]}
    assert client.get(f"/api/v1/networks/{uuid.uuid4()}/routes").status_code == 404
