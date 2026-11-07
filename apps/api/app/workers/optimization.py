"""Paired native search through the shared process driver and publication fence."""

import re
from uuid import UUID, uuid4

import sqlalchemy as sa

from app.models.networks import PlanningComparisonV3, PlanningScenarioV3
from app.models.optimization import MethodVerification, PlanningComparison, PlanningScenario
from app.schemas.or_inputs import ORScenarioPayload
from app.schemas.or_outputs import MethodOutcome
from app.schemas.v1_planning import (
    ComparisonRequestV3,
    ComparisonResultV3,
    MethodResult,
    ORInputV3,
    require_methods_for_mode,
)
from app.services.jobs.contracts import OperationKind, StepSpec, StepStatus
from app.services.jobs.policies import COMPARISON_METHODS, comparison_steps
from app.services.jobs.registry import InputRejected, PublicationRejected, Registration
from app.services.optimization.canonical import operational_hash
from app.services.optimization.scenario import verify_scenario
from app.services.optimization.settings import execution_limits, validate_settings


class ComparisonHandler:
    def validate_input(self, payload):
        try:
            if set(payload) != {"scenario_id", "scenario", "settings"}:
                raise ValueError("Unexpected comparison fields")
            scenario = ORScenarioPayload.model_validate(payload["scenario"])
            verify_scenario(scenario)
            return dict(
                scenario_id=str(UUID(payload["scenario_id"])),
                scenario=scenario.model_dump(mode="json"),
                settings=validate_settings(payload["settings"]),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise InputRejected("INVALID_COMPARISON_INPUT", "Invalid frozen comparison") from exc

    def execution_budget(self, validated, profile):
        settings = validate_settings(validated["settings"])
        wall, total = execution_limits(settings)
        if (
            wall > profile.method_wall_s
            or settings["search_milliseconds"] / 1000 > profile.method_search_s
        ):
            raise InputRejected(
                "UNSUPPORTED_EXECUTION_SETTINGS", "Worker cannot honor frozen settings"
            )
        return total

    def steps(self, validated, profile):
        self.execution_budget(validated, profile)
        wall, _ = execution_limits(validated["settings"])
        return tuple(
            StepSpec(name=method, min_s=profile.method_min_s, max_s=wall, cutoff_s=2 * wall)
            for method in COMPARISON_METHODS
        )

    def execute_step(self, step, validated, prior, context):
        from app.services.optimization.service import solve_one

        settings = validate_settings(validated["settings"])
        if (
            step not in COMPARISON_METHODS
            or settings["search_milliseconds"] / 1000 > context.search_limit_s
        ):
            raise ValueError("Unsupported method execution")
        scenario = ORScenarioPayload.model_validate(validated["scenario"])
        result = solve_one(scenario, step, settings)
        return {"method": result.model_dump(mode="json")}


class ComparisonPublisher:
    def validate(self, validated, outcomes):
        from app.services.optimization.compare import assemble

        scenario = ORScenarioPayload.model_validate(validated["scenario"])
        settings = validate_settings(validated["settings"])
        if len({row.name for row in outcomes}) != len(outcomes) or any(
            row.name not in COMPARISON_METHODS for row in outcomes
        ):
            raise PublicationRejected("OUTPUT_INVALID")
        methods = []
        for name in COMPARISON_METHODS:
            row = next((row for row in outcomes if row.name == name), None)
            if row and row.status == StepStatus.COMPLETED:
                try:
                    value = MethodOutcome.model_validate(row.output["method"])
                    if value.method != name:
                        raise ValueError("Wrong method")
                    methods.append(value)
                    continue
                except (KeyError, TypeError, ValueError):
                    pass
            methods.append(
                MethodOutcome(
                    method=name,
                    transfer_mode=scenario.transfer_mode,
                    operational_hash=scenario.operational_hash,
                    policy_hash=scenario.policy_hash,
                    settings_hash=operational_hash(settings),
                    decision_ids=scenario.decision_ids,
                    historical=scenario.intent == "HISTORICAL_REPLAY",
                    native_status=None,
                    outcome="TIMED_OUT" if row and row.status == StepStatus.TIMED_OUT else "FAILED",
                    candidate=None,
                    verification=None,
                    objective=None,
                    error_code=(row.error_code if row else None) or "METHOD_OUTPUT_UNAVAILABLE",
                )
            )
        try:
            result = assemble(scenario, methods, expected_settings=settings)
        except (ValueError, TypeError, AttributeError):
            # Isolate an invalid partner rather than discarding a valid method.
            failed = [
                MethodOutcome(
                    method=name,
                    transfer_mode=scenario.transfer_mode,
                    operational_hash=scenario.operational_hash,
                    policy_hash=scenario.policy_hash,
                    settings_hash=operational_hash(settings),
                    decision_ids=scenario.decision_ids,
                    historical=scenario.intent == "HISTORICAL_REPLAY",
                    native_status=None,
                    outcome="FAILED",
                    candidate=None,
                    verification=None,
                    objective=None,
                    error_code="METHOD_VERIFICATION_FAILED",
                )
                for name in COMPARISON_METHODS
            ]
            for i in range(2):
                isolated = list(failed)
                isolated[i] = methods[i]
                try:
                    assemble(scenario, isolated, expected_settings=settings)
                except (ValueError, TypeError, AttributeError):
                    methods[i] = failed[i]
            result = assemble(scenario, methods, expected_settings=settings)
        if result.outcome == "FAILED":
            raise PublicationRejected("NO_VERIFIED_METHOD")
        return {"comparison": result.model_dump(mode="json")}

    def publish(self, connection, identity, package):
        from app.models.jobs import compute_jobs

        job = (
            connection.execute(
                sa.select(compute_jobs).where(
                    compute_jobs.c.job_id == identity.job_id,
                    compute_jobs.c.organization_id == identity.organization_id,
                )
            )
            .mappings()
            .one()
        )
        data = ComparisonHandler().validate_input(job["input_package"]["input"])
        scenario = (
            connection.execute(
                sa.select(PlanningScenario.__table__).where(
                    PlanningScenario.id == UUID(data["scenario_id"]),
                    PlanningScenario.organization_id == identity.organization_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            scenario is None
            or scenario["payload"] != data["scenario"]
            or identity.handler_contract != "or-comparison.v2"
        ):
            raise PublicationRejected("SCENARIO_OWNERSHIP_MISMATCH")
        # Recheck the exact staged values inside the ownership transaction.
        checked = self.validate(
            data, tuple(StepOutcomeProxy(item) for item in package["comparison"]["methods"])
        )
        result = checked["comparison"]
        connection.execute(
            sa.insert(PlanningComparison).values(
                id=identity.job_id,
                organization_id=identity.organization_id,
                job_id=identity.job_id,
                attempt_id=identity.attempt_id,
                scenario_id=scenario["id"],
                settings=data["settings"],
                input_hash=identity.input_sha256,
                outcome=result["outcome"],
                result=result,
            )
        )
        for method in result["methods"]:
            verification_id = uuid4()
            connection.execute(
                sa.insert(MethodVerification).values(
                    id=verification_id,
                    organization_id=identity.organization_id,
                    comparison_id=identity.job_id,
                    method=method["method"],
                    outcome=method["outcome"],
                    record=method,
                )
            )
            if method["outcome"] == "VERIFIED":
                from app.repositories.plans import put_plan

                put_plan(
                    connection,
                    identity,
                    scenario["id"],
                    data["settings"],
                    method,
                    comparison_id=identity.job_id,
                    plan_id=verification_id,
                )
        return {
            "result_ref": str(identity.job_id),
            "planning_ready": result["outcome"] == "SUCCEEDED",
            "comparison_outcome": result["outcome"],
        }


def StepOutcomeProxy(item):
    from app.services.jobs.contracts import StepOutcome

    return StepOutcome(item["method"], StepStatus.COMPLETED, {"method": item})


REGISTRATION = Registration(
    contract="or-comparison.v2",
    operation_kind=OperationKind.COMPARISON,
    input_schema_version="2",
    max_input_bytes=4_000_000,
    max_output_bytes=8_000_000,
    handler=ComparisonHandler(),
    publisher=ComparisonPublisher(),
)


V3_FIELDS = {"network_id", "scenario_id", "scenario_hash", "scenario", "methods", "measure"}
VERIFY_RESERVE_S = 30.0  # method step 330 s minus 300 s search: assembly and verification


class ComparisonV3Handler:
    """or-comparison.v3 (W1-S04): one step per requested method on a frozen or-input-v3."""

    def validate_input(self, payload):
        try:
            if not isinstance(payload, dict) or set(payload) != V3_FIELDS:
                raise ValueError("Unexpected comparison fields")
            scenario = ORInputV3.model_validate(payload["scenario"])
            request = ComparisonRequestV3.model_validate(
                {k: payload[k] for k in ("scenario_id", "methods", "measure")}
            )
            network_id = UUID(payload["network_id"])
            if not re.fullmatch(r"[0-9a-f]{64}", payload["scenario_hash"]):
                raise ValueError("scenario_hash")
        except (ValueError, KeyError, TypeError) as exc:
            raise InputRejected("INVALID_COMPARISON_INPUT", "Invalid frozen comparison") from exc
        if scenario.network_id != network_id:
            raise InputRejected("SCENARIO_MISMATCH", "Scenario belongs to another network")
        require_methods_for_mode(scenario.mode, request.methods)
        if scenario.mode == "PANTRY" and request.measure != "UNITS":
            raise InputRejected("MEASURE_NOT_IN_MODE", "Pantry comparisons are measured in units")
        return dict(
            network_id=str(network_id),
            scenario_id=str(request.scenario_id),
            scenario_hash=payload["scenario_hash"],
            scenario=scenario.model_dump(mode="json"),
            methods=list(request.methods),
            measure=request.measure,
        )

    def steps(self, validated, profile):
        return comparison_steps(profile, validated["methods"])

    def execute_step(self, step, validated, prior, context):
        from app.services.optimization.methods import (
            METHOD_SEARCH_S,
            PER_PRODUCT_SEARCH_S,
            run_method,
        )

        if step not in validated["methods"]:
            raise ValueError("Unsupported method execution")
        result = run_method(
            ORInputV3.model_validate(validated["scenario"]),
            step,
            validated["measure"],
            search_seconds=min(PER_PRODUCT_SEARCH_S, context.search_limit_s),
            method_seconds=min(
                METHOD_SEARCH_S, context.search_limit_s, context.remaining_s - VERIFY_RESERVE_S
            ),
        )
        return {"method": result.model_dump(mode="json")}


class ComparisonV3Publisher:
    def validate(self, validated, outcomes):
        """Every requested method once; failures stay per method; claimed plans are re-checked."""
        from app.services.optimization.compare import publishable
        from app.services.optimization.methods import failed_result
        from app.services.optimization.projection import project_v3

        s = ORInputV3.model_validate(validated["scenario"])
        methods, measure = validated["methods"], validated["measure"]
        names = [row.name for row in outcomes]
        if len(set(names)) != len(names) or any(name not in methods for name in names):
            raise PublicationRejected("OUTPUT_INVALID")
        baseline = project_v3(s).days
        results = []
        for name in methods:
            row = next((row for row in outcomes if row.name == name), None)
            result = None
            if row and row.status == StepStatus.COMPLETED:
                try:
                    result = MethodResult.model_validate(row.output["method"])
                    if result.method != name or result.measure != measure:
                        result = None
                except (KeyError, TypeError, ValueError):
                    result = None
            if result is None:
                if row and row.status == StepStatus.TIMED_OUT:
                    reason = "METHOD_TIMED_OUT"
                elif row and row.status == StepStatus.FAILED and row.error_code:
                    reason = f"METHOD_FAILED:{row.error_code}"
                else:
                    reason = "METHOD_OUTPUT_UNAVAILABLE"
                result = failed_result(s, name, measure, None, reason, ())
            results.append(publishable(s, baseline, result))
        comparison = ComparisonResultV3(
            scenario_id=UUID(validated["scenario_id"]),
            scenario_hash=validated["scenario_hash"],
            mode=s.mode,
            measure=measure,
            methods=tuple(results),
        )
        return {"comparison": comparison.model_dump(mode="json")}

    def publish(self, connection, identity, package):
        from app.models.jobs import compute_jobs

        job = (
            connection.execute(
                sa.select(compute_jobs).where(
                    compute_jobs.c.job_id == identity.job_id,
                    compute_jobs.c.organization_id == identity.organization_id,
                )
            )
            .mappings()
            .one()
        )
        data = ComparisonV3Handler().validate_input(job["input_package"]["input"])
        scenario = (
            connection.execute(
                sa.select(PlanningScenarioV3.__table__).where(
                    PlanningScenarioV3.id == UUID(data["scenario_id"]),
                    PlanningScenarioV3.organization_id == identity.organization_id,
                    PlanningScenarioV3.network_id == UUID(data["network_id"]),
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            scenario is None
            or scenario["content_hash"] != data["scenario_hash"]
            or ORInputV3.model_validate(scenario["payload"]).model_dump(mode="json")
            != data["scenario"]
            or identity.handler_contract != "or-comparison.v3"
        ):
            raise PublicationRejected("SCENARIO_OWNERSHIP_MISMATCH")
        try:
            result = ComparisonResultV3.model_validate(package["comparison"])
        except (KeyError, TypeError, ValueError):
            raise PublicationRejected("OUTPUT_INVALID") from None
        # validate() already re-verified every plan in the parent; here only identity is checked.
        if (
            str(result.scenario_id) != data["scenario_id"]
            or result.scenario_hash != data["scenario_hash"]
            or result.measure != data["measure"]
            or [m.method for m in result.methods] != data["methods"]
            or any(m.measure != data["measure"] for m in result.methods)
        ):
            raise PublicationRejected("OUTPUT_INVALID")
        # Same transaction as the SUCCEEDED transition: the row exists only if the attempt
        # succeeded (an uncertain commit leaves both or neither), and rows are immutable.
        connection.execute(
            sa.insert(PlanningComparisonV3.__table__).values(
                id=identity.job_id,
                organization_id=identity.organization_id,
                network_id=scenario["network_id"],
                scenario_id=scenario["id"],
                job_id=identity.job_id,
                attempt_id=identity.attempt_id,
                measure=result.measure,
                result=result.model_dump(mode="json"),
            )
        )
        verified = sum(m.verified for m in result.methods)
        outcome = (
            "SUCCEEDED" if verified == len(result.methods) else "PARTIAL" if verified else "FAILED"
        )
        return {
            "result_ref": str(identity.job_id),
            "planning_ready": outcome == "SUCCEEDED",
            "comparison_outcome": outcome,
        }


# W1-S04: v1 N-method comparison on or-input-v3 (W0-08b registered the contract).
V3_REGISTRATION = Registration(
    contract="or-comparison.v3",
    operation_kind=OperationKind.COMPARISON,
    input_schema_version="3",
    max_input_bytes=64_000_000,
    max_output_bytes=64_000_000,
    handler=ComparisonV3Handler(),
    publisher=ComparisonV3Publisher(),
)
