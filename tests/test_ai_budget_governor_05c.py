"""05C PR 1: the production AI budget governor, verified with MOCKED providers only. No network, no credential, no paid call.

Follows ``tests/test_demo_live_budget.py``: every request goes through ``httpx.MockTransport``; a fixture makes any real socket connection fail the test, so "no network" is asserted, not assumed.
Covers exhaustion, concurrency (threads and two independent ledger handles standing in for two processes), the kill switch, unknown outcomes, bounded retries, duplicate suppression,
fail-closed configuration, the approved-budget marker, the Admin status, the models probe and the paid-script wiring.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text

from src.llm.budget import config as C
from src.llm.budget import governor as G
from src.llm.budget.config import load_config, parse_config, require_approved_marker, resolve_budget_class, usd_to_micro
from src.llm.budget.errors import BudgetError
from src.llm.budget.governor import BudgetGovernor
from src.llm.budget.status import budget_status
from src.persistence import AiBudgetEntry, Base, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
URL = "https://openrouter.ai/api/v1"
MODEL = "provider/model-a"
MARKER = "OD-BUDGET:test-ref-001"
SECRET_PROMPT = "PROMPT-TEXT-THAT-MUST-NEVER-BE-STORED"


def raw_config(**over) -> dict:
    raw = {
        "currency": "USD", "approval_marker": MARKER,
        "limits": {"max_input_tokens": 2000, "max_output_tokens": 500, "request_timeout_s": 30, "max_retries": 1, "max_concurrency": 8, "dedupe_window_s": 300},
        "pricing": {"models": {MODEL: {"prompt": "0.000001", "completion": "0.000002"}, "provider/embed": {"prompt": "0.0000001", "completion": "0"}}},
        "classes": {
            "development": {"hard_cap_usd": "1.00", "stop_usd": "0.80", "max_requests": 1000,
                            "categories": {"agent": {"hard_cap_usd": "0.50", "stop_usd": "0.40"}, "interview": {"hard_cap_usd": "0.50", "stop_usd": "0.40"},
                                           "embedding": {"hard_cap_usd": "0.20", "stop_usd": "0.10"}, "evaluation": {"hard_cap_usd": "0.50", "stop_usd": "0.40"}}},
            "evaluation": {"hard_cap_usd": "2.00", "stop_usd": "1.50", "max_requests": 100,
                           "categories": {"evaluation": {"hard_cap_usd": "1.00", "stop_usd": "0.90"}, "embedding": {"hard_cap_usd": "1.00", "stop_usd": "0.90"}}},
            "production": {"hard_cap_usd": "5.00", "stop_usd": "4.00", "max_requests": 1000,
                           "categories": {"agent": {"hard_cap_usd": "2.00", "stop_usd": "1.50"}, "interview": {"hard_cap_usd": "2.00", "stop_usd": "1.50"}}},
        },
    }
    for k, v in over.items():
        raw[k] = v
    return raw


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", C.MODE_ENV, C.CLASS_ENV, C.MARKER_ENV, C.KILL_ENV, C.CONFIG_PATH_ENV, "API_ENV", "ASK4MO_PROVIDER_MODE", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    yield
    G.uninstall()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any real connection attempt fails the test: every provider call here must be served by httpx.MockTransport."""
    def refuse(*a, **k):
        raise AssertionError("a real network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture()
def sf(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    Base.metadata.create_all(eng)
    yield make_session_factory(eng)
    eng.dispose()


def body_usage(tin=10, tout=5, cost=None):
    usage = {"prompt_tokens": tin, "completion_tokens": tout}
    if cost is not None:
        usage["cost"] = cost
    return {"id": "x", "model": MODEL, "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "usage": usage}


class Provider:
    def __init__(self, fn=None):
        self.requests: list[httpx.Request] = []
        self.fn = fn or (lambda req, n: httpx.Response(200, json=body_usage()))
        self._lock = threading.Lock()

    def __call__(self, request):
        with self._lock:
            self.requests.append(request)
            n = len(self.requests)
        return self.fn(request, n)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))

    def aclient(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


_n = [0]


def chat(client, *, model=MODEL, op="agent", cap=100, text_="hello", **extra):
    body = {"model": model, "messages": [{"role": "user", "content": text_}], **({"max_completion_tokens": cap} if cap is not None else {}), **extra}
    return client.post(f"{URL}/chat/completions", json=body, headers={"x-ask4mo-operation": op} if op else {})


def uniq() -> str:
    _n[0] += 1
    return f"{SECRET_PROMPT} #{_n[0]}"


def make_gov(sf, *, klass="development", raw=None, category=None, env=None) -> BudgetGovernor:
    cfg = parse_config(raw or raw_config())
    return BudgetGovernor.build(sf, budget_class=klass, config=cfg, default_category=category, environ={C.MARKER_ENV: MARKER, **(env or {})})


@pytest.fixture()
def live(sf):
    gov = G.install(make_gov(sf))
    yield gov
    G.uninstall()


# ====================================================================================================== configuration fails closed
def test_valid_config_parses_into_integer_micro_usd_rounded_up():
    cfg = parse_config(raw_config())
    assert cfg.classes["development"].ceiling.stop == 800_000 and cfg.classes["development"].ceiling.hard_cap == 1_000_000
    assert usd_to_micro("0.0000011") == 2          # rounded UP, never down
    assert cfg.classes["development"].categories["embedding"].stop == 100_000


def test_missing_config_path_and_unreadable_file_fail_closed(tmp_path):
    with pytest.raises(BudgetError) as e:
        load_config(environ={})
    assert e.value.reason == "config_unavailable"
    with pytest.raises(BudgetError) as e:
        load_config(environ={C.CONFIG_PATH_ENV: str(tmp_path / "nope.json")})
    assert e.value.reason == "config_unavailable"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(BudgetError):
        load_config(environ={C.CONFIG_PATH_ENV: str(bad)})


@pytest.mark.parametrize("mutate", [
    lambda r: r["classes"]["development"].update(stop_usd="2.00"),                                         # stop above hard cap
    lambda r: r["classes"]["development"]["categories"]["agent"].update(hard_cap_usd="9.00", stop_usd="3.00"),  # category above class
    lambda r: r["classes"].update(unknown={"hard_cap_usd": "1", "stop_usd": "1", "max_requests": 1}),       # unknown class
    lambda r: r["classes"]["development"]["categories"].update(mystery={"hard_cap_usd": "0.1", "stop_usd": "0.1"}),   # unknown category
    lambda r: r["limits"].update(max_output_tokens=0),
    lambda r: r.update(pricing={"models": {}}),
    lambda r: r.update(approval_marker="not-a-marker"),
    lambda r: r["classes"]["development"].update(max_requests=0),
    lambda r: r["classes"]["development"].update(hard_cap_usd="-1"),
])
def test_invalid_config_is_refused(mutate):
    raw = raw_config()
    mutate(raw)
    with pytest.raises(BudgetError) as e:
        parse_config(raw)
    assert e.value.reason == "config_invalid"


def test_budget_class_resolution():
    assert resolve_budget_class({}) == "development"
    assert resolve_budget_class({"API_ENV": "production"}) == "production"
    assert resolve_budget_class({"API_ENV": "staging"}) == "production"
    assert resolve_budget_class({"API_ENV": "something-new"}) == "production"       # unknown environments are hosted
    assert resolve_budget_class({C.CLASS_ENV: "evaluation", "API_ENV": "production"}) == "evaluation"
    with pytest.raises(BudgetError):
        resolve_budget_class({C.CLASS_ENV: "yolo"})


# ====================================================================================================== the approved-budget marker
def test_marker_mechanism_never_passes_without_the_owner_defined_value():
    cfg = parse_config(raw_config())
    for env, reason in (({}, "marker_missing"), ({C.MARKER_ENV: "OD-BUDGET:other-ref-9"}, "marker_mismatch")):
        with pytest.raises(BudgetError) as e:
            require_approved_marker(cfg, env)
        assert e.value.reason == reason
        assert MARKER not in str(e.value) and "other-ref-9" not in str(e.value)       # a refusal never echoes either value
    require_approved_marker(cfg, {C.MARKER_ENV: MARKER})
    no_marker = parse_config(raw_config(approval_marker=None))
    with pytest.raises(BudgetError) as e:
        require_approved_marker(no_marker, {C.MARKER_ENV: MARKER})
    assert e.value.reason == "marker_not_configured"


def test_repository_never_ships_a_marker_or_budget_configuration():
    shipped = [p for p in ROOT.rglob("*.json") if "node_modules" not in p.parts and ".git" not in p.parts and ".venv" not in p.parts]
    for p in shipped:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        assert not (isinstance(data, dict) and "approval_marker" in data), p
    for src in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py")) + [ROOT / ".env.staging.example"]:
        if src.exists():
            assert "AI_BUDGET_APPROVED_MARKER=OD-BUDGET" not in src.read_text(encoding="utf-8", errors="ignore"), src


def test_build_refuses_in_ci_without_marker_and_without_ledger_tables(sf, monkeypatch, tmp_path):
    cfg = parse_config(raw_config())
    with pytest.raises(BudgetError) as e:
        BudgetGovernor.build(sf, budget_class="development", config=cfg, environ={})
    assert e.value.reason == "marker_missing"
    with pytest.raises(BudgetError) as e:
        BudgetGovernor.build(sf, budget_class="development", config=cfg, environ={C.MARKER_ENV: MARKER, "CI": "true"})
    assert e.value.reason == "ci_forbidden"
    with pytest.raises(BudgetError) as e:
        BudgetGovernor.build(sf, budget_class="nothing", config=cfg, environ={C.MARKER_ENV: MARKER})
    assert e.value.reason == "class_not_configured"
    empty = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'empty.db'}"))          # no tables: migration 0044 not applied
    with pytest.raises(BudgetError) as e:
        BudgetGovernor.build(empty, budget_class="development", config=cfg, environ={C.MARKER_ENV: MARKER})
    assert e.value.reason == "ledger_unavailable"


# ====================================================================================================== settlement, tokens, latency, errors
def test_settlement_uses_the_larger_of_our_estimate_and_the_provider_figure(live, sf):
    p = Provider(lambda r, n: httpx.Response(200, json=body_usage(100, 50, cost=0.0008)))        # our estimate: 100*1e-6 + 50*2e-6 = 0.0002 USD; provider says 0.0008 (both below the reservation)
    chat(p.client(), cap=500, text_=uniq())
    p2 = Provider(lambda r, n: httpx.Response(200, json=body_usage(20, 400, cost=0.0000005)))    # our estimate 0.00082 is larger than the provider's 0.0000005
    chat(p2.client(), cap=500, text_=uniq())
    with sf() as s:
        rows = s.execute(select(AiBudgetEntry).order_by(AiBudgetEntry.id)).scalars().all()
    assert rows[0].state == "settled" and rows[0].committed_micro_usd == 800 and rows[0].provider_cost_micro_usd == 800 and rows[0].est_cost_micro_usd == 200
    assert rows[1].committed_micro_usd == 820 and rows[1].est_cost_micro_usd == 820 and rows[1].provider_cost_micro_usd == 1
    assert rows[0].input_tokens == 100 and rows[0].output_tokens == 50 and rows[0].latency_ms is not None


def test_a_response_without_usage_is_unknown_held_at_worst_case_with_null_figures(live, sf):
    p = Provider(lambda r, n: httpx.Response(200, json={"id": "x", "choices": []}))
    chat(p.client(), cap=100, text_=uniq())
    with sf() as s:
        row = s.execute(select(AiBudgetEntry)).scalar_one()
    assert row.state == "unknown" and row.committed_micro_usd == 0 and row.reserved_micro_usd > 0
    assert row.input_tokens is None and row.output_tokens is None and row.est_cost_micro_usd is None and row.provider_cost_micro_usd is None    # NULL, never 0
    assert row.error_category == "usage_missing"
    snap = live.status()
    assert float(snap["unknown_held_usd"]) > 0 and float(snap["held_usd"]) == float(snap["unknown_held_usd"])


def test_timeout_and_connection_loss_are_unknown_outcomes_held_at_worst_case(live, sf):
    def boom(req, n):
        raise httpx.ReadTimeout("slow")
    with pytest.raises(httpx.ReadTimeout):
        chat(Provider(boom).client(), text_=uniq())

    def lost(req, n):
        raise httpx.ConnectError("gone")
    with pytest.raises(httpx.ConnectError):
        chat(Provider(lost).client(), text_=uniq())
    with sf() as s:
        rows = s.execute(select(AiBudgetEntry).order_by(AiBudgetEntry.id)).scalars().all()
    assert [r.state for r in rows] == ["unknown", "unknown"] and [r.error_category for r in rows] == ["timeout", "network"]
    assert all(r.reserved_micro_usd > 0 for r in rows)


def test_server_error_and_malformed_200_are_unknown(live, sf):
    chat(Provider(lambda r, n: httpx.Response(503, json={"error": "x"})).client(), text_=uniq())
    chat(Provider(lambda r, n: httpx.Response(200, content=b"<html>not json</html>")).client(), text_=uniq())
    with sf() as s:
        rows = s.execute(select(AiBudgetEntry).order_by(AiBudgetEntry.id)).scalars().all()
    assert [(r.state, r.error_category) for r in rows] == [("unknown", "server_error"), ("unknown", "malformed_body")]


def test_a_429_releases_the_money_but_the_call_stays_counted(live, sf):
    chat(Provider(lambda r, n: httpx.Response(429, json={"error": "slow down"})).client(), text_=uniq())
    snap = live.status()
    assert float(snap["held_usd"]) == 0.0 and snap["requests"] == 1 and snap["calls_by_state"] == {"rejected": 1}
    with sf() as s:
        assert s.execute(select(AiBudgetEntry.error_category)).scalar_one() == "rate_limited"


def test_unknown_outcome_is_never_retried_automatically(live):
    p = Provider(lambda r, n: httpx.Response(503, json={}))
    c = p.client()
    chat(c, text_="same request")
    with pytest.raises(BudgetError) as e:
        chat(c, text_="same request")                                         # an identical call after an unknown outcome
    assert e.value.reason == "unknown_outcome_no_retry" and len(p.requests) == 1
    chat(c, text_="a different request")                                       # a different request is unaffected
    assert len(p.requests) == 2


def test_retries_after_a_determinate_refusal_are_bounded(live):
    p = Provider(lambda r, n: httpx.Response(429, json={}))                    # max_retries = 1 -> one call plus one retry
    c = p.client()
    chat(c, text_="retry me")
    chat(c, text_="retry me")
    with pytest.raises(BudgetError) as e:
        chat(c, text_="retry me")
    assert e.value.reason == "retry_limit" and len(p.requests) == 2


def test_the_sdk_retry_header_beyond_the_bound_is_refused(live):
    p = Provider()
    with pytest.raises(BudgetError) as e:
        p.client().post(f"{URL}/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": "x"}], "max_tokens": 10},
                        headers={"x-stainless-retry-count": "5", "x-ask4mo-operation": "agent"})
    assert e.value.reason == "retry_limit" and not p.requests


