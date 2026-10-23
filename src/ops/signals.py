"""Operational health signals (05C): API, worker, job queue, indexing, provider, quota reaper and AI budget.

Every signal is DERIVED from facts the platform already records (``operational_metric_events``, ``job_workers``, ``jobs``, ``usage_quota_reservations``, ``ai_budget_entries`` and the budget
status). Nothing is probed, no provider is contacted and no secret is read. A signal carries a status (``ok``, ``failing`` or ``unknown``) and a detail dictionary of integers and fixed
codes only: no prompt, response, key, user identifier, path or exception text. ``unknown`` means "the data to judge does not exist (yet)" and never raises an alert and never looks healthy
in Admin; it is not ``ok``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping

from sqlalchemy import func, select

from src.persistence import AiBudgetEntry, Job, JobWorker, OperationalMetricEvent, UsageQuotaReservation, utcnow

OK, FAILING, UNKNOWN = "ok", "failing", "unknown"
KNOWLEDGE_JOB_TYPES = ("knowledge_parse", "knowledge_index", "knowledge_remove_index", "knowledge_reindex")


@dataclass(frozen=True)
class Thresholds:
    """Engineering defaults for when a derived condition counts as failing. They only decide WHEN an in-app alert is raised; nothing else depends on them."""

    window_s: int = 900                 # look-back window for rate signals
    api_min_requests: int = 20          # fewer requests than this in the window: not enough evidence (unknown)
    api_failing_rate: float = 0.25      # server errors / requests
    provider_min_calls: int = 5
    provider_failing_rate: float = 0.5  # failed calls / calls
    worker_stale_s: int = 180           # no heartbeat for this long (and no running job with a live lease) = no worker
    backlog_age_s: int = 900            # a runnable queued job older than this is a backlog
    indexing_age_s: int = 1800          # a knowledge job queued or running longer than this is stalled
    reaper_grace_s: int = 900           # an expired reservation still held this long after expiry means the reaper is not running
    budget_low_headroom: float = 0.10   # remaining share of the stop threshold below which the budget needs attention


@dataclass(frozen=True)
class Signal:
    code: str
    category: str                       # the alert category this signal drives
    status: str
    detail: Mapping[str, Any] = field(default_factory=dict)


def api_signal(sf, now: datetime, t: Thresholds) -> Signal:
    since = now - timedelta(seconds=t.window_s)
    with sf() as s:
        rows = dict(s.execute(select(OperationalMetricEvent.outcome, func.count()).where(OperationalMetricEvent.event_type == "request", OperationalMetricEvent.occurred_at >= since)
                              .group_by(OperationalMetricEvent.outcome)).all())
    total = sum(rows.values())
    errors = int(rows.get("server_error", 0)) + int(rows.get("unavailable", 0))
    detail = {"requests": total, "server_errors": errors, "window_s": t.window_s}
    if total < t.api_min_requests:
        return Signal("api_error_rate", "api_error_rate_high", UNKNOWN if total == 0 else OK, detail)
    return Signal("api_error_rate", "api_error_rate_high", FAILING if errors / total >= t.api_failing_rate else OK, detail)


def provider_signal(sf, now: datetime, t: Thresholds) -> Signal:
    """Observed real provider calls: first-party operational events and, when the governor is enforcing, its ledger. Either source failing makes the signal failing."""
    since = now - timedelta(seconds=t.window_s)
    with sf() as s:
        ev = dict(s.execute(select(OperationalMetricEvent.outcome, func.count()).where(OperationalMetricEvent.event_type == "provider_call", OperationalMetricEvent.occurred_at >= since)
                            .group_by(OperationalMetricEvent.outcome)).all())
        since_ts = since.timestamp()
        led_total = int(s.scalar(select(func.count()).select_from(AiBudgetEntry).where(AiBudgetEntry.created_ts >= since_ts, AiBudgetEntry.state != "reserved")) or 0)
        led_err = int(s.scalar(select(func.count()).select_from(AiBudgetEntry).where(AiBudgetEntry.created_ts >= since_ts, AiBudgetEntry.state.in_(("unknown", "rejected")),
                                                                                     AiBudgetEntry.error_category.is_not(None))) or 0)
    ev_total, ev_err = sum(ev.values()), sum(n for o, n in ev.items() if o != "success")
    detail = {"events": ev_total, "event_failures": ev_err, "ledger_calls": led_total, "ledger_failures": led_err, "window_s": t.window_s}
    judged = False
    failing = False
    for total, err in ((ev_total, ev_err), (led_total, led_err)):
        if total >= t.provider_min_calls:
            judged = True
            failing = failing or (err / total >= t.provider_failing_rate)
    if failing:
        return Signal("provider_health", "provider_unhealthy", FAILING, detail)
    return Signal("provider_health", "provider_unhealthy", OK if judged else UNKNOWN, detail)


def worker_signal(sf, now: datetime, t: Thresholds) -> Signal:
    stale = now - timedelta(seconds=t.worker_stale_s)
    backlog_since = now - timedelta(seconds=t.backlog_age_s)
    with sf() as s:
        live = int(s.scalar(select(func.count()).select_from(JobWorker).where(JobWorker.status == "running", JobWorker.last_seen_at >= stale)) or 0)
        known = int(s.scalar(select(func.count()).select_from(JobWorker)) or 0)
        leased = int(s.scalar(select(func.count()).select_from(Job).where(Job.state == "running", Job.lease_expires_at >= now)) or 0)   # a long job keeps its worker alive
        waiting = int(s.scalar(select(func.count()).select_from(Job).where(Job.state == "queued", Job.available_at <= backlog_since)) or 0)
    detail = {"live_workers": live, "workers_ever_seen": known, "running_jobs_with_live_lease": leased, "runnable_jobs_waiting_too_long": waiting}
    if live or leased:
        return Signal("worker_health", "worker_unhealthy", OK, detail)
    if waiting:
        return Signal("worker_health", "worker_unhealthy", FAILING, detail)       # work is waiting and nothing is running it
    return Signal("worker_health", "worker_unhealthy", FAILING if known else UNKNOWN, detail)    # a worker existed and is gone: failing; never seen and nothing waiting: unknown


def backlog_signal(sf, now: datetime, t: Thresholds, worker: Signal) -> Signal:
    since = now - timedelta(seconds=t.backlog_age_s)
    with sf() as s:
        waiting = int(s.scalar(select(func.count()).select_from(Job).where(Job.state == "queued", Job.available_at <= since)) or 0)
    detail = {"runnable_jobs_waiting_too_long": waiting, "age_s": t.backlog_age_s}
    if worker.status != OK:
        return Signal("job_backlog", "job_queue_backlog", UNKNOWN, detail)         # without a live worker the worker alert already covers it (no duplicate alert)
    return Signal("job_backlog", "job_queue_backlog", FAILING if waiting else OK, detail)


def indexing_signal(sf, now: datetime, t: Thresholds) -> Signal:
    since = now - timedelta(seconds=t.indexing_age_s)
    with sf() as s:
        stalled = int(s.scalar(select(func.count()).select_from(Job).where(Job.job_type.in_(KNOWLEDGE_JOB_TYPES), Job.state.in_(("queued", "running")), Job.created_at <= since)) or 0)
    return Signal("indexing_progress", "indexing_stalled", FAILING if stalled else OK, {"stalled_knowledge_jobs": stalled, "age_s": t.indexing_age_s})


def reaper_signal(sf, now: datetime, t: Thresholds) -> Signal:
    cutoff = now - timedelta(seconds=t.reaper_grace_s)
    with sf() as s:
        stuck = int(s.scalar(select(func.count()).select_from(UsageQuotaReservation).where(UsageQuotaReservation.state == "reserved", UsageQuotaReservation.expires_at < cutoff)) or 0)
    return Signal("quota_reaper", "quota_reaper_stale", FAILING if stuck else OK, {"expired_reservations_unreleased": stuck, "grace_s": t.reaper_grace_s})


def budget_signal(sf, now: datetime, t: Thresholds, environ: Mapping[str, str] | None = None) -> Signal:
    from src.llm.budget.status import budget_status

    st = budget_status(sf, environ)
    detail: dict[str, Any] = {"state": st["state"], "enforcement": st["enforcement"], "reason": st.get("reason")}
    led = st.get("ledger")
    if led:
        stop, remaining = float(led["stop_usd"]), float(led["remaining_to_stop_usd"])
        detail.update({"remaining_to_stop_usd": led["remaining_to_stop_usd"], "remaining_requests": led["remaining_requests"]})
        low = stop > 0 and remaining / stop < t.budget_low_headroom
    else:
        low = False
    if st["enforcement"] == "closed" or st["state"] in ("killed", "stopped") or st.get("reason") == "ledger_inconsistent" or (low and st["state"] == "open"):
        return Signal("ai_budget", "ai_budget_attention", FAILING, detail)
    if st["enforcement"] == "enforcing" and st["state"] == "open":
        return Signal("ai_budget", "ai_budget_attention", OK, detail)
    return Signal("ai_budget", "ai_budget_attention", UNKNOWN, detail)               # not enforcing / not configured: shown in Admin, never reported as healthy


def evaluate_signals(sf, *, now: datetime | None = None, thresholds: Thresholds | None = None, environ: Mapping[str, str] | None = None) -> list[Signal]:
    t, n = thresholds or Thresholds(), now or utcnow()
    worker = worker_signal(sf, n, t)
    return [api_signal(sf, n, t), provider_signal(sf, n, t), worker, backlog_signal(sf, n, t, worker), indexing_signal(sf, n, t), reaper_signal(sf, n, t),
            budget_signal(sf, n, t, os.environ if environ is None else environ)]
