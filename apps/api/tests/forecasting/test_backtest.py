# covers: V1-A12
"""W3-F02: rolling-origin backtest on the user's own history (V1-SPEC §6.4, V5 §7).

Origins are the last four weekly cutoffs. Origin k (k = 1 nearest) fits on the history before
day n - 7k and scores the seven days that follow it. WAPE and bias come from one scored set:
error = prediction - actual, WAPE = Σ|error| / Σactual, bias = Σerror / Σactual, both shown
as percentages and both unavailable when Σactual is zero. A missing actual is left out of
the scored set, never scored as zero.
"""

from decimal import Decimal

import pytest

from app.schemas.v1_networks import BacktestScore
from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.backtest import (
    backtest_series,
    baseline_fit,
    location_rollups,
    scored_set,
)

D = Decimal


def weeks(*values: int) -> list[Decimal | None]:
    """One constant value per week, seven days each."""
    return [D(v) for v in values for _ in range(7)]


def test_wape_and_bias_hand_values():
    """42 days, weekly values 10, 10, 12, 8, 9, 11 (cutoff = day 41).

    Seasonal naive at each origin predicts the previous week, so with weeks w0..w5:

    | origin | scores | prediction | actual | error per day | Σerror | Σ|error| | Σactual |
    |---|---|---|---|---|---|---|---|
    | 4 | days 14–20 (w2) | 10 | 12 | −2 | −14 | 14 | 84 |
    | 3 | days 21–27 (w3) | 12 | 8 | +4 | +28 | 28 | 56 |
    | 2 | days 28–34 (w4) | 8 | 9 | −1 | −7 | 7 | 63 |
    | 1 | days 35–41 (w5) | 9 | 11 | −2 | −14 | 14 | 77 |
    | total | 28 points | | | | −7 | 63 | 280 |

    WAPE = 63 / 280 = 22.50 %; bias = −7 / 280 = −2.50 % (under-forecast)."""
    score = backtest_series(weeks(10, 10, 12, 8, 9, 11), baseline_fit())
    assert score == BacktestScore(origins_evaluated=4, wape_pct=D("22.50"), bias_pct=D("-2.50"),
                                  status="evaluated", scored_points=28)


def test_same_scored_set_for_wape_and_bias():
    """Origin 3's fit fails and one actual in origin 1 is missing: both metrics drop exactly
    those points. Remaining pairs (prediction, actual): origin 4: 7 × (10, 12);
    origin 2: 7 × (8, 9); origin 1: 6 × (9, 11). Σ|e| = 14 + 7 + 12 = 33, Σe = −33,
    Σa = 84 + 63 + 66 = 213. WAPE = 15.49 %, bias = −15.49 %, 20 points."""
    history = weeks(10, 10, 12, 8, 9, 11)
    history[38] = None  # an actual in origin 1's week

    def fit(context):
        if len(context) == 21:  # origin 3
            raise ProviderError("INSUFFICIENT_DATA", "test failure")
        return baseline_fit()(context)

    score = backtest_series(history, fit)
    assert score.scored_points == 20
    assert score.origins_evaluated == 3
    assert score.wape_pct == (100 * D(33) / D(213)).quantize(D("0.01"))
    assert score.bias_pct == (-100 * D(33) / D(213)).quantize(D("0.01"))


def test_missing_actuals_excluded_not_zero():
    history = weeks(10, 10, 10, 10, 10, 10)
    history[40] = None  # origin 1, prediction 10
    score = backtest_series(history, baseline_fit())
    # Excluded: 27 perfect points. Scored as zero it would be |10 - 0| / 270 = 3.70 %.
    assert score.scored_points == 27
    assert score.wape_pct == D("0.00")
    assert score.bias_pct == D("0.00")


def test_under_35_days_not_evaluated():
    calls = []

    def fit(context):
        calls.append(len(context))
        return [D(1)] * 7

    short = backtest_series([D(5)] * 34, fit)
    assert short == BacktestScore(origins_evaluated=0, wape_pct=None, bias_pct=None,
                                  status="not_evaluated_insufficient_history", scored_points=0)
    assert calls == []
    enough = backtest_series([D(5)] * 35, fit)
    assert enough.status == "evaluated"
    assert enough.origins_evaluated == 4


