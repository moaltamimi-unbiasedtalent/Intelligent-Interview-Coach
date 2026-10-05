"""Security-event projection, audit browsing and bounded audit export (P10B-W10.13). Read-only over ``audit_events``.

There is NO second log: a security event IS an audit row, projected to a typed bounded schema without its ``context``. Nothing here records an IP address,
user agent, device or email, and nothing reads candidate content.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from src.application.admin_audit import ADMIN_EVENT_NAMES
from src.application.errors import ValidationError
from src.persistence import AuditEvent, utcnow
from src.admin_security import definitions as D

MAX_PAGE = 100
AREAS = ("account", "admin", "security", "platform")
AUDIT_PERIODS = {**D.EVENT_PERIODS}


def _page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, int(page)), max(1, min(int(page_size), MAX_PAGE))


def _iso(v):
    return v.isoformat() if v else None


def _since(period: str | None, *, allow_all: bool):
    if period in (None, "", "all"):
        if allow_all:
            return None
        raise ValidationError("A bounded period is required.")
    if period not in AUDIT_PERIODS:
        raise ValidationError("Unknown period.")
    return utcnow() - timedelta(seconds=AUDIT_PERIODS[period])


def _filters(*, event_type, area, result, actor_user_id, target_type, request_id, since) -> list:
    conds = []
    if event_type:
        conds.append(AuditEvent.event_type == event_type[:64])
    if area:
        if area not in AREAS:
            raise ValidationError("Unknown area.")
        conds.append(AuditEvent.event_type.startswith(f"{area}.", autoescape=True))
    if result:
        conds.append(AuditEvent.result == result[:32])
    if actor_user_id is not None:
        conds.append(AuditEvent.actor_user_id == int(actor_user_id))
    if target_type:
        conds.append(AuditEvent.target_type == target_type[:64])
    if request_id:
        conds.append(AuditEvent.request_id == request_id[:64])
    if since is not None:
        conds.append(AuditEvent.created_at >= since)
    return conds


def _audit_row(r: AuditEvent, *, with_context: bool) -> dict:
    out = {"id": r.id, "event_type": r.event_type, "result": r.result, "actor_user_id": r.actor_user_id, "target_type": r.target_type,
           "target_id": r.target_id, "request_id": r.request_id, "created_at": _iso(r.created_at)}
    # Context only for admin events (built by build_audit, which rejects secret/content keys); never other writers' context.
    out["context"] = r.context if (with_context and r.event_type in ADMIN_EVENT_NAMES) else None
    return out


class SecurityEventService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- security events ---------------------------------------------------------------------------------------------------
    def events(self, *, category: str | None = None, severity: str | None = None, result: str | None = None, period: str | None = "7d",
               request_id: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        if category and category not in D.SECURITY_CATEGORIES:
            raise ValidationError("Unknown category.")
        if severity and severity not in D.SECURITY_SEVERITIES:
            raise ValidationError("Unknown severity.")
        types = [t for t, (c, sv) in D.SECURITY_EVENT_TYPES.items()
                 if (not category or c == category) and (not severity or sv == severity)]
        since = _since(period, allow_all=True)
        conds = [AuditEvent.event_type.in_(types or ["__none__"])] + _filters(
            event_type=None, area=None, result=result, actor_user_id=None, target_type=None, request_id=request_id, since=since)
        # An authentication event is a SECURITY event only when it failed.
        conds.append((AuditEvent.event_type != "account.login") | (AuditEvent.result != "success"))
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(AuditEvent).where(*conds)) or 0)
            rows = s.scalars(select(AuditEvent).where(*conds).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            items = []
            for r in rows:
                cat, sev = D.SECURITY_EVENT_TYPES[r.event_type]
                items.append({"id": r.id, "event_type": r.event_type, "category": cat, "severity": sev, "actor_user_id": r.actor_user_id,
                              "target_type": r.target_type, "target_id": r.target_id, "result": r.result, "request_id": r.request_id,
                              "created_at": _iso(r.created_at)})
        return {"items": items, "total": total, "page": page, "page_size": page_size, "anomalies": self.anomalies(),
                "advanced_anomaly_detection": False}

    def anomalies(self) -> list[dict]:
        """Deterministic rules over existing audit rows for KNOWN accounts only (no IP/device/email tracking, no classifier)."""
        now = utcnow()
        since = now - timedelta(seconds=D.BURST_WINDOW_SECONDS)
        out: list[dict] = []
        rules = (("authentication_failure_burst", "account.login", D.AUTH_FAILURE_BURST_THRESHOLD, True),
                 ("admin_access_denied_burst", "admin.access.denied", D.DENIED_BURST_THRESHOLD, False))
        with self._sf() as s:
            for rule, etype, threshold, failures_only in rules:
                conds = [AuditEvent.event_type == etype, AuditEvent.created_at >= since, AuditEvent.actor_user_id.is_not(None)]
                if failures_only:
                    conds.append(AuditEvent.result != "success")
                for actor, n in s.execute(select(AuditEvent.actor_user_id, func.count()).where(*conds)
                                          .group_by(AuditEvent.actor_user_id).having(func.count() >= threshold)
                                          .order_by(AuditEvent.actor_user_id)).all():
                    out.append({"rule": rule, "actor_user_id": actor, "count": int(n), "window_minutes": D.BURST_WINDOW_SECONDS // 60,
                                "threshold": threshold, "since": _iso(since)})
        return out

    # -- audit browsing -------------------------------------------------------------------------------------------------------
    def browse(self, *, event_type=None, area=None, result=None, actor_user_id=None, target_type=None, request_id=None, period="all",
               page: int = 1, page_size: int = 50) -> dict:
        page, page_size = _page(page, page_size)
        conds = _filters(event_type=event_type, area=area, result=result, actor_user_id=actor_user_id, target_type=target_type,
                         request_id=request_id, since=_since(period, allow_all=True))
        with self._sf() as s:
            total = int(s.scalar(select(func.count()).select_from(AuditEvent).where(*conds)) or 0)
            rows = s.scalars(select(AuditEvent).where(*conds).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            items = [_audit_row(r, with_context=True) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # -- bounded export --------------------------------------------------------------------------------------------------------
    EXPORT_FIELDS = ("id", "created_at", "event_type", "result", "actor_user_id", "target_type", "target_id", "request_id")

    def export_snapshot(self, *, fmt: str, period: str, event_type=None, area=None, result=None, actor_user_id=None, target_type=None,
                        request_id=None) -> dict:
        """Take the bounded snapshot. The export audit event is written AFTER this snapshot, so a file never contains its own export event."""
        if fmt not in D.EXPORT_FORMATS:
            raise ValidationError("Unknown export format.")
        since = _since(period, allow_all=False)
        if AUDIT_PERIODS[period] > D.EXPORT_MAX_DAYS * 86400:
            raise ValidationError("Export period too long.")
        conds = _filters(event_type=event_type, area=area, result=result, actor_user_id=actor_user_id, target_type=target_type,
                         request_id=request_id, since=since)
        with self._sf() as s:
            rows = s.scalars(select(AuditEvent).where(*conds).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                             .limit(D.EXPORT_MAX_ROWS + 1)).all()
            if len(rows) > D.EXPORT_MAX_ROWS:
                raise ValidationError(f"The export would exceed {D.EXPORT_MAX_ROWS} rows. Narrow the period or filters.")
            records = [{k: v for k, v in _audit_row(r, with_context=False).items() if k in self.EXPORT_FIELDS} for r in rows]
        return {"records": records, "count": len(records), "format": fmt}

    @staticmethod
    def render(records: list[dict], fmt: str) -> tuple[str, str]:
        if fmt == "json":
            return json.dumps({"events": records}, separators=(",", ":")), "application/json"
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(SecurityEventService.EXPORT_FIELDS)
        for r in records:
            w.writerow([_csv_safe(r.get(k)) for k in SecurityEventService.EXPORT_FIELDS])
        return buf.getvalue(), "text/csv"


def _csv_safe(v) -> str:
    text = "" if v is None else str(v)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text
