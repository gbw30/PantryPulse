"""Lazy, explicitly configured forecast dependencies; schema export stays offline."""

import os
from dataclasses import dataclass

from sqlalchemy.engine import make_url

from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services.jobs.contracts import PRODUCTION_PROFILE
from app.workers.registries import load_registry


@dataclass
class ForecastRuntime:
    engine: object
    queue: QueueRepository


def configured_runtime():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    parsed = make_url(url)
    if parsed.get_backend_name() not in ("postgres", "postgresql"):
        raise ValueError("PostgreSQL is required")
    engine = create_queue_engine(
        parsed.set(drivername="postgresql+psycopg"),
        schema=os.environ.get("PP_DATABASE_SCHEMA") or None,
    )
    return ForecastRuntime(
        engine,
        QueueRepository(engine, registry=load_registry("production"), profile=PRODUCTION_PROFILE),
    )
