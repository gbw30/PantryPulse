"""Checked independent outcomes/common metrics; no persistence or method substitution."""

import re

from app.schemas.or_outputs import ComparisonResult, MethodOutcome
from app.services.optimization.canonical import operational_hash
from app.services.optimization.service import solve_one


def assemble(scenario, outcomes, *, expected_settings=None):
    from app.services.optimization.candidates import prepare_problem
    from app.services.optimization.constraints import build_physical_model
    from app.services.optimization.metrics import evaluate
    from app.services.optimization.verify import verify

    problem = prepare_problem(scenario)  # includes frozen scenario hash/derivation checks
    try:
        outcomes = tuple(
            MethodOutcome.model_validate(
                item.model_dump(warnings=False) if isinstance(item, MethodOutcome) else item
            )
            for item in outcomes
        )
    except (ValueError, TypeError):
        raise ValueError("PAIRED_OUTCOME_INVALID") from None

    if len(outcomes) != 2 or tuple(str(x.method) for x in outcomes) != (
        "CLASSICAL_GP",
        "EGP_PI_INSPIRED",
    ):
        raise ValueError("PAIRED_METHOD_ORDER_REQUIRED")
    if any(
        x.operational_hash != scenario.operational_hash
        or x.policy_hash != scenario.policy_hash
        or x.transfer_mode != scenario.transfer_mode
        or x.historical != (scenario.intent == "HISTORICAL_REPLAY")
        or len(x.decision_ids) != len(scenario.decision_ids)
        or set(x.decision_ids) != set(scenario.decision_ids)
        for x in outcomes
    ):
        raise ValueError("PAIRED_INPUT_MISMATCH")
    if (
        any(not re.fullmatch(r"[0-9a-f]{64}", x.settings_hash) for x in outcomes)
        or len({x.settings_hash for x in outcomes}) != 1
        or len({x.physical_fingerprint for x in outcomes if x.physical_fingerprint}) > 1
        or any(
            x.physical_fingerprint is not None
            and not re.fullmatch(r"[0-9a-f]{64}", x.physical_fingerprint)
            for x in outcomes
        )
    ):
        raise ValueError("PAIRED_MODEL_SETTINGS_MISMATCH")
    if expected_settings is not None and outcomes[0].settings_hash != operational_hash(
        expected_settings
    ):
        raise ValueError("PAIRED_SETTINGS_EXPECTATION_MISMATCH")
    fingerprints = {x.physical_fingerprint for x in outcomes if x.physical_fingerprint}
    if fingerprints and fingerprints != {build_physical_model(problem).fingerprint}:
        raise ValueError("PAIRED_PHYSICAL_MODEL_MISMATCH")
    verified = [x for x in outcomes if x.outcome == "VERIFIED"]
    for outcome in verified:
        if not outcome.physical_fingerprint:
            raise ValueError("PAIRED_MODEL_FINGERPRINT_REQUIRED")
        checked = verify(problem, outcome.candidate, outcome.method)
        objective = (
            (
                checked.metrics.classical_objective
                if outcome.method == "CLASSICAL_GP"
                else checked.metrics.research_objective
            )
            if checked.passed
            else None
        )
        if not checked.passed or checked != outcome.verification or objective != outcome.objective:
            raise ValueError("PAIRED_VERIFICATION_MISMATCH")
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
        baseline_metrics=evaluate(scenario, problem.baseline, ()),
        warnings=(
            "SIMULATED" if scenario.package.source_kind == "SIMULATED" else "LIVE",
            "FIXED_LOADING_ORDER_RESTRICTS_FEASIBLE_SET",
        ),
    )


def compare(scenario, settings=None):
    from app.services.optimization.service import DEFAULT_SETTINGS

    settings = dict(DEFAULT_SETTINGS if settings is None else settings)
    return assemble(
        scenario,
        tuple(
            solve_one(scenario, method, settings) for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED")
        ),
        expected_settings=settings,
    )
