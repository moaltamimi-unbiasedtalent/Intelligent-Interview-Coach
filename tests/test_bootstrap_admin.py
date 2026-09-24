"""The controlled platform-admin bootstrap script (Capstone P1/E1, §7)."""

from __future__ import annotations

from sqlalchemy import create_engine, select

from scripts import bootstrap_admin
from src.auth_repository import AccountRepository
from src.persistence import AuditEvent, Base, make_session_factory


def _db(tmp_path):
    url = f"sqlite:///{tmp_path/'admin.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    AccountRepository(sf).create_password_account(
        email="owner@example.com", password_hash="x", display_name=None
    )
    return url, sf


def test_dry_run_does_not_change_role(tmp_path):
    url, sf = _db(tmp_path)
    rc = bootstrap_admin.main(["--email", "owner@example.com", "--database-url", url])
    assert rc == 0
    assert AccountRepository(sf).find_by_email("owner@example.com").platform_role == "user"


def test_apply_promotes_and_audits(tmp_path):
    url, sf = _db(tmp_path)
    rc = bootstrap_admin.main(["--email", "owner@example.com", "--database-url", url, "--yes"])
    assert rc == 0
    assert AccountRepository(sf).find_by_email("owner@example.com").platform_role == "platform_admin"
    with sf() as s:
        events = s.scalars(select(AuditEvent).where(
            AuditEvent.event_type == "account.platform_role_change")).all()
        assert len(events) == 1 and events[0].result == "success"


def test_unknown_email_is_error(tmp_path):
    url, _ = _db(tmp_path)
    rc = bootstrap_admin.main(["--email", "ghost@example.com", "--database-url", url, "--yes"])
    assert rc == 1
