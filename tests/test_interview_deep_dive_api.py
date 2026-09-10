"""Sprint 4 Phase 10 — Deep Dive (branch) HTTP surface (section 68).

Exercises the Deep Dive endpoints over the durable store with fake services: start
gating, branch question/answer/evaluation, main-progress isolation, can_go_deeper,
max-depth enforcement, go-deeper, return-to-main, restart mid-branch, archived-branch
persistence, and user isolation. No provider calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src import constants
from src.api import dependencies as deps
from src.api.main import create_app
from src.application.interview_service import InterviewApplicationService
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import init_db, make_engine, make_session_factory
from tests import _interview_factories as f
from tests.test_api import _FakeClient, _FakeRepo


class _Domain:
    def generate_strategy(self, config, settings):
        return f.strategy(), f.usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        return f.question(current_question_number), f.usage()

    def generate_branch_question(self, config, settings, *, parent_question, candidate_answer,
                                 evaluation, branch_mode, depth, branch_id,
                                 previous_branch_questions, previous_branch_answers):
        return f.branch_question(qid=depth, depth=depth, parent_id=parent_question.question_id), f.usage()


class _Eval:
    def evaluate_answer(self, config, question, answer, settings):
        return f.evaluation(75), f.usage()


class _Report:
    def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
        return f.report(), f.usage()


def _svc():
    return InterviewApplicationService(config=None, services=(_Domain(), _Eval(), _Report(), _FakeClient()))


def _store_over(url):
    engine = make_engine(url)
    init_db(engine, force=True)
    return DurableInterviewSessionStore(make_session_factory(engine))


def _client(store, repo):
    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = _svc
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    return TestClient(app)


CONFIG = {"configuration": {
    "target_role": "Registered Nurse", "industry_or_sector": "healthcare",
    "career_level": "senior", "number_of_questions": 3}}
ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}
MODE = "deepen_reasoning"


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path/'dd.db'}"


def _to_evaluated(c, headers=ALICE):
    """Create → answer Q1 so a Deep Dive may start (state INTERVIEW_IN_PROGRESS)."""
    sid = c.post("/api/v1/interviews", json=CONFIG, headers=headers).json()["session_id"]
    c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "main answer"}, headers=headers)
    return sid


def test_cannot_start_before_main_evaluation(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        # Still AWAITING_ANSWER — no evaluation yet.
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        assert r.status_code == 422


def test_start_generates_branch_question(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        assert r.status_code == 200
        dd = r.json()["deep_dive"]
        assert dd["active"] is True and dd["mode"] == MODE and dd["depth"] == 1
        assert dd["current_branch_question"]["depth"] == 1


def test_branch_answer_is_evaluated(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "branch answer"}, headers=ALICE)
        assert r.status_code == 200
        assert r.json()["last_evaluation"]["overall_score"] == 75
        assert r.json()["deep_dive"]["can_go_deeper"] is True  # 1 < MAX_BRANCH_DEPTH(2)


def test_main_progress_unchanged_during_deep_dive(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        before = c.get(f"/api/v1/interviews/{sid}", headers=ALICE).json()["question_number"]
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "b"}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/deep-dive/next", headers=ALICE)
        during = c.get(f"/api/v1/interviews/{sid}", headers=ALICE).json()["question_number"]
        assert before == during == 1


def test_go_deeper_then_max_depth_enforced(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)         # depth 1
        c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "b1"}, headers=ALICE)
        r2 = c.post(f"/api/v1/interviews/{sid}/deep-dive/next", headers=ALICE)                     # depth 2
        assert r2.json()["deep_dive"]["depth"] == constants.MAX_BRANCH_DEPTH
        c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "b2"}, headers=ALICE)
        # A third level exceeds MAX_BRANCH_DEPTH → rejected.
        r3 = c.post(f"/api/v1/interviews/{sid}/deep-dive/next", headers=ALICE)
        assert r3.status_code == 422


def test_return_to_main_surfaces_last_main_evaluation(db_url):
    # Phase 5.1 Defect C: the return response must carry last_evaluation exactly as GET
    # does. Without it the client has no evaluation to render on return, so the main
    # actions (Next question / End) only appear after a manual reload.
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "b1"}, headers=ALICE)
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive/return", headers=ALICE)
        assert r.status_code == 200
        body = r.json()
        assert body["deep_dive"] is None and body["state"] == "INTERVIEW_IN_PROGRESS"
        assert body["last_evaluation"] is not None
        # Identical to what GET reports on resume — no reload needed to see it.
        got = c.get(f"/api/v1/interviews/{sid}", headers=ALICE).json()
        assert body["last_evaluation"] == got["last_evaluation"]


def test_return_to_main_resumes_and_archives(db_url):
    repo = _FakeRepo()
    store = _store_over(db_url)
    with _client(store, repo) as c:
        sid = _to_evaluated(c)
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "b1"}, headers=ALICE)
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive/return", headers=ALICE)
        assert r.status_code == 200
        assert r.json()["deep_dive"] is None and r.json()["state"] == "INTERVIEW_IN_PROGRESS"
        # Main interview can still advance normally after the Deep Dive.
        adv = c.post(f"/api/v1/interviews/{sid}/next-question", headers=ALICE)
        assert adv.json()["current_question"]["question_id"] == 2
    # Archived branch persisted durably.
    uid = repo.get_or_create_user(subject="alice", provider="dev")
    reloaded = store.load_state(sid, uid)
    assert len(reloaded.data.branches) == 1
    assert reloaded.data.branches[0]["mode"] == MODE
    assert len(reloaded.data.branches[0]["questions"]) == 1


def test_restart_mid_deep_dive_restores(db_url):
    repo = _FakeRepo()
    store_a = _store_over(db_url)
    with _client(store_a, repo) as c:
        sid = _to_evaluated(c)
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
    store_b = DurableInterviewSessionStore(make_session_factory(make_engine(db_url)))
    with _client(store_b, repo) as c:
        state = c.get(f"/api/v1/interviews/{sid}", headers=ALICE).json()
        assert state["deep_dive"]["active"] is True and state["deep_dive"]["mode"] == MODE


def test_deep_dive_user_isolation(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=BOB)
        assert r.status_code == 422  # unknown/foreign — indistinguishable


def test_report_after_deep_dive_still_generates(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = _to_evaluated(c)
        c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": MODE}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/deep-dive/answers", json={"answer": "b1"}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/deep-dive/return", headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/complete", headers=ALICE)
        rep = c.post(f"/api/v1/interviews/{sid}/report", headers=ALICE)
        assert rep.status_code == 200 and rep.json()["report"]["overall_readiness_score"] == 68