def test_an_identical_in_flight_request_is_not_sent_twice(live):
    gate, started = threading.Event(), threading.Event()

    def slow(req, n):
        started.set()
        gate.wait(5)
        return httpx.Response(200, json=body_usage())
    p = Provider(slow)
    errs: list[BudgetError] = []
    t = threading.Thread(target=lambda: chat(p.client(), text_="dup"))
    t.start()
    assert started.wait(5)
    try:
        chat(p.client(), text_="dup")
    except BudgetError as exc:
        errs.append(exc)
    gate.set()
    t.join(5)
    assert [e.reason for e in errs] == ["duplicate_in_flight"] and len(p.requests) == 1


# ====================================================================================================== per-request limits (nothing is dispatched)
@pytest.mark.parametrize("kwargs, reason", [
    (dict(cap=None), "output_cap_missing"),
    (dict(cap=501), "output_cap_exceeds_limit"),
    (dict(model="provider/unpriced"), "model_not_priced"),
    (dict(stream=True), "streaming_not_supported"),
    (dict(text_="x" * 7000), "input_too_large"),
    (dict(op=""), "category_unknown"),
    (dict(op="mystery"), "category_unknown"),
])
def test_per_request_limits_refuse_before_dispatch(live, kwargs, reason):
    p = Provider()
    with pytest.raises(BudgetError) as e:
        chat(p.client(), **kwargs)
    assert e.value.reason == reason and not p.requests
    assert live.status()["requests"] == 0                                       # nothing was reserved


