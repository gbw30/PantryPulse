"""Trusted internal stock commands, not authentication or public HTTP DTOs."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.operational import Contract, ExpiryDeclaration, Nonempty, PositiveCount, Quantity

SignedDelta = Annotated[int, Field(strict=True, ge=-(2**63 - 1), le=2**63 - 1)]


class StockActor(Contract):
    """Construct only after caller authorization; never trust a browser actor flag."""
    organization_id: UUID
    actor: Nonempty


class VersionExpectation(Contract):
    site_id: UUID
    product_id: UUID
    version: PositiveCount


class SupplyVersion(Contract):
    supply_id: UUID
    version: PositiveCount


class LotDeclaration(Contract):
    line_key: Nonempty
    eligibility: Literal["ELIGIBLE", "HELD", "INELIGIBLE", "UNKNOWN"]
    expiry: ExpiryDeclaration


class SupplyMatch(Contract):
    line_key: Nonempty
    supply_id: UUID
    quantity: PositiveCount


class StockRequest(Contract):
    idempotency_key: Nonempty
    reason: Nonempty
    expected_versions: tuple[VersionExpectation, ...]

    @model_validator(mode="after")
    def unique_versions(self) -> Self:
        keys = [(item.site_id, item.product_id) for item in self.expected_versions]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("inventory version pairs must be nonempty and unique")
        return self


class ReceiptRequest(StockRequest):
    revision_id: UUID
    declarations: tuple[LotDeclaration, ...]
    supply_matches: tuple[SupplyMatch, ...]
    supply_versions: tuple[SupplyVersion, ...]

    @model_validator(mode="after")
    def unique_targets(self) -> Self:
        groups = [
            [item.line_key for item in self.declarations],
            [(item.line_key, item.supply_id) for item in self.supply_matches],
            [item.supply_id for item in self.supply_versions],
        ]
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("duplicate declaration, match or supply version")
        return self


class PostReceipt(ReceiptRequest):
    pass


class ReconcileReceipt(ReceiptRequest):
    """Supply matches are the complete desired allocation, not incremental deltas."""


class LotDelta(Contract):
    lot_id: UUID
    delta: SignedDelta

    @model_validator(mode="after")
    def nonzero(self) -> Self:
        if self.delta == 0:
            raise ValueError("zero stock adjustment is not a physical movement")
        return self


class AdjustStock(StockRequest):
    source_reference: Nonempty
    changes: tuple[LotDelta, ...]

    @model_validator(mode="after")
    def unique_lots(self) -> Self:
        keys = [item.lot_id for item in self.changes]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("lot targets must be nonempty and unique")
        return self


class DeclareLot(StockRequest):
    lot_id: UUID
    eligibility: Literal["ELIGIBLE", "HELD", "INELIGIBLE", "UNKNOWN"]
    expiry: ExpiryDeclaration


class ConfirmSupply(StockRequest):
    supply_id: UUID
    expected_supply_version: PositiveCount
    outstanding_quantity: Quantity
    expected_arrival_at: AwareDatetime | None
    cancel: bool = Field(strict=True)

    @model_validator(mode="after")
    def confirmation(self) -> Self:
        if self.cancel and self.outstanding_quantity:
            raise ValueError("cancelled supply cannot remain outstanding")
        if self.outstanding_quantity and self.expected_arrival_at is None:
            raise ValueError("confirmed outstanding supply needs an arrival instant")
        return self
