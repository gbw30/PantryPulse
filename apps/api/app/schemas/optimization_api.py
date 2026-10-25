"""Connected simulated planning contracts. No client-supplied source facts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.or_inputs import (
    Capacities,
    DemandModifier,
    ORContract,
    ORPolicy,
    ORScenarioPayload,
    Reserve,
    Route,
    VulnerabilityAttributes,
)
from app.schemas.or_outputs import ComparisonResult
from app.schemas.planning_primitives import TransferMode


class HandlingCoefficient(ORContract):
    product_id: UUID
    coefficient: int = Field(strict=True, ge=1, le=1000)


class AssumptionsPayload(ORContract):
    schema_version: Literal["planning-assumptions-v1"] = "planning-assumptions-v1"
    classification: Literal["SIMULATED"] = "SIMULATED"
    policy: ORPolicy
    routes: tuple[Route, ...] = Field(max_length=182)
    capacities: Capacities
    reserves: tuple[Reserve, ...] = Field(max_length=28)
    vulnerability_attributes: tuple[VulnerabilityAttributes, ...] = Field(max_length=12)
    handling: tuple[HandlingCoefficient, ...] = Field(min_length=1, max_length=2)


class AssumptionsRequest(ORContract):
    name: str = Field(min_length=1, max_length=120)
    parent_id: UUID
    payload: AssumptionsPayload


class AssumptionsResult(ORContract):
    id: UUID
    parent_id: UUID | None
    name: str
    content_hash: str
    recorded_at: datetime
    payload: AssumptionsPayload


class ScenarioRequest(ORContract):
    forecast_run_id: UUID
    assumptions_id: UUID
    parent_id: UUID | None = None
    expected_source_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    transfer_mode: TransferMode
    planning_days: int = Field(strict=True, ge=1, le=3)
    modifiers: tuple[DemandModifier, ...] = Field(max_length=28)


class ScenarioResult(ORContract):
    id: UUID
    parent_id: UUID | None
    forecast_run_id: UUID
    assumptions_id: UUID
    recorded_at: datetime
    stale: bool
    historical: bool
    payload: ORScenarioPayload


class ComparisonRequest(ORContract):
    scenario_id: UUID
    search_seconds: int = Field(default=120, strict=True, ge=1, le=300)


class SavedComparison(ORContract):
    id: UUID
    scenario_id: UUID
    recorded_at: datetime
    settings: dict[str, str | int]
    stale: bool
    historical: bool
    result: ComparisonResult


class SavedItem(ORContract):
    id: UUID
    recorded_at: datetime
    label: str


class PlanningCatalog(ORContract):
    source_revision: str
    assumptions: tuple[SavedItem, ...]
    forecasts: tuple[SavedItem, ...]
    scenarios: tuple[SavedItem, ...]
    comparisons: tuple[SavedItem, ...]
    next_before: datetime | None
    next_before_id: UUID | None
