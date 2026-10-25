"""PP-45 HTTP adapter. Reads never execute inference or mutate inventory/queue state."""

from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, Request, Response

from app.models import operational as m
from app.models.forecasts import ForecastRun
from app.repositories.forecast_history import HistoryRejected, load_input
from app.repositories.jobs import JobNotFound
from app.schemas.forecast_api import (
    AttemptSummary,
    ErrorEnvelope,
    ForecastAccepted,
    ForecastCancelled,
    ForecastCatalog,
    ForecastJob,
    ForecastRequest,
    ForecastResult,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)
from app.services.chronos_runtime import CHRONOS_CONTRACT, bind_policy
from app.services.forecast_runtime import configured_runtime
from app.services.presenter_access import AccessError, authenticate, login, logout

router = APIRouter(
    prefix="/api/v1",
    responses={
        status: {"model": ErrorEnvelope}
        for status in (400, 401, 403, 404, 409, 413, 422, 429, 500, 503)
    },
)


def runtime(request: Request):
    if not hasattr(request.app.state, "forecast_runtime"):
        request.app.state.forecast_runtime = configured_runtime()
    value = request.app.state.forecast_runtime
    if value is None:
        raise AccessError("DATABASE_NOT_CONFIGURED", 503)
    return value


RUNTIME = Depends(runtime)


def presenter(request: Request, rt=RUNTIME):
    return authenticate(request, rt, mutation=request.method != "GET")


PRESENTER = Depends(presenter)


@router.post("/presenter/login", response_model=LoginResponse, tags=["presenter"])
def presenter_login(body: LoginRequest, request: Request, response: Response, rt=RUNTIME):
    return login(request, response, rt, body)


@router.post("/presenter/logout", response_model=LogoutResponse, tags=["presenter"])
def presenter_logout(request: Request, response: Response, rt=RUNTIME):
    return logout(request, response, rt)


@router.get("/forecast-catalog", response_model=ForecastCatalog, tags=["forecasts"])
def catalog(rt=RUNTIME, scope=PRESENTER):
    with rt.engine.connect() as conn:

        def rows(model, *conditions):
            result = (
                conn.execute(
                    sa.select(model.__table__)
                    .where(model.organization_id == scope.organization_id, *conditions)
                    .order_by(model.id)
                    .limit(101)
                )
                .mappings()
                .all()
            )
            if len(result) > (100 if model is m.DataSource else 20):
                raise HistoryRejected("CATALOG_TOO_LARGE")
            return result

        sources = rows(m.DataSource)
        sites = rows(m.Site, m.Site.active.is_(True))
        calendars = {
            r["id"]: r
            for r in conn.execute(
                sa.select(m.SiteCalendar.__table__).where(
                    m.SiteCalendar.organization_id == scope.organization_id
                )
            ).mappings()
        }
        products = rows(m.Product, m.Product.active.is_(True))
        return dict(
            sources=[
                dict(id=r["id"], name=r["name"], classification=r["classification"])
                for r in sources
            ],
            sites=[
                dict(
                    id=r["id"],
                    name=r["name"],
                    role=r["role"],
                    timezone=calendars[r["current_calendar_id"]]["timezone"],
                )
                for r in sites
                if r["current_calendar_id"] in calendars
            ],
            products=[dict(id=r["id"], name=r["name"], base_unit=r["base_unit"]) for r in products],
        )


@router.post("/forecasts", response_model=ForecastAccepted, status_code=202, tags=["forecasts"])
def submit(
    body: ForecastRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
    rt=RUNTIME,
    scope=PRESENTER,
):
    contract = "forecast.v1"
    policy = None
    if body.policy.strategy == "CHRONOS2":
        policy = bind_policy(body.policy)
        if policy is None:
            raise AccessError("COMPUTE_UNAVAILABLE", 503)
        contract = CHRONOS_CONTRACT
    inputs = load_input(rt.engine, scope.organization_id, body, policy=policy)
    accepted = rt.queue.submit(
        scope,
        contract,
        {
            "forecast_input": inputs.model_dump(mode="json"),
        },
        idempotency_key,
        deduplicate=not body.force_refresh,
    )
    status_url = f"/api/v1/jobs/{accepted.job_id}"
    response.headers["Location"] = status_url
    return ForecastAccepted(
        job_id=accepted.job_id,
        attempt_id=accepted.attempt_id,
        state=accepted.state,
        replayed=accepted.replayed,
        status_url=status_url,
        result_url=f"/api/v1/forecasts/{accepted.job_id}",
    )


