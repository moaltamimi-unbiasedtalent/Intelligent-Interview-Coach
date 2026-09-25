"""Data-access for the identity/platform foundation (Capstone P1/E1).

Sibling repositories to :mod:`src.repository`, sharing the same session factory /
database engine. They own the durable identity tables introduced in migration
0007 (accounts, identities, credentials, sessions, tokens, entitlements, audit).

Design rules preserved from the rest of the data layer:
* Every account-scoped read/write is keyed by the internal integer ``user_id``.
* A foreign/unknown row resolves to ``None`` / a no-op, never another user's data.
* Nothing here logs a password, a raw token, or a token hash.

These repositories return plain dataclasses (never live ORM objects) so callers in
the application layer depend on data, not the session lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    ACCOUNT_STATUS_DELETION_REQUESTED,
    DEFAULT_LOCALE,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLE_USER,
    RESPONSE_DETAIL_BRIEF,
    RESPONSE_DETAIL_VALUES,
    SUPPORTED_LOCALES,
    TIER_BASIC,
    TIER_PREMIUM,
    AccountIdentity,
    AuditEvent,
    AuthSession,
    AuthToken,
    PasswordCredential,
    ProductEntitlement,
    User,
    UserPreference,
    utcnow,
)

__all__ = [
    "AccountRecord",
    "SessionRecord",
    "AccountRepository",
    "SessionRepository",
    "TokenRepository",
    "AuditRepository",
]


@dataclass(frozen=True)
class AccountRecord:
    """A safe projection of a principal + its platform/entitlement state."""

    user_id: int
    email: str | None
    display_name: str | None
    platform_role: str
    status: str
    email_verified: bool
    tier: str
    has_password: bool
    providers: tuple[str, ...]
    response_detail: str = RESPONSE_DETAIL_BRIEF
    interface_locale: str = DEFAULT_LOCALE
    conversation_language: str = DEFAULT_LOCALE


@dataclass(frozen=True)
class SessionRecord:
    user_id: int
    expires_at: datetime
    revoked_at: datetime | None


def _aware(dt: datetime | None) -> datetime | None:
    """Normalise a possibly-naive DB datetime to timezone-aware UTC for comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class AccountRepository:
    """Users, identities, credentials and entitlements (the principal)."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> sessionmaker:
        return self._session_factory

    # -- lookups --------------------------------------------------------------

    def _project(self, session, user: User) -> AccountRecord:
        cred = session.scalar(
            select(PasswordCredential).where(PasswordCredential.user_id == user.id)
        )
        ent = session.scalar(
            select(ProductEntitlement).where(ProductEntitlement.user_id == user.id)
        )
        idents = session.scalars(
            select(AccountIdentity).where(AccountIdentity.user_id == user.id)
        ).all()
        pref = session.scalar(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        return AccountRecord(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            platform_role=user.platform_role,
            status=user.status,
            email_verified=bool(user.email_verified),
            tier=ent.tier if ent else TIER_BASIC,
            has_password=cred is not None,
            providers=tuple(sorted({i.provider for i in idents})),
            response_detail=pref.response_detail if pref else RESPONSE_DETAIL_BRIEF,
            interface_locale=pref.interface_locale if pref else DEFAULT_LOCALE,
            conversation_language=pref.conversation_language if pref else DEFAULT_LOCALE,
        )

    def get_account(self, user_id: int) -> AccountRecord | None:
        with self._session_factory() as session:
            user = session.get(User, user_id)
            return self._project(session, user) if user else None

    def find_by_email(self, email: str) -> AccountRecord | None:
        """Case-insensitive lookup by primary email (for login / reset)."""
        norm = _normalize_email(email)
        with self._session_factory() as session:
            user = session.scalar(
                select(User).where(User.email == norm)
            )
            return self._project(session, user) if user else None

    def get_password_hash(self, user_id: int) -> str | None:
        with self._session_factory() as session:
            cred = session.scalar(
                select(PasswordCredential).where(PasswordCredential.user_id == user_id)
            )
            return cred.password_hash if cred else None

    def find_identity_user(self, provider: str, provider_subject: str) -> int | None:
        with self._session_factory() as session:
            ident = session.scalar(
                select(AccountIdentity).where(
                    AccountIdentity.provider == provider,
                    AccountIdentity.provider_subject == provider_subject,
                )
            )
            return ident.user_id if ident else None

    # -- account creation / mutation -----------------------------------------

    def create_password_account(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None,
    ) -> int | None:
        """Create a principal with a password identity + credential + basic tier.

        Returns the new ``user_id``, or ``None`` if the email is already taken
        (unique violation) — the caller maps that to a safe, non-enumerating result.
        """
        norm = _normalize_email(email)
        with self._session_factory() as session:
            user = User(
                subject=norm,
                provider="password",
                display_name=display_name,
                email=norm,
                platform_role=PLATFORM_ROLE_USER,
                status=ACCOUNT_STATUS_ACTIVE,
                email_verified=False,
            )
            session.add(user)
            try:
                session.flush()  # allocate user.id, surface unique violations early
                session.add(
                    AccountIdentity(
                        user_id=user.id,
                        provider="password",
                        provider_subject=norm,
                        email=norm,
                        email_verified=False,
                    )
                )
                session.add(
                    PasswordCredential(user_id=user.id, password_hash=password_hash)
                )
                session.add(
                    ProductEntitlement(user_id=user.id, tier=TIER_BASIC, source="default")
                )
                session.commit()
                return user.id
            except IntegrityError:
                session.rollback()
                return None

    def link_or_create_oidc(
        self,
        *,
        provider: str,
        provider_subject: str,
        email: str | None,
        email_verified: bool,
        display_name: str | None,
    ) -> int:
        """Resolve a social identity to a principal (account linking by verified email).

        * Existing (provider, subject) → that user.
        * Else a VERIFIED email matching an existing account → link a new identity to it.
        * Else create a fresh principal (+ identity + basic tier).
        """
        norm = _normalize_email(email) if email else None
        with self._session_factory() as session:
            existing = session.scalar(
                select(AccountIdentity).where(
                    AccountIdentity.provider == provider,
                    AccountIdentity.provider_subject == provider_subject,
                )
            )
            if existing is not None:
                return existing.user_id

            user: User | None = None
            # Link only on a provider-verified email — never merge on an unverified one.
            if norm and email_verified:
                user = session.scalar(select(User).where(User.email == norm))

            if user is None:
                user = User(
                    subject=provider_subject,
                    provider=provider,
                    display_name=display_name,
                    email=norm,
                    platform_role=PLATFORM_ROLE_USER,
                    status=ACCOUNT_STATUS_ACTIVE,
                    email_verified=bool(email_verified and norm),
                )
                session.add(user)
                session.flush()
                session.add(
                    ProductEntitlement(user_id=user.id, tier=TIER_BASIC, source="default")
                )
            session.add(
                AccountIdentity(
                    user_id=user.id,
                    provider=provider,
                    provider_subject=provider_subject,
                    email=norm,
                    email_verified=bool(email_verified),
                )
            )
            if email_verified and norm and not user.email_verified:
                user.email_verified = True
            session.commit()
            return user.id

    def set_password(self, user_id: int, password_hash: str) -> bool:
        with self._session_factory() as session:
            cred = session.scalar(
                select(PasswordCredential).where(PasswordCredential.user_id == user_id)
            )
            if cred is None:
                session.add(PasswordCredential(user_id=user_id, password_hash=password_hash))
            else:
                cred.password_hash = password_hash
            session.commit()
            return True

    def mark_email_verified(self, user_id: int) -> bool:
        with self._session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return False
            user.email_verified = True
            for ident in session.scalars(
                select(AccountIdentity).where(AccountIdentity.user_id == user_id)
            ):
                if ident.email and user.email and _normalize_email(ident.email) == _normalize_email(user.email):
                    ident.email_verified = True
            session.commit()
            return True

    def set_platform_role(self, user_id: int, role: str) -> bool:
        with self._session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return False
            user.platform_role = role
            session.commit()
            return True

    def set_tier(self, user_id: int, tier: str, *, source: str | None = None) -> bool:
        with self._session_factory() as session:
            ent = session.scalar(
                select(ProductEntitlement).where(ProductEntitlement.user_id == user_id)
            )
            if ent is None:
                session.add(ProductEntitlement(user_id=user_id, tier=tier, source=source))
            else:
                ent.tier = tier
                if source:
                    ent.source = source
            session.commit()
            return True

    def set_status(self, user_id: int, status: str) -> bool:
        with self._session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return False
            user.status = status
            session.commit()
            return True

    # -- admin operational reads (Capstone P6.5) — METADATA ONLY -------------

    def list_accounts(self, *, limit: int = 100, query: str | None = None) -> list[dict]:
        """Bounded account METADATA for the Platform Admin surface. NEVER candidate-private
        content — only identity/status/role/tier/verification/created metadata."""
        with self._session_factory() as session:
            stmt = select(User).order_by(User.created_at.desc()).limit(max(1, min(int(limit), 500)))
            if query:
                like = f"%{query.strip().lower()}%"
                stmt = select(User).where(func.lower(User.email).like(like)).order_by(
                    User.created_at.desc()).limit(max(1, min(int(limit), 500)))
            users = session.scalars(stmt).all()
            out = []
            for u in users:
                ent = session.scalar(select(ProductEntitlement).where(ProductEntitlement.user_id == u.id))
                out.append({
                    "user_id": u.id, "email": u.email, "display_name": u.display_name,
                    "platform_role": u.platform_role, "status": u.status,
                    "email_verified": bool(u.email_verified),
                    "tier": ent.tier if ent else None,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                })
            return out

    def account_stats(self) -> dict:
        """Aggregate account metadata for the admin home (counts only)."""
        with self._session_factory() as session:
            total = int(session.scalar(select(func.count()).select_from(User)) or 0)
            admins = int(session.scalar(select(func.count()).select_from(User).where(
                User.platform_role == PLATFORM_ROLE_ADMIN)) or 0)
            verified = int(session.scalar(select(func.count()).select_from(User).where(
                User.email_verified.is_(True))) or 0)
            premium = int(session.scalar(select(func.count()).select_from(ProductEntitlement).where(
                ProductEntitlement.tier == TIER_PREMIUM)) or 0)
            deletion_requested = int(session.scalar(select(func.count()).select_from(User).where(
                User.status == ACCOUNT_STATUS_DELETION_REQUESTED)) or 0)
            return {"users_total": total, "platform_admins": admins,
                    "email_verified": verified, "premium_accounts": premium,
                    "deletion_requests_open": deletion_requested}

    def list_privacy_requests(self, *, limit: int = 100) -> list[dict]:
        """Open privacy/deletion requests — METADATA ONLY (never the user's private data)."""
        with self._session_factory() as session:
            users = session.scalars(select(User).where(
                User.status == ACCOUNT_STATUS_DELETION_REQUESTED)
                .order_by(User.updated_at.desc()).limit(max(1, min(int(limit), 500)))).all()
            return [{"user_id": u.id, "email": u.email, "request_type": "account_deletion",
                     "status": u.status,
                     "requested_at": u.updated_at.isoformat() if u.updated_at else None}
                    for u in users]

    # -- preferences (P2/E2) --------------------------------------------------

    def get_response_detail(self, user_id: int) -> str:
        with self._session_factory() as session:
            pref = session.scalar(
                select(UserPreference).where(UserPreference.user_id == user_id)
            )
            return pref.response_detail if pref else RESPONSE_DETAIL_BRIEF

    def set_response_detail(self, user_id: int, value: str) -> bool:
        """Set the user's response-detail preference (validated brief/detailed)."""
        if value not in RESPONSE_DETAIL_VALUES:
            return False
        return self._upsert_preference(user_id, response_detail=value)

    def set_interface_locale(self, user_id: int, value: str) -> bool:
        """Set the UI language (validated against the supported allow-list)."""
        if value not in SUPPORTED_LOCALES:
            return False
        return self._upsert_preference(user_id, interface_locale=value)

    def set_conversation_language(self, user_id: int, value: str) -> bool:
        """Set Mo's conversation language (validated against the supported allow-list)."""
        if value not in SUPPORTED_LOCALES:
            return False
        return self._upsert_preference(user_id, conversation_language=value)

    def _upsert_preference(self, user_id: int, **fields: str) -> bool:
        """Create/update the user's preference row for the given validated fields."""
        with self._session_factory() as session:
            # Only upsert for a real user (never create a preference row for a
            # non-existent principal — keeps the table clean and FK-valid).
            if session.get(User, user_id) is None:
                return False
            pref = session.scalar(
                select(UserPreference).where(UserPreference.user_id == user_id)
            )
            if pref is None:
                session.add(UserPreference(user_id=user_id, **fields))
            else:
                for key, value in fields.items():
                    setattr(pref, key, value)
            session.commit()
            return True


class SessionRepository:
    """Server-side authentication sessions (opaque token hash → user)."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def create(
        self, *, token_hash: str, user_id: int, ttl_seconds: int, user_agent: str | None = None
    ) -> None:
        now = utcnow()
        with self._session_factory() as session:
            session.add(
                AuthSession(
                    token_hash=token_hash,
                    user_id=user_id,
                    created_at=now,
                    expires_at=now + timedelta(seconds=ttl_seconds),
                    last_used_at=now,
                    user_agent=(user_agent or None),
                )
            )
            session.commit()

    def resolve(self, token_hash: str) -> int | None:
        """Return the owning user_id for a live session, else None.

        A session is live when it exists, is not revoked and has not expired.
        Updates ``last_used_at`` opportunistically.
        """
        now = utcnow()
        with self._session_factory() as session:
            row = session.get(AuthSession, token_hash)
            if row is None:
                return None
            if row.revoked_at is not None:
                return None
            if _aware(row.expires_at) <= now:
                return None
            row.last_used_at = now
            session.commit()
            return row.user_id

    def revoke(self, token_hash: str) -> bool:
        with self._session_factory() as session:
            row = session.get(AuthSession, token_hash)
            if row is None or row.revoked_at is not None:
                return False
            row.revoked_at = utcnow()
            session.commit()
            return True

    def revoke_all_for_user(self, user_id: int) -> int:
        now = utcnow()
        with self._session_factory() as session:
            rows = session.scalars(
                select(AuthSession).where(
                    AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
                )
            ).all()
            for row in rows:
                row.revoked_at = now
            session.commit()
            return len(rows)

    def list_active(self, user_id: int) -> list[SessionRecord]:
        now = utcnow()
        with self._session_factory() as session:
            rows = session.scalars(
                select(AuthSession).where(AuthSession.user_id == user_id)
            ).all()
            return [
                SessionRecord(user_id=r.user_id, expires_at=r.expires_at, revoked_at=r.revoked_at)
                for r in rows
                if r.revoked_at is None and _aware(r.expires_at) > now
            ]


class TokenRepository:
    """Single-use, expiring email-verification / password-reset tokens (hash only)."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def issue(
        self, *, token_hash: str, user_id: int, purpose: str, ttl_seconds: int
    ) -> None:
        now = utcnow()
        with self._session_factory() as session:
            session.add(
                AuthToken(
                    token_hash=token_hash,
                    user_id=user_id,
                    purpose=purpose,
                    created_at=now,
                    expires_at=now + timedelta(seconds=ttl_seconds),
                )
            )
            session.commit()

    def consume(self, *, token_hash: str, purpose: str) -> int | None:
        """Atomically consume a valid token, returning its user_id (else None).

        Returns None for unknown, wrong-purpose, expired, or already-consumed tokens
        (token replay is therefore impossible).
        """
        now = utcnow()
        with self._session_factory() as session:
            row = session.get(AuthToken, token_hash)
            if row is None or row.purpose != purpose:
                return None
            if row.consumed_at is not None:
                return None
            if _aware(row.expires_at) <= now:
                return None
            row.consumed_at = now
            session.commit()
            return row.user_id

    def invalidate_for_user(self, *, user_id: int, purpose: str) -> int:
        """Consume all outstanding tokens of a purpose (e.g. after a completed reset)."""
        now = utcnow()
        with self._session_factory() as session:
            rows = session.scalars(
                select(AuthToken).where(
                    AuthToken.user_id == user_id,
                    AuthToken.purpose == purpose,
                    AuthToken.consumed_at.is_(None),
                )
            ).all()
            for row in rows:
                row.consumed_at = now
            session.commit()
            return len(rows)


