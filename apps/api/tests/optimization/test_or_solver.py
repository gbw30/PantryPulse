"""Native model evidence, separate from the stdlib enumeration oracle."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from app.schemas.or_inputs import ORScenarioPayload
from app.services.optimization.service import solve_one

FIXTURES = Path(__file__).resolve().parents[4] / "data/demo/or-v1"


@pytest.mark.parametrize("mode", ["HUB_ONLY", "HUB_AND_PANTRY"])
@pytest.mark.parametrize(
    "method,expected,score",
    [
        ("CLASSICAL_GP", (1, 1, 1, 1, 1, 1), Fraction(163, 50)),
        ("EGP_PI_INSPIRED", (2, 2, 1, 1, 0, 0), Fraction(1393, 300)),
    ],
)
def test_six_unique_optima_native(mode, method, expected, score):
    # OR-DEC-006/008/019 [PROVISIONAL]: independent exact expectations, both modes.
    # OR-DEC-008 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    from app.services.optimization.scenario import freeze_scenario

    original = ORScenarioPayload.model_validate_json(
        (FIXTURES / "six-beneficiary-v1.snapshot.json").read_text()
    )
    scenario = freeze_scenario(
        original.package,
        original.policy,
        transfer_mode=mode,
        planning_days=3,
        modifiers=original.modifiers,
        intent=original.intent,
        expected_source_revision=original.package.source_revision_token,
    )
    result = solve_one(scenario, method)
    assert result.outcome == "VERIFIED", result.model_dump()
    assert result.native_status == "OPTIMAL"
    assert result.objective.fraction() == score
    for product in scenario.package.products:
        goals = sorted(
            (g for g in result.verification.metrics.goals if g.product_id == product.id),
            key=lambda g: str(g.site_id),
        )
        assert tuple(g.fulfilled for g in goals) == expected


@pytest.mark.parametrize(
    "fixture,vector,score",
    [
        ("ap-ablation-v1", (1, 0), Fraction(19, 8)),
        ("rp-ablation-v1", (0, 1), Fraction(11, 4)),
    ],
)
def test_native_active_poverty_terms(fixture, vector, score):
    scenario = ORScenarioPayload.model_validate_json(
        (FIXTURES / f"{fixture}.snapshot.json").read_text()
    )
    result = solve_one(scenario, "EGP_PI_INSPIRED")
    assert result.outcome == "VERIFIED", result.model_dump()
    assert result.objective.fraction() == score
    goals = sorted(result.verification.metrics.goals, key=lambda g: str(g.site_id))
    assert tuple(g.fulfilled for g in goals) == vector


def test_both_physical_fingerprints_identical():
    # OR-DEC-013 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    from app.services.optimization.compare import compare

    scenario = ORScenarioPayload.model_validate(
        json.loads((FIXTURES / "six-beneficiary-v1.snapshot.json").read_text())
    )
    result = compare(scenario)
    assert result.outcome == "SUCCEEDED"
    assert len({m.physical_fingerprint for m in result.methods}) == 1
    assert len({m.settings_hash for m in result.methods}) == 1
