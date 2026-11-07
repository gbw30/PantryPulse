"""v1 scenarios and comparison results get their own tables (CR-w1-solver-3, Gabriel 2026-11-07).

`planning_scenarios_v3` holds frozen or-input-v3 scenarios (ScenarioV3) and
`planning_comparisons_v3` the published or-comparison.v3 results. The v2 tables
(`planning_scenarios`, `planning_comparisons`) stay untouched (V1-A22). Both rows are
immutable, using ppv1_0008's `ppv1_immutable()` trigger function. The DDL in
ppv1_0011_scenarios_v3.sql is generated from app/models/networks.py.

Downgrade refuses while either table holds rows, like ppv1_0008.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "ppv1_0011"
down_revision = "ppv1_0010"
branch_labels = None
depends_on = None

TABLES = ("planning_comparisons_v3", "planning_scenarios_v3")  # drop order: dependants first


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text())
    for table in TABLES:
        op.execute(f"CREATE TRIGGER ppv1_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION ppv1_immutable()")


def downgrade():
    bind = op.get_bind()
    if any(bind.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {t})")) for t in TABLES):
        raise RuntimeError("V1_DATA_PRESENT: saved v1 scenarios or comparisons would be lost")
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
