"""Two-person platform-role changes (P10B-W10.13), closing the W10.2 gap.

A role is never changed by one Admin alone: one Admin REQUESTS (creating a durable request), a DIFFERENT Admin who currently holds
``platform.users.role.assign`` APPROVES, and the approval, the role update and the audit row commit in ONE transaction. The target may be neither requester nor
approver. Approval re-reads the target's current role and the actors' current state: an obsolete decision is marked ``stale`` and never applied.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.admin_repository import LAST_ADMIN_MESSAGE, AdminNotFound, AdminUserRepository, _stage
from src.application import admin_audit as A
from src.application.admin_permissions import USERS_ROLE_ASSIGN, permissions_for_role
from src.application.errors import ConflictError, ValidationError
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE, PLATFORM_ROLE_ADMIN, PLATFORM_ROLES, AdminRoleChangeRequest, User, utcnow,
)


def _iso(v):
    return v.isoformat() if v else None


def _view(r: AdminRoleChangeRequest) -> dict:
    return {"public_id": r.public_id, "target_user_id": r.target_user_id, "before_role": r.before_role, "requested_role": r.requested_role,
            "requester_user_id": r.requester_user_id, "approver_user_id": r.approver_user_id, "status": r.status, "reason": r.reason,
            "requested_at": _iso(r.requested_at), "decided_at": _iso(r.decided_at), "applied_at": _iso(r.applied_at), "revision": r.revision}


def _active(u: User | None) -> bool:
    return u is not None and u.status == ACCOUNT_STATUS_ACTIVE


def _may_assign(u: User | None) -> bool:
    """CURRENT database authority: the actor is active and their role presently holds role.assign."""
    return _active(u) and USERS_ROLE_ASSIGN in permissions_for_role(u.platform_role)


class RoleChangeService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def list(self, *, status: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = max(1, int(page)), max(1, min(int(page_size), 100))
        conds = [AdminRoleChangeRequest.status == status] if status else []
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(AdminRoleChangeRequest).where(*conds)) or 0)
            rows = s.scalars(select(AdminRoleChangeRequest).where(*conds).order_by(AdminRoleChangeRequest.requested_at.desc(), AdminRoleChangeRequest.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            items = [_view(r) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size, "assignable_roles": list(PLATFORM_ROLES)}

    def pending_count(self) -> int:
        with self._sf() as s:
            return int(s.scalar(select(func.count()).select_from(AdminRoleChangeRequest).where(AdminRoleChangeRequest.status == "pending")) or 0)

    def request(self, *, target_user_id: int, requested_role: str, reason: str, requester_user_id: int, request_id: str | None, audit: dict) -> dict:
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("A reason is required.")
        if len(reason) > 200:
            raise ValidationError("The reason is too long.")
        if requested_role not in PLATFORM_ROLES:  # only code-defined presets
            raise ValidationError("Unknown platform role.")
        if target_user_id == requester_user_id:
            raise ConflictError("You cannot request a role change for your own account.")
        with self._sf() as s:
            requester = s.get(User, requester_user_id)
            if not _may_assign(requester):
                raise ConflictError("The requester is not an active Admin who may assign roles.")
            target = s.get(User, target_user_id)
            if target is None:
                raise AdminNotFound("Account not found.")
            if target.platform_role == requested_role:
                raise ConflictError("The account already has that role.")
            req = AdminRoleChangeRequest(public_id=uuid.uuid4().hex, target_user_id=target_user_id, before_role=target.platform_role,
                                         requested_role=requested_role, requester_user_id=requester_user_id, status="pending", reason=reason,
                                         requested_at=utcnow(), revision=0)
            s.add(req)
            _stage(s, audit, request_public_id=req.public_id, requested_role=requested_role)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise ConflictError("A role change is already pending for this account.")
            return _view(req)

    @staticmethod
    def _get(s: Session, public_id: str) -> AdminRoleChangeRequest:
        r = s.scalar(select(AdminRoleChangeRequest).where(AdminRoleChangeRequest.public_id == public_id).with_for_update())
        if r is None:
            raise AdminNotFound("Role change request not found.")
        return r

    def approve(self, public_id: str, *, approver_user_id: int, request_id: str | None, audit_for) -> dict:
        """``audit_for(event_name, **ctx)`` builds the audit spec. Returns the request view; ``outcome`` is 'applied', 'replay' or 'stale'."""
        with self._sf() as s:
            r = self._get(s, public_id)
            if r.status == "applied" and r.approver_user_id == approver_user_id:
                return {**_view(r), "outcome": "replay"}      # idempotent replay: no second mutation, no second audit row
            if r.status != "pending":
                raise ConflictError(f"This request is already {r.status}.")
            if approver_user_id in (r.requester_user_id, r.target_user_id):
                raise ConflictError("A second, different Admin must approve; the requester and the target cannot.")
            approver = s.get(User, approver_user_id)
            if not _may_assign(approver):
                raise ConflictError("The approver is not an active Admin who may assign roles.")
            requester = s.get(User, r.requester_user_id) if r.requester_user_id else None
            target = s.get(User, r.target_user_id)
            reason = None
            if not _may_assign(requester):
                reason = "requester_no_longer_authorised"
            elif target is None or target.platform_role != r.before_role:
                reason = "target_role_changed"
            if reason:
                now = utcnow()
                r.status, r.decided_at, r.decision_reason, r.revision = "stale", now, reason, r.revision + 1
                _stage(s, audit_for(A.ADMIN_ROLE_CHANGE_STALE, result="stale"), request_public_id=public_id, target_user_id=r.target_user_id, reason_code=reason)
                s.commit()
                return {**_view(r), "outcome": "stale", "stale_reason": reason}
            if (r.before_role == PLATFORM_ROLE_ADMIN and target.status == ACCOUNT_STATUS_ACTIVE
                    and AdminUserRepository._other_active_admins(s, target.id) == 0):
                raise ConflictError(LAST_ADMIN_MESSAGE)
            now = utcnow()
            target.platform_role, target.updated_at = r.requested_role, now
            r.status, r.approver_user_id, r.decided_at, r.applied_at, r.revision = "applied", approver_user_id, now, now, r.revision + 1
            _stage(s, audit_for(A.ADMIN_ROLE_CHANGE_APPROVED), request_public_id=public_id, target_user_id=r.target_user_id,
                   before_role=r.before_role, requested_role=r.requested_role, elevation=(r.requested_role == PLATFORM_ROLE_ADMIN))
            s.commit()   # approval + role update + audit: ONE transaction
            return {**_view(r), "outcome": "applied"}

    def _close(self, public_id: str, *, actor_user_id: int, new_status: str, audit: dict, decision_reason: str | None) -> dict:
        with self._sf() as s:
            r = self._get(s, public_id)
            if r.status != "pending":
                raise ConflictError(f"This request is already {r.status}.")
            if new_status == "cancelled" and actor_user_id != r.requester_user_id:
                raise ConflictError("Only the requester can cancel a request.")
            if new_status == "rejected" and actor_user_id in (r.requester_user_id, r.target_user_id):
                raise ConflictError("The requester cancels; the target cannot decide their own request.")
            now = utcnow()
            r.status, r.decided_at, r.revision = new_status, now, r.revision + 1
            r.decision_reason = (decision_reason or "").strip()[:200] or None
            if new_status == "rejected":
                r.approver_user_id = actor_user_id
            _stage(s, audit, request_public_id=public_id)
            s.commit()
            return _view(r)

    def reject(self, public_id: str, *, approver_user_id: int, audit: dict, reason: str | None = None) -> dict:
        with self._sf() as s:
            if not _may_assign(s.get(User, approver_user_id)):
                raise ConflictError("The approver is not an active Admin who may assign roles.")
        return self._close(public_id, actor_user_id=approver_user_id, new_status="rejected", audit=audit, decision_reason=reason)

    def cancel(self, public_id: str, *, requester_user_id: int, audit: dict) -> dict:
        return self._close(public_id, actor_user_id=requester_user_id, new_status="cancelled", audit=audit, decision_reason=None)
