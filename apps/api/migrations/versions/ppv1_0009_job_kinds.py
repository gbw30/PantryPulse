"""v1 job kinds: IMPORT and ENRICHMENT durable jobs (W0-08b; Gabriel, 2026-11-06).

Downgrade refuses (CHECK violation) while any IMPORT/ENRICHMENT job row exists, rather than
deleting job history.
"""

from alembic import op

revision = "ppv1_0009"
down_revision = "ppv1_0008"
branch_labels = None
depends_on = None


def _kinds(*kinds):
    listed = ",".join(f"'{k}'" for k in kinds)
    op.execute("ALTER TABLE compute_jobs DROP CONSTRAINT compute_jobs_operation_kind_check")
    op.execute(
        "ALTER TABLE compute_jobs ADD CONSTRAINT compute_jobs_operation_kind_check "
        f"CHECK (operation_kind IN ({listed}))"
    )


def upgrade():
    _kinds("FORECAST", "ALLOCATION", "COMPARISON", "IMPORT", "ENRICHMENT")


def downgrade():
    _kinds("FORECAST", "ALLOCATION", "COMPARISON")
