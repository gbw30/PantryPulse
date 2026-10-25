"""OR-DEC-011/016 [PROVISIONAL]: manual OR retry is a linked new immutable job.

Revision ID: 0004_or_retry_links
Revises: 0003_or_partial
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_or_retry_links"
down_revision = "0003_or_partial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("compute_jobs", sa.Column("retry_of_job_id", sa.UUID(), nullable=True))
    op.add_column("compute_jobs", sa.Column("retry_of_attempt_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_compute_retry_job",
        "compute_jobs",
        "compute_jobs",
        ["organization_id", "retry_of_job_id"],
        ["organization_id", "job_id"],
    )
    op.create_foreign_key(
        "fk_compute_retry_attempt",
        "compute_jobs",
        "compute_attempts",
        ["organization_id", "retry_of_attempt_id"],
        ["organization_id", "attempt_id"],
    )
    op.create_foreign_key(
        "fk_compute_retry_pair",
        "compute_jobs",
        "compute_attempts",
        ["retry_of_job_id", "retry_of_attempt_id"],
        ["job_id", "attempt_id"],
    )
    op.create_check_constraint(
        "ck_compute_retry_pair",
        "compute_jobs",
        "(retry_of_job_id IS NULL)=(retry_of_attempt_id IS NULL)",
    )
    conn = op.get_bind()
    original = conn.scalar(
        sa.text("SELECT pg_get_functiondef('compute_jobs_guard()'::regprocedure)")
    )
    modified = original.replace(
        "IF NEW.job_id IS DISTINCT FROM OLD.job_id",
        "IF NEW.retry_of_job_id IS DISTINCT FROM OLD.retry_of_job_id "
        "OR NEW.retry_of_attempt_id IS DISTINCT FROM OLD.retry_of_attempt_id "
        "OR NEW.job_id IS DISTINCT FROM OLD.job_id",
    )
    conn.execute(sa.text(modified))


def downgrade():
    conn = op.get_bind()
    current = conn.scalar(
        sa.text("SELECT pg_get_functiondef('compute_jobs_guard()'::regprocedure)")
    )
    original = current.replace(
        "IF NEW.retry_of_job_id IS DISTINCT FROM OLD.retry_of_job_id "
        "OR NEW.retry_of_attempt_id IS DISTINCT FROM OLD.retry_of_attempt_id "
        "OR NEW.job_id IS DISTINCT FROM OLD.job_id",
        "IF NEW.job_id IS DISTINCT FROM OLD.job_id",
    )
    conn.execute(sa.text(original))
    for name in ("fk_compute_retry_job", "fk_compute_retry_attempt", "fk_compute_retry_pair"):
        op.drop_constraint(name, "compute_jobs", type_="foreignkey")
    op.drop_constraint("ck_compute_retry_pair", "compute_jobs", type_="check")
    op.drop_column("compute_jobs", "retry_of_attempt_id")
    op.drop_column("compute_jobs", "retry_of_job_id")
