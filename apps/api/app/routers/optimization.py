"""Presenter-only simulated planning; all computation goes through durable jobs."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Header, Response

from app.models.optimization import PlanningComparison
from app.repositories import planning
from app.repositories.forecast_history import HistoryRejected
from app.repositories.jobs import JobNotFound
from app.routers.forecasts import PRESENTER, RUNTIME
from app.schemas.forecast_api import ErrorEnvelope, ForecastAccepted
from app.schemas.optimization_api import (
    AssumptionsRequest,
    AssumptionsResult,
    ComparisonRequest,
    PlanningCatalog,
    SavedComparison,
    ScenarioRequest,
    ScenarioResult,
)
from app.services.optimization.settings import solver_settings

router = APIRouter(
    prefix="/api/v1",
    tags=["optimization"],
    responses={code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 422, 503)},
)
KEY = Annotated[str, Header(min_length=1, max_length=128)]


@router.get("/planning-catalog", response_model=PlanningCatalog)
def catalog(
    before: datetime | None = None, before_id: UUID | None = None, rt=RUNTIME, scope=PRESENTER
):
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        return planning.catalog(conn, scope.organization_id, before, before_id)


@router.get("/planning-assumptions/{identity}", response_model=AssumptionsResult)
def assumptions(identity: UUID, rt=RUNTIME, scope=PRESENTER):
    with rt.engine.connect() as conn:
        row, _ = planning.read_assumptions(conn, scope.organization_id, identity)
        return {key: row[key] for key in AssumptionsResult.model_fields}


@router.post("/planning-assumptions", response_model=AssumptionsResult, status_code=201)
def save_assumptions(body: AssumptionsRequest, rt=RUNTIME, scope=PRESENTER):
    row = planning.save_assumptions(rt.engine, scope, body)
    return {key: row[key] for key in AssumptionsResult.model_fields}


@router.post("/scenarios", response_model=ScenarioResult, status_code=201)
def save_scenario(body: ScenarioRequest, idempotency_key: KEY, rt=RUNTIME, scope=PRESENTER):
    identity = planning.save_scenario(rt.engine, scope, body, idempotency_key)
    return scenario(identity, rt, scope)


@router.get("/scenarios/{identity}", response_model=ScenarioResult)
def scenario(identity: UUID, rt=RUNTIME, scope=PRESENTER):
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        return planning.read_scenario(conn, scope.organization_id, identity)


@router.post("/comparisons", response_model=ForecastAccepted, status_code=202)
def submit(
    body: ComparisonRequest, response: Response, idempotency_key: KEY, rt=RUNTIME, scope=PRESENTER
):
    with rt.engine.connect() as conn:
        saved = planning.read_scenario(conn, scope.organization_id, body.scenario_id)
    accepted = rt.queue.submit(
        scope,
        "or-comparison.v2",
        dict(
            scenario_id=str(body.scenario_id),
            scenario=saved["payload"].model_dump(mode="json"),
            settings=solver_settings(body.search_seconds),
        ),
        idempotency_key,
        deduplicate=True,
    )
    status_url = f"/api/v1/jobs/{accepted.job_id}"
    response.headers["Location"] = status_url
    return ForecastAccepted(
        job_id=accepted.job_id,
        attempt_id=accepted.attempt_id,
        state=accepted.state,
        replayed=accepted.replayed,
        status_url=status_url,
        result_url=f"/api/v1/comparisons/{accepted.job_id}",
    )


@router.get("/comparisons/{identity}", response_model=SavedComparison)
def comparison(identity: UUID, rt=RUNTIME, scope=PRESENTER):
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        row = (
            conn.execute(
                sa.select(PlanningComparison.__table__).where(
                    PlanningComparison.organization_id == scope.organization_id,
                    PlanningComparison.id == identity,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            job = rt.queue.get_job(scope, identity)
            if job.handler_contract != "or-comparison.v2":
                raise JobNotFound()
            raise HistoryRejected("COMPARISON_NOT_PUBLISHED", 409)
        saved = planning.read_scenario(conn, scope.organization_id, row["scenario_id"])
        return dict(
            id=identity,
            scenario_id=row["scenario_id"],
            recorded_at=row["recorded_at"],
            settings=row["settings"],
            result=row["result"],
            stale=saved["stale"],
            historical=saved["historical"],
        )
