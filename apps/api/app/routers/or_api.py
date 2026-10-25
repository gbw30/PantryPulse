"""Saved OR reads and presenter-only creation/admission. No compute starts on GET."""

import base64
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Header, Query, Request, Response

from app.models.jobs import compute_jobs
from app.models.or_records import (
    ComparisonRecord,
    DatasetState,
    InputPackageRecord,
    PlanRecord,
    PolicyRecord,
    RequestKey,
    ReviewRecord,
    ScenarioRecord,
)
from app.repositories.jobs import TrustedScope
from app.repositories.or_repository import ORRepository, ORStorageError
from app.schemas.or_http import (
    AttemptSummary,
    ComparisonSummary,
    ErrorResponse,
    JobAccepted,
    JobSummary,
    LoginRequest,
    LoginResponse,
    PackageSummary,
    PairSubmit,
    PlanRef,
    PlanSubmit,
    PlanSummary,
    ResetRequest,
    ResourceCreated,
    ReviewRequest,
    ReviewResponse,
    ScenarioCreate,
    ScenarioSummary,
    SeedRequest,
    SeedResponse,
    SourcePackageRequest,
)
from app.schemas.or_inputs import ORInputPackage, ORPolicy, ORScenarioPayload
from app.schemas.or_outputs import ComparisonResult, MethodOutcome
from app.services.jobs.contracts import sha256_hex
from app.services.optimization.canonical import operational_hash
from app.services.optimization.decisions import DECISION_IDS, DECISION_STATUS, POLICY_VERSION
from app.services.optimization.scenario import freeze_scenario
from app.services.or_access import AccessError, authenticate, login, logout
from app.services.or_runtime import ORRuntime

router = APIRouter(
    prefix="/api/v1",
    tags=["optimization"],
    responses={
        status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 409, 413, 422, 429, 503)
    },
)
Key = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def runtime(request: Request) -> ORRuntime:
    if not hasattr(request.app.state, "or_runtime"):
        request.app.state.or_runtime = ORRuntime.from_environment()
    value = request.app.state.or_runtime
    if value is None:
        raise AccessError("DATABASE_UNAVAILABLE", 503)
    return value


def presenter(request: Request):
    active = runtime(request)
    return active, authenticate(request, active, mutation=True)


def _read(request, model, record_id):
    active = runtime(request)
    actor = authenticate(request, active, required=False)
    with active.engine.connect() as conn:
        if actor is not None:
            org = actor.organization_id
        else:
            org = active.public_organization_id
            if org is None:
                raise AccessError("NOT_FOUND", 404)
        row = ORRepository(conn).get(model, org, record_id)
        if model is InputPackageRecord:
            kind = row["source_kind"]
        elif model is PolicyRecord:
            # Policies are safe formula metadata only; no operational payload.
            kind = "SIMULATED"
        else:
            scenario = (
                row
                if model is ScenarioRecord
                else ORRepository(conn).get(ScenarioRecord, org, row["scenario_id"])
            )
            kind = scenario["payload"]["package"]["source_kind"]
        if actor is None and kind != "SIMULATED":
            raise AccessError("NOT_FOUND", 404)
    return active, actor, row


def _stale(conn, scenario):
    current = (
        conn.execute(
            sa.select(DatasetState.__table__).where(
                DatasetState.organization_id == scenario["organization_id"],
                DatasetState.dataset_id == UUID(scenario["payload"]["package"]["dataset_id"]),
            )
        )
        .mappings()
        .one_or_none()
    )
    return (
        current is None
        or current["org_epoch"] != scenario["org_epoch"]
        or current["revision_token"] != scenario["revision_token"]
    )


