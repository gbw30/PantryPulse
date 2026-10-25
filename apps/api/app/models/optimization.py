"""Immutable simulated planning versions and fenced comparison publication."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.models.forecasts import ForecastRun  # noqa: F401 - register referenced metadata
from app.models.jobs import compute_attempts, compute_jobs
from app.models.operational import Base, OwnedIdentity, check, fk, owned, uid


class PlanningAssumptions(OwnedIdentity, Base):
    __tablename__ = "planning_assumptions"
    parent_id = uid()
    name = mapped_column(sa.String(120), nullable=False)
    content_hash = mapped_column(sa.String(64), nullable=False)
    payload = mapped_column(JSONB, nullable=False)
    actor = mapped_column(sa.String(200), nullable=False)
    __table_args__ = owned(
        fk(["parent_id"], "planning_assumptions", ["id"]),
        check("content_hash ~ '^[0-9a-f]{64}$'", "hash"),
    )


class PlanningScenario(OwnedIdentity, Base):
    __tablename__ = "planning_scenarios"
    parent_id = uid()
    forecast_run_id = uid(nullable=False)
    assumptions_id = uid(nullable=False)
    request_key = mapped_column(sa.String(128), nullable=False)
    request_hash = mapped_column(sa.String(64), nullable=False)
    operational_hash = mapped_column(sa.String(64), nullable=False)
    source_revision = mapped_column(sa.String(64), nullable=False)
    payload = mapped_column(JSONB, nullable=False)
    actor = mapped_column(sa.String(200), nullable=False)
    __table_args__ = owned(
        fk(["parent_id"], "planning_scenarios", ["id"]),
        fk(["forecast_run_id"], "forecast_runs", ["id"]),
        fk(["assumptions_id"], "planning_assumptions", ["id"]),
        sa.UniqueConstraint("organization_id", "request_key"),
        check(
            "operational_hash ~ '^[0-9a-f]{64}$' AND source_revision ~ '^[0-9a-f]{64}$' "
            "AND request_hash ~ '^[0-9a-f]{64}$'",
            "hashes",
        ),
    )


class PlanningComparison(OwnedIdentity, Base):
    __tablename__ = "planning_comparisons"
    scenario_id = uid(nullable=False)
    job_id = uid(nullable=False, unique=True)
    attempt_id = uid(nullable=False, unique=True)
    settings = mapped_column(JSONB, nullable=False)
    input_hash = mapped_column(sa.String(64), nullable=False)
    outcome = mapped_column(sa.Text, nullable=False)
    result = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        fk(["scenario_id"], "planning_scenarios", ["id"]),
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
        check("outcome IN ('SUCCEEDED', 'PARTIAL')", "outcome"),
        check("input_hash ~ '^[0-9a-f]{64}$'", "hash"),
    )


class MethodVerification(OwnedIdentity, Base):
    __tablename__ = "planning_method_verifications"
    comparison_id = uid(nullable=False)
    method = mapped_column(sa.Text, nullable=False)
    outcome = mapped_column(sa.Text, nullable=False)
    record = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        fk(["comparison_id"], "planning_comparisons", ["id"]),
        sa.UniqueConstraint("organization_id", "comparison_id", "method"),
        check("method IN ('CLASSICAL_GP', 'EGP_PI_INSPIRED')", "method"),
    )


class PlanningPlan(OwnedIdentity, Base):
    """One independently verified method, from a single solve or paired comparison."""

    __tablename__ = "planning_plans"
    scenario_id = uid(nullable=False)
    job_id = uid(nullable=False)
    attempt_id = uid(nullable=False)
    comparison_id = uid()
    method = mapped_column(sa.Text, nullable=False)
    settings = mapped_column(JSONB, nullable=False)
    result = mapped_column(JSONB, nullable=False)
    result_hash = mapped_column(sa.String(64), nullable=False)
    __table_args__ = owned(
        fk(["scenario_id"], "planning_scenarios", ["id"]),
        fk(["comparison_id"], "planning_comparisons", ["id"]),
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
        sa.ForeignKeyConstraint(
            ["job_id", "attempt_id"],
            [compute_attempts.c.job_id, compute_attempts.c.attempt_id],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("attempt_id", "method"),
        check("method IN ('CLASSICAL_GP', 'EGP_PI_INSPIRED')", "method"),
        check("result_hash ~ '^[0-9a-f]{64}$'", "hash"),
        check(
            "result->>'outcome' = 'VERIFIED' AND result->'verification'->>'passed' = 'true'",
            "verified",
        ),
    )


class PlanningReview(OwnedIdentity, Base):
    __tablename__ = "planning_reviews"
    plan_id = uid(nullable=False)
    actor = mapped_column(sa.String(200), nullable=False)
    action = mapped_column(sa.Text, nullable=False)
    result_hash = mapped_column(sa.String(64), nullable=False)
    note = mapped_column(sa.String(2000))
    __table_args__ = owned(
        fk(["plan_id"], "planning_plans", ["id"]),
        check("action IN ('REVIEWED', 'REJECTED')", "action"),
        check("result_hash ~ '^[0-9a-f]{64}$'", "hash"),
    )
