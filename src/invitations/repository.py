"""Invitation rows: hashed at rest, single use, atomically consumed (04E).

Everything that touches a code goes through :func:`hash_code`; the plaintext is generated in :func:`new_code`, returned to the caller ONCE and never stored, logged or
put in an audit context. Two kinds of caller use this module:

* registration (``AccountRepository``) calls :func:`peek` (cheap, non-consuming, before any bcrypt work) and :func:`consume` (ONE conditional UPDATE inside the
  account-creation transaction, so a failed registration never burns a code and two racing registrations cannot both win);
* the Admin service calls :class:`InvitationRepository` to issue, list and revoke (state change and audit row in one transaction).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.authsec import tokens
from src.invitations import policy
from src.persistence import AuditEvent, RegistrationInvitation, utcnow

# Bounded refusal reasons. They go to the AUDIT trail only; the requester always sees one uniform refusal.
REASON_MISSING = "missing"
REASON_INVALID = "invalid"          # unknown code (or malformed)
REASON_EXPIRED = "expired"
REASON_REVOKED = "revoked"
REASON_USED = "used"
REASON_EMAIL_MISMATCH = "email_mismatch"
REASON_RATE_LIMITED = "rate_limited"
REFUSAL_REASONS = (REASON_MISSING, REASON_INVALID, REASON_EXPIRED, REASON_REVOKED, REASON_USED, REASON_EMAIL_MISMATCH, REASON_RATE_LIMITED)

STATE_PENDING, STATE_REDEEMED, STATE_EXPIRED, STATE_REVOKED = "pending", "redeemed", "expired", "revoked"

_EMAIL_HASH_PREFIX = "ask4mo.invitation.email.v1:"


class InvitationRefused(Exception):
    """Registration needs an invitation and the presented one cannot be used. ``reason`` is audit-only; callers must show ONE uniform message."""

    def __init__(self, reason: str) -> None:
        super().__init__("invitation_required")
        self.reason = reason


class InvitationNotFound(LookupError):
    """No such invitation id (mapped to 404)."""


class InvitationConflict(Exception):
    """The requested change is impossible in the invitation's current state (mapped to 409)."""


class InvitationLimit(Exception):
    """Too many outstanding invitations (mapped to 409)."""


# -- code and email primitives -----------------------------------------------------------------------------------------------------------------------------

def new_code() -> str:
    """A fresh 256-bit URL-safe code (the plaintext; shown once)."""
    return secrets.token_urlsafe(policy.CODE_BYTES)


def hash_code(code: str) -> str:
    """SHA-256 hex of the code: the ONLY form that is persisted. 256-bit random input makes a salt or slow hash unnecessary (same rule as session and link tokens)."""
    return tokens.hash_token((code or "").strip())


def _normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_email(email: str) -> str:
    """Domain-separated SHA-256 of the normalised address (the optional binding). Not reversible from the row alone for an address nobody guesses; it is cleared when the
    invitation is redeemed by an account that is later deleted, and it is never returned by any API."""
    return hashlib.sha256((_EMAIL_HASH_PREFIX + _normalise_email(email)).encode("utf-8")).hexdigest()


def mask_email(email: str) -> str:
    """A display-only masked form (``j***@e***.com``) so an operator can recognise which invitation is which without seeing the address."""
    value = _normalise_email(email)
    local, _, domain = value.partition("@")
    if not local or not domain:
        return "***"
    host, dot, tld = domain.rpartition(".")
    host = host or domain
    masked_domain = f"{host[:1]}***{dot}{tld}" if dot else f"{host[:1]}***"
    return f"{local[:1]}***@{masked_domain}"[:64]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


def derive_state(row: RegistrationInvitation, now: datetime | None = None) -> str:
    now = now or utcnow()
    if row.revoked_at is not None:
        return STATE_REVOKED
    if row.redeemed_at is not None:
        return STATE_REDEEMED
    if _aware(row.expires_at) <= now:
        return STATE_EXPIRED
    return STATE_PENDING


# -- registration-side primitives (take the caller's session so they join ITS transaction) -------------------------------------------------------------------

def _refusal_reason(session: Session, code_hash: str, email_hash: str | None, now: datetime) -> str:
    row = session.scalar(select(RegistrationInvitation).where(RegistrationInvitation.code_hash == code_hash))
    if row is None:
        return REASON_INVALID
    state = derive_state(row, now)
    if state == STATE_REVOKED:
        return REASON_REVOKED
    if state == STATE_REDEEMED:
        return REASON_USED
    if state == STATE_EXPIRED:
        return REASON_EXPIRED
    if row.email_hash is not None and (email_hash is None or row.email_hash != email_hash):
        return REASON_EMAIL_MISMATCH
    return REASON_INVALID


