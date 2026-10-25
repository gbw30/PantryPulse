"""Versioned immutable OR contracts; all policy choices remain provisional Draft 1.1."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.planning_primitives import TransferMode

Count = Annotated[int, Field(strict=True, ge=0, le=100_000)]
CapacityCount = Annotated[int, Field(strict=True, ge=0, le=25_600_000_000)]
CostCount = Annotated[int, Field(strict=True, ge=0, le=25_600_000_000_000)]
Bool = Annotated[bool, Field(strict=True)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ORContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class Rational(ORContract):
    numerator: int = Field(strict=True)
    denominator: int = Field(strict=True, gt=0)

    @model_validator(mode="after")
    def reduced(self) -> Self:
        value = Fraction(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", value.numerator)
        object.__setattr__(self, "denominator", value.denominator)
        return self

    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @classmethod
    def of(cls, value: Fraction | int) -> "Rational":
        value = Fraction(value)
        return cls(numerator=value.numerator, denominator=value.denominator)


def decimal_literal(value: object, *, max_value: Decimal = Decimal(100_000)) -> str:
    # OR-DEC-010 [PROVISIONAL]: exact source strings, never guessed float precision.
    if not isinstance(value, str):
        raise ValueError("Decimal source must be a literal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal source literal") from exc
    if not number.is_finite() or number < 0 or number > max_value:
        raise ValueError("Decimal source outside supported finite nonnegative range")
    if len(number.as_tuple().digits) > 28 or max(0, -number.as_tuple().exponent) > 18:
        raise ValueError("Decimal source precision unsupported")
    text = format(number, "f")
    return (text.rstrip("0").rstrip(".") if "." in text else text) if number else "0"


class SourceRef(ORContract):
    id: UUID
    kind: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_hash: Hash


class Site(ORContract):
    id: UUID
    organization_id: UUID
    role: Literal["HUB", "BENEFICIARY"]
    name: str = Field(min_length=1, max_length=120)
    timezone: str
    source_revision: str = Field(min_length=1)


class Product(ORContract):
    id: UUID
    unit: str = Field(min_length=1, max_length=80)
    handling_coefficient: int = Field(strict=True, ge=1, le=1000)
    source_revision: str = Field(min_length=1)


class ForecastDay(ORContract):
    day: date
    central_literal: str
    p10_literal: str | None
    p50_literal: str | None
    p90_literal: str | None

    @field_validator("central_literal", "p10_literal", "p50_literal", "p90_literal")
    @classmethod
    def literals(cls, value: str | None) -> str | None:
        return None if value is None else decimal_literal(value)

    @model_validator(mode="after")
    def quantiles(self) -> Self:
        ordered = [
            Decimal(x)
            for x in (self.p10_literal, self.p50_literal, self.p90_literal)
            if x is not None
        ]
        if ordered != sorted(ordered):
            raise ValueError("Crossed forecast quantiles")
        return self


class ForecastSeries(ORContract):
    id: UUID
    run_id: UUID
    source_id: UUID
    organization_id: UUID
    site_id: UUID
    product_id: UUID
    unit: str
    timezone: str
    source_revision: str
    actual_provider: str = Field(min_length=1)
    basis: Literal["REQUESTED", "FULFILLED_PROXY"]
    source_classification: Literal["SIMULATED", "OBSERVED", "MIXED"]
    estimate_kind: Literal["POINT", "MEAN", "MEDIAN"]
    interval_method: Literal["NONE", "MODEL_QUANTILES"]
    cutoff: date
    generated_at: AwareDatetime
    committed: Bool
    planning_ready: Bool
    numeric_conversion: Literal["EXACT_LITERAL", "LEGACY_FLOAT_LITERAL"]
    upstream_metadata_json: str | None = None
    days: tuple[ForecastDay, ...] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def available(self) -> Self:
        if not self.committed or not self.planning_ready:
            raise ValueError("SOURCE_NOT_COMMITTED")
        if self.interval_method == "NONE" and any(
            point.p10_literal is not None
            or point.p50_literal is not None
            or point.p90_literal is not None
            for point in self.days
        ):
            raise ValueError("Point forecasts cannot invent quantiles")
        if self.estimate_kind == "MEDIAN" and any(
            p.p50_literal is None or p.central_literal != p.p50_literal for p in self.days
        ):
            raise ValueError("Median requires actual central p50")
        return self


class InventoryLot(ORContract):
    id: UUID
    site_id: UUID
    product_id: UUID
    unit: str
    physical_units: Count
    free_units: Count
    reserved_units: Count
    committed_units: Count
    held_units: Count
    available_on: date
    expires_on: date | None
    eligibility: Literal["ELIGIBLE", "HELD", "UNKNOWN"]
    source_line_id: UUID
    source_revision: str = Field(min_length=1)
    dispatchable: Bool
    commitment_scope_refs: tuple[str, ...]
    commitment_overlaps_demand: Bool

    @model_validator(mode="after")
    def reconcile(self) -> Self:
        # OR-DEC-005 [PROVISIONAL]: disjoint free and protected components.
        if self.physical_units != (
            self.free_units + self.reserved_units + self.committed_units + self.held_units
        ):
            raise ValueError("STOCK_COMPONENT_MISMATCH")
        if (self.committed_units or self.reserved_units) and not self.commitment_scope_refs:
            raise ValueError("Protected stock requires obligation scope references")
        if self.commitment_overlaps_demand:
            raise ValueError("COMMITMENT_SERVICE_OVERLAP_UNSUPPORTED")
        return self


class ConfirmedArrival(ORContract):
    id: UUID
    source_line_id: UUID
    site_id: UUID
    product_id: UUID
    unit: str
    units: Count
    available_on: date
    expires_on: date | None
    eligibility: Literal["ELIGIBLE", "HELD", "UNKNOWN"]
    confirmed: Bool
    already_posted: Bool
    source_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def confirmed_only(self) -> Self:
        if not self.confirmed or self.already_posted:
            raise ValueError("Only unposted confirmed supply enters an OR package")
        return self


class ResidualCapacity(ORContract):
    original: CapacityCount
    fixed_used: CapacityCount
    residual: CapacityCount
    source_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def reconcile(self) -> Self:
        # OR-DEC-017 [PROVISIONAL]: upstream fixed usage deducted exactly once.
        if self.original - self.fixed_used != self.residual:
            raise ValueError("CAPACITY_RESIDUAL_MISMATCH")
        return self


class RouteCost(ORContract):
    product_id: UUID
    cost_minor: int = Field(strict=True, ge=0, le=1_000_000)


class Route(ORContract):
    id: UUID
    source_id: UUID
    destination_id: UUID
    enabled: Bool
    eta_days: int = Field(strict=True, ge=0, le=2)
    capacity: ResidualCapacity
    costs: tuple[RouteCost, ...]
    cost_unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def no_self(self) -> Self:
        if self.source_id == self.destination_id:
            raise ValueError("SELF_TRANSFER")
        return self


class SiteCapacity(ORContract):
    site_id: UUID
    source: ResidualCapacity
    receiving: tuple[ResidualCapacity, ...] = Field(min_length=7, max_length=7)
    storage: tuple[ResidualCapacity, ...] = Field(min_length=7, max_length=7)


class Capacities(ORContract):
    sites: tuple[SiteCapacity, ...]
    global_handling: ResidualCapacity
    cost_budget_minor: CostCount | None


class Reserve(ORContract):
    site_id: UUID
    product_id: UUID
    floors: tuple[Count, ...] = Field(min_length=7, max_length=7)


class AttributeScore(ORContract):
    attribute_id: str = Field(min_length=1)
    score_bp: int = Field(strict=True, ge=0, le=10_000)
    raw_note: str = Field(min_length=1)
    transformation: str = Field(min_length=1)
    transformation_version: str = Field(min_length=1)
    classification: Literal["SIMULATED", "OBSERVED"]


class VulnerabilityAttributes(ORContract):
    site_id: UUID
    scores: tuple[AttributeScore, ...] = Field(min_length=2, max_length=8)


class SourceCoverage(ORContract):
    required_complete: Bool
    excluded_series: tuple[str, ...]
    partial_scope: Bool
    forecast_handoff_hash: Hash | None

    @model_validator(mode="after")
    def complete(self) -> Self:
        if not self.required_complete:
            raise ValueError("SOURCE_COVERAGE_INCOMPLETE")
        if self.excluded_series and not self.partial_scope:
            raise ValueError("Explicit partial scope required")
        return self


# OR-DEC-020 [PROVISIONAL]: structural source coverage, not committed publication.
class ORInputPackage(ORContract):
    schema_version: Literal["or-input-v1"] = "or-input-v1"
    organization_id: UUID
    dataset_id: UUID
    source_kind: Literal["SIMULATED", "LIVE"]
    source_revision_token: str = Field(min_length=1)
    source_refs: tuple[SourceRef, ...] = Field(min_length=1)
    snapshot_as_of: AwareDatetime
    operational_timezone: str
    first_planning_date: date
    sites: tuple[Site, ...] = Field(min_length=2, max_length=14)
    products: tuple[Product, ...] = Field(min_length=1, max_length=2)
    forecasts: tuple[ForecastSeries, ...]
    inventory: tuple[InventoryLot, ...]
    confirmed_arrivals: tuple[ConfirmedArrival, ...]
    routes: tuple[Route, ...] = Field(max_length=182)
    capacities: Capacities
    reserves: tuple[Reserve, ...]
    vulnerability_attributes: tuple[VulnerabilityAttributes, ...]
    source_coverage: SourceCoverage
    source_manifest_hash: Hash
    provenance_warnings: tuple[str, ...]
    decision_ids: tuple[str, ...]

    @model_validator(mode="after")
    def scope(self) -> Self:
        # OR-DEC-001 [PROVISIONAL]: one explicit operational timezone and seven local dates.
        try:
            ZoneInfo(self.operational_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown operational timezone") from exc
        from app.services.optimization.canonical import operational_hash

        if self.source_manifest_hash != operational_hash(self.source_refs):
            raise ValueError("SOURCE_MANIFEST_HASH_MISMATCH")
        if len({ref.id for ref in self.source_refs}) != len(self.source_refs):
            raise ValueError("DUPLICATE_SOURCE_REF")
        if len({forecast.id for forecast in self.forecasts}) != len(self.forecasts):
            raise ValueError("DUPLICATE_FORECAST_RESULT")
        sites = {s.id: s for s in self.sites}
        products = {p.id: p for p in self.products}
        if len(sites) != len(self.sites) or len(products) != len(self.products):
            raise ValueError("DUPLICATE_ID")
        if any(
            s.organization_id != self.organization_id or s.timezone != self.operational_timezone
            for s in self.sites
        ):
            raise ValueError("CROSS_ORGANIZATION_OR_TIMEZONE")
        if (
            sum(s.role == "BENEFICIARY" for s in self.sites) > 12
            or sum(s.role == "HUB" for s in self.sites) > 2
        ):
            raise ValueError("SCOPE_UNSUPPORTED")
        if len(self.inventory) + len(self.confirmed_arrivals) > 256:
            raise ValueError("SCOPE_UNSUPPORTED")
        ids = [x.id for x in (*self.inventory, *self.confirmed_arrivals)]
        lines = [x.source_line_id for x in (*self.inventory, *self.confirmed_arrivals)]
        if len(ids) != len(set(ids)) or len(lines) != len(set(lines)):
            raise ValueError("DUPLICATE_SOURCE_RESOURCE")
        keys = {(s, p) for s in sites for p in products}
        for rows in (self.forecasts, self.reserves):
            if len(rows) != len(keys) or {(r.site_id, r.product_id) for r in rows} != keys:
                raise ValueError("INCOMPLETE_SITE_PRODUCT_COVERAGE")
        dates = tuple(self.first_planning_date + timedelta(days=i) for i in range(7))
        snapshot_day = self.snapshot_as_of.astimezone(ZoneInfo(self.operational_timezone)).date()
        for f in self.forecasts:
            if (
                f.organization_id != self.organization_id
                or f.unit != products[f.product_id].unit
                or f.timezone != self.operational_timezone
            ):
                raise ValueError("FORECAST_SCOPE_MISMATCH")
            if (
                tuple(p.day for p in f.days) != dates
                or f.cutoff != dates[0] - timedelta(days=1)
                or f.generated_at > self.snapshot_as_of
            ):
                raise ValueError("FORECAST_DATE_COVERAGE")
        for resource in (*self.inventory, *self.confirmed_arrivals):
            if resource.site_id not in sites or resource.product_id not in products:
                raise ValueError("UNKNOWN_RESOURCE_REFERENCE")
            if resource.unit != products[resource.product_id].unit:
                raise ValueError("UNIT_MISMATCH")
            # OR-DEC-005 [PROVISIONAL]: original physical stock already exists at snapshot.
            if isinstance(resource, InventoryLot) and resource.available_on > min(
                dates[0], snapshot_day
            ):
                raise ValueError("FUTURE_ON_HAND_STOCK")
        if len({r.id for r in self.routes}) != len(self.routes) or len(
            {(r.source_id, r.destination_id) for r in self.routes}
        ) != len(self.routes):
            raise ValueError("DUPLICATE_ROUTE")
        if len({r.cost_unit for r in self.routes}) > 1:
            raise ValueError("MIXED_COST_UNITS")
        for route in self.routes:
            if route.source_id not in sites or route.destination_id not in sites:
                raise ValueError("UNKNOWN_ROUTE_REFERENCE")
            if len(route.costs) != len(products) or {c.product_id for c in route.costs} != set(
                products
            ):
                raise ValueError("ROUTE_PRODUCT_COST_COVERAGE")
        if len(self.capacities.sites) != len(sites) or {
            c.site_id for c in self.capacities.sites
        } != set(sites):
            raise ValueError("CAPACITY_SITE_COVERAGE")
        beneficiaries = {s.id for s in self.sites if s.role == "BENEFICIARY"}
        if (
            len(self.vulnerability_attributes) != len(beneficiaries)
            or {a.site_id for a in self.vulnerability_attributes} != beneficiaries
        ):
            raise ValueError("ATTRIBUTE_COVERAGE")
        for a in self.vulnerability_attributes:
            if len({x.attribute_id for x in a.scores}) != len(a.scores):
                raise ValueError("DUPLICATE_ATTRIBUTE")
        from app.services.optimization.decisions import DECISION_IDS

        if len(self.decision_ids) != len(DECISION_IDS) or set(self.decision_ids) != set(
            DECISION_IDS
        ):
            raise ValueError("DECISION_COVERAGE")
        return self


class AttributeCoefficient(ORContract):
    attribute_id: str
    percent: int = Field(strict=True, ge=0, le=100)


class ORPolicy(ORContract):
    schema_version: Literal["or-policy-v1"] = "or-policy-v1"
    version: str = Field(min_length=1)
    purpose: Literal["PRIMARY", "ABLATION"]
    lambda_percent: int = Field(strict=True, ge=0, le=100)
    beta_percent: int = Field(strict=True, ge=0, le=100)
    coefficients: tuple[AttributeCoefficient, ...] = Field(min_length=2, max_length=8)
    ap_threshold: int = Field(strict=True, ge=0, le=20_000)
    rp_threshold: int = Field(strict=True, ge=0, le=20_000)
    ap_cap_bp: int = Field(strict=True, ge=0, le=10_000)
    rp_cap_bp: int = Field(strict=True, ge=0, le=10_000)
    gamma_ap_percent: int = Field(strict=True, ge=0, le=1000)
    gamma_rp_percent: int = Field(strict=True, ge=0, le=1000)
    epsilon_cost_bp: int = Field(strict=True, ge=0, le=10_000)
    epsilon_waste_bp: int = Field(strict=True, ge=0, le=10_000)
    decision_ids: tuple[str, ...]

    @model_validator(mode="after")
    def policy(self) -> Self:
        # OR-DEC-006 [PROVISIONAL]: specified grids and active primary penalties.
        if sum(x.percent for x in self.coefficients) != 100:
            raise ValueError("ATTRIBUTE_COEFFICIENT_SUM")
        if len({x.attribute_id for x in self.coefficients}) != len(self.coefficients):
            raise ValueError("DUPLICATE_ATTRIBUTE_COEFFICIENT")
        from app.services.optimization.decisions import DECISION_IDS

        if len(self.decision_ids) != len(DECISION_IDS) or set(self.decision_ids) != set(
            DECISION_IDS
        ):
            raise ValueError("DECISION_COVERAGE")
        if self.purpose == "PRIMARY" and (not self.gamma_ap_percent or not self.gamma_rp_percent):
            raise ValueError("PRIMARY_REQUIRES_ACTIVE_AP_RP")
        return self


class DemandModifier(ORContract):
    site_id: UUID
    product_id: UUID
    mode: Literal["CENTRAL", "CONSERVATIVE"]
    multiplier: str
    buffer_fraction: str | None

    @model_validator(mode="after")
    def modifiers(self) -> Self:
        for name, maximum in (("multiplier", Decimal(3)), ("buffer_fraction", Decimal(1))):
            value = getattr(self, name)
            if value is None:
                continue
            canonical = decimal_literal(value, max_value=maximum)
            if max(0, -Decimal(canonical).as_tuple().exponent) > 4:
                raise ValueError("Scenario modifier requires at most four fractional digits")
            object.__setattr__(self, name, canonical)
        if self.mode == "CENTRAL" and self.buffer_fraction is not None:
            raise ValueError("Central choice cannot have buffer")
        return self


class DemandDay(ORContract):
    day: date
    source_literal: str
    unrounded_literal: str
    units: Count
    method: Literal["CENTRAL", "MODEL_UPPER_QUANTILE", "EXPLICIT_BUFFER"]


class DemandSeries(ORContract):
    site_id: UUID
    product_id: UUID
    unit: str
    days: tuple[DemandDay, ...] = Field(min_length=7, max_length=7)
    forecast_result_id: UUID
    actual_provider: str
    basis: str
    numeric_conversion: Literal["EXACT_LITERAL", "LEGACY_FLOAT_LITERAL"]
    upstream_metadata_json: str | None = None


class CandidateKey(ORContract):
    route_id: UUID
    product_id: UUID


class ProductReference(ORContract):
    product_id: UUID
    units: CapacityCount


class ORScenarioPayload(ORContract):
    # OR-DEC-002 [PROVISIONAL]: explicit mode and bounded one-batch allocation window.
    schema_version: Literal["or-scenario-v1"] = "or-scenario-v1"
    package: ORInputPackage
    policy: ORPolicy
    transfer_mode: TransferMode
    planning_days: int = Field(strict=True, ge=1, le=3)
    intent: Literal["CURRENT", "HISTORICAL_REPLAY"]
    modifiers: tuple[DemandModifier, ...]
    demand: tuple[DemandSeries, ...]
    loading_order: tuple[CandidateKey, ...]
    cost_reference: CostCount
    waste_references: tuple[ProductReference, ...]
    decision_ids: tuple[str, ...]
    policy_hash: str
    operational_hash: str

    @field_validator("transfer_mode", mode="before")
    @classmethod
    def exact_mode(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("Transfer mode must be an exact string")
        return value
