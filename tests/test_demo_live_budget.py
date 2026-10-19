"""Capstone live-demonstration provider control, verified with MOCKED provider calls and simulated budget exhaustion. No network, no credential, no paid call."""

from __future__ import annotations

import json
import threading

import httpx
import pytest

from src.demo_live import budget as B
from src.demo_live.guard import ProviderControl, install_from_env, operation_headers
from src.demo_live.budget import DemoBudget, DemoBudgetError, eur, load_authorization, load_pricing, micros

URL = "https://openrouter.ai/api/v1"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", "ASK4MO_PROVIDER_MODE", "ASK4MO_DEMO_LEDGER_DIR", "ASK4MO_DEMO_CATEGORY"):
        monkeypatch.delenv(k, raising=False)
    yield
    if ProviderControl._active is not None:
        ProviderControl._active.uninstall()


def ok_body(tin=10, tout=5, cost=None):
    usage = {"prompt_tokens": tin, "completion_tokens": tout}
    if cost is not None:
        usage["cost"] = cost
    return {"id": "x", "model": "openai/gpt-5.4", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "usage": usage}


class Provider:
    def __init__(self, fn=None):
        self.requests: list[httpx.Request] = []
        self.fn = fn or (lambda req, n: httpx.Response(200, json=ok_body()))

    def __call__(self, request):
        self.requests.append(request)
        return self.fn(request, len(self.requests))

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def chat(client, *, model="openai/gpt-5.4", op="agent", cap=100, text="hello", **extra):
    body = {"model": model, "messages": [{"role": "user", "content": text}], **({"max_completion_tokens": cap} if cap is not None else {}), **extra}
    return client.post(f"{URL}/chat/completions", json=body, headers={"x-ask4mo-operation": op} if op else {})


@pytest.fixture()
def live(tmp_path):
    ctl = ProviderControl("live", ledger_dir=str(tmp_path / "ledger")).install()
    yield ctl
    ctl.uninstall()
    ctl.budget.close()


