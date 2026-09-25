"""Workspaces + explicit sharing routes (Capstone P6.5).

Route classes: USER (any authenticated caller) and WORKSPACE (membership/role enforced in
the service). Ownership and membership are always checked server-side; private-by-default is
preserved (a member sees another member's resource ONLY via an explicit share grant).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import (
    get_current_principal,
    get_current_user_id,
    get_sharing_service,
    get_workspace_service,
)
from src.application.errors import ConflictError, ValidationError
from src.application.sharing_service import SharingNotFoundError, SharingPermissionError
from src.application.workspace_service import WorkspaceNotFoundError, WorkspacePermissionError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
shares_router = APIRouter(prefix="/shares", tags=["workspaces"])


def _guard(fn):
    """Map service exceptions to safe HTTP status codes."""
    try:
        return fn()
    except (WorkspaceNotFoundError, SharingNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (WorkspacePermissionError, SharingPermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default="workspace_member", max_length=24)


class TokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class TransferRequest(BaseModel):
    new_owner_user_id: int


class ShareRequest(BaseModel):
    workspace_id: int
    resource_type: str = Field(max_length=32)
    resource_id: str = Field(max_length=128)


# -- workspaces ---------------------------------------------------------------

@router.post("", summary="Create a workspace")
def create_workspace(body: CreateWorkspaceRequest, user_id: int = Depends(get_current_user_id),
                     svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.create_workspace(user_id=user_id, name=body.name))


@router.get("", summary="My workspaces + invitations")
def my_workspaces(principal=Depends(get_current_principal), svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.list_my_workspaces(user_id=principal.user_id, email=principal.email))


@router.get("/{workspace_id}", summary="Workspace detail (members) — members only")
def workspace_detail(workspace_id: int, user_id: int = Depends(get_current_user_id),
                     svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.get_workspace_detail(user_id=user_id, workspace_id=workspace_id))


@router.post("/{workspace_id}/invite", summary="Invite by email — owner only")
def invite(workspace_id: int, body: InviteRequest, user_id: int = Depends(get_current_user_id),
           svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.invite(user_id=user_id, workspace_id=workspace_id,
                                     email=body.email, role=body.role))


@router.post("/invitations/accept", summary="Accept an invitation (own email only)")
def accept_invitation(body: TokenRequest, user_id: int = Depends(get_current_user_id),
                      svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.accept_invitation(user_id=user_id, token=body.token))


@router.post("/invitations/decline", summary="Decline an invitation")
def decline_invitation(body: TokenRequest, user_id: int = Depends(get_current_user_id),
                       svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.decline_invitation(user_id=user_id, token=body.token))


@router.post("/{workspace_id}/leave", summary="Leave a workspace")
def leave(workspace_id: int, user_id: int = Depends(get_current_user_id),
          svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.leave(user_id=user_id, workspace_id=workspace_id))


@router.post("/{workspace_id}/members/{target_user_id}/remove", summary="Remove a member — owner only")
def remove_member(workspace_id: int, target_user_id: int, user_id: int = Depends(get_current_user_id),
                  svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.remove_member(user_id=user_id, workspace_id=workspace_id,
                                           target_user_id=target_user_id))


@router.post("/{workspace_id}/transfer", summary="Transfer ownership — owner only")
def transfer(workspace_id: int, body: TransferRequest, user_id: int = Depends(get_current_user_id),
             svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.transfer_ownership(user_id=user_id, workspace_id=workspace_id,
                                                new_owner_user_id=body.new_owner_user_id))


@router.post("/{workspace_id}/deactivate", summary="Deactivate a workspace — owner only")
def deactivate(workspace_id: int, user_id: int = Depends(get_current_user_id),
               svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.deactivate_workspace(user_id=user_id, workspace_id=workspace_id))


# -- sharing ------------------------------------------------------------------

@shares_router.post("", summary="Share an owned resource into a workspace (VIEW)")
def create_share(body: ShareRequest, user_id: int = Depends(get_current_user_id),
                 svc=Depends(get_sharing_service)) -> dict:
    return _guard(lambda: svc.share(user_id=user_id, workspace_id=body.workspace_id,
                                   resource_type=body.resource_type, resource_id=body.resource_id))


@shares_router.delete("/{share_id}", summary="Revoke a share (owner only)")
def revoke_share(share_id: int, user_id: int = Depends(get_current_user_id),
                 svc=Depends(get_sharing_service)) -> dict:
    return _guard(lambda: svc.revoke(user_id=user_id, share_id=share_id))


@shares_router.get("/mine", summary="Resources I have shared")
def shares_mine(user_id: int = Depends(get_current_user_id), svc=Depends(get_sharing_service)) -> dict:
    return {"shares": svc.list_shared_by_me(user_id=user_id)}


@shares_router.get("/with-me", summary="Resources shared with me")
def shares_with_me(user_id: int = Depends(get_current_user_id), svc=Depends(get_sharing_service)) -> dict:
    return {"shares": svc.list_shared_with_me(user_id=user_id)}


@shares_router.get("/resource/{resource_type}/{resource_id}", summary="View a shared resource")
def view_shared(resource_type: str, resource_id: str, user_id: int = Depends(get_current_user_id),
                svc=Depends(get_sharing_service)) -> dict:
    return _guard(lambda: svc.resolve_shared_resource(
        user_id=user_id, resource_type=resource_type, resource_id=resource_id))
