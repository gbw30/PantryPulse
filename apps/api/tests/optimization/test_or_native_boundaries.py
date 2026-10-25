"""Native strict-boundary and ablation checks with independent literal expectations."""

from fractions import Fraction
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from app.schemas.or_inputs import ORInputPackage, ORScenarioPayload
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import operational_hash
from app.services.optimization.constraints import build_physical_model
from app.services.optimization.egp_pi_inspired import attach_research
from app.services.optimization.numerics import audit_model
from app.services.optimization.scenario import freeze_scenario
from app.services.optimization.service import solve_one

DATA = Path(__file__).resolve().parents[4] / "data/demo/or-v2"


def snapshot(name):
    return ORScenarioPayload.model_validate_json((DATA / f"{name}.snapshot.json").read_text())


def refreeze(original, *, package=None, policy=None):
    package = package or original.package
    return freeze_scenario(
        package,
        policy or original.policy,
        transfer_mode=original.transfer_mode,
        planning_days=original.planning_days,
        modifiers=original.modifiers,
        intent=original.intent,
        expected_source_revision=package.source_revision_token,
    )


def changed_simulated_package(original, raw, revision):
    """Fingerprint the actual independently constructed synthetic source content."""
    assert raw["source_kind"] == "SIMULATED"
    raw["source_revision_token"] = revision
    content = {k: v for k, v in raw.items() if k not in {"source_refs", "source_manifest_hash"}}
    raw["source_refs"] = tuple(
        ref.model_copy(update={"revision": revision, "content_hash": operational_hash(content)})
        for ref in original.package.source_refs
    )
    raw["source_manifest_hash"] = operational_hash(raw["source_refs"])
    return ORInputPackage.model_validate(raw)


def beneficiaries(scenario):
    return sorted((s.id for s in scenario.package.sites if s.role == "BENEFICIARY"), key=str)


def native_solver():
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 2
    return solver


@pytest.mark.parametrize(
    "kind,fixture,score,first_units,expected_q,expected_flag",
    [
        pytest.param("ap", "ap-ablation-v2", 5000, 1, 7500, False, id="ap-equality"),
        pytest.param("ap", "ap-ablation-v2", 5002, 1, 7501, True, id="ap-one-quantum-above"),
        pytest.param("rp", "rp-ablation-v2", 5000, 0, 15000, False, id="rp-equality"),
        pytest.param("rp", "rp-ablation-v2", 5001, 0, 15001, True, id="rp-one-quantum-above"),
    ],
)
@pytest.mark.parametrize("forced_flag", [False, True], ids=["force-false", "force-true"])
def test_native_poverty_flags_reify_both_sides_of_strict_boundary(
    kind, fixture, score, first_units, expected_q, expected_flag, forced_flag
):
    # OR-DEC-006/007/018 [PROVISIONAL]: equality is false; one integer quantum above is true.
    original = snapshot(fixture)
    first = beneficiaries(original)[0]
    raw = original.package.model_dump()
    for row in raw["vulnerability_attributes"]:
        if row["site_id"] == first:
            for attribute in row["scores"]:
                attribute.update(score_bp=score, raw_note=f"SIMULATED boundary score {score}/10000")
    package = changed_simulated_package(original, raw, f"native-boundary-{kind}-{score}")
    scenario = refreeze(original, package=package)
    problem = prepare_problem(scenario)
    physical = build_physical_model(problem)
    handles = attach_research(physical)
    for candidate in problem.candidates:
        units = first_units if candidate.destination_id == first else 1 - first_units
        physical.model.add(physical.y[candidate.route_id, candidate.product_id] == units)
    first_key = next(key for key in handles.auxiliaries[kind] if key[0] == first)
    flag = handles.auxiliaries[kind][first_key]
    physical.model.add(flag == int(forced_flag))
    audit_model(physical.model)
    solver = native_solver()
    status = solver.status_name(solver.solve(physical.model))
    assert status == ("OPTIMAL" if forced_flag == expected_flag else "INFEASIBLE")
    if status == "OPTIMAL":
        assert solver.value(handles.auxiliaries["q"][first_key]) == expected_q
        assert bool(solver.value(flag)) is expected_flag
        if kind == "rp":
            # Literal current-group values: 2*15000-(15000+10000)=5000 at equality;
            # changing only the first q to15001 gives5001, strictly above2*T=5000.
            peers = [value for key, value in handles.auxiliaries["q"].items() if key != first_key]
            assert len(peers) == 1 and solver.value(peers[0]) == 10000
            assert 2 * expected_q - (expected_q + 10000) == (5001 if expected_flag else 5000)


