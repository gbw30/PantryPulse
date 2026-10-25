"""Provisional public OR request/response contracts; OpenAPI is the TS authority."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.or_inputs import DemandModifier, ORContract
from app.schemas.or_outputs import ComparisonResult, MethodOutcome
from app.schemas.planning_primitives import AllocationMethod, TransferMode


class LoginRequest(ORContract):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(ORContract):
    actor_id: UUID
    organization_id: UUID
    csrf_token: str
    expires_in_seconds: int


class ResourceCreated(ORContract):
    id: UUID
    content_hash: str


class PackageSummary(ORContract):
    id: UUID
    organization_id: UUID
    dataset_id: UUID
    source_kind: Literal["SIMULATED", "LIVE"]
    content_hash: str
    revision_token: str
    schema_version: str
    created_at: datetime
    payload: dict[str, Any] | None = None


class ScenarioCreate(ORContract):
    input_package_id: UUID
    policy_id: UUID
    transfer_mode: TransferMode
    planning_days: int = Field(strict=True, ge=1, le=3)
    modifiers: tuple[DemandModifier, ...]
    intent: Literal["CURRENT", "HISTORICAL_REPLAY"]
    expected_source_revision: str | None


class SiteLabel(ORContract):
    id: UUID
    name: str


class ProductLabel(ORContract):
    id: UUID
    unit: str


class ScenarioSummary(ORContract):
    id: UUID
    organization_id: UUID
    input_package_id: UUID
    policy_id: UUID
    transfer_mode: TransferMode
    planning_days: int
    intent: str
    operational_hash: str
    policy_hash: str
    source_kind: str
    revision_token: str
    historical: bool
    stale: bool
    created_at: datetime
    decision_ids: tuple[str, ...]
    sites: tuple[SiteLabel, ...]
    products: tuple[ProductLabel, ...]


class PairSubmit(ORContract):
    expected_scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    intent: Literal["CURRENT", "HISTORICAL_REPLAY"]


class PlanSubmit(PairSubmit):
    method: AllocationMethod


class JobAccepted(ORContract):
    job_id: UUID
    attempt_id: UUID
    state: str
    status_url: str
    replayed: bool


class PlanRef(ORContract):
    plan_id: UUID
    method: AllocationMethod
    result_hash: str


class AttemptSummary(ORContract):
    attempt_id: UUID
    attempt_number: int
    state: str
    reason_code: str | None
    enqueued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobSummary(ORContract):
    job_id: UUID
    state: str
    result_completeness: str
    plans: tuple[PlanRef, ...]
    comparison_id: UUID | None
    attempts: tuple[AttemptSummary, ...]
    error_code: str | None
    status_url: str


class PlanSummary(ORContract):
    id: UUID
    scenario_id: UUID
    result_hash: str
    result: MethodOutcome
    historical: bool
    stale: bool


class ComparisonSummary(ORContract):
    id: UUID
    scenario_id: UUID
    result: ComparisonResult
    historical: bool
    stale: bool


class ReviewRequest(ORContract):
    action: Literal["REVIEWED", "REJECTED"]
    expected_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str | None = Field(default=None, max_length=2000)


class ReviewResponse(ORContract):
    id: UUID
    plan_id: UUID
    actor_id: UUID
    action: str
    plan_result_hash: str
    created_at: datetime


class SourcePackageRequest(ORContract):
    organization_id: UUID
    expected_source_revision: str
    result_ids: tuple[UUID, ...]


class ResetRequest(ORContract):
    dataset_id: UUID


class ErrorDetail(ORContract):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(ORContract):
    error: ErrorDetail
    request_id: str


class SeedRequest(ORContract):
    fixture: Literal["six-beneficiary-v1", "ap-ablation-v1", "rp-ablation-v1"]


class SeedResponse(ORContract):
    input_package_id: UUID
    policy_id: UUID
    dataset_id: UUID
    modifiers: tuple[DemandModifier, ...]
    source_revision_token: str
