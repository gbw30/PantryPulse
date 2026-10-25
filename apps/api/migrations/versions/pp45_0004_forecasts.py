"""Persisted forecasts and presenter sessions on the combined VP history.

Revision ID: pp45_0004
Revises: pp_merge_0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "pp45_0004"
down_revision = "pp_merge_0003"
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
    ]


def own(table):
    return [
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
            name=op.f(f"fk_{table}_organization_id_organizations"),
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f(f"uq_{table}_organization_id_id")),
    ]


def fk(local, table):
    return sa.ForeignKeyConstraint(
        ["organization_id", local], [f"{table}.organization_id", f"{table}.id"], ondelete="RESTRICT"
    )


def upgrade():
    op.create_unique_constraint(
        "uq_compute_job_org_id", "compute_jobs", ["organization_id", "job_id"]
    )
    op.create_unique_constraint(
        "uq_compute_attempt_org_id", "compute_attempts", ["organization_id", "attempt_id"]
    )
    op.create_table(
        "forecast_runs",
        *identity(),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("job_id", name=op.f("uq_forecast_runs_job_id")),
        sa.UniqueConstraint("attempt_id", name=op.f("uq_forecast_runs_attempt_id")),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("planning_ready", sa.Boolean, nullable=False),
        sa.Column("frozen_input", JSONB, nullable=False),
        sa.Column("output", JSONB, nullable=False),
        *own("forecast_runs"),
        sa.ForeignKeyConstraint(
            ["organization_id", "job_id"],
            ["compute_jobs.organization_id", "compute_jobs.job_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["compute_attempts.organization_id", "compute_attempts.attempt_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="input_hash"),
    )
    op.create_index(
        "ix_forecast_reuse", "forecast_runs", ["organization_id", "input_hash", "planning_ready"]
    )
    op.create_table(
        "forecast_series",
        *identity(),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("details", JSONB, nullable=False),
        *own("forecast_series"),
        fk("run_id", "forecast_runs"),
        fk("site_id", "sites"),
        fk("product_id", "products"),
        sa.UniqueConstraint(
            "organization_id",
            "run_id",
            "site_id",
            "product_id",
            "target_type",
            name=op.f("uq_forecast_series_organization_id_run_id_site_id_product_id_target_type"),
        ),
        sa.CheckConstraint("target_type IN ('DEMAND', 'DONATION')", name="target"),
        sa.CheckConstraint("status IN ('AVAILABLE', 'INSUFFICIENT_DATA', 'FAILED')", name="status"),
    )
    op.create_table(
        "forecast_points",
        *identity(),
        sa.Column("series_id", UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("central_estimate", sa.Double, nullable=False),
        sa.Column("details", JSONB, nullable=False),
        *own("forecast_points"),
        fk("series_id", "forecast_series"),
        sa.UniqueConstraint(
            "organization_id",
            "series_id",
            "day",
            name=op.f("uq_forecast_points_organization_id_series_id_day"),
        ),
        sa.CheckConstraint(
            "central_estimate >= 0 AND central_estimate < 'Infinity'::float8", name="finite"
        ),
    )
    op.create_table(
        "presenter_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("token_hash", name=op.f("uq_presenter_sessions_token_hash")),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$' AND csrf_hash ~ '^[0-9a-f]{64}$'", name="hashes"
        ),
        sa.CheckConstraint("expires_at > created_at", name="expiry"),
    )
    op.execute("""CREATE FUNCTION pp45_immutable_forecast() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'published forecast records are immutable'
        USING ERRCODE = 'integrity_constraint_violation'; END $$""")
    for table in ("forecast_runs", "forecast_series", "forecast_points"):
        op.execute(
            f"CREATE TRIGGER pp45_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pp45_immutable_forecast()"
        )


def downgrade():
    for table in ("forecast_points", "forecast_series", "forecast_runs"):
        op.drop_table(table)
    op.execute("DROP FUNCTION pp45_immutable_forecast()")
    op.drop_table("presenter_sessions")
    op.drop_constraint("uq_compute_attempt_org_id", "compute_attempts", type_="unique")
    op.drop_constraint("uq_compute_job_org_id", "compute_jobs", type_="unique")
