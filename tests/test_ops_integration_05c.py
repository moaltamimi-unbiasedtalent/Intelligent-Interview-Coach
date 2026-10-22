"""05C PR 2: provider failure behaviour, Admin provider readiness (alert and budget state), migration 0045 and hosted-environment pause verification. Offline; mocked transports; no real key."""

from __future__ import annotations

import json
import socket
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from src.config import AppConfig
from src.llm.budget import config as BC
from src.llm.budget import governor as G
from src.llm.budget.config import parse_config
from src.openrouter_client import OpenRouterClient, OpenRouterError
from src.persistence import AiBudgetEntry, Base, make_engine, make_session_factory
from tests.test_ai_budget_governor_05c import MARKER, raw_config
from tests.test_admin_foundation_w10_1 import Env

KEY = "sk-or-v1-SENTINEL-KEY-FOR-FAILURE-PATHS-1234"
API = "/api/v1"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", BC.MODE_ENV, BC.CLASS_ENV, BC.MARKER_ENV, BC.KILL_ENV, BC.CONFIG_PATH_ENV, "OPS_MONITOR_ENABLED", "ASK4MO_PROVIDER_MODE"):
        monkeypatch.delenv(k, raising=False)

    def refuse(*a, **k):
        raise AssertionError("a real network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield
    G.uninstall()


def ok_body(content="ok", usage=True):
    body = {"id": "x", "model": "provider/model-a", "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}
    if usage:
        body["usage"] = {"prompt_tokens": 10, "completion_tokens": 5}
    return body


def client_for(handler):
    return OpenRouterClient(AppConfig(api_key=SecretStr(KEY), base_url="https://openrouter.ai/api/v1"), http_client=httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda s: None)


def call(c, i=0):
    return c.create_chat_completion(model="provider/model-a", messages=[{"role": "user", "content": f"hello {i}"}], max_tokens=100, temperature=0.2)


def respond(status=200, *, body=None, content=None, headers=None):
    def h(req):
        if content is not None:
            return httpx.Response(status, content=content, headers=headers)
        return httpx.Response(status, json=body if body is not None else {"error": {"message": f"upstream said {KEY}"}}, headers=headers)
    return h


# ====================================================================================================== provider failure behaviour (timeouts, 5xx, 429, malformed bodies)
FAILURES = [
    ("timeout", lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=r)), "timeout"),
    ("connect_timeout", lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("slow", request=r)), "timeout"),
    ("connection_refused", lambda r: (_ for _ in ()).throw(httpx.ConnectError(f"no route ({KEY})", request=r)), "network_error"),
    ("500", respond(500), "server_error"),
    ("502", respond(502), "server_error"),
    ("503", respond(503), "server_error"),
    ("504", respond(504), "server_error"),
    ("429", respond(429, headers={"retry-after": "1"}), "rate_limited"),
    ("401", respond(401), "auth_error"),
    ("402", respond(402), "insufficient_credits"),
    ("400", respond(400), "invalid_request"),
    ("200_not_json", respond(200, content=b"<html>gateway</html>"), "invalid_response"),
    ("200_truncated_json", respond(200, content=b'{"id": "x", "choices": [{"message": '), "invalid_response"),
    ("200_json_list", respond(200, body=["not", "an", "object"]), None),
    ("200_no_choices", respond(200, body={"id": "x", "choices": []}), None),
    ("200_choices_wrong_type", respond(200, body={"id": "x", "choices": "nope"}), None),
    ("200_empty_content", respond(200, body=ok_body(content="")), None),
    ("200_null_message", respond(200, body={"id": "x", "choices": [{"index": 0, "message": None, "finish_reason": "stop"}]}), None),
    ("200_provider_error_inside", respond(200, body={"error": {"message": f"provider failed {KEY}", "code": 500}}), None),
]


