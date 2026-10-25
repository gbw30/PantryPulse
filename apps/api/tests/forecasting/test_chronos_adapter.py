"""Provider contract checks; stubs prove boundaries, not actual model inference."""

import copy
import math
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from app.services.forecasting.adapters import chronos2
from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.adapters.chronos2 import (
    ADAPTER_VERSION,
    MODEL_ID,
    PACKAGE_VERSION,
    Chronos2Adapter,
    ChronosConfig,
)
from app.services.forecasting.service import forecast

from .conftest import CUTOFF
from .test_core import frozen

REVISION = "a" * 40


class Native:
    def __init__(self, rows=None, error=None):
        self.rows = rows if rows is not None else [[1.0, 2.0, 3.0] for _ in range(7)]
        self.calls = []
        self.error = error

    def predict_quantiles(self, values, **kwargs):
        self.calls.append((values, kwargs))
        if self.error:
            raise self.error
        # The native point slot is deliberately wrong: it must never be our median.
        return [np.array([self.rows])], [np.array([[999.0] * 7])]


def pinned(history, policy):
    return frozen(
        history(),
        policy,
        strategy="CHRONOS2",
        checkpoint=MODEL_ID,
        checkpoint_revision=REVISION,
        provider_package_version=PACKAGE_VERSION,
    )


def configured(native):
    calls = []

    def loader(config):
        calls.append(config)
        return native

    return Chronos2Adapter(
        ChronosConfig(REVISION, "/operator/cache"), pipeline_loader=loader
    ), calls


def test_import_has_no_heavy_model_dependencies():
    code = (
        "import sys; from app.services.forecasting.adapters.chronos2 import Chronos2Adapter; "
        "assert not {'torch','chronos','huggingface_hub','numpy'}.intersection(sys.modules)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[2], check=True)


def test_pinned_policy_maps_seven_dates_and_actual_quantiles(history, policy):
    inputs = pinned(history, policy)
    native = Native()
    adapter, loads = configured(native)
    result = forecast(inputs, adapter=adapter, single_candidate=True)
    assert result.ready_for_publication
    row = result.series[0]
    assert [p.day for p in row.points] == [CUTOFF + timedelta(days=i) for i in range(1, 8)]
    assert all(
        p.central_estimate == p.p50 == 2.0
        and p.estimate_kind == "MEDIAN"
        and p.p10 == 1.0
        and p.p90 == 3.0
        and p.interval_method == "MODEL_QUANTILES"
        for p in row.points
    )
    assert row.actual_provider.model_dump() == {
        "name": "CHRONOS2",
        "adapter_version": ADAPTER_VERSION,
        "package_version": PACKAGE_VERSION,
        "checkpoint": MODEL_ID,
        "checkpoint_revision": REVISION,
    }
    assert not row.fallback_used
    assert len(loads) == 1
    assert native.calls[0][1] == {
        "prediction_length": 7,
        "quantile_levels": [0.1, 0.5, 0.9],
        "batch_size": 1,
        "context_length": 366,
        "cross_learning": False,
    }


def test_model_load_is_lazy_and_reused_across_calls():
    native = Native()
    adapter, loads = configured(native)
    assert loads == []
    adapter.predict_values([1.0] * 28, cutoff=CUTOFF)
    adapter.predict_values([2.0] * 7, cutoff=CUTOFF)
    assert len(loads) == 1
    assert len(native.calls) == 2


def test_native_input_keeps_missing_gaps_zeros_and_order():
    native = Native()
    adapter, _ = configured(native)
    original = [None, 0.0, 4.0, None, 6.0]
    adapter.predict_values(original, cutoff=CUTOFF)
    passed = native.calls[0][0][0]
    assert passed.dtype == np.float32
    assert math.isnan(passed[0]) and math.isnan(passed[3])
    assert passed[[1, 2, 4]].tolist() == [0.0, 4.0, 6.0]
    assert original == [None, 0.0, 4.0, None, 6.0]


@pytest.mark.parametrize("values", [[], [None] * 7, [1.0] * 367])
def test_unusable_history_fails_before_loading(values):
    adapter, loads = configured(Native())
    with pytest.raises(ProviderError) as exc:
        adapter.predict_values(values, cutoff=CUTOFF)
    assert exc.value.code == "INSUFFICIENT_DATA"
    assert loads == []


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), True, "1"])
def test_invalid_history_is_not_classified_as_substitutable_provider_failure(bad):
    adapter, loads = configured(Native())
    with pytest.raises(ValueError):
        adapter.predict_values([bad], cutoff=CUTOFF)
    assert loads == []


@pytest.mark.parametrize("revision", ["main", "a" * 39, "A" * 40, "../cache", None])
def test_config_requires_exact_immutable_revision(revision):
    with pytest.raises(ValueError):
        ChronosConfig(revision)


def test_missing_policy_pin_stays_unavailable_without_loading(history, policy):
    adapter, loads = configured(Native())
    inputs = frozen(history(), policy, strategy="CHRONOS2")
    with pytest.raises(ProviderError) as exc:
        adapter.predict(inputs.series[0], inputs)
    assert exc.value.code == "PROVIDER_UNAVAILABLE"
    assert loads == []


