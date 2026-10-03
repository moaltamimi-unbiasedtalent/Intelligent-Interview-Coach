"""Admin privacy requests and preparation-data operations (P10B-W10.10). Every route declares an explicit permission.

PRIVACY ADMIN IS NOT A CONTENT SUPERUSER. Nothing here renders a candidate's CV, documents, answers, preparation chats, Mo conversations,
memories or evidence; the request detail shows safe account metadata, the bounded note the candidate wrote, state and job links.
There is no admin export/download of candidate data: the candidate's own export stays self-service. Account deletion is executed by a
W10.9 job that calls the SAME ``AccountDeletionService`` candidates use: there is no separate admin deletion engine.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from src.api.dependencies import (
    get_audit_repository, get_job_service, get_legal_service, get_privacy_request_service, get_repository, get_request_id,
    require_permission,
)
from src.api.schemas.admin import (
    PrivacyAssignRequest, PrivacyRecordRequest, PrivacyRequestDetail, PrivacyRequestPage, PrivacyStatusRequest,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import AuditEvent, User
from src.privacy import policy as P
from src.privacy.preparation import PreparationRunIndex
from src.privacy.requests import PrivacyConflict, PrivacyNotFound, PrivacyValidationError

router = APIRouter(prefix="/admin/privacy", tags=["admin-privacy"])


def _guard(fn):
    try:
        return fn()
    except PrivacyNotFound:
        raise HTTPException(status_code=404, detail="Not found.")
    except PrivacyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PrivacyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _audit(request: Request, principal, event: str, target: str | None = None) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="privacy_request", target_id=target)


@router.get("/requests", response_model=PrivacyRequestPage, summary="Privacy request queue (server-side filters, pagination)")
def list_requests(status: str | None = None, request_type: str | None = None, assignee: str | None = Query(default=None, max_length=12),
                  q: str | None = Query(default=None, max_length=120), page: int = Query(default=1, ge=1),
                  page_size: int = Query(default=25, ge=1, le=100), principal=Depends(require_permission(perm.PRIVACY_READ)),
                  svc=Depends(get_privacy_request_service)) -> PrivacyRequestPage:
    return PrivacyRequestPage(**_guard(lambda: svc.list(status=status, request_type=request_type, assignee=assignee, q=q, page=page,
                                                       page_size=page_size, actor_user_id=principal.user_id)))


@router.get("/requests/{public_id}", response_model=PrivacyRequestDetail, summary="One request: safe candidate metadata, state, jobs, audit")
def request_detail(public_id: str, _p=Depends(require_permission(perm.PRIVACY_READ)), svc=Depends(get_privacy_request_service),
                   legal=Depends(get_legal_service), audit=Depends(get_audit_repository)) -> PrivacyRequestDetail:
    d = _guard(lambda: svc.detail(public_id[:40]))
    legal_rows: list = []
    if d["user_id"]:
        legal_rows = [{"document": x["code"], "current_version": x["current_version"], "accepted_current": x["accepted_current"],
                       "last_accepted_at": (x["last_acceptance"] or {}).get("accepted_at")} for x in legal.for_user(d["user_id"])["documents"]]
    with audit._session_factory() as s:
        rows = s.scalars(select(AuditEvent).where(AuditEvent.target_type == "privacy_request", AuditEvent.target_id == public_id,
                                                  AuditEvent.event_type.like("admin.%"))
                         .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(20)).all()
        events = [{"event_type": e.event_type, "result": e.result, "actor_user_id": e.actor_user_id, "request_id": e.request_id,
                   "created_at": e.created_at.isoformat() if e.created_at else None, "context": e.context} for e in rows]
    return PrivacyRequestDetail(**d, legal=legal_rows, audit=events)


@router.post("/requests", response_model=PrivacyRequestDetail, status_code=201,
             summary="Record a request received through another channel (human process) for an account")
def record_request(body: PrivacyRecordRequest, request: Request, principal=Depends(require_permission(perm.PRIVACY_EXECUTE)),
                   svc=Depends(get_privacy_request_service), repo=Depends(get_repository), legal=Depends(get_legal_service)):
    with repo.session_factory() as s:
        ref = body.account.strip()
        user = s.get(User, int(ref)) if ref.isdigit() else s.scalar(select(User).where(User.email == ref.lower()))
        if user is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        uid = user.id
    created = _guard(lambda: svc.create(uid, body.request_type, body.note, source="admin_recorded", created_by_user_id=principal.user_id,
                                        audit=_audit(request, principal, A.ADMIN_PRIVACY_REQUEST_RECORDED)))
    return PrivacyRequestDetail(**svc.detail(created["public_id"]), legal=[], audit=[])


@router.post("/requests/{public_id}/assign", response_model=PrivacyRequestDetail, summary="Assign or unassign a request")
def assign(public_id: str, body: PrivacyAssignRequest, request: Request, principal=Depends(require_permission(perm.PRIVACY_EXECUTE)),
           svc=Depends(get_privacy_request_service)):
    return PrivacyRequestDetail(**_guard(lambda: svc.assign(public_id[:40], body.assignee_user_id,
                                                           audit=_audit(request, principal, A.ADMIN_PRIVACY_REQUEST_ASSIGNED, public_id))),
                                legal=[], audit=[])


@router.post("/requests/{public_id}/status", response_model=PrivacyRequestDetail, summary="Move a request to a valid next status")
def set_status(public_id: str, body: PrivacyStatusRequest, request: Request, principal=Depends(require_permission(perm.PRIVACY_EXECUTE)),
               svc=Depends(get_privacy_request_service)):
    return PrivacyRequestDetail(**_guard(lambda: svc.set_status(
        public_id[:40], body.status, result_category=body.result_category,
        audit=_audit(request, principal, A.ADMIN_PRIVACY_REQUEST_STATUS_CHANGED, public_id))), legal=[], audit=[])


@router.post("/requests/{public_id}/execute-deletion", response_model=PrivacyRequestDetail,
             summary="Queue the SAME account deletion candidates use (a W10.9 job); completes the request only when everything is removed")
def execute_deletion(public_id: str, request: Request, principal=Depends(require_permission(perm.PRIVACY_EXECUTE)),
                     svc=Depends(get_privacy_request_service), jobs=Depends(get_job_service)):
    d = _guard(lambda: svc.detail(public_id[:40]))
    if not d["can_execute_deletion"]:
        raise HTTPException(status_code=409, detail="This request cannot be executed as a deletion.")
    if d["status"] == "acknowledged":
        _guard(lambda: svc.set_status(public_id, "in_progress", audit=_audit(request, principal, A.ADMIN_PRIVACY_DELETION_INITIATED, public_id)))
    view, _ = jobs.enqueue(P.JOB_ACCOUNT_DELETE, {"request_id": public_id}, idempotency_key=f"privdel:{public_id}", actor_user_id=principal.user_id)
    svc.link_job(public_id, view["public_id"])
    return PrivacyRequestDetail(**svc.detail(public_id), legal=[], audit=[])


@router.get("/preparation", summary="Preparation-run index coverage (counts only; no chat content)")
def preparation_coverage(_p=Depends(require_permission(perm.PRIVACY_READ)), repo=Depends(get_repository)) -> dict:
    return PreparationRunIndex(repo.session_factory).coverage()


@router.post("/preparation/backfill", status_code=202, summary="Queue a bounded job that indexes historical runs from relational references")
def backfill(request: Request, principal=Depends(require_permission(perm.PRIVACY_EXECUTE)), jobs=Depends(get_job_service),
            audit_repo=Depends(get_audit_repository)) -> dict:
    spec = A.build_audit(event_type=A.ADMIN_PRIVACY_BACKFILL_REQUESTED, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="preparation_runs", target_id="backfill")
    view, created = jobs.enqueue(P.JOB_BACKFILL, {"after_id": 0}, idempotency_key="backfill:0", actor_user_id=principal.user_id, audit=spec)
    return {"job_id": view["public_id"], "created": created}
