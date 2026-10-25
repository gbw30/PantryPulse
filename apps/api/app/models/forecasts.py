"""Additive forecast records on VP's operational metadata; no connections on import."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.models.jobs import compute_attempts, compute_jobs
from app.models.operational import Base, OwnedIdentity, check, fk, instant, owned, uid

compute_jobs.append_constraint(
    sa.UniqueConstraint("organization_id", "job_id", name="uq_compute_job_org_id")
)
compute_attempts.append_constraint(
    sa.UniqueConstraint("organization_id", "attempt_id", name="uq_compute_attempt_org_id")
)


class ForecastRun(OwnedIdentity, Base):
    __tablename__ = "forecast_runs"
    job_id = uid(nullable=False, unique=True)
    attempt_id = uid(nullable=False, unique=True)
    input_hash = mapped_column(sa.String(64), nullable=False)
    planning_ready = mapped_column(sa.Boolean, nullable=False)
    frozen_input = mapped_column(JSONB, nullable=False)
    output = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        sa.ForeignKeyConstraint(
            ["organization_id", "job_id"],
            [compute_jobs.c.organization_id, compute_jobs.c.job_id],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            [compute_attempts.c.organization_id, compute_attempts.c.attempt_id],
            ondelete="RESTRICT",
        ),
        check("input_hash ~ '^[0-9a-f]{64}$'", "input_hash"),
        sa.Index("ix_forecast_reuse", "organization_id", "input_hash", "planning_ready"),
    )


class ForecastSeries(OwnedIdentity, Base):
    __tablename__ = "forecast_series"
    run_id = uid(nullable=False)
    site_id = uid(nullable=False)
    product_id = uid(nullable=False)
    target_type = mapped_column(sa.Text, nullable=False)
    status = mapped_column(sa.Text, nullable=False)
    details = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        fk(["run_id"], "forecast_runs", ["id"]),
        fk(["site_id"], "sites", ["id"]),
        fk(["product_id"], "products", ["id"]),
        sa.UniqueConstraint("organization_id", "run_id", "site_id", "product_id", "target_type"),
        check("target_type IN ('DEMAND', 'DONATION')", "target"),
        check("status IN ('AVAILABLE', 'INSUFFICIENT_DATA', 'FAILED')", "status"),
    )


class ForecastPointRecord(OwnedIdentity, Base):
    __tablename__ = "forecast_points"
    series_id = uid(nullable=False)
    day = mapped_column(sa.Date, nullable=False)
    central_estimate = mapped_column(sa.Double, nullable=False)
    details = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        fk(["series_id"], "forecast_series", ["id"]),
        sa.UniqueConstraint("organization_id", "series_id", "day"),
        check("central_estimate >= 0 AND central_estimate < 'Infinity'::float8", "finite"),
    )


class PresenterSession(Base):
    """Same cookie/column convention as or_pipeline; convergence is still required."""

    __tablename__ = "presenter_sessions"
    id = uid(primary_key=True)
    organization_id = uid(nullable=False)
    actor_id = mapped_column(sa.String(200), nullable=False)
    token_hash = mapped_column(sa.String(64), nullable=False, unique=True)
    csrf_hash = mapped_column(sa.String(64), nullable=False)
    created_at = instant(nullable=False, server_default=sa.text("clock_timestamp()"))
    expires_at = instant(nullable=False)
    revoked_at = instant()
    __table_args__ = (
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        check("token_hash ~ '^[0-9a-f]{64}$' AND csrf_hash ~ '^[0-9a-f]{64}$'", "hashes"),
        check("expires_at > created_at", "expiry"),
    )
