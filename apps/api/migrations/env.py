"""Unified worker/operational Alembic environment; no implicit credential loading."""

import os
import re

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.database import database_engine
from app.models import (
    forecasts,  # noqa: F401 — register additive operational metadata
    http_commands,  # noqa: F401
    optimization,  # noqa: F401
    or_records,  # noqa: F401 - retained legacy VP records
)
from app.models.jobs import metadata as job_metadata
from app.models.operational import Base

config = context.config
metadata = [Base.metadata, job_metadata]


def run(connection):
    # Preserve a worker test connection's isolated search_path unless explicitly overridden.
    schema = config.attributes.get("schema") or os.environ.get("PANTRYPULSE_MIGRATION_SCHEMA")
    if schema is None:
        schema = connection.scalar(text("SELECT current_schema()"))
    if not isinstance(schema, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
        raise ValueError("invalid migration schema identifier")
    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    connection.execute(text(
        "SELECT pg_advisory_xact_lock(hashtext('pantrypulse_migrations'), hashtext(:schema))"
    ), {"schema": schema})
    context.configure(
        connection=connection, target_metadata=metadata, version_table_schema=schema,
        compare_type=True, include_object=lambda obj, name, kind, reflected, compare_to:
            not (kind == "table" and name == "alembic_version"),
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported")
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    # Worker CLI compatibility; both environment options must be direct URLs.
    url = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("DATABASE_URL")
    if not url or "-pooler" in (make_url(url).host or ""):
        raise ValueError("an explicit direct PostgreSQL connection is required for migrations")
    engine = database_engine(url)
    try:
        with engine.begin() as connection:
            run(connection)
    finally:
        engine.dispose()
