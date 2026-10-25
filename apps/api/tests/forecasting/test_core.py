from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.services.forecasting.preparation import canonical_hash, prepare
from app.services.forecasting.schemas import ForecastInput
from app.services.forecasting.service import forecast, reusable_result

from .conftest import AS_OF, CUTOFF, demand, ref


def frozen(history, policy, **changes):
    return prepare(
        history,
        data_cutoff_date=CUTOFF,
        snapshot_as_of=AS_OF,
        policy=policy.model_copy(update=changes),
    )


def test_weekly_uses_dates_and_baseline_has_no_fake_quantiles(history, policy):
    inputs = frozen(history(), policy)
    output = forecast(inputs)
    assert output.ready_for_publication
    result = output.series[0]
    assert [p.day for p in result.points] == [CUTOFF + timedelta(days=i) for i in range(1, 8)]
    assert [p.central_estimate for p in result.points] == [16, 15, 14, 13, 12, 11, 10]
    assert result.actual_provider.name == "SEASONAL_NAIVE"
    assert all(p.p50 is None and p.interval_method == "NONE" for p in result.points)


def test_sparse_uses_trailing_calendar_and_reports_mean(history, policy):
    rows = [demand(CUTOFF - timedelta(days=i), i, i, 0) for i in (0, 2, 8, 20)]
    inputs = frozen(history(rows), policy, allow_fallback=True)
    output = forecast(inputs)
    result = output.series[0]
    assert [p.central_estimate for p in result.points] == pytest.approx([10 / 3] * 7)
    assert result.points[0].estimate_kind == "MEAN"
    assert result.fallback_used
    assert result.diagnostics.observed_count == 4
    assert "SPARSE_HISTORY" in result.warnings
    assert inputs.series[0].observations[-2].is_missing


def test_all_zero_is_available_but_missing_is_not(history, policy):
    rows = [demand(CUTOFF - timedelta(days=i), 0, 0, 0) for i in range(7)]
    assert forecast(frozen(history(rows), policy)).ready_for_publication
    output = forecast(frozen(history([]), policy, allow_fallback=True))
    assert not output.ready_for_publication
    assert output.series[0].status == "INSUFFICIENT_DATA"
    assert output.series[0].points == ()


def test_proxy_requires_opt_in_and_original_components_survive(history, policy):
    rows = [demand(CUTOFF - timedelta(days=i), None, 8, None) for i in range(7)]
    blocked = forecast(frozen(history(rows), policy))
    assert not blocked.ready_for_publication
    inputs = frozen(history(rows), policy, allow_fulfilled_proxy=True)
    result = forecast(inputs).series[0]
    assert result.diagnostics.proxy_fraction == 1
    assert result.target_basis == "FULFILLED_PROXY"
    assert "FULFILLED_PROXY" in result.warnings
    assert inputs.series[0].observations[0].requested_units is None


def test_hash_is_order_independent_but_policy_and_revision_sensitive(history, policy):
    bundle = history()
    first = frozen(bundle, policy)
    reordered = frozen(bundle.model_copy(update={"demand": tuple(reversed(bundle.demand))}), policy)
    assert first.input_hash == reordered.input_hash
    assert first.input_hash != frozen(bundle, policy, allow_fallback=True).input_hash
    changed = bundle.demand[0].model_copy(
        update={"source": bundle.demand[0].source.model_copy(update={"revision": 2})}
    )
    assert first.input_hash != frozen(history([changed, *bundle.demand[1:]]), policy).input_hash


def test_revision_selection_is_as_of_and_does_not_leak(history, policy):
    original = demand(CUTOFF)
    late = demand(CUTOFF, 100, 98, 2, source=ref(f"demand:{CUTOFF}", 2, "2026-11-01T00:00:00Z"))
    first = frozen(history([original]), policy)
    assert frozen(history([original, late]), policy).input_hash == first.input_hash
    future = demand(CUTOFF + timedelta(days=1), 999, 999, 0)
    assert frozen(history([original, future]), policy).input_hash == first.input_hash


