"""HTTP + real Postgres in a disposable schema; no live worker or persistent demo writes."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from test_forecast_api_postgres import api as api
from test_forecast_api_postgres import forecast_storage as forecast_storage

from app.main import create_app
from app.models import operational as m

pytestmark = pytest.mark.integration


def path(site, product):
    return f"/api/v1/inventory/sites/{site}/products/{product}"


def catalog(client):
    response = client.get("/api/v1/forecast-catalog")
    assert response.status_code == 200
    data = response.json()
    return UUID(data["sites"][0]["id"]), UUID(data["products"][0]["id"])


def seeded_stock(runtime, demo, site, amounts):
    org = UUID(demo["organization_id"])
    product = uuid4()
    with runtime.engine.begin() as conn:
        category = conn.scalar(sa.select(m.Category.id).where(m.Category.organization_id == org))
        conn.execute(sa.insert(m.Product).values(
            id=product, organization_id=org, category_id=category, name="Snapshot test meals",
            base_unit="meal", active=True,
        ))
        timezone = conn.scalar(sa.select(m.SiteCalendar.timezone).join(
            m.Site, m.Site.current_calendar_id == m.SiteCalendar.id,
        ).where(m.Site.id == site))
        today = conn.scalar(sa.text("SELECT transaction_timestamp()")).astimezone(
            ZoneInfo(timezone)
        ).date()
        conn.execute(sa.insert(m.InventoryVersion).values(
            id=uuid4(), organization_id=org, site_id=site, product_id=product, version=7,
        ))
        for amount, eligibility, kind, offset in amounts:
            conn.execute(sa.insert(m.InventoryLot).values(
                id=uuid4(), organization_id=org, site_id=site, product_id=product,
                batch_key=uuid4().hex, on_hand=amount, eligibility=eligibility,
                expiry_kind=kind, expires_on=today + timedelta(days=offset) if offset else (
                    today if kind == "DATED" else None
                ), metadata_version=1, declaration_actor="isolated-fixture",
                declaration_reason="Synthetic test only", declared_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
            ))
    return product


def test_http_inventory_without_worker_has_exact_totals_and_no_writes(api):
    client, _, runtime, demo = api
    site, _ = catalog(client)
    product = seeded_stock(runtime, demo, site, [
        (2**63 - 1, "ELIGIBLE", "NON_EXPIRING", None),
        (12, "ELIGIBLE", "DATED", 0), (4, "ELIGIBLE", "DATED", -1),
        (5, "HELD", "DATED", -1), (6, "ELIGIBLE", "UNKNOWN", None),
        (0, "ELIGIBLE", "NON_EXPIRING", None),
    ])
    models = (m.StockCommand, m.StockLedgerEntry, m.AuditEvent, m.InventoryVersion)
    with runtime.engine.connect() as conn:
        before = [conn.scalar(sa.select(sa.func.count()).select_from(model)) for model in models]
    response = client.get(path(site, product))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["inventory_version"] == "7"
    assert result["on_hand_quantity"] == str(2**63 - 1 + 27)
    assert result["usable_quantity"] == str(2**63 - 1 + 12)
    assert result["excluded_quantity"] == "15"
    assert result["excluded_quantities"]["EXPIRED"] == "4"
    assert result["excluded_quantities"]["HELD"] == "5"
    assert result["excluded_quantities"]["UNKNOWN_EXPIRY"] == "6"
    assert len(result["lots"]) == 5
    assert result["base_unit"] == "meal"
    assert response.headers["Cache-Control"] == "no-store"
    assert UUID(response.headers["X-Request-ID"])
    assert client.get(path(site, product)).json()["inventory_version"] == "7"
    with runtime.engine.connect() as conn:
        after = [conn.scalar(sa.select(sa.func.count()).select_from(model)) for model in models]
    assert before == after


def test_empty_inventory_missing_ids_validation_and_authentication(api):
    client, _, runtime, demo = api
    site, _ = catalog(client)
    # UUID catalog order is not a guarantee of empty stock after other tests seed lots.
    product = uuid4()
    org = UUID(demo["organization_id"])
    with runtime.engine.begin() as conn:
        category = conn.scalar(sa.select(m.Category.id).where(m.Category.organization_id == org))
        conn.execute(sa.insert(m.Product).values(
            id=product, organization_id=org, category_id=category,
            name="Explicitly empty fixture", base_unit="meal", active=True,
        ))
    response = client.get(path(site, product))
    assert response.status_code == 200
    assert response.json()["inventory_version"] is None
    assert response.json()["on_hand_quantity"] == "0"
    assert response.json()["lots"] == []
    assert client.get(path(uuid4(), product)).status_code == 404
    assert client.get(path(site, uuid4())).status_code == 404
    assert client.get(path("invalid", product)).status_code == 422
    with TestClient(create_app(runtime)) as anonymous:
        assert anonymous.get(path(site, product)).status_code == 401


def test_other_tenant_ids_are_not_visible(api):
    client, _, runtime, _ = api
    site, product = catalog(client)
    with runtime.engine.begin() as conn:
        org, other_site, category, other_product = [uuid4() for _ in range(4)]
        conn.execute(sa.insert(m.Organization).values(id=org, name="Other tenant", is_demo=True))
        conn.execute(sa.insert(m.Site).values(
            id=other_site, organization_id=org, name="Other site", role="HUB", active=True,
        ))
        calendar = uuid4()
        conn.execute(sa.insert(m.SiteCalendar).values(
            id=calendar, organization_id=org, site_id=other_site,
            timezone="America/New_York", revision=1,
        ))
        conn.execute(sa.update(m.Site).where(m.Site.id == other_site).values(
            current_calendar_id=calendar,
        ))
        conn.execute(sa.insert(m.Category).values(
            id=category, organization_id=org, name="Other category", active=True,
        ))
        conn.execute(sa.insert(m.Product).values(
            id=other_product, organization_id=org, category_id=category,
            name="Other product", base_unit="unit", active=True,
        ))
    assert client.get(path(other_site, product)).status_code == 404
    assert client.get(path(site, other_product)).status_code == 404


def test_oversized_snapshot_rejected_instead_of_partial_totals(api, monkeypatch):
    client, _, runtime, demo = api
    site, _ = catalog(client)
    product = seeded_stock(runtime, demo, site, [
        (1, "ELIGIBLE", "NON_EXPIRING", None),
        (2, "ELIGIBLE", "NON_EXPIRING", None),
    ])
    monkeypatch.setattr("app.repositories.inventory.MAX_LOTS", 1)
    response = client.get(path(site, product))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVENTORY_TOO_LARGE"


def test_concurrent_stock_change_cannot_mix_versions_and_balances(api):
    client, _, runtime, demo = api
    site, _ = catalog(client)
    product = seeded_stock(runtime, demo, site, [(3, "ELIGIBLE", "NON_EXPIRING", None)])
    updated = False

    def concurrent_update(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal updated
        if updated or not statement.startswith("SELECT inventory_versions.version"):
            return
        updated = True
        # Deliberate concurrent fixture change after the reader fetched its version.
        with runtime.engine.begin() as writer:
            writer.execute(sa.update(m.InventoryLot).where(
                m.InventoryLot.product_id == product,
            ).values(on_hand=9))
            writer.execute(sa.update(m.InventoryVersion).where(
                m.InventoryVersion.product_id == product,
            ).values(version=8))

    sa.event.listen(runtime.engine, "after_cursor_execute", concurrent_update)
    try:
        before = client.get(path(site, product))
    finally:
        sa.event.remove(runtime.engine, "after_cursor_execute", concurrent_update)
    assert updated
    assert before.status_code == 200, before.text
    assert before.json()["inventory_version"] == "7"
    assert before.json()["on_hand_quantity"] == "3"
    after = client.get(path(site, product)).json()
    assert after["inventory_version"] == "8"
    assert after["on_hand_quantity"] == "9"
