# covers: V1-A14, V1-A15, V1-A22
"""or-comparison.v3 worker: one step per method, independent failures, publication re-check."""

from uuid import UUID

import pytest

from app.schemas.v1_planning import MethodResult
from app.services.jobs.contracts import PRODUCTION_PROFILE, StepOutcome, StepStatus
from app.services.jobs.registry import ExecutionContext, InputRejected
from app.services.optimization.compare import compare_methods
from app.services.optimization.methods import run_method
from app.workers.optimization import V3_REGISTRATION, VERIFY_RESERVE_S
from tests.optimization.test_retail_oracle import load

NETWORK = "00000000-0000-4000-8000-0000000000a1"  # the fixtures' network_id
SCENARIO = "00000000-0000-4000-8000-0000000000c3"
HASH = "d" * 64
HANDLER, PUBLISHER = V3_REGISTRATION.handler, V3_REGISTRATION.publisher
RETAIL = ["NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"]


def payload(name="retail-usd-flip", methods=RETAIL, measure="UNITS"):
    s, _ = load(name)
    return dict(
        network_id=NETWORK,
        scenario_id=SCENARIO,
        scenario_hash=HASH,
        scenario=s.model_dump(mode="json"),
        methods=list(methods),
        measure=measure,
    )


def run_steps(validated, skip=()):
    outcomes = []
    for step in HANDLER.steps(validated, PRODUCTION_PROFILE):
        if step.name in skip:
            outcomes.append(StepOutcome(step.name, StepStatus.TIMED_OUT, None, "STEP_TIMEOUT"))
            continue
        context = ExecutionContext(UUID(int=1), UUID(int=2), step.name, 330, 300)
        output = HANDLER.execute_step(step.name, validated, [], context)
        outcomes.append(StepOutcome(step.name, StepStatus.COMPLETED, output))
    return outcomes


def test_validate_input_rejects_foreign_shapes():
    good = payload()
    assert HANDLER.validate_input(good)["methods"] == RETAIL
    for bad, code in (
        ({**good, "extra": 1}, "INVALID_COMPARISON_INPUT"),
        ({**good, "methods": ["CLASSICAL_GP"]}, "METHOD_NOT_IN_MODE"),
        ({**good, "network_id": "00000000-0000-4000-8000-0000000000ff"}, "SCENARIO_MISMATCH"),
        (payload("pantry-four-methods", ["CLASSICAL_GP"], "USD"), "MEASURE_NOT_IN_MODE"),
    ):
        with pytest.raises(InputRejected) as caught:
            HANDLER.validate_input(bad)
        assert caught.value.code == code


def test_one_step_per_method_within_method_ceiling():
    steps = HANDLER.steps(HANDLER.validate_input(payload()), PRODUCTION_PROFILE)
    assert [s.name for s in steps] == RETAIL
    assert all(s.max_s == PRODUCTION_PROFILE.method_wall_s for s in steps)


def test_method_deadline_reports_unsolved_products():
    s, _ = load("retail-usd-flip")
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS", method_seconds=0)
    assert result.native_status == "UNKNOWN" and not result.verified and result.transfers == ()
    assert result.failure_reason.startswith("METHOD_TIME_LIMIT:")


def test_step_search_stops_before_the_method_ceiling():
    """A step keeps VERIFY_RESERVE_S of its remaining time for assembly and verification."""
    validated = HANDLER.validate_input(payload())
    ctx = ExecutionContext(UUID(int=1), UUID(int=2), "RETAIL_OPTIMIZED", VERIFY_RESERVE_S, 300)
    output = HANDLER.execute_step("RETAIL_OPTIMIZED", validated, [], ctx)["method"]
    assert MethodResult.model_validate(output).failure_reason.startswith("METHOD_TIME_LIMIT:")
    with pytest.raises(ValueError):
        HANDLER.execute_step("EQUAL_SHARE", validated, [], ctx)  # not a requested method


def test_worker_publishes_what_compare_methods_computes():
    validated = HANDLER.validate_input(payload())
    package = PUBLISHER.validate(validated, run_steps(validated))
    s, _ = load("retail-usd-flip")
    direct = compare_methods(
        s, RETAIL, "UNITS", scenario_id=UUID(SCENARIO), scenario_hash=HASH
    ).model_dump(mode="json")
    assert package["comparison"] == direct


