"""Immutable simulated planning versions after forecast publication."""

from pathlib import Path

from alembic import op

revision = "ppor_0005"
down_revision = "pp45_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_name("ppor_0005_tables.sql").read_text())


def downgrade():
    for table in (
        "planning_method_verifications",
        "planning_comparisons",
        "planning_scenarios",
        "planning_assumptions",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION ppor_immutable_planning()")
