"""Namespaced OR planning records on VP; operational audit/auth remain authoritative."""

from pathlib import Path

from alembic import op

revision = "pp49_0006"
down_revision = "pp49_0005"
branch_labels = None
depends_on = None

TABLES = (
    "or_comparisons", "or_reviews", "or_transfers", "or_verifications", "or_plans",
    "or_scenarios", "or_request_keys", "or_policies", "or_input_packages",
    "or_audit_events", "or_dataset_state",
)


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8-sig"))
    for table in TABLES:
        if table != "or_dataset_state":
            op.execute(f"CREATE TRIGGER pp49_immutable BEFORE UPDATE OR DELETE ON {table} "
                       "FOR EACH ROW EXECUTE FUNCTION pp49_immutable_command()")


def downgrade():
    for table in TABLES:
        op.drop_table(table)
