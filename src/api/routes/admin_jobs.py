"""Admin jobs, queues and operational diagnostics (P10B-W10.9). Every route declares an explicit permission.

The Admin API can only enqueue CODE-DEFINED job types with a schema-validated payload, retry a failed job, or cancel a
queued one. It cannot edit a payload, change a type or handler, force a state, or read a raw payload: the only payload
view is the type's own safe summary. The API process never executes jobs (a separate worker does).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from src.api.dependencies import get_audit_repository, get_job_service, get_request_id, require_permission
from src.api.schemas.admin import (
    JobDetail, JobEnqueueRequest, JobEnqueueResult, JobList, JobRow, JobTypeInfo,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.jobs.service import JobNotFound, JobStateConflict, JobValidationError
from src.persistence import AuditEvent

router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


def _found(fn):
    try:
        return fn()
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found.")


@router.get("", response_model=JobList, summary="Job queue (server-side filters and pagination)")
def list_jobs(state: str | None = None, job_type: str | None = None, priority: str | None = None,
              q: str | None = Query(default=None, max_length=64), page: int = Query(default=1, ge=1),
              page_size: int = Query(default=25, ge=1, le=100),
              _p=Depends(require_permission(perm.JOBS_READ)), jobs=Depends(get_job_service)) -> JobList:
    try:
        return JobList(**jobs.list(state=state, job_type=job_type, priority=priority, q=q, page=page,
                                   page_size=page_size))
    except JobValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/diagnostics", summary="Queue and worker diagnostics (counts and ages only)")
def diagnostics(_p=Depends(require_permission(perm.JOBS_READ)), jobs=Depends(get_job_service)) -> dict:
    return jobs.stats()


@router.get("/types", response_model=list[JobTypeInfo], summary="The code-defined job types")
def job_types(_p=Depends(require_permission(perm.JOBS_READ)), jobs=Depends(get_job_service)) -> list[JobTypeInfo]:
    return [JobTypeInfo(job_type=d.code, label=d.label, max_attempts=d.max_attempts, manual_retry=d.manual_retry,
                        cancellable_when_queued=d.cancellable_when_queued, idempotency=d.idempotency)
            for d in jobs._registry.values()]


@router.get("/{public_id}", response_model=JobDetail, summary="One job (safe summary; never a raw payload)")
def job_detail(public_id: str, _p=Depends(require_permission(perm.JOBS_READ)), jobs=Depends(get_job_service),
               audit=Depends(get_audit_repository)) -> JobDetail:
    d = _found(lambda: jobs.get(public_id))
    with audit._session_factory() as s:
        rows = s.scalars(select(AuditEvent).where(
            AuditEvent.target_type == "job", AuditEvent.target_id == public_id,
            AuditEvent.event_type.like("admin.%")).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(15)).all()
        events = [{"event_type": e.event_type, "result": e.result, "actor_user_id": e.actor_user_id,
                   "request_id": e.request_id, "created_at": e.created_at.isoformat() if e.created_at else None,
                   "context": e.context} for e in rows]
    return JobDetail(**d, audit=events)


@router.post("", response_model=JobEnqueueResult, status_code=201,
             summary="Enqueue a code-defined job type with a validated payload")
def enqueue(body: JobEnqueueRequest, request: Request, principal=Depends(require_permission(perm.JOBS_MANAGE)),
            jobs=Depends(get_job_service)) -> JobEnqueueResult:
    try:
        defn = jobs.definition(body.job_type)
    except JobValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not defn.admin_enqueue:
        raise HTTPException(status_code=422, detail="This job type cannot be enqueued from Admin.")
    if defn.requires_permission and defn.requires_permission not in perm.permissions_for_role(principal.platform_role):
        raise HTTPException(status_code=403, detail="Permission denied.")
    audit = A.build_audit(event_type=A.ADMIN_JOB_ENQUEUED, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="job")
    try:
        view, created = jobs.enqueue(body.job_type, body.payload, idempotency_key=body.dedupe_id,
                                     priority=body.priority, actor_user_id=principal.user_id,
                                     audit=audit)
    except JobValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JobEnqueueResult(job=JobRow(**view), created=created)


def _act(request: Request, principal, event: str, public_id: str) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="job", target_id=public_id)


@router.post("/{public_id}/retry", response_model=JobRow, summary="Retry a failed job (same job, explicit action)")
def retry(public_id: str, request: Request, principal=Depends(require_permission(perm.JOBS_MANAGE)),
          jobs=Depends(get_job_service)) -> JobRow:
    try:
        return JobRow(**_found(lambda: jobs.retry(public_id, audit=_act(request, principal, A.ADMIN_JOB_RETRY_REQUESTED, public_id))))
    except JobStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{public_id}/cancel", response_model=JobRow, summary="Cancel a QUEUED job (running jobs cannot be cancelled)")
def cancel(public_id: str, request: Request, principal=Depends(require_permission(perm.JOBS_MANAGE)),
           jobs=Depends(get_job_service)) -> JobRow:
    try:
        return JobRow(**_found(lambda: jobs.cancel(public_id, audit=_act(request, principal, A.ADMIN_JOB_CANCELLED, public_id))))
    except JobStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