def _idempotent(conn, actor, operation, key, request_hash, model, create):
    # Domain-create keys have no queue job; reuse a transaction advisory lock to make
    # append-only review and resource creation replay exactly once under races.
    lock_key = f"{actor.organization_id}:{actor.actor_id}:{operation}:{key}"
    conn.execute(sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": lock_key})
    row = (
        conn.execute(
            sa.select(RequestKey.__table__).where(
                RequestKey.organization_id == actor.organization_id,
                RequestKey.actor_id == actor.actor_id,
                RequestKey.route_operation == operation,
                RequestKey.key == key,
            )
        )
        .mappings()
        .one_or_none()
    )
    repo = ORRepository(conn)
    if row is not None:
        if row["request_hash"] != request_hash:
            raise ORStorageError("IDEMPOTENCY_CONFLICT")
        return repo.get(model, actor.organization_id, row["job_or_resource_id"])
    created = create(repo)
    repo.request_key(
        actor.organization_id, actor.actor_id, operation, key, request_hash, created["id"]
    )
    return created


@router.post("/presenter/login", response_model=LoginResponse)
def presenter_login(body: LoginRequest, request: Request, response: Response):
    return login(request, response, runtime(request), body.username, body.password)


@router.get("/presenter/session")
def presenter_session(request: Request):
    actor = authenticate(request, runtime(request), required=False)
    return {
        "authenticated": actor is not None,
        "actor_id": str(actor.actor_id) if actor else None,
        "organization_id": str(actor.organization_id) if actor else None,
    }


@router.post("/presenter/logout")
def presenter_logout(request: Request, response: Response):
    return logout(request, response, runtime(request))


@router.post("/or/input-packages", response_model=ResourceCreated, status_code=201)
def create_package(
    body: ORInputPackage,
    request: Request,
    idempotency_key: Key,
    expected_revision: Annotated[str | None, Header(alias="X-Expected-Revision")] = None,
):
    active, actor = presenter(request)
    if body.organization_id != actor.organization_id:
        raise AccessError("ORGANIZATION_FORBIDDEN", 403)
    with active.engine.begin() as conn:
        row = _idempotent(
            conn,
            actor,
            "package-create",
            idempotency_key,
            operational_hash({"package": body, "expected_revision": expected_revision}),
            InputPackageRecord,
            lambda repo: repo.put_package(
                body, actor.actor_id, expected_revision=expected_revision
            ),
        )
    return {"id": row["id"], "content_hash": row["content_hash"]}


@router.post("/or/input-packages/from-sources", response_model=ResourceCreated, status_code=201)
def package_from_sources(body: SourcePackageRequest, request: Request, idempotency_key: Key):
    _, actor = presenter(request)
    if body.organization_id != actor.organization_id:
        raise AccessError("ORGANIZATION_FORBIDDEN", 403)
    raise AccessError("SOURCE_INTEGRATION_UNAVAILABLE", 503)


@router.get("/or/input-packages/{record_id}", response_model=PackageSummary)
def package_read(record_id: UUID, request: Request):
    _, actor, row = _read(request, InputPackageRecord, record_id)
    return {
        **{k: row[k] for k in PackageSummary.model_fields if k != "payload"},
        "payload": row["payload"] if actor else None,
    }


@router.post("/or/policies", response_model=ResourceCreated, status_code=201)
def create_policy(body: ORPolicy, request: Request, idempotency_key: Key):
    active, actor = presenter(request)
    with active.engine.begin() as conn:
        row = _idempotent(
            conn,
            actor,
            "policy-create",
            idempotency_key,
            operational_hash(body),
            PolicyRecord,
            lambda repo: repo.put_policy(actor.organization_id, body, actor.actor_id),
        )
    return {"id": row["id"], "content_hash": row["content_hash"]}


@router.get("/or/policies/{record_id}", response_model=ORPolicy)
def policy_read(record_id: UUID, request: Request):
    return _read(request, PolicyRecord, record_id)[2]["payload"]


@router.post("/scenarios", response_model=ScenarioSummary, status_code=201)
def create_scenario(body: ScenarioCreate, request: Request, idempotency_key: Key):
    active, actor = presenter(request)
    with active.engine.begin() as conn:

        def create(repo):
            package = ORInputPackage.model_validate(
                repo.get(InputPackageRecord, actor.organization_id, body.input_package_id)[
                    "payload"
                ]
            )
            policy = ORPolicy.model_validate(
                repo.get(PolicyRecord, actor.organization_id, body.policy_id)["payload"]
            )
            scenario = freeze_scenario(
                package,
                policy,
                transfer_mode=body.transfer_mode,
                planning_days=body.planning_days,
                modifiers=body.modifiers,
                intent=body.intent,
                expected_source_revision=body.expected_source_revision,
            )
            return repo.put_scenario(
                scenario,
                body.input_package_id,
                body.policy_id,
                actor.actor_id,
                expected_revision=body.expected_source_revision,
            )

        row = _idempotent(
            conn,
            actor,
            "scenario-create",
            idempotency_key,
            operational_hash(body),
            ScenarioRecord,
            create,
        )
    return _scenario_summary(active, row)


def _scenario_summary(active, row):
    scenario = ORScenarioPayload.model_validate(row["payload"])
    with active.engine.connect() as conn:
        stale = _stale(conn, row)
    return {
        **{
            k: row[k]
            for k in (
                "id",
                "organization_id",
                "input_package_id",
                "policy_id",
                "transfer_mode",
                "planning_days",
                "intent",
                "operational_hash",
                "policy_hash",
                "revision_token",
                "created_at",
            )
        },
        "source_kind": scenario.package.source_kind,
        "historical": scenario.intent == "HISTORICAL_REPLAY",
        "stale": stale,
        "decision_ids": scenario.decision_ids,
        "sites": [{"id": s.id, "name": s.name} for s in scenario.package.sites],
        "products": [{"id": p.id, "unit": p.unit} for p in scenario.package.products],
    }


@router.get("/scenarios/{record_id}", response_model=ScenarioSummary)
def scenario_read(record_id: UUID, request: Request):
    active, _, row = _read(request, ScenarioRecord, record_id)
    return _scenario_summary(active, row)


def _submit(scenario_id, body, request, key, method):
    active, actor = presenter(request)
    with active.engine.begin() as conn:
        repo = ORRepository(conn)
        row = repo.get(ScenarioRecord, actor.organization_id, scenario_id)
        repo.assert_current(row)
        if row["operational_hash"] != body.expected_scenario_hash or row["intent"] != body.intent:
            raise ORStorageError("SCENARIO_REVISION_MISMATCH")
        scenario = ORScenarioPayload.model_validate(row["payload"])
        if scenario.policy.purpose != "PRIMARY":
            raise AccessError("PRIMARY_POLICY_REQUIRED", 422)
    from app.services.optimization.service import DEFAULT_SETTINGS

    accepted = active.queue.submit(
        TrustedScope(actor.organization_id, str(actor.actor_id)),
        "or-allocation-v1" if method else "or-comparison-v1",
        {
            "scenario_id": str(scenario_id),
            "scenario": scenario.model_dump(mode="json"),
            "settings": DEFAULT_SETTINGS,
            "method": method,
            "org_epoch": row["org_epoch"],
        },
        sha256_hex({"actor_id": str(actor.actor_id), "key": key}),
    )
    return {**asdict(accepted), "status_url": f"/api/v1/jobs/{accepted.job_id}"}


@router.post("/scenarios/{scenario_id}/plans", response_model=JobAccepted, status_code=202)
def submit_plan(scenario_id: UUID, body: PlanSubmit, request: Request, idempotency_key: Key):
    return _submit(scenario_id, body, request, idempotency_key, body.method.value)


@router.post(
    "/scenarios/{scenario_id}/compare-methods", response_model=JobAccepted, status_code=202
)
def submit_pair(scenario_id: UUID, body: PairSubmit, request: Request, idempotency_key: Key):
    return _submit(scenario_id, body, request, idempotency_key, None)


def _job_scope(request, job_id, *, mutation=False):
    active = runtime(request)
    actor = authenticate(request, active, required=mutation, mutation=mutation)
    org = actor.organization_id if actor else active.public_organization_id
    if org is None:
        raise AccessError("NOT_FOUND", 404)
    with active.engine.connect() as conn:
        row = (
            conn.execute(
                sa.select(compute_jobs).where(
                    compute_jobs.c.organization_id == org,
                    compute_jobs.c.job_id == job_id,
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AccessError("NOT_FOUND", 404)
    if actor is None:
        data = row["input_package"].get("input", {}).get("scenario", {})
        if data.get("package", {}).get("source_kind") != "SIMULATED":
            raise AccessError("NOT_FOUND", 404)
    return active, actor, TrustedScope(org, str(actor.actor_id) if actor else "visitor")


@router.get("/jobs/{job_id}", response_model=JobSummary)
def job_read(job_id: UUID, request: Request):
    active, _, scope = _job_scope(request, job_id)
    job = active.queue.get_job(scope, job_id)
    with active.engine.connect() as conn:
        plans = (
            conn.execute(
                sa.select(PlanRecord.__table__)
                .where(
                    PlanRecord.organization_id == scope.organization_id,
                    PlanRecord.job_id == job_id,
                )
                .order_by(PlanRecord.created_at, PlanRecord.id)
            )
            .mappings()
            .all()
        )
        comparison = conn.execute(
            sa.select(ComparisonRecord.id)
            .where(
                ComparisonRecord.organization_id == scope.organization_id,
                ComparisonRecord.job_id == job_id,
            )
            .order_by(ComparisonRecord.created_at.desc())
        ).scalar()
    refs = tuple(
        PlanRef(plan_id=p["id"], method=p["method"], result_hash=p["result_hash"]) for p in plans
    )
    latest = [p for p in plans if p["attempt_id"] == job.current_attempt_id]
    pair = job.operation_kind.value == "COMPARISON"
    completeness = (
        "TWO_OF_TWO"
        if len(latest) == 2
        else "ONE_OF_TWO"
        if latest and pair
        else "ONE_OF_ONE"
        if latest
        else "NONE"
    )
    return JobSummary(
        job_id=job.job_id,
        state=job.state.value,
        result_completeness=completeness,
        plans=refs,
        comparison_id=comparison,
        attempts=tuple(
            AttemptSummary(
                attempt_id=a.attempt_id,
                attempt_number=a.attempt_number,
                state=a.state.value,
                reason_code=a.reason_code,
                enqueued_at=a.enqueued_at,
                started_at=a.started_at,
                completed_at=a.completed_at,
            )
            for a in job.attempts
        ),
        error_code=job.attempts[-1].reason_code if job.attempts else None,
        status_url=f"/api/v1/jobs/{job.job_id}",
    )


@router.post("/jobs/{job_id}/cancel", status_code=202)
def job_cancel(job_id: UUID, request: Request, idempotency_key: Key):
    active, _, scope = _job_scope(request, job_id, mutation=True)
    return asdict(
        active.queue.cancel(
            scope, job_id, sha256_hex({"actor_id": scope.actor_ref, "key": idempotency_key})
        )
    )


@router.post("/jobs/{job_id}/retry", response_model=JobAccepted, status_code=202)
def job_retry(job_id: UUID, request: Request, idempotency_key: Key):
    active, _, scope = _job_scope(request, job_id, mutation=True)
    with active.engine.connect() as conn:
        payload = conn.execute(
            sa.select(compute_jobs.c.input_package).where(compute_jobs.c.job_id == job_id)
        ).scalar_one()["input"]
        scenario = ORRepository(conn).get(
            ScenarioRecord, scope.organization_id, UUID(payload["scenario_id"])
        )
        ORRepository(conn).assert_current(scenario, lock=False)
    accepted = active.queue.retry(
        scope, job_id, sha256_hex({"actor_id": scope.actor_ref, "key": idempotency_key})
    )
    return {**asdict(accepted), "status_url": f"/api/v1/jobs/{accepted.job_id}"}


@router.get("/plans/{record_id}", response_model=PlanSummary)
def plan_read(record_id: UUID, request: Request):
    active, _, row = _read(request, PlanRecord, record_id)
    with active.engine.connect() as conn:
        scenario = ORRepository(conn).get(
            ScenarioRecord, row["organization_id"], row["scenario_id"]
        )
        stale = _stale(conn, scenario)
    return PlanSummary(
        id=row["id"],
        scenario_id=row["scenario_id"],
        result_hash=row["result_hash"],
        result=MethodOutcome.model_validate(row["result"]),
        historical=scenario["intent"] == "HISTORICAL_REPLAY",
        stale=stale,
    )


@router.get("/comparisons/{record_id}", response_model=ComparisonSummary)
def comparison_read(record_id: UUID, request: Request):
    active, _, row = _read(request, ComparisonRecord, record_id)
    with active.engine.connect() as conn:
        scenario = ORRepository(conn).get(
            ScenarioRecord, row["organization_id"], row["scenario_id"]
        )
        stale = _stale(conn, scenario)
    return ComparisonSummary(
        id=row["id"],
        scenario_id=row["scenario_id"],
        result=ComparisonResult.model_validate(row["payload"]),
        historical=scenario["intent"] == "HISTORICAL_REPLAY",
        stale=stale,
    )


@router.post("/plans/{plan_id}/review", response_model=ReviewResponse, status_code=201)
def plan_review(plan_id: UUID, body: ReviewRequest, request: Request, idempotency_key: Key):
    active, actor = presenter(request)
    with active.engine.begin() as conn:
        row = _idempotent(
            conn,
            actor,
            f"review:{plan_id}",
            idempotency_key,
            operational_hash(body),
            ReviewRecord,
            lambda repo: repo.review(
                actor.organization_id,
                plan_id,
                actor.actor_id,
                body.action,
                body.expected_result_hash,
                body.note,
            ),
        )

    return {key: row[key] for key in ReviewResponse.model_fields}


@router.get("/allocation-methodology")
def methodology():
    # OR-DEC-013/019 [PROVISIONAL]: bounded adaptation, no numerical per-transfer benefit.
    return {
        "schema_version": "or-methodology-v1",
        "policy_version": POLICY_VERSION,
        "decision_ids": DECISION_IDS,
        "decision_status": DECISION_STATUS,
        "method": "EGP_PI_INSPIRED",
        "doi": "10.1111/itor.70252",
        "published_on": "2026-09-11",
        "source_kind": "SIMULATED",
        "formulation": (
            "Weighted and maximum deficit blend plus strict AP/RP excess, cost and waste"
        ),
        "quantization": "floor(10000 * vulnerability * unmet / target)",
        "classical": "Equal-weight deficits without vulnerability or AP/RP objective terms",
        "loading_policy": "Descending ETA, destination UUID, then eligible FEFO lots",
        "limitations": [
            "Fixed loading order restricts possible assignments",
            "Local adaptation; paper multi-period/endogenous weights are not reproduced",
            "Vulnerability scores and demo inputs are simulated",
            "Native objective values across methods do not establish a universal winner",
            "Transfer rationale has no numerical additive per-transfer benefit",
            "Review has no inventory effect",
            "Quantiles are not calibrated probabilities",
        ],
    }


@router.get("/readiness")
def readiness(request: Request):
    active = runtime(request)
    try:
        with active.engine.connect() as conn:
            installed = conn.scalar(sa.text("SELECT to_regclass('or_scenarios') IS NOT NULL"))
            now = conn.scalar(sa.text("SELECT clock_timestamp()"))
        control = active.queue.control()
        age = (now - control.heartbeat_at).total_seconds() if control.heartbeat_at else None
        compute = bool(
            age is not None
            and age < 15
            and control.state.value == "READY"
            and not control.recovery_required
        )
        return {
            "database": True,
            "schema": bool(installed),
            "compute_available": compute,
            "compute_busy": control.active_attempt_id is not None,
            "heartbeat_age_seconds": age,
        }
    except sa.exc.DBAPIError:
        raise AccessError("DATABASE_UNAVAILABLE", 503) from None


@router.get("/capabilities")
def capabilities():
    return {
        "schema_version": "or-capabilities-v1",
        "allocation_methods": ["CLASSICAL_GP", "EGP_PI_INSPIRED"],
        "transfer_modes": ["HUB_ONLY", "HUB_AND_PANTRY"],
        "simulated_input_publication": True,
        "live_source_integration": False,
        "live_unavailable_code": "SOURCE_INTEGRATION_UNAVAILABLE",
        "chronos_qualified": False,
        "supplier_planning": "PAUSED",
        "inventory_effect": "NONE",
        "decision_ids": DECISION_IDS,
    }


@router.post("/demo/seed", response_model=SeedResponse, status_code=201)
def demo_seed(body: SeedRequest, request: Request, idempotency_key: Key):
    active, actor = presenter(request)
    if body.fixture != "six-beneficiary-v1":
        raise AccessError("PRIMARY_DEMO_FIXTURE_REQUIRED", 422)
    path = Path(__file__).resolve().parents[4] / "data/demo/or-v1" / f"{body.fixture}.snapshot.json"
    raw = ORScenarioPayload.model_validate_json(path.read_text())
    # Rebind fictional identities only to the authorized demo organization.
    data = raw.package.model_dump(mode="json")
    data["organization_id"] = str(actor.organization_id)
    for site in data["sites"]:
        site["organization_id"] = str(actor.organization_id)
    for series in data["forecasts"]:
        series["organization_id"] = str(actor.organization_id)
    package = ORInputPackage.model_validate(data)
    with active.engine.begin() as conn:
        package_row = _idempotent(
            conn,
            actor,
            "demo-package-seed",
            idempotency_key,
            operational_hash(package),
            InputPackageRecord,
            lambda repo: repo.put_package(package, actor.actor_id, demo_scope=True),
        )
        policy_row = ORRepository(conn).put_policy(
            actor.organization_id, raw.policy, actor.actor_id
        )
    return SeedResponse(
        input_package_id=package_row["id"],
        policy_id=policy_row["id"],
        dataset_id=package.dataset_id,
        modifiers=raw.modifiers,
        source_revision_token=package.source_revision_token,
    )


@router.post("/demo/reset")
def demo_reset(body: ResetRequest, request: Request):
    active, actor = presenter(request)
    scope = TrustedScope(actor.organization_id, str(actor.actor_id))
    with active.engine.connect() as conn:
        dataset = (
            conn.execute(
                sa.select(DatasetState.__table__).where(
                    DatasetState.organization_id == actor.organization_id,
                    DatasetState.dataset_id == body.dataset_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if dataset is None or not dataset["is_demo"]:
            raise ORStorageError("DEMO_SCOPE_REQUIRED")
        jobs = (
            conn.execute(
                sa.select(compute_jobs.c.job_id).where(
                    compute_jobs.c.organization_id == actor.organization_id,
                    compute_jobs.c.input_package["input"]["scenario"]["package"][
                        "dataset_id"
                    ].astext
                    == str(body.dataset_id),
                    compute_jobs.c.state.in_(["QUEUED", "RUNNING", "STOPPING"]),
                )
            )
            .scalars()
            .all()
        )
    for job_id in jobs:
        active.queue.cancel(scope, job_id, f"reset-{job_id}")
    deadline = time.monotonic() + 5
    while True:
        try:
            with active.engine.begin() as conn:
                epoch = ORRepository(conn).reset_demo(
                    actor.organization_id, body.dataset_id, actor.actor_id
                )
            return {"dataset_id": body.dataset_id, "org_epoch": epoch, "history_retained": True}
        except ORStorageError as exc:
            if exc.code != "DEMO_RESET_REQUIRES_QUIESCENT_SCOPE" or time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


@router.get("/scenarios", response_model=list[ScenarioSummary])
def scenario_list(
    request: Request,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
):
    active = runtime(request)
    actor = authenticate(request, active, required=False)
    org = actor.organization_id if actor else active.public_organization_id
    if org is None:
        return []
    query = sa.select(ScenarioRecord.__table__).where(ScenarioRecord.organization_id == org)
    if actor is None:
        query = query.where(ScenarioRecord.payload["package"]["source_kind"].astext == "SIMULATED")
    if cursor:
        try:
            stamp, record_id = base64.urlsafe_b64decode(cursor).decode().split("|", 1)
            query = query.where(
                sa.tuple_(ScenarioRecord.created_at, ScenarioRecord.id)
                < sa.tuple_(datetime.fromisoformat(stamp), UUID(record_id))
            )
        except (ValueError, UnicodeError):
            raise AccessError("INVALID_CURSOR", 422) from None
    with active.engine.connect() as conn:
        rows = (
            conn.execute(
                query.order_by(ScenarioRecord.created_at.desc(), ScenarioRecord.id.desc()).limit(
                    limit
                )
            )
            .mappings()
            .all()
        )
    if len(rows) == limit:
        tail = rows[-1]
        response.headers["X-Next-Cursor"] = base64.urlsafe_b64encode(
            f"{tail['created_at'].isoformat()}|{tail['id']}".encode()
        ).decode()
    return [_scenario_summary(active, row) for row in rows]
