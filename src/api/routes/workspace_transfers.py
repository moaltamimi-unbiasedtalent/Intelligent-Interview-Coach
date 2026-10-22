"""Two-step workspace ownership transfer routes (04B completion, REQ-OWN-07; OD-WS-TRANSFER is a provisional recommendation, not an approval).

A NEW module (the shared ``workspaces.py`` only lost its old one-step ``/transfer`` route). It is included BEFORE the workspaces router so that the literal
``/workspaces/transfers/...`` paths are matched before ``/workspaces/{workspace_id}``.

Route classes: USER (any authenticated caller; the service binds the caller to the transfer) and WORKSPACE (membership/role enforced in the service). A
non-member, a member who is not a party, and a caller the token is not bound to all get the same 404 so a pending transfer cannot be probed. Proposing needs
the owner's FRESH password confirmation on THIS session (the existing step-up, five minutes, not MFA; an OIDC-only account fails closed and cannot propose).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from src.api.dependencies import (
    _session_cookie_name,
    get_account_repository,
    get_current_user_id,
    get_email_sender,
    get_request_id,
    get_workspace_repository,
)
from src.api.rate_limit import enforce, user_key
from src.api.routes.workspaces import TokenRequest            # the SAME request model as the invitation token (one shape, one allow-listed input field)
from src.api.routes.admin_security import StepUpBody          # the SAME request model as the existing step-up (one shape, one allow-listed input field)
from src.application.errors import ConflictError, ValidationError
from src.application.ownership_transfer_service import OwnershipTransferService
from src.application.workspace_service import WorkspaceNotFoundError, WorkspacePermissionError
from src.ownership_transfer_repository import OwnershipTransferRepository

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def get_ownership_transfer_service(request: Request, workspaces=Depends(get_workspace_repository),
                                   accounts=Depends(get_account_repository), email=Depends(get_email_sender)):
    base = getattr(getattr(request.app.state, "settings", None), "app_base_url", None) or "https://app.ask4mo.local"
    return OwnershipTransferService(workspaces=workspaces, transfers=OwnershipTransferRepository(workspaces.session_factory),
                                    accounts=accounts, email=email, app_base_url=base)


def _guard(fn):
    try:
        return fn()
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposeRequest(_Strict):
    new_owner_user_id: int
    confirm_name: str = Field(default="", max_length=200)
    # What the current owner keeps after a successful transfer.
    former_owner_role: str = Field(default="workspace_member", max_length=24)


def _step_up():
    from src.admin_security.stepup import StepUpService

    return StepUpService


# -- literal paths first --------------------------------------------------------------------------------------------

@router.get("/transfers/mine", summary="My open ownership transfers (as proposer or recipient)")
def my_transfers(user_id: int = Depends(get_current_user_id), svc=Depends(get_ownership_transfer_service)) -> dict:
    return _guard(lambda: svc.list_mine(user_id=user_id))


@router.get("/transfers/step-up", summary="Is THIS session freshly confirmed for an ownership transfer? (password re-authentication; not MFA)")
def step_up_status(request: Request, user_id: int = Depends(get_current_user_id), workspaces=Depends(get_workspace_repository)) -> dict:
    return _step_up()(workspaces.session_factory).status(request.cookies.get(_session_cookie_name(request)))


@router.post("/transfers/step-up", summary="Confirm your password to authorise proposing an ownership transfer (reuses the existing step-up; not MFA)")
def step_up(body: StepUpBody, request: Request, user_id: int = Depends(get_current_user_id), workspaces=Depends(get_workspace_repository)) -> dict:
    enforce("stepup_user", user_key(user_id))
    return _step_up()(workspaces.session_factory).confirm(
        user_id=user_id, session_token=request.cookies.get(_session_cookie_name(request)), password=body.password,
        request_id=get_request_id(request))


@router.post("/transfers/preview", summary="Preview a transfer before deciding (the bound, verified recipient only)")
def preview(body: TokenRequest, user_id: int = Depends(get_current_user_id), svc=Depends(get_ownership_transfer_service)) -> dict:
    return _guard(lambda: svc.preview(user_id=user_id, token=body.token))


@router.post("/transfers/accept", summary="Accept an ownership transfer (the bound, verified recipient, with the one-time token)")
def accept(body: TokenRequest, user_id: int = Depends(get_current_user_id), svc=Depends(get_ownership_transfer_service)) -> dict:
    return _guard(lambda: svc.accept(user_id=user_id, token=body.token))


@router.post("/transfers/{transfer_id}/decline", summary="Decline an ownership transfer - the recipient only")
def decline(transfer_id: int, user_id: int = Depends(get_current_user_id), svc=Depends(get_ownership_transfer_service)) -> dict:
    return _guard(lambda: svc.decline(user_id=user_id, transfer_id=transfer_id))


# -- workspace-scoped -----------------------------------------------------------------------------------------------

@router.get("/{workspace_id}/transfer", summary="The open ownership transfer of this workspace - the two parties only")
def workspace_transfer(workspace_id: int, user_id: int = Depends(get_current_user_id), svc=Depends(get_ownership_transfer_service)) -> dict:
    return _guard(lambda: svc.get_for_workspace(user_id=user_id, workspace_id=workspace_id))


@router.post("/{workspace_id}/transfer", summary="Propose an ownership transfer - owner only, typed name, fresh password confirmation")
def propose(workspace_id: int, body: ProposeRequest, request: Request, user_id: int = Depends(get_current_user_id),
            svc=Depends(get_ownership_transfer_service), workspaces=Depends(get_workspace_repository)) -> dict:
    def run():
        # Authorisation order: membership (404) and role (403) first, so the step-up prompt is never shown to someone who could not propose anyway.
        role = workspaces.member_role(workspace_id, user_id)
        if role is None:
            raise WorkspaceNotFoundError("Workspace not found.")
        if role != "workspace_owner":
            raise WorkspacePermissionError("Only the workspace owner may propose an ownership transfer.")
        _step_up()(workspaces.session_factory).require(request.cookies.get(_session_cookie_name(request)))   # 403 step_up_required / step_up_unavailable
        return svc.propose(user_id=user_id, workspace_id=workspace_id, new_owner_user_id=body.new_owner_user_id,
                           confirm_name=body.confirm_name, former_owner_role=body.former_owner_role)
    return _guard(run)


@router.post("/{workspace_id}/transfer/cancel", summary="Cancel the open ownership transfer - the proposer only")
def cancel(workspace_id: int, user_id: int = Depends(get_current_user_id), svc=Depends(get_ownership_transfer_service)) -> dict:
    return _guard(lambda: svc.cancel(user_id=user_id, workspace_id=workspace_id))
