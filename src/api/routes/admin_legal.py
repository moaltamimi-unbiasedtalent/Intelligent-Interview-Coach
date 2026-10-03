"""Admin legal document registry (P10B-W10.10). Reads use ``platform.privacy.read`` (the canonical registry has no separate legal-read
permission); changes need ``platform.legal.manage``. Published versions are immutable; new text is a new version. There is no rich-text
editor, no delete, and no compliance score."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_legal_service, get_request_id, require_permission
from src.api.schemas.admin import LegalDraftRequest, LegalDraftUpdate, LegalOverview, LegalVersionRow
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.privacy.legal import LegalConflict, LegalNotFound, LegalValidationError

router = APIRouter(prefix="/admin/legal", tags=["admin-legal"])


def _guard(fn):
    try:
        return fn()
    except LegalNotFound:
        raise HTTPException(status_code=404, detail="Not found.")
    except LegalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LegalConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="The effective date must be an ISO date or date-time.")


def _audit(request: Request, principal, event: str) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="legal_version")


@router.get("", response_model=LegalOverview, summary="Legal documents, versions, current version and RECORDED acceptance counts")
def overview(_p=Depends(require_permission(perm.PRIVACY_READ)), legal=Depends(get_legal_service)) -> LegalOverview:
    return LegalOverview(**legal.admin_overview())


@router.post("/{code}/versions", response_model=LegalVersionRow, status_code=201, summary="Register a DRAFT version of a document")
def create_draft(code: str, body: LegalDraftRequest, request: Request, principal=Depends(require_permission(perm.LEGAL_MANAGE)),
                 legal=Depends(get_legal_service)) -> LegalVersionRow:
    return LegalVersionRow(**_guard(lambda: legal.create_draft(
        code[:24], version=body.version, content_ref=body.content_ref, content_hash=body.content_hash, effective_at=_when(body.effective_at),
        actor_user_id=principal.user_id, audit=_audit(request, principal, A.ADMIN_LEGAL_VERSION_CREATED))))


@router.patch("/versions/{version_id}", response_model=LegalVersionRow, summary="Edit a DRAFT version (published versions are immutable)")
def update_draft(version_id: int, body: LegalDraftUpdate, request: Request, principal=Depends(require_permission(perm.LEGAL_MANAGE)),
                 legal=Depends(get_legal_service)) -> LegalVersionRow:
    return LegalVersionRow(**_guard(lambda: legal.update_draft(
        version_id, content_ref=body.content_ref, content_hash=body.content_hash, effective_at=_when(body.effective_at),
        audit=_audit(request, principal, A.ADMIN_LEGAL_VERSION_UPDATED))))


@router.post("/versions/{version_id}/publish", response_model=LegalVersionRow,
             summary="Publish a draft (immutable afterwards; becomes the current version and retires the previous one)")
def publish(version_id: int, request: Request, principal=Depends(require_permission(perm.LEGAL_MANAGE)),
            legal=Depends(get_legal_service)) -> LegalVersionRow:
    return LegalVersionRow(**_guard(lambda: legal.publish(version_id, actor_user_id=principal.user_id,
                                                          audit=_audit(request, principal, A.ADMIN_LEGAL_VERSION_PUBLISHED))))
