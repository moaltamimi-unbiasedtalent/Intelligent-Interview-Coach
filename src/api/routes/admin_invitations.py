"""Admin surface for private-beta registration invitations (04E, REQ-BETA-01).

Permissions (an EXISTING pair; the registry stays at 44): ``platform.users.read`` to list and ``platform.users.manage`` to issue and revoke. An invitation is the
right to create a candidate ACCOUNT, which is exactly what ``users.manage`` governs (it is held only by the platform owner preset), and listing shows account-access
metadata at the same sensitivity as the users list. No new permission was needed.

The plaintext code and link are in the ISSUE response only (``Cache-Control: no-store``); they are never stored, logged, audited or listed. Lists show state and masked
identifiers only: no code, no hash, no full email, and not the account that redeemed an invitation. No email is sent: the operator copies the link.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from src.api.dependencies import get_auth_config, get_invitation_repository, get_request_id, require_permission
from src.api.rate_limit import enforce, user_key
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application.auth_service import _valid_email
from src.invitations import policy
from src.invitations import repository as R

router = APIRouter(prefix="/admin/invitations", tags=["admin-invitations"])


class InvitationRow(BaseModel):
    """State and masked identifiers only."""

    id: int
    state: Literal["pending", "redeemed", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    redeemed_at: datetime | None = None
    revoked_at: datetime | None = None
    email_bound: bool
    email_hint: str | None = None
    issued_by_user_id: int | None = None


class InvitationList(BaseModel):
    items: list[InvitationRow]
    total: int
    counts: dict[str, int]


class IssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expires_in_days: int = Field(default=policy.DEFAULT_TTL_DAYS, ge=1, le=policy.MAX_TTL_DAYS)
    email: str | None = Field(default=None, max_length=320)       # optional binding: only this address may redeem it


class IssuedInvitation(InvitationRow):
    """The ONE response that carries the plaintext. ``code`` and ``link`` are never available again."""

    code: str
    link: str


def _row(view: R.InvitationView) -> InvitationRow:
    return InvitationRow(**view.__dict__)


def _audit(event: str, request: Request, principal, target_id=None) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="invitation", target_id=target_id)


@router.get("", response_model=InvitationList, summary="Invitations: state and masked identifiers only (never a code, hash or full email)")
def list_invitations(
    state: Literal["pending", "redeemed", "expired", "revoked"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _p=Depends(require_permission(perm.USERS_READ)),
    invitations=Depends(get_invitation_repository),
) -> InvitationList:
    items, total = invitations.list(state=state, limit=limit, offset=offset)
    return InvitationList(items=[_row(v) for v in items], total=total, counts=invitations.counts())


@router.post("", response_model=IssuedInvitation, status_code=201,
             summary="Issue an invitation. The plaintext code and link are returned ONCE, in this response only; nothing is emailed")
def issue_invitation(
    body: IssueRequest,
    request: Request,
    response: Response,
    principal=Depends(require_permission(perm.USERS_MANAGE)),
    invitations=Depends(get_invitation_repository),
) -> IssuedInvitation:
    enforce("invitation_issue_user", user_key(principal.user_id))
    email = _valid_email(body.email) if body.email else None
    code = R.new_code()
    try:
        view = invitations.issue(code_hash=R.hash_code(code), ttl_days=body.expires_in_days, email=email, issued_by_user_id=principal.user_id,
                                 audit=_audit(A.ADMIN_INVITATION_ISSUED, request, principal))
    except R.InvitationLimit as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # The code rides in the URL FRAGMENT: it is never sent to a server, logged by a proxy or leaked through a Referer header.
    base = get_auth_config(request).app_base_url
    response.headers["Cache-Control"] = "no-store"
    return IssuedInvitation(**_row(view).model_dump(), code=code, link=f"{base}/register#invitation={code}")


@router.post("/{invitation_id}/revoke", response_model=InvitationRow,
             summary="Revoke an unredeemed invitation (idempotent; a redeemed one cannot be revoked)")
def revoke_invitation(
    invitation_id: int,
    request: Request,
    principal=Depends(require_permission(perm.USERS_MANAGE)),
    invitations=Depends(get_invitation_repository),
) -> InvitationRow:
    try:
        view = invitations.revoke(invitation_id, actor_user_id=principal.user_id,
                                  audit=_audit(A.ADMIN_INVITATION_REVOKED, request, principal, invitation_id))
    except R.InvitationNotFound:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    except R.InvitationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _row(view)
