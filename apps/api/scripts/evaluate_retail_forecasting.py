"""Validation-only retail benchmark CLI with a separately guarded FC-07 entry point.

Run in the pinned optional-model tooling environment. Ordinary imports do not
load models or decode external data. No command-line option opens final truth.
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.forecasting.adapters.chronos2 import (  # noqa: E402
    ADAPTER_VERSION,
    CONTEXT_LENGTH,
    PACKAGE_VERSION,
    THREADS,
    Chronos2Adapter,
    ChronosConfig,
)
from app.services.forecasting.benchmark_data import (  # noqa: E402
    canonical_hash,
    file_sha256,
    load_dataset,
)
from app.services.forecasting.benchmark_evaluation import (  # noqa: E402
    BenchmarkProvider,
    baseline_providers,
    evaluate_benchmark,
    qualification_decision,
)
from scripts.forecasting_data import load_final_holdout  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
_CODE_PATHS = (
    "apps/api/app/services/forecasting/benchmark_data.py",
    "apps/api/app/services/forecasting/benchmark_evaluation.py",
    "apps/api/app/services/forecasting/evaluation.py",
    "apps/api/app/services/forecasting/schemas.py",
    "apps/api/app/services/forecasting/adapters/base.py",
    "apps/api/app/services/forecasting/adapters/seasonal_naive.py",
    "apps/api/app/services/forecasting/adapters/moving_average.py",
    "apps/api/app/services/forecasting/adapters/chronos2.py",
    "apps/api/scripts/forecasting_data.py",
    "apps/api/scripts/evaluate_retail_forecasting.py",
    "docs/forecasting/QUALIFICATION-PROTOCOL.md",
)


def code_identity() -> dict:
    hashes = {path: file_sha256(REPO_ROOT / path) for path in _CODE_PATHS}
    return {"files": hashes, "code_hash": canonical_hash(hashes)}


def model_identity(revision: str) -> dict:
    return {
        "model_id": "amazon/chronos-2",
        "checkpoint_revision": revision,
        "package_version": PACKAGE_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "device": "cpu",
        "dtype": "float32",
        "threads": THREADS,
        "context_length": CONTEXT_LENGTH,
        "cross_learning": False,
        "quantiles": [0.1, 0.5, 0.9],
    }


def model_file_identity(config: ChronosConfig) -> dict:
    if config.cache_dir is None:
        raise ValueError("Measured benchmark execution requires an explicit model cache")
    snapshot = Path(config.cache_dir) / "models--amazon--chronos-2" / "snapshots" / config.revision
    return {name: file_sha256(snapshot / name) for name in ("config.json", "model.safetensors")}


def configured_providers(config: ChronosConfig) -> tuple[BenchmarkProvider, ...]:
    adapter = Chronos2Adapter(config)
    return (
        *baseline_providers(),
        BenchmarkProvider(
            "CHRONOS2",
            config.identity,
            lambda window: adapter.predict_values(
                tuple(row.value for row in window.observations), cutoff=window.cutoff
            ),
        ),
    )


def _runtime() -> dict:
    packages = {}
    for name in ("chronos-forecasting", "torch", "transformers", "numpy", "pyarrow", "pydantic"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.SubprocessError, OSError):
        commit = None
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
        "git_head": commit,
        "source_files_hashed_separately": True,
    }


def peak_rss_kib() -> int | None:
    """Measured process RSS where supported; ordinary Windows imports stay valid."""
    try:
        import resource
    except ImportError:
        return None
    maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(maximum / 1024) if sys.platform == "darwin" else int(maximum)


def _write_new(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_report(output_dir: Path, report: dict, records: tuple[dict, ...]) -> dict:
    output_dir = Path(output_dir)
    _write_new(output_dir / "raw-predictions.json", list(records))
    report["raw_predictions_artifact"] = {
        "filename": "raw-predictions.json",
        "sha256": file_sha256(output_dir / "raw-predictions.json"),
        "canonical_content_hash": report["raw_predictions_hash"],
        "records": len(records),
    }
    _write_new(output_dir / "report.json", report)
    return {
        "report_sha256": file_sha256(output_dir / "report.json"),
        "raw_predictions_sha256": report["raw_predictions_artifact"]["sha256"],
    }


def run_validation(manifest_path: Path, output_dir: Path, config: ChronosConfig) -> dict:
    """Actual validation providers only; this function has no raw eval-file path."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Use an empty output directory for a new frozen validation experiment")
    started = time.monotonic()
    dataset = load_dataset(Path(manifest_path))
    before_code = code_identity()
    model_files = model_file_identity(config)
    report, records = evaluate_benchmark(dataset, configured_providers(config))
    if code_identity() != before_code:
        raise ValueError("Evaluation source files changed while validation was running")
    report["source_code"] = before_code
    report["model_profile"] = model_identity(config.revision)
    report["model_file_sha256"] = model_files
    report["runtime"] = _runtime()
    report["execution"]["wall_seconds"] = time.monotonic() - started
    report["execution"]["process_peak_rss_kib"] = peak_rss_kib()
    artifacts = _write_report(output_dir, report, records)
    freeze = {
        "schema_version": "forecast-validation-freeze-v1",
        "validation_manifest_path": str(Path(manifest_path).resolve()),
        "manifest_file_sha256": file_sha256(Path(manifest_path)),
        "dataset_manifest_hash": dataset.manifest_hash,
        "cohort_hash": dataset.cohort_hash,
        "folds_hash": report["folds_hash"],
        "validation_metrics_hash": report["metrics_hash"],
        "validation_raw_predictions_hash": report["raw_predictions_hash"],
        "model_profile": report["model_profile"],
        "model_file_sha256": model_files,
        "runtime_package_versions": report["runtime"]["packages"],
        "source_code": before_code,
        "validation_selected_baseline": report["baseline_selection"],
        "final_holdout_consulted": False,
        "qualification_protocol": "forecasting-qualification-v1",
        **artifacts,
    }
    freeze["freeze_hash"] = canonical_hash(freeze)
    _write_new(output_dir / "validation-freeze.json", freeze)
    return {
        "output_dir": str(output_dir),
        "freeze_hash": freeze["freeze_hash"],
        "selected_baseline": freeze["validation_selected_baseline"]["selected_strategy"],
        "strategies": {
            name: {
                key: summary[key]
                for key in ("expected_count", "available_prediction_count", "metrics")
            }
            for name, summary in report["strategies"].items()
        },
        "final_holdout_consulted": False,
    }


