"""scenario-v1: internal operational input contract, not persistence or solver code."""

import json
from datetime import date, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, StrictBool, field_validator, model_validator

from app.schemas.operational import Contract, Nonempty, PositiveCount, Quantity
from app.schemas.planning_primitives import TransferModeSelection
from app.schemas.projection import ProjectionInput

Digest = Annotated[str, Field(strict=True, min_length=64, max_length=64,
                              pattern=r"^[a-f0-9]{64}$")]


def canonical_object(text: str) -> dict:
    """Validate exact JSON bytes for an opaque upstream policy/assumption object.

    Integers are JSON numbers; noninteger exact values use upstream-defined decimal
    strings or rational objects. This does not validate research-policy semantics.
    """
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def reject_number(value):
        raise ValueError("noninteger/nonfinite JSON numbers are not canonical")

    value = json.loads(text, object_pairs_hook=pairs, parse_float=reject_number,
                       parse_constant=reject_number)
    if not isinstance(value, dict):
        raise ValueError("canonical document must be an object")
    if text != json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False):
        raise ValueError("document must use canonical JSON object encoding")
    return value


class SourceReference(Contract):
    kind: Nonempty
    key: Nonempty
    version: Nonempty
    content_hash: Digest


class ScopeExclusion(Contract):
    entity_id: UUID
    reason: Nonempty


class ReceivingCapacity(Contract):
    day: date
    handling_units: Quantity


class ReserveFloor(Contract):
    product_id: UUID
    day: date
    quantity: Quantity


class FrozenSite(Contract):
    site_id: UUID
    role: Literal["HUB", "BENEFICIARY"]
    calendar_version_id: UUID
    timezone: Nonempty
    receiving_capacity: tuple[ReceivingCapacity, ...]
    reserves: tuple[ReserveFloor, ...]


class FrozenProduct(Contract):
    product_id: UUID
    base_unit: Nonempty
    handling_units: PositiveCount


class ProductMovementCost(Contract):
    product_id: UUID
    cost_ticks: Quantity


class FrozenRoute(Contract):
    route_id: UUID
    origin_id: UUID
    destination_id: UUID
    enabled: StrictBool
    transit_days: Annotated[int, Field(strict=True, ge=0, le=6)]
    handling_capacity: Quantity
    unit_costs: tuple[ProductMovementCost, ...]


class FrozenPolicy(Contract):
    policy_id: UUID
    schema_version: Nonempty
    canonical_json: Nonempty

    @field_validator("canonical_json")
    @classmethod
    def check_policy_document(cls, value):
        canonical_object(value)
        return value


class FrozenForecast(Contract):
    forecast_id: UUID
    schema_version: Nonempty
    canonical_json: Nonempty

    @field_validator("canonical_json")
    @classmethod
    def check_forecast_document(cls, value):
        payload = canonical_object(value)
        if not isinstance(payload.get("actual_provider"), str) or not payload["actual_provider"]:
            raise ValueError("frozen forecast must identify its actual provider")
        return value


def required_source_keys(value) -> set[tuple[str, str]]:
    """Derive provenance dependencies; accepting a mapping is not validation."""
    data = value.model_dump() if isinstance(value, OperationalScenario) else value
    org = str(data["organization_id"])
    result = {("SCOPE", org), ("CAPACITY", org), ("CONTRACT", "scenario-v1"),
              ("POLICY", str(data["policy"]["policy_id"]))}
    for site in data["sites"]:
        result.add(("SITE", str(site["site_id"])))
        result.add(("CALENDAR", str(site["calendar_version_id"])))
    for product in data["products"]:
        result.add(("PRODUCT", str(product["product_id"])))
    for route in data["routes"]:
        result.add(("ROUTE", str(route["route_id"])))
    for series in data["series"]:
        result.add(("INVENTORY", f'{series["site_id"]}/{series["product_id"]}'))
        result.add(("FORECAST", str(series["forecast_id"])))
        result.add(("FORECAST_SELECTION", f'{series["site_id"]}/{series["product_id"]}'))
        for lot in series["lots"]:
            result.add(("LOT", str(lot["lot_id"])))
            if lot["source_kind"] == "CONFIRMED":
                result.add(("SUPPLY", lot["source_id"]))
        for item in series["commitments"]:
            result.add(("COMMITMENT", str(item["commitment_id"])))
    return result


def _unique(items, label):
    if len(items) != len(set(items)):
        raise ValueError(f"duplicate {label}")


def _partition(known, included, excluded, label):
    _unique(known, f"network {label}")
    _unique(included, f"included {label}")
    _unique(excluded, f"excluded {label}")
    if set(included) & set(excluded) or set(included) | set(excluded) != set(known):
        raise ValueError(f"{label} scope must explicitly partition known network membership")


