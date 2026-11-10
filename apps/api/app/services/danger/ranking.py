"""Danger ranking per location, driven by one product (W3-F05, V1-SPEC §6.6).

Danger and the site inspector replay the forecast run's own dataset version through
`optimization/projection.py::project_v3` with no transfers: the solver's FEFO kernel, with
confirmed inbound counted once on its arrival date (W2-06 §3). The demand targets are the
solver's (`networks/scenario.py::_demand`). Donation forecasts are shown, never supply.

Score per location, each share inside one product and its own unit:
- unmet share = 7-day unmet / 7-day target, for a product whose target is known and above 0;
- Retail only, expiry share = units expiring unsold in the horizon / stock (eligible on hand
  now + confirmed inbound), for a product with dated stock and no unknown target.
The worst product drives the location. Ties, between a product's two shares, between products
or between locations, go to the earliest first day of that loss, then unmet before expiry,
then the ID. A location with no share (no known target, no dated stock) gets no row:
unknown is not zero.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import sqlalchemy as sa

from app.repositories.forecast_history import HistoryRejected
from app.schemas.or_inputs import decimal_literal
from app.schemas.v1_networks import DangerRanking, DangerRow, LocationProjection, ProductProjection
from app.schemas.v1_planning import NetworkMode
from app.services.demand_targets import round_daily_targets
from app.services.forecasting.network import read_run
from app.services.networks.scenario import _batches, _demand, _inbound
from app.services.optimization.projection import project_v3

HIGH = Decimal("0.50")  # half or more of the driving product's week projected lost
MEDIUM = Decimal("0.20")
STEP = Decimal("0.0001")  # the score as shown; ranking uses the shown value
UNKNOWN = (None,) * 7


def band(score: Decimal) -> str:
    return "high" if score >= HIGH else "medium" if score >= MEDIUM else "low"


@dataclass(frozen=True, slots=True)
class Line:
    """One product at one location; inbound_units is already inside the projection."""

    location_id: str
    product: ProductProjection
    inbound_units: int  # confirmed arrivals in the horizon: the expiry share's stock


def _share(lost, base: int, dates) -> tuple[Decimal, int, date | None] | None:
    if lost is None or None in lost or base <= 0:
        return None
    first = next((d for d, x in zip(dates, lost, strict=True) if x), None)
    return (Decimal(sum(lost)) / base).quantize(STEP), sum(lost), first


def _losses(line: Line, mode: NetworkMode):
    p = line.product
    if None not in p.target and (unmet := _share(p.unmet, sum(p.target), p.dates)):
        yield *unmet, "unmet"
    if mode == "RETAIL" and (expiry := _share(
            p.expiring_unsold, p.eligible_stock_now + line.inbound_units, p.dates)):
        yield *expiry, "expiry"


def danger_ranking(projection: Iterable[Line], mode: NetworkMode) -> list[DangerRow]:
    worst: dict[str, tuple] = {}
    for line in projection:
        p = line.product
        for score, units, first, reason in _losses(line, mode):
            key = (-score, first or date.max, reason != "unmet", p.product_id.encode())
            if line.location_id not in worst or key < worst[line.location_id][0]:
                worst[line.location_id] = key, (score, reason, p.product_id, units, p.unit, first)
    # score, first day, unmet before expiry, then the location (not the product)
    ordered = sorted(worst.items(), key=lambda item: (*item[1][0][:3], item[0].encode()))
    return [DangerRow(location_id=location, rank=rank, score_ratio=score, band=band(score),
                      reason=reason, driving_product_id=product, driving_units=units, unit=unit,
                      first_deficit_date=first)
            for rank, (location, (_, (score, reason, product, units, unit, first)))
            in enumerate(ordered, 1)]


def _daily(series) -> tuple[int | None, ...]:
    """A donation series in whole units per day, rounded as demand targets are."""
    if series.status != "AVAILABLE":
        return UNKNOWN
    rounded = round_daily_targets([(p.day, Decimal(decimal_literal(str(p.central_estimate))))
                                   for p in series.points])
    return tuple(p.target for p in rounded.points)


def _lines(rt, scope, network_id: UUID, forecast_run_id: UUID, location_id: str | None = None):
    inputs, output, _ = read_run(rt, scope, network_id, forecast_run_id)  # tenancy + 404
    if location_id is not None and location_id not in dict(inputs.locations).values():
        raise HistoryRejected("LOCATION_NOT_FOUND", 404)
    version, as_of = inputs.dataset_id, inputs.data_cutoff_date
    units = {external: unit for _, external, unit in inputs.products}
    with rt.engine.connect() as conn:  # a published dataset version never changes
        mode = conn.scalar(sa.text("SELECT mode FROM networks WHERE id = :n"),
                           {"n": network_id}).upper()
        batches = _batches(conn, version, as_of, units, [])
        inbound, _ = _inbound(conn, version, [])
    return mode, project_lines(inputs, output, batches, inbound, location_id)


def project_lines(inputs, output, batches, inbound, location_id: str | None = None) -> list[Line]:
    """A run's forecasts and its version's frozen lots → one Line per location × product."""
    locations = dict(inputs.locations)
    products = {net: external for net, external, _ in inputs.products}
    units = {external: unit for _, external, unit in inputs.products}
    demand = _demand(output, locations, products, [])
    unknown, donations = set(), {}
    for s in output.series:
        key = locations[s.scope.key.site_id], products[s.scope.key.product_id]
        if s.scope.key.target_type == "DONATION":
            donations[key] = _daily(s)
        elif s.status != "AVAILABLE":
            unknown.add(key)

    def keep(key) -> bool:
        return location_id is None or key[0] == location_id

    first = inputs.data_cutoff_date + timedelta(days=1)
    # The parts of an or-input-v3 scenario that project_v3 reads.
    scenario = SimpleNamespace(
        first_planning_date=first,
        demand=[d for d in demand if keep((d.location_id, d.product_id))],
        batches=[b for b in batches if keep((b.location_id, b.product_id))],
        inbound=[i for i in inbound if keep((i.location_id, i.product_id))])
    days = defaultdict(list)
    for day in project_v3(scenario).days:
        days[day.location_id, day.product_id].append(day)
    targets = {(d.location_id, d.product_id): d.targets for d in scenario.demand}
    stock, arriving = defaultdict(int), defaultdict(int)
    for b in scenario.batches:
        stock[b.location_id, b.product_id] += b.quantity
    for i in scenario.inbound:
        arriving[i.location_id, i.product_id] += i.quantity
    dated = {(lot.location_id, lot.product_id) for lot in (*scenario.batches, *scenario.inbound)
             if not lot.non_expiring}
    keys = {*targets, *unknown, *donations, *stock, *arriving}
    dates = tuple(first + timedelta(days=i) for i in range(7))
    lines = []
    for key in sorted(filter(keep, keys), key=lambda k: (k[0].encode(), k[1].encode())):
        rows = days.get(key, ())
        known = key in targets
        lines.append(Line(key[0], ProductProjection(
            product_id=key[1], unit=units[key[1]], dates=dates,
            target=targets[key] if known else UNKNOWN,
            served=tuple(r.served for r in rows) if known else UNKNOWN,
            unmet=tuple(r.unmet for r in rows) if known else UNKNOWN,
            eligible_stock_now=stock[key],
            expiring_unsold=None if key not in dated else UNKNOWN if key in unknown
            else tuple(r.expired for r in rows),
            donation_forecast=donations.get(key)), arriving[key]))
    return lines


def get_danger(rt, scope, network_id: UUID, forecast_run_id: UUID) -> DangerRanking:
    mode, lines = _lines(rt, scope, network_id, forecast_run_id)
    return DangerRanking(network_id=network_id, forecast_run_id=forecast_run_id, mode=mode,
                         rows=tuple(danger_ranking(lines, mode)))


def get_projection(
    rt, scope, network_id: UUID, forecast_run_id: UUID, location_id: str
) -> LocationProjection:
    """Per-product projection at one location for the site inspector (CR-w1-web-3)."""
    mode, lines = _lines(rt, scope, network_id, forecast_run_id, location_id)
    return LocationProjection(network_id=network_id, forecast_run_id=forecast_run_id,
                              location_id=location_id, mode=mode,
                              products=tuple(line.product for line in lines))
