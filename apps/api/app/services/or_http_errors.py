"""Bounded request bodies and safe, request-identified HTTP error envelopes."""

import re
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from starlette.responses import JSONResponse

from app.repositories.jobs import (
    AdmissionRejected,
    IdempotencyConflict,
    JobNotFound,
    JobStateConflict,
    QueueError,
)
from app.repositories.or_repository import ORStorageError
from app.services.jobs.registry import InputRejected
from app.services.or_access import AccessError

MAX_BODY = 4 * 1024 * 1024


def envelope(request_id, code, status, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": code.replace("_", " ").capitalize(),
                "details": details or {},
            },
            "request_id": request_id,
        },
    )


class BodyTooLarge(RuntimeError):
    pass


class ORHTTPBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        supplied_id = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        request_id = (
            supplied_id if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied_id) else str(uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        length = headers.get(b"content-length")
        if length is not None:
            try:
                declared = int(length)
            except ValueError:
                await envelope(request_id, "INVALID_CONTENT_LENGTH", 400)(scope, receive, send)
                return
            if declared < 0 or declared > MAX_BODY:
                await envelope(request_id, "BODY_TOO_LARGE", 413)(scope, receive, send)
                return
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > MAX_BODY:
                    scope["state"]["or_body_too_large"] = True
                    raise BodyTooLarge()
            return message

        replaced = False

        async def identified_send(message):
            nonlocal replaced
            if replaced:
                return
            if scope["state"].get("or_body_too_large"):
                replaced = True
                response = envelope(request_id, "BODY_TOO_LARGE", 413)
                response.headers["X-Request-ID"] = request_id
                await response(scope, receive, send)
                return
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-request-id", request_id.encode())
                ]
            await send(message)

        try:
            await self.app(scope, limited_receive, identified_send)
        except BodyTooLarge:
            await envelope(request_id, "BODY_TOO_LARGE", 413)(scope, receive, identified_send)


def install_or_http(app):
    app.add_middleware(ORHTTPBoundary)

    async def access_error(request: Request, error: AccessError):
        return envelope(request.state.request_id, error.code, error.status)

    async def storage_error(request: Request, error: ORStorageError):
        status = (
            404
            if error.code == "NOT_FOUND"
            else 503
            if error.code == "SOURCE_INTEGRATION_UNAVAILABLE"
            else 422
            if error.code.endswith("HASH_MISMATCH")
            else 409
        )
        return envelope(request.state.request_id, error.code, status)

    async def queue_error(request: Request, error: QueueError):
        code = error.code
        if isinstance(error, AdmissionRejected):
            status = 429 if code in {"COMPUTE_QUEUE_FULL", "QUEUE_FULL"} else 503
            if status == 429:
                code = "QUEUE_FULL"
        elif isinstance(error, IdempotencyConflict | JobStateConflict):
            status = 409
        elif isinstance(error, JobNotFound):
            status = 404
        else:
            status = 503
        return envelope(request.state.request_id, code, status)

    async def validation_error(request: Request, error):
        details = [
            {"location": list(e["loc"]), "type": e["type"], "message": e["msg"]}
            for e in error.errors()
        ]
        malformed = any(e["type"] == "json_invalid" for e in error.errors())
        return envelope(
            request.state.request_id,
            "MALFORMED_JSON" if malformed else "INVALID_INPUT",
            400 if malformed else 422,
            {"violations": details},
        )

    async def rejected_input(request: Request, error: InputRejected):
        return envelope(
            request.state.request_id, error.code, 413 if error.code == "INPUT_TOO_LARGE" else 422
        )

    async def database_error(request: Request, error: DBAPIError):
        return envelope(request.state.request_id, "DATABASE_UNAVAILABLE", 503)

    async def safe_internal(request: Request, error: Exception):
        return envelope(getattr(request.state, "request_id", str(uuid4())), "INTERNAL_ERROR", 500)

    async def value_error(request: Request, error: ValueError):
        # Pure contract errors become safe codes without echoing literals/source payloads.
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", code):
            code = "INVALID_INPUT"
        return envelope(request.state.request_id, code, 422)

    for kind, handler in (
        (AccessError, access_error),
        (ORStorageError, storage_error),
        (QueueError, queue_error),
        (RequestValidationError, validation_error),
        (ValidationError, validation_error),
        (InputRejected, rejected_input),
        (DBAPIError, database_error),
        (ValueError, value_error),
        (Exception, safe_internal),
    ):
        app.add_exception_handler(kind, handler)
