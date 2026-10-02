"""Customer support and ticketing persistence + rules (P10B-W10.3).

Data boundaries (see migration 0015):
* ``support_messages``      CUSTOMER-VISIBLE thread (candidate + support).
* ``support_internal_notes`` ADMIN-ONLY. No candidate method in this module ever reads this table.

Candidate methods are owner-scoped by ``owner_user_id`` (the opaque ``public_id`` is a reference, never the
authorisation). Admin mutations stage their canonical audit row in the SAME transaction (SEC-W10-02
semantics); audit context never carries message or note text. No SLA fields, no attachments, no email.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from src.admin_repository import AdminNotFound, AdminUserRepository, _page, _stage
from src.application import admin_permissions as perm
from src.application.errors import ConflictError, ValidationError
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE,
    SUPPORT_AUTHOR_CANDIDATE,
    SUPPORT_AUTHOR_SUPPORT,
    SUPPORT_CATEGORIES,
    SUPPORT_PRIORITIES,
    SUPPORT_STATUSES,
    SupportInternalNote,
    SupportMessage,
    SupportTicket,
    User,
    utcnow,
)

SUBJECT_MAX = 200
MESSAGE_MAX = 5000
NOTE_MAX = 5000
ROUTE_MAX = 200

# Server-side lifecycle. `closed` is terminal in W10.3. Closing is allowed from any open state (spam,
# duplicates); everything else follows the operational flow.
_OPEN = ("new", "triaged", "in_progress", "waiting_for_customer", "resolved")
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new": ("triaged", "in_progress", "waiting_for_customer", "resolved", "closed"),
    "triaged": ("in_progress", "waiting_for_customer", "resolved", "closed"),
    "in_progress": ("waiting_for_customer", "resolved", "closed"),
    "waiting_for_customer": ("in_progress", "resolved", "closed"),
    "resolved": ("in_progress", "closed"),
    "closed": (),
}
# A candidate reply re-opens work: waiting_for_customer and resolved go back to in_progress.
_CANDIDATE_REPLY_REOPENS = {"waiting_for_customer": "in_progress", "resolved": "in_progress"}

_REQUEST_ID = re.compile(r"[^A-Za-z0-9._:\-]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str | None, *, field: str, max_len: int, required: bool = True) -> str:
    """Trim, drop control characters (NUL etc.), and bound the length. Plain text only: markup is stored as
    typed and rendered as text by every client (never as HTML)."""
    text = _CONTROL.sub("", (value or "")).strip()
    if required and not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_len:
        raise ValidationError(f"{field} must be at most {max_len} characters.")
    return text


def clean_request_id(value: str | None) -> str | None:
    cleaned = _REQUEST_ID.sub("", value or "")[:64]
    return cleaned or None


def clean_route(value: str | None) -> str | None:
    """Pathname only: query string and fragment are dropped (they may carry sensitive data)."""
    path = (value or "").strip().split("?")[0].split("#")[0]
    if not path.startswith("/"):
        return None
    return _CONTROL.sub("", path)[:ROUTE_MAX] or None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class SupportRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- candidate side -----------------------------------------------------------------------------

    @staticmethod
    def _candidate_summary(t: SupportTicket) -> dict:
        return {"public_id": t.public_id, "category": t.category, "status": t.status, "subject": t.subject,
                "created_at": _iso(t.created_at), "updated_at": _iso(t.updated_at)}

    def create_ticket(self, *, owner_user_id: int, category: str, subject: str, message: str,
                      request_id: str | None, source_route: str | None, environment: str | None) -> dict:
        if category not in SUPPORT_CATEGORIES:
            raise ValidationError("Unknown support category.")
        subject = clean_text(subject, field="Subject", max_len=SUBJECT_MAX)
        message = clean_text(message, field="Message", max_len=MESSAGE_MAX)
        rid = clean_request_id(request_id)
        with self._sf() as s:
            ticket = SupportTicket(
                public_id=uuid.uuid4().hex, owner_user_id=owner_user_id, category=category, subject=subject,
                initial_request_id=rid, source_route=clean_route(source_route),
                source_environment=(environment or None) and environment[:24])
            s.add(ticket)
            s.flush()
            s.add(SupportMessage(ticket_id=ticket.id, author_user_id=owner_user_id,
                                 author_kind=SUPPORT_AUTHOR_CANDIDATE, body=message, request_id=rid))
            s.commit()  # ticket + first message are one transaction
            return self._candidate_summary(ticket)

    def list_for_owner(self, owner_user_id: int, *, page: int = 1, page_size: int = 20) -> dict:
        page, page_size = _page(page, page_size)
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(SupportTicket)
                                 .where(SupportTicket.owner_user_id == owner_user_id)) or 0)
            rows = s.scalars(select(SupportTicket).where(SupportTicket.owner_user_id == owner_user_id)
                             .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._candidate_summary(t) for t in rows], "total": total,
                    "page": page, "page_size": page_size}

    def _owned(self, s: Session, owner_user_id: int, public_id: str) -> SupportTicket | None:
        return s.scalar(select(SupportTicket).where(SupportTicket.public_id == public_id,
                                                    SupportTicket.owner_user_id == owner_user_id))

    def get_for_owner(self, owner_user_id: int, public_id: str) -> dict | None:
        with self._sf() as s:
            t = self._owned(s, owner_user_id, public_id)
            if t is None:
                return None
            msgs = s.scalars(select(SupportMessage).where(SupportMessage.ticket_id == t.id)
                             .order_by(SupportMessage.id)).all()
            return {**self._candidate_summary(t), "can_reply": t.status != "closed",
                    "messages": [{"id": m.id, "author_kind": m.author_kind, "body": m.body,
                                  "created_at": _iso(m.created_at)} for m in msgs]}

    def candidate_reply(self, *, owner_user_id: int, public_id: str, body: str, request_id: str | None) -> dict:
        body = clean_text(body, field="Message", max_len=MESSAGE_MAX)
        with self._sf() as s:
            t = self._owned(s, owner_user_id, public_id)
            if t is None:
                raise AdminNotFound("Ticket not found.")
            if t.status == "closed":
                raise ConflictError("This ticket is closed. Please open a new one.")
            s.add(SupportMessage(ticket_id=t.id, author_user_id=owner_user_id,
                                 author_kind=SUPPORT_AUTHOR_CANDIDATE, body=body,
                                 request_id=clean_request_id(request_id)))
            t.status = _CANDIDATE_REPLY_REOPENS.get(t.status, t.status)
            t.resolved_at = None if t.status != "resolved" else t.resolved_at
            t.updated_at = utcnow()
            s.commit()
        return self.get_for_owner(owner_user_id, public_id) or {}

    def export_for_owner(self, owner_user_id: int) -> list[dict]:
        """Candidate-visible tickets + thread for the self-service export. NEVER internal notes."""
        with self._sf() as s:
            tickets = s.scalars(select(SupportTicket).where(SupportTicket.owner_user_id == owner_user_id)
                                .order_by(SupportTicket.id)).all()
            out = []
            for t in tickets:
                msgs = s.scalars(select(SupportMessage).where(SupportMessage.ticket_id == t.id)
                                 .order_by(SupportMessage.id)).all()
                out.append({**self._candidate_summary(t), "resolved_at": _iso(t.resolved_at),
                            "closed_at": _iso(t.closed_at),
                            "messages": [{"author": m.author_kind, "body": m.body,
                                          "created_at": _iso(m.created_at)} for m in msgs]})
            return out

    # -- admin side -----------------------------------------------------------------------------------

    @staticmethod
    def _admin_summary(t: SupportTicket, email: str | None, assignee_email: str | None, msgs: int) -> dict:
        return {"id": t.id, "public_id": t.public_id, "owner_user_id": t.owner_user_id, "owner_email": email,
                "category": t.category, "priority": t.priority, "status": t.status, "subject": t.subject,
                "assigned_user_id": t.assigned_user_id, "assignee_email": assignee_email,
                "message_count": msgs, "created_at": _iso(t.created_at), "updated_at": _iso(t.updated_at)}

    def list_admin(self, *, q: str | None = None, status: str | None = None, category: str | None = None,
                   priority: str | None = None, assignee: str | None = None, page: int = 1,
                   page_size: int = 25, viewer_user_id: int | None = None) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if q and q.strip():
            term = q.strip().lower()
            parts = [SupportTicket.public_id == term, func.lower(User.email).contains(term, autoescape=True)]
            if term.isdigit():
                parts += [SupportTicket.id == int(term), SupportTicket.owner_user_id == int(term)]
            conds.append(or_(*parts))
        if status:
            conds.append(SupportTicket.status == status)
        if category:
            conds.append(SupportTicket.category == category)
        if priority:
            conds.append(SupportTicket.priority == priority)
        if assignee == "unassigned":
            conds.append(SupportTicket.assigned_user_id.is_(None))
        elif assignee == "me" and viewer_user_id is not None:
            conds.append(SupportTicket.assigned_user_id == viewer_user_id)
        elif assignee and assignee.isdigit():
            conds.append(SupportTicket.assigned_user_id == int(assignee))
        count = (select(func.count()).select_from(SupportTicket)
                 .join(User, User.id == SupportTicket.owner_user_id).where(*conds))
        msg_count = (select(func.count()).select_from(SupportMessage)
                     .where(SupportMessage.ticket_id == SupportTicket.id).correlate(SupportTicket).scalar_subquery())
        assignee_email = (select(User.email).where(User.id == SupportTicket.assigned_user_id)
                          .correlate(SupportTicket).scalar_subquery())
        with self._sf() as s:
            total = int(s.scalar(count) or 0)
            rows = s.execute(
                select(SupportTicket, User.email, assignee_email, msg_count)
                .join(User, User.id == SupportTicket.owner_user_id).where(*conds)
                .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
                .limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._admin_summary(t, e, a, int(n or 0)) for t, e, a, n in rows],
                    "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _find(s: Session, ref: str, *, lock: bool = False) -> SupportTicket:
        cond = SupportTicket.id == int(ref) if ref.isdigit() else SupportTicket.public_id == ref
        stmt = select(SupportTicket).where(cond)
        t = s.scalar(stmt.with_for_update() if lock else stmt)
        if t is None:
            raise AdminNotFound("Ticket not found.")
        return t

    def get_admin(self, ref: str) -> dict | None:
        with self._sf() as s:
            try:
                t = self._find(s, ref)
            except AdminNotFound:
                return None
            msgs = s.scalars(select(SupportMessage).where(SupportMessage.ticket_id == t.id)
                             .order_by(SupportMessage.id)).all()
            notes = s.scalars(select(SupportInternalNote).where(SupportInternalNote.ticket_id == t.id)
                              .order_by(SupportInternalNote.id)).all()
            owner_email = s.scalar(select(User.email).where(User.id == t.owner_user_id))
            assignee_email = (s.scalar(select(User.email).where(User.id == t.assigned_user_id))
                              if t.assigned_user_id else None)
            ticket = {**self._admin_summary(t, owner_email, assignee_email, len(msgs)),
                      "initial_request_id": t.initial_request_id, "source_route": t.source_route,
                      "source_environment": t.source_environment, "resolved_at": _iso(t.resolved_at),
                      "closed_at": _iso(t.closed_at), "allowed_statuses": list(TRANSITIONS[t.status])}
            messages = [{"id": m.id, "author_kind": m.author_kind, "author_user_id": m.author_user_id,
                         "body": m.body, "request_id": m.request_id, "created_at": _iso(m.created_at)}
                        for m in msgs]
            internal = [{"id": n.id, "author_user_id": n.author_user_id, "body": n.body,
                         "request_id": n.request_id, "created_at": _iso(n.created_at)} for n in notes]
            owner_id = t.owner_user_id
        detail = AdminUserRepository(self._sf).get_user_detail(owner_id)
        return {"ticket": ticket, "messages": messages, "internal_notes": internal,
                "account": detail["account"] if detail else None}

    def eligible_assignees(self) -> list[dict]:
        roles = [r for r, p in perm.ROLE_PRESETS.items() if perm.SUPPORT_MANAGE in p]
        with self._sf() as s:
            rows = s.scalars(select(User).where(User.platform_role.in_(roles),
                                                User.status == ACCOUNT_STATUS_ACTIVE).order_by(User.id)).all()
            return [{"user_id": u.id, "email": u.email, "platform_role": u.platform_role} for u in rows]

    def assign(self, ref: str, assignee_user_id: int | None, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            t = self._find(s, ref, lock=True)
            if t.status == "closed":
                raise ConflictError("A closed ticket cannot be changed.")
            before = t.assigned_user_id
            if assignee_user_id is not None:
                u = s.get(User, assignee_user_id)
                if (u is None or u.status != ACCOUNT_STATUS_ACTIVE
                        or perm.SUPPORT_MANAGE not in perm.permissions_for_role(u.platform_role)):
                    raise ConflictError("That account cannot be assigned support tickets.")
            t.assigned_user_id = assignee_user_id
            t.updated_at = utcnow()
            _stage(s, audit, ticket_id=t.id, before_assignee=before, after_assignee=assignee_user_id)
            s.commit()
            return {"ticket_id": t.id, "assigned_user_id": assignee_user_id}

    def set_status(self, ref: str, status: str, *, audit: dict | None = None) -> dict:
        if status not in SUPPORT_STATUSES:
            raise ValidationError("Unknown ticket status.")
        with self._sf() as s:
            t = self._find(s, ref, lock=True)
            if status not in TRANSITIONS[t.status]:
                raise ConflictError(f"A {t.status.replace('_', ' ')} ticket cannot move to {status.replace('_', ' ')}.")
            now = utcnow()
            before = t.status
            t.status = status
            t.updated_at = now
            if status == "resolved":
                t.resolved_at = now
            if status == "closed":
                t.closed_at = now
            if status == "in_progress" and before == "resolved":
                t.resolved_at = None
            _stage(s, audit, ticket_id=t.id, before=before, after=status)
            s.commit()
            return {"ticket_id": t.id, "status": status}

    def set_priority(self, ref: str, priority: str, *, audit: dict | None = None) -> dict:
        if priority not in SUPPORT_PRIORITIES:
            raise ValidationError("Unknown priority.")
        with self._sf() as s:
            t = self._find(s, ref, lock=True)
            if t.status == "closed":
                raise ConflictError("A closed ticket cannot be changed.")
            before = t.priority
            t.priority = priority
            t.updated_at = utcnow()
            _stage(s, audit, ticket_id=t.id, before=before, after=priority)
            s.commit()
            return {"ticket_id": t.id, "priority": priority}

    def support_reply(self, ref: str, *, author_user_id: int, body: str, request_id: str | None,
                      audit: dict | None = None) -> dict:
        body = clean_text(body, field="Reply", max_len=MESSAGE_MAX)
        with self._sf() as s:
            t = self._find(s, ref, lock=True)
            if t.status == "closed":
                raise ConflictError("A closed ticket cannot receive a reply.")
            m = SupportMessage(ticket_id=t.id, author_user_id=author_user_id, author_kind=SUPPORT_AUTHOR_SUPPORT,
                               body=body, request_id=clean_request_id(request_id))
            s.add(m)
            t.updated_at = utcnow()
            s.flush()
            _stage(s, audit, ticket_id=t.id, message_id=m.id)  # ids only; never the text
            s.commit()
            return {"ticket_id": t.id, "message_id": m.id}

    def add_note(self, ref: str, *, author_user_id: int, body: str, request_id: str | None,
                 audit: dict | None = None) -> dict:
        body = clean_text(body, field="Note", max_len=NOTE_MAX)
        with self._sf() as s:
            t = self._find(s, ref, lock=True)
            n = SupportInternalNote(ticket_id=t.id, author_user_id=author_user_id, body=body,
                                    request_id=clean_request_id(request_id))
            s.add(n)
            t.updated_at = utcnow()
            s.flush()
            _stage(s, audit, ticket_id=t.id, note_id=n.id)
            s.commit()
            return {"ticket_id": t.id, "note_id": n.id}

    def stats(self) -> dict:
        """Counts only (Command Center). No SLA or breach figures: no SLA policy exists."""
        with self._sf() as s:
            def n(*conds) -> int:
                return int(s.scalar(select(func.count()).select_from(SupportTicket).where(*conds)) or 0)
            active = ("new", "triaged", "in_progress", "waiting_for_customer")
            return {
                "open": n(SupportTicket.status.in_(active)),
                "unassigned": n(SupportTicket.status.in_(active), SupportTicket.assigned_user_id.is_(None)),
                "waiting_for_customer": n(SupportTicket.status == "waiting_for_customer"),
                "high_or_urgent": n(SupportTicket.status.in_(active), SupportTicket.priority.in_(("high", "urgent"))),
                "total": n(),
            }
