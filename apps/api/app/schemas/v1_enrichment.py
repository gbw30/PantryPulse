"""v1 enrichment, routes and local settings contract (W0-08). The Google key is write-only."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, SecretStr, model_validator

from app.schemas.or_inputs import ORContract
from app.schemas.v1_planning import Id, LocationRole, RouteMethod

AttributeState = Literal["known", "unknown", "manual", "excluded"]


class LocationAttributes(ORContract):
    location_id: Id
    state: AttributeState
    poverty_rate: Decimal | None
    snap_rate: Decimal | None
    source: str | None  # "ACS 5-year YYYY, tract NNNN" or "manual"
    fetched_at: datetime | None


class LocationAttributesUpdate(ORContract):
    """A manual value for both rates, or an explicit exclusion from EGP."""

    poverty_rate: Decimal | None = Field(default=None, ge=0, le=1)
    snap_rate: Decimal | None = Field(default=None, ge=0, le=1)
    excluded: bool = False

    @model_validator(mode="after")
    def one_choice(self) -> Self:
        rates = (self.poverty_rate, self.snap_rate)
        if self.excluded and any(r is not None for r in rates):
            raise ValueError("EXCLUDED_WITH_VALUES")
        if not self.excluded and any(r is None for r in rates):
            raise ValueError("BOTH_RATES_REQUIRED")
        return self


class UnmatchedAddress(ORContract):
    location_id: Id
    address: str
    hint: str


class EgpBlocker(ORContract):
    location_id: Id
    missing: tuple[Literal["poverty_rate", "snap_rate"], ...] = Field(min_length=1)


class EnrichmentStatus(ORContract):
    network_id: UUID
    dataset_version_id: UUID
    state: Literal["not_started", "running", "done", "failed"]
    job_id: UUID | None
    last_error: str | None  # an outage marks fields unknown; import still succeeds
    locations: tuple[LocationAttributes, ...]
    unmatched: tuple[UnmatchedAddress, ...]
    egp_blockers: tuple[EgpBlocker, ...]


class GeoLocation(ORContract):
    id: Id
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    role: LocationRole


class CandidateRoute(ORContract):
    from_location_id: Id
    to_location_id: Id
    straight_miles: Decimal
    road_miles: Decimal
    travel_days: int = Field(ge=1)
    method: RouteMethod


class RouteEntry(ORContract):
    from_location_id: Id
    to_location_id: Id
    road_miles: Decimal | None
    travel_days: int = Field(ge=1)
    method: RouteMethod
    fetched_at: datetime | None  # Google fetch date
    override: bool  # from routes.csv
    disabled: bool


class RouteList(ORContract):
    network_id: UUID
    dataset_version_id: UUID
    routes: tuple[RouteEntry, ...]


class LocalSettings(ORContract):
    google_maps_configured: bool


class GoogleKey(ORContract):
    key: SecretStr = Field(min_length=1, max_length=256)


class GoogleLookupPreview(ORContract):
    lookups: int = Field(ge=0)  # uncached routes only
    cached: int = Field(ge=0)
