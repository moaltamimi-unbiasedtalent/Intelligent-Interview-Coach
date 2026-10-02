"""Platform Admin / Operations routes (Capstone P6.5).

Permission-gated (W10.1): every route declares an explicit ``require_permission(...)``; there is no
router-level coarse gate. This is an OPERATIONS surface, not a data
superuser: it exposes account/workspace/entitlement/privacy/provider/audit METADATA and
performs audited privileged changes — it NEVER returns candidate-private content (CV,
answers, Memory, Story Bank, raw conversation, documents), has no "view as user" and no
private-data search. Owner-scoped repositories stay owner-scoped.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from fastapi import Request

from src.api.dependencies import (
    get_account_repository,
    get_audit_repository,
    get_request_id,
    get_workspace_repository,
    require_permission,
)
from src.api.schemas.admin import ProvidersResponse
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    ACCOUNT_STATUS_DEACTIVATED,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLES,
    PRODUCT_TIERS,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleRequest(BaseModel):
    role: str = Field(max_length=32)


class TierRequest(BaseModel):
    tier: str = Field(max_length=32)


class StatusRequest(BaseModel):
    status: str = Field(max_length=32)


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


@router.get("/users", summary="Account metadata (never candidate content)")
def list_users(query: str | None = Query(default=None, max_length=320), limit: int = Query(default=100, ge=1, le=500),
               _p=Depends(require_permission(perm.USERS_READ)),
               accounts=Depends(get_account_repository)) -> dict:
    return {"users": accounts.list_accounts(limit=limit, query=query)}


def _current(accounts, user_id: int):
    """Safe before-state (a single enum value) for the audit; None when the account is unknown."""
    return accounts.get_account(user_id)


@router.post("/users/{user_id}/role", summary="Set platform role (audited, atomic)")
def set_role(user_id: int, body: RoleRequest, request: Request,
             principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)),
             accounts=Depends(get_account_repository)) -> dict:
    if body.role not in PLATFORM_ROLES:
        raise HTTPException(status_code=422, detail="Unknown platform role.")
    # Self-lockout guard: an admin may not demote their own admin role.
    if user_id == principal.user_id and body.role != PLATFORM_ROLE_ADMIN:
        raise HTTPException(status_code=409, detail="You cannot remove your own admin role.")
    before = _current(accounts, user_id)
    if before is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    audit = A.build_audit(event_type=A.ADMIN_PLATFORM_ROLE_CHANGE, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          before=before.platform_role, after=body.role, role=body.role)
    if not accounts.set_platform_role(user_id, body.role, audit=audit):  # state + audit: one transaction
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"user_id": user_id, "platform_role": body.role}


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


@router.post("/users/{user_id}/status", summary="Set account status (audited, atomic)")
def set_status(user_id: int, body: StatusRequest, request: Request,
               principal=Depends(require_permission(perm.USERS_MANAGE)),
               accounts=Depends(get_account_repository)) -> dict:
    if body.status not in (ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_DEACTIVATED):
        raise HTTPException(status_code=422, detail="Unsupported status for admin change.")
    if user_id == principal.user_id and body.status != ACCOUNT_STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
    before = _current(accounts, user_id)
    if before is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    audit = A.build_audit(event_type=A.ADMIN_ACCOUNT_STATUS_CHANGE, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="user", target_id=user_id,
                          before=before.status, after=body.status, status=body.status)
    if not accounts.set_status(user_id, body.status, audit=audit):
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"user_id": user_id, "status": body.status}


@router.get("/workspaces", summary="Workspace metadata (no shared content)")
def list_workspaces(_p=Depends(require_permission(perm.WORKSPACES_READ)),
                    workspaces=Depends(get_workspace_repository)) -> dict:
    return {"workspaces": workspaces.list_workspaces_admin()}


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