class OperationalScenario(Contract, TransferModeSelection):
    schema_version: Literal["scenario-v1"]
    organization_id: UUID
    planning_timezone: Nonempty
    horizon_start: date
    allocation_start: date
    allocation_days: Annotated[int, Field(strict=True, ge=1, le=3)]
    network_site_ids: tuple[UUID, ...]
    network_product_ids: tuple[UUID, ...]
    excluded_sites: tuple[ScopeExclusion, ...]
    excluded_products: tuple[ScopeExclusion, ...]
    sites: Annotated[tuple[FrozenSite, ...], Field(min_length=2)]
    products: Annotated[tuple[FrozenProduct, ...], Field(min_length=1)]
    series: tuple[ProjectionInput, ...]
    routes: tuple[FrozenRoute, ...]
    handling_unit_label: Nonempty
    batch_handling_capacity: Quantity
    cost_unit_label: Nonempty
    policy: FrozenPolicy
    forecasts: tuple[FrozenForecast, ...]
    assumptions_json: Nonempty
    sources: tuple[SourceReference, ...]

    @field_validator("assumptions_json")
    @classmethod
    def check_assumption_document(cls, value):
        canonical_object(value)
        return value

    @model_validator(mode="after")
    def check_frozen_inputs(self) -> Self:
        try:
            ZoneInfo(self.planning_timezone)
        except (KeyError, ValueError) as error:
            raise ValueError("unknown planning timezone") from error
        days = {self.horizon_start + timedelta(days=i) for i in range(7)}
        if (self.allocation_start not in days or
                self.allocation_start + timedelta(days=self.allocation_days-1) not in days):
            raise ValueError("allocation window must fit the seven-day protection horizon")
        site_ids = [site.site_id for site in self.sites]
        product_ids = [product.product_id for product in self.products]
        _partition(self.network_site_ids, site_ids,
                   [e.entity_id for e in self.excluded_sites], "site")
        _partition(self.network_product_ids, product_ids,
                   [e.entity_id for e in self.excluded_products], "product")
        if not any(site.role == "HUB" for site in self.sites):
            raise ValueError("scenario requires an included hub")
        if not any(site.role == "BENEFICIARY" for site in self.sites):
            raise ValueError("scenario requires an included beneficiary")
        for site in self.sites:
            if site.timezone != self.planning_timezone:
                raise ValueError("scenario-v1 requires a shared frozen planning timezone")
            capacity_days = [item.day for item in site.receiving_capacity]
            _unique(capacity_days, "receiving capacity day")
            if set(capacity_days) != days:
                raise ValueError("receiving capacities require seven days, including explicit zero")
            reserve_keys = [(item.product_id, item.day) for item in site.reserves]
            _unique(reserve_keys, "reserve day/product")
            if set(reserve_keys) != {(p, d) for p in product_ids for d in days}:
                raise ValueError("reserves require every product/day, including explicit zero")
        series_keys = [(item.site_id, item.product_id) for item in self.series]
        _unique(series_keys, "site/product series")
        if set(series_keys) != {(s, p) for s in site_ids for p in product_ids}:
            raise ValueError("each included site/product requires a frozen seven-day series")
        sites = {site.site_id: site for site in self.sites}
        products = {product.product_id: product for product in self.products}
        forecast_ids = [item.forecast_id for item in self.forecasts]
        _unique(forecast_ids, "frozen forecast identity")
        if set(forecast_ids) != {item.forecast_id for item in self.series}:
            raise ValueError("embed every selected forecast document exactly once")
        forecasts = {item.forecast_id: canonical_object(item.canonical_json)
                     for item in self.forecasts}
        lot_ids = []
        stock_sources = []
        commitment_ids = []
        for item in self.series:
            site = sites[item.site_id]
            if (item.organization_id, item.opening_on, item.timezone, item.transfer_mode,
                item.calendar_version_id, item.base_unit) != (
                self.organization_id, self.horizon_start, self.planning_timezone,
                self.transfer_mode, site.calendar_version_id, products[item.product_id].base_unit
            ):
                raise ValueError("series ownership, calendar, unit or mode conflicts with scenario")
            if len(item.demand) != 7:
                raise ValueError("scenario protection requires seven complete frozen demand days")
            if forecasts[item.forecast_id]["actual_provider"] != item.provider:
                raise ValueError("selected series provider conflicts with its frozen forecast")
            if site.role == "HUB" and any(point.estimate for point in item.demand):
                raise ValueError("scenario-v1 hub series has no beneficiary demand")
            lot_ids.extend(lot.lot_id for lot in item.lots)
            stock_sources.extend((lot.source_kind, lot.source_id) for lot in item.lots)
            commitment_ids.extend(c.commitment_id for c in item.commitments)
        _unique(lot_ids, "cross-series lot identity")
        _unique(stock_sources, "cross-series stock/supply source identity")
        _unique(commitment_ids, "cross-series commitment identity")
        _unique([r.route_id for r in self.routes], "route identity")
        _unique([(r.origin_id, r.destination_id) for r in self.routes], "directed route")
        for route in self.routes:
            if (route.origin_id not in sites or route.destination_id not in sites
                    or route.origin_id == route.destination_id):
                raise ValueError("route endpoints must be distinct included sites")
            if sites[route.destination_id].role != "BENEFICIARY":
                raise ValueError("route destination must be a beneficiary")
            cost_products = [cost.product_id for cost in route.unit_costs]
            _unique(cost_products, "route product cost")
            if set(cost_products) != set(product_ids):
                raise ValueError("route costs must cover each included product explicitly")
        source_keys = [(source.kind, source.key) for source in self.sources]
        _unique(source_keys, "source reference")
        if not required_source_keys(self) <= set(source_keys):
            raise ValueError("source manifest does not cover every frozen dependency")
        return self
