"""Independent forced-vector CP feasibility versus replay, beyond objective optima."""

from itertools import product
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from app.schemas.or_inputs import ORScenarioPayload
from app.schemas.or_outputs import Candidate, RouteQuantity
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.constraints import build_physical_model
from app.services.optimization.packing import pack
from app.services.optimization.service import solve_one
from app.services.optimization.verify import verify

FIXTURES = Path(__file__).resolve().parents[4] / "data/demo/or-v1"


@pytest.mark.parametrize("fixture", ["ap-ablation-v1", "rp-ablation-v1", "eta-expiry-v1"])
def test_every_tiny_vector_has_identical_cp_and_replay_feasibility(fixture):
    # OR-DEC-004 [PROVISIONAL]: hard loading + service selects exactly one trajectory per y.
    s = ORScenarioPayload.model_validate_json((FIXTURES / f"{fixture}.snapshot.json").read_text())
    p = prepare_problem(s)
    for vector in product(*(range(c.upper + 1) for c in p.candidates)):
        quantities = tuple(
            RouteQuantity(route_id=c.route_id, product_id=c.product_id, units=n)
            for c, n in zip(p.candidates, vector, strict=True)
        )
        try:
            feasible = verify(
                p, Candidate(route_quantities=quantities, assignments=pack(p, quantities))
            ).passed
        except ValueError:
            feasible = False
        physical = build_physical_model(p)
        for c, n in zip(p.candidates, vector, strict=True):
            physical.model.add(physical.y[c.route_id, c.product_id] == n)
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        status = solver.solve(physical.model)
        assert (status in [cp_model.OPTIMAL, cp_model.FEASIBLE]) == feasible, vector


@pytest.mark.parametrize(
    "fixture",
    [
        "pantry-surplus-v1",
        "harmful-donor-v1",
        "shared-capacity-v1",
        "zero-stock-v1",
        "eta-expiry-v1",
    ],
)
@pytest.mark.parametrize("method", ["CLASSICAL_GP", "EGP_PI_INSPIRED"])
def test_actual_methods_on_donor_capacity_empty_and_expiry_inputs(fixture, method):
    # OR-DEC-003/017 [PROVISIONAL]: no-inbound protection and shared engineering capacities.
    s = ORScenarioPayload.model_validate_json((FIXTURES / f"{fixture}.snapshot.json").read_text())
    result = solve_one(s, method)
    assert result.outcome == "VERIFIED", result.error_code
    assert result.native_status == "OPTIMAL"
    assert result.verification.passed
