"""Transaction-local OR persistence over the canonical shared PostgreSQL connection.

Callers own commit/rollback. No method starts compute, posts stock or commits a partial
transaction. The queue supervisor remains the only publication authority.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert

from app.models.or_records import (
    AuditEvent,
    ComparisonRecord,
    DatasetState,
    InputPackageRecord,
    PlanRecord,
    PolicyRecord,
    RequestKey,
    ReviewRecord,
    ScenarioRecord,
    TransferRecord,
    VerificationRecord,
)
from app.schemas.or_inputs import ORInputPackage, ORPolicy, ORScenarioPayload
from app.schemas.or_outputs import ComparisonResult, MethodOutcome
from app.services.jobs.contracts import sha256_hex
from app.services.jobs.registry import PublicationIdentity, PublicationRejected
from app.services.optimization.canonical import operational_hash
from app.services.optimization.scenario import verify_scenario


class ORStorageError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _json(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def _validated(model, value):
    return model.model_validate(_json(value))


class ORRepository:
    """Use with ``with engine.begin() as connection:``; methods never commit."""

    def __init__(self, connection: sa.Connection):
        if connection.dialect.name != "postgresql":
            raise ValueError("OR persistence requires PostgreSQL")
        self.connection = connection

    def audit(
        self,
        organization_id: UUID,
        actor_id: UUID | None,
        action: str,
        resource_id: UUID | None,
        details: dict | None = None,
    ) -> None:
        self.connection.execute(
            sa.insert(AuditEvent).values(
                id=uuid4(),
                organization_id=organization_id,
                actor_id=actor_id,
                action=action,
                resource_id=resource_id,
                details=details or {},
            )
        )

    def get(self, model, organization_id: UUID, record_id: UUID) -> dict[str, Any]:
        row = (
            self.connection.execute(
                sa.select(model.__table__).where(
                    model.organization_id == organization_id,
                    model.id == record_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ORStorageError("NOT_FOUND")
        result = dict(row)
        if model is InputPackageRecord:
            payload = _validated(ORInputPackage, result["payload"])
            if operational_hash(payload) != result["content_hash"]:
                raise ORStorageError("INPUT_HASH_MISMATCH")
        elif model is PolicyRecord:
            payload = _validated(ORPolicy, result["payload"])
            if operational_hash(payload) != result["content_hash"]:
                raise ORStorageError("POLICY_HASH_MISMATCH")
        elif model is ScenarioRecord:
            payload = _validated(ORScenarioPayload, result["payload"])
            verify_scenario(payload)
            if (
                payload.operational_hash != result["operational_hash"]
                or payload.policy_hash != result["policy_hash"]
            ):
                raise ORStorageError("SCENARIO_HASH_MISMATCH")
        elif model is PlanRecord and sha256_hex(result["result"]) != result["result_hash"]:
            raise ORStorageError("RESULT_HASH_MISMATCH")
        return result

    def request_key(
        self,
        organization_id: UUID,
        actor_id: UUID,
        operation: str,
        key: str,
        request_hash: str,
        resource_id: UUID,
    ) -> UUID:
        """Unique insert resolves races; mismatched key reuse is always a conflict."""
        table = RequestKey.__table__
        inserted = self.connection.execute(
            insert(table)
            .values(
                id=uuid4(),
                organization_id=organization_id,
                actor_id=actor_id,
                route_operation=operation,
                key=key,
                request_hash=request_hash,
                job_or_resource_id=resource_id,
            )
            .on_conflict_do_nothing(constraint="uq_or_request_key")
            .returning(table.c.id)
        ).scalar()
        if inserted:
            return resource_id
        row = (
            self.connection.execute(
                sa.select(table).where(
                    table.c.organization_id == organization_id,
                    table.c.actor_id == actor_id,
                    table.c.route_operation == operation,
                    table.c.key == key,
                )
            )
            .mappings()
            .one()
        )
        if row["request_hash"] != request_hash:
            raise ORStorageError("IDEMPOTENCY_CONFLICT")
        return row["job_or_resource_id"]

    def _dedup(self, model, values: dict, constraint: str, criteria: list) -> tuple[dict, bool]:
        table = model.__table__
        row = (
            self.connection.execute(
                insert(table)
                .values(**values)
                .on_conflict_do_nothing(constraint=constraint)
                .returning(table)
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            return dict(row), True
        row = self.connection.execute(sa.select(table).where(*criteria)).mappings().one()
        return dict(row), False

    def put_package(
        self,
        payload: ORInputPackage | Mapping,
        actor_id: UUID,
        *,
        expected_revision: str | None = None,
        trusted_live: bool = False,
        demo_scope: bool = False,
    ) -> dict:
        package = _validated(ORInputPackage, payload)
        if package.source_kind == "LIVE" and not trusted_live:
            raise ORStorageError("SOURCE_INTEGRATION_UNAVAILABLE")
        if operational_hash(package.source_refs) != package.source_manifest_hash:
            raise ORStorageError("SOURCE_MANIFEST_HASH_MISMATCH")
        content_hash = operational_hash(package)
        # OR-DEC-020 [PROVISIONAL]: explicit simulated publication, no inventory ledger.
        state = DatasetState.__table__
        self.connection.execute(
            insert(state)
            .values(
                organization_id=package.organization_id,
                dataset_id=package.dataset_id,
                revision_token=package.source_revision_token,
                org_epoch=0,
                is_demo=demo_scope,
            )
            .on_conflict_do_nothing()
        )
        current = (
            self.connection.execute(
                sa.select(state)
                .where(
                    state.c.organization_id == package.organization_id,
                    state.c.dataset_id == package.dataset_id,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        if current["revision_token"] != package.source_revision_token:
            if current["revision_token"] != expected_revision:
                raise ORStorageError("SOURCE_REVISION_MISMATCH")
            self.connection.execute(
                sa.update(state)
                .where(
                    state.c.organization_id == package.organization_id,
                    state.c.dataset_id == package.dataset_id,
                )
                .values(revision_token=package.source_revision_token)
            )
        row, added = self._dedup(
            InputPackageRecord,
            dict(
                id=uuid4(),
                organization_id=package.organization_id,
                dataset_id=package.dataset_id,
                schema_version=package.schema_version,
                source_kind=package.source_kind,
                revision_token=package.source_revision_token,
                payload=_json(package),
                content_hash=content_hash,
                source_manifest_hash=package.source_manifest_hash,
                created_by=actor_id,
            ),
            "uq_or_package_content",
            [
                InputPackageRecord.organization_id == package.organization_id,
                InputPackageRecord.dataset_id == package.dataset_id,
                InputPackageRecord.content_hash == content_hash,
            ],
        )
        if added:
            self.audit(package.organization_id, actor_id, "OR_PACKAGE_CREATED", row["id"])
        return row

    def put_policy(
        self, organization_id: UUID, payload: ORPolicy | Mapping, actor_id: UUID
    ) -> dict:
        policy = _validated(ORPolicy, payload)
        content_hash = operational_hash(policy)
        row, added = self._dedup(
            PolicyRecord,
            dict(
                id=uuid4(),
                organization_id=organization_id,
                version=policy.version,
                payload=_json(policy),
                content_hash=content_hash,
                decision_ids=list(policy.decision_ids),
                created_by=actor_id,
            ),
            "uq_or_policy_content",
            [
                PolicyRecord.organization_id == organization_id,
                PolicyRecord.content_hash == content_hash,
            ],
        )
        if added:
            self.audit(organization_id, actor_id, "OR_POLICY_CREATED", row["id"])
        return row

    def put_scenario(
        self,
        payload: ORScenarioPayload | Mapping,
        input_package_id: UUID,
        policy_id: UUID,
        actor_id: UUID,
        *,
        expected_revision: str | None = None,
    ) -> dict:
        scenario = _validated(ORScenarioPayload, payload)
        verify_scenario(scenario)
        org = scenario.package.organization_id
        package = self.get(InputPackageRecord, org, input_package_id)
        policy = self.get(PolicyRecord, org, policy_id)
        if (
            package["content_hash"] != operational_hash(scenario.package)
            or policy["content_hash"] != scenario.policy_hash
        ):
            raise ORStorageError("SNAPSHOT_SOURCE_MISMATCH")
        state = DatasetState.__table__
        current = (
            self.connection.execute(
                sa.select(state)
                .where(
                    state.c.organization_id == org,
                    state.c.dataset_id == scenario.package.dataset_id,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        # OR-DEC-015 [PROVISIONAL]: replay freezes old facts; current requires exact revision.
        if scenario.intent == "CURRENT" and (
            expected_revision != current["revision_token"]
            or expected_revision != scenario.package.source_revision_token
        ):
            raise ORStorageError("SOURCE_REVISION_MISMATCH")
        row, added = self._dedup(
            ScenarioRecord,
            dict(
                id=uuid4(),
                organization_id=org,
                input_package_id=input_package_id,
                policy_id=policy_id,
                schema_version=scenario.schema_version,
                transfer_mode=scenario.transfer_mode.value,
                planning_days=scenario.planning_days,
                intent=scenario.intent,
                revision_token=scenario.package.source_revision_token,
                org_epoch=current["org_epoch"],
                payload=_json(scenario),
                operational_hash=scenario.operational_hash,
                policy_hash=scenario.policy_hash,
                created_by=actor_id,
            ),
            "uq_or_scenario_content",
            [
                ScenarioRecord.organization_id == org,
                ScenarioRecord.operational_hash == scenario.operational_hash,
                ScenarioRecord.policy_hash == scenario.policy_hash,
                ScenarioRecord.org_epoch == current["org_epoch"],
            ],
        )
        if added:
            self.audit(org, actor_id, "OR_SCENARIO_CREATED", row["id"])
        return row

    def assert_current(self, scenario_row: Mapping, *, lock: bool = True) -> dict:
        scenario = _validated(ORScenarioPayload, scenario_row["payload"])
        verify_scenario(scenario)
        table = DatasetState.__table__
        query = sa.select(table).where(
            table.c.organization_id == scenario_row["organization_id"],
            table.c.dataset_id == scenario.package.dataset_id,
        )
        if lock:
            query = query.with_for_update()
        current = dict(self.connection.execute(query).mappings().one())
        if current["org_epoch"] != scenario_row["org_epoch"]:
            raise ORStorageError("DATASET_EPOCH_MISMATCH")
        if (
            scenario.intent == "CURRENT"
            and current["revision_token"] != scenario_row["revision_token"]
        ):
            raise ORStorageError("SOURCE_REVISION_MISMATCH")
        return current

    def publish_plan(
        self, identity: PublicationIdentity, scenario_id: UUID, outcome: MethodOutcome | Mapping
    ) -> dict:
        """Called only inside shared-queue locked publication; parent checks again here."""
        outcome = _validated(MethodOutcome, outcome)
        # PublicationIdentity alone is never authority; require the shared lane's current
        # live attempt under its existing row lock, including the parent's deadline.
        from app.models.jobs import compute_attempts, compute_control, compute_jobs

        job = (
            self.connection.execute(
                sa.select(compute_jobs).where(
                    compute_jobs.c.job_id == identity.job_id,
                    compute_jobs.c.organization_id == identity.organization_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if job is None:
            raise PublicationRejected("OR_PUBLICATION_FENCED")
        control = (
            self.connection.execute(
                sa.select(compute_control)
                .where(compute_control.c.lane_id == job["lane_id"])
                .with_for_update()
            )
            .mappings()
            .one()
        )
        attempt = (
            self.connection.execute(
                sa.select(compute_attempts)
                .where(
                    compute_attempts.c.attempt_id == identity.attempt_id,
                    compute_attempts.c.job_id == identity.job_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        now = self.connection.scalar(sa.text("SELECT clock_timestamp()"))
        if (
            attempt is None
            or job["current_attempt_id"] != identity.attempt_id
            or job["input_sha256"] != identity.input_sha256
            or job["handler_contract"] != identity.handler_contract
            or attempt["state"] != "RUNNING"
            or attempt["stop_requested_at"] is not None
            or attempt["execution_deadline_at"] is None
            or now >= attempt["execution_deadline_at"]
            or control["active_attempt_id"] != identity.attempt_id
            or control["supervisor_id"] != attempt["supervisor_id"]
            or control["generation"] != attempt["supervisor_generation"]
        ):
            raise PublicationRejected("OR_PUBLICATION_FENCED")
        scenario_row = self.get(ScenarioRecord, identity.organization_id, scenario_id)
        self.assert_current(scenario_row)
        scenario = _validated(ORScenarioPayload, scenario_row["payload"])
        if (
            outcome.outcome != "VERIFIED"
            or outcome.operational_hash != scenario.operational_hash
            or outcome.policy_hash != scenario.policy_hash
            or outcome.transfer_mode != scenario.transfer_mode
        ):
            raise PublicationRejected("OR_RESULT_IDENTITY_MISMATCH")
        # The parent never trusts a child's passed flag or self-reported metrics.
        from app.services.optimization.candidates import prepare_problem
        from app.services.optimization.verify import verify

        report = verify(prepare_problem(scenario), outcome.candidate, outcome.method)
        if not report.passed or report != outcome.verification:
            raise PublicationRejected("OR_INDEPENDENT_CHECK_FAILED")
        objective = (
            report.metrics.classical_objective
            if outcome.method.value == "CLASSICAL_GP"
            else report.metrics.research_objective
        )
        if outcome.objective != objective:
            raise PublicationRejected("OR_OBJECTIVE_MISMATCH")
        now = self.connection.scalar(sa.text("SELECT clock_timestamp()"))
        result = _json(outcome)
        plan_id = uuid4()
        values = dict(
            id=plan_id,
            organization_id=identity.organization_id,
            scenario_id=scenario_id,
            job_id=identity.job_id,
            attempt_id=identity.attempt_id,
            method=outcome.method.value,
            native_status=outcome.native_status,
            outcome="VERIFIED",
            settings_hash=outcome.settings_hash,
            result=result,
            result_hash=sha256_hex(result),
            verified_at=now,
        )
        self.connection.execute(sa.insert(PlanRecord).values(**values))
        for line in outcome.candidate.assignments:
            if not line.units:
                continue
            self.connection.execute(
                sa.insert(TransferRecord).values(
                    id=uuid4(),
                    organization_id=identity.organization_id,
                    plan_id=plan_id,
                    original_lot_id=line.original_lot_id,
                    source_id=line.source_id,
                    destination_id=line.destination_id,
                    product_id=line.product_id,
                    unit=line.unit,
                    quantity=line.units,
                    departure_date=line.departure,
                    arrival_date=line.arrival,
                    expiry_date=line.expires_on,
                    source_revision=line.source_revision,
                    cost_minor=line.cost_minor,
                )
            )
        report_json = _json(report)
        self.connection.execute(
            sa.insert(VerificationRecord).values(
                id=uuid4(),
                organization_id=identity.organization_id,
                plan_id=plan_id,
                verifier_version=report.verifier_version,
                passed=True,
                checks=report_json,
                objective=_json(objective),
                report_hash=sha256_hex(report_json),
            )
        )
        self.audit(
            identity.organization_id,
            None,
            "OR_PLAN_PUBLISHED",
            plan_id,
            {"job_id": str(identity.job_id), "method": outcome.method.value},
        )
        return self.get(PlanRecord, identity.organization_id, plan_id)

    def publish_comparison(
        self,
        identity: PublicationIdentity,
        scenario_id: UUID,
        *,
        first_plan_id: UUID | None,
        second_plan_id: UUID | None,
        payload: Mapping,
    ) -> dict:
        scenario_row = self.get(ScenarioRecord, identity.organization_id, scenario_id)
        self.assert_current(scenario_row)
        comparison = _validated(ComparisonResult, payload)
        scenario = _validated(ORScenarioPayload, scenario_row["payload"])
        if (
            comparison.operational_hash != scenario.operational_hash
            or comparison.transfer_mode != scenario.transfer_mode
        ):
            raise PublicationRejected("OR_COMPARISON_IDENTITY_MISMATCH")
        if tuple(m.method.value for m in comparison.methods) != ("CLASSICAL_GP", "EGP_PI_INSPIRED"):
            raise PublicationRejected("OR_COMPARISON_METHOD_MISMATCH")
        for plan_id, method in zip(
            (first_plan_id, second_plan_id), comparison.methods, strict=True
        ):
            if (plan_id is not None) != (method.outcome == "VERIFIED"):
                raise PublicationRejected("OR_COMPARISON_COMPLETENESS_MISMATCH")
            if plan_id is not None:
                plan = self.get(PlanRecord, identity.organization_id, plan_id)
                if (
                    plan["result_hash"] != sha256_hex(_json(method))
                    or plan["scenario_id"] != scenario_id
                    or plan["attempt_id"] != identity.attempt_id
                ):
                    raise PublicationRejected("OR_COMPARISON_PLAN_MISMATCH")
        outcome = (
            "SUCCEEDED"
            if first_plan_id and second_plan_id
            else "PARTIAL"
            if first_plan_id or second_plan_id
            else "FAILED"
        )
        if comparison.outcome != outcome:
            raise PublicationRejected("OR_COMPARISON_COMPLETENESS_MISMATCH")
        table = ComparisonRecord.__table__
        record_id = uuid4()
        self.connection.execute(
            sa.insert(table).values(
                id=record_id,
                organization_id=identity.organization_id,
                job_id=identity.job_id,
                attempt_id=identity.attempt_id,
                scenario_id=scenario_id,
                first_plan_id=first_plan_id,
                second_plan_id=second_plan_id,
                outcome=outcome,
                payload=_json(comparison),
            )
        )
        self.audit(identity.organization_id, None, "OR_COMPARISON_PUBLISHED", record_id)
        return self.get(ComparisonRecord, identity.organization_id, record_id)

    def review(
        self,
        organization_id: UUID,
        plan_id: UUID,
        actor_id: UUID,
        action: str,
        result_hash: str,
        note: str | None = None,
    ) -> dict:
        plan = self.get(PlanRecord, organization_id, plan_id)
        if result_hash != plan["result_hash"]:
            raise ORStorageError("RESULT_REVISION_MISMATCH")
        table = ReviewRecord.__table__
        row = (
            self.connection.execute(
                sa.insert(table)
                .values(
                    id=uuid4(),
                    organization_id=organization_id,
                    plan_id=plan_id,
                    actor_id=actor_id,
                    action=action,
                    note=note,
                    plan_result_hash=result_hash,
                )
                .returning(table)
            )
            .mappings()
            .one()
        )
        self.audit(
            organization_id,
            actor_id,
            "OR_PLAN_REVIEWED",
            row["id"],
            {"plan_id": str(plan_id), "action": action},
        )
        return dict(row)

    def reset_demo(self, organization_id: UUID, dataset_id: UUID, actor_id: UUID) -> int:
        """Fence a dedicated isolated dataset and preserve append-only history.

        Supervisor must stop/reap active work before reset. This method locks the same
        compute control row first; a running dataset's reset is rejected pending cleanup.
        """
        from app.models.jobs import compute_attempts, compute_control, compute_jobs

        self.connection.execute(
            sa.select(compute_control)
            .where(compute_control.c.lane_id == "default")
            .with_for_update()
        ).mappings().one()
        jobs = (
            self.connection.execute(
                sa.select(compute_jobs.c.input_package, compute_attempts.c.state)
                .join(
                    compute_attempts,
                    compute_attempts.c.attempt_id == compute_jobs.c.current_attempt_id,
                )
                .where(
                    compute_jobs.c.organization_id == organization_id,
                    compute_jobs.c.input_package["input"]["scenario"]["package"][
                        "dataset_id"
                    ].astext
                    == str(dataset_id),
                    compute_attempts.c.state.in_(["RUNNING", "STOPPING", "QUEUED"]),
                )
            )
            .mappings()
            .all()
        )
        if jobs:
            raise ORStorageError("DEMO_RESET_REQUIRES_QUIESCENT_SCOPE")
        table = DatasetState.__table__
        row = (
            self.connection.execute(
                sa.select(table)
                .where(
                    table.c.organization_id == organization_id,
                    table.c.dataset_id == dataset_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None or not row["is_demo"]:
            raise ORStorageError("DEMO_SCOPE_REQUIRED")
        epoch = row["org_epoch"] + 1
        self.connection.execute(
            sa.update(table)
            .where(
                table.c.organization_id == organization_id,
                table.c.dataset_id == dataset_id,
            )
            .values(org_epoch=epoch)
        )
        self.audit(
            organization_id,
            actor_id,
            "OR_DEMO_RESET",
            dataset_id,
            {"old_epoch": row["org_epoch"], "new_epoch": epoch, "history_retained": True},
        )
        return epoch
