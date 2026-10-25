"""Converge main and VP histories; add canonical verified plans and simulation reviews."""

from pathlib import Path

from alembic import op

revision = "ppvp_0007"
down_revision = ("ppor_0005", "pp49_0006")
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text())
    for table in ("planning_plans", "planning_reviews"):
        op.execute(
            f"CREATE TRIGGER ppor_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION ppor_immutable_planning()"
        )


def downgrade():
    op.drop_table("planning_reviews")
    op.drop_table("planning_plans")
