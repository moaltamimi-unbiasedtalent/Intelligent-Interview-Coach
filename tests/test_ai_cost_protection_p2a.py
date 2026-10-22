"""W12.4D-P2-A: AI cost protection and usage metering foundation. FULLY OFFLINE: a self-contained FastAPI app mounts the real ``ai_operation`` dependency over
fake provider evidence, an isolated database, fake Redis clients, and ``httpx.MockTransport`` for the real OpenRouter client. No provider, Redis or Stripe call is made.
Nothing here is a plan allowance: ceilings are existing request-per-hour buckets, enforcement is a code constant that is OFF by default."""

from __future__ import annotations

from tests._alembic_head import repository_head
import json
import subprocess
import sys
import textwrap
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from src import ai_protection as AP
from src.api import rate_limit as rl
from src.api.dependencies import get_current_user_id, get_pause_service, get_repository
from src.api.exception_handlers import register_exception_handlers
from src.application.pause import PauseService
from src.config import AppConfig
from src.openrouter_client import OpenRouterClient
from src.persistence import AIOperationEvent, AIUsageFact, User, init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
OLD_LIMIT = rl.POLICIES["cost_interview_user"]


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
    rl.POLICIES["cost_interview_user"] = OLD_LIMIT
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())


class World:
    pass


@pytest.fixture()
def world(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'p2a.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    w = World()
    w.sf = sf
    with sf() as s:
        users = [User(subject=f"u{i}", provider="local", email=f"u{i}@x.test") for i in range(3)]
        s.add_all(users)
        s.commit()
        w.users = [u.id for u in users]
    app = FastAPI()
    register_exception_handlers(app)
    calls = []
    w.calls = calls

    @app.post("/practice/{session_id}/op")
    def practice_op(session_id: str, mode: str = "ok", _ai=Depends(AP.ai_operation("practice", "t_answer"))):
        calls.append(mode)
        if mode == "ok":
            AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=100, output_tokens=50, cost_usd=0.001, latency_ms=20)
        elif mode == "no_usage":
            AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=None, output_tokens=None, cost_usd=None, latency_ms=20)
        elif mode == "zero_usage":
            AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=0, output_tokens=0, cost_usd=None, latency_ms=20)
        elif mode == "repair":
            for _ in range(2):
                AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=80, output_tokens=40, cost_usd=0.001, latency_ms=10)
        elif mode == "retry_then_ok":
            AP.note_attempt(); AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=10, output_tokens=5, cost_usd=None, latency_ms=30)
        elif mode == "ok_then_fail":
            AP.note_attempt(); AP.note_call_ok(model="x/known", input_tokens=60, output_tokens=20, cost_usd=0.0005, latency_ms=10)
            AP.note_attempt(); AP.note_call_failed("timeout", 5000)
            raise RuntimeError("provider failed after a billable call")
        elif mode == "timeout":
            AP.note_attempt(); AP.note_attempt(); AP.note_call_failed("timeout", 9000)
            raise RuntimeError("timeout")
        elif mode == "no_provider":
            pass                                         # e.g. an idempotent replay: no provider work
        return {"ok": True}

    @app.post("/career/chat")
    def career_op(_ai=Depends(AP.ai_operation("career", "t_chat"))):
        AP.note_call_started(); AP.note_call_ok(model="x/known", input_tokens=None, output_tokens=None, cost_usd=None, latency_ms=12)
        return {"ok": True}

    @app.get("/history")
    def history():
        return {"items": []}

    def _uid(request: Request) -> int:
        return int(request.headers["x-test-user"])
    app.dependency_overrides[get_current_user_id] = _uid
    app.dependency_overrides[get_repository] = lambda: SimpleNamespace(session_factory=sf)
    app.dependency_overrides[get_pause_service] = lambda: PauseService(sf, environment="development")
    w.client = TestClient(app, raise_server_exceptions=False)
    w.pause = PauseService(sf, environment="development")
    return w


def hdr(user_id):
    return {"x-test-user": str(user_id)}


def rows(w):
    with w.sf() as s:
        return s.scalars(select(AIOperationEvent).order_by(AIOperationEvent.id)).all()


def small_limit(limit=2):
    rl.POLICIES["cost_interview_user"] = rl.RateLimitPolicy("cost_interview_user", limit, 3600, "user")


# ================================================================ 1. FINDINGS: the buckets exist, units are requests, call sites now exist =====================

