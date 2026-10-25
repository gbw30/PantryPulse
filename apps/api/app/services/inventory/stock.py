"""Atomic internal inventory services. Caller authorizes and owns the transaction.

Every operation has a savepoint: failure rolls back its own changes. No service
commits, reserves a plan, dispatches goods or calls forecasting/worker code.
"""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from app.models import operational as m
from app.schemas.stock import AdjustStock, ConfirmSupply, DeclareLot, PostReceipt, ReconcileReceipt

MAX_COUNT = 2**63 - 1


class StockError(ValueError):
    def __init__(self, code, status=409):
        self.code = code
        self.status = status
        super().__init__(code)


def _canonical(value):
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return str(value) if hasattr(value, "hex") else value


def command_hash(actor, request):
    content = {"actor": actor.model_dump(), "operation": type(request).__name__,
               "payload": request.model_dump()}
    encoded = json.dumps(_canonical(content), sort_keys=True, separators=(",", ":"),
                         allow_nan=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _get(session, model, actor, identity, lock=False):
    query = sa.select(model).where(model.organization_id == actor.organization_id,
                                   model.id == identity).execution_options(populate_existing=True)
    row = session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise StockError("NOT_FOUND", 404)
    return row


def _versions(session, actor, expectations, affected):
    wanted = {(item.site_id, item.product_id): item.version for item in expectations}
    if set(wanted) != set(affected):
        raise StockError("VERSION_SCOPE_MISMATCH", 422)
    rows = {}
    for site_id, product_id in sorted(affected, key=lambda pair: tuple(map(str, pair))):
        _get(session, m.Site, actor, site_id)
        _get(session, m.Product, actor, product_id)
        session.execute(insert(m.InventoryVersion).values(
            id=uuid4(), organization_id=actor.organization_id, site_id=site_id,
            product_id=product_id, version=1,
        ).on_conflict_do_nothing(index_elements=["organization_id", "site_id", "product_id"]))
        row = session.scalar(sa.select(m.InventoryVersion).where(
            m.InventoryVersion.organization_id == actor.organization_id,
            m.InventoryVersion.site_id == site_id, m.InventoryVersion.product_id == product_id,
        ).with_for_update().execution_options(populate_existing=True))
        if row.version != wanted[(site_id, product_id)]:
            raise StockError("STALE_INVENTORY_VERSION")
        if row.version == MAX_COUNT:
            raise StockError("VERSION_OVERFLOW", 422)
        rows[(site_id, product_id)] = row
    return rows


@dataclass
class Plan:
    versions: dict
    # Each entry is (lot, quantity delta, optional declaration, is_new).
    lots: list = field(default_factory=list)
    details: dict = field(default_factory=dict)
    posting: object = None
    reconciliation: object = None
    target_revision: object = None
    supplies: list = field(default_factory=list)
    allocations: list = field(default_factory=list)


def _save(session, actor, request, plan, now):
    identity = uuid4()
    version_result = [{"site_id": str(site), "product_id": str(product),
                       "before": row.version, "after": row.version + 1}
                      for (site, product), row in sorted(
                          plan.versions.items(), key=lambda item: tuple(map(str, item[0])))]
    lot_result = []
    for lot, delta, _declaration, _is_new in plan.lots:
        if not _is_new:
            ledger_balance = session.scalar(sa.select(sa.func.coalesce(
                sa.func.sum(m.StockLedgerEntry.delta), 0
            )).where(m.StockLedgerEntry.organization_id == actor.organization_id,
                     m.StockLedgerEntry.lot_id == lot.id))
            if ledger_balance != lot.on_hand:
                raise StockError("LEDGER_BALANCE_MISMATCH")
        next_quantity = lot.on_hand + delta
        if not 0 <= next_quantity <= MAX_COUNT:
            raise StockError("INSUFFICIENT_STOCK" if next_quantity < 0 else "COUNT_OVERFLOW", 422)
        change = {"lot_id": str(lot.id), "before": lot.on_hand, "after": next_quantity}
        if _declaration is not None:
            change["declaration"] = {
                "before": None if _is_new else {
                    "eligibility": lot.eligibility, "expiry_kind": lot.expiry_kind,
                    "expires_on": str(lot.expires_on) if lot.expires_on else None,
                },
                "after": {"eligibility": _declaration.eligibility,
                          "expiry_kind": _declaration.expiry.kind,
                          "expires_on": str(_declaration.expiry.expires_on)
                          if _declaration.expiry.expires_on else None},
            }
        lot_result.append(change)
    supply_result = [{
        "supply_id": str(row.id),
        "before": {"received": row.received_quantity,
                   "outstanding_confirmed": row.outstanding_confirmed_quantity,
                   "version": row.version, "state": row.state},
        "after": {"received": received, "outstanding_confirmed": outstanding,
                  "version": row.version + 1, "state": state,
                  "arrival": arrival.astimezone(UTC).isoformat() if arrival else None},
    } for row, received, outstanding, state, arrival in plan.supplies]
    outcome = {"status": "APPLIED", "command_id": str(identity),
               "inventory_versions": version_result, "lots": lot_result,
               "supplies": supply_result, **plan.details}
    session.add(m.StockCommand(
        id=identity, organization_id=actor.organization_id, actor=actor.actor,
        operation=type(request).__name__, reason=request.reason,
        idempotency_key=request.idempotency_key, payload_hash=command_hash(actor, request),
        outcome=outcome, recorded_at=now,
    ))
    session.flush()
    if plan.posting is not None:
        plan.posting.command_id = identity
        session.add(plan.posting)
        session.flush()
    for lot, delta, declaration, is_new in plan.lots:
        lot.on_hand += delta
        if declaration is not None:
            if not is_new:
                lot.metadata_version += 1
            lot.eligibility = declaration.eligibility
            lot.expiry_kind = declaration.expiry.kind
            lot.expires_on = declaration.expiry.expires_on
            lot.declaration_actor = actor.actor
            lot.declaration_reason = request.reason
            lot.declared_at = now
        session.add(lot)
    session.flush()
    for lot, delta, _, _ in plan.lots:
        if delta:
            version = plan.versions[(lot.site_id, lot.product_id)].version
            session.add(m.StockLedgerEntry(
                id=uuid4(), organization_id=actor.organization_id, site_id=lot.site_id,
                product_id=lot.product_id, lot_id=lot.id, command_id=identity, delta=delta,
                effective_at=now, before_version=version, after_version=version + 1,
                recorded_at=now,
            ))
    for supply, received, outstanding, state, arrival in plan.supplies:
        supply.received_quantity = received
        supply.outstanding_confirmed_quantity = outstanding
        supply.state, supply.expected_arrival_at = state, arrival
        supply.version += 1
    session.flush()
    for values in plan.allocations:  # reversals precede positive additions
        session.add(m.SupplyReceipt(id=uuid4(), organization_id=actor.organization_id,
                                   command_id=identity, recorded_at=now, **values))
        session.flush()
    for version in plan.versions.values():
        version.version += 1
    if plan.reconciliation is not None:
        plan.reconciliation.latest_revision_id = plan.target_revision.id
        plan.reconciliation.stock_revision_id = plan.target_revision.id
        plan.reconciliation.needs_reconciliation = False
        session.add(plan.reconciliation)
    session.add(m.AuditEvent(id=uuid4(), organization_id=actor.organization_id,
                            command_id=identity, event=type(request).__name__,
                            details=deepcopy(outcome), recorded_at=now))
    session.flush()
    return deepcopy(outcome)


def execute_stock(session, actor, request):
    """Use an authenticated internal StockActor. Returned success is pending caller commit."""
    if not isinstance(request, (PostReceipt, ReconcileReceipt, AdjustStock, DeclareLot,
                                ConfirmSupply)):
        raise TypeError("unsupported stock request")
    with session.begin_nested():
        session.execute(sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {
            "key": f"vp-operational:{actor.organization_id}",
        })
        session.execute(sa.text(
            "SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || :key, 0))"
        ), {"key": f":stock:{actor.organization_id}:{request.idempotency_key}"})
        old = session.scalar(sa.select(m.StockCommand).where(
            m.StockCommand.organization_id == actor.organization_id,
            m.StockCommand.idempotency_key == request.idempotency_key,
        ))
        if old is not None:
            if old.payload_hash != command_hash(actor, request):
                raise StockError("IDEMPOTENCY_CONFLICT")
            return deepcopy(old.outcome)
        now = session.scalar(sa.select(sa.func.clock_timestamp()))
        if isinstance(request, (PostReceipt, ReconcileReceipt)):
            plan = _receipt_plan(session, actor, request, now)
        elif isinstance(request, (AdjustStock, DeclareLot)):
            plan = _adjustment_plan(session, actor, request)
        else:
            plan = _confirmation_plan(session, actor, request)
        return _save(session, actor, request, plan, now)


def _adjustment_plan(session, actor, request):
    changes = ([(item.lot_id, item.delta) for item in request.changes]
               if isinstance(request, AdjustStock) else [(request.lot_id, 0)])
    lots = [_get(session, m.InventoryLot, actor, identity) for identity, _ in changes]
    versions = _versions(session, actor, request.expected_versions,
                         {(lot.site_id, lot.product_id) for lot in lots})
    entries = []
    for identity, delta in sorted(changes, key=lambda value: str(value[0])):
        lot = _get(session, m.InventoryLot, actor, identity, lock=True)
        if isinstance(request, DeclareLot) and lot.metadata_version == MAX_COUNT:
            raise StockError("VERSION_OVERFLOW", 422)
        entries.append((lot, delta, request if isinstance(request, DeclareLot) else None, False))
    details = ({"source_reference": request.source_reference}
               if isinstance(request, AdjustStock) else {"metadata_change": True})
    return Plan(versions=versions, lots=entries, details=details)


def _receipt_plan(session, actor, request, now):
    target = _get(session, m.ReceiptRevision, actor, request.revision_id)
    _get(session, m.Receipt, actor, target.receipt_id, lock=True)
    latest = session.scalar(sa.select(m.ReceiptRevision).where(
        m.ReceiptRevision.organization_id == actor.organization_id,
        m.ReceiptRevision.receipt_id == target.receipt_id,
    ).order_by(m.ReceiptRevision.revision.desc()).limit(1))
    if latest.id != target.id:
        raise StockError("STALE_RECEIPT_REVISION")
    posting = session.scalar(sa.select(m.ReceiptPosting).where(
        m.ReceiptPosting.organization_id == actor.organization_id,
        m.ReceiptPosting.receipt_id == target.receipt_id,
    ))
    is_post = isinstance(request, PostReceipt)
    if is_post and (posting is not None or target.is_void):
        raise StockError("RECEIPT_ALREADY_POSTED_OR_VOID")
    if not is_post and posting is None:
        raise StockError("RECEIPT_NOT_POSTED")
    marker = session.scalar(sa.select(m.ReceiptReconciliation).where(
        m.ReceiptReconciliation.organization_id == actor.organization_id,
        m.ReceiptReconciliation.receipt_id == target.receipt_id,
    ))
    if not is_post and (marker is None or marker.stock_revision_id == target.id):
        raise StockError("RECEIPT_ALREADY_RECONCILED")
    old_revision = (None if is_post else _get(
        session, m.ReceiptRevision, actor, marker.stock_revision_id))
    new_lines = list(session.scalars(sa.select(m.ReceiptLine).where(
        m.ReceiptLine.organization_id == actor.organization_id,
        m.ReceiptLine.receipt_revision_id == target.id,
    )))
    old_lines = ([] if old_revision is None else list(session.scalars(
        sa.select(m.ReceiptLine).where(
        m.ReceiptLine.organization_id == actor.organization_id,
        m.ReceiptLine.receipt_revision_id == old_revision.id,
    ))))
    affected = {(target.receiving_site_id, line.product_id) for line in new_lines}
    if old_revision:
        affected |= {(old_revision.receiving_site_id, line.product_id) for line in old_lines}
    versions = _versions(session, actor, request.expected_versions, affected)
    declarations = {item.line_key: item for item in request.declarations}
    if not set(declarations) <= {line.line_key for line in new_lines}:
        raise StockError("DECLARATION_SCOPE_MISMATCH", 422)
    if is_post and set(declarations) != {line.line_key for line in new_lines}:
        raise StockError("DECLARATION_REQUIRED", 422)
    if is_post:
        posting = m.ReceiptPosting(id=uuid4(), organization_id=actor.organization_id,
                                   receipt_id=target.receipt_id, posted_revision_id=target.id,
                                   recorded_at=now)
        marker = m.ReceiptReconciliation(id=uuid4(), organization_id=actor.organization_id,
                                         receipt_id=target.receipt_id, recorded_at=now)
    lot_rows = session.execute(sa.select(m.InventoryLot, m.ReceiptLine.line_key).join(
        m.ReceiptLine, m.ReceiptLine.id == m.InventoryLot.receipt_line_id,
    ).where(m.InventoryLot.organization_id == actor.organization_id,
            m.InventoryLot.receipt_id == target.receipt_id).order_by(m.InventoryLot.id)
        .with_for_update(of=m.InventoryLot).execution_options(populate_existing=True)).all()
    existing = {(lot.site_id, lot.product_id, key): lot for lot, key in lot_rows}
    previous = {
        (old_revision.receiving_site_id, line.product_id, line.line_key): line.received_quantity
        for line in old_lines
    }
    desired = {
        (target.receiving_site_id, line.product_id, line.line_key): line for line in new_lines
    }
    entries = []
    for key in sorted(previous.keys() | desired.keys(), key=str):
        line = desired.get(key)
        delta = (line.received_quantity if line else 0) - previous.get(key, 0)
        declaration = declarations.get(key[2]) if line else None
        lot = existing.get(key)
        is_new = lot is None
        if is_new:
            if line is None or declaration is None:
                raise StockError("DECLARATION_REQUIRED", 422)
            lot = m.InventoryLot(
                id=uuid4(), organization_id=actor.organization_id,
                site_id=key[0], product_id=key[1],
                receipt_id=target.receipt_id, receipt_line_id=line.id,
                receipt_revision_id=target.id, posting_id=posting.id,
                batch_key=f"{target.receipt_id}:{hashlib.sha256(key[2].encode()).hexdigest()}",
                received_at=target.received_at, on_hand=0, metadata_version=1, recorded_at=now,
            )
        if delta or declaration is not None:
            if declaration is not None and not is_new and lot.metadata_version == MAX_COUNT:
                raise StockError("VERSION_OVERFLOW", 422)
            entries.append((lot, delta, declaration, is_new))
    plan = Plan(versions=versions, lots=entries, reconciliation=marker, target_revision=target,
                posting=posting if is_post else None,
                details={"receipt_id": str(target.receipt_id), "revision_id": str(target.id),
                         "void": target.is_void})
    _supply_plan(session, actor, request, target, new_lines, plan)
    return plan


def _supply_plan(session, actor, request, target, lines, plan):
    rows = session.execute(sa.select(m.SupplyReceipt, m.ReceiptLine.line_key).join(
        m.ReceiptLine, m.ReceiptLine.id == m.SupplyReceipt.receipt_line_id,
    ).join(m.ReceiptRevision, m.ReceiptRevision.id == m.ReceiptLine.receipt_revision_id).where(
        m.SupplyReceipt.organization_id == actor.organization_id,
        m.ReceiptRevision.receipt_id == target.receipt_id,
    )).all()
    current = {}
    for allocation, key in rows:
        pair = (key, allocation.site_id, allocation.product_id, allocation.supply_id)
        current[pair] = current.get(pair, 0) + allocation.quantity_delta
    by_key = {line.line_key: line for line in lines}
    desired = {}
    for item in request.supply_matches:
        line = by_key.get(item.line_key)
        if line is None:
            raise StockError("SUPPLY_MATCH_LINE_MISSING", 422)
        pair = (item.line_key, target.receiving_site_id, line.product_id, item.supply_id)
        desired[pair] = item.quantity
    for key, line in by_key.items():
        matched = sum(amount for pair, amount in desired.items() if pair[0] == key)
        if matched > line.received_quantity:
            raise StockError("SUPPLY_MATCH_EXCEEDS_RECEIPT", 422)
    ids = {pair[3] for pair in current if current[pair]} | {pair[3] for pair in desired}
    expected = {item.supply_id: item.version for item in request.supply_versions}
    if set(expected) != ids:
        raise StockError("SUPPLY_VERSION_SCOPE_MISMATCH", 422)
    supplies = {}
    for identity in sorted(ids, key=str):
        row = _get(session, m.ExpectedSupply, actor, identity, lock=True)
        if row.version != expected[identity]:
            raise StockError("STALE_SUPPLY_VERSION")
        if row.version == MAX_COUNT:
            raise StockError("VERSION_OVERFLOW", 422)
        allocated = session.scalar(sa.select(sa.func.coalesce(
            sa.func.sum(m.SupplyReceipt.quantity_delta), 0
        )).where(m.SupplyReceipt.organization_id == actor.organization_id,
                 m.SupplyReceipt.supply_id == row.id))
        if allocated != row.received_quantity:
            raise StockError("SUPPLY_BALANCE_MISMATCH")
        supplies[identity] = row
    pending = []
    net = {}
    for pair in sorted(current.keys() | desired.keys(), key=str):
        key, site_id, product_id, supply_id = pair
        delta = desired.get(pair, 0) - current.get(pair, 0)
        if not delta:
            continue
        supply = supplies[supply_id]
        if (supply.site_id, supply.product_id) != (site_id, product_id):
            raise StockError("SUPPLY_SCOPE_MISMATCH", 422)
        net[supply_id] = net.get(supply_id, 0) + delta
        if delta > 0:
            line = by_key[key]
            pending.append(dict(supply_id=supply_id, site_id=site_id, product_id=product_id,
                                receipt_line_id=line.id, receipt_revision_id=target.id,
                                quantity_delta=delta))
        else:
            remaining = -delta
            positives = sorted((row for row, line_key in rows if line_key == key
                                and row.supply_id == supply_id and row.site_id == site_id
                                and row.product_id == product_id and row.quantity_delta > 0),
                               key=lambda row: str(row.id))
            for original in positives:
                available = original.quantity_delta + sum(
                    row.quantity_delta for row, _ in rows
                    if row.reverses_allocation_id == original.id)
                take = min(remaining, available)
                if take:
                    pending.append(dict(supply_id=supply_id, site_id=site_id, product_id=product_id,
                                        receipt_line_id=original.receipt_line_id,
                                        receipt_revision_id=original.receipt_revision_id,
                                        quantity_delta=-take, reverses_allocation_id=original.id))
                    remaining -= take
                if not remaining:
                    break
            if remaining:
                raise StockError("ALLOCATION_HISTORY_MISMATCH")
    for identity, delta in net.items():
        row = supplies[identity]
        received = row.received_quantity + delta
        outstanding = row.outstanding_confirmed_quantity - max(delta, 0)
        if not (0 <= received <= row.quantity and 0 <= outstanding <= row.quantity - received):
            raise StockError("SUPPLY_NOT_CONFIRMED_OR_EXCEEDED", 422)
        state = ("CONFIRMED" if outstanding else "RECEIVED" if received else
                 "CANCELLED" if row.state == "CANCELLED" else "UNCONFIRMED")
        plan.supplies.append((row, received, outstanding, state, row.expected_arrival_at))
    plan.allocations = sorted(pending, key=lambda item: item["quantity_delta"] > 0)


def _confirmation_plan(session, actor, request):
    initial = _get(session, m.ExpectedSupply, actor, request.supply_id)
    versions = _versions(session, actor, request.expected_versions,
                         {(initial.site_id, initial.product_id)})
    row = _get(session, m.ExpectedSupply, actor, request.supply_id, lock=True)
    if row.version != request.expected_supply_version:
        raise StockError("STALE_SUPPLY_VERSION")
    allocated = session.scalar(sa.select(sa.func.coalesce(
        sa.func.sum(m.SupplyReceipt.quantity_delta), 0
    )).where(m.SupplyReceipt.organization_id == actor.organization_id,
             m.SupplyReceipt.supply_id == row.id))
    if allocated != row.received_quantity:
        raise StockError("SUPPLY_BALANCE_MISMATCH")
    if (row.version == MAX_COUNT
            or row.received_quantity + request.outstanding_quantity > row.quantity):
        raise StockError("SUPPLY_CAPACITY_EXCEEDED", 422)
    state = ("CANCELLED" if request.cancel else "CONFIRMED" if request.outstanding_quantity
             else "RECEIVED" if row.received_quantity else "UNCONFIRMED")
    return Plan(versions=versions,
                supplies=[(row, row.received_quantity, request.outstanding_quantity,
                           state, request.expected_arrival_at)],
                details={"supply_id": str(row.id), "supply_version": row.version + 1})


def eligible_lots(session, organization_id, on_day: date):
    """Saved usable stock only; not a donor-budget, reservation or route calculation."""
    return list(session.scalars(sa.select(m.InventoryLot).where(
        m.InventoryLot.organization_id == organization_id,
        m.InventoryLot.eligibility == "ELIGIBLE", m.InventoryLot.on_hand > 0,
        sa.or_(m.InventoryLot.expiry_kind == "NON_EXPIRING",
               sa.and_(m.InventoryLot.expiry_kind == "DATED", m.InventoryLot.expires_on >= on_day)),
    ).order_by(m.InventoryLot.id)))


def inventory_versions_match(session, organization_id, expectations):
    for item in expectations:
        version = session.scalar(sa.select(m.InventoryVersion.version).where(
            m.InventoryVersion.organization_id == organization_id,
            m.InventoryVersion.site_id == item.site_id,
            m.InventoryVersion.product_id == item.product_id,
        ))
        if version != item.version:
            return False
    return bool(expectations)
