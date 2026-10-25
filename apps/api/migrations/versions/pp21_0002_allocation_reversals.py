"""Permit one command to reverse multiple original allocations of the same line."""

import sqlalchemy as sa
from alembic import op

revision = "pp21_0002"
down_revision = "pp19_0001"
branch_labels = None
depends_on = None
OLD_KEY = "uq_supply_receipts_organization_id_command_id_supply_id_receipt_line_id"


def upgrade():
    op.drop_constraint(op.f(OLD_KEY), "supply_receipts", type_="unique")
    op.create_index("ix_supply_positive_command", "supply_receipts",
                    ["organization_id", "command_id", "supply_id", "receipt_line_id"],
                    unique=True, postgresql_where=sa.text("reverses_allocation_id IS NULL"))
    op.create_index("ix_supply_reversal_command", "supply_receipts",
                    ["organization_id", "command_id", "reverses_allocation_id"],
                    unique=True, postgresql_where=sa.text("reverses_allocation_id IS NOT NULL"))


def downgrade():
    # If newer data needs this capability, PostgreSQL refuses a lossy downgrade.
    op.create_unique_constraint(op.f(OLD_KEY), "supply_receipts",
                                ["organization_id", "command_id", "supply_id", "receipt_line_id"])
    op.drop_index("ix_supply_reversal_command", table_name="supply_receipts")
    op.drop_index("ix_supply_positive_command", table_name="supply_receipts")
