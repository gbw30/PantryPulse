"""Explicit, checksum-pinned FreshRetailNet acquisition and training-only preparation.

Run with a Python environment containing pyarrow (see scripts/forecasting/README.md).
Importing this script does not load Arrow, open external files or access the network.
Final holdout values require the separately named, explicit opt-in function below.
"""

import argparse
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.forecasting.benchmark_data import (  # noqa: E402
    AVAILABILITY,
    RETAIL_BASIS,
    RETAIL_UNIT,
    SEED,
    TRANSFORM_VERSION,
    BenchmarkFold,
    canonical_hash,
    file_sha256,
    materialize_series,
    read_manifest,
    select_cohort,
    series_id,
)

SOURCE_SPEC = (
    Path(__file__).resolve().parents[3]
    / "data/benchmarks/forecasting/freshretailnet50k-source-v1.json"
)
_KEYS = ["store_id", "product_id"]
_VALUE_COLUMNS = [*_KEYS, "dt", "sale_amount", "stock_hour6_22_cnt", "hours_stock_status"]


def _source_spec() -> dict:
    return json.loads(SOURCE_SPEC.read_text(encoding="utf-8"))


def verify_cache(cache_dir: Path, spec: dict) -> None:
    for filename, expected in spec["raw_files"].items():
        path = Path(cache_dir) / filename
        if not path.is_file():
            raise ValueError(
                f"Missing pinned source file: {filename}; use the explicit fetch command"
            )
        if path.stat().st_size != expected["bytes"] or file_sha256(path) != expected["sha256"]:
            raise ValueError(f"Pinned source checksum/size mismatch: {filename}")


def fetch_source(cache_dir: Path, spec: dict) -> None:
    """The only network path: a deliberate fetch of two source-controlled URLs."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for filename, expected in spec["raw_files"].items():
        destination = cache_dir / filename
        if destination.exists():
            if file_sha256(destination) != expected["sha256"]:
                raise ValueError(f"Existing cache has wrong checksum: {filename}")
            continue
        url = (
            f"https://huggingface.co/datasets/{spec['source_id']}/resolve/"
            f"{spec['source_revision']}/data/{filename}?download=true"
        )
        partial = destination.with_suffix(".part")
        try:
            with urllib.request.urlopen(url, timeout=60) as source, partial.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            if partial.stat().st_size != expected["bytes"] or (
                file_sha256(partial) != expected["sha256"]
            ):
                raise ValueError(f"Downloaded source checksum mismatch: {filename}")
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    verify_cache(cache_dir, spec)


def inspect_layout(path: Path) -> dict:
    """Read schema plus key/date columns ONLY; safe for final-holdout preparation."""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    missing = set(_VALUE_COLUMNS) - set(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"Source schema lacks required columns: {sorted(missing)}")
    # In particular, do not read sale_amount, masks or covariates from eval here.
    table = pq.read_table(path, columns=[*_KEYS, "dt"], use_threads=False)
    dates = tuple(sorted(date.fromisoformat(day) for day in pc.unique(table["dt"]).to_pylist()))
    if not dates or any(
        right - left != timedelta(days=1) for left, right in zip(dates, dates[1:], strict=False)
    ):
        raise ValueError("Source split does not have one contiguous global calendar")
    groups = table.group_by(_KEYS, use_threads=False).aggregate(
        [("dt", "count"), ("dt", "count_distinct")]
    )
    rows = groups.to_pylist()
    if any(row["dt_count"] != len(dates) or row["dt_count_distinct"] != len(dates) for row in rows):
        raise ValueError("Source series have duplicate dates or uneven split calendars")
    keys = sorted((row["store_id"], row["product_id"]) for row in rows)
    if any(type(store) is not int or type(product) is not int for store, product in keys):
        raise ValueError("Invalid source store/product IDs")
    return {
        "rows": parquet.metadata.num_rows,
        "series_count": len(keys),
        "calendar_dates": [day.isoformat() for day in dates],
        "keys": keys,
        "schema": {field.name: str(field.type) for field in parquet.schema_arrow},
    }


def read_selected_rows(path: Path, selected_ids: tuple[str, ...]) -> list[dict]:
    """Decode source-native observations only for the already frozen cohort."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    selected = set(selected_ids)
    stores, products = set(), set()
    for identity in selected:
        store, product = identity.split("/")
        stores.add(int(store.removeprefix("store:")))
        products.add(int(product.removeprefix("product:")))
    rows = []
    for batch in pq.ParquetFile(path).iter_batches(
        batch_size=65_536, columns=_VALUE_COLUMNS, use_threads=False
    ):
        mask = pc.and_(
            pc.is_in(batch.column("store_id"), value_set=pa.array(sorted(stores))),
            pc.is_in(batch.column("product_id"), value_set=pa.array(sorted(products))),
        )
        for row in batch.filter(mask).to_pylist():
            if series_id(row["store_id"], row["product_id"]) in selected:
                rows.append(row)
    return sorted(rows, key=lambda row: (row["store_id"], row["product_id"], row["dt"]))


