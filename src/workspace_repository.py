"""Owner- and workspace-scoped data access for Teams/Workspaces (Capstone P6.5, completed by 04B).

Every read/write is scoped by workspace membership or resource ownership; a foreign id
resolves to None / a no-op, never another user's or workspace's data. Returns plain dict
projections (safe metadata) — never live ORM objects, and never candidate-private content.
Sharing access is re-derived on every read so revocation/deletion take effect immediately.

04B: every state change that must not be observable half-done (accept an invitation, end a
membership and revoke that member's shares, archive and revoke, delete) is ONE transaction,
and every "claim" (accept, decline, revoke an invitation) is a conditional UPDATE so two
concurrent callers cannot both win.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import sessionmaker

from src.persistence import (
    INVITATION_STATUS_ACCEPTED,
    INVITATION_STATUS_DECLINED,
    INVITATION_STATUS_EXPIRED,
    INVITATION_STATUS_PENDING,
    INVITATION_STATUS_REVOKED,
    MEMBERSHIP_STATUS_ACTIVE,
    SHARE_STATUS_ACTIVE,
    SHARE_STATUS_REVOKED,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_DEACTIVATED,
    ShareGrant,
    Subscription,
    User,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceOwnershipTransfer,
    utcnow,
)
from src.ownership_transfer_repository import cancel_open_in_session

__all__ = ["WorkspaceRepository", "purge_workspace", "mask_email",
           "MAX_PENDING_INVITATIONS", "MAX_ACTIVE_MEMBERS"]

# Bounded growth (04B): a workspace is a small collaboration space, not a directory.
MAX_PENDING_INVITATIONS = 50
MAX_ACTIVE_MEMBERS = 100


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; every stored value is UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def mask_email(email: str | None) -> str:
    """``a***@example.com``: enough to recognise your own colleague, never a usable address."""
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _label(display_name: str | None, email: str | None) -> str:
    name = (display_name or "").strip()
    return name[:80] if name else mask_email(email)


def purge_workspace(s, workspace_id: int) -> dict:
    """Delete a workspace and EVERY dependent row inside the caller's session (explicit child-first deletion because SQLite
    does not enforce cascades). Used by owner deletion and by account deletion when no successor exists, so the two paths cannot
    drift. Candidate content is never touched: it belongs to its owners and was only ever referenced by a share grant."""
    counts = {"shares": 0, "invitations": 0, "memberships": 0, "subscriptions": 0, "transfers": 0, "transfers_cancelled": 0}
    # 04B: an open ownership transfer is cancelled (and audited) before its rows go; terminal transfer rows are removed with the workspace.
    counts["transfers_cancelled"] = len(cancel_open_in_session(s, reason="workspace_deleted", workspace_id=workspace_id))
    for model, col, key in (
        (ShareGrant, ShareGrant.workspace_id, "shares"),
        (WorkspaceInvitation, WorkspaceInvitation.workspace_id, "invitations"),
        (WorkspaceMembership, WorkspaceMembership.workspace_id, "memberships"),
        (Subscription, Subscription.workspace_id, "subscriptions"),   # W10.4: the workspace's own plan assignments
        (WorkspaceOwnershipTransfer, WorkspaceOwnershipTransfer.workspace_id, "transfers"),
    ):
        for obj in s.execute(select(model).where(col == workspace_id)).scalars().all():
            s.delete(obj)
            counts[key] += 1
    from src.billing.service import delete_billing_for

    delete_billing_for(s, workspace_id=workspace_id)                    # W10.5: the workspace's MOCK billing mirrors
    ws = s.get(Workspace, workspace_id)
    if ws is not None:
        s.delete(ws)
    return counts


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

    def rename_workspace(self, workspace_id: int, name: str) -> bool:
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id)
            if ws is None:
                return False
            ws.name = name
            ws.updated_at = utcnow()
            s.commit()
            return True

    def archive_workspace(self, workspace_id: int) -> int | None:
        """Archive (stored as ``deactivated``) AND revoke every share into the workspace in ONE transaction, so there is no moment
        where an archived workspace still serves shared content. Returns the number of grants revoked, or None when the workspace
        is missing. Idempotent. Restoring never revives a revoked grant: the sharer must consent again."""
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id, with_for_update=True)
            if ws is None:
                return None
            ws.status = WORKSPACE_STATUS_DEACTIVATED
            ws.updated_at = utcnow()
            revoked = self._revoke_where(s, ShareGrant.workspace_id == workspace_id)
            s.commit()
            return revoked

    def restore_workspace(self, workspace_id: int) -> bool:
        return self.set_workspace_status(workspace_id, WORKSPACE_STATUS_ACTIVE)

    def delete_workspace(self, workspace_id: int) -> dict | None:
        """Permanently delete the workspace, its memberships, invitations, share grants (so every grant stops granting at once)
        and plan rows, atomically. Returns the row counts, or None when it does not exist."""
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id, with_for_update=True)
            if ws is None:
                return None
            counts = purge_workspace(s, workspace_id)
            s.commit()
            return counts

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
        """Active members. ``email`` and ``display_name`` are returned to the SERVICE, which decides what each caller may see
        (a plain member never receives another member's address)."""
        with self._sf() as s:
            rows = s.execute(
                select(WorkspaceMembership, User.email, User.display_name)
                .join(User, User.id == WorkspaceMembership.user_id)
                .where(WorkspaceMembership.workspace_id == workspace_id,
                       WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)
                .order_by(WorkspaceMembership.created_at, WorkspaceMembership.id)).all()
            return [{"user_id": m.user_id, "role": m.role, "status": m.status,
                     "email": email, "display_name": display_name,
                     "joined_at": m.created_at.isoformat() if m.created_at else None}
                    for m, email, display_name in rows]

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
            self._upsert_membership(s, workspace_id=workspace_id, user_id=user_id, role=role)
            s.commit()

    @staticmethod
    def _upsert_membership(s, *, workspace_id: int, user_id: int, role: str) -> None:
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

    def end_membership(self, *, workspace_id: int, user_id: int, status: str,
                       cancelled_transfers: list[int] | None = None) -> tuple[str, int]:
        """End an ACTIVE membership (left/removed) and revoke that member's outbound shares into the workspace, in ONE transaction,
        refusing to end the last owner (the check and the write share the transaction and the workspace row lock, so two
        concurrent leaves cannot both pass). An open ownership transfer involving this member is cancelled (and audited) in the SAME
        transaction; the cancelled ids are appended to ``cancelled_transfers`` when given. Returns ``(outcome, shares_revoked)``: ok, not_member or last_owner."""
        with self._sf() as s:
            s.get(Workspace, workspace_id, with_for_update=True)             # serialise membership changes per workspace
            m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))
            if m is None:
                return "not_member", 0
            if m.role == WORKSPACE_ROLE_OWNER:
                owners = int(s.scalar(select(func.count()).select_from(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.role == WORKSPACE_ROLE_OWNER,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)) or 0)
                if owners <= 1:
                    return "last_owner", 0
            m.status = status
            m.updated_at = utcnow()
            revoked = self._revoke_where(
                s, ShareGrant.owner_user_id == user_id, ShareGrant.workspace_id == workspace_id)
            cancelled = cancel_open_in_session(s, reason="membership_ended", workspace_id=workspace_id, user_id=user_id)
            if cancelled_transfers is not None:
                cancelled_transfers.extend(cancelled)
            s.commit()
            return "ok", revoked

    def change_member_role(self, *, workspace_id: int, user_id: int, role: str) -> tuple[str, str | None]:
        """Change an ACTIVE non-owner member between admin and member. Never creates or removes an owner (ownership moves only
        through ``transfer_ownership``). Returns ``(outcome, previous_role)``: ok, unchanged, not_member or owner_role."""
        with self._sf() as s:
            s.get(Workspace, workspace_id, with_for_update=True)
            m = s.scalar(select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))
            if m is None:
                return "not_member", None
            if m.role == WORKSPACE_ROLE_OWNER or role == WORKSPACE_ROLE_OWNER:
                return "owner_role", m.role
            if m.role == role:
                return "unchanged", m.role
            previous = m.role
            m.role = role
            m.updated_at = utcnow()
            s.commit()
            return "ok", previous

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

    def issue_invitation(self, *, workspace_id: int, inviter_user_id: int, email: str,
                         token_hash: str, role: str, expires_at: datetime) -> tuple[str, int | None]:
        """Create a pending invitation, superseding (revoking) any earlier pending one for the same address in the same
        transaction (one live token per address), and refusing when the address already belongs to an active member or a bound is
        reached. Returns ``(outcome, invitation_id)``: ok, already_member, too_many_pending, member_limit."""
        with self._sf() as s:
            s.get(Workspace, workspace_id, with_for_update=True)
            member = s.scalar(
                select(WorkspaceMembership.id)
                .join(User, User.id == WorkspaceMembership.user_id)
                .where(WorkspaceMembership.workspace_id == workspace_id,
                       WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE,
                       func.lower(User.email) == email))
            if member is not None:
                return "already_member", None
            active = int(s.scalar(select(func.count()).select_from(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)) or 0)
            if active >= MAX_ACTIVE_MEMBERS:
                return "member_limit", None
            now = utcnow()
            pending = int(s.scalar(select(func.count()).select_from(WorkspaceInvitation).where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING,
                func.lower(WorkspaceInvitation.email) != email)) or 0)
            if pending >= MAX_PENDING_INVITATIONS:
                return "too_many_pending", None
            s.execute(update(WorkspaceInvitation).where(
                WorkspaceInvitation.workspace_id == workspace_id,
                func.lower(WorkspaceInvitation.email) == email,
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING)
                .values(status=INVITATION_STATUS_REVOKED, updated_at=now))
            inv = WorkspaceInvitation(
                workspace_id=workspace_id, inviter_user_id=inviter_user_id,
                email=email, token_hash=token_hash, role=role,
                status=INVITATION_STATUS_PENDING, expires_at=expires_at)
            s.add(inv)
            s.commit()
            return "ok", inv.id

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

    def decide_invitation(self, *, invitation_id: int, user_id: int, email: str,
                          accept: bool) -> tuple[str, dict | None]:
        """Accept or decline an invitation ATOMICALLY and race safely.

        Everything happens in one transaction: the invitation row is claimed with a conditional UPDATE (``status = pending``), so
        of N concurrent decisions exactly one sees ``rowcount == 1``; the membership is written in the same transaction, so there
        is never an accepted invitation without a membership or the reverse. The caller's verified address must equal the invited
        one. Outcomes: ok, not_found, wrong_email, used (already decided or revoked), expired, workspace_inactive, member_limit.
        An existing ACTIVE membership is never downgraded by an invitation (the invitation is just consumed)."""
        with self._sf() as s:
            inv = s.get(WorkspaceInvitation, invitation_id)
            if inv is None:
                return "not_found", None
            if (inv.email or "").strip().lower() != (email or "").strip().lower():
                return "wrong_email", None
            if inv.status != INVITATION_STATUS_PENDING:
                return "used", None
            expires = _aware(inv.expires_at)
            if expires is not None and expires < utcnow():
                s.execute(update(WorkspaceInvitation).where(
                    WorkspaceInvitation.id == invitation_id,
                    WorkspaceInvitation.status == INVITATION_STATUS_PENDING)
                    .values(status=INVITATION_STATUS_EXPIRED, updated_at=utcnow()))
                s.commit()
                return "expired", None
            ws = s.get(Workspace, inv.workspace_id, with_for_update=True)
            if ws is None or ws.status != WORKSPACE_STATUS_ACTIVE:
                return "workspace_inactive", None
            workspace_id, role, inv_id = inv.workspace_id, inv.role, inv.id
            values = {"status": INVITATION_STATUS_ACCEPTED if accept else INVITATION_STATUS_DECLINED,
                      "updated_at": utcnow()}
            if accept:
                values["accepted_user_id"] = user_id
            claimed = s.execute(update(WorkspaceInvitation).where(
                WorkspaceInvitation.id == invitation_id,
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING).values(**values)).rowcount
            if claimed != 1:
                s.rollback()
                return "used", None
            if accept:
                existing = s.scalar(select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))
                if existing is None:
                    active = int(s.scalar(select(func.count()).select_from(WorkspaceMembership).where(
                        WorkspaceMembership.workspace_id == workspace_id,
                        WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE)) or 0)
                    if active >= MAX_ACTIVE_MEMBERS:
                        s.rollback()
                        return "member_limit", None
                    self._upsert_membership(s, workspace_id=workspace_id, user_id=user_id, role=role)
            s.commit()
            return "ok", {"workspace_id": workspace_id, "role": role, "id": inv_id}

    def revoke_invitation(self, *, workspace_id: int, invitation_id: int) -> bool:
        """Revoke a PENDING invitation of this workspace (conditional update; False when not pending or not in this workspace)."""
        with self._sf() as s:
            n = s.execute(update(WorkspaceInvitation).where(
                WorkspaceInvitation.id == invitation_id,
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING)
                .values(status=INVITATION_STATUS_REVOKED, updated_at=utcnow())).rowcount
            s.commit()
            return n == 1

    def list_invitations_for_workspace(self, workspace_id: int) -> list[dict]:
        """Pending invitations (a pending row past its expiry is reported as ``expired``). Newest first, bounded."""
        with self._sf() as s:
            rows = s.scalars(select(WorkspaceInvitation).where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status.in_((INVITATION_STATUS_PENDING, INVITATION_STATUS_EXPIRED)))
                .order_by(WorkspaceInvitation.created_at.desc(), WorkspaceInvitation.id.desc()).limit(100)).all()
            now = utcnow()
            out = []
            for i in rows:
                d = self._inv_dict(i)
                exp = _aware(i.expires_at)
                if d["status"] == INVITATION_STATUS_PENDING and exp is not None and exp < now:
                    d["status"] = INVITATION_STATUS_EXPIRED
                out.append(d)
            return out

    def list_pending_invitations_for_email(self, email: str) -> list[dict]:
        """Live (pending, unexpired) invitations addressed to this address, for an active workspace only."""
        with self._sf() as s:
            now = utcnow()
            rows = s.scalars(select(WorkspaceInvitation).where(
                func.lower(WorkspaceInvitation.email) == email.strip().lower(),
                WorkspaceInvitation.status == INVITATION_STATUS_PENDING)
                .order_by(WorkspaceInvitation.created_at.desc())).all()
            out = []
            for inv in rows:
                exp = _aware(inv.expires_at)
                if exp is not None and exp < now:
                    continue
                ws = s.get(Workspace, inv.workspace_id)
                if ws is None or ws.status != WORKSPACE_STATUS_ACTIVE:
                    continue
                d = self._inv_dict(inv)
                d["workspace_name"] = ws.name
                out.append(d)
            return out

    # -- sharing --------------------------------------------------------------

    def create_share(self, *, owner_user_id: int, workspace_id: int, resource_type: str,
                     resource_id: str, permission: str) -> int | None:
        """Create or re-activate a VIEW share of an owned resource into an ACTIVE workspace the owner is an active member of.
        Returns None when either condition no longer holds (checked in the same transaction as the write)."""
        with self._sf() as s:
            ws = s.get(Workspace, workspace_id, with_for_update=True)
            if ws is None or ws.status != WORKSPACE_STATUS_ACTIVE:
                return None
            member = s.scalar(select(WorkspaceMembership.id).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == owner_user_id,
                WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE))
            if member is None:
                return None
            existing = s.scalar(select(ShareGrant).where(
                ShareGrant.owner_user_id == owner_user_id,
                ShareGrant.workspace_id == workspace_id,
                ShareGrant.resource_type == resource_type,
                ShareGrant.resource_id == resource_id))
            if existing is not None:
                if existing.status != SHARE_STATUS_ACTIVE:
                    existing.created_at = utcnow()      # a re-consent is a new grant moment
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
            if grant.status == SHARE_STATUS_ACTIVE:
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

    def _decorated(self, s, grants) -> list[dict]:
        """Share projections with the workspace name and a SAFE sharer label (display name, else a masked address). No content."""
        out = []
        for g in grants:
            d = self._share_dict(g)
            ws = s.get(Workspace, g.workspace_id)
            d["workspace_name"] = ws.name if ws else None
            owner = s.get(User, g.owner_user_id)
            d["shared_by"] = _label(owner.display_name if owner else None, owner.email if owner else None)
            out.append(d)
        return out

    def active_share_owner_for_member(self, *, user_id: int, resource_type: str,
                                      resource_id: str) -> int | None:
        """THE authorization read: return the owner id iff an ACTIVE share of this resource exists into an ACTIVE workspace in
        which BOTH the caller and the sharing owner are still ACTIVE members. Else None. Re-derived every call, so revocation,
        removal, archive and deletion take effect immediately and a stale or cached link cannot bypass it."""
        with self._sf() as s:
            owner_m = WorkspaceMembership.__table__.alias("owner_m")
            row = s.execute(
                select(ShareGrant.owner_user_id)
                .join(WorkspaceMembership, WorkspaceMembership.workspace_id == ShareGrant.workspace_id)
                .join(Workspace, Workspace.id == ShareGrant.workspace_id)
                .join(owner_m, (owner_m.c.workspace_id == ShareGrant.workspace_id)
                      & (owner_m.c.user_id == ShareGrant.owner_user_id))
                .where(
                    ShareGrant.resource_type == resource_type,
                    ShareGrant.resource_id == resource_id,
                    ShareGrant.status == SHARE_STATUS_ACTIVE,
                    Workspace.status == WORKSPACE_STATUS_ACTIVE,
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE,
                    owner_m.c.status == MEMBERSHIP_STATUS_ACTIVE,
                )
            ).first()
            return int(row[0]) if row else None

    def list_shares_by_owner(self, owner_user_id: int) -> list[dict]:
        with self._sf() as s:
            rows = s.scalars(select(ShareGrant).where(
                ShareGrant.owner_user_id == owner_user_id,
                ShareGrant.status == SHARE_STATUS_ACTIVE)
                .order_by(ShareGrant.created_at.desc(), ShareGrant.id.desc())).all()
            return self._decorated(s, rows)

    def list_shares_for_member(self, user_id: int) -> list[dict]:
        """Resources shared WITH the caller (active shares into their active workspaces, by owners who are still members)."""
        with self._sf() as s:
            owner_m = WorkspaceMembership.__table__.alias("owner_m")
            rows = s.scalars(
                select(ShareGrant)
                .join(WorkspaceMembership, WorkspaceMembership.workspace_id == ShareGrant.workspace_id)
                .join(Workspace, Workspace.id == ShareGrant.workspace_id)
                .join(owner_m, (owner_m.c.workspace_id == ShareGrant.workspace_id)
                      & (owner_m.c.user_id == ShareGrant.owner_user_id))
                .where(
                    ShareGrant.status == SHARE_STATUS_ACTIVE,
                    Workspace.status == WORKSPACE_STATUS_ACTIVE,
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.status == MEMBERSHIP_STATUS_ACTIVE,
                    owner_m.c.status == MEMBERSHIP_STATUS_ACTIVE,
                    ShareGrant.owner_user_id != user_id,
                )
                .order_by(ShareGrant.created_at.desc(), ShareGrant.id.desc())).all()
            return self._decorated(s, rows)

    def list_shares_for_workspace(self, workspace_id: int) -> list[dict]:
        """Active shares INTO one workspace: metadata only (type, id, sharer label, time)."""
        with self._sf() as s:
            rows = s.scalars(select(ShareGrant).where(
                ShareGrant.workspace_id == workspace_id,
                ShareGrant.status == SHARE_STATUS_ACTIVE)
                .order_by(ShareGrant.created_at.desc(), ShareGrant.id.desc())).all()
            return self._decorated(s, rows)

    def invalidate_shares_for_resource(self, *, owner_user_id: int, resource_type: str,
                                       resource_id: str) -> int:
        """Revoke all shares of a resource (call when the source resource is deleted)."""
        return self._bulk_revoke(
            ShareGrant.owner_user_id == owner_user_id, ShareGrant.resource_type == resource_type,
            ShareGrant.resource_id == resource_id)

    def revoke_member_shares_into_workspace(self, *, user_id: int, workspace_id: int) -> int:
        """Revoke a member's outbound shares into a workspace (call on leave/remove)."""
        return self._bulk_revoke(ShareGrant.owner_user_id == user_id, ShareGrant.workspace_id == workspace_id)

    def revoke_workspace_shares(self, workspace_id: int) -> int:
        """Revoke every share into a workspace (call on workspace deactivate/delete)."""
        return self._bulk_revoke(ShareGrant.workspace_id == workspace_id)

    @staticmethod
    def _revoke_where(s, *conditions) -> int:
        return int(s.execute(update(ShareGrant).where(
            ShareGrant.status == SHARE_STATUS_ACTIVE, *conditions)
            .values(status=SHARE_STATUS_REVOKED, revoked_at=utcnow())).rowcount or 0)

    def _bulk_revoke(self, *conditions) -> int:
        with self._sf() as s:
            n = self._revoke_where(s, *conditions)
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
