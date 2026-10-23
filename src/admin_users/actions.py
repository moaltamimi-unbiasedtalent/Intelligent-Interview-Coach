"""Strict Admin Users actions (03C). Every method: re-reads CURRENT state inside ONE transaction, enforces self / hierarchy / stale-revision protection, mutates,
and stages the audit row in that same transaction. Reuses the existing domains (status + sessions in ``AdminUserRepository``, plans in ``PlanRepository``,
deletion through ``PrivacyRequestService``); nothing here re-implements them."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.admin_repository import AdminNotFound, AdminUserRepository, _stage
from src.admin_users import insights
from src.admin_users.guards import make_precondition
from src.application.errors import ConflictError
from src.persistence import ACCOUNT_STATUS_ACTIVE, TOKEN_PURPOSE_EMAIL_VERIFICATION, AuthToken, User, utcnow
from src.plans_repository import PlanRepository
from src.privacy.requests import PrivacyRequestService


def pending_verification_tokens(s, user_id: int, now) -> list[AuthToken]:
    """Outstanding (unconsumed, unexpired) email-verification links of one account. Shared by the single and the bulk expiry action."""
    return list(s.scalars(select(AuthToken).where(AuthToken.user_id == user_id, AuthToken.purpose == TOKEN_PURPOSE_EMAIL_VERIFICATION,
                                                  AuthToken.consumed_at.is_(None), AuthToken.expires_at > now)).all())


class UserActions:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory
        self._users = AdminUserRepository(session_factory)
        self._plans = PlanRepository(session_factory)
        self._privacy = PrivacyRequestService(session_factory)

    def detail_extras(self, user_id: int) -> dict | None:
        with self._sf() as s:
            user = s.get(User, user_id)
            return insights.build(s, user) if user else None

    def set_status(self, user_id: int, status: str, *, actor_user_id: int, expected_revision: str | None, audit: dict) -> dict:
        return self._users.set_status(user_id, status, audit=audit, precondition=make_precondition(
            actor_user_id=actor_user_id, expected_revision=expected_revision, self_message="You cannot change the status of your own account."))

    def force_signout(self, user_id: int, *, actor_user_id: int, expected_revision: str | None, audit: dict) -> int:
        return self._users.revoke_sessions(user_id, audit=audit, precondition=make_precondition(
            actor_user_id=actor_user_id, expected_revision=expected_revision, self_message="You cannot sign out your own sessions from Admin."))

    def assign_plan(self, user_id: int, plan_code: str, *, actor_user_id: int, expected_revision: str | None, audit: dict) -> dict:
        # Hierarchy does not apply: a plan is access, not authority. Self-assignment is still refused.
        return self._plans.assign(plan_code, user_id=user_id, source="admin", audit=audit, precondition=make_precondition(
            actor_user_id=actor_user_id, expected_revision=expected_revision, hierarchy=False, self_message="You cannot change your own plan."))

    def begin_verification_resend(self, user_id: int, *, actor_user_id: int, expected_revision: str, audit: dict) -> None:
        """Authorise and AUDIT the resend in one transaction; the mail itself is sent afterwards by the existing identity flow (an external side effect
        cannot join a database transaction, so the intent is recorded first and a delivery failure is recorded by that flow as ``account.email_failed``)."""
        check = make_precondition(actor_user_id=actor_user_id, expected_revision=expected_revision, self_message="Use your own account page to verify your email.")
        with self._sf() as s:
            user = s.get(User, user_id, with_for_update=True)
            if user is None:
                raise AdminNotFound("Account not found.")
            check(s, user)
            if user.status != ACCOUNT_STATUS_ACTIVE:
                raise ConflictError("Only an active account can receive a verification link.")
            if not user.email:
                raise ConflictError("This account has no email address.")
            if user.email_verified:
                raise ConflictError("This email address is already verified.")
            _stage(s, audit)
            s.commit()

    def expire_verification(self, user_id: int, *, actor_user_id: int, expected_revision: str, audit: dict) -> dict:
        check = make_precondition(actor_user_id=actor_user_id, expected_revision=expected_revision, self_message="You cannot do this to your own account.")
        with self._sf() as s:
            user = s.get(User, user_id, with_for_update=True)
            if user is None:
                raise AdminNotFound("Account not found.")
            check(s, user)
            now = utcnow()
            rows = pending_verification_tokens(s, user_id, now)
            for row in rows:
                row.consumed_at = now
            _stage(s, audit, links_expired=len(rows))
            s.commit()
            return {"user_id": user_id, "links_expired": len(rows), "changed": bool(rows)}

    def request_deletion(self, user_id: int, *, actor_user_id: int, expected_revision: str, audit: dict) -> dict:
        """Record a deletion request through the EXISTING privacy-request pipeline. Executing it stays a separate, privacy-gated step
        (``POST /admin/privacy/requests/{id}/execute-deletion``) that queues the same job candidates use."""
        existing = self.detail_extras(user_id)
        if existing is None:
            raise AdminNotFound("Account not found.")
        open_id = existing["cases"]["open_deletion_request_id"]
        if open_id:   # idempotent: never a second open deletion request for the same account
            return {"user_id": user_id, "request_id": open_id, "created": False}
        created = self._privacy.create(user_id, "deletion", None, source="admin_recorded", created_by_user_id=actor_user_id, audit=audit,
                                       precondition=make_precondition(actor_user_id=actor_user_id, expected_revision=expected_revision,
                                                                      self_message="Request deletion of your own account from your privacy settings."))
        return {"user_id": user_id, "request_id": created["public_id"], "created": True}
