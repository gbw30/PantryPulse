"""PP-37: real stock transactions in disposable schemas, never public demo data."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session
from test_operational_postgres import contract, insert, seed, stock_command
from test_operational_postgres import db as db
from test_operational_postgres import storage as storage

from app.models import operational as m
from app.repositories.operational import append_receipt_revision
from app.schemas.stock import (
    AdjustStock,
    ConfirmSupply,
    DeclareLot,
    LotDeclaration,
    LotDelta,
    PostReceipt,
    ReconcileReceipt,
    StockActor,
    SupplyMatch,
    SupplyVersion,
    VersionExpectation,
)
from app.services.inventory.stock import (
    StockError,
    eligible_lots,
    execute_stock,
    inventory_versions_match,
)

pytestmark = pytest.mark.integration


def version(items, number):
    return VersionExpectation(site_id=items[1].id, product_id=items[3].id, version=number)


def actor(items):
    return StockActor(organization_id=items[0].id, actor="authorized-test-presenter")


def declaration(key="1", eligibility="ELIGIBLE", kind="NON_EXPIRING", expiry=None):
    return LotDeclaration(line_key=key, eligibility=eligibility,
                          expiry={"kind": kind, "expires_on": expiry})


def received(db, amount=100, supply=None):
    items = seed(db)
    value = contract(items, lines=({"line_key": "1", "product_id": items[3].id,
                                   "quantity": amount},))
    revision = append_receipt_revision(db, value)
    cmd = PostReceipt(idempotency_key="post", reason="Received actual supplies",
                      revision_id=revision.id, expected_versions=(version(items, 1),),
                      declarations=(declaration(),), supply_matches=(), supply_versions=())
    if supply:
        row = insert(db, m.ExpectedSupply, organization_id=items[0].id, site_id=items[1].id,
                     product_id=items[3].id, source_id=items[4].id, source_record_key="incoming",
                     quantity=supply, received_quantity=0, outstanding_confirmed_quantity=supply,
                     expected_arrival_at=datetime(2026, 10, 24, tzinfo=UTC),
                     state="CONFIRMED", version=1)
        cmd = cmd.model_copy(update={
            "supply_matches": (SupplyMatch(line_key="1", supply_id=row.id, quantity=amount),),
            "supply_versions": (SupplyVersion(supply_id=row.id, version=1),),
        })
    result = execute_stock(db, actor(items), cmd)
    lot = db.scalar(sa.select(m.InventoryLot).where(
        m.InventoryLot.organization_id == items[0].id))
    return items, cmd, result, lot


def count(db, model, organization_id):
    return db.scalar(sa.select(sa.func.count()).select_from(model).where(
        model.organization_id == organization_id))


def adjust(items, lot_id, amount, expected, key="adjust"):
    return AdjustStock(idempotency_key=key, reason="Documented physical stock correction",
                       source_reference="fixture/count-note",
                       expected_versions=(version(items, expected),),
                       changes=(LotDelta(lot_id=lot_id, delta=amount),))


def correction(db, items, amount=None, revision=2):
    values = {"revision": revision}
    if amount is None:
        values.update(is_void=True, lines=())
    else:
        values["lines"] = ({"line_key": "1", "product_id": items[3].id, "quantity": amount},)
    return append_receipt_revision(db, contract(items, **values))


def reconcile(items, revision, expected, key="correct", matches=(), supplies=(), declarations=()):
    return ReconcileReceipt(idempotency_key=key, reason="Explicit receipt reconciliation",
                            revision_id=revision.id, expected_versions=(version(items, expected),),
                            declarations=declarations, supply_matches=matches,
                            supply_versions=supplies)


def test_receipt_posts_once_and_exact_replay_is_identical(db):
    items, cmd, result, lot = received(db)
    assert lot.on_hand == 100
    assert execute_stock(db, actor(items), cmd) == result
    assert lot.on_hand == 100
    for model in (m.StockCommand, m.ReceiptPosting, m.StockLedgerEntry, m.AuditEvent):
        assert count(db, model, items[0].id) == 1
    with pytest.raises(StockError, match="IDEMPOTENCY_CONFLICT"):
        execute_stock(db, actor(items), cmd.model_copy(update={"reason": "different payload"}))
    with pytest.raises(StockError, match="ALREADY_POSTED"):
        execute_stock(db, actor(items), cmd.model_copy(update={"idempotency_key": "second-post"}))


def test_adjustment_versions_audit_and_stale_snapshot(db):
    items, _, _, lot = received(db)
    snapshot = (version(items, 2),)
    assert inventory_versions_match(db, items[0].id, snapshot)
    result = execute_stock(db, actor(items), adjust(items, lot.id, -10, 2))
    assert lot.on_hand == 90
    assert result["inventory_versions"][0]["after"] == 3
    assert not inventory_versions_match(db, items[0].id, snapshot)
    assert snapshot[0].version == 2
    with pytest.raises(StockError, match="STALE_INVENTORY"):
        execute_stock(db, actor(items), adjust(items, lot.id, -1, 2, "stale"))
    assert lot.on_hand == 90
    assert count(db, m.StockCommand, items[0].id) == 2
    cmd = db.scalar(sa.select(m.StockCommand).where(m.StockCommand.idempotency_key == "adjust"))
    assert cmd.actor == "authorized-test-presenter" and cmd.reason


def test_consumed_correction_preserves_history_then_applies_incremental_deltas(db):
    items, _, _, lot = received(db)
    execute_stock(db, actor(items), adjust(items, lot.id, -70, 2))
    target = correction(db, items, 50)
    with pytest.raises(StockError, match="INSUFFICIENT_STOCK"):
        execute_stock(db, actor(items), reconcile(items, target, 3))
    assert lot.on_hand == 30
    marker = db.scalar(sa.select(m.ReceiptReconciliation).where(
        m.ReceiptReconciliation.receipt_id == items[6].id))
    assert marker.latest_revision_id == target.id and marker.needs_reconciliation
    assert count(db, m.ReceiptRevision, items[0].id) == 2
    later = correction(db, items, 80, revision=3)
    execute_stock(db, actor(items), reconcile(items, later, 3, key="correct80"))
    assert lot.on_hand == 10
    next_revision = correction(db, items, 90, revision=4)
    execute_stock(db, actor(items), reconcile(items, next_revision, 4, key="correct90"))
    assert lot.on_hand == 20 and not marker.needs_reconciliation
    total = db.scalar(sa.select(sa.func.sum(m.StockLedgerEntry.delta)).where(
        m.StockLedgerEntry.lot_id == lot.id))
    assert total == lot.on_hand


@pytest.mark.parametrize("consumed", [0, 70])
def test_posted_cancellation_respects_consumed_stock(db, consumed):
    items, _, _, lot = received(db)
    expected = 2
    if consumed:
        execute_stock(db, actor(items), adjust(items, lot.id, -consumed, 2))
        expected += 1
    target = correction(db, items)
    if consumed:
        with pytest.raises(StockError, match="INSUFFICIENT_STOCK"):
            execute_stock(db, actor(items), reconcile(items, target, expected))
        assert lot.on_hand == 30
    else:
        execute_stock(db, actor(items), reconcile(items, target, expected))
        assert lot.on_hand == 0
    assert target.is_void


def test_unknown_held_expired_and_non_expiring_stock(db):
    items, _, _, lot = received(db)
    for index, (eligibility, kind, expiry, available) in enumerate([
        ("UNKNOWN", "NON_EXPIRING", None, False),
        ("ELIGIBLE", "UNKNOWN", None, False),
        ("HELD", "NON_EXPIRING", None, False),
        ("ELIGIBLE", "DATED", date(2026, 10, 24), True),
    ]):
        cmd = DeclareLot(idempotency_key=f"declare-{index}", reason="Eligibility declaration",
                         expected_versions=(version(items, 2 + index),), lot_id=lot.id,
                         eligibility=eligibility, expiry={"kind": kind, "expires_on": expiry})
        result = execute_stock(db, actor(items), cmd)
        assert result["lots"][0]["declaration"]["after"]["eligibility"] == eligibility
        assert bool(eligible_lots(db, items[0].id, date(2026, 10, 24))) == available
    assert not eligible_lots(db, items[0].id, date(2026, 10, 25))
    assert lot.on_hand == 100 and count(db, m.StockLedgerEntry, items[0].id) == 1


def test_wrong_organization_has_no_mutation(db):
    items, _, _, lot = received(db)
    other = StockActor(organization_id=uuid4(), actor="other")
    with pytest.raises(StockError, match="NOT_FOUND"):
        execute_stock(db, other, adjust(items, lot.id, -1, 2))
    assert lot.on_hand == 100


def test_failure_at_audit_rolls_back_entire_posting(db):
    items = seed(db)
    target = append_receipt_revision(db, contract(items))
    request = PostReceipt(idempotency_key="fail", reason="Rollback injection",
                          revision_id=target.id, expected_versions=(version(items, 1),),
                          declarations=(declaration(),), supply_matches=(), supply_versions=())

    def fail(session, flush_context, instances):
        if any(isinstance(row, m.AuditEvent) for row in session.new):
            raise RuntimeError("injected audit failure")

    event.listen(db, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="injected audit"):
            execute_stock(db, actor(items), request)
    finally:
        event.remove(db, "before_flush", fail)
    for model in (m.InventoryLot, m.StockLedgerEntry, m.StockCommand, m.ReceiptPosting):
        assert count(db, model, items[0].id) == 0
    assert count(db, m.ReceiptRevision, items[0].id) == 1


def test_confirmed_arrivals_count_once_and_downward_correction_does_not_reconfirm(db):
    items, _, _, lot = received(db, amount=100, supply=100)
    supply = db.scalar(sa.select(m.ExpectedSupply).where(
        m.ExpectedSupply.organization_id == items[0].id))
    assert (lot.on_hand, supply.received_quantity,
            supply.outstanding_confirmed_quantity) == (100, 100, 0)
    target = correction(db, items, 80)
    execute_stock(db, actor(items), reconcile(
        items, target, 2, matches=(SupplyMatch(line_key="1", supply_id=supply.id, quantity=80),),
        supplies=(SupplyVersion(supply_id=supply.id, version=2),)))
    assert (lot.on_hand, supply.received_quantity,
            supply.outstanding_confirmed_quantity) == (80, 80, 0)
    confirmation = ConfirmSupply(idempotency_key="confirm20", reason="New explicit promise",
                                 expected_versions=(version(items, 3),), supply_id=supply.id,
                                 expected_supply_version=3, outstanding_quantity=20,
                                 expected_arrival_at=datetime(2026, 10, 26, tzinfo=UTC),
                                 cancel=False)
    execute_stock(db, actor(items), confirmation)
    assert lot.on_hand == 80 and supply.outstanding_confirmed_quantity == 20


def test_larger_correction_needs_explicit_new_supply_confirmation(db):
    items, _, _, lot = received(db, amount=100, supply=100)
    supply = db.scalar(sa.select(m.ExpectedSupply).where(
        m.ExpectedSupply.organization_id == items[0].id))
    target = correction(db, items, 80)
    execute_stock(db, actor(items), reconcile(
        items, target, 2, matches=(SupplyMatch(line_key="1", supply_id=supply.id, quantity=80),),
        supplies=(SupplyVersion(supply_id=supply.id, version=2),)))
    target90 = correction(db, items, 90, revision=3)
    match90 = (SupplyMatch(line_key="1", supply_id=supply.id, quantity=90),)
    with pytest.raises(StockError, match="SUPPLY_NOT_CONFIRMED"):
        execute_stock(db, actor(items), reconcile(
            items, target90, 3, key="90", matches=match90,
            supplies=(SupplyVersion(supply_id=supply.id, version=3),)))
    assert lot.on_hand == 80 and supply.outstanding_confirmed_quantity == 0
    execute_stock(db, actor(items), ConfirmSupply(
        idempotency_key="new-confirmation", reason="Supplier explicitly reconfirmed",
        expected_versions=(version(items, 3),), supply_id=supply.id, expected_supply_version=3,
        outstanding_quantity=20, expected_arrival_at=datetime(2026, 10, 26, tzinfo=UTC),
        cancel=False))
    execute_stock(db, actor(items), reconcile(
        items, target90, 4, key="90", matches=match90,
        supplies=(SupplyVersion(supply_id=supply.id, version=4),)))
    assert lot.on_hand == 90 and supply.received_quantity == 90
    assert supply.outstanding_confirmed_quantity == 10


def test_correction_can_add_new_product_without_reposting_old_lines(db):
    items, _, _, meal_lot = received(db)
    water = insert(db, m.Product, organization_id=items[0].id,
                   category_id=items[3].category_id, name="Water", base_unit="bottle", active=True)
    revision = append_receipt_revision(db, contract(items, revision=2, lines=(
        {"line_key": "1", "product_id": items[3].id, "quantity": 100},
        {"line_key": "water", "product_id": water.id, "quantity": 20},
    )))
    request = ReconcileReceipt(idempotency_key="add-water", reason="Receipt omitted water",
                               revision_id=revision.id, declarations=(declaration("water"),),
                               supply_matches=(), supply_versions=(), expected_versions=(
                                   version(items, 2), VersionExpectation(site_id=items[1].id,
                                       product_id=water.id, version=1)))
    execute_stock(db, actor(items), request)
    water_lot = db.scalar(sa.select(m.InventoryLot).where(m.InventoryLot.product_id == water.id))
    assert water_lot.on_hand == 20 and meal_lot.on_hand == 100
    assert water_lot.receipt_revision_id == revision.id
    assert water_lot.posting_id == meal_lot.posting_id
    bad_adjustment = AdjustStock(
        idempotency_key="bad-multi", reason="All changes must roll back", source_reference="test",
        expected_versions=(version(items, 3), VersionExpectation(site_id=items[1].id,
                                                               product_id=water.id, version=2)),
        changes=(LotDelta(lot_id=meal_lot.id, delta=-1), LotDelta(lot_id=water_lot.id, delta=-100)),
    )
    with pytest.raises(StockError, match="INSUFFICIENT_STOCK"):
        execute_stock(db, actor(items), bad_adjustment)
    assert water_lot.on_hand == 20 and meal_lot.on_hand == 100
    assert count(db, m.StockCommand, items[0].id) == 2


def test_late_ledger_inconsistency_and_count_overflow_are_rejected(db):
    items, _, _, lot = received(db)
    with pytest.raises(StockError, match="COUNT_OVERFLOW"):
        execute_stock(db, actor(items), adjust(items, lot.id, 2**63 - 1, 2))
    lot.on_hand = 101  # simulate out-of-band corruption, not a supported stock operation
    db.flush()
    with pytest.raises(StockError, match="LEDGER_BALANCE_MISMATCH"):
        execute_stock(db, actor(items), adjust(items, lot.id, -1, 2, key="corrupt"))
    assert count(db, m.StockCommand, items[0].id) == 1


def test_cancellation_reverses_multiple_original_allocations_of_same_line(db):
    items, _, _, lot = received(db, amount=50)
    org, site, _, product, source, _, _ = items
    supply = insert(db, m.ExpectedSupply, organization_id=org.id, site_id=site.id,
                    product_id=product.id, source_id=source.id, source_record_key="legacy-arrival",
                    quantity=50, received_quantity=50, outstanding_confirmed_quantity=0,
                    state="RECEIVED", version=1)
    line = db.scalar(sa.select(m.ReceiptLine).where(m.ReceiptLine.id == lot.receipt_line_id))
    for amount in (20, 30):
        command = stock_command(db, org.id)
        insert(db, m.SupplyReceipt, organization_id=org.id, supply_id=supply.id,
               site_id=site.id, product_id=product.id, receipt_line_id=line.id,
               receipt_revision_id=line.receipt_revision_id, command_id=command.id,
               quantity_delta=amount)
    void = correction(db, items)
    execute_stock(db, actor(items), reconcile(
        items, void, 2, supplies=(SupplyVersion(supply_id=supply.id, version=1),)))
    assert lot.on_hand == 0 and supply.received_quantity == 0
    assert db.scalar(sa.select(sa.func.sum(m.SupplyReceipt.quantity_delta)).where(
        m.SupplyReceipt.supply_id == supply.id)) == 0


def test_committed_history_survives_separate_failed_stock_transaction(storage):
    engine, schema = storage
    with engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        with Session(bind=connection) as session:
            items, _, _, lot = received(session)
            execute_stock(session, actor(items), adjust(items, lot.id, -70, 2))
            saved_actor, organization_id, lot_id = actor(items), items[0].id, lot.id
            history = contract(items, revision=2, lines=(
                {"line_key": "1", "product_id": items[3].id, "quantity": 50},))
            expected = (version(items, 3),)
    with engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        with Session(bind=connection) as session:
            revision = append_receipt_revision(session, history)
            target_id = revision.id
    with pytest.raises(StockError, match="INSUFFICIENT_STOCK"), engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        with Session(bind=connection) as session:
            execute_stock(session, saved_actor, ReconcileReceipt(
                idempotency_key="committed-correction", reason="Correct actual receipt",
                revision_id=target_id, expected_versions=expected,
                declarations=(), supply_matches=(), supply_versions=()))
    with engine.connect() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        assert connection.scalar(sa.select(m.InventoryLot.on_hand).where(
            m.InventoryLot.id == lot_id)) == 30
        assert connection.scalar(sa.select(sa.func.count()).select_from(m.ReceiptRevision).where(
            m.ReceiptRevision.organization_id == organization_id)) == 2
        assert connection.scalar(sa.select(m.ReceiptReconciliation.needs_reconciliation).where(
            m.ReceiptReconciliation.latest_revision_id == target_id))


def test_partial_arrival_and_cancel_preserve_received_stock(db):
    items, _, _, lot = received(db, amount=60, supply=100)
    supply = db.scalar(sa.select(m.ExpectedSupply).where(
        m.ExpectedSupply.organization_id == items[0].id))
    assert lot.on_hand + supply.outstanding_confirmed_quantity == 100
    execute_stock(db, actor(items), ConfirmSupply(
        idempotency_key="cancel", reason="Remainder cancelled",
        expected_versions=(version(items, 2),),
        supply_id=supply.id, expected_supply_version=2, outstanding_quantity=0,
        expected_arrival_at=None, cancel=True))
    assert lot.on_hand == 60 and supply.received_quantity == 60
    assert supply.outstanding_confirmed_quantity == 0 and supply.state == "CANCELLED"


@pytest.mark.parametrize("duplicate", [False, True])
def test_two_connections_compete_or_replay_safely(storage, duplicate):
    engine, schema = storage
    with engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        with Session(bind=connection) as session:
            items, _, _, lot = received(session)
            organization_id, lot_id = items[0].id, lot.id
            site_id, product_id = items[1].id, items[3].id
    gate = Barrier(2)

    def worker(index):
        request = AdjustStock(idempotency_key="same" if duplicate else f"parallel-{index}",
                              reason="Concurrent update", source_reference="test",
                              expected_versions=(VersionExpectation(site_id=site_id,
                                  product_id=product_id, version=2),),
                              changes=(LotDelta(lot_id=lot_id, delta=-1),))
        gate.wait(timeout=10)
        try:
            with engine.begin() as connection:
                connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
                connection.execute(sa.text("SET LOCAL lock_timeout = '10s'"))
                with Session(bind=connection) as session:
                    result = execute_stock(session, StockActor(organization_id=organization_id,
                                                               actor="presenter"), request)
                    return result
        except StockError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in (1, 2)]
        results = [future.result(timeout=30) for future in futures]
    if duplicate:
        assert isinstance(results[0], dict) and results[0] == results[1]
    else:
        assert sum(isinstance(result, dict) for result in results) == 1
        assert "STALE_INVENTORY_VERSION" in results
    with engine.connect() as connection:
        connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        assert connection.scalar(sa.select(m.InventoryLot.on_hand).where(
            m.InventoryLot.id == lot_id)) == 99
        assert connection.scalar(sa.select(sa.func.sum(m.StockLedgerEntry.delta)).where(
            m.StockLedgerEntry.lot_id == lot_id)) == 99
