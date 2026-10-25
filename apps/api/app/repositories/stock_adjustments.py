"""HTTP-to-stock adapter; caller returns only after the audited transaction commits."""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import operational as m
from app.schemas.inventory_api import StockAdjustmentResult
from app.schemas.stock import AdjustStock, LotDelta, StockActor, VersionExpectation
from app.services.inventory.stock import StockError, execute_stock


def adjust_inventory(engine, scope, site_id, product_id, body, idempotency_key):
    command = AdjustStock(
        idempotency_key=idempotency_key, reason=body.reason,
        source_reference=body.source_reference,
        expected_versions=(VersionExpectation(
            site_id=site_id, product_id=product_id, version=int(body.expected_inventory_version),
        ),),
        changes=tuple(LotDelta(lot_id=change.lot_id, delta=int(change.delta))
                      for change in body.changes),
    )
    actor = StockActor(organization_id=scope.organization_id, actor=str(scope.actor_ref))
    with Session(engine) as session, session.begin():
        session.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
        requested = {change.lot_id for change in body.changes}
        found = set(session.scalars(sa.select(m.InventoryLot.id).where(
            m.InventoryLot.organization_id == scope.organization_id,
            m.InventoryLot.site_id == site_id, m.InventoryLot.product_id == product_id,
            m.InventoryLot.id.in_(requested),
        )))
        if found != requested:
            raise StockError("NOT_FOUND", 404)
        outcome = execute_stock(session, actor, command)
        version = outcome["inventory_versions"][0]
        result = StockAdjustmentResult(
            status=outcome["status"], command_id=outcome["command_id"],
            site_id=site_id, product_id=product_id,
            before_version=version["before"], after_version=version["after"],
            lots=outcome["lots"],
        )
    return result
