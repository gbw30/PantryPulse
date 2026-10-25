"""Real PostgreSQL tests, confined to a generated disposable schema.

Opt in with PP19_TEST_DATABASE_URL and PP19_TEST_SCHEMA_ISOLATION=1.
No existing table/data is reset; cleanup is confined to the generated schema.
"""

import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import database_engine
from app.models import operational as m
from app.models.jobs import metadata as job_metadata
from app.repositories.operational import append_receipt_revision, tenant_get
from app.schemas.operational import ReceiptRevision

pytestmark = pytest.mark.integration
API_ROOT = Path(__file__).resolve().parents[2]


def migrate(connection, schema, target="head", downgrade=False):
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes.update(connection=connection, schema=schema)
    (command.downgrade if downgrade else command.upgrade)(config, target)


@pytest.fixture(scope="module")
def storage():
    url = os.environ.get("PP19_TEST_DATABASE_URL")
    if not url or os.environ.get("PP19_TEST_SCHEMA_ISOLATION") != "1":
        pytest.skip("requires explicit PP19 PostgreSQL isolated-schema opt-in")
    engine = database_engine(url)
    schema = "pp19_test_" + uuid4().hex
    assert re.fullmatch(r"pp19_test_[0-9a-f]{32}", schema)
    with engine.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
        migrate(connection, schema)
    try:
        yield engine, schema
    finally:
        # Only a name generated in this fixture can reach the destructive operation.
        assert re.fullmatch(r"pp19_test_[0-9a-f]{32}", schema)
        with engine.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def db(storage):
    engine, schema = storage
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


def insert(db, model, **values):
    row = model(id=uuid4(), **values)
    db.add(row)
    db.flush()
    return row


def seed(db):
    org = insert(db, m.Organization, name="PP19 synthetic test", is_demo=True)
    own = {"organization_id": org.id}
    site = insert(db, m.Site, **own, name="Test hub", role="HUB", active=True)
    calendar = insert(db, m.SiteCalendar, **own, site_id=site.id,
                      timezone="America/New_York", revision=1)
    site.current_calendar_id = calendar.id
    category = insert(db, m.Category, **own, name="Meals", active=True)
    product = insert(db, m.Product, **own, category_id=category.id,
                     name="Meal", base_unit="meal", active=True)
    source = insert(db, m.DataSource, **own, name="Test fixture", classification="SIMULATED")
    donor = insert(db, m.Donor, **own, name="Fixture donor", active=True)
    receipt = insert(db, m.Receipt, **own, source_id=source.id, source_record_key="receipt-1")
    return org, site, calendar, product, source, donor, receipt


def contract(items, **changes):
    org, site, calendar, product, source, donor, receipt = items
    return ReceiptRevision(**({
        "organization_id": org.id, "receipt_id": receipt.id, "revision_id": uuid4(),
        "revision": 1, "source_id": source.id, "source_record_key": "receipt-1",
        "source_classification": "SIMULATED", "receiving_site_id": site.id,
        "donor_id": donor.id, "calendar_version_id": calendar.id,
        "received_at": datetime(2026, 10, 25, 2, tzinfo=UTC),
        "recorded_at": datetime(2026, 10, 25, 3, tzinfo=UTC),
        "local_day": date(2026, 10, 24), "timezone": "America/New_York", "is_void": False,
        "lines": ({"line_key": "1", "product_id": product.id, "quantity": 30},),
    } | changes))


def test_upgrade_matches_models_and_indexes(storage):
    engine, schema = storage
    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert set(inspector.get_table_names(schema=schema)) == (
            set(m.Base.metadata.tables) | set(job_metadata.tables)
        ) | {
            "alembic_version"
        }
        all_tables = dict(m.Base.metadata.tables) | dict(job_metadata.tables)
        for name, table in all_tables.items():
            assert {column["name"] for column in inspector.get_columns(name, schema=schema)} == {
                column.name for column in table.columns
            }
        assert "ix_lot_expiry" in {
            index["name"] for index in inspector.get_indexes("inventory_lots", schema=schema)
        }


def test_frozen_migration_matches_current_orm(storage):
    engine, schema = storage
    with engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        context = MigrationContext.configure(connection, opts={
            "version_table_schema": schema,
            # search_path reflection calls this infrastructure table schema=None.
            # Domain-table presence is checked separately above, including version table.
            "include_object": lambda obj, name, kind, reflected, compare_to:
                not (kind == "table" and name in {"alembic_version", *job_metadata.tables}),
        })
        # Worker metadata intentionally mirrors columns only, not historical FKs.
        # Its columns are checked above; retain the full operational drift check.
        assert compare_metadata(context, m.Base.metadata) == []


