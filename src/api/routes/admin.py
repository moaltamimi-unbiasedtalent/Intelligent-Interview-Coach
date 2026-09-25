"""Platform Admin / Operations routes (Capstone P6.5).

PLATFORM_ADMIN-only (router-level gate). This is an OPERATIONS surface, not a data
superuser: it exposes account/workspace/entitlement/privacy/provider/audit METADATA and
performs audited privileged changes — it NEVER returns candidate-private content (CV,
answers, Memory, Story Bank, raw conversation, documents), has no "view as user" and no
private-data search. Owner-scoped repositories stay owner-scoped.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import (
    get_account_repository,
    get_audit_repository,
    get_current_principal,
    get_workspace_repository,
    require_platform_admin,
)
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    ACCOUNT_STATUS_DEACTIVATED,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLES,
    PRODUCT_TIERS,
)

router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(require_platform_admin)])


class RoleRequest(BaseModel):
    role: str = Field(max_length=32)


class TierRequest(BaseModel):
    tier: str = Field(max_length=32)


class StatusRequest(BaseModel):
    status: str = Field(max_length=32)


def _audit(audit, event_type, actor_id, target_user_id, **ctx):
    try:
        audit.record(event_type=event_type, actor_user_id=actor_id, target_type="user",
                     target_id=str(target_user_id),
                     context={k: v for k, v in ctx.items() if v is not None})
    except Exception:  # noqa: BLE001
        pass


@router.get("/home", summary="Operational overview (metadata only)")
def home(accounts=Depends(get_account_repository), workspaces=Depends(get_workspace_repository)) -> dict:
    from src.copilot.knowledge import governance as gov
    return {
        "accounts": accounts.account_stats(),
        "workspaces": workspaces.workspace_stats(),
        "knowledge": {"overall_readiness": gov.overall_readiness().get("overall")},
        "notes": "Operational metadata only. No candidate-private content is accessible here.",
    }


@router.get("/users", summary="Account metadata (never candidate content)")
def list_users(query: str | None = Query(default=None, max_length=320), limit: int = Query(default=100, ge=1, le=500),
               accounts=Depends(get_account_repository)) -> dict:
    return {"users": accounts.list_accounts(limit=limit, query=query)}


@router.post("/users/{user_id}/role", summary="Set platform role (audited)")
def set_role(user_id: int, body: RoleRequest, principal=Depends(get_current_principal),
             accounts=Depends(get_account_repository), audit=Depends(get_audit_repository)) -> dict:
    if body.role not in PLATFORM_ROLES:
        raise HTTPException(status_code=422, detail="Unknown platform role.")
    # Self-lockout guard: an admin may not demote their own admin role.
    if user_id == principal.user_id and body.role != PLATFORM_ROLE_ADMIN:
        raise HTTPException(status_code=409, detail="You cannot remove your own admin role.")
    if not accounts.set_platform_role(user_id, body.role):
        raise HTTPException(status_code=404, detail="Account not found.")
    _audit(audit, "admin.platform_role_change", principal.user_id, user_id, role=body.role)
    return {"user_id": user_id, "platform_role": body.role}


@router.post("/users/{user_id}/tier", summary="Set product entitlement tier (audited)")
def set_tier(user_id: int, body: TierRequest, principal=Depends(get_current_principal),
             accounts=Depends(get_account_repository), audit=Depends(get_audit_repository)) -> dict:
    if body.tier not in PRODUCT_TIERS:
        raise HTTPException(status_code=422, detail="Unknown tier.")
    if not accounts.set_tier(user_id, body.tier, source="admin"):
        raise HTTPException(status_code=404, detail="Account not found.")
    _audit(audit, "admin.entitlement_change", principal.user_id, user_id, tier=body.tier)
    return {"user_id": user_id, "tier": body.tier}


@router.post("/users/{user_id}/status", summary="Set account status (audited)")
def set_status(user_id: int, body: StatusRequest, principal=Depends(get_current_principal),
               accounts=Depends(get_account_repository), audit=Depends(get_audit_repository)) -> dict:
    if body.status not in (ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_DEACTIVATED):
        raise HTTPException(status_code=422, detail="Unsupported status for admin change.")
    if user_id == principal.user_id and body.status != ACCOUNT_STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
    if not accounts.set_status(user_id, body.status):
        raise HTTPException(status_code=404, detail="Account not found.")
    _audit(audit, "admin.account_status_change", principal.user_id, user_id, status=body.status)
    return {"user_id": user_id, "status": body.status}


@router.get("/workspaces", summary="Workspace metadata (no shared content)")
def list_workspaces(workspaces=Depends(get_workspace_repository)) -> dict:
    return {"workspaces": workspaces.list_workspaces_admin()}


@router.get("/privacy-requests", summary="Open privacy/deletion requests (metadata only)")
def privacy_requests(accounts=Depends(get_account_repository)) -> dict:
    return {
        "requests": accounts.list_privacy_requests(),
        "note": "Global hard-delete (private-file + agent checkpoint purge) remains PARTIAL; "
                "deletion is not falsely reported complete.",
    }


@router.get("/feedback", summary="Feedback taxonomy + aggregate counts (no raw content)")
def feedback_overview(accounts=Depends(get_account_repository)) -> dict:
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


@router.get("/providers", summary="Provider/system configuration status (no secrets)")
def providers() -> dict:
    import os

    def configured(*names: str) -> bool:
        return any(bool(os.environ.get(n, "").strip()) for n in names)

    try:
        import pytesseract  # noqa: F401
        ocr = "configured"
    except Exception:  # noqa: BLE001
        ocr = "not_configured"
    return {
        "google_oidc": {"configured": configured("GOOGLE_OIDC_CLIENT_ID", "GOOGLE_CLIENT_ID"),
                        "live_validation": "UNVALIDATED"},
        "email": {"provider": os.environ.get("EMAIL_PROVIDER", "console"),
                  "configured": configured("BREVO_API_KEY", "EMAIL_PROVIDER"),
                  "live_validation": "UNVALIDATED"},
        "speech": {
            "architecture": "browser_web_speech", "camera": "never_requested",
            "input": "browser_web_speech_stt",          # P3 dictation (STT)
            "output": "browser_speech_synthesis_tts",    # P7 voice playback (TTS)
            "audio_persisted_by_ask4mo": False,          # no recordings/voiceprints stored
            "voice_trait_inference": "none",             # no emotion/personality/accent/hiring signal
            "live_quality": "UNVALIDATED",
        },
        "ocr": {"status": ocr, "live_quality": "UNVALIDATED"},
        "adzuna": {"configured": configured("ADZUNA_APP_ID", "ADZUNA_APP_KEY"),
                   "live_validation": "UNVALIDATED"},
        "langfuse": {"configured": configured("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"),
                     "external_enabled": configured("AGENT_EXTERNAL_OBSERVABILITY_ENABLED")},
        "note": "Booleans/status only — no API keys, secrets, tokens or connection strings.",
    }


@router.get("/audit", summary="Recent audit events (safe metadata)")
def audit_view(event_type: str | None = Query(default=None, max_length=64),
               limit: int = Query(default=100, ge=1, le=500),
               audit=Depends(get_audit_repository)) -> dict:
    return {"events": audit.recent(limit=limit, event_type=event_type)}
