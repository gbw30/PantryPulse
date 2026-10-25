"""Small persistence primitives; caller owns the transaction and authorization.

These are not CSV imports, public endpoints, or stock-posting services.
"""

from uuid import UUID, uuid4

from sqlalchemy import select

from app.models.operational import (
    DataSource,
    Receipt,
    ReceiptLine,
    ReceiptReconciliation,
    ReceiptRevision,
)
from app.schemas.operational import ReceiptRevision as ReceiptContract


def tenant_get(session, model, organization_id: UUID, record_id: UUID):
    return session.scalar(select(model).where(
        model.organization_id == organization_id, model.id == record_id
    ))


def append_receipt_revision(session, value: ReceiptContract):
    """Persist one complete historical revision and lines, never current stock."""
    # Serialize factual revisions with stock posting/reconciliation of this receipt.
    receipt = session.scalar(select(Receipt).where(
        Receipt.organization_id == value.organization_id, Receipt.id == value.receipt_id,
    ).with_for_update())
    source = tenant_get(session, DataSource, value.organization_id, value.source_id)
    if receipt is None or source is None:
        raise ValueError("receipt/source not found in organization")
    if (receipt.source_id != value.source_id
            or receipt.source_record_key != value.source_record_key
            or source.classification != value.source_classification):
        raise ValueError("receipt/source provenance mismatch")
    row = ReceiptRevision(
        organization_id=value.organization_id, id=value.revision_id,
        receipt_id=value.receipt_id, receiving_site_id=value.receiving_site_id,
        donor_id=value.donor_id, calendar_version_id=value.calendar_version_id,
        revision=value.revision, received_at=value.received_at, local_day=value.local_day,
        recorded_at=value.recorded_at, is_void=value.is_void,
    )
    session.add(row)
    session.flush()
    for line in value.lines:
        session.add(ReceiptLine(
            organization_id=value.organization_id, id=uuid4(),
            receipt_revision_id=value.revision_id, line_key=line.line_key,
            product_id=line.product_id, received_quantity=line.quantity,
            recorded_at=value.recorded_at,
        ))
    session.flush()
    marker = session.scalar(select(ReceiptReconciliation).where(
        ReceiptReconciliation.organization_id == value.organization_id,
        ReceiptReconciliation.receipt_id == value.receipt_id,
    ).with_for_update())
    if marker is not None:
        latest = session.scalar(select(ReceiptRevision).where(
            ReceiptRevision.organization_id == value.organization_id,
            ReceiptRevision.receipt_id == value.receipt_id,
        ).order_by(ReceiptRevision.revision.desc()).limit(1))
        marker.latest_revision_id = latest.id
        marker.needs_reconciliation = marker.stock_revision_id != latest.id
        session.flush()
    return row
