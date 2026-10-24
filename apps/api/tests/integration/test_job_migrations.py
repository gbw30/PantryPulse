"""WQ-T27: jobs-only migration upgrade/integrity/downgrade on an isolated PostgreSQL schema."""

import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import DBAPIError, IntegrityError
from wq_support import alembic_config, database_url, reset_schema

from app.models.jobs import metadata
from app.repositories.jobs import create_queue_engine

pytestmark = pytest.mark.integration

MIGRATION_SCHEMA = "wq_migration_test"
JOB_TABLES = {
    "compute_control",
    "compute_jobs",
    "compute_attempts",
    "compute_commands",
    "compute_audit_events",
}


@pytest.fixture
def fresh():
    url = database_url()
    reset_schema(url, MIGRATION_SCHEMA)
    eng = create_queue_engine(url, schema=MIGRATION_SCHEMA)
    yield eng
    eng.dispose()
    reset_schema(url, MIGRATION_SCHEMA)


def _tables(conn):
    return set(sa.inspect(conn).get_table_names(schema=MIGRATION_SCHEMA))


def test_upgrade_downgrade_upgrade_creates_only_job_tables(fresh):
    with fresh.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        assert _tables(conn) == JOB_TABLES | {"alembic_version"}
        seeded = conn.execute(sa.text("SELECT lane_id, state, generation FROM compute_control"))
        assert seeded.all() == [("default", "OFFLINE", 0)]
    with fresh.begin() as conn:
        command.downgrade(alembic_config(conn), "base")
        assert _tables(conn) == {"alembic_version"}
    with fresh.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        assert JOB_TABLES <= _tables(conn)


def test_model_metadata_matches_migrated_columns(fresh):
    with fresh.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        inspector = sa.inspect(conn)
        for table in metadata.sorted_tables:
            db_cols = {
                c["name"] for c in inspector.get_columns(table.name, schema=MIGRATION_SCHEMA)
            }
            assert db_cols == {c.name for c in table.columns}, table.name


ORG = uuid.uuid4()


def _seed_job(conn, *, state="QUEUED"):
    job, att = uuid.uuid4(), uuid.uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO compute_attempts (attempt_id, job_id, attempt_number, lane_id,"
            " organization_id, state, enqueued_at, queue_deadline_at)"
            " VALUES (:a, :j, 1, 'default', :o, :s, now(), now() + interval '15 minutes')"
        ),
        {"a": att, "j": job, "o": ORG, "s": state},
    )
    conn.execute(
        sa.text(
            "INSERT INTO compute_jobs (job_id, lane_id, organization_id, requested_by_ref,"
            " operation_kind, handler_contract, input_schema_version, input_package,"
            " input_sha256, current_attempt_id, state, created_at, updated_at)"
            " VALUES (:j, 'default', :o, 'actor', 'ALLOCATION', 'test.echo.v1', '1',"
            " '{\"input\": {}}', repeat('a', 64), :a, :s, now(), now())"
        ),
        {"a": att, "j": job, "o": ORG, "s": state},
    )
    return job, att


@pytest.fixture
def migrated(fresh):
    with fresh.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    return fresh


def _rejects(engine, sql, params=None):
    with pytest.raises((IntegrityError, DBAPIError)):
        with engine.begin() as conn:
            conn.execute(sa.text(sql), params or {})


def test_valid_rows_are_accepted(migrated):
    with migrated.begin() as conn:
        _seed_job(conn)


def test_unknown_state_and_bad_hash_are_rejected(migrated):
    _rejects(
        migrated,
        "INSERT INTO compute_attempts (attempt_id, job_id, attempt_number, lane_id,"
        " organization_id, state, enqueued_at, queue_deadline_at)"
        " VALUES (gen_random_uuid(), gen_random_uuid(), 1, 'default', gen_random_uuid(),"
        " 'queued', now(), now() + interval '1 minute')",
    )
    with pytest.raises((IntegrityError, DBAPIError)):
        with migrated.begin() as conn:
            job, att = _seed_job(conn)
            conn.execute(
                sa.text(
                    "INSERT INTO compute_commands (command_id, organization_id, action,"
                    " idempotency_key, request_sha256, job_id, attempt_id, response, created_at)"
                    " VALUES (gen_random_uuid(), :o, 'SUBMIT', 'k', 'NOTHEX', :j, :a, '{}', now())"
                ),
                {"o": ORG, "j": job, "a": att},
            )


def test_queue_deadline_must_follow_enqueue(migrated):
    with pytest.raises((IntegrityError, DBAPIError)):
        with migrated.begin() as conn:
            job, att = _seed_job(conn)
            conn.execute(
                sa.text(
                    "INSERT INTO compute_attempts (attempt_id, job_id, attempt_number, lane_id,"
                    " organization_id, state, enqueued_at, queue_deadline_at, reason_code,"
                    " completed_at) VALUES (gen_random_uuid(), :j, 2, 'default', :o, 'EXPIRED',"
                    " now(), now(), 'X', now())"
                ),
                {"j": job, "o": ORG},
            )