# ------------------------------------------------------------------------------------------------------------------------------ offline mode never contacts a provider
def test_offline_mode_refuses_every_external_host_even_when_a_credential_exists(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-FAKE-TEST-ONLY")
    ctl = ProviderControl("offline").install()
    p = Provider()
    c = p.client()
    with pytest.raises(DemoBudgetError) as e:
        chat(c)
    assert e.value.reason == "offline_mode" and p.requests == []
    with pytest.raises(DemoBudgetError):
        c.get("https://example.com/")
    assert c.get("http://localhost:8000/health").status_code == 200 and c.get("http://testserver/x").status_code == 200       # local traffic stays available
    ctl.uninstall()


def test_a_mode_must_be_offline_or_live_and_unset_means_no_guard(monkeypatch):
    assert install_from_env({}) is None
    with pytest.raises(DemoBudgetError):
        install_from_env({"ASK4MO_PROVIDER_MODE": "maybe"})


def test_live_mode_fails_closed_without_a_ledger_or_in_ci(tmp_path, monkeypatch):
    with pytest.raises(DemoBudgetError) as e:
        ProviderControl("live")
    assert e.value.reason == "ledger_missing"
    monkeypatch.setenv("CI", "true")
    with pytest.raises(DemoBudgetError) as e2:
        ProviderControl("live", ledger_dir=str(tmp_path / "l"))
    assert e2.value.reason == "ci_forbidden"


def test_a_missing_or_invalid_authorization_or_pricing_fails_closed(tmp_path):
    with pytest.raises(DemoBudgetError) as e:
        load_authorization(tmp_path / "nope.json")
    assert e.value.reason == "authorization_unavailable"
    with pytest.raises(DemoBudgetError):
        load_pricing(tmp_path / "nope.json")
    raw = json.loads(B.AUTH_PATH.read_text())
    bad = dict(raw, cap_eur="11.00")
    (tmp_path / "a.json").write_text(json.dumps(bad))
    with pytest.raises(DemoBudgetError):
        load_authorization(tmp_path / "a.json")
    bad = dict(raw, usd_to_eur_rate_applied="0.85")                     # an under-counting rate is refused: USD must be counted at 1.00 or more
    (tmp_path / "b.json").write_text(json.dumps(bad))
    with pytest.raises(DemoBudgetError):
        load_authorization(tmp_path / "b.json")
    bad = dict(raw, category_caps_eur={"agent": "5.00", "interview": "5.00", "ragas": "3.00", "troubleshooting": "1.00"})
    (tmp_path / "c.json").write_text(json.dumps(bad))
    with pytest.raises(DemoBudgetError):
        load_authorization(tmp_path / "c.json")


# ------------------------------------------------------------------------------------------------------------------------------ admission rules
def test_unpriced_models_missing_caps_oversized_requests_streaming_and_other_endpoints_are_refused(live):
    p = Provider()
    c = p.client()
    cases = [({"model": "openai/unknown-model"}, "model_not_priced"), ({"cap": None}, "output_cap_missing"), ({"cap": 4097}, "output_cap_exceeds_limit"), ({"text": "x" * 70000}, "input_too_large"),
             ({"stream": True}, "streaming_not_supported")]
    for kw, reason in cases:
        with pytest.raises(DemoBudgetError) as e:
            chat(c, **kw)
        assert e.value.reason == reason, (kw, e.value.reason)
    with pytest.raises(DemoBudgetError) as e:
        c.post("https://openrouter.ai/api/v1/completions", json={"model": "openai/gpt-5.4"})
    assert e.value.reason == "endpoint_not_allowed"
    with pytest.raises(DemoBudgetError) as e:
        c.post("https://api.openai.com/v1/chat/completions", json={"model": "openai/gpt-5.4", "max_tokens": 5})
    assert e.value.reason == "host_not_allowed"
    assert p.requests == [] and live.budget.summary()["requests"] == 0


def test_a_request_without_a_budget_category_is_refused_and_the_label_never_reaches_the_provider(live):
    p = Provider()
    with pytest.raises(DemoBudgetError) as e:
        chat(p.client(), op=None)
    assert e.value.reason == "category_unknown"
    chat(p.client(), op="agent")
    assert "x-ask4mo-operation" not in p.requests[0].headers


def test_the_timeout_is_clamped_and_retries_beyond_the_approved_maximum_are_refused(live):
    p = Provider()
    c = p.client()
    chat(c)
    assert max(v for v in p.requests[0].extensions["timeout"].values()) <= 60
    with pytest.raises(DemoBudgetError) as e:
        c.post(f"{URL}/chat/completions", json={"model": "openai/gpt-5.4", "messages": [], "max_completion_tokens": 10}, headers={"x-ask4mo-operation": "agent", "x-stainless-retry-count": "2"})
    assert e.value.reason == "retry_limit"


# ------------------------------------------------------------------------------------------------------------------------------ accounting
def test_actual_cost_is_priced_from_usage_in_eur_and_the_provider_cost_is_used_when_larger(live):
    p = Provider(lambda r, n: httpx.Response(200, json=ok_body(1000, 500)))
    chat(p.client(), cap=600, text="x" * 3000)
    s = live.budget.summary()
    assert s["settled_eur"] == eur(micros(1000 * 2.5e-6 + 500 * 15e-6)) and s["requests"] == 1 and s["reserved_open_eur"] == "0.000000"
    p2 = Provider(lambda r, n: httpx.Response(200, json=ok_body(1000, 500, cost=0.5)))
    chat(p2.client(), cap=600, text="x" * 3000)
    assert live.budget.summary()["settled_eur"] == eur(micros(1000 * 2.5e-6 + 500 * 15e-6) + micros(0.5))      # the larger, reported figure is held


def test_embeddings_are_priced_and_counted(live):
    p = Provider(lambda r, n: httpx.Response(200, json={"data": [{"embedding": [0.1]}], "usage": {"prompt_tokens": 1000, "total_tokens": 1000}}))
    r = p.client().post(f"{URL}/embeddings", json={"model": "openai/text-embedding-3-small", "input": ["hello world"]}, headers={"x-ask4mo-operation": "ragas"})
    assert r.status_code == 200
    s = live.budget.summary()
    assert s["settled_eur"] == eur(micros(1000 * 2e-8)) and s["categories"]["ragas"]["held_eur"] == s["settled_eur"]


def test_retries_and_each_attempt_are_counted_separately(live):
    p = Provider(lambda r, n: httpx.Response(200 if n == 2 else 500, json=ok_body() if n == 2 else {}))
    c = p.client()
    assert chat(c).status_code == 500                         # an unknown outcome keeps its worst case
    assert chat(c).status_code == 200
    s = live.budget.summary()
    assert s["requests"] == 2 and s["requests_by_state"] == {"unknown": 1, "settled": 1} and float(s["unknown_held_eur"]) > 0


def test_a_response_without_usage_and_a_transport_failure_keep_the_worst_case(live):
    p = Provider(lambda r, n: httpx.Response(200, json={"choices": []}))
    chat(p.client())
    assert live.budget.summary()["requests_by_state"] == {"unknown": 1}

    def boom(request):
        raise httpx.ConnectError("down")

    c = httpx.Client(transport=httpx.MockTransport(boom))
    with pytest.raises(httpx.ConnectError):
        chat(c)
    s = live.budget.summary()
    assert s["requests_by_state"] == {"unknown": 2} and float(s["unknown_held_eur"]) > 0 and s["reserved_open_eur"] == "0.000000"


def test_a_determinate_provider_rejection_releases_the_money_but_counts_the_call(live):
    p = Provider(lambda r, n: httpx.Response(401, json={"error": "bad key"}))
    chat(p.client())
    s = live.budget.summary()
    assert s["requests"] == 1 and s["held_total_eur"] == "0.000000" and s["requests_by_state"] == {"rejected": 1}


def test_open_reservations_survive_a_restart_at_their_worst_case(tmp_path):
    auth = load_authorization()
    b1 = DemoBudget(tmp_path / "l", auth)
    b1.reserve(category="agent", operation="agent", model="openai/gpt-5.4", endpoint="chat", worst_case=micros("0.50"))
    b1.close()                                              # a crash: the reservation was never settled
    b2 = DemoBudget(tmp_path / "l", auth)
    assert b2.summary()["reserved_open_eur"] == "0.500000" and b2.summary()["held_total_eur"] == "0.500000"
    with pytest.raises(DemoBudgetError):
        b2.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=micros("1.60"))      # 0.50 + 1.60 > the agent allocation of 2.00
    b2.close()


