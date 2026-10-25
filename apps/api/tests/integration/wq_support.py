"""Shared helpers for PostgreSQL queue tests (imported by conftest and test modules)."""

import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from app.services.jobs.contracts import RuntimeProfile, SupervisorState
from app.services.jobs.policies import supervisor_advertisement
from app.workers.testing import REGISTRY

API_ROOT = Path(__file__).resolve().parents[2]
URL_ENV = "PP_TEST_DATABASE_URL"
SCHEMA = "wq_test"

# Short, explicit test profile. Production values are asserted by the pure policy tests.
TEST_PROFILE = RuntimeProfile(
    queue_wait_s=30,
    heartbeat_interval_s=0.2,
    heartbeat_stale_s=2,
    forecast_total_s=8,
    forecast_primary_cutoff_s=4,
    allocation_total_s=6,
    method_wall_s=6,
    method_search_s=3,
    comparison_total_s=10,
    stop_grace_s=0.4,
    publication_reserve_s=0.5,
    method_min_s=0.5,
)


def database_url() -> str:
    url = os.environ.get(URL_ENV)
    if not url:
        pytest.skip(f"NOT RUN: {URL_ENV} is not set")
    return url


def alembic_config(connection: sa.Connection) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


def reset_schema(url: str, schema: str) -> None:
    raw = sa.create_engine(url)
    with raw.begin() as conn:
        name = conn.scalar(sa.text("SELECT current_database()"))
        assert name.endswith("_test"), f"refusing to touch non-test database {name!r}"
        conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    raw.dispose()


def advertisement(contracts=None, containment=True):
    return supervisor_advertisement(
        TEST_PROFILE,
        handler_contracts=REGISTRY.contracts() if contracts is None else contracts,
        process_containment=containment,
    )


def make_ready(repo, **kw):
    own = repo.acquire_ownership(
        supervisor_id=uuid.uuid4(), host_identity="test-host", effective_limits=advertisement(**kw)
    )
    assert own is not None
    assert repo.finish_recovery(own)
    assert repo.set_state(own, SupervisorState.READY)
    return own


def echo(value=1, **behavior):
    return {"value": value, "behavior": behavior}
