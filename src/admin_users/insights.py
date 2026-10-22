"""Read model for the complete Admin user detail (03C). Counts, buckets and states only: no ticket subject or message, no privacy note, no token, no email
beyond what the existing account summary already carries, no provider subject, no timestamp of activity finer than a bucket."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.admin_repository import OPEN_PRIVACY_STATUSES, activity_bucket
from src.admin_users.revision import account_revision
from src.persistence import (
    MEMBERSHIP_STATUS_ACTIVE, TOKEN_PURPOSE_EMAIL_VERIFICATION, WORKSPACE_ROLE_OWNER, AccountIdentity, AdminRoleChangeRequest, AuthSession, AuthToken,
    PasswordCredential, PrivacyRequest, SupportTicket, User, WorkspaceMembership, utcnow,
)

_CLOSED_SUPPORT = ("resolved", "closed")


def _kind(provider: str) -> str:
    """Coarse method label: never the OIDC issuer or the provider subject."""
    return provider if provider in ("password", "google") else "sso"


def build(s: Session, user: User) -> dict:
    now = utcnow()
    identities = s.scalars(select(AccountIdentity).where(AccountIdentity.user_id == user.id).order_by(AccountIdentity.created_at)).all()
    methods = [{"method": _kind(i.provider), "email_verified": bool(i.email_verified), "linked_at": i.created_at.isoformat() if i.created_at else None}
               for i in identities]
    local_sign_in = s.scalar(select(func.count()).select_from(PasswordCredential).where(PasswordCredential.user_id == user.id)) or 0
    seen = s.scalar(select(func.max(AuthSession.last_used_at)).where(AuthSession.user_id == user.id))
    pending_links = s.scalar(select(func.count()).select_from(AuthToken).where(
        AuthToken.user_id == user.id, AuthToken.purpose == TOKEN_PURPOSE_EMAIL_VERIFICATION,
        AuthToken.consumed_at.is_(None), AuthToken.expires_at > now)) or 0
    support_total = s.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.owner_user_id == user.id)) or 0
    support_open = s.scalar(select(func.count()).select_from(SupportTicket).where(
        SupportTicket.owner_user_id == user.id, SupportTicket.status.not_in(_CLOSED_SUPPORT))) or 0
    privacy_total = s.scalar(select(func.count()).select_from(PrivacyRequest).where(PrivacyRequest.user_id == user.id)) or 0
    deletion = s.execute(select(PrivacyRequest.public_id, PrivacyRequest.status).where(
        PrivacyRequest.user_id == user.id, PrivacyRequest.request_type == "deletion", PrivacyRequest.status.in_(OPEN_PRIVACY_STATUSES))
        .order_by(PrivacyRequest.created_at.desc())).first()
    privacy_open = s.scalar(select(func.count()).select_from(PrivacyRequest).where(
        PrivacyRequest.user_id == user.id, PrivacyRequest.status.in_(OPEN_PRIVACY_STATUSES))) or 0
    pending_role = s.scalar(select(func.count()).select_from(AdminRoleChangeRequest).where(
        AdminRoleChangeRequest.target_user_id == user.id, AdminRoleChangeRequest.status == "pending")) or 0
    m_rows = s.execute(select(WorkspaceMembership.role, WorkspaceMembership.status).where(WorkspaceMembership.user_id == user.id)).all()
    return {
        "revision": account_revision(s, user),
        "auth": {"methods": methods, "local_sign_in": bool(local_sign_in), "email_verified": bool(user.email_verified),
                 "pending_verification_links": int(pending_links)},
        "activity": {"last_active": activity_bucket(seen)},
        "cases": {"support_open": int(support_open), "support_total": int(support_total), "privacy_open": int(privacy_open),
                  "privacy_total": int(privacy_total), "pending_role_change": bool(pending_role),
                  "open_deletion_request_id": deletion[0] if deletion else None, "open_deletion_status": deletion[1] if deletion else None},
        "membership": {"active": sum(1 for r, st in m_rows if st == MEMBERSHIP_STATUS_ACTIVE), "total": len(m_rows),
                       "owner_of_active": sum(1 for r, st in m_rows if st == MEMBERSHIP_STATUS_ACTIVE and r == WORKSPACE_ROLE_OWNER)},
    }
