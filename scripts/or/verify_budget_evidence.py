"""Replay every recorded budget-sweep pair without invoking native search."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.schemas.or_inputs import ORScenarioPayload
from app.schemas.or_outputs import MethodOutcome
from app.services.optimization.canonical import operational_hash
from app.services.optimization.compare import assemble
from app.services.optimization.settings import solver_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text())
    assert data["schema_version"] == "or-budget-benchmark-v2" and data["completed_at"]
    assert len(data["runs"]) == 20
    for mode in ("HUB_ONLY", "HUB_AND_PANTRY"):
        scenario = ORScenarioPayload.model_validate(data["scenarios"][mode])
        for seconds in (15, 30, 60, 120, 300):
            settings = solver_settings(seconds)
            rows = [row for row in data["runs"] if row["mode"] == mode and row["settings"] == settings]
            assert [r["method"] for r in rows] == ["CLASSICAL_GP", "EGP_PI_INSPIRED"]
            for row in rows:
                assert row["process_returncode"] == 0 and row["process_reason"] is None
                assert row["operational_hash"] == scenario.operational_hash
                assert row["settings_hash"] == operational_hash(settings)
                assert row["peak_rss_kib"] > 0
            result = assemble(scenario, [MethodOutcome.model_validate(r["method_result"]) for r in rows], expected_settings=settings)
            assert result.outcome == "SUCCEEDED"
    print("PASS: all 20 outcomes independently replayed with exact input/settings identities.")


if __name__ == "__main__":
    main()