def test_a_ledger_created_under_different_limits_is_never_reused(tmp_path):
    b = DemoBudget(tmp_path / "l", load_authorization())
    b.close()
    other = json.loads(B.AUTH_PATH.read_text())
    other["limits"]["max_requests_total"] = 5
    (tmp_path / "a.json").write_text(json.dumps(other))
    with pytest.raises(DemoBudgetError) as e:
        DemoBudget(tmp_path / "l", load_authorization(tmp_path / "a.json"))
    assert e.value.reason == "ledger_mismatch"


# ------------------------------------------------------------------------------------------------------------------------------ simulated exhaustion
def test_category_allocations_are_enforced_and_the_total_never_exceeds_the_operating_stop(tmp_path):
    b = DemoBudget(tmp_path / "l", load_authorization())
    caps = {"agent": "2.00", "interview": "2.00", "ragas": "3.00", "troubleshooting": "1.00"}
    for cat, cap in caps.items():
        s1 = b.reserve(category=cat, operation=cat, model="m", endpoint="chat", worst_case=micros(cap) - 10)
        b.settle(s1, outcome="settled", committed=micros(cap) - 10)
        with pytest.raises(DemoBudgetError) as e:
            b.reserve(category=cat, operation=cat, model="m", endpoint="chat", worst_case=11)
        assert e.value.reason in ("category_cap", "operating_stop")
    s = b.summary()
    assert float(s["held_total_eur"]) < 8.0 and float(s["remaining_to_cap_eur"]) > 2.0
    b.close()


