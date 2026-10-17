"""W12.4D-P4-A: gated Basic/Premium usage-quota foundation. FULLY OFFLINE: isolated SQLite databases, synthetic entitlement state and synthetic allowances
(NO owner-approved number exists), every non-loopback socket fails the test. ``USAGE_QUOTAS_ENFORCED`` is a code constant that is OFF; tests flip it on an isolated
module attribute only. Nothing here is Stripe evidence, a price, or a real allowance."""

from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src import ai_protection as AP
from src.api import rate_limit as rl
from src.api.dependencies import get_current_user_id, get_pause_service, get_repository
from src.api.exception_handlers import register_exception_handlers
from src.application import usage_quota as UQ
from src.application.pause import PauseService
from src.persistence import AIOperationEvent, UsageQuotaCounter, UsageQuotaReservation, User, init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 17, 10, 30, tzinfo=timezone.utc)
SYNTH = UQ.QuotaPolicy("synthetic-test", {("basic", "practice_session"): UQ.Allowance(2, "day"), ("premium", "practice_session"): UQ.Allowance(5, "day"),
                                           ("basic", "career_ai"): UQ.Allowance(1, "hour"), ("premium", "career_ai"): UQ.Allowance(3, "hour")})


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    real = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost", "testserver") and not str(host).startswith("/"):
            raise AssertionError(f"network access attempted: {address}")
        return real(self, address, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture(autouse=True)
def _fresh_limiter():
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    yield
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())


class Plans:
    def __init__(self, table=None, boom=()):
        self.table, self.boom = table or {}, set(boom)

    def plan_summary(self, user_id, **k):
        if user_id in self.boom:
            raise RuntimeError("unreadable")
        return self.table.get(user_id, {"plan_code": "basic", "source": "fallback_default"})


PREMIUM = {"plan_code": "premium", "source": "subscription", "entitlements": {"premium_preview": {"enabled": True}}}
FORGED = {"plan_code": "premium", "source": "fallback_default"}
PREVIEW_ONLY = {"plan_code": "basic", "source": "subscription", "entitlements": {"premium_preview": {"enabled": True}}}


class W:
    pass


