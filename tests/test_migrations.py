"""Phase 6: Alembic baseline migration produces the expected schema.

Skipped when alembic is not installed (it ships in the optional [db] extra).
Runs the immutable 0001 baseline against a throwaway SQLite database and checks
the tables/indexes it creates, then that downgrade removes them.
"""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("alembic") is None,
    reason="alembic not installed (pip install -e \".[db]\")",
)

_EXPECTED_TABLES = {"users", "interviews", "questions", "answers", "reports"}
_EXPECTED_INDEXES = {
    "ix_users_subject", "ix_interviews_user_id", "ix_questions_interview_id",
    "ix_answers_question_id", "ix_reports_interview_id",
}
# Phase 7 (0002) adds the long-term preparation-memory table.
_MEMORY_TABLE = "preparation_memories"
_MEMORY_INDEXES = {
    "ix_preparation_memories_user_id", "ix_preparation_memories_user_category",
}


def _alembic_config(db_url: str):
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_upgrade_head_creates_baseline_schema(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'m.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)  # env.py reads this
    command.upgrade(_alembic_config(db_url), "head")

    insp = inspect(create_engine(db_url))
    tables = set(insp.get_table_names())
    assert _EXPECTED_TABLES <= tables
    assert _MEMORY_TABLE in tables  # 0002 preparation-memory table present at head
    assert "interview_sessions" in tables  # 0003 durable interview sessions at head
    indexes = {ix["name"] for t in _EXPECTED_TABLES for ix in insp.get_indexes(t)}
    assert _EXPECTED_INDEXES <= indexes
    memory_indexes = {ix["name"] for ix in insp.get_indexes(_MEMORY_TABLE)}
    assert _MEMORY_INDEXES <= memory_indexes


def test_single_head_after_phase10(tmp_path, monkeypatch):
    # Alembic must have exactly one head, and it must be the 0004 revision (Phase 10
    # pre-merge correction: completed-history source_session_id idempotency).
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert list(heads) == ["0004_completed_interview_source_session"]


def test_upgrade_head_adds_source_session_id(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'m.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    command.upgrade(_alembic_config(db_url), "head")

    insp = inspect(create_engine(db_url))
    cols = {c["name"] for c in insp.get_columns("interviews")}
    idx = {i["name"] for i in insp.get_indexes("interviews")}
    assert "source_session_id" in cols
    assert "uq_interviews_user_source_session" in idx


def test_downgrade_0004_keeps_phase10_schema(tmp_path, monkeypatch):
    # 0004 → 0003 removes only source_session_id; interview_sessions is untouched.
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'m.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0003_interview_sessions")

    insp = inspect(create_engine(db_url))
    assert "source_session_id" not in {c["name"] for c in insp.get_columns("interviews")}
    assert "interview_sessions" in insp.get_table_names()  # 0003 intact


def test_downgrade_0003_keeps_phase7_schema(tmp_path, monkeypatch):
    # 0003 → 0002 removes only the interview_sessions table; nothing else is touched.
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'m.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0002_preparation_memory")

    tables = set(inspect(create_engine(db_url)).get_table_names())
    assert "interview_sessions" not in tables   # 0003 table removed
    assert _MEMORY_TABLE in tables               # 0002 intact
    assert _EXPECTED_TABLES <= tables            # 0001 baseline intact


def test_downgrade_0002_keeps_baseline_schema(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'m.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001_initial")

    tables = set(inspect(create_engine(db_url)).get_table_names())
    assert _MEMORY_TABLE not in tables      # 0002 table removed
    assert _EXPECTED_TABLES <= tables        # 0001 baseline intact


def test_downgrade_base_removes_schema(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'m.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tables = set(inspect(create_engine(db_url)).get_table_names())
    assert not (_EXPECTED_TABLES & tables)  # all baseline tables dropped


def test_baseline_migration_does_not_import_live_metadata():
    # The baseline must be immutable: it must NOT create the schema from the live
    # model metadata (which would let later model edits mutate migration 0001).
    from pathlib import Path

    source = Path("migrations/versions/0001_initial.py").read_text()
    assert "metadata.create_all" not in source
    assert "op.create_table" in source
