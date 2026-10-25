"""Lazy, pinned, cache-only Chronos-2 inference behind the provider boundary.

Ordinary application imports need neither torch nor chronos. Missing pins,
optional packages or cached checkpoints remain classified unavailable; model
preparation/download is explicit and separate. This adapter does not admit jobs
or change the public baseline contract.
"""

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from numbers import Real
from typing import Any

from pydantic import ValidationError

from ..schemas import ForecastInput, ForecastPoint, PreparedSeries, ProviderIdentity
from .base import ProviderError

MODEL_ID = "amazon/chronos-2"
PACKAGE_VERSION = "2.3.2"
ADAPTER_VERSION = "chronos2-univariate-cpu-f32-v1"
CONTEXT_LENGTH = 366
THREADS = 2
QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True, slots=True)
class ChronosConfig:
    """An operator pin; numerical execution settings are fixed by this profile.

    cache_dir is an operator location, never part of the browser API or forecast
    identity. Its contents resolve only the exact pinned model revision.
    """

    revision: str
    cache_dir: str | None = None

    def __post_init__(self):
        if (
            not isinstance(self.revision, str)
            or re.fullmatch(r"[0-9a-f]{40}", self.revision) is None
        ):
            raise ValueError("Chronos requires a full immutable lowercase checkpoint SHA")
        if self.cache_dir is not None and not isinstance(self.cache_dir, str):
            raise TypeError("cache_dir must be an operator-supplied string or None")

    @property
    def identity(self) -> ProviderIdentity:
        return ProviderIdentity(
            name="CHRONOS2",
            adapter_version=ADAPTER_VERSION,
            package_version=PACKAGE_VERSION,
            checkpoint=MODEL_ID,
            checkpoint_revision=self.revision,
        )


def _load_pipeline(config: ChronosConfig):
    """Load only the pinned local snapshot, inside controlled inference."""
    try:
        actual_version = version("chronos-forecasting")
    except PackageNotFoundError as exc:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Chronos optional dependencies are absent"
        ) from exc
    if actual_version != PACKAGE_VERSION:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Chronos package differs from its frozen version"
        )
    try:
        import torch
        from chronos import Chronos2Pipeline
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError
    except ImportError as exc:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Chronos optional dependencies are absent"
        ) from exc

    torch.set_num_threads(THREADS)
    if torch.get_num_interop_threads() != 1:
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE", "Chronos thread profile cannot be enforced in this process"
            ) from exc
    try:
        local_path = snapshot_download(
            repo_id=MODEL_ID,
            revision=config.revision,
            cache_dir=config.cache_dir,
            local_files_only=True,
            allow_patterns=["config.json", "model.safetensors"],
        )
        pipeline = Chronos2Pipeline.from_pretrained(
            local_path,
            device_map="cpu",
            torch_dtype=torch.float32,
            local_files_only=True,
        )
    except (LocalEntryNotFoundError, OSError) as exc:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Pinned Chronos checkpoint is not usable locally"
        ) from exc
    except (MemoryError, torch.OutOfMemoryError) as exc:
        raise ProviderError(
            "PROVIDER_RESOURCE_EXHAUSTED", "Chronos model exceeded available memory"
        ) from exc
    pipeline.model.eval()
    return pipeline


def _quantile_rows(raw: Any) -> list[list[float]]:
    """Check native [one variate, seven dates, three quantiles] without repair."""
    if not isinstance(raw, tuple) or len(raw) != 2:
        raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos returned an unexpected result")
    quantiles, _native_point = raw
    if not isinstance(quantiles, list) or len(quantiles) != 1:
        raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos returned the wrong series count")
    tensor = quantiles[0]
    if hasattr(tensor, "detach"):
        tensor = tensor.detach().cpu()
    if not hasattr(tensor, "tolist"):
        raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos returned invalid quantile storage")
    values = tensor.tolist()
    if not isinstance(values, list) or len(values) != 1:
        raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos returned the wrong variate count")
    rows = values[0]
    if not isinstance(rows, list) or len(rows) != 7:
        raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos must return seven future dates")
    for row in rows:
        if (
            not isinstance(row, list)
            or len(row) != 3
            or any(
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
                or value < 0
                for value in row
            )
        ):
            raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos returned invalid raw quantiles")
        if row != sorted(row):
            raise ProviderError("INVALID_PROVIDER_OUTPUT", "Chronos returned crossed raw quantiles")
    return rows


