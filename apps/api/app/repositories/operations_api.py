"""Operational HTTP transactions with immutable command replay and scoped sources."""

import hashlib
import json
from datetime import date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import operational as m
from app.models.http_commands import HTTPCommand
from app.repositories.import_feedback import imported_row
from app.repositories.operational import append_receipt_revision
from app.schemas.operational import DemandQuantities, ReceiptRevision
from app.schemas.stock import (
    ConfirmSupply,
    DeclareLot,
    PostReceipt,
    ReconcileReceipt,
    StockActor,
)
from app.services.inventory.stock import StockError, execute_stock


def wire(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, UUID, datetime, date)):
        return str(value) if not isinstance(value, (datetime, date)) else value.isoformat()
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    return value


def owned(session, model, org, identity, *, lock=False):
    query = sa.select(model).where(model.organization_id == org, model.id == identity)
    row = session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise StockError("NOT_FOUND", 404)
    return row


def row_data(row):
    return wire({column.name: getattr(row, column.name) for column in row.__table__.columns})


def journal(session, scope, operation, key, payload, create):
    session.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || :key, 0))"),
        {
            "key": f"vp-operational:{scope.organization_id}",
        },
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    actor = str(scope.actor_ref)
    session.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || :key, 0))"),
        {
            "key": f"http:{scope.organization_id}:{actor}:{operation}:{key}",
        },
    )
    previous = session.scalar(
        sa.select(HTTPCommand).where(
            HTTPCommand.organization_id == scope.organization_id,
            HTTPCommand.actor == actor,
            HTTPCommand.operation == operation,
            HTTPCommand.key == key,
        )
    )
    if previous is not None:
        if previous.request_hash != digest:
            raise StockError("IDEMPOTENCY_CONFLICT")
        return dict(command_id=previous.id, operation=operation, result=previous.result)
    result = wire(create())
    command = HTTPCommand(
        id=uuid4(),
        organization_id=scope.organization_id,
        actor=actor,
        operation=operation,
        key=key,
        request_hash=digest,
        result=result,
    )
    session.add(command)
    session.flush()
    return dict(command_id=command.id, operation=operation, result=result)


def transact(engine, action):
    with Session(engine) as session, session.begin():
        session.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
        result = action(session)
    return result


def receipt_write(session, scope, body, receipt_id=None):
    org = scope.organization_id
    source = owned(session, m.DataSource, org, body.source_id)
    site = owned(session, m.Site, org, body.site_id)
    calendar = owned(session, m.SiteCalendar, org, site.current_calendar_id)
    owned(session, m.Donor, org, body.donor_id)
    for line in body.lines:
        owned(session, m.Product, org, line.product_id)
    now = session.scalar(sa.select(sa.func.clock_timestamp()))
    if body.received_at > now:
        raise StockError("FUTURE_RECEIPT", 422)
    if receipt_id is None:
        if body.expected_revision is not None:
            raise StockError("NEW_RECEIPT_HAS_NO_REVISION", 422)
        receipt = m.Receipt(
            id=uuid4(),
            organization_id=org,
            source_id=source.id,
            source_record_key=body.source_record_key,
        )
        session.add(receipt)
        session.flush()
        number = 1
    else:
        receipt = owned(session, m.Receipt, org, receipt_id, lock=True)
        if (receipt.source_id, receipt.source_record_key) != (source.id, body.source_record_key):
            raise StockError("RECEIPT_SOURCE_MISMATCH", 422)
        latest = session.scalar(
            sa.select(sa.func.max(m.ReceiptRevision.revision)).where(
                m.ReceiptRevision.organization_id == org,
                m.ReceiptRevision.receipt_id == receipt_id,
            )
        )
        if body.expected_revision is None or latest != int(body.expected_revision):
            raise StockError("STALE_RECEIPT_REVISION")
        number = latest + 1
    value = ReceiptRevision(
        organization_id=org,
        receipt_id=receipt.id,
        revision_id=uuid4(),
        revision=number,
        source_id=source.id,
        source_record_key=receipt.source_record_key,
        source_classification=source.classification,
        receiving_site_id=site.id,
        donor_id=body.donor_id,
        received_at=body.received_at,
        recorded_at=now,
        local_day=body.received_at.astimezone(ZoneInfo(calendar.timezone)).date(),
        calendar_version_id=calendar.id,
        timezone=calendar.timezone,
        is_void=body.is_void,
        lines=tuple(
            dict(line_key=line.line_key, product_id=line.product_id, quantity=int(line.quantity))
            for line in body.lines
        ),
    )
    row = append_receipt_revision(session, value)
    return dict(
        receipt_id=receipt.id,
        revision_id=row.id,
        revision=number,
        stock_changed=False,
        is_void=row.is_void,
    )