def test_timed_out_method_fails_alone():
    validated = HANDLER.validate_input(payload())
    outcomes = run_steps(validated, skip={"SOONEST_EXPIRY_FIRST"})
    outcomes[0] = StepOutcome("NO_TRANSFERS", StepStatus.FAILED, None, "CHILD_EXITED")
    package = PUBLISHER.validate(validated, outcomes)
    methods = {m["method"]: m for m in package["comparison"]["methods"]}
    assert methods["NO_TRANSFERS"]["failure_reason"] == "METHOD_FAILED:CHILD_EXITED"
    assert methods["SOONEST_EXPIRY_FIRST"]["verified"] is False
    assert methods["SOONEST_EXPIRY_FIRST"]["failure_reason"] == "METHOD_TIMED_OUT"
    assert methods["SOONEST_EXPIRY_FIRST"]["transfers"] == []
    assert methods["RETAIL_OPTIMIZED"]["verified"] and methods["RETAIL_OPTIMIZED"]["transfers"]


def test_tampered_output_is_published_unverified():
    """A child claiming a verified plan the raw scenario rejects never publishes that plan."""
    validated = HANDLER.validate_input(payload())
    outcomes = run_steps(validated)
    optimized = MethodResult.model_validate(outcomes[2].output["method"])
    bigger = optimized.transfers[0].model_copy(update={"quantity": 40})
    outcomes[2] = StepOutcome(
        "RETAIL_OPTIMIZED",
        StepStatus.COMPLETED,
        {"method": optimized.model_copy(update={"transfers": (bigger,)}).model_dump(mode="json")},
    )
    methods = PUBLISHER.validate(validated, outcomes)["comparison"]["methods"]
    assert methods[2]["verified"] is False and methods[2]["transfers"] == []
    assert methods[2]["failure_reason"].startswith("PUBLICATION_VERIFICATION_FAILED:")


def test_pantry_five_methods_through_the_worker():
    methods = [
        "NO_TRANSFERS",
        "EQUAL_SHARE",
        "MOST_URGENT_FIRST",
        "CLASSICAL_GP",
        "EGP_PI_INSPIRED",
    ]
    validated = HANDLER.validate_input(payload("pantry-four-methods", methods))
    comparison = PUBLISHER.validate(validated, run_steps(validated))["comparison"]
    assert [m["method"] for m in comparison["methods"]] == methods
    assert all(m["verified"] for m in comparison["methods"])
    assert comparison["mode"] == "PANTRY"


@pytest.mark.parametrize(
    ("field", "value"), [("objective", "0"), ("labels", ()), ("native_status", "FEASIBLE")]
)
def test_tampered_result_fields_are_published_unverified(field, value):
    """Publication rebuilds every derived field from the raw scenario and the plan itself."""
    validated = HANDLER.validate_input(payload())
    outcomes = run_steps(validated)
    optimized = MethodResult.model_validate(outcomes[2].output["method"])
    assert getattr(optimized, field) != value
    tampered = optimized.model_copy(update={field: value}).model_dump(mode="json")
    outcomes[2] = StepOutcome("RETAIL_OPTIMIZED", StepStatus.COMPLETED, {"method": tampered})
    method = PUBLISHER.validate(validated, outcomes)["comparison"]["methods"][2]
    assert (method["verified"], method["transfers"]) == (False, [])
    assert method["failure_reason"] == f"PUBLICATION_VERIFICATION_FAILED:{field}"
    assert method["native_status"] == optimized.native_status  # derived, never the claim


def test_product_status_relabel_is_published_unverified():
    """Per-product statuses are the solver's claims; the method status and the solved-count label
    must agree with them, so a partial relabel can't publish."""
    validated = HANDLER.validate_input(payload())
    outcomes = run_steps(validated)
    optimized = MethodResult.model_validate(outcomes[2].output["method"])
    first = optimized.products[0].model_copy(update={"native_status": "FEASIBLE", "gap": "0.5"})
    tampered = optimized.model_copy(update={"products": (first, *optimized.products[1:])})
    outcomes[2] = StepOutcome(
        "RETAIL_OPTIMIZED", StepStatus.COMPLETED, {"method": tampered.model_dump(mode="json")}
    )
    method = PUBLISHER.validate(validated, outcomes)["comparison"]["methods"][2]
    assert method["verified"] is False
    assert method["failure_reason"] == "PUBLICATION_VERIFICATION_FAILED:native_status,labels"