def test_unlisted_endpoint_of_a_governed_host_is_refused_but_other_hosts_pass_through(live):
    p = Provider()
    with pytest.raises(BudgetError) as e:
        p.client().post(f"{URL}/images/generations", json={"model": MODEL})
    assert e.value.reason == "endpoint_not_allowed" and not p.requests
    assert p.client().get("http://localhost/health").status_code == 200        # not a governed host: untouched, nothing recorded
    assert live.status()["requests"] == 0


def test_the_request_timeout_is_clamped_to_the_configured_limit(live):
    seen = {}

    def spy(req, n):
        seen.update(req.extensions.get("timeout") or {})
        return httpx.Response(200, json=body_usage())
    chat(Provider(spy).client(), text_=uniq())
    assert seen and max(seen.values()) <= 30.0


def test_operation_label_is_stripped_before_the_provider_sees_it_and_embeddings_are_always_embedding(live, sf):
    p = Provider(lambda r, n: httpx.Response(200, json={"data": [], "usage": {"prompt_tokens": 20}}))
    chat(Provider().client(), text_=uniq())
    c = p.client()
    c.post(f"{URL}/embeddings", json={"model": "provider/embed", "input": [uniq()]}, headers={"x-ask4mo-operation": "agent"})
    assert "x-ask4mo-operation" not in p.requests[0].headers
    with sf() as s:
        cats = [r.category for r in s.execute(select(AiBudgetEntry).order_by(AiBudgetEntry.id)).scalars()]
    assert cats == ["agent", "embedding"]


