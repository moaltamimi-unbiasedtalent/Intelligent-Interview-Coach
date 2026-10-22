"""Bulk Admin user actions (03C, OD-BULK-ACTIONS PROVISIONAL recommendation; the permitted set is an OWNER decision, not approved).

Allow-list chosen for LOW harm and REVERSIBILITY only:

* ``force-signout``: revoke every live session (the person simply signs in again);
* ``expire-verification``: invalidate outstanding email-verification links (a new link can be requested at any time).

NOT offered (recorded for the owner, see the evidence file): bulk deactivation, deletion, role change, plan change (03B already has bulk assignment) and
anything touching candidate content, identity or access in a hard-to-reverse way.

Contract (preview, then execute):

* PREVIEW returns counts only, bound to a ``preview_revision`` derived from every chosen account's CURRENT revision, the actor and the active-admin count.
* EXECUTE re-derives that token under a process lock and refuses a stale one (409); evaluates every subject again with the same actor guards as the single
  actions (self, privilege hierarchy, last active ``platform_admin``, acting administrator active); applies each subject inside its own SAVEPOINT, so ONE
  failing subject never undoes the others; stages one audit row per subject plus one batch row in the SAME outer transaction, so an audit failure
  aborts the whole batch (nothing applied). The response lists applied, skipped (reason codes) and failed counts: partial failure is never a silent success.
* The batch row doubles as the idempotency record (``target_id`` = digest of actor, action and Idempotency-Key). There is no unique index (no migration),
  so first-result replay is race-safe within ONE process (a lock serialises batches) and best-effort across processes; the per-subject re-evaluation
  still guarantees no subject is changed twice by overlapping batches.

Metadata only: no email, no token, no candidate content ever enters a response or an audit row.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.admin_repository import AdminUserRepository, _stage
from src.admin_users.actions import pending_verification_tokens
from src.admin_users.guards import AdminForbidden
from src.admin_users.revision import account_revision
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application.errors import ConflictError
from src.persistence import ACCOUNT_STATUS_ACTIVE, AuditEvent, AuthSession, User, utcnow

MAX_BATCH = 100
SELF, HIGHER, LAST_ADMIN, NOT_FOUND = "self", "higher_authority", "last_active_platform_admin", "not_found"
NO_SESSIONS, NO_LINKS = "no_live_sessions", "no_pending_verification"
APPLY_ERROR = "apply_error"
STALE_MESSAGE = "The selection changed since the preview. Preview again before applying."
_LOCK = threading.Lock()      # serialises batches inside one process (SQLite has one writer; PostgreSQL additionally has row locks)


class BulkAuditFailure(RuntimeError):
    """The audit trail could not be written: the whole batch was rolled back and nothing was applied."""


class BulkIdempotencyMismatch(ConflictError):
    """The Idempotency-Key was already used for a different request."""


def _digest(*parts: object, n: int = 32) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:n]


@dataclass(frozen=True)
class BulkAction:
    code: str                                   # the URL token and audit ``action``
    permission: str                             # an EXISTING permission, the same one the single-user action needs
    event: str                                  # the existing single-user audit event reused for an applied subject
    noop: str                                   # reason code when there is nothing to do
    has_effect: Callable[[Session, User], bool]
    apply: Callable[[Session, User], int]


def _live_sessions(s: Session, user_id: int) -> int:
    return int(s.scalar(select(func.count()).select_from(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > utcnow())) or 0)


def _expire_links(s: Session, user: User) -> int:
    now = utcnow()
    rows = pending_verification_tokens(s, user.id, now)
    for row in rows:
        row.consumed_at = now
    return len(rows)


ACTIONS: dict[str, BulkAction] = {
    "force-signout": BulkAction("force-signout", perm.USERS_SESSIONS_REVOKE, A.ADMIN_SESSIONS_REVOKED, NO_SESSIONS,
                                lambda s, u: _live_sessions(s, u.id) > 0, lambda s, u: AdminUserRepository._revoke_live_sessions(s, u.id)),
    "expire-verification": BulkAction("expire-verification", perm.USERS_MANAGE, A.ADMIN_USER_VERIFICATION_EXPIRED, NO_LINKS,
                                      lambda s, u: bool(pending_verification_tokens(s, u.id, utcnow())), _expire_links),
}
# Offered actions are the allow-list above; everything else is deliberately absent (see the module docstring and the evidence file).
NOT_OFFERED = {
    "deactivate": "Ends access and sessions for many people at once; one mistaken selection locks out candidates. Single-account only, with a revision check.",
    "delete": "Irreversible and privacy-gated; stays a per-request, separately authorised pipeline (/admin/privacy).",
    "role-change": "Authority escalation; stays the two-person step-up approval flow (/admin/role-changes), never in bulk.",
    "plan-change": "Already available as the 03B bulk assignment (one transaction, preview, audited); not duplicated here.",
    "resend-verification": "Sends real email to many people from one click; external side effects cannot join the batch transaction or be rolled back.",
    "any action touching candidate content": "No Admin permission reads candidate content; none is added.",
}


def reasons_for(action: BulkAction) -> tuple[str, ...]:
    return (SELF, HIGHER, LAST_ADMIN, NOT_FOUND, action.noop)


def clean_ids(ids: list[int]) -> list[int]:
    out = sorted({int(i) for i in ids})
    if not out or any(i < 1 for i in out) or len(out) > MAX_BATCH:
        raise ValueError(f"Choose between 1 and {MAX_BATCH} valid accounts.")
    return out


class BulkUserActions:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # ------------------------------------------------------------------ evaluation (shared by preview and execute)
    @staticmethod
    def _actor(s: Session, actor_user_id: int, *, lock: bool = False) -> User:
        actor = s.get(User, actor_user_id, with_for_update=lock)
        if actor is None or actor.status != ACCOUNT_STATUS_ACTIVE:
            raise AdminForbidden("The acting administrator is no longer active.")
        return actor

    @staticmethod
    def _active_admins(s: Session) -> int:
        return int(s.scalar(select(func.count()).select_from(User).where(
            User.platform_role == perm.ROLE_PLATFORM_ADMIN, User.status == ACCOUNT_STATUS_ACTIVE)) or 0)

    @staticmethod
    def classify(s: Session, action: BulkAction, actor: User, target: User | None, active_admins: int) -> str | None:
        """Why this subject is excluded, or None when it is eligible. Same protections as the single-user actions."""
        if target is None:
            return NOT_FOUND
        if target.id == actor.id:
            return SELF
        if not perm.permissions_for_role(target.platform_role) <= perm.permissions_for_role(actor.platform_role):
            return HIGHER
        if target.platform_role == perm.ROLE_PLATFORM_ADMIN and target.status == ACCOUNT_STATUS_ACTIVE and active_admins <= 1:
            return LAST_ADMIN
        return None if action.has_effect(s, target) else action.noop

    def _analyse(self, s: Session, action: BulkAction, actor_user_id: int, ids: list[int], *, lock: bool = False) -> tuple[dict[int, str | None], str]:
        actor = self._actor(s, actor_user_id, lock=lock)
        admins = self._active_admins(s)
        outcome: dict[int, str | None] = {}
        revs = []
        for i in ids:
            target = s.get(User, i, with_for_update=lock)
            outcome[i] = self.classify(s, action, actor, target, admins)
            revs.append(f"{i}:{account_revision(s, target) if target else 'missing'}")
        token = _digest("bulk", action.code, actor.id, actor.platform_role, admins, ",".join(revs), n=16)
        return outcome, token

    # ------------------------------------------------------------------ preview
    def preview(self, action_code: str, ids: list[int], *, actor_user_id: int) -> dict:
        action = ACTIONS[action_code]
        clean = clean_ids(ids)
        with self._sf() as s:
            outcome, token = self._analyse(s, action, actor_user_id, clean)
        excluded = {r: 0 for r in reasons_for(action)}
        for reason in outcome.values():
            if reason:
                excluded[reason] += 1
        eligible = sum(1 for r in outcome.values() if r is None)
        return {"action": action.code, "requested": len(ids), "unique": len(clean), "eligible": eligible, "excluded": len(clean) - eligible,
                "excluded_by_reason": excluded, "max_batch": MAX_BATCH, "preview_revision": token}

    # ------------------------------------------------------------------ idempotency
    @staticmethod
    def idempotency_digest(actor_user_id: int, action_code: str, key: str) -> str:
        return _digest("bulk-idem", actor_user_id, action_code, key)

    @staticmethod
    def request_hash(action_code: str, ids: list[int], preview_revision: str, reason: str) -> str:
        return _digest("bulk-req", action_code, ",".join(str(i) for i in ids), preview_revision, reason.strip(), n=32)

    @staticmethod
    def _stored(s: Session, idem: str, req_hash: str) -> dict | None:
        row = s.scalars(select(AuditEvent).where(AuditEvent.event_type == A.ADMIN_USER_BULK_ACTION, AuditEvent.target_id == idem)
                        .order_by(AuditEvent.id).limit(1)).first()
        if row is None:
            return None
        ctx = row.context or {}
        if ctx.get("request_hash") != req_hash:
            raise BulkIdempotencyMismatch("That Idempotency-Key was already used for a different request.")
        return _result_from(ctx, replayed=True)

    def replay(self, action_code: str, ids: list[int], preview_revision: str, reason: str, *, actor_user_id: int, idempotency_key: str) -> dict | None:
        clean = clean_ids(ids)
        with self._sf() as s:
            return self._stored(s, self.idempotency_digest(actor_user_id, action_code, idempotency_key),
                                self.request_hash(action_code, clean, preview_revision, reason))

    # ------------------------------------------------------------------ execute
    def execute(self, action_code: str, ids: list[int], *, preview_revision: str, reason: str, actor_user_id: int, idempotency_key: str,
                request_id: str | None) -> dict:
        action = ACTIONS[action_code]
        clean = clean_ids(ids)
        reason = reason.strip()
        idem = self.idempotency_digest(actor_user_id, action.code, idempotency_key)
        req_hash = self.request_hash(action.code, clean, preview_revision, reason)
        with _LOCK:
            with self._sf() as s:
                again = self._stored(s, idem, req_hash)
                if again is not None:
                    return again
                self._begin_real_transaction(s)
                outcome, token = self._analyse(s, action, actor_user_id, clean, lock=True)
                if token != preview_revision:
                    raise ConflictError(STALE_MESSAGE)
                batch_id = uuid.uuid4().hex[:16]
                applied = 0
                skipped: dict[str, int] = {}
                failed: dict[str, int] = {}
                for i in clean:
                    reason_code = outcome[i]
                    state, code = "success", None
                    if reason_code is None:
                        try:
                            with s.begin_nested():
                                self._reconfirm(s, action, actor_user_id, i)
                                action.apply(s, s.get(User, i))
                            applied += 1
                        except _Skipped as skip:    # a concurrent change made the subject ineligible between the analysis and the apply
                            state, code = "skipped", skip.reason
                            skipped[code] = skipped.get(code, 0) + 1
                        except Exception:  # noqa: BLE001 - one subject failing never undoes the others; only a fixed category is recorded
                            state, code = "failed", APPLY_ERROR
                            failed[code] = failed.get(code, 0) + 1
                    else:
                        state, code = "skipped", reason_code
                        skipped[code] = skipped.get(code, 0) + 1
                    self._audit(s, A.build_audit(
                        event_type=action.event if state == "success" else A.ADMIN_USER_BULK_SUBJECT, actor_user_id=actor_user_id, request_id=request_id,
                        target_type="user", target_id=i, result=state, reason=reason, bulk=True, action=action.code, batch_id=batch_id, reason_code=code))
                counts = {"action": action.code, "batch_id": batch_id, "requested": len(ids), "unique": len(clean), "applied": applied,
                          "skipped": sum(skipped.values()), "skipped_by_reason": skipped, "failed": sum(failed.values()), "failed_by_reason": failed}
                self._audit(s, A.build_audit(
                    event_type=A.ADMIN_USER_BULK_ACTION, actor_user_id=actor_user_id, request_id=request_id, target_type="user_bulk", target_id=idem,
                    reason=reason, request_hash=req_hash, **counts))
                try:
                    s.commit()
                except Exception as exc:  # noqa: BLE001
                            raise BulkAuditFailure("The batch could not be recorded and was not applied.") from exc
                return _result_from(counts, replayed=False)

    @staticmethod
    def _begin_real_transaction(s: Session) -> None:
        """SQLite (dev/test) only: the driver opens a transaction lazily at the first write, so a SAVEPOINT taken before any write would be the OUTERMOST one and its
        RELEASE would COMMIT. Starting the transaction explicitly (IMMEDIATE, so the write lock is taken up front and waits for the busy timeout instead of failing on a later upgrade) makes every
        savepoint genuinely nested, so an audit failure still rolls the whole batch back.
        PostgreSQL begins transactions itself and needs nothing."""
        conn = s.connection()
        if conn.dialect.name == "sqlite" and not conn.connection.dbapi_connection.in_transaction:
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    def _reconfirm(self, s: Session, action: BulkAction, actor_user_id: int, user_id: int) -> None:
        actor = self._actor(s, actor_user_id)
        reason = self.classify(s, action, actor, s.get(User, user_id), self._active_admins(s))
        if reason:
            raise _Skipped(reason)

    @staticmethod
    def _audit(s: Session, spec: dict) -> None:
        try:
            _stage(s, spec)
            s.flush()
        except Exception as exc:  # noqa: BLE001 - an audit failure aborts the WHOLE batch: the outer transaction is never committed
            raise BulkAuditFailure("The batch could not be recorded and was not applied.") from exc


class _Skipped(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _result_from(ctx: dict, *, replayed: bool) -> dict:
    applied, skipped, failed = int(ctx["applied"]), int(ctx["skipped"]), int(ctx["failed"])
    unique = int(ctx["unique"])
    status = "complete" if applied == unique else ("none_applied" if applied == 0 else "partial")
    return {"action": ctx["action"], "batch_id": ctx["batch_id"], "status": status, "requested": int(ctx["requested"]), "unique": unique,
            "applied": applied, "skipped": skipped, "skipped_by_reason": dict(ctx.get("skipped_by_reason") or {}), "failed": failed,
            "failed_by_reason": dict(ctx.get("failed_by_reason") or {}), "replayed": replayed}