def test_origins_weekly_last_four():
    contexts = []

    def fit(context):
        contexts.append(len(context))
        return [D(0)] * 7

    score = backtest_series([D(1)] * 60, fit)
    assert sorted(contexts) == [32, 39, 46, 53]  # cutoffs n − 28, n − 21, n − 14, n − 7
    assert score.scored_points == 28
    assert score.origins_evaluated == 4


def test_no_future_leakage():
    """Each origin's fit sees only the days before it; changing later days changes nothing it
    saw."""
    history = weeks(10, 10, 12, 8, 9, 11)
    seen = []

    def fit(context):
        seen.append(list(context))
        return baseline_fit()(context)

    backtest_series(history, fit)
    for context in seen:
        assert context == history[: len(context)]
    perturbed = history[:35] + [D(999)] * 7  # only origin 1's scored week changes
    again = []
    backtest_series(perturbed, lambda c: again.append(list(c)) or baseline_fit()(c))
    assert again == seen


def test_zero_denominator_reports_none():
    score = backtest_series([D(0)] * 35, baseline_fit())
    assert score.status == "evaluated"
    assert score.scored_points == 28
    assert score.wape_pct is None
    assert score.bias_pct is None


def test_moving_average_fallback_when_a_prior_weekday_is_missing():
    """Seasonal naive needs all seven prior days; with one missing, the labeled moving average
    (14-day window, 3 samples) forecasts that origin, as in the forecast run itself."""
    history = weeks(10, 10, 10, 10, 10, 10)
    history[34] = None  # the day before origin 1
    score = backtest_series(history, baseline_fit())
    assert score.origins_evaluated == 4
    assert score.wape_pct == D("0.00")


def test_location_rollup_from_series():
    """Pooled: (Σ|e|₁ + Σ|e|₂) / (Σa₁ + Σa₂), not the mean of the two WAPEs."""
    a = scored_set(weeks(10, 10, 12, 8, 9, 11), baseline_fit())  # 63 / 280
    b = scored_set(weeks(10, 10, 10, 10, 10, 20), baseline_fit())  # 70 / 350, Σe = −70
    other = scored_set(weeks(5, 5, 5, 5, 5, 5), baseline_fit())
    rows = location_rollups([("P1", "case", a), ("P1", "case", b), ("P2", "case", other)])
    assert [(r.location_id, r.unit, r.series_count) for r in rows] == [
        ("P1", "case", 2), ("P2", "case", 1)]
    pooled = rows[0].score
    assert pooled.wape_pct == (100 * D(133) / D(630)).quantize(D("0.01"))  # 21.11, not 21.25
    assert pooled.bias_pct == (100 * D(-77) / D(630)).quantize(D("0.01"))
    assert pooled.scored_points == 56
    assert pooled.origins_evaluated == 4
    assert rows[1].score.wape_pct == D("0.00")


def test_location_rollup_never_pools_units():
    cases = scored_set(weeks(10, 10, 12, 8, 9, 11), baseline_fit())
    pounds = scored_set(weeks(100, 100, 100, 100, 100, 100), baseline_fit())
    rows = location_rollups([("P1", "lb", pounds), ("P1", "case", cases)])
    assert [(r.location_id, r.unit, r.series_count) for r in rows] == [
        ("P1", "case", 1), ("P1", "lb", 1)]
    assert rows[0].score.wape_pct == D("22.50")
    assert rows[1].score.wape_pct == D("0.00")


def test_rollup_of_only_short_series_is_not_evaluated():
    short = scored_set([D(3)] * 20, baseline_fit())
    (row,) = location_rollups([("P1", "case", short)])
    assert row.series_count == 1
    assert row.score.status == "not_evaluated_insufficient_history"
    assert row.score.wape_pct is None


@pytest.mark.parametrize("bad", [[D(-1)] * 35, [D("NaN")] * 35])
def test_invalid_history_rejected(bad):
    with pytest.raises(ValueError):
        backtest_series(bad, baseline_fit())
