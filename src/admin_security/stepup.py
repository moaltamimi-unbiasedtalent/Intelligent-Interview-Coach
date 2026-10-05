"""Password step-up (P10B-W10.13): re-authentication of the CURRENT server-side session. It is NOT multi-factor authentication.

The Admin submits their current password; the server verifies it against the stored hash, then marks that exact session elevated for ``STEP_UP_WINDOW_SECONDS``.
The plaintext is never stored, logged or audited, there is no browser-held elevation token, and an account with no local password credential (OIDC-only) fails
closed: OIDC re-authentication is not validated in the Capstone, and an ordinary OIDC session is never treated as elevated.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import sessionmaker

from src.application import admin_audit as A
from src.auth_repository import AccountRepository, AuditRepository, SessionRepository
from src.authsec import passwords, tokens
from src.admin_security.errors import StepUpFailed, StepUpRequired, StepUpUnavailable

STEP_UP_WINDOW_SECONDS = 5 * 60


class StepUpService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._accounts = AccountRepository(session_factory)
        self._sessions = SessionRepository(session_factory)
        self._audit = AuditRepository(session_factory)

    def status(self, session_token: str | None) -> dict:
        until = self._sessions.elevated_until(tokens.hash_token(session_token)) if session_token else None
        return {"elevated": until is not None, "elevated_until": until.isoformat() if until else None, "window_seconds": STEP_UP_WINDOW_SECONDS,
                "method": "password_reauthentication"}

    def confirm(self, *, user_id: int, session_token: str | None, password: str, request_id: str | None) -> dict:
        if not session_token:
            raise StepUpUnavailable("Confirming your password requires a signed-in session.")
        stored = self._accounts.get_password_hash(user_id)
        if stored is None:  # OIDC-only (or no credential): unavailable, never elevated
            raise StepUpUnavailable("Password confirmation is not available for this account.")
        ok = passwords.verify_password(password or "", stored)
        if not ok:
            self._audit.record(**A.build_audit(event_type=A.ADMIN_STEP_UP_FAILED, actor_user_id=user_id, request_id=request_id, result="failure",
                                               target_type="session"))
            raise StepUpFailed("That password was not accepted.")
        until = self._sessions.elevate(tokens.hash_token(session_token), seconds=STEP_UP_WINDOW_SECONDS)
        if until is None:
            raise StepUpUnavailable("Confirming your password requires a signed-in session.")
        self._audit.record(**A.build_audit(event_type=A.ADMIN_STEP_UP_SUCCEEDED, actor_user_id=user_id, request_id=request_id, target_type="session",
                                           window_seconds=STEP_UP_WINDOW_SECONDS))
        return {"elevated": True, "elevated_until": until.isoformat(), "window_seconds": STEP_UP_WINDOW_SECONDS, "method": "password_reauthentication"}

    def require(self, session_token: str | None) -> datetime:
        """Raise StepUpRequired unless THIS session is currently elevated."""
        until = self._sessions.elevated_until(tokens.hash_token(session_token)) if session_token else None
        if until is None:
            raise StepUpRequired("Confirm your password to continue.")
        return until
