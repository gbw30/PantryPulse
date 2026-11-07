"""v1 allocation methods on one or-input-v3 scenario (W1-S02/S03).

Every method returns route quantities; one assembly packs them FEFO, runs the independent
verifier over the union plan (verify.verify_plan) and publishes a plan only when it passes.
Units of different products are never summed (LocationEffect is per location × product).
"""

from collections import defaultdict
from decimal import Decimal

from app.schemas.v1_planning import (
    NOT_AT_RISK_LABEL,
    AllocationMethod,
    LocationEffect,
    Measure,
    MethodResult,
    ORInputV3,
    ProductSolve,
    require_methods_for_mode,
)
from app.services.optimization.decompose import at_risk, protected_senders, split
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import (
    PER_PRODUCT_LABEL,
    STARVED_LABEL,
    candidates,
    pack,
)
from app.services.optimization.verify import verify_plan

# shortcut: fixed per-product search cap from spike S1 (5 s); W1-S05 adds the method deadline
# and the process pool for 100 × 500.
PER_PRODUCT_SEARCH_S = 5.0
OPTIMIZING = ("CLASSICAL_GP", "EGP_PI_INSPIRED", "RETAIL_OPTIMIZED")
UNITS_NOT_SUMMED = "units objective is per product; not summed across products"


def usd_unavailable_reason(s: ORInputV3) -> str | None:
    missing = [p.name for p in s.products if p.unit_value_usd is None]
    return f"USD unavailable: no unit value for {', '.join(missing)}" if missing else None


def run_method(
    scenario: ORInputV3,
    method: AllocationMethod,
    measure: Measure,
    *,
    search_seconds: float = PER_PRODUCT_SEARCH_S,
) -> MethodResult:
    s = scenario
    require_methods_for_mode(s.mode, [method])
    if s.mode == "PANTRY" and measure != "UNITS":
        raise ValueError("MEASURE_NOT_IN_MODE")  # Pantry is measured in units; the API maps 422
    reason = usd_unavailable_reason(s)
    if measure == "USD" and reason:
        return failed_result(s, method, measure, None, "USD_UNAVAILABLE", ())
    baseline = project_v3(s).days
    if method in OPTIMIZING:
        return _optimized(s, method, measure, baseline, search_seconds)
    if method == "NO_TRANSFERS":
        products = tuple(
            ProductSolve(product_id=p.id, native_status=None, gap=None, label=None)
            for p in s.products
        )
        return assemble(s, method, measure, baseline, {}, None, products, {})
    from app.services.optimization.baselines import heuristic

    plan = heuristic(s, method, measure, baseline)
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
    return assemble(s, method, measure, baseline, plan.quantities, None, products, {})


def _optimized(s, method, measure, baseline, search_seconds) -> MethodResult:
    risky = at_risk(s, baseline)
    cands = {p: candidates(s, p) for p in risky}
    parts = split(s, baseline, risky, measure, cands)
    outcomes = {}
    for p in sorted(risky - parts.starved):
        rows = [d for d in baseline if d.product_id == p]
        protected = protected_senders(s, baseline, p)
        if method == "RETAIL_OPTIMIZED":
            from app.services.optimization.retail import solve_retail_product as solve
        else:
            from app.services.optimization.pantry import solve_pantry_product as solve

            solve = _bind_method(solve, method)
        outcomes[p] = solve(s, p, cands[p], parts.shares[p], rows, protected, search_seconds)
    products = []
    for p in s.products:
        if p.id not in risky:
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
    if failed:
        status = outcomes[failed[0]].native_status
        return failed_result(
            s, method, measure, status, f"NO_SOLUTION:{','.join(failed)}", products
        )
    status = None if not statuses else "FEASIBLE" if "FEASIBLE" in statuses else "OPTIMAL"
    quantities = {k: v for o in outcomes.values() for k, v in o.quantities.items()}
    native = {p: o.primary for p, o in outcomes.items()}
    return assemble(s, method, measure, baseline, quantities, status, tuple(products), native)


def _bind_method(solve, method):
    return lambda *args: solve(*args, method=method)


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
    replay = product_objectives(s, report.days, method)
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
    )


def product_objectives(s, days, method) -> dict[str, int]:
    """Per-product objective recomputed from the verifier's projection (Retail primary)."""
    if s.mode != "RETAIL":
        from app.services.optimization.pantry import pantry_objectives

        return pantry_objectives(s, days, method)
    w = s.retail_weights
    out = defaultdict(int)
    for d in days:
        out[d.product_id] += w.w_exp * d.expired + w.w_lost * d.unmet
    return dict(out)


def retail_objective(s, measure, per_product) -> str | None:
    if measure == "USD":
        prices = {p.id: Decimal(p.unit_value_usd) for p in s.products}
        return str(sum((prices[p] * v for p, v in per_product.items()), Decimal(0)))
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
