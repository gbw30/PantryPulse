"""operational-v1 storage. Importing metadata never connects to a database.

Foreign keys include tenant and contextual identity. Database triggers in the
initial migration protect immutable history and complete receipt revisions.
No relationships cascade deletes into historical data.
"""

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    metadata = sa.MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


def uid(**options):
    return mapped_column(UUID(as_uuid=True), **options)


def instant(**options):
    return mapped_column(sa.DateTime(timezone=True), **options)


def check(expression, name):
    return sa.CheckConstraint(expression, name=name)


def fk(columns, target, remote=None):
    return sa.ForeignKeyConstraint(
        ["organization_id", *columns],
        [f"{target}.organization_id", *(f"{target}.{name}" for name in (remote or columns))],
        ondelete="RESTRICT",
    )


def owned(*constraints):
    return (
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "id"),
        *constraints,
    )


class Identity:
    id = uid(primary_key=True, default=uuid4)
    recorded_at = instant(nullable=False, server_default=sa.func.clock_timestamp())


class OwnedIdentity(Identity):
    organization_id = uid(nullable=False)


class Organization(Identity, Base):
    __tablename__ = "organizations"
    name = mapped_column(sa.Text, nullable=False)
    is_demo = mapped_column(sa.Boolean, nullable=False)


class Site(OwnedIdentity, Base):
    __tablename__ = "sites"
    name = mapped_column(sa.Text, nullable=False)
    role = mapped_column(sa.Text, nullable=False)
    active = mapped_column(sa.Boolean, nullable=False)
    current_calendar_id = uid()
    latitude = mapped_column(sa.Numeric(9, 6))
    longitude = mapped_column(sa.Numeric(9, 6))
    __table_args__ = owned(
        check("role IN ('HUB', 'BENEFICIARY')", "role"),
        check("latitude BETWEEN -90 AND 90", "latitude"),
        check("longitude BETWEEN -180 AND 180", "longitude"),
        sa.ForeignKeyConstraint(
            ["organization_id", "current_calendar_id", "id"],
            ["site_calendars.organization_id", "site_calendars.id", "site_calendars.site_id"],
            name="fk_site_current_calendar", use_alter=True,
            deferrable=True, initially="DEFERRED",
        ),
    )


class SiteCalendar(OwnedIdentity, Base):
    __tablename__ = "site_calendars"
    site_id = uid(nullable=False)
    timezone = mapped_column(sa.Text, nullable=False)
    revision = mapped_column(sa.BigInteger, nullable=False)
    __table_args__ = owned(
        fk(["site_id"], "sites", ["id"]),
        sa.UniqueConstraint("organization_id", "site_id", "revision"),
        sa.UniqueConstraint("organization_id", "id", "site_id"),
        check("revision > 0", "revision"),
    )


class Category(OwnedIdentity, Base):
    __tablename__ = "categories"
    name = mapped_column(sa.Text, nullable=False)
    active = mapped_column(sa.Boolean, nullable=False)
    __table_args__ = owned()


class Product(OwnedIdentity, Base):
    __tablename__ = "products"
    category_id = uid(nullable=False)
    name = mapped_column(sa.Text, nullable=False)
    base_unit = mapped_column(sa.Text, nullable=False)
    active = mapped_column(sa.Boolean, nullable=False)
    __table_args__ = owned(
        fk(["category_id"], "categories", ["id"]),
        check("length(trim(base_unit)) > 0", "base_unit"),
    )


class Donor(OwnedIdentity, Base):
    __tablename__ = "donors"
    name = mapped_column(sa.Text, nullable=False)
    active = mapped_column(sa.Boolean, nullable=False)
    __table_args__ = owned()


class DataSource(OwnedIdentity, Base):
    __tablename__ = "data_sources"
    name = mapped_column(sa.Text, nullable=False)
    classification = mapped_column(sa.Text, nullable=False)
    __table_args__ = owned(
        check("classification IN ('OBSERVED', 'SIMULATED')", "classification"),
    )


class DemandRecord(OwnedIdentity, Base):
    __tablename__ = "demand_records"
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    local_day = mapped_column(sa.Date, nullable=False)
    source_id = uid(nullable=False)
    source_record_key = mapped_column(sa.Text, nullable=False)
    __table_args__ = owned(
        fk(["site_id"], "sites", ["id"]),
        fk(["product_id"], "products", ["id"]),
        fk(["source_id"], "data_sources", ["id"]),
        sa.UniqueConstraint("organization_id", "source_id", "source_record_key"),
        sa.UniqueConstraint("organization_id", "source_id", "site_id", "product_id", "local_day"),
        sa.UniqueConstraint("organization_id", "id", "site_id"),
        sa.Index("ix_demand_scope_day", "organization_id", "site_id", "product_id", "local_day"),
    )