def receipt_read(session, scope, receipt_id):
    receipt = owned(session, m.Receipt, scope.organization_id, receipt_id)
    revisions = list(
        session.scalars(
            sa.select(m.ReceiptRevision)
            .where(
                m.ReceiptRevision.organization_id == scope.organization_id,
                m.ReceiptRevision.receipt_id == receipt_id,
            )
            .order_by(m.ReceiptRevision.revision)
            .limit(101)
        )
    )
    if len(revisions) > 100:
        raise StockError("RECEIPT_HISTORY_TOO_LARGE", 422)
    ids = [row.id for row in revisions]
    lines = list(
        session.scalars(
            sa.select(m.ReceiptLine)
            .where(
                m.ReceiptLine.organization_id == scope.organization_id,
                m.ReceiptLine.receipt_revision_id.in_(ids),
            )
            .order_by(m.ReceiptLine.line_key)
            .limit(10001)
        )
    )
    if len(lines) > 10000:
        raise StockError("RECEIPT_HISTORY_TOO_LARGE", 422)
    marker = session.scalar(
        sa.select(m.ReceiptReconciliation).where(
            m.ReceiptReconciliation.organization_id == scope.organization_id,
            m.ReceiptReconciliation.receipt_id == receipt_id,
        )
    )
    return dict(
        receipt=row_data(receipt),
        revisions=[
            dict(
                **row_data(row),
                lines=[row_data(line) for line in lines if line.receipt_revision_id == row.id],
            )
            for row in revisions
        ],
        reconciliation=row_data(marker) if marker else None,
    )


def stock_write(session, scope, key, operation, body, identity):
    org = scope.organization_id
    data = body.model_dump(mode="python")
    data["idempotency_key"] = key
    if operation in {"post", "reconcile"}:
        revision = owned(session, m.ReceiptRevision, org, body.revision_id)
        if revision.receipt_id != identity:
            raise StockError("NOT_FOUND", 404)
        for field in ("expected_versions", "supply_versions"):
            for item in data[field]:
                item["version"] = int(item["version"])
        for item in data["supply_matches"]:
            item["quantity"] = int(item["quantity"])
        request = (PostReceipt if operation == "post" else ReconcileReceipt)(**data)
    else:
        model = m.InventoryLot if operation == "declare" else m.ExpectedSupply
        row = owned(session, model, org, identity)
        version = int(data.pop("expected_inventory_version"))
        data["expected_versions"] = (
            dict(
                site_id=row.site_id,
                product_id=row.product_id,
                version=version,
            ),
        )
        if operation == "declare":
            request = DeclareLot(lot_id=identity, **data)
        else:
            data["expected_supply_version"] = int(data["expected_supply_version"])
            data["outstanding_quantity"] = int(data["outstanding_quantity"])
            request = ConfirmSupply(supply_id=identity, **data)
    outcome = execute_stock(
        session, StockActor(organization_id=org, actor=str(scope.actor_ref)), request
    )
    return dict(command_id=outcome["command_id"], operation=operation, result=wire(outcome))


MAX_ACTIVE_PRODUCTS = 8  # planning.MAX_PLANNING_PRODUCTS


def product_create(session, scope, body):
    org = scope.organization_id
    active = list(
        session.scalars(
            sa.select(m.Product).where(m.Product.organization_id == org, m.Product.active.is_(True))
        )
    )
    name = body.name.strip()
    if any(row.name.strip().casefold() == name.casefold() for row in active):
        raise StockError("PRODUCT_EXISTS", 409)
    if len(active) >= MAX_ACTIVE_PRODUCTS:
        raise StockError("PRODUCT_LIMIT_REACHED", 409)
    category_name = (body.category_name or name).strip()
    category = session.scalar(
        sa.select(m.Category).where(
            m.Category.organization_id == org,
            sa.func.lower(m.Category.name) == category_name.casefold(),
            m.Category.active.is_(True),
        )
    )
    if category is None:
        category = m.Category(id=uuid4(), organization_id=org, name=category_name, active=True)
        session.add(category)
        session.flush()
    row = m.Product(
        id=uuid4(),
        organization_id=org,
        category_id=category.id,
        name=name,
        base_unit=body.base_unit.strip(),
        active=True,
    )
    session.add(row)
    session.flush()
    return row_data(row)


