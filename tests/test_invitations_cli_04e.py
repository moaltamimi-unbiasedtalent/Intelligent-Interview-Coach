"""04E operator bootstrap: ``scripts/issue_invitation.py`` (dry-run default, code printed once, hash only at rest, metadata-only audit)."""

from __future__ import annotations

import re

from sqlalchemy import create_engine, select, text

from scripts import issue_invitation
from src.invitations import repository as R
from src.persistence import AuditEvent, Base, RegistrationInvitation, make_session_factory


def _db(tmp_path):
    url = f"sqlite:///{tmp_path / 'inv.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return url, make_session_factory(engine)


def test_dry_run_writes_nothing(tmp_path, capsys):
    url, sf = _db(tmp_path)
    assert issue_invitation.main(["--database-url", url]) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    with sf() as s:
        assert s.scalars(select(RegistrationInvitation)).all() == []


def test_issue_prints_the_code_once_and_stores_only_its_hash(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://staging.example.com")
    url, sf = _db(tmp_path)
    assert issue_invitation.main(["--database-url", url, "--yes", "--email", "Owner@Example.com", "--expires-days", "3"]) == 0
    out = capsys.readouterr().out
    code = re.search(r"code: (\S+)", out).group(1)
    assert f"link: https://staging.example.com/register#invitation={code}" in out
    with sf() as s:
        row = s.scalars(select(RegistrationInvitation)).one()
        assert row.code_hash == R.hash_code(code) and row.issued_by_user_id is None and row.email_hint == "o***@e***.com"
        assert code not in " ".join(str(v) for v in s.execute(text("select * from registration_invitations")).one())
        ev = s.scalars(select(AuditEvent).where(AuditEvent.event_type == "admin.invitation_issued")).one()
        assert ev.actor_user_id is None and ev.context["origin"] == "cli" and ev.context["ttl_days"] == 3 and ev.context["email_bound"] is True
        blob = str(ev.context) + str(ev.target_id)
        assert code not in blob and "owner@example.com" not in blob.lower() and row.code_hash not in blob
    assert R.peek(sf, code=code, email="owner@example.com") is None                  # usable by the bound address
    assert R.peek(sf, code=code, email="intruder@example.com") == R.REASON_EMAIL_MISMATCH


def test_bad_arguments_are_refused_before_any_write(tmp_path, capsys):
    url, sf = _db(tmp_path)
    assert issue_invitation.main(["--database-url", url, "--yes", "--expires-days", "0"]) == 2
    assert issue_invitation.main(["--database-url", url, "--yes", "--expires-days", "31"]) == 2
    assert issue_invitation.main(["--database-url", url, "--yes", "--email", "nope"]) == 2
    with sf() as s:
        assert s.scalars(select(RegistrationInvitation)).all() == []
    assert capsys.readouterr().out.count("code:") == 0
