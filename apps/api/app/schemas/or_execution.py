"""Closed input envelope for registered OR handlers, never arbitrary task execution."""
from uuid import UUID

from pydantic import Field

from app.schemas.or_inputs import ORContract, ORScenarioPayload
from app.schemas.planning_primitives import AllocationMethod


class ORExecutionInput(ORContract):
    scenario_id: UUID
    scenario: ORScenarioPayload
    settings: dict
    method: AllocationMethod | None
    org_epoch: int = Field(strict=True, ge=0)
