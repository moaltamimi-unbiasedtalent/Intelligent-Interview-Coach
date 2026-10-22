"""Workspace / Teams application service (Capstone P6.5, completed by 04B).

Enforces every membership + invitation invariant server-side. Roles live on the membership:

* ``workspace_owner``  - everything: rename, archive/restore/delete, invite (member or admin), change roles, remove anyone,
  transfer ownership, leave only after transferring (the last owner can never be removed or leave).
* ``workspace_admin``  - rename, invite PLAIN MEMBERS, revoke invitations, remove PLAIN MEMBERS. Never archives, deletes,
  transfers, changes a role, invites an admin, or removes an admin or the owner.
* ``workspace_member`` - read the workspace, list members (display labels only), share their own items, leave.

Invitations are opaque, hashed at rest, single-use, expiring, bound to the invited address, and may only be answered by an
account whose address is VERIFIED and equal to the invited one; the answer is one atomic, race-safe claim. Ending a membership
revokes that member's outbound shares in the same transaction. Every mutation is audited with safe metadata only (ids, roles
and counts; never candidate content, tokens or addresses). No candidate-private data is ever exposed to other members and a
workspace role never grants access to anything that was not explicitly shared.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from src.application.errors import ConflictError, ValidationError
from src.mail.sender import EmailMessage
from src.mail.service import EmailService
from src.mail.templates import render as render_mail
from src.persistence import (
    INVITATION_STATUS_DECLINED,
    INVITATION_STATUS_PENDING,
    MEMBERSHIP_STATUS_LEFT,
    MEMBERSHIP_STATUS_REMOVED,
    WORKSPACE_ROLE_ADMIN,
    WORKSPACE_ROLE_MEMBER,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    utcnow,
)
from src.workspace_repository import MAX_ACTIVE_MEMBERS, MAX_PENDING_INVITATIONS, mask_email

__all__ = ["WorkspaceService", "WorkspaceNotFoundError", "WorkspacePermissionError",
           "INVITATION_TTL_HOURS", "MAX_OWNED_WORKSPACES"]

log = logging.getLogger(__name__)

INVITATION_TTL_HOURS = 72
MAX_OWNED_WORKSPACES = 20
_MAX_NAME = 120
_EMAIL_RE = re.compile(r"^[^@\s<>,;\"'\\]+@[^@\s<>,;\"'\\]+\.[^@\s<>,;\"'\\]+$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_INVITABLE_ROLES = (WORKSPACE_ROLE_ADMIN, WORKSPACE_ROLE_MEMBER)


class WorkspaceNotFoundError(Exception):
    """Not found OR not visible to the caller (indistinguishable, by design)."""


class WorkspacePermissionError(Exception):
    """The caller is authenticated but not authorized for this workspace action."""


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clean_name(name: str | None) -> str:
    clean = _CONTROL.sub(" ", name or "").strip()
    clean = re.sub(r"\s+", " ", clean)
    if not clean:
        raise ValidationError("A workspace needs a name.")
    if len(clean) > _MAX_NAME:
        raise ValidationError("Workspace name is too long.")
    return clean


def _capabilities(role: str, active: bool) -> dict:
    """What THIS caller may do, derived from the role (the UI only reflects it; every route re-checks)."""
    owner = role == WORKSPACE_ROLE_OWNER
    admin = role == WORKSPACE_ROLE_ADMIN
    manage = owner or admin
    return {
        "can_rename": manage and active,
        "can_invite": manage and active,
        "can_invite_admin": owner and active,
        "can_remove_members": manage,
        "can_change_roles": owner and active,
        "can_transfer": owner,
        "can_archive": owner and active,
        "can_restore": owner and not active,
        "can_delete": owner,
        "can_leave": not owner,
        "can_share": active,
    }


class WorkspaceService:
    def __init__(self, *, workspaces, accounts, audit=None, email=None,
                 app_base_url: str = "https://app.ask4mo.local") -> None:
        self._ws = workspaces
        self._accounts = accounts
        self._audit = audit
        # One guarded submission boundary (W12.4C): a bounded result, an adapter failure never becomes a 500 or a false success.
        # No attempt log is attached: the attempt-type CHECK of ``email_attempts`` (migration 0027) does not list this message and
        # widening it would need a migration that this package does not otherwise need.
        self._mail = None if email is None else (email if isinstance(email, EmailService) else EmailService(email))
        self._base = app_base_url.rstrip("/")

    # -- audit helper ---------------------------------------------------------

    def _audit_event(self, event_type: str, actor_user_id: int, workspace_id: int, **context) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=event_type, actor_user_id=actor_user_id,
                               target_type="workspace", target_id=str(workspace_id),
                               context={k: v for k, v in context.items() if v is not None})
        except Exception:  # noqa: BLE001 - audit is best-effort, never breaks the action
            log.warning("workspace audit write failed event=%s", event_type)

    def _require_workspace(self, workspace_id: int) -> dict:
        ws = self._ws.get_workspace(workspace_id)
        if ws is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        return ws

    def _require_member(self, workspace_id: int, user_id: int) -> str:
        role = self._ws.member_role(workspace_id, user_id)
        if role is None:
            # Membership is the visibility boundary: a non-member (never joined, invited-not-accepted, left, removed) gets
            # not-found, not 403, so workspace existence/membership can't be probed.
            raise WorkspaceNotFoundError("Workspace not found.")
        return role

    def _require_owner(self, workspace_id: int, user_id: int) -> None:
        if self._require_member(workspace_id, user_id) != WORKSPACE_ROLE_OWNER:
            raise WorkspacePermissionError("Only a workspace owner may perform this action.")

    def _require_manager(self, workspace_id: int, user_id: int) -> str:
        role = self._require_member(workspace_id, user_id)
        if role not in (WORKSPACE_ROLE_OWNER, WORKSPACE_ROLE_ADMIN):
            raise WorkspacePermissionError("Only a workspace owner or admin may perform this action.")
        return role

    @staticmethod
    def _require_active(ws: dict) -> None:
        if ws["status"] != WORKSPACE_STATUS_ACTIVE:
            raise ConflictError("This workspace is archived. Restore it to continue.")

    # -- workspaces -----------------------------------------------------------

    def create_workspace(self, *, user_id: int, name: str) -> dict:
        clean = _clean_name(name)
        owned = sum(1 for w in self._ws.list_workspaces_for_user(user_id) if w.get("my_role") == WORKSPACE_ROLE_OWNER)
        if owned >= MAX_OWNED_WORKSPACES:
            raise ConflictError("You have reached the maximum number of workspaces you can own.")
        ws_id = self._ws.create_workspace(owner_user_id=user_id, name=clean)
        self._audit_event("workspace.created", user_id, ws_id, role=WORKSPACE_ROLE_OWNER)
        return self._ws.get_workspace(ws_id)

    def list_my_workspaces(self, *, user_id: int, email: str | None, email_verified: bool = False) -> dict:
        workspaces = self._ws.list_workspaces_for_user(user_id)
        for w in workspaces:
            w["capabilities"] = _capabilities(w["my_role"], w["status"] == WORKSPACE_STATUS_ACTIVE)
        # Invitations are shown only to an account that has PROVEN the address (an unverified registrant of someone else's
        # address must not even learn that an invitation exists).
        invited = self._ws.list_pending_invitations_for_email(email) if (email and email_verified) else []
        for inv in invited:
            inv.pop("email", None)
            inv.pop("inviter_user_id", None)
            inv.pop("accepted_user_id", None)
        return {"workspaces": workspaces, "invited": invited}

    def _shape_members(self, rows: list[dict], *, viewer_id: int, viewer_role: str) -> list[dict]:
        sees_email = viewer_role in (WORKSPACE_ROLE_OWNER, WORKSPACE_ROLE_ADMIN)
        out = []
        for m in rows:
            name = (m.get("display_name") or "").strip()
            label = name[:80] if name else mask_email(m.get("email"))
            item = {"user_id": m["user_id"], "role": m["role"], "status": m["status"],
                    "joined_at": m["joined_at"], "label": label, "is_me": m["user_id"] == viewer_id}
            if sees_email or m["user_id"] == viewer_id:
                item["email"] = m.get("email")
            out.append(item)
        return out

    def get_workspace_detail(self, *, user_id: int, workspace_id: int) -> dict:
        role = self._require_member(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        active = ws["status"] == WORKSPACE_STATUS_ACTIVE
        ws["my_role"] = role
        ws["capabilities"] = _capabilities(role, active)
        ws["members"] = self._shape_members(self._ws.list_members(workspace_id), viewer_id=user_id, viewer_role=role)
        if role in (WORKSPACE_ROLE_OWNER, WORKSPACE_ROLE_ADMIN):
            ws["pending_invitations"] = [
                {k: v for k, v in inv.items() if k not in ("accepted_user_id",)}
                for inv in self._ws.list_invitations_for_workspace(workspace_id)]
        ws["limits"] = {"max_members": MAX_ACTIVE_MEMBERS, "max_pending_invitations": MAX_PENDING_INVITATIONS,
                        "invitation_ttl_hours": INVITATION_TTL_HOURS}
        return ws

    def rename_workspace(self, *, user_id: int, workspace_id: int, name: str) -> dict:
        self._require_manager(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        self._require_active(ws)
        clean = _clean_name(name)
        self._ws.rename_workspace(workspace_id, clean)
        self._audit_event("workspace.renamed", user_id, workspace_id)
        return self._ws.get_workspace(workspace_id)

    def archive_workspace(self, *, user_id: int, workspace_id: int) -> dict:
        """Archive: invites, renames and new shares stop; every grant into it is revoked atomically (and stays revoked on
        restore); members keep read access to the workspace page itself and can still leave."""
        self._require_owner(workspace_id, user_id)
        revoked = self._ws.archive_workspace(workspace_id)
        if revoked is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        self._audit_event("workspace.archived", user_id, workspace_id, shares_revoked=revoked)
        return self._ws.get_workspace(workspace_id)

    # The pre-04B name stays as an alias (existing callers and the legacy route).
    deactivate_workspace = archive_workspace

    def restore_workspace(self, *, user_id: int, workspace_id: int) -> dict:
        self._require_owner(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        if ws["status"] != WORKSPACE_STATUS_ACTIVE:
            self._ws.restore_workspace(workspace_id)
            self._audit_event("workspace.restored", user_id, workspace_id)
        return self._ws.get_workspace(workspace_id)

    def delete_workspace(self, *, user_id: int, workspace_id: int, confirm_name: str | None = None) -> dict:
        """Permanently delete. Consequences (all in one transaction): every membership, pending invitation and share grant row
        is removed, so every member loses access at once; the workspace's own plan assignment rows go with it. Nothing a member
        owns is deleted (stories, reports and documents belong to their owners and were only ever referenced by a grant).
        Requires the owner to type the exact workspace name."""
        self._require_owner(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        if (confirm_name or "").strip() != ws["name"]:
            raise ValidationError("Type the exact workspace name to confirm deletion.")
        counts = self._ws.delete_workspace(workspace_id)
        if counts is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        self._audit_event("workspace.deleted", user_id, workspace_id, members_removed=counts["memberships"],
                         shares_revoked=counts["shares"], invitations_removed=counts["invitations"])
        return {"status": "deleted", "members_removed": counts["memberships"], "shares_removed": counts["shares"],
                "invitations_removed": counts["invitations"]}

    def transfer_ownership(self, *, user_id: int, workspace_id: int, new_owner_user_id: int,
                           confirm_name: str | None = None) -> dict:
        """Owner hands ownership to a DIFFERENT active member in one atomic step; the former owner becomes a plain member.
        The owner must type the exact workspace name (an irreversible act for the sender). OD-WS-TRANSFER (acceptance
        procedure, cooling-off, constraints) is still awaiting the owner; this is the safe, minimal default."""
        self._require_owner(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        if (confirm_name or "").strip() != ws["name"]:
            raise ValidationError("Type the exact workspace name to confirm the ownership transfer.")
        if new_owner_user_id == user_id:
            raise ValidationError("You already own this workspace.")
        if not self._ws.transfer_ownership(workspace_id=workspace_id, new_owner_user_id=new_owner_user_id,
                                           expected_owner_user_id=user_id):
            raise ValidationError("The new owner must be another active member of this workspace.")
        self._audit_event("workspace.ownership_transferred", user_id, workspace_id,
                         new_owner=str(new_owner_user_id))
        return self._ws.get_workspace(workspace_id)

    # -- invitations ----------------------------------------------------------

    def invite(self, *, user_id: int, workspace_id: int, email: str,
               role: str = WORKSPACE_ROLE_MEMBER) -> dict:
        actor_role = self._require_manager(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        self._require_active(ws)
        clean_email = (email or "").strip().lower()
        if len(clean_email) > 320 or not _EMAIL_RE.match(clean_email):
            raise ValidationError("A valid email address is required.")
        if role not in _INVITABLE_ROLES:
            raise ValidationError("Unknown workspace role.")
        if role == WORKSPACE_ROLE_ADMIN and actor_role != WORKSPACE_ROLE_OWNER:
            raise WorkspacePermissionError("Only a workspace owner may invite an admin.")
        raw = secrets.token_urlsafe(32)
        expires = utcnow() + timedelta(hours=INVITATION_TTL_HOURS)
        outcome, inv_id = self._ws.issue_invitation(
            workspace_id=workspace_id, inviter_user_id=user_id, email=clean_email,
            token_hash=_hash_token(raw), role=role, expires_at=expires)
        if outcome == "already_member":
            raise ConflictError("That person is already a member of this workspace.")
        if outcome == "too_many_pending":
            raise ConflictError("Too many pending invitations. Revoke some before inviting more people.")
        if outcome == "member_limit":
            raise ConflictError("This workspace has reached its member limit.")
        delivery = self._send_invitation_email(clean_email, raw)
        self._audit_event("workspace.invite_created", user_id, workspace_id, role=role,
                         email_submitted=delivery == "submitted")
        return {"invitation_id": inv_id, "status": INVITATION_STATUS_PENDING,
                "expires_at": expires.isoformat(), "email_delivery": delivery}

    def _send_invitation_email(self, email: str, raw_token: str) -> str:
        """``submitted`` when the guarded EmailService reports the provider accepted (or captured) it, ``not_submitted`` otherwise.
        Never ``delivered``: acceptance by a provider is not delivery. The invitation row exists either way (revoke or re-invite)."""
        if self._mail is None:
            return "not_submitted"
        locale = None
        try:
            found = self._accounts.find_by_email(email)
            locale = getattr(found, "interface_locale", None) if found else None
        except Exception:  # noqa: BLE001 - a lookup failure only costs the localisation
            locale = None
        link = f"{self._base}/workspaces/accept?token={quote(raw_token)}"
        rendered = render_mail("workspace_invitation", locale=locale, link=link,
                               expires_in_seconds=INVITATION_TTL_HOURS * 3600)
        try:
            result = self._mail.deliver(
                EmailMessage(to=email, subject=rendered.subject, body=rendered.body, category="workspace_invitation"),
                locale=rendered.locale)
        except Exception:  # noqa: BLE001
            return "not_submitted"
        return "submitted" if getattr(result, "accepted", False) else "not_submitted"

    def revoke_invitation(self, *, user_id: int, workspace_id: int, invitation_id: int) -> dict:
        actor_role = self._require_manager(workspace_id, user_id)
        inv = self._ws.get_invitation(invitation_id)
        if inv is None or inv["workspace_id"] != workspace_id:
            raise WorkspaceNotFoundError("Invitation not found.")
        if inv["role"] == WORKSPACE_ROLE_ADMIN and actor_role != WORKSPACE_ROLE_OWNER:
            raise WorkspacePermissionError("Only a workspace owner may revoke an admin invitation.")
        if not self._ws.revoke_invitation(workspace_id=workspace_id, invitation_id=invitation_id):
            raise ConflictError("This invitation is no longer pending.")
        self._audit_event("workspace.invite_revoked", user_id, workspace_id, role=inv["role"])
        return {"status": "revoked"}

    # -- answering an invitation ---------------------------------------------

    def _verified_email(self, user_id: int) -> str:
        account = self._accounts.get_account(user_id)
        email = (getattr(account, "email", None) or "").strip().lower()
        if not email or getattr(account, "email_verified", False) is not True:
            raise WorkspacePermissionError("Verify your email address before responding to a workspace invitation.")
        return email

    def _decide(self, *, user_id: int, inv: dict | None, accept: bool, hide_mismatch: bool) -> dict:
        if inv is None:
            raise WorkspaceNotFoundError("Invitation not found.")
        email = self._verified_email(user_id)
        outcome, info = self._ws.decide_invitation(invitation_id=inv["id"], user_id=user_id, email=email, accept=accept)
        if outcome == "ok":
            event = "workspace.invite_accepted" if accept else "workspace.invite_declined"
            self._audit_event(event, user_id, info["workspace_id"], role=info["role"] if accept else None)
            return info
        if outcome == "not_found" or (outcome == "wrong_email" and hide_mismatch):
            raise WorkspaceNotFoundError("Invitation not found.")
        if outcome == "wrong_email":
            raise WorkspacePermissionError("This invitation was issued to a different email.")
        if outcome == "expired":
            raise ConflictError("This invitation has expired.")
        if outcome == "workspace_inactive":
            raise ConflictError("This workspace is archived or no longer exists.")
        if outcome == "member_limit":
            raise ConflictError("This workspace has reached its member limit.")
        raise ConflictError("This invitation has already been used or is no longer valid.")

    def _by_token(self, token: str) -> dict | None:
        return self._ws.get_invitation_by_token_hash(_hash_token((token or "").strip()))

    def accept_invitation(self, *, user_id: int, token: str) -> dict:
        info = self._decide(user_id=user_id, inv=self._by_token(token), accept=True, hide_mismatch=False)
        return self._ws.get_workspace(info["workspace_id"])

    def decline_invitation(self, *, user_id: int, token: str) -> dict:
        self._decide(user_id=user_id, inv=self._by_token(token), accept=False, hide_mismatch=False)
        return {"status": INVITATION_STATUS_DECLINED}

    def accept_invitation_by_id(self, *, user_id: int, invitation_id: int) -> dict:
        info = self._decide(user_id=user_id, inv=self._ws.get_invitation(invitation_id), accept=True, hide_mismatch=True)
        return self._ws.get_workspace(info["workspace_id"])

    def decline_invitation_by_id(self, *, user_id: int, invitation_id: int) -> dict:
        self._decide(user_id=user_id, inv=self._ws.get_invitation(invitation_id), accept=False, hide_mismatch=True)
        return {"status": INVITATION_STATUS_DECLINED}

    def preview_invitation(self, *, user_id: int, token: str) -> dict:
        """What the invitation page may show BEFORE the person decides: the workspace name, the offered role and the expiry, and
        only to the verified account the invitation was issued to (anyone else gets the same errors as accepting)."""
        inv = self._by_token(token)
        if inv is None:
            raise WorkspaceNotFoundError("Invitation not found.")
        email = self._verified_email(user_id)
        if inv["email"].strip().lower() != email:
            raise WorkspacePermissionError("This invitation was issued to a different email.")
        if inv["status"] != INVITATION_STATUS_PENDING:
            raise ConflictError("This invitation has already been used or is no longer valid.")
        expires = inv.get("expires_at")
        if expires and _parse(expires) < utcnow():
            raise ConflictError("This invitation has expired.")
        ws = self._ws.get_workspace(inv["workspace_id"])
        if ws is None or ws["status"] != WORKSPACE_STATUS_ACTIVE:
            raise ConflictError("This workspace is archived or no longer exists.")
        return {"invitation_id": inv["id"], "workspace_name": ws["name"], "role": inv["role"], "expires_at": expires}

    # -- membership changes ---------------------------------------------------

    def leave(self, *, user_id: int, workspace_id: int) -> dict:
        self._require_member(workspace_id, user_id)
        outcome, revoked = self._ws.end_membership(
            workspace_id=workspace_id, user_id=user_id, status=MEMBERSHIP_STATUS_LEFT)
        if outcome == "last_owner":
            raise ConflictError("Transfer ownership before leaving. A workspace needs an owner.")
        if outcome != "ok":
            raise WorkspaceNotFoundError("Workspace not found.")
        self._audit_event("workspace.member_left", user_id, workspace_id, shares_revoked=revoked)
        return {"status": MEMBERSHIP_STATUS_LEFT, "shares_revoked": revoked}

    def remove_member(self, *, user_id: int, workspace_id: int, target_user_id: int) -> dict:
        actor_role = self._require_manager(workspace_id, user_id)
        target_role = self._ws.member_role(workspace_id, target_user_id)
        if target_role is None:
            raise WorkspaceNotFoundError("That member is not in this workspace.")
        if target_user_id == user_id:
            raise ValidationError("Use Leave to remove yourself.")
        if target_role == WORKSPACE_ROLE_OWNER:
            raise ConflictError("The owner cannot be removed. Transfer ownership first.")
        if target_role == WORKSPACE_ROLE_ADMIN and actor_role != WORKSPACE_ROLE_OWNER:
            raise WorkspacePermissionError("Only a workspace owner may remove an admin.")
        outcome, revoked = self._ws.end_membership(
            workspace_id=workspace_id, user_id=target_user_id, status=MEMBERSHIP_STATUS_REMOVED)
        if outcome == "last_owner":
            raise ConflictError("Cannot remove the last owner. Transfer ownership first.")
        if outcome != "ok":
            raise WorkspaceNotFoundError("That member is not in this workspace.")
        self._audit_event("workspace.member_removed", user_id, workspace_id,
                         target=str(target_user_id), target_role=target_role, shares_revoked=revoked)
        return {"status": MEMBERSHIP_STATUS_REMOVED, "shares_revoked": revoked}

    def change_member_role(self, *, user_id: int, workspace_id: int, target_user_id: int, role: str) -> dict:
        """Owner promotes a member to admin or demotes an admin to member. The owner role never moves here (transfer only)."""
        self._require_owner(workspace_id, user_id)
        ws = self._require_workspace(workspace_id)
        self._require_active(ws)
        if role not in _INVITABLE_ROLES:
            raise ValidationError("Unknown workspace role.")
        if target_user_id == user_id:
            raise ValidationError("You cannot change your own role.")
        outcome, previous = self._ws.change_member_role(workspace_id=workspace_id, user_id=target_user_id, role=role)
        if outcome == "not_member":
            raise WorkspaceNotFoundError("That member is not in this workspace.")
        if outcome == "owner_role":
            raise ConflictError("The owner role changes only through ownership transfer.")
        if outcome == "ok":
            self._audit_event("workspace.member_role_changed", user_id, workspace_id,
                             target=str(target_user_id), before=previous, after=role)
        return {"user_id": target_user_id, "role": role, "changed": outcome == "ok"}


def _parse(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
