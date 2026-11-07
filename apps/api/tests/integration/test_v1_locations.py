# covers: V1-A13
"""GET /networks/{id}/locations (CR-w1-web-1): names, roles and coordinates for the atlas."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.services.networks.locations import list_locations
from app.services.presenter_access import AccessError

pytestmark = pytest.mark.integration


def _version(conn, ids, ver, recorded_at, locations):
    q = lambda sql, **kw: conn.execute(sa.text(sql), {**ids, "ver": ver, **kw})  # noqa: E731
    run = uuid.uuid4()
    q(
        "INSERT INTO import_runs (id, organization_id, network_id, phase) "
        "VALUES (:run, :org, :net, 'done')",
        run=run,
    )
    q(
        "INSERT INTO dataset_versions (id, organization_id, network_id, import_run_id, as_of_date, "
        "input_sha256, recorded_at) VALUES (:ver, :org, :net, :run, '2026-11-03', repeat('a', 64), "
        ":at)",
        run=run,
        at=recorded_at,
    )
    for ext, name, role, lat, lon, source in locations:
        q(
            "INSERT INTO net_locations (id, organization_id, dataset_version_id, external_id, "
            "name, "
            "role, street, city, state, zip, latitude, longitude, coordinates_source) VALUES "
            "(gen_random_uuid(), :org, :ver, :ext, :name, :role, '1 Main', 'Gainesville', 'FL', "
            "'32601', :lat, :lon, :src)",
            ext=ext,
            name=name,
            role=role,
            lat=lat,
            lon=lon,
            src=source,
        )


@pytest.fixture
def network(db):
    ids = {"org": uuid.uuid4(), "net": uuid.uuid4()}
    old, new = uuid.uuid4(), uuid.uuid4()
    with db.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO organizations (id, name, is_demo) VALUES (:org, 'n', false)"), ids
        )
        conn.execute(
            sa.text(
                "INSERT INTO networks (id, organization_id, name, mode, timezone) "
                "VALUES (:net, :org, 'n', 'PANTRY', 'America/New_York')"
            ),
            ids,
        )
        _version(
            conn, ids, old, "2026-11-01T00:00:00Z", [("OLD", "Old", "pantry", None, None, None)]
        )
        _version(
            conn,
            ids,
            new,
            "2026-11-02T00:00:00Z",
            [
                ("P-2", "North Pantry", "pantry", "29.651634", "-82.324826", "census_geocoder"),
                ("H-1", "Main Hub", "hub", "29.600000", "-82.300000", "user"),
                ("P-3", "Unmatched", "pantry", None, None, None),
            ],
        )
    yield SimpleNamespace(engine=db), ids["net"], new
    with db.begin() as conn:  # rows are immutable: drop the throwaway network by cascade
        conn.execute(sa.text("SET LOCAL session_replication_role = replica"))
        for table in ("net_locations", "dataset_versions", "import_runs", "networks"):
            conn.execute(sa.text(f"DELETE FROM {table} WHERE organization_id = :org"), ids)


def test_locations_of_the_latest_version_with_coordinates(network):
    rt, net, ver = network
    result = list_locations(rt, None, net)
    assert result.network_id == net and result.dataset_version_id == ver
    assert [loc.location_id for loc in result.locations] == ["H-1", "P-2", "P-3"]
    hub, pantry, unmatched = result.locations
    assert (hub.name, hub.role, hub.coordinates_source) == ("Main Hub", "hub", "user")
    assert pantry.latitude == Decimal("29.651634") and pantry.longitude == Decimal("-82.324826")
    assert unmatched.latitude is None and unmatched.longitude is None
    assert result.model_dump(mode="json")["locations"][1]["latitude"] == "29.651634"


def test_unknown_network_is_404(db):
    with pytest.raises(AccessError) as caught:
        list_locations(SimpleNamespace(engine=db), None, uuid.uuid4())
    assert caught.value.status == 404
