"""One typed offline OR computation. Input/output only; no jobs or publication."""

import json
import sys


def main():
    from app.schemas.or_inputs import ORScenarioPayload
    from app.services.optimization.scenario import verify_scenario
    from app.services.optimization.service import solve_one

    request = json.loads(sys.stdin.buffer.read(4 * 1024**2 + 1))
    if set(request) != {"scenario", "method", "settings"}:
        raise ValueError("INVALID_OFFLINE_REQUEST")
    scenario = ORScenarioPayload.model_validate(request["scenario"])
    verify_scenario(scenario)
    result = solve_one(scenario, request["method"], request["settings"])
    print(json.dumps(result.model_dump(mode="json"), allow_nan=False))


if __name__ == "__main__":
    main()