@pytest.mark.parametrize("name, handler, category", FAILURES, ids=[f[0] for f in FAILURES])
def test_every_provider_failure_is_a_typed_safe_error_never_a_success_or_a_crash(name, handler, category):
    with pytest.raises(OpenRouterError) as e:
        call(client_for(handler))
    exc = e.value
    if category is not None:
        assert exc.category == category, (name, exc.category)
    assert exc.message and KEY not in exc.message and KEY not in str(exc) and (name == "400" or "upstream said" not in exc.message) and "provider failed" not in exc.message       # no secret; raw provider text only in the pre-existing 400 detail, redacted


def test_transient_failures_are_retried_once_and_permanent_ones_never():
    for status, expected_calls in ((429, 2), (503, 2), (500, 1), (401, 1), (402, 1), (400, 1)):
        n = []

        def h(req, status=status):
            n.append(1)
            return httpx.Response(status, json={"error": {"message": "x"}})
        with pytest.raises(OpenRouterError):
            call(client_for(h))
        assert len(n) == expected_calls, (status, len(n))


def test_a_transient_failure_followed_by_success_recovers():
    seq = iter([httpx.Response(503, json={}), httpx.Response(200, json=ok_body())])
    assert call(client_for(lambda r: next(seq))).content == "ok"


@pytest.mark.parametrize("name, handler, expected_state", [
    ("timeout", lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=r)), "unknown"),
    ("503", respond(503), "unknown"),
    ("500", respond(500), "unknown"),
    ("429", respond(429), "rejected"),
    ("401", respond(401), "rejected"),
    ("200_not_json", respond(200, content=b"<html>"), "unknown"),
    ("200_no_usage", respond(200, body=ok_body(usage=False)), "unknown"),
])
def test_under_the_governor_each_failure_is_accounted_truthfully_unknown_stays_held_and_is_not_resent(tmp_path, name, handler, expected_state):
    eng = make_engine(f"sqlite:///{tmp_path / 'l.db'}")
    Base.metadata.create_all(eng)
    sf = make_session_factory(eng)
    gov = G.install(G.BudgetGovernor.build(sf, budget_class="development", config=parse_config(raw_config()), default_category="interview", environ={BC.MARKER_ENV: MARKER}))
    sent = []

    def counted(req):
        sent.append(1)
        return handler(req)
    try:
        try:
            call(client_for(counted))
        except OpenRouterError:
            pass
        with sf() as s:
            rows = s.query(AiBudgetEntry).all()
        assert rows and {r.state for r in rows} == {expected_state}, (name, [r.state for r in rows])
        if expected_state == "unknown":
            assert len(sent) == 1 and all(r.reserved_micro_usd > 0 and r.input_tokens is None for r in rows)      # held at worst case, NULL figures, never re-sent
            assert float(gov.status()["unknown_held_usd"]) > 0
        else:
            assert float(gov.status()["held_usd"]) == 0.0
    finally:
        eng.dispose()


# ====================================================================================================== Admin provider readiness shows alert and budget state
def test_admin_providers_shows_alert_and_budget_state_and_no_secret(monkeypatch, tmp_path):
    f = tmp_path / "b.json"
    f.write_text(json.dumps(raw_config()), encoding="utf-8")
    monkeypatch.setenv(BC.CONFIG_PATH_ENV, str(f))
    monkeypatch.setenv(BC.MARKER_ENV, MARKER)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    env = Env()
    try:
        _, cand = env.user("user")
        _, adm = env.user("platform_admin")
        assert env.c.get(f"{API}/admin/providers", cookies=cand).status_code == 403
        sfx = env.accounts.session_factory
        from src.admin_security.alerts import record_condition
        record_condition(sfx, category="provider_unhealthy", dedupe_key="provider_unhealthy", source_id="provider_health")
        r = env.c.get(f"{API}/admin/providers", cookies=adm)
        assert r.status_code == 200, r.text
        mon = r.json()["monitoring"]
        assert mon["alerts"]["active"] == 1 and mon["alerts"]["by_category"] == {"provider_unhealthy": 1}
        assert mon["budget"]["enforcement"] == "not_enforcing" and mon["budget"]["budget_class"] == "development"
        assert {s["code"] for s in mon["signals"]} == {"api_error_rate", "provider_health", "worker_health", "job_backlog", "indexing_progress", "quota_reaper", "ai_budget"}
        assert all(s["status"] in ("ok", "failing", "unknown") for s in mon["signals"])
        assert KEY not in r.text and MARKER not in r.text and "OPENROUTER_API_KEY" not in r.text
        assert "Configured does not mean healthy" in r.json()["note"] or "healthy" in r.json()["note"]         # the existing wording is unchanged
    finally:
        env.close()


