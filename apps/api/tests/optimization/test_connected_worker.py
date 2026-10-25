"""Frozen comparison settings and independent partial publication contracts."""

import json
from pathlib import Path

import pytest

from app.services.jobs.contracts import PRODUCTION_PROFILE, StepOutcome, StepStatus
from app.services.jobs.registry import InputRejected
from app.services.optimization.settings import solver_settings
from app.workers.optimization import REGISTRATION


def payload(seconds=120):
    path = Path(__file__).resolve().parents[4] / "data/demo/or-v2/ap-ablation-v2.snapshot.json"
    return {
        "scenario_id": "00000000-0000-0000-0000-000000000099",
        "scenario": json.loads(path.read_text()),
        "settings": solver_settings(seconds),
    }


def test_frozen_allowance_and_equal_sequential_methods():
    data = REGISTRATION.handler.validate_input(payload())
    assert REGISTRATION.execution_budget(data, PRODUCTION_PROFILE) == 330
    steps = REGISTRATION.handler.steps(data, PRODUCTION_PROFILE)
    assert [s.name for s in steps] == ["CLASSICAL_GP", "EGP_PI_INSPIRED"]
    assert [s.max_s for s in steps] == [150, 150]
    from app.services.jobs.policies import plan_step_window

    window = plan_step_window(steps[1], elapsed_s=151, budget_s=330, profile=PRODUCTION_PROFILE)
    assert window.hard_stop_s == 300  # thirty seconds reserved for verified publication
    maximum = REGISTRATION.handler.validate_input(payload(300))
    assert REGISTRATION.execution_budget(maximum, PRODUCTION_PROFILE) == 690
    assert maximum != data


def test_budget_tampering_and_unknown_payload_rejected():
    data = payload()
    data["settings"]["comparison_wall_milliseconds"] = 30_000
    with pytest.raises(InputRejected):
        REGISTRATION.handler.validate_input(data)
    with pytest.raises(InputRejected):
        REGISTRATION.handler.validate_input({**payload(), "committed": True})


def test_valid_partner_retained_on_process_failure():
    from app.schemas.or_inputs import ORScenarioPayload
    from app.services.optimization.service import solve_one

    data = REGISTRATION.handler.validate_input(payload(1))
    outcome = solve_one(
        ORScenarioPayload.model_validate(data["scenario"]), "CLASSICAL_GP", data["settings"]
    )
    saved = REGISTRATION.publisher.validate(
        data,
        (
            StepOutcome(
                "CLASSICAL_GP", StepStatus.COMPLETED, {"method": outcome.model_dump(mode="json")}
            ),
            StepOutcome(
                "EGP_PI_INSPIRED", StepStatus.TIMED_OUT, error_code="STEP_DEADLINE_EXCEEDED"
            ),
        ),
    )
    assert saved["comparison"]["outcome"] == "PARTIAL"
    assert saved["comparison"]["methods"][0]["verification"]["passed"]
    assert saved["comparison"]["methods"][1]["candidate"] is None


def test_invalid_partner_does_not_discard_independently_valid_method():
    from app.schemas.or_inputs import ORScenarioPayload
    from app.services.optimization.service import solve_one

    data = REGISTRATION.handler.validate_input(payload(1))
    scenario = ORScenarioPayload.model_validate(data["scenario"])
    first = solve_one(scenario, "CLASSICAL_GP", data["settings"]).model_dump(mode="json")
    second = solve_one(scenario, "EGP_PI_INSPIRED", data["settings"]).model_dump(mode="json")
    second["settings_hash"] = "0" * 64
    result = REGISTRATION.publisher.validate(
        data,
        (
            StepOutcome("CLASSICAL_GP", StepStatus.COMPLETED, {"method": first}),
            StepOutcome("EGP_PI_INSPIRED", StepStatus.COMPLETED, {"method": second}),
        ),
    )["comparison"]
    assert result["outcome"] == "PARTIAL"
    assert result["methods"][0]["outcome"] == "VERIFIED"
    assert result["methods"][1]["error_code"] == "METHOD_VERIFICATION_FAILED"