@pytest.mark.parametrize("prior", ["pp21_0002", "0001_jobs_foundation"])
def test_existing_parent_history_upgrades_to_combined_head(storage, prior):
    engine, _ = storage
    schema = "ppmerge_test_" + uuid4().hex
    assert re.fullmatch(r"ppmerge_test_[0-9a-f]{32}", schema)
    with engine.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    try:
        with engine.begin() as connection:
            migrate(connection, schema, prior)
            migrate(connection, schema)
            assert connection.scalar(sa.text(
                f'SELECT version_num FROM "{schema}".alembic_version'
            )) == "pp49_0006"
            assert set(sa.inspect(connection).get_table_names(schema=schema)) == (
                set(m.Base.metadata.tables) | set(job_metadata.tables) | {"alembic_version"}
            )
            migrate(connection, schema, "base", downgrade=True)
            assert sa.inspect(connection).get_table_names(schema=schema) == ["alembic_version"]
    finally:
        assert re.fullmatch(r"ppmerge_test_[0-9a-f]{32}", schema)
        with engine.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))


def test_history_roundtrip_does_not_create_stock(db):
    items = seed(db)
    row = append_receipt_revision(db, contract(items))
    db.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert tenant_get(db, m.ReceiptRevision, items[0].id, row.id).revision == 1
    assert tenant_get(db, m.ReceiptRevision, uuid4(), row.id) is None
    assert db.scalar(sa.select(sa.func.count()).select_from(m.InventoryLot)) == 0
    assert db.scalar(sa.select(sa.func.count()).select_from(m.StockLedgerEntry)) == 0


def test_cross_organization_reference_rejected(db):
    org, _, _, product, _, _, _ = seed(db)
    other = insert(db, m.Organization, name="Unrelated fixture", is_demo=True)
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, m.Product, organization_id=other.id, category_id=product.category_id,
               name="Wrong owner", base_unit="meal", active=True)
    assert org.id != other.id


@pytest.mark.parametrize("requested,fulfilled,unmet", [(-1, 0, 0), (60, 45, 16), (40, 45, None)])
def test_database_rejects_invalid_demand(db, requested, fulfilled, unmet):
    org, site, calendar, product, source, _, _ = seed(db)
    record = insert(db, m.DemandRecord, organization_id=org.id, site_id=site.id,
                    product_id=product.id, source_id=source.id, source_record_key="d1",
                    local_day=date(2026, 10, 24))
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, m.DemandRevision, organization_id=org.id, record_id=record.id,
               site_id=site.id, calendar_version_id=calendar.id, revision=1,
               requested=requested, fulfilled=fulfilled, unmet=unmet)


def test_revisions_preserve_original_and_reject_duplicate(db):
    items = seed(db)
    first = append_receipt_revision(db, contract(items))
    second = append_receipt_revision(db, contract(items, revision=2))
    with pytest.raises(IntegrityError), db.begin_nested():
        append_receipt_revision(db, contract(items, revision=2))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(sa.update(m.ReceiptRevision).where(m.ReceiptRevision.id == first.id)
                   .values(revision=10))
    assert first.id != second.id


def test_incomplete_receipt_fails_and_rolls_back(db):
    items = seed(db)
    value = contract(items)
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, m.ReceiptRevision, organization_id=value.organization_id,
               receipt_id=value.receipt_id, receiving_site_id=value.receiving_site_id,
               donor_id=value.donor_id, calendar_version_id=value.calendar_version_id,
               revision=1, received_at=value.received_at, local_day=value.local_day, is_void=False)
        db.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert db.scalar(sa.select(sa.func.count()).select_from(m.ReceiptRevision)) == 0


def lot_values(items):
    org, site, _, product, _, _, _ = items
    return dict(organization_id=org.id, site_id=site.id, product_id=product.id,
                batch_key="opening", received_at=datetime(2026, 10, 24, tzinfo=UTC),
                on_hand=30, eligibility="ELIGIBLE", expiry_kind="NON_EXPIRING", expires_on=None,
                declaration_actor="fixture", declaration_reason="Test non-expiring declaration",
                declared_at=datetime(2026, 10, 24, tzinfo=UTC), metadata_version=1)


@pytest.mark.parametrize("changes", [
    {"on_hand": -1}, {"expiry_kind": "DATED", "expires_on": None},
    {"expiry_kind": "NON_EXPIRING", "expires_on": date(2026, 10, 24)},
])
def test_stock_constraints(db, changes):
    values = lot_values(seed(db)) | changes
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, m.InventoryLot, **values)


def test_failed_multirow_write_rolls_back(db):
    values = lot_values(seed(db))
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, m.InventoryLot, **values)
        insert(db, m.InventoryLot, **(values | {"batch_key": "invalid", "on_hand": -1}))
    assert db.scalar(sa.select(sa.func.count()).select_from(m.InventoryLot)) == 0


