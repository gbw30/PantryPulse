"""Validate packages/contracts/examples/v1: exactly one valid example per v1 response model.

w1-web builds its Playwright mocks only from these files, so an example that drifts from the
Pydantic model fails here (and in `npm run contracts:check`). No database or credentials needed.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.routing import APIRoute  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.routers import v1_decisions, v1_imports, v1_networks, v1_settings  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[3] / "packages/contracts/examples/v1"


def v1_response_models():
    models = {}
    for module in (v1_decisions, v1_imports, v1_networks, v1_settings):
        for route in module.router.routes:
            if isinstance(route, APIRoute) and route.response_model is not None:
                models[route.response_model.__name__] = route.response_model
    return models


def main() -> int:
    models = v1_response_models()
    files = {p.stem: p for p in EXAMPLES.glob("*.json")}
    problems = [f"missing example: {name}.json" for name in sorted(models.keys() - files.keys())]
    problems += [
        f"example has no v1 response model: {name}.json"
        for name in sorted(files.keys() - models.keys())
    ]
    for name in sorted(models.keys() & files.keys()):
        try:
            models[name].model_validate(json.loads(files[name].read_text()))
        except (ValidationError, json.JSONDecodeError) as error:
            problems.append(f"{name}.json: {error}")
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"{len(models)} v1 examples valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
