"""Plan and simulation-review extensions to the canonical connected planning API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.optimization_api import ComparisonRequest
from app.schemas.or_inputs import ORContract
from app.schemas.or_outputs import MethodOutcome
from app.schemas.planning_primitives import AllocationMethod


class PairSubmit(ORContract):
    expected_scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    search_seconds: int = Field(default=120, strict=True, ge=1, le=300)


class PlanSubmit(PairSubmit):
    method: AllocationMethod


class PlanResult(ORContract):
    id: UUID
    scenario_id: UUID
    job_id: UUID
    attempt_id: UUID
    comparison_id: UUID | None
    method: AllocationMethod
    recorded_at: datetime
    settings: dict[str, str | int]
    result_hash: str
    result: MethodOutcome
    stale: bool
    historical: bool


class ReviewRequest(ORContract):
    action: Literal["REVIEWED", "REJECTED"]
    expected_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str | None = Field(default=None, max_length=2000)


class ReviewResult(ORContract):
    id: UUID
    plan_id: UUID
    actor: str
    action: Literal["REVIEWED", "REJECTED"]
    result_hash: str
    note: str | None
    recorded_at: datetime


class AllocationResults(ORContract):
    state: str
    plans: tuple[PlanResult, ...]
    comparison_id: UUID | None


def comparison_request(scenario_id, body):
    return ComparisonRequest(scenario_id=scenario_id, search_seconds=body.search_seconds)
