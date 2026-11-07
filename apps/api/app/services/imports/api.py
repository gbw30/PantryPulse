"""Import lifecycle: create, store each file, commit as import.v1, status (W1-D04/D05).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import AsyncIterator
from uuid import UUID

from app.schemas.v1_imports import (
    ImportAccepted,
    ImportCommit,
    ImportCreate,
    ImportCreated,
    ImportFile,
    ImportStatus,
)
from app.schemas.v1_networks import TemplateName
from app.services.v1_errors import NotImplementedV1


def create_import(rt, scope, request: ImportCreate) -> ImportCreated:
    raise NotImplementedV1("W1-D05")


async def store_import_file(
    rt, scope, import_id: UUID, name: TemplateName, chunks: AsyncIterator[bytes]
) -> ImportFile:
    """`chunks` is already capped at UPLOAD_CAP_BYTES by the router (InputRejected → 413)."""
    raise NotImplementedV1("W1-D04")


def commit_import(
    rt, scope, import_id: UUID, request: ImportCommit, idempotency_key: str
) -> ImportAccepted:
    raise NotImplementedV1("W1-D05")


def import_status(rt, scope, import_id: UUID) -> ImportStatus:
    raise NotImplementedV1("W1-D05")