def test_default_category_applies_when_the_label_is_missing(sf):
    G.install(make_gov(sf, klass="evaluation", category="evaluation"))
    p = Provider()
    chat(p.client(), op="", text_=uniq())
    assert len(p.requests) == 1


# ====================================================================================================== exhaustion
def test_stop_threshold_is_never_exceeded_and_the_hard_cap_is_unreachable(live, sf):
    # category agent stop = 0.40 USD; one request worst case = ~0.0001*? : cap 500 tokens * 2e-6 = 0.001 + input
    p = Provider(lambda r, n: httpx.Response(200, json=body_usage(30, 500)))      # settles at its full worst-ish case
    refused = None
    for i in range(1000):
        try:
            chat(p.client(), cap=500, text_=uniq())
        except BudgetError as exc:
            refused = exc
            break
    assert refused is not None and refused.reason in ("category_stop", "stop_threshold")
    snap = live.status()
    cat = snap["categories"]["agent"]
    assert float(cat["held_usd"]) <= float(cat["stop_usd"]) <= float(cat["hard_cap_usd"])
    assert float(snap["held_usd"]) <= float(snap["stop_usd"]) < float(snap["hard_cap_usd"])
    before = len(p.requests)
    with pytest.raises(BudgetError):
        chat(p.client(), cap=500, text_=uniq())
    assert len(p.requests) == before                                           # a refused request is never dispatched
    assert snap["integrity"]["consistent"]


