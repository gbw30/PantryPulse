"""Frozen internal inputs for one site/product projection; no public API contract."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.operational import (
    Contract,
    ExpiryDeclaration,
    Nonempty,
    PositiveCount,
    Quantity,
)
from app.schemas.planning_primitives import TransferModeSelection
from app.services.inventory.contracts import local_day


class ProjectionDemand(Contract):
    day: date
    estimate: Annotated[
        Decimal, Field(strict=True, ge=0, le=Decimal(2**63 - 1), allow_inf_nan=False)
    ]


class ProjectionLot(Contract):
    lot_id: UUID
    organization_id: UUID
    site_id: UUID
    product_id: UUID
    base_unit: Nonempty
    quantity: Quantity
    source_kind: Literal["ON_HAND", "CONFIRMED"]
    source_id: Nonempty
    source_version: Nonempty
    available_at: AwareDatetime
    eligibility: Literal["ELIGIBLE", "HELD", "INELIGIBLE", "UNKNOWN"]
    expiry: ExpiryDeclaration


class OutboundCommitment(Contract):
    commitment_id: UUID
    lot_id: UUID
    day: date
    quantity: PositiveCount
    source_version: Nonempty


class ProjectionInput(Contract, TransferModeSelection):
    policy_version: Literal["projection-v1"]
    snapshot_id: UUID
    organization_id: UUID
    site_id: UUID
    product_id: UUID
    base_unit: Nonempty
    timezone: Nonempty
    calendar_version_id: UUID
    inventory_version: PositiveCount
    opening_on: date
    forecast_id: UUID
    provider: Nonempty
    planning_mode: Nonempty
    assumptions: tuple[Nonempty, ...]
    lots: tuple[ProjectionLot, ...]
    commitments: tuple[OutboundCommitment, ...]
    demand: Annotated[tuple[ProjectionDemand, ...], Field(min_length=1, max_length=7)]

    @model_validator(mode="after")
    def check_snapshot(self) -> Self:
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as error:
            raise ValueError("unknown operational timezone") from error
        for index, point in enumerate(self.demand):
            if point.day != self.opening_on + timedelta(days=index):
                raise ValueError("demand must contain contiguous dates starting on opening_on")
        lots = {lot.lot_id: lot for lot in self.lots}
        if len(lots) != len(self.lots):
            raise ValueError("duplicate lot identity")
        sources = set()
        for lot in self.lots:
            if (lot.organization_id, lot.site_id, lot.product_id, lot.base_unit) != (
                self.organization_id, self.site_id, self.product_id, self.base_unit
            ):
                raise ValueError("lot scope or base unit does not match projection")
            available = local_day(lot.available_at, self.timezone)
            if lot.source_kind == "ON_HAND" and available > self.opening_on:
                raise ValueError("future stock cannot be labeled ON_HAND")
            if lot.source_kind == "CONFIRMED" and available < self.opening_on:
                raise ValueError("confirmed arrival predates opening stock boundary")
            source = (lot.source_kind, lot.source_id)
            if source in sources:
                raise ValueError("duplicate stock/confirmed source identity")
            sources.add(source)
        if len({c.commitment_id for c in self.commitments}) != len(self.commitments):
            raise ValueError("duplicate commitment identity")
        for item in self.commitments:
            if item.lot_id not in lots:
                raise ValueError("commitment references an unknown lot")
            if not self.opening_on <= item.day <= self.demand[-1].day:
                raise ValueError("commitment outside projection horizon")
        return self
