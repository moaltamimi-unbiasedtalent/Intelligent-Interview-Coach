"""04E migration 0042 (registration_invitations): upgrade, schema parity with the ORM, constraints, and the FAIL-CLOSED downgrade."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests._alembic_head import assert_chain
from tests.test_billing_f1_qualification import _alembic

REV, PREV = "0042_registration_invitations", "0041_report_configurations"
_INS = ("insert into registration_invitations (code_hash, email_hash, created_at, expires_at, redeemed_at, revoked_at) "
        "values (:h, null, :c, :e, :r, :v)")


def _row(c, h, *, created="2020-01-01 00:00:00.000000", expires="2999-01-01 00:00:00.000000", redeemed=None, revoked=None):
    c.execute(text(_INS), {"h": h, "c": created, "e": expires, "r": redeemed, "v": revoked})


def test_0042_chains_from_0041_and_is_in_the_single_linear_chain(tmp_path, monkeypatch):
    from alembic.script import ScriptDirectory

    cfg, _ = _alembic(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision(REV).down_revision == PREV
    assert len(script.get_heads()) == 1 and assert_chain(require=(REV,)) == script.get_heads()[0]


def test_upgrade_creates_the_table_with_the_orm_shape(tmp_path, monkeypatch):
    from alembic import command

    from src.persistence import RegistrationInvitation

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    insp = inspect(create_engine(url))
    cols = {c["name"]: c for c in insp.get_columns("registration_invitations")}
    orm = RegistrationInvitation.__table__
    assert set(cols) == {c.name for c in orm.columns}
    for c in orm.columns:
        assert cols[c.name]["nullable"] == c.nullable, c.name
    assert {"code_hash", "created_at", "expires_at"} == {n for n, c in cols.items() if not c["nullable"] and n != "id"}
    assert "code" not in cols and "plaintext_code" not in cols and "email" not in cols          # no plaintext code or address column exists
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("registration_invitations")}
    assert ("code_hash",) in uniques
    assert "ix_registration_invitations_expires" in {i["name"] for i in insp.get_indexes("registration_invitations")}
    fks = {fk["constrained_columns"][0]: (fk["referred_table"], fk["options"].get("ondelete")) for fk in insp.get_foreign_keys("registration_invitations")}
    assert fks == {"issued_by_user_id": ("users", "SET NULL"), "redeemed_by_user_id": ("users", "SET NULL"), "revoked_by_user_id": ("users", "SET NULL")}


def test_constraints_reject_duplicate_hashes_and_non_expiring_rows(tmp_path, monkeypatch):
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    eng = create_engine(url)
    with eng.begin() as c:
        _row(c, "h1")
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            _row(c, "h1")                                                  # unique code hash
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            _row(c, "h2", created="2025-01-02 00:00:00.000000", expires="2025-01-01 00:00:00.000000")      # expires_at must follow created_at


def test_upgrade_preserves_every_existing_row_and_user(tmp_path, monkeypatch):
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, PREV)
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("insert into users (subject, provider, status, platform_role, email_verified, created_at, updated_at) "
                       "values ('legacy-user', 'password', 'active', 'user', 0, '2026-01-01', '2026-01-01')"))
        before = c.execute(text("select count(*) from users")).scalar()
    command.upgrade(cfg, REV)
    with eng.connect() as c:
        assert c.execute(text("select count(*) from users")).scalar() == before        # existing users are untouched
        assert c.execute(text("select count(*) from registration_invitations")).scalar() == 0     # nothing is seeded


def test_downgrade_is_fail_closed_for_pending_and_redeemed_rows_then_allowed_when_only_dead_rows_remain(tmp_path, monkeypatch):
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    eng = create_engine(url)
    # 1) a PENDING invitation blocks it and nothing is deleted
    with eng.begin() as c:
        _row(c, "pending")
    with pytest.raises(RuntimeError, match="Refusing to downgrade 0042_registration_invitations"):
        command.downgrade(cfg, PREV)
    with eng.connect() as c:
        assert c.execute(text("select count(*) from registration_invitations")).scalar() == 1
        assert c.execute(text("select version_num from alembic_version")).scalar() == REV
    # 2) a REDEEMED invitation blocks it too
    with eng.begin() as c:
        c.execute(text("delete from registration_invitations"))
        _row(c, "redeemed", redeemed="2025-06-01 00:00:00.000000")
    with pytest.raises(RuntimeError, match="live invitation"):
        command.downgrade(cfg, PREV)
    # 3) only revoked and expired rows left: allowed (they grant nothing and can be recreated)
    with eng.begin() as c:
        c.execute(text("delete from registration_invitations"))
        _row(c, "revoked", revoked="2025-06-01 00:00:00.000000")
        _row(c, "expired", expires="2021-01-01 00:00:00.000000")
    command.downgrade(cfg, PREV)
    with eng.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == PREV
        assert "registration_invitations" not in inspect(c).get_table_names()
    command.upgrade(cfg, REV)                                               # and it re-applies
    assert "registration_invitations" in inspect(create_engine(url)).get_table_names()


def test_create_all_and_the_migration_agree_on_the_table(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session  # noqa: F401

    from src.persistence import Base

    eng = create_engine(f"sqlite:///{tmp_path / 'ca.db'}")
    Base.metadata.create_all(eng)
    created = {c["name"] for c in inspect(eng).get_columns("registration_invitations")}
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    assert created == {c["name"] for c in inspect(create_engine(url)).get_columns("registration_invitations")}


# ===================================================================== privacy schema invariant (the one shared guard 0042 interacts with)
def _privacy_evaluator():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("eval_privacy_controls_04e", root / "scripts/eval_privacy_controls.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return root, mod


def test_0042_only_points_at_users_with_foreign_keys_and_the_privacy_invariant_still_holds():
    import tests.conftest  # noqa: F401  (isolation first)
    from src.persistence import Base

    root, ev = _privacy_evaluator()
    known = set(Base.metadata.tables)
    src = (root / "migrations/versions/0042_registration_invitations.py").read_text(encoding="utf-8")
    assert ev.migration_tables_touched(src, known) == {"registration_invitations"}      # its own table only; "users.id" targets are references, not changes
    assert ev.post_baseline_privacy_touches(root / "migrations/versions", known) == {}


_FK = 'op.create_table("t", sa.Column("u", sa.Integer()), sa.ForeignKeyConstraint(["u"], ["users.id"]))\n'


@pytest.mark.parametrize("body, tables", [
    ('def upgrade():\n    op.add_column("users", sa.Column("x", sa.Text()))\n', ["users"]),
    ('def upgrade():\n    op.create_foreign_key("fk", "interviews", "users", ["user_id"], ["id"])\n', ["interviews", "users"]),
    ('def upgrade():\n    op.execute("UPDATE users SET status = 1")\n', ["users"]),
])
def test_foreign_key_targets_are_exempt_but_every_real_alteration_of_a_privacy_table_still_fails(tmp_path, body, tables):
    import tests.conftest  # noqa: F401
    from src.persistence import Base

    _, ev = _privacy_evaluator()
    known = set(Base.metadata.tables)
    head = '"""x"""\nimport sqlalchemy as sa\nfrom alembic import op\n'
    only_fk = tmp_path / "only_fk"
    only_fk.mkdir()
    (only_fk / "0099_only_fk.py").write_text(head + "def upgrade():\n    " + _FK, encoding="utf-8")
    assert ev.post_baseline_privacy_touches(only_fk, known) == {}                  # a migration with ONLY a foreign-key target passes
    altering = tmp_path / "altering"
    altering.mkdir()
    (altering / "0100_alter.py").write_text(head + body.replace("def upgrade():\n", "def upgrade():\n    " + _FK, 1), encoding="utf-8")
    assert ev.post_baseline_privacy_touches(altering, known) == {"0100_alter.py": tables}     # the same migration ALSO altering the table is still flagged
