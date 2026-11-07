"""v1 network reads: networks, templates, backtest scores and the danger ranking (W0-08)."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.or_inputs import ORContract
from app.schemas.v1_planning import Basis, Id, NetworkMode

TemplateName = Literal[
    "locations", "products", "inventory", "demand_history", "routes", "inbound", "donation_history"
]
REQUIRED_TEMPLATES: tuple[TemplateName, ...] = (
    "locations", "products", "inventory", "demand_history"
)


class Network(ORContract):
    id: UUID
    name: str
    mode: NetworkMode
    timezone: str
    is_sample: bool  # sample networks show "Sample data — fictional"
    dataset_version_id: UUID | None  # None = import not finished
    as_of_date: date | None
    location_count: int = Field(ge=0)
    product_count: int = Field(ge=0)


class NetworkList(ORContract):
    networks: tuple[Network, ...]


class TemplateColumn(ORContract):
    name: str
    required: bool
    unit: str | None
    meaning: str = Field(min_length=1)
    effect_on_plan: str = Field(min_length=1)
    allowed_values: tuple[str, ...] = ()  # e.g. location types for the chosen mode


class Template(ORContract):
    name: TemplateName
    required: bool
    description: str
    columns: tuple[TemplateColumn, ...]
    example_available: bool


class TemplateCatalog(ORContract):
    mode: NetworkMode | None
    templates: tuple[Template, ...]
    notes: tuple[str, ...]  # single timezone; "capacity not provided — no limit assumed"


class BacktestScore(ORContract):
    """V5 §7 WAPE and bias on one shared scored set (W3-F02)."""

    origins_evaluated: int = Field(ge=0)
    wape_pct: Decimal | None
    bias_pct: Decimal | None
    status: Literal["evaluated", "not_evaluated_insufficient_history"]
    scored_points: int = Field(ge=0)


class SeriesBacktest(ORContract):
    location_id: Id
    product_id: Id
    basis: Basis
    score: BacktestScore


class IneligibleSeries(ORContract):
    """Listed, never forecast from zeros (e.g. under 14 days of history, or all blank)."""

    location_id: Id
    product_id: Id
    reason: str


class BacktestResult(ORContract):
    forecast_job_id: UUID
    network_id: UUID
    series: tuple[SeriesBacktest, ...]
    ineligible: tuple[IneligibleSeries, ...]


class DangerRow(ORContract):
    location_id: Id
    rank: int = Field(ge=1)
    score_ratio: Decimal
    band: Literal["high", "medium", "low"]  # thresholds are declared in services/danger
    reason: Literal["unmet", "expiry"]
    driving_product_id: Id
    driving_units: int = Field(ge=0)
    unit: str  # the driving product's own unit; no cross-product total
    first_deficit_date: date | None


class DangerRanking(ORContract):
    network_id: UUID
    forecast_run_id: UUID
    mode: NetworkMode
    rows: tuple[DangerRow, ...]


class NetworkForecastRequest(ORContract):
    """POST /networks/{id}/forecasts: forecast one dataset version through forecast.v1."""

    dataset_version_id: UUID
