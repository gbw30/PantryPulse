"""v1 network reads: networks, templates, backtest scores and the danger ranking (W0-08)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.or_inputs import ORContract
from app.schemas.v1_planning import Basis, Id, NetworkMode
from app.services.jobs.contracts import AttemptState

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


class LocationSummary(ORContract):
    """One location of a dataset version, for the atlas and names (CR-w1-web-1)."""

    location_id: Id  # the ID from locations.csv
    name: str
    role: Literal["hub", "pantry", "distribution_center", "store"]
    city: str
    state: str
    latitude: Decimal | None  # both null when geocoding failed and no coordinates were given
    longitude: Decimal | None
    coordinates_source: Literal["user", "census_geocoder"] | None


class LocationList(ORContract):
    """GET /networks/{id}/locations: the network's latest dataset version."""

    network_id: UUID
    dataset_version_id: UUID
    locations: tuple[LocationSummary, ...]  # ordered by location_id


class ForecastRunSummary(ORContract):
    """One forecast.v1 job for the network (CR-w1-web-2)."""

    job_id: UUID
    forecast_run_id: UUID | None  # None until the job publishes a run
    dataset_version_id: UUID
    state: AttemptState
    recorded_at: datetime


class ForecastRunList(ORContract):
    """GET /networks/{id}/forecasts: newest first, so the UI finds runs after a reload."""

    network_id: UUID
    runs: tuple[ForecastRunSummary, ...]


Daily = tuple[Annotated[int, Field(ge=0)] | None, ...]  # one value per date; None = unknown


class ProductProjection(ORContract):
    """One product at one location over the projection dates, in the product's own unit."""

    product_id: Id
    unit: str
    dates: tuple[date, ...]
    target: Daily
    served: Daily
    unmet: Daily
    eligible_stock_now: int = Field(ge=0)
    expiring_unsold: Daily | None  # None = no expiry data for this product
    donation_forecast: Daily | None  # None = no donation history for this location


class LocationProjection(ORContract):
    """GET /networks/{id}/projection?forecast_run_id=&location_id= (CR-w1-web-3).

    Raw per-product projections for the site inspector; no cross-product totals."""

    network_id: UUID
    forecast_run_id: UUID
    location_id: Id
    mode: NetworkMode
    products: tuple[ProductProjection, ...]
