"""Shared harness for the 04E (invitation-only registration) tests. Real isolated SQLite, in-memory mail, no network."""

from __future__ import annotations

import json
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.auth_repository import AccountRepository
from src.invitations import repository as R
from src.persistence import AuditEvent, RegistrationInvitation, utcnow
from tests._auth_factories import build_auth_app, cookies_for, login_token

API = "/api/v1"
PW = "correcthorsebattery"
REFUSAL = {"code": "invitation_required", "message": "A valid invitation is required to register during the private beta."}


class Env:
    """An app in ``env`` ('staging' = invitation required; 'test' = local, off unless the override variable is set)."""

    def __init__(self, env: str = "staging"):
        self.app, self.repo, self.mail = build_auth_app(env=env)
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = AccountRepository(self.repo.session_factory)
        self.invites = R.InvitationRepository(self.repo.session_factory)
        self.sf = self.repo.session_factory
        self.n = 0

    def close(self):
        self.c.__exit__(None, None, None)

    # -- invitations ---------------------------------------------------------------------------------------------------
    def issue(self, *, email: str | None = None, ttl_days: int = 14, issued_by: int | None = None) -> tuple[str, R.InvitationView]:
        code = R.new_code()
        view = self.invites.issue(code_hash=R.hash_code(code), ttl_days=ttl_days, email=email, issued_by_user_id=issued_by)
        return code, view

    def expire(self, invitation_id: int) -> None:
        with self.sf() as s:
            row = s.get(RegistrationInvitation, invitation_id)
            row.created_at = utcnow() - timedelta(days=30)
            row.expires_at = utcnow() - timedelta(days=1)
            s.commit()

    def row(self, invitation_id: int) -> RegistrationInvitation:
        with self.sf() as s:
            r = s.get(RegistrationInvitation, invitation_id)
            s.expunge(r)
            return r

    # -- accounts ------------------------------------------------------------------------------------------------------
    def register(self, email: str, code: str | None = None, **extra):
        body = {"email": email, "password": PW, **extra}
        if code is not None:
            body["invitation_code"] = code
        return self.c.post(f"{API}/auth/register", json=body)

    def make_user(self, role: str = "user", email: str | None = None) -> tuple[int, dict]:
        """Create an account directly (bypassing registration, like an operator bootstrap) and sign in. Returns (user_id, cookies)."""
        from src.authsec import passwords

        self.n += 1
        email = email or f"u04e{self.n}@example.com"
        uid = self.accounts.create_password_account(email=email, password_hash=passwords.hash_password(PW), display_name=None)
        self.accounts.mark_email_verified(uid)
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        tok = login_token(self.c, email, PW)
        assert tok, "sign-in must work without any invitation"
        return uid, cookies_for(tok)

    def audit_rows(self) -> list[AuditEvent]:
        with self.sf() as s:
            return list(s.scalars(select(AuditEvent).order_by(AuditEvent.id)).all())

    def audit_blob(self) -> str:
        return json.dumps([{"t": e.event_type, "r": e.result, "tt": e.target_type, "ti": e.target_id, "c": e.context} for e in self.audit_rows()], default=str)

    def set_user_count(self, email: str) -> int:
        from sqlalchemy import func

        from src.persistence import User

        with self.sf() as s:
            return s.scalar(select(func.count()).select_from(User).where(User.email == email)) or 0


def refusal_body(resp) -> dict:
    """The error envelope minus the per-request id (everything a client can compare)."""
    err = resp.json()["error"]
    return {"code": err["code"], "message": err["message"]}


def full_database_text(env: Env) -> str:
    """Every cell of every table as text (to prove a plaintext code or address is nowhere at rest)."""
    from sqlalchemy import text

    out: list[str] = []
    with env.sf() as s:
        tables = [r[0] for r in s.execute(text("select name from sqlite_master where type='table'"))]
        for t in tables:
            for row in s.execute(text(f'select * from "{t}"')):
                out.append(" ".join(str(v) for v in row))
    return "\n".join(out)


__all__ = ["Env", "API", "PW", "REFUSAL", "refusal_body", "full_database_text"]