def test_categories_are_independent_and_classes_are_separate(sf):
    dev = G.install(make_gov(sf, klass="development"))
    p = Provider(lambda r, n: httpx.Response(200, json=body_usage(30, 500)))
    while True:
        try:
            chat(p.client(), op="agent", cap=500, text_=uniq())
        except BudgetError as exc:
            assert exc.reason == "category_stop"
            break
    small = Provider()
    chat(small.client(), op="interview", cap=100, text_=uniq())                  # interview still has its own allocation
    assert float(dev.status()["categories"]["interview"]["held_usd"]) > 0
    G.uninstall()
    prod = G.install(make_gov(sf, klass="production"))                          # the production class has its own counters in the same ledger
    chat(small.client(), op="agent", cap=100, text_=uniq())
    assert float(prod.status()["categories"]["agent"]["held_usd"]) > 0
    assert float(prod.status()["held_usd"]) < float(dev.status()["held_usd"])


def test_a_category_not_configured_for_the_class_is_refused(sf):
    G.install(make_gov(sf, klass="production"))
    with pytest.raises(BudgetError) as e:
        chat(Provider().client(), op="evaluation", text_=uniq())               # production has no evaluation allocation
    assert e.value.reason == "category_not_configured"


def test_request_cap(sf):
    raw = raw_config()
    raw["classes"]["development"]["max_requests"] = 2
    G.install(make_gov(sf, raw=raw))
    p = Provider()
    for _ in range(2):
        chat(p.client(), text_=uniq())
    with pytest.raises(BudgetError) as e:
        chat(p.client(), text_=uniq())
    assert e.value.reason == "request_cap" and len(p.requests) == 2


def test_one_request_larger_than_the_category_stop_is_refused(sf):
    raw = raw_config()
    raw["classes"]["development"]["categories"]["agent"] = {"hard_cap_usd": "0.0005", "stop_usd": "0.0005"}
    G.install(make_gov(sf, raw=raw))
    with pytest.raises(BudgetError) as e:
        chat(Provider().client(), cap=500, text_=uniq())                         # worst case 0.001 USD
    assert e.value.reason == "request_exceeds_category"


# ====================================================================================================== concurrency and multi-process safety
def _hammer(governors, n_threads, per_thread, op="agent", cap=500):
    ok, refused, lock = [], [], threading.Lock()
    p = Provider(lambda r, n: httpx.Response(200, json=body_usage(30, 500)))

    def run(i):
        gov = governors[i % len(governors)]
        for _ in range(per_thread):
            try:
                with httpx.Client(transport=httpx.MockTransport(p)) as c:
                    request = c.build_request("POST", f"{URL}/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": uniq()}], "max_completion_tokens": cap},
                                              headers={"x-ask4mo-operation": op})
                    gov.send_sync(lambda client, req, **kw: httpx.Response(200, json=body_usage(30, 500), request=req), c, request, {})
                with lock:
                    ok.append(1)
            except BudgetError as exc:
                with lock:
                    refused.append(exc.reason)
    threads = [threading.Thread(target=run, args=(i,)) for i in range(n_threads)]
    [t.start() for t in threads]
    [t.join(60) for t in threads]
    return ok, refused


