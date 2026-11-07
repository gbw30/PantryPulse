# covers: V1-A11
"""Bring-your-own Google key: settings, lookup preview, Routes API client, cache (W1-D08).

No Google API is called: the transport answers in the documented computeRouteMatrix shape
(S6), recorded in tests/fixtures/google/route-matrix-documented.json."""

import io
import json
import logging
import urllib.error
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from pydantic import SecretStr

from app.repositories.jobs import TrustedScope, create_queue_engine
from app.services.enrichment import settings
from app.services.enrichment.api import list_routes
from app.services.enrichment.google import (
    GoogleClient,
    GoogleUnavailable,
    apply_google,
    fetch_routes,
    google_input,
    google_step,
    preview_lookups,
)
from app.services.presenter_access import AccessError
from tests.enrichment.test_distance import LOCATED
from tests.imports.test_import_postgres import _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

SCHEMA = "w1_data_google_test"
KEY = "AIzaTEST-not-a-real-key-0123456789"
SCOPE = TrustedScope(uuid.UUID(int=1), "local")
NOW = datetime(2026, 11, 7, 18, 0, tzinfo=UTC)
DOCUMENTED = json.loads((Path(__file__).parents[1] / "fixtures" / "google" /
                         "route-matrix-documented.json").read_text())


class Routes:
    """Answers like computeRouteMatrix: one element per origin, out of order."""

    def __init__(self, error: Exception | None = None):
        self.error, self.requests = error, []

    def __call__(self, request) -> bytes:
        self.requests.append(request)
        if self.error:
            raise self.error
        body = json.loads(request.data)
        return json.dumps([
            {"originIndex": i, "destinationIndex": 0, "status": {},
             "distanceMeters": 100_000 + i, "duration": "5400s", "condition": "ROUTE_EXISTS"}
            for i in reversed(range(len(body["origins"])))]).encode()


def _http_error():
    return urllib.error.HTTPError(
        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix", 403,
        f"API key {KEY} not valid", {}, io.BytesIO(json.dumps(
            {"error": {"code": 403, "message": f"API key {KEY} invalid"}}).encode()))


# --- pure: the client -------------------------------------------------------------------

def test_client_sends_the_s6_request_and_maps_indexes():
    transport = Routes()
    found = GoogleClient(KEY, transport).distances(
        [(Decimal("30.4383"), Decimal("-84.2807")), (Decimal("30.1897"), Decimal("-82.6393"))],
        (Decimal("29.6516"), Decimal("-82.3248")))
    assert found == [(100_000, 5400), (100_001, 5400)]
    [request] = transport.requests
    assert request.full_url == DOCUMENTED["request"]["url"]
    assert request.get_header("X-goog-api-key") == KEY
    assert set(request.get_header("X-goog-fieldmask").split(",")) == {
        "originIndex", "destinationIndex", "status", "condition", "distanceMeters", "duration"}
    body = json.loads(request.data)
    assert (body["travelMode"], body["routingPreference"]) == ("DRIVE", "TRAFFIC_UNAWARE")
    assert body["destinations"] == [{"waypoint": {"location": {"latLng": {
        "latitude": 29.6516, "longitude": -82.3248}}}}]


def test_client_reads_the_documented_example():
    body = DOCUMENTED["response"]["body"].encode()  # elements out of order, 2 × 2
    assert GoogleClient.parse(body, origins=2, destination=0) == [(822, 160), (2919, 361)]
    assert GoogleClient.parse(body, origins=2, destination=1) == [(7259, 712), (5598, 402)]


def test_route_not_found_keeps_no_distance():
    body = json.dumps([{"originIndex": 0, "destinationIndex": 0, "status": {},
                        "condition": "ROUTE_NOT_FOUND"}]).encode()
    assert GoogleClient(KEY, lambda r: body).distances(
        [(Decimal(30), Decimal(-84))], (Decimal(29), Decimal(-82))) == [None]


@pytest.mark.integration
def test_no_google_call_without_key(engine, network):
    transport = Routes()
    with pytest.raises(GoogleUnavailable):
        GoogleClient("", transport)
    with pytest.raises(AccessError) as error:  # no key saved: nothing is submitted
        fetch_routes(_rt(engine), SCOPE, network.network_id, str(uuid.uuid4()))
    assert (error.value.code, error.value.status) == ("GOOGLE_KEY_MISSING", 409)
    assert transport.requests == []


@pytest.mark.integration
def test_key_never_in_logs_responses_or_errors(engine, network, caplog):
    caplog.set_level(logging.DEBUG)
    rt = _rt(engine)
    assert settings.set_google_key(rt, SecretStr(KEY)).google_maps_configured
    try:
        assert KEY not in settings.get_settings(rt).model_dump_json()
        with pytest.raises(GoogleUnavailable) as error:
            GoogleClient(KEY, Routes(_http_error())).distances(
                [(Decimal(30), Decimal(-84))], (Decimal(29), Decimal(-82)))
        assert KEY not in str(error.value) and KEY not in repr(error.value)
        with engine.connect() as conn:
            payload = google_input(conn, network.dataset_version_id)
        output = google_step(payload, GoogleClient(KEY, Routes(_http_error())))
        assert output["error"] == "GOOGLE_HTTP_403"
        assert KEY not in json.dumps(output) and KEY not in json.dumps(payload)
        assert KEY not in caplog.text
    finally:
        assert not settings.delete_google_key(rt).google_maps_configured


