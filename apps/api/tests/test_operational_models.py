"""Metadata boundaries; PostgreSQL tests separately establish actual integrity."""

from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateTable

from app.models.operational import Base


def test_domain_metadata_is_tenant_scoped_and_excludes_compute():
    assert len(Base.metadata.tables) >= 20
    for name, table in Base.metadata.tables.items():
        assert not any(word in name for word in ("job", "forecast", "scenario"))
        if name != "organizations":
            assert "organization_id" in table.c
            assert any(
                constraint.referred_table.name == "organizations"
                for constraint in table.foreign_key_constraints
            )
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=dialect()))
