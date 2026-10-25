"""PantryPulse HTTP application; importing/exporting OpenAPI needs no credentials."""

from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.repositories.forecast_history import HistoryRejected
from app.repositories.inventory import InventoryError
from app.repositories.jobs import IdempotencyConflict, JobNotFound, JobStateConflict, QueueError
from app.routers.dashboard import router as dashboard_router
from app.routers.forecasts import router
from app.routers.inventory import router as inventory_router
from app.routers.operations import router as operations_router
from app.routers.optimization import router as optimization_router
from app.routers.planning import router as planning_router
from app.services.inventory.stock import StockError
from app.services.jobs.registry import InputRejected
from app.services.presenter_access import AccessError, LoginLimiter


class HealthResponse(BaseModel):
    status: Literal["ok"]
    scope: Literal["process"]


def health() -> HealthResponse:
    """Process liveness only; does not assert database or worker readiness."""
    return HealthResponse(status="ok", scope="process")


def error_response(code, status, request_id):
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": code.replace("_", " ").lower(),
                "details": {},
            },
            "request_id": str(request_id),
        },
        status_code=status,
        headers={"X-Request-ID": str(request_id), "Cache-Control": "no-store"},
    )


class RequestBoundary:
    """Bound request bytes before JSON parsing; never log credentials or source data."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4()
        scope.setdefault("state", {})["request_id"] = request_id
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            limit = 524_288 if scope["path"] == "/api/v1/planning-assumptions" else 65_536
            if len(body) > limit:
                return await error_response("INPUT_TOO_LARGE", 413, request_id)(
                    scope, receive, send
                )
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        async def headers(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *(
                        h
                        for h in message.get("headers", [])
                        if h[0].lower() not in {b"x-request-id", b"cache-control"}
                    ),
                    (b"x-request-id", str(request_id).encode()),
                    (b"cache-control", b"no-store"),
                ]
            await send(message)

        await self.app(scope, bounded_receive, headers)


@asynccontextmanager
async def lifespan(application):
    yield
    runtime = getattr(application.state, "forecast_runtime", None)
    if runtime is not None:
        runtime.engine.dispose()


def create_app(runtime=None):
    application = FastAPI(title="PantryPulse API", version="0.2.0", lifespan=lifespan)
    application.add_middleware(RequestBoundary)
    application.state.login_limiter = LoginLimiter()
    if runtime is not None:
        application.state.forecast_runtime = runtime

    @application.exception_handler(RequestValidationError)
    async def invalid(request: Request, error):
        malformed = any(item["type"] == "json_invalid" for item in error.errors())
        return error_response(
            "INVALID_REQUEST", 400 if malformed else 422, request.state.request_id
        )

    async def domain_error(request: Request, error):
        if isinstance(error, (AccessError, HistoryRejected, InventoryError, StockError)):
            status = error.status
        elif isinstance(error, JobNotFound):
            status = 404
        elif isinstance(error, (IdempotencyConflict, JobStateConflict)):
            status = 409
        elif isinstance(error, InputRejected):
            status = 413 if error.code == "INPUT_TOO_LARGE" else 422
        else:
            status = 503
        return error_response(error.code, status, request.state.request_id)

    for error_type in (
        AccessError,
        HistoryRejected,
        InventoryError,
        StockError,
        QueueError,
        InputRejected,
    ):
        application.add_exception_handler(error_type, domain_error)

    @application.exception_handler(SQLAlchemyError)
    async def storage_error(request: Request, _error):
        return error_response("DATABASE_UNAVAILABLE", 503, request.state.request_id)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error):
        return error_response(
            "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR",
            error.status_code,
            request.state.request_id,
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, _error):
        return error_response("INTERNAL_ERROR", 500, request.state.request_id)

    application.include_router(router)
    application.include_router(optimization_router)
    application.include_router(inventory_router)
    application.include_router(operations_router)
    application.include_router(dashboard_router)
    application.include_router(planning_router)
    application.add_api_route(
        "/api/v1/health", health, response_model=HealthResponse, tags=["health"]
    )
    return application


app = create_app()
