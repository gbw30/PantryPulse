"""Explicit SQLAlchemy engine/session factories. No connection on import."""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def database_engine(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() not in ("postgresql", "postgres"):
        raise ValueError("PostgreSQL is required")
    parsed = parsed.set(drivername="postgresql+psycopg")
    return create_engine(parsed, pool_pre_ping=True, hide_parameters=True,
                         connect_args={"connect_timeout": 15})


@contextmanager
def transaction(engine):
    """One caller-owned transaction; repositories never commit independently."""
    with Session(engine) as session, session.begin():
        yield session
