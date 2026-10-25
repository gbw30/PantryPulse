"""Immutable offline retail benchmark data; never a production demand/stock contract.

Source-native normalized sales remain observed sales. Missing dates are explicit,
and stockout annotations describe censoring rather than recovered latent demand.
No pandas/Arrow/model imports or network access occur in this module.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

RETAIL_UNIT = "NORMALIZED_RETAIL_SALES"
RETAIL_BASIS = "OBSERVED_RETAIL_SALES"
AVAILABILITY = "RETROSPECTIVE_EVENT_TIME"
TRANSFORM_VERSION = "freshretailnet-observed-sales-v1"
SEED = 20261025


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _plain_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    day: date
    value: float | None
    stockout_hours: int | None = None
    hourly_stockout_status: tuple[int, ...] | None = None
    source_present: bool = True

    def __post_init__(self) -> None:
        if not _plain_date(self.day):
            raise TypeError("Observation day must be a plain date")
        if self.value is not None and (
            type(self.value) not in (float, int) or not math.isfinite(self.value) or self.value < 0
        ):
            raise ValueError("Observed sales must be finite, nonnegative or missing")
        if type(self.source_present) is not bool:
            raise TypeError("source_present must be bool")
        if self.stockout_hours is not None and (
            type(self.stockout_hours) is not int or not 0 <= self.stockout_hours <= 17
        ):
            raise ValueError("Stockout hours must be an integer in 0..17 or unknown")
        flags = self.hourly_stockout_status
        if flags is not None and (
            type(flags) is not tuple
            or len(flags) != 24
            or any(type(flag) is not int or flag not in (0, 1) for flag in flags)
        ):
            raise ValueError("Hourly stockout status must retain exactly 24 binary flags")
        if not self.source_present and (
            self.value is not None or self.stockout_hours is not None or flags is not None
        ):
            raise ValueError("An absent source row cannot claim an observed value or mask")

    @property
    def censored(self) -> bool | None:
        # The source count is for its daytime window; nightly mask bits alone do
        # not establish a censored service day.
        return self.stockout_hours > 0 if self.stockout_hours is not None else None

    def as_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "value": self.value,
            "stockout_hours": self.stockout_hours,
            "hourly_stockout_status": (
                list(self.hourly_stockout_status)
                if self.hourly_stockout_status is not None
                else None
            ),
            "source_present": self.source_present,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkWindow:
    series_id: str
    cutoff: date
    observations: tuple[BenchmarkObservation, ...]
    unit: str = RETAIL_UNIT
    target_basis: str = RETAIL_BASIS
    availability_semantics: str = AVAILABILITY

    def __post_init__(self) -> None:
        if not _plain_date(self.cutoff) or not self.observations:
            raise ValueError("Model window needs a cutoff and observations")
        if self.unit != RETAIL_UNIT or self.target_basis != RETAIL_BASIS:
            raise ValueError("Model window must preserve native retail semantics")
        if any(row.day > self.cutoff for row in self.observations):
            raise ValueError("Model window cannot expose future observations")
        if any(
            right.day - left.day != timedelta(days=1)
            for left, right in zip(self.observations, self.observations[1:], strict=False)
        ):
            raise ValueError("Model window must retain a gap-explicit calendar")

    @property
    def input_hash(self) -> str:
        # Only data available by this origin enter the model-input identity.
        # The separately recorded raw-file hash is intentionally not included.
        return canonical_hash(
            {
                "series_id": self.series_id,
                "cutoff": self.cutoff.isoformat(),
                "observations": [observation.as_dict() for observation in self.observations],
                "unit": self.unit,
                "target_basis": self.target_basis,
                "availability_semantics": self.availability_semantics,
            }
        )


@dataclass(frozen=True, slots=True)
class BenchmarkSeries:
    series_id: str
    store_id: int
    product_id: int
    observations: tuple[BenchmarkObservation, ...]
    unit: str = RETAIL_UNIT
    target_basis: str = RETAIL_BASIS

    def __post_init__(self) -> None:
        if type(self.store_id) is not int or type(self.product_id) is not int:
            raise TypeError("Source IDs must remain integers")
        if self.series_id != series_id(self.store_id, self.product_id):
            raise ValueError("Series identity contradicts native store/product IDs")
        if self.unit != RETAIL_UNIT or self.target_basis != RETAIL_BASIS:
            raise ValueError("Retail sales cannot be relabeled as pantry need or stock")
        if type(self.observations) is not tuple or not self.observations:
            raise ValueError("A series needs an immutable nonempty observation calendar")
        if any(not isinstance(row, BenchmarkObservation) for row in self.observations):
            raise TypeError("Observations must be BenchmarkObservation records")
        if any(
            right.day - left.day != timedelta(days=1)
            for left, right in zip(self.observations, self.observations[1:], strict=False)
        ):
            raise ValueError("Series dates must be unique, ordered and gap-explicit")

    def at_origin(self, cutoff: date) -> BenchmarkWindow:
        if not _plain_date(cutoff):
            raise TypeError("Cutoff must be a plain date")
        rows = tuple(row for row in self.observations if row.day <= cutoff)
        if not rows or rows[-1].day != cutoff:
            raise ValueError("Origin must be within the explicit observation calendar")
        return BenchmarkWindow(self.series_id, cutoff, rows, self.unit, self.target_basis)

    def as_dict(self) -> dict:
        return {
            "series_id": self.series_id,
            "store_id": self.store_id,
            "product_id": self.product_id,
            "unit": self.unit,
            "target_basis": self.target_basis,
            "observations": [row.as_dict() for row in self.observations],
        }


@dataclass(frozen=True, slots=True)
class BenchmarkFold:
    name: str
    cutoff: date
    truth_dates: tuple[date, ...]
    split: str = "validation"

    def __post_init__(self) -> None:
        if not self.name or not _plain_date(self.cutoff):
            raise ValueError("A fold needs a name and plain cutoff date")
        if self.split not in ("validation", "final_holdout"):
            raise ValueError("Unknown fold split")
        if type(self.truth_dates) is not tuple or self.truth_dates != tuple(
            self.cutoff + timedelta(days=offset) for offset in range(1, 8)
        ):
            raise ValueError("A fold requires exactly seven future calendar dates")

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "cutoff": self.cutoff.isoformat(),
            "truth_dates": [day.isoformat() for day in self.truth_dates],
            "split": self.split,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkDataset:
    source_id: str
    source_revision: str
    series: tuple[BenchmarkSeries, ...]
    validation_folds: tuple[BenchmarkFold, ...]
    final_fold: BenchmarkFold
    source_train_sha256: str
    source_eval_sha256: str
    cohort_hash: str
    manifest_hash: str
    availability_semantics: str = AVAILABILITY

    def __post_init__(self) -> None:
        if len({row.series_id for row in self.series}) != len(self.series):
            raise ValueError("Duplicate benchmark series")
        if not self.series or not self.validation_folds:
            raise ValueError("Dataset needs nonempty series and validation folds")
        if self.availability_semantics != AVAILABILITY:
            raise ValueError("Source does not establish historical knowledge timestamps")
        if self.final_fold.split != "final_holdout":
            raise ValueError("Final holdout must be explicitly named")
        if any(
            fold.split != "validation" or fold.truth_dates[-1] > self.final_fold.cutoff
            for fold in self.validation_folds
        ):
            raise ValueError("Validation truth must remain before final holdout")
        if any(row.observations[-1].day > self.final_fold.cutoff for row in self.series):
            raise ValueError("Ordinary benchmark dataset must not contain final truth")
        if any(
            fold.cutoff < row.observations[0].day or fold.truth_dates[-1] > row.observations[-1].day
            for row in self.series
            for fold in self.validation_folds
        ):
            raise ValueError("Validation folds fall outside the training calendar")


def series_id(store_id: int, product_id: int) -> str:
    return f"store:{store_id}/product:{product_id}"


def select_cohort(keys: list[tuple[int, int]], size: int, seed: int = SEED) -> tuple[str, ...]:
    if type(size) is not int or size < 1 or size > len(keys):
        raise ValueError("Cohort size must be between one and the available series count")
    if type(seed) is not int or len(set(keys)) != len(keys):
        raise ValueError("Cohort keys must be unique and seed must be integer")
    ranked = sorted(
        (series_id(store, product) for store, product in keys),
        key=lambda key: (hashlib.sha256(f"{seed}:{key}".encode()).hexdigest(), key),
    )
    return tuple(sorted(ranked[:size]))


def materialize_series(rows: list[dict], *, start: date, end: date) -> tuple[BenchmarkSeries, ...]:
    """Validate source rows and fill missing *rows* with explicit nulls, never zero."""
    if not _plain_date(start) or not _plain_date(end) or end < start:
        raise ValueError("Invalid explicit source calendar")
    grouped: dict[tuple[int, int], dict[date, BenchmarkObservation]] = {}
    for raw in rows:
        store, product = raw["store_id"], raw["product_id"]
        if type(store) is not int or type(product) is not int:
            raise TypeError("Source IDs must remain integers")
        day = date.fromisoformat(raw["dt"])
        if not start <= day <= end:
            raise ValueError("Source row lies outside declared split dates")
        flags = raw.get("hours_stock_status")
        row = BenchmarkObservation(
            day=day,
            value=raw.get("sale_amount"),
            stockout_hours=raw.get("stock_hour6_22_cnt"),
            hourly_stockout_status=tuple(flags) if flags is not None else None,
        )
        by_day = grouped.setdefault((store, product), {})
        if day in by_day:
            raise ValueError("Duplicate source series/date")
        by_day[day] = row
    calendar = tuple(start + timedelta(days=offset) for offset in range((end - start).days + 1))
    return tuple(
        BenchmarkSeries(
            series_id(store, product),
            store,
            product,
            tuple(
                by_day.get(day, BenchmarkObservation(day, None, source_present=False))
                for day in calendar
            ),
        )
        for (store, product), by_day in sorted(grouped.items())
    )


def read_manifest(path: Path) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = manifest.get("manifest_hash")
    if not expected or expected != canonical_hash(
        {key: value for key, value in manifest.items() if key != "manifest_hash"}
    ):
        raise ValueError("Benchmark manifest checksum mismatch")
    if manifest.get("transform_version") != TRANSFORM_VERSION:
        raise ValueError("Unsupported benchmark transformation")
    if manifest.get("final_holdout_values_included") is not False:
        raise ValueError("Ordinary manifest must exclude final holdout values")
    if manifest.get("cohort_hash") != canonical_hash(manifest.get("series_ids")):
        raise ValueError("Cohort checksum mismatch")
    return manifest


def _fold(raw: dict) -> BenchmarkFold:
    return BenchmarkFold(
        name=raw["name"],
        cutoff=date.fromisoformat(raw["cutoff"]),
        truth_dates=tuple(date.fromisoformat(day) for day in raw["truth_dates"]),
        split=raw["split"],
    )


def load_dataset(manifest_path: Path) -> BenchmarkDataset:
    """Load training-only converted observations and verify both content identities."""
    manifest_path = Path(manifest_path)
    manifest = read_manifest(manifest_path)
    data_path = manifest_path.parent / manifest["training_artifact"]["filename"]
    if file_sha256(data_path) != manifest["training_artifact"]["sha256"]:
        raise ValueError("Converted training artifact checksum mismatch")
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    series = []
    for item in raw["series"]:
        observations = tuple(
            BenchmarkObservation(
                date.fromisoformat(row["day"]),
                row["value"],
                row["stockout_hours"],
                tuple(row["hourly_stockout_status"])
                if row["hourly_stockout_status"] is not None
                else None,
                row["source_present"],
            )
            for row in item["observations"]
        )
        series.append(
            BenchmarkSeries(
                item["series_id"],
                item["store_id"],
                item["product_id"],
                observations,
                item["unit"],
                item["target_basis"],
            )
        )
    if sorted(row.series_id for row in series) != manifest["series_ids"]:
        raise ValueError("Training artifact does not match frozen cohort")
    return BenchmarkDataset(
        source_id=manifest["source_id"],
        source_revision=manifest["source_revision"],
        series=tuple(series),
        validation_folds=tuple(_fold(fold) for fold in manifest["validation_folds"]),
        final_fold=_fold(manifest["final_fold"]),
        source_train_sha256=manifest["raw_files"]["train.parquet"]["sha256"],
        source_eval_sha256=manifest["raw_files"]["eval.parquet"]["sha256"],
        cohort_hash=manifest["cohort_hash"],
        manifest_hash=manifest["manifest_hash"],
    )
