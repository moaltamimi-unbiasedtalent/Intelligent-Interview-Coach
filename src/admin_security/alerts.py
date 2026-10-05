"""Durable in-app Admin alerts (P10B-W10.13). Code-defined categories, stable dedupe keys, no arbitrary payload, no external paging.

Emission is best-effort and never changes the outcome of the operation that observed the condition. Only categories with a real emission seam today are
implemented (see ``definitions.ALERT_NOT_IMPLEMENTED``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.admin_repository import AdminNotFound, _stage
from src.application import admin_audit as A
from src.application.errors import ConflictError, ValidationError
from src.persistence import ALERT_STATES, AdminNotification, AuditEvent, utcnow
from src.admin_security import definitions as D

log = logging.getLogger("ask4mo.security.alerts")


def _iso(v):
    return v.isoformat() if v else None


def view(n: AdminNotification) -> dict:
    return {"public_id": n.public_id, "category": n.category, "severity": n.severity, "state": n.state, "source_type": n.source_type,
            "source_id": n.source_id, "title": n.title, "occurrence_count": n.occurrence_count, "first_seen_at": _iso(n.first_seen_at),
            "last_seen_at": _iso(n.last_seen_at), "acknowledged_at": _iso(n.acknowledged_at), "resolved_at": _iso(n.resolved_at),
            "revision": n.revision}


def record_condition(session_factory: sessionmaker, *, category: str, dedupe_key: str, source_id: str | None) -> None:
    """Create or refresh ONE alert for a logical condition. A recurrence of a resolved condition reopens the same alert. Never raises."""
    try:
        defn = D.ALERT_DEFINITIONS[category]
        for attempt in (0, 1):
            try:
                with session_factory() as s:
                    now = utcnow()
                    row = s.scalar(select(AdminNotification).where(AdminNotification.dedupe_key == dedupe_key))
                    if row is None:
                        s.add(AdminNotification(public_id=uuid.uuid4().hex, category=category, severity=defn["severity"], dedupe_key=dedupe_key,
                                                state="active", source_type=defn["source_type"], source_id=source_id, title=defn["title"],
                                                occurrence_count=1, first_seen_at=now, last_seen_at=now, created_at=now, updated_at=now, revision=0))
                    else:
                        row.occurrence_count += 1
                        row.last_seen_at = now
                        row.updated_at = now
                        row.revision += 1
                        if row.state == "resolved":  # the condition recurred: reopen, do not stack a duplicate
                            row.state, row.acknowledged_at, row.acknowledged_by_user_id = "active", None, None
                            row.resolved_at, row.resolved_by_user_id = None, None
                    s.commit()
                return
            except IntegrityError:  # concurrent first insert: retry as an update
                if attempt == 1:
                    raise
    except Exception:  # noqa: BLE001 - alerting must never break the observed operation
        log.warning("admin alert could not be recorded")


def observe_audit_event(session_factory: sessionmaker, *, event_type: str, actor_user_id: int | None, result: str) -> None:
    """Called after an audit row is committed. Raises an alert when a deterministic burst rule is met for a KNOWN account. Never raises."""
    try:
        if actor_user_id is None:
            return
        if event_type == "account.login" and result != "success":
            category, threshold, only_failures = "auth_failure_burst", D.AUTH_FAILURE_BURST_THRESHOLD, True
        elif event_type == A.ADMIN_ACCESS_DENIED:
            category, threshold, only_failures = "admin_access_denied_burst", D.DENIED_BURST_THRESHOLD, False
        else:
            return
        since = utcnow() - timedelta(seconds=D.BURST_WINDOW_SECONDS)
        with session_factory() as s:
            conds = [AuditEvent.event_type == event_type, AuditEvent.actor_user_id == actor_user_id, AuditEvent.created_at >= since]
            if only_failures:
                conds.append(AuditEvent.result != "success")
            n = int(s.scalar(select(func.count()).select_from(AuditEvent).where(*conds)) or 0)
        if n >= threshold:
            record_condition(session_factory, category=category, dedupe_key=f"{category}:{actor_user_id}", source_id=str(actor_user_id))
    except Exception:  # noqa: BLE001
        log.warning("alert observation failed")


def observe_job_failed(session_factory: sessionmaker, *, job_type: str, job_public_id: str) -> None:
    """A background job reached a terminal failure. One alert per job TYPE (deduplicated). Never raises."""
    record_condition(session_factory, category="job_failed", dedupe_key=f"job_failed:{job_type}"[:80], source_id=job_public_id)


class AlertService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def list(self, *, state: str | None = None, severity: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = max(1, int(page)), max(1, min(int(page_size), 100))
        if state and state not in ALERT_STATES:
            raise ValidationError("Unknown state.")
        if severity and severity not in D.SECURITY_SEVERITIES:
            raise ValidationError("Unknown severity.")
        conds = [c for c in (AdminNotification.state == state if state else None, AdminNotification.severity == severity if severity else None) if c is not None]
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(AdminNotification).where(*conds)) or 0)
            rows = s.scalars(select(AdminNotification).where(*conds).order_by(AdminNotification.last_seen_at.desc(), AdminNotification.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            items = [view(r) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size, "categories": list(D.ALERT_DEFINITIONS),
                "not_implemented": list(D.ALERT_NOT_IMPLEMENTED), "delivery": "in_app_only"}

    def summary(self) -> dict:
        with self._sf() as s:
            def n(*c):
                return int(s.scalar(select(func.count()).select_from(AdminNotification).where(*c)) or 0)
            return {"active_critical": n(AdminNotification.state == "active", AdminNotification.severity == "critical"),
                    "active_high": n(AdminNotification.state == "active", AdminNotification.severity == "high"),
                    "active": n(AdminNotification.state == "active"), "acknowledged": n(AdminNotification.state == "acknowledged")}

    def _transition(self, public_id: str, *, expected_revision: int, new_state: str, actor_user_id: int, audit: dict) -> dict:
        with self._sf() as s:
            row = s.scalar(select(AdminNotification).where(AdminNotification.public_id == public_id).with_for_update())
            if row is None:
                raise AdminNotFound("Alert not found.")
            if row.revision != int(expected_revision):
                raise ConflictError("This alert changed. Reload and try again.")
            now = utcnow()
            old = row.state
            if new_state == "acknowledged":
                if old != "active":
                    raise ConflictError("Only an active alert can be acknowledged.")
                row.acknowledged_at, row.acknowledged_by_user_id = now, actor_user_id
            else:
                if old == "resolved":
                    raise ConflictError("This alert is already resolved.")
                row.resolved_at, row.resolved_by_user_id = now, actor_user_id
            row.state, row.updated_at, row.revision = new_state, now, row.revision + 1
            _stage(s, audit, alert_public_id=public_id, category=row.category, old_state=old, new_state=new_state)
            s.commit()
            return view(row)

    def acknowledge(self, public_id: str, *, expected_revision: int, actor_user_id: int, audit: dict) -> dict:
        return self._transition(public_id, expected_revision=expected_revision, new_state="acknowledged", actor_user_id=actor_user_id, audit=audit)

    def resolve(self, public_id: str, *, expected_revision: int, actor_user_id: int, audit: dict) -> dict:
        return self._transition(public_id, expected_revision=expected_revision, new_state="resolved", actor_user_id=actor_user_id, audit=audit)
