"""Offline demo/evaluation; run from apps/api with `python -m scripts.evaluate_forecasting`."""

import argparse
import json
from datetime import timedelta
from pathlib import Path

from app.services.forecasting.evaluation import backtest, paired_metrics
from app.services.forecasting.handoff import DemandChoice, freeze_handoff
from app.services.forecasting.preparation import prepare
from app.services.forecasting.service import forecast
from scripts.forecasting_fixture import build_fixture


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write full synthetic evidence as JSON")
    args = parser.parse_args()
    history, policy, origins, truth_as_of = build_fixture()
    reports = tuple(
        backtest(
            history,
            origins=origins,
            truth_as_of=truth_as_of,
            policy=policy.model_copy(update={"strategy": strategy}),
        )
        for strategy in ("SEASONAL_NAIVE", "MOVING_AVERAGE")
    )
    cutoff = origins[-1].data_cutoff_date + timedelta(days=7)
    inputs = prepare(history, data_cutoff_date=cutoff, snapshot_as_of=truth_as_of, policy=policy)
    output = forecast(inputs)
    handoff = freeze_handoff(
        inputs,
        output,
        choices=tuple(
            DemandChoice(key=scope.key, mode="CENTRAL")
            for scope in history.scope
            if scope.key.target_type == "DEMAND"
        ),
    )
    evidence = {
        "classification": "SIMULATED",
        "qualification": {
            "experiment_scope": "OFFLINE_SYNTHETIC_BASELINE_EVALUATION",
            "postgres_api_jobs": "IMPLEMENTED_NOT_EXERCISED_BY_THIS_COMMAND",
            "chronos": "NOT_EVALUATED_BY_THIS_COMMAND",
            "solvers_research": "IMPLEMENTED_NOT_EXERCISED_BY_THIS_COMMAND",
            "predictive_accuracy": "SYNTHETIC_ONLY_NOT_DOMAIN_QUALIFIED",
        },
        "fixture": {
            "beneficiaries": 6,
            "hubs": 1,
            "products": 2,
            "required_series": len(history.scope),
            "optional_series": 0,
            "ineligible_series": "Hub DEMAND for both products",
        },
        "input_hash": inputs.input_hash,
        "run_id": str(output.run_id),
        "handoff_hash": handoff.content_hash,
        "ready_for_publication": output.ready_for_publication,
        "forecast_point_count": sum(len(series.points) for series in output.series),
        "reports": [report.model_dump(mode="json") for report in reports],
        "paired_metrics": [
            [group.model_dump(mode="json") for group in groups]
            for groups in paired_metrics(reports)
        ],
        "forecast_input": inputs.model_dump(mode="json"),
        "forecast_output": output.model_dump(mode="json"),
        "handoff": handoff.model_dump(mode="json"),
    }
    if args.output:
        args.output.write_text(
            json.dumps(evidence, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    summary = {
        key: value
        for key, value in evidence.items()
        if key not in {"reports", "forecast_input", "forecast_output", "handoff"}
    }
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
