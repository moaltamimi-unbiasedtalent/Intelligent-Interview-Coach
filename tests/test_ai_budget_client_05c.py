"""05C: the Interview HTTPX client (``src/openrouter_client.py``) under the budget governor. Mocked transport only; no network."""

from __future__ import annotations

import socket

import httpx
import pytest
from pydantic import SecretStr

from src.config import AppConfig
from src.llm.budget import config as C
from src.llm.budget import governor as G
from src.llm.budget.config import parse_config
from src.openrouter_client import BudgetRefusedError, OpenRouterClient, RateLimitError, RequestTimeoutError
from src.persistence import Base, make_engine, make_session_factory
from tests.test_ai_budget_governor_05c import MARKER, raw_config


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", C.MODE_ENV, C.CLASS_ENV, C.MARKER_ENV, C.KILL_ENV, C.CONFIG_PATH_ENV, "API_ENV", "ASK4MO_PROVIDER_MODE"):
        monkeypatch.delenv(k, raising=False)

    def refuse(*a, **k):
        raise AssertionError("a real network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield
    G.uninstall()


@pytest.fixture()
def sf(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    Base.metadata.create_all(eng)
    yield make_session_factory(eng)
    eng.dispose()


def build(sf, handler):
    gov = G.install(G.BudgetGovernor.build(sf, budget_class="development", config=parse_config(raw_config()), default_category="interview", environ={C.MARKER_ENV: MARKER}))
    client = OpenRouterClient(AppConfig(api_key=SecretStr("test-key-not-real"), base_url="https://openrouter.ai/api/v1"),
                              http_client=httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda s: None)
    return gov, client


def call(client):
    return client.create_chat_completion(model="provider/model-a", messages=[{"role": "user", "content": "hello"}], max_tokens=100, temperature=0.2)


def test_timeout_is_not_retried_under_the_governor_and_surfaces_the_real_timeout_error(sf):
    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout("slow", request=req)
    gov, client = build(sf, handler)
    with pytest.raises(RequestTimeoutError):
        call(client)
    assert len(calls) == 1                                                        # the unknown outcome was NOT sent a second time
    assert gov.status()["calls_by_state"] == {"unknown": 1}


def test_budget_refusal_is_a_typed_safe_error_not_a_crash(sf):
    gov, client = build(sf, lambda r: httpx.Response(200, json={}))
    gov.ledger.kill("operator")
    with pytest.raises(BudgetRefusedError) as e:
        call(client)
    assert e.value.category == "budget_refused" and MARKER not in e.value.message and "kill" not in e.value.message.lower()


def test_429_is_retried_a_bounded_number_of_times_and_then_raised(sf):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(429, json={"error": {"message": "slow"}})
    gov, client = build(sf, handler)
    with pytest.raises(RateLimitError):
        call(client)
    assert len(calls) == 2                                                        # one attempt plus the one bounded retry, never more