def run_final_holdout(
    validation_dir: Path,
    data_cache_dir: Path,
    output_dir: Path,
    *,
    model_cache_dir: str,
    operational_qualified: bool,
    allow_final_holdout: bool = False,
) -> dict:
    """FC-07 only: verify frozen choices, journal one opening, then evaluate final.

    There is deliberately no CLI route to this function. Root must first review
    the combined gates and explicitly authorize the one serialized opening.
    """
    if allow_final_holdout is not True:
        raise PermissionError("Final holdout remains sealed until explicit FC-07 authorization")
    validation_dir, output_dir = Path(validation_dir), Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Final output directory must be empty")
    freeze = json.loads((validation_dir / "validation-freeze.json").read_text())
    if freeze["freeze_hash"] != canonical_hash(
        {k: v for k, v in freeze.items() if k != "freeze_hash"}
    ):
        raise ValueError("Validation freeze hash mismatch")
    if freeze["source_code"] != code_identity():
        raise ValueError(
            "Evaluation code changed after validation; review and freeze a new experiment"
        )
    manifest_path = Path(freeze["validation_manifest_path"])
    if file_sha256(manifest_path) != freeze["manifest_file_sha256"] or (
        file_sha256(validation_dir / "report.json") != freeze["report_sha256"]
        or file_sha256(validation_dir / "raw-predictions.json") != freeze["raw_predictions_sha256"]
    ):
        raise ValueError("Frozen validation artifacts changed")
    chosen = freeze["validation_selected_baseline"]["selected_strategy"]
    if chosen is None:
        raise ValueError("No validation-qualified baseline was selected before final evaluation")
    revision = freeze["model_profile"]["checkpoint_revision"]
    if freeze["model_profile"] != model_identity(revision):
        raise ValueError("Model profile changed after validation")
    config = ChronosConfig(revision, cache_dir=model_cache_dir)
    if model_file_identity(config) != freeze["model_file_sha256"] or (
        _runtime()["packages"] != freeze["runtime_package_versions"]
    ):
        raise ValueError("Model files or runtime dependencies changed after validation")
    dataset = load_dataset(manifest_path)
    # Exclusive marker survives failures so the same experiment cannot silently
    # consume/retry the held-out labels after inspecting a failed or partial run.
    _write_new(
        validation_dir / "final-holdout-opened.json",
        {
            "freeze_hash": freeze["freeze_hash"],
            "opened_at": datetime.now(UTC).isoformat(),
            "selected_baseline": chosen,
            "output_dir": str(output_dir.resolve()),
        },
    )
    truth = load_final_holdout(manifest_path, data_cache_dir, allow_final_holdout=True)
    started = time.monotonic()
    report, records = evaluate_benchmark(
        dataset,
        configured_providers(config),
        split="final_holdout",
        final_truth=truth,
        allow_final_holdout=True,
    )
    if code_identity() != freeze["source_code"]:
        raise ValueError(
            "Evaluation code changed during final inference; opening remains journaled"
        )
    report["qualification"] = qualification_decision(
        report, records, chosen, operational_qualified=operational_qualified
    )
    report["validation_freeze_hash"] = freeze["freeze_hash"]
    report["frozen_validation_selected_baseline"] = chosen
    report["source_code"] = freeze["source_code"]
    report["model_profile"] = freeze["model_profile"]
    report["model_file_sha256"] = freeze["model_file_sha256"]
    report["runtime"] = _runtime()
    report["execution"]["wall_seconds"] = time.monotonic() - started
    report["execution"]["process_peak_rss_kib"] = peak_rss_kib()
    _write_report(output_dir, report, records)
    return {
        "output_dir": str(output_dir),
        "qualification": report["qualification"],
        "validation_freeze_hash": freeze["freeze_hash"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--model-cache", required=True)
    args = parser.parse_args()
    result = run_validation(
        args.manifest,
        args.output_dir,
        ChronosConfig(args.model_revision, cache_dir=args.model_cache),
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
