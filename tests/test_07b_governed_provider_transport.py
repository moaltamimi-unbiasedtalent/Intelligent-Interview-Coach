"""07B qualification through synthetic HTTPX transports and disposable durable ledgers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing
import os
import socket
import sqlite3
import sys
import threading
from concurrent.futures import CancelledError as SyncCancelledError, ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from types import ModuleType

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from scripts import eval_ragas
from src.copilot.config import CopilotConfig
from src.copilot.evaluation import ragas_adapter
from src.copilot.openrouter_embeddings import OpenRouterEmbedder
from src.copilot.rag.translation import QueryTranslator
from src.llm.budget import config as C
from src.llm.budget import governor as G
from src.llm.budget import script_guard
from src.llm.budget.errors import BudgetError
from src.llm.budget.ledger import DbBudgetLedger, Reservation
from src.persistence import AiBudgetControl, AiBudgetEntry, Base, make_engine, make_session_factory
from tests.test_ai_budget_governor_05c import MARKER, MODEL, URL, body_usage, raw_config

EMBED = "provider/embed"
KEY = "synthetic-fixture-key"
CHAT = f"{URL}/chat/completions"
EMBED_URL = f"{URL}/embeddings"
CLI = ["--governed-07b", "--mode", "judge", "--allow-paid", "--subset", "reviewer", "--limit", "1"]


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("real socket use is forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(script_guard, "getproxies", lambda: {})
    yield
    G.uninstall()


def _policy(path, ledger_url, **changes):
    raw = raw_config(allowed_provider_hosts=["openrouter.ai"])
    raw["classes"] = {"evaluation": raw["classes"]["evaluation"]}
    raw["classes"]["evaluation"]["categories"]["agent"] = dict(raw["classes"]["evaluation"]["categories"]["evaluation"])
    raw["limits"].update(max_retries=0, max_concurrency=1, max_input_tokens=6000, request_timeout_s=2)
    raw["total"] = {"hard_cap_usd": "2.00", "stop_usd": "1.50", "max_requests": 20}
    now = datetime.now(timezone.utc)
    start, end = (now - timedelta(hours=1)).isoformat(), (now + timedelta(hours=1)).isoformat()
    raw["approval"] = {
        "scope": "07b", "environment": "development", "currency": "USD",
        "period_start": start, "expires_at": end,
        "pricing_effective_at": start, "pricing_expires_at": end,
        "owner": "fixture", "approver": "fixture", "pricing_source": "fixture",
        "reconciliation_owner": "fixture", "incident_owner": "fixture",
        "ledger_url_sha256": hashlib.sha256(ledger_url.encode()).hexdigest(),
        "operation_models": {
            "agent": MODEL, "ragas": MODEL, "retrieval_embedding": EMBED, "evaluator_embedding": EMBED,
        },
    } | changes
    path.write_text(json.dumps(raw), encoding="utf-8")
    return {
        C.CONFIG_PATH_ENV: str(path), C.GOVERNED_07B_LEDGER_ENV: ledger_url, C.MARKER_ENV: MARKER,
        C.MODE_ENV: "enforce", C.CLASS_ENV: "evaluation", "API_ENV": "development",
    }


@pytest.fixture()
def env(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'ledger.sqlite3'}"
    engine = make_engine(db_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return _policy(tmp_path / "policy.json", db_url)


def _build(env):
    engine = make_engine(env[C.GOVERNED_07B_LEDGER_ENV])
    factory = make_session_factory(engine)
    return G.BudgetGovernor.build(factory, environ=env, governed_07b=True), engine, factory


def _chat(text="synthetic", **overrides):
    return {"model": MODEL, "messages": [{"role": "user", "content": text}], "max_tokens": 32} | overrides


def _request(url=CHAT, body=None, *, op="ragas", method="POST", headers=None):
    headers = ({G.OP_HEADER: op} if op else {}) | (headers or {})
    return httpx.Request(method, url, json=_chat() if body is None else body, headers=headers)


def _dispatch(gov, request, handler, *, asynchronous=False, follow_redirects=False):
    if asynchronous:
        async def send():
            async with gov.prototype_client(handler, asynchronous=True) as client:
                return await gov.send_async(httpx.AsyncClient.send, client, request, {"follow_redirects": follow_redirects})

        return asyncio.run(send())
    with gov.prototype_client(handler) as client:
        return gov.send_sync(httpx.Client.send, client, request, {"follow_redirects": follow_redirects})


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(("url", "body", "operation", "headers", "reason"), [
    ("https://fixture.invalid/v1/chat/completions", _chat(), "", {}, "provider_host_not_allowed"),
    ("https://fixture.invalid/custom", _chat(), "", {}, "provider_host_not_allowed"),
    ("https://fixture.invalid/custom", {}, "ragas", {}, "provider_host_not_allowed"),
    ("https://api.openai.com/v1/chat/completions", _chat(), "", {}, "provider_host_not_allowed"),
    (f"{URL}/responses", _chat(), "ragas", {}, "endpoint_not_allowed"),
    ("https://openrouter.ai/wrong/chat/completions", _chat(), "ragas", {}, "endpoint_not_allowed"),
    (f"{CHAT}?route=other", _chat(), "ragas", {}, "endpoint_not_allowed"),
    (f"{CHAT}/", _chat(), "ragas", {}, "endpoint_not_allowed"),
    ("http://openrouter.ai/api/v1/chat/completions", _chat(), "ragas", {}, "provider_endpoint_invalid"),
    (CHAT, _chat(), "ragas", {"host": "fixture.invalid"}, "provider_endpoint_invalid"),
    (CHAT, _chat(model="fixture/unpriced"), "ragas", {}, "model_not_priced"),
    (CHAT, _chat(model=EMBED), "ragas", {}, "model_not_allowed"),
    (CHAT, _chat(models=[MODEL]), "ragas", {}, "request_shape_not_supported"),
    (CHAT, _chat(provider={"allow_fallbacks": True}), "ragas", {}, "request_shape_not_supported"),
    (CHAT, _chat(max_tokens=None), "ragas", {}, "output_cap_missing"),
    (CHAT, _chat(max_tokens=501), "ragas", {}, "output_cap_exceeds_limit"),
    (CHAT, _chat(), "ragas", {"x-stainless-retry-count": "1"}, "retry_limit"),
    (CHAT, _chat(), "", {}, "category_unknown"),
    (EMBED_URL, {"model": EMBED, "input": [1]}, "evaluator_embedding", {}, "embedding_input_invalid"),
    (EMBED_URL, {"model": EMBED, "input": [""]}, "evaluator_embedding", {}, "embedding_input_invalid"),
    (EMBED_URL, {"model": EMBED, "input": ["x"] * 65}, "evaluator_embedding", {}, "input_too_large"),
    (EMBED_URL, {"model": EMBED, "input": ["x" * 6001]}, "evaluator_embedding", {}, "input_too_large"),
])
def test_refusal_before_dispatch(env, asynchronous, url, body, operation, headers, reason):
    gov, engine, _ = _build(env)
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(url, body, op=operation, headers=headers), lambda _: pytest.fail("dispatched"), asynchronous=asynchronous)
        assert exc.value.reason == reason
        assert gov.status()["requests"] == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_ordinary_http_and_redirect_boundary(env, asynchronous):
    gov, engine, _ = _build(env)
    calls = []

    def transport(request):
        calls.append(request.url.path)
        if request.url.path == "/redirect":
            return httpx.Response(307, headers={"location": "/health"})
        return httpx.Response(204)

    async def ordinary_async():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            assert (await client.get("https://fixture.invalid/redirect", follow_redirects=True)).status_code == 204

    try:
        if asynchronous:
            asyncio.run(ordinary_async())
        else:
            with httpx.Client(transport=httpx.MockTransport(transport)) as client:
                assert client.get("https://fixture.invalid/redirect", follow_redirects=True).status_code == 204
        assert calls == ["/redirect", "/health"]
        assert gov.status()["requests"] == 0

        def provider(request):
            assert request.url.path == "/api/v1/chat/completions"
            calls.append(request.url.path)
            return httpx.Response(307, headers={"location": "https://fixture.invalid/alternate"})

        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(), provider, asynchronous=asynchronous, follow_redirects=True)
        assert exc.value.reason == "outcome_unknown"
        assert calls == ["/redirect", "/health", "/api/v1/chat/completions"]
        assert gov.status()["calls_by_state"] == {"unknown": 1}
    finally:
        engine.dispose()


def test_duplicate_json_fields_are_refused(env):
    gov, engine, _ = _build(env)
    request = httpx.Request("POST", CHAT, headers={G.OP_HEADER: "ragas"},
                            content=b'{"model":"fixture/unpriced","model":"provider/model-a","messages":[]}')
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, request, lambda _: pytest.fail("dispatched"))
        assert exc.value.reason == "body_unreadable"
        assert gov.status()["requests"] == 0
    finally:
        engine.dispose()


def test_approval_rechecked_before_dispatch(env):
    from pathlib import Path

    gov, engine, _ = _build(env)
    try:
        # An already-installed governor will also refuse a changed on-disk policy.
        path = Path(env[C.CONFIG_PATH_ENV])
        old = path.read_text(encoding="utf-8")
        path.write_text(old.replace('"scope": "07b"', '"scope": "other"'), encoding="utf-8")
        with pytest.raises(BudgetError, match="policy_mismatch|runtime budget file changed"):
            _dispatch(gov, _request(), lambda _: pytest.fail("dispatched"))
        path.write_text(old, encoding="utf-8")

        class AfterExpiry(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(hours=2)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(C, "datetime", AfterExpiry)
            with pytest.raises(BudgetError) as exc:
                _dispatch(gov, _request(), lambda _: pytest.fail("dispatched"))
            assert exc.value.reason == "approval_invalid"
        assert gov.status()["requests"] == 0
    finally:
        engine.dispose()


def test_approval_expiring_during_reservation_refuses_dispatch(env, monkeypatch):
    gov, engine, _ = _build(env)
    reserve = gov.ledger.reserve

    class AfterExpiry(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(hours=2)

    def reserve_then_expire(*args, **kwargs):
        result = reserve(*args, **kwargs)
        monkeypatch.setattr(C, "datetime", AfterExpiry)
        return result

    monkeypatch.setattr(gov.ledger, "reserve", reserve_then_expire)
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(), lambda _: pytest.fail("dispatched"))
        assert exc.value.reason == "approval_invalid"
        assert gov.status()["calls_by_state"] == {"rejected": 1}
        assert gov.status()["held_usd"] == "0.000000"
    finally:
        engine.dispose()


@pytest.mark.parametrize("mode", ["offline", "live"])
def test_cli_refuses_legacy_before_credentials(monkeypatch, mode, capsys):
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", mode)
    monkeypatch.setattr(ragas_adapter, "evaluator_config_from_env", lambda **kw: pytest.fail("credentials resolved"))
    assert eval_ragas.main(CLI, prototype_handler=lambda _: pytest.fail("unexpected dispatch")) == 2
    assert "guard_conflict" in capsys.readouterr().err
    assert G.active_governor() is None


def test_cli_rejects_legacy_active_control_before_credentials(monkeypatch):
    from src.demo_live.guard import ProviderControl

    ctl = ProviderControl("offline").install()
    try:
        with pytest.raises(BudgetError) as exc:
            script_guard.require_paid_budget("fixture", governed_07b=True)
        assert exc.value.reason == "guard_conflict"
    finally:
        ctl.uninstall()


@pytest.mark.parametrize("options", [[], ["--live"], ["--allow-chat-fallback"], ["--estimate-only"], ["--limit", "0"]])
def test_cli_requires_bounded_explicit_scope(monkeypatch, options, capsys):
    monkeypatch.setattr(script_guard, "require_paid_budget", lambda *a, **kw: pytest.fail("budget loaded"))
    assert eval_ragas.main((CLI + options) if options else ["--governed-07b"]) == 2
    assert "evaluation_options_invalid" in capsys.readouterr().err


def test_cli_refuses_dotenv_and_explicit_sdk_proxy_before_credentials(monkeypatch, capsys):
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED")
    monkeypatch.setattr(ragas_adapter, "evaluator_config_from_env", lambda **kw: pytest.fail("credentials resolved"))
    assert eval_ragas.main(CLI) == 2
    assert "evaluation_environment_invalid" in capsys.readouterr().err
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("OPENAI_PROXY", "https://fixture.invalid")
    assert eval_ragas.main(CLI, prototype_handler=lambda _: pytest.fail("unexpected dispatch")) == 2
    assert "provider_proxy_not_allowed" in capsys.readouterr().err


def test_cli_installs_before_credential_resolution_and_uninstalls(env, monkeypatch):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(ragas_adapter, "ragas_available", lambda: True)

    def evaluator(**kw):
        assert G.active_governor().governed_07b
        assert kw == {"allow_chat_fallback": False}
        return ragas_adapter.EvaluatorConfig(KEY, MODEL, URL, EMBED)

    monkeypatch.setattr(ragas_adapter, "evaluator_config_from_env", evaluator)
    from src.copilot import config
    monkeypatch.setattr(config, "load_config", lambda: CopilotConfig(api_key=SecretStr(KEY), base_url=URL, embedding_provider="local"))

    def runner(**kw):
        assert G.active_governor().budget_class == "evaluation"
        assert kw["case_ids"] and kw["limit"] == 1
        return type("FixtureResult", (), {
            "is_failed": False, "status": "COMPLETE", "valid_score_count": 1, "expected_score_count": 1,
            "score_coverage": 1, "output_directory": "fixture", "metrics": {},
        })()

    monkeypatch.setattr(eval_ragas.runner, "run_live_ragas", runner)
    assert eval_ragas.main(CLI, prototype_handler=lambda _: pytest.fail("unexpected dispatch")) == 0
    assert G.active_governor() is None


def test_cli_without_prototype_refuses_before_credentials(env, monkeypatch, capsys):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(ragas_adapter, "evaluator_config_from_env", lambda **kw: pytest.fail("credentials resolved"))
    monkeypatch.setattr(script_guard, "require_paid_budget", lambda *a, **kw: pytest.fail("ledger opened"))
    assert eval_ragas.main(CLI) == 2
    assert "transport_not_qualified" in capsys.readouterr().err
    assert G.active_governor() is None


def test_actual_sdk_sync_async_and_nested_adapters(env, monkeypatch):
    engine = make_engine(env[C.GOVERNED_07B_LEDGER_ENV])
    factory = make_session_factory(engine)
    seen = []

    def transport(request):
        body = json.loads(request.content)
        assert G.OP_HEADER not in request.headers
        assert request.headers.get("x-stainless-retry-count", "0") == "0"
        assert max(request.extensions["timeout"].values()) <= 2
        with factory() as session:
            entry = session.execute(select(AiBudgetEntry).where(AiBudgetEntry.state == "reserved")).scalar_one()
            seen.append((entry.operation, entry.category))
            assert entry.reserved_micro_usd > 0
            assert entry.model == body["model"]
        if request.url.path.endswith("/embeddings"):
            assert all(isinstance(item, str) for item in body["input"])
            return httpx.Response(200, json={
                "object": "list", "model": EMBED, "data": [{"object": "embedding", "index": 0, "embedding": [0.25] * 8}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            })
        assert 0 < body["max_completion_tokens"] <= 500
        return httpx.Response(200, json=body_usage())

    gov = script_guard.require_paid_budget("fixture", environ=env, governed_07b=True, prototype_handler=transport)
    llms, embs = ModuleType("ragas.llms"), ModuleType("ragas.embeddings")
    llms.LangchainLLMWrapper = embs.LangchainEmbeddingsWrapper = lambda model: model
    monkeypatch.setitem(sys.modules, llms.__name__, llms)
    monkeypatch.setitem(sys.modules, embs.__name__, embs)
    try:
        cfg = CopilotConfig(api_key=SecretStr(KEY), base_url=URL, default_model=MODEL,
                            embedding_provider="openrouter", embedding_model=EMBED, embedding_dimensions=8)
        QueryTranslator(config=cfg, model=MODEL).translate("synthetic nested translation")
        assert len(OpenRouterEmbedder(cfg).embed_query("retrieval fixture")) == 8
        chat, embeddings = ragas_adapter._build_evaluator(ragas_adapter.EvaluatorConfig(KEY, MODEL, URL, EMBED))
        assert chat.invoke("sync judge fixture").content
        assert len(embeddings.embed_query("sync embedding fixture")) == 8

        async def async_requests():
            assert (await chat.ainvoke("async judge fixture")).content
            assert len(await embeddings.aembed_query("async embedding fixture")) == 8

        asyncio.run(async_requests())
        assert seen == [
            ("agent", "agent"), ("retrieval_embedding", "embedding"),
            ("ragas", "evaluation"), ("evaluator_embedding", "embedding"),
            ("ragas", "evaluation"), ("evaluator_embedding", "embedding"),
        ]
        assert gov.status()["calls_by_state"] == {"settled": 6}
    finally:
        engine.dispose()


@pytest.mark.parametrize("outcome", ["rate_limit", "timeout"])
def test_actual_evaluator_sdk_never_retries_failure(env, outcome):
    import openai
    from langchain_openai import ChatOpenAI

    gov = script_guard.require_paid_budget("fixture", environ=env, governed_07b=True)
    attempts = []

    def transport(request):
        attempts.append(request.headers["x-stainless-retry-count"])
        if outcome == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        return httpx.Response(429, headers={"retry-after-ms": "1"}, json={"error": {"message": "fixture"}})

    with gov.prototype_client(transport) as client:
        bounds, _ = ragas_adapter._evaluator_bounds()
        judge = ChatOpenAI(model=MODEL, api_key=KEY, base_url=URL, http_client=client, **bounds)
        with pytest.raises(openai.APITimeoutError if outcome == "timeout" else openai.RateLimitError):
            judge.invoke("fixture")
    assert attempts == ["0"]
    assert gov.status()["calls_by_state"] == {"unknown" if outcome == "timeout" else "rejected": 1}


def test_closed_and_killed_governors_refuse_before_dispatch(env):
    closed = G.BudgetGovernor(None, None, "evaluation", governed_07b=True, closed_reason="ledger_unavailable")
    with pytest.raises(BudgetError) as exc:
        _dispatch(closed, _request(), lambda _: pytest.fail("dispatched"))
    assert exc.value.reason == "ledger_unavailable"

    gov, engine, _ = _build(env)
    try:
        gov.ledger.kill("fixture")
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(), lambda _: pytest.fail("dispatched"))
        assert exc.value.reason == "kill_switch"
        assert gov.status()["requests"] == 0
    finally:
        engine.dispose()


def test_policy_is_bound_to_actual_ledger(env, tmp_path):
    wrong = make_engine(f"sqlite:///{tmp_path / 'wrong.sqlite3'}")
    try:
        with pytest.raises(BudgetError) as exc:
            G.BudgetGovernor.build(make_session_factory(wrong), environ=env, governed_07b=True)
        assert exc.value.reason == "ledger_unavailable"
        assert not (tmp_path / "wrong.sqlite3").exists()
    finally:
        wrong.dispose()


def _ledger_worker(env, conn, action, asynchronous):
    gov, engine, _ = _build(env)
    with closing(conn):
        def handler(_):
            conn.send("dispatched")
            if action == "crash_after_dispatch":
                os._exit(42)
            if action != "replay_crash_after_commit":
                assert conn.recv() == "release"
            return httpx.Response(200, json=body_usage())

        if action == "crash_after_reservation":
            def crash_before_handoff(*args):
                conn.send("reserved")
                os._exit(41)

            gov.ledger.accept_07b_handoff = crash_before_handoff
        if action == "crash_during_acceptance":
            def crash_during_acceptance(config):
                conn.send("acceptance_locked")
                os._exit(43)

            G.check_07b_handoff_deadline = crash_during_acceptance
        if action == "replay_crash_after_commit":
            settle = gov.ledger.settle

            def crash_after_settlement_commit(reservation, **kwargs):
                assert kwargs["outcome"] == "settled"
                settle(reservation, **kwargs)
                conn.send("settlement_committed")
                os._exit(44)

            gov.ledger.settle = crash_after_settlement_commit
        request = _request() if action.startswith("replay_") else _request(body=_chat(action))
        try:
            _dispatch(gov, request, handler, asynchronous=asynchronous)
        except BudgetError as exc:
            conn.send(exc.reason)
        else:
            conn.send("settled")
        finally:
            engine.dispose()


def _recv(conn):
    assert conn.poll(15), "disposable worker did not respond"
    return conn.recv()


@pytest.mark.parametrize(("stage", "message", "code"), [
    ("crash_after_reservation", "reserved", 41), ("crash_after_dispatch", "dispatched", 42),
    ("crash_during_acceptance", "acceptance_locked", 43),
])
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_durable_reservation_survives_worker_crash(env, stage, message, code, asynchronous):
    ctx = multiprocessing.get_context("spawn")
    with _worker(ctx, env, stage, asynchronous=asynchronous) as (parent, proc):
        assert _recv(parent) == message
        proc.join(15)
        assert proc.exitcode == code
        gov, engine, factory = _build(env)
        try:
            status = gov.status()
            assert status["calls_by_state"] == {"reserved": 1}
            assert status["open_reservations_usd"] == status["held_usd"] != "0.000000"
            assert status["integrity"]["consistent"]
            with pytest.raises(BudgetError) as exc:
                _dispatch(gov, _request(body=_chat("other"), op="agent"), lambda _: pytest.fail("dispatched"))
            assert exc.value.reason == "concurrency_limit"

            # Fixture evidence explicitly resolves the abandoned reservation.
            # Ordinary restart above could neither dispatch nor release it.
            with factory() as session:
                entry = session.execute(select(AiBudgetEntry)).scalar_one()
                reservation = Reservation(entry.id, entry.budget_class, entry.category,
                                          entry.reserved_micro_usd, entry.endpoint)
            if stage != "crash_after_dispatch":
                gov.ledger.settle(reservation, outcome="rejected")
                assert gov.status()["calls_by_state"] == {"rejected": 1}
            else:
                gov.ledger.settle(reservation, outcome="settled", committed=3)
                assert gov.status()["settled_usd"] == "0.000003"
            assert gov.status()["open_reservations_usd"] == "0.000000"
            assert gov.status()["integrity"]["consistent"]
        finally:
            engine.dispose()


@contextmanager
def _worker(ctx, env, action, *, asynchronous=False):
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_ledger_worker, args=(env, child, action, asynchronous))
    proc.start()
    child.close()
    try:
        yield parent, proc
    finally:
        parent.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(15)


def test_durable_concurrency_and_restart(env):
    ctx = multiprocessing.get_context("spawn")
    with _worker(ctx, env, "first") as (first, proc1):
        assert _recv(first) == "dispatched"
        with _worker(ctx, env, "second") as (second, proc2):
            assert _recv(second) == "concurrency_limit"
            proc2.join(15)
            assert proc2.exitcode == 0
        first.send("release")
        assert _recv(first) == "settled"
        proc1.join(15)
        assert proc1.exitcode == 0
    gov, engine, _ = _build(env)
    try:
        assert gov.status()["calls_by_state"] == {"settled": 1}
        assert _dispatch(gov, _request(body=_chat("after restart")), lambda _: httpx.Response(200, json=body_usage())).status_code == 200
        assert gov.status()["calls_by_state"] == {"settled": 2}
    finally:
        engine.dispose()


@pytest.mark.parametrize("outcome", ["timeout", "missing_usage", "unexpected_model", "malformed_usage"])
def test_unknown_settlement_and_reconciliation_hold_survive_restart(env, outcome):
    gov, engine, _ = _build(env)

    def transport(request):
        if outcome == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        data = body_usage()
        if outcome == "missing_usage":
            del data["usage"]
        elif outcome == "malformed_usage":
            data["usage"] = {"prompt_tokens": "invalid"}
        else:
            data["model"] = "provider/unexpected"
        return httpx.Response(200, json=data)

    try:
        with pytest.raises(httpx.ReadTimeout if outcome == "timeout" else BudgetError):
            _dispatch(gov, _request(), transport)
        status = gov.status()
        assert status["calls_by_state"] == {"unknown": 1}
        assert status["unknown_held_usd"] == status["held_usd"] != "0.000000"
        assert status["settled_usd"] == "0.000000"
    finally:
        engine.dispose()
    restarted, engine, _ = _build(env)
    try:
        # A routine kill-switch resume does not reconcile or release a charge.
        restarted.ledger.resume()
        for text in ("synthetic", "changed retry body"):
            with pytest.raises(BudgetError) as exc:
                _dispatch(restarted, _request(body=_chat(text)), lambda _: pytest.fail("dispatched"))
            assert exc.value.reason == "unknown_outcome_no_retry"
        assert restarted.status()["calls_by_state"] == {"unknown": 1}
        assert restarted.status()["integrity"]["consistent"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("transition", ["kill", "approval_expiry", "pricing_expiry"])
def test_transport_refuses_transition_after_final_governor_read(env, monkeypatch, asynchronous, transition):
    gov, engine, factory = _build(env)
    receive = gov.ledger.accept_07b_handoff
    events = []

    def transition_before_acceptance(reservation, accept):
        with factory() as session:
            assert session.get(AiBudgetEntry, reservation.entry_id).state == "reserved"
        if transition == "kill":
            with closing(sqlite3.connect(engine.url.database, timeout=0)) as writer:
                assert writer.execute("UPDATE ai_budget_controls SET killed=1 WHERE scope_key='global'").rowcount == 1
                writer.commit()
        else:
            key = "expires_at" if transition == "approval_expiry" else "pricing_expires_at"
            cutoff = datetime.fromisoformat(gov.config.approval[key])

            class AtCutoff(datetime):
                @classmethod
                def now(cls, tz=None):
                    return cutoff.astimezone(tz)

            monkeypatch.setattr(C, "datetime", AtCutoff)
        events.append(transition)
        return receive(reservation, accept)

    monkeypatch.setattr(gov.ledger, "accept_07b_handoff", transition_before_acceptance)
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(), lambda _: pytest.fail("provider handler entered"), asynchronous=asynchronous)
        assert exc.value.reason == ("kill_switch" if transition == "kill" else "approval_invalid")
        assert events == [transition]
        assert gov.status()["calls_by_state"] == {"rejected": 1}
        assert gov.status()["held_usd"] == "0.000000"
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_acceptance_owns_sqlite_ordering_until_before_mock_io(env, monkeypatch, asynchronous):
    gov, engine, _ = _build(env)
    check_deadline = G.check_07b_handoff_deadline
    events = []

    def check_with_competing_writer(config):
        with closing(sqlite3.connect(engine.url.database, timeout=0)) as writer:
            with pytest.raises(sqlite3.OperationalError) as exc:
                writer.execute("UPDATE ai_budget_controls SET killed=1 WHERE scope_key='global'")
            assert exc.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        events.append("writer_excluded_at_acceptance")
        check_deadline(config)

    def provider(_):
        with closing(sqlite3.connect(engine.url.database, timeout=0)) as writer:
            assert writer.execute("UPDATE ai_budget_controls SET killed=1 WHERE scope_key='global'").rowcount == 1
            writer.commit()
        assert gov.ledger.killed()
        events.append("kill_committed_during_io_phase")
        return httpx.Response(200, json=body_usage())

    monkeypatch.setattr(G, "check_07b_handoff_deadline", check_with_competing_writer)
    try:
        assert _dispatch(gov, _request(), provider, asynchronous=asynchronous).status_code == 200
        assert events == ["writer_excluded_at_acceptance", "kill_committed_during_io_phase"]
        assert gov.status()["calls_by_state"] == {"settled": 1}
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_independent_kill_commits_while_provider_stalls(env, asynchronous):
    ctx = multiprocessing.get_context("spawn")
    with _worker(ctx, env, "stalled", asynchronous=asynchronous) as (parent, proc):
        assert _recv(parent) == "dispatched"
        gov, engine, factory = _build(env)
        try:
            other = DbBudgetLedger(factory)
            other.kill("fixture")
            assert other.killed() and proc.is_alive()
            with pytest.raises(BudgetError) as exc:
                other.resume()
            assert exc.value.reason == "recovery_reconciliation_required"
            with pytest.raises(BudgetError) as exc:
                _dispatch(gov, _request(body=_chat("second")), lambda _: pytest.fail("dispatched"), asynchronous=asynchronous)
            assert exc.value.reason == "kill_switch"
            assert gov.status()["calls_by_state"] == {"reserved": 1}
            parent.send("release")
            assert _recv(parent) == "settled"
            proc.join(15)
            assert proc.exitcode == 0
            assert gov.status()["calls_by_state"] == {"settled": 1}
            other.resume()
            assert not other.killed()
        finally:
            engine.dispose()


@pytest.mark.parametrize("after_handoff", [False, True], ids=["before", "after"])
def test_sync_interruption_preserves_correct_hold(env, monkeypatch, after_handoff):
    gov, engine, _ = _build(env)

    def interrupt(*args):
        raise SyncCancelledError

    try:
        if not after_handoff:
            monkeypatch.setattr(G, "check_07b_handoff_deadline", interrupt)
        with pytest.raises(SyncCancelledError):
            _dispatch(gov, _request(), interrupt if after_handoff else lambda _: pytest.fail("dispatched"))
        status = gov.status()
        assert status["calls_by_state"] == {"unknown" if after_handoff else "rejected": 1}
        assert (status["held_usd"] != "0.000000") == after_handoff
    finally:
        engine.dispose()


@pytest.mark.parametrize("after_handoff", [False, True], ids=["before", "after"])
def test_async_task_cancellation_preserves_correct_hold(env, monkeypatch, after_handoff):
    gov, engine, _ = _build(env)
    accept = gov.ledger.accept_07b_handoff

    def cancel_before_handoff(reservation, receive):
        asyncio.current_task().cancel()
        return accept(reservation, receive)

    async def exercise():
        entered = asyncio.Event()

        async def provider(_):
            assert after_handoff
            entered.set()
            await asyncio.Future()

        async with gov.prototype_client(provider, asynchronous=True) as client:
            work = asyncio.create_task(gov.send_async(httpx.AsyncClient.send, client, _request(), {}))
            if after_handoff:
                await asyncio.wait_for(entered.wait(), timeout=5)
                work.cancel()
            with pytest.raises(asyncio.CancelledError):
                await work
        assert entered.is_set() == after_handoff

    try:
        if not after_handoff:
            monkeypatch.setattr(gov.ledger, "accept_07b_handoff", cancel_before_handoff)
        asyncio.run(exercise())
        status = gov.status()
        assert status["calls_by_state"] == {"unknown" if after_handoff else "rejected": 1}
        assert (status["held_usd"] != "0.000000") == after_handoff
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("media", [None, "text/plain", "application/json", "application/vnd.fixture+json", "x/unknown"])
def test_dedicated_transport_refuses_unlisted_host_without_intent_heuristic(env, asynchronous, media):
    gov, engine, _ = _build(env)
    headers = {"Content-Type": media} if media else {}
    req = httpx.Request("POST", "https://fixture.invalid/custom", headers=headers, content=json.dumps(_chat()).encode())
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, req, lambda _: pytest.fail("dispatched"), asynchronous=asynchronous)
        assert exc.value.reason == "provider_host_not_allowed"
        assert gov.status()["requests"] == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("extension", [{"read": v} for v in (float("nan"), float("inf"), -float("inf"), -1, 0, True, "1")]
                         + [None, [], {"custom": 1}])
def test_invalid_timeout_refused_before_reservation(env, asynchronous, extension):
    gov, engine, _ = _build(env)
    request = _request()
    request.extensions["timeout"] = extension
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, request, lambda _: pytest.fail("dispatched"), asynchronous=asynchronous)
        assert exc.value.reason == "invalid_timeout"
        assert gov.status()["requests"] == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(("usage", "charged_or_ambiguous"), [
    (None, False), ({"cost": "0", "prompt_tokens": 0}, False), ({"cost": "invalid"}, True),
    ({"prompt_tokens": 3}, True), ({"cost": "0.005"}, True), ({"prompt_tokens": 3, "cost": "invalid"}, True),
])
def test_429_charge_evidence_controls_durable_hold(env, asynchronous, usage, charged_or_ambiguous):
    gov, engine, _ = _build(env)
    body = {"error": {"message": "synthetic"}}
    if usage is not None:
        body["usage"] = usage

    def provider(_):
        return httpx.Response(429, json=body)

    try:
        if charged_or_ambiguous:
            with pytest.raises(BudgetError) as exc:
                _dispatch(gov, _request(), provider, asynchronous=asynchronous)
            assert exc.value.reason == "outcome_unknown"
            assert gov.status()["calls_by_state"] == {"unknown": 1}
            assert gov.status()["unknown_held_usd"] != "0.000000"
            if usage.get("cost") == "0.005":
                assert gov.status()["unknown_held_usd"] == "0.005000"
        else:
            assert _dispatch(gov, _request(), provider, asynchronous=asynchronous).status_code == 429
            assert gov.status()["calls_by_state"] == {"rejected": 1}
            assert gov.status()["held_usd"] == "0.000000"
    finally:
        engine.dispose()
    if charged_or_ambiguous:
        restarted, engine, _ = _build(env)
        try:
            if usage.get("cost") == "0.005":
                with pytest.raises(BudgetError) as exc:
                    restarted.ledger.resume()
                assert exc.value.reason == "recovery_reconciliation_required"
            else:
                restarted.ledger.resume()
            with pytest.raises(BudgetError) as exc:
                _dispatch(restarted, _request(body=_chat("new")), lambda _: pytest.fail("dispatched"), asynchronous=asynchronous)
            assert exc.value.reason == ("kill_switch" if usage.get("cost") == "0.005" else "unknown_outcome_no_retry")
            assert restarted.status()["calls_by_state"] == {"unknown": 1}
        finally:
            engine.dispose()


def _ledger_rows(factory):
    with factory() as session:
        rows = session.scalars(select(AiBudgetEntry).order_by(AiBudgetEntry.id)).all()
        entries = [(row.fingerprint, row.state, row.reserved_micro_usd, row.committed_micro_usd) for row in rows]
        counters = {}
        for scope in ("class:evaluation", "cat:evaluation:evaluation"):
            control = session.get(AiBudgetControl, scope)
            counters[scope] = (control.requests, control.held_micro_usd)
        return entries, counters


def _assert_single_07b_row(factory, fingerprint, state):
    entries, counters = _ledger_rows(factory)
    [(actual, actual_state, reserved, committed)] = entries
    assert (actual, actual_state) == (fingerprint, state)
    held = committed if state == "settled" else reserved
    assert held > 0
    assert counters == {"class:evaluation": (1, held), "cat:evaluation:evaluation": (1, held)}
    return entries, counters


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_durable_replay_refused_after_settlement_commit_crash(env, asynchronous):
    ctx = multiprocessing.get_context("spawn")
    with _worker(ctx, env, "replay_crash_after_commit", asynchronous=asynchronous) as (parent, proc):
        assert _recv(parent) == "dispatched"
        assert _recv(parent) == "settlement_committed"
        proc.join(15)
        assert proc.exitcode == 44

    gov, engine, factory = _build(env)
    try:
        fingerprint = gov.prepare(_request(), "chat", {})[3]
        before = _assert_single_07b_row(factory, fingerprint, "settled")
        # Move beyond the ordinary 05C retry window without expiring the policy.
        gov.ledger._clock = lambda: 10**10
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(), lambda _: pytest.fail("replayed"), asynchronous=asynchronous)
        assert exc.value.reason == "retry_limit"
        assert _ledger_rows(factory) == before
        assert gov.status()["integrity"]["consistent"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_durable_replay_refused_after_same_governor_race(env, monkeypatch, asynchronous):
    gov, engine, factory = _build(env)
    entered = threading.Event()
    release = threading.Event()
    reserve = gov.ledger.reserve
    calls = []

    def delay_first_reservation(*args, **kwargs):
        if threading.current_thread().name.startswith("first-07b"):
            entered.set()
            assert release.wait(5)
        return reserve(*args, **kwargs)

    def provider(_):
        calls.append("accepted")
        return httpx.Response(200, json=body_usage())

    monkeypatch.setattr(gov.ledger, "reserve", delay_first_reservation)
    try:
        fingerprint = gov.prepare(_request(), "chat", {})[3]
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="first-07b") as pool:
            first = pool.submit(_dispatch, gov, _request(), provider, asynchronous=asynchronous)
            try:
                assert entered.wait(5)
                assert _dispatch(gov, _request(), provider, asynchronous=asynchronous).status_code == 200
                before = _assert_single_07b_row(factory, fingerprint, "settled")
            finally:
                release.set()
            with pytest.raises(BudgetError) as exc:
                first.result(timeout=6)
            assert exc.value.reason == "retry_limit"
        assert calls == ["accepted"]
        assert _ledger_rows(factory) == before

        different = _request(body=_chat("different approved fingerprint"))
        different_fingerprint = gov.prepare(different, "chat", {})[3]
        assert different_fingerprint != fingerprint
        assert _dispatch(gov, different, provider, asynchronous=asynchronous).status_code == 200
        assert calls == ["accepted", "accepted"]
        entries, counters = _ledger_rows(factory)
        assert [(row[0], row[1]) for row in entries] == [(fingerprint, "settled"), (different_fingerprint, "settled")]
        total = sum(row[3] for row in entries)
        assert all(value == (2, total) for value in counters.values())
        assert gov.status()["integrity"]["consistent"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_durable_replay_refused_across_independent_sqlite_workers(env, asynchronous):
    ctx = multiprocessing.get_context("spawn")
    gov, engine, factory = _build(env)
    try:
        fingerprint = gov.prepare(_request(), "chat", {})[3]
        with _worker(ctx, env, "replay_wait", asynchronous=asynchronous) as (first, first_proc):
            assert _recv(first) == "dispatched"
            reserved = _assert_single_07b_row(factory, fingerprint, "reserved")
            with _worker(ctx, env, "replay_compete", asynchronous=asynchronous) as (second, proc):
                assert _recv(second) == "concurrency_limit"
                proc.join(15)
                assert proc.exitcode == 0
            assert _ledger_rows(factory) == reserved
            first.send("release")
            assert _recv(first) == "settled"
            first_proc.join(15)
            assert first_proc.exitcode == 0
        settled = _assert_single_07b_row(factory, fingerprint, "settled")
        with _worker(ctx, env, "replay_compete", asynchronous=asynchronous) as (third, proc):
            assert _recv(third) == "retry_limit"
            proc.join(15)
            assert proc.exitcode == 0
        assert _ledger_rows(factory) == settled
        assert gov.status()["integrity"]["consistent"]
    finally:
        engine.dispose()


class _Unreadable429(httpx.SyncByteStream, httpx.AsyncByteStream):
    def __iter__(self):
        raise httpx.ReadError("synthetic unreadable rejection")

    def __aiter__(self):
        raise httpx.ReadError("synthetic unreadable rejection")


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(("body", "reported"), [
    pytest.param(b'{"usage":{"cost":"0.005","cost":null}}', 5000, id="cost-then-null"),
    pytest.param(b'{"usage":{"cost":"0.005","cost":0}}', 5000, id="cost-then-zero"),
    pytest.param(b'{"usage":{"cost":null,"cost":"0.005"}}', 5000, id="null-then-cost"),
    pytest.param(b'{"usage":{"cost":0,"cost":"0.005"}}', 5000, id="zero-then-cost"),
    pytest.param(b'{"usage":{"cost":"0.005","cost":"0.002"}}', 5000, id="conflicting-costs"),
    pytest.param(b'{"usage":{"prompt_tokens":5},"usage":null}', 0, id="usage-then-null"),
    pytest.param(b'{"usage":null,"usage":{"prompt_tokens":5}}', 0, id="null-then-usage"),
    pytest.param(b'{"usage":{"prompt_tokens":5,"prompt_tokens":0}}', 0, id="duplicate-tokens"),
    pytest.param(b'{"usage":{"cost_details":{"upstream_inference_cost":"0.005"}},"usage":null}', 5000, id="nested-cost"),
    pytest.param(b'{"error":{"metadata":{"provider_cost_usd":"0.005","provider_cost_usd":0}}}', 5000, id="nested-provider-cost"),
    pytest.param(b'{"usage":{"cost":"0.005"', 0, id="truncated"),
    pytest.param(b'{"usage":{"cost":NaN}}', 0, id="nonfinite-json"),
    pytest.param(b'{"usage":{"cost":"1e999999"}}', 0, id="unrepresentable-cost"),
    pytest.param(b'{"usage":{"cost":"1e-9999999"}}', 0, id="underflowed-positive-cost"),
    pytest.param(b'{"error":' + b'[' * 1100 + b'0' + b']' * 1100 + b'}', 0, id="excess-nesting"),
    pytest.param(b'{"usage":{"cost":"0.005"},"padding":"' + b'x' * (64 * 1024) + b'"}', 0, id="oversized"),
    pytest.param(None, 0, id="unreadable-stream"),
])
def test_ambiguous_429_retains_durable_exposure(env, asynchronous, body, reported):
    gov, engine, factory = _build(env)
    calls = []

    def provider(_):
        calls.append("accepted")
        if body is None:
            return httpx.Response(429, stream=_Unreadable429())
        return httpx.Response(429, content=body)

    try:
        _, _, worst, fingerprint, _ = gov.prepare(_request(), "chat", {})
        with pytest.raises(httpx.ReadError if body is None else BudgetError) as exc:
            _dispatch(gov, _request(), provider, asynchronous=asynchronous)
        if body is not None:
            assert exc.value.reason == "outcome_unknown"
        assert calls == ["accepted"]
        before = _assert_single_07b_row(factory, fingerprint, "unknown")
        assert before[0][0][2:] == (max(reported, worst), 0)
        assert gov.status()["integrity"]["consistent"]
    finally:
        engine.dispose()
    restarted, engine, _ = _build(env)
    try:
        if reported > worst:
            with pytest.raises(BudgetError) as exc:
                restarted.ledger.resume()
            assert exc.value.reason == "recovery_reconciliation_required"
        else:
            restarted.ledger.resume()
        with pytest.raises(BudgetError) as exc:
            _dispatch(restarted, _request(), provider, asynchronous=asynchronous)
        assert exc.value.reason == ("kill_switch" if reported > worst else "unknown_outcome_no_retry")
        assert calls == ["accepted"]
        assert _ledger_rows(factory) == before
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_429_unrepresentable_total_preserves_hold_and_kills(env, asynchronous):
    gov, engine, factory = _build(env)
    try:
        first = gov.prepare(_request(), "chat", {})[3]
        assert _dispatch(gov, _request(), lambda _: httpx.Response(200, json=body_usage()),
                         asynchronous=asynchronous).status_code == 200
        entries, _ = _assert_single_07b_row(factory, first, "settled")
        _, _, worst, fingerprint, _ = gov.prepare(_request(body=_chat("another")), "chat", {})
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(body=_chat("another")), lambda _: httpx.Response(
                429, content=b'{"usage":{"cost":"9223372036854.775807"}}'), asynchronous=asynchronous)
        assert exc.value.reason == "outcome_unknown"
        rows, counters = _ledger_rows(factory)
        assert rows == entries + [(fingerprint, "unknown", worst, 0)]
        assert counters == dict.fromkeys(counters, (2, entries[0][3] + worst))
        assert gov.killed()
        assert gov.status()["integrity"]["consistent"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_explicit_429_reconciliation_fixture_keeps_settled_identity(env, asynchronous):
    gov, engine, factory = _build(env)
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(gov, _request(), lambda _: httpx.Response(429, content=b'{"usage":{"cost":"0.005","cost":0}}'),
                      asynchronous=asynchronous)
        assert exc.value.reason == "outcome_unknown"
        # Model separately authorized reconciliation using a known synthetic
        # receipt. No runtime resume or transport path performs these writes.
        with factory.begin() as session:
            row = session.scalars(select(AiBudgetEntry)).one()
            assert row.state == "unknown" and row.reserved_micro_usd == 5000
            row.state = "settled"
            row.committed_micro_usd = 7
            for scope in ("class:evaluation", "cat:evaluation:evaluation"):
                session.get(AiBudgetControl, scope).held_micro_usd = 7
        gov.ledger.resume()
        restarted, restart_engine, restart_factory = _build(env)
        try:
            fingerprint = restarted.prepare(_request(), "chat", {})[3]
            before = _assert_single_07b_row(restart_factory, fingerprint, "settled")
            with pytest.raises(BudgetError) as exc:
                _dispatch(restarted, _request(), lambda _: pytest.fail("replayed"), asynchronous=asynchronous)
            assert exc.value.reason == "retry_limit"
            assert _ledger_rows(restart_factory) == before
            assert restarted.status()["integrity"]["consistent"]
        finally:
            restart_engine.dispose()
    finally:
        engine.dispose()


def test_durable_policy_binding_and_idempotent_settlement(env, tmp_path):
    gov, engine, factory = _build(env)
    try:
        reservation, _, _ = gov.reserve(_request(), "chat", {})
        gov.ledger.settle(reservation, outcome="settled", committed=3)
        gov.ledger.settle(reservation, outcome="settled", committed=4)
        assert gov.status()["settled_usd"] == "0.000003"
        with factory() as session:
            policy = session.execute(select(AiBudgetControl.scope_key).where(AiBudgetControl.scope_key.like("policy:%"))).scalar_one()
            assert policy == "policy:" + gov.config.raw_hash
    finally:
        engine.dispose()
    other = _policy(tmp_path / "other.json", env[C.GOVERNED_07B_LEDGER_ENV], incident_owner="fixture replacement")
    restarted, engine, _ = _build(other)
    try:
        with pytest.raises(BudgetError) as exc:
            _dispatch(restarted, _request(), lambda _: pytest.fail("dispatched"))
        assert exc.value.reason == "policy_mismatch"
        assert restarted.status()["calls_by_state"] == {"settled": 1}
    finally:
        engine.dispose()
