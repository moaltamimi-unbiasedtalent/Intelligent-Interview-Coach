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

    def __init__(self, items):
        self._items = list(items)
        self.calls = 0

    def create_chat_completion(self, **kwargs) -> ChatResult:
        self.calls += 1
        content, finish = self._items.pop(0)
        return ChatResult(
            content=content, model=kwargs["model"],
            prompt_tokens=200, completion_tokens=300, total_tokens=500,
            reported_cost=0.001, duration_seconds=0.4,
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


def _client(store, provider):
    svc = InterviewApplicationService(
        config=None, services=(InterviewService(provider, _pricing()),
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
    # Every call truncates (finish_reason=length): strategy generation fails cleanly as
    # a 503 that names the output-token limit, and is NOT masked by a follow-on
    # "cannot add a question from state ERROR".
    truncated = "{ \"role_summary\": \"cut off mid-object"
    provider = _ProviderStub([(truncated, "length"), (truncated, "length"),
                              (truncated, "length"), (truncated, "length")])
    with _client(store, provider) as c:
        r = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE)
    assert r.status_code == 503
    msg = r.json()["error"]["message"]
    assert "output-token limit" in msg
    assert "state ERROR" not in msg and "add a question" not in msg


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
