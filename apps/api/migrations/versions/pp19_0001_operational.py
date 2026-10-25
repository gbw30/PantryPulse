"""Initial operational-v1 storage; frozen SQL, independent of later model edits."""

from pathlib import Path

from alembic import op

revision = "pp19_0001"
down_revision = None
branch_labels = ("operational",)
depends_on = None


def upgrade():
    root = Path(__file__).parent
    for name in ("pp19_0001_tables.sql", "pp19_0001_guards.sql"):
        op.execute((root / name).read_text(encoding="utf-8"))


def downgrade():
    # Explicit reverse order, scoped by env.py's search_path. No DROP SCHEMA/CASCADE.
    for table in (
        "supply_receipts", "stock_ledger", "inventory_lots", "receipt_reconciliations",
        "audit_events", "receipt_postings", "receipt_lines", "expected_supplies",
        "stock_commands", "inventory_versions", "donation_coverage_revisions",
        "receipt_revisions", "receipts", "demand_revisions", "demand_records",
        "data_sources", "donors", "products", "categories",
    ):
        op.drop_table(table)
    op.execute('ALTER TABLE sites DROP CONSTRAINT fk_site_current_calendar')
    op.drop_table("site_calendars")
    op.drop_table("sites")
    op.drop_table("organizations")
    for name in ("pp19_immutable", "pp19_calendar", "pp19_receipt_day",
                 "pp19_line_insert", "pp19_complete_receipt", "pp19_product_unit",
                 "pp19_site_calendar_required", "pp19_supply_allocation"):
        op.execute(f"DROP FUNCTION {name}()")
