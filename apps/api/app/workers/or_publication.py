"""Parent-only independent checks and transactional persistence of each method."""

import sqlalchemy as sa

from app.models.or_records import PlanRecord, ScenarioRecord
from app.repositories.or_repository import ORRepository
from app.schemas.or_execution import ORExecutionInput
from app.schemas.or_outputs import MethodOutcome
from app.services.jobs.contracts import StepStatus
from app.services.jobs.registry import PublicationRejected
from app.services.optimization.compare import assemble
from app.services.optimization.service import DEFAULT_SETTINGS


class ORPublisher:
    def __init__(self, comparison):
        self.comparison = comparison

    def admit(self, connection, scope, validated):
        """Recheck current epoch under the shared admission lock, closing reset races."""
        value = ORExecutionInput.model_validate(validated)
        repo = ORRepository(connection)
        row = repo.get(ScenarioRecord, scope.organization_id, value.scenario_id)
        repo.assert_current(row)
        if (
            row["org_epoch"] != value.org_epoch
            or row["operational_hash"] != value.scenario.operational_hash
        ):
            raise PublicationRejected("OR_ADMISSION_SOURCE_CHANGED")

    def publish_step(self, connection, identity, validated, outcome):
        value = ORExecutionInput.model_validate(validated)
        repo = ORRepository(connection)
        scenario = repo.get(ScenarioRecord, identity.organization_id, value.scenario_id)
        if scenario["org_epoch"] != value.org_epoch:
            raise PublicationRejected("DATASET_EPOCH_MISMATCH")
        if outcome.status != StepStatus.COMPLETED:
            return None
        method = MethodOutcome.model_validate(outcome.output)
        if str(method.method) != outcome.name:
            raise PublicationRejected("METHOD_IDENTITY_MISMATCH")
        if method.outcome != "VERIFIED":
            return None
        plan = repo.publish_plan(identity, value.scenario_id, method)
        return {
            "plan_id": str(plan["id"]),
            "method": method.method.value,
            "result_hash": plan["result_hash"],
        }

    def validate(self, validated, outcomes):
        value = ORExecutionInput.model_validate(validated)
        methods = ("CLASSICAL_GP", "EGP_PI_INSPIRED") if self.comparison else (value.method.value,)
        by_method = {o.name: o for o in outcomes}
        results = []
        for method in methods:
            outcome = by_method.get(method)
            if outcome is not None and outcome.status == StepStatus.COMPLETED:
                result = MethodOutcome.model_validate(outcome.output)
                if (
                    result.method.value != method
                    or result.operational_hash != value.scenario.operational_hash
                ):
                    raise PublicationRejected("METHOD_IDENTITY_MISMATCH")
            else:
                from app.services.optimization.canonical import operational_hash

                result = MethodOutcome(
                    method=method,
                    transfer_mode=value.scenario.transfer_mode,
                    operational_hash=value.scenario.operational_hash,
                    policy_hash=value.scenario.policy_hash,
                    settings_hash=operational_hash(value.settings or DEFAULT_SETTINGS),
                    decision_ids=value.scenario.decision_ids,
                    native_status=None,
                    outcome="FAILED",
                    candidate=None,
                    verification=None,
                    objective=None,
                    error_code=outcome.error_code if outcome else "METHOD_NOT_RUN",
                )
            results.append(result)
        if self.comparison:
            comparison = assemble(value.scenario, tuple(results))
            return {"input": validated, "comparison": comparison.model_dump(mode="json")}
        return {"input": validated, "method": results[0].model_dump(mode="json")}

    def publish(self, connection, identity, package):
        value = ORExecutionInput.model_validate(package["input"])
        repo = ORRepository(connection)
        scenario = repo.get(ScenarioRecord, identity.organization_id, value.scenario_id)
        repo.assert_current(scenario)
        if scenario["org_epoch"] != value.org_epoch:
            raise PublicationRejected("DATASET_EPOCH_MISMATCH")
        records = (
            connection.execute(
                sa.select(PlanRecord.__table__).where(
                    PlanRecord.organization_id == identity.organization_id,
                    PlanRecord.attempt_id == identity.attempt_id,
                )
            )
            .mappings()
            .all()
        )
        plans = {r["method"]: r for r in records}
        if self.comparison:
            comparison = package["comparison"]
            row = repo.publish_comparison(
                identity,
                value.scenario_id,
                first_plan_id=plans.get("CLASSICAL_GP", {}).get("id"),
                second_plan_id=plans.get("EGP_PI_INSPIRED", {}).get("id"),
                payload=comparison,
            )
            return {
                "outcome": row["outcome"],
                "comparison_id": str(row["id"]),
                "plan_ids": {key: str(plan["id"]) for key, plan in plans.items()},
                "result_completeness": "BOTH"
                if len(plans) == 2
                else "ONE_OF_TWO"
                if plans
                else "NONE",
            }
        result = package["method"]
        return {
            "outcome": "SUCCEEDED" if plans else "FAILED",
            "plan_ids": {key: str(plan["id"]) for key, plan in plans.items()},
            "error_code": result.get("error_code"),
        }