@router.post(
    "/jobs/{job_id}/retry", response_model=ForecastAccepted, status_code=202, tags=["forecasts"]
)
def retry(
    job_id: UUID,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
    rt=RUNTIME,
    scope=PRESENTER,
):
    if rt.queue.get_job(scope, job_id).handler_contract not in {
        "forecast.v1",
        CHRONOS_CONTRACT,
        "or-comparison.v2",
        "or-allocation.v2",
    }:
        raise JobNotFound()
    accepted = rt.queue.retry(scope, job_id, idempotency_key)
    contract = rt.queue.get_job(scope, job_id).handler_contract
    resource = (
        "comparisons"
        if rt.queue.get_job(scope, job_id).handler_contract == "or-comparison.v2"
        else "forecasts"
    )
    status_url = f"/api/v1/jobs/{job_id}"
    response.headers["Location"] = status_url
    return ForecastAccepted(
        job_id=job_id,
        attempt_id=accepted.attempt_id,
        state=accepted.state,
        replayed=accepted.replayed,
        status_url=status_url,
        result_url=(
            f"/api/v1/allocation-jobs/{job_id}/results"
            if contract == "or-allocation.v2"
            else f"/api/v1/{resource}/{job_id}"
        ),
    )


@router.post(
    "/jobs/{job_id}/cancel", response_model=ForecastCancelled, status_code=202, tags=["forecasts"]
)
def cancel(
    job_id: UUID,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
    rt=RUNTIME,
    scope=PRESENTER,
):
    if rt.queue.get_job(scope, job_id).handler_contract not in {
        "forecast.v1",
        CHRONOS_CONTRACT,
        "or-comparison.v2",
        "or-allocation.v2",
    }:
        raise JobNotFound()
    outcome = rt.queue.cancel(scope, job_id, idempotency_key)
    return ForecastCancelled(
        job_id=job_id,
        attempt_id=outcome.attempt_id,
        state=outcome.state,
        completed=outcome.completed,
        replayed=outcome.replayed,
    )


@router.get("/jobs/{job_id}", response_model=ForecastJob, tags=["forecasts"])
def job_status(job_id: UUID, rt=RUNTIME, scope=PRESENTER):
    job = rt.queue.get_job(scope, job_id)
    if job.handler_contract not in {
        "forecast.v1",
        CHRONOS_CONTRACT,
        "or-comparison.v2",
        "or-allocation.v2",
    }:
        raise JobNotFound()
    return ForecastJob(
        job_id=job.job_id,
        state=job.state,
        current_attempt_id=job.current_attempt_id,
        attempts=tuple(
            AttemptSummary(
                attempt_id=a.attempt_id,
                state=a.state,
                reason_code=a.reason_code,
                enqueued_at=a.enqueued_at,
                started_at=a.started_at,
                completed_at=a.completed_at,
            )
            for a in job.attempts
        ),
    )


@router.get("/forecasts/{job_id}", response_model=ForecastResult, tags=["forecasts"])
def result(job_id: UUID, rt=RUNTIME, scope=PRESENTER):
    with rt.engine.connect() as conn:
        row = (
            conn.execute(
                sa.select(ForecastRun.__table__).where(
                    ForecastRun.organization_id == scope.organization_id,
                    ForecastRun.job_id == job_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            # Different organizations get 404; an owned job awaiting publication gets 409.
            job = rt.queue.get_job(scope, job_id)
            if job.handler_contract not in {
                "forecast.v1",
                CHRONOS_CONTRACT,
                "or-comparison.v2",
                "or-allocation.v2",
            }:
                raise JobNotFound()
            raise HistoryRejected("FORECAST_NOT_PUBLISHED", 409)
        return ForecastResult(
            job_id=job_id,
            attempt_id=row["attempt_id"],
            planning_ready=row["planning_ready"],
            published_at=row["recorded_at"],
            forecast=row["output"],
        )
