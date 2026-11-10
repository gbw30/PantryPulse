"""Network forecasts through forecast.v1 (W3-F03; V1-SPEC §6.1, §6.4; spike S7).

`submit_network_forecast` freezes a compact input from one dataset version. Each series is one
demand location × product or one donation receiving location × product. It carries the last 42
days up to the as-of date, gap-explicit (None = unknown day, never zero), with its observed and
missing day counts. That is everything the methods read (S7): the per-day ForecastInput doesn't
fit 50,000 series. The forecast.v1 step runs seasonal naive, then the labeled moving average, and
the 4-origin backtest. The publisher writes one forecast_runs row whose output is the
ForecastOutput create_scenario reads, keyed by net_locations.id / net_products.id (W1-D09).
A series with under 14 observed days, or none, is listed with its reason and never forecast.
"""

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID, uuid5

import sqlalchemy as sa
from pydantic import Field

from app.repositories import networks as networks_repo
from app.repositories.forecast_history import HistoryRejected
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_envelope import MAX_FORECAST_SERIES, MIN_FORECAST_HISTORY_DAYS
from app.schemas.v1_networks import (
    BacktestResult,
    ForecastRunList,
    ForecastRunSummary,
    IneligibleSeries,
    NetworkForecastRequest,
    NetworkForecastRun,
    NetworkSeries,
    SeriesBacktest,
)
from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.adapters.moving_average import MovingAverageAdapter
from app.services.forecasting.adapters.seasonal_naive import SeasonalNaiveAdapter
from app.services.forecasting.backtest import (
    ScoredSet,
    baseline_fit,
    location_rollups,
    score,
    scored_set,
)
from app.services.forecasting.schemas import (
    Contract,
    Diagnostics,
    ForecastOutput,
    ForecastSeriesResult,
    SeriesKey,
    SeriesScope,
    StructuredError,
)
from app.services.jobs.contracts import AttemptState, canonical_json
from app.services.optimization.api_v3 import _tenant

WINDOW_DAYS = 42  # the most any method reads: the moving average at backtest origin 4 (28 + 14)
SENDERS = ("hub", "distribution_center")  # never have demand of their own
NAIVE, AVERAGE = SeasonalNaiveAdapter(), MovingAverageAdapter()
Count = Annotated[int, Field(ge=0)]


class NetworkPolicy(Contract):
    """Fixed: the network request can't choose a model, so Chronos stays off (V1-SPEC §6.4)."""

    strategy: Literal["SEASONAL_NAIVE"] = "SEASONAL_NAIVE"
    fallback: Literal["MOVING_AVERAGE"] = "MOVING_AVERAGE"
    sparse_window_days: Literal[14] = 14
    sparse_min_samples: Literal[3] = 3
    min_history_days: Literal[14] = MIN_FORECAST_HISTORY_DAYS


class FrozenSeries(Contract):
    location: Count  # index into NetworkForecastInput.locations
    product: Count  # index into NetworkForecastInput.products
    kind: Literal["demand", "donation"]
    basis: Literal["demand", "sales"] | None  # demand only; sales if any row is sales
    values: tuple[Count | None, ...] = Field(max_length=WINDOW_DAYS)  # ends at history_end
    observed: Count  # days with a known quantity in the whole history
    missing: Count  # blank or absent days from the first history day through history_end
    sales_days: Count = 0  # observed days reported as sales (the proxy share)


class NetworkForecastInput(Contract):
    schema_version: Literal["network-forecast-v1"] = "network-forecast-v1"
    organization_id: UUID
    network_id: UUID
    dataset_id: UUID  # the dataset version; create_scenario checks it (W1-D09)
    data_cutoff_date: date  # the version's as-of date
    # The version's last history day (demand or donation). By default the as-of date is the
    # day after it (V1-SPEC §6.1): the days between are not history, so never read as blank.
    history_end: date
    timezone: str
    policy: NetworkPolicy
    locations: tuple[tuple[UUID, str], ...]  # (net_locations.id, location_id)
    products: tuple[tuple[UUID, str, str], ...]  # (net_products.id, product_id, unit)
    series: tuple[FrozenSeries, ...] = Field(max_length=MAX_FORECAST_SERIES)
    input_hash: str


