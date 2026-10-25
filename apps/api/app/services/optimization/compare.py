"""Saved independent outcomes and common metrics; no substitution or universal winner."""

from app.schemas.or_outputs import ComparisonResult


def assemble(scenario, outcomes):
    from app.services.optimization.candidates import prepare_problem
    from app.services.optimization.metrics import evaluate

    if len(outcomes) != 2 or tuple(str(x.method) for x in outcomes) != (
        "CLASSICAL_GP",
        "EGP_PI_INSPIRED",
    ):
        raise ValueError("Exact ordered pair required")
    if any(
        x.operational_hash != scenario.operational_hash or x.transfer_mode != scenario.transfer_mode
        for x in outcomes
    ):
        raise ValueError("PAIRED_INPUT_MISMATCH")
    verified = [x for x in outcomes if x.outcome == "VERIFIED"]
    if len(verified) == 2 and (
        len({x.physical_fingerprint for x in verified}) != 1
        or len({x.settings_hash for x in verified}) != 1
    ):
        raise ValueError("PAIRED_MODEL_SETTINGS_MISMATCH")
    differences = {}
    if len(verified) == 2:
        before, after = (x.verification.metrics for x in verified)
        differences = {
            "cost_minor_delta": after.cost_minor - before.cost_minor,
            "by_product": [
                {
                    "product_id": str(p.id),
                    "unit": p.unit,
                    "unmet_delta": sum(g.unmet for g in after.goals if g.product_id == p.id)
                    - sum(g.unmet for g in before.goals if g.product_id == p.id),
                }
                for p in scenario.package.products
            ],
            "interpretation": "Native objectives differ; inspect common metrics and trade-offs.",
        }
    # OR-DEC-013/016 [PROVISIONAL]: independent failures; no numeric transfer attribution.
    return ComparisonResult(
        operational_hash=scenario.operational_hash,
        transfer_mode=scenario.transfer_mode,
        methods=tuple(outcomes),
        outcome="SUCCEEDED" if len(verified) == 2 else "PARTIAL" if verified else "FAILED",
        common_differences=differences,
        historical=scenario.intent == "HISTORICAL_REPLAY",
        baseline_metrics=evaluate(scenario, prepare_problem(scenario).baseline, ()),
        warnings=(
            "SIMULATED" if scenario.package.source_kind == "SIMULATED" else "LIVE",
            "FIXED_LOADING_ORDER_RESTRICTS_FEASIBLE_SET",
        ),
    )


def compare(scenario, settings=None):
    from app.services.optimization.service import solve_one

    return assemble(
        scenario,
        tuple(
            solve_one(scenario, method, settings) for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED")
        ),
    )
