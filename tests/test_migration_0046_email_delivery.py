"""05D migration 0046 (email_attempts delivery evidence): chain, ORM parity, CHECK, existing rows untouched, and the FAIL-CLOSED downgrade."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests._alembic_head import assert_chain
from tests.test_billing_f1_qualification import _alembic

REV, PREV = "0046_email_delivery_events", "0045_monitoring_alert_categories"
_INS = ("insert into email_attempts (message_type, provider, status, created_at, delivery_state) values ('email_verification', 'brevo', 'provider_accepted', "
        "'2020-01-01 00:00:00.000000', :s)")


def test_0046_chains_from_0045_and_the_chain_stays_single_and_linear(tmp_path, monkeypatch):
    from alembic.script import ScriptDirectory

    cfg, _ = _alembic(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision(REV).down_revision == PREV
    assert len(script.get_heads()) == 1 and assert_chain(require=(REV,)) == script.get_heads()[0]


def test_upgrade_adds_nullable_columns_matching_the_orm_and_keeps_existing_rows(tmp_path, monkeypatch):
    from alembic import command

    from src.persistence import EmailAttempt

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, PREV)
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("insert into email_attempts (message_type, provider, status, created_at) values ('password_reset', 'brevo', 'provider_accepted', '2020-01-01 00:00:00.000000')"))
    command.upgrade(cfg, REV)
    insp = inspect(eng)
    cols = {c["name"]: c for c in insp.get_columns("email_attempts")}
    assert set(cols) == {c.name for c in EmailAttempt.__table__.columns}
    for name in ("delivery_state", "delivery_event_at", "delivery_event_digest"):
        assert cols[name]["nullable"] is True
    assert "recipient" not in cols and "email" not in cols and "payload" not in cols and "body" not in cols
    assert "ix_email_attempts_message_ref" in {i["name"] for i in insp.get_indexes("email_attempts")}
    with eng.connect() as c:
        assert c.execute(text("select delivery_state, delivery_event_digest from email_attempts")).all() == [(None, None)]       # nothing backfilled


def test_check_constraint_accepts_the_allow_list_and_null_and_rejects_anything_else(tmp_path, monkeypatch):
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    eng = create_engine(url)
    with eng.begin() as c:
        for s in ("delivered", "soft_bounced", "blocked", "hard_bounced", "complained", None):
            c.execute(text(_INS), {"s": s})
    for bad in ("opened", "bounced", "DELIVERED", ""):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(_INS), {"s": bad})


def test_downgrade_with_no_evidence_is_clean_and_reversible(tmp_path, monkeypatch):
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text(_INS), {"s": None})
    command.downgrade(cfg, PREV)
    insp = inspect(eng)
    assert "delivery_state" not in {c["name"] for c in insp.get_columns("email_attempts")}
    assert "ix_email_attempts_message_ref" not in {i["name"] for i in insp.get_indexes("email_attempts")}
    with eng.connect() as c:
        assert c.execute(text("select count(*) from email_attempts")).scalar() == 1            # the attempt row survived
    command.upgrade(cfg, REV)


def test_downgrade_is_fail_closed_while_any_row_carries_delivery_evidence(tmp_path, monkeypatch):
    from alembic import command

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, REV)
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text(_INS), {"s": "hard_bounced"})
    with pytest.raises(Exception) as err:
        command.downgrade(cfg, PREV)
    assert "Refusing to downgrade 0046_email_delivery_events" in str(err.value)
    with eng.connect() as c:                                            # nothing was deleted or altered
        assert c.execute(text("select delivery_state from email_attempts")).scalar() == "hard_bounced"
    assert "delivery_state" in {c["name"] for c in inspect(eng).get_columns("email_attempts")}