def _hash(inputs: NetworkForecastInput) -> str:
    payload = inputs.model_dump(mode="json", exclude={"input_hash"})
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def validate_frozen(payload: Any) -> NetworkForecastInput:
    """Revalidate a frozen input: schema, keys, and the hash over its exact content."""
    inputs = NetworkForecastInput.model_validate(payload)
    if inputs.history_end > inputs.data_cutoff_date:
        raise ValueError("HISTORY_AFTER_CUTOFF")
    keys = [(s.location, s.product, s.kind) for s in inputs.series]
    if len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_SERIES")
    for s in inputs.series:
        if s.location >= len(inputs.locations) or s.product >= len(inputs.products):
            raise ValueError("UNKNOWN_SERIES_KEY")
        if (s.kind == "donation") != (s.basis is None):
            raise ValueError("BASIS_ONLY_FOR_DEMAND")
        if sum(v is not None for v in s.values) > s.observed or s.sales_days > s.observed:
            raise ValueError("COUNTS_CONTRADICT_VALUES")
    if inputs.input_hash != _hash(inputs):
        raise ValueError("INPUT_HASH_MISMATCH")
    return inputs


# --- freeze (API process) -------------------------------------------------------------------

def _history_end(conn, version_id: UUID, as_of: date) -> date:
    """The version's last history day, blank rows included (as the import's default as-of
    date reads it); the as-of date when the version has no history."""
    return conn.scalar(sa.text(
        "SELECT greatest((SELECT max(day) FROM net_demand_history WHERE dataset_version_id = :v),"
        " (SELECT max(day) FROM net_donation_history WHERE dataset_version_id = :v))"),
        {"v": version_id}) or as_of


def _history(conn, table: str, version_id: UUID, end: date) -> list[sa.Row]:
    """One row per location × product, aggregated in PostgreSQL (≤ 4.5 M history rows)."""
    sales = ("count(quantity) FILTER (WHERE basis = 'sales')" if table == "net_demand_history"
             else "0")
    label = "bool_or(basis = 'sales')" if table == "net_demand_history" else "NULL"
    return list(conn.execute(sa.text(
        f"SELECT location_id, product_id, min(day) AS first_day, count(quantity) AS observed, "
        f"{sales} AS sales_days, {label} AS sales, "
        "array_agg(day ORDER BY day) FILTER (WHERE day > :start) AS days, "
        "array_agg(quantity ORDER BY day) FILTER (WHERE day > :start) AS quantities "
        f"FROM {table} WHERE dataset_version_id = :v GROUP BY location_id, product_id"),
        {"v": version_id, "start": end - timedelta(days=WINDOW_DAYS)}))


def _frozen_series(row, kind: str, end: date, location: int, product: int) -> dict:
    first = max(row.first_day, end - timedelta(days=WINDOW_DAYS - 1))
    values: list[int | None] = [None] * ((end - first).days + 1)
    for day, quantity in zip(row.days or (), row.quantities or (), strict=True):
        values[(day - first).days] = quantity
    return dict(location=location, product=product, kind=kind,
                basis=None if kind == "donation" else ("sales" if row.sales else "demand"),
                values=values, observed=row.observed,
                missing=(end - row.first_day).days + 1 - row.observed,
                sales_days=row.sales_days)


def freeze(conn, organization_id: UUID, network) -> NetworkForecastInput:
    version, as_of = network.dataset_version_id, network.as_of_date
    end = _history_end(conn, version, as_of)
    locations = conn.execute(sa.text(
        "SELECT id, external_id, role FROM net_locations WHERE dataset_version_id = :v "
        'ORDER BY external_id COLLATE "C"'), {"v": version}).all()
    products = conn.execute(sa.text(
        "SELECT id, external_id, unit FROM net_products WHERE dataset_version_id = :v "
        'ORDER BY external_id COLLATE "C"'), {"v": version}).all()
    li = {r.id: i for i, r in enumerate(locations)}
    pi = {r.id: i for i, r in enumerate(products)}
    series = [_frozen_series(r, kind, end, li[r.location_id], pi[r.product_id])
              for kind, table in (("demand", "net_demand_history"),
                                  ("donation", "net_donation_history"))
              for r in _history(conn, table, version, end)]
    # A receiving location with stock or deliveries but no demand rows (a new store) is listed,
    # never forecast from zeros (plan Review Focus 5).
    known = {(s["location"], s["product"]) for s in series if s["kind"] == "demand"}
    stocked = conn.execute(sa.text(
        "SELECT location_id, product_id FROM net_batches WHERE dataset_version_id = :v UNION "
        "SELECT location_id, product_id FROM net_inbound WHERE dataset_version_id = :v"),
        {"v": version}).all()
    receivers = {li[r.id] for r in locations if r.role not in SENDERS}
    series += [dict(location=loc, product=prod, kind="demand", basis="demand", values=[],
                    observed=0, missing=0)
               for loc, prod in sorted({(li[r.location_id], pi[r.product_id]) for r in stocked})
               if loc in receivers and (loc, prod) not in known]
    if len(series) > MAX_FORECAST_SERIES:
        raise HistoryRejected("FORECAST_SERIES_OVER_ENVELOPE", 422)  # never truncated
    series.sort(key=lambda s: (locations[s["location"]].external_id.encode(),
                               products[s["product"]].external_id.encode(), s["kind"]))
    inputs = NetworkForecastInput(
        organization_id=organization_id, network_id=network.id, dataset_id=version,
        data_cutoff_date=as_of, history_end=end, timezone=network.timezone, policy=NetworkPolicy(),
        locations=tuple((r.id, r.external_id) for r in locations),
        products=tuple((r.id, r.external_id, r.unit) for r in products),
        series=tuple(FrozenSeries(**s) for s in series), input_hash="")
    return inputs.model_copy(update={"input_hash": _hash(inputs)})