def _write_once(path: Path, value: dict) -> None:
    content = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"Refusing to replace a different frozen artifact: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def prepare_dataset(cache_dir: Path, output_dir: Path, *, cohort_size: int = 100) -> dict:
    spec = _source_spec()
    verify_cache(cache_dir, spec)
    train_layout = inspect_layout(Path(cache_dir) / "train.parquet")
    eval_layout = inspect_layout(Path(cache_dir) / "eval.parquet")
    train_dates = tuple(date.fromisoformat(day) for day in train_layout["calendar_dates"])
    eval_dates = tuple(date.fromisoformat(day) for day in eval_layout["calendar_dates"])
    if (
        len(train_dates) != 90
        or len(eval_dates) != 7
        or (eval_dates[0] != train_dates[-1] + timedelta(days=1))
    ):
        raise ValueError("Pinned source differs from frozen 90-day train / 7-day final protocol")
    if train_layout["keys"] != eval_layout["keys"]:
        raise ValueError("Upstream split series identities differ")
    selected = select_cohort(train_layout["keys"], cohort_size, SEED)
    source_rows = read_selected_rows(Path(cache_dir) / "train.parquet", selected)
    series = materialize_series(source_rows, start=train_dates[0], end=train_dates[-1])
    if tuple(sorted(row.series_id for row in series)) != selected:
        raise ValueError("Source conversion did not produce the frozen cohort")
    training = {
        "schema_version": "forecast-benchmark-training-v1",
        "transform_version": TRANSFORM_VERSION,
        "availability_semantics": AVAILABILITY,
        "series": [row.as_dict() for row in series],
    }
    output_dir = Path(output_dir)
    training_path = output_dir / "pilot-training.json"
    _write_once(training_path, training)
    folds = tuple(
        BenchmarkFold(
            f"validation-day-{offset}",
            train_dates[offset - 1],
            tuple(train_dates[offset - 1] + timedelta(days=i) for i in range(1, 8)),
        )
        for offset in (62, 69, 76, 83)
    )
    final = BenchmarkFold("upstream-final-week", train_dates[-1], eval_dates, "final_holdout")
    observations = [observation for row in series for observation in row.observations]
    cohort_summary = {
        "series_count": len(series),
        "training_observations": len(observations),
        "zero_value_count": sum(row.value == 0 for row in observations),
        "missing_value_count": sum(row.value is None for row in observations),
        "censored_day_count": sum(row.censored is True for row in observations),
        "uncensored_day_count": sum(row.censored is False for row in observations),
        "unknown_censoring_count": sum(row.censored is None for row in observations),
        "series_with_zero": sum(any(o.value == 0 for o in row.observations) for row in series),
        "series_with_missing": sum(
            any(o.value is None for o in row.observations) for row in series
        ),
        "series_with_censoring": sum(
            any(o.censored is True for o in row.observations) for row in series
        ),
    }
    manifest = {
        "schema_version": "forecast-benchmark-manifest-v1",
        "source_id": spec["source_id"],
        "source_revision": spec["source_revision"],
        "source_url": spec["source_url"],
        "license": spec["license"],
        "attribution": spec["attribution"],
        "raw_files": spec["raw_files"],
        "transform_version": TRANSFORM_VERSION,
        "transformation_sha256": canonical_hash(
            {
                "cli": file_sha256(Path(__file__)),
                "envelope": file_sha256(
                    Path(__file__).resolve().parents[1]
                    / "app/services/forecasting/benchmark_data.py"
                ),
            }
        ),
        "target_basis": RETAIL_BASIS,
        "unit": RETAIL_UNIT,
        "availability_semantics": AVAILABILITY,
        "sampling": {
            "method": "stable-sha256-training-ids-v1",
            "seed": SEED,
            "requested_size": cohort_size,
            "source_series_count": len(train_layout["keys"]),
            "excluded_series_count": len(train_layout["keys"]) - cohort_size,
        },
        "series_ids": list(selected),
        "cohort_hash": canonical_hash(list(selected)),
        "training_artifact": {"filename": training_path.name, "sha256": file_sha256(training_path)},
        "validation_folds": [fold.as_dict() for fold in folds],
        "final_fold": final.as_dict(),
        "final_holdout_values_included": False,
        "final_holdout_columns_read": [*_KEYS, "dt"],
        "training_calendar": {
            "start": train_dates[0].isoformat(),
            "end": train_dates[-1].isoformat(),
            "days": len(train_dates),
        },
        "source_layout": {
            "train_rows": train_layout["rows"],
            "eval_rows": eval_layout["rows"],
            "series_count": train_layout["series_count"],
            "schema": train_layout["schema"],
        },
        "cohort_summary_training_only": cohort_summary,
        "limitations": [
            "Normalized retail observed sales, not latent requested demand or donations",
            "Retrospective event-time evaluation; historical recording revisions unavailable",
            "Stockout-day sales are censored; uncensored diagnostics remain conditional",
            "Short history does not establish annual seasonality",
            "Model pretraining contamination remains unknown",
            "Initial pilot is an ID-hash sample, not a representative stratified population",
        ],
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    _write_once(output_dir / "manifest.json", manifest)
    return manifest


def load_final_holdout(manifest_path: Path, cache_dir: Path, *, allow_final_holdout: bool = False):
    """Only FC-07 may explicitly opt in after freezing validation/model settings.

    Returns seven-day BenchmarkSeries records, not training+truth concatenation.
    Calling without the flag raises before accessing any raw source file.
    """
    if allow_final_holdout is not True:
        raise PermissionError("Final holdout is sealed; explicit FC-07 opt-in is required")
    manifest = read_manifest(Path(manifest_path))
    spec = _source_spec()
    if manifest["source_revision"] != spec["source_revision"] or (
        manifest["raw_files"] != spec["raw_files"]
    ):
        raise ValueError("Holdout source differs from the frozen manifest")
    verify_cache(cache_dir, spec)
    selected = tuple(manifest["series_ids"])
    rows = read_selected_rows(Path(cache_dir) / "eval.parquet", selected)
    dates = tuple(date.fromisoformat(day) for day in manifest["final_fold"]["truth_dates"])
    return materialize_series(rows, start=dates[0], end=dates[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Explicit download of checksum-pinned source files")
    fetch.add_argument("--cache-dir", type=Path, required=True)
    prepare = commands.add_parser("prepare", help="Prepare training-only cohort and sealed splits")
    prepare.add_argument("--cache-dir", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--cohort-size", type=int, default=100)
    args = parser.parse_args()
    if args.command == "fetch":
        fetch_source(args.cache_dir, _source_spec())
        print(json.dumps({"status": "verified", "cache_dir": str(args.cache_dir)}))
    else:
        manifest = prepare_dataset(args.cache_dir, args.output_dir, cohort_size=args.cohort_size)
        print(
            json.dumps(
                {
                    "manifest_hash": manifest["manifest_hash"],
                    "cohort": manifest["cohort_summary_training_only"],
                    "final_holdout_values_included": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
