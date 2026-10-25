"""Immutable operational HTTP command journal; no existing data rewrites."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "pp49_0005"
down_revision = "pp45_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "http_commands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT",
                                name=op.f("fk_http_commands_organization_id_organizations")),
        sa.UniqueConstraint("organization_id", "id",
                            name=op.f("uq_http_commands_organization_id_id")),
        sa.UniqueConstraint("organization_id", "actor", "operation", "key",
                            name=op.f("uq_http_commands_organization_id_actor_operation_key")),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'",
                           name=op.f("ck_http_commands_hash")),
        sa.CheckConstraint("jsonb_typeof(result) = 'object'",
                           name=op.f("ck_http_commands_result")),
    )
    op.execute("""CREATE FUNCTION pp49_immutable_command() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'HTTP command records are immutable'
        USING ERRCODE = 'integrity_constraint_violation'; END $$""")
    op.execute("CREATE TRIGGER pp49_immutable BEFORE UPDATE OR DELETE ON http_commands "
               "FOR EACH ROW EXECUTE FUNCTION pp49_immutable_command()")


def downgrade():
    op.drop_table("http_commands")
    op.execute("DROP FUNCTION pp49_immutable_command()")