# --- the forecast.v1 step (child process; no database) --------------------------------------

def _unavailable(code: str, message: str) -> dict:
    return {"status": "INSUFFICIENT_DATA", "error_code": code, "error_message": message}


def _forecast(s: FrozenSeries, policy: NetworkPolicy, cutoff: date, gap: int) -> dict:
    """`gap` = cutoff − history_end in days; the horizon starts the day after the cutoff."""
    if s.observed == 0:
        return _unavailable("NO_HISTORY", "Every history day is blank (unknown), so there is "
                            "nothing to forecast from; blank days are never read as zero"
                            if s.missing else "No demand history rows for this location and "
                            "product")
    if s.observed < policy.min_history_days:
        return _unavailable("INSUFFICIENT_HISTORY", f"Needs {policy.min_history_days}+ days of "
                            f"history to forecast; has {s.observed}")
    values = [None if v is None else float(v) for v in s.values]
    week, shift = values[-7:], gap % 7  # rotated so each horizon day reads its own weekday
    fallback = None
    try:
        points = NAIVE.predict_values(week[shift:] + week[:shift], cutoff=cutoff)
        provider = policy.strategy
    except ProviderError as primary:
        fallback = primary.code
        try:
            points = AVERAGE.predict_values(values, cutoff=cutoff,
                                            window_days=policy.sparse_window_days,
                                            min_samples=policy.sparse_min_samples)
            provider = policy.fallback
        except ProviderError as error:
            return _unavailable(error.code, error.safe_message)
    return {"status": "AVAILABLE", "provider": provider, "fallback_reason": fallback,
            "central": [p.central_estimate for p in points]}


def _sums(scored: ScoredSet) -> dict:
    return {"evaluated": scored.evaluated, "points": scored.points,
            "abs_error": str(scored.abs_error), "error": str(scored.error),
            "actual": str(scored.actual), "origins": sorted(scored.origins)}


def compute(inputs: NetworkForecastInput) -> dict:
    """Compact output, in the input's series order: the forecasts and the demand backtests."""
    policy, generated_at = inputs.policy, datetime.now(UTC)
    fit = baseline_fit(policy.sparse_window_days, policy.sparse_min_samples)
    gap = (inputs.data_cutoff_date - inputs.history_end).days
    series = [_forecast(s, policy, inputs.data_cutoff_date, gap) for s in inputs.series]
    backtest = [_sums(scored_set(s.values, fit))
                if s.kind == "demand" and row["status"] == "AVAILABLE" else None
                for s, row in zip(inputs.series, series, strict=True)]
    return {"generated_at": generated_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "series": series, "backtest": backtest}


# --- the publisher (supervisor) -------------------------------------------------------------

