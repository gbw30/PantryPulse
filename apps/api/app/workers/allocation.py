"""A single verified method using main's frozen scenario, solver and publication fence."""

from uuid import UUID

import sqlalchemy as sa

from app.models.jobs import compute_jobs
from app.models.optimization import PlanningScenario
from app.repositories.plans import put_plan
from app.schemas.planning_primitives import AllocationMethod
from app.services.jobs.contracts import OperationKind, StepOutcome, StepSpec, StepStatus
from app.services.jobs.registry import InputRejected, PublicationRejected, Registration
from app.services.optimization.settings import execution_limits
from app.workers.optimization import ComparisonHandler, ComparisonPublisher


class AllocationHandler(ComparisonHandler):
    def validate_input(self, payload):
        try:
            if set(payload) != {"scenario_id", "scenario", "settings", "method"}:
                raise ValueError("Unexpected allocation fields")
            base = super().validate_input({k: v for k, v in payload.items() if k != "method"})
            return base | {"method": AllocationMethod(payload["method"]).value}
        except (ValueError, TypeError) as exc:
            raise InputRejected("INVALID_ALLOCATION_INPUT", "Invalid frozen allocation") from exc

    def execution_budget(self, validated, profile):
        super().execution_budget(validated, profile)
        return execution_limits(validated["settings"])[0]

    def steps(self, validated, profile):
        wall = self.execution_budget(validated, profile)
        return (StepSpec(name=validated["method"], min_s=profile.method_min_s, max_s=wall),)

    def execute_step(self, step, validated, prior, context):
        if step != validated["method"]:
            raise ValueError("Wrong allocation method")
        return super().execute_step(step, validated, prior, context)


class AllocationPublisher:
    def validate(self, validated, outcomes):
        if len(outcomes) != 1 or outcomes[0].name != validated["method"]:
            raise PublicationRejected("OUTPUT_INVALID")
        # Reuse the same independent identity/model/candidate/objective replay that
        # protects paired comparisons. The absent partner is explicitly unavailable.
        comparison = ComparisonPublisher().validate(validated, outcomes)["comparison"]
        result = next(m for m in comparison["methods"] if m["method"] == validated["method"])
        if result["outcome"] != "VERIFIED":
            raise PublicationRejected("NO_VERIFIED_METHOD")
        return {"method": result}

    def publish(self, connection, identity, package):
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
        data = AllocationHandler().validate_input(job["input_package"]["input"])
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
            or identity.handler_contract != "or-allocation.v2"
        ):
            raise PublicationRejected("SCENARIO_OWNERSHIP_MISMATCH")
        checked = self.validate(
            data,
            (StepOutcome(data["method"], StepStatus.COMPLETED, {"method": package["method"]}),),
        )
        plan_id = put_plan(
            connection, identity, scenario["id"], data["settings"], checked["method"]
        )
        return {"result_ref": str(plan_id), "planning_ready": True}


REGISTRATION = Registration(
    contract="or-allocation.v2",
    operation_kind=OperationKind.ALLOCATION,
    input_schema_version="2",
    max_input_bytes=4_000_000,
    max_output_bytes=8_000_000,
    handler=AllocationHandler(),
    publisher=AllocationPublisher(),
)