def test_concurrent_threads_can_never_jointly_exceed_the_stop_threshold(sf):
    raw = raw_config()
    raw["classes"]["development"]["categories"]["agent"] = {"hard_cap_usd": "0.02", "stop_usd": "0.0125"}      # each request reserves ~0.0013 USD -> room for 9
    gov = make_gov(sf, raw=raw)
    ok, refused = _hammer([gov], n_threads=12, per_thread=4)
    snap = gov.status()
    assert len(ok) + len(refused) == 48 and len(ok) > 0 and refused
    assert float(snap["categories"]["agent"]["held_usd"]) <= 0.0125
    assert snap["integrity"]["consistent"] and snap["requests"] == len(ok)


def test_two_independent_ledger_handles_standing_in_for_two_processes_share_one_budget(sf):
    raw = raw_config()
    raw["classes"]["development"]["categories"]["agent"] = {"hard_cap_usd": "0.02", "stop_usd": "0.0125"}
    a, b = make_gov(sf, raw=raw), make_gov(sf, raw=raw)                           # separate ledger objects, separate caches: only the database is shared
    assert a.ledger is not b.ledger
    ok, refused = _hammer([a, b], n_threads=8, per_thread=4)
    snap = a.status()
    assert float(snap["categories"]["agent"]["held_usd"]) <= 0.0125 and snap["integrity"]["consistent"]
    assert snap["requests"] == len(ok) and b.status()["held_usd"] == snap["held_usd"] and refused


# ====================================================================================================== kill switch
def test_database_kill_switch_stops_everything_and_resume_restores(live):
    p = Provider()
    chat(p.client(), text_=uniq())
    live.ledger.kill("operator")
    with pytest.raises(BudgetError) as e:
        chat(p.client(), text_=uniq())
    assert e.value.reason == "kill_switch" and len(p.requests) == 1
    with pytest.raises(BudgetError):
        p.client().get(f"{URL}/models")                                          # even free metadata honours the switch
    assert live.status()["state"] == "killed"
    live.ledger.resume()
    chat(p.client(), text_=uniq())
    assert len(p.requests) == 2


def test_environment_kill_switch(sf):
    gov = G.install(make_gov(sf, env={C.KILL_ENV: "1"}))
    p = Provider()
    with pytest.raises(BudgetError) as e:
        chat(p.client(), text_=uniq())
    assert e.value.reason == "kill_switch" and not p.requests and gov.killed()


def test_an_overrun_engages_the_kill_switch(live):
    p = Provider(lambda r, n: httpx.Response(200, json=body_usage(2000, 500, cost=0.5)))    # the provider reports far more than we reserved
    chat(p.client(), text_=uniq())
    assert live.ledger.killed() and live.status()["kill_reason"] == "overrun"
    with pytest.raises(BudgetError) as e:
        chat(p.client(), text_=uniq())
    assert e.value.reason == "kill_switch"


# ====================================================================================================== fail closed
def test_a_closed_governor_refuses_every_paid_call_and_metadata_with_a_fixed_reason():
    gov = G.install(BudgetGovernor.closed("config_unavailable"))
    p = Provider()
    for fn in (lambda: chat(p.client(), text_=uniq()), lambda: p.client().get(f"{URL}/models")):
        with pytest.raises(BudgetError) as e:
            fn()
        assert e.value.reason == "config_unavailable"
    assert not p.requests and gov.status() == {"state": "closed", "reason": "config_unavailable", "budget_class": "production"}


def test_enforce_mode_without_valid_config_installs_a_closed_governor_not_a_crash(sf):
    assert G.install_from_env(sf, environ={}) is None and G.active_governor() is None          # unset: provider behaviour unchanged
    gov = G.install_from_env(sf, environ={C.MODE_ENV: "enforce"})                                # enforce, no configuration at all
    assert gov is not None and not gov.is_open and gov.closed_reason == "config_unavailable"
    with pytest.raises(BudgetError):
        chat(Provider().client(), text_=uniq())


def test_enforce_mode_with_config_but_no_marker_is_closed(sf, tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps(raw_config()), encoding="utf-8")
    gov = G.install_from_env(sf, environ={C.MODE_ENV: "enforce", C.CONFIG_PATH_ENV: str(f)})
    assert not gov.is_open and gov.closed_reason == "marker_missing"


def test_enforce_mode_with_everything_valid_is_open(sf, tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps(raw_config()), encoding="utf-8")
    gov = G.install_from_env(sf, environ={C.MODE_ENV: "enforce", C.CONFIG_PATH_ENV: str(f), C.MARKER_ENV: MARKER, C.CLASS_ENV: "development"})
    assert gov.is_open
    p = Provider()
    chat(p.client(), text_=uniq())
    assert len(p.requests) == 1


