"""W12.4D-P5-B: PostgreSQL portability of the migration chain, enforced WITHOUT a PostgreSQL server (the real server run is ``tests/test_pg_p5b.py``).

Executing ``alembic upgrade head`` on a fresh PostgreSQL database found three defects that SQLite silently accepted: (1) revision ids longer than 32 characters overflow
the default ``alembic_version.version_num``; (2) BOOLEAN columns declared with a numeric default (``DEFAULT 0``); (3) CHECK constraints comparing a BOOLEAN to ``1``.
These tests keep them from coming back."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from src import db_migration_support as D

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "migrations/versions").glob("0*.py")) + [ROOT / "src/persistence.py"]


def test_no_boolean_column_has_a_numeric_server_default_in_any_migration():
    offenders = []
    for f in FILES[:-1]:
        text = f.read_text()
        for m in re.finditer(r"sa\.Column\((?:[^()]|\([^()]*\))*sa\.Boolean\(\)(?:[^()]|\([^()]*\))*\)", text):
            if re.search(r'server_default=(?:sa\.text\(["\'][01]["\']\)|["\'][01]["\'])', m.group(0)):
                offenders.append(f"{f.name}: {m.group(0)[:80]}")
    assert offenders == []


def test_no_check_constraint_compares_a_boolean_column_to_an_integer_literal():
    boolean_names = {"enabled", "is_baseline", "paused", "applied", "review_required", "cancel_at_period_end", "email_verified"}
    offenders = []
    for f in FILES:
        for m in re.finditer(r"CheckConstraint\(\s*[\"']([^\"']*)[\"']", f.read_text()):
            for col in boolean_names:
                if re.search(rf"\b{col}\s*=\s*[01]\b", m.group(1)):
                    offenders.append(f"{f.name}: {m.group(1)[:80]}")
    assert offenders == []


def test_every_revision_id_that_exceeds_the_default_version_column_is_covered_by_the_widening_helper():
    long_ids = [re.search(r'^revision\s*=\s*["\']([^"\']+)', f.read_text(), re.M).group(1) for f in FILES[:-1]]
    assert any(len(i) > 32 for i in long_ids), "premise: some revision ids are longer than Alembic's default VARCHAR(32)"
    assert D.VERSION_COLUMN_WIDTH >= max(len(i) for i in long_ids)


def test_the_widening_helper_is_a_no_op_off_postgresql_and_issues_the_idempotent_ddl_on_postgresql():
    calls = []
    sqlite = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"), execute=lambda *a: calls.append("x"), commit=lambda: calls.append("c"))
    D.widen_version_table(sqlite)
    assert calls == []
    pg = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), execute=lambda stmt: calls.append(str(stmt)), commit=lambda: calls.append("commit"))
    D.widen_version_table(pg)
    assert "CREATE TABLE IF NOT EXISTS alembic_version" in calls[0] and "VARCHAR(255)" in calls[0] and "ALTER COLUMN version_num TYPE VARCHAR(255)" in calls[1] and calls[-1] == "commit"


def test_the_migration_environment_widens_the_version_table_before_running_migrations():
    env = (ROOT / "migrations/env.py").read_text()
    assert env.index("widen_version_table(connection)") < env.index("context.configure(connection=connection")


def test_the_test_isolation_guard_still_refuses_every_postgresql_database_except_the_announced_throwaway_one(monkeypatch):
    import pytest
    import sqlalchemy
    monkeypatch.delenv("P5B_PG_ADMIN_URL", raising=False)
    for url in ("postgresql+psycopg://u@127.0.0.1:5432/ask4mo", "postgresql+psycopg://u@db.example.com/prod", "postgresql+psycopg://p5b@127.0.0.1:54329/p5b_x"):
        with pytest.raises(RuntimeError):
            sqlalchemy.create_engine(url)                                           # nothing is announced: even a p5b_ name is refused
    monkeypatch.setenv("P5B_PG_ADMIN_URL", "postgresql+psycopg://p5b@127.0.0.1:54329/postgres")
    for url in ("postgresql+psycopg://p5b@127.0.0.1:54329/ask4mo", "postgresql+psycopg://p5b@127.0.0.1:5432/p5b_x", "postgresql+psycopg://p5b@db.example.com:54329/p5b_x"):
        with pytest.raises(RuntimeError):
            sqlalchemy.create_engine(url)                                           # wrong database name, port or host
    sqlalchemy.create_engine("postgresql+psycopg://p5b@127.0.0.1:54329/p5b_ok").dispose()
