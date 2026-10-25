"""Actual operational HTTP lifecycle; all writes confined to disposable test schemas."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from test_forecast_api_postgres import api as api
from test_forecast_api_postgres import forecast_storage as forecast_storage

from app.models import operational as m
from app.models.http_commands import HTTPCommand

pytestmark = pytest.mark.integration


def inputs(api):
    client, headers, runtime, _demo = api
    response = client.get("/api/v1/operational-catalog")
    assert response.status_code == 200, response.text
    catalog = response.json()
    return client, headers, runtime, catalog


def post(client, headers, url, body, key=None):
    return client.post(url, json=body, headers=headers | {"Idempotency-Key": key or uuid4().hex})


def receipt_body(catalog):
    return dict(
        source_id=catalog["data_sources"][0]["id"],
        source_record_key=uuid4().hex,
        site_id=catalog["sites"][0]["id"],
        donor_id=catalog["donors"][0]["id"],
        received_at="2026-10-24T12:00:00Z",
        expected_revision=None,
        is_void=False,
        lines=[dict(line_key="main", product_id=catalog["products"][0]["id"], quantity="100")],
    )


def stock_body(body, revision, version):
    return dict(
        revision_id=revision,
        reason="Actual delivery received",
        expected_versions=[
            dict(
                site_id=body["site_id"], product_id=body["lines"][0]["product_id"], version=version
            )
        ],
        declarations=[
            dict(
                line_key="main",
                eligibility="ELIGIBLE",
                expiry=dict(kind="NON_EXPIRING", expires_on=None),
            )
        ],
        supply_matches=[],
        supply_versions=[],
    )


def snapshot(client, body):
    return client.get(
        f"/api/v1/inventory/sites/{body['site_id']}/products/{body['lines'][0]['product_id']}"
    ).json()


def test_receipt_history_post_replay_correction_and_void(api):
    client, headers, _runtime, catalog = inputs(api)
    body = receipt_body(catalog)
    before = snapshot(client, body)
    key = uuid4().hex
    created = post(client, headers, "/api/v1/receipts", body, key)
    assert created.status_code == 201, created.text
    assert post(client, headers, "/api/v1/receipts", body, key).json() == created.json()
    assert snapshot(client, body)["on_hand_quantity"] == before["on_hand_quantity"]
    data = created.json()["result"]
    rid, revision = data["receipt_id"], data["revision_id"]
    version = before["inventory_version"] or "1"
    request = stock_body(body, revision, version)
    key = uuid4().hex
    posted = post(client, headers, f"/api/v1/receipts/{rid}/post", request, key)
    assert posted.status_code == 200, posted.text
    assert (
        post(client, headers, f"/api/v1/receipts/{rid}/post", request, key).json() == posted.json()
    )
    updated = snapshot(client, body)
    assert int(updated["on_hand_quantity"]) == int(before["on_hand_quantity"]) + 100
    correction = body | {"expected_revision": "1", "lines": [body["lines"][0] | {"quantity": "50"}]}
    revised = post(client, headers, f"/api/v1/receipts/{rid}/revisions", correction)
    assert revised.status_code == 201, revised.text
    saved = client.get(f"/api/v1/receipts/{rid}").json()
    assert saved["reconciliation"]["needs_reconciliation"] is True
    request = stock_body(
        body, revised.json()["result"]["revision_id"], updated["inventory_version"]
    )
    reconciled = post(client, headers, f"/api/v1/receipts/{rid}/reconcile", request)
    assert reconciled.status_code == 200, reconciled.text
    assert int(snapshot(client, body)["on_hand_quantity"]) == int(before["on_hand_quantity"]) + 50
    void = post(
        client,
        headers,
        f"/api/v1/receipts/{rid}/revisions",
        body
        | {
            "expected_revision": "2",
            "is_void": True,
            "lines": [],
        },
    )
    assert void.status_code == 201
    request = stock_body(
        body, void.json()["result"]["revision_id"], snapshot(client, body)["inventory_version"]
    )
    request["declarations"] = []
    assert post(client, headers, f"/api/v1/receipts/{rid}/reconcile", request).status_code == 200
    assert snapshot(client, body)["on_hand_quantity"] == before["on_hand_quantity"]


def test_lot_declaration_and_supply_confirmation_cancellation(api):
    client, headers, _runtime, catalog = inputs(api)
    body = receipt_body(catalog)
    created = post(client, headers, "/api/v1/receipts", body).json()["result"]
    old = snapshot(client, body)
    request = stock_body(body, created["revision_id"], old["inventory_version"] or "1")
    posted = post(client, headers, f"/api/v1/receipts/{created['receipt_id']}/post", request)
    assert posted.status_code == 200, posted.text
    lot = posted.json()["result"]["lots"][0]["lot_id"]
    current = snapshot(client, body)
    declaration = dict(
        expected_inventory_version=current["inventory_version"],
        reason="Expiry verified",
        eligibility="HELD",
        expiry=dict(kind="DATED", expires_on="2026-11-01"),
    )
    declared = post(client, headers, f"/api/v1/inventory/lots/{lot}/declarations", declaration)
    assert declared.status_code == 200, declared.text
    assert int(snapshot(client, body)["excluded_quantities"]["HELD"]) >= 100
    incoming = post(
        client,
        headers,
        "/api/v1/supplies",
        dict(
            site_id=body["site_id"],
            product_id=body["lines"][0]["product_id"],
            source_id=body["source_id"],
            source_record_key=uuid4().hex,
            quantity="25",
        ),
    )
    assert incoming.status_code == 201, incoming.text
    sid = incoming.json()["result"]["id"]
    confirmation = dict(
        expected_inventory_version=snapshot(client, body)["inventory_version"],
        expected_supply_version="1",
        reason="Donor explicitly confirmed",
        outstanding_quantity="25",
        expected_arrival_at=datetime.now(UTC).isoformat(),
        cancel=False,
    )
    confirmed = post(client, headers, f"/api/v1/supplies/{sid}/confirmation", confirmation)
    assert confirmed.status_code == 200, confirmed.text
    assert client.get(f"/api/v1/supplies/{sid}").json()["state"] == "CONFIRMED"
    cancelled = post(
        client,
        headers,
        f"/api/v1/supplies/{sid}/confirmation",
        confirmation
        | {
            "expected_inventory_version": snapshot(client, body)["inventory_version"],
            "expected_supply_version": "2",
            "outstanding_quantity": "0",
            "cancel": True,
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert client.get(f"/api/v1/supplies/{sid}").json()["state"] == "CANCELLED"


def test_import_missingness_revisions_atomicity_and_csv(api):
    client, headers, runtime, catalog = inputs(api)
    row = dict(
        source_record_key=uuid4().hex,
        site_id=catalog["sites"][0]["id"],
        product_id=catalog["products"][0]["id"],
        day="2026-01-01",
        expected_revision=None,
        requested="10",
        fulfilled=None,
        unmet=None,
    )
    body = dict(source_id=catalog["data_sources"][0]["id"], rows=[row])
    imported = post(client, headers, "/api/v1/imports/demand", body)
    assert imported.status_code == 201, imported.text
    revision = UUID(imported.json()["result"]["rows"][0]["revision_id"])
    with runtime.engine.connect() as conn:
        saved = (
            conn.execute(
                sa.select(m.DemandRevision.__table__).where(m.DemandRevision.id == revision)
            )
            .mappings()
            .one()
        )
        assert saved["fulfilled"] is None and saved["unmet"] is None
    corrected = post(
        client,
        headers,
        "/api/v1/imports/demand",
        body
        | {
            "rows": [row | {"expected_revision": "1", "requested": "11"}],
        },
    )
    assert corrected.status_code == 201, corrected.text
    invalid = row | {
        "source_record_key": uuid4().hex,
        "day": "2026-01-02",
        "requested": "5",
        "fulfilled": "10",
    }
    assert (
        post(client, headers, "/api/v1/imports/demand", body | {"rows": [invalid]}).status_code
        == 422
    )
    coverage = post(
        client,
        headers,
        "/api/v1/imports/donation-coverage",
        dict(
            source_id=body["source_id"],
            rows=[
                dict(
                    site_id=row["site_id"],
                    product_id=row["product_id"],
                    day="2026-01-01",
                    expected_revision=None,
                    complete=True,
                )
            ],
        ),
    )
    assert coverage.status_code == 201, coverage.text
    csv = (
        "source_record_key,site_id,product_id,day,expected_revision,requested,fulfilled,unmet\n"
        f"{uuid4().hex},{row['site_id']},{row['product_id']},2026-01-03,,12,,\n"
    )
    response = client.post(
        "/api/v1/imports/demand/csv",
        headers=(headers | {"Idempotency-Key": uuid4().hex}),
        data={"source_id": body["source_id"]},
        files={"file": ("history.csv", csv, "text/csv")},
    )
    assert response.status_code == 201, response.text


def test_journal_conflict_cross_tenant_and_immutability(api):
    client, headers, runtime, catalog = inputs(api)
    body = receipt_body(catalog)
    key = uuid4().hex
    created = post(client, headers, "/api/v1/receipts", body, key)
    assert created.status_code == 201, created.text
    changed = body | {"is_void": True, "lines": []}
    assert post(client, headers, "/api/v1/receipts", changed, key).status_code == 409
    assert (
        post(client, headers, "/api/v1/receipts", body | {"donor_id": str(uuid4())}).status_code
        == 404
    )
    with pytest.raises(sa.exc.IntegrityError), runtime.engine.begin() as conn:
        conn.execute(sa.update(HTTPCommand).values(operation="tampered"))


def test_same_tenant_in_isolated_schemas_does_not_share_http_write_locks(api):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    from sqlalchemy.orm import Session
    from test_operational_postgres import migrate

    from app.repositories.jobs import TrustedScope, create_queue_engine
    from app.repositories.operations_api import journal, transact

    _, _, runtime, demo = api
    schema = "ppmerge_test_" + uuid4().hex
    with runtime.engine.begin() as conn:
        conn.execute(sa.schema.CreateSchema(schema))
        migrate(conn, schema)
        conn.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(
            sa.insert(m.Organization).values(
                id=UUID(demo["organization_id"]), name="Independent schema", is_demo=True
            )
        )
    other = create_queue_engine(runtime.engine.url, schema=schema)
    scope = TrustedScope(UUID(demo["organization_id"]), "same-presenter")
    blocked = False
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with Session(runtime.engine) as session, session.begin():
                journal(session, scope, "schema-test", "same-key", {}, lambda: {"schema": "first"})
                future = pool.submit(
                    transact,
                    other,
                    lambda second: journal(
                        second, scope, "schema-test", "same-key", {}, lambda: {"schema": "second"}
                    ),
                )
                try:
                    result = future.result(timeout=2)
                except TimeoutError:
                    blocked = True
            result = future.result(timeout=5)
        assert not blocked, "An independent schema was blocked by another schema's write lock"
        assert result["result"] == {"schema": "second"}
    finally:
        other.dispose()
        with runtime.engine.begin() as conn:
            conn.execute(sa.schema.DropSchema(schema, cascade=True))


def test_atomic_import_reports_row_fields_and_counts_without_leaking_input(api):
    client, headers, runtime, catalog = inputs(api)
    row = dict(
        source_record_key=uuid4().hex,
        site_id=catalog["sites"][0]["id"],
        product_id=catalog["products"][0]["id"],
        day="2001-01-01",
        expected_revision=None,
        requested="3",
        fulfilled=None,
        unmet=None,
    )
    body = dict(
        source_id=catalog["data_sources"][0]["id"],
        rows=[
            row,
            row
            | {
                "source_record_key": "private-row-marker",
                "day": "2001-01-02",
                "requested": "1",
                "fulfilled": "2",
            },
        ],
    )
    with runtime.engine.connect() as conn:
        before = conn.scalar(sa.select(sa.func.count()).select_from(m.DemandRevision))
    response = post(client, headers, "/api/v1/imports/demand", body)
    assert response.status_code == 422, response.text
    details = response.json()["error"]["details"]
    assert (
        details["atomic"] is True
        and details["accepted_count"] == "0"
        and details["rejected_count"] == "2"
    )
    assert details["errors"][0]["row_index"] == 1
    assert "private-row-marker" not in response.text
    with runtime.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.DemandRevision)) == before
    malformed = post(
        client,
        headers,
        "/api/v1/imports/demand",
        body | {"rows": [row | {"requested": "private-bad-value"}]},
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["details"]["errors"][0]["field"] == "requested"
    assert "private-bad-value" not in malformed.text


def test_presenter_creates_products_up_to_the_limit(api):
    """More than two products: create, reject duplicates, enforce the active-product cap."""
    from app.repositories.operations_api import MAX_ACTIVE_PRODUCTS

    client, headers, _runtime, catalog = inputs(api)
    existing = len([p for p in catalog["products"] if p["active"]])
    created = post(
        client, headers, "/api/v1/products", {"name": "Canned vegetables", "base_unit": "can"}
    )
    assert created.status_code == 201, created.text
    product = created.json()["result"]
    assert (product["name"], product["base_unit"], product["active"]) == (
        "Canned vegetables",
        "can",
        True,
    )
    after = client.get("/api/v1/operational-catalog").json()["products"]
    assert any(p["id"] == product["id"] for p in after)
    duplicate = post(
        client, headers, "/api/v1/products", {"name": "canned VEGETABLES", "base_unit": "can"}
    )
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "PRODUCT_EXISTS"
    for index in range(MAX_ACTIVE_PRODUCTS - existing - 1):
        filler = post(
            client, headers, "/api/v1/products", {"name": f"Item {index}", "base_unit": "unit"}
        )
        assert filler.status_code == 201, filler.text
    over = post(client, headers, "/api/v1/products", {"name": "One too many", "base_unit": "unit"})
    assert over.status_code == 409 and over.json()["error"]["code"] == "PRODUCT_LIMIT_REACHED"
    visitor = client.post(
        "/api/v1/products",
        json={"name": "No session", "base_unit": "unit"},
        headers={"Idempotency-Key": uuid4().hex},
        cookies={},
    )
    assert visitor.status_code in (401, 403)
