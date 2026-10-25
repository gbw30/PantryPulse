"""Qualification inputs reach declared bounds without bypassing strict contracts."""

import importlib.util
from pathlib import Path

import pytest

from app.schemas.or_inputs import ORInputPackage
from app.services.optimization.scenario import verify_scenario

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("or_qualification", ROOT / "scripts/or/qualify.py")
qualification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualification)


@pytest.mark.parametrize("numeric", [False, True])
def test_upper_scope_inputs_cover_all_size_limits_and_replay_deterministically(numeric):
    scenario = qualification.upper_scope(numeric=numeric)
    package = scenario.package
    assert package.source_kind == "SIMULATED"
    assert sum(s.role == "BENEFICIARY" for s in package.sites) == 12
    assert sum(s.role == "HUB" for s in package.sites) == 2
    assert len(package.products) == 2
    assert len(package.inventory) == 228 and len(package.confirmed_arrivals) == 28
    assert len(package.routes) == 182
    sites = {s.id for s in package.sites}
    assert {(r.source_id, r.destination_id) for r in package.routes} == {
        (a, b) for a in sites for b in sites if a != b
    }
    assert {r.eta_days for r in package.routes} == {0, 1, 2}
    assert all(len(f.days) == 7 for f in package.forecasts)
    assert scenario.planning_days == 3
    verify_scenario(scenario)
    assert scenario.operational_hash == qualification.upper_scope(numeric=numeric).operational_hash
    if numeric:
        assert max(lot.free_units for lot in package.inventory) == 100000
        assert max(c.cost_minor for r in package.routes for c in r.costs) == 1000000
        assert max(sum(d.units for d in s.days[:3]) for s in scenario.demand) == 100000
    raw = package.model_dump()
    raw["inventory"] = (*raw["inventory"], raw["inventory"][0])
    with pytest.raises(ValueError, match="SCOPE_UNSUPPORTED"):
        ORInputPackage.model_validate(raw)


def test_mode_is_explicit_and_sensitivity_cannot_overwrite_primary_policy():
    hub = qualification.upper_scope()
    pantry = qualification.upper_scope(mode="HUB_AND_PANTRY")
    assert hub.package == pantry.package and hub.policy == pantry.policy
    assert hub.operational_hash != pantry.operational_hash
    original = qualification.fixture()
    before = original.model_dump_json()
    cases = dict(qualification.sensitivity_cases())
    assert len(cases) == 19
    assert original.model_dump_json() == before and original.policy.purpose == "PRIMARY"
    assert all(s.policy.purpose == "ABLATION" for n, s in cases.items() if not n.endswith("-full"))
    assert cases["no-research-terms"].policy.lambda_percent == 0
    assert cases["no-research-terms"].policy.gamma_ap_percent == 0
    assert cases["no-research-terms"].policy.gamma_rp_percent == 0
    assert len({s.policy_hash for n, s in cases.items() if not n.endswith("-full")}) == 17
    assert cases["ap-ablation-v1-full"].policy_hash == cases["rp-ablation-v1-full"].policy_hash
    assert (
        cases["ap-ablation-v1-full"].operational_hash
        != cases["rp-ablation-v1-full"].operational_hash
    )


def test_pruned_upper_model_preserves_zero_transfers_and_dated_service():
    from ortools.sat.python import cp_model

    from app.schemas.or_outputs import Candidate, RouteQuantity
    from app.services.optimization.candidates import prepare_problem
    from app.services.optimization.constraints import build_physical_model
    from app.services.optimization.extract import read_candidate
    from app.services.optimization.verify import verify

    problem = prepare_problem(qualification.upper_scope(mode="HUB_AND_PANTRY"))
    assert any(c.upper == 0 and c.lot_ids for c in problem.candidates)
    physical = build_physical_model(problem)
    for variable in physical.y.values():
        physical.model.add(variable == 0)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = 5
    status = solver.status_name(solver.solve(physical.model))
    assert status == "OPTIMAL"
    candidate = read_candidate(status, solver, physical)
    assert not candidate.assignments
    expected = Candidate(
        route_quantities=tuple(
            RouteQuantity(route_id=c.route_id, product_id=c.product_id, units=0)
            for c in problem.candidates
        ),
        assignments=(),
    )
    assert candidate == expected
    checked = verify(problem, candidate)
    assert checked.passed and checked.projection == problem.baseline
    for series in problem.scenario.demand:
        key = series.site_id, series.product_id
        rows = [d for d in problem.baseline.days if (d.site_id, d.product_id) == key]
        assert [solver.value(x) for x in physical.served[key]] == [d.served for d in rows]
        assert [solver.value(x) for x in physical.ends[key]] == [d.on_hand for d in rows]
        assert [solver.value(x) for x in physical.expired[key]] == [d.expired for d in rows]


def test_coefficient_sensitivity_has_distinct_attributes_and_source_identity():
    cases = dict(qualification.sensitivity_cases())
    mixed = cases["mixed-attributes-50"]
    assert (
        mixed.package.source_manifest_hash != qualification.fixture().package.source_manifest_hash
    )
    assert (
        mixed.package
        == cases["mixed-attributes-need"].package
        == cases["mixed-attributes-access"].package
    )
    assert any(
        row.scores[0].score_bp != row.scores[1].score_bp
        for row in mixed.package.vulnerability_attributes
    )
    assert all(
        sum(s.score_bp for s in row.scores) == 10000
        for row in mixed.package.vulnerability_attributes
    )