def test_a_ledger_that_cannot_record_refuses_the_request(live, sf, monkeypatch):
    p = Provider()
    monkeypatch.setattr(live.ledger, "_sf", lambda: (_ for _ in ()).throw(__import__("sqlalchemy").exc.OperationalError("x", {}, Exception("db down"))))
    with pytest.raises(BudgetError) as e:
        chat(p.client(), text_=uniq())
    assert e.value.reason in ("ledger_error", "kill_switch") and not p.requests          # an unreadable switch counts as engaged; an unwritable ledger refuses


def test_a_failed_settlement_leaves_the_reservation_held(live, sf, monkeypatch):
    p = Provider()
    real = live.ledger.settle

    def broken(*a, **k):
        raise BudgetError("ledger_error", "down")
    monkeypatch.setattr(live.ledger, "settle", broken)
    with pytest.raises(BudgetError):
        chat(p.client(), text_=uniq())
    monkeypatch.setattr(live.ledger, "settle", real)
    with sf() as s:
        row = s.execute(select(AiBudgetEntry)).scalar_one()
    assert row.state == "reserved" and row.reserved_micro_usd > 0               # never released silently
    assert float(live.status()["held_usd"]) > 0


def test_settle_is_idempotent(live, sf):
    p = Provider()
    chat(p.client(), text_=uniq())
    with sf() as s:
        row = s.execute(select(AiBudgetEntry)).scalar_one()
    from src.llm.budget.ledger import Reservation
    live.ledger.settle(Reservation(row.id, "development", "agent", row.reserved_micro_usd), outcome="rejected")     # a second settlement of the same entry is a no-op
    assert live.status()["integrity"]["consistent"] and live.status()["calls_by_state"] == {"settled": 1}


def test_integrity_detects_counter_drift(live, sf):
    chat(Provider().client(), text_=uniq())
    with sf() as s:
        s.execute(text("UPDATE ai_budget_controls SET held_micro_usd = held_micro_usd + 7 WHERE scope_key = 'class:development'"))
        s.commit()
    assert not live.status()["integrity"]["consistent"]
    assert budget_status(sf, {C.CONFIG_PATH_ENV: "x"})["state"] == "unavailable"


def test_governor_does_not_install_on_top_of_the_demo_provider_control_or_twice(sf, tmp_path):
    from src.demo_live.guard import ProviderControl

    ctl = ProviderControl("offline").install()
    try:
        with pytest.raises(BudgetError) as e:
            G.install(make_gov(sf))
        assert e.value.reason == "guard_conflict"
    finally:
        ctl.uninstall()
    G.install(make_gov(sf))
    with pytest.raises(BudgetError) as e:
        G.install(make_gov(sf))
    assert e.value.reason == "guard_active"


def test_ledger_never_stores_prompt_text_keys_or_headers(live, sf, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-SECRET-KEY-VALUE")
    p = Provider()
    p.client().post(f"{URL}/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": SECRET_PROMPT}], "max_tokens": 50},
                    headers={"x-ask4mo-operation": "agent", "authorization": "Bearer sk-or-test-SECRET-KEY-VALUE"})
    with sf() as s:
        dump = json.dumps([dict(r._mapping) for r in s.execute(text("SELECT * FROM ai_budget_entries"))] + [dict(r._mapping) for r in s.execute(text("SELECT * FROM ai_budget_controls"))], default=str)
    assert SECRET_PROMPT not in dump and "SECRET-KEY" not in dump and "Bearer" not in dump
    assert SECRET_PROMPT not in json.dumps(live.status(), default=str)


# ====================================================================================================== async path
def test_async_requests_are_governed_too(live):
    async def go():
        p = Provider()
        async with p.aclient() as c:
            r = await c.post(f"{URL}/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": uniq()}], "max_tokens": 50}, headers={"x-ask4mo-operation": "agent"})
            assert r.status_code == 200 and len(p.requests) == 1
            with pytest.raises(BudgetError) as e:
                await c.post(f"{URL}/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": "x"}]}, headers={"x-ask4mo-operation": "agent"})
            assert e.value.reason == "output_cap_missing" and len(p.requests) == 1
    asyncio.run(go())
    assert live.status()["calls_by_state"] == {"settled": 1}


