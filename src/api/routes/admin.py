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
from src.entitlements import PLAN_CODES
from src.integrations import IntegrationService
from src.jobs.service import JobService
from src.knowledge_admin.service import KnowledgeAdminService
from src.ai_admin.service import AIConfigService
from src.application.pause import PauseService
from src.platform_config.flags import FeatureFlagService
from src.billing.wiring import build_billing_service
from src.privacy.requests import PrivacyRequestService
from src.plans_repository import PlanRepository
from src.secret_store import get_secret_store
from src.support_repository import SupportRepository
from src.api.dependencies import (
    get_account_repository,
    get_admin_user_repository,
    get_pause_service,
    get_plan_repository,
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
    PLATFORM_ROLES,
    PRODUCT_TIERS,
    SUPPORTED_LOCALES,
    WORKSPACE_ROLES,
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_DEACTIVATED,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class PlanAssignRequest(BaseModel):
    plan_code: str = Field(max_length=32)


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




@router.get("/home", summary="Command Center (operational metadata only)")
def home(request: Request, principal=Depends(require_permission(perm.OVERVIEW_READ)),
         accounts=Depends(get_account_repository), workspaces=Depends(get_workspace_repository)) -> dict:
    from src.application.admin_command_center import command_center

    return command_center(
        version=request.app.state.settings.version, session_factory=accounts.session_factory,
        accounts=accounts, workspaces=workspaces,
        allowed=perm.permissions_for_role(principal.platform_role),
        support=SupportRepository(accounts.session_factory),
        plans=PlanRepository(accounts.session_factory),
        integrations=IntegrationService(accounts.session_factory, get_secret_store()),
        jobs=JobService(accounts.session_factory),
        knowledge=KnowledgeAdminService(accounts.session_factory, doc_store=None, jobs=None),
        privacy=PrivacyRequestService(accounts.session_factory),
        billing=build_billing_service(accounts.session_factory),
        ai=AIConfigService(accounts.session_factory),
        pause=PauseService(accounts.session_factory),
        flags=FeatureFlagService(accounts.session_factory),
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
                users=Depends(get_admin_user_repository), plans=Depends(get_plan_repository)) -> AdminUserDetail:
    d = users.get_user_detail(user_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    role = d["account"]["platform_role"]
    d["plan"] = plans.subject_plan(user_id=user_id)
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


@router.post("/users/{user_id}/plan", summary="Move an account to the active version of a plan (audited, atomic)")
def set_user_plan(user_id: int, body: PlanAssignRequest, request: Request,
                  principal=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)),
                  plans=Depends(get_plan_repository)) -> dict:
    """Subscription change: the old subscription ends, a new one starts, the legacy tier column follows, and the
    audit row is written in the same transaction. A plan assignment is access, not a payment."""
    if body.plan_code not in PLAN_CODES:
        raise HTTPException(status_code=422, detail="Unknown plan.")
    before = plans.subject_plan(user_id=user_id)["current"]
    audit = A.build_audit(event_type=A.ADMIN_SUBSCRIPTION_ASSIGNED, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          before=before["plan_code"] if before else None, after=body.plan_code)
    return _guard(lambda: plans.assign(body.plan_code, user_id=user_id, source="admin", audit=audit))


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
                     users=Depends(get_admin_user_repository), plans=Depends(get_plan_repository)) -> AdminWorkspaceDetail:
    d = users.get_workspace_detail(workspace_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return AdminWorkspaceDetail(**d, workspace_roles=list(WORKSPACE_ROLES), plan=plans.subject_plan(workspace_id=workspace_id))


@router.post("/workspaces/{workspace_id}/plan", summary="Assign a plan to a workspace (audited, atomic; not billing)")
def set_workspace_plan(workspace_id: int, body: PlanAssignRequest, request: Request,
                       principal=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)),
                       plans=Depends(get_plan_repository)) -> dict:
    """Workspace subscriptions only apply to explicitly workspace-scoped actions; they never raise a member's
    personal access."""
    if body.plan_code not in PLAN_CODES:
        raise HTTPException(status_code=422, detail="Unknown plan.")
    before = plans.subject_plan(workspace_id=workspace_id)["current"]
    audit = A.build_audit(event_type=A.ADMIN_SUBSCRIPTION_ASSIGNED, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="workspace", target_id=workspace_id,
                          before=before["plan_code"] if before else None, after=body.plan_code)
    return _guard(lambda: plans.assign(body.plan_code, workspace_id=workspace_id, source="admin", audit=audit))


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


@router.get("/privacy-requests", summary="Open privacy requests (metadata only; the durable queue, SEC-W10-04)")
def privacy_requests(_p=Depends(require_permission(perm.PRIVACY_READ)),
                     accounts=Depends(get_account_repository)) -> dict:
    from src.privacy.requests import PrivacyRequestService

    page = PrivacyRequestService(accounts.session_factory).list(status="open", page=1, page_size=100)
    return {
        "requests": [{"public_id": r["public_id"], "request_type": r["request_type"], "status": r["status"], "user_id": r["user_id"],
                      "requested_at": r["created_at"]} for r in page["items"]],
        "total": page["total"],
        "note": "Durable queue (W10.10). Full handling is at /admin/privacy.",
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


def _realtime_provider_status() -> dict:
    """Safe realtime-voice operational metadata (Capstone P7.5): booleans/labels ONLY, now produced by the
    allowlist provider schema (W10.1). Never a key, an ephemeral secret, audio or any transcript."""
    from src.application.admin_providers import build_providers_response

    return build_providers_response().speech.realtime.model_dump()


@router.get("/providers", response_model=ProvidersResponse,
            summary="Provider status (allowlist schema; no secrets, no live calls)")
def providers(_p=Depends(require_permission(perm.INTEGRATIONS_READ)), pause=Depends(get_pause_service)) -> ProvidersResponse:
    from src.application.admin_providers import build_providers_response

    return build_providers_response(pause)
