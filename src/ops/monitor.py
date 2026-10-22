"""Alert rules, maintenance tick and API-side loop of operational monitoring (05C).

Rules: each signal (``signals.py``) drives ONE existing in-app alert category with a stable dedupe key equal to the category. ``failing`` raises (or refreshes) the alert; a recurrence of a
resolved condition reopens the SAME row (the existing mechanism, no duplicates); ``ok`` auto-resolves it (a system resolution with no actor); ``unknown`` changes nothing, so missing
evidence neither raises nor clears. An already-active alert is refreshed at most every ``REFRESH_SECONDS`` so a condition seen every minute does not rewrite its row each time.
Alerts are in-app only (no paging, email or webhook) and hold only the code-defined title, the category and the signal code as source id.

The maintenance tick additionally RELEASES expired quota reservations (``UsageQuotaService.reap_expired``, previously unscheduled). It is idempotent, so the worker and the API loop may
both run it. Nothing here raises into the caller: monitoring must never break the operation it observes.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping

from sqlalchemy import select

from src.admin_security.alerts import record_condition, resolve_condition
from src.ops.signals import FAILING, OK, Signal, Thresholds, evaluate_signals
from src.persistence import AdminNotification, utcnow

log = logging.getLogger("ask4mo.ops")

REFRESH_SECONDS = 300
DEFAULT_INTERVAL_S = 60
LOCAL_ENVIRONMENTS = ("development", "dev", "local", "test", "testing")


def _aware(dt: datetime | None, ref: datetime) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=ref.tzinfo)


@dataclass
class CycleResult:
    signals: list[Signal] = field(default_factory=list)
    raised: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    reaped: int | None = None
    reaper_error: bool = False


def apply_signals(sf, signals: list[Signal], *, now: datetime | None = None) -> tuple[list[str], list[str]]:
    """Turn signals into alert state. Returns (categories raised or refreshed, categories resolved)."""
    n = now or utcnow()
    raised: list[str] = []
    resolved: list[str] = []
    for sig in signals:
        try:
            if sig.status == FAILING:
                with sf() as s:
                    row = s.scalar(select(AdminNotification).where(AdminNotification.dedupe_key == sig.category))
                    fresh = row is not None and row.state in ("active", "acknowledged") and _aware(row.last_seen_at, n) > n - timedelta(seconds=REFRESH_SECONDS)
                if not fresh:
                    record_condition(sf, category=sig.category, dedupe_key=sig.category, source_id=sig.code)
                raised.append(sig.category)
            elif sig.status == OK:
                if resolve_condition(sf, dedupe_key=sig.category):
                    resolved.append(sig.category)
        except Exception:  # noqa: BLE001
            log.warning("monitoring alert could not be applied")
    return raised, resolved


def run_monitoring_cycle(sf, *, now: datetime | None = None, thresholds: Thresholds | None = None, environ: Mapping[str, str] | None = None, reap: bool = True,
                         quota_factory: Callable[[Any], Any] | None = None) -> CycleResult:
    """One evaluation: release expired quota reservations (when ``reap``), derive every signal, apply the alert rules. Never raises."""
    out = CycleResult()
    n = now or utcnow()
    if reap:
        try:
            from src.application.usage_quota import UsageQuotaService

            svc = (quota_factory or UsageQuotaService.from_session_factory)(sf)
            out.reaped = int(svc.reap_expired())
        except Exception as exc:  # noqa: BLE001 - the stale-reaper signal reports a reaper that is not working
            out.reaper_error = True
            log.warning("quota reaper failed (%s)", type(exc).__name__)
    try:
        out.signals = evaluate_signals(sf, now=n, thresholds=thresholds, environ=environ)
        out.raised, out.resolved = apply_signals(sf, out.signals, now=n)
    except Exception as exc:  # noqa: BLE001
        log.warning("monitoring evaluation failed (%s)", type(exc).__name__)
    return out


class MaintenanceTick:
    """Runs ``run_monitoring_cycle`` at most once per ``interval_s`` per process (the worker loop calls ``maybe_run`` every cycle)."""

    def __init__(self, sf, *, interval_s: float = DEFAULT_INTERVAL_S, clock: Callable[[], datetime] = utcnow, environ: Mapping[str, str] | None = None,
                 thresholds: Thresholds | None = None, reap: bool = True) -> None:
        self._sf, self.interval = sf, max(1.0, float(interval_s))
        self._clock, self._env, self._thresholds, self._reap = clock, environ, thresholds, reap
        self._last: datetime | None = None

    def due(self) -> bool:
        return self._last is None or (self._clock() - self._last).total_seconds() >= self.interval

    def maybe_run(self) -> CycleResult | None:
        if not self.due():
            return None
        self._last = self._clock()
        return run_monitoring_cycle(self._sf, now=self._last, thresholds=self._thresholds, environ=self._env, reap=self._reap)


def interval_from_env(environ: Mapping[str, str] | None = None) -> float:
    raw = (os.environ if environ is None else environ).get("OPS_MONITOR_INTERVAL_SECONDS")
    try:
        v = float(raw) if raw else DEFAULT_INTERVAL_S
    except ValueError:
        v = DEFAULT_INTERVAL_S
    return max(10.0, min(3600.0, v))


def api_monitor_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """``OPS_MONITOR_ENABLED`` decides explicitly; unset means ON for hosted environments (anything but the local labels) and OFF for development and tests."""
    env = os.environ if environ is None else environ
    explicit = (env.get("OPS_MONITOR_ENABLED") or "").strip().lower()
    if explicit in ("1", "true", "yes", "on"):
        return True
    if explicit in ("0", "false", "no", "off"):
        return False
    return (env.get("API_ENV") or "development").strip().lower() not in LOCAL_ENVIRONMENTS


class ApiMonitorLoop:
    """A daemon thread in the API process that runs the maintenance tick, so a dead worker is still noticed (the worker cannot report its own absence). The first evaluation happens after
    one interval, never at startup, so importing or starting an app does no database work."""

    def __init__(self, sf, *, interval_s: float | None = None) -> None:
        self._tick = MaintenanceTick(sf, interval_s=interval_s or interval_from_env())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._tick._last = self._tick._clock()          # first run after one interval
        self._thread = threading.Thread(target=self._run, name="ops-monitor", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(min(self._tick.interval, 15.0)):
            try:
                self._tick.maybe_run()
            except Exception:  # noqa: BLE001
                log.warning("api monitor cycle failed")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