def supply_create(session, scope, body):
    org = scope.organization_id
    for model, identity in (
        (m.Site, body.site_id),
        (m.Product, body.product_id),
        (m.DataSource, body.source_id),
    ):
        owned(session, model, org, identity)
    row = m.ExpectedSupply(
        id=uuid4(),
        organization_id=org,
        site_id=body.site_id,
        product_id=body.product_id,
        source_id=body.source_id,
        source_record_key=body.source_record_key,
        quantity=int(body.quantity),
        received_quantity=0,
        outstanding_confirmed_quantity=0,
        expected_arrival_at=None,
        state="UNCONFIRMED",
        version=1,
    )
    session.add(row)
    session.flush()
    return row_data(row)


def import_history(session, scope, body, *, coverage=False):
    org = scope.organization_id
    owned(session, m.DataSource, org, body.source_id)
    inserted = []
    keys = set()
    for index, item in enumerate(body.rows):
        with imported_row(index, len(body.rows)):
            key = (item.site_id, item.product_id, item.day)
            if key in keys:
                raise StockError("DUPLICATE_IMPORT_DAY", 422)
            keys.add(key)
            site = owned(session, m.Site, org, item.site_id)
            owned(session, m.Product, org, item.product_id)
            calendar = owned(session, m.SiteCalendar, org, site.current_calendar_id)
            now = session.scalar(sa.select(sa.func.clock_timestamp()))
            if item.day > now.astimezone(ZoneInfo(calendar.timezone)).date():
                raise StockError("FUTURE_HISTORY", 422)
            # Serialize both day and external-key membership across concurrent imports.
            session.execute(
                sa.text(
                    "SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || :key, 0))"
                ),
                {
                    "key": f"import:{org}:{body.source_id}",
                },
            )
            if coverage:
                existing = session.scalar(
                    sa.select(sa.func.max(m.DonationCoverageRevision.revision)).where(
                        m.DonationCoverageRevision.organization_id == org,
                        m.DonationCoverageRevision.site_id == item.site_id,
                        m.DonationCoverageRevision.product_id == item.product_id,
                        m.DonationCoverageRevision.source_id == body.source_id,
                        m.DonationCoverageRevision.local_day == item.day,
                    )
                )
            else:
                record = session.scalar(
                    sa.select(m.DemandRecord)
                    .where(
                        m.DemandRecord.organization_id == org,
                        m.DemandRecord.source_id == body.source_id,
                        m.DemandRecord.source_record_key == item.source_record_key,
                    )
                    .with_for_update()
                )
                if record and (record.site_id, record.product_id, record.local_day) != key:
                    raise StockError("SOURCE_RECORD_SCOPE_MISMATCH", 422)
                existing = (
                    None
                    if record is None
                    else session.scalar(
                        sa.select(
                            sa.func.max(m.DemandRevision.revision),
                        ).where(m.DemandRevision.record_id == record.id)
                    )
                )
            expected = None if item.expected_revision is None else int(item.expected_revision)
            if existing != expected:
                raise StockError("STALE_HISTORY_REVISION")
            revision = (existing or 0) + 1
            values = dict(
                id=uuid4(),
                organization_id=org,
                site_id=site.id,
                calendar_version_id=calendar.id,
                revision=revision,
            )
            if coverage:
                row = m.DonationCoverageRevision(
                    **values,
                    product_id=item.product_id,
                    source_id=body.source_id,
                    local_day=item.day,
                    complete=item.complete,
                )
            else:
                quantities = DemandQuantities(
                    **{
                        field: None if getattr(item, field) is None else int(getattr(item, field))
                        for field in ("requested", "fulfilled", "unmet")
                    }
                )
                if all(value is None for value in quantities.model_dump().values()):
                    raise StockError("EMPTY_DEMAND_OBSERVATION", 422)
                if record is None:
                    record = m.DemandRecord(
                        id=uuid4(),
                        organization_id=org,
                        site_id=site.id,
                        product_id=item.product_id,
                        local_day=item.day,
                        source_id=body.source_id,
                        source_record_key=item.source_record_key,
                    )
                    session.add(record)
                    session.flush()
                row = m.DemandRevision(**values, record_id=record.id, **quantities.model_dump())
            session.add(row)
            session.flush()
            inserted.append(
                dict(
                    revision_id=row.id,
                    revision=revision,
                    site_id=site.id,
                    product_id=item.product_id,
                    day=item.day,
                )
            )
    return dict(
        rows=inserted,
        stock_changed=False,
        atomic=True,
        accepted_count=str(len(inserted)),
        rejected_count="0",
    )