def test_the_bucket_units_are_requests_per_window_not_tokens_or_money():
    for name in ("cost_interview_user", "cost_career_user"):
        p = rl.POLICIES[name]
        assert (p.window_seconds, p.scope) == (3600, "user") and isinstance(p.limit, int) and p.on_store_failure == "local"
    assert (rl.POLICIES["cost_interview_user"].limit, rl.POLICIES["cost_career_user"].limit) == (120, 60)      # unchanged existing definitions


def test_every_provider_backed_practice_and_career_route_is_wired_and_non_ai_routes_are_not():
    from src.api.routes import career, history, interview

    def wired(router):
        out = {}
        for route in router.routes:
            dependant = getattr(route, "dependant", None)
            if dependant is None:
                continue
            for d in dependant.dependencies:
                wf = getattr(d.call, "ai_workflow", None)
                if wf:
                    out[(sorted(route.methods)[0], route.path)] = wf
        return out
    practice, careers = wired(interview.router), wired(career.router)
    sid = "/interviews/{session_id}"
    assert {p for (_m, p) in practice} == {"/interviews", f"{sid}/answers", f"{sid}/next-question", f"{sid}/deep-dive", f"{sid}/deep-dive/answers",
                                          f"{sid}/deep-dive/next", f"{sid}/report"} and set(practice.values()) == {"practice"}
    assert {p for (_m, p) in careers} == {"/career/chat", "/career/job-analysis", "/career/questions"} and set(careers.values()) == {"career"}
    assert all(m == "POST" for (m, _p) in list(practice) + list(careers))                  # no read-only route consumes a ceiling or a pause
    assert wired(history.router) == {}                                                       # history stays readable whatever happens to AI work


# ================================================================ 2. ADMISSION: observe by default, enforce when approved ========================================

def test_enforcement_is_a_disabled_code_constant_and_existing_access_is_unchanged_by_default():
    assert AP.AI_COST_LIMITS_ENFORCED is False


def test_observe_mode_never_refuses_but_records_that_the_ceiling_was_exceeded(world):
    small_limit(2)
    codes = [world.client.post("/practice/s1/op", headers=hdr(world.users[0])).status_code for _ in range(5)]
    assert codes == [200] * 5                                                   # existing candidate access is preserved
    flags = [r.limit_observed for r in rows(world)]
    assert flags == [False, False, True, True, True]


def test_enforce_mode_refuses_with_a_safe_localizable_envelope_and_isolates_users(world, monkeypatch):
    monkeypatch.setattr(AP, "AI_COST_LIMITS_ENFORCED", True)
    small_limit(2)
    a = hdr(world.users[0])
    assert [world.client.post("/practice/s1/op", headers=a).status_code for _ in range(2)] == [200, 200]
    blocked = world.client.post("/practice/s1/op", headers=a)
    assert blocked.status_code == 429 and blocked.headers["retry-after"].isdigit()
    err = blocked.json()["error"]
    assert err["code"] == "ai_usage_limit" and err["capability"] == "practice" and err["temporary"] is True and err["retry_after_seconds"] >= 1
    text = json.dumps(err).lower()
    assert "premium" not in text and "upgrade" not in text and "plan" not in text and "$" not in text and "€" not in text
    assert world.client.post("/practice/s1/op", headers=hdr(world.users[1])).status_code == 200      # another user's quota is untouched
    assert len(world.calls) == 3                                                # the refused request never reached the endpoint (no provider work)


def test_the_identity_is_the_authenticated_user_not_a_client_supplied_value(world, monkeypatch):
    monkeypatch.setattr(AP, "AI_COST_LIMITS_ENFORCED", True)
    small_limit(1)
    a = hdr(world.users[0])
    assert world.client.post("/practice/s1/op", headers=a).status_code == 200
    spoof = {**a, "x-user-id": str(world.users[1]), "x-forwarded-for": "9.9.9.9"}
    assert world.client.post("/practice/s1/op", headers=spoof).status_code == 429               # same authenticated user, whatever the extra headers say


def test_career_has_its_own_bucket(world, monkeypatch):
    monkeypatch.setattr(AP, "AI_COST_LIMITS_ENFORCED", True)
    rl.POLICIES["cost_career_user"] = rl.RateLimitPolicy("cost_career_user", 1, 3600, "user")
    try:
        a = hdr(world.users[0])
        assert world.client.post("/career/chat", headers=a).status_code == 200
        assert world.client.post("/career/chat", headers=a).status_code == 429
        assert world.client.post("/practice/s1/op", headers=a).status_code == 200                # practice bucket is separate
    finally:
        rl.POLICIES["cost_career_user"] = rl.COST_POLICIES["cost_career_user"]


