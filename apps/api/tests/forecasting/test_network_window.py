# covers: V1-A08
"""The as-of date may come after the version's last history day: V1-SPEC §6.1 defaults it to
the day after, and it is editable. Each window ends on that last history day, so the gap is
never read as blank history, and seasonal naive still repeats each horizon day's prior
comparable weekday."""

from datetime import timedelta

import pytest

from app.services.forecasting.network import FrozenSeries, compute, validate_frozen
from tests.forecasting.test_forecast_scale import CUTOFF, network_input


@pytest.mark.parametrize("gap", [0, 1, 3, 9])
def test_seasonal_naive_repeats_the_prior_comparable_weekday_across_the_as_of_gap(gap):
    end = CUTOFF - timedelta(days=gap)
    history = {end - timedelta(days=41 - i): i + 1 for i in range(42)}  # every value distinct
    series = FrozenSeries(location=0, product=0, kind="demand", basis="demand",
                          values=tuple(history.values()), observed=42, missing=0)
    (row,) = compute(network_input([series], history_end=end))["series"]
    horizon = [CUTOFF + timedelta(days=i) for i in range(1, 8)]
    assert (row["provider"], row["fallback_reason"]) == ("SEASONAL_NAIVE", None)
    assert row["central"] == [history[max(d for d in history if (day - d).days % 7 == 0)]
                              for day in horizon]


def test_history_end_after_the_cutoff_is_refused():
    late = network_input([], history_end=CUTOFF + timedelta(days=1))
    with pytest.raises(ValueError, match="HISTORY_AFTER_CUTOFF"):
        validate_frozen(late.model_dump(mode="json"))
