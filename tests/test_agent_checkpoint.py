"""Sprint 4 Phase 8 — agent checkpoint saver selection.

Verifies the checkpointer factory picks an official durable SQLite saver for a
file DB, falls back to a transient MemorySaver for :memory:/unset, keeps the
checkpoint file separate from the application DB, and never leaks the URL.
"""

from __future__ import annotations

from src.agent.checkpoint import build_checkpointer, sqlite_path_from_url


def test_sqlite_path_normalisation():
    assert sqlite_path_from_url("sqlite:///app.db") == "app.db"
    assert sqlite_path_from_url("sqlite:////abs/app.db") == "/abs/app.db"
    assert sqlite_path_from_url("sqlite:///:memory:") == ":memory:"
    assert sqlite_path_from_url("bare/path.db") == "bare/path.db"
    assert sqlite_path_from_url("postgresql://x/y") is None


def test_file_sqlite_yields_durable_saver(tmp_path):
    db = tmp_path / "app.db"
    info = build_checkpointer(database_url=f"sqlite:///{db}")
    assert info.kind == "sqlite" and info.durable is True
    from langgraph.checkpoint.sqlite import SqliteSaver
    assert isinstance(info.saver, SqliteSaver)


def test_checkpoint_file_is_separate_from_application_db(tmp_path):
    db = tmp_path / "app.db"
    build_checkpointer(database_url=f"sqlite:///{db}")
    # A dedicated checkpoint file is created next to (not inside) the app DB.
    assert (tmp_path / "agent_checkpoints.sqlite").exists()


def test_memory_url_is_transient_fallback():
    info = build_checkpointer(database_url="sqlite:///:memory:")
    assert info.kind == "memory" and info.durable is False


def test_unset_url_is_transient_fallback(monkeypatch):
    monkeypatch.delenv("AGENT_CHECKPOINT_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    info = build_checkpointer(database_url=None)
    assert info.kind == "memory" and info.durable is False


def test_info_detail_never_contains_a_url(tmp_path):
    db = tmp_path / "secret-path.db"
    info = build_checkpointer(database_url=f"sqlite:///{db}")
    assert "secret-path" not in info.detail  # SAFE label only, never the URL/path
