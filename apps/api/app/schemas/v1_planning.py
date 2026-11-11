"""v1 planning contract (W0-08, option A): the or-input-v3 package, method sets and results.

or-input-v2 (`or_inputs.py`) and or-comparison.v2 stay untouched (V1-A22). Network mode and
allocation methods use the README's API names; the database stores mode in lowercase
(`app/models/networks.py`). Quantities are integer units of each product's own unit; nothing
here sums different products into one total.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.schemas.or_inputs import (
    AttributeCoefficient,
    Bool,
    CapacityCount,
    CostCount,
    Count,
    Hash,
    ORContract,
    ORPolicy,
    decimal_literal,
)
from app.schemas.planning_primitives import TransferMode
from app.schemas.v1_envelope import (
    MAX_BATCHES,
    MAX_FORECAST_SERIES,
    MAX_LOCATIONS,
    MAX_PRODUCTS,
)
from app.services.jobs.registry import InputRejected
from app.services.optimization.decisions import DECISION_IDS, POLICY_VERSION

NetworkMode = Literal["PANTRY", "RETAIL"]
LocationRole = Literal["hub", "pantry", "distribution_center", "store"]
AllocationMethod = Literal[
    "NO_TRANSFERS", "EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP", "EGP_PI_INSPIRED",
    "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED",
]
Measure = Literal["UNITS", "USD"]
RouteMethod = Literal["straight_line_estimate", "google_road", "routes_csv"]
ExplanationKind = Literal["proven_binding", "inferred"]
NativeStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
Basis = Literal["demand", "sales"]
Id = Annotated[str, Field(min_length=1, max_length=64)]

METHODS_BY_MODE: dict[str, tuple[str, ...]] = {
    "PANTRY": (
        "NO_TRANSFERS", "EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP", "EGP_PI_INSPIRED"
    ),
    "RETAIL": ("NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"),
}
ROLES_BY_MODE: dict[str, tuple[str, ...]] = {
    "PANTRY": ("hub", "pantry"),
    "RETAIL": ("distribution_center", "store"),
}
VULNERABILITY_ATTRIBUTES = ("poverty_rate", "snap_rate")  # VulnerabilityV3, V1-SPEC §6.2
# V1-SPEC §6.2: the connected flow's λ/β, thresholds and 50/50 weights, on the v1 attributes.
DEFAULT_PANTRY_POLICY = ORPolicy(
    version=POLICY_VERSION, purpose="PRIMARY", lambda_percent=100, beta_percent=50,
    coefficients=tuple(AttributeCoefficient(attribute_id=a, percent=50)
                       for a in VULNERABILITY_ATTRIBUTES),
    ap_threshold=7500, rp_threshold=2500, ap_cap_bp=2500, rp_cap_bp=2500,
    gamma_ap_percent=100, gamma_rp_percent=100, epsilon_cost_bp=100, epsilon_waste_bp=100,
    decision_ids=DECISION_IDS,
)
NOT_AT_RISK_LABEL = "not at risk; not optimized"
NON_ADDITIVE_LABEL = (
    "effect of this action given the rest of the plan; effects don't add up across actions"
)


def require_methods_for_mode(mode: NetworkMode, methods: Sequence[AllocationMethod]) -> None:
    """Pantry and Retail each accept only their own method set (422 otherwise)."""
    foreign = [m for m in methods if m not in METHODS_BY_MODE[mode]]
    if foreign:
        raise InputRejected("METHOD_NOT_IN_MODE", f"{mode} does not offer {', '.join(foreign)}")


def _literal(value: str | None) -> str | None:
    return None if value is None else decimal_literal(value, max_value=Decimal(1_000_000))


def _expiry(expiry_date: date | None, non_expiring: bool) -> None:
    # Exactly one of a dated expiry or non_expiring; unknown expiry never enters a scenario.
    if (expiry_date is None) != non_expiring:
        raise ValueError("EXPIRY_DECLARATION_MISMATCH")


class LocationV3(ORContract):
    id: Id
    name: str = Field(min_length=1, max_length=120)
    role: LocationRole


class ProductV3(ORContract):
    id: Id
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=80)
    handling_units_per_unit: int = Field(strict=True, ge=1, le=1000)
    unit_value_usd: str | None  # exact decimal literal; None = USD unavailable for this product

    @field_validator("unit_value_usd")
    @classmethod
    def usd(cls, value: str | None) -> str | None:
        return _literal(value)


class BatchV3(ORContract):
    id: Id
    location_id: Id
    product_id: Id
    quantity: Count
    expiry_date: date | None
    non_expiring: Bool

    @model_validator(mode="after")
    def expiry(self) -> Self:
        _expiry(self.expiry_date, self.non_expiring)
        return self


class DemandSeriesV3(ORContract):
    """Seven planning days of one location × product forecast, with its actual provenance."""

    location_id: Id
    product_id: Id
    basis: Basis
    actual_provider: str = Field(min_length=1)
    fallback_reason: str | None
    central_literals: tuple[str, ...] = Field(min_length=7, max_length=7)
    targets: tuple[Count, ...] = Field(min_length=7, max_length=7)  # rounded daily demand

    @field_validator("central_literals")
    @classmethod
    def central(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(decimal_literal(x) for x in value)


class DonationForecastV3(ORContract):
    """Seven planning days of expected donations at one receiving location × product.

    Display only (V1-SPEC §6.1, V1-A23): forecast, not confirmed; never supply."""

    location_id: Id
    product_id: Id
    actual_provider: str = Field(min_length=1)
    fallback_reason: str | None = Field(min_length=1)  # set = a fallback ran, and why
    central_literals: tuple[str, ...] = Field(min_length=7, max_length=7)

    @field_validator("central_literals")
    @classmethod
    def central(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(decimal_literal(x) for x in value)


class InboundV3(ORContract):
    """A scheduled delivery inside the horizon; counted once, never also as on-hand stock."""

    id: Id
    location_id: Id
    product_id: Id
    quantity: Count
    arrival_date: date
    expiry_date: date | None
    non_expiring: Bool

    @model_validator(mode="after")
    def expiry(self) -> Self:
        _expiry(self.expiry_date, self.non_expiring)
        return self


class RouteV3(ORContract):
    from_location_id: Id
    to_location_id: Id
    travel_days: int = Field(strict=True, ge=1, le=7)
    method: RouteMethod
    road_miles: str | None
    # routes.csv columns (V1-SPEC §6.1); None = not given, so no route cost or no per-batch limit.
    cost_per_handling_unit_usd: str | None  # exact decimal literal
    capacity_per_batch: CapacityCount | None  # handling units per shipment, floored from the CSV

    @field_validator("road_miles", "cost_per_handling_unit_usd")
    @classmethod
    def miles(cls, value: str | None) -> str | None:
        return _literal(value)

    @model_validator(mode="after")
    def no_self(self) -> Self:
        if self.from_location_id == self.to_location_id:
            raise ValueError("SELF_TRANSFER")
        return self


class CapacityV3(ORContract):
    """Per-day capacities in handling units.

    None means "capacity not provided — no limit assumed".
    """

    location_id: Id
    receiving: CapacityCount | None
    dispatch: CapacityCount | None
    storage: CapacityCount | None


class ReserveV3(ORContract):
    location_id: Id
    product_id: Id
    floor: Count


class RetailWeights(ORContract):
    w_exp: int = Field(strict=True, ge=0, le=1000)
    w_lost: int = Field(strict=True, ge=0, le=1000)

    @model_validator(mode="after")
    def one_positive(self) -> Self:
        if self.w_exp == 0 and self.w_lost == 0:  # the objective would be constant (E-1)
            raise ValueError("RETAIL_WEIGHTS_ALL_ZERO")
        return self


class VulnerabilityV3(ORContract):
    location_id: Id
    poverty_rate: str
    snap_rate: str
    # "ACS 5-year YYYY, tract NNNN", "manual" (on a sample network: "sample values"), or one
    # manual rate beside a looked-up one:
    # "poverty_rate: manual; snap_rate: ACS 5-year YYYY, tract NNNN" (either order)
    source: str = Field(min_length=1)

    @field_validator("poverty_rate", "snap_rate")
    @classmethod
    def rate(cls, value: str) -> str:
        return decimal_literal(value, max_value=Decimal(1))


class ORInputV3(ORContract):
    schema_version: Literal["or-input-v3"] = "or-input-v3"
    network_id: UUID
    organization_id: UUID
    dataset_version_id: UUID
    forecast_run_id: UUID
    mode: NetworkMode
    transfer_mode: TransferMode  # explicit, no default
    timezone: str
    snapshot_as_of: date
    first_planning_date: date
    horizon_days: Literal[7] = 7
    # Explicit in PANTRY (BD-50 window, §6.2 policy), absent in RETAIL; no defaults.
    planning_days: Annotated[int, Field(strict=True, ge=1, le=3)] | None
    policy: ORPolicy | None
    locations: tuple[LocationV3, ...] = Field(min_length=2, max_length=MAX_LOCATIONS)
    products: tuple[ProductV3, ...] = Field(min_length=1, max_length=MAX_PRODUCTS)
    batches: tuple[BatchV3, ...] = Field(max_length=MAX_BATCHES)
    demand: tuple[DemandSeriesV3, ...] = Field(max_length=MAX_FORECAST_SERIES)
    # Omitted from dumps when empty, so scenarios frozen before W5-L01 keep their hash.
    donations: tuple[DonationForecastV3, ...] = Field(
        default=(), max_length=MAX_FORECAST_SERIES, exclude_if=lambda rows: not rows,
        description="Expected donations (forecast, not confirmed) for display only: never "
        "supply, never an allocation, projection or danger-score input.",
    )
    inbound: tuple[InboundV3, ...]
    inbound_file_provided: Bool  # False → "no scheduled deliveries provided"
    routes: tuple[RouteV3, ...]
    capacities: tuple[CapacityV3, ...]
    global_handling: CapacityCount | None
    cost_budget_minor: CostCount | None  # off unless the user sets one
    reserves: tuple[ReserveV3, ...]
    retail_weights: RetailWeights | None  # required in RETAIL, absent in PANTRY
    vulnerability: tuple[VulnerabilityV3, ...]
    assumptions: tuple[str, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("UNKNOWN_TIMEZONE") from exc
        if self.first_planning_date != self.snapshot_as_of + timedelta(days=1):
            raise ValueError("FIRST_PLANNING_DATE_NOT_DAY_AFTER_SNAPSHOT")  # V1-SPEC §6.1
        if any(loc.role not in ROLES_BY_MODE[self.mode] for loc in self.locations):
            raise ValueError("ROLE_NOT_IN_MODE")
        if (self.retail_weights is None) != (self.mode == "PANTRY"):
            raise ValueError("RETAIL_WEIGHTS_REQUIRED_ONLY_IN_RETAIL")
        if {self.planning_days is None, self.policy is None} != {self.mode == "RETAIL"}:
            raise ValueError("WINDOW_AND_POLICY_ONLY_IN_PANTRY")
        if self.policy and any(c.attribute_id not in VULNERABILITY_ATTRIBUTES
                               for c in self.policy.coefficients):
            raise ValueError("UNKNOWN_POLICY_ATTRIBUTE")
        locations = {loc.id for loc in self.locations}
        products = {p.id for p in self.products}
        if len(locations) != len(self.locations) or len(products) != len(self.products):
            raise ValueError("DUPLICATE_ID")
        rows = (*self.batches, *self.demand, *self.donations, *self.inbound, *self.reserves)
        if any(r.location_id not in locations or r.product_id not in products for r in rows):
            raise ValueError("UNKNOWN_REFERENCE")
        if any({r.from_location_id, r.to_location_id} - locations for r in self.routes):
            raise ValueError("UNKNOWN_REFERENCE")
        if any(r.location_id not in locations for r in (*self.capacities, *self.vulnerability)):
            raise ValueError("UNKNOWN_REFERENCE")
        # A repeated row would be counted twice (demand, stock) or make an ID ambiguous.
        keys = (
            [b.id for b in self.batches], [i.id for i in self.inbound],
            [(d.location_id, d.product_id) for d in self.demand],
            [(d.location_id, d.product_id) for d in self.donations],
            [(r.from_location_id, r.to_location_id) for r in self.routes],
            [(r.location_id, r.product_id) for r in self.reserves],
            [c.location_id for c in self.capacities], [v.location_id for v in self.vulnerability],
        )
        if any(len(set(k)) != len(k) for k in keys):
            raise ValueError("DUPLICATE_ROW")
        if self.inbound and not self.inbound_file_provided:
            raise ValueError("INBOUND_WITHOUT_FILE")
        last_day = self.first_planning_date + timedelta(days=self.horizon_days - 1)
        if any(not self.first_planning_date <= i.arrival_date <= last_day for i in self.inbound):
            raise ValueError("INBOUND_OUTSIDE_HORIZON")
        return self


class ScenarioOptions(ORContract):
    """POST /networks/{id}/scenarios. Blank capacity = no limit, reserve floors 0, budget off."""

    dataset_version_id: UUID
    forecast_run_id: UUID
    transfer_mode: TransferMode  # explicit, no default
    reserve_floors: tuple[ReserveV3, ...] = ()
    retail_weights: RetailWeights | None = None  # Retail default w_exp = w_lost = 1
    cost_budget_minor: CostCount | None = None
    planning_days: Annotated[int, Field(strict=True, ge=1, le=3)] | None = None  # PANTRY: required
    policy: ORPolicy | None = None  # PANTRY: DEFAULT_PANTRY_POLICY when omitted


def resolve_window_and_policy(
    mode: NetworkMode, options: ScenarioOptions
) -> tuple[int | None, ORPolicy | None]:
    """The window and policy a new scenario freezes (422 when they don't fit the mode)."""
    if mode == "RETAIL":
        if options.planning_days is not None or options.policy is not None:
            raise InputRejected(
                "WINDOW_AND_POLICY_ONLY_IN_PANTRY",
                "Retail measures all seven days and has no EGP policy",
            )
        return None, None
    if options.planning_days is None:
        raise InputRejected("PLANNING_DAYS_REQUIRED", "Choose a 1-3 day allocation window")
    policy = options.policy or DEFAULT_PANTRY_POLICY
    if any(c.attribute_id not in VULNERABILITY_ATTRIBUTES for c in policy.coefficients):
        raise InputRejected(
            "UNKNOWN_POLICY_ATTRIBUTE", "Policy weights may use only poverty_rate and snap_rate"
        )
    return options.planning_days, policy


class ScenarioV3(ORContract):
    id: UUID
    network_id: UUID
    recorded_at: datetime
    content_hash: Hash
    payload: ORInputV3


class ComparisonRequestV3(ORContract):
    scenario_id: UUID
    methods: tuple[AllocationMethod, ...] = Field(min_length=1, max_length=5)
    measure: Measure

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("DUPLICATE_METHOD")
        return self


class ProductSolve(ORContract):
    product_id: Id
    native_status: NativeStatus | None  # None when the product was not solved
    gap: str | None  # relative gap literal for FEASIBLE; never relabeled OPTIMAL
    label: str | None  # NOT_AT_RISK_LABEL for products left out of optimization


class TransferV3(ORContract):
    id: Id
    product_id: Id
    from_location_id: Id
    to_location_id: Id
    quantity: Count
    ship_date: date
    arrival_date: date
    batch_ids: tuple[Id, ...] = Field(min_length=1)


class LocationEffect(ORContract):
    """Per location and product, in that product's unit; never summed across products."""

    location_id: Id
    product_id: Id
    unmet_without_plan: Count
    unmet_with_plan: Count
    expired_without_plan: Count
    expired_with_plan: Count


class SolverRun(ORContract):
    """How an optimizing method's per-product solves ran, for replay (solver S2)."""

    engine: Literal["OR-Tools CP-SAT"]
    version: str = Field(min_length=1, max_length=40)
    seed: int = Field(strict=True, ge=0)
    workers: int = Field(strict=True, ge=1)


class MethodResult(ORContract):
    method: AllocationMethod
    measure: Measure
    native_status: NativeStatus | None  # None for deterministic baselines
    verified: Bool  # only verified results are published with a plan
    failure_reason: str | None
    products: tuple[ProductSolve, ...]
    transfers: tuple[TransferV3, ...]
    effects: tuple[LocationEffect, ...]
    objective: str | None
    usd_unavailable_reason: str | None
    retail_weights: RetailWeights | None
    labels: tuple[str, ...]  # e.g. "optimized per product, with shared capacity split in advance"
    solver: SolverRun | None = None  # None for the deterministic baselines

    @model_validator(mode="after")
    def published_only_if_verified(self) -> Self:
        if self.transfers and not self.verified:
            raise ValueError("UNVERIFIED_RESULT_HAS_PLAN")
        return self


class ComparisonResultV3(ORContract):
    scenario_id: UUID
    scenario_hash: Hash
    mode: NetworkMode
    measure: Measure
    methods: tuple[MethodResult, ...] = Field(min_length=1, max_length=5)


class SavedComparisonV3(ORContract):
    id: UUID
    network_id: UUID
    scenario_id: UUID
    recorded_at: datetime
    result: ComparisonResultV3
    # The frozen scenario's notes, for pages opened without it (CR-w1-web-6)
    assumptions: tuple[str, ...]
    inbound_file_provided: Bool


class ActionEffect(ORContract):
    """Remove-one effect of one transfer given the rest of the plan; there is no total."""

    product_id: Id
    unit: str = Field(min_length=1, max_length=80)  # the product's own unit (CR-w1-web-5)
    sender_unmet_delta: int = Field(strict=True)
    receiver_unmet_delta: int = Field(strict=True)
    expired_delta: int = Field(strict=True)
    # Retail: price × (Δunmet + Δexpired), the dollar value of the units changed; not the
    # objective. None when USD is unavailable.
    usd_delta: str | None


class DecisionAction(ORContract):
    id: Id  # the transfer id
    action_text: str
    why_text: str
    explanation_kind: ExplanationKind
    effect: ActionEffect


class DecisionActions(ORContract):
    comparison_id: UUID
    method: AllocationMethod
    actions: tuple[DecisionAction, ...]
    non_additive_label: Literal[
        "effect of this action given the rest of the plan; effects don't add up across actions"
    ] = NON_ADDITIVE_LABEL


# The web proxy admits export bodies up to 1 MiB; 40,000 real action ids (22 characters) fit.
EXPORT_MAX_ACTIONS = 40_000


class ExportRequest(ORContract):
    action_ids: tuple[Id, ...] = Field(min_length=1, max_length=EXPORT_MAX_ACTIONS)
