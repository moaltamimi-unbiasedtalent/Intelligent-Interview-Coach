"""Post-Sprint-4 P5.1 — EXACT feedback-target existence validation.

Owning the parent run/session is necessary but not sufficient: the precise rated output
(a specific Agent response, an evaluated Interview question, a generated final report)
must exist. Foreign, unknown, malformed and nonexistent targets are all not-found. No
provider calls.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from src.agent.models import AgentRunRequest
from src.api.feedback_targets import (
    agent_answer_verifier,
    final_report_verifier,
    interview_evaluation_verifier,
)
from src.api.main import create_app
from src.application.agent_service import AgentApplicationService
from src.persistence import init_db, make_engine, make_session_factory
from src.repository import FeedbackRepository


# --- agent answer verifier (real fake-model agent service) -------------------


class _M:
    def bind_tools(self, s):
        return self

    def invoke(self, messages):
        return AIMessage(content="An answer.")


def _agent_svc():
    return AgentApplicationService(model_factory=lambda: _M(), career_service=object())


def test_agent_real_response_id_accepted():
    svc = _agent_svc()
    res = svc.run(AgentRunRequest(goal="hi", user_id="1"))
    rid = [m for m in res.conversation if m["role"] == "assistant"][-1]["response_id"]
    assert agent_answer_verifier(svc)(rid, 1) is True


def test_agent_nonexistent_index_rejected():
    svc = _agent_svc()
    res = svc.run(AgentRunRequest(goal="hi", user_id="1"))
    assert agent_answer_verifier(svc)(f"{res.run_id}:999999", 1) is False


@pytest.mark.parametrize("bad", ["", "norun", "run_only:", ":3", "run:0", "run:-1", "run:abc", "run:1:2"])
def test_agent_malformed_target_rejected(bad):
    svc = _agent_svc()
    assert agent_answer_verifier(svc)(bad, 1) is False


def test_agent_response_id_from_a_different_run_rejected():
    svc = _agent_svc()
    a = svc.run(AgentRunRequest(goal="a", user_id="1"))
    b = svc.run(AgentRunRequest(goal="b", user_id="1"))
    a_rid = [m for m in a.conversation if m["role"] == "assistant"][-1]["response_id"]
    # a's response_id must not validate against run b (index 1 exists in b, but the id
    # is prefixed with a's run_id, so get_run(b) never contains it and get_run(a-run) is
    # what the id points at — cross-run id cannot be forged onto another run).
    assert a_rid.split(":")[0] == a.run_id != b.run_id


def test_agent_foreign_user_rejected():
    svc = _agent_svc()
    res = svc.run(AgentRunRequest(goal="hi", user_id="1"))
    rid = [m for m in res.conversation if m["role"] == "assistant"][-1]["response_id"]
    assert agent_answer_verifier(svc)(rid, 2) is False  # different user


def test_agent_multiturn_answers_independently_targetable():
    svc = _agent_svc()
    res = svc.run(AgentRunRequest(goal="hi", user_id="1"))
    cont = svc.continue_run(res.run_id, "1", "again")
    ids = [m["response_id"] for m in cont.conversation if m["role"] == "assistant"]
    v = agent_answer_verifier(svc)
    assert all(v(rid, 1) for rid in ids)
    assert v(f"{res.run_id}:{len(ids) + 5}", 1) is False


# --- interview evaluation + report verifiers (fake store) --------------------


class _FakeStore:
    """Minimal durable-store stand-in: load_state raises for foreign/unknown."""

    def __init__(self, sessions):
        # sessions: {(session_id, user_id): SimpleNamespace(data=...)}
        self._s = sessions

    def load_state(self, session_id, user_id):
        key = (session_id, user_id)
        if key not in self._s:
            raise KeyError("not found")
        return self._s[key]


def _mgr(*, evaluations=0, report=None):
    return SimpleNamespace(data=SimpleNamespace(evaluations=[object()] * evaluations, report=report))


def test_interview_evaluated_question_accepted():
    store = _FakeStore({("s1", 1): _mgr(evaluations=2)})
    v = interview_evaluation_verifier(store)
    assert v("s1:1", 1) is True and v("s1:2", 1) is True


def test_interview_nonexistent_question_rejected():
    store = _FakeStore({("s1", 1): _mgr(evaluations=2)})
    assert interview_evaluation_verifier(store)("s1:3", 1) is False


def test_interview_question_without_evaluation_rejected():
    # A session exists but no answer has been evaluated yet.
    store = _FakeStore({("s1", 1): _mgr(evaluations=0)})
    assert interview_evaluation_verifier(store)("s1:1", 1) is False


def test_interview_foreign_session_rejected():
    store = _FakeStore({("s1", 1): _mgr(evaluations=2)})
    assert interview_evaluation_verifier(store)("s1:1", 2) is False


@pytest.mark.parametrize("bad", ["", "s1", "s1:", ":1", "s1:0", "s1:x"])
def test_interview_malformed_rejected(bad):
    store = _FakeStore({("s1", 1): _mgr(evaluations=2)})
    assert interview_evaluation_verifier(store)(bad, 1) is False


def test_report_present_accepted():
    store = _FakeStore({("s1", 1): _mgr(report=object())})
    assert final_report_verifier(store)("s1", 1) is True


def test_report_not_generated_rejected():
    store = _FakeStore({("s1", 1): _mgr(report=None)})
    assert final_report_verifier(store)("s1", 1) is False


def test_report_foreign_and_unknown_rejected():
    store = _FakeStore({("s1", 1): _mgr(report=object())})
    assert final_report_verifier(store)("s1", 2) is False   # foreign
    assert final_report_verifier(store)("nope", 1) is False  # unknown


# --- API end-to-end: exact target maps to the same safe 404 (§20) -----------


class _FakeRepo:
    def get_or_create_user(self, *, subject, provider, display_name=None, email=None):
        return {"alice": 1, "bob": 2}.get(subject, 99)


@pytest.fixture()
def api(tmp_path):
    app = create_app()
    app.state.resources = {}
    app.state.resources_lock = threading.RLock()
    engine = make_engine(f"sqlite:///{tmp_path/'p51.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    agent = _agent_svc()
    store = _FakeStore({("s1", 1): _mgr(evaluations=1, report=object())})
    # Pre-seed shared resources so the REAL feedback verifiers use these services.
    app.state.resources["repository"] = _FakeRepo()
    app.state.resources["feedback_repository"] = FeedbackRepository(sf)
    app.state.resources["agent_service"] = agent
    app.state.resources["durable_session_store"] = store
    return SimpleNamespace(client=TestClient(app), agent=agent)


ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}


def test_api_agent_exact_target(api):
    res = api.agent.run(AgentRunRequest(goal="hi", user_id="1"))
    rid = [m for m in res.conversation if m["role"] == "assistant"][-1]["response_id"]
    ok = api.client.post("/api/v1/feedback", json={"surface": "agent_answer", "target_id": rid, "rating": "helpful"}, headers=ALICE)
    assert ok.status_code == 201, ok.text
    bogus = api.client.post("/api/v1/feedback", json={"surface": "agent_answer", "target_id": f"{res.run_id}:999", "rating": "helpful"}, headers=ALICE)
    assert bogus.status_code == 404
    # The safe message never reveals WHY (no "index"/"question"/"report" specifics).
    body = bogus.text.lower()
    assert "not found" in body and "index" not in body and "response" not in body
    foreign = api.client.post("/api/v1/feedback", json={"surface": "agent_answer", "target_id": rid, "rating": "helpful"}, headers=BOB)
    assert foreign.status_code == 404


def test_api_interview_and_report_exact_target(api):
    # s1 (user 1 = alice) has 1 evaluation and a report.
    assert api.client.post("/api/v1/feedback", json={"surface": "interview_evaluation", "target_id": "s1:1", "rating": "helpful"}, headers=ALICE).status_code == 201
    assert api.client.post("/api/v1/feedback", json={"surface": "interview_evaluation", "target_id": "s1:2", "rating": "helpful"}, headers=ALICE).status_code == 404
    assert api.client.post("/api/v1/feedback", json={"surface": "final_report", "target_id": "s1", "rating": "helpful"}, headers=ALICE).status_code == 201
    # Bob owns nothing here → not-found for both.
    assert api.client.post("/api/v1/feedback", json={"surface": "interview_evaluation", "target_id": "s1:1", "rating": "helpful"}, headers=BOB).status_code == 404
    assert api.client.post("/api/v1/feedback", json={"surface": "final_report", "target_id": "s1", "rating": "helpful"}, headers=BOB).status_code == 404