def test_the_global_ceiling_also_applies(world, monkeypatch):
    monkeypatch.setattr(AP, "AI_COST_LIMITS_ENFORCED", True)
    old = rl.POLICIES["cost_global"]
    rl.POLICIES["cost_global"] = rl.RateLimitPolicy("cost_global", 2, 3600, "global")
    try:
        codes = [world.client.post("/practice/s1/op", headers=hdr(world.users[i % 3])).status_code for i in range(4)]
        assert codes == [200, 200, 429, 429]
    finally:
        rl.POLICIES["cost_global"] = old


def test_concurrent_requests_cannot_both_slip_under_the_ceiling(world, monkeypatch):
    monkeypatch.setattr(AP, "AI_COST_LIMITS_ENFORCED", True)
    small_limit(5)
    results, lock = [], threading.Lock()

    def go():
        r = world.client.post("/practice/s1/op", headers=hdr(world.users[0]))
        with lock:
            results.append(r.status_code)
    threads = [threading.Thread(target=go) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count(200) == 5 and results.count(429) == 15


# ================================================================ 3. OPERATOR PAUSE ============================================================================

def test_the_new_pause_capabilities_exist_default_to_running_and_do_not_touch_read_only_history(world):
    from src.application.pause import PAUSABLE_CAPABILITIES
    assert {"practice_ai", "career_ai"} <= set(PAUSABLE_CAPABILITIES) and AP.PAUSE_CAPABILITIES == ("practice_ai", "career_ai")
    assert not world.pause.is_paused("practice_ai") and not world.pause.is_paused("career_ai")
    assert world.client.post("/practice/s1/op", headers=hdr(world.users[0])).status_code == 200


def test_pausing_practice_refuses_new_ai_work_before_any_provider_work_and_leaves_reads_and_career_alone(world):
    world.pause.set_paused("practice_ai", True, expected_revision=world.pause.snapshot()["practice_ai"]["revision"], reason="cost incident", actor_user_id=world.users[0])
    assert world.pause.is_paused("practice_ai") and not world.pause.is_paused("career_ai")
    before = len(world.calls)
    r = world.client.post("/practice/s1/op", headers=hdr(world.users[0]))
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_paused" and len(world.calls) == before
    assert "cost incident" not in r.text                                                                              # the internal reason never reaches the candidate
    assert world.client.get("/history", headers=hdr(world.users[0])).status_code == 200                              # read-only access is untouched
    assert world.client.post("/career/chat", headers=hdr(world.users[0])).status_code == 200
    assert rows(world)[-1].workflow == "career"                                                                       # the refused practice request wrote nothing
    world.pause.set_paused("practice_ai", False, expected_revision=world.pause.snapshot()["practice_ai"]["revision"], reason="resolved", actor_user_id=world.users[0])
    assert world.client.post("/practice/s1/op", headers=hdr(world.users[0])).status_code == 200


def test_an_unreadable_pause_store_fails_closed_for_costly_work(world):
    class Broken:
        def is_paused(self, capability):
            from src.application.pause import PauseStateUnavailable
            raise PauseStateUnavailable("x")
    world.client.app.dependency_overrides[get_pause_service] = lambda: Broken()
    r = world.client.post("/practice/s1/op", headers=hdr(world.users[0]))
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_state_unavailable" and world.calls == []


# ================================================================ 4. METERING ==================================================================================

def test_a_successful_operation_records_known_tokens_cost_latency_and_exact_attempts(world):
    world.client.post("/practice/s1/op", headers=hdr(world.users[0]))
    (r,) = rows(world)
    assert (r.workflow, r.operation, r.status, r.provider, r.model_id) == ("practice", "t_answer", "succeeded", "openrouter", "x/known")
    assert (r.input_tokens, r.output_tokens, r.total_tokens, r.token_coverage) == (100, 50, 150, "known")
    assert (r.cost_usd_micros, r.cost_source, r.provider_attempts, r.attempt_coverage, r.latency_ms) == (1000, "reported", 1, "exact", 20)


@pytest.mark.parametrize("mode", ["no_usage", "zero_usage"])
def test_missing_or_zero_usage_is_unknown_never_silently_zero(world, mode):
    world.client.post(f"/practice/s1/op?mode={mode}", headers=hdr(world.users[0]))
    (r,) = rows(world)
    assert (r.input_tokens, r.output_tokens, r.total_tokens, r.cost_usd_micros) == (None, None, None, None)
    assert (r.token_coverage, r.cost_source) == ("unknown", "unavailable") and r.calls_ok == 1


def test_structured_output_repair_is_one_logical_operation_with_all_provider_calls_counted(world):
    world.client.post("/practice/s1/op?mode=repair", headers=hdr(world.users[0]))
    (r,) = rows(world)                                                          # ONE row = one logical operation
    assert (r.calls_ok, r.provider_attempts, r.input_tokens, r.output_tokens, r.cost_usd_micros) == (2, 2, 160, 80, 2000)


def test_retried_attempts_are_counted_as_provider_consumption_but_the_operation_is_counted_once(world):
    world.client.post("/practice/s1/op?mode=retry_then_ok", headers=hdr(world.users[0]))
    (r,) = rows(world)
    assert r.provider_attempts == 2 and r.calls_ok == 1 and r.status == "succeeded"


def test_a_failure_after_a_billable_call_still_reports_the_consumed_tokens(world):
    r = world.client.post("/practice/s1/op?mode=ok_then_fail", headers=hdr(world.users[0]))
    assert r.status_code == 500
    (row,) = rows(world)
    assert row.status == "failed" and (row.input_tokens, row.output_tokens) == (60, 20) and row.calls_ok == 1 and row.calls_failed == 1 and row.provider_attempts == 2
    assert row.failure_category == "timeout" or row.failure_category == "RuntimeError"


def test_a_timeout_with_no_completion_is_a_failed_operation_with_unknown_tokens(world):
    world.client.post("/practice/s1/op?mode=timeout", headers=hdr(world.users[0]))
    (r,) = rows(world)
    assert (r.status, r.provider_attempts, r.token_coverage, r.input_tokens, r.cost_usd_micros) == ("failed", 2, "unknown", None, None)


def test_an_operation_that_never_reached_a_provider_writes_no_row(world):
    for _ in range(3):
        world.client.post("/practice/s1/op?mode=no_provider", headers=hdr(world.users[0]))
    assert rows(world) == []                                                     # writes are bounded by costly work, not by request volume


def test_a_duplicate_submission_with_the_same_idempotency_key_is_one_logical_operation(world):
    h = {**hdr(world.users[0]), "idempotency-key": "same-key-0001"}
    for _ in range(3):
        assert world.client.post("/practice/s1/op", headers=h).status_code == 200
    assert len(rows(world)) == 1


def test_concurrent_duplicate_submissions_do_not_double_record(world):
    h = {**hdr(world.users[0]), "idempotency-key": "same-key-0002"}
    threads = [threading.Thread(target=lambda: world.client.post("/practice/s2/op", headers=h)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(rows(world)) == 1


def test_career_without_token_evidence_is_recorded_as_unknown_with_call_count_coverage(world):
    world.client.post("/career/chat", headers=hdr(world.users[0]))
    (r,) = rows(world)
    assert (r.workflow, r.attempt_coverage, r.provider_attempts, r.token_coverage, r.input_tokens) == ("career", "calls_only", 1, "unknown", None)


def test_rows_are_user_scoped(world):
    world.client.post("/practice/s1/op", headers=hdr(world.users[0]))
    world.client.post("/practice/s1/op", headers=hdr(world.users[1]))
    assert sorted(r.user_id for r in rows(world)) == sorted(world.users[:2])               # account deletion cascades (asserted on the migrated schema below)


def test_no_content_or_secret_can_be_stored_the_schema_has_only_bounded_metadata_columns():
    cols = {c.name: c for c in AIOperationEvent.__table__.columns}
    assert set(cols) == {"id", "op_key", "user_id", "workflow", "operation", "provider", "model_profile", "model_id", "status", "failure_category", "provider_attempts",
                         "attempt_coverage", "calls_ok", "calls_failed", "input_tokens", "output_tokens", "total_tokens", "token_coverage", "cost_usd_micros",
                         "cost_source", "latency_ms", "limit_observed", "started_at", "completed_at"}
    for name, col in cols.items():
        length = getattr(col.type, "length", None)
        assert length is None or length <= 120, name                                # no free-text column exists


# ================================================================ 5. THE REAL OPENROUTER CLIENT REPORTS EVIDENCE ===========================================

def _ok_body(usage=True, model="x/actual", cost=0.002):
    body = {"id": "gen-1", "model": model, "choices": [{"message": {"content": "{\"a\": 1}"}, "finish_reason": "stop"}]}
    if usage:
        body["usage"] = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18, "cost": cost}
    return body


def _client(handler):
    return OpenRouterClient(AppConfig(api_key=SecretStr("test-key-not-real")), http_client=httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda s: None)


def _scope():
    return AP.AiOperationScope(user_id=1, workflow="practice", operation="t", op_key="k")


def _call(client):
    return client.create_chat_completion(model="x/m", messages=[{"role": "user", "content": "hi"}], temperature=None, max_tokens=32)


def test_the_real_client_counts_a_transient_retry_and_reports_known_usage():
    seen = []

    def handler(request):
        seen.append(1)
        return httpx.Response(503) if len(seen) == 1 else httpx.Response(200, json=_ok_body())
    scope = _scope()
    token = AP._current.set(scope)
    try:
        _call(_client(handler))
    finally:
        AP._current.reset(token)
    s = scope.summary(status="succeeded", category=None)
    assert (s["provider_attempts"], s["attempt_coverage"], s["calls_ok"], s["input_tokens"], s["output_tokens"], s["token_coverage"]) == (2, "exact", 1, 11, 7, "known")
    assert s["model_id"] == "x/actual" and s["cost_usd_micros"] == 2000 and s["cost_source"] == "reported"


def test_the_real_client_marks_a_response_without_usage_as_unknown():
    scope = _scope()
    token = AP._current.set(scope)
    try:
        _call(_client(lambda r: httpx.Response(200, json=_ok_body(usage=False))))
    finally:
        AP._current.reset(token)
    s = scope.summary(status="succeeded", category=None)
    assert (s["token_coverage"], s["input_tokens"], s["cost_usd_micros"], s["cost_source"]) == ("unknown", None, None, "unavailable")


def test_the_real_client_records_a_timeout_failure_with_every_attempt_and_no_content():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    scope = _scope()
    token = AP._current.set(scope)
    try:
        with pytest.raises(Exception):
            _call(_client(handler))
    finally:
        AP._current.reset(token)
    s = scope.summary(status="failed", category=None)
    assert s["provider_attempts"] == 1 + __import__("src.constants", fromlist=["x"]).MAX_TRANSIENT_RETRIES and s["calls_failed"] == 1 and s["failure_category"] == "timeout"
    assert "hi" not in json.dumps(s) and "test-key" not in json.dumps(s)


def test_outside_a_scope_the_client_is_unchanged_and_no_state_leaks_between_requests():
    assert AP.current_scope() is None
    _call(_client(lambda r: httpx.Response(200, json=_ok_body())))
    assert AP.current_scope() is None


def test_the_langchain_callback_reports_calls_usage_and_errors_into_the_scope():
    cb = AP.langchain_callback()
    if cb is None:
        pytest.skip("langchain_core unavailable")
    scope = _scope()
    token = AP._current.set(scope)
    try:
        cb.on_chat_model_start({}, [[]], run_id="r1")
        cb.on_llm_end(SimpleNamespace(llm_output={"token_usage": {"prompt_tokens": 9, "completion_tokens": 4}, "model_name": "x/lc"}, generations=[]), run_id="r1")
        cb.on_chat_model_start({}, [[]], run_id="r2")
        cb.on_llm_error(TimeoutError("t"), run_id="r2")
    finally:
        AP._current.reset(token)
    s = scope.summary(status="failed", category=None)
    assert (s["provider_attempts"], s["attempt_coverage"], s["calls_ok"], s["calls_failed"], s["input_tokens"], s["model_id"]) == (2, "calls_only", 1, 1, 9, "x/lc")


# ================================================================ 6. PRACTICE USAGE FACTS NO LONGER TURN MISSING USAGE INTO ZERO ===========================

def test_practice_usage_facts_store_unknown_not_zero_when_the_provider_reported_no_usage(world):
    from src.models import UsageRecord
    from src.reporting.telemetry import record_practice_usage
    missing = UsageRecord(model="openai/gpt-5.6-terra", prompt_tokens=0, completion_tokens=0, total_tokens=0, reported_cost=None, calculated_cost=0.0,
                          cost_source="calculated", request_duration_seconds=1.0)
    known = UsageRecord(model="openai/gpt-5.6-terra", prompt_tokens=10, completion_tokens=5, total_tokens=15, reported_cost=0.001, calculated_cost=0.001,
                        cost_source="reported", request_duration_seconds=1.0)
    assert record_practice_usage(world.sf, world.users[0], "sess-1", 0, [missing, known], "answer") == 2
    with world.sf() as s:
        a, b = s.scalars(select(AIUsageFact).order_by(AIUsageFact.id)).all()
    assert (a.input_tokens, a.total_tokens, a.cost_usd_micros, a.token_coverage, a.cost_source) == (None, None, None, "unknown", "unavailable")
    assert (b.input_tokens, b.total_tokens, b.cost_usd_micros, b.token_coverage) == (10, 15, 1000, "complete")


# ================================================================ 7. THE SHARED LIMITER ========================================================================

class SharedFake:
    """Emulates the Redis window script (trim, count, add) behind ONE lock, so two limiter instances behave like two API processes on one store."""

    def __init__(self):
        self.z, self.lock, self.fail = {}, threading.Lock(), False

    def eval(self, script, numkeys, key, now, window, limit, member):
        if self.fail:
            raise ConnectionError("redis down")
        with self.lock:
            z = [t for t in self.z.get(key, []) if t > now - window]
            if len(z) >= limit:
                self.z[key] = z
                return [0, len(z), min(z)]
            z.append(now)
            self.z[key] = z
            return [1, len(z), 0]


POLICY = rl.RateLimitPolicy("p", 10, 60, "user")


def test_two_limiter_instances_on_one_store_share_one_window_but_isolate_users():
    store = SharedFake()
    a, b = rl.RedisRateLimiter(store), rl.RedisRateLimiter(store)                  # two "processes"
    allowed = [x.hit("p", "user:1", POLICY).allowed for _ in range(10) for x in (a, b)]
    assert allowed.count(True) == 10                                                # one global ceiling, not one per process
    assert a.hit("p", "user:2", POLICY).allowed and b.hit("p", "user:2", POLICY).allowed


def test_the_window_expires_and_slots_return():
    store, t = SharedFake(), [1000.0]
    lim = rl.RedisRateLimiter(store, clock=lambda: t[0])
    pol = rl.RateLimitPolicy("p", 2, 60, "user")
    assert lim.hit("p", "u", pol).allowed and lim.hit("p", "u", pol).allowed and not lim.hit("p", "u", pol).allowed
    t[0] += 61
    assert lim.hit("p", "u", pol).allowed


def test_a_real_multi_process_run_never_exceeds_the_ceiling(tmp_path):
    """Four OS processes share one sqlite-backed fake store that emulates the script's atomic semantics. This proves the ADAPTER's keying and arithmetic across
    processes; the Lua script itself has not been run against a live Redis in CI."""
    db = tmp_path / "shared.db"
    script = textwrap.dedent(f'''
        import sqlite3, sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from src.api import rate_limit as rl
        class Store:
            def __init__(self): self.c = sqlite3.connect({str(db)!r}, timeout=30, isolation_level=None); self.c.execute("create table if not exists z(k text, t real)")
            def eval(self, script, numkeys, key, now, window, limit, member):
                c = self.c
                c.execute("begin immediate")
                c.execute("delete from z where k=? and t<=?", (key, now - window))
                n = c.execute("select count(*) from z where k=?", (key,)).fetchone()[0]
                if n >= limit:
                    o = c.execute("select min(t) from z where k=?", (key,)).fetchone()[0]
                    c.execute("commit"); return [0, n, o]
                c.execute("insert into z values (?,?)", (key, now)); c.execute("commit"); return [1, n + 1, 0]
        lim = rl.RedisRateLimiter(Store())
        pol = rl.RateLimitPolicy("p", 20, 3600, "user")
        print(sum(1 for _ in range(15) if lim.hit("p", "user:7", pol).allowed))
    ''')
    procs = [subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1] for o in outs]
    assert sum(int(o[0].strip()) for o in outs) == 20                                # 4 x 15 attempts, exactly the ceiling of 20 allowed


def test_a_store_outage_applies_the_explicit_per_bucket_policy_and_recovers_honestly():
    store = SharedFake()
    lim = rl.RedisRateLimiter(store)
    local, deny = rl.RateLimitPolicy("c", 2, 60, "user"), rl.RateLimitPolicy("d", 2, 60, "user", on_store_failure="deny")
    store.fail = True
    assert [lim.hit("c", "u", local).allowed for _ in range(3)] == [True, True, False] and lim.degraded is True        # bounded locally: never unlimited, never offline
    r = lim.hit("d", "u", deny)
    assert r.allowed is False and r.retry_after >= 1                                                                    # fail-closed buckets refuse
    store.fail = False
    assert lim.hit("c", "other", local).allowed and lim.degraded is False                                            # sharing restored and reported as such


def test_limiter_status_never_calls_an_in_process_limiter_distributed(monkeypatch):
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    s = rl.limiter_status()
    assert s["backend"] == "in_memory" and s["effectively_distributed"] is False
    redis_lim = rl.RedisRateLimiter(SharedFake())
    redis_lim.degraded = True
    rl.reset_rate_limiter(redis_lim)
    s = rl.limiter_status()
    assert s["backend"] == "redis" and s["degraded"] is True and s["effectively_distributed"] is False


def test_cost_buckets_declare_the_explicit_failure_policy():
    assert {n: rl.POLICIES[n].on_store_failure for n in rl.COST_POLICIES} == {n: "local" for n in rl.COST_POLICIES}


# ================================================================ 8. PRESERVED PRODUCT, MODEL AND BILLING BOUNDARIES ===========================================

def test_no_tier_logic_model_routing_or_billing_is_touched_by_the_protection_module():
    text = (ROOT / "src/ai_protection.py").read_text().lower()
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(("#", '"""')))
    for banned in ("entitlementservice", "require_entitlement", "src.entitlements", "src.billing", "stripe", "plan_code", "resolve_policy", "modelprofile"):
        assert banned not in code, banned