class DemandRevision(OwnedIdentity, Base):
    __tablename__ = "demand_revisions"
    record_id = uid(nullable=False)
    site_id = uid(nullable=False)
    calendar_version_id = uid(nullable=False)
    revision = mapped_column(sa.BigInteger, nullable=False)
    requested = mapped_column(sa.BigInteger)
    fulfilled = mapped_column(sa.BigInteger)
    unmet = mapped_column(sa.BigInteger)
    __table_args__ = owned(
        fk(["record_id", "site_id"], "demand_records", ["id", "site_id"]),
        fk(["calendar_version_id", "site_id"], "site_calendars", ["id", "site_id"]),
        sa.UniqueConstraint("organization_id", "record_id", "revision"),
        check("revision > 0", "revision"),
        check("requested IS NOT NULL OR fulfilled IS NOT NULL OR unmet IS NOT NULL", "observed"),
        check("requested >= 0 AND fulfilled >= 0 AND unmet >= 0", "counts"),
        check("requested >= fulfilled AND requested >= unmet", "component_bounds"),
        check("requested::numeric = fulfilled::numeric + unmet::numeric", "arithmetic"),
    )


class Receipt(OwnedIdentity, Base):
    __tablename__ = "receipts"
    source_id = uid(nullable=False)
    source_record_key = mapped_column(sa.Text, nullable=False)
    __table_args__ = owned(
        fk(["source_id"], "data_sources", ["id"]),
        sa.UniqueConstraint("organization_id", "source_id", "source_record_key"),
    )


class ReceiptRevision(OwnedIdentity, Base):
    __tablename__ = "receipt_revisions"
    receipt_id = uid(nullable=False)
    receiving_site_id = uid(nullable=False)
    donor_id = uid(nullable=False)
    calendar_version_id = uid(nullable=False)
    revision = mapped_column(sa.BigInteger, nullable=False)
    received_at = instant(nullable=False)
    local_day = mapped_column(sa.Date, nullable=False)
    is_void = mapped_column(sa.Boolean, nullable=False)
    ingest_transaction = mapped_column(sa.BigInteger, nullable=False,
                                       server_default=sa.text("txid_current()"))
    __table_args__ = owned(
        fk(["receipt_id"], "receipts", ["id"]),
        fk(["donor_id"], "donors", ["id"]),
        fk(["calendar_version_id", "receiving_site_id"], "site_calendars", ["id", "site_id"]),
        sa.UniqueConstraint("organization_id", "receipt_id", "revision"),
        sa.UniqueConstraint("organization_id", "id", "receipt_id"),
        sa.UniqueConstraint("organization_id", "id", "receiving_site_id"),
        check("revision > 0", "revision"),
        sa.Index("ix_receipt_day", "organization_id", "receiving_site_id", "local_day"),
    )


class ReceiptLine(OwnedIdentity, Base):
    __tablename__ = "receipt_lines"
    receipt_revision_id = uid(nullable=False)
    line_key = mapped_column(sa.Text, nullable=False)
    product_id = uid(nullable=False)
    received_quantity = mapped_column(sa.BigInteger, nullable=False)
    __table_args__ = owned(
        fk(["receipt_revision_id"], "receipt_revisions", ["id"]),
        fk(["product_id"], "products", ["id"]),
        sa.UniqueConstraint("organization_id", "receipt_revision_id", "line_key"),
        sa.UniqueConstraint("organization_id", "id", "product_id", "receipt_revision_id"),
        check("received_quantity > 0", "quantity"),
    )


class DonationCoverageRevision(OwnedIdentity, Base):
    __tablename__ = "donation_coverage_revisions"
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    source_id = uid(nullable=False)
    calendar_version_id = uid(nullable=False)
    local_day = mapped_column(sa.Date, nullable=False)
    revision = mapped_column(sa.BigInteger, nullable=False)
    complete = mapped_column(sa.Boolean, nullable=False)
    __table_args__ = owned(
        fk(["product_id"], "products", ["id"]),
        fk(["source_id"], "data_sources", ["id"]),
        fk(["calendar_version_id", "site_id"], "site_calendars", ["id", "site_id"]),
        sa.UniqueConstraint("organization_id", "site_id", "product_id", "source_id",
                            "local_day", "revision"),
        check("revision > 0", "revision"),
    )


class InventoryVersion(OwnedIdentity, Base):
    __tablename__ = "inventory_versions"
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    version = mapped_column(sa.BigInteger, nullable=False)
    __table_args__ = owned(
        fk(["site_id"], "sites", ["id"]),
        fk(["product_id"], "products", ["id"]),
        sa.UniqueConstraint("organization_id", "site_id", "product_id"),
        check("version > 0", "version"),
    )


