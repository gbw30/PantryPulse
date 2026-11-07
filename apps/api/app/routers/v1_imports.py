"""v1 import routes: create → upload each template file (streamed) → commit as import.v1."""

import re
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.routers.v1_common import KEY, PRESENTER, RESPONSES, RUNTIME, job_accepted
from app.schemas.v1_envelope import UPLOAD_CAP_BYTES
from app.schemas.v1_imports import (
    ImportAccepted,
    ImportCommit,
    ImportCreate,
    ImportCreated,
    ImportFile,
    ImportStatus,
)
from app.schemas.v1_networks import TemplateName
from app.services.imports import api
from app.services.jobs.registry import InputRejected

router = APIRouter(prefix="/api/v1", tags=["v1-imports"], responses=RESPONSES)
UPLOAD_PATH = re.compile(r"^/api/v1/imports/[^/]+/files/[^/]+$")  # exempt from RequestBoundary
_CSV = re.compile(r"^text/csv\s*(;|$)", re.IGNORECASE)


async def bounded_chunks(chunks: AsyncIterator[bytes], cap: int) -> AsyncIterator[bytes]:
    """Pass chunks through, raising INPUT_TOO_LARGE (413) once more than `cap` bytes arrive."""
    size = 0
    async for chunk in chunks:
        size += len(chunk)
        if size > cap:
            raise InputRejected("INPUT_TOO_LARGE", f"file is over the {cap}-byte limit")
        yield chunk


@router.post("/imports", response_model=ImportCreated, status_code=201)
def create_import(body: ImportCreate, rt=RUNTIME, scope=PRESENTER):
    return api.create_import(rt, scope, body)


@router.post(
    "/imports/{import_id}/files/{name}",
    response_model=ImportFile,
    openapi_extra={"requestBody": {"required": True, "content": {"text/csv": {}}}},
)
async def upload_file(
    import_id: UUID, name: TemplateName, request: Request, rt=RUNTIME, scope=PRESENTER
):
    if not _CSV.match(request.headers.get("content-type", "")):
        raise InputRejected("INVALID_UPLOAD_CONTENT_TYPE", "send the file as text/csv")
    if int(request.headers.get("content-length") or 0) > UPLOAD_CAP_BYTES:
        raise InputRejected("INPUT_TOO_LARGE", f"file is over the {UPLOAD_CAP_BYTES}-byte limit")
    chunks = bounded_chunks(request.stream(), UPLOAD_CAP_BYTES)
    return await api.store_import_file(rt, scope, import_id, name, chunks)


@router.post("/imports/{import_id}/commit", response_model=ImportAccepted, status_code=202)
def commit_import(
    import_id: UUID,
    body: ImportCommit,
    response: Response,
    idempotency_key: KEY,
    rt=RUNTIME,
    scope=PRESENTER,
):
    return job_accepted(response, api.commit_import(rt, scope, import_id, body, idempotency_key))


@router.get("/imports/{import_id}", response_model=ImportStatus)
def import_status(import_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return api.import_status(rt, scope, import_id)

