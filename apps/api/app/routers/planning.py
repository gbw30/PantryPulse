"""Saved allocation workflows on the shared presenter/session and durable queue."""

from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter

from app.models import operational as operational
from app.models.or_records import (
    ComparisonRecord,
    InputPackageRecord,
    PlanRecord,
    PolicyRecord,
    ScenarioRecord,
)
from app.repositories.operations_api import journal, wire
from app.repositories.or_repository import ORRepository, ORStorageError
from app.repositories.planning_sources import assert_sources, capture
from app.routers.forecasts import PRESENTER, RUNTIME
from app.routers.operations import CSRF, Key, write
from app.schemas.forecast_api import ErrorEnvelope, ForecastAccepted
from app.schemas.operations_api import CommandResult
from app.schemas.or_http import PairSubmit, PlanSubmit, ReviewRequest, ScenarioCreate
from app.schemas.or_inputs import ORInputPackage, ORPolicy, ORScenarioPayload
from app.schemas.planning_api import CaptureRequest
from app.services.inventory.stock import StockError
from app.services.optimization.canonical import operational_hash
from app.services.optimization.decisions import DECISION_IDS, POLICY_VERSION
from app.services.optimization.scenario import freeze_scenario
from app.services.optimization.settings import DEFAULT_SETTINGS

router = APIRouter(prefix="/api/v1", tags=["allocation"], responses={
    code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 422, 503)
})


def saved(rt, scope, operation, key, body, create):
    return write(
        rt,
        lambda session: journal(
            session,
            scope,
            operation,
            key,
            body.model_dump(mode="json"),
            lambda: create(session.connection()),
        ),
    )


@router.get("/allocation-methodology")
def methodology(scope=PRESENTER):
    return dict(
        transfer_modes=["HUB_ONLY", "HUB_AND_PANTRY"],
        methods=["CLASSICAL_GP", "EGP_PI_INSPIRED"],
        default_transfer_mode=None,
        policy_version=POLICY_VERSION,
        decision_ids=DECISION_IDS,
        expiry="usable through stated local expiry date",
        donor_protection_days=7,
        planning_window_days=[1, 2, 3],
        stock_effect="NONE_SIMULATION_ONLY",
        limitations=[
            "Fixed route loading order restricts the feasible region",
            "Coefficients must be supplied explicitly; no research-policy defaults",
        ],
    )


