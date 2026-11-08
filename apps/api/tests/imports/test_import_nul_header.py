# covers: V1-A07
"""W2-06: a NUL in a CSV header (e.g. a file saved as UTF-16 without a BOM) ends the import as
a stored, listed row error. It must never reach PostgreSQL text, where the publication would
fail with a DataError and nothing would be saved or shown."""

import pytest
from alembic import command

from app.repositories.jobs import create_queue_engine
from app.services.imports import api
from app.services.jobs.contracts import AttemptState
from tests.imports.test_import_postgres import FILES
from tests.imports.test_import_worker import SCOPE, _commit, _running, _settle
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w2_import_nul_header_test"


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


@pytest.fixture
def lane(engine, tmp_path, monkeypatch):
    with _running(engine, tmp_path, monkeypatch) as running:
        yield running


def test_nul_in_a_header_fails_the_import_with_a_stored_row_error(lane):
    files = {**FILES, "locations": FILES["locations"].replace("location_id", "location_id\x00", 1)}
    import_id, job_id = _commit(lane, files)
    job = _settle(lane, import_id, job_id)
    assert job.state == AttemptState.SUCCEEDED  # the job finished; its result is the report
    status = api.import_status(lane, SCOPE, import_id)
    assert (status.phase, status.failure.kind) == ("failed", "ROW_ERRORS")
    [error] = status.errors
    assert (error.file, error.line, error.code) == ("locations", 1, "MALFORMED")
    assert "CSV UTF-8" in error.fix
    assert status.network_id is None and status.dataset_version_id is None
