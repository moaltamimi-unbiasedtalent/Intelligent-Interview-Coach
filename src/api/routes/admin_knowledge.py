"""Admin knowledge base and RAG administration (P10B-W10.8). Every route declares an explicit permission.

PLATFORM knowledge only: this is not a browser for candidate CVs, answers, chats, memories or support tickets, and there is no
raw vector-store or chunk browser. The only content view is a bounded extracted-text preview of the version under review.
Approval happens BEFORE indexing; indexing happens before activation; only activation makes content candidate-retrievable.
No route fetches a URL (a source URL is a reference string only).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import select

from src.api.dependencies import get_audit_repository, get_knowledge_admin_service, get_request_id, require_permission
from src.api.schemas.admin import (
    KnowledgeList, KnowledgeMeta, KnowledgeMetaUpdate, KnowledgeRejectRequest, KnowledgeSourceDetail, KnowledgeVersionDetail,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.knowledge_admin import policy as P
from src.knowledge_admin.service import (
    KnowledgeBlocked, KnowledgeConflict, KnowledgeDuplicate, KnowledgeNotFound, KnowledgeValidationError,
)
from src.persistence import AuditEvent

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


def _guard(fn):
    try:
        return fn()
    except KnowledgeNotFound:
        raise HTTPException(status_code=404, detail="Not found.")
    except KnowledgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except KnowledgeBlocked as exc:
        raise HTTPException(status_code=409, detail="Blocked: " + " ".join(exc.blockers))
    except KnowledgeDuplicate as exc:
        raise HTTPException(status_code=409, detail=f"This exact file is already version {exc.existing_public_id} of this source.")
    except KnowledgeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _audit(request: Request, principal, event: str, target: str | None = None) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="knowledge_version", target_id=target)


async def _read(file: UploadFile) -> bytes:
    data = await file.read(P.MAX_UPLOAD_BYTES + 1)       # bounded read: an oversize body is never buffered whole
    return data


@router.get("/meta", response_model=KnowledgeMeta, summary="Static governance vocabulary (authority meanings, licences, upload policy)")
def meta(_p=Depends(require_permission(perm.KNOWLEDGE_READ))) -> KnowledgeMeta:
    return KnowledgeMeta(
        languages=list(P.KB_LANGUAGES),
        authority_levels=[{"level": k, "meaning": v} for k, v in P.AUTHORITY_MEANING.items()],
        licence_classes=[{"code": c, "label": P.LICENCE_LABEL[c], "activatable": c in P.ACTIVATABLE_LICENCES} for c in P.LICENCE_CLASSES],
        states=list(P.STATES), rejection_reasons=list(P.REJECTION_REASONS),
        upload={"max_bytes": P.MAX_UPLOAD_BYTES, "extensions": sorted(P.ALLOWED_EXTENSIONS), "preview_chars": P.PREVIEW_CHARS})


@router.get("/sources", response_model=KnowledgeList, summary="Sources with their current version (server-side filters, pagination)")
def list_sources(state: str | None = None, language: str | None = None, authority: int | None = Query(default=None, ge=1, le=3),
                 licence: str | None = None, active: bool | None = None, q: str | None = Query(default=None, max_length=80),
                 page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                 _p=Depends(require_permission(perm.KNOWLEDGE_READ)), svc=Depends(get_knowledge_admin_service)) -> KnowledgeList:
    return KnowledgeList(**_guard(lambda: svc.list_sources(state=state, language=language, authority=authority, licence=licence,
                                                          active=active, q=q, page=page, page_size=page_size)))


@router.get("/sources/{source_id}", response_model=KnowledgeSourceDetail, summary="One source and its versions")
def source_detail(source_id: str, _p=Depends(require_permission(perm.KNOWLEDGE_READ)),
                  svc=Depends(get_knowledge_admin_service)) -> KnowledgeSourceDetail:
    return KnowledgeSourceDetail(**_guard(lambda: svc.source_detail(source_id)))


@router.get("/versions/{version_id}", response_model=KnowledgeVersionDetail,
            summary="One version: provenance, checks, bounded preview, index and approval state")
def version_detail(version_id: str, _p=Depends(require_permission(perm.KNOWLEDGE_READ)),
                   svc=Depends(get_knowledge_admin_service), audit=Depends(get_audit_repository)) -> KnowledgeVersionDetail:
    d = _guard(lambda: svc.version_detail(version_id))
    with audit._session_factory() as s:
        rows = s.scalars(select(AuditEvent).where(AuditEvent.target_type == "knowledge_version", AuditEvent.target_id == version_id,
                                                  AuditEvent.event_type.like("admin.%"))
                         .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(20)).all()
        events = [{"event_type": e.event_type, "result": e.result, "actor_user_id": e.actor_user_id, "request_id": e.request_id,
                   "created_at": e.created_at.isoformat() if e.created_at else None, "context": e.context} for e in rows]
    return KnowledgeVersionDetail(**d, audit=events)


@router.post("/sources", status_code=201, summary="Register a new source from an uploaded file (queues scan and parsing)")
async def create_source(request: Request, title: str = Form(...), language: str = Form(...), authority_level: int = Form(...),
                        publisher: str = Form(""), source_url: str = Form(""), provenance_note: str = Form(""),
                        licence_class: str = Form("unclear"), file: UploadFile = File(...),
                        principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)), svc=Depends(get_knowledge_admin_service)) -> dict:
    data = await _read(file)
    return _guard(lambda: svc.create_source(
        title=title, filename=file.filename or "", data=data, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_KNOWLEDGE_VERSION_UPLOADED), language=language, authority_level=authority_level,
        publisher=publisher, source_url=source_url or None, provenance_note=provenance_note, licence_class=licence_class))


@router.post("/sources/{source_id}/versions", status_code=201, summary="Upload a NEW immutable version of an existing source")
async def add_version(source_id: str, request: Request, language: str = Form(...), authority_level: int = Form(...),
                      publisher: str = Form(""), source_url: str = Form(""), provenance_note: str = Form(""),
                      licence_class: str = Form("unclear"), file: UploadFile = File(...),
                      principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)), svc=Depends(get_knowledge_admin_service)) -> dict:
    data = await _read(file)
    return _guard(lambda: svc.add_version(
        source_id, filename=file.filename or "", data=data, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_KNOWLEDGE_VERSION_UPLOADED), language=language, authority_level=authority_level,
        publisher=publisher, source_url=source_url or None, provenance_note=provenance_note, licence_class=licence_class))


@router.patch("/versions/{version_id}", response_model=KnowledgeVersionDetail,
              summary="Correct governance metadata BEFORE approval (frozen afterwards; upload a new version to change it)")
def update_version(version_id: str, body: KnowledgeMetaUpdate, request: Request,
                   principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)), svc=Depends(get_knowledge_admin_service)):
    d = _guard(lambda: svc.update_metadata(version_id, audit=_audit(request, principal, A.ADMIN_KNOWLEDGE_VERSION_UPDATED, version_id),
                                           language=body.language, authority_level=body.authority_level, publisher=body.publisher,
                                           source_url=body.source_reference, provenance_note=body.provenance_note, licence_class=body.licence_class))
    return KnowledgeVersionDetail(**d, audit=[])


def _act(version_id, request, principal, event, fn):
    return KnowledgeVersionDetail(**_guard(lambda: fn(version_id, actor_user_id=principal.user_id,
                                                      audit=_audit(request, principal, event, version_id))), audit=[])


@router.post("/versions/{version_id}/approve", response_model=KnowledgeVersionDetail,
             summary="Approve (human decision) a parsed version; does NOT index or activate it")
def approve(version_id: str, request: Request, principal=Depends(require_permission(perm.KNOWLEDGE_APPROVE)),
            svc=Depends(get_knowledge_admin_service)):
    return _act(version_id, request, principal, A.ADMIN_KNOWLEDGE_VERSION_APPROVED, svc.approve)


@router.post("/versions/{version_id}/reject", response_model=KnowledgeVersionDetail, summary="Reject a version with a reason category")
def reject(version_id: str, body: KnowledgeRejectRequest, request: Request,
           principal=Depends(require_permission(perm.KNOWLEDGE_APPROVE)), svc=Depends(get_knowledge_admin_service)):
    return KnowledgeVersionDetail(**_guard(lambda: svc.reject(version_id, reason=body.reason, actor_user_id=principal.user_id,
                                                              audit=_audit(request, principal, A.ADMIN_KNOWLEDGE_VERSION_REJECTED, version_id))), audit=[])


@router.post("/versions/{version_id}/index", response_model=KnowledgeVersionDetail,
             summary="Queue indexing of an APPROVED version (a W10.9 job); does not activate it")
def index(version_id: str, request: Request, principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)),
          svc=Depends(get_knowledge_admin_service)):
    return _act(version_id, request, principal, A.ADMIN_KNOWLEDGE_INDEX_REQUESTED, svc.request_index)


@router.post("/versions/{version_id}/activate", response_model=KnowledgeVersionDetail,
             summary="Activate an approved, indexed version for candidate retrieval (retires the previous active version)")
def activate(version_id: str, request: Request, principal=Depends(require_permission(perm.KNOWLEDGE_APPROVE)),
             svc=Depends(get_knowledge_admin_service)):
    return _act(version_id, request, principal, A.ADMIN_KNOWLEDGE_VERSION_ACTIVATED, svc.activate)


@router.post("/versions/{version_id}/retire", response_model=KnowledgeVersionDetail,
             summary="Retire from candidate retrieval immediately; vector removal follows as a job")
def retire(version_id: str, request: Request, principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)),
           svc=Depends(get_knowledge_admin_service)):
    return _act(version_id, request, principal, A.ADMIN_KNOWLEDGE_VERSION_RETIRED, svc.retire)


@router.post("/versions/{version_id}/reprocess", response_model=KnowledgeVersionDetail, summary="Re-queue a FAILED version at its failed stage")
def reprocess(version_id: str, request: Request, principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)),
              svc=Depends(get_knowledge_admin_service)):
    return _act(version_id, request, principal, A.ADMIN_KNOWLEDGE_REPROCESS_REQUESTED, svc.reprocess)


@router.delete("/versions/{version_id}", summary="Hard-delete a NEVER-approved version and its file (approved history is retired instead)")
def delete(version_id: str, request: Request, principal=Depends(require_permission(perm.KNOWLEDGE_MANAGE)),
           svc=Depends(get_knowledge_admin_service)) -> dict:
    return _guard(lambda: svc.delete_version(version_id, audit=_audit(request, principal, A.ADMIN_KNOWLEDGE_VERSION_DELETED, version_id)))
