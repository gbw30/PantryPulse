"""Issue #8 internal validation contracts, not HTTP routes or ORM records.

No mutation, source selection or receipt posting is performed by these types.
Database ownership/uniqueness and atomicity remain issue #19/#21 responsibilities.
"""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.services.inventory.contracts import local_day

Quantity = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
PositiveCount = Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
Nonempty = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Count(Contract):
    value: Quantity


class DemandQuantities(Contract):
    requested: Quantity | None
    fulfilled: Quantity | None
    unmet: Quantity | None

    @model_validator(mode="after")
    def check_components(self) -> Self:
        if self.requested is None and self.fulfilled is None and self.unmet is None:
            raise ValueError("at least one demand component must be observed")
        if self.requested is not None:
            if self.fulfilled is not None and self.fulfilled > self.requested:
                raise ValueError("fulfilled exceeds requested")
            if self.unmet is not None and self.unmet > self.requested:
                raise ValueError("unmet exceeds requested")
            if self.fulfilled is not None and self.unmet is not None:
                if self.requested != self.fulfilled + self.unmet:
                    raise ValueError("requested must equal fulfilled plus unmet")
        return self


class ExpiryDeclaration(Contract):
    kind: Literal["DATED", "NON_EXPIRING", "UNKNOWN"]
    expires_on: date | None

    @model_validator(mode="after")
    def check_date(self) -> Self:
        if (self.kind == "DATED") != (self.expires_on is not None):
            raise ValueError("only DATED expiry requires and permits an expiry date")
        return self

    def permits_day(self, day: date) -> bool:
        """Date exclusion only: this is not eligibility or transfer feasibility."""
        if self.kind == "UNKNOWN":
            return False
        return self.expires_on is None or day <= self.expires_on


class ReceiptLine(Contract):
    line_key: Nonempty
    product_id: UUID
    quantity: PositiveCount


class ReceiptRevision(Contract):
    organization_id: UUID
    receipt_id: UUID
    revision_id: UUID
    revision: PositiveCount
    source_id: UUID
    source_record_key: Nonempty
    source_classification: Literal["OBSERVED", "SIMULATED"]
    receiving_site_id: UUID
    donor_id: UUID
    received_at: AwareDatetime
    recorded_at: AwareDatetime
    local_day: date
    calendar_version_id: UUID
    timezone: Nonempty
    is_void: StrictBool
    lines: tuple[ReceiptLine, ...]

    @model_validator(mode="after")
    def check_complete_event(self) -> Self:
        if self.local_day != local_day(self.received_at, self.timezone):
            raise ValueError("receipt local_day does not match the receiving-site calendar")
        if self.is_void and self.lines:
            raise ValueError("void revision cannot contain received lines")
        if not self.is_void and not self.lines:
            raise ValueError("received revision requires at least one complete line")
        keys = [line.line_key for line in self.lines]
        if len(keys) != len(set(keys)):
            raise ValueError("receipt line keys must be unique within a revision")
        return self
