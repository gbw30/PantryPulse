"""Publish an explicit isolated SIMULATED scope; no inventory ledger writes."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from app.repositories.or_repository import ORRepository
from app.schemas.or_inputs import ORInputPackage, ORScenarioPayload
from app.services.optimization.scenario import freeze_scenario
from app.services.or_runtime import ORRuntime
from scripts.or_common import write


def seed(active, organization_id, dataset_id, fixture, actor_id):
    directory = Path(__file__).resolve().parents[3] / "data/demo/or-v1"
    original = ORScenarioPayload.model_validate_json(
        (directory / f"{fixture}.snapshot.json").read_text()
    )
    data = original.package.model_dump(mode="json")
    data.update(organization_id=str(organization_id), dataset_id=str(dataset_id))
    for row in (*data["sites"], *data["forecasts"]):
        row["organization_id"] = str(organization_id)
    package = ORInputPackage.model_validate(data)
    with active.engine.begin() as connection:
        repo = ORRepository(connection)
        source = repo.put_package(package, actor_id, demo_scope=True)
        policy = repo.put_policy(organization_id, original.policy, actor_id)
        scenarios = {}
        for mode in ("HUB_ONLY", "HUB_AND_PANTRY"):
            payload = freeze_scenario(
                package,
                original.policy,
                transfer_mode=mode,
                planning_days=original.planning_days,
                modifiers=original.modifiers,
                intent="CURRENT",
                expected_source_revision=package.source_revision_token,
            )
            row = repo.put_scenario(
                payload,
                source["id"],
                policy["id"],
                actor_id,
                expected_revision=package.source_revision_token,
            )
            scenarios[mode] = str(row["id"])
    return {
        "source_kind": "SIMULATED",
        "organization_id": str(organization_id),
        "dataset_id": str(dataset_id),
        "input_package_id": str(source["id"]),
        "policy_id": str(policy["id"]),
        "scenarios": scenarios,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", type=UUID, required=True)
    parser.add_argument("--dataset-id", type=UUID, required=True)
    parser.add_argument(
        "--fixture",
        choices=[
            "six-beneficiary-v1",
            "pantry-surplus-v1",
            "harmful-donor-v1",
            "shared-capacity-v1",
            "eta-expiry-v1",
            "zero-stock-v1",
        ],
        required=True,
    )
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if os.environ.get("PP_DEMO_ORGANIZATION_ID") != str(args.organization_id) or os.environ.get(
        "PP_DEMO_DATASET_ID"
    ) != str(args.dataset_id):
        parser.error("Set PP_DEMO_ORGANIZATION_ID and PP_DEMO_DATASET_ID to this dedicated scope")
    active = ORRuntime.from_environment()
    if active is None:
        parser.error("DATABASE_URL is required")
    actor = UUID(os.environ["PP_PRESENTER_ACTOR_ID"])
    result = seed(active, args.organization_id, args.dataset_id, args.fixture, actor)
    if args.output:
        write(args.output, result)
    else:
        print(json.dumps(result, indent=2))
    active.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
