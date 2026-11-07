# covers: V1-A11
"""Straight-line candidate routes and routes.csv overrides (W1-D07)."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

from app.repositories.jobs import TrustedScope, create_queue_engine
from app.schemas.v1_enrichment import GeoLocation
from app.services.enrichment.api import list_routes
from app.services.enrichment.distance import (
    API_TO_DB,
    DB_TO_API,
    candidate_routes,
    haversine_miles,
    travel_days,
)
from tests.imports.test_import_postgres import FILES, _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

TALLAHASSEE = (Decimal("30.4383"), Decimal("-84.2807"))
GAINESVILLE = (Decimal("29.6516"), Decimal("-82.3248"))


def _geo(id, lat, lon, role="pantry"):
    return GeoLocation(id=id, latitude=Decimal(lat), longitude=Decimal(lon), role=role)


def test_haversine_hand_value():
    straight = haversine_miles(*TALLAHASSEE, *GAINESVILLE)
    assert Decimal(128) < straight < Decimal(132)  # about 130 miles
    [route] = candidate_routes([_geo("TLH", *TALLAHASSEE, role="hub"),
                                _geo("GNV", *GAINESVILLE)])
    assert (route.from_location_id, route.to_location_id) == ("TLH", "GNV")
    assert route.straight_miles == straight
    assert route.road_miles == (straight * Decimal("1.3")).quantize(Decimal("0.001"))
    assert Decimal(166) < route.road_miles < Decimal(172)  # about 169 road miles
    assert route.travel_days == 1


def test_travel_days_rounds_up_whole_days():
    assert travel_days(Decimal(0)) == 1  # a same-region transfer arrives the next day
    assert travel_days(Decimal(1080)) == 1  # exactly 24 h at 45 mph
    assert travel_days(Decimal("1080.001")) == 2


def test_k10_nearest_within_150_miles():
    receiver = _geo("R", "29.0", "-82.0")
    # 12 hubs north of the receiver, 0.1° apart (~6.9 mi); hub 11 is the farthest.
    hubs = [_geo(f"H{i:02d}", str(Decimal("29.1") + Decimal("0.1") * i), "-82.0", "hub")
            for i in range(12)]
    far = _geo("FAR", "32.0", "-82.0", "hub")  # ~207 straight miles: outside 150
    routes = candidate_routes([receiver, far, *hubs])
    assert [r.from_location_id for r in routes if r.to_location_id == "R"] == [
        f"H{i:02d}" for i in range(10)]
    assert all(r.straight_miles <= 150 for r in routes)


def test_hubs_and_dcs_never_receive():
    locations = [_geo("H", "29.0", "-82.0", "hub"), _geo("H2", "29.1", "-82.0", "hub"),
                 _geo("D", "29.2", "-82.0", "distribution_center"), _geo("P", "29.3", "-82.0")]
    routes = candidate_routes(locations)
    assert {r.to_location_id for r in routes} == {"P"}
    assert {r.from_location_id for r in routes} == {"H", "H2", "D"}


def test_method_label_straight_line_estimate():
    routes = candidate_routes([_geo("H", *TALLAHASSEE, role="hub"), _geo("P", *GAINESVILLE)])
    assert {r.method for r in routes} == {"straight_line_estimate"}


def test_route_method_maps_between_api_and_database():
    assert API_TO_DB == {"straight_line_estimate": "straight_line", "google_road": "google",
                         "routes_csv": "user"}
    assert DB_TO_API == {db: api for api, db in API_TO_DB.items()}


# --- PostgreSQL: routes stored at import, routes.csv overrides ---------------------------

SCHEMA = "w1_data_routes_test"
LOCATED = {**FILES, "locations": (
    "location_id,name,type,street,city,state,zip,latitude,longitude\n"
    "H1,North Hub,hub,301 S Monroe St,Tallahassee,FL,32301,30.4383,-84.2807\n"
    "P1,Pantry One,pantry,201 E University Ave,Gainesville,FL,32601,29.6516,-82.3248\n"
    "P2,Pantry Two,pantry,1 Main St,Lake City,FL,32055,30.1897,-82.6393\n")}


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


def _routes(engine, outcome):
    rt = SimpleNamespace(engine=engine)
    listed = list_routes(rt, TrustedScope(uuid.UUID(int=1), "local"), outcome.network_id)
    assert listed.dataset_version_id == outcome.dataset_version_id
    return {(r.from_location_id, r.to_location_id): r for r in listed.routes}


@pytest.mark.integration
def test_import_stores_straight_line_routes(engine, tmp_path):
    outcome = _import(engine, tmp_path, LOCATED)
    assert outcome.ok, outcome.errors
    routes = _routes(engine, outcome)
    assert set(routes) == {("H1", "P1"), ("H1", "P2"), ("P1", "P2"), ("P2", "P1")}
    hub_route = routes[("H1", "P1")]
    assert (hub_route.method, hub_route.travel_days, hub_route.override, hub_route.disabled,
            hub_route.fetched_at) == ("straight_line_estimate", 1, False, False, None)
    assert Decimal(166) < hub_route.road_miles < Decimal(172)
    with engine.connect() as conn:
        methods = conn.scalars(sa.text("SELECT DISTINCT method FROM net_routes WHERE "
                                       "dataset_version_id = :v"),
                               {"v": outcome.dataset_version_id}).all()
    assert methods == ["straight_line"]


@pytest.mark.integration
def test_routes_csv_overrides_computed_values(engine, tmp_path):
    csv = ("from_location_id,to_location_id,travel_days,cost_per_handling_unit\n"
           "H1,P1,3,\nH1,P2,,0.25\n")
    outcome = _import(engine, tmp_path, {**LOCATED, "routes": csv})
    assert outcome.ok, outcome.errors
    routes = _routes(engine, outcome)
    assert (routes[("H1", "P1")].method, routes[("H1", "P1")].travel_days,
            routes[("H1", "P1")].override) == ("routes_csv", 3, True)
    # A blank travel_days overrides nothing: the estimate and its label stay.
    assert (routes[("H1", "P2")].method, routes[("H1", "P2")].travel_days,
            routes[("H1", "P2")].override) == ("straight_line_estimate", 1, True)
    with engine.connect() as conn:
        cost = conn.scalar(sa.text(
            "SELECT r.cost_per_handling_unit FROM net_routes r JOIN net_locations t "
            "ON t.id = r.to_location_id WHERE r.dataset_version_id = :v AND t.external_id = "
            "'P2' AND r.is_override"), {"v": outcome.dataset_version_id})
    assert cost == Decimal("0.2500")


@pytest.mark.integration
def test_routes_csv_disabled_removes_route(engine, tmp_path):
    csv = "from_location_id,to_location_id,disabled\nP1,P2,true\n"
    outcome = _import(engine, tmp_path, {**LOCATED, "routes": csv})
    routes = _routes(engine, outcome)
    assert routes[("P1", "P2")].disabled and routes[("P1", "P2")].override
    assert not routes[("P2", "P1")].disabled


@pytest.mark.integration
def test_routes_csv_pair_without_days_or_coordinates_is_a_row_error(engine, tmp_path):
    csv = "from_location_id,to_location_id\nH1,P1\n"
    outcome = _import(engine, tmp_path, {**FILES, "routes": csv})  # no coordinates
    assert not outcome.ok
    [error] = outcome.errors
    assert (error.file, error.line, error.column, error.code) == (
        "routes", 2, "travel_days", "MALFORMED")
    assert "latitude" in error.fix


@pytest.mark.integration
def test_locations_without_coordinates_get_no_routes_yet(engine, tmp_path):
    outcome = _import(engine, tmp_path, FILES, as_of=date(2026, 11, 4))
    assert _routes(engine, outcome) == {}
