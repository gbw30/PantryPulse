"""OR-DEC-016 [PROVISIONAL]: partial comparison is terminal without losing causal stops.

Revision ID: 0003_or_partial
Revises: 0002_or_snapshots
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0003_or_partial"
down_revision = "0002_or_snapshots"
branch_labels = None
depends_on = None
_PREFIX = "OR0003_ORIGINAL:"


def upgrade():
    connection = op.get_bind()
    for table in ("compute_jobs", "compute_attempts"):
        checks = (
            connection.execute(
                sa.text(
                    "SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint "
                    "WHERE conrelid=CAST(:table AS regclass) AND contype='c'"
                ),
                {"table": table},
            )
            .mappings()
            .all()
        )
        for check in checks:
            definition = check["definition"]
            if not re.search(r"\bstate\b", definition):
                continue
            name = check["conname"]
            expression = definition[len("CHECK (") : -1]
            op.drop_constraint(name, table, type_="check")
            op.create_check_constraint(name, table, f"({expression}) OR state='PARTIAL'")
            # Keep the exact old guard for a reversible downgrade, without changing records.
            literal = str(
                sa.literal(_PREFIX + definition).compile(
                    dialect=connection.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )
            connection.exec_driver_sql(f'COMMENT ON CONSTRAINT "{name}" ON "{table}" IS {literal}')
    op.create_check_constraint(
        "ck_partial_fields",
        "compute_attempts",
        "state<>'PARTIAL' OR (started_at IS NOT NULL AND completed_at IS NOT NULL "
        "AND cleanup_confirmed_at IS NOT NULL AND result_manifest IS NOT NULL "
        "AND stop_requested_at IS NULL)",
    )
    original = connection.scalar(
        sa.text("SELECT pg_get_functiondef('compute_attempts_guard()'::regprocedure)")
    )
    modified = original.replace(
        "IF OLD.state IN ('SUCCEEDED'", "IF OLD.state IN ('PARTIAL','SUCCEEDED'"
    )
    modified = modified.replace(
        "NEW.state IN ('SUCCEEDED','FAILED','STOPPING')",
        "NEW.state IN ('SUCCEEDED','PARTIAL','FAILED','STOPPING')",
    )
    connection.execute(sa.text(modified))


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM compute_attempts WHERE state='PARTIAL')")
    ):
        raise RuntimeError("Cannot downgrade while immutable PARTIAL history exists")
    op.drop_constraint("ck_partial_fields", "compute_attempts", type_="check")
    for table in ("compute_jobs", "compute_attempts"):
        checks = (
            connection.execute(
                sa.text(
                    "SELECT conname,obj_description(oid,'pg_constraint') AS original "
                    "FROM pg_constraint WHERE conrelid=CAST(:table AS regclass) AND contype='c'"
                ),
                {"table": table},
            )
            .mappings()
            .all()
        )
        for check in checks:
            original = check["original"]
            if not original or not original.startswith(_PREFIX):
                continue
            op.drop_constraint(check["conname"], table, type_="check")
            definition = original[len(_PREFIX) :]
            op.create_check_constraint(check["conname"], table, definition[len("CHECK (") : -1])
    modified = connection.scalar(
        sa.text("SELECT pg_get_functiondef('compute_attempts_guard()'::regprocedure)")
    )
    original = modified.replace(
        "IF OLD.state IN ('PARTIAL','SUCCEEDED'", "IF OLD.state IN ('SUCCEEDED'"
    )
    original = original.replace(
        "NEW.state IN ('SUCCEEDED','PARTIAL','FAILED','STOPPING')",
        "NEW.state IN ('SUCCEEDED','FAILED','STOPPING')",
    )
    connection.execute(sa.text(original))