@pytest.fixture()
def world(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'q.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    w = W()
    w.sf, w.url = sf, f"sqlite:///{tmp_path / 'q.db'}"
    with sf() as s:
        us = [User(subject=f"u{i}", provider="local", email=f"u{i}@x.test") for i in range(4)]
        s.add_all(us)
        s.commit()
        w.users = [u.id for u in us]
    w.now = [T0]
    w.plans = Plans()

    def svc(plans=None, policy=SYNTH):
        return UQ.UsageQuotaService(sf, plans or w.plans, policy=policy, now=lambda: w.now[0])
    w.svc = svc
    return w


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(UQ, "USAGE_QUOTAS_ENFORCED", True)


def used(w, user, feature="practice_session"):
    with w.sf() as s:
        return s.scalar(select(func.coalesce(func.sum(UsageQuotaCounter.used), 0)).where(UsageQuotaCounter.user_id == user, UsageQuotaCounter.feature == feature))


# ============================================================ gate, defaults, no invented numbers ============================================================
def test_enforcement_is_a_disabled_code_constant_with_no_approved_allowance():
    assert UQ.USAGE_QUOTAS_ENFORCED is False
    assert UQ.DEFAULT_POLICY.allowances == {} and UQ.DEFAULT_POLICY.version == "p4a-unconfigured" and not UQ.DEFAULT_POLICY.complete()


def test_disabled_gate_reserves_nothing_touches_no_table_and_reads_no_entitlement(world):
    boom = Plans(boom=world.users)
    s = world.svc(boom)
    assert s.reserve(world.users[0], "practice_session", "k1") is False
    assert s.commit("k1") is False and s.release("k1") is False
    assert s.snapshot(world.users[0]) == {"enforcement_active": False, "policy_version": None, "features": []}
    with world.sf() as db:
        assert db.scalar(select(func.count()).select_from(UsageQuotaReservation)) == 0 and db.scalar(select(func.count()).select_from(UsageQuotaCounter)) == 0


# ============================================================ Basic / Premium policy ============================================================
def test_basic_allowance_is_enforced_and_premium_has_its_own(world, on):
    b, p = world.users[0], world.users[1]
    world.plans.table[p] = PREMIUM
    s = world.svc()
    assert [s.reserve(b, "practice_session", f"b{i}") for i in range(2)] == [True, True]
    with pytest.raises(UQ.QuotaExhausted) as e:
        s.reserve(b, "practice_session", "b3")
    assert e.value.period == "day" and e.value.reset_at == datetime(2026, 10, 18, tzinfo=timezone.utc) and e.value.retry_after > 0
    assert all(s.reserve(p, "practice_session", f"p{i}") for i in range(5))
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(p, "practice_session", "p6")


@pytest.mark.parametrize("entitlement", [FORGED, PREVIEW_ONLY, {"plan_code": "weird", "source": "subscription"}, {}])
def test_forged_preview_expired_or_unknown_state_is_never_premium(world, on, entitlement):
    u = world.users[0]
    world.plans.table[u] = entitlement
    assert world.svc().plan_for(u) == "basic"


def test_an_unreadable_entitlement_is_basic_never_premium_or_unlimited(world, on):
    u = world.users[0]
    s = world.svc(Plans(boom=[u]))
    assert s.plan_for(u) == "basic"
    assert [s.reserve(u, "practice_session", f"x{i}") for i in range(2)] == [True, True]
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(u, "practice_session", "x3")


def test_the_plan_never_comes_from_the_client(world, on):
    """A request header or body can say anything; the service signature accepts only the authenticated user id."""
    import inspect
    assert list(inspect.signature(UQ.UsageQuotaService.reserve).parameters) == ["self", "user_id", "feature", "op_key"]


def test_a_synthetic_plan_override_is_refused_outside_test(world, monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ValueError):
        UQ.UsageQuotaService(world.sf, world.plans, override=lambda u: "premium")


def test_missing_configuration_fails_closed_never_unlimited(world, on):
    with pytest.raises(UQ.QuotaNotConfigured):
        world.svc(policy=UQ.DEFAULT_POLICY).reserve(world.users[0], "practice_session", "k")
    with pytest.raises(UQ.QuotaNotConfigured):
        world.svc().reserve(world.users[0], "not_a_feature", "k")
    with world.sf() as db:
        assert db.scalar(select(func.count()).select_from(UsageQuotaReservation)) == 0


def test_the_allowance_rejects_invalid_values():
    for bad in ((-1, "day"), (3, "billing_period"), (3, "week")):
        with pytest.raises(ValueError):
            UQ.Allowance(*bad)


# ============================================================ atomicity, idempotency, isolation ============================================================
def test_a_duplicate_or_retried_operation_consumes_one_unit(world, on):
    u, s = world.users[0], world.svc()
    assert s.reserve(u, "practice_session", "same") and s.reserve(u, "practice_session", "same") and s.reserve(u, "practice_session", "same")
    assert used(world, u) == 1
    s.commit("same")
    assert s.reserve(u, "practice_session", "same") and used(world, u) == 1          # a replay after success is still one unit


def test_concurrent_requests_cannot_exceed_the_allowance(world, on):
    u, results = world.users[0], []
    gate = threading.Barrier(12)

    def go(i):
        gate.wait()
        try:
            results.append(world.svc().reserve(u, "practice_session", f"c{i}"))
        except UQ.QuotaExhausted:
            results.append("denied")
        except UQ.QuotaUnavailable:
            results.append("unavailable")
    ts = [threading.Thread(target=go, args=(i,)) for i in range(12)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results.count(True) <= 2 and used(world, u) == results.count(True)
    assert results.count(True) + results.count("denied") + results.count("unavailable") == 12
    assert results.count(True) == 2 or "unavailable" in results                       # a lock timeout may fail closed, but never over-grants


def test_concurrent_duplicates_of_one_operation_take_exactly_one_unit(world, on):
    u, gate = world.users[0], threading.Barrier(8)

    def go():
        gate.wait()
        try:
            world.svc().reserve(u, "practice_session", "dup")
        except UQ.QuotaUnavailable:
            pass
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert used(world, u) <= 1
    with world.sf() as db:
        assert db.scalar(select(func.count()).select_from(UsageQuotaReservation).where(UsageQuotaReservation.op_key == "dup")) <= 1


def test_a_real_multi_process_run_never_exceeds_the_allowance(world, on, tmp_path):
    """Four OS processes share the database (the shared durable store), each making attempts with distinct keys."""
    script = textwrap.dedent(f'''
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from datetime import datetime, timezone
        from src.application import usage_quota as UQ
        from src.persistence import make_engine, make_session_factory
        UQ.USAGE_QUOTAS_ENFORCED = True
        sf = make_session_factory(make_engine({world.url!r}))
        pol = UQ.QuotaPolicy("synthetic-test", {{("basic", "practice_session"): UQ.Allowance(5, "month")}})
        class P:
            def plan_summary(self, uid, **k): return {{"plan_code": "basic", "source": "fallback_default"}}
        svc = UQ.UsageQuotaService(sf, P(), policy=pol)
        pid = sys.argv[1]; granted = 0
        for i in range(8):
            try:
                granted += 1 if svc.reserve({world.users[2]}, "practice_session", f"mp-{{pid}}-{{i}}") else 0
            except (UQ.QuotaExhausted, UQ.QuotaUnavailable):
                pass
        print(granted)
    ''')
    procs = [subprocess.Popen([sys.executable, "-c", script, str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(4)]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1][-400:] for o in outs]
    total = sum(int(o[0].strip().splitlines()[-1]) for o in outs)
    assert total <= 5 and used(world, world.users[2]) == total


def test_users_are_isolated(world, on):
    a, b, s = world.users[0], world.users[1], world.svc()
    s.reserve(a, "practice_session", "a1"); s.reserve(a, "practice_session", "a2")
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(a, "practice_session", "a3")
    assert s.reserve(b, "practice_session", "b1") and used(world, b) == 1
    assert [f["status"] for f in s.snapshot(b)["features"] if f["feature"] == "practice_session"] == ["available"]


def test_an_op_key_cannot_be_borrowed_by_another_user(world, on):
    s = world.svc()
    s.reserve(world.users[0], "practice_session", "shared-key")
    with pytest.raises(UQ.QuotaNotConfigured):
        s.reserve(world.users[1], "practice_session", "shared-key")
    assert used(world, world.users[1]) == 0


# ============================================================ lifecycle, retry, recovery ============================================================
def test_commit_keeps_the_unit_and_release_returns_it_idempotently(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "practice_session", "ok"); s.reserve(u, "practice_session", "bad")
    assert s.commit("ok") is True and s.commit("ok") is False and s.release("ok") is False      # single-use transitions
    assert s.release("bad") is True and s.release("bad") is False and s.commit("bad") is False
    assert used(world, u) == 1


def test_a_failed_operation_returns_its_unit_and_a_retry_with_the_same_key_reuses_it(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "practice_session", "r1"); s.reserve(u, "practice_session", "other")
    s.release("r1")
    assert used(world, u) == 1
    assert s.reserve(u, "practice_session", "r1") and used(world, u) == 2           # the retry takes ONE unit again, never two
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(u, "practice_session", "r-new")


def test_a_crashed_worker_reservation_is_recovered_after_expiry(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "practice_session", "crash")
    assert s.reap_expired() == 0 and used(world, u) == 1
    world.now[0] = T0 + UQ.RESERVATION_TTL + timedelta(seconds=1)
    assert s.reap_expired() == 1 and used(world, u) == 0
    assert s.reap_expired() == 0


def test_a_committed_operation_is_never_reaped(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "practice_session", "done"); s.commit("done")
    world.now[0] = T0 + timedelta(days=1, hours=1)
    assert s.reap_expired() == 0


def test_a_failed_finalization_after_denial_leaves_no_reservation(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "career_ai", "c1")
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(u, "career_ai", "c2")
    with world.sf() as db:
        assert db.scalar(select(UsageQuotaReservation.state).where(UsageQuotaReservation.op_key == "c2")) is None


# ============================================================ periods ============================================================
@pytest.mark.parametrize("period,start,reset", [("hour", datetime(2026, 10, 17, 10, tzinfo=timezone.utc), datetime(2026, 10, 17, 11, tzinfo=timezone.utc)),
                                                 ("day", datetime(2026, 10, 17, tzinfo=timezone.utc), datetime(2026, 10, 18, tzinfo=timezone.utc)),
                                                 ("month", datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc))])
def test_period_bounds_are_utc_calendar_boundaries(period, start, reset):
    assert UQ.period_bounds(period, T0) == (start, reset)
    assert UQ.period_bounds(period, T0.astimezone(timezone(timedelta(hours=-11)))) == (start, reset)   # a different local clock changes nothing


def test_december_rolls_into_the_next_year_and_naive_datetimes_are_treated_as_utc():
    assert UQ.period_bounds("month", datetime(2026, 12, 31, 23, 59))[1] == datetime(2027, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        UQ.period_bounds("billing_period", T0)


def test_the_allowance_resets_at_the_boundary_and_the_old_period_stays_recorded(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "career_ai", "h1")
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(u, "career_ai", "h2")
    world.now[0] = datetime(2026, 10, 17, 11, 0, 0, tzinfo=timezone.utc)
    assert s.reserve(u, "career_ai", "h3")
    assert used(world, u, "career_ai") == 2                                          # both periods remain auditable


def test_a_retry_straddling_a_boundary_does_not_consume_in_the_new_period(world, on):
    u, s = world.users[0], world.svc()
    s.reserve(u, "career_ai", "edge")
    world.now[0] = datetime(2026, 10, 17, 11, 0, 1, tzinfo=timezone.utc)
    assert s.reserve(u, "career_ai", "edge")                                         # the same logical operation, still one unit
    assert used(world, u, "career_ai") == 1


# ============================================================ subscription transitions ============================================================
def test_downgrade_applies_the_basic_allowance_to_what_is_already_consumed_and_re_upgrade_restores_headroom(world, on):
    u, s = world.users[0], world.svc()
    world.plans.table[u] = PREMIUM
    for i in range(3):
        s.reserve(u, "practice_session", f"t{i}")
    del world.plans.table[u]                                                         # subscription ended
    with pytest.raises(UQ.QuotaExhausted):
        s.reserve(u, "practice_session", "t-basic")
    assert used(world, u) == 3                                                       # nothing is deleted or rewritten
    world.plans.table[u] = PREMIUM
    assert s.reserve(u, "practice_session", "t-again")


def test_the_snapshot_reports_server_state_and_fabricates_nothing(world, on):
    u = world.users[0]
    s = world.svc()
    s.reserve(u, "practice_session", "s1")
    snap = {f["feature"]: f for f in s.snapshot(u)["features"]}
    assert snap["practice_session"]["used"] == 1 and snap["practice_session"]["remaining"] == 1 and snap["practice_session"]["allowance"] == 2
    assert snap["practice_session"]["reset_at"].startswith("2026-10-18")
    empty = {f["feature"]: f for f in world.svc(policy=UQ.DEFAULT_POLICY).snapshot(u)["features"]}
    assert all(f == {"feature": k, "unit": f["unit"], "status": "not_configured"} for k, f in empty.items())


def test_a_store_failure_fails_closed_for_the_gated_operation(world, on):
    s = UQ.UsageQuotaService(lambda: (_ for _ in ()).throw(RuntimeError("down")), world.plans, policy=SYNTH, now=lambda: T0)
    with pytest.raises(UQ.QuotaUnavailable):
        s.reserve(world.users[0], "practice_session", "k")
    assert s.snapshot(world.users[0])["features"][0]["status"] == "unavailable"
    assert s.release("k") is False                                                   # finalization never raises


# ============================================================ route integration (self-contained app, real dependency) ============================================================
@pytest.fixture()
def app_world(world):
    app = FastAPI()
    register_exception_handlers(app)
    calls = []
    world.calls = calls

    @app.post("/practice/{session_id}/setup")
    def setup(session_id: str, fail: bool = False, _ai=Depends(AP.ai_operation("practice", "setup"))):
        calls.append("provider")
        AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=10, output_tokens=5, cost_usd=0.001, latency_ms=5)
        if fail:
            raise RuntimeError("provider failed")
        return {"ok": True}

    @app.post("/practice/{session_id}/answer")
    def answer(session_id: str, _ai=Depends(AP.ai_operation("practice", "answer_feedback"))):
        calls.append("answer")
        AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=10, output_tokens=5, cost_usd=None, latency_ms=5)
        return {"ok": True}

    from src.api.routes import usage_quotas

    app.include_router(usage_quotas.router)
    app.dependency_overrides[get_current_user_id] = lambda request=None: 0
    def _uid(request: Request) -> int:
        return int(request.headers["x-test-user"])
    app.dependency_overrides[get_current_user_id] = _uid
    app.dependency_overrides[get_repository] = lambda: SimpleNamespace(session_factory=world.sf)
    app.dependency_overrides[get_pause_service] = lambda: PauseService(world.sf, environment="development")
    world.client = TestClient(app, raise_server_exceptions=False)
    return world


