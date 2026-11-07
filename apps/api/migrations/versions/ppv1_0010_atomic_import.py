"""Atomic import: a new network exists only after its import succeeds (Gabriel, 2026-11-06).

`POST /imports` for a new network creates its organization and an import run holding the
pending network in `new_network`; the import.v1 commit inserts the network row in the same
transaction as the data. A failed first import leaves no network.

Each stored import error also keeps its `fix` (what to change in the file), so the status
endpoint can rebuild RowError after the job ends.

`networks.mode` now stores the API's NetworkMode spelling (PANTRY, RETAIL) instead of lowercase.

Downgrade refuses while any run has no network (it cannot restore NOT NULL without one).
"""

import sqlalchemy as sa
from alembic import op

revision = "ppv1_0010"
down_revision = "ppv1_0009"
branch_labels = None
depends_on = None


def _modes(case, *modes):
    """Respell existing rows; the fixed-mode trigger is paused only for this conversion."""
    listed = ", ".join(f"'{m}'" for m in modes)
    op.execute("ALTER TABLE networks DROP CONSTRAINT ck_networks_mode")
    op.execute("ALTER TABLE networks DISABLE TRIGGER ppv1_mode_fixed")
    op.execute(f"UPDATE networks SET mode = {case}(mode)")
    op.execute("ALTER TABLE networks ENABLE TRIGGER ppv1_mode_fixed")
    op.execute(f"ALTER TABLE networks ADD CONSTRAINT ck_networks_mode CHECK (mode IN ({listed}))")


def upgrade():
    _modes("upper", "PANTRY", "RETAIL")
    op.execute("ALTER TABLE import_runs ADD COLUMN new_network JSONB")
    op.execute("ALTER TABLE import_runs ALTER COLUMN network_id DROP NOT NULL")
    op.execute("ALTER TABLE import_runs ADD CONSTRAINT ck_import_runs_network_or_new "
               "CHECK (network_id IS NOT NULL OR new_network IS NOT NULL)")
    op.execute("ALTER TABLE import_runs ADD CONSTRAINT ck_import_runs_done_has_network "
               "CHECK (phase <> 'done' OR network_id IS NOT NULL)")
    op.execute("ALTER TABLE import_errors ADD COLUMN fix TEXT NOT NULL")
    op.execute(r"ALTER TABLE import_errors ADD CONSTRAINT ck_import_errors_fix CHECK (fix ~ '\S')")


def downgrade():
    if op.get_bind().execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM import_runs WHERE network_id IS NULL)")
    ).scalar():
        raise RuntimeError("V1_DATA_PRESENT: import runs without a network exist")
    _modes("lower", "pantry", "retail")
    op.execute("ALTER TABLE import_errors DROP COLUMN fix")
    op.execute("ALTER TABLE import_runs DROP CONSTRAINT ck_import_runs_done_has_network")
    op.execute("ALTER TABLE import_runs DROP CONSTRAINT ck_import_runs_network_or_new")
    op.execute("ALTER TABLE import_runs ALTER COLUMN network_id SET NOT NULL")
    op.execute("ALTER TABLE import_runs DROP COLUMN new_network")
