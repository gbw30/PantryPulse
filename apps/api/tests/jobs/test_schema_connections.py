"""Neon pooled connections must not use unsupported startup search_path options."""

import sqlalchemy as sa

from app.repositories.jobs import create_queue_engine


def test_schema_is_selected_per_transaction_instead_of_startup(monkeypatch):
    captured = {}
    original = sa.create_engine

    def capture(*args, **kwargs):
        captured.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(sa, "create_engine", capture)
    engine = create_queue_engine("postgresql://unused:unused@localhost/unused", schema="demo_scope")
    try:
        assert "options" not in captured["connect_args"]
        assert list(engine.dispatch.begin), "Every transaction must select the validated schema"
    finally:
        engine.dispose()