def test_all_billing_gates_stay_off_and_the_profile_vocabulary_is_unchanged():
    from src.billing import policy as P
    from src.llm.models import ModelProfile
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PROVIDER_READS_AUTHORIZED,
            P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 6
    assert [p.value for p in ModelProfile] == ["fast", "balanced", "advanced"]


def test_the_permission_registry_is_unchanged():
    from src.application import admin_permissions as perm
    assert len(perm.PERMISSIONS) == 44 and "platform.billing.recover" in perm.PERMISSIONS


# ================================================================ 9. MIGRATION ===================================================================================

def test_migration_0032_is_the_single_head_upgrades_cleanly_and_downgrades_without_touching_other_tables(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == [repository_head()]
    command.upgrade(cfg, "0031_account_closure")
    assert "ai_operation_events" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert "ai_operation_events" in insp.get_table_names()
    assert {i["name"] for i in insp.get_indexes("ai_operation_events")} >= {"ix_aiop_user_time", "ix_aiop_workflow_time"}
    assert any(u["name"] == "uq_aiop_key" for u in insp.get_unique_constraints("ai_operation_events"))
    fks = insp.get_foreign_keys("ai_operation_events")
    assert fks and fks[0]["referred_table"] == "users" and fks[0]["options"].get("ondelete") == "CASCADE"
    command.downgrade(cfg, "0031_account_closure")
    after = inspect(create_engine(url))
    assert "ai_operation_events" not in after.get_table_names() and "billing_account_closures" in after.get_table_names()
    command.upgrade(cfg, "head")                                                    # re-application is clean


def test_the_orm_model_and_the_migration_agree_on_columns(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    migrated = {c["name"] for c in inspect(create_engine(url)).get_columns("ai_operation_events")}
    assert migrated == {c.name for c in AIOperationEvent.__table__.columns}


def test_check_constraints_reject_inconsistent_rows(world):
    from sqlalchemy.exc import IntegrityError
    base = dict(op_key="k1", user_id=world.users[0], workflow="practice", operation="x", status="succeeded", started_at=__import__("src.persistence", fromlist=["x"]).utcnow())
    for bad in ({"status": "paid"}, {"workflow": "billing"}, {"cost_source": "unavailable", "cost_usd_micros": 0}, {"input_tokens": -1}, {"token_coverage": "complete"}):
        with world.sf() as s:
            s.add(AIOperationEvent(**{**base, "op_key": "k-" + next(iter(bad)), **bad}))
            with pytest.raises(IntegrityError):
                s.commit()
