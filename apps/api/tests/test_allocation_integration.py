from datetime import date

import pytest

from app.schemas.or_inputs import ORInputPackage
from app.services.inventory.or_kernel import KernelLot, project_kernel
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.scenario import freeze_scenario
from scripts.allocation_fixture import fixture


def test_kernel_expiry_is_inclusive_and_non_expiring_is_explicit():
    day = date(2026, 10, 25)
    days, _ = project_kernel(((day, 2),), (KernelLot("dated", 2, day, day, False),))
    assert days[0].served == 2 and days[0].expired == 0
    next_day = date(2026, 10, 26)
    days, _ = project_kernel(((next_day, 2),), (KernelLot("dated", 2, day, day, False),))
    assert days[0].served == 0 and days[0].expired == 2


@pytest.mark.parametrize("mode", ["HUB_ONLY", "HUB_AND_PANTRY"])
@pytest.mark.parametrize("method", ["CLASSICAL_GP", "EGP_PI_INSPIRED"])
def test_real_native_solver_and_verifier_for_both_modes_and_methods(mode, method):
    from app.services.optimization.service import solve_one

    _, _, scenario = fixture(mode=mode)
    outcome = solve_one(scenario, method)
    assert outcome.outcome == "VERIFIED", outcome.model_dump()
    assert outcome.native_status in {"OPTIMAL", "FEASIBLE"}
    assert outcome.verification.passed
    assert outcome.transfer_mode == mode
    assert outcome.operational_hash == scenario.operational_hash
    if mode == "HUB_ONLY":
        hubs = {site.id for site in scenario.package.sites if site.role == "HUB"}
        assert all(row.source_id in hubs for row in outcome.candidate.assignments)


def test_non_expiring_lots_are_usable_unknown_expiry_is_not():
    package, policy, original = fixture()
    value = package.model_dump(mode="python")
    for lot in value["inventory"]:
        lot.update(expiry_kind="NON_EXPIRING", expires_on=None)
    package = ORInputPackage.model_validate(value)
    scenario = freeze_scenario(
        package,
        policy,
        transfer_mode="HUB_ONLY",
        planning_days=2,
        modifiers=original.modifiers,
        intent="CURRENT",
        expected_source_revision=package.source_revision_token,
    )
    assert any(candidate.upper > 0 for candidate in prepare_problem(scenario).candidates)
    for lot in value["inventory"]:
        lot["expiry_kind"] = "UNKNOWN"
    package = ORInputPackage.model_validate(value)
    scenario = freeze_scenario(
        package,
        policy,
        transfer_mode="HUB_ONLY",
        planning_days=2,
        modifiers=original.modifiers,
        intent="CURRENT",
        expected_source_revision=package.source_revision_token,
    )
    assert all(candidate.upper == 0 for candidate in prepare_problem(scenario).candidates)