def build_output(inputs: NetworkForecastInput, compact: dict, run_id: UUID) -> ForecastOutput:
    """The stored ForecastOutput, validated row by row; raises ValueError on any contradiction."""
    from app.services.forecasting.schemas import ForecastPoint, ProviderIdentity

    policy, cutoff = inputs.policy, inputs.data_cutoff_date
    generated_at = datetime.fromisoformat(compact["generated_at"])
    rows = []
    for s, r in zip(inputs.series, compact["series"], strict=True):
        available = r["status"] == "AVAILABLE"
        if available and (s.observed < policy.min_history_days or (
                r["provider"] == policy.fallback) != (r["fallback_reason"] is not None)
                or r["provider"] not in (policy.strategy, policy.fallback)):
            raise ValueError("Provider provenance contradicts the frozen policy")
        location, (product, _, unit) = inputs.locations[s.location][0], inputs.products[s.product]
        donation = s.kind == "donation"
        common = dict(
            result_id=uuid5(run_id, f"{s.location}:{s.product}:{s.kind}"),
            scope=SeriesScope(key=SeriesKey(
                organization_id=inputs.organization_id, site_id=location, product_id=product,
                target_type="DONATION" if donation else "DEMAND"),
                unit=unit, timezone=inputs.timezone, required=available),
            target_basis="RECEIVED" if donation else (
                "FULFILLED_PROXY" if s.basis == "sales" else "REQUESTED"),
            diagnostics=Diagnostics(
                observed_count=s.observed, missing_count=s.missing,
                proxy_fraction=s.sales_days / s.observed if s.observed else 0.0,
                reference_weekday_count=sum(v is not None for v in s.values[-7:]),
                trailing_sample_count=sum(
                    v is not None for v in s.values[-policy.sparse_window_days:])),
            input_hash=inputs.input_hash, generated_at=generated_at)
        if not available:
            rows.append(ForecastSeriesResult(**common, status=r["status"], errors=(
                StructuredError(code=r["error_code"], message=r["error_message"],
                                category="DATA"),)))
            continue
        kind = "MEAN" if r["provider"] == policy.fallback else "POINT"
        rows.append(ForecastSeriesResult(
            **common, status="AVAILABLE", actual_provider=ProviderIdentity(name=r["provider"]),
            fallback_used=r["fallback_reason"] is not None, fallback_reason=r["fallback_reason"],
            warnings=("SPARSE_HISTORY",) if kind == "MEAN" else (),
            points=tuple(ForecastPoint(day=cutoff + timedelta(days=i + 1), central_estimate=c,
                                       estimate_kind=kind)
                         for i, c in enumerate(r["central"]))))
    return ForecastOutput(
        run_id=run_id, input_hash=inputs.input_hash, data_cutoff_date=cutoff,
        generated_at=generated_at, completed_at=datetime.fromisoformat(compact["completed_at"]),
        ready_for_publication=any(r.status == "AVAILABLE" for r in rows),
        partial_scope=any(r.status != "AVAILABLE" for r in rows),
        actual_providers=tuple(sorted({r.actual_provider.name for r in rows
                                       if r.actual_provider is not None})),
        warnings=tuple(sorted({w for r in rows for w in r.warnings})), series=tuple(rows))


def build_backtest(inputs: NetworkForecastInput, compact: dict, run_id: UUID) -> dict:
    """The stored `forecast_runs.backtest` (CR-w3-forecast-1 B): the BacktestResult body by CSV
    ids, without its two ids. One row per forecast demand series, the per-location roll-ups by
    unit (never pooled across units), and the demand series that were never forecast."""
    series, pooled, ineligible = [], [], []
    for s, row, sums in zip(inputs.series, compact["series"], compact["backtest"], strict=True):
        if s.kind != "demand":
            continue
        location, (_, product, unit) = inputs.locations[s.location][1], inputs.products[s.product]
        if row["status"] != "AVAILABLE":
            ineligible.append(IneligibleSeries(location_id=location, product_id=product,
                                               reason=row["error_message"]))
            continue
        scored = ScoredSet(sums["evaluated"], sums["points"], Decimal(sums["abs_error"]),
                           Decimal(sums["error"]), Decimal(sums["actual"]),
                           frozenset(sums["origins"]))
        series.append(SeriesBacktest(location_id=location, product_id=product, basis=s.basis,
                                     score=score(scored)))
        pooled.append((location, unit, scored))

    def by_ids(r):
        return r.location_id.encode(), r.product_id.encode()

    return BacktestResult(
        forecast_job_id=run_id, network_id=inputs.network_id,
        series=tuple(sorted(series, key=by_ids)), locations=location_rollups(pooled),
        ineligible=tuple(sorted(ineligible, key=by_ids)),
    ).model_dump(mode="json", exclude={"forecast_job_id", "network_id"})


# --- router-facing services -----------------------------------------------------------------

