"""Migration 0007 (identity/platform) preserves existing user-scoped data (P1/E1).

Proves the critical legacy-preservation requirement: upgrading an existing Sprint 4
database to the identity foundation orphans NOTHING, backfills one identity + a basic
entitlement per user, and survives upgrade → downgrade → re-upgrade.
"""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("alembic") is None,
    reason="alembic not installed (pip install -e \".[db]\")",
)


def _cfg(db_url: str):
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _seed_legacy(engine):
    """Insert transitional (pre-identity) users + owned candidate resources."""
    import sqlalchemy as sa

    with engine.begin() as c:
        c.execute(sa.text(
            "INSERT INTO users (subject, provider, display_name, email, created_at, updated_at) "
            "VALUES ('local-dev','dev','Local dev','dev@example.com', datetime('now'), datetime('now'))"
        ))
        c.execute(sa.text(
            "INSERT INTO users (subject, provider, email, created_at, updated_at) "
            "VALUES ('google-sub-1','https://accounts.google.com','alice@example.com', datetime('now'), datetime('now'))"
        ))
        c.execute(sa.text(
            "INSERT INTO interviews (user_id, configuration, status, created_at) "
            "VALUES (1, '{}', 'completed', datetime('now'))"
        ))
        c.execute(sa.text(
            "INSERT INTO preparation_memories (user_id, category, summary, pinned, created_at, updated_at) "
            "VALUES (2,'gap','System design', 0, datetime('now'), datetime('now'))"
        ))


def test_upgrade_preserves_data_and_backfills(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text

    db_url = f"sqlite:///{tmp_path/'legacy.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = _cfg(db_url)

    # Existing Sprint 4 database at the pre-identity head.
    command.upgrade(cfg, "0006_user_feedback")
    engine = create_engine(db_url)
    _seed_legacy(engine)

    # Upgrade to the identity foundation.
    command.upgrade(cfg, "0007_identity_platform")

    with engine.begin() as c:
        users = c.execute(text(
            "SELECT id, platform_role, status, email_verified FROM users ORDER BY id")).fetchall()
        idents = c.execute(text(
            "SELECT user_id, provider, provider_subject, email FROM account_identities ORDER BY user_id")).fetchall()
        ents = c.execute(text("SELECT user_id, tier FROM product_entitlements ORDER BY user_id")).fetchall()
        interviews = c.execute(text("SELECT user_id FROM interviews")).fetchall()
        memories = c.execute(text("SELECT user_id, summary FROM preparation_memories")).fetchall()

    # Principal columns backfilled with safe defaults.
    assert [(u[1], u[2], u[3]) for u in users] == [("user", "active", 0), ("user", "active", 0)]
    # One identity backfilled per user, preserving (provider, subject).
    assert idents == [
        (1, "dev", "local-dev", "dev@example.com"),
        (2, "https://accounts.google.com", "google-sub-1", "alice@example.com"),
    ]
    # A basic entitlement per user.
    assert ents == [(1, "basic"), (2, "basic")]
    # Candidate data ownership is UNCHANGED (nothing orphaned).
    assert interviews == [(1,)]
    assert memories == [(2, "System design")]


def test_upgrade_downgrade_reupgrade_cycles_cleanly(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    db_url = f"sqlite:///{tmp_path/'cycle.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = _cfg(db_url)

    command.upgrade(cfg, "0006_user_feedback")
    engine = create_engine(db_url)
    _seed_legacy(engine)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006_user_feedback")

    insp = inspect(engine)
    # Identity tables are gone after downgrade; candidate data remains.
    assert "account_identities" not in insp.get_table_names()
    assert "users" in insp.get_table_names()
    from sqlalchemy import text
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM interviews")).scalar() == 1
        cols = {col["name"] for col in insp.get_columns("users")}
        assert "platform_role" not in cols

    # Re-upgrade restores the identity foundation and re-backfills deterministically.
    command.upgrade(cfg, "head")
    insp = inspect(engine)
    assert "account_identities" in insp.get_table_names()
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM account_identities")).scalar() == 2
        assert c.execute(text("SELECT count(*) FROM interviews")).scalar() == 1
