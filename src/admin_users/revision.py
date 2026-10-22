"""Account revision token (03C): an opaque fingerprint of the account state an Admin decision is based on.

There is no ``revision`` column (no migration): the token is derived from the facts every Admin action on an account can change, so a stale screen cannot
overwrite a newer decision. It contains no secret and no email; it is a 16-hex digest and is only ever compared for equality.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.persistence import (
    SUBSCRIPTION_STATUS_ACTIVE, TOKEN_PURPOSE_EMAIL_VERIFICATION, AuthSession, AuthToken, PrivacyRequest, Subscription, User, utcnow,
)

OPEN_PRIVACY = ("submitted", "acknowledged", "in_progress", "waiting_for_user")


def account_revision(s: Session, user: User) -> str:
    now = utcnow()
    sub = s.scalar(select(Subscription.id).where(Subscription.user_id == user.id, Subscription.status == SUBSCRIPTION_STATUS_ACTIVE)) or 0
    live = s.scalar(select(func.count()).select_from(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)) or 0
    tokens = s.scalar(select(func.count()).select_from(AuthToken).where(
        AuthToken.user_id == user.id, AuthToken.purpose == TOKEN_PURPOSE_EMAIL_VERIFICATION,
        AuthToken.consumed_at.is_(None), AuthToken.expires_at > now)) or 0
    privacy = s.scalar(select(func.count()).select_from(PrivacyRequest).where(
        PrivacyRequest.user_id == user.id, PrivacyRequest.status.in_(OPEN_PRIVACY))) or 0
    raw = "|".join(str(x) for x in (user.id, user.status, user.platform_role, int(bool(user.email_verified)), user.updated_at, sub, live, tokens, privacy))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