def test_the_operating_stop_is_eur_8_and_the_hard_cap_is_never_reachable_without_the_reserve(tmp_path):
    b = DemoBudget(tmp_path / "l", load_authorization())
    for cat, cap in {"agent": "2.00", "interview": "2.00", "ragas": "3.00", "troubleshooting": "1.00"}.items():
        s1 = b.reserve(category=cat, operation=cat, model="m", endpoint="chat", worst_case=micros(cap))
        b.settle(s1, outcome="settled", committed=micros(cap))
    assert b.summary()["held_total_eur"] == "8.000000"
    with pytest.raises(DemoBudgetError) as e:
        b.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=1)
    assert e.value.reason in ("operating_stop", "category_cap")
    b.release_reserve()                                                         # the owner's explicit decision
    b.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=micros("1.99"))
    with pytest.raises(DemoBudgetError) as e2:
        b.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=micros("0.02"))
    assert e2.value.reason in ("operating_stop", "hard_cap")                    # EUR 10.00 is never exceeded
    assert float(b.summary()["held_total_eur"]) <= 10.0
    b.close()


def test_concurrent_requests_can_never_jointly_exceed_an_allocation(tmp_path):
    b = DemoBudget(tmp_path / "l", load_authorization())
    admitted, refused = [], []

    def worker():
        try:
            b.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=micros("0.30"))
            admitted.append(1)
        except DemoBudgetError:
            refused.append(1)

    threads = [threading.Thread(target=worker) for _ in range(40)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(admitted) == 6 and len(refused) == 34 and b.summary()["categories"]["agent"]["held_eur"] == "1.800000"      # 6 x 0.30 <= 2.00 < 7 x 0.30
    b.close()


def test_the_request_cap_is_enforced(tmp_path):
    auth = load_authorization()
    b = DemoBudget(tmp_path / "l", auth)
    for _ in range(auth.limits.max_requests_total):
        s = b.reserve(category="troubleshooting", operation="t", model="m", endpoint="chat", worst_case=1)
        b.settle(s, outcome="rejected")
    with pytest.raises(DemoBudgetError) as e:
        b.reserve(category="troubleshooting", operation="t", model="m", endpoint="chat", worst_case=1)
    assert e.value.reason == "request_cap"
    b.close()


def test_an_overrun_engages_the_kill_switch(tmp_path):
    b = DemoBudget(tmp_path / "l", load_authorization())
    s = b.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=100)
    b.settle(s, outcome="settled", committed=500)
    assert b.killed() and "OVERRUN" in b.recent(1)[0]["note"]
    with pytest.raises(DemoBudgetError) as e:
        b.reserve(category="agent", operation="agent", model="m", endpoint="chat", worst_case=1)
    assert e.value.reason == "kill_switch"
    b.close()


def test_the_kill_switch_blocks_chat_embeddings_and_metadata_immediately_and_can_be_resumed(live):
    p = Provider()
    c = p.client()
    chat(c)
    live.budget.kill("test")
    with pytest.raises(DemoBudgetError) as e:
        chat(c)
    assert e.value.reason == "kill_switch"
    with pytest.raises(DemoBudgetError):
        c.get("https://openrouter.ai/api/v1/models")
    assert len(p.requests) == 1
    live.budget.resume()
    assert chat(c).status_code == 200


def test_metadata_reads_are_allowed_unpriced_in_live_mode(live):
    p = Provider(lambda r, n: httpx.Response(200, json={"data": []}))
    assert p.client().get("https://openrouter.ai/api/v1/models").status_code == 200
    assert live.budget.summary()["requests"] == 0


