"""Admin user, session and workspace operations (P10B-W10.2). METADATA ONLY.

Every mutation here runs in ONE database transaction together with its required audit row (the audit
spec comes from ``admin_audit.build_audit``); if any step, including the audit insert, fails, the whole
change rolls back (SEC-W10-02 semantics extended to W10.2). Reads project explicit safe fields only: no
session token or token hash, no candidate content, no workspace-contained content.

Concurrency: the rows that decide an invariant (the active platform admins; the active owners of a
workspace) are read with ``SELECT ... FOR UPDATE`` inside the mutation transaction. SQLite ignores the
lock clause but serialises writers, so a racing second writer fails instead of both committing; PostgreSQL
takes real row locks.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.application.errors import ConflictError
from src.auth_repository import AccountRepository
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    DEFAULT_LOCALE,
    MEMBERSHIP_STATUS_ACTIVE,
    MEMBERSHIP_STATUS_REMOVED,
    PLATFORM_ROLE_ADMIN,
    SHARE_STATUS_ACTIVE,
    SHARE_STATUS_REVOKED,
    TIER_BASIC,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    AuditEvent,
    AuthSession,
    ProductEntitlement,
    ShareGrant,
    User,
    UserPreference,
    Workspace,
    WorkspaceMembership,
    utcnow,
)

MAX_PAGE_SIZE = 100
LAST_ADMIN_MESSAGE = "This would leave no active platform administrator."


class AdminNotFound(LookupError):
    """The target account/workspace/membership does not exist (mapped to 404)."""


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _stage(session: Session, audit: dict | None, **extra) -> None:
    """Add the audit row to THIS transaction (extra safe fields are merged into its context)."""
    if not audit:
        return
    spec = dict(audit)
    if extra:
        spec["context"] = {**(audit.get("context") or {}), **extra}
    AccountRepository._stage_audit(session, spec)


def _page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, int(page)), max(1, min(int(page_size), MAX_PAGE_SIZE))


class AdminUserRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    @property
    def session_factory(self) -> sessionmaker:
        return self._sf

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _other_active_admins(s: Session, user_id: int) -> int:
        rows = s.scalars(
            select(User.id).where(
                User.platform_role == PLATFORM_ROLE_ADMIN,
                User.status == ACCOUNT_STATUS_ACTIVE,
                User.id != user_id,
            ).with_for_update()
        ).all()
        return len(rows)

    @staticmethod
    def _revoke_live_sessions(s: Session, user_id: int) -> int:
        now = utcnow()
        live = s.scalar(
            select(func.count()).select_from(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        ) or 0
        s.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return int(live)

    @staticmethod
    def _user(s: Session, user_id: int) -> User:
        user = s.get(User, user_id, with_for_update=True)
        if user is None:
            raise AdminNotFound("Account not found.")
        return user

    # -- reads ----------------------------------------------------------------

    def list_users(self, *, q: str | None = None, status: str | None = None, role: str | None = None,
                   tier: str | None = None, onboarding: str | None = None, locale: str | None = None,
                   email_verified: bool | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        now = utcnow()
        ws_count = (select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.user_id == User.id,
            WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE).correlate(User).scalar_subquery())
        sess_count = (select(func.count()).select_from(AuthSession).where(
            AuthSession.user_id == User.id, AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now).correlate(User).scalar_subquery())
        base = (select(User, ProductEntitlement.tier, UserPreference.interface_locale,
                       ws_count.label("ws"), sess_count.label("sess"))
                .outerjoin(ProductEntitlement, ProductEntitlement.user_id == User.id)
                .outerjoin(UserPreference, UserPreference.user_id == User.id))
        conds = []
        if q and q.strip():
            term = q.strip().lower()
            like = func.lower(User.email).contains(term, autoescape=True)
            conds.append(or_(like, User.id == int(term)) if term.isdigit() else like)
        if status:
            conds.append(User.status == status)
        if role:
            conds.append(User.platform_role == role)
        if tier:
            conds.append(ProductEntitlement.tier == tier if tier != TIER_BASIC
                         else or_(ProductEntitlement.tier == TIER_BASIC, ProductEntitlement.tier.is_(None)))
        if onboarding == "completed":
            conds.append(User.onboarding_completed_at.is_not(None))
        elif onboarding == "pending":
            conds.append(User.onboarding_completed_at.is_(None))
        if locale:
            conds.append(UserPreference.interface_locale == locale if locale != DEFAULT_LOCALE
                         else or_(UserPreference.interface_locale == locale,
                                  UserPreference.interface_locale.is_(None)))
        if email_verified is not None:
            conds.append(User.email_verified.is_(email_verified))
        with self._sf() as s:
            total = int(s.scalar(
                select(func.count()).select_from(User)
                .outerjoin(ProductEntitlement, ProductEntitlement.user_id == User.id)
                .outerjoin(UserPreference, UserPreference.user_id == User.id).where(*conds)) or 0)
            rows = s.execute(base.where(*conds).order_by(User.created_at.desc(), User.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            items = [self._summary(u, t, loc, ws, sess) for u, t, loc, ws, sess in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _summary(u: User, tier, locale, ws, sess) -> dict:
        return {
            "user_id": u.id, "email": u.email, "display_name": u.display_name, "status": u.status,
            "platform_role": u.platform_role, "tier": tier or TIER_BASIC,
            "onboarding_completed": u.onboarding_completed_at is not None,
            "interface_locale": locale or DEFAULT_LOCALE, "email_verified": bool(u.email_verified),
            "created_at": _iso(u.created_at), "updated_at": _iso(u.updated_at),
            "workspace_count": int(ws or 0), "active_session_count": int(sess or 0),
        }

    def get_user_detail(self, user_id: int, *, audit_limit: int = 20) -> dict | None:
        now = utcnow()
        with self._sf() as s:
            u = s.get(User, user_id)
            if u is None:
                return None
            ent = s.scalar(select(ProductEntitlement.tier).where(ProductEntitlement.user_id == user_id))
            loc = s.scalar(select(UserPreference.interface_locale).where(UserPreference.user_id == user_id))
            sess = s.scalars(select(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now).order_by(AuthSession.created_at.desc()).limit(20)).all()
            members = s.execute(
                select(WorkspaceMembership, Workspace.name, Workspace.status)
                .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
                .where(WorkspaceMembership.user_id == user_id)
                .order_by(WorkspaceMembership.created_at)).all()
            events = s.scalars(select(AuditEvent).where(
                AuditEvent.target_type == "user", AuditEvent.target_id == str(user_id),
                AuditEvent.event_type.like("admin.%"))
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(audit_limit)).all()
            summary = self._summary(u, ent, loc, sum(1 for m, *_ in members if m.status == MEMBERSHIP_STATUS_ACTIVE), len(sess))
            return {
                "account": summary,
                "sessions": {
                    "active_count": len(sess),
                    # Only data that is genuinely stored and safe: never the token or its hash.
                    "recent": [{"created_at": _iso(r.created_at), "last_used_at": _iso(r.last_used_at),
                                "expires_at": _iso(r.expires_at)} for r in sess[:10]],
                },
                "workspaces": [{"workspace_id": m.workspace_id, "name": name, "workspace_status": wst,
                                "role": m.role, "membership_status": m.status,
                                "joined_at": _iso(m.created_at)} for m, name, wst in members],
                "audit": [{"event_type": e.event_type, "result": e.result, "actor_user_id": e.actor_user_id,
                           "request_id": e.request_id, "created_at": _iso(e.created_at),
                           "context": e.context} for e in events],
            }

    # -- mutations (state + audit in one transaction) ----------------------------

    def set_status(self, user_id: int, status: str, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            user = self._user(s, user_id)
            before = user.status
            if before == status:  # no-op: still audited (every accepted privileged call leaves evidence)
                _stage(s, audit, sessions_revoked=0)
                s.commit()
                return {"user_id": user_id, "status": status, "changed": False, "sessions_revoked": 0}
            if (status != ACCOUNT_STATUS_ACTIVE and before == ACCOUNT_STATUS_ACTIVE
                    and user.platform_role == PLATFORM_ROLE_ADMIN
                    and self._other_active_admins(s, user_id) == 0):
                raise ConflictError(LAST_ADMIN_MESSAGE)
            user.status = status
            user.updated_at = utcnow()
            # Deactivation ends every live session NOW (SEC-W10-01). Reactivation never revives them.
            revoked = self._revoke_live_sessions(s, user_id) if status != ACCOUNT_STATUS_ACTIVE else 0
            _stage(s, audit, sessions_revoked=revoked)
            s.commit()
            return {"user_id": user_id, "status": status, "changed": True, "sessions_revoked": revoked}

    def set_platform_role(self, user_id: int, role: str, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            user = self._user(s, user_id)
            before = user.platform_role
            if before == role:  # no-op: still audited
                _stage(s, audit, elevation=False)
                s.commit()
                return {"user_id": user_id, "platform_role": role, "changed": False}
            if (before == PLATFORM_ROLE_ADMIN and user.status == ACCOUNT_STATUS_ACTIVE
                    and self._other_active_admins(s, user_id) == 0):
                raise ConflictError(LAST_ADMIN_MESSAGE)
            user.platform_role = role
            user.updated_at = utcnow()
            _stage(s, audit, elevation=(role == PLATFORM_ROLE_ADMIN))
            s.commit()
            return {"user_id": user_id, "platform_role": role, "changed": True}

    def revoke_sessions(self, user_id: int, *, audit: dict | None = None) -> int:
        with self._sf() as s:
            self._user(s, user_id)
            revoked = self._revoke_live_sessions(s, user_id)
            _stage(s, audit, sessions_revoked=revoked)
            s.commit()
            return revoked

    # -- workspaces (admin) ------------------------------------------------------

    def list_workspaces(self, *, q: str | None = None, status: str | None = None,
                        page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        members = (select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == Workspace.id,
            WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE).correlate(Workspace).scalar_subquery())
        conds = []
        if q and q.strip():
            term = q.strip().lower()
            like = func.lower(Workspace.name).contains(term, autoescape=True)
            conds.append(or_(like, Workspace.id == int(term)) if term.isdigit() else like)
        if status:
            conds.append(Workspace.status == status)
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(Workspace).where(*conds)) or 0)
            rows = s.execute(
                select(Workspace, User.email, members.label("n"))
                .outerjoin(User, User.id == Workspace.owner_user_id).where(*conds)
                .order_by(Workspace.created_at.desc(), Workspace.id.desc())
                .limit(page_size).offset((page - 1) * page_size)).all()
            items = [{"id": w.id, "name": w.name, "status": w.status, "owner_user_id": w.owner_user_id,
                      "owner_email": email, "member_count": int(n or 0), "created_at": _iso(w.created_at)}
                     for w, email, n in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_workspace_detail(self, workspace_id: int) -> dict | None:
        with self._sf() as s:
            w = s.get(Workspace, workspace_id)
            if w is None:
                return None
            owner_email = s.scalar(select(User.email).where(User.id == w.owner_user_id))
            rows = s.execute(
                select(WorkspaceMembership, User.email, User.status)
                .join(User, User.id == WorkspaceMembership.user_id)
                .where(WorkspaceMembership.workspace_id == workspace_id)
                .order_by(WorkspaceMembership.created_at)).all()
            active_shares = int(s.scalar(select(func.count()).select_from(ShareGrant).where(
                ShareGrant.workspace_id == workspace_id, ShareGrant.status == SHARE_STATUS_ACTIVE)) or 0)
            active = [m for m, *_ in rows if m.status == MEMBERSHIP_STATUS_ACTIVE]
            return {
                "workspace": {"id": w.id, "name": w.name, "status": w.status, "owner_user_id": w.owner_user_id,
                              "owner_email": owner_email, "member_count": len(active),
                              "created_at": _iso(w.created_at)},
                "members": [{"user_id": m.user_id, "email": email, "account_status": ust, "role": m.role,
                             "membership_status": m.status, "joined_at": _iso(m.created_at)}
                            for m, email, ust in rows],
                # A count only: shared items themselves are candidate content and never listed here.
                "active_share_count": active_shares,
                "active_owner_count": sum(1 for m in active if m.role == WORKSPACE_ROLE_OWNER),
            }

    @staticmethod
    def _active_owner_rows(s: Session, workspace_id: int) -> list[int]:
        return list(s.scalars(select(WorkspaceMembership.user_id).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role == WORKSPACE_ROLE_OWNER,
            WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE).with_for_update()).all())

    @staticmethod
    def _workspace(s: Session, workspace_id: int) -> Workspace:
        w = s.get(Workspace, workspace_id, with_for_update=True)
        if w is None:
            raise AdminNotFound("Workspace not found.")
        return w

    @staticmethod
    def _membership(s: Session, workspace_id: int, user_id: int) -> WorkspaceMembership | None:
        return s.scalar(select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.user_id == user_id))

    def add_member(self, workspace_id: int, user_id: int, role: str, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            w = self._workspace(s, workspace_id)
            if w.status != WORKSPACE_STATUS_ACTIVE:
                raise ConflictError("The workspace is not active.")
            user = s.get(User, user_id)
            if user is None:
                raise AdminNotFound("Account not found.")
            if user.status != ACCOUNT_STATUS_ACTIVE:
                raise ConflictError("Only an active account can be added to a workspace.")
            m = self._membership(s, workspace_id, user_id)
            if m is not None and m.status == MEMBERSHIP_STATUS_ACTIVE:
                raise ConflictError("That account is already a member of this workspace.")
            if m is None:
                s.add(WorkspaceMembership(workspace_id=workspace_id, user_id=user_id, role=role,
                                          status=MEMBERSHIP_STATUS_ACTIVE))
            else:
                m.role, m.status, m.updated_at = role, MEMBERSHIP_STATUS_ACTIVE, utcnow()
            _stage(s, audit)
            s.commit()
            return {"workspace_id": workspace_id, "user_id": user_id, "role": role}

    def remove_member(self, workspace_id: int, user_id: int, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            self._workspace(s, workspace_id)
            m = self._membership(s, workspace_id, user_id)
            if m is None or m.status != MEMBERSHIP_STATUS_ACTIVE:
                raise AdminNotFound("That member is not in this workspace.")
            if m.role == WORKSPACE_ROLE_OWNER and len(self._active_owner_rows(s, workspace_id)) <= 1:
                raise ConflictError("Cannot remove the last owner of a workspace.")
            m.status, m.updated_at = MEMBERSHIP_STATUS_REMOVED, utcnow()
            now = utcnow()
            revoked = s.execute(
                update(ShareGrant).where(
                    ShareGrant.owner_user_id == user_id, ShareGrant.workspace_id == workspace_id,
                    ShareGrant.status == SHARE_STATUS_ACTIVE)
                .values(status=SHARE_STATUS_REVOKED, revoked_at=now)).rowcount or 0
            _stage(s, audit, shares_revoked=int(revoked))
            s.commit()
            return {"workspace_id": workspace_id, "user_id": user_id, "shares_revoked": int(revoked)}

    def set_member_role(self, workspace_id: int, user_id: int, role: str, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            self._workspace(s, workspace_id)
            m = self._membership(s, workspace_id, user_id)
            if m is None or m.status != MEMBERSHIP_STATUS_ACTIVE:
                raise AdminNotFound("That member is not in this workspace.")
            if m.role == role:
                return {"workspace_id": workspace_id, "user_id": user_id, "role": role, "changed": False}
            if m.role == WORKSPACE_ROLE_OWNER and len(self._active_owner_rows(s, workspace_id)) <= 1:
                raise ConflictError("A workspace must keep at least one owner.")
            m.role, m.updated_at = role, utcnow()
            _stage(s, audit)
            s.commit()
            return {"workspace_id": workspace_id, "user_id": user_id, "role": role, "changed": True}
