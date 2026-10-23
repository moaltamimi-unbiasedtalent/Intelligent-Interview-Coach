"""Two-step workspace ownership transfer (04B completion, REQ-OWN-07).

OD-WS-TRANSFER is still an OWNER DECISION: this implements the owner's PROVISIONAL RECOMMENDED DEFAULT ("explicit workspace ownership transfer requiring
appropriate authorization, verified acceptance and immutable audit evidence"). It is not an approval of those rules.

Flow
1. PROPOSE (the current owner): the typed workspace name, a fresh password step-up on the owner's session (enforced at the route; reuses the existing
   ``StepUpService``), ONE existing ACTIVE member whose account is active with a VERIFIED email, and the role the owner keeps (admin or member).
   This creates a pending transfer (one open transfer per workspace, 7 days) and sends a generic notice to the recipient's verified address.
2. ACCEPT (the recipient): signed in with the bound, verified account AND presenting the one-time token from that notice. The claim, the role swap and
   the audit row are one transaction: exactly one owner before and after, and concurrent accept / cancel / expire yields exactly one outcome.
   DECLINE (recipient) and CANCEL (proposer) end it. Expiry is enforced on the server at every read and every claim.
3. Leaving, removal or deactivation of either party, and the deletion of either account or of the workspace, cancels the transfer in the SAME transaction
   as that change; the successor logic of account deletion is unchanged, so a workspace is never orphaned.
4. Every state change writes ONE append-only audit row (metadata only; see ``src/ownership_transfer_repository.py``).

The mail never names the workspace or the proposer (both are user-authored text and could carry a phishing message); the recipient sees the workspace name only
after signing in with the bound address.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from urllib.parse import quote

from src.application.errors import ConflictError, ValidationError
from src.application.workspace_service import WorkspaceNotFoundError, WorkspacePermissionError
from src.mail.sender import EmailMessage
from src.mail.service import EmailService
from src.mail.templates import render as render_mail
from src.ownership_transfer_repository import FORMER_OWNER_ROLES, hash_token, transfer_email_hash
from src.persistence import (
    WORKSPACE_ROLE_MEMBER,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_STATUS_ACTIVE,
    utcnow,
)
from src.workspace_repository import mask_email

__all__ = ["OwnershipTransferService", "TRANSFER_TTL_DAYS"]

log = logging.getLogger(__name__)

TRANSFER_TTL_DAYS = 7


class OwnershipTransferService:
    def __init__(self, *, workspaces, transfers, accounts, email=None, app_base_url: str = "https://app.ask4mo.local") -> None:
        self._ws = workspaces
        self._tr = transfers
        self._accounts = accounts
        # The guarded submission boundary (a bounded result; an adapter failure never becomes a 500 or a false success).
        self._mail = None if email is None else (email if isinstance(email, EmailService) else EmailService(email))
        self._base = app_base_url.rstrip("/")

    # -- helpers ----------------------------------------------------------------------------------------------------

    def _require_member(self, workspace_id: int, user_id: int) -> str:
        role = self._ws.member_role(workspace_id, user_id)
        if role is None:
            raise WorkspaceNotFoundError("Workspace not found.")      # not a member: existence is never revealed
        return role

    def _label(self, user_id: int) -> str:
        account = self._accounts.get_account(user_id)
        if account is None:
            return ""
        name = (getattr(account, "display_name", None) or "").strip()
        return name[:80] if name else mask_email(getattr(account, "email", None))

    def _verified_email(self, user_id: int) -> str:
        account = self._accounts.get_account(user_id)
        email = (getattr(account, "email", None) or "").strip().lower()
        if (account is None or getattr(account, "status", "active") != "active" or not email
                or getattr(account, "email_verified", False) is not True):
            raise WorkspacePermissionError("Verify your email address before responding to an ownership transfer.")
        return email

    def _shape(self, row: dict, viewer_id: int, *, with_workspace: bool = False) -> dict:
        is_proposer = row["proposer_user_id"] == viewer_id
        other = row["recipient_user_id"] if is_proposer else row["proposer_user_id"]
        out = {"id": row["id"], "workspace_id": row["workspace_id"], "status": row["status"],
               "viewer_role": "proposer" if is_proposer else "recipient", "former_owner_role": row["former_owner_role"],
               "expires_at": row["expires_at"], "created_at": row["created_at"], "counterpart_label": self._label(other)}
        if with_workspace:
            ws = self._ws.get_workspace(row["workspace_id"])
            out["workspace_name"] = ws["name"] if ws else ""
        return out

    # -- propose ----------------------------------------------------------------------------------------------------

    def propose(self, *, user_id: int, workspace_id: int, new_owner_user_id: int, confirm_name: str | None,
                former_owner_role: str = WORKSPACE_ROLE_MEMBER) -> dict:
        role = self._require_member(workspace_id, user_id)
        if role != WORKSPACE_ROLE_OWNER:
            raise WorkspacePermissionError("Only the workspace owner may propose an ownership transfer.")
        ws = self._ws.get_workspace(workspace_id)
        if ws is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        if ws["status"] != WORKSPACE_STATUS_ACTIVE:
            raise ConflictError("This workspace is archived. Restore it to continue.")
        if (confirm_name or "").strip() != ws["name"]:
            raise ValidationError("Type the exact workspace name to confirm the ownership transfer.")
        if former_owner_role not in FORMER_OWNER_ROLES:
            raise ValidationError("Choose whether you stay as an admin or a member.")
        if new_owner_user_id == user_id:
            raise ValidationError("You already own this workspace.")
        if self._ws.member_role(workspace_id, new_owner_user_id) in (None, WORKSPACE_ROLE_OWNER):
            raise ValidationError("The new owner must be another active member of this workspace.")
        recipient = self._accounts.get_account(new_owner_user_id)
        email = (getattr(recipient, "email", None) or "").strip().lower()
        if (recipient is None or getattr(recipient, "status", "active") != "active" or not email
                or getattr(recipient, "email_verified", False) is not True):
            raise ValidationError("The new owner needs an active account with a verified email address.")
        raw = secrets.token_urlsafe(32)
        expires = utcnow() + timedelta(days=TRANSFER_TTL_DAYS)
        outcome, row = self._tr.propose(
            workspace_id=workspace_id, proposer_user_id=user_id, recipient_user_id=new_owner_user_id,
            recipient_email_hash=transfer_email_hash(email), former_owner_role=former_owner_role,
            token_hash=hash_token(raw), expires_at=expires)
        if outcome == "open_transfer_exists":
            raise ConflictError("This workspace already has an open ownership transfer. Cancel it before proposing another.")
        if outcome == "multiple_owners":
            raise ConflictError("This workspace has more than one owner, so it cannot be transferred.")
        if outcome == "workspace_inactive":
            raise ConflictError("This workspace is archived. Restore it to continue.")
        if outcome == "recipient_not_member":
            raise ValidationError("The new owner must be another active member of this workspace.")
        if outcome in ("not_owner",):
            raise WorkspacePermissionError("Only the workspace owner may propose an ownership transfer.")
        if outcome != "ok" or row is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        shaped = self._shape(row, user_id)
        shaped["email_delivery"] = self._send_notice(email, getattr(recipient, "interface_locale", None), raw)
        return shaped

    def _send_notice(self, email: str, locale: str | None, raw_token: str) -> str:
        """``submitted`` when the guarded EmailService reports the provider accepted (or captured) it, else ``not_submitted``. Never ``delivered``."""
        if self._mail is None:
            return "not_submitted"
        link = f"{self._base}/workspaces/transfer/accept?token={quote(raw_token)}"
        rendered = render_mail("ownership_transfer", locale=locale, link=link, expires_in_seconds=TRANSFER_TTL_DAYS * 86400)
        try:
            result = self._mail.deliver(
                EmailMessage(to=email, subject=rendered.subject, body=rendered.body, category="ownership_transfer"), locale=rendered.locale)
        except Exception:  # noqa: BLE001 - the transfer exists either way; the owner can cancel and propose again
            return "not_submitted"
        return "submitted" if getattr(result, "accepted", False) else "not_submitted"

    # -- reads ------------------------------------------------------------------------------------------------------

    def get_for_workspace(self, *, user_id: int, workspace_id: int) -> dict:
        """The open transfer of this workspace, but ONLY to its two parties; any other member gets ``null`` (no hint that one exists)."""
        self._require_member(workspace_id, user_id)
        self._tr.expire_due(workspace_id=workspace_id)
        row = self._tr.pending_for_workspace(workspace_id)
        if row is None or user_id not in (row["proposer_user_id"], row["recipient_user_id"]):
            return {"transfer": None}
        return {"transfer": self._shape(row, user_id)}

    def list_mine(self, *, user_id: int) -> dict:
        self._tr.expire_due(user_id=user_id)
        rows = self._tr.pending_for_user(user_id)
        out = []
        for row in rows:
            if self._ws.member_role(row["workspace_id"], user_id) is None:
                continue                                   # defensive: never list a workspace the caller no longer belongs to
            out.append(self._shape(row, user_id, with_workspace=True))
        return {"transfers": out}

    def preview(self, *, user_id: int, token: str) -> dict:
        """What the accept page may show BEFORE the person decides, only to the bound, verified account (anyone else gets the same errors as accepting)."""
        email = self._verified_email(user_id)
        row = self._tr.get_by_token_hash(hash_token(token))
        if row is None or row["recipient_user_id"] != user_id:
            raise WorkspaceNotFoundError("Ownership transfer not found.")
        self._tr.expire_due(workspace_id=row["workspace_id"])
        row = self._tr.get(row["id"])
        if row is None or row["status"] != "pending":
            raise ConflictError("This ownership transfer has already been used, cancelled or has expired.")
        ws = self._ws.get_workspace(row["workspace_id"])
        if ws is None or ws["status"] != WORKSPACE_STATUS_ACTIVE:
            raise ConflictError("This workspace is archived or no longer exists.")
        # The bound address must still be the verified one (the same check the claim makes).
        if not self._tr.email_bound(row["id"], transfer_email_hash(email)):
            raise WorkspacePermissionError("This ownership transfer was issued to a different email.")
        shaped = self._shape(row, user_id)
        shaped["workspace_name"] = ws["name"]
        return shaped

    # -- decisions --------------------------------------------------------------------------------------------------

    def accept(self, *, user_id: int, token: str) -> dict:
        email = self._verified_email(user_id)
        outcome, info = self._tr.accept(token_hash=hash_token(token), user_id=user_id, email_hash=transfer_email_hash(email))
        if outcome == "ok" and info is not None:
            return self._ws.get_workspace(info["workspace_id"]) or {}
        if outcome == "not_found":
            raise WorkspaceNotFoundError("Ownership transfer not found.")
        if outcome == "wrong_email":
            raise WorkspacePermissionError("This ownership transfer was issued to a different email.")
        if outcome == "expired":
            raise ConflictError("This ownership transfer has expired.")
        if outcome == "workspace_inactive":
            raise ConflictError("This workspace is archived or no longer exists.")
        if outcome == "invalid":
            raise ConflictError("This ownership transfer is no longer valid and was cancelled.")
        raise ConflictError("This ownership transfer has already been used, cancelled or has expired.")

    def decline(self, *, user_id: int, transfer_id: int) -> dict:
        outcome, _info = self._tr.decline(transfer_id=transfer_id, user_id=user_id)
        if outcome == "ok":
            return {"status": "declined"}
        if outcome == "not_found":
            raise WorkspaceNotFoundError("Ownership transfer not found.")
        if outcome == "expired":
            raise ConflictError("This ownership transfer has expired.")
        raise ConflictError("This ownership transfer has already been used, cancelled or has expired.")

    def cancel(self, *, user_id: int, workspace_id: int) -> dict:
        self._require_member(workspace_id, user_id)
        outcome, _info = self._tr.cancel(workspace_id=workspace_id, user_id=user_id)
        if outcome == "ok":
            return {"status": "cancelled"}
        if outcome == "not_found":
            raise WorkspaceNotFoundError("Ownership transfer not found.")     # nothing open, or the caller is not the proposer
        if outcome == "expired":
            raise ConflictError("This ownership transfer has expired.")
        raise ConflictError("This ownership transfer has already been used, cancelled or has expired.")
