"""Authenticated operational history/import and explicit stock-command APIs."""

import csv
import io
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, File, Form, Header, UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models import operational as m
from app.repositories import operations_api as service
from app.repositories.import_feedback import ImportRejected, validation_feedback
from app.routers.forecasts import PRESENTER, RUNTIME
from app.schemas.forecast_api import ErrorEnvelope
from app.schemas.operations_api import (
    CommandResult,
    CoverageImport,
    DemandImport,
    LotDeclarationWrite,
    ReceiptStockWrite,
    ReceiptWrite,
    SupplyConfirmation,
    SupplyCreate,
)
from app.services.inventory.stock import StockError

router = APIRouter(
    prefix="/api/v1",
    tags=["operations"],
    responses={code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 422, 503)},
)
Key = Annotated[str, Header(min_length=1, max_length=128, pattern=r"\S", alias="Idempotency-Key")]
CSRF = Annotated[str, Header(alias="X-CSRF-Token", min_length=1, max_length=128)]


def write(rt, action):
    try:
        return service.transact(rt.engine, action)
    except IntegrityError:
        raise StockError("OPERATIONAL_CONFLICT", 409) from None
    except ValidationError:
        raise StockError("INVALID_OPERATIONAL_INPUT", 422) from None


def saved_write(rt, scope, operation, key, body, action):
    return write(
        rt,
        lambda session: service.journal(
            session,
            scope,
            operation,
            key,
            body.model_dump(mode="json"),
            lambda: action(session),
        ),
    )


@router.get("/operational-catalog")
def catalog(rt=RUNTIME, scope=PRESENTER):
    def read(session):
        result = {}
        for model in (m.Site, m.Product, m.Donor, m.DataSource):
            rows = list(
                session.scalars(
                    sa.select(model)
                    .where(
                        model.organization_id == scope.organization_id,
                    )
                    .order_by(model.id)
                    .limit(101)
                )
            )
            if len(rows) > 100:
                raise StockError("CATALOG_TOO_LARGE", 422)
            result[model.__tablename__] = [service.row_data(row) for row in rows]
        return result

    return service.transact(rt.engine, read)


@router.post("/receipts", response_model=CommandResult, status_code=201)
def create_receipt(
    body: ReceiptWrite, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    return saved_write(
        rt,
        scope,
        "receipt-create",
        idempotency_key,
        body,
        lambda session: service.receipt_write(session, scope, body),
    )


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return service.transact(
        rt.engine,
        lambda session: service.receipt_read(
            session,
            scope,
            receipt_id,
        ),
    )


@router.post("/receipts/{receipt_id}/revisions", response_model=CommandResult, status_code=201)
def revise_receipt(
    receipt_id: UUID,
    body: ReceiptWrite,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return saved_write(
        rt,
        scope,
        f"receipt-revise:{receipt_id}",
        idempotency_key,
        body,
        lambda session: service.receipt_write(session, scope, body, receipt_id),
    )


@router.post("/receipts/{receipt_id}/post", response_model=CommandResult)
def post_receipt(
    receipt_id: UUID,
    body: ReceiptStockWrite,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return write(
        rt,
        lambda session: service.stock_write(
            session,
            scope,
            idempotency_key,
            "post",
            body,
            receipt_id,
        ),
    )


@router.post("/receipts/{receipt_id}/reconcile", response_model=CommandResult)
def reconcile_receipt(
    receipt_id: UUID,
    body: ReceiptStockWrite,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return write(
        rt,
        lambda session: service.stock_write(
            session,
            scope,
            idempotency_key,
            "reconcile",
            body,
            receipt_id,
        ),
    )


@router.post("/inventory/lots/{lot_id}/declarations", response_model=CommandResult)
def declare_lot(
    lot_id: UUID,
    body: LotDeclarationWrite,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return write(
        rt,
        lambda session: service.stock_write(
            session,
            scope,
            idempotency_key,
            "declare",
            body,
            lot_id,
        ),
    )


@router.post("/supplies", response_model=CommandResult, status_code=201)
def create_supply(
    body: SupplyCreate, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    return saved_write(
        rt,
        scope,
        "supply-create",
        idempotency_key,
        body,
        lambda session: service.supply_create(session, scope, body),
    )


@router.get("/supplies")
def supplies(rt=RUNTIME, scope=PRESENTER):
    def read(session):
        rows = list(
            session.scalars(
                sa.select(m.ExpectedSupply)
                .where(
                    m.ExpectedSupply.organization_id == scope.organization_id,
                )
                .order_by(m.ExpectedSupply.id)
                .limit(101)
            )
        )
        if len(rows) > 100:
            raise StockError("SUPPLY_LIST_TOO_LARGE", 422)
        return dict(supplies=[service.row_data(row) for row in rows])

    return service.transact(rt.engine, read)


@router.get("/supplies/{supply_id}")
def supply(supply_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return service.transact(
        rt.engine,
        lambda session: service.row_data(
            service.owned(
                session,
                m.ExpectedSupply,
                scope.organization_id,
                supply_id,
            )
        ),
    )


@router.post("/supplies/{supply_id}/confirmation", response_model=CommandResult)
def confirm_supply(
    supply_id: UUID,
    body: SupplyConfirmation,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return write(
        rt,
        lambda session: service.stock_write(
            session,
            scope,
            idempotency_key,
            "confirm",
            body,
            supply_id,
        ),
    )


@router.post("/imports/demand", response_model=CommandResult, status_code=201)
def demand_import(
    body: DemandImport, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    return saved_write(
        rt,
        scope,
        "demand-import",
        idempotency_key,
        body,
        lambda session: service.import_history(session, scope, body),
    )


@router.post("/imports/donation-coverage", response_model=CommandResult, status_code=201)
def coverage_import(
    body: CoverageImport, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    return saved_write(
        rt,
        scope,
        "coverage-import",
        idempotency_key,
        body,
        lambda session: service.import_history(session, scope, body, coverage=True),
    )


@router.post("/imports/demand/csv", response_model=CommandResult, status_code=201)
def demand_csv(
    source_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    try:
        content = file.file.read(60_001)
        if len(content) > 60_000:
            raise StockError("IMPORT_TOO_LARGE", 413)
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        expected = {
            "source_record_key",
            "site_id",
            "product_id",
            "day",
            "expected_revision",
            "requested",
            "fulfilled",
            "unmet",
        }
        if reader.fieldnames is None or set(reader.fieldnames) != expected:
            raise StockError("INVALID_CSV_HEADERS", 422)
        if len(reader.fieldnames) != len(expected):
            raise StockError("INVALID_CSV_HEADERS", 422)
        rows = []
        for row in reader:
            if len(rows) >= 100 or None in row:
                raise StockError("INVALID_CSV_ROWS", 422)
            rows.append(
                {
                    key: (
                        None
                        if value == ""
                        and key
                        in {
                            "expected_revision",
                            "requested",
                            "fulfilled",
                            "unmet",
                        }
                        else value
                    )
                    for key, value in row.items()
                }
            )
        body = DemandImport.model_validate(dict(source_id=source_id, rows=rows))
    except ValidationError as exc:
        raise ImportRejected(
            "INVALID_DEMAND_CSV", 422, validation_feedback(exc.errors(), len(rows))
        ) from None
    except (UnicodeError, csv.Error):
        raise StockError("INVALID_DEMAND_CSV", 422) from None
    finally:
        file.file.close()
    return saved_write(
        rt,
        scope,
        "demand-import",
        idempotency_key,
        body,
        lambda session: service.import_history(session, scope, body),
    )