def test_supply_correction_does_not_recreate_confirmed_arrival(db):
    org, site, _, product, source, _, _ = seed(db)
    supply = insert(db, m.ExpectedSupply, organization_id=org.id, site_id=site.id,
                    product_id=product.id, source_id=source.id, source_record_key="s1",
                    quantity=100, received_quantity=100, outstanding_confirmed_quantity=0,
                    state="RECEIVED", version=1)
    supply.received_quantity = 80
    supply.version = 2
    db.flush()
    assert supply.outstanding_confirmed_quantity == 0


def test_active_site_requires_calendar_and_units_cannot_be_rewritten(db):
    org, _, _, product, _, _, _ = seed(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, m.Site, organization_id=org.id, name="No calendar", role="HUB", active=True)
        db.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(sa.update(m.Product).where(m.Product.id == product.id)
                   .values(base_unit="bottle"))


def stock_command(db, organization_id, key=None):
    return insert(db, m.StockCommand, organization_id=organization_id,
                  actor="fixture", operation="TEST", reason="Synthetic test only",
                  idempotency_key=key or str(uuid4()), payload_hash="a" * 64, outcome={})


def test_command_key_is_unique_and_audit_is_append_only(db):
    org, *_ = seed(db)
    first = stock_command(db, org.id, "same-key")
    event = insert(db, m.AuditEvent, organization_id=org.id, command_id=first.id,
                   event="test", details={})
    with pytest.raises(IntegrityError), db.begin_nested():
        stock_command(db, org.id, "same-key")
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(sa.delete(m.AuditEvent).where(m.AuditEvent.id == event.id))


def test_supply_allocations_cannot_reuse_receipt_units(db):
    items = seed(db)
    org, site, _, product, source, _, _ = items
    revision = append_receipt_revision(db, contract(items))
    line = db.scalar(sa.select(m.ReceiptLine).where(
        m.ReceiptLine.receipt_revision_id == revision.id
    ))
    supplies = [insert(db, m.ExpectedSupply, organization_id=org.id, site_id=site.id,
                       product_id=product.id, source_id=source.id, source_record_key=f"s-{i}",
                       quantity=100, received_quantity=0, outstanding_confirmed_quantity=100,
                       expected_arrival_at=datetime(2026, 10, 24, tzinfo=UTC),
                       state="CONFIRMED", version=1) for i in range(2)]

    def allocate(supply, amount, reverses=None):
        cmd = stock_command(db, org.id)
        return insert(db, m.SupplyReceipt, organization_id=org.id, supply_id=supply.id,
                      site_id=site.id, product_id=product.id, receipt_line_id=line.id,
                      receipt_revision_id=revision.id, command_id=cmd.id,
                      quantity_delta=amount, reverses_allocation_id=reverses)

    first = allocate(supplies[0], 20)
    with pytest.raises(IntegrityError), db.begin_nested():
        allocate(supplies[1], 20)  # total 40 exceeds receipt's 30
    with pytest.raises(IntegrityError), db.begin_nested():
        allocate(supplies[0], -21, first.id)
    allocate(supplies[0], -20, first.id)
    allocate(supplies[1], 30)


def test_committed_receipt_line_set_cannot_be_extended(storage):
    engine, schema = storage
    with engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        with Session(bind=connection) as session:
            items = seed(session)
            revision = append_receipt_revision(session, contract(items))
            organization_id, revision_id, product_id = items[0].id, revision.id, items[3].id
            session.flush()
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        connection.execute(sa.insert(m.ReceiptLine).values(
            organization_id=organization_id, id=uuid4(), receipt_revision_id=revision_id,
            line_key="late", product_id=product_id, received_quantity=1,
        ))


def test_downgrade_reupgrade_and_unrelated_schema_untouched(storage):
    engine, schema = storage
    with engine.begin() as connection:
        unrelated = "pp19_test_" + uuid4().hex
        assert re.fullmatch(r"pp19_test_[0-9a-f]{32}", unrelated)
        connection.execute(sa.schema.CreateSchema(unrelated))
        try:
            connection.execute(sa.text(f'CREATE TABLE "{unrelated}".sentinel (value integer)'))
            connection.execute(sa.text(f'INSERT INTO "{unrelated}".sentinel VALUES (7)'))
            migrate(connection, schema, "base", downgrade=True)
            assert sa.inspect(connection).get_table_names(schema=schema) == ["alembic_version"]
            assert connection.scalar(sa.text(f'SELECT value FROM "{unrelated}".sentinel')) == 7
            migrate(connection, schema)
        finally:
            connection.execute(sa.schema.DropSchema(unrelated, cascade=True))
