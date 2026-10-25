"""Isolated PostgreSQL fixtures for queue tests.

Requires PP_TEST_DATABASE_URL naming a database whose name ends in ``_test``. Tests create
and drop only their own schemas; without the variable every test here skips (NOT RUN).
"""

import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from wq_support import SCHEMA, TEST_PROFILE, alembic_config, database_url, reset_schema

from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.workers.testing import FIXTURE_TABLE_DDL, REGISTRY


@pytest.fixture(scope="session")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        conn.execute(sa.text(FIXTURE_TABLE_DDL))
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "TRUNCATE compute_audit_events, compute_commands, wq_fixture_results, "
                "compute_jobs, compute_attempts, compute_control CASCADE"
            )
        )
        conn.execute(sa.text("INSERT INTO compute_control (lane_id) VALUES ('default')"))
    return engine


@pytest.fixture
def repo(db):
    return QueueRepository(db, registry=REGISTRY, profile=TEST_PROFILE)


@pytest.fixture
def scope():
    return TrustedScope(organization_id=uuid.uuid4(), actor_ref="test-presenter")
