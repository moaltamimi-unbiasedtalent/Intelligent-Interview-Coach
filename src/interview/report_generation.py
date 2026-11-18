"""Opaque report incarnations in the existing append-only metadata audit.

New reports get an identifier in their creation transaction. Existing legacy rows
are enrolled under a row lock on first owner selection. No report content, table,
column, migration or stored report format is changed. Supported writers must use
the repository creation boundary; arbitrary privileged SQL is not this contract.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from src.persistence import AuditEvent

EVENT = "interview.generation"


def current_generation(db, user_id: int, report_id: int) -> str | None:
    events = db.execute(select(AuditEvent.event_type, AuditEvent.request_id).where(
        AuditEvent.actor_user_id == user_id, AuditEvent.target_type == "interview",
        AuditEvent.target_id == str(report_id), AuditEvent.result == "success",
        AuditEvent.event_type.in_((EVENT, "interview.deleted")),
    ).order_by(AuditEvent.id.desc()).limit(1)).first()
    if events is None or events.event_type != EVENT:
        return None
    value = events.request_id
    if not isinstance(value, str) or len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Invalid report generation evidence.")
    return value


def issue_generation(db, user_id: int, report_id: int) -> str:
    value = uuid.uuid4().hex
    db.add(AuditEvent(event_type=EVENT, result="success", actor_user_id=user_id,
                      target_type="interview", target_id=str(report_id), request_id=value))
    db.flush()
    return value