class Chronos2Adapter:
    """Independent-series inference, reusing one model per adapter/child.

    A default instance takes its pin from immutable ForecastPolicy at predict
    time. An explicitly configured instance must match that policy. predict_values
    serves source-specific offline envelopes without fabricating pantry history.
    """

    identity = ProviderIdentity(
        name="CHRONOS2", adapter_version=ADAPTER_VERSION, package_version=PACKAGE_VERSION
    )

    def __init__(
        self,
        config: ChronosConfig | None = None,
        *,
        pipeline_loader: Callable[[ChronosConfig], Any] | None = None,
    ):
        self.config = config
        self._pipeline = None
        self._pipeline_loader = pipeline_loader or _load_pipeline
        if config is not None:
            self.identity = config.identity

    def _select_policy(self, inputs: ForecastInput) -> None:
        policy = inputs.policy
        if policy.strategy != "CHRONOS2":
            raise ValueError("Chronos adapter requires the CHRONOS2 strategy")
        if (
            not policy.checkpoint
            or not policy.checkpoint_revision
            or not policy.provider_package_version
        ):
            raise ProviderError("PROVIDER_UNAVAILABLE", "Chronos requires an explicitly frozen pin")
        if policy.checkpoint != MODEL_ID or policy.provider_package_version != PACKAGE_VERSION:
            raise ValueError("Chronos policy does not match the supported model/package")
        requested = ChronosConfig(revision=policy.checkpoint_revision)
        if self.config is None:
            self.config = requested
            self.identity = requested.identity
        elif self.config.revision != requested.revision:
            raise ValueError("Chronos adapter pin differs from the immutable forecast policy")

    def predict_values(
        self, values: Sequence[float | None], *, cutoff: date
    ) -> tuple[ForecastPoint, ...]:
        """Forecast ordered, gap-explicit daily values ending at cutoff.

        Missing rows become native NaN. This method never relabels retail sales as
        requested demand or donation truth.
        """
        if not isinstance(cutoff, date) or isinstance(cutoff, datetime):
            raise TypeError("cutoff must be a local date")
        if not isinstance(values, Sequence) or isinstance(values, str | bytes):
            raise TypeError("values must be a daily sequence")
        if not 1 <= len(values) <= CONTEXT_LENGTH:
            raise ProviderError("INSUFFICIENT_DATA", "Chronos history needs 1–366 daily values")
        if any(
            value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
                or value < 0
            )
            for value in values
        ):
            raise ValueError("Chronos history requires finite nonnegative values or missingness")
        if not any(value is not None for value in values):
            raise ProviderError("INSUFFICIENT_DATA", "Chronos history is entirely missing")
        if self.config is None:
            raise ProviderError("PROVIDER_UNAVAILABLE", "Chronos requires an explicitly frozen pin")
        if self._pipeline is None:
            self._pipeline = self._pipeline_loader(self.config)
        # No optional numeric/model import at module or application startup.
        import numpy as np

        native = np.array(
            [float("nan") if value is None else value for value in values], dtype=np.float32
        )
        if np.isinf(native).any():
            raise ValueError("History cannot be represented by the frozen float32 profile")
        try:
            raw = self._pipeline.predict_quantiles(
                [native],
                prediction_length=7,
                quantile_levels=list(QUANTILES),
                batch_size=1,
                context_length=CONTEXT_LENGTH,
                cross_learning=False,
            )
        except MemoryError as exc:
            raise ProviderError(
                "PROVIDER_RESOURCE_EXHAUSTED", "Chronos inference exceeded available memory"
            ) from exc
        except RuntimeError as exc:
            # torch.OutOfMemoryError derives from RuntimeError, not MemoryError.
            # Match the actual framework class narrowly without importing torch
            # into stub-only/unit-test processes or hiding unrelated native bugs.
            if type(exc).__module__ == "torch" and type(exc).__name__ == "OutOfMemoryError":
                raise ProviderError(
                    "PROVIDER_RESOURCE_EXHAUSTED", "Chronos inference exceeded available memory"
                ) from exc
            raise
        rows = _quantile_rows(raw)
        try:
            return tuple(
                ForecastPoint(
                    day=cutoff + timedelta(days=offset),
                    central_estimate=float(row[1]),
                    estimate_kind="MEDIAN",
                    p10=float(row[0]),
                    p50=float(row[1]),
                    p90=float(row[2]),
                    interval_method="MODEL_QUANTILES",
                )
                for offset, row in enumerate(rows, 1)
            )
        except ValidationError as exc:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT", "Chronos quantiles violate output policy"
            ) from exc

    def predict(self, series: PreparedSeries, inputs: ForecastInput) -> tuple[ForecastPoint, ...]:
        self._select_policy(inputs)
        if series not in inputs.series:
            raise ValueError("Chronos series is outside the immutable forecast scope")
        return self.predict_values(
            tuple(row.value for row in series.observations), cutoff=inputs.data_cutoff_date
        )
