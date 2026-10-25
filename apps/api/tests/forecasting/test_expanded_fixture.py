from datetime import timedelta

from app.services.forecasting.evaluation import backtest
from app.services.forecasting.preparation import prepare
from app.services.forecasting.service import forecast
from scripts.forecasting_fixture import build_fixture


def test_six_beneficiaries_two_products_and_designated_hub_targets():
    history, policy, origins, as_of = build_fixture()
    demand = [scope for scope in history.scope if scope.key.target_type == "DEMAND"]
    assert len({scope.key.site_id for scope in demand}) == 6
    assert len({scope.key.product_id for scope in history.scope}) == 2
    assert len(history.scope) == 26
    inputs = prepare(
        history,
        data_cutoff_date=origins[-1].data_cutoff_date + timedelta(days=7),
        snapshot_as_of=as_of,
        policy=policy,
    )
    output = forecast(inputs)
    assert output.ready_for_publication
    assert sum(len(series.points) for series in output.series) == 182
    assert "SIMULATED_SOURCE" in output.warnings
    report = backtest(history, origins=origins, policy=policy, truth_as_of=as_of)
    assert sum(len(fold.pairs) for fold in report.folds) == 728
    assert all(fold.unavailable_prediction_count == 0 for fold in report.folds)
    assert {group.unit for group in report.strategy_metrics} == {"meal", "bottle"}
