"""Public contracts for saved dashboard and physical-stock shortage reads.

They describe the existing route JSON exactly: timestamps keep ``datetime.isoformat()``
and quantities stay decimal strings for JS precision.
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field, PlainSerializer

from app.schemas.inventory_api import InventorySnapshot
from app.schemas.operational import Contract

IsoDatetime = Annotated[
    AwareDatetime,
    PlainSerializer(datetime.isoformat, return_type=str, when_used="json"),
]
UnitString = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^(0|[1-9][0-9]*)$",
        description="Nonnegative base units; no digit cap (eligible_end sums lots).",
    ),
]


class LatestForecast(Contract):
    id: UUID
    job_id: UUID
    planning_ready: bool
    recorded_at: IsoDatetime


class DashboardSummary(Contract):
    observed_at: IsoDatetime
    inventory: tuple[InventorySnapshot, ...]
    latest_forecast: LatestForecast | None


class ShortageDay(Contract):
    day: date
    demand: UnitString
    served: UnitString
    unmet: UnitString
    eligible_end: UnitString = Field(description="Eligible physical stock left at day end.")


class ShortageSeries(Contract):
    site_id: UUID
    product_id: UUID
    base_unit: str
    actual_provider: str
    fallback_used: bool
    fallback_reason: str | None
    days: tuple[ShortageDay, ...]


class ShortageProjection(Contract):
    forecast_run_id: UUID
    observed_at: IsoDatetime
    series: tuple[ShortageSeries, ...]
    warnings: tuple[str, ...]
