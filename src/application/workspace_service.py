"""Workspace / Teams application service (Capstone P6.5).

Enforces every membership + invitation invariant server-side: only a workspace owner may
invite/remove/transfer/deactivate; invitations are opaque, hashed, single-use and expiring;
the last owner can never orphan a workspace; a member may only accept an invitation issued
to their own verified email; leaving/removal revokes that member's outbound shares. Every
mutation is audited with safe metadata only (never candidate content, tokens or PII beyond
the allow-listed context). No candidate-private data is ever exposed to other members.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from src.application.errors import ConflictError, ValidationError
from src.mail.sender import EmailMessage
from src.persistence import (
    INVITATION_STATUS_ACCEPTED,
    INVITATION_STATUS_DECLINED,
    INVITATION_STATUS_EXPIRED,
    INVITATION_STATUS_PENDING,
    MEMBERSHIP_STATUS_LEFT,
    MEMBERSHIP_STATUS_REMOVED,
    WORKSPACE_ROLE_MEMBER,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_DEACTIVATED,
    utcnow,
)

__all__ = ["WorkspaceService", "WorkspaceNotFoundError", "WorkspacePermissionError"]

INVITATION_TTL_HOURS = 72
_MAX_NAME = 120


class WorkspaceNotFoundError(Exception):
    """Not found OR not visible to the caller (indistinguishable, by design)."""


class WorkspacePermissionError(Exception):
    """The caller is authenticated but not authorized for this workspace action."""


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class WorkspaceService:
    def __init__(self, *, workspaces, accounts, audit=None, email=None,
                 app_base_url: str = "https://app.ask4mo.local") -> None:
        self._ws = workspaces
        self._accounts = accounts
        self._audit = audit
        self._email = email
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
            pass

    def _require_active_workspace(self, workspace_id: int) -> dict:
        ws = self._ws.get_workspace(workspace_id)
        if ws is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        return ws

    def _require_member(self, workspace_id: int, user_id: int) -> str:
        role = self._ws.member_role(workspace_id, user_id)
        if role is None:
            # Membership is the visibility boundary — a non-member gets not-found, not 403,
            # so workspace existence/membership can't be probed.
            raise WorkspaceNotFoundError("Workspace not found.")
        return role

    def _require_owner(self, workspace_id: int, user_id: int) -> None:
        if self._require_member(workspace_id, user_id) != WORKSPACE_ROLE_OWNER:
            raise WorkspacePermissionError("Only a workspace owner may perform this action.")

    # -- workspaces -----------------------------------------------------------

    def create_workspace(self, *, user_id: int, name: str) -> dict:
        clean = (name or "").strip()
        if not clean:
            raise ValidationError("A workspace needs a name.")
        if len(clean) > _MAX_NAME:
            raise ValidationError("Workspace name is too long.")
        ws_id = self._ws.create_workspace(owner_user_id=user_id, name=clean[:_MAX_NAME])
        self._audit_event("workspace.created", user_id, ws_id, role=WORKSPACE_ROLE_OWNER)
        return self._ws.get_workspace(ws_id)

    def list_my_workspaces(self, *, user_id: int, email: str | None) -> dict:
        workspaces = self._ws.list_workspaces_for_user(user_id)
        invited = self._ws.list_pending_invitations_for_email(email) if email else []
        # Strip the raw email from the invited projection (the caller already owns it).
        for inv in invited:
            inv.pop("email", None)
        return {"workspaces": workspaces, "invited": invited}

    def get_workspace_detail(self, *, user_id: int, workspace_id: int) -> dict:
        role = self._require_member(workspace_id, user_id)
        ws = self._require_active_workspace(workspace_id)
        ws["my_role"] = role
        ws["members"] = self._ws.list_members(workspace_id)
        if role == WORKSPACE_ROLE_OWNER:
            ws["pending_invitations"] = self._ws.list_invitations_for_workspace(workspace_id)
        return ws

    def deactivate_workspace(self, *, user_id: int, workspace_id: int) -> dict:
        self._require_owner(workspace_id, user_id)
        self._ws.set_workspace_status(workspace_id, WORKSPACE_STATUS_DEACTIVATED)
        revoked = self._ws.revoke_workspace_shares(workspace_id)
        self._audit_event("workspace.deactivated", user_id, workspace_id, shares_revoked=revoked)
        return self._ws.get_workspace(workspace_id)

    def transfer_ownership(self, *, user_id: int, workspace_id: int, new_owner_user_id: int) -> dict:
        self._require_owner(workspace_id, user_id)
        if not self._ws.transfer_ownership(workspace_id=workspace_id, new_owner_user_id=new_owner_user_id):
            raise ValidationError("The new owner must be an active member of this workspace.")
        self._audit_event("workspace.ownership_transferred", user_id, workspace_id,
                         new_owner=str(new_owner_user_id))
        return self._ws.get_workspace(workspace_id)

    # -- invitations ----------------------------------------------------------

    def invite(self, *, user_id: int, workspace_id: int, email: str,
               role: str = WORKSPACE_ROLE_MEMBER) -> dict:
        self._require_owner(workspace_id, user_id)
        ws = self._require_active_workspace(workspace_id)
        if ws["status"] != WORKSPACE_STATUS_ACTIVE:
            raise ConflictError("This workspace is not active.")
        clean_email = (email or "").strip().lower()
        if "@" not in clean_email or len(clean_email) > 320:
            raise ValidationError("A valid email address is required.")
        if role not in (WORKSPACE_ROLE_OWNER, WORKSPACE_ROLE_MEMBER):
            raise ValidationError("Unknown workspace role.")
        raw = secrets.token_urlsafe(32)
        expires = utcnow() + timedelta(hours=INVITATION_TTL_HOURS)
        inv_id = self._ws.create_invitation(
            workspace_id=workspace_id, inviter_user_id=user_id, email=clean_email,
            token_hash=_hash_token(raw), role=role, expires_at=expires)
        self._send_invitation_email(clean_email, ws["name"], raw)
        self._audit_event("workspace.invite_created", user_id, workspace_id, role=role)
        return {"invitation_id": inv_id, "status": INVITATION_STATUS_PENDING,
                "expires_at": expires.isoformat()}

    def _send_invitation_email(self, email: str, workspace_name: str, raw_token: str) -> None:
        if self._email is None:
            return
        link = f"{self._base}/workspaces/accept?token={quote(raw_token)}"
        body = (f"You have been invited to join the workspace '{workspace_name}' on Ask4Mo.\n\n"
                f"Accept the invitation: {link}\n\n"
                "This invitation is single-use and expires soon. If you did not expect it, "
                "ignore this email — nothing is shared with a workspace unless you choose to "
                "share it.")
        try:
            self._email.send(EmailMessage(to=email, subject="You're invited to an Ask4Mo workspace",
                                          body=body, category="invitation"))
        except Exception:  # noqa: BLE001 - email best-effort; the invite row still exists
            pass

    def _resolve_valid_invitation(self, token: str) -> dict:
        inv = self._ws.get_invitation_by_token_hash(_hash_token((token or "").strip()))
        if inv is None:
            raise WorkspaceNotFoundError("Invitation not found.")
        if inv["status"] != INVITATION_STATUS_PENDING:
            raise ConflictError("This invitation has already been used or is no longer valid.")
        expires = inv.get("expires_at")
        if expires and _parse(expires) < utcnow():
            self._ws.set_invitation_status(invitation_id=inv["id"], status=INVITATION_STATUS_EXPIRED)
            raise ConflictError("This invitation has expired.")
        return inv

    def accept_invitation(self, *, user_id: int, token: str) -> dict:
        inv = self._resolve_valid_invitation(token)
        # Foreign-acceptance guard: the accepting account's own email must match the invite.
        account = self._accounts.get_account(user_id)
        caller_email = (getattr(account, "email", None) or "").strip().lower()
        if not caller_email or caller_email != inv["email"].strip().lower():
            raise WorkspacePermissionError("This invitation was issued to a different email.")
        self._ws.upsert_membership(workspace_id=inv["workspace_id"], user_id=user_id, role=inv["role"])
        self._ws.set_invitation_status(invitation_id=inv["id"],
                                       status=INVITATION_STATUS_ACCEPTED, accepted_user_id=user_id)
        self._audit_event("workspace.invite_accepted", user_id, inv["workspace_id"], role=inv["role"])
        return self._ws.get_workspace(inv["workspace_id"])

    def decline_invitation(self, *, user_id: int, token: str) -> dict:
        inv = self._resolve_valid_invitation(token)
        account = self._accounts.get_account(user_id)
        caller_email = (getattr(account, "email", None) or "").strip().lower()
        if caller_email != inv["email"].strip().lower():
            raise WorkspacePermissionError("This invitation was issued to a different email.")
        self._ws.set_invitation_status(invitation_id=inv["id"], status=INVITATION_STATUS_DECLINED)
        self._audit_event("workspace.invite_declined", user_id, inv["workspace_id"])
        return {"status": INVITATION_STATUS_DECLINED}

    # -- membership changes ---------------------------------------------------

    def leave(self, *, user_id: int, workspace_id: int) -> dict:
        role = self._require_member(workspace_id, user_id)
        if role == WORKSPACE_ROLE_OWNER and self._ws.count_active_owners(workspace_id) <= 1:
            raise ConflictError("Transfer ownership before leaving — a workspace needs an owner.")
        self._ws.set_membership_status(workspace_id=workspace_id, user_id=user_id,
                                       status=MEMBERSHIP_STATUS_LEFT)
        revoked = self._ws.revoke_member_shares_into_workspace(user_id=user_id, workspace_id=workspace_id)
        self._audit_event("workspace.member_left", user_id, workspace_id, shares_revoked=revoked)
        return {"status": MEMBERSHIP_STATUS_LEFT}

    def remove_member(self, *, user_id: int, workspace_id: int, target_user_id: int) -> dict:
        self._require_owner(workspace_id, user_id)
        target_role = self._ws.member_role(workspace_id, target_user_id)
        if target_role is None:
            raise WorkspaceNotFoundError("That member is not in this workspace.")
        if target_role == WORKSPACE_ROLE_OWNER and self._ws.count_active_owners(workspace_id) <= 1:
            raise ConflictError("Cannot remove the last owner — transfer ownership first.")
        self._ws.set_membership_status(workspace_id=workspace_id, user_id=target_user_id,
                                       status=MEMBERSHIP_STATUS_REMOVED)
        revoked = self._ws.revoke_member_shares_into_workspace(
            user_id=target_user_id, workspace_id=workspace_id)
        self._audit_event("workspace.member_removed", user_id, workspace_id,
                         target=str(target_user_id), shares_revoked=revoked)
        return {"status": MEMBERSHIP_STATUS_REMOVED}


def _parse(iso: str):
    from datetime import datetime
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
