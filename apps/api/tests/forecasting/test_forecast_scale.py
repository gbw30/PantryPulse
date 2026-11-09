# covers: V1-A17
"""W3-F06: splitting a network forecast's series never changes its output.

S7 found that one compact step fits 50,000 series, so the step does not batch. This pins the
property any batching relies on: each series' forecast and backtest depend only on that series,
not on its neighbours or its position. The 50,000-series timing is the committed benchmark
docs/forecasting/evidence/v1-forecast-scale.json (scripts/bench_forecast.py --part built).
"""

from datetime import date
from uuid import UUID, uuid5

from app.repositories.jobs import _json
from app.schemas.v1_envelope import MAX_FORECAST_SERIES, MAX_LOCATIONS, MAX_PRODUCTS
from app.services.forecasting.network import (
    WINDOW_DAYS,
    FrozenSeries,
    NetworkForecastInput,
    NetworkPolicy,
    _hash,
    compute,
)
from app.services.imports.validate import MAX_QUANTITY
from app.workers.forecasting import REGISTRATION

NET = UUID(int=9)
WEEK = (10, 12, 8, 9, 11, 14, 6)
SERIES = (
    # 42 weekly days: seasonal naive, backtest evaluated
    FrozenSeries(location=0, product=0, kind="demand", basis="demand",
                 values=tuple(WEEK[i % 7] for i in range(42)), observed=60, missing=0),
    # a blank 2 days ago: the labeled moving average
    FrozenSeries(location=0, product=1, kind="demand", basis="sales",
                 values=(*(4,) * 40, None, 4), observed=41, missing=1, sales_days=41),
    # 10 days: under the 14-day minimum, listed, never forecast
    FrozenSeries(location=1, product=0, kind="demand", basis="demand", values=(5,) * 10,
                 observed=10, missing=0),
    # every day blank: no history
    FrozenSeries(location=1, product=1, kind="demand", basis="demand", values=(None,) * 20,
                 observed=0, missing=20),
    # a donation series: forecast, never backtested
    FrozenSeries(location=1, product=0, kind="donation", basis=None, values=(3,) * 21,
                 observed=21, missing=0),
    # 20 days: forecast, backtest not evaluated (under 35 days)
    FrozenSeries(location=2, product=2, kind="demand", basis="demand",
                 values=tuple(7 + i % 3 for i in range(20)), observed=20, missing=0),
)


def network_input(series) -> NetworkForecastInput:
    inputs = NetworkForecastInput(
        organization_id=UUID(int=1), network_id=NET, dataset_id=UUID(int=2),
        data_cutoff_date=date(2026, 11, 4), timezone="America/New_York", policy=NetworkPolicy(),
        locations=tuple((uuid5(NET, f"L{i}"), f"L{i}") for i in range(3)),
        products=tuple((uuid5(NET, f"P{i}"), f"P{i}", "case") for i in range(3)),
        series=tuple(series), input_hash="")
    return inputs.model_copy(update={"input_hash": _hash(inputs)})


def merged(parts: list[dict]) -> dict:
    """The parts' rows in order; the run's own clock (generated_at, completed_at) is dropped."""
    return {key: [row for part in parts for row in part[key]] for key in ("series", "backtest")}


def test_batched_series_equal_unbatched_on_small_set():
    unbatched = merged([compute(network_input(SERIES))])
    statuses = {(r["status"], r.get("provider")) for r in unbatched["series"]}
    assert statuses == {("AVAILABLE", "SEASONAL_NAIVE"), ("AVAILABLE", "MOVING_AVERAGE"),
                        ("INSUFFICIENT_DATA", None)}  # every path is in the set
    assert [b is None for b in unbatched["backtest"]] == [False, False, True, True, True, False]
    for size in (1, 2, 4):
        batched = [compute(network_input(SERIES[i:i + size]))
                   for i in range(0, len(SERIES), size)]
        assert merged(batched) == unbatched, size
    backwards = merged([compute(network_input(SERIES[::-1]))])
    assert {k: v[::-1] for k, v in backwards.items()} == unbatched


def test_worst_case_frozen_input_fits_the_registered_bound():
    """At the envelope (50,000 series, 100 locations, 500 products, 64-character IDs) with every
    day at the 100,000-unit maximum, the package the queue encodes still fits max_input_bytes.
    S7 measured small synthetic quantities; 4-digit daily quantities passed the old 16 MB."""
    def ids(prefix: str, n: int) -> list[str]:
        return [f"{prefix}{i:04d}".ljust(64, "x") for i in range(n)]

    locations = tuple((uuid5(NET, x), x) for x in ids("L", MAX_LOCATIONS))
    products = tuple((uuid5(NET, x), x, "case") for x in ids("P", MAX_PRODUCTS))
    worst = FrozenSeries(location=MAX_LOCATIONS - 1, product=MAX_PRODUCTS - 1, kind="demand",
                         basis="demand", values=(MAX_QUANTITY,) * WINDOW_DAYS, observed=45,
                         missing=45, sales_days=45)  # 2 digits each, 90 days
    series = tuple(worst.model_copy(update={"location": i % MAX_LOCATIONS,
                                            "product": i // MAX_LOCATIONS})
                   for i in range(MAX_FORECAST_SERIES))
    inputs = network_input(()).model_copy(update={"locations": locations, "products": products,
                                                  "series": series})
    package = {"contract": REGISTRATION.contract,
               "input_schema_version": REGISTRATION.input_schema_version,
               "input": {"network_forecast": inputs.model_dump(mode="json")}}
    assert len(_json(package).encode()) <= REGISTRATION.max_input_bytes
