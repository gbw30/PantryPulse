"""Experimental v1 internal contracts. These are not frozen HTTP/SQL schemas."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    field_validator,
    model_validator,
)

Quantity = Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)]
Target = Literal["DEMAND", "DONATION"]
Basis = Literal["REQUESTED", "FULFILLED_PROXY", "RECEIVED", "MIXED", "UNAVAILABLE"]
Classification = Literal["OBSERVED", "SIMULATED"]
Strategy = Literal["SEASONAL_NAIVE", "MOVING_AVERAGE", "CHRONOS2"]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class SeriesKey(Contract):
    organization_id: UUID
    site_id: UUID
    product_id: UUID
    target_type: Target


def series_identity(key: SeriesKey) -> tuple[str, ...]:
    return tuple(str(getattr(key, field)) for field in SeriesKey.model_fields)


class SeriesScope(Contract):
    key: SeriesKey
    unit: str = Field(min_length=1, max_length=80)
    timezone: str
    calendar_version: str = "site-local-v1"
    unit_version: str = "base-unit-v1"
    required: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown site timezone") from exc
        return value


class SourceRevision(Contract):
    organization_id: UUID
    dataset_id: UUID
    logical_key: str = Field(min_length=1)
    revision_id: UUID
    revision: int = Field(ge=1, strict=True)
    recorded_at: AwareDatetime

    @field_validator("recorded_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class DemandRevision(Contract):
    source: SourceRevision
    key: SeriesKey
    day: date
    requested_units: Quantity | None
    fulfilled_units: Quantity | None
    unmet_units: Quantity | None
    source_classification: Classification

    @model_validator(mode="after")
    def valid_components(self) -> Self:
        if self.key.target_type != "DEMAND":
            raise ValueError("Demand fact requires DEMAND target")
        requested, fulfilled, unmet = self.requested_units, self.fulfilled_units, self.unmet_units
        if requested is not None and fulfilled is not None:
            if fulfilled > requested:
                raise ValueError("Fulfilled units exceed requested units")
            if unmet is not None and requested != fulfilled + unmet:
                raise ValueError("Requested units must equal fulfilled plus unmet units")
        if self.source.organization_id != self.key.organization_id:
            raise ValueError("Demand organization differs from its source")
        return self


class ReceiptLine(Contract):
    line_id: UUID
    product_id: UUID
    unit: str = Field(min_length=1)
    received_units: Quantity


class ReceiptRevision(Contract):
    """One complete donation event revision; purchases/transfers are outside this type."""

    source: SourceRevision
    donor_id: UUID
    receiving_site_id: UUID
    received_at: AwareDatetime
    local_day: date
    timezone: str
    source_classification: Classification
    lines: tuple[ReceiptLine, ...]
    is_void: bool = False
    receipt_kind: Literal["DONATION"] = "DONATION"

    @field_validator("received_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_event(self) -> Self:
        if self.is_void != (len(self.lines) == 0):
            raise ValueError("A void receipt has no lines; a received event requires lines")
        try:
            zone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown receipt timezone") from exc
        if self.received_at.astimezone(zone).date() != self.local_day:
            raise ValueError("Receipt local day disagrees with received instant/timezone")
        if len({line.line_id for line in self.lines}) != len(self.lines):
            raise ValueError("Duplicate receipt line")
        return self


class CoverageRevision(Contract):
    source: SourceRevision
    key: SeriesKey
    day: date
    complete: bool
    source_classification: Classification

    @model_validator(mode="after")
    def donation_only(self) -> Self:
        if self.key.target_type != "DONATION":
            raise ValueError("Receipt coverage requires DONATION target")
        if self.source.organization_id != self.key.organization_id:
            raise ValueError("Coverage organization differs from its source")
        return self


class HistoryBundle(Contract):
    organization_id: UUID
    dataset_id: UUID
    scope: tuple[SeriesScope, ...] = Field(min_length=1)
    demand: tuple[DemandRevision, ...] = ()
    receipts: tuple[ReceiptRevision, ...] = ()
    coverage: tuple[CoverageRevision, ...] = ()
    availability_semantics: Literal["AS_OF_RECORDED", "RETROSPECTIVE_CORRECTED"] = "AS_OF_RECORDED"

    @model_validator(mode="after")
    def scoped_ownership(self) -> Self:
        keys = [s.key for s in self.scope]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate series scope")
        if any(key.organization_id != self.organization_id for key in keys):
            raise ValueError("Cross-organization scope")
        for row in (*self.demand, *self.receipts, *self.coverage):
            if row.source.organization_id != self.organization_id:
                raise ValueError("Cross-organization historical source")
            if row.source.dataset_id != self.dataset_id:
                raise ValueError("Historical source is outside selected dataset")
        for site_id in {key.site_id for key in keys}:
            if len({s.timezone for s in self.scope if s.key.site_id == site_id}) != 1:
                raise ValueError("Inconsistent site timezone")
        for product_id in {key.product_id for key in keys}:
            if len({s.unit for s in self.scope if s.key.product_id == product_id}) != 1:
                raise ValueError("Inconsistent product base unit")
        return self


class ForecastPolicy(Contract):
    """Sparse thresholds must be selected explicitly; no production defaults."""

    policy_version: str = Field(min_length=1)
    sparse_window_days: int = Field(ge=1, le=366, strict=True)
    sparse_min_samples: int = Field(ge=1, strict=True)
    strategy: Strategy = "SEASONAL_NAIVE"
    allow_fallback: bool = False
    allow_fulfilled_proxy: bool = False
    # Mixed-basis histories require a second explicit choice (OPEN-13).
    allow_mixed_proxy_history: bool = False
    preprocessing_version: Literal["preserve-gaps-v1"] = "preserve-gaps-v1"
    postprocessing_version: Literal["reject-invalid-v1"] = "reject-invalid-v1"
    adapter_version: Literal["core-v1", "chronos2-univariate-cpu-f32-v1"] = "core-v1"
    provider_package_version: str | None = None
    checkpoint: str | None = None
    checkpoint_revision: str | None = None

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if self.sparse_min_samples > self.sparse_window_days:
            raise ValueError("Sparse minimum exceeds calendar window")
        return self


class DailyObservation(Contract):
    day: date
    value: Quantity | None
    is_missing: bool
    target_basis: Basis
    source_classifications: tuple[Classification, ...] = ()
    sources: tuple[SourceRevision, ...] = ()
    receipt_line_ids: tuple[UUID, ...] = ()
    requested_units: Quantity | None = None
    fulfilled_units: Quantity | None = None
    unmet_units: Quantity | None = None
    quality_flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def consistent_missingness(self) -> Self:
        if self.is_missing != (self.value is None):
            raise ValueError("Missing flag contradicts value")
        if self.value is not None and not self.sources:
            raise ValueError("Observed values require source revisions")
        if self.value is not None and self.target_basis in {"UNAVAILABLE", "MIXED"}:
            raise ValueError("Each observed day requires its exact target basis")
        if self.value is None and self.target_basis != "UNAVAILABLE":
            raise ValueError("Missing days cannot claim an observed target basis")
        return self


class Diagnostics(Contract):
    observed_count: int
    missing_count: int
    proxy_fraction: float
    reference_weekday_count: int
    trailing_sample_count: int


class PreparedSeries(Contract):
    scope: SeriesScope
    observations: tuple[DailyObservation, ...]
    diagnostics: Diagnostics
    target_basis: Basis
    warnings: tuple[str, ...] = ()


class HistoricalSnapshot(Contract):
    """Exact selected fact content, including complete receipt headers/line sets."""

    demand: tuple[DemandRevision, ...]
    receipts: tuple[ReceiptRevision, ...]
    coverage: tuple[CoverageRevision, ...]


class ForecastInput(Contract):
    schema_version: Literal["forecast-input-experimental-v1"] = "forecast-input-experimental-v1"
    organization_id: UUID
    dataset_id: UUID
    data_cutoff_date: date
    snapshot_as_of: AwareDatetime
    horizon_days: Literal[7] = 7
    revision_selection_version: Literal["dataset-max-visible-revision-v1"] = (
        "dataset-max-visible-revision-v1"
    )
    availability_semantics: Literal["AS_OF_RECORDED", "RETROSPECTIVE_CORRECTED"]
    policy: ForecastPolicy
    source_snapshot: HistoricalSnapshot
    series: tuple[PreparedSeries, ...] = Field(min_length=1)
    input_hash: str

    @model_validator(mode="after")
    def valid_frozen_context(self) -> Self:
        keys = [row.scope.key for row in self.series]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate prepared series")
        selected_sources = {
            row.source
            for row in (
                *self.source_snapshot.demand,
                *self.source_snapshot.receipts,
                *self.source_snapshot.coverage,
            )
        }
        snapshot_rows = (
            *self.source_snapshot.demand,
            *self.source_snapshot.receipts,
            *self.source_snapshot.coverage,
        )
        for row in snapshot_rows:
            source = row.source
            day = row.local_day if isinstance(row, ReceiptRevision) else row.day
            if (
                source.organization_id != self.organization_id
                or source.dataset_id != self.dataset_id
                or source.recorded_at > self.snapshot_as_of
                or day > self.data_cutoff_date
            ):
                raise ValueError("Historical snapshot violates its frozen temporal/ownership scope")
        for series in self.series:
            if series.scope.key.organization_id != self.organization_id:
                raise ValueError("Cross-organization prepared series")
            observations = series.observations
            if not observations or observations[-1].day != self.data_cutoff_date:
                raise ValueError("Prepared calendar must end at the cutoff")
            if any(
                b.day - a.day != timedelta(days=1)
                for a, b in zip(observations, observations[1:], strict=False)
            ):
                raise ValueError("Prepared calendar must be ordered, unique and gap-explicit")
            for observation in observations:
                if (
                    observation.target_basis == "FULFILLED_PROXY"
                    and not self.policy.allow_fulfilled_proxy
                ):
                    raise ValueError("Proxy history requires opt-in")
                if series.scope.key.target_type == "DONATION" and observation.target_basis not in {
                    "RECEIVED",
                    "UNAVAILABLE",
                }:
                    raise ValueError("Donation target must be actual received units")
                if (
                    series.scope.key.target_type == "DEMAND"
                    and observation.target_basis == "RECEIVED"
                ):
                    raise ValueError("Demand target cannot contain receipt observations")
                for source in observation.sources:
                    if (
                        source.organization_id != self.organization_id
                        or source.dataset_id != self.dataset_id
                        or source.recorded_at > self.snapshot_as_of
                    ):
                        raise ValueError(
                            "Prepared source violates ownership/dataset/as-of boundary"
                        )
                    if source not in selected_sources:
                        raise ValueError("Prepared source is absent from exact historical snapshot")
        return self


class ForecastPoint(Contract):
    day: date
    central_estimate: Quantity
    estimate_kind: Literal["POINT", "MEAN", "MEDIAN"]
    p10: Quantity | None = None
    p50: Quantity | None = None
    p90: Quantity | None = None
    interval_method: Literal["NONE", "MODEL_QUANTILES"] = "NONE"
    postprocessing_policy: Literal["reject-invalid-v1"] = "reject-invalid-v1"

    @model_validator(mode="after")
    def valid_quantiles(self) -> Self:
        values = [v for v in (self.p10, self.p50, self.p90) if v is not None]
        if values != sorted(values):
            raise ValueError("Crossed quantiles")
        if self.interval_method == "NONE" and values:
            raise ValueError("Quantiles require an honest interval method")
        if self.interval_method == "MODEL_QUANTILES" and not values:
            raise ValueError("Model quantiles require actual quantiles")
        if self.estimate_kind == "MEDIAN" and self.p50 != self.central_estimate:
            raise ValueError("Median central estimate must equal p50")
        return self


class ProviderIdentity(Contract):
    name: str = Field(min_length=1)
    adapter_version: str = "core-v1"
    package_version: str | None = None
    checkpoint: str | None = None
    checkpoint_revision: str | None = None


class StructuredError(Contract):
    code: str
    message: str
    category: Literal["DATA", "PROVIDER", "DEADLINE"]
    retryable: bool = False


class ForecastSeriesResult(Contract):
    result_id: UUID
    scope: SeriesScope
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA", "FAILED"]
    target_basis: Basis
    diagnostics: Diagnostics
    actual_provider: ProviderIdentity | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    input_hash: str
    generated_at: AwareDatetime
    warnings: tuple[str, ...] = ()
    errors: tuple[StructuredError, ...] = ()
    points: tuple[ForecastPoint, ...] = ()

    @model_validator(mode="after")
    def available_points(self) -> Self:
        if self.status == "AVAILABLE":
            if self.actual_provider is None or len(self.points) != 7 or self.errors:
                raise ValueError("Available series requires provider and seven valid points")
        elif self.points or self.actual_provider is not None or not self.errors:
            raise ValueError("Unavailable series requires errors and no fabricated output")
        if self.fallback_used and (self.fallback_reason is None or self.actual_provider is None):
            raise ValueError("Fallback requires actual provider and reason")
        return self


class ForecastOutput(Contract):
    schema_version: Literal["forecast-output-experimental-v1"] = "forecast-output-experimental-v1"
    run_id: UUID
    input_hash: str
    data_cutoff_date: date
    generated_at: AwareDatetime
    completed_at: AwareDatetime
    # Persisted planning_ready belongs to the future transactional publisher.
    ready_for_publication: bool
    partial_scope: bool
    actual_providers: tuple[str, ...]
    warnings: tuple[str, ...]
    series: tuple[ForecastSeriesResult, ...]

    @model_validator(mode="after")
    def consistent_publication(self) -> Self:
        keys = [row.scope.key for row in self.series]
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("Output requires unique series identities")
        required = [row for row in self.series if row.scope.required]
        ready = bool(required) and all(row.status == "AVAILABLE" for row in required)
        if self.ready_for_publication != ready:
            raise ValueError("Planning readiness contradicts required series outcomes")
        expected = {self.data_cutoff_date + timedelta(days=i) for i in range(1, 8)}
        for row in self.series:
            if row.input_hash != self.input_hash:
                raise ValueError("Output input identity mismatch")
            if row.status == "AVAILABLE" and (
                {point.day for point in row.points} != expected
                or [point.day for point in row.points] != sorted(expected)
            ):
                raise ValueError("Output requires seven unique future dates")
        providers = tuple(
            sorted(
                {row.actual_provider.name for row in self.series if row.actual_provider is not None}
            )
        )
        if self.actual_providers != providers:
            raise ValueError("Output provider summary contradicts actual per-series providers")
        if self.completed_at < self.generated_at:
            raise ValueError("Forecast completion cannot predate generation")
        return self