class AuditRepository:
    """Bounded security/privacy audit log (append-only in practice)."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        event_type: str,
        result: str = "success",
        actor_user_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        request_id: str | None = None,
        context: dict | None = None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                AuditEvent(
                    actor_user_id=actor_user_id,
                    event_type=event_type,
                    target_type=target_type,
                    target_id=target_id,
                    result=result,
                    request_id=request_id,
                    context=(context or None),
                )
            )
            session.commit()

    def recent_for_actor(self, actor_user_id: int, *, limit: int = 50) -> list[dict]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(AuditEvent)
                .where(AuditEvent.actor_user_id == actor_user_id)
                .order_by(AuditEvent.created_at.desc())
                .limit(limit)
            ).all()
            return [
                {
                    "event_type": r.event_type,
                    "result": r.result,
                    "target_type": r.target_type,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def recent(self, *, limit: int = 100, event_type: str | None = None) -> list[dict]:
        """Cross-actor recent audit events for the Platform Admin audit view (Capstone
        P6.5). Returns ONLY safe allow-listed metadata — never the secret-free ``context``
        blob's arbitrary contents beyond a bounded projection, never passwords/tokens/PII."""
        with self._session_factory() as session:
            stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(
                max(1, min(int(limit), 500)))
            if event_type:
                stmt = select(AuditEvent).where(AuditEvent.event_type == event_type).order_by(
                    AuditEvent.created_at.desc()).limit(max(1, min(int(limit), 500)))
            rows = session.scalars(stmt).all()
            return [
                {
                    "event_type": r.event_type, "result": r.result,
                    "actor_user_id": r.actor_user_id, "target_type": r.target_type,
                    "target_id": r.target_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]


def _normalize_email(email: str) -> str:
    return email.strip().lower()
