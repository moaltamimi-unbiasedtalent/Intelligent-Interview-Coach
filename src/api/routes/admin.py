"""Platform Admin / Operations routes (Capstone P6.5).

Permission-gated (W10.1): every route declares an explicit ``require_permission(...)``; there is no
router-level coarse gate. This is an OPERATIONS surface, not a data
superuser: it exposes account/workspace/entitlement/privacy/provider/audit METADATA and
performs audited privileged changes — it NEVER returns candidate-private content (CV,
answers, Memory, Story Bank, raw conversation, documents), has no "view as user" and no
private-data search. Owner-scoped repositories stay owner-scoped.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from fastapi import Request

from src.admin_repository import AdminNotFound
from src.api.dependencies import (
    get_account_repository,
    get_admin_user_repository,
    get_audit_repository,
    get_request_id,
    get_workspace_repository,
    require_permission,
)
from src.api.schemas.admin import (
    AdminUserDetail,
    AdminUserList,
    AdminWorkspaceDetail,
    AdminWorkspaceList,
    ProvidersResponse,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    ACCOUNT_STATUS_DEACTIVATED,
    ACCOUNT_STATUSES,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLES,
    PRODUCT_TIERS,
    SUPPORTED_LOCALES,
    WORKSPACE_ROLES,
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_DEACTIVATED,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleRequest(BaseModel):
    role: str = Field(max_length=32)
    reason: str | None = Field(default=None, max_length=200)


class TierRequest(BaseModel):
    tier: str = Field(max_length=32)


class StatusRequest(BaseModel):
    status: str = Field(max_length=32)
    reason: str | None = Field(default=None, max_length=200)


class RevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class MemberAddRequest(BaseModel):
    user_id: int = Field(ge=1)
    role: str = Field(default="workspace_member", max_length=24)


class MemberRoleRequest(BaseModel):
    role: str = Field(max_length=24)


class PauseRequest(BaseModel):
    paused: bool


@router.get("/home", summary="Command Center (operational metadata only)")
def home(request: Request, principal=Depends(require_permission(perm.OVERVIEW_READ)),
         accounts=Depends(get_account_repository), workspaces=Depends(get_workspace_repository)) -> dict:
    from src.application.admin_command_center import command_center

    return command_center(
        version=request.app.state.settings.version, session_factory=accounts.session_factory,
        accounts=accounts, workspaces=workspaces,
        allowed=perm.permissions_for_role(principal.platform_role),
    )


@router.get("/users", response_model=AdminUserList,
            summary="Account metadata: server-side search, filters and pagination (never candidate content)")
def list_users(
    q: str | None = Query(default=None, max_length=320),
    status: str | None = Query(default=None, max_length=32),
    role: str | None = Query(default=None, max_length=32),
    tier: str | None = Query(default=None, max_length=32),
    onboarding: Literal["completed", "pending"] | None = Query(default=None),
    locale: str | None = Query(default=None, max_length=8),
    email_verified: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=25, ge=1, le=100),
    _p=Depends(require_permission(perm.USERS_READ)),
    users=Depends(get_admin_user_repository),
) -> AdminUserList:
    for value, allowed, label in ((status, ACCOUNT_STATUSES, "status"), (role, PLATFORM_ROLES, "role"),
                                  (tier, PRODUCT_TIERS, "tier"), (locale, SUPPORTED_LOCALES, "locale")):
        if value and value not in allowed:
            raise HTTPException(status_code=422, detail=f"Unknown {label} filter.")
    out = users.list_users(q=q, status=status, role=role, tier=tier, onboarding=onboarding, locale=locale,
                           email_verified=email_verified, page=page, page_size=page_size)
    return AdminUserList(**out, users=out["items"])


@router.get("/users/{user_id}", response_model=AdminUserDetail,
            summary="Safe account detail: account, access, session metadata, workspaces, admin audit")
def user_detail(user_id: int, principal=Depends(require_permission(perm.USERS_READ)),
                users=Depends(get_admin_user_repository)) -> AdminUserDetail:
    d = users.get_user_detail(user_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    role = d["account"]["platform_role"]
    d["access"] = {"platform_role": role, "capabilities": perm.sorted_permissions(role),
                   "assignable_roles": list(PLATFORM_ROLES), "is_self": user_id == principal.user_id}
    return AdminUserDetail(**d)


def _current(accounts, user_id: int):
    """Safe before-state (a single enum value) for the audit; None when the account is unknown."""
    return accounts.get_account(user_id)


def _guard(fn):
    """Map repository domain errors to HTTP (missing -> 404). ConflictError is handled app-wide (409)."""
    try:
        return fn()
    except AdminNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/users/{user_id}/role", summary="Set platform role preset (audited, atomic)")
def set_role(user_id: int, body: RoleRequest, request: Request,
             principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)),
             users=Depends(get_admin_user_repository)) -> dict:
    if body.role not in PLATFORM_ROLES:  # only the code-defined presets; no custom roles
        raise HTTPException(status_code=422, detail="Unknown platform role.")
    # Self-lockout guard: an admin may not demote their own admin role.
    if user_id == principal.user_id and body.role != PLATFORM_ROLE_ADMIN:
        raise HTTPException(status_code=409, detail="You cannot remove your own admin role.")
    d = users.get_user_detail(user_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    audit = A.build_audit(event_type=A.ADMIN_PLATFORM_ROLE_CHANGE, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          reason=body.reason, before=d["account"]["platform_role"], after=body.role,
                          role=body.role)
    # Role is re-read from the database on every request, so a demotion takes effect immediately.
    out = _guard(lambda: users.set_platform_role(user_id, body.role, audit=audit))
    return {"user_id": user_id, "platform_role": body.role, "changed": out["changed"]}


@router.post("/users/{user_id}/tier", summary="Set product entitlement tier (audited, atomic)")
def set_tier(user_id: int, body: TierRequest, request: Request,
             principal=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)),
             accounts=Depends(get_account_repository)) -> dict:
    if body.tier not in PRODUCT_TIERS:
        raise HTTPException(status_code=422, detail="Unknown tier.")
    before = _current(accounts, user_id)
    if before is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    audit = A.build_audit(event_type=A.ADMIN_ENTITLEMENT_CHANGE, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          before=before.tier, after=body.tier, tier=body.tier)
    if not accounts.set_tier(user_id, body.tier, source="admin", audit=audit):
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"user_id": user_id, "tier": body.tier}


@router.post("/users/{user_id}/status", summary="Deactivate or reactivate an account (audited, atomic)")
def set_status(user_id: int, body: StatusRequest, request: Request,
               principal=Depends(require_permission(perm.USERS_MANAGE)),
               users=Depends(get_admin_user_repository)) -> dict:
    if body.status not in (ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_DEACTIVATED):
        raise HTTPException(status_code=422, detail="Unsupported status for admin change.")
    if user_id == principal.user_id and body.status != ACCOUNT_STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
    d = users.get_user_detail(user_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    audit = A.build_audit(event_type=A.ADMIN_ACCOUNT_STATUS_CHANGE, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          reason=body.reason, before=d["account"]["status"], after=body.status,
                          status=body.status)
    # Deactivation revokes every live session in the SAME transaction as the status change and the audit.
    out = _guard(lambda: users.set_status(user_id, body.status, audit=audit))
    return {"user_id": user_id, "status": body.status, "changed": out["changed"],
            "sessions_revoked": out["sessions_revoked"]}


@router.post("/users/{user_id}/sessions/revoke", summary="Force logout: revoke all live sessions (audited)")
def revoke_sessions(user_id: int, request: Request, body: RevokeRequest | None = None,
                    principal=Depends(require_permission(perm.USERS_SESSIONS_REVOKE)),
                    users=Depends(get_admin_user_repository)) -> dict:
    audit = A.build_audit(event_type=A.ADMIN_SESSIONS_REVOKED, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          reason=body.reason if body else None)
    revoked = _guard(lambda: users.revoke_sessions(user_id, audit=audit))
    return {"user_id": user_id, "sessions_revoked": revoked}


@router.get("/workspaces", response_model=AdminWorkspaceList,
            summary="Workspace metadata: search, filter, pagination (no shared content)")
def list_workspaces(q: str | None = Query(default=None, max_length=120),
                    status: str | None = Query(default=None, max_length=16),
                    page: int = Query(default=1, ge=1, le=100000),
                    page_size: int = Query(default=25, ge=1, le=100),
                    _p=Depends(require_permission(perm.WORKSPACES_READ)),
                    users=Depends(get_admin_user_repository)) -> AdminWorkspaceList:
    if status and status not in (WORKSPACE_STATUS_ACTIVE, WORKSPACE_STATUS_DEACTIVATED):
        raise HTTPException(status_code=422, detail="Unknown status filter.")
    out = users.list_workspaces(q=q, status=status, page=page, page_size=page_size)
    return AdminWorkspaceList(**out, workspaces=out["items"])


@router.get("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetail,
            summary="Safe workspace detail: metadata and members (never workspace content)")
def workspace_detail(workspace_id: int, _p=Depends(require_permission(perm.WORKSPACES_READ)),
                     users=Depends(get_admin_user_repository)) -> AdminWorkspaceDetail:
    d = users.get_workspace_detail(workspace_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return AdminWorkspaceDetail(**d, workspace_roles=list(WORKSPACE_ROLES))


def _ws_audit(event: str, request: Request, principal, workspace_id: int, **ctx):
    return A.build_audit(event_type=event, actor_user_id=principal.user_id,
                         request_id=get_request_id(request), target_type="workspace",
                         target_id=workspace_id, **ctx)


@router.post("/workspaces/{workspace_id}/members", summary="Add an existing account to a workspace (audited)")
def add_member(workspace_id: int, body: MemberAddRequest, request: Request,
               principal=Depends(require_permission(perm.WORKSPACES_MANAGE)),
               users=Depends(get_admin_user_repository)) -> dict:
    if body.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=422, detail="Unknown workspace role.")
    audit = _ws_audit(A.ADMIN_WORKSPACE_MEMBER_ADDED, request, principal, workspace_id,
                      member_user_id=body.user_id, after=body.role)
    return _guard(lambda: users.add_member(workspace_id, body.user_id, body.role, audit=audit))


@router.delete("/workspaces/{workspace_id}/members/{user_id}",
               summary="Remove a member from a workspace (audited; revokes their shares into it)")
def remove_member(workspace_id: int, user_id: int, request: Request,
                  principal=Depends(require_permission(perm.WORKSPACES_MANAGE)),
                  users=Depends(get_admin_user_repository)) -> dict:
    audit = _ws_audit(A.ADMIN_WORKSPACE_MEMBER_REMOVED, request, principal, workspace_id,
                      member_user_id=user_id)
    return _guard(lambda: users.remove_member(workspace_id, user_id, audit=audit))


@router.post("/workspaces/{workspace_id}/members/{user_id}/role",
             summary="Change a member's workspace role (audited; a workspace keeps at least one owner)")
def set_member_role(workspace_id: int, user_id: int, body: MemberRoleRequest, request: Request,
                    principal=Depends(require_permission(perm.WORKSPACES_MANAGE)),
                    users=Depends(get_admin_user_repository)) -> dict:
    if body.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=422, detail="Unknown workspace role.")
    audit = _ws_audit(A.ADMIN_WORKSPACE_MEMBER_ROLE_CHANGED, request, principal, workspace_id,
                      member_user_id=user_id, after=body.role)
    return _guard(lambda: users.set_member_role(workspace_id, user_id, body.role, audit=audit))


@router.get("/privacy-requests", summary="Open privacy/deletion requests (metadata only)")
def privacy_requests(_p=Depends(require_permission(perm.PRIVACY_READ)),
                     accounts=Depends(get_account_repository)) -> dict:
    return {
        "requests": accounts.list_privacy_requests(),
        "note": "Global hard-delete (private-file + agent checkpoint purge) remains PARTIAL; "
                "deletion is not falsely reported complete.",
    }


@router.get("/feedback", summary="Feedback taxonomy + aggregate counts (no raw content)")
def feedback_overview(_p=Depends(require_permission(perm.REPORTS_READ)),
                      accounts=Depends(get_account_repository)) -> dict:
    from sqlalchemy import func, select

    from src.copilot.feedback_intelligence.improvement import ImprovementStatus
    from src.feedback_taxonomy import FeedbackCategory
    from src.persistence import UserFeedback

    with accounts.session_factory() as s:
        by_rating = dict(s.execute(
            select(UserFeedback.rating, func.count()).group_by(UserFeedback.rating)).all())
        by_category = dict(s.execute(
            select(UserFeedback.category, func.count())
            .where(UserFeedback.category.is_not(None)).group_by(UserFeedback.category)).all())
    return {
        "taxonomy": [c.value for c in FeedbackCategory],
        "improvement_lifecycle": [s.value for s in ImprovementStatus],
        "counts_by_rating": {k: int(v) for k, v in by_rating.items()},
        "counts_by_category": {k: int(v) for k, v in by_category.items()},
        "note": "Aggregate counts only; raw comments/candidate content are never exposed here.",
    }


@router.get("/pause", summary="Operator pause switches (process-local, non-durable)")
def pause_state(_p=Depends(require_permission(perm.FLAGS_READ))) -> dict:
    """Current pause state (booleans only). A paused capability returns 503 to candidates.
    State is process-local and non-durable until W10.11 (SEC-W10-05); the response says so."""
    from src.application.admin_command_center import pause_state as _ps
    from src.application.pause import PAUSABLE_CAPABILITIES

    return {"pausable": list(PAUSABLE_CAPABILITIES), **_ps()}


@router.post("/pause/{capability}", summary="Pause or resume a capability (audit-first, fail-closed)")
def set_pause(capability: str, body: PauseRequest, request: Request,
              principal=Depends(require_permission(perm.FLAGS_MANAGE)),
              audit=Depends(get_audit_repository)) -> dict:
    from src.application.pause import PAUSABLE_CAPABILITIES, get_pause_registry

    if capability not in PAUSABLE_CAPABILITIES:
        raise HTTPException(status_code=422, detail="Unknown pausable capability.")
    registry = get_pause_registry()
    before = registry.is_paused(capability)
    # The pause state is in memory (no DB row), so there is no shared transaction. The ordering
    # guarantee is audit FIRST and fail-closed: if the audit cannot be committed, nothing is applied.
    spec = A.build_audit(event_type=A.PLATFORM_PAUSE_TOGGLED, actor_user_id=principal.user_id,
                         request_id=get_request_id(request), target_type="capability",
                         target_id=capability, before=before, after=body.paused, paused=body.paused)
    try:
        audit.record(**spec)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Audit unavailable; the change was not applied.")
    registry.set(capability, body.paused)
    return {"capability": capability, "paused": body.paused}


def _realtime_provider_status() -> dict:
    """Safe realtime-voice operational metadata (Capstone P7.5): booleans/labels ONLY, now produced by the
    allowlist provider schema (W10.1). Never a key, an ephemeral secret, audio or any transcript."""
    from src.application.admin_providers import build_providers_response

    return build_providers_response().speech.realtime.model_dump()


@router.get("/providers", response_model=ProvidersResponse,
            summary="Provider status (allowlist schema; no secrets, no live calls)")
def providers(_p=Depends(require_permission(perm.INTEGRATIONS_READ))) -> ProvidersResponse:
    from src.application.admin_providers import build_providers_response

    return build_providers_response()


@router.get("/audit", summary="Recent audit events (safe metadata)")
def audit_view(event_type: str | None = Query(default=None, max_length=64),
               limit: int = Query(default=100, ge=1, le=500),
               _p=Depends(require_permission(perm.AUDIT_READ)),
               audit=Depends(get_audit_repository)) -> dict:
    return {"events": audit.recent(limit=limit, event_type=event_type)}