# ====================================================================================================== Admin status (state, counts, headroom only)
def test_status_states_and_contents(sf, tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps(raw_config()), encoding="utf-8")
    env = {C.CONFIG_PATH_ENV: str(f), C.CLASS_ENV: "development"}
    assert budget_status(sf, {})["state"] == "unavailable" and budget_status(sf, {})["reason"] == "config_unavailable"
    s = budget_status(sf, env)
    assert s["state"] == "not_approved" and s["ledger"]["requests"] == 0 and s["approval_marker_configured"] is True and s["approval_marker_presented"] is False
    assert budget_status(sf, {**env, C.MARKER_ENV: MARKER})["state"] == "closed"
    G.install(make_gov(sf))
    s = budget_status(sf, {**env, C.MARKER_ENV: MARKER})
    assert s["state"] == "open" and float(s["ledger"]["remaining_to_stop_usd"]) == 0.8 and s["ledger"]["integrity"]["consistent"]
    assert budget_status(sf, {**env, C.MARKER_ENV: MARKER, C.KILL_ENV: "1"})["state"] == "killed"
    dump = json.dumps(s)
    assert MARKER not in dump and "OPENROUTER" not in dump and "sk-" not in dump
    empty = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'e.db'}"))
    assert budget_status(empty, env)["state"] == "unavailable" and budget_status(empty, env)["reason"] == "ledger_unavailable"


def test_status_reports_stopped_when_headroom_is_gone(sf, tmp_path):
    raw = raw_config()
    raw["classes"]["development"]["max_requests"] = 1
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps(raw), encoding="utf-8")
    G.install(make_gov(sf, raw=raw))
    chat(Provider().client(), text_=uniq())
    assert budget_status(sf, {C.CONFIG_PATH_ENV: str(f), C.CLASS_ENV: "development", C.MARKER_ENV: MARKER})["state"] == "stopped"


def test_admin_budget_route_uses_the_existing_ai_read_permission_and_returns_no_secret(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient  # noqa: F401  (Env builds it)

    from src.application import admin_permissions as perm
    from tests.test_admin_foundation_w10_1 import Env

    f = tmp_path / "cfg.json"
    f.write_text(json.dumps(raw_config()), encoding="utf-8")
    monkeypatch.setenv(C.CONFIG_PATH_ENV, str(f))
    monkeypatch.setenv(C.MARKER_ENV, MARKER)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-SECRET-KEY-VALUE")
    env = Env()
    try:
        _, cand = env.user("user")
        _, adm = env.user("platform_admin")
        _, support = env.user("support_operator")
        url = "/api/v1/admin/ai/budget"
        assert env.c.get(url, cookies=cand).status_code == 403
        assert perm.AI_READ not in perm.ROLE_PRESETS["support_operator"] and env.c.get(url, cookies=support).status_code == 403
        r = env.c.get(url, cookies=adm)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["config_loaded"] is True and body["approval_marker_configured"] is True and body["ledger"] is not None or body["reason"] == "ledger_unavailable"
        assert MARKER not in r.text and "SECRET-KEY" not in r.text and "OPENROUTER_API_KEY" not in r.text
        assert env.c.post(url, cookies=adm, json={}).status_code in (404, 405)                 # read-only: no mutating route exists
    finally:
        env.close()


# ====================================================================================================== migration 0044
def test_migration_0044_chains_has_the_orm_shape_and_fails_closed_on_downgrade(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    from tests._alembic_head import assert_chain
    from tests.test_billing_f1_qualification import _alembic

    rev, prev = "0044_ai_budget_ledger", "0043_story_bank_completion"
    cfg, url = _alembic(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision(rev).down_revision == prev and assert_chain(require=(rev,)) == script.get_heads()[0]         # the head moves as later packages add revisions; 0044 only has to be in the chain
    command.upgrade(cfg, rev)
    eng = create_engine(url)
    insp = inspect(eng)
    for orm in (AiBudgetEntry.__table__, Base.metadata.tables["ai_budget_controls"]):
        cols = {c["name"]: c for c in insp.get_columns(orm.name)}
        assert set(cols) == {c.name for c in orm.columns}, orm.name
        for c in orm.columns:
            assert cols[c.name]["nullable"] == c.nullable, (orm.name, c.name)
    assert not {"prompt", "content", "response", "api_key", "user_id", "text"} & {c["name"] for c in insp.get_columns("ai_budget_entries")}
    idx = {i["name"] for i in insp.get_indexes("ai_budget_entries")}
    assert {"ix_aibe_class_state", "ix_aibe_fingerprint", "uq_aibe_inflight_fingerprint"} <= idx
    with eng.begin() as c:
        c.execute(text("INSERT INTO ai_budget_controls (scope_key, held_micro_usd, requests, killed, updated_at) VALUES ('global', 0, 0, 0, '2026-01-01')"))
    with pytest.raises(RuntimeError, match="Refusing to downgrade 0044_ai_budget_ledger"):
        command.downgrade(cfg, prev)
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM ai_budget_controls")).scalar() == 1                    # nothing was deleted
    with eng.begin() as c:
        c.execute(text("DELETE FROM ai_budget_controls"))
    command.downgrade(cfg, prev)
    assert "ai_budget_entries" not in inspect(create_engine(url)).get_table_names()
