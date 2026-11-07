"""Import lifecycle: create, store each file, commit as import.v1, status (W1-D04/D05).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import AsyncIterator
from uuid import UUID

from app.repositories import imports as repo
from app.schemas.v1_imports import (
    ImportAccepted,
    ImportCommit,
    ImportCreate,
    ImportCreated,
    ImportFile,
    ImportStatus,
)
from app.schemas.v1_networks import TemplateName
from app.services.imports import staging
from app.services.presenter_access import AccessError
from app.services.v1_errors import NotImplementedV1


def create_import(rt, scope, request: ImportCreate) -> ImportCreated:
    raise NotImplementedV1("W1-D05")


async def store_import_file(
    rt, scope, import_id: UUID, name: TemplateName, chunks: AsyncIterator[bytes]
) -> ImportFile:
    """`chunks` is already capped at UPLOAD_CAP_BYTES by the router (InputRejected → 413).

    The local session may use every import of the install (W0-network-model §2); the run is
    checked to exist and still accept files. An over-cap or broken upload leaves no file."""
    with rt.engine.connect() as conn:
        _uploading(repo.get_run(conn, import_id))
    size, sha256 = await staging.write_upload(staging.import_dir(), import_id, name, chunks)
    with rt.engine.begin() as conn:
        _uploading(repo.get_run(conn, import_id, lock=True))
        repo.record_file(conn, import_id, name, size, sha256)
    return ImportFile(name=name, bytes=size, sha256=sha256)


def _uploading(run: repo.Run) -> None:
    if run.phase != "uploading":
        raise AccessError("IMPORT_NOT_UPLOADING", 409)


def commit_import(
    rt, scope, import_id: UUID, request: ImportCommit, idempotency_key: str
) -> ImportAccepted:
    raise NotImplementedV1("W1-D05")


def import_status(rt, scope, import_id: UUID) -> ImportStatus:
    raise NotImplementedV1("W1-D05")