def hdr(u):
    return {"x-test-user": str(u)}


def test_gate_off_the_routes_behave_exactly_as_before_and_expose_no_numbers(app_world):
    w = app_world
    for i in range(5):
        assert w.client.post(f"/practice/s{i}/setup", headers=hdr(w.users[0])).status_code == 200
    assert w.client.get("/usage-quotas", headers=hdr(w.users[0])).json() == {"enforcement_active": False, "policy_version": None, "features": []}
    with w.sf() as db:
        assert db.scalar(select(func.count()).select_from(UsageQuotaReservation)) == 0


def test_denial_happens_before_any_provider_call_and_is_a_safe_envelope(app_world, on, monkeypatch):
    monkeypatch.setattr(UQ, "DEFAULT_POLICY", SYNTH)
    w = app_world
    h = hdr(w.users[0])
    assert [w.client.post(f"/practice/s{i}/setup", headers=h).status_code for i in range(2)] == [200, 200]
    before = len(w.calls)
    r = w.client.post("/practice/s9/setup", headers=h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "usage_quota_exhausted" and "Retry-After" in r.headers
    assert {"feature", "period", "reset_at", "retry_after_seconds"} <= set(r.json()["error"]) and len(w.calls) == before
    blob = r.text.lower()
    assert not any(t in blob for t in ("upgrade", "premium", "price", "checkout", "plan", "subscribe", "€"))


def test_only_the_session_start_consumes_a_unit_follow_up_steps_do_not(app_world, on, monkeypatch):
    monkeypatch.setattr(UQ, "DEFAULT_POLICY", SYNTH)
    w = app_world
    h = hdr(w.users[0])
    assert w.client.post("/practice/s1/setup", headers=h).status_code == 200
    assert all(w.client.post("/practice/s1/answer", headers=h).status_code == 200 for _ in range(6))
    assert used(w, w.users[0]) == 1


def test_a_failed_provider_operation_returns_the_unit_but_keeps_the_provider_ledger(app_world, on, monkeypatch):
    monkeypatch.setattr(UQ, "DEFAULT_POLICY", SYNTH)
    w = app_world
    h = hdr(w.users[0])
    assert w.client.post("/practice/s1/setup?fail=true", headers={**h, "idempotency-key": "k1"}).status_code == 500
    assert used(w, w.users[0]) == 0
    with w.sf() as db:
        row = db.scalar(select(AIOperationEvent).where(AIOperationEvent.user_id == w.users[0]))
        assert row is not None and row.status == "failed" and row.total_tokens == 15       # actual provider consumption is not lost
    assert w.client.post("/practice/s1/setup", headers={**h, "idempotency-key": "k2"}).status_code == 200
    assert used(w, w.users[0]) == 1


def test_a_replayed_idempotency_key_after_success_is_one_unit(app_world, on, monkeypatch):
    monkeypatch.setattr(UQ, "DEFAULT_POLICY", SYNTH)
    w = app_world
    h = {**hdr(w.users[0]), "idempotency-key": "same"}
    assert all(w.client.post("/practice/s1/setup", headers=h).status_code == 200 for _ in range(3))
    assert used(w, w.users[0]) == 1


def test_missing_policy_with_enforcement_on_fails_closed_before_the_provider(app_world, on):
    w = app_world
    r = w.client.post("/practice/s1/setup", headers=hdr(w.users[0]))
    assert r.status_code == 503 and r.json()["error"]["code"] == "usage_quota_unavailable" and w.calls == []


def test_the_quota_endpoint_is_caller_scoped_and_forged_headers_change_nothing(app_world, on, monkeypatch):
    monkeypatch.setattr(UQ, "DEFAULT_POLICY", SYNTH)
    w = app_world
    w.client.post("/practice/s1/setup", headers=hdr(w.users[0]))
    mine = w.client.get("/usage-quotas", headers={**hdr(w.users[0]), "x-plan": "premium", "x-tier": "premium"}).json()
    other = w.client.get("/usage-quotas", headers=hdr(w.users[1])).json()
    f = {x["feature"]: x for x in mine["features"]}["practice_session"]
    assert mine["enforcement_active"] and f["allowance"] == 2 and f["used"] == 1
    assert {x["feature"]: x for x in other["features"]}["practice_session"]["used"] == 0
    assert set(f) <= {"feature", "unit", "status", "period", "allowance", "used", "remaining", "reset_at"}


# ============================================================ structure and safety ============================================================
def test_every_quota_operation_is_a_real_wired_operation_and_maps_to_one_feature():
    import re
    src = (ROOT / "src/api/routes/interview.py").read_text() + (ROOT / "src/api/routes/career.py").read_text()
    wired = set(re.findall(r'ai_operation\("(\w+)", "(\w+)"\)', src))
    for f in UQ.QUOTA_FEATURES.values():
        assert f.operations <= wired
    flat = [op for f in UQ.QUOTA_FEATURES.values() for op in f.operations]
    assert len(flat) == len(set(flat))


def test_the_quota_module_does_not_touch_billing_stripe_or_the_provider_ledger():
    text = (ROOT / "src/application/usage_quota.py").read_text().lower()
    code = "\n".join(l for l in text.splitlines() if not l.strip().startswith(("#", '"""')))
    for token in ("import stripe", "from src.billing", "aioperationevent", "openrouter", "subscription_repository"):
        assert token not in code, token


def test_all_rollout_and_billing_gates_stay_off():
    from src.application.history_access import HISTORY_RESTRICTIONS_ENFORCED
    from src.application.model_profile_access import MODEL_PROFILE_ENFORCED
    from src.billing import policy as bp
    assert AP.AI_COST_LIMITS_ENFORCED is False and HISTORY_RESTRICTIONS_ENFORCED is False and MODEL_PROFILE_ENFORCED is False and UQ.USAGE_QUOTAS_ENFORCED is False
    for gate in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED",
                 "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, gate) is False


def test_the_permission_registry_is_unchanged():
    from src.application.admin_permissions import PERMISSIONS
    assert len(PERMISSIONS) == 44


def test_migration_0033_upgrades_and_the_chain_has_one_head_upgrades_cleanly_and_downgrades_without_touching_other_tables(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0038_compensation_concepts"]
    command.upgrade(cfg, "0032_ai_operation_events")
    assert "usage_quota_counters" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert {"usage_quota_counters", "usage_quota_reservations"} <= set(insp.get_table_names())
    assert any(u["name"] == "uq_quota_reservation_key" for u in insp.get_unique_constraints("usage_quota_reservations"))
    assert any(u["name"] == "uq_quota_counter" for u in insp.get_unique_constraints("usage_quota_counters"))
    for t in ("usage_quota_counters", "usage_quota_reservations"):
        fks = insp.get_foreign_keys(t)
        assert fks and fks[0]["referred_table"] == "users" and fks[0]["options"].get("ondelete") == "CASCADE"
    command.downgrade(cfg, "0032_ai_operation_events")
    after = inspect(create_engine(url))
    assert "usage_quota_counters" not in after.get_table_names() and "ai_operation_events" in after.get_table_names()
    command.upgrade(cfg, "head")


def test_the_orm_models_and_the_migration_agree_on_columns(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    for model in (UsageQuotaCounter, UsageQuotaReservation):
        assert {c["name"] for c in insp.get_columns(model.__tablename__)} == {c.name for c in model.__table__.columns}


def test_check_constraints_reject_inconsistent_rows(world):
    from sqlalchemy.exc import IntegrityError
    with world.sf() as db:
        db.add(UsageQuotaReservation(op_key="bad", user_id=world.users[0], feature="practice_session", period_start=T0, state="bogus", policy_version="v",
                                     expires_at=T0))
        with pytest.raises(IntegrityError):
            db.commit()
    with world.sf() as db:
        db.add(UsageQuotaCounter(user_id=world.users[0], feature="practice_session", period_start=T0, used=-1, policy_version="v", updated_at=T0))
        with pytest.raises(IntegrityError):
            db.commit()