class StockCommand(OwnedIdentity, Base):
    __tablename__ = "stock_commands"
    actor = mapped_column(sa.Text, nullable=False)
    operation = mapped_column(sa.Text, nullable=False)
    reason = mapped_column(sa.Text, nullable=False)
    idempotency_key = mapped_column(sa.Text, nullable=False)
    payload_hash = mapped_column(sa.String(64), nullable=False)
    outcome = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        sa.UniqueConstraint("organization_id", "idempotency_key"),
        check("payload_hash ~ '^[0-9a-f]{64}$'", "payload_hash"),
        check("length(trim(actor)) > 0 AND length(trim(reason)) > 0", "attribution"),
        check("length(trim(idempotency_key)) > 0", "idempotency_key"),
    )


class ReceiptPosting(OwnedIdentity, Base):
    __tablename__ = "receipt_postings"
    receipt_id = uid(nullable=False)
    posted_revision_id = uid(nullable=False)
    command_id = uid(nullable=False)
    __table_args__ = owned(
        fk(["posted_revision_id", "receipt_id"], "receipt_revisions", ["id", "receipt_id"]),
        fk(["command_id"], "stock_commands", ["id"]),
        sa.UniqueConstraint("organization_id", "receipt_id"),
        sa.UniqueConstraint("organization_id", "command_id"),
        sa.UniqueConstraint("organization_id", "id", "receipt_id"),
    )


class InventoryLot(OwnedIdentity, Base):
    __tablename__ = "inventory_lots"
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    receipt_id = uid()
    receipt_line_id = uid()
    receipt_revision_id = uid()
    posting_id = uid()
    batch_key = mapped_column(sa.Text, nullable=False)
    received_at = instant(nullable=False)
    on_hand = mapped_column(sa.BigInteger, nullable=False)
    eligibility = mapped_column(sa.Text, nullable=False)
    expiry_kind = mapped_column(sa.Text, nullable=False)
    expires_on = mapped_column(sa.Date)
    declaration_actor = mapped_column(sa.Text, nullable=False)
    declaration_reason = mapped_column(sa.Text, nullable=False)
    declared_at = instant(nullable=False)
    metadata_version = mapped_column(sa.BigInteger, nullable=False)
    __table_args__ = owned(
        fk(["site_id"], "sites", ["id"]),
        fk(["product_id"], "products", ["id"]),
        fk(["receipt_line_id", "product_id", "receipt_revision_id"], "receipt_lines",
           ["id", "product_id", "receipt_revision_id"]),
        fk(["receipt_revision_id", "site_id"], "receipt_revisions", ["id", "receiving_site_id"]),
        fk(["receipt_revision_id", "receipt_id"], "receipt_revisions", ["id", "receipt_id"]),
        fk(["posting_id", "receipt_id"], "receipt_postings", ["id", "receipt_id"]),
        sa.UniqueConstraint("organization_id", "site_id", "product_id", "batch_key"),
        sa.UniqueConstraint("organization_id", "id", "site_id", "product_id"),
        check("on_hand >= 0 AND metadata_version > 0", "balance_version"),
        check("eligibility IN ('ELIGIBLE', 'HELD', 'INELIGIBLE', 'UNKNOWN')", "eligibility"),
        check("(expiry_kind = 'DATED' AND expires_on IS NOT NULL) OR "
              "(expiry_kind IN ('NON_EXPIRING', 'UNKNOWN') AND expires_on IS NULL)", "expiry"),
        check("num_nonnulls(receipt_id, receipt_line_id, receipt_revision_id, posting_id) "
              "IN (0, 4)", "receipt_linkage"),
        check("length(trim(declaration_actor)) > 0 AND length(trim(declaration_reason)) > 0",
              "declaration"),
        sa.Index("ix_lot_expiry", "organization_id", "site_id", "product_id", "expires_on"),
    )


class StockLedgerEntry(OwnedIdentity, Base):
    __tablename__ = "stock_ledger"
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    lot_id = uid(nullable=False)
    command_id = uid(nullable=False)
    delta = mapped_column(sa.BigInteger, nullable=False)
    effective_at = instant(nullable=False)
    before_version = mapped_column(sa.BigInteger, nullable=False)
    after_version = mapped_column(sa.BigInteger, nullable=False)
    reverses_entry_id = uid()
    __table_args__ = owned(
        fk(["lot_id", "site_id", "product_id"], "inventory_lots", ["id", "site_id", "product_id"]),
        fk(["command_id"], "stock_commands", ["id"]),
        fk(["reverses_entry_id", "lot_id"], "stock_ledger", ["id", "lot_id"]),
        sa.UniqueConstraint("organization_id", "id", "lot_id"),
        sa.UniqueConstraint("organization_id", "command_id", "lot_id"),
        check("delta <> 0", "delta"),
        check("before_version > 0 AND after_version::numeric = before_version::numeric + 1",
              "versions"),
        sa.Index("ix_ledger_lot_time", "organization_id", "lot_id", "recorded_at"),
    )


