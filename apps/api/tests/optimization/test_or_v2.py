"""Approved runtime/expiry policy, independently specified from implementation."""

from datetime import date

import pytest

from app.services.optimization.kernel import KernelLot, project_kernel
from app.services.optimization.settings import execution_limits, solver_settings


def test_approved_default_and_maximum_budgets():
    assert solver_settings()["search_milliseconds"] == 120_000
    assert execution_limits(solver_settings()) == (150, 330)
    assert execution_limits(solver_settings(300)) == (330, 690)
    for invalid in (True, 0, -1, 301, 1.5):
        with pytest.raises(ValueError):
            solver_settings(invalid)


def test_expiry_day_is_usable_but_following_day_is_not():
    first, following = date(2026, 10, 25), date(2026, 10, 26)
    days, _ = project_kernel(
        ((first, 3), (following, 3)), (KernelLot("dated", 5, first, first, False),)
    )
    assert [(d.served, d.expired, d.unmet) for d in days] == [(3, 0, 0), (0, 2, 3)]


def test_declared_nonexpiring_lot_follows_dated_fefo():
    day = date(2026, 10, 25)
    days, lots = project_kernel(
        ((day, 4),),
        (KernelLot("permanent", 5, day, None, False), KernelLot("dated", 3, day, day, False)),
    )
    assert days[0].served == 4
    assert {lot.lot.id: lot.consumed for lot in lots} == {"dated": (3,), "permanent": (1,)}


@pytest.mark.parametrize("expiry_kind", ["DATED", "NON_EXPIRING", "UNKNOWN"])
def test_expiry_contract_reaches_candidates_native_model_and_independent_replay(expiry_kind):
    from pathlib import Path

    from app.schemas.or_inputs import ORScenarioPayload
    from app.services.optimization.scenario import freeze_scenario
    from app.services.optimization.service import solve_one

    root = Path(__file__).resolve().parents[4]
    source = ORScenarioPayload.model_validate_json(
        (root / "data/demo/or-v2/ap-ablation-v2.snapshot.json").read_text()
    )
    package = source.package.model_copy(
        update={
            "inventory": tuple(
                lot.model_copy(
                    update={
                        "expiry_kind": expiry_kind,
                        "expires_on": source.package.first_planning_date
                        if expiry_kind == "DATED"
                        else None,
                    }
                )
                for lot in source.package.inventory
            )
        }
    )
    scenario = freeze_scenario(
        package,
        source.policy,
        transfer_mode=source.transfer_mode,
        planning_days=source.planning_days,
        modifiers=source.modifiers,
        intent="CURRENT",
        expected_source_revision=package.source_revision_token,
    )
    result = solve_one(scenario, "CLASSICAL_GP", solver_settings(1))
    assert result.outcome == "VERIFIED"
    assert result.verification.passed
    if expiry_kind == "UNKNOWN":
        assert result.candidate.assignments == ()
        assert result.verification.projection.exclusions
    else:
        assert sum(a.units for a in result.candidate.assignments) > 0


def test_v1_evidence_is_never_reinterpreted_as_v2():
    from pathlib import Path

    from app.schemas.or_inputs import ORScenarioPayload

    root = Path(__file__).resolve().parents[4]
    with pytest.raises(ValueError):
        ORScenarioPayload.model_validate_json(
            (root / "data/demo/or-v1/ap-ablation-v1.snapshot.json").read_text()
        )


def test_offline_exhausted_parent_budget_never_starts_another_child(monkeypatch):
    import json
    from pathlib import Path

    from app.schemas.or_inputs import ORScenarioPayload
    from app.services.optimization import offline

    scenario = ORScenarioPayload.model_validate(
        json.loads(
            (
                Path(__file__).resolve().parents[4] / "data/demo/or-v2/ap-ablation-v2.snapshot.json"
            ).read_text()
        )
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Child launched after exhausted budget")

    monkeypatch.setattr(offline, "run_child", forbidden)
    results = offline.bounded_methods(scenario, ("CLASSICAL_GP", "EGP_PI_INSPIRED"), deadline=0)
    assert all(
        row.outcome == "TIMED_OUT" and row.error_code == "DEADLINE_EXCEEDED" for row in results
    )
