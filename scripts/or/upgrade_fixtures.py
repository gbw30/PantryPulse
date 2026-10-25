"""Create explicit v2 fixtures; never change the retained v1 historical evidence."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.schemas.or_inputs import ORInputPackage, ORPolicy, DemandModifier  # noqa: E402
from app.services.optimization.scenario import freeze_scenario  # noqa: E402


def main():
    destination = ROOT / "data/demo/or-v2"
    destination.mkdir(exist_ok=True)
    for source in sorted((ROOT / "data/demo/or-v1").glob("*.snapshot.json")):
        old = json.loads(source.read_text())
        package = old["package"]
        package["schema_version"] = "or-input-v2"
        for row in (*package["inventory"], *package["confirmed_arrivals"]):
            row["expiry_kind"] = "DATED" if row["expires_on"] else "UNKNOWN"
        package = ORInputPackage.model_validate(package)
        snapshot = freeze_scenario(
            package, ORPolicy.model_validate(old["policy"]),
            transfer_mode=old["transfer_mode"], planning_days=old["planning_days"],
            modifiers=tuple(DemandModifier.model_validate(m) for m in old["modifiers"]),
            intent=old["intent"], expected_source_revision=package.source_revision_token,
        )
        name = source.name.replace("-v1.", "-v2.")
        for filename, data in [(name, snapshot),
                               (name.replace(".snapshot.", ".input."), package)]:
            (destination / filename).write_text(
                json.dumps(data.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    main()
