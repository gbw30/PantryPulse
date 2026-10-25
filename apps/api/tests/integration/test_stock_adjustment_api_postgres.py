"""Audited HTTP commands against real Postgres in generated disposable schemas."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_forecast_api_postgres import api as api
from test_forecast_api_postgres import forecast_storage as forecast_storage

from app.main import create_app
from app.models import operational as m
from app.repositories.operational import append_receipt_revision
from app.schemas.operational import ReceiptRevision
from app.schemas.stock import LotDeclaration, PostReceipt, StockActor, VersionExpectation
from app.services.inventory.stock import execute_stock

pytestmark = pytest.mark.integration


@pytest.fixture
def stock(api):
    client, headers, runtime, demo = api
    org = UUID(demo["organization_id"])
    product, receipt = uuid4(), uuid4()
    with Session(runtime.engine) as session, session.begin():
        site = session.scalar(sa.select(m.Site).where(m.Site.organization_id == org))
        calendar = session.get(m.SiteCalendar, site.current_calendar_id)
        category = session.scalar(sa.select(m.Category.id).where(m.Category.organization_id == org))
        donor = session.scalar(sa.select(m.Donor.id).where(m.Donor.organization_id == org))
        source = session.scalar(sa.select(m.DataSource).where(m.DataSource.organization_id == org))
        session.add(m.Product(id=product, organization_id=org, category_id=category,
                              name="Adjustment fixture", base_unit="meal", active=True))
        session.add(m.Receipt(id=receipt, organization_id=org, source_id=source.id,
                              source_record_key=receipt.hex))
        session.flush()
        now = session.scalar(sa.text("SELECT clock_timestamp()"))
        revision = append_receipt_revision(session, ReceiptRevision(
            organization_id=org, receipt_id=receipt, revision_id=uuid4(), revision=1,
            source_id=source.id, source_record_key=receipt.hex, source_classification="SIMULATED",
            receiving_site_id=site.id, donor_id=donor, calendar_version_id=calendar.id,
            received_at=now, recorded_at=now, timezone=calendar.timezone,
            local_day=now.astimezone(ZoneInfo(calendar.timezone)).date(), is_void=False,
            lines=tuple(dict(line_key=str(i), product_id=product, quantity=q)
                        for i, q in enumerate((30, 40))),
        ))
        actor = StockActor(organization_id=org, actor="isolated-fixture")
        execute_stock(session, actor, PostReceipt(
            idempotency_key=receipt.hex, reason="Synthetic receipt for HTTP test",
            expected_versions=(VersionExpectation(site_id=site.id, product_id=product, version=1),),
            revision_id=revision.id, declarations=tuple(LotDeclaration(
                line_key=str(i), eligibility="ELIGIBLE",
                expiry=dict(kind="NON_EXPIRING", expires_on=None),
            ) for i in range(2)), supply_matches=(), supply_versions=(),
        ))
        lots = list(session.scalars(sa.select(m.InventoryLot).where(
            m.InventoryLot.product_id == product,
        ).order_by(m.InventoryLot.on_hand)))
        identities = site.id, product, tuple(lot.id for lot in lots)
    return client, headers, runtime, org, identities


def urls(identities):
    site, product, _lots = identities
    snapshot = f"/api/v1/inventory/sites/{site}/products/{product}"
    return snapshot, snapshot + "/adjustments"


def body(identities, delta="-5", version="2"):
    return dict(expected_inventory_version=version, reason="Physical count correction",
                source_reference="count-note-001",
                changes=[dict(lot_id=str(identities[2][0]), delta=delta)])


def counts(runtime):
    with runtime.engine.connect() as conn:
        return tuple(conn.scalar(sa.select(sa.func.count()).select_from(model)) for model in (
            m.StockCommand, m.StockLedgerEntry, m.AuditEvent,
        ))


def test_committed_adjustment_audit_exact_replay_and_changed_key_conflict(stock):
    client, headers, runtime, org, ids = stock
    read, write = urls(ids)
    request = body(ids)
    before = counts(runtime)
    command_headers = headers | {"Idempotency-Key": uuid4().hex}
    response = client.post(write, json=request, headers=command_headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "APPLIED"
    assert result["before_version"] == "2" and result["after_version"] == "3"
    assert result["lots"] == [dict(lot_id=str(ids[2][0]), before="30", after="25")]
    assert client.get(read).json()["on_hand_quantity"] == "65"
    assert counts(runtime) == tuple(value + 1 for value in before)
    with runtime.engine.connect() as conn:
        saved = conn.execute(sa.select(m.StockCommand.__table__).where(
            m.StockCommand.id == UUID(result["command_id"]),
        )).mappings().one()
        assert saved["organization_id"] == org
        assert saved["actor"] != "isolated-fixture"
        assert saved["reason"] == request["reason"]
        assert saved["outcome"]["source_reference"] == request["source_reference"]
    replay = client.post(write, json=request, headers=command_headers)
    assert replay.status_code == 200 and replay.json() == result
    assert counts(runtime) == tuple(value + 1 for value in before)
    conflict = client.post(write, json=body(ids, "-6"), headers=command_headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert client.get(read).json()["on_hand_quantity"] == "65"


def test_multi_lot_negative_adjustment_rolls_back_everything(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    before = counts(runtime)
    request = body(ids)
    request["changes"].append(dict(lot_id=str(ids[2][1]), delta="-100"))
    response = client.post(write, json=request, headers=headers | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert counts(runtime) == before
    saved = client.get(read).json()
    assert saved["on_hand_quantity"] == "70" and saved["inventory_version"] == "2"


def test_stale_version_rejected_without_second_movement(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    assert client.post(write, json=body(ids), headers=(
        headers | {"Idempotency-Key": uuid4().hex}
    )).status_code == 200
    before = counts(runtime)
    stale = client.post(write, json=body(ids), headers=headers | {"Idempotency-Key": uuid4().hex})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_INVENTORY_VERSION"
    assert counts(runtime) == before
    assert client.get(read).json()["on_hand_quantity"] == "65"


def test_security_and_missing_command_headers_cannot_mutate_stock(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    request = body(ids)
    before = counts(runtime)
    valid = headers | {"Idempotency-Key": uuid4().hex}
    for changed in (valid | {"Origin": "https://evil.example"},
                    valid | {"X-CSRF-Token": "wrong"}):
        assert client.post(write, json=request, headers=changed).status_code == 403
    no_origin = {key: value for key, value in valid.items() if key != "Origin"}
    no_csrf = {key: value for key, value in valid.items() if key != "X-CSRF-Token"}
    assert client.post(write, json=request, headers=no_origin).status_code == 403
    assert client.post(write, json=request, headers=no_csrf).status_code == 403
    assert client.post(write, json=request, headers=headers).status_code == 422
    assert client.post(write, json=request, headers=(
        headers | {"Idempotency-Key": " "}
    )).status_code == 422
    assert client.post(write, json=request | {"actor": "admin"}, headers=valid).status_code == 422
    with TestClient(create_app(runtime)) as anonymous:
        assert anonymous.post(write, json=request, headers=valid).status_code == 401
    assert counts(runtime) == before
    assert client.get(read).json()["on_hand_quantity"] == "70"


def test_lots_cannot_escape_site_product_or_tenant_scope(stock):
    client, headers, runtime, _org, ids = stock
    _read, write = urls(ids)
    request = body(ids)
    before = counts(runtime)
    valid = headers | {"Idempotency-Key": uuid4().hex}
    assert client.post(write.replace(str(ids[0]), str(uuid4())), json=request,
                       headers=valid).status_code == 404
    assert client.post(write.replace(str(ids[1]), str(uuid4())), json=request,
                       headers=valid).status_code == 404
    with runtime.engine.begin() as conn:
        org, site, category, product, lot = [uuid4() for _ in range(5)]
        conn.execute(sa.insert(m.Organization).values(id=org, name="Other tenant", is_demo=True))
        conn.execute(sa.insert(m.Site).values(
            id=site, organization_id=org, name="Inactive fixture", role="HUB", active=False,
        ))
        conn.execute(sa.insert(m.Category).values(
            id=category, organization_id=org, name="Other", active=True,
        ))
        conn.execute(sa.insert(m.Product).values(
            id=product, organization_id=org, category_id=category,
            name="Other", base_unit="meal", active=True,
        ))
        conn.execute(sa.insert(m.InventoryLot).values(
            id=lot, organization_id=org, site_id=site, product_id=product,
            batch_key="other", on_hand=1, eligibility="ELIGIBLE", expiry_kind="NON_EXPIRING",
            metadata_version=1, declaration_actor="fixture", declaration_reason="Fixture",
            received_at=sa.func.clock_timestamp(), declared_at=sa.func.clock_timestamp(),
        ))
    request["changes"][0]["lot_id"] = str(lot)
    assert client.post(write, json=request, headers=valid).status_code == 404
    assert counts(runtime) == before


def test_concurrent_different_commands_with_same_version_have_one_winner(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    barrier = Barrier(2)
    before = counts(runtime)

    def submit(_index):
        barrier.wait(timeout=10)
        return client.post(write, json=body(ids), headers=(
            headers | {"Idempotency-Key": uuid4().hex}
        ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(response.status_code for response in results) == [200, 409]
    assert counts(runtime) == tuple(value + 1 for value in before)
    saved = client.get(read).json()
    assert saved["inventory_version"] == "3" and saved["on_hand_quantity"] == "65"


def test_concurrent_identical_commands_share_one_committed_outcome(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    barrier = Barrier(2)
    before = counts(runtime)
    valid = headers | {"Idempotency-Key": uuid4().hex}

    def submit(_index):
        barrier.wait(timeout=10)
        return client.post(write, json=body(ids, "5"), headers=valid)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert [response.status_code for response in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert counts(runtime) == tuple(value + 1 for value in before)
    assert client.get(read).json()["on_hand_quantity"] == "75"


def test_failure_during_audit_insert_rolls_back_balance_version_and_ledger(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    before = counts(runtime)
    fired = False

    def fail_audit(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal fired
        if statement.startswith("INSERT INTO audit_events"):
            fired = True
            raise sa.exc.OperationalError("synthetic audit failure", None, RuntimeError("fixture"))

    sa.event.listen(runtime.engine, "before_cursor_execute", fail_audit)
    try:
        response = client.post(write, json=body(ids), headers=(
            headers | {"Idempotency-Key": uuid4().hex}
        ))
    finally:
        sa.event.remove(runtime.engine, "before_cursor_execute", fail_audit)
    assert fired
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "fixture" not in response.text
    assert counts(runtime) == before
    saved = client.get(read).json()
    assert saved["inventory_version"] == "2" and saved["on_hand_quantity"] == "70"


def test_count_overflow_rejected_without_any_writes(stock):
    client, headers, runtime, _org, ids = stock
    read, write = urls(ids)
    before = counts(runtime)
    response = client.post(write, json=body(ids, str(2**63 - 1)), headers=(
        headers | {"Idempotency-Key": uuid4().hex}
    ))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "COUNT_OVERFLOW"
    assert counts(runtime) == before
    assert client.get(read).json()["on_hand_quantity"] == "70"
