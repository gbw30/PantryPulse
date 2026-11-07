"""RETAIL_OPTIMIZED: minimize w_exp × expired + w_lost × lost sales over seven days, per product.

Units and USD share the model: per product the USD objective is unit_value_usd × the units
objective, so only the capacity split differs between measures (CR-w1-solver-2, decompose.py).
Declared tie-break: among plans with the same objective, move fewer units. The primary term is
scaled by K = (sum of route upper bounds) + 1, so the tie-break never changes the objective.
"""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.services.optimization.numerics import audit_model
from app.services.optimization.product_model import build_product_model
from app.services.optimization.v3 import RouteKey

SEED = 0
WORKERS = 1  # repeatability per product (cpsat-patterns); parallelism is across products


@dataclass(frozen=True)
class ProductOutcome:
    product_id: str
    native_status: str
    quantities: dict[RouteKey, int]  # empty unless OPTIMAL/FEASIBLE
    primary: int | None  # native primary objective (units), replayed by the verifier
    gap: str | None  # relative gap on the primary objective, FEASIBLE only


def solve(pm, primary, search_seconds: float, product_id: str) -> ProductOutcome:
    """Solve primary × K + moved units; keep the native status, never relabel FEASIBLE."""
    m = pm.model
    moved = [v for v in pm.y.values() if not isinstance(v, int)]
    k = sum(pm.upper.values()) + 1
    m.minimize(k * primary + sum(moved))
    audit_model(m)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = WORKERS
    solver.parameters.random_seed = SEED
    solver.parameters.max_time_in_seconds = search_seconds
    status = solver.status_name(solver.solve(m))
    if status not in ("OPTIMAL", "FEASIBLE"):
        return ProductOutcome(product_id, status, {}, None, None)
    quantities = {key: int(solver.value(v)) for key, v in pm.y.items() if not isinstance(v, int)}
    value = int(solver.value(primary))
    gap = None
    if status == "FEASIBLE":
        bound = solver.best_objective_bound / k
        gap = f"{max(0.0, (value - bound) / max(1, abs(value))):.6f}"
    return ProductOutcome(
        product_id, status, {q: v for q, v in quantities.items() if v}, value, gap
    )


def solve_retail_product(s, product_id, cands, shares, baseline, protected, search_seconds):
    pm = build_product_model(s, product_id, cands, shares, baseline, protected)
    w = s.retail_weights
    expired = sum(sum(points) for points in pm.expired.values())
    lost = sum(sum(days) for days in pm.unmet.values())
    return solve(pm, w.w_exp * expired + w.w_lost * lost, search_seconds, product_id)