def peek(session_factory: sessionmaker, *, code: str | None, email: str | None) -> str | None:
    """Non-consuming check. Returns ``None`` when the code is usable right now for ``email``, else the audit-only refusal reason."""
    if not (code or "").strip():
        return REASON_MISSING
    now = utcnow()
    with session_factory() as session:
        code_hash = hash_code(code)
        email_hash = hash_email(email) if email else None
        row = session.scalar(select(RegistrationInvitation).where(RegistrationInvitation.code_hash == code_hash))
        if row is None:
            return REASON_INVALID
        if derive_state(row, now) != STATE_PENDING:
            return _refusal_reason(session, code_hash, email_hash, now)
        if row.email_hash is not None and (email_hash is None or row.email_hash != email_hash):
            return REASON_EMAIL_MISMATCH
        return None


def consume(session: Session, *, code: str, email: str | None, user_id: int) -> None:
    """Redeem ``code`` for ``user_id`` with ONE conditional UPDATE inside the caller's transaction.

    The UPDATE succeeds only while the row is unredeemed, unrevoked, unexpired and (when bound) matches ``email``; two concurrent callers cannot both get
    ``rowcount == 1`` (SQLite serialises writers, PostgreSQL re-evaluates the WHERE after the first commit). On failure it raises :class:`InvitationRefused` and the
    caller MUST roll back (so the account it just staged disappears with it).
    """
    now = utcnow()
    code_hash = hash_code(code)
    email_hash = hash_email(email) if email else None
    res = session.execute(
        update(RegistrationInvitation)
        .where(
            RegistrationInvitation.code_hash == code_hash,
            RegistrationInvitation.redeemed_at.is_(None),
            RegistrationInvitation.revoked_at.is_(None),
            RegistrationInvitation.expires_at > now,
            (RegistrationInvitation.email_hash.is_(None)) | (RegistrationInvitation.email_hash == (email_hash or "")),
        )
        .values(redeemed_at=now, redeemed_by_user_id=user_id)
    )
    if res.rowcount != 1:
        raise InvitationRefused(_refusal_reason(session, code_hash, email_hash, now))


def anonymise_for_deleted_user(session: Session, user_id: int) -> int:
    """Account deletion: clear the redeemer linkage (and the email binding of the consumed row) and the issuer/revoker linkage of rows this user touched.

    The rows stay (consumed, anonymous) so a redeemed code can never be replayed, and a pending invitation issued by a deleted administrator stays usable until it
    expires or is revoked. Returns the number of rows changed.
    """
    n = 0
    redeemed = session.execute(
        update(RegistrationInvitation).where(RegistrationInvitation.redeemed_by_user_id == user_id)
        .values(redeemed_by_user_id=None, email_hash=None, email_hint=None))
    n += redeemed.rowcount or 0
    issued = session.execute(update(RegistrationInvitation).where(RegistrationInvitation.issued_by_user_id == user_id).values(issued_by_user_id=None))
    n += issued.rowcount or 0
    revoked = session.execute(update(RegistrationInvitation).where(RegistrationInvitation.revoked_by_user_id == user_id).values(revoked_by_user_id=None))
    n += revoked.rowcount or 0
    return n


# -- Admin-side repository -----------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class InvitationView:
    """What Admin may see: state and masked identifiers only. No code, hash, full address, or the redeeming account."""

    id: int
    state: str
    created_at: datetime
    expires_at: datetime
    redeemed_at: datetime | None
    revoked_at: datetime | None
    email_bound: bool
    email_hint: str | None
    issued_by_user_id: int | None


def _view(row: RegistrationInvitation, now: datetime) -> InvitationView:
    return InvitationView(
        id=row.id, state=derive_state(row, now), created_at=_aware(row.created_at), expires_at=_aware(row.expires_at),
        redeemed_at=_aware(row.redeemed_at), revoked_at=_aware(row.revoked_at), email_bound=row.email_hash is not None,
        email_hint=row.email_hint, issued_by_user_id=row.issued_by_user_id)


def _stage_audit(session: Session, audit: dict | None, **extra) -> None:
    if not audit:
        return
    context = {**(audit.get("context") or {}), **extra} or None
    session.add(AuditEvent(actor_user_id=audit.get("actor_user_id"), event_type=audit["event_type"], target_type=audit.get("target_type"),
                           target_id=audit.get("target_id"), result=audit.get("result", "success"), request_id=audit.get("request_id"), context=context))


class InvitationRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def issue(self, *, code_hash: str, ttl_days: int, email: str | None, issued_by_user_id: int | None, audit: dict | None = None) -> InvitationView:
        """Persist one invitation (hash only) and its audit row in ONE transaction. The caller already holds the plaintext; this method never sees it."""
        now = utcnow()
        with self._sf() as session:
            pending = session.scalar(select(func.count()).select_from(RegistrationInvitation).where(
                RegistrationInvitation.redeemed_at.is_(None), RegistrationInvitation.revoked_at.is_(None), RegistrationInvitation.expires_at > now)) or 0
            if pending >= policy.MAX_OUTSTANDING_PENDING:
                raise InvitationLimit("Too many pending invitations. Revoke unused ones first.")
            row = RegistrationInvitation(
                code_hash=code_hash, email_hash=hash_email(email) if email else None, email_hint=mask_email(email) if email else None,
                issued_by_user_id=issued_by_user_id, created_at=now, expires_at=now + timedelta(days=ttl_days))
            session.add(row)
            session.flush()
            _stage_audit(session, audit, invitation_id=row.id, ttl_days=ttl_days, email_bound=bool(email))
            session.commit()
            session.refresh(row)
            return _view(row, now)

    def list(self, *, state: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[InvitationView], int]:
        now = utcnow()
        limit = max(1, min(int(limit), 100))
        with self._sf() as session:
            stmt = select(RegistrationInvitation)
            if state == STATE_REVOKED:
                stmt = stmt.where(RegistrationInvitation.revoked_at.is_not(None))
            elif state == STATE_REDEEMED:
                stmt = stmt.where(RegistrationInvitation.revoked_at.is_(None), RegistrationInvitation.redeemed_at.is_not(None))
            elif state == STATE_EXPIRED:
                stmt = stmt.where(RegistrationInvitation.revoked_at.is_(None), RegistrationInvitation.redeemed_at.is_(None), RegistrationInvitation.expires_at <= now)
            elif state == STATE_PENDING:
                stmt = stmt.where(RegistrationInvitation.revoked_at.is_(None), RegistrationInvitation.redeemed_at.is_(None), RegistrationInvitation.expires_at > now)
            total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = session.scalars(stmt.order_by(RegistrationInvitation.id.desc()).limit(limit).offset(max(0, int(offset)))).all()
            return [_view(r, now) for r in rows], int(total)

    def revoke(self, invitation_id: int, *, actor_user_id: int | None, audit: dict | None = None) -> InvitationView:
        """Revoke a PENDING (or already expired/revoked) invitation. A redeemed one cannot be revoked (the account exists); an already revoked one is returned unchanged."""
        now = utcnow()
        with self._sf() as session:
            row = session.get(RegistrationInvitation, invitation_id)
            if row is None:
                raise InvitationNotFound("Invitation not found.")
            if row.revoked_at is not None:
                session.rollback()
                return _view(row, now)
            res = session.execute(update(RegistrationInvitation).where(
                RegistrationInvitation.id == invitation_id, RegistrationInvitation.redeemed_at.is_(None), RegistrationInvitation.revoked_at.is_(None))
                .values(revoked_at=now, revoked_by_user_id=actor_user_id))
            if res.rowcount != 1:
                session.rollback()
                raise InvitationConflict("This invitation was already redeemed and cannot be revoked.")
            _stage_audit(session, audit, invitation_id=invitation_id)
            session.commit()
            session.refresh(row)
            return _view(row, now)

    def counts(self) -> dict[str, int]:
        now = utcnow()
        with self._sf() as session:
            out = {s: 0 for s in (STATE_PENDING, STATE_REDEEMED, STATE_EXPIRED, STATE_REVOKED)}
            for row in session.scalars(select(RegistrationInvitation)).all():
                out[derive_state(row, now)] += 1
            return out


def redeemed_at_for_user(session: Session, user_id: int) -> datetime | None:
    """For the owner's own privacy export: when THEIR registration invitation was redeemed (nothing else about it)."""
    return _aware(session.scalar(select(RegistrationInvitation.redeemed_at).where(RegistrationInvitation.redeemed_by_user_id == user_id)))


__all__ = [
    "InvitationRefused", "InvitationNotFound", "InvitationConflict", "InvitationLimit", "InvitationRepository", "InvitationView",
    "new_code", "hash_code", "hash_email", "mask_email", "derive_state", "peek", "consume", "anonymise_for_deleted_user", "redeemed_at_for_user",
    "REFUSAL_REASONS",
]
