"""Data access for two-step workspace ownership transfers (04B completion, REQ-OWN-07).

Design rules (all enforced here, not in the UI):

* ONE open (``pending``) transfer per workspace, enforced by a partial unique index; a proposal that loses that race is reported as ``open_transfer_exists``.
* Every state change (proposed, accepted, declined, cancelled, expired) is ONE transaction that writes the new state, any role change AND the append-only
  audit row together. If the audit row cannot be written the state change rolls back: the evidence is never optional for an ownership decision.
* Every "claim" is a conditional ``UPDATE ... WHERE status = 'pending'``; of N concurrent accept / decline / cancel / expire attempts exactly one sees
  ``rowcount == 1`` and the others observe ``used``. Acceptance claims and swaps the roles in the SAME transaction, so there is never an accepted transfer
  without the swap, nor a swap without an accepted transfer, and exactly one active owner exists before and after.
* The acceptance token and the recipient address are stored ONLY as SHA-256 hashes. Audit rows hold metadata only: ids, roles, outcome and a fixed reason code.
  Never a name, an address, a token or a workspace title (asserted by a context key allow-list below and by the tests).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.persistence import (
    MEMBERSHIP_STATUS_ACTIVE,
    TRANSFER_STATUS_ACCEPTED,
    TRANSFER_STATUS_CANCELLED,
    TRANSFER_STATUS_DECLINED,
    TRANSFER_STATUS_EXPIRED,
    TRANSFER_STATUS_PENDING,
    WORKSPACE_ROLE_ADMIN,
    WORKSPACE_ROLE_MEMBER,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    AuditEvent,
    Workspace,
    WorkspaceMembership,
    WorkspaceOwnershipTransfer as T,
    utcnow,
)

__all__ = ["OwnershipTransferRepository", "cancel_open_in_session", "transfer_email_hash", "hash_token",
           "AUDIT_PROPOSED", "AUDIT_ACCEPTED", "AUDIT_DECLINED", "AUDIT_CANCELLED", "AUDIT_EXPIRED", "AUDIT_EVENTS",
           "FORMER_OWNER_ROLES", "CANCEL_REASONS"]

AUDIT_PROPOSED = "workspace.transfer_proposed"
AUDIT_ACCEPTED = "workspace.transfer_accepted"
AUDIT_DECLINED = "workspace.transfer_declined"
AUDIT_CANCELLED = "workspace.transfer_cancelled"
AUDIT_EXPIRED = "workspace.transfer_expired"
AUDIT_EVENTS = (AUDIT_PROPOSED, AUDIT_ACCEPTED, AUDIT_DECLINED, AUDIT_CANCELLED, AUDIT_EXPIRED)

FORMER_OWNER_ROLES = (WORKSPACE_ROLE_ADMIN, WORKSPACE_ROLE_MEMBER)

# Fixed vocabulary (the audit ``reason`` is never free text).
CANCEL_REASONS = ("proposer_cancelled", "membership_ended", "account_deactivated", "account_deleted", "workspace_deleted", "invalid_state")

# The ONLY keys an ownership-transfer audit row may carry.
_ALLOWED_CONTEXT = frozenset({"transfer_id", "actor_role", "former_owner_role", "outcome", "reason"})


def hash_token(raw: str) -> str:
    return hashlib.sha256((raw or "").strip().encode("utf-8")).hexdigest()


def transfer_email_hash(email: str | None) -> str:
    """SHA-256 of the lower-cased address: binds a transfer to the verified address without keeping a second copy of it."""
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _stage_audit(s: Session, event_type: str, *, actor_user_id: int | None, workspace_id: int, **context) -> None:
    """Add the audit row to THIS transaction. Unknown context keys are a programming error (fail loud, never silently widen the record)."""
    ctx = {k: v for k, v in context.items() if v is not None}
    unknown = set(ctx) - _ALLOWED_CONTEXT
    if unknown:
        raise ValueError(f"Ownership-transfer audit context key not allowed: {sorted(unknown)}")
    s.add(AuditEvent(actor_user_id=actor_user_id, event_type=event_type, target_type="workspace",
                     target_id=str(workspace_id), result="success", context=ctx or None))


def _claim(s: Session, transfer_id: int, status: str, reason: str | None = None) -> bool:
    """The ONE conditional UPDATE that moves a pending transfer to a terminal state (True only for the single winner)."""
    now = utcnow()
    n = s.execute(update(T).where(T.id == transfer_id, T.status == TRANSFER_STATUS_PENDING)
                  .values(status=status, decided_at=now, decided_reason=reason, updated_at=now)).rowcount
    return n == 1


def _expire_rows(s: Session, rows) -> list[int]:
    """Expire every given PENDING row that is past its deadline (one audit row each, written only by the claim winner)."""
    done: list[int] = []
    now = utcnow()
    for row in rows:
        exp = _aware(row.expires_at)
        if row.status == TRANSFER_STATUS_PENDING and exp is not None and exp < now and _claim(s, row.id, TRANSFER_STATUS_EXPIRED, "expired"):
            _stage_audit(s, AUDIT_EXPIRED, actor_user_id=None, workspace_id=row.workspace_id, transfer_id=row.id,
                         actor_role="system", outcome="expired", former_owner_role=row.former_owner_role)
            done.append(row.id)
    return done


def cancel_open_in_session(s: Session, *, reason: str, workspace_id: int | None = None, user_id: int | None = None,
                           actor_user_id: int | None = None) -> list[int]:
    """Cancel every open transfer of a workspace and/or involving a user, INSIDE the caller's transaction (so a membership change, an account
    deactivation or a deletion and the cancellation are one unit). Returns the ids actually cancelled (each with its own audit row)."""
    if reason not in CANCEL_REASONS:
        raise ValueError("unknown cancel reason")
    cond = [T.status == TRANSFER_STATUS_PENDING]
    if workspace_id is not None:
        cond.append(T.workspace_id == workspace_id)
    if user_id is not None:
        cond.append(or_(T.proposer_user_id == user_id, T.recipient_user_id == user_id))
    if workspace_id is None and user_id is None:
        raise ValueError("a scope is required")
    cancelled: list[int] = []
    for row in s.scalars(select(T).where(*cond)).all():
        if _claim(s, row.id, TRANSFER_STATUS_CANCELLED, reason):
            _stage_audit(s, AUDIT_CANCELLED, actor_user_id=actor_user_id, workspace_id=row.workspace_id, transfer_id=row.id,
                         actor_role="system" if actor_user_id is None else "owner", reason=reason, outcome="cancelled",
                         former_owner_role=row.former_owner_role)
            cancelled.append(row.id)
    return cancelled


def _view(row: T) -> dict:
    """Plain, safe projection (no token hash, no address hash)."""
    return {"id": row.id, "workspace_id": row.workspace_id, "proposer_user_id": row.proposer_user_id,
            "recipient_user_id": row.recipient_user_id, "former_owner_role": row.former_owner_role, "status": row.status,
            "expires_at": _aware(row.expires_at).isoformat() if row.expires_at else None,
            "created_at": _aware(row.created_at).isoformat() if row.created_at else None,
            "decided_at": _aware(row.decided_at).isoformat() if row.decided_at else None}


def _active_membership(s: Session, workspace_id: int, user_id: int) -> WorkspaceMembership | None:
    return s.scalar(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))


def _active_owner_count(s: Session, workspace_id: int) -> int:
    return int(s.scalar(select(func.count()).select_from(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.role == WORKSPACE_ROLE_OWNER,
        WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)) or 0)


class OwnershipTransferRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- reads ------------------------------------------------------------------------------------------------------

    def expire_due(self, *, workspace_id: int | None = None, user_id: int | None = None) -> list[int]:
        """Server-side expiry: mark overdue pending transfers (of a workspace and/or a user) expired, each with its audit row, in one transaction."""
        with self._sf() as s:
            # ``_expire_rows`` compares timezone-aware values (SQLite returns naive ones), so the SQL side only scopes by workspace / user.
            rows = s.scalars(select(T).where(T.status == TRANSFER_STATUS_PENDING,
                                             *([T.workspace_id == workspace_id] if workspace_id is not None else []),
                                             *([or_(T.proposer_user_id == user_id, T.recipient_user_id == user_id)] if user_id is not None else []))).all()
            done = _expire_rows(s, rows)
            s.commit()
            return done

    def get(self, transfer_id: int) -> dict | None:
        with self._sf() as s:
            row = s.get(T, transfer_id)
            return _view(row) if row else None

    def get_by_token_hash(self, token_hash: str) -> dict | None:
        with self._sf() as s:
            row = s.scalar(select(T).where(T.token_hash == token_hash))
            return _view(row) if row else None

    def email_bound(self, transfer_id: int, email_hash: str) -> bool:
        """Whether this transfer is bound to that address hash (the hash itself never leaves the repository)."""
        with self._sf() as s:
            return s.scalar(select(T.recipient_email_hash).where(T.id == transfer_id)) == email_hash

    def pending_for_workspace(self, workspace_id: int) -> dict | None:
        with self._sf() as s:
            row = s.scalar(select(T).where(T.workspace_id == workspace_id, T.status == TRANSFER_STATUS_PENDING))
            return _view(row) if row else None

    def pending_for_user(self, user_id: int) -> list[dict]:
        """Open transfers where the user is the proposer or the recipient (newest first, bounded)."""
        with self._sf() as s:
            rows = s.scalars(select(T).where(
                T.status == TRANSFER_STATUS_PENDING, or_(T.proposer_user_id == user_id, T.recipient_user_id == user_id))
                .order_by(T.created_at.desc(), T.id.desc()).limit(50)).all()
            return [_view(r) for r in rows]

    def pending_workspace_ids(self, workspace_ids: list[int]) -> set[int]:
        """Metadata only (Platform Admin): which of these workspaces have an open transfer."""
        if not workspace_ids:
            return set()
        with self._sf() as s:
            return {int(i) for i in s.scalars(select(T.workspace_id).where(
                T.status == TRANSFER_STATUS_PENDING, T.workspace_id.in_(workspace_ids))).all()}

    # -- proposal ---------------------------------------------------------------------------------------------------

    def propose(self, *, workspace_id: int, proposer_user_id: int, recipient_user_id: int, recipient_email_hash: str,
                former_owner_role: str, token_hash: str, expires_at: datetime) -> tuple[str, dict | None]:
        """Create the pending transfer and its audit row in ONE transaction. Outcomes: ok, not_found, not_owner, workspace_inactive,
        multiple_owners, recipient_not_member, open_transfer_exists. A stale (expired) pending row of this workspace is expired first (audited)."""
        if former_owner_role not in FORMER_OWNER_ROLES:
            return "invalid_role", None
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id, with_for_update=True)
            if ws is None:
                return "not_found", None
            owner_m = _active_membership(s, workspace_id, proposer_user_id)
            if owner_m is None or owner_m.role != WORKSPACE_ROLE_OWNER or ws.owner_user_id != proposer_user_id:
                return "not_owner", None
            if ws.status != WORKSPACE_STATUS_ACTIVE:
                return "workspace_inactive", None
            if _active_owner_count(s, workspace_id) != 1:
                return "multiple_owners", None
            recipient_m = _active_membership(s, workspace_id, recipient_user_id)
            if recipient_m is None or recipient_m.role == WORKSPACE_ROLE_OWNER or recipient_user_id == proposer_user_id:
                return "recipient_not_member", None
            _expire_rows(s, s.scalars(select(T).where(T.workspace_id == workspace_id, T.status == TRANSFER_STATUS_PENDING)).all())
            if s.scalar(select(T.id).where(T.workspace_id == workspace_id, T.status == TRANSFER_STATUS_PENDING)) is not None:
                s.rollback()
                return "open_transfer_exists", None
            row = T(workspace_id=workspace_id, proposer_user_id=proposer_user_id, recipient_user_id=recipient_user_id,
                    former_owner_role=former_owner_role, token_hash=token_hash, recipient_email_hash=recipient_email_hash,
                    status=TRANSFER_STATUS_PENDING, expires_at=expires_at)
            s.add(row)
            try:
                s.flush()
            except IntegrityError:                                    # the partial unique index: a concurrent proposal won
                s.rollback()
                return "open_transfer_exists", None
            _stage_audit(s, AUDIT_PROPOSED, actor_user_id=proposer_user_id, workspace_id=workspace_id, transfer_id=row.id,
                         actor_role="owner", former_owner_role=former_owner_role, outcome="pending")
            s.commit()
            return "ok", _view(row)

    # -- acceptance -------------------------------------------------------------------------------------------------

    def accept(self, *, token_hash: str, user_id: int, email_hash: str) -> tuple[str, dict | None]:
        """Accept ATOMICALLY and race safely: claim (conditional UPDATE), role swap and audit row are one transaction.

        Outcomes: ok, not_found (unknown token, or the token is bound to someone else), wrong_email (the verified address no longer matches the
        one the transfer was bound to), used, expired, workspace_inactive, invalid (the parties are no longer owner / active member; the transfer
        is cancelled and audited)."""
        with self._sf() as s:
            row = s.scalar(select(T).where(T.token_hash == token_hash))
            if row is None or row.recipient_user_id != user_id:
                return "not_found", None
            if row.status != TRANSFER_STATUS_PENDING:
                return "used", None
            exp = _aware(row.expires_at)
            if exp is not None and exp < utcnow():
                _expire_rows(s, [row])
                s.commit()
                return "expired", None
            if row.recipient_email_hash != email_hash:
                return "wrong_email", None
            ws = s.get(Workspace, row.workspace_id, with_for_update=True)
            if ws is None:
                return "not_found", None
            if ws.status != WORKSPACE_STATUS_ACTIVE:
                return "workspace_inactive", None
            transfer_id, workspace_id, former_role = row.id, row.workspace_id, row.former_owner_role
            old_m = _active_membership(s, workspace_id, row.proposer_user_id)
            new_m = _active_membership(s, workspace_id, user_id)
            if (old_m is None or old_m.role != WORKSPACE_ROLE_OWNER or ws.owner_user_id != row.proposer_user_id
                    or new_m is None or new_m.role == WORKSPACE_ROLE_OWNER or _active_owner_count(s, workspace_id) != 1):
                if _claim(s, transfer_id, TRANSFER_STATUS_CANCELLED, "invalid_state"):
                    _stage_audit(s, AUDIT_CANCELLED, actor_user_id=None, workspace_id=workspace_id, transfer_id=transfer_id,
                                 actor_role="system", reason="invalid_state", outcome="cancelled", former_owner_role=former_role)
                    s.commit()
                    return "invalid", None
                s.rollback()
                return "used", None
            if not _claim(s, transfer_id, TRANSFER_STATUS_ACCEPTED, "accepted"):
                s.rollback()
                return "used", None
            now = utcnow()
            new_m.role, new_m.updated_at = WORKSPACE_ROLE_OWNER, now
            old_m.role, old_m.updated_at = former_role, now
            ws.owner_user_id, ws.updated_at = user_id, now
            s.flush()
            if _active_owner_count(s, workspace_id) != 1:             # defence in depth: never commit anything but exactly one owner
                s.rollback()
                return "invalid", None
            _stage_audit(s, AUDIT_ACCEPTED, actor_user_id=user_id, workspace_id=workspace_id, transfer_id=transfer_id,
                         actor_role="recipient", former_owner_role=former_role, outcome="accepted")
            s.commit()
            return "ok", {"workspace_id": workspace_id, "id": transfer_id, "former_owner_role": former_role}

    # -- decline / cancel -------------------------------------------------------------------------------------------

    def decline(self, *, transfer_id: int, user_id: int) -> tuple[str, dict | None]:
        """The recipient declines. Outcomes: ok, not_found (unknown, or not the recipient), used, expired."""
        with self._sf() as s:
            row = s.get(T, transfer_id)
            if row is None or row.recipient_user_id != user_id:
                return "not_found", None
            if row.status != TRANSFER_STATUS_PENDING:
                return "used", None
            if _expire_rows(s, [row]):
                s.commit()
                return "expired", None
            workspace_id, former_role = row.workspace_id, row.former_owner_role
            if not _claim(s, transfer_id, TRANSFER_STATUS_DECLINED, "declined"):
                s.rollback()
                return "used", None
            _stage_audit(s, AUDIT_DECLINED, actor_user_id=user_id, workspace_id=workspace_id, transfer_id=transfer_id,
                         actor_role="recipient", former_owner_role=former_role, outcome="declined")
            s.commit()
            return "ok", {"workspace_id": workspace_id, "id": transfer_id}

    def cancel(self, *, workspace_id: int, user_id: int) -> tuple[str, dict | None]:
        """The proposer cancels the workspace's open transfer. Outcomes: ok, not_found (nothing open, or the caller is not the proposer), expired."""
        with self._sf() as s:
            row = s.scalar(select(T).where(T.workspace_id == workspace_id, T.status == TRANSFER_STATUS_PENDING))
            if row is None or row.proposer_user_id != user_id:
                return "not_found", None
            if _expire_rows(s, [row]):
                s.commit()
                return "expired", None
            transfer_id, former_role = row.id, row.former_owner_role
            if not _claim(s, transfer_id, TRANSFER_STATUS_CANCELLED, "proposer_cancelled"):
                s.rollback()
                return "used", None
            _stage_audit(s, AUDIT_CANCELLED, actor_user_id=user_id, workspace_id=workspace_id, transfer_id=transfer_id,
                         actor_role="owner", reason="proposer_cancelled", outcome="cancelled", former_owner_role=former_role)
            s.commit()
            return "ok", {"workspace_id": workspace_id, "id": transfer_id}