def test_default_adapter_can_resolve_pin_from_input_policy(history, policy, monkeypatch):
    native = Native()
    configs = []
    monkeypatch.setattr(chronos2, "_load_pipeline", lambda cfg: configs.append(cfg) or native)
    adapter = Chronos2Adapter()
    inputs = pinned(history, policy)
    adapter.predict(inputs.series[0], inputs)
    assert adapter.config.revision == REVISION
    assert adapter.identity.checkpoint_revision == REVISION
    assert len(configs) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"checkpoint_revision": "b" * 40},
        {"checkpoint": "arbitrary/model"},
        {"provider_package_version": "9.9.9"},
        {"strategy": "MOVING_AVERAGE"},
    ],
)
def test_policy_mismatch_is_application_error_not_fallback(history, policy, change):
    inputs = pinned(history, policy)
    changed = inputs.model_copy(update={"policy": inputs.policy.model_copy(update=change)})
    adapter, loads = configured(Native())
    with pytest.raises(ValueError):
        adapter.predict(changed.series[0], changed)
    assert loads == []


def test_scope_mismatch_is_not_relabelled_as_provider_failure(history, policy):
    inputs = pinned(history, policy)
    series = inputs.series[0].model_copy(update={"warnings": ("not-the-frozen-series",)})
    adapter, _ = configured(Native())
    with pytest.raises(ValueError, match="scope"):
        adapter.predict(series, inputs)


@pytest.mark.parametrize(
    "row", [[-0.1, 2.0, 3.0], [1.0, float("nan"), 3.0], [1.0, 2.0, float("inf")], [2.0, 1.0, 3.0]]
)
def test_invalid_raw_quantiles_are_rejected_without_repair(row):
    native = Native([row] + [[1.0, 2.0, 3.0] for _ in range(6)])
    adapter, _ = configured(native)
    original = copy.deepcopy(native.rows)
    with pytest.raises(ProviderError) as exc:
        adapter.predict_values([1.0] * 7, cutoff=CUTOFF)
    assert exc.value.code == "INVALID_PROVIDER_OUTPUT"
    for old, new in zip(original[0], native.rows[0], strict=True):
        assert (math.isnan(old) and math.isnan(new)) or old == new


@pytest.mark.parametrize("rows", [[], [[1.0, 2.0, 3.0]] * 6, [[1.0, 2.0]] * 7])
def test_wrong_native_horizon_or_quantile_shape_is_rejected(rows):
    adapter, _ = configured(Native(rows))
    with pytest.raises(ProviderError) as exc:
        adapter.predict_values([1.0] * 7, cutoff=CUTOFF)
    assert exc.value.code == "INVALID_PROVIDER_OUTPUT"


def test_programming_error_escapes_instead_of_enabling_fallback():
    adapter, _ = configured(Native(error=RuntimeError("programming defect")))
    with pytest.raises(RuntimeError, match="programming defect"):
        adapter.predict_values([1.0] * 7, cutoff=CUTOFF)


def test_memory_exhaustion_is_classified():
    adapter, _ = configured(Native(error=MemoryError()))
    with pytest.raises(ProviderError) as exc:
        adapter.predict_values([1.0] * 7, cutoff=CUTOFF)
    assert exc.value.code == "PROVIDER_RESOURCE_EXHAUSTED"


def test_framework_oom_is_classified_but_other_runtime_errors_escape():
    framework_oom = type("OutOfMemoryError", (RuntimeError,), {"__module__": "torch"})
    adapter, _ = configured(Native(error=framework_oom()))
    with pytest.raises(ProviderError) as exc:
        adapter.predict_values([1.0] * 7, cutoff=CUTOFF)
    assert exc.value.code == "PROVIDER_RESOURCE_EXHAUSTED"


def test_unavailable_optional_package_is_classified(monkeypatch):
    def missing(_name):
        raise chronos2.PackageNotFoundError()

    monkeypatch.setattr(chronos2, "version", missing)
    with pytest.raises(ProviderError) as exc:
        chronos2._load_pipeline(ChronosConfig(REVISION))
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


def test_wrong_installed_package_is_rejected_without_importing_model(monkeypatch):
    monkeypatch.setattr(chronos2, "version", lambda _name: "9.9.9")
    with pytest.raises(ProviderError) as exc:
        chronos2._load_pipeline(ChronosConfig(REVISION))
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


def test_loader_is_cache_only_for_exact_revision_and_frozen_cpu_profile(monkeypatch):
    calls = {}
    torch = ModuleType("torch")
    torch.float32 = object()
    torch.OutOfMemoryError = type("OutOfMemoryError", (RuntimeError,), {})
    torch.set_num_threads = lambda n: calls.setdefault("threads", n)
    torch.get_num_interop_threads = lambda: 1
    hub = ModuleType("huggingface_hub")
    errors = ModuleType("huggingface_hub.errors")
    errors.LocalEntryNotFoundError = type("LocalEntryNotFoundError", (OSError,), {})

    def snapshot(**kwargs):
        calls["snapshot"] = kwargs
        return "/operator/cache/exact-snapshot"

    hub.snapshot_download = snapshot
    native_module = ModuleType("chronos")

    class Pipeline:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls["load"] = (path, kwargs)
            return SimpleNamespace(
                model=SimpleNamespace(eval=lambda: calls.setdefault("eval", True))
            )

    native_module.Chronos2Pipeline = Pipeline
    monkeypatch.setattr(chronos2, "version", lambda _name: PACKAGE_VERSION)
    for name, module in {
        "torch": torch,
        "chronos": native_module,
        "huggingface_hub": hub,
        "huggingface_hub.errors": errors,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    chronos2._load_pipeline(ChronosConfig(REVISION, "/operator/cache"))
    assert calls["snapshot"] == {
        "repo_id": MODEL_ID,
        "revision": REVISION,
        "cache_dir": "/operator/cache",
        "local_files_only": True,
        "allow_patterns": ["config.json", "model.safetensors"],
    }
    assert calls["load"] == (
        "/operator/cache/exact-snapshot",
        {
            "device_map": "cpu",
            "torch_dtype": torch.float32,
            "local_files_only": True,
        },
    )
    assert calls["threads"] == 2 and calls["eval"] is True
