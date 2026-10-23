"""Workspaces + explicit sharing routes (Capstone P6.5, completed by 04B).

Route classes: USER (any authenticated caller) and WORKSPACE (membership/role enforced in
the service). Ownership and membership are always checked server-side; private-by-default is
preserved (a member sees another member's resource ONLY via an explicit share grant). A caller
who is not an ACTIVE member (never joined, invited but not accepted, left, removed) gets 404 for
every workspace-scoped route so existence cannot be probed; an active member without the needed
role gets 403.
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


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ConfirmRequest(BaseModel):
    confirm_name: str = Field(default="", max_length=200)


class RoleRequest(BaseModel):
    role: str = Field(max_length=24)


class ShareRequest(BaseModel):
    workspace_id: int
    resource_type: str = Field(max_length=32)
    resource_id: str = Field(max_length=128)
    # Explicit consent: the sharer acknowledges that every active member of the workspace can view this one item.
    consent: bool = False


# -- workspaces ---------------------------------------------------------------

@router.post("", summary="Create a workspace")
def create_workspace(body: CreateWorkspaceRequest, user_id: int = Depends(get_current_user_id),
                     svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.create_workspace(user_id=user_id, name=body.name))


@router.get("", summary="My workspaces + invitations")
def my_workspaces(principal=Depends(get_current_principal), svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.list_my_workspaces(user_id=principal.user_id, email=principal.email,
                                                 email_verified=principal.email_verified))


@router.get("/{workspace_id}", summary="Workspace detail (members) — members only")
def workspace_detail(workspace_id: int, user_id: int = Depends(get_current_user_id),
                     svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.get_workspace_detail(user_id=user_id, workspace_id=workspace_id))


@router.patch("/{workspace_id}", summary="Rename a workspace - owner or admin")
def rename(workspace_id: int, body: RenameRequest, user_id: int = Depends(get_current_user_id),
           svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.rename_workspace(user_id=user_id, workspace_id=workspace_id, name=body.name))


@router.post("/{workspace_id}/invite", summary="Invite by email - owner or admin (only an owner may invite an admin)")
def invite(workspace_id: int, body: InviteRequest, user_id: int = Depends(get_current_user_id),
           svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.invite(user_id=user_id, workspace_id=workspace_id,
                                     email=body.email, role=body.role))


@router.post("/{workspace_id}/invitations/{invitation_id}/revoke", summary="Revoke a pending invitation - owner or admin")
def revoke_invitation(workspace_id: int, invitation_id: int, user_id: int = Depends(get_current_user_id),
                      svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.revoke_invitation(user_id=user_id, workspace_id=workspace_id,
                                                invitation_id=invitation_id))


@router.post("/invitations/preview", summary="Preview an invitation before deciding (the invited, verified account only)")
def preview_invitation(body: TokenRequest, user_id: int = Depends(get_current_user_id),
                       svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.preview_invitation(user_id=user_id, token=body.token))


@router.post("/invitations/{invitation_id}/accept", summary="Accept an invitation addressed to my verified email")
def accept_invitation_by_id(invitation_id: int, user_id: int = Depends(get_current_user_id),
                            svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.accept_invitation_by_id(user_id=user_id, invitation_id=invitation_id))


@router.post("/invitations/{invitation_id}/decline", summary="Decline an invitation addressed to my verified email")
def decline_invitation_by_id(invitation_id: int, user_id: int = Depends(get_current_user_id),
                             svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.decline_invitation_by_id(user_id=user_id, invitation_id=invitation_id))


@router.post("/invitations/accept", summary="Accept an invitation (verified, own email only)")
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


@router.post("/{workspace_id}/members/{target_user_id}/role", summary="Promote a member to admin or demote an admin - owner only")
def change_role(workspace_id: int, target_user_id: int, body: RoleRequest,
                user_id: int = Depends(get_current_user_id), svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.change_member_role(user_id=user_id, workspace_id=workspace_id,
                                                 target_user_id=target_user_id, role=body.role))


@router.post("/{workspace_id}/members/{target_user_id}/remove", summary="Remove a member - owner, or an admin for plain members")
def remove_member(workspace_id: int, target_user_id: int, user_id: int = Depends(get_current_user_id),
                  svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.remove_member(user_id=user_id, workspace_id=workspace_id,
                                           target_user_id=target_user_id))


@router.post("/{workspace_id}/archive", summary="Archive a workspace and revoke every share into it - owner only")
def archive(workspace_id: int, user_id: int = Depends(get_current_user_id),
            svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.archive_workspace(user_id=user_id, workspace_id=workspace_id))


@router.post("/{workspace_id}/deactivate", summary="Legacy alias of archive - owner only")
def deactivate(workspace_id: int, user_id: int = Depends(get_current_user_id),
               svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.archive_workspace(user_id=user_id, workspace_id=workspace_id))


@router.post("/{workspace_id}/restore", summary="Restore an archived workspace (revoked shares stay revoked) - owner only")
def restore(workspace_id: int, user_id: int = Depends(get_current_user_id),
            svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.restore_workspace(user_id=user_id, workspace_id=workspace_id))


@router.post("/{workspace_id}/delete", summary="Permanently delete a workspace - owner only, typed confirmation")
def delete_workspace(workspace_id: int, body: ConfirmRequest, user_id: int = Depends(get_current_user_id),
                     svc=Depends(get_workspace_service)) -> dict:
    return _guard(lambda: svc.delete_workspace(user_id=user_id, workspace_id=workspace_id,
                                               confirm_name=body.confirm_name))


@router.get("/{workspace_id}/shares", summary="What is shared into this workspace (metadata only) - members only")
def workspace_shares(workspace_id: int, user_id: int = Depends(get_current_user_id),
                     svc=Depends(get_sharing_service)) -> dict:
    return _guard(lambda: {"shares": svc.list_workspace_shares(user_id=user_id, workspace_id=workspace_id)})


# -- sharing ------------------------------------------------------------------

@shares_router.post("", summary="Share an owned resource into a workspace (VIEW, explicit consent required)")
def create_share(body: ShareRequest, user_id: int = Depends(get_current_user_id),
                 svc=Depends(get_sharing_service)) -> dict:
    return _guard(lambda: svc.share(user_id=user_id, workspace_id=body.workspace_id,
                                   resource_type=body.resource_type, resource_id=body.resource_id,
                                   consent=body.consent))


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
