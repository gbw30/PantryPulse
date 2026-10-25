"""Build an explicitly simulated VP-v2 fixture from retained OR branch source inputs."""

import json
from pathlib import Path

from app.schemas.or_inputs import DemandModifier, ORInputPackage, ORPolicy
from app.services.optimization.scenario import freeze_scenario

ROOT = Path(__file__).resolve().parents[3] / "data/demo/or-v2"


def fixture(organization_id=None, mode="HUB_ONLY"):
    package = json.loads((ROOT / "six-beneficiary-v2.input.json").read_text(encoding="utf-8-sig"))
    original = json.loads(
        (ROOT / "six-beneficiary-v2.snapshot.json").read_text(encoding="utf-8-sig")
    )
    for lot in (*package["inventory"], *package["confirmed_arrivals"]):
        lot["expiry_kind"] = "UNKNOWN" if lot["expires_on"] is None else "DATED"
    if organization_id is not None:
        package["organization_id"] = str(organization_id)
        for row in (*package["sites"], *package["forecasts"]):
            row["organization_id"] = str(organization_id)
    inputs = ORInputPackage.model_validate(package)
    policy = ORPolicy.model_validate(original["policy"])
    scenario = freeze_scenario(
        inputs,
        policy,
        transfer_mode=mode,
        planning_days=2,
        modifiers=tuple(DemandModifier.model_validate(row) for row in original["modifiers"]),
        intent="CURRENT",
        expected_source_revision=inputs.source_revision_token,
    )
    return inputs, policy, scenario
