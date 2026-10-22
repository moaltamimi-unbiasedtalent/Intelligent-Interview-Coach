"""05C PR 2: operational monitoring and alerts. Offline and deterministic: temp databases, fake clocks, mocked providers, no network, no real key.

Covers every health signal (API, worker, job queue, indexing, provider, quota reaper, AI budget), alert dedupe and auto-resolve on the EXISTING in-app mechanism, the scheduled
quota-reservation reaper, the worker and API hooks, a SYNTHETIC OUTAGE that raises an alert through the real client + governor path, secrets never reaching telemetry, the Admin provider
readiness addition, migration 0045, and hosted-environment pause verification.
"""

from __future__ import annotations

import json
import socket
import threading
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select, text

from src.llm.budget import config as BC
from src.llm.budget import governor as G
from src.ops import monitor as M
from src.ops import signals as S
from src.persistence import (
    AdminNotification, AiBudgetEntry, Base, Job, JobWorker, OperationalMetricEvent, UsageQuotaReservation, make_engine, make_session_factory, utcnow,
)
from tests.test_ai_budget_governor_05c import MARKER, raw_config

KEY = "sk-or-v1-SENTINEL-KEY-FOR-TELEMETRY-9876"
NOW = datetime.now(timezone.utc).replace(microsecond=0)        # alert rows are stamped with the real clock, so the fake "now" starts at the real one
CATS = ("api_error_rate_high", "worker_unhealthy", "job_queue_backlog", "indexing_stalled", "provider_unhealthy", "quota_reaper_stale", "ai_budget_attention")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", BC.MODE_ENV, BC.CLASS_ENV, BC.MARKER_ENV, BC.KILL_ENV, BC.CONFIG_PATH_ENV, "API_ENV", "OPS_MONITOR_ENABLED", "OPS_MONITOR_INTERVAL_SECONDS", "ASK4MO_PROVIDER_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)

    def refuse(*a, **k):
        raise AssertionError("a real network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield
    G.uninstall()


@pytest.fixture()
def sf(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'ops.db'}")
    Base.metadata.create_all(eng)
    yield make_session_factory(eng)
    eng.dispose()


def alerts(sf, state=None):
    with sf() as s:
        q = select(AdminNotification)
        if state:
            q = q.where(AdminNotification.state == state)
        return list(s.scalars(q.order_by(AdminNotification.id)))


def add_events(sf, event_type, outcome, n, *, at=NOW, subsystem="career", operation="career_chat"):
    with sf() as s:
        for _ in range(n):
            s.add(OperationalMetricEvent(event_type=event_type, subsystem=subsystem, operation=operation, outcome=outcome, occurred_at=at))
        s.commit()


def cycle(sf, now=NOW, **kw):
    kw.setdefault("environ", {})
    kw.setdefault("reap", False)
    return M.run_monitoring_cycle(sf, now=now, **kw)


def status(result, code):
    return next(x.status for x in result.signals if x.code == code)


# ====================================================================================================== API signal and alert lifecycle
def test_api_signal_unknown_without_evidence_ok_below_threshold_failing_above(sf):
    assert status(cycle(sf), "api_error_rate") == S.UNKNOWN and not alerts(sf)             # no data: unknown, no alert, never "ok"
    add_events(sf, "request", "success", 30)
    r = cycle(sf)
    assert status(r, "api_error_rate") == S.OK and not alerts(sf)
    add_events(sf, "request", "server_error", 12)                                         # 12 of 42 = 28.6% >= 25%
    r = cycle(sf)
    assert status(r, "api_error_rate") == S.FAILING and r.raised == ["api_error_rate_high"]
    [a] = alerts(sf)
    assert a.category == "api_error_rate_high" and a.state == "active" and a.severity == "high" and a.source_id == "api_error_rate"


def test_too_few_requests_never_raise_and_503_counts_as_failure(sf):
    add_events(sf, "request", "server_error", 5)                                          # below the 20-request minimum
    assert status(cycle(sf), "api_error_rate") == S.OK and not alerts(sf)
    add_events(sf, "request", "unavailable", 20)
    assert status(cycle(sf), "api_error_rate") == S.FAILING


def test_dedupe_one_row_per_condition_refresh_is_rate_limited_and_recovery_auto_resolves(sf):
    add_events(sf, "request", "server_error", 30)
    cycle(sf, NOW)
    cycle(sf, NOW + timedelta(seconds=60))                                                 # seen again inside the refresh window: not rewritten
    assert len(alerts(sf)) == 1 and alerts(sf)[0].occurrence_count == 1
    cycle(sf, NOW + timedelta(seconds=M.REFRESH_SECONDS + 5), thresholds=S.Thresholds(window_s=10_000))   # refreshed after the window: same row, count incremented
    assert len(alerts(sf)) == 1 and alerts(sf)[0].occurrence_count == 2
    # recovery: the failing events fall out of the window and healthy traffic arrives
    later = NOW + timedelta(hours=2)
    add_events(sf, "request", "success", 40, at=later)
    r = cycle(sf, later)
    assert r.resolved == ["api_error_rate_high"]
    [a] = alerts(sf)
    assert a.state == "resolved" and a.resolved_by_user_id is None and a.resolved_at is not None       # a system resolution, no actor
    # the condition recurs: the SAME alert is reopened, never a duplicate
    add_events(sf, "request", "server_error", 200, at=later + timedelta(minutes=5))
    cycle(sf, later + timedelta(minutes=6))
    [a] = alerts(sf)
    assert a.state == "active" and a.resolved_at is None


def test_unknown_neither_raises_nor_clears_an_existing_alert(sf):
    add_events(sf, "request", "server_error", 30)
    cycle(sf)
    assert [a.state for a in alerts(sf)] == ["active"]
    r = cycle(sf, NOW + timedelta(days=2))                                                 # the window is empty again: unknown, not ok
    assert status(r, "api_error_rate") == S.UNKNOWN and [a.state for a in alerts(sf)] == ["active"]


def test_an_acknowledged_alert_stays_acknowledged_while_the_condition_holds(sf):
    add_events(sf, "request", "server_error", 30)
    cycle(sf)
    with sf() as s:
        a = s.scalar(select(AdminNotification))
        a.state, a.acknowledged_at = "acknowledged", utcnow()
        s.commit()
    cycle(sf, NOW + timedelta(seconds=M.REFRESH_SECONDS + 5), thresholds=S.Thresholds(window_s=10_000))
    assert [a.state for a in alerts(sf)] == ["acknowledged"] and len(alerts(sf)) == 1


# ====================================================================================================== provider signal
def test_provider_signal_from_events_and_from_the_budget_ledger(sf):
    assert status(cycle(sf), "provider_health") == S.UNKNOWN
    add_events(sf, "provider_call", "success", 4)
    assert status(cycle(sf), "provider_health") == S.UNKNOWN                               # 4 < 5 calls: not enough evidence
    add_events(sf, "provider_call", "error", 6)                                            # 6 of 10 failing
    r = cycle(sf)
    assert status(r, "provider_health") == S.FAILING and "provider_unhealthy" in r.raised
    assert alerts(sf)[0].source_type == "provider"


def test_provider_signal_uses_the_ledger_when_events_are_absent(sf):
    with sf() as s:
        for i in range(6):
            s.add(AiBudgetEntry(created_ts=NOW.timestamp() - 10, budget_class="development", category="agent", operation="agent", model="m", endpoint="chat", fingerprint=f"{i:064d}",
                                state="unknown", reserved_micro_usd=100, error_category="server_error"))
        s.commit()
    assert status(cycle(sf), "provider_health") == S.FAILING


# ====================================================================================================== worker, backlog, indexing
def add_worker(sf, *, last_seen, status_="running"):
    with sf() as s:
        s.add(JobWorker(worker_id="w1", status=status_, started_at=last_seen, last_seen_at=last_seen))
        s.commit()


def add_job(sf, *, state="queued", job_type="knowledge_index", created=NOW, available=NOW, lease=None, pid="j1"):
    with sf() as s:
        s.add(Job(public_id=pid, job_type=job_type, state=state, payload_json={}, created_at=created, available_at=available,
                  lease_owner="w1" if state == "running" else None, lease_expires_at=lease if state == "running" else None))
        s.commit()


def test_worker_signal_matrix(sf):
    assert status(cycle(sf), "worker_health") == S.UNKNOWN and not alerts(sf)             # never seen a worker, nothing waiting: unknown
    add_worker(sf, last_seen=NOW - timedelta(seconds=10))
    assert status(cycle(sf), "worker_health") == S.OK
    r = cycle(sf, NOW + timedelta(hours=1))                                                # the worker stopped heartbeating
    assert status(r, "worker_health") == S.FAILING and "worker_unhealthy" in r.raised
    cycle(sf, NOW + timedelta(hours=1, seconds=1))
    assert [a.category for a in alerts(sf)] == ["worker_unhealthy"]


def test_a_waiting_job_with_no_worker_ever_is_a_worker_failure_and_a_long_running_job_keeps_the_worker_alive(sf):
    add_job(sf, available=NOW - timedelta(hours=1), created=NOW - timedelta(hours=1))
    r = cycle(sf)
    assert status(r, "worker_health") == S.FAILING and status(r, "job_backlog") == S.UNKNOWN       # one alert (the worker one), no duplicate backlog alert
    assert [a.category for a in alerts(sf)] == ["worker_unhealthy", "indexing_stalled"]


def test_running_job_with_a_live_lease_counts_as_a_live_worker(sf):
    add_worker(sf, last_seen=NOW - timedelta(hours=1))
    add_job(sf, state="running", lease=NOW + timedelta(minutes=5))
    assert status(cycle(sf), "worker_health") == S.OK


def test_backlog_only_when_a_live_worker_exists(sf):
    add_worker(sf, last_seen=NOW - timedelta(seconds=5))
    add_job(sf, job_type="privacy_deletion", available=NOW - timedelta(minutes=30), created=NOW - timedelta(minutes=30))
    r = cycle(sf)
    assert status(r, "worker_health") == S.OK and status(r, "job_backlog") == S.FAILING and "job_queue_backlog" in r.raised
    assert status(cycle(sf), "indexing_progress") == S.OK                                  # not a knowledge job


def test_indexing_stalled_and_recovery(sf):
    add_worker(sf, last_seen=NOW - timedelta(seconds=5))
    add_job(sf, job_type="knowledge_reindex", state="queued", created=NOW - timedelta(hours=2), available=NOW)
    r = cycle(sf)
    assert status(r, "indexing_progress") == S.FAILING and "indexing_stalled" in r.raised
    with sf() as s:
        s.execute(text("UPDATE jobs SET state='succeeded'"))
        s.commit()
    r = cycle(sf, NOW + timedelta(seconds=1))
    assert "indexing_stalled" in r.resolved and {a.category: a.state for a in alerts(sf)}["indexing_stalled"] == "resolved"


# ====================================================================================================== the scheduled quota-reservation reaper
def add_reservation(sf, key, *, expires, state="reserved"):
    from src.persistence import User

    with sf() as s:
        u = s.scalar(select(User).limit(1))
        if u is None:
            u = User(subject="u1", provider="password", status="active", platform_role="user", email_verified=True)
            s.add(u)
            s.flush()
        s.add(UsageQuotaReservation(op_key=key, user_id=u.id, feature="practice_create", period_start=expires - timedelta(days=1), state=state, policy_version="v1", expires_at=expires))
        s.commit()


def test_the_tick_releases_expired_reservations_and_leaves_live_ones(sf):
    from src.application.usage_quota import UsageQuotaService
    from src.entitlements import EntitlementService

    add_reservation(sf, "expired-1", expires=NOW - timedelta(hours=2))
    add_reservation(sf, "live-1", expires=NOW + timedelta(hours=2))
    svc = UsageQuotaService(sf, EntitlementService(sf), now=lambda: NOW)
    r = M.run_monitoring_cycle(sf, now=NOW, environ={}, reap=True, quota_factory=lambda _sf: svc)
    assert r.reaped == 1
    with sf() as s:
        states = {x.op_key: x.state for x in s.scalars(select(UsageQuotaReservation))}
    assert states == {"expired-1": "released", "live-1": "reserved"}
    assert M.run_monitoring_cycle(sf, now=NOW, environ={}, reap=True, quota_factory=lambda _sf: svc).reaped == 0        # idempotent


def test_a_reaper_that_is_not_running_raises_quota_reaper_stale_and_running_it_resolves(sf):
    add_reservation(sf, "stuck-1", expires=NOW - timedelta(hours=2))
    r = cycle(sf)                                                                          # monitoring without the reaper
    assert status(r, "quota_reaper") == S.FAILING and "quota_reaper_stale" in r.raised
    from src.application.usage_quota import UsageQuotaService
    from src.entitlements import EntitlementService

    svc = UsageQuotaService(sf, EntitlementService(sf), now=lambda: NOW)
    r = M.run_monitoring_cycle(sf, now=NOW + timedelta(seconds=1), environ={}, reap=True, quota_factory=lambda _sf: svc)
    assert r.reaped == 1 and "quota_reaper_stale" in r.resolved


def test_a_failing_reaper_never_raises_into_the_caller_and_keeps_the_alert(sf):
    add_reservation(sf, "stuck-2", expires=NOW - timedelta(hours=2))

    class Boom:
        def reap_expired(self):
            raise RuntimeError("database exploded with " + KEY)
    r = M.run_monitoring_cycle(sf, now=NOW, environ={}, reap=True, quota_factory=lambda _sf: Boom())
    assert r.reaper_error and r.reaped is None and "quota_reaper_stale" in r.raised
    assert KEY not in json.dumps([x.detail for x in r.signals], default=str)


def test_maintenance_tick_runs_at_most_once_per_interval():
    clock = [NOW]
    calls = []

    class Fake(M.MaintenanceTick):
        pass
    t = Fake(sf=None, interval_s=60, clock=lambda: clock[0])
    import src.ops.monitor as mod

    orig = mod.run_monitoring_cycle
    mod.run_monitoring_cycle = lambda *a, **k: calls.append(1) or M.CycleResult()
    try:
        assert t.maybe_run() is not None and t.maybe_run() is None
        clock[0] += timedelta(seconds=59)
        assert t.maybe_run() is None
        clock[0] += timedelta(seconds=2)
        assert t.maybe_run() is not None
    finally:
        mod.run_monitoring_cycle = orig
    assert len(calls) == 2


def test_the_worker_loop_runs_the_tick_and_a_failing_tick_never_stops_job_processing(sf):
    from src.jobs.service import JobService
    from src.jobs.worker import Worker

    ran = []

    class Tick:
        def maybe_run(self):
            ran.append(1)
            raise RuntimeError("monitor bug")
    w = Worker(JobService(sf), maintenance=Tick(), worker_id="w-test")
    assert w.run_once() == "idle" and ran == [1]                                           # the cycle completed despite the failing tick


# ====================================================================================================== AI budget signal
def budget_env(tmp_path, **extra):
    f = tmp_path / "budget.json"
    f.write_text(json.dumps(raw_config()), encoding="utf-8")
    return {BC.CONFIG_PATH_ENV: str(f), BC.CLASS_ENV: "development", **extra}


def test_budget_signal_unknown_when_not_enforcing_and_never_a_false_ok(sf, tmp_path):
    r = cycle(sf)
    assert status(r, "ai_budget") == S.UNKNOWN and not alerts(sf)
    r = cycle(sf, environ=budget_env(tmp_path, **{BC.MARKER_ENV: MARKER}))                # configured and approved but this process is not enforcing
    assert status(r, "ai_budget") == S.UNKNOWN


def test_budget_signal_failing_when_killed_stopped_closed_or_low_and_ok_when_enforcing_with_headroom(sf, tmp_path):
    env = budget_env(tmp_path, **{BC.MARKER_ENV: MARKER, BC.MODE_ENV: "enforce"})
    gov = G.install(G.BudgetGovernor.build(sf, budget_class="development", config=BC.parse_config(raw_config()), environ=env))
    assert status(cycle(sf, environ=env), "ai_budget") == S.OK
    gov.ledger.kill("operator")
    r = cycle(sf, environ=env)
    assert status(r, "ai_budget") == S.FAILING and "ai_budget_attention" in r.raised
    gov.ledger.resume()
    assert "ai_budget_attention" in cycle(sf, NOW + timedelta(seconds=1), environ=env).resolved
    with sf() as s:                                                                        # headroom below 10% of the stop threshold
        s.execute(text("UPDATE ai_budget_controls SET held_micro_usd = 750000 WHERE scope_key = 'class:development'"))
        s.add(AiBudgetEntry(created_ts=1.0, budget_class="development", category="agent", operation="a", model="m", endpoint="chat", fingerprint="f" * 64, state="settled",
                            reserved_micro_usd=750000, committed_micro_usd=750000))
        s.execute(text("UPDATE ai_budget_controls SET requests = 1 WHERE scope_key = 'class:development'"))
        s.commit()
    assert status(cycle(sf, NOW + timedelta(seconds=2), environ=env), "ai_budget") == S.FAILING


def test_a_closed_governor_is_a_budget_failure(sf, tmp_path):
    G.install(G.BudgetGovernor.closed("config_unavailable"))
    r = cycle(sf, environ={BC.MODE_ENV: "enforce"})
    assert status(r, "ai_budget") == S.FAILING and r.signals[-1].detail["enforcement"] == "closed"


# ====================================================================================================== synthetic outage through the real client + governor
def test_synthetic_provider_outage_raises_an_alert_and_recovery_resolves_it(sf, tmp_path, monkeypatch):
    from pydantic import SecretStr

    from src.config import AppConfig
    from src.openrouter_client import OpenRouterClient, OpenRouterError
    from src.reporting import telemetry

    telemetry.install(sf)
    monkeypatch.setattr(telemetry, "utcnow", lambda: NOW, raising=False)
    env = {BC.MARKER_ENV: MARKER}
    gov = G.install(G.BudgetGovernor.build(sf, budget_class="development", config=BC.parse_config(raw_config()), default_category="interview", environ=env))
    state = {"up": False}

    def handler(req):
        if not state["up"]:
            return httpx.Response(503, json={"error": {"message": f"upstream down {KEY}"}})
        return httpx.Response(200, json={"id": "x", "model": "provider/model-a", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    client = OpenRouterClient(AppConfig(api_key=SecretStr(KEY), base_url="https://openrouter.ai/api/v1"), http_client=httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda s: None)

    def call(i):
        return client.create_chat_completion(model="provider/model-a", messages=[{"role": "user", "content": f"hello {i}"}], max_tokens=100, temperature=0.2)
    failures = 0
    for i in range(8):                                                                     # the outage: eight distinct logical calls all fail
        with pytest.raises(OpenRouterError):
            call(i)
        failures += 1
    r = M.run_monitoring_cycle(sf, now=utcnow(), environ=env, reap=False)
    assert status(r, "provider_health") == S.FAILING and "provider_unhealthy" in r.raised
    active = [a for a in alerts(sf, "active") if a.category == "provider_unhealthy"]
    assert len(active) == 1 and active[0].severity == "high"
    dump = json.dumps([[a.title, a.source_id, a.category] for a in alerts(sf)]) + json.dumps([x.detail for x in r.signals], default=str)
    assert KEY not in dump and "upstream down" not in dump                                 # NO secrets or provider text in alerts or signal details
    # recovery: the provider is back; healthy calls dominate a later window
    state["up"] = True
    for i in range(20, 40):
        call(i)
    with sf() as s:                                                                        # age the outage out of the look-back window
        s.execute(text("UPDATE operational_metric_events SET occurred_at = :old WHERE outcome = 'error'"), {"old": (utcnow() - timedelta(hours=3)).isoformat(sep=" ")})
        s.execute(text("UPDATE ai_budget_entries SET created_ts = created_ts - 10800 WHERE state = 'unknown'"))
        s.commit()
    r = M.run_monitoring_cycle(sf, now=utcnow() + timedelta(seconds=1), environ=env, reap=False)
    assert status(r, "provider_health") == S.OK and "provider_unhealthy" in r.resolved
    assert [a.state for a in alerts(sf) if a.category == "provider_unhealthy"] == ["resolved"]
    telemetry.uninstall()
    assert gov.status()["calls_by_state"]["settled"] == 20


# ====================================================================================================== telemetry never carries a secret
def test_signals_and_alert_rows_hold_only_counts_and_fixed_codes(sf, tmp_path):
    add_events(sf, "request", "server_error", 30)
    add_events(sf, "provider_call", "error", 9)
    r = cycle(sf, environ=budget_env(tmp_path, **{BC.MARKER_ENV: MARKER}))
    for sig in r.signals:
        for k, v in sig.detail.items():
            assert isinstance(v, (int, float, str, type(None))) and (not isinstance(v, str) or len(v) < 40), (sig.code, k, v)
    dump = json.dumps([x.detail for x in r.signals], default=str) + json.dumps([[a.title, a.source_id, a.category, a.dedupe_key] for a in alerts(sf)])
    assert KEY not in dump and MARKER not in dump and "Bearer" not in dump


# ====================================================================================================== API monitor policy and loop
def test_api_monitor_is_on_for_hosted_environments_and_off_locally_unless_forced():
    on = M.api_monitor_enabled
    assert on({"API_ENV": "production"}) and on({"API_ENV": "staging"}) and on({"API_ENV": "weird"})
    assert not on({}) and not on({"API_ENV": "development"}) and not on({"API_ENV": "test"})
    assert not on({"API_ENV": "production", "OPS_MONITOR_ENABLED": "false"}) and on({"API_ENV": "development", "OPS_MONITOR_ENABLED": "true"})
    assert M.interval_from_env({}) == 60 and M.interval_from_env({"OPS_MONITOR_INTERVAL_SECONDS": "5"}) == 10 and M.interval_from_env({"OPS_MONITOR_INTERVAL_SECONDS": "x"}) == 60


def test_the_api_loop_does_no_work_at_start_and_stops_cleanly(sf, monkeypatch):
    calls = []
    monkeypatch.setattr(M, "run_monitoring_cycle", lambda *a, **k: calls.append(1) or M.CycleResult())
    loop = M.ApiMonitorLoop(sf, interval_s=3600)
    loop.start()
    loop.start()                                                                           # idempotent
    assert calls == []                                                                     # first evaluation is one interval away
    loop.stop()
    assert loop._thread is None and threading.active_count() >= 1


def test_the_loop_runs_the_tick_when_due(sf, monkeypatch):
    done = threading.Event()
    monkeypatch.setattr(M, "run_monitoring_cycle", lambda *a, **k: (done.set(), M.CycleResult())[1])
    loop = M.ApiMonitorLoop(sf, interval_s=10)
    loop._tick.interval = 0.05
    loop._tick._last = None
    monkeypatch.setattr(loop._tick, "_clock", lambda: datetime.now(timezone.utc))
    loop.start()
    loop._tick._last = datetime.now(timezone.utc) - timedelta(seconds=5)
    try:
        assert done.wait(20)
    finally:
        loop.stop()
