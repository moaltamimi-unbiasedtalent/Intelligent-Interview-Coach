"""P10B-W10.9: durable DB-backed jobs, separate worker, leases, retries, idempotency and Admin visibility.

Deterministic: an injectable clock (no real lease waits), temp file-backed SQLite (real cross-connection concurrency),
fake handlers/probes, and a network block. No provider is ever contacted."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src import integrations as I
from src.application import admin_audit as A
from src.jobs import registry as R
from src.jobs.registry import JobTypeDef, PermanentJobError, RetryableJobError
from src.jobs.service import JobService, JobStateConflict, JobValidationError, LeaseLost
from src.jobs.worker import Worker, poll_seconds_from_env
from src.persistence import Job, init_db, make_engine, make_session_factory
from tests.test_admin_foundation_w10_1 import Env

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "sk-or-v1-SENTINELSECRET1234567890"
T0 = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class P(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: str = "x"


DOMAIN: dict = {}


def _types(handler=None, max_attempts=3, **kw):
    h = handler or (lambda payload, ctx: None)
    defn = JobTypeDef(code="t", label="Test", payload_model=P, handler=h, summarize=lambda p: {"n": p.n},
                      idempotency="test", max_attempts=max_attempts, lease_seconds=30, backoff_base_seconds=10,
                      backoff_cap_seconds=40, admin_enqueue=True, **kw)
    return {"t": defn}


@pytest.fixture()
def sf(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine, force=True)
    yield make_session_factory(engine)
    engine.dispose()


def svc(sf, clock, registry=None):
    return JobService(sf, registry or _types(), clock=clock)


def row(sf, public_id):
    with sf() as s:
        j = s.scalar(select(Job).where(Job.public_id == public_id))
        s.expunge(j)
        return j


# ---------------------------------------------------------------- enqueue / payload safety
def test_enqueue_validates_type_payload_priority_and_never_echoes(sf):
    c = Clock(); s = svc(sf, c)
    with pytest.raises(JobValidationError):
        s.enqueue("shell", {"cmd": "rm -rf /"})                      # arbitrary job names do not exist
    for bad in ({"n": "x", "extra": 1}, {"api_key": SENTINEL}, {"n": {"password": SENTINEL}}, ["x"]):
        with pytest.raises(JobValidationError) as e:
            s.enqueue("t", bad)
        assert SENTINEL not in str(e.value)
    with pytest.raises(JobValidationError):
        s.enqueue("t", {"n": "x"}, priority="urgent")
    view, created = s.enqueue("t", {"n": "ok"})
    assert created and view["state"] == "queued" and view["attempts"] == 0 and view["payload_summary"] == {"n": "ok"}
    assert "payload" not in view and "payload_json" not in view


def test_enqueue_idempotency_active_key_only(sf):
    c = Clock(); s = svc(sf, c)
    a, ca = s.enqueue("t", {}, idempotency_key="k1")
    b, cb = s.enqueue("t", {}, idempotency_key="k1")
    assert ca and not cb and a["public_id"] == b["public_id"]
    other, co = s.enqueue("t", {}, idempotency_key="k2")
    assert co and other["public_id"] != a["public_id"]
    claim = s.claim("w1"); s.complete(claim)                           # finished: the key no longer blocks
    again, cc = s.enqueue("t", {}, idempotency_key="k1")
    assert cc and again["public_id"] != a["public_id"]
    with sf() as s2, pytest.raises(IntegrityError):                    # the DB itself enforces it
        for pid in ("a" * 32, "b" * 32):
            s2.add(Job(public_id=pid, job_type="t", payload_json={}, idempotency_key="k1", available_at=T0))
        s2.commit()


def test_enqueue_race_same_key_creates_one_active_job(sf):
    c = Clock(); s = svc(sf, c); results = []
    barrier = threading.Barrier(8)

    def go():
        barrier.wait()
        results.append(s.enqueue("t", {}, idempotency_key="race"))

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(1 for _, created in results if created) == 1 and len({v["public_id"] for v, _ in results}) == 1


# ---------------------------------------------------------------- claiming
def test_concurrent_workers_claim_each_job_exactly_once(sf):
    c = Clock(); s = svc(sf, c)
    ids = [s.enqueue("t", {"n": str(i)})[0]["public_id"] for i in range(12)]
    claimed, barrier = [], threading.Barrier(8)

    def worker(k):
        barrier.wait()
        while True:
            claim = s.claim(f"w{k}")
            if claim is None:
                return
            claimed.append((claim.public_id, claim.attempts, k))

    ts = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(p for p, _, _ in claimed) == sorted(ids)             # every job once, none twice
    assert all(a == 1 for _, a, _ in claimed)                          # losers consumed no attempt
    assert all(row(sf, i).attempts == 1 and row(sf, i).state == "running" for i in ids)


def test_single_job_many_competing_claimers_one_winner(sf):
    c = Clock(); s = svc(sf, c)
    pid = s.enqueue("t", {})[0]["public_id"]
    wins, barrier = [], threading.Barrier(10)

    def go(k):
        barrier.wait()
        if s.claim(f"w{k}"):
            wins.append(k)

    ts = [threading.Thread(target=go, args=(k,)) for k in range(10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(wins) == 1 and row(sf, pid).attempts == 1


def test_claim_order_priority_then_age_and_respects_available_at(sf):
    c = Clock(); s = svc(sf, c)
    low = s.enqueue("t", {}, priority="low")[0]["public_id"]
    c.advance(1)
    normal = s.enqueue("t", {})[0]["public_id"]
    high = s.enqueue("t", {}, priority="high")[0]["public_id"]
    later = s.enqueue("t", {}, priority="high", available_at=c.now + timedelta(seconds=100))[0]["public_id"]
    assert [s.claim("w").public_id for _ in range(3)] == [high, normal, low]
    assert s.claim("w") is None                                        # `later` is not eligible yet
    c.advance(100)
    assert s.claim("w").public_id == later


def test_postgres_claim_uses_for_update_skip_locked():
    from sqlalchemy.dialects import postgresql

    stmt = select(Job).where(Job.state == "queued").limit(1).with_for_update(skip_locked=True)
    assert "FOR UPDATE SKIP LOCKED" in str(stmt.compile(dialect=postgresql.dialect()))
    src = (ROOT / "src/jobs/service.py").read_text()
    assert "with_for_update(skip_locked=True)" in src and 'dialect.name == "postgresql"' in src


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"),
                    reason="needs TEST_POSTGRES_URL pointing at a disposable PostgreSQL database with the migrated schema")
def test_postgres_two_workers_one_claim():   # pragma: no cover - requires a real PostgreSQL
    engine = make_engine(os.environ["TEST_POSTGRES_URL"])
    sfp = make_session_factory(engine)
    s = JobService(sfp, _types())
    pid = s.enqueue("t", {})[0]["public_id"]
    wins, barrier = [], threading.Barrier(6)

    def go(k):
        barrier.wait()
        if s.claim(f"pg{k}"):
            wins.append(k)

    ts = [threading.Thread(target=go, args=(k,)) for k in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(wins) == 1 and row(sfp, pid).attempts == 1


# ---------------------------------------------------------------- leases, heartbeat, crash recovery
def test_crash_recovery_reclaims_after_lease_expiry_and_completes(sf):
    c = Clock(); s = svc(sf, c)
    pid = s.enqueue("t", {})[0]["public_id"]
    a = s.claim("workerA")                                             # worker A claims then "crashes"
    assert a.attempts == 1 and s.claim("workerB") is None              # leased: B cannot take it
    c.advance(29); assert s.reap_expired() == 0
    c.advance(2); assert s.reap_expired() == 1                          # lease expired: reclaimable, not succeeded
    r = row(sf, pid)
    assert r.state == "queued" and r.last_error_category == "lease_expired" and r.lease_owner is None
    b = s.claim("workerB")
    assert b.attempts == 2
    s.complete(b)
    assert row(sf, pid).state == "succeeded"
    with pytest.raises(LeaseLost):                                     # the old owner can no longer finish it
        s.complete(a)


def test_expired_lease_with_attempts_exhausted_becomes_terminal_failed(sf):
    c = Clock(); s = svc(sf, c, _types(max_attempts=1))
    pid = s.enqueue("t", {})[0]["public_id"]
    s.claim("w"); c.advance(31)
    assert s.reap_expired() == 1
    r = row(sf, pid)
    assert r.state == "failed" and r.last_error_category == "lease_expired" and r.finished_at is not None


def test_heartbeat_rules(sf):
    c = Clock(); s = svc(sf, c)
    pid = s.enqueue("t", {})[0]["public_id"]
    a = s.claim("A")
    c.advance(20); s.heartbeat(a)
    assert row(sf, pid).lease_expires_at.replace(tzinfo=timezone.utc) == c.now + timedelta(seconds=30)
    from dataclasses import replace
    with pytest.raises(LeaseLost):
        s.heartbeat(replace(a, worker_id="B"))                         # wrong worker
    c.advance(31)
    with pytest.raises(LeaseLost):
        s.heartbeat(a)                                                 # expired lease is not casually renewable
    s.reap_expired(); b = s.claim("B")
    with pytest.raises(LeaseLost):
        s.heartbeat(a)                                                 # another worker owns it now
    s.complete(b)
    with pytest.raises(LeaseLost):
        s.heartbeat(b)                                                 # terminal job cannot heartbeat


# ---------------------------------------------------------------- retry, backoff, attempts
def test_retry_backoff_max_attempts_and_terminal_failure(sf):
    c = Clock(); s = svc(sf, c)
    pid = s.enqueue("t", {})[0]["public_id"]
    seen = []
    for attempt in (1, 2):
        claim = s.claim("w"); assert claim.attempts == attempt
        assert s.fail(claim, "transient", retryable=True) == "retry_scheduled"
        r = row(sf, pid)
        delay = (r.available_at.replace(tzinfo=timezone.utc) - c.now).total_seconds()
        seen.append(delay)
        assert s.claim("w") is None                                    # not before available_at
        c.advance(delay)
    assert seen == [10, 20]                                            # base x 2^(n-1)
    last = s.claim("w"); assert last.attempts == 3
    assert s.fail(last, "transient", retryable=True) == "failed"        # max attempts reached: terminal
    r = row(sf, pid)
    assert r.state == "failed" and r.attempts == 3 and s.claim("w") is None
    assert R.backoff_seconds(_types()["t"], 10) == 40                  # capped


def test_non_retryable_failure_is_terminal_and_message_is_fixed(sf):
    c = Clock(); s = svc(sf, c)
    pid = s.enqueue("t", {})[0]["public_id"]
    assert s.fail(s.claim("w"), "invalid_payload", retryable=False) == "failed"
    r = row(sf, pid)
    assert r.last_error_message_safe == R.SAFE_MESSAGES["invalid_payload"]


def test_manual_retry_and_cancel_state_rules(sf):
    c = Clock(); s = svc(sf, c)
    pid = s.enqueue("t", {})[0]["public_id"]
    with pytest.raises(JobStateConflict):
        s.retry(pid)                                                   # queued is not retryable
    claim = s.claim("w")
    with pytest.raises(JobStateConflict):
        s.cancel(pid)                                                  # running is NOT cancellable
    s.fail(claim, "configuration_error", retryable=False)
    with pytest.raises(JobStateConflict):
        s.cancel(pid)
    v = s.retry(pid)
    assert v["state"] == "queued" and v["attempts"] == 0 and v["manual_retries"] == 1 and v["error_category"] is None
    assert s.cancel(pid)["state"] == "cancelled"
    with pytest.raises(JobStateConflict):
        s.retry(pid)                                                   # cancelled is final
    nr = {"t": _types(manual_retry=False)["t"]}
    s2 = svc(sf, c, nr)
    p2 = s2.enqueue("t", {})[0]["public_id"]; s2.fail(s2.claim("w"), "unsupported", retryable=False)
    with pytest.raises(JobStateConflict):
        s2.retry(p2)


def test_db_constraints_reject_malformed_rows(sf):
    def bad(**kw):
        base = dict(public_id=os.urandom(8).hex(), job_type="t", payload_json={}, available_at=T0)
        with sf() as s2:
            s2.add(Job(**{**base, **kw}))
            with pytest.raises(IntegrityError):
                s2.commit()
    bad(state="exploded"); bad(priority="urgent"); bad(attempts=-1); bad(max_attempts=0); bad(attempts=5, max_attempts=3)
    bad(state="running")                                               # running without owner/lease
    bad(state="queued", lease_owner="w", lease_expires_at=T0)          # lease on a non-running job
    bad(last_error_category="boom")
    with sf() as s2:
        s2.add(Job(public_id="d" * 32, job_type="t", payload_json={}, available_at=T0)); s2.commit()
        s2.add(Job(public_id="d" * 32, job_type="t", payload_json={}, available_at=T0))
        with pytest.raises(IntegrityError):
            s2.commit()                                                # duplicate public id


# ---------------------------------------------------------------- worker
def test_worker_success_idle_and_presence(sf):
    c = Clock(); done = []
    s = svc(sf, c, _types(handler=lambda p, ctx: done.append(ctx.job_public_id)))
    w = Worker(s, s._registry, worker_id="w1", clock=c)
    assert w.run_once() == "idle"
    pid = s.enqueue("t", {})[0]["public_id"]
    assert w.run_once() == "succeeded" and done == [pid] and row(sf, pid).state == "succeeded"
    stats = s.stats()
    assert stats["queue"]["succeeded"] == 1 and stats["workers"]["seen_recently"] == 1
    assert stats["workers"]["items"][0]["jobs_succeeded"] == 1
    c.advance(120)
    assert s.stats()["workers"]["seen_recently"] == 0                  # presence comes from worker heartbeats only


def test_worker_retry_then_success_and_terminal(sf):
    c = Clock(); calls = {"n": 0}

    def flaky(p, ctx):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableJobError("unavailable")

    s = svc(sf, c, _types(handler=flaky)); w = Worker(s, s._registry, clock=c)
    pid = s.enqueue("t", {})[0]["public_id"]
    assert w.run_once() == "retry_scheduled" and w.run_once() == "idle"   # not retried before available_at
    c.advance(10); assert w.run_once() == "retry_scheduled"
    c.advance(20); assert w.run_once() == "succeeded" and row(sf, pid).attempts == 3

    def hard(p, ctx):
        raise PermanentJobError("configuration_error")
    s2 = svc(sf, c, _types(handler=hard)); w2 = Worker(s2, s2._registry, clock=c)
    p2 = s2.enqueue("t", {})[0]["public_id"]
    assert w2.run_once() == "failed" and row(sf, p2).last_error_category == "configuration_error"


def test_worker_unknown_type_invalid_payload_and_unexpected_error_are_safe(sf):
    c = Clock(); s = svc(sf, c)
    with sf() as s2:                                                   # a row for a type this worker does not know
        s2.add(Job(public_id="e" * 32, job_type="ghost", payload_json={"x": 1}, available_at=T0, created_at=T0, updated_at=T0))
        s2.add(Job(public_id="f" * 32, job_type="t", payload_json={"nope": 1}, available_at=T0, created_at=T0, updated_at=T0))
        s2.commit()
    w = Worker(s, s._registry, clock=c)
    assert w.run_once() == "failed" and w.run_once() == "failed"
    assert row(sf, "e" * 32).last_error_category == "unknown_job_type"
    assert row(sf, "f" * 32).last_error_category == "invalid_payload"

    def boom(p, ctx):
        raise RuntimeError(f"upstream said {SENTINEL} Authorization: Bearer {SENTINEL}")
    s3 = svc(sf, c, _types(handler=boom)); w3 = Worker(s3, s3._registry, clock=c)
    pid = s3.enqueue("t", {})[0]["public_id"]
    assert w3.run_once() == "failed"
    r = row(sf, pid)
    assert r.last_error_category == "internal_error" and SENTINEL not in (r.last_error_message_safe or "")
    assert SENTINEL not in str(s3.get(pid))


def test_worker_lease_lost_discards_result_and_does_not_overwrite(sf):
    c = Clock(); other = {}

    def slow(p, ctx):
        c.advance(31)                                                  # this worker stalls past its lease...
        s.reap_expired()
        other["claim"] = s.claim("rescuer")                            # ...and another worker takes the job

    s = svc(sf, c, _types(handler=slow)); w = Worker(s, s._registry, worker_id="slowpoke", clock=c)
    pid = s.enqueue("t", {})[0]["public_id"]
    assert w.run_once() == "lease_lost"
    r = row(sf, pid)
    assert r.state == "running" and r.lease_owner == "rescuer" and r.attempts == 2
    s.complete(other["claim"])
    assert row(sf, pid).state == "succeeded"


def test_handler_replay_after_crash_window_has_one_domain_effect(sf):
    """Domain effect committed, worker dies before completing: the replay must not duplicate it."""
    DOMAIN.clear(); c = Clock()

    def idempotent(p, ctx):
        DOMAIN.setdefault(ctx.job_public_id, 0)
        if DOMAIN[ctx.job_public_id] == 0:                             # the handler's own replay guard
            DOMAIN[ctx.job_public_id] += 1

    s = svc(sf, c, _types(handler=idempotent))
    pid = s.enqueue("t", {})[0]["public_id"]
    a = s.claim("A")
    idempotent(P(), R.JobContext(job_public_id=a.public_id, attempt=1, created_by_user_id=None, session_factory=sf))
    c.advance(31)                                                      # A crashed after the effect, before complete()
    Worker(s, s._registry, clock=c, worker_id="B").run_once()
    assert row(sf, pid).state == "succeeded" and row(sf, pid).attempts == 2 and DOMAIN[pid] == 1


def test_run_forever_stops_gracefully_and_marks_worker_stopped(sf):
    c = Clock(); s = svc(sf, c); w = Worker(s, s._registry, worker_id="g1", clock=c)
    stop = threading.Event(); waits = []

    def wait(seconds):
        waits.append(seconds); stop.set()

    w.run_forever(stop, wait=wait)
    assert waits == [w.poll_seconds]
    assert s.stats()["workers"]["items"][0]["status"] == "stopped"
    assert poll_seconds_from_env({"JOB_WORKER_POLL_SECONDS": "9999"}) == 60.0
    assert poll_seconds_from_env({"JOB_WORKER_POLL_SECONDS": "nope"}) == 2.0


# ---------------------------------------------------------------- built-in job types
def test_integration_test_job_uses_fake_probes_and_maps_categories(sf, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    c = Clock(); results = {"r": I.ProbeResult("success", "ok", 3)}
    probes = {"openrouter": lambda store: results["r"]}
    s = JobService(sf, clock=c); w = Worker(s, clock=c, probes=probes, secret_store=I.get_secret_store())
    s.enqueue("integration_connection_test", {"integration_code": "openrouter"}, actor_user_id=None)
    assert w.run_once() == "succeeded"
    results["r"] = I.ProbeResult("failure", "timeout", 5000)
    p2 = s.enqueue("integration_connection_test", {"integration_code": "openrouter"})[0]["public_id"]
    assert w.run_once() == "retry_scheduled"                           # timeout is retryable
    results["r"] = I.ProbeResult("failure", "unauthorized", 5)
    c.advance(3600); assert w.run_once() == "failed"
    assert row(sf, p2).last_error_category == "configuration_error"
    with pytest.raises(JobValidationError):
        s.enqueue("integration_connection_test", {"integration_code": "http://169.254.169.254"})
    with pytest.raises(JobValidationError):
        s.enqueue("integration_connection_test", {"integration_code": "redis_rate_limit"})   # no probe exists


def test_registry_is_code_defined_with_no_shell_or_arbitrary_handler():
    assert set(R.REGISTRY) == {"diagnostic_noop", "integration_connection_test"}
    for d in R.REGISTRY.values():
        assert callable(d.handler) and d.max_attempts >= 1 and d.lease_seconds > 0 and d.idempotency
    src = " ".join((ROOT / "src/jobs" / f).read_text() for f in ("registry.py", "service.py", "worker.py"))
    for banned in ("subprocess", "os.system", "eval(", "exec(", "importlib", "celery", "kombu", "apscheduler", "pika", "kafka"):
        assert banned not in src, banned


# ---------------------------------------------------------------- Admin API
@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def jobsvc(env, clock=None):
    return JobService(env.accounts.session_factory, clock=clock or Clock())


def test_admin_permission_matrix_and_default_deny(env):
    _, op = env.user("operations_admin"); _, ro = env.user("knowledge_admin")
    _, cand = env.user("user"); _, sup = env.user("support_operator")
    assert env.c.get(f"{API}/admin/jobs").status_code in (401, 403)
    for ck in (cand, sup):
        assert env.c.get(f"{API}/admin/jobs", cookies=ck).status_code == 403
        assert env.c.get(f"{API}/admin/jobs/diagnostics", cookies=ck).status_code == 403
        assert env.c.post(f"{API}/admin/jobs", json={"job_type": "diagnostic_noop", "payload": {"label": "x"}}, cookies=ck).status_code == 403
    assert env.c.get(f"{API}/admin/jobs", cookies=ro).status_code == 200      # jobs.read only
    assert env.c.post(f"{API}/admin/jobs", json={"job_type": "diagnostic_noop", "payload": {"label": "x"}}, cookies=ro).status_code == 403
    assert env.c.post(f"{API}/admin/jobs", json={"job_type": "diagnostic_noop", "payload": {"label": "x"}}, cookies=op).status_code == 201


def test_admin_enqueue_list_filter_detail_retry_cancel_and_audit(env):
    _, op = env.user("operations_admin")
    r = env.c.post(f"{API}/admin/jobs", json={"job_type": "diagnostic_noop", "payload": {"label": "Check 1"}, "dedupe_id": "k"}, cookies=op)
    assert r.status_code == 201 and r.json()["created"] is True
    pid = r.json()["job"]["public_id"]
    again = env.c.post(f"{API}/admin/jobs", json={"job_type": "diagnostic_noop", "payload": {"label": "Check 1"}, "dedupe_id": "k"}, cookies=op)
    assert again.status_code == 201 and again.json()["created"] is False and again.json()["job"]["public_id"] == pid
    # the API process never executes jobs: it stays queued until a worker runs
    assert env.c.get(f"{API}/admin/jobs/{pid}", cookies=op).json()["state"] == "queued"
    for bad in ({"job_type": "shell", "payload": {}}, {"job_type": "diagnostic_noop", "payload": {"label": SENTINEL, "api_key": SENTINEL}},
                {"job_type": "diagnostic_noop", "payload": {"label": "!!"}}):
        rr = env.c.post(f"{API}/admin/jobs", json=bad, cookies=op)
        assert rr.status_code == 422 and SENTINEL not in rr.text
    # worker runs one failed job fixture
    svc_ = jobsvc(env)
    fid = svc_.enqueue("diagnostic_noop", {"label": "will fail"}, priority="high")[0]["public_id"]
    svc_.fail(svc_.claim("w"), "configuration_error", retryable=False)
    lst = env.c.get(f"{API}/admin/jobs?state=failed", cookies=op).json()
    assert [i["public_id"] for i in lst["items"]] == [fid] and lst["total"] == 1
    assert env.c.get(f"{API}/admin/jobs?q={pid}", cookies=op).json()["total"] == 1
    assert env.c.get(f"{API}/admin/jobs?q=will", cookies=op).json()["total"] == 0        # payloads are not searchable
    assert env.c.get(f"{API}/admin/jobs?state=bogus", cookies=op).status_code == 422
    assert env.c.get(f"{API}/admin/jobs?page_size=1&page=2", cookies=op).json()["items"].__len__() == 1
    d = env.c.get(f"{API}/admin/jobs/{fid}", cookies=op).json()
    assert d["can_retry"] and not d["can_cancel"] and d["error_message"] == R.SAFE_MESSAGES["configuration_error"]
    assert "payload" not in d and "payload_json" not in d and d["payload_summary"] == {"label": "will fail"}
    assert env.c.post(f"{API}/admin/jobs/{fid}/cancel", cookies=op).status_code == 409
    rt = env.c.post(f"{API}/admin/jobs/{fid}/retry", cookies=op)
    assert rt.status_code == 200 and rt.json()["state"] == "queued" and rt.json()["manual_retries"] == 1
    assert env.c.post(f"{API}/admin/jobs/{fid}/retry", cookies=op).status_code == 409
    cn = env.c.post(f"{API}/admin/jobs/{fid}/cancel", cookies=op)
    assert cn.status_code == 200 and cn.json()["state"] == "cancelled"
    assert env.c.post(f"{API}/admin/jobs/{'0' * 32}/cancel", cookies=op).status_code == 404
    for path in ("retry", "cancel"):
        assert env.c.post(f"{API}/admin/jobs/{pid}/{path}", cookies=env.user("knowledge_admin")[1]).status_code == 403
    names = {e["event_type"] for e in env.events()}
    assert {A.ADMIN_JOB_ENQUEUED, A.ADMIN_JOB_RETRY_REQUESTED, A.ADMIN_JOB_CANCELLED} <= names
    for e in env.events():
        if e["event_type"].startswith("admin.job_"):
            blob = str(e)
            assert "will fail" not in blob and "Check 1" not in blob and SENTINEL not in blob       # ids and states only
    assert [e for e in env.events(A.ADMIN_JOB_ENQUEUED) if e["target_id"] == pid]


def test_admin_integration_job_needs_integrations_manage_and_validates_code(env):
    _, op = env.user("operations_admin")
    ok = env.c.post(f"{API}/admin/jobs", json={"job_type": "integration_connection_test", "payload": {"integration_code": "openrouter"}}, cookies=op)
    assert ok.status_code == 201 and ok.json()["job"]["payload_summary"] == {"integration": "openrouter"}
    bad = env.c.post(f"{API}/admin/jobs", json={"job_type": "integration_connection_test", "payload": {"integration_code": "http://localhost"}}, cookies=op)
    assert bad.status_code == 422
    assert env.c.get(f"{API}/admin/jobs/types", cookies=op).status_code == 200


def test_diagnostics_and_command_center(env):
    _, op = env.user("operations_admin"); _, sup = env.user("support_operator")
    c = Clock(); c.now = datetime.now(timezone.utc) - timedelta(hours=1); s = jobsvc(env, c)
    s.enqueue("diagnostic_noop", {"label": "a"}); s.enqueue("diagnostic_noop", {"label": "b"})
    s.claim("w")                                                       # leased an hour ago (30 s lease): now stale
    d = env.c.get(f"{API}/admin/jobs/diagnostics", cookies=op).json()
    assert d["queue"]["queued"] == 1 and d["queue"]["running"] == 1 and d["queue"]["stale_leases"] == 1
    assert d["queue"]["oldest_ready_age_seconds"] is not None and d["workers"]["seen_recently"] == 0
    home = env.c.get(f"{API}/admin/home", cookies=op).json()
    assert home["jobs"]["queue"]["queued"] == 1
    assert "jobs" not in env.c.get(f"{API}/admin/home", cookies=sup).json()


def test_no_job_routes_for_arbitrary_state_editing_or_raw_payload():
    from src.api.admin_route_invariant import admin_routes
    found = {(m, r.path) for r in admin_routes() if r.path.startswith("/admin/jobs") for m in r.methods}
    assert found == {("GET", "/admin/jobs"), ("POST", "/admin/jobs"), ("GET", "/admin/jobs/diagnostics"),
                     ("GET", "/admin/jobs/types"), ("GET", "/admin/jobs/{public_id}"),
                     ("POST", "/admin/jobs/{public_id}/retry"), ("POST", "/admin/jobs/{public_id}/cancel")}
    assert all(r.permissions for r in admin_routes() if r.path.startswith("/admin/jobs"))
    schema = (ROOT / "src/api/schemas/admin.py").read_text()
    block = schema[schema.index("class JobLease"):]
    assert "payload_json" not in block and "lease_owner_secret" not in block


def test_migration_0018_fresh_from_0017_constraints_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    def cfg(url):
        c = Config("alembic.ini"); c.set_main_option("script_location", "migrations"); c.set_main_option("sqlalchemy.url", url)
        return c

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(cfg(url), "0017_integrations")
    assert "jobs" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    eng = create_engine(url); insp = inspect(eng)
    assert {"jobs", "job_workers"} <= set(insp.get_table_names())
    idx = {i["name"] for i in insp.get_indexes("jobs")}
    assert {"uq_jobs_active_idempotency", "ix_jobs_claim", "ix_jobs_lease_expiry", "ix_jobs_type_state", "ix_jobs_public_id"} <= idx
    ins = ("INSERT INTO jobs(public_id,job_type,state,priority,payload_json,attempts,max_attempts,available_at,created_at,updated_at,"
           "idempotency_key) VALUES (:p,'t',:s,'normal','{}',:a,3,'2026-01-01','2026-01-01','2026-01-01',:k)")
    with eng.begin() as c:
        c.execute(text(ins), {"p": "p1", "s": "queued", "a": 0, "k": "key"})
    for params in ({"p": "p2", "s": "exploded", "a": 0, "k": None}, {"p": "p3", "s": "queued", "a": 9, "k": None},
                   {"p": "p1", "s": "queued", "a": 0, "k": None}, {"p": "p4", "s": "queued", "a": 0, "k": "key"},
                   {"p": "p5", "s": "running", "a": 1, "k": None}):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(ins), params)
    with eng.begin() as c:                                             # a finished job does not block the same key
        c.execute(text(ins), {"p": "p6", "s": "succeeded", "a": 1, "k": "key"})
    command.downgrade(cfg(url), "0017_integrations")
    assert "jobs" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    assert "jobs" in inspect(create_engine(url)).get_table_names()