# --- PostgreSQL: preview, cache, labels ------------------------------------------------

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


@pytest.fixture
def network(engine, tmp_path):
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM google_distance_cache"))
    outcome = _import(engine, tmp_path, LOCATED)
    assert outcome.ok, outcome.errors
    return outcome


def _rt(engine):
    return SimpleNamespace(engine=engine)


def _fetch(engine, network, transport):
    with engine.connect() as conn:
        payload = google_input(conn, network.dataset_version_id)
    step = google_step(payload, GoogleClient(KEY, transport))
    with engine.begin() as conn:
        apply_google(conn, network.dataset_version_id, step, NOW)
    return step


def _routes(engine, network):
    return {(r.from_location_id, r.to_location_id): r
            for r in list_routes(_rt(engine), SCOPE, network.network_id).routes}


@pytest.mark.integration
def test_preview_counts_only_uncached_routes(engine, network):
    preview = preview_lookups(_rt(engine), SCOPE, network.network_id)
    assert (preview.lookups, preview.cached) == (4, 0)  # H1→P1, H1→P2, P1→P2, P2→P1
    with engine.begin() as conn:  # one pair already looked up (by any network)
        conn.execute(sa.text(
            "INSERT INTO google_distance_cache VALUES (30.4383, -84.2807, 29.6516, -82.3248, "
            "270000, 10800, :at)"), {"at": NOW})
    preview = preview_lookups(_rt(engine), SCOPE, network.network_id)
    assert (preview.lookups, preview.cached) == (3, 1)


@pytest.mark.integration
def test_results_cached_and_labeled_google_road_with_fetch_date(engine, network):
    transport = Routes()
    _fetch(engine, network, transport)
    assert len(transport.requests) == 2  # one request per receiver (S6 billing)
    route = _routes(engine, network)[("H1", "P1")]
    assert (route.method, route.fetched_at, route.travel_days) == ("google_road", NOW, 1)
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM google_distance_cache")) == 4
        meters = conn.scalar(sa.text(
            "SELECT distance_meters FROM google_distance_cache WHERE origin_lat = 30.4383 "
            "AND dest_lat = 29.6516"))
    assert route.road_miles == (Decimal(meters) / Decimal("1609.344")).quantize(Decimal("0.001"))
    preview = preview_lookups(_rt(engine), SCOPE, network.network_id)
    assert (preview.lookups, preview.cached) == (0, 4)
    again = Routes()
    _fetch(engine, network, again)
    assert again.requests == []  # everything cached: nothing billed


@pytest.mark.integration
def test_routes_csv_still_overrides_google(engine, tmp_path):
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM google_distance_cache"))
    csv = "from_location_id,to_location_id,travel_days\nH1,P1,3\n"
    outcome = _import(engine, tmp_path, {**LOCATED, "routes": csv})
    assert preview_lookups(_rt(engine), SCOPE, outcome.network_id).lookups == 3
    _fetch(engine, outcome, Routes())
    routes = _routes(engine, outcome)
    assert (routes[("H1", "P1")].method, routes[("H1", "P1")].travel_days) == ("routes_csv", 3)
    assert routes[("H1", "P2")].method == "google_road"


@pytest.mark.integration
def test_provider_error_keeps_straight_line_routes(engine, network):
    step = _fetch(engine, network, Routes(urllib.error.URLError("timed out")))
    assert step["error"] == "GOOGLE_UNAVAILABLE"
    assert {r.method for r in _routes(engine, network).values()} == {"straight_line_estimate"}
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM google_distance_cache")) == 0


@pytest.mark.integration
def test_settings_and_google_routes_over_http(engine, network):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    app = create_app()
    app.dependency_overrides[runtime] = lambda: _rt(engine)
    app.dependency_overrides[presenter] = lambda: SimpleNamespace(
        organization_id=uuid.UUID(int=1), actor="local", actor_ref="local")
    client = TestClient(app)
    base = f"/api/v1/networks/{network.network_id}/routes"
    assert client.get("/api/v1/settings").json() == {"google_maps_configured": False}
    fetch = client.post(f"{base}/google-fetch", json={},
                        headers={"Idempotency-Key": str(uuid.uuid4())})
    assert (fetch.status_code, fetch.json()["error"]["code"]) == (409, "GOOGLE_KEY_MISSING")
    saved = client.put("/api/v1/settings/google-maps-key", json={"key": KEY})
    assert saved.status_code == 200 and KEY not in saved.text
    assert client.get("/api/v1/settings").json() == {"google_maps_configured": True}
    preview = client.post(f"{base}/google-preview", json={})
    assert preview.json() == {"lookups": 4, "cached": 0}
    assert client.delete("/api/v1/settings/google-maps-key").json() == {
        "google_maps_configured": False}
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM local_secrets")) == 0
