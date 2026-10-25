from datetime import timedelta

import pytest

from app.services.forecasting.evaluation import EvaluationOrigin, backtest, metrics, paired_metrics

from .conftest import AS_OF, CUTOFF, demand, ref


def evaluate(history, policy):
    return backtest(
        history,
        policy=policy,
        origins=(EvaluationOrigin(data_cutoff_date=CUTOFF, snapshot_as_of=AS_OF),),
        truth_as_of=AS_OF + timedelta(days=14),
    )


def test_measured_metrics_and_missing_actual_counts(history, policy):
    bundle = history()
    rows = list(bundle.demand)
    for offset in range(1, 7):
        rows.append(demand(CUTOFF + timedelta(days=offset), 10, 10, 0))
    report = evaluate(history(rows), policy)
    fold = report.folds[0]
    assert (fold.expected_count, fold.predicted_count, fold.missing_actual_count) == (7, 7, 1)
    score = report.strategy_metrics[0].metrics
    assert score.scored_count == 6
    assert score.mae == 3.5
    assert score.bias == 3.5
    assert score.wape == 0.35
    assert report.actual_provider_metrics[0].actual_provider == "SEASONAL_NAIVE"


def test_post_origin_correction_changes_truth_but_not_training_forecast(history, policy):
    row = demand(CUTOFF, 90, 90, 0, source=ref(f"demand:{CUTOFF}", 2, "2026-10-25T00:00:00Z"))
    held_out = [demand(CUTOFF + timedelta(days=i)) for i in range(1, 8)]
    original = evaluate(history([*history().demand, *held_out]), policy)
    changed = evaluate(history([*history().demand, *held_out, row]), policy)
    assert original.folds[0].input_hash == changed.folds[0].input_hash
    assert len(original.folds[0].pairs) == 7
    assert original.folds[0].pairs == changed.folds[0].pairs


def test_zero_denominator_and_empty_metrics_are_unavailable(history, policy):
    rows = [demand(CUTOFF + timedelta(days=i), 0, 0, 0) for i in range(-6, 8)]
    report = evaluate(history(rows), policy)
    score = report.strategy_metrics[0].metrics
    assert score.mae == 0 and score.wape is None and score.scored_count == 7
    assert metrics(()).model_dump() == {"scored_count": 0, "mae": None, "bias": None, "wape": None}


def test_paired_coverage_and_actual_provider_are_not_chronos_evidence(history, policy):
    rows = [*history().demand, *[demand(CUTOFF + timedelta(days=i)) for i in range(1, 8)]]
    bundle = history(rows)
    baseline = evaluate(bundle, policy)
    unavailable = evaluate(bundle, policy.model_copy(update={"strategy": "CHRONOS2"}))
    fallback = evaluate(
        bundle, policy.model_copy(update={"strategy": "CHRONOS2", "allow_fallback": True})
    )
    assert paired_metrics((baseline, unavailable)) == ((), ())
    assert unavailable.folds[0].unavailable_prediction_count == 7
    assert fallback.actual_provider_metrics[0].actual_provider == "SEASONAL_NAIVE"
    paired = paired_metrics((baseline, fallback))
    assert paired[0][0].metrics == paired[1][0].metrics
    assert fallback.folds[0].fallback_series_count == 1
    changed_pair = fallback.folds[0].pairs[0].model_copy(update={"actual": 999})
    changed_fold = fallback.folds[0].model_copy(
        update={"pairs": (changed_pair, *fallback.folds[0].pairs[1:])}
    )
    with pytest.raises(ValueError, match="held-out truth"):
        paired_metrics((baseline, fallback.model_copy(update={"folds": (changed_fold,)})))


@pytest.mark.parametrize("training_proxy", [False, True])
def test_held_out_basis_change_is_counted_without_relaxing_training(
    history, policy, training_proxy
):
    requested = None if training_proxy else 10
    rows = [demand(CUTOFF - timedelta(days=i), requested, 8, None) for i in range(7)]
    held_requested = 10 if training_proxy else None
    rows.extend(demand(CUTOFF + timedelta(days=i), held_requested, 8, None) for i in range(1, 8))
    selected_policy = policy.model_copy(update={"allow_fulfilled_proxy": True})
    report = evaluate(history(rows), selected_policy)
    fold = report.folds[0]
    assert fold.predicted_count == 7
    assert fold.basis_mismatch_count == 7
    assert fold.pairs == ()
    assert report.strategy_metrics == ()
    assert report.policy.allow_mixed_proxy_history is False
    # Mixed training still needs the separate explicit opt-in.
    rows[0] = demand(CUTOFF, held_requested, 8, None)
    with pytest.raises(ValueError, match="Mixed proxy"):
        evaluate(history(rows), selected_policy)


def test_truth_preparation_does_not_enable_unauthorized_proxies(history, policy):
    rows = [*history().demand]
    rows.extend(demand(CUTOFF + timedelta(days=i), None, 8, None) for i in range(1, 8))
    fold = evaluate(history(rows), policy).folds[0]
    assert fold.missing_actual_count == 7
    assert fold.basis_mismatch_count == 0
    assert fold.pairs == ()