def test_concurrency_is_bounded_and_the_budget_is_atomic_through_the_real_chokepoint(live):
    gate = threading.Event()
    seen = {"max": 0, "now": 0}
    lock = threading.Lock()

    def slow(request, n):
        with lock:
            seen["now"] += 1
            seen["max"] = max(seen["max"], seen["now"])
        gate.wait(0.05)
        with lock:
            seen["now"] -= 1
        return httpx.Response(200, json=ok_body())

    p = Provider(slow)
    c = p.client()
    ts = [threading.Thread(target=lambda: chat(c)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert seen["max"] <= 2 and live.budget.summary()["requests"] == 8


def test_adapters_add_the_operation_label_only_when_a_mode_is_set(monkeypatch):
    assert operation_headers("agent") == {}
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "offline")
    assert operation_headers("agent") == {"X-Ask4Mo-Operation": "agent"}


def test_the_demo_ledger_is_separate_from_the_p10e_ledger():
    import src.p10e.ledger as p10e_ledger

    assert "ledger.db" not in getattr(p10e_ledger, "LEDGER_FILE", "") and B.AUTH_PATH.parent.name == "demo_live"
    src = open(B.__file__, encoding="utf-8").read()
    assert "p10e" not in src.replace("P10E ledger", "").lower().replace("p10e evaluation ledger", "")


def test_evaluator_bounds_apply_only_in_a_provider_mode(monkeypatch):
    """Runs everywhere (imports no optional package)."""
    from src.copilot.evaluation.ragas_adapter import _evaluator_bounds

    assert _evaluator_bounds() == ({}, {})
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "live")
    chat_b, emb_b = _evaluator_bounds()
    assert chat_b == {"max_tokens": 2048, "timeout": 60, "max_retries": 1} and emb_b["check_embedding_ctx_length"] is False and emb_b["max_retries"] == 1


def test_a_missing_ragas_fails_safely_when_a_live_evaluation_is_requested(monkeypatch):
    import src.copilot.evaluation.ragas_adapter as ra

    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    assert ra.ragas_available() is False
    with pytest.raises(ra.RagasNotInstalled):
        ra.run_ragas([], config=ra.EvaluatorConfig(api_key="sk-or-FAKE-TEST-ONLY", base_url=URL, model="m", embedding_model="e"))


def test_ragas_evaluator_is_built_with_the_bounds_when_the_evaluation_extras_are_installed(monkeypatch):
    """Needs the optional evaluation extras (the dedicated CI job installs them); skipped, never failed, in a base install."""
    pytest.importorskip("ragas")
    pytest.importorskip("langchain_openai")
    from src.copilot.evaluation.ragas_adapter import EvaluatorConfig, _build_evaluator

    cfg = EvaluatorConfig(api_key="sk-or-FAKE-TEST-ONLY", base_url=URL, model="openai/gpt-4o-mini", embedding_model="openai/text-embedding-3-small")
    llm, emb = _build_evaluator(cfg)
    assert llm.langchain_llm.max_tokens is None
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "live")
    llm, emb = _build_evaluator(cfg)
    assert llm.langchain_llm.max_tokens == 2048 and llm.langchain_llm.max_retries == 1 and emb.embeddings.check_embedding_ctx_length is False


def test_async_requests_do_not_deadlock_the_event_loop_and_respect_the_concurrency_limit(live):
    import asyncio

    seen = {"max": 0, "now": 0}

    async def slow(request):
        seen["now"] += 1
        seen["max"] = max(seen["max"], seen["now"])
        await asyncio.sleep(0.05)
        seen["now"] -= 1
        return httpx.Response(200, json=ok_body())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as c:
            body = {"model": "openai/gpt-5.4", "messages": [{"role": "user", "content": "hi"}], "max_completion_tokens": 50}
            return await asyncio.wait_for(asyncio.gather(*[c.post(f"{URL}/chat/completions", json=body, headers={"x-ask4mo-operation": "ragas"}) for _ in range(8)]), timeout=20)

    results = asyncio.run(run())
    assert [r.status_code for r in results] == [200] * 8 and seen["max"] <= 2 and live.budget.summary()["requests"] == 8
