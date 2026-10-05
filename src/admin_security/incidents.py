"""Governed incident management (P10B-W10.13).

Incident title / root cause / remediation are INTERNAL operator-authored text: they are never populated from candidate content, and they are never copied
into audit context (audit carries ids, enum before/after and the NAMES of changed fields). Support tickets are linked by identifier only. There is no delete:
an incident is closed, and ``incident_events`` is the append-only evidentiary history (DB triggers reject UPDATE/DELETE).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.admin_repository import AdminNotFound, _stage
from src.application.admin_permissions import is_admin_role
from src.application.errors import ConflictError, ValidationError
from src.persistence import (
    AdminIncident, AdminIncidentEvent, AdminIncidentTicket, SupportTicket, User, utcnow,
)
from src.admin_security import definitions as D

_FIELDS = ("title", "severity", "affected_service", "owner_admin_user_id", "affected_user_estimate", "root_cause", "remediation")


def _iso(v):
    return v.isoformat() if v else None


def _view(i: AdminIncident) -> dict:
    return {"public_id": i.public_id, "title": i.title, "severity": i.severity, "status": i.status, "affected_service": i.affected_service,
            "started_at": _iso(i.started_at), "resolved_at": _iso(i.resolved_at), "owner_admin_user_id": i.owner_admin_user_id,
            "affected_user_estimate": i.affected_user_estimate, "root_cause": i.root_cause, "remediation": i.remediation,
            "created_at": _iso(i.created_at), "updated_at": _iso(i.updated_at), "revision": i.revision}


def _clean(text: str | None, limit: int, name: str, *, required: bool = False) -> str | None:
    t = (text or "").strip()
    if not t:
        if required:
            raise ValidationError(f"{name} is required.")
        return None
    if len(t) > limit:
        raise ValidationError(f"{name} is too long.")
    return t


class IncidentService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- reads -----------------------------------------------------------------------------------------------------------------
    def list(self, *, status: str | None = None, severity: str | None = None, service: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = max(1, int(page)), max(1, min(int(page_size), D.INCIDENT_PAGE_MAX))
        for v, allowed, nm in ((status, D.INCIDENT_STATUSES, "status"), (severity, D.INCIDENT_SEVERITIES, "severity"), (service, D.INCIDENT_SERVICES, "service")):
            if v and v not in allowed:
                raise ValidationError(f"Unknown {nm}.")
        conds = [c for c in (AdminIncident.status == status if status else None, AdminIncident.severity == severity if severity else None,
                             AdminIncident.affected_service == service if service else None) if c is not None]
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(AdminIncident).where(*conds)) or 0)
            rows = s.scalars(select(AdminIncident).where(*conds).order_by(AdminIncident.updated_at.desc(), AdminIncident.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            items = [_view(r) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size, "severities": list(D.INCIDENT_SEVERITIES),
                "statuses": list(D.INCIDENT_STATUSES), "services": list(D.INCIDENT_SERVICES)}

    def open_count(self) -> int:
        with self._sf() as s:
            return int(s.scalar(select(func.count()).select_from(AdminIncident).where(AdminIncident.status.in_(("open", "investigating", "monitoring")))) or 0)

    def detail(self, public_id: str) -> dict:
        with self._sf() as s:
            inc = self._get(s, public_id)
            events = s.scalars(select(AdminIncidentEvent).where(AdminIncidentEvent.incident_id == inc.id)
                               .order_by(AdminIncidentEvent.id.desc()).limit(200)).all()
            links = s.execute(select(SupportTicket.public_id, SupportTicket.status, SupportTicket.category, AdminIncidentTicket.linked_at)
                              .join(AdminIncidentTicket, AdminIncidentTicket.ticket_id == SupportTicket.id)
                              .where(AdminIncidentTicket.incident_id == inc.id).order_by(AdminIncidentTicket.id)).all()
            out = _view(inc)
            out["allowed_transitions"] = list(D.INCIDENT_TRANSITIONS[inc.status])
            out["tickets"] = [{"public_id": p, "status": st, "category": c, "linked_at": _iso(at)} for p, st, c, at in links]  # ids/status/category only
            out["history"] = [{"id": e.id, "action": e.action, "prior_status": e.prior_status, "new_status": e.new_status,
                               "actor_user_id": e.actor_user_id, "request_id": e.request_id, "meta": e.meta, "created_at": _iso(e.created_at)}
                              for e in events]
        return out

    # -- writes (each: one transaction = incident change + history row + audit row) ---------------------------------------------
    @staticmethod
    def _get(s: Session, public_id: str, *, lock: bool = False) -> AdminIncident:
        stmt = select(AdminIncident).where(AdminIncident.public_id == public_id)
        inc = s.scalar(stmt.with_for_update() if lock else stmt)
        if inc is None:
            raise AdminNotFound("Incident not found.")
        return inc

    @staticmethod
    def _event(s: Session, inc: AdminIncident, *, action: str, actor: int, request_id, prior=None, new=None, meta=None) -> None:
        s.add(AdminIncidentEvent(incident_id=inc.id, action=action, prior_status=prior, new_status=new, actor_user_id=actor,
                                 request_id=request_id, meta=meta or None, created_at=utcnow()))

    @staticmethod
    def _owner_ok(s: Session, owner_id: int | None) -> None:
        if owner_id is None:
            return
        u = s.get(User, owner_id)
        if u is None or u.status != "active" or not is_admin_role(u.platform_role):
            raise ValidationError("The owner must be an active Admin account.")

    def create(self, *, title: str, severity: str, affected_service: str, actor_user_id: int, request_id: str | None, audit: dict,
               owner_admin_user_id: int | None = None, affected_user_estimate: int | None = None) -> dict:
        title = _clean(title, D.MAX_TITLE, "Title", required=True)
        if severity not in D.INCIDENT_SEVERITIES:
            raise ValidationError("Unknown severity.")
        if affected_service not in D.INCIDENT_SERVICES:
            raise ValidationError("Unknown service.")
        if affected_user_estimate is not None and affected_user_estimate < 0:
            raise ValidationError("The affected-user estimate cannot be negative.")
        with self._sf() as s:
            self._owner_ok(s, owner_admin_user_id)
            now = utcnow()
            inc = AdminIncident(public_id=uuid.uuid4().hex, title=title, severity=severity, status="open", affected_service=affected_service,
                                started_at=now, owner_admin_user_id=owner_admin_user_id, affected_user_estimate=affected_user_estimate,
                                created_by_user_id=actor_user_id, created_at=now, updated_at=now, revision=0)
            s.add(inc)
            s.flush()
            self._event(s, inc, action="created", actor=actor_user_id, request_id=request_id, new="open",
                        meta={"severity": severity, "affected_service": affected_service})
            _stage(s, audit, incident_public_id=inc.public_id, severity=severity, affected_service=affected_service, new_status="open")
            s.commit()
            return _view(inc)

    def update(self, public_id: str, *, expected_revision: int, changes: dict, actor_user_id: int, request_id: str | None, audit: dict) -> dict:
        unknown = set(changes) - set(_FIELDS)
        if unknown:
            raise ValidationError("Unsupported field.")
        with self._sf() as s:
            inc = self._get(s, public_id, lock=True)
            if inc.revision != int(expected_revision):
                raise ConflictError("This incident changed. Reload and try again.")
            if inc.status == "closed":
                raise ConflictError("A closed incident cannot be edited.")
            changed: list[str] = []
            for field, raw in changes.items():
                if field == "title":
                    new = _clean(raw, D.MAX_TITLE, "Title", required=True)
                elif field in ("root_cause", "remediation"):
                    new = _clean(raw, D.MAX_NARRATIVE, field.replace("_", " ").capitalize())
                elif field == "severity":
                    if raw not in D.INCIDENT_SEVERITIES:
                        raise ValidationError("Unknown severity.")
                    new = raw
                elif field == "affected_service":
                    if raw not in D.INCIDENT_SERVICES:
                        raise ValidationError("Unknown service.")
                    new = raw
                elif field == "affected_user_estimate":
                    if raw is not None and int(raw) < 0:
                        raise ValidationError("The affected-user estimate cannot be negative.")
                    new = None if raw is None else int(raw)
                else:  # owner_admin_user_id
                    self._owner_ok(s, raw)
                    new = raw
                if getattr(inc, field) != new:
                    setattr(inc, field, new)
                    changed.append(field)
            if not changed:
                return _view(inc)
            inc.updated_at, inc.revision = utcnow(), inc.revision + 1
            # History and audit carry the NAMES of the changed fields, never the free-text values.
            self._event(s, inc, action="updated", actor=actor_user_id, request_id=request_id, meta={"fields_changed": changed})
            _stage(s, audit, incident_public_id=public_id, fields_changed=changed, severity=inc.severity, owner_admin_user_id=inc.owner_admin_user_id,
                   affected_service=inc.affected_service)
            s.commit()
            return _view(inc)

    def change_status(self, public_id: str, *, expected_revision: int, new_status: str, actor_user_id: int, request_id: str | None, audit: dict) -> dict:
        if new_status not in D.INCIDENT_STATUSES:
            raise ValidationError("Unknown status.")
        with self._sf() as s:
            inc = self._get(s, public_id, lock=True)
            if inc.revision != int(expected_revision):
                raise ConflictError("This incident changed. Reload and try again.")
            old = inc.status
            if new_status not in D.INCIDENT_TRANSITIONS[old]:
                raise ConflictError(f"An incident cannot move from {old} to {new_status}.")
            if new_status == "resolved" and not ((inc.root_cause or "").strip() or (inc.remediation or "").strip()):
                raise ValidationError("Record a root cause or a remediation before resolving an incident.")
            now = utcnow()
            inc.status, inc.updated_at, inc.revision = new_status, now, inc.revision + 1
            if new_status == "resolved":
                inc.resolved_at = now
            elif new_status in ("investigating", "open", "monitoring"):
                inc.resolved_at = None
            self._event(s, inc, action="status_changed", actor=actor_user_id, request_id=request_id, prior=old, new=new_status)
            _stage(s, audit, incident_public_id=public_id, old_status=old, new_status=new_status, severity=inc.severity, affected_service=inc.affected_service)
            s.commit()
            return _view(inc)

    def link_ticket(self, public_id: str, ticket_public_id: str, *, expected_revision: int, actor_user_id: int, request_id: str | None, audit: dict) -> dict:
        return self._ticket(public_id, ticket_public_id, link=True, expected_revision=expected_revision, actor_user_id=actor_user_id,
                            request_id=request_id, audit=audit)

    def unlink_ticket(self, public_id: str, ticket_public_id: str, *, expected_revision: int, actor_user_id: int, request_id: str | None, audit: dict) -> dict:
        return self._ticket(public_id, ticket_public_id, link=False, expected_revision=expected_revision, actor_user_id=actor_user_id,
                            request_id=request_id, audit=audit)

    def _ticket(self, public_id, ticket_public_id, *, link: bool, expected_revision, actor_user_id, request_id, audit) -> dict:
        with self._sf() as s:
            inc = self._get(s, public_id, lock=True)
            if inc.revision != int(expected_revision):
                raise ConflictError("This incident changed. Reload and try again.")
            ticket = s.scalar(select(SupportTicket).where(SupportTicket.public_id == (ticket_public_id or "")[:32]))
            if ticket is None:
                raise AdminNotFound("Ticket not found.")
            existing = s.scalar(select(AdminIncidentTicket).where(AdminIncidentTicket.incident_id == inc.id, AdminIncidentTicket.ticket_id == ticket.id))
            if link:
                if existing is not None:
                    raise ConflictError("This ticket is already linked.")
                s.add(AdminIncidentTicket(incident_id=inc.id, ticket_id=ticket.id, linked_by_user_id=actor_user_id, linked_at=utcnow()))
            else:
                if existing is None:
                    raise AdminNotFound("This ticket is not linked.")
                s.delete(existing)
            inc.updated_at, inc.revision = utcnow(), inc.revision + 1
            action = "ticket_linked" if link else "ticket_unlinked"
            self._event(s, inc, action=action, actor=actor_user_id, request_id=request_id, meta={"ticket_public_id": ticket.public_id})
            _stage(s, audit, incident_public_id=public_id, ticket_public_id=ticket.public_id)
            s.commit()
            return _view(inc)
