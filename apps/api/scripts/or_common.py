"""Common CLI I/O only; all calculations belong to shared application modules."""

import json
from pathlib import Path

from pydantic import BaseModel

from app.schemas.or_inputs import ORScenarioPayload
from app.services.optimization.scenario import verify_scenario


def snapshot(path):
    value = ORScenarioPayload.model_validate_json(Path(path).read_text())
    verify_scenario(value)
    return value


def write(path, value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
