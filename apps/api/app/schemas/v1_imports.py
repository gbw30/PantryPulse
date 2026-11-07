"""v1 import contract: create → upload each file → commit as an import.v1 job (W0-08, S4)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.schemas.or_inputs import Hash, ORContract
from app.schemas.v1_envelope import MAX_REPORTED_ERRORS
from app.schemas.v1_networks import TemplateName
from app.schemas.v1_planning import Id, NetworkMode

ImportPhase = Literal["uploading", "staging", "validating", "committing", "done", "failed"]
ErrorCode = Literal[
    "MALFORMED", "DUPLICATE", "NEGATIVE", "FRACTIONAL", "UNKNOWN_ID", "MISSING_EXPIRY",
    "AFTER_AS_OF_DATE", "OVER_ENVELOPE",
]


class NewNetwork(ORContract):
    name: str = Field(min_length=1, max_length=120)
    mode: NetworkMode  # fixed for the network's life
    timezone: str  # one planning timezone per network

    @field_validator("timezone")
    @classmethod
    def known(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("UNKNOWN_TIMEZONE") from exc
        return value


class ImportCreate(ORContract):
    """Either a new network or a re-import (new dataset version) into an existing one."""

    network: NewNetwork | None = None
    network_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        if (self.network is None) == (self.network_id is None):
            raise ValueError("NETWORK_OR_NETWORK_ID_REQUIRED")
        return self


class ImportCreated(ORContract):
    import_id: UUID
    network_id: UUID


class ImportFile(ORContract):
    name: TemplateName
    bytes: int = Field(ge=0)
    sha256: Hash


class ImportCommit(ORContract):
    as_of_date: date | None = None  # default: the day after the last history date


class ImportAccepted(ORContract):
    import_id: UUID
    job_id: UUID
    status_url: str


class ImportProgress(ORContract):
    unit: Literal["bytes", "rows", "checks"]
    done: int = Field(ge=0)
    total: int | None = Field(ge=0)


class RowError(ORContract):
    file: TemplateName
    line: int = Field(ge=1)  # 1-based, the header is line 1
    column: str | None  # None for row-level errors
    code: ErrorCode
    reason: str
    value: str | None


class OutsideHorizonInbound(ORContract):
    line: int = Field(ge=2)
    location_id: Id
    product_id: Id
    quantity: int = Field(ge=0)
    arrival_date: date


class ImportStatus(ORContract):
    import_id: UUID
    network_id: UUID
    job_id: UUID | None
    phase: ImportPhase
    files: tuple[ImportFile, ...]
    progress: ImportProgress | None
    error_count: int = Field(ge=0)
    errors_truncated: bool
    errors: tuple[RowError, ...] = Field(max_length=MAX_REPORTED_ERRORS)
    outside_horizon_inbound: tuple[OutsideHorizonInbound, ...]
    dataset_version_id: UUID | None  # set only when phase is "done"
    as_of_date: date | None


class ImportSettings(ORContract):
    """What validate_files needs besides the files (W1-D02)."""

    mode: NetworkMode
    timezone: str
    as_of_date: date | None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Result of validate_files: at most MAX_REPORTED_ERRORS kept, all counted (W1-D02)."""

    ok: bool
    errors: Sequence[RowError]
    error_count: int
    rows: Any = None  # the lane's ParsedNetwork, present only when ok