def test_job_input_package_is_immutable(migrated):
    with migrated.begin() as conn:
        job, _ = _seed_job(conn)
    _rejects(
        migrated,
        'UPDATE compute_jobs SET input_package = \'{"input": {"x": 1}}\' WHERE job_id = :j',
        {"j": job},
    )
    _rejects(migrated, "UPDATE compute_jobs SET input_sha256 = repeat('b', 64)")


def test_terminal_attempts_are_immutable_and_transitions_are_checked(migrated):
    with migrated.begin() as conn:
        _, att = _seed_job(conn)
        conn.execute(
            sa.text(
                "UPDATE compute_attempts SET state = 'CANCELLED', reason_code = 'CANCEL_REQUESTED',"
                " completed_at = clock_timestamp(), state_version = state_version + 1"
                " WHERE attempt_id = :a"
            ),
            {"a": att},
        )
    _rejects(
        migrated,
        "UPDATE compute_attempts SET diagnostics = '{\"x\": 1}' WHERE attempt_id = :a",
        {"a": att},
    )
    with migrated.begin() as conn:
        _, att2 = _seed_job(conn)
    # QUEUED -> SUCCEEDED skips RUNNING and is forbidden even with all fields present.
    _rejects(
        migrated,
        "UPDATE compute_attempts SET state = 'SUCCEEDED', result_manifest = '{}',"
        " completed_at = clock_timestamp(), state_version = state_version + 1"
        " WHERE attempt_id = :a",
        {"a": att2},
    )


def test_one_active_attempt_per_lane_and_one_nonterminal_per_job(migrated):
    def run(conn, att):
        conn.execute(
            sa.text(
                "UPDATE compute_attempts SET state = 'RUNNING', supervisor_id = gen_random_uuid(),"
                " supervisor_generation = 1, execution_token = gen_random_uuid(),"
                " started_at = clock_timestamp(),"
                " execution_deadline_at = clock_timestamp() + interval '1 minute',"
                " state_version = state_version + 1 WHERE attempt_id = :a"
            ),
            {"a": att},
        )

    with migrated.begin() as conn:
        _, a1 = _seed_job(conn)
        _, a2 = _seed_job(conn)
        run(conn, a1)
    with pytest.raises(IntegrityError):
        with migrated.begin() as conn:
            run(conn, a2)
    with pytest.raises(IntegrityError):
        with migrated.begin() as conn:
            job, _ = _seed_job(conn)
            conn.execute(
                sa.text(
                    "INSERT INTO compute_attempts (attempt_id, job_id, attempt_number, lane_id,"
                    " organization_id, state, enqueued_at, queue_deadline_at)"
                    " VALUES (gen_random_uuid(), :j, 2, 'default', :o, 'QUEUED', now(),"
                    " now() + interval '1 minute')"
                ),
                {"j": job, "o": ORG},
            )


def test_attempt_must_match_its_job_scope(migrated):
    with pytest.raises(IntegrityError):
        with migrated.begin() as conn:
            job, _ = _seed_job(conn)
            conn.execute(
                sa.text(
                    "INSERT INTO compute_attempts (attempt_id, job_id, attempt_number, lane_id,"
                    " organization_id, state, enqueued_at, queue_deadline_at, reason_code,"
                    " completed_at) VALUES (gen_random_uuid(), :j, 2, 'default',"
                    " gen_random_uuid(), 'EXPIRED', now(), now() + interval '1 minute', 'X',"
                    " now() + interval '2 minutes')"
                ),
                {"j": job},
            )


def test_audit_is_append_only(migrated):
    with migrated.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO compute_audit_events (lane_id, event_type) VALUES ('default', 'X')"
            )
        )
    _rejects(migrated, "UPDATE compute_audit_events SET event_type = 'Y'")
    _rejects(migrated, "DELETE FROM compute_audit_events")


def test_succeeded_requires_manifest_and_cleanup(migrated):
    with migrated.begin() as conn:
        _, att = _seed_job(conn)
        conn.execute(
            sa.text(
                "UPDATE compute_attempts SET state = 'RUNNING', supervisor_id = gen_random_uuid(),"
                " supervisor_generation = 1, execution_token = gen_random_uuid(),"
                " started_at = clock_timestamp(),"
                " execution_deadline_at = clock_timestamp() + interval '1 minute',"
                " state_version = state_version + 1 WHERE attempt_id = :a"
            ),
            {"a": att},
        )
    _rejects(
        migrated,
        "UPDATE compute_attempts SET state = 'SUCCEEDED', completed_at = clock_timestamp(),"
        " result_manifest = '{}', state_version = state_version + 1 WHERE attempt_id = :a",
        {"a": att},
    )
