"""v1 allocation methods on one or-input-v3 scenario (W1-S02/S03).

Every method returns route quantities; one assembly packs them FEFO, runs the independent
verifier over the union plan (verify.verify_plan) and publishes a plan only when it passes.
Units of different products are never summed (LocationEffect is per location × product).
"""

import time
from collections import defaultdict
from decimal import Decimal

import ortools

from app.schemas.v1_planning import (
    NOT_AT_RISK_LABEL,
    AllocationMethod,
    LocationEffect,
    Measure,
    MethodResult,
    ORInputV3,
    ProductSolve,
    SolverRun,
    require_methods_for_mode,
)
from app.services.optimization.decompose import at_risk, protected_senders, split
from app.services.optimization.pantry import (
    SINGLETON_LABEL,
    coverage_gap,
    goals,
    pantry_index,
    pantry_objectives,
    solve_pantry_product,
)
from app.services.optimization.projection import project_v3
from app.services.optimization.retail import SEED, WORKERS, ProductOutcome, solve_retail_product
from app.services.optimization.v3 import (
    PER_PRODUCT_LABEL,
    STARVED_LABEL,
    candidates,
    money,
    pack,
)
from app.services.optimization.verify import verify_plan

# shortcut: fixed per-product search cap from spike S1 (5 s), solved serially within the method
# deadline; add a process pool if a measured network needs more than METHOD_SEARCH_S.
PER_PRODUCT_SEARCH_S = 5.0
METHOD_SEARCH_S = 300.0  # solver search ceiling per method (CLAUDE.md: 300 s search / 330 s method)
OPTIMIZING = ("CLASSICAL_GP", "EGP_PI_INSPIRED", "RETAIL_OPTIMIZED")
UNITS_NOT_SUMMED = "units objective is per product; not summed across products"


def solver_run(method) -> SolverRun | None:
    if method not in OPTIMIZING:
        return None
    return SolverRun(
        engine="OR-Tools CP-SAT", version=ortools.__version__, seed=SEED, workers=WORKERS
    )


def usd_unavailable_reason(s: ORInputV3) -> str | None:
    missing = [p.name for p in s.products if p.unit_value_usd is None]
    return f"USD unavailable: no unit value for {', '.join(missing)}" if missing else None


def run_method(
    scenario: ORInputV3,
    method: AllocationMethod,
    measure: Measure,
    *,
    search_seconds: float = PER_PRODUCT_SEARCH_S,
    method_seconds: float = METHOD_SEARCH_S,
) -> MethodResult:
    deadline = time.monotonic() + min(method_seconds, METHOD_SEARCH_S)  # counts preparation
    s = scenario
    require_methods_for_mode(s.mode, [method])
    if s.mode == "PANTRY" and measure != "UNITS":
        raise ValueError("MEASURE_NOT_IN_MODE")  # Pantry is measured in units; the API maps 422
    reason = usd_unavailable_reason(s)
    if measure == "USD" and reason:
        return failed_result(s, method, measure, None, "USD_UNAVAILABLE", ())
    baseline = project_v3(s).days
    if method in OPTIMIZING:
        return _optimized(s, method, measure, baseline, search_seconds, deadline)
    if method == "NO_TRANSFERS":
        products = tuple(
            ProductSolve(product_id=p.id, native_status=None, gap=None, label=None)
            for p in s.products
        )
        return assemble(s, method, measure, baseline, {}, None, products, {})
    from app.services.optimization.baselines import heuristic

    plan = heuristic(s, method, measure, baseline, deadline)
    products = tuple(
        ProductSolve(
            product_id=p.id,
            native_status=None,
            gap=None,
            label=NOT_AT_RISK_LABEL
            if p.id not in plan.risky
            else STARVED_LABEL
            if p.id in plan.starved
            else None,
        )
        for p in s.products
    )
    if plan.late:
        reason = f"METHOD_TIME_LIMIT:{','.join(plan.late)}"
        return failed_result(s, method, measure, None, reason, products)
    return assemble(s, method, measure, baseline, plan.quantities, None, products, {})