@router.post("/or/input-packages", response_model=CommandResult, status_code=201)
def simulated_package(
    body: ORInputPackage, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    if body.organization_id != scope.organization_id:
        raise StockError("ORGANIZATION_FORBIDDEN", 403)
    if body.source_kind != "SIMULATED":
        raise StockError("USE_VERIFIED_SOURCE_CAPTURE", 422)

    def create(conn):
        demo = conn.scalar(
            sa.select(operational.Organization.is_demo).where(
                operational.Organization.id == scope.organization_id
            )
        )
        if not demo:
            raise StockError("SIMULATED_PACKAGE_REQUIRES_DEMO_SCOPE", 403)
        row = ORRepository(conn).put_package(body, UUID(str(scope.actor_ref)), demo_scope=True)
        return dict(id=row["id"], content_hash=row["content_hash"])

    return saved(rt, scope, "or-package-create", idempotency_key, body, create)


@router.post("/or/input-packages/from-sources", response_model=CommandResult, status_code=201)
def source_package(
    body: CaptureRequest, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    # Serialize API source writes during capture, and freeze all reads in this transaction.
    def create(conn):
        package = capture(conn, scope.organization_id, body)
        row = ORRepository(conn).put_package(
            package,
            UUID(str(scope.actor_ref)),
            trusted_live=True,
            expected_revision=body.expected_source_revision,
        )
        return dict(
            id=row["id"],
            content_hash=row["content_hash"],
            source_revision=package.source_revision_token,
        )

    return saved(rt, scope, "or-source-capture", idempotency_key, body, create)


def record(rt, scope, model, identity):
    with rt.engine.connect() as conn:
        row = ORRepository(conn).get(model, scope.organization_id, identity)
        if model in (ScenarioRecord, PlanRecord, ComparisonRecord):
            scenario = (
                row
                if model is ScenarioRecord
                else ORRepository(conn).get(
                    ScenarioRecord, scope.organization_id, row["scenario_id"]
                )
            )
            package = ORScenarioPayload.model_validate(scenario["payload"]).package
            try:
                ORRepository(conn).assert_current(scenario, lock=False)
                assert_sources(conn, package)
                row["stale"] = False
            except (ORStorageError, StockError):
                row["stale"] = True
            row["historical"] = scenario["intent"] == "HISTORICAL_REPLAY"
        result = wire(row)
        # OR input/policy values are explicitly bounded safe JSON integers. Preserve
        # their request schema on reads; unrestricted result metrics use exact strings.
        if "payload" in row:
            result["payload"] = row["payload"]
        return result


@router.get("/or/input-packages/{record_id}")
def package_read(record_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return record(rt, scope, InputPackageRecord, record_id)


@router.post("/or/policies", response_model=CommandResult, status_code=201)
def create_policy(body: ORPolicy, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER):
    return saved(
        rt,
        scope,
        "or-policy-create",
        idempotency_key,
        body,
        lambda conn: {
            key: value
            for key, value in ORRepository(conn)
            .put_policy(scope.organization_id, body, UUID(str(scope.actor_ref)))
            .items()
            if key in {"id", "content_hash"}
        },
    )


@router.get("/or/policies/{record_id}")
def policy_read(record_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return record(rt, scope, PolicyRecord, record_id)


@router.post("/scenarios", response_model=CommandResult, status_code=201)
def create_scenario(
    body: ScenarioCreate, idempotency_key: Key, csrf: CSRF, rt=RUNTIME, scope=PRESENTER
):
    def create(conn):
        repo = ORRepository(conn)
        package = ORInputPackage.model_validate(
            repo.get(InputPackageRecord, scope.organization_id, body.input_package_id)["payload"]
        )
        policy = ORPolicy.model_validate(
            repo.get(PolicyRecord, scope.organization_id, body.policy_id)["payload"]
        )
        if body.intent == "CURRENT":
            assert_sources(conn, package)
        try:
            scenario = freeze_scenario(
                package,
                policy,
                transfer_mode=body.transfer_mode,
                planning_days=body.planning_days,
                modifiers=body.modifiers,
                intent=body.intent,
                expected_source_revision=body.expected_source_revision,
            )
        except ValueError:
            raise StockError("INVALID_SCENARIO", 422) from None
        row = repo.put_scenario(
            scenario,
            body.input_package_id,
            body.policy_id,
            UUID(str(scope.actor_ref)),
            expected_revision=body.expected_source_revision,
        )
        return dict(
            id=row["id"],
            operational_hash=row["operational_hash"],
            transfer_mode=row["transfer_mode"],
        )

    return saved(rt, scope, "scenario-create", idempotency_key, body, create)


@router.get("/scenarios/{record_id}")
def scenario_read(record_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return record(rt, scope, ScenarioRecord, record_id)


@router.get("/scenarios")
def scenarios(rt=RUNTIME, scope=PRESENTER):
    with rt.engine.connect() as conn:
        ids = list(
            conn.scalars(
                sa.select(ScenarioRecord.id)
                .where(
                    ScenarioRecord.organization_id == scope.organization_id,
                )
                .order_by(ScenarioRecord.created_at.desc())
                .limit(101)
            )
        )
    if len(ids) > 100:
        raise StockError("SCENARIO_LIST_TOO_LARGE", 422)
    return dict(scenarios=[record(rt, scope, ScenarioRecord, identity) for identity in ids])


def submit(rt, scope, scenario_id, body, key, method):
    with rt.engine.begin() as conn:
        row = ORRepository(conn).get(ScenarioRecord, scope.organization_id, scenario_id)
        ORRepository(conn).assert_current(row)
        scenario = ORScenarioPayload.model_validate(row["payload"])
        if row["operational_hash"] != body.expected_scenario_hash or row["intent"] != body.intent:
            raise StockError("SCENARIO_REVISION_MISMATCH")
        if scenario.intent == "CURRENT":
            assert_sources(conn, scenario.package)
    accepted = rt.queue.submit(
        scope,
        "or-allocation-v1" if method else "or-comparison-v1",
        dict(
            scenario_id=str(scenario_id),
            scenario=scenario.model_dump(mode="json"),
            settings=DEFAULT_SETTINGS,
            method=method,
            org_epoch=row["org_epoch"],
        ),
        operational_hash(dict(actor=str(scope.actor_ref), key=key)),
    )
    return ForecastAccepted(
        job_id=accepted.job_id,
        attempt_id=accepted.attempt_id,
        state=accepted.state,
        replayed=accepted.replayed,
        status_url=f"/api/v1/jobs/{accepted.job_id}",
        result_url=f"/api/v1/allocation-jobs/{accepted.job_id}/results",
    )


@router.post("/scenarios/{scenario_id}/plans", response_model=ForecastAccepted, status_code=202)
def plan(
    scenario_id: UUID,
    body: PlanSubmit,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return submit(rt, scope, scenario_id, body, idempotency_key, body.method.value)


@router.post(
    "/scenarios/{scenario_id}/compare-methods", response_model=ForecastAccepted, status_code=202
)
def compare(
    scenario_id: UUID,
    body: PairSubmit,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return submit(rt, scope, scenario_id, body, idempotency_key, None)


@router.get("/plans/{record_id}")
def plan_read(record_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return record(rt, scope, PlanRecord, record_id)


@router.get("/comparisons/{record_id}")
def comparison_read(record_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return record(rt, scope, ComparisonRecord, record_id)


@router.get("/allocation-jobs/{job_id}/results")
def allocation_results(job_id: UUID, rt=RUNTIME, scope=PRESENTER):
    job = rt.queue.get_job(scope, job_id)
    if job.handler_contract not in {"or-allocation-v1", "or-comparison-v1"}:
        raise StockError("NOT_FOUND", 404)
    with rt.engine.connect() as conn:
        plans = list(
            conn.scalars(
                sa.select(PlanRecord.id).where(
                    PlanRecord.organization_id == scope.organization_id, PlanRecord.job_id == job_id
                )
            )
        )
        comparisons = list(
            conn.scalars(
                sa.select(ComparisonRecord.id).where(
                    ComparisonRecord.organization_id == scope.organization_id,
                    ComparisonRecord.job_id == job_id,
                )
            )
        )
    return dict(
        state=job.state,
        plans=[record(rt, scope, PlanRecord, identity) for identity in plans],
        comparisons=[record(rt, scope, ComparisonRecord, identity) for identity in comparisons],
    )


@router.post("/plans/{plan_id}/review", response_model=CommandResult, status_code=201)
def review(
    plan_id: UUID,
    body: ReviewRequest,
    idempotency_key: Key,
    csrf: CSRF,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return saved(
        rt,
        scope,
        f"plan-review:{plan_id}",
        idempotency_key,
        body,
        lambda conn: ORRepository(conn).review(
            scope.organization_id,
            plan_id,
            UUID(str(scope.actor_ref)),
            body.action,
            body.expected_result_hash,
            body.note,
        ),
    )
