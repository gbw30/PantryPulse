"""Explicit real-model provider smoke; no network, database, API or final holdout.

Run from apps/api with an installed optional model environment and a prepared
official snapshot: python -m scripts.smoke_chronos_adapter --revision FULL_SHA
--cache-dir CACHE --output /tmp/chronos-adapter-smoke.json. This smoke records
invalid raw quantiles as failures rather than repairing them or hiding fallback.
"""

import argparse
import hashlib
import json
import platform
import resource
import time
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from app.services.forecasting.adapters.chronos2 import (
    ADAPTER_VERSION,
    CONTEXT_LENGTH,
    MODEL_ID,
    PACKAGE_VERSION,
    THREADS,
    Chronos2Adapter,
    ChronosConfig,
    _load_pipeline,
)
from app.services.forecasting.preparation import prepare
from app.services.forecasting.service import forecast
from scripts.forecasting_fixture import build_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--cache-dir")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 3:
        parser.error("repeats must be between one and three")
    config = ChronosConfig(args.revision, args.cache_dir)
    history, policy, origins, truth_as_of = build_fixture()
    inputs = prepare(
        history,
        data_cutoff_date=origins[-1].data_cutoff_date + timedelta(days=7),
        snapshot_as_of=truth_as_of,
        policy=policy.model_copy(
            update={
                "strategy": "CHRONOS2",
                "allow_fallback": False,
                "checkpoint": MODEL_ID,
                "checkpoint_revision": args.revision,
                "provider_package_version": PACKAGE_VERSION,
            }
        ),
    )
    native_summaries = []
    loads = []

    class RecordingPipeline:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def predict_quantiles(self, values, **kwargs):
            started = time.perf_counter()
            raw = self.wrapped.predict_quantiles(values, **kwargs)
            native_summaries.append(
                {
                    "seconds": time.perf_counter() - started,
                    "history_length": len(values[0]),
                    "missing_count": int(sum(value != value for value in values[0])),
                    "raw_quantiles": raw[0][0].tolist(),
                }
            )
            return raw

    def loader(selected):
        started = time.perf_counter()
        loaded = _load_pipeline(selected)
        loads.append(time.perf_counter() - started)
        return RecordingPipeline(loaded)

    adapter = Chronos2Adapter(config, pipeline_loader=loader)
    started = time.perf_counter()
    runs = []
    for _ in range(args.repeats):
        begin = time.perf_counter()
        output = forecast(inputs, adapter=adapter, single_candidate=True)
        runs.append(
            {
                "seconds": time.perf_counter() - begin,
                "ready_for_publication": output.ready_for_publication,
                "series_count": len(output.series),
                "available_series": sum(row.status == "AVAILABLE" for row in output.series),
                "forecast_point_count": sum(len(row.points) for row in output.series),
                "series": [row.model_dump(mode="json") for row in output.series],
            }
        )
    edge_cases = {}
    from app.services.forecasting.adapters.base import ProviderError

    for name, values in {
        "gappy": [10.0, None, 12.0, 0.0, None, 15.0, 9.0] * 4,
        "all_zero": [0.0] * 28,
        "one_observation": [10.0],
        "all_missing": [None] * 28,
    }.items():
        try:
            points = adapter.predict_values(values, cutoff=inputs.data_cutoff_date)
            edge_cases[name] = {
                "status": "AVAILABLE",
                "points": [point.model_dump(mode="json") for point in points],
            }
        except ProviderError as exc:
            edge_cases[name] = {"status": "CLASSIFIED_FAILURE", "code": exc.code}
    record = {
        "schema_version": "chronos-adapter-smoke-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "real adapter execution on SIMULATED history; not predictive qualification",
        "model_id": MODEL_ID,
        "revision": args.revision,
        "adapter_version": ADAPTER_VERSION,
        "environment": {
            name: version(name)
            for name in ("chronos-forecasting", "torch", "transformers", "huggingface-hub", "numpy")
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "threads": THREADS,
            "device": "cpu",
            "dtype": "float32",
            "context_length": CONTEXT_LENGTH,
            "cross_learning": False,
        },
        "input_hash": inputs.input_hash,
        "code_sha256": hashlib.sha256(
            Path("app/services/forecasting/adapters/chronos2.py").read_bytes()
        ).hexdigest(),
        "runs": runs,
        "model_load_seconds": loads,
        "edge_cases": edge_cases,
        "native_summaries": native_summaries,
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                key: record[key]
                for key in ("input_hash", "model_load_seconds", "wall_seconds", "peak_rss_kib")
            }
            | {
                "runs": [{k: v for k, v in run.items() if k != "series"} for run in runs],
                "edge_status": {
                    name: {k: v for k, v in result.items() if k != "points"}
                    for name, result in edge_cases.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
