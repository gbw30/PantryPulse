"""Saved and pure result contracts for Draft 1.1; no solver or database dependency."""

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.or_inputs import Count, ORContract, Rational
from app.schemas.planning_primitives import AllocationMethod, TransferMode


class RouteQuantity(ORContract):
    route_id: UUID
    product_id: UUID
    units: Count


class TransferAssignment(ORContract):
    original_lot_id: UUID
    route_id: UUID
    source_id: UUID
    destination_id: UUID
    product_id: UUID
    unit: str
    units: Count
    departure: date
    arrival: date
    expires_on: date | None
    source_revision: str
    cost_minor: int = Field(strict=True, ge=0)


class ProjectionDay(ORContract):
    site_id: UUID
    product_id: UUID
    day: date
    demand: Count
    received: int = Field(strict=True, ge=0)
    expired: int = Field(strict=True, ge=0)
    served: Count
    unmet: Count
    on_hand: int = Field(strict=True, ge=0)


class LotTrajectory(ORContract):
    id: str
    original_lot_id: UUID
    site_id: UUID
    product_id: UUID
    arrival: date
    expires_on: date | None
    initial_units: int
    consumed: tuple[int, ...]
    expired: tuple[int, ...]
    end_balances: tuple[int, ...]
    proposed: bool


class TransitDay(ORContract):
    day: date
    product_id: UUID
    units: int


class Exclusion(ORContract):
    resource_id: str
    code: str


class ProjectionReport(ORContract):
    schema_version: Literal["or-projection-v1"] = "or-projection-v1"
    days: tuple[ProjectionDay, ...]
    lots: tuple[LotTrajectory, ...]
    transit: tuple[TransitDay, ...]
    exclusions: tuple[Exclusion, ...]
    blocked_units: tuple[tuple[UUID, int], ...]


class GoalMetric(ORContract):
    site_id: UUID
    product_id: UUID
    target: int
    fulfilled: int
    unmet: int
    service_ratio: Rational | None
    deficit: Rational
    vulnerability: Rational
    weighted_deficit: Rational
    q: int
    q0: int
    ap: bool
    rp: bool
    exact_ap: bool
    exact_rp: bool


class GroupMetric(ORContract):
    product_id: UUID
    size: int
    ap_count: int
    rp_count: int
    ap_excess_numerator: int
    rp_excess_numerator: int


class Metrics(ORContract):
    goals: tuple[GoalMetric, ...]
    groups: tuple[GroupMetric, ...]
    cost_minor: int
    q_cost: int
    waste_by_product: tuple[tuple[UUID, int], ...]
    q_waste_by_product: tuple[tuple[UUID, int], ...]
    W: Rational
    Z: Rational
    W0: Rational
    Z0: Rational
    ap_excess: Rational
    rp_excess: Rational
    classical_objective: Rational
    research_objective: Rational
    warnings: tuple[str, ...]


class Candidate(ORContract):
    route_quantities: tuple[RouteQuantity, ...]
    assignments: tuple[TransferAssignment, ...]
    claimed_metrics: Metrics | None = None


class VerificationReport(ORContract):
    schema_version: Literal["or-verification-v1"] = "or-verification-v1"
    passed: bool
    violations: tuple[str, ...]
    projection: ProjectionReport | None
    metrics: Metrics | None
    operational_hash: str
    candidate_hash: str | None
    verifier_version: Literal["independent-replay-v1"] = "independent-replay-v1"


class MethodOutcome(ORContract):
    schema_version: Literal["or-method-result-v1"] = "or-method-result-v1"
    method: AllocationMethod
    transfer_mode: TransferMode
    operational_hash: str
    policy_hash: str
    settings_hash: str
    decision_ids: tuple[str, ...]
    native_status: str | None
    outcome: Literal["VERIFIED", "FAILED", "TIMED_OUT", "CANCELLED", "INTERRUPTED"]
    candidate: Candidate | None
    verification: VerificationReport | None
    objective: Rational | None
    objective_integer: int | None = None
    objective_scale: Rational | None = None
    solver_version: str | None = None
    search_seconds: float = 0
    total_seconds: float = 0
    native_bound: float | None = None
    gap: float | None = None
    error_code: str | None = None
    termination_reason: str | None = None
    physical_fingerprint: str | None = None
    historical: bool = False
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def readable_only(self):
        if self.outcome == "VERIFIED":
            if (
                self.native_status not in {"OPTIMAL", "FEASIBLE"}
                or self.candidate is None
                or self.verification is None
                or not self.verification.passed
            ):
                raise ValueError("Verified method requires readable checked vector")
        elif self.candidate is not None:
            raise ValueError("Failed outcome cannot expose a vector")
        return self


class ComparisonResult(ORContract):
    schema_version: Literal["or-comparison-v1"] = "or-comparison-v1"
    operational_hash: str
    transfer_mode: TransferMode
    outcome: Literal["SUCCEEDED", "PARTIAL", "FAILED"]
    methods: tuple[MethodOutcome, ...]
    common_differences: dict[str, Any]
    historical: bool
    warnings: tuple[str, ...]
    baseline_metrics: Metrics | None = None
