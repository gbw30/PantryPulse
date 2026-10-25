"""Authenticated inventory inspection independent of the compute worker."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header

from app.repositories.inventory import load_inventory
from app.repositories.stock_adjustments import adjust_inventory
from app.routers.forecasts import PRESENTER, RUNTIME
from app.schemas.forecast_api import ErrorEnvelope
from app.schemas.inventory_api import (
    InventorySnapshot,
    StockAdjustmentRequest,
    StockAdjustmentResult,
)

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.get(
    "/sites/{site_id}/products/{product_id}", response_model=InventorySnapshot,
    responses={code: {"model": ErrorEnvelope} for code in (401, 403, 404, 422, 503)},
)
def snapshot(site_id: UUID, product_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return load_inventory(rt.engine, scope.organization_id, site_id, product_id)


@router.post(
    "/sites/{site_id}/products/{product_id}/adjustments",
    response_model=StockAdjustmentResult,
    responses={code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 422, 503)},
)
def adjust(
    site_id: UUID, product_id: UUID, body: StockAdjustmentRequest,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern=r"\S")],
    csrf_token: Annotated[str, Header(alias="X-CSRF-Token", min_length=1, max_length=128)],
    rt=RUNTIME, scope=PRESENTER,
):
    return adjust_inventory(rt.engine, scope, site_id, product_id, body, idempotency_key)
