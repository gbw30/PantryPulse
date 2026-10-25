"""Bounded operational HTTP writes. Integer quantities travel as exact strings."""

from datetime import date
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field, StrictBool, model_validator

from app.schemas.inventory_api import VersionString, bigint_string
from app.schemas.operational import Contract, ExpiryDeclaration
from app.schemas.stock import LotDeclaration

Text = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
CountString = Annotated[
    str, Field(strict=True, pattern=r"^(0|[1-9][0-9]{0,18})$"), AfterValidator(bigint_string)
]


class ReceiptLineWrite(Contract):
    line_key: Text
    product_id: UUID
    quantity: VersionString


class ReceiptWrite(Contract):
    source_id: UUID
    source_record_key: Text
    site_id: UUID
    donor_id: UUID
    received_at: AwareDatetime
    expected_revision: VersionString | None
    is_void: StrictBool
    lines: tuple[ReceiptLineWrite, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def complete(self) -> Self:
        if self.is_void == bool(self.lines):
            raise ValueError("void receipts have no lines; received receipts need complete lines")
        if len({line.line_key for line in self.lines}) != len(self.lines):
            raise ValueError("duplicate receipt line key")
        return self


class VersionWrite(Contract):
    site_id: UUID
    product_id: UUID
    version: VersionString


class SupplyMatchWrite(Contract):
    line_key: Text
    supply_id: UUID
    quantity: VersionString


class SupplyVersionWrite(Contract):
    supply_id: UUID
    version: VersionString


class ReceiptStockWrite(Contract):
    revision_id: UUID
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    expected_versions: tuple[VersionWrite, ...] = Field(min_length=1, max_length=40)
    declarations: tuple[LotDeclaration, ...] = Field(max_length=100)
    supply_matches: tuple[SupplyMatchWrite, ...] = Field(max_length=100)
    supply_versions: tuple[SupplyVersionWrite, ...] = Field(max_length=100)


class LotDeclarationWrite(Contract):
    expected_inventory_version: VersionString
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    eligibility: Annotated[str, Field(pattern=r"^(ELIGIBLE|HELD|INELIGIBLE|UNKNOWN)$")]
    expiry: ExpiryDeclaration


class ProductCreate(Contract):
    """A new product/resource category with its base unit (quantities stay per product)."""

    name: Text
    base_unit: Annotated[str, Field(min_length=1, max_length=32, pattern=r"\S")]
    category_name: Text | None = None


class SupplyCreate(Contract):
    site_id: UUID
    product_id: UUID
    source_id: UUID
    source_record_key: Text
    quantity: VersionString


class SupplyConfirmation(Contract):
    expected_inventory_version: VersionString
    expected_supply_version: VersionString
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    outstanding_quantity: CountString
    expected_arrival_at: AwareDatetime | None
    cancel: StrictBool


class DemandRow(Contract):
    source_record_key: Text
    site_id: UUID
    product_id: UUID
    day: date
    expected_revision: VersionString | None
    requested: CountString | None
    fulfilled: CountString | None
    unmet: CountString | None


class DemandImport(Contract):
    source_id: UUID
    rows: tuple[DemandRow, ...] = Field(min_length=1, max_length=100)


class CoverageRow(Contract):
    site_id: UUID
    product_id: UUID
    day: date
    expected_revision: VersionString | None
    complete: StrictBool


class CoverageImport(Contract):
    source_id: UUID
    rows: tuple[CoverageRow, ...] = Field(min_length=1, max_length=100)


class CommandResult(Contract):
    """Operation-specific saved details; integer quantities serialize as strings."""

    command_id: UUID
    operation: str
    result: dict[str, Any]