class AuditEvent(OwnedIdentity, Base):
    __tablename__ = "audit_events"
    command_id = uid(nullable=False)
    event = mapped_column(sa.Text, nullable=False)
    details = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(fk(["command_id"], "stock_commands", ["id"]))


class ReceiptReconciliation(OwnedIdentity, Base):
    __tablename__ = "receipt_reconciliations"
    receipt_id = uid(nullable=False)
    latest_revision_id = uid(nullable=False)
    stock_revision_id = uid()
    needs_reconciliation = mapped_column(sa.Boolean, nullable=False)
    __table_args__ = owned(
        fk(["latest_revision_id", "receipt_id"], "receipt_revisions", ["id", "receipt_id"]),
        fk(["stock_revision_id", "receipt_id"], "receipt_revisions", ["id", "receipt_id"]),
        sa.UniqueConstraint("organization_id", "receipt_id"),
        check("needs_reconciliation OR (stock_revision_id IS NOT NULL "
              "AND stock_revision_id = latest_revision_id)", "consistent"),
    )


class ExpectedSupply(OwnedIdentity, Base):
    __tablename__ = "expected_supplies"
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    source_id = uid(nullable=False)
    source_record_key = mapped_column(sa.Text, nullable=False)
    quantity = mapped_column(sa.BigInteger, nullable=False)
    received_quantity = mapped_column(sa.BigInteger, nullable=False)
    outstanding_confirmed_quantity = mapped_column(sa.BigInteger, nullable=False)
    expected_arrival_at = instant()
    state = mapped_column(sa.Text, nullable=False)
    version = mapped_column(sa.BigInteger, nullable=False)
    __table_args__ = owned(
        fk(["site_id"], "sites", ["id"]),
        fk(["product_id"], "products", ["id"]),
        fk(["source_id"], "data_sources", ["id"]),
        sa.UniqueConstraint("organization_id", "source_id", "source_record_key"),
        sa.UniqueConstraint("organization_id", "id", "site_id", "product_id"),
        check("quantity > 0 AND received_quantity >= 0 "
              "AND outstanding_confirmed_quantity >= 0 AND version > 0", "counts"),
        check("received_quantity::numeric + outstanding_confirmed_quantity::numeric "
              "<= quantity::numeric", "balance"),
        check("state IN ('UNCONFIRMED', 'CONFIRMED', 'CANCELLED', 'RECEIVED')", "state"),
        check("outstanding_confirmed_quantity = 0 OR "
              "(state = 'CONFIRMED' AND expected_arrival_at IS NOT NULL)", "confirmed_arrival"),
        check("state <> 'RECEIVED' OR received_quantity > 0", "received_state"),
        sa.Index("ix_supply_arrival", "organization_id", "site_id", "product_id",
                 "state", "expected_arrival_at"),
    )


class SupplyReceipt(OwnedIdentity, Base):
    """Immutable allocation deltas; a correction appends a linked negative delta."""

    __tablename__ = "supply_receipts"
    supply_id = uid(nullable=False)
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    receipt_line_id = uid(nullable=False)
    receipt_revision_id = uid(nullable=False)
    command_id = uid(nullable=False)
    quantity_delta = mapped_column(sa.BigInteger, nullable=False)
    reverses_allocation_id = uid()
    __table_args__ = owned(
        fk(["supply_id", "site_id", "product_id"], "expected_supplies",
           ["id", "site_id", "product_id"]),
        fk(["receipt_line_id", "product_id", "receipt_revision_id"], "receipt_lines",
           ["id", "product_id", "receipt_revision_id"]),
        fk(["receipt_revision_id", "site_id"], "receipt_revisions", ["id", "receiving_site_id"]),
        fk(["command_id"], "stock_commands", ["id"]),
        fk(["reverses_allocation_id", "supply_id", "receipt_line_id"], "supply_receipts",
           ["id", "supply_id", "receipt_line_id"]),
        sa.UniqueConstraint("organization_id", "id", "supply_id", "receipt_line_id"),
        sa.Index("ix_supply_positive_command", "organization_id", "command_id", "supply_id",
                 "receipt_line_id", unique=True,
                 postgresql_where=sa.text("reverses_allocation_id IS NULL")),
        sa.Index("ix_supply_reversal_command", "organization_id", "command_id",
                 "reverses_allocation_id", unique=True,
                 postgresql_where=sa.text("reverses_allocation_id IS NOT NULL")),
        check("quantity_delta <> 0", "delta"),
        check("(quantity_delta < 0) = (reverses_allocation_id IS NOT NULL)", "reversal"),
    )
