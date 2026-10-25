"""Trusted Chronos configuration and cheap worker preflight; no heavy imports.

API admission binds an approved pin even when its process has no optional model
packages. Only the supervisor's execution-capability advertisement checks local
dependencies/cache. This module neither downloads a model nor opens a database.
"""

import importlib.util
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.services.forecasting.adapters.chronos2 import (
    ADAPTER_VERSION,
    MODEL_ID,
    PACKAGE_VERSION,
    ChronosConfig,
)
from app.services.forecasting.schemas import ForecastPolicy

CHRONOS_CONTRACT = "forecast.chronos.v1"


def operator_config() -> ChronosConfig | None:
    if os.environ.get("PP_CHRONOS_ENABLED") != "1":
        return None
    revision = os.environ.get("PP_CHRONOS_REVISION", "")
    cache = os.environ.get("PP_CHRONOS_MODEL_CACHE", "")
    try:
        config = ChronosConfig(revision, cache)
        if not cache or not Path(cache).is_absolute():
            return None
        return config
    except (TypeError, ValueError):
        return None


def policy_capability(policy: ForecastPolicy) -> dict:
    return {
        "checkpoint": policy.checkpoint,
        "checkpoint_revision": policy.checkpoint_revision,
        "package_version": policy.provider_package_version,
        "adapter_version": policy.adapter_version,
    }


def bind_policy(policy: ForecastPolicy) -> ForecastPolicy | None:
    config = operator_config()
    if config is None:
        return None
    return ForecastPolicy.model_validate(
        policy.model_dump()
        | {
            "strategy": "CHRONOS2",
            "adapter_version": ADAPTER_VERSION,
            "provider_package_version": PACKAGE_VERSION,
            "checkpoint": MODEL_ID,
            "checkpoint_revision": config.revision,
        }
    )


def execution_capability() -> dict | None:
    config = operator_config()
    if config is None:
        return None
    try:
        if version("chronos-forecasting") != PACKAGE_VERSION or any(
            importlib.util.find_spec(name) is None
            for name in ("torch", "chronos", "huggingface_hub")
        ):
            return None
        snapshot = (
            Path(config.cache_dir) / "models--amazon--chronos-2" / "snapshots" / config.revision
        )
        if (
            not (snapshot / "model.safetensors").is_file()
            or (snapshot / "model.safetensors").stat().st_size == 0
        ):
            return None
        document = json.loads((snapshot / "config.json").read_text())
        if not isinstance(document, dict) or not isinstance(document.get("chronos_config"), dict):
            return None
    except (PackageNotFoundError, ImportError, OSError, ValueError):
        return None
    return {
        "checkpoint": MODEL_ID,
        "checkpoint_revision": config.revision,
        "package_version": PACKAGE_VERSION,
        "adapter_version": ADAPTER_VERSION,
    }
