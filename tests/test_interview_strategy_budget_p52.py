"""Interview strategy generation robustness (Phase 5.2, P0).

Golden Demo Live Rehearsal #2 failed at interview creation: strategy generation with a
gpt-5.x REASONING model truncated at the old 1024-token output budget (the reasoning
tokens are drawn from the same completion budget before any JSON is emitted), so the
response came back finish_reason=length and creation failed with a safe 503 — and the
retry re-ran the same doomed request.

These tests pin the fix and its guarantees WITHOUT any provider/paid call:

  * the default output budget now leaves bounded headroom for minimal reasoning + the
    largest structured contract (strategy / report), and stays within the hard limit;
  * a full-size strategy completes through the real generation pipeline and creates Q1;
  * an explicit provider length/max-token finish reason is surfaced safely as a 503 that
    names the truncation — never masked by a follow-on "cannot add a question" error;
  * creation stays idempotent (a repeat with the same key does not re-generate).

The provider is a deterministic stub; no network, no model call.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src import constants
from src.api import dependencies as deps
from src.api.main import create_app
from src.application.interview_service import InterviewApplicationService
from src.interview_service import InterviewService
from src.openrouter_client import ChatResult
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import init_db, make_engine, make_session_factory
from src.pricing_service import PricingService
from src.repository import InterviewRepository

MODEL = constants.DEFAULT_MODEL
ALICE = {"X-User-Subject": "alice"}
CONFIG = {"configuration": {
    "target_role": "Registered Nurse", "industry_or_sector": "healthcare",
    "career_level": "senior", "number_of_questions": 3}}


# --- deterministic provider stub --------------------------------------------

class _ProviderStub:
    """Returns queued (content, finish_reason) pairs; records every call."""

    def __init__(self, items, *, reported_cost=0.001):
        self.reported_cost = reported_cost
        self._items = list(items)
        self.calls = 0

    def create_chat_completion(self, **kwargs) -> ChatResult:
        self.calls += 1
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        content, finish = item
        return ChatResult(
            content=content, model=kwargs["model"],
            prompt_tokens=200, completion_tokens=300, total_tokens=500,
            reported_cost=self.reported_cost, duration_seconds=0.4,
            request_id=f"stub-{self.calls}", finish_reason=finish,
        )

    def close(self):  # pragma: no cover - injected client is not closed
        pass


class _EvalStub:
    def evaluate_answer(self, *a, **k):  # pragma: no cover - not hit on create
        raise AssertionError("evaluation not used during create")


class _ReportStub:
    def generate_report(self, *a, **k):  # pragma: no cover - not hit on create
        raise AssertionError("report not used during create")


def _pricing() -> PricingService:
    # Defensive (non-strict) path: omit the structured_outputs parameter. A generous
    # completion limit so the budget cap never lowers the request below the default.
    return PricingService(models_fetcher=lambda: [{
        "id": MODEL,
        "pricing": {"prompt": "0.0000006", "completion": "0.0000018"},
        "supported_parameters": ["temperature", "max_tokens", "response_format"],
        "top_provider": {"max_completion_tokens": 8192},
    }])


def _strategy_json(item: str = "A concrete, useful preparation item.") -> str:
    section = [item]
    return json.dumps({
        "role_summary": "Concise summary of the role and what success looks like.",
        "likely_interview_stages": section, "critical_competencies": section,
        "likely_question_themes": section, "probable_challenges": section,
        "evidence_to_prepare": section, "technical_or_functional_topics": section,
        "behavioural_topics": section, "questions_for_interviewer": section,
        "preparation_priorities": section,
    })


def _large_strategy_json() -> str:
    """A full-size strategy: every section richly populated (the shape that used to
    truncate at 1024 tokens now completes under the raised budget)."""
    items = [f"Detailed, specific preparation point number {i} with concrete guidance "
             f"the candidate can act on before the interview." for i in range(1, 7)]
    return json.dumps({
        "role_summary": "A thorough summary of the target role, the scope of ownership, "
                        "the stakeholders involved, and what strong performance in the "
                        "first six to twelve months would concretely look like.",
        "likely_interview_stages": items, "critical_competencies": items,
        "likely_question_themes": items, "probable_challenges": items,
        "evidence_to_prepare": items, "technical_or_functional_topics": items,
        "behavioural_topics": items, "questions_for_interviewer": items,
        "preparation_priorities": items,
    })


def _question_json(qid: int = 1) -> str:
    return json.dumps({
        "question_id": qid, "question": "Tell me about a challenge you handled.",
        "question_type": "behavioural", "competency": "resilience",
        "difficulty": "moderate", "interviewer_intent": "See how they respond.",
        "expected_answer_elements": ["situation", "action", "result"],
    })


def _client(store, provider, *, pricing=None):
    # The atomic-history fixture creates a minimal schema. Exercise the real
    # fail-closed admission and metering using their existing synthetic tables.
    from src.persistence import AIOperationEvent, PlatformPauseState
    for table in (PlatformPauseState.__table__, AIOperationEvent.__table__):
        table.create(store._session_factory.kw["bind"], checkfirst=True)
    svc = InterviewApplicationService(
        config=None, services=(InterviewService(provider, pricing or _pricing()),
                               _EvalStub(), _ReportStub(), provider))
    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = lambda: svc
    app.dependency_overrides[deps.get_repository] = lambda: store.repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    return TestClient(app)


@pytest.fixture()
def store(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path/'iv.db'}")
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    s = DurableInterviewSessionStore(sf)
    s.repo = InterviewRepository(sf)  # a real user-scoped repo over the same DB
    return s


# --- tests -------------------------------------------------------------------

def test_default_output_budget_covers_reasoning_and_strategy():
    # Guards against regressing to the 1024 default that truncated a reasoning-model
    # strategy. Bounded: comfortably below the hard limit, not an arbitrary huge value.
    assert constants.DEFAULT_MAX_OUTPUT_TOKENS >= 2048
    assert constants.DEFAULT_MAX_OUTPUT_TOKENS <= constants.MAX_OUTPUT_TOKENS_LIMIT
    assert constants.MIN_OUTPUT_TOKENS <= constants.DEFAULT_MAX_OUTPUT_TOKENS


def test_create_generates_strategy_and_first_question(store):
    provider = _ProviderStub([(_strategy_json(), "stop"), (_question_json(1), "stop")])
    with _client(store, provider) as c:
        r = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "AWAITING_ANSWER"
    assert body["current_question"]["question_id"] == 1
    assert provider.calls == 2  # strategy + first question


def test_large_strategy_completes_and_creates_q1(store):
    # A full-size strategy (the shape that previously truncated) completes end to end.
    provider = _ProviderStub([(_large_strategy_json(), "stop"), (_question_json(1), "stop")])
    with _client(store, provider) as c:
        r = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE)
    assert r.status_code == 200
    assert r.json()["current_question"] is not None


def test_strategy_truncation_returns_safe_503_without_masking(store):
    # Historical regression name retained. Post-dispatch failure now returns the
    # explicit durable hold, while retaining the original diagnostic and charge.
    from sqlalchemy import select
    from src.persistence import InterviewSession
    provider = _ProviderStub([('{"role_summary":"synthetic truncated', "length")])
    pricing = _pricing()
    headers = {**ALICE, "Idempotency-Key": "synthetic-truncation"}
    with _client(store, provider, pricing=pricing) as c:
        r = c.post("/api/v1/interviews", json=CONFIG, headers=headers)
        assert r.status_code == 409 and r.json()["error"]["code"] == "practice_setup_outcome_uncertain"
        assert "output-token limit" not in r.text and "state ERROR" not in r.text
        with store._session_factory() as db:
            row = db.scalar(select(InterviewSession))
            assert row.active_operation.endswith(":hold")
            assert "output-token limit" in row.state_payload["error"]
            assert "add a question" not in row.state_payload["error"]
            assert len(row.state_payload["usage_records"]) == 1
            assert row.state_payload["usage_records"][0]["reported_cost"] == 0.001
        again = c.post("/api/v1/interviews", json=CONFIG, headers=headers)
        assert again.status_code == 409 and provider.calls == 1
        assert len(pricing.records) == 1 and pricing.records[0].reported_cost == 0.001


def test_create_is_idempotent_after_success(store):
    provider = _ProviderStub([(_strategy_json(), "stop"), (_question_json(1), "stop")])
    headers = {**ALICE, "Idempotency-Key": "handoff:run-xyz"}
    with _client(store, provider) as c:
        first = c.post("/api/v1/interviews", json=CONFIG, headers=headers)
        second = c.post("/api/v1/interviews", json=CONFIG, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"]
    # The repeat returns the existing session WITHOUT re-generating (no duplicate).
    assert provider.calls == 2


# Failed-generation receipts: real generation pipeline, synthetic responses only.
from tests.test_history_atomic_deletion import f as _atomic_fixture  # noqa: E402

usage_world = _atomic_fixture


def _receipt_pricing(mode="reported", strict=False):
    if mode == "unavailable":
        return PricingService(models_fetcher=lambda: [])
    params = ["temperature", "max_tokens", "response_format"]
    if strict:
        params.append("structured_outputs")
    return PricingService(models_fetcher=lambda: [{
        "id": MODEL, "pricing": {"prompt": "0.0000006", "completion": "0.0000018"},
        "supported_parameters": params,
    }])


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("content", ['{"role_summary":"synthetic truncated', "valid"])
@pytest.mark.parametrize("mode", ["reported", "calculated", "unavailable"])
def test_explicit_length_never_repairs_even_parseable_json_and_receipt_is_independent(strict, content, mode):
    from src.interview_service import ModelResponseError
    from tests import _interview_factories as f
    response = _strategy_json() if content == "valid" else content
    provider = _ProviderStub([(response, "length")], reported_cost=0.001 if mode == "reported" else None)
    pricing = _receipt_pricing(mode, strict)
    domain = InterviewService(provider, pricing)
    with pytest.raises(ModelResponseError) as failure:
        domain.generate_strategy(f.config(), f.settings())
    receipt = failure.value.usage_receipt
    assert provider.calls == 1 and len(pricing.records) == 1
    assert receipt.model_dump() == pricing.records[0].model_dump()
    assert (receipt.prompt_tokens, receipt.completion_tokens, receipt.total_tokens) == (200, 300, 500)
    assert receipt.cost_source == mode
    assert receipt.reported_cost == (0.001 if mode == "reported" else None)
    if mode == "unavailable":
        assert receipt.calculated_cost == 0 and receipt.reported_cost is None  # unknown, never reported zero
    elif mode == "calculated":
        assert receipt.calculated_cost > 0
    receipt.reported_cost = 99
    assert failure.value.usage_receipt.reported_cost != 99 and pricing.records[0].reported_cost != 99
    assert "synthetic truncated" not in str(failure.value) and "synthetic truncated" not in repr(vars(failure.value))


@pytest.mark.parametrize("case", ["success", "repaired", "failed_repair", "strict_fallback", "transport", "repair_transport", "unsafe"])
def test_failure_path_matrix_preserves_only_observed_usage(case, monkeypatch):
    from src.interview_service import ModelResponseError
    from src.openrouter_client import ServerError
    from tests import _interview_factories as f
    error = ServerError("synthetic transport error", status_code=503, category="server")
    items = {
        "success": [(_strategy_json(), "stop")],
        "repaired": [("not json", "stop"), (_strategy_json(), "stop")],
        "failed_repair": [("not json", "stop"), ("still not json", "stop")],
        "strict_fallback": [("not json", "stop"), ("not json", "stop"), (_strategy_json(), "stop")],
        "transport": [error], "repair_transport": [("not json", "stop"), error],
        "unsafe": [("SYNTHETIC_PRIVATE_OUTPUT", "stop")],
    }[case]
    provider = _ProviderStub(items)
    pricing = _receipt_pricing(strict=case == "strict_fallback")
    domain = InterviewService(provider, pricing)
    if case == "unsafe":
        def refuse(_):
            raise ModelResponseError("The model response failed a safety check and was not used.")
        monkeypatch.setattr(domain, "_guard_output", refuse)
    if case in {"success", "repaired", "strict_fallback"}:
        _, receipt = domain.generate_strategy(f.config(), f.settings())
    else:
        with pytest.raises(ModelResponseError) as failure:
            domain.generate_strategy(f.config(), f.settings())
        receipt = failure.value.usage_receipt
        assert "SYNTHETIC_PRIVATE_OUTPUT" not in repr(vars(failure.value))
    calls = {"success": 1, "repaired": 2, "failed_repair": 2, "strict_fallback": 3,
             "transport": 1, "repair_transport": 2, "unsafe": 1}[case]
    observed = calls - (1 if case in {"transport", "repair_transport"} else 0)
    assert provider.calls == calls and len(pricing.records) == (1 if observed else 0)
    if observed:
        assert receipt.model_dump() == pricing.records[0].model_dump()
        assert receipt.total_tokens == 500 * observed and receipt.reported_cost == pytest.approx(0.001 * observed)
    else:
        assert receipt is None


@pytest.mark.parametrize("mode", ["reported", "calculated", "unavailable"])
def test_held_failure_receipt_survives_restart_and_concurrent_retries_without_double_counting(usage_world, mode):
    from concurrent.futures import ThreadPoolExecutor
    from src.persistence import InterviewSession
    f = usage_world
    f.store.repo = f.repo
    pricing = _receipt_pricing(mode)
    provider = _ProviderStub([("not complete", "length")], reported_cost=0.001 if mode == "reported" else None)
    key = {"Idempotency-Key": "synthetic-held-receipt"}
    with _client(f.store, provider, pricing=pricing) as c:
        c.app.dependency_overrides[deps.get_current_user_id] = lambda: f.owner
        response = c.post("/api/v1/interviews", json=CONFIG, headers=key)
        assert response.status_code == 409 and response.json()["error"]["code"] == "practice_setup_outcome_uncertain", response.json()
        sid = f.store.find_idempotent_session(f.owner, key["Idempotency-Key"])
        with f.sf() as db:
            row = db.get(InterviewSession, sid)
            payload = row.state_payload
            assert row.active_operation.endswith(":hold") and len(payload["usage_records"]) == 1
            assert payload["usage_records"][0] == pricing.records[0].model_dump(mode="json")
            expected_cost = pricing.records[0].reported_cost if pricing.records[0].reported_cost is not None else pricing.records[0].calculated_cost
            assert payload["cumulative_cost_usd"] == expected_cost
            before = (row.version, row.active_operation, row.state_payload)
        restarted = DurableInterviewSessionStore(f.sf)
        restarted.repo = f.repo
        c.app.dependency_overrides[deps.get_session_store] = lambda: restarted
        def retry(_):
            result = c.post("/api/v1/interviews", json=CONFIG, headers=key)
            assert result.status_code == 409 and result.json()["error"]["code"] == "practice_setup_outcome_uncertain"
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(retry, range(3)))
        assert provider.calls == 1 and len(pricing.records) == 1
        with f.sf() as db:
            row = db.get(InterviewSession, sid)
            assert (row.version, row.active_operation, row.state_payload) == before


@pytest.mark.parametrize("phase", ["success", "save_failure", "lost_ack", "question_failure"])
def test_success_and_save_ack_boundaries_account_each_observed_generation_once(usage_world, phase, monkeypatch):
    from src.openrouter_client import ServerError
    from src.persistence import InterviewSession
    f = usage_world
    f.store.repo = f.repo
    second = ServerError("synthetic question outage", status_code=503, category="server") if phase == "question_failure" else (_question_json(), "stop")
    provider = _ProviderStub([(_strategy_json(), "stop"), second])
    pricing = _pricing()
    original = f.store._save
    def save(*args, **kwargs):
        if phase == "lost_ack":
            original(*args, **kwargs)
        raise RuntimeError("SYNTHETIC_SAVE_ACK_FAILURE")
    if phase in {"save_failure", "lost_ack"}:
        monkeypatch.setattr(f.store, "_save", save)
    key = {"Idempotency-Key": "synthetic-save-receipt"}
    with _client(f.store, provider, pricing=pricing) as c:
        c.app.dependency_overrides[deps.get_current_user_id] = lambda: f.owner
        response = c.post("/api/v1/interviews", json=CONFIG, headers=key)
        assert response.status_code == (200 if phase == "success" else 409), response.json()
        sid = f.store.find_idempotent_session(f.owner, key["Idempotency-Key"])
        observed = 1 if phase == "question_failure" else 2
        with f.sf() as db:
            row = db.get(InterviewSession, sid)
            assert len(row.state_payload["usage_records"]) == len(pricing.records) == observed
            assert row.state_payload["cumulative_cost_usd"] == pytest.approx(0.001 * observed)
            if phase in {"save_failure", "question_failure"}:
                assert row.active_operation.endswith(":hold")
            else:
                assert row.active_operation is None
        monkeypatch.setattr(f.store, "_save", original)
        restarted = DurableInterviewSessionStore(f.sf)
        restarted.repo = f.repo
        c.app.dependency_overrides[deps.get_session_store] = lambda: restarted
        again = c.post("/api/v1/interviews", json=CONFIG, headers=key)
        assert again.status_code == (409 if phase in {"save_failure", "question_failure"} else 200)
        assert provider.calls == 2 and len(pricing.records) == observed