def submit_network_forecast(
    rt, scope, network_id: UUID, request: NetworkForecastRequest, idempotency_key: str
) -> ForecastAccepted:
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        tenant = _tenant(conn, scope, network_id)
        (network,) = networks_repo.networks(conn, network_id)
        if request.dataset_version_id != network.dataset_version_id:
            known = conn.scalar(sa.text(
                "SELECT 1 FROM dataset_versions WHERE id = :v AND network_id = :n"),
                {"v": request.dataset_version_id, "n": network_id})
            raise (HistoryRejected("STALE_DATASET_VERSION", 409) if known
                   else HistoryRejected("DATASET_VERSION_NOT_FOUND", 404))
        inputs = freeze(conn, tenant.organization_id, network)
    accepted = rt.queue.submit(tenant, "forecast.v1",
                               {"network_forecast": inputs.model_dump(mode="json")},
                               idempotency_key, deduplicate=True)
    return ForecastAccepted(
        job_id=accepted.job_id, attempt_id=accepted.attempt_id, state=accepted.state,
        replayed=accepted.replayed, status_url=f"/api/v1/jobs/{accepted.job_id}",
        result_url=f"/api/v1/networks/{network_id}/forecasts/{accepted.job_id}")


def list_forecast_runs(rt, scope, network_id: UUID) -> ForecastRunList:
    """The network's forecast.v1 jobs, newest first (CR-w1-web-2)."""
    with rt.engine.connect() as conn:
        tenant = _tenant(conn, scope, network_id)
        rows = conn.execute(sa.text(
            "SELECT j.job_id, j.state, j.created_at, r.id AS run_id, "
            "j.input_package -> 'input' -> 'network_forecast' ->> 'dataset_id' AS dataset_id "
            "FROM compute_jobs j LEFT JOIN forecast_runs r ON r.job_id = j.job_id "
            "AND r.organization_id = j.organization_id "
            "WHERE j.organization_id = :org AND j.handler_contract = 'forecast.v1' "
            "AND j.input_package -> 'input' -> 'network_forecast' ->> 'network_id' = :net "
            "ORDER BY j.created_at DESC, j.job_id"),
            {"org": tenant.organization_id, "net": str(network_id)}).all()
    return ForecastRunList(network_id=network_id, runs=tuple(ForecastRunSummary(
        job_id=r.job_id, forecast_run_id=r.run_id, dataset_version_id=UUID(r.dataset_id),
        state=AttemptState(r.state), recorded_at=r.created_at) for r in rows))


def read_run(rt, scope, network_id: UUID, forecast_run_id: UUID):
    """(frozen input, output, row) of a published network run; 404 for any other run."""
    with rt.engine.connect() as conn:
        tenant = _tenant(conn, scope, network_id)
        row = conn.execute(sa.text(
            "SELECT id, job_id, planning_ready, frozen_input, output FROM forecast_runs "
            "WHERE id = :r AND organization_id = :org "
            "AND frozen_input ->> 'network_id' = :net"),
            {"r": forecast_run_id, "org": tenant.organization_id,
             "net": str(network_id)}).one_or_none()
    if row is None:
        raise HistoryRejected("FORECAST_RUN_NOT_FOUND", 404)
    return validate_frozen(row.frozen_input), ForecastOutput.model_validate(row.output), row


def get_forecast_run(rt, scope, network_id: UUID, forecast_run_id: UUID) -> NetworkForecastRun:
    """A published network run's series by CSV ids (CR-w1-web-4)."""
    inputs, output, row = read_run(rt, scope, network_id, forecast_run_id)
    locations = dict(inputs.locations)
    products = {net: (external, unit) for net, external, unit in inputs.products}
    series = []
    for s in output.series:
        product, unit = products[s.scope.key.product_id]
        donation = s.scope.key.target_type == "DONATION"
        series.append(NetworkSeries(
            location_id=locations[s.scope.key.site_id], product_id=product,
            kind="donation" if donation else "demand",
            basis=None if donation else (
                "sales" if s.target_basis == "FULFILLED_PROXY" else "demand"),
            unit=unit, status=s.status,
            reason=s.errors[0].message if s.status != "AVAILABLE" else None,
            actual_provider=s.actual_provider, fallback_used=s.fallback_used,
            fallback_reason=s.fallback_reason, observed_count=s.diagnostics.observed_count,
            missing_count=s.diagnostics.missing_count, points=s.points))
    series.sort(key=lambda x: (x.location_id.encode(), x.product_id.encode(), x.kind))
    return NetworkForecastRun(
        network_id=network_id, forecast_run_id=row.id, job_id=row.job_id,
        dataset_version_id=inputs.dataset_id, data_cutoff_date=output.data_cutoff_date,
        planning_ready=row.planning_ready, generated_at=output.generated_at,
        series=tuple(series))
