"""Admin support routes (P10B-W10.3). Every route declares an explicit canonical permission.

Support operators see the ticket, what the candidate submitted to Support, safe W10.2 account metadata and
request ids. A ticket is NOT a gateway into private candidate data. All mutations stage their canonical
audit row in the same transaction; audit payloads hold ids and enum before/after, never message text.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.admin_repository import AdminNotFound
from src.api.dependencies import get_request_id, get_support_repository, require_permission
from src.api.schemas.admin import AdminAssignee, AdminTicketDetail, AdminTicketPage
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import SUPPORT_CATEGORIES, SUPPORT_PRIORITIES, SUPPORT_STATUSES

router = APIRouter(prefix="/admin/support", tags=["admin-support"])


class AssignRequest(BaseModel):
    assignee_user_id: int | None = Field(default=None, ge=1)


class StatusBody(BaseModel):
    status: str = Field(max_length=24)


class PriorityBody(BaseModel):
    priority: str = Field(max_length=16)


class TextBody(BaseModel):
    body: str = Field(max_length=20000)


def _audit(event: str, request: Request, principal, ticket_id: str, **ctx):
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="support_ticket", target_id=ticket_id, **ctx)


def _ticket_id(support, ref: str) -> int:
    d = support.get_admin(ref[:64])
    if d is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return d["ticket"]["id"]


def _guard(fn):
    try:
        return fn()
    except AdminNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/tickets", response_model=AdminTicketPage,
            summary="Support queue: server-side filters and pagination (operational identifiers only)")
def queue(
    q: str | None = Query(default=None, max_length=320),
    status: str | None = Query(default=None, max_length=24),
    category: str | None = Query(default=None, max_length=32),
    priority: str | None = Query(default=None, max_length=16),
    assignee: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=25, ge=1, le=100),
    principal=Depends(require_permission(perm.SUPPORT_READ)),
    support=Depends(get_support_repository),
) -> AdminTicketPage:
    for value, allowed, label in ((status, SUPPORT_STATUSES, "status"), (category, SUPPORT_CATEGORIES, "category"),
                                  (priority, SUPPORT_PRIORITIES, "priority")):
        if value and value not in allowed:
            raise HTTPException(status_code=422, detail=f"Unknown {label} filter.")
    if assignee and assignee not in ("me", "unassigned") and not assignee.isdigit():
        raise HTTPException(status_code=422, detail="Unknown assignee filter.")
    return AdminTicketPage(**support.list_admin(
        q=q, status=status, category=category, priority=priority, assignee=assignee, page=page,
        page_size=page_size, viewer_user_id=principal.user_id))


@router.get("/assignees", response_model=list[AdminAssignee],
            summary="Active accounts eligible to be assigned tickets")
def assignees(_p=Depends(require_permission(perm.SUPPORT_MANAGE)), support=Depends(get_support_repository)):
    return [AdminAssignee(**a) for a in support.eligible_assignees()]


@router.get("/tickets/{ref}", response_model=AdminTicketDetail,
            summary="Ticket detail: thread, internal notes, safe account metadata")
def detail(ref: str, _p=Depends(require_permission(perm.SUPPORT_READ)), support=Depends(get_support_repository)):
    d = support.get_admin(ref[:64])
    if d is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return AdminTicketDetail(**d, priorities=list(SUPPORT_PRIORITIES), statuses=list(SUPPORT_STATUSES))


@router.post("/tickets/{ref}/assign", summary="Assign, reassign or unassign a ticket (audited, atomic)")
def assign(ref: str, body: AssignRequest, request: Request,
           principal=Depends(require_permission(perm.SUPPORT_MANAGE)), support=Depends(get_support_repository)):
    tid = _ticket_id(support, ref)
    return _guard(lambda: support.assign(str(tid), body.assignee_user_id,
                                         audit=_audit(A.ADMIN_SUPPORT_TICKET_ASSIGNED, request, principal, tid)))


@router.post("/tickets/{ref}/status", summary="Move a ticket through its lifecycle (validated, audited, atomic)")
def status(ref: str, body: StatusBody, request: Request,
           principal=Depends(require_permission(perm.SUPPORT_MANAGE)), support=Depends(get_support_repository)):
    tid = _ticket_id(support, ref)
    return _guard(lambda: support.set_status(str(tid), body.status,
                                             audit=_audit(A.ADMIN_SUPPORT_TICKET_STATUS_CHANGED, request, principal, tid)))


@router.post("/tickets/{ref}/priority", summary="Set ticket priority (audited, atomic). No SLA is implied.")
def priority(ref: str, body: PriorityBody, request: Request,
             principal=Depends(require_permission(perm.SUPPORT_MANAGE)), support=Depends(get_support_repository)):
    tid = _ticket_id(support, ref)
    return _guard(lambda: support.set_priority(str(tid), body.priority,
                                               audit=_audit(A.ADMIN_SUPPORT_TICKET_PRIORITY_CHANGED, request, principal, tid)))


@router.post("/tickets/{ref}/reply", summary="Send a customer-visible reply (audited, atomic)")
def reply(ref: str, body: TextBody, request: Request,
          principal=Depends(require_permission(perm.SUPPORT_REPLY)), support=Depends(get_support_repository)):
    tid = _ticket_id(support, ref)
    return _guard(lambda: support.support_reply(
        str(tid), author_user_id=principal.user_id, body=body.body, request_id=get_request_id(request),
        audit=_audit(A.ADMIN_SUPPORT_REPLY_SENT, request, principal, tid)))


@router.post("/tickets/{ref}/notes", summary="Add an Admin-only internal note (audited, atomic; never candidate-visible)")
def note(ref: str, body: TextBody, request: Request,
         principal=Depends(require_permission(perm.SUPPORT_NOTE)), support=Depends(get_support_repository)):
    tid = _ticket_id(support, ref)
    return _guard(lambda: support.add_note(
        str(tid), author_user_id=principal.user_id, body=body.body, request_id=get_request_id(request),
        audit=_audit(A.ADMIN_SUPPORT_INTERNAL_NOTE_CREATED, request, principal, tid)))
