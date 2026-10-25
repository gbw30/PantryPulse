"""Bounded PP-45 public forecasting contracts; Pydantic is the OpenAPI authority."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.services.forecasting.schemas import Contract, ForecastOutput, ForecastPolicy
from app.services.jobs.contracts import AttemptState


class BaselinePolicy(ForecastPolicy):
    strategy: Literal["SEASONAL_NAIVE", "MOVING_AVERAGE"]


class ForecastRequest(Contract):
    source_id: UUID
    data_cutoff_date: date
    snapshot_as_of: AwareDatetime
    history_start_date: date
    policy: BaselinePolicy
    force_refresh: bool = False

    @model_validator(mode="after")
    def bounded_history(self) -> Self:
        if not 6 <= (self.data_cutoff_date - self.history_start_date).days <= 365:
            raise ValueError("History must contain between 7 and 366 calendar days")
        return self


class LoginRequest(Contract):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(Contract):
    actor_id: UUID
    organization_id: UUID
    csrf_token: str
    expires_in_seconds: int


class LogoutResponse(Contract):
    revoked: Literal[True] = True


class ForecastAccepted(Contract):
    job_id: UUID
    attempt_id: UUID
    state: AttemptState
    replayed: bool
    status_url: str
    result_url: str


class ForecastCancelled(Contract):
    job_id: UUID
    attempt_id: UUID
    state: AttemptState
    completed: bool
    replayed: bool


class AttemptSummary(Contract):
    attempt_id: UUID
    state: AttemptState
    reason_code: str | None
    enqueued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ForecastJob(Contract):
    job_id: UUID
    state: AttemptState
    current_attempt_id: UUID
    attempts: tuple[AttemptSummary, ...]


class ForecastResult(Contract):
    job_id: UUID
    attempt_id: UUID
    planning_ready: bool
    published_at: datetime
    forecast: ForecastOutput


class ErrorDetail(Contract):
    code: str
    message: str
    request_id: UUID


class ErrorEnvelope(Contract):
    error: ErrorDetail


class SourceSummary(Contract):
    id: UUID
    name: str
    classification: Literal["OBSERVED", "SIMULATED"]


class SiteSummary(Contract):
    id: UUID
    name: str
    role: Literal["HUB", "BENEFICIARY"]
    timezone: str


class ProductSummary(Contract):
    id: UUID
    name: str
    base_unit: str


class ForecastCatalog(Contract):
    sources: Annotated[tuple[SourceSummary, ...], Field(max_length=100)]
    sites: Annotated[tuple[SiteSummary, ...], Field(max_length=20)]
    products: Annotated[tuple[ProductSummary, ...], Field(max_length=20)]