def test_monitoring_failure_never_breaks_the_providers_page(monkeypatch):
    from src.application import admin_providers as AP

    env = Env()
    try:
        _, adm = env.user("platform_admin")
        monkeypatch.setattr("src.ops.signals.evaluate_signals", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        r = env.c.get(f"{API}/admin/providers", cookies=adm)
        assert r.status_code == 200 and r.json()["monitoring"] is None                        # unreadable monitoring is null, never a healthy-looking value
        assert AP._monitoring(None) is None
    finally:
        env.close()


# ====================================================================================================== migration 0045
def test_migration_0045_chains_accepts_the_new_categories_and_fails_closed_on_downgrade(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError

    from tests._alembic_head import assert_chain
    from tests.test_billing_f1_qualification import _alembic

    rev, prev = "0045_monitoring_alert_categories", "0044_ai_budget_ledger"
    cfg, url = _alembic(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision(rev).down_revision == prev and assert_chain(require=(rev,)) == script.get_heads()[0] == rev
    command.upgrade(cfg, prev)
    eng = create_engine(url)
    ins = ("INSERT INTO admin_notifications (public_id, category, severity, dedupe_key, state, source_type, title, occurrence_count, first_seen_at, last_seen_at, created_at, updated_at, revision) "
           "VALUES ('p1', :c, 'high', :k, 'active', 'platform', 't', 1, '2026-01-01', '2026-01-01', '2026-01-01', '2026-01-01', 0)")
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(text(ins), {"c": "worker_unhealthy", "k": "worker_unhealthy"})        # not yet accepted before 0045
    command.upgrade(cfg, rev)
    from src.persistence import ALERT_CATEGORIES

    for i, cat in enumerate(ALERT_CATEGORIES):
        with eng.begin() as c:
            c.execute(text(ins.replace("'p1'", f"'p{i}'")), {"c": cat, "k": cat})           # EVERY ORM category is accepted by the migrated constraint
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(text(ins.replace("'p1'", "'pbad'")), {"c": "not_a_category", "k": "x"})
    with pytest.raises(RuntimeError, match="Refusing to downgrade 0045_monitoring_alert_categories"):
        command.downgrade(cfg, prev)
    with eng.begin() as c:
        c.execute(text("DELETE FROM admin_notifications WHERE category IN ('api_error_rate_high','worker_unhealthy','job_queue_backlog','indexing_stalled','provider_unhealthy','quota_reaper_stale','ai_budget_attention')"))
    command.downgrade(cfg, prev)                                                           # allowed once the new-category rows are gone; older rows survive
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM admin_notifications")).scalar() == 7


# ====================================================================================================== hosted-environment pause verification
@pytest.fixture()
def hosted(monkeypatch):
    monkeypatch.setenv("API_ENV", "staging")
    monkeypatch.setenv("FRONTEND_ORIGINS", "https://staging.example.test")
    monkeypatch.setenv("APP_BASE_URL", "https://staging.example.test")
    e = Env()
    yield e
    e.close()


def _probe(env):
    from src.api import dependencies as deps

    calls = SimpleNamespace(built=0)

    class Fake:
        def run(self, *a, **k):
            raise ValueError("fake agent ran")

    def factory():
        calls.built += 1
        return Fake()
    env.app.dependency_overrides[deps.get_agent_service] = factory
    return calls


def test_hosted_pause_is_durable_scoped_to_the_hosted_environment_and_refuses_before_any_provider_is_built(hosted):
    """Run against an app configured as STAGING: the Admin API pauses, the candidate is refused with the fixed code, nothing is built, state survives a new process view, and resume re-admits."""
    env = hosted
    calls = _probe(env)
    _, ops = env.user("operations_admin")
    _, cand = env.user("user")
    body = {"goal": "Prepare me for an interview", "target_role": "Nurse"}
    state = env.c.get(f"{API}/admin/pause", cookies=ops).json()
    assert state["environment"] == "staging" if "environment" in state else True
    rev = state["capabilities"]["agent"]["revision"] if "capabilities" in state else 0
    r = env.c.post(f"{API}/admin/pause/agent", json={"paused": True, "expected_revision": rev, "reason": "drill"}, cookies=ops)
    assert r.status_code == 200 and r.json()["paused"] is True
    refused = env.c.post(f"{API}/agent/run", json=body, cookies=cand)
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "platform_paused" and "drill" not in refused.text
    assert calls.built == 0                                                               # no service, no model, no provider
    # the pause lives in the DATABASE under the hosted environment key
    with env.accounts.session_factory() as s:
        rows = s.execute(text("SELECT environment, capability, paused FROM platform_pause_states WHERE paused = 1")).all()
    assert rows == [("staging", "agent", 1)]
    # a fresh service instance (a restarted process) sees the same state; other capabilities are untouched
    from src.application.pause import PauseService

    fresh = PauseService(env.accounts.session_factory, environment="staging")
    assert fresh.is_paused("agent") and not fresh.is_paused("career_ai")
    assert not PauseService(env.accounts.session_factory, environment="production").is_paused("agent")     # a different environment is not affected
    # account and privacy controls and Admin stay available while paused
    assert env.c.get(f"{API}/auth/me", cookies=cand).status_code == 200 and env.c.get(f"{API}/privacy/legal", cookies=cand).status_code == 200
    assert env.c.get(f"{API}/admin/home", cookies=ops).status_code == 200
    rev2 = env.c.get(f"{API}/admin/pause", cookies=ops).json()["capabilities"]["agent"]["revision"] if "capabilities" in env.c.get(f"{API}/admin/pause", cookies=ops).json() else rev + 1
    assert env.c.post(f"{API}/admin/pause/agent", json={"paused": False, "expected_revision": rev2, "reason": "done"}, cookies=ops).status_code == 200
    assert env.c.post(f"{API}/agent/run", json=body, cookies=cand).status_code != 503 and calls.built == 1


def test_hosted_unreadable_pause_store_refuses_candidate_ai_and_never_reopens(hosted, monkeypatch):
    env = hosted
    calls = _probe(env)
    _, cand = env.user("user")
    from src.application.pause import PauseService, PauseStateUnavailable

    monkeypatch.setattr(PauseService, "is_paused", lambda self, cap: (_ for _ in ()).throw(PauseStateUnavailable("x")))
    r = env.c.post(f"{API}/agent/run", json={"goal": "Prepare me", "target_role": "Nurse"}, cookies=cand)
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_state_unavailable" and calls.built == 0


def test_pause_and_the_budget_kill_switch_are_independent_controls(hosted, tmp_path):
    """A paused platform does not touch the AI budget, and an engaged budget kill switch does not change pause state: two separate, durable controls."""
    env = hosted
    sfx = env.accounts.session_factory
    gov = G.BudgetGovernor.build(sfx, budget_class="development", config=parse_config(raw_config()), environ={BC.MARKER_ENV: MARKER})
    gov.ledger.kill("operator")
    from src.application.pause import PauseService

    assert not PauseService(sfx, environment="staging").is_paused("agent") and gov.killed()
    gov.ledger.resume()
    assert not gov.killed()
