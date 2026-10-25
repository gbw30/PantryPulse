"""Current physical stock; quantities serialize as decimal strings for JS precision."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field, PlainSerializer, model_validator

from app.schemas.operational import Contract

ExactCount = Annotated[
    int, Field(strict=True, ge=0), PlainSerializer(str, return_type=str, when_used="json")
]
ExclusionReason = Literal[
    "HELD", "INELIGIBLE", "UNKNOWN_ELIGIBILITY", "UNKNOWN_EXPIRY", "EXPIRED"
]


class InventoryLotView(Contract):
    lot_id: UUID
    batch_key: str
    on_hand_quantity: ExactCount
    eligibility: Literal["ELIGIBLE", "HELD", "INELIGIBLE", "UNKNOWN"]
    expiry_kind: Literal["DATED", "NON_EXPIRING", "UNKNOWN"]
    expires_on: date | None
    metadata_version: ExactCount
    usable: bool
    exclusion_reason: ExclusionReason | None


class InventorySnapshot(Contract):
    site_id: UUID
    site_name: str
    product_id: UUID
    product_name: str
    base_unit: str
    timezone: str
    local_date: date
    observed_at: AwareDatetime
    inventory_version: ExactCount | None
    on_hand_quantity: ExactCount
    usable_quantity: ExactCount
    excluded_quantity: ExactCount
    excluded_quantities: dict[ExclusionReason, ExactCount]
    lots: tuple[InventoryLotView, ...]


def bigint_string(value: str) -> str:
    if abs(int(value)) > 2**63 - 1:
        raise ValueError("value exceeds the supported signed BIGINT range")
    return value


VersionString = Annotated[
    str, Field(strict=True, pattern=r"^[1-9][0-9]{0,18}$"), AfterValidator(bigint_string)
]
DeltaString = Annotated[
    str, Field(strict=True, pattern=r"^-?[1-9][0-9]{0,18}$"), AfterValidator(bigint_string)
]


class StockAdjustmentChange(Contract):
    lot_id: UUID
    delta: DeltaString = Field(description="Signed nonzero base-unit delta, as a decimal string.")


class StockAdjustmentRequest(Contract):
    expected_inventory_version: VersionString
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    source_reference: str = Field(min_length=1, max_length=256, pattern=r"\S")
    changes: tuple[StockAdjustmentChange, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_lots(self) -> Self:
        if len({change.lot_id for change in self.changes}) != len(self.changes):
            raise ValueError("lot IDs must be unique")
        return self


class AdjustedLot(Contract):
    lot_id: UUID
    before: ExactCount
    after: ExactCount


class StockAdjustmentResult(Contract):
    status: Literal["APPLIED"]
    command_id: UUID
    site_id: UUID
    product_id: UUID
    before_version: ExactCount
    after_version: ExactCount
    lots: tuple[AdjustedLot, ...]
