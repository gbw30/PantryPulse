"""Rolling-origin backtest (W3-F02) and its read (W3-F03).

V1-SPEC §6.4 with the V5 §7 formulas. Origin k (k = 1 nearest) is the weekly cutoff n - 7k:
its fit sees only the days before it and it scores the seven days after. Error = prediction -
actual. WAPE = Σ|error| / Σactual and bias = Σerror / Σactual (positive = over-forecast), as
percentages, both read from one scored set. When Σactual is zero both are undefined, so the score
is not evaluated, with the reason sum_actual_zero (W5-D03). A missing
actual is left out of the set, never scored as zero. Under 35 days: not evaluated.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa

from app.repositories.forecast_history import HistoryRejected
from app.repositories.networks import network_organization
from app.schemas.v1_envelope import MIN_BACKTEST_HISTORY_DAYS
from app.schemas.v1_networks import BacktestResult, BacktestScore, LocationBacktest
from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.adapters.moving_average import MovingAverageAdapter
from app.services.forecasting.adapters.seasonal_naive import SeasonalNaiveAdapter

Fit = Callable[[Sequence[Decimal | None]], Sequence[Decimal]]
SPARSE_WINDOW_DAYS = 14  # the network forecast's moving-average fallback policy
SPARSE_MIN_SAMPLES = 3
CENT = Decimal("0.01")
_ANCHOR = date(2000, 1, 1)  # the adapters date their points; the backtest uses only values
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ScoredSet:
    """Sums over one set of (prediction, actual) pairs. WAPE and bias both read these sums, so
    they always describe the same points; adding two sets pools them."""

    evaluated: bool
    points: int = 0
    abs_error: Decimal = ZERO
    error: Decimal = ZERO
    actual: Decimal = ZERO
    origins: frozenset[int] = frozenset()

    def __add__(self, other: "ScoredSet") -> "ScoredSet":
        return ScoredSet(
            self.evaluated or other.evaluated,
            self.points + other.points,
            self.abs_error + other.abs_error,
            self.error + other.error,
            self.actual + other.actual,
            self.origins | other.origins,
        )


def baseline_fit(window_days: int = SPARSE_WINDOW_DAYS,
                 min_samples: int = SPARSE_MIN_SAMPLES) -> Fit:
    """Seasonal naive, then the labeled moving average: the network forecast's own chain."""
    naive, average = SeasonalNaiveAdapter(), MovingAverageAdapter()

    def fit(context: Sequence[Decimal | None]) -> list[Decimal]:
        values = [None if v is None else float(v) for v in context]
        try:
            points = naive.predict_values(values[-7:], cutoff=_ANCHOR)
        except ProviderError:
            points = average.predict_values(values, cutoff=_ANCHOR, window_days=window_days,
                                            min_samples=min_samples)
        return [Decimal(str(p.central_estimate)) for p in points]

    return fit


def scored_set(history: Sequence[Decimal | None], fit: Fit, origins: int = 4,
               horizon: int = 7) -> ScoredSet:
    """`history` is the gap-explicit daily calendar ending at the cutoff (None = unknown day)."""
    values = [None if v is None else Decimal(v) for v in history]
    if any(v is not None and (not v.is_finite() or v < 0) for v in values):
        raise ValueError("History must be finite and nonnegative")
    n = len(values)
    if n < MIN_BACKTEST_HISTORY_DAYS or n <= origins * horizon:
        return ScoredSet(evaluated=False)
    total = ScoredSet(evaluated=True)
    for k in range(origins, 0, -1):
        origin = n - horizon * k
        try:
            predictions = list(fit(values[:origin]))
        except ProviderError:
            continue  # no forecast at this origin: none of its days enter the scored set
        if len(predictions) != horizon:
            raise ValueError("A fit must return one prediction per horizon day")
        pairs = [(p, a) for p, a in zip(predictions, values[origin:origin + horizon], strict=True)
                 if a is not None]
        if pairs:
            errors = [p - a for p, a in pairs]
            total += ScoredSet(True, len(pairs), sum(map(abs, errors), ZERO), sum(errors, ZERO),
                               sum((a for _, a in pairs), ZERO), frozenset({k}))
    return total


def score(scored: ScoredSet) -> BacktestScore:
    if not scored.evaluated or not scored.points:  # 35+ days but nothing could be scored
        return BacktestScore(origins_evaluated=0, wape_pct=None, bias_pct=None,
                             status="not_evaluated_insufficient_history", scored_points=0)

    if scored.actual == 0:  # WAPE and bias divide by Σactual: undefined, so not evaluated
        return BacktestScore(origins_evaluated=len(scored.origins), wape_pct=None, bias_pct=None,
                             status="not_evaluated_zero_actual", reason="sum_actual_zero",
                             scored_points=scored.points)

    def pct(value: Decimal) -> Decimal:
        return (100 * value / scored.actual).quantize(CENT)

    return BacktestScore(origins_evaluated=len(scored.origins), wape_pct=pct(scored.abs_error),
                         bias_pct=pct(scored.error), status="evaluated",
                         scored_points=scored.points)


def backtest_series(
    history: Sequence[Decimal | None], fit: Callable, origins: int = 4, horizon: int = 7
) -> BacktestScore:
    return score(scored_set(history, fit, origins, horizon))


def location_rollups(rows: Iterable[tuple[str, str, ScoredSet]]) -> tuple[LocationBacktest, ...]:
    """One row per (location, unit) on the pooled scored set; units are never pooled
    (W2-06 §2, CR-w1-web-4 b)."""
    pooled: dict[tuple[str, str], tuple[int, ScoredSet]] = {}
    for location_id, unit, scored in rows:
        count, total = pooled.get((location_id, unit), (0, ScoredSet(evaluated=False)))
        pooled[(location_id, unit)] = (count + 1, total + scored)
    return tuple(
        LocationBacktest(location_id=location, unit=unit, series_count=count, score=score(total))
        for (location, unit), (count, total) in sorted(pooled.items())
    )


def get_backtest(rt, scope, job_id: UUID) -> BacktestResult:
    """A network forecast run's stored backtest (CR-w3-forecast-1 B); 404 for any other job.
    The run's network decides the organization, as for every network route."""
    with rt.engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT organization_id, frozen_input ->> 'network_id' AS network_id, backtest "
            "FROM forecast_runs WHERE id = :j AND backtest IS NOT NULL"), {"j": job_id}
        ).one_or_none()
        if row is None or network_organization(conn, UUID(row.network_id)) \
                != row.organization_id:
            raise HistoryRejected("FORECAST_RUN_NOT_FOUND", 404)
    return BacktestResult(forecast_job_id=job_id, network_id=row.network_id, **row.backtest)
