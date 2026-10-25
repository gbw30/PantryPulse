"""Immutable request journal for operational writes that do not move stock."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.models.operational import Base, OwnedIdentity, check, owned


class HTTPCommand(OwnedIdentity, Base):
    __tablename__ = "http_commands"
    actor = mapped_column(sa.String(200), nullable=False)
    operation = mapped_column(sa.String(100), nullable=False)
    key = mapped_column(sa.String(128), nullable=False)
    request_hash = mapped_column(sa.String(64), nullable=False)
    result = mapped_column(JSONB, nullable=False)
    __table_args__ = owned(
        sa.UniqueConstraint("organization_id", "actor", "operation", "key"),
        check("request_hash ~ '^[0-9a-f]{64}$'", "hash"),
        check("jsonb_typeof(result) = 'object'", "result"),
    )
