"""First-party operational telemetry and canonical AI usage capture (P10B-W10.12). Best-effort: NOTHING here may break the operation it observes.

Operational events carry only bounded, code-defined labels: an event type, a subsystem, an ``operation`` label chosen from a fixed table (never a raw
URL, path, id or query string), an outcome, an optional duration, a safe error category and a provider code. No identity, body, prompt, exception text
or candidate content is ever recorded. Admin traffic is never recorded (reporting must not measure itself).

AI usage capture happens at ONE canonical boundary per workflow, so a provider call is counted once:
* Agent: the run's CUMULATIVE aggregate (agent calls + the model-backed tools inside it, already summed by ``src/agent/usage.py``) is upserted ONCE per
  run (key ``agent:<run_id>``). Nested tool calls are never added again.
* Practice: each canonical ``UsageRecord`` of a session is recorded ONCE (key ``practice:<session_id>:<index>``).
"""

from __future__ import annotations

import logging
import re
import threading

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.persistence import (
    AI_USAGE_COST_SOURCES, OPERATIONAL_EVENT_TYPES, OPERATIONAL_OUTCOMES, AIUsageFact, OperationalMetricEvent, utcnow,
)

log = logging.getLogger(__name__)
__all__ = ["install", "uninstall", "record_event", "record_agent_usage", "record_practice_usage", "route_label", "outcome_for_status", "usage_micros"]

_lock = threading.Lock()
_sf = None
_SAFE = re.compile(r"^[a-z0-9_]{1,40}$")

# Code-defined request operation labels. A request is recorded ONLY if its matched route TEMPLATE maps here; the raw path is never stored.
_REQUEST_LABELS: tuple[tuple[str, str, str, str], ...] = (
    # (method, regex over the route TEMPLATE, subsystem, operation)
    ("POST", r"/agent/run$", "agent", "agent_run"),
    ("POST", r"/agent/runs/\{[^}]+\}/messages$", "agent", "agent_continue"),
    ("POST", r"/agent/runs/\{[^}]+\}/resume$", "agent", "agent_resume"),
    ("POST", r"/career/chat$", "career", "career_chat"),
    ("POST", r"/research/company$", "research", "company_research"),
    ("POST", r"/interviews$", "practice", "practice_create"),
    ("POST", r"/interviews/\{[^}]+\}/[a-z-]+$", "practice", "practice_step"),
    ("POST", r"/documents$", "documents", "document_upload"),
    ("POST", r"/voice/realtime/session$", "voice", "realtime_session"),
    ("POST", r"/privacy/requests$", "privacy", "privacy_request"),
)


def install(session_factory) -> None:
    global _sf
    with _lock:
        _sf = session_factory


def uninstall() -> None:
    global _sf
    with _lock:
        _sf = None


def route_label(method: str, template: str | None) -> tuple[str, str] | None:
    """(subsystem, operation) for a matched route template, or None (not recorded). Admin routes are never recorded."""
    if not template or "/admin" in template:
        return None
    for m, pattern, subsystem, operation in _REQUEST_LABELS:
        if method.upper() == m and re.search(pattern, template):
            return subsystem, operation
    return None


def outcome_for_status(status: int) -> str:
    if status == 503:
        return "unavailable"
    if status >= 500:
        return "server_error"
    if status >= 400:
        return "client_error"
    return "success"


def _clean(value: str | None, limit: int = 32) -> str | None:
    if value is None:
        return None
    v = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return v[:limit] if re.match(r"^[a-z0-9_]+$", v) else "other"


def record_event(event_type: str, subsystem: str, operation: str, outcome: str, *, duration_ms: int | None = None,
                 error_category: str | None = None, provider: str | None = None) -> bool:
    """Persist one bounded event. Returns False (never raises) if it could not be recorded."""
    sf = _sf
    if sf is None or event_type not in OPERATIONAL_EVENT_TYPES or outcome not in OPERATIONAL_OUTCOMES:
        return False
    if not _SAFE.match(subsystem or "") or not _SAFE.match(operation or ""):
        return False
    try:
        with sf() as s:
            s.add(OperationalMetricEvent(event_type=event_type, subsystem=subsystem[:24], operation=operation[:40], outcome=outcome,
                                         duration_ms=None if duration_ms is None else max(0, int(duration_ms)), error_category=_clean(error_category),
                                         provider=_clean(provider, 24), occurred_at=utcnow()))
            s.commit()
        return True
    except Exception:  # noqa: BLE001 - observation must never affect the operation
        log.warning("operational telemetry could not be recorded")
        return False


# ---------------------------------------------------------------------------------------------------------------- AI usage
def usage_micros(cost_usd: float | None) -> int | None:
    """USD (float, as the existing usage records carry it) -> integer micro-USD. None stays None: unknown is never zero."""
    if cost_usd is None:
        return None
    return int(round(float(cost_usd) * 1_000_000))


