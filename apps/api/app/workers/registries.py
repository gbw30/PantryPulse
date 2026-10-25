"""Fixed table of named registries. Configuration selects a name; payloads never do."""

import importlib

from app.services.jobs.registry import Registry

_REGISTRIES = {
    "production": ("app.workers.production", "REGISTRY"),
    "test": ("app.workers.testing", "REGISTRY"),
}


def load_registry(name: str) -> Registry:
    if name not in _REGISTRIES:
        raise ValueError(f"unknown registry {name!r}; expected one of {sorted(_REGISTRIES)}")
    target = _REGISTRIES[name]
    if target is None:
        return Registry([])
    module, attribute = target
    return getattr(importlib.import_module(module), attribute)
