"""OR-DEC-011 [PROVISIONAL]: concurrent active OR work has one shared durable identity.

Revision ID: 0005_or_active_dedup
Revises: 0004_or_retry_links
"""

from alembic import op

revision = "0005_or_active_dedup"
down_revision = "0004_or_retry_links"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE UNIQUE INDEX uq_or_active_jobs ON compute_jobs "
        "(organization_id,handler_contract,input_sha256) "
        "WHERE state IN ('QUEUED','RUNNING','STOPPING') AND "
        "handler_contract IN ('or-allocation-v1','or-comparison-v1')"
    )


def downgrade():
    op.drop_index("uq_or_active_jobs", table_name="compute_jobs")