def test_ambiguous_duplicate_revision_and_duplicate_day_fail(history, policy):
    row = demand(CUTOFF)
    with pytest.raises(ValueError, match="Duplicate revision"):
        frozen(history([row, row]), policy)
    different_fact = demand(CUTOFF, source=ref("competing-fact"))
    with pytest.raises(ValueError, match="Duplicate demand day"):
        frozen(history([row, different_fact]), policy)


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_units": -1},
        {"requested_units": float("nan")},
        {"requested_units": 2},
        {"requested_units": None, "fulfilled_units": -1},
    ],
)
def test_invalid_history_is_rejected_before_fallback(history, changes):
    with pytest.raises(ValidationError):
        history([demand(CUTOFF, **changes)])


def test_chronos_unqualified_is_truthful_and_only_falls_back_when_allowed(history, policy):
    blocked = forecast(frozen(history(), policy, strategy="CHRONOS2"))
    assert not blocked.ready_for_publication
    assert blocked.series[0].errors[0].code == "PROVIDER_UNAVAILABLE"
    result = forecast(frozen(history(), policy, strategy="CHRONOS2", allow_fallback=True)).series[0]
    assert result.actual_provider.name == "SEASONAL_NAIVE"
    assert result.fallback_reason == "PROVIDER_UNAVAILABLE"


def test_inputs_are_deeply_immutable_and_hash_is_checked(history, policy):
    inputs = frozen(history(), policy)
    with pytest.raises(ValidationError):
        inputs.series[0].observations[0].value = 123
    with pytest.raises(ValueError, match="hash"):
        forecast(inputs.model_copy(update={"input_hash": "tampered"}))
    restored = ForecastInput.model_validate_json(inputs.model_dump_json())
    assert reusable_result(restored, forecast(inputs)) is not None


def test_mixed_proxy_history_requires_separate_explicit_opt_in(history, policy):
    rows = [demand(CUTOFF - timedelta(days=i)) for i in range(7)]
    rows[0] = demand(CUTOFF, None, 8, None)
    with pytest.raises(ValueError, match="Mixed proxy"):
        frozen(history(rows), policy, allow_fulfilled_proxy=True)
    inputs = frozen(
        history(rows), policy, allow_fulfilled_proxy=True, allow_mixed_proxy_history=True
    )
    result = forecast(inputs).series[0]
    assert result.target_basis == "MIXED" and result.diagnostics.proxy_fraction == pytest.approx(
        1 / 7
    )
    assert "FULFILLED_PROXY" in result.warnings


def test_leap_day_uses_real_calendar_references(history, policy):
    cutoff = date(2024, 2, 28)
    rows = [demand(cutoff - timedelta(days=i), i, i, 0) for i in range(7)]
    inputs = prepare(
        history(rows),
        data_cutoff_date=cutoff,
        snapshot_as_of=datetime(2024, 2, 29, tzinfo=UTC),
        policy=policy,
    )
    # These facts were recorded in 2026, so they cannot be used in a 2024 replay.
    assert not forecast(inputs).ready_for_publication
    for row in rows:
        row["source"]["recorded_at"] = "2024-01-01T00:00:00Z"
    inputs = prepare(
        history(rows),
        data_cutoff_date=cutoff,
        snapshot_as_of=datetime(2024, 2, 29, tzinfo=UTC),
        policy=policy,
    )
    assert forecast(inputs).series[0].points[0].day == date(2024, 2, 29)
    assert forecast(inputs).series[0].points[0].central_estimate == 6


def test_reuse_keeps_original_generation_and_fallback_provenance(history, policy):
    inputs = frozen(history(), policy, strategy="CHRONOS2", allow_fallback=True)
    saved = forecast(inputs)
    assert reusable_result(inputs, saved) is saved
    assert reusable_result(inputs, saved).series[0].fallback_used
    changed = frozen(history(), policy, strategy="SEASONAL_NAIVE", allow_fallback=True)
    assert reusable_result(changed, saved) is None
    refreshed = forecast(inputs)
    assert refreshed.run_id != saved.run_id
    assert refreshed.series[0].result_id != saved.series[0].result_id


def test_valid_hash_cannot_hide_observations_inconsistent_with_exact_source(history, policy):
    inputs = frozen(history(), policy)
    first = inputs.series[0]
    changed = first.observations[0].model_copy(update={"value": 9999})
    altered_series = first.model_copy(update={"observations": (changed, *first.observations[1:])})
    altered = inputs.model_copy(update={"series": (altered_series,)})
    altered = altered.model_copy(update={"input_hash": canonical_hash(altered)})
    with pytest.raises(ValueError, match="canonical preparation"):
        forecast(altered)
