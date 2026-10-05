"""Admin security, audit, incidents, alerts, step-up and role-change routes (P10B-W10.13). Every route declares an explicit canonical permission.

Security administration is NOT private-candidate-data access: nothing here returns a CV, answer, chat, memory, document, prompt, support-ticket body, email, IP address
or user agent. There is no break-glass and no impersonation. Role changes are two-person (request, then a DIFFERENT Admin approves) and require a recent password
confirmation (step-up) from both humans; step-up is password re-authentication, not MFA.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.admin_repository import AdminNotFound
from src.api.dependencies import (
    _session_cookie_name, get_admin_user_repository, get_audit_repository, get_repository, get_request_id, require_permission,
)
from src.api.rate_limit import enforce, user_key
from src.api.schemas.admin import SecurityEventPage
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.admin_security import definitions as D
from src.admin_security.alerts import AlertService
from src.admin_security.events import SecurityEventService
from src.admin_security.incidents import IncidentService
from src.admin_security.role_changes import RoleChangeService
from src.admin_security.stepup import StepUpService

router = APIRouter(prefix="/admin", tags=["admin-security"])


def _sf(repo=Depends(get_repository)):
    return repo.session_factory


def _guard(fn):
    try:
        return fn()
    except AdminNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _token(request: Request) -> str | None:
    return request.cookies.get(_session_cookie_name(request))


def _audit(request: Request, principal, event: str, target_type: str, target: str | None = None, **ctx) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type=target_type,
                         target_id=target, **ctx)


class Revision(BaseModel):
    expected_revision: int = Field(ge=0)


# ------------------------------------------------------------------ security events / summary ----------------------------------------------
@router.get("/security/events", response_model=SecurityEventPage, summary="Security events: typed projection of audit rows (safe metadata only)")
def security_events(category: str | None = Query(default=None, max_length=24), severity: str | None = Query(default=None, max_length=12),
                    result: str | None = Query(default=None, max_length=32), period: str = Query(default="7d", max_length=8),
                    request_id: str | None = Query(default=None, max_length=64), page: int = Query(default=1, ge=1, le=100000),
                    page_size: int = Query(default=25, ge=1, le=100), _p=Depends(require_permission(perm.SECURITY_READ)),
                    sf=Depends(_sf)) -> SecurityEventPage:
    out = SecurityEventService(sf).events(category=category, severity=severity, result=result, period=period, request_id=request_id,
                                          page=page, page_size=page_size)
    out.pop("advanced_anomaly_detection", None)
    return SecurityEventPage(**out)


@router.get("/security/summary", summary="Safe counts for the Command Center and Security landing")
def security_summary(_p=Depends(require_permission(perm.SECURITY_READ)), sf=Depends(_sf)) -> dict:
    return {"alerts": AlertService(sf).summary(), "open_incidents": IncidentService(sf).open_count(),
            "pending_role_changes": RoleChangeService(sf).pending_count(), "categories": list(D.SECURITY_CATEGORIES),
            "anomaly_rules": ["authentication_failure_burst", "admin_access_denied_burst"], "advanced_anomaly_detection": False}


# ------------------------------------------------------------------ alerts ------------------------------------------------------------------
@router.get("/security/alerts", summary="Durable in-app alerts (read)")
def alerts(state: str | None = Query(default=None, max_length=14), severity: str | None = Query(default=None, max_length=12),
           page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=25, ge=1, le=100),
           _p=Depends(require_permission(perm.SECURITY_READ)), sf=Depends(_sf)) -> dict:
    return AlertService(sf).list(state=state, severity=severity, page=page, page_size=page_size)


@router.post("/security/alerts/{public_id}/acknowledge", summary="Acknowledge an alert (audited, atomic, revision-checked)")
def ack_alert(public_id: str, body: Revision, request: Request, principal=Depends(require_permission(perm.SECURITY_MANAGE)), sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.SECURITY_ALERT_ACKNOWLEDGED, "alert", public_id[:32])
    return _guard(lambda: AlertService(sf).acknowledge(public_id[:32], expected_revision=body.expected_revision, actor_user_id=principal.user_id, audit=audit))


@router.post("/security/alerts/{public_id}/resolve", summary="Resolve an alert (audited, atomic, revision-checked)")
def resolve_alert(public_id: str, body: Revision, request: Request, principal=Depends(require_permission(perm.SECURITY_MANAGE)), sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.SECURITY_ALERT_RESOLVED, "alert", public_id[:32])
    return _guard(lambda: AlertService(sf).resolve(public_id[:32], expected_revision=body.expected_revision, actor_user_id=principal.user_id, audit=audit))


# ------------------------------------------------------------------ incidents ----------------------------------------------------------------
class IncidentCreate(BaseModel):
    title: str = Field(max_length=D.MAX_TITLE)
    severity: str = Field(max_length=12)
    affected_service: str = Field(max_length=24)
    owner_admin_user_id: int | None = Field(default=None, ge=1)
    affected_user_estimate: int | None = Field(default=None, ge=0, le=100_000_000)


class IncidentUpdate(Revision):
    title: str | None = Field(default=None, max_length=D.MAX_TITLE)
    severity: str | None = Field(default=None, max_length=12)
    affected_service: str | None = Field(default=None, max_length=24)
    owner_admin_user_id: int | None = Field(default=None, ge=1)
    affected_user_estimate: int | None = Field(default=None, ge=0, le=100_000_000)
    root_cause: str | None = Field(default=None, max_length=D.MAX_NARRATIVE)
    remediation: str | None = Field(default=None, max_length=D.MAX_NARRATIVE)


class IncidentStatus(Revision):
    status: str = Field(max_length=16)


class IncidentTicketBody(Revision):
    ticket_public_id: str = Field(min_length=1, max_length=32)


@router.get("/security/incidents", summary="Incidents (internal operational metadata)")
def incidents(status: str | None = Query(default=None, max_length=16), severity: str | None = Query(default=None, max_length=12),
              service: str | None = Query(default=None, max_length=24), page: int = Query(default=1, ge=1, le=100000),
              page_size: int = Query(default=25, ge=1, le=100), _p=Depends(require_permission(perm.SECURITY_READ)), sf=Depends(_sf)) -> dict:
    return IncidentService(sf).list(status=status, severity=severity, service=service, page=page, page_size=page_size)


@router.get("/security/incidents/{public_id}", summary="Incident detail with append-only history and linked ticket identifiers")
def incident_detail(public_id: str, _p=Depends(require_permission(perm.SECURITY_READ)), sf=Depends(_sf)) -> dict:
    return _guard(lambda: IncidentService(sf).detail(public_id[:32]))


@router.post("/security/incidents", summary="Create an incident (audited, atomic)")
def create_incident(body: IncidentCreate, request: Request, principal=Depends(require_permission(perm.INCIDENTS_MANAGE)), sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.SECURITY_INCIDENT_CREATED, "incident")
    return IncidentService(sf).create(title=body.title, severity=body.severity, affected_service=body.affected_service, actor_user_id=principal.user_id,
                                      request_id=get_request_id(request), audit=audit, owner_admin_user_id=body.owner_admin_user_id,
                                      affected_user_estimate=body.affected_user_estimate)


@router.post("/security/incidents/{public_id}/update", summary="Update an incident's fields (audited, atomic, revision-checked)")
def update_incident(public_id: str, body: IncidentUpdate, request: Request, principal=Depends(require_permission(perm.INCIDENTS_MANAGE)),
                    sf=Depends(_sf)) -> dict:
    changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
    audit = _audit(request, principal, A.SECURITY_INCIDENT_UPDATED, "incident", public_id[:32])
    return _guard(lambda: IncidentService(sf).update(public_id[:32], expected_revision=body.expected_revision, changes=changes,
                                                     actor_user_id=principal.user_id, request_id=get_request_id(request), audit=audit))


@router.post("/security/incidents/{public_id}/status", summary="Change an incident's status along a code-defined lifecycle (audited, atomic)")
def incident_status(public_id: str, body: IncidentStatus, request: Request, principal=Depends(require_permission(perm.INCIDENTS_MANAGE)),
                    sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.SECURITY_INCIDENT_STATUS_CHANGED, "incident", public_id[:32])
    return _guard(lambda: IncidentService(sf).change_status(public_id[:32], expected_revision=body.expected_revision, new_status=body.status,
                                                            actor_user_id=principal.user_id, request_id=get_request_id(request), audit=audit))


@router.post("/security/incidents/{public_id}/tickets/link", summary="Link a support ticket by identifier only (audited, atomic)")
def link_ticket(public_id: str, body: IncidentTicketBody, request: Request, principal=Depends(require_permission(perm.INCIDENTS_MANAGE)),
                sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.SECURITY_INCIDENT_TICKET_LINKED, "incident", public_id[:32])
    return _guard(lambda: IncidentService(sf).link_ticket(public_id[:32], body.ticket_public_id, expected_revision=body.expected_revision,
                                                          actor_user_id=principal.user_id, request_id=get_request_id(request), audit=audit))


@router.post("/security/incidents/{public_id}/tickets/unlink", summary="Remove a ticket link (audited, atomic)")
def unlink_ticket(public_id: str, body: IncidentTicketBody, request: Request, principal=Depends(require_permission(perm.INCIDENTS_MANAGE)),
                  sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.SECURITY_INCIDENT_TICKET_UNLINKED, "incident", public_id[:32])
    return _guard(lambda: IncidentService(sf).unlink_ticket(public_id[:32], body.ticket_public_id, expected_revision=body.expected_revision,
                                                            actor_user_id=principal.user_id, request_id=get_request_id(request), audit=audit))


# ------------------------------------------------------------------ audit browse / export ---------------------------------------------------
@router.get("/audit", summary="Audit events: bounded, filtered, paginated safe metadata (global view; no candidate content)")
def audit_view(event_type: str | None = Query(default=None, max_length=64), area: str | None = Query(default=None, max_length=12),
               result: str | None = Query(default=None, max_length=32), actor_user_id: int | None = Query(default=None, ge=1),
               target_type: str | None = Query(default=None, max_length=64), request_id: str | None = Query(default=None, max_length=64),
               period: str = Query(default="all", max_length=8), page: int = Query(default=1, ge=1, le=100000),
               page_size: int = Query(default=50, ge=1, le=100), limit: int | None = Query(default=None, ge=1, le=100),
               _p=Depends(require_permission(perm.AUDIT_READ)), sf=Depends(_sf)) -> dict:
    out = SecurityEventService(sf).browse(event_type=event_type, area=area, result=result, actor_user_id=actor_user_id, target_type=target_type,
                                          request_id=request_id, period=period, page=page, page_size=limit or page_size)
    return {**out, "events": out["items"]}


class AuditExport(BaseModel):
    format: str = Field(max_length=8)
    period: str = Field(max_length=8)
    reason: str = Field(min_length=D.EXPORT_MIN_REASON, max_length=200)
    event_type: str | None = Field(default=None, max_length=64)
    area: str | None = Field(default=None, max_length=12)
    result: str | None = Field(default=None, max_length=32)
    actor_user_id: int | None = Field(default=None, ge=1)
    target_type: str | None = Field(default=None, max_length=64)
    request_id: str | None = Field(default=None, max_length=64)


@router.post("/audit/export", summary="Bounded audit export (separate permission; reason required; the export itself is audited)")
def audit_export(body: AuditExport, request: Request, principal=Depends(require_permission(perm.AUDIT_EXPORT)), sf=Depends(_sf),
                 audit_repo=Depends(get_audit_repository)) -> Response:
    svc = SecurityEventService(sf)
    snap = svc.export_snapshot(fmt=body.format, period=body.period, event_type=body.event_type, area=body.area, result=body.result,
                               actor_user_id=body.actor_user_id, target_type=body.target_type, request_id=body.request_id)
    filters = {k: v for k, v in {"period": body.period, "event_type": body.event_type, "area": body.area, "result": body.result,
                                 "actor_user_id": body.actor_user_id, "target_type": body.target_type, "filter_request_id": body.request_id}.items() if v is not None}
    # Written AFTER the snapshot: a file never contains its own export event. If this audit write fails, no file is returned (fail closed).
    audit_repo.record(**A.build_audit(event_type=A.ADMIN_AUDIT_EXPORTED, actor_user_id=principal.user_id, request_id=get_request_id(request),
                                      target_type="audit", reason=body.reason, format=snap["format"], count=snap["count"], filters=filters))
    content, media = svc.render(snap["records"], snap["format"])
    ext = "json" if snap["format"] == "json" else "csv"
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="audit-export.{ext}"',
                                                                "Cache-Control": "no-store", "X-Export-Count": str(snap["count"])})


# ------------------------------------------------------------------ step-up -----------------------------------------------------------------
class StepUpBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.get("/step-up", summary="Is THIS session currently elevated? (password re-authentication; not MFA)")
def step_up_status(request: Request, _p=Depends(require_permission(perm.USERS_ROLE_ASSIGN)), sf=Depends(_sf)) -> dict:
    return StepUpService(sf).status(_token(request))


@router.post("/step-up", summary="Confirm your password to elevate THIS session for a short window (not MFA)")
def step_up(body: StepUpBody, request: Request, principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)), sf=Depends(_sf)) -> dict:
    enforce("stepup_user", user_key(principal.user_id))
    return StepUpService(sf).confirm(user_id=principal.user_id, session_token=_token(request), password=body.password, request_id=get_request_id(request))


# ------------------------------------------------------------------ role-change requests (two-person) ------------------------------------------
class RoleChangeCreate(BaseModel):
    target_user_id: int = Field(ge=1)
    role: str = Field(max_length=32)
    reason: str = Field(min_length=1, max_length=200)


class RoleChangeDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


@router.get("/role-changes", summary="Role-change requests (pending approvals and history)")
def role_changes(status: str | None = Query(default=None, max_length=12), page: int = Query(default=1, ge=1, le=100000),
                 page_size: int = Query(default=25, ge=1, le=100), principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)),
                 sf=Depends(_sf)) -> dict:
    out = RoleChangeService(sf).list(status=status, page=page, page_size=page_size)
    return {**out, "viewer_user_id": principal.user_id}


@router.post("/role-changes", summary="Request a platform-role change (requires step-up; applied only after a different Admin approves)")
def request_role_change(body: RoleChangeCreate, request: Request, principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)),
                        sf=Depends(_sf), users=Depends(get_admin_user_repository)) -> dict:
    enforce("role_request_user", user_key(principal.user_id))
    StepUpService(sf).require(_token(request))
    d = users.get_user_detail(body.target_user_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    audit = _audit(request, principal, A.ADMIN_ROLE_CHANGE_REQUESTED, "user", body.target_user_id, reason=body.reason,
                   before=d["account"]["platform_role"], after=body.role)
    return RoleChangeService(sf).request(target_user_id=body.target_user_id, requested_role=body.role, reason=body.reason,
                                         requester_user_id=principal.user_id, request_id=get_request_id(request), audit=audit)


@router.post("/role-changes/{public_id}/approve", summary="Approve and apply a role change (a DIFFERENT Admin; requires step-up; atomic with its audit)")
def approve_role_change(public_id: str, request: Request, principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)), sf=Depends(_sf)) -> dict:
    enforce("role_approve_user", user_key(principal.user_id))
    StepUpService(sf).require(_token(request))
    rid = get_request_id(request)

    def audit_for(event: str, result: str = "success", **ctx) -> dict:
        return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=rid, target_type="role_change_request",
                             target_id=public_id[:32], result=result, **ctx)

    out = _guard(lambda: RoleChangeService(sf).approve(public_id[:32], approver_user_id=principal.user_id, request_id=rid, audit_for=audit_for))
    if out["outcome"] == "stale":
        from src.application.errors import ConflictError

        raise ConflictError("This request is stale: the account or an actor changed since it was made. Nothing was applied.")
    return out


@router.post("/role-changes/{public_id}/reject", summary="Reject a pending role change (audited)")
def reject_role_change(public_id: str, request: Request, body: RoleChangeDecision | None = None,
                       principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)), sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.ADMIN_ROLE_CHANGE_REJECTED, "role_change_request", public_id[:32], reason=body.reason if body else None)
    return _guard(lambda: RoleChangeService(sf).reject(public_id[:32], approver_user_id=principal.user_id, audit=audit, reason=body.reason if body else None))


@router.post("/role-changes/{public_id}/cancel", summary="Cancel your own pending role change (audited)")
def cancel_role_change(public_id: str, request: Request, principal=Depends(require_permission(perm.USERS_ROLE_ASSIGN)), sf=Depends(_sf)) -> dict:
    audit = _audit(request, principal, A.ADMIN_ROLE_CHANGE_CANCELLED, "role_change_request", public_id[:32])
    return _guard(lambda: RoleChangeService(sf).cancel(public_id[:32], requester_user_id=principal.user_id, audit=audit))