@pytest.mark.parametrize(
    "fixture,gamma_field,full_vector,full_score,ablated_vector,ablated_score",
    [
        ("ap-ablation-v2", "gamma_ap_percent", (1, 0), Fraction(19, 8), (0, 1), Fraction(2)),
        ("rp-ablation-v2", "gamma_rp_percent", (0, 1), Fraction(11, 4), (1, 0), Fraction(21, 8)),
    ],
)
def test_native_diagnostic_ablations_change_the_actual_research_allocation(
    fixture, gamma_field, full_vector, full_score, ablated_vector, ablated_score
):
    # OR-DEC-006/019 [PROVISIONAL]: diagnostic gamma0 policy is explicitly ABLATION.
    original = snapshot(fixture)
    policy = original.policy.model_copy(
        update={
            "purpose": "ABLATION",
            "version": f"native-{fixture}-gamma0",
            gamma_field: 0,
        }
    )
    ablated = refreeze(original, policy=policy)
    full = solve_one(original, "EGP_PI_INSPIRED")
    removed = solve_one(ablated, "EGP_PI_INSPIRED")
    assert ablated.policy.purpose == "ABLATION" and original.policy.purpose == "PRIMARY"
    for outcome, vector, objective in (
        (full, full_vector, full_score),
        (removed, ablated_vector, ablated_score),
    ):
        assert outcome.outcome == "VERIFIED" and outcome.native_status == "OPTIMAL"
        assert outcome.method.value == "EGP_PI_INSPIRED"
        goals = sorted(outcome.verification.metrics.goals, key=lambda g: str(g.site_id))
        assert tuple(goal.fulfilled for goal in goals) == vector
        assert outcome.objective.fraction() == objective
    assert full.physical_fingerprint == removed.physical_fingerprint
    assert full.operational_hash != removed.operational_hash


def test_independent_one_unit_case_has_unique_research_optimum_over_full_feasible_set():
    # OR-DEC-006/019 [PROVISIONAL]: independently hand-derived r=(1,1),v=(2,1),supply1.
    # With beta=.5, AP/RP thresholds .75/.25 and caps .25:
    # f=(0,0): 2.5+.75+.25=3.5; f=(1,0): 1+.25+.25=1.5;
    # f=(0,1): 2+.25+.25=2.5. f=(1,1) exceeds original stock.
    original = snapshot("ap-ablation-v2")
    first, second = beneficiaries(original)
    raw = original.package.model_dump()
    for series in raw["forecasts"]:
        if series["site_id"] in {first, second}:
            series["days"][0]["central_literal"] = "1"
    for row in raw["vulnerability_attributes"]:
        score = 10000 if row["site_id"] == first else 0
        for attribute in row["scores"]:
            attribute.update(score_bp=score, raw_note=f"SIMULATED independent score {score}/10000")
    scenario = refreeze(
        original, package=changed_simulated_package(original, raw, "native-independent-one-unit-v1")
    )
    assert scenario.policy.epsilon_cost_bp == scenario.policy.epsilon_waste_bp == 0
    expected = {(0, 0): Fraction(7, 2), (1, 0): Fraction(3, 2), (0, 1): Fraction(5, 2)}
    actual = {}
    problem = prepare_problem(scenario)
    assert len(problem.candidates) == 2
    for vector in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        physical = build_physical_model(problem)
        handles = attach_research(physical)
        for candidate in problem.candidates:
            units = vector[0] if candidate.destination_id == first else vector[1]
            physical.model.add(physical.y[candidate.route_id, candidate.product_id] == units)
        audit_model(physical.model)
        solver = native_solver()
        status = solver.status_name(solver.solve(physical.model))
        if vector not in expected:
            assert status == "INFEASIBLE"
            continue
        assert status == "OPTIMAL"
        integer = sum(
            c * solver.value(v) for c, v in zip(handles.coefficients, handles.terms, strict=True)
        )
        actual[vector] = integer * handles.scale
        assert actual[vector] == expected[vector]
    optimum = min(actual.values())
    assert [vector for vector, objective in actual.items() if objective == optimum] == [(1, 0)]
    result = solve_one(scenario, "EGP_PI_INSPIRED")
    assert result.outcome == "VERIFIED" and result.native_status == "OPTIMAL"
    assert result.objective.fraction() == Fraction(3, 2)
    goals = sorted(result.verification.metrics.goals, key=lambda g: str(g.site_id))
    assert tuple(goal.fulfilled for goal in goals) == (1, 0)
