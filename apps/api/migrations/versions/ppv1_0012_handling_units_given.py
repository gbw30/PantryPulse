"""net_products records whether the file gave handling units (CR-w1-data-6, Gabriel 2026-11-07).

A blank `handling_units_per_unit` is stored as 1 (V1-SPEC §6.1), and the scenario must list that
default as an assumption. `handling_units_given` keeps the difference: true when the file gave a
value, false when 1 was assumed. Existing rows predate the flag and stay true.

Downgrade refuses while any product has an assumed value: the assumption could no longer be listed.
"""

import sqlalchemy as sa
from alembic import op

revision = "ppv1_0012"
down_revision = "ppv1_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE net_products "
               "ADD COLUMN handling_units_given BOOLEAN NOT NULL DEFAULT true")


def downgrade():
    if op.get_bind().scalar(sa.text(
            "SELECT EXISTS (SELECT 1 FROM net_products WHERE NOT handling_units_given)")):
        raise RuntimeError("V1_DATA_PRESENT: products with an assumed handling unit would lose it")
    op.execute("ALTER TABLE net_products DROP COLUMN handling_units_given")