def _optimized(s, method, measure, baseline, search_seconds, deadline) -> MethodResult:
    undefined = set()
    ix = pantry_index(s) if s.mode == "PANTRY" else None
    if method == "EGP_PI_INSPIRED":
        missing = coverage_gap(s, ix)
        if missing:
            reason = f"ATTRIBUTE_POLICY_COVERAGE:{','.join(missing)}"
            return failed_result(s, method, measure, None, reason, ())
        undefined = {p.id for p in s.products if len(goals(s, p.id, ix)) < 2}
    at_risk_all = at_risk(s, baseline)
    risky = at_risk_all - undefined
    cands = {p: candidates(s, p) for p in at_risk_all}
    # One feasible region: every method splits over every at-risk product; EGP only skips solving
    # the singleton ones, and their shares stay unused.
    parts = split(s, baseline, at_risk_all, measure, cands)
    outcomes, late = {}, []
    by_product = defaultdict(list)
    for d in baseline:
        by_product[d.product_id].append(d)
    for p in sorted(risky - parts.starved):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            outcomes[p] = ProductOutcome(p, "UNKNOWN", {}, None, None)
            late.append(p)
            continue
        rows = by_product[p]
        protected = protected_senders(s, rows, p)
        args = (s, p, cands[p], parts.shares[p], rows, protected, min(search_seconds, remaining))
        if method == "RETAIL_OPTIMIZED":
            outcomes[p] = solve_retail_product(*args)
        else:
            outcomes[p] = solve_pantry_product(*args, method=method, ix=ix)
    products = []
    for p in s.products:
        if p.id in undefined and p.id in at_risk_all:
            products.append(
                ProductSolve(product_id=p.id, native_status=None, gap=None, label=SINGLETON_LABEL)
            )
        elif p.id not in risky:
            products.append(
                ProductSolve(product_id=p.id, native_status=None, gap=None, label=NOT_AT_RISK_LABEL)
            )
        elif p.id in parts.starved:
            products.append(
                ProductSolve(product_id=p.id, native_status=None, gap=None, label=STARVED_LABEL)
            )
        else:
            o = outcomes[p.id]
            products.append(
                ProductSolve(product_id=p.id, native_status=o.native_status, gap=o.gap, label=None)
            )
    statuses = [o.native_status for o in outcomes.values()]
    failed = sorted(
        p for p, o in outcomes.items() if o.native_status not in ("OPTIMAL", "FEASIBLE")
    )
    if late:
        reason = f"METHOD_TIME_LIMIT:{','.join(late)}"
        return failed_result(s, method, measure, "UNKNOWN", reason, products)
    if failed:
        status = outcomes[failed[0]].native_status
        return failed_result(
            s, method, measure, status, f"NO_SOLUTION:{','.join(failed)}", products
        )
    status = None if not statuses else "FEASIBLE" if "FEASIBLE" in statuses else "OPTIMAL"
    quantities = {k: v for o in outcomes.values() for k, v in o.quantities.items()}
    native = {p: o.primary for p, o in outcomes.items()}
    return assemble(s, method, measure, baseline, quantities, status, tuple(products), native)


def assemble(s, method, measure, baseline, quantities, status, products, native) -> MethodResult:
    """Pack, verify the union plan, replay native objectives, publish only verified plans."""
    try:
        packed = pack(s, quantities)
    except ValueError as exc:
        return failed_result(s, method, measure, status, f"PACKING_FAILED:{exc}", products)
    transfers = tuple(p.transfer for p in packed)
    report = verify_plan(s, transfers)
    if not report.passed:
        reason = f"VERIFICATION_FAILED:{','.join(report.violations)}"
        return failed_result(s, method, measure, status, reason, products)
    replay = product_objectives(s, report, method)
    mismatched = sorted(p for p, value in native.items() if replay.get(p, 0) != value)
    if mismatched:
        reason = f"NATIVE_OBJECTIVE_REPLAY_MISMATCH:{','.join(mismatched)}"
        return failed_result(s, method, measure, status, reason, products)
    labels = []
    if method in OPTIMIZING:
        solved = [p.native_status for p in products if p.native_status]
        labels += [
            PER_PRODUCT_LABEL,
            f"solved per product: {solved.count('OPTIMAL')} OPTIMAL, "
            f"{solved.count('FEASIBLE')} FEASIBLE",
        ]
    if s.mode == "RETAIL" and measure == "UNITS" and len(s.products) > 1:
        labels.append(UNITS_NOT_SUMMED)
    if report.above_storage_at_baseline:
        labels.append("stock already above storage capacity before any transfer")
    return MethodResult(
        method=method,
        measure=measure,
        native_status=status,
        verified=True,
        failure_reason=None,
        products=products,
        transfers=transfers,
        effects=effects(baseline, report.days),
        objective=retail_objective(s, measure, replay) if s.mode == "RETAIL" else None,
        usd_unavailable_reason=usd_unavailable_reason(s),
        retail_weights=s.retail_weights,
        labels=tuple(labels),
        solver=solver_run(method),
    )


def failed_result(s, method, measure, status, reason, products) -> MethodResult:
    return MethodResult(
        method=method,
        measure=measure,
        native_status=status,
        verified=False,
        failure_reason=reason,
        products=tuple(products),
        transfers=(),
        effects=(),
        objective=None,
        usd_unavailable_reason=usd_unavailable_reason(s),
        retail_weights=s.retail_weights,
        labels=(),
        solver=solver_run(method),
    )


def product_objectives(s, report, method) -> dict[str, int]:
    """Per-product objective recomputed from the verifier's projection and plan."""
    if s.mode != "RETAIL":
        return pantry_objectives(s, report, method)
    w = s.retail_weights
    out = defaultdict(int)
    for d in report.days:
        out[d.product_id] += w.w_exp * d.expired + w.w_lost * d.unmet
    return dict(out)


def retail_objective(s, measure, per_product) -> str | None:
    if measure == "USD":
        prices = {p.id: Decimal(p.unit_value_usd) for p in s.products}
        return money(sum((prices[p] * v for p, v in per_product.items()), Decimal(0)))
    return str(per_product.get(s.products[0].id, 0)) if len(s.products) == 1 else None


def effects(baseline, days) -> tuple[LocationEffect, ...]:
    totals = defaultdict(lambda: [0, 0, 0, 0])
    for i, rows in enumerate((baseline, days)):
        for d in rows:
            t = totals[d.location_id, d.product_id]
            t[i] += d.unmet
            t[2 + i] += d.expired
    return tuple(
        LocationEffect(
            location_id=loc,
            product_id=pid,
            unmet_without_plan=t[0],
            unmet_with_plan=t[1],
            expired_without_plan=t[2],
            expired_with_plan=t[3],
        )
        for (loc, pid), t in sorted(totals.items())
    )
