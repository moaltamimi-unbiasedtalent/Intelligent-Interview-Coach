"""Owner- and workspace-scoped data access for Teams/Workspaces (Capstone P6.5).

Every read/write is scoped by workspace membership or resource ownership; a foreign id
resolves to None / a no-op, never another user's or workspace's data. Returns plain dict
projections (safe metadata) — never live ORM objects, and never candidate-private content.
Sharing access is re-derived on every read so revocation/deletion take effect immediately.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from src.persistence import (
    INVITATION_STATUS_ACCEPTED,
    INVITATION_STATUS_PENDING,
    MEMBERSHIP_STATUS_ACTIVE,
    SHARE_STATUS_ACTIVE,
    SHARE_STATUS_REVOKED,
    WORKSPACE_ROLE_MEMBER,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    ShareGrant,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    utcnow,
)

__all__ = ["WorkspaceRepository"]


class WorkspaceRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    @property
    def session_factory(self) -> sessionmaker:
        return self._sf

    # -- workspaces -----------------------------------------------------------

    def create_workspace(self, *, owner_user_id: int, name: str) -> int:
        with self._sf() as s:
            ws = Workspace(owner_user_id=owner_user_id, name=name, status=WORKSPACE_STATUS_ACTIVE)
            s.add(ws)
            s.flush()
            s.add(WorkspaceMembership(
                workspace_id=ws.id, user_id=owner_user_id,
                role=WORKSPACE_ROLE_OWNER, status=MEMBERSHIP_STATUS_ACTIVE))
            s.commit()
            return ws.id

    def get_workspace(self, workspace_id: int) -> dict | None:
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id)
            return self._ws_dict(s, ws) if ws else None

    def _ws_dict(self, s, ws: Workspace) -> dict:
        member_count = s.scalar(
            select(func.count()).select_from(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == ws.id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE,
            )
        ) or 0
        return {
            "id": ws.id, "name": ws.name, "status": ws.status,
            "owner_user_id": ws.owner_user_id, "member_count": int(member_count),
            "created_at": ws.created_at.isoformat() if ws.created_at else None,
        }

    def set_workspace_status(self, workspace_id: int, status: str) -> bool:
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id)
            if ws is None:
                return False
            ws.status = status
            ws.updated_at = utcnow()
            s.commit()
            return True

    def transfer_ownership(self, *, workspace_id: int, new_owner_user_id: int) -> bool:
        """Make new_owner the WORKSPACE_OWNER (must be an active member); demote the old
        owner to member. Updates workspaces.owner_user_id."""
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id)
            if ws is None:
                return False
            new_m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == new_owner_user_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))
            if new_m is None:
                return False
            old_owner = ws.owner_user_id
            new_m.role = WORKSPACE_ROLE_OWNER
            old_m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == old_owner))
            if old_m is not None and old_owner != new_owner_user_id:
                old_m.role = WORKSPACE_ROLE_MEMBER
            ws.owner_user_id = new_owner_user_id
            ws.updated_at = utcnow()
            s.commit()
            return True

    def list_workspaces_for_user(self, user_id: int) -> list[dict]:
        with self._sf() as s:
            rows = s.execute(
                select(Workspace, WorkspaceMembership.role)
                .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
                .where(WorkspaceMembership.user_id == user_id,
                       WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)
                .order_by(Workspace.created_at)
            ).all()
            out = []
            for ws, role in rows:
                d = self._ws_dict(s, ws)
                d["my_role"] = role
                out.append(d)
            return out

    def list_workspaces_admin(self, limit: int = 200) -> list[dict]:
        """Admin metadata listing (no candidate content)."""
        with self._sf() as s:
            rows = s.scalars(select(Workspace).order_by(Workspace.created_at.desc()).limit(limit)).all()
            return [self._ws_dict(s, ws) for ws in rows]

    # -- membership -----------------------------------------------------------

    def member_role(self, workspace_id: int, user_id: int) -> str | None:
        """The caller's ACTIVE workspace role, or None if not an active member."""
        with self._sf() as s:
            m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))
            return m.role if m else None

    def list_members(self, workspace_id: int) -> list[dict]:
        """Active members — metadata only (user_id, role); never private account data."""
        with self._sf() as s:
            rows = s.scalars(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)
                .order_by(WorkspaceMembership.created_at)).all()
            return [{"user_id": m.user_id, "role": m.role, "status": m.status,
                     "joined_at": m.created_at.isoformat() if m.created_at else None}
                    for m in rows]

    def count_active_owners(self, workspace_id: int) -> int:
        with self._sf() as s:
            return int(s.scalar(
                select(func.count()).select_from(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.role == WORKSPACE_ROLE_OWNER,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)) or 0)

    def upsert_membership(self, *, workspace_id: int, user_id: int, role: str) -> None:
        """Add or re-activate a membership (re-inviting a removed member reuses the row)."""
        with self._sf() as s:
            m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id))
            if m is None:
                s.add(WorkspaceMembership(workspace_id=workspace_id, user_id=user_id,
                                         role=role, status=MEMBERSHIP_STATUS_ACTIVE))
            else:
                m.role = role
                m.status = MEMBERSHIP_STATUS_ACTIVE
                m.updated_at = utcnow()
            s.commit()

    def set_membership_status(self, *, workspace_id: int, user_id: int, status: str) -> bool:
        with self._sf() as s:
            m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id))
            if m is None:
                return False
            m.status = status
            m.updated_at = utcnow()
            s.commit()
            return True

    # -- invitations ----------------------------------------------------------

    def create_invitation(self, *, workspace_id: int, inviter_user_id: int, email: str,
                          token_hash: str, role: str, expires_at: datetime) -> int:
        with self._sf() as s:
            inv = WorkspaceInvitation(
                workspace_id=workspace_id, inviter_user_id=inviter_user_id,
                email=email, token_hash=token_hash, role=role,
                status=INVITATION_STATUS_PENDING, expires_at=expires_at)
            s.add(inv)
            s.commit()
            return inv.id

    def get_invitation_by_token_hash(self, token_hash: str) -> dict | None:
        with self._sf() as s:
            inv = s.scalar(select(WorkspaceInvitation).where(
                WorkspaceInvitation.token_hash == token_hash))
            return self._inv_dict(inv) if inv else None

    def get_invitation(self, invitation_id: int) -> dict | None:
        with self._sf() as s:
            inv = s.get(WorkspaceInvitation, invitation_id)
            return self._inv_dict(inv) if inv else None

    def _inv_dict(self, inv: WorkspaceInvitation) -> dict:
        return {
            "id": inv.id, "workspace_id": inv.workspace_id,
            "inviter_user_id": inv.inviter_user_id, "email": inv.email,
            "role": inv.role, "status": inv.status,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "accepted_user_id": inv.accepted_user_id,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }

    def set_invitation_status(self, *, invitation_id: int, status: str,
                             accepted_user_id: int | None = None) -> bool:
        with self._sf() as s:
            inv = s.get(WorkspaceInvitation, invitation_id)
            if inv is None:
                return False
            inv.status = status
            if accepted_user_id is not None:
                inv.accepted_user_id = accepted_user_id
            inv.updated_at = utcnow()
            s.commit()
            return True

    def list_invitations_for_workspace(self, workspace_id: int) -> list[dict]:
        with self._sf() as s:
            rows = s.scalars(select(WorkspaceInvitation).where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING)
                .order_by(WorkspaceInvitation.created_at.desc())).all()
            # Email is metadata the workspace owner already knows (they invited them).
            return [self._inv_dict(i) for i in rows]

    def list_pending_invitations_for_email(self, email: str) -> list[dict]:
        with self._sf() as s:
            rows = s.scalars(select(WorkspaceInvitation).where(
                func.lower(WorkspaceInvitation.email) == email.strip().lower(),
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING)
                .order_by(WorkspaceInvitation.created_at.desc())).all()
            out = []
            for inv in rows:
                ws = s.get(Workspace, inv.workspace_id)
                d = self._inv_dict(inv)
                d["workspace_name"] = ws.name if ws else None
                out.append(d)
            return out

    # -- sharing --------------------------------------------------------------

    def create_share(self, *, owner_user_id: int, workspace_id: int, resource_type: str,
                     resource_id: str, permission: str) -> int:
        """Create or re-activate a VIEW share of an owned resource into a workspace."""
        with self._sf() as s:
            existing = s.scalar(select(ShareGrant).where(
                ShareGrant.owner_user_id == owner_user_id,
                ShareGrant.workspace_id == workspace_id,
                ShareGrant.resource_type == resource_type,
                ShareGrant.resource_id == resource_id))
            if existing is not None:
                existing.status = SHARE_STATUS_ACTIVE
                existing.permission = permission
                existing.revoked_at = None
                s.commit()
                return existing.id
            grant = ShareGrant(
                owner_user_id=owner_user_id, workspace_id=workspace_id,
                resource_type=resource_type, resource_id=resource_id,
                permission=permission, status=SHARE_STATUS_ACTIVE)
            s.add(grant)
            s.commit()
            return grant.id

    def revoke_share(self, *, share_id: int, owner_user_id: int) -> bool:
        """Revoke a share — ONLY the owner may (owner-scoped)."""
        with self._sf() as s:
            grant = s.get(ShareGrant, share_id)
            if grant is None or grant.owner_user_id != owner_user_id:
                return False
            grant.status = SHARE_STATUS_REVOKED
            grant.revoked_at = utcnow()
            s.commit()
            return True

    def get_share(self, share_id: int) -> dict | None:
        with self._sf() as s:
            g = s.get(ShareGrant, share_id)
            return self._share_dict(g) if g else None

    def _share_dict(self, g: ShareGrant) -> dict:
        return {
            "id": g.id, "owner_user_id": g.owner_user_id, "workspace_id": g.workspace_id,
            "resource_type": g.resource_type, "resource_id": g.resource_id,
            "permission": g.permission, "status": g.status,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None,
        }

    def active_share_owner_for_member(self, *, user_id: int, resource_type: str,
                                      resource_id: str) -> int | None:
        """THE authorization read: return the owner id iff an ACTIVE share of this
        resource exists into an ACTIVE workspace the caller is an ACTIVE member of (and
        the workspace itself is active). Else None. Re-derived every call → revocation and
        deletion take effect immediately; a stale/cached link cannot bypass it."""
        with self._sf() as s:
            row = s.execute(
                select(ShareGrant.owner_user_id)
                .join(WorkspaceMembership, WorkspaceMembership.workspace_id == ShareGrant.workspace_id)
                .join(Workspace, Workspace.id == ShareGrant.workspace_id)
                .where(
                    ShareGrant.resource_type == resource_type,
                    ShareGrant.resource_id == resource_id,
                    ShareGrant.status == SHARE_STATUS_ACTIVE,
                    Workspace.status == WORKSPACE_STATUS_ACTIVE,
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE,
                )
            ).first()
            return int(row[0]) if row else None

    def list_shares_by_owner(self, owner_user_id: int) -> list[dict]:
        with self._sf() as s:
            rows = s.scalars(select(ShareGrant).where(
                ShareGrant.owner_user_id == owner_user_id,
                ShareGrant.status == SHARE_STATUS_ACTIVE)
                .order_by(ShareGrant.created_at.desc())).all()
            return [self._share_dict(g) for g in rows]

    def list_shares_for_member(self, user_id: int) -> list[dict]:
        """Resources shared WITH the caller (active shares into their active workspaces)."""
        with self._sf() as s:
            rows = s.scalars(
                select(ShareGrant)
                .join(WorkspaceMembership, WorkspaceMembership.workspace_id == ShareGrant.workspace_id)
                .join(Workspace, Workspace.id == ShareGrant.workspace_id)
                .where(
                    ShareGrant.status == SHARE_STATUS_ACTIVE,
                    Workspace.status == WORKSPACE_STATUS_ACTIVE,
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE,
                    ShareGrant.owner_user_id != user_id,
                )
                .order_by(ShareGrant.created_at.desc())).all()
            return [self._share_dict(g) for g in rows]

    def invalidate_shares_for_resource(self, *, owner_user_id: int, resource_type: str,
                                       resource_id: str) -> int:
        """Revoke all shares of a resource (call when the source resource is deleted)."""
        return self._bulk_revoke(lambda g: (
            g.owner_user_id == owner_user_id and g.resource_type == resource_type
            and g.resource_id == resource_id))

    def revoke_member_shares_into_workspace(self, *, user_id: int, workspace_id: int) -> int:
        """Revoke a member's outbound shares into a workspace (call on leave/remove)."""
        return self._bulk_revoke(lambda g: (
            g.owner_user_id == user_id and g.workspace_id == workspace_id))

    def revoke_workspace_shares(self, workspace_id: int) -> int:
        """Revoke every share into a workspace (call on workspace deactivate/delete)."""
        return self._bulk_revoke(lambda g: g.workspace_id == workspace_id)

    def _bulk_revoke(self, predicate) -> int:
        with self._sf() as s:
            rows = s.scalars(select(ShareGrant).where(
                ShareGrant.status == SHARE_STATUS_ACTIVE)).all()
            n = 0
            for g in rows:
                if predicate(g):
                    g.status = SHARE_STATUS_REVOKED
                    g.revoked_at = utcnow()
                    n += 1
            s.commit()
            return n

    # -- admin metadata -------------------------------------------------------

    def workspace_stats(self) -> dict:
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(Workspace)) or 0)
            active = int(s.scalar(select(func.count()).select_from(Workspace).where(
                Workspace.status == WORKSPACE_STATUS_ACTIVE)) or 0)
            shares = int(s.scalar(select(func.count()).select_from(ShareGrant).where(
                ShareGrant.status == SHARE_STATUS_ACTIVE)) or 0)
            pending_invites = int(s.scalar(select(func.count()).select_from(WorkspaceInvitation).where(
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING)) or 0)
            return {"workspaces_total": total, "workspaces_active": active,
                    "active_shares": shares, "pending_invitations": pending_invites,
                    "accepted_invitations": int(s.scalar(
                        select(func.count()).select_from(WorkspaceInvitation).where(
                            WorkspaceInvitation.status == INVITATION_STATUS_ACCEPTED)) or 0)}