def _coverage(known: bool, complete: bool) -> str:
    return "unknown" if not known else ("complete" if complete else "partial")


def record_agent_usage(session_factory, user_id: int | str | None, run_id: str, usage: dict | None, profile: str | None) -> bool:
    """Upsert the run's CUMULATIVE canonical aggregate (one fact per run; a later turn replaces the earlier cumulative value, never adds to it)."""
    if not usage or not run_id or user_id is None:
        return False
    try:
        uid = int(user_id)
        calls = int(usage.get("model_calls") or 0)
        tin, tout, ttot = usage.get("input_tokens"), usage.get("output_tokens"), usage.get("total_tokens")
        complete = bool(usage.get("usage_complete", True))
        cost = usage.get("estimated_cost_usd")
        if tin is not None and tout is not None:
            ttot = int(tin) + int(tout)
        micros = usage_micros(cost)
        from src.llm.models import ModelProfile, model_id

        try:
            prof = ModelProfile(profile) if profile else None
        except ValueError:
            prof = None
        mid = model_id(prof) if prof else None
        key = f"agent:{run_id}"[:80]
        with session_factory() as s:
            row = s.scalar(select(AIUsageFact).where(AIUsageFact.usage_key == key))
            if row is not None:
                if calls < row.model_calls:                       # never replace a larger cumulative aggregate with a smaller one
                    return False
            else:
                row = AIUsageFact(usage_key=key, user_id=uid, workflow="agent", operation="run", occurred_at=utcnow())
                s.add(row)
            row.model_profile = prof.value if prof else None
            row.model_id = mid
            row.model_calls = calls
            row.input_tokens = None if tin is None else int(tin)
            row.output_tokens = None if tout is None else int(tout)
            row.total_tokens = None if ttot is None else int(ttot)
            row.cost_usd_micros = micros
            row.cost_source = "reported" if micros is not None else "unavailable"
            row.token_coverage = _coverage(ttot is not None, complete)
            row.cost_coverage = _coverage(micros is not None, complete)
            row.updated_at = utcnow()
            try:
                s.commit()
            except IntegrityError:
                s.rollback()                                      # a concurrent first insert: the other writer's row stands
                return False
        return True
    except Exception:  # noqa: BLE001
        log.warning("agent usage fact could not be recorded")
        return False


def record_practice_usage(session_factory, user_id: int, session_id: str, start_index: int, records: list, operation: str | None) -> int:
    """Record each NEW canonical Practice ``UsageRecord`` once (key ``practice:<session>:<index>``). Replays hit the unique key and add nothing."""
    written = 0
    op = _clean(operation or "step", 32) or "step"
    for offset, rec in enumerate(records):
        try:
            idx = start_index + offset
            source = rec.cost_source if rec.cost_source in AI_USAGE_COST_SOURCES else "unavailable"
            if source == "reported" and rec.reported_cost is not None:
                micros = usage_micros(rec.reported_cost)
            elif source == "calculated":
                micros = usage_micros(rec.calculated_cost)
            else:
                source, micros = "unavailable", None            # unavailable cost is NULL, never 0
            from src.llm.models import known_profile_for_slug

            prof = known_profile_for_slug(rec.model)
            with session_factory() as s:
                s.add(AIUsageFact(usage_key=f"practice:{session_id}:{idx}"[:80], user_id=int(user_id), workflow="practice", operation=op,
                                  model_profile=prof.value if prof else None, model_id=str(rec.model)[:80], model_calls=1,
                                  input_tokens=int(rec.prompt_tokens), output_tokens=int(rec.completion_tokens), total_tokens=int(rec.prompt_tokens) + int(rec.completion_tokens),
                                  cost_usd_micros=micros, cost_source=source, token_coverage="complete", cost_coverage="complete" if micros is not None else "unknown",
                                  occurred_at=utcnow(), updated_at=utcnow()))
                try:
                    s.commit()
                    written += 1
                except IntegrityError:
                    s.rollback()
        except Exception:  # noqa: BLE001
            log.warning("practice usage fact could not be recorded")
    return written


# ------------------------------------------------------------------------------------------------------------ request middleware
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402


class OperationalTelemetryMiddleware(BaseHTTPMiddleware):
    """Record a bounded outcome for code-defined candidate operations. Installed as the INNERMOST user middleware so an unhandled exception is seen
    (and re-raised unchanged) before the catch-all converts it. Never records Admin traffic, raw paths, queries, bodies or identities."""

    async def dispatch(self, request, call_next):
        import time as _time

        started = _time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            try:
                route = request.scope.get("route")
                label = route_label(request.method, getattr(route, "path", None))
                if label is not None and _sf is not None:
                    record_event("request", label[0], label[1], outcome_for_status(status), duration_ms=int((_time.perf_counter() - started) * 1000))
            except Exception:  # noqa: BLE001
                pass
