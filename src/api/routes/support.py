"""Candidate support routes (P10B-W10.3). Owner-scoped; NOT admin routes.

A candidate can create tickets and read/reply to ONLY their own. The ticket reference (``public_id``) is
opaque but never the authorisation: every query filters on the authenticated owner, and a foreign or unknown
reference is the same 404. Internal notes have no code path here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.admin_repository import AdminNotFound
from src.api.dependencies import get_current_user_id, get_request_id, get_support_repository
from src.api.rate_limit import enforce, user_key
from src.api.schemas.support import (
    TicketCreateRequest,
    TicketDetail,
    TicketList,
    TicketReplyRequest,
    TicketSummary,
)

router = APIRouter(prefix="/support", tags=["support"])


def _env(request: Request) -> str | None:
    return str(getattr(getattr(request.app.state, "settings", None), "env", "") or "") or None


@router.post("/tickets", response_model=TicketSummary, status_code=201,
             summary="Contact Support: create a ticket with its first message")
def create_ticket(body: TicketCreateRequest, request: Request, user_id: int = Depends(get_current_user_id),
                  support=Depends(get_support_repository)) -> TicketSummary:
    enforce("support_create_user", user_key(user_id))
    out = support.create_ticket(
        owner_user_id=user_id, category=body.category, subject=body.subject, message=body.message,
        request_id=body.request_id or get_request_id(request), source_route=body.source_route,
        environment=_env(request))
    return TicketSummary(**out)


@router.get("/tickets", response_model=TicketList, summary="My support tickets")
def my_tickets(page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=20, ge=1, le=50),
               user_id: int = Depends(get_current_user_id), support=Depends(get_support_repository)) -> TicketList:
    return TicketList(**support.list_for_owner(user_id, page=page, page_size=page_size))


@router.get("/tickets/{public_id}", response_model=TicketDetail, summary="One of my tickets, with its thread")
def my_ticket(public_id: str, user_id: int = Depends(get_current_user_id),
              support=Depends(get_support_repository)) -> TicketDetail:
    d = support.get_for_owner(user_id, public_id[:64])
    if d is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return TicketDetail(**d)


@router.post("/tickets/{public_id}/messages", response_model=TicketDetail, summary="Reply on my ticket")
def reply(public_id: str, body: TicketReplyRequest, request: Request, user_id: int = Depends(get_current_user_id),
          support=Depends(get_support_repository)) -> TicketDetail:
    enforce("support_reply_user", user_key(user_id))
    try:
        d = support.candidate_reply(owner_user_id=user_id, public_id=public_id[:64], body=body.message,
                                    request_id=body.request_id or get_request_id(request))
    except AdminNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return TicketDetail(**d)
