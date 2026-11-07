"""v1 bring-your-own networks: datasets, imports, enrichment, routes, local login (W0-07).

The table DDL in ppv1_0008_networks.sql is generated from app/models/networks.py. History and
staging tables are partitioned; the import job creates and attaches one partition per version/run.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "ppv1_0008"
down_revision = "ppvp_0007"
branch_labels = None
depends_on = None

IMMUTABLE = ("dataset_versions", "import_events")
TABLES = (  # drop order: dependants first
    "local_secrets", "local_logins", "google_distance_cache", "import_staging", "backtest_scores",
    "net_routes", "net_inbound", "net_donation_history", "net_demand_history", "net_batches",
    "net_products", "net_locations", "import_events", "import_errors", "dataset_versions",
    "import_runs", "networks",
)


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text())
    op.execute(
        "CREATE FUNCTION ppv1_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME "
        "USING ERRCODE = 'integrity_constraint_violation'; END $$"
    )
    for table in IMMUTABLE:
        op.execute(f"CREATE TRIGGER ppv1_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION ppv1_immutable()")
    op.execute(
        "CREATE FUNCTION ppv1_network_mode_fixed() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF NEW.mode IS DISTINCT FROM OLD.mode THEN RAISE EXCEPTION 'network mode is fixed' "
        "USING ERRCODE = 'integrity_constraint_violation'; END IF; RETURN NEW; END $$"
    )
    op.execute("CREATE TRIGGER ppv1_mode_fixed BEFORE UPDATE OF mode ON networks "
               "FOR EACH ROW EXECUTE FUNCTION ppv1_network_mode_fixed()")


def downgrade():
    # Dropping these tables would delete every imported network; refuse instead of losing data.
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM networks)")).scalar():
        raise RuntimeError("V1_DATA_PRESENT: delete the imported networks before downgrading")
    for table in TABLES:
        op.drop_table(table)
    op.execute("DROP FUNCTION ppv1_network_mode_fixed()")
    op.execute("DROP FUNCTION ppv1_immutable()")
