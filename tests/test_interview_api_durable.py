"""Sprint 4 Phase 10 — Interview API over the durable store (sections 16, 17, 67).

End-to-end HTTP tests with FAKE interview services (no provider calls) against an
isolated file-backed SQLite durable store: full lifecycle, resume after service/store
recreation, a process-style restart, duplicate-answer protection, user isolation,
durable idempotency across restart, stale-version conflict, active listing, delete.
"""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient

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


class _Eval:
    def evaluate_answer(self, config, question, answer, settings):
        return f.evaluation(), f.usage()


class _Report:
    def generate_report(self, config, questions, answers, evaluations, settings):
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
    "career_level": "senior", "number_of_questions": 2}}
ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path/'iv.db'}"


# --- lifecycle ---------------------------------------------------------------


def test_create_gives_first_question(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        r = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE)
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "AWAITING_ANSWER"
        assert body["current_question"]["question_id"] == 1
        assert body["questions_planned"] == 2


def test_submit_answer_returns_evaluation(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        r = c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "My answer."}, headers=ALICE)
        assert r.status_code == 200
        assert r.json()["last_evaluation"]["overall_score"] == 70
        assert r.json()["state"] == "INTERVIEW_IN_PROGRESS"


def test_duplicate_answer_is_rejected_without_second_evaluation(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        r1 = c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "one"}, headers=ALICE).json()
        assert r1["last_evaluation"]["overall_score"] == 70 and r1["state"] == "INTERVIEW_IN_PROGRESS"
        # A repeated submit is rejected by the state machine (the question is already
        # answered/evaluated) — a safe 4xx, never a second evaluation of the same answer.
        r2 = c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "again"}, headers=ALICE)
        assert r2.status_code in (409, 422)
        state = c.get(f"/api/v1/interviews/{sid}", headers=ALICE).json()
        # State/progress unchanged; no duplicate evaluation was recorded.
        assert state["state"] == "INTERVIEW_IN_PROGRESS" and state["question_number"] == 1


def test_full_flow_to_report(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a1"}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/next-question", headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a2"}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/next-question", headers=ALICE)  # → complete
        rep = c.post(f"/api/v1/interviews/{sid}/report", headers=ALICE)
        assert rep.status_code == 200 and rep.json()["report"]["overall_readiness_score"] == 68
        # Fetch is idempotent; repeated POST must not regenerate/duplicate history.
        assert c.get(f"/api/v1/interviews/{sid}/report", headers=ALICE).status_code == 200


def test_repeated_report_does_not_regenerate(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/complete", headers=ALICE)
        r1 = c.post(f"/api/v1/interviews/{sid}/report", headers=ALICE).json()
        r2 = c.post(f"/api/v1/interviews/{sid}/report", headers=ALICE).json()
        assert r1["saved_report_id"] == r2["saved_report_id"]
        assert len(repo.list_interviews(repo.get_or_create_user(subject="alice", provider="dev"))) == 1


# --- durability / restart ----------------------------------------------------


def test_get_after_store_recreation(db_url):
    repo = _FakeRepo()
    store_a = _store_over(db_url)
    with _client(store_a, repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "durable"}, headers=ALICE)
    # New store object over the SAME db (fresh engine/session_factory) — restart.
    store_b = DurableInterviewSessionStore(make_session_factory(make_engine(db_url)))
    with _client(store_b, repo) as c:
        state = c.get(f"/api/v1/interviews/{sid}", headers=ALICE).json()
        assert state["state"] == "INTERVIEW_IN_PROGRESS"
        # Continue on the recreated instance.
        r = c.post(f"/api/v1/interviews/{sid}/next-question", headers=ALICE)
        assert r.status_code == 200 and r.json()["current_question"]["question_id"] == 2


def test_idempotent_create_survives_restart(db_url):
    repo = _FakeRepo()
    hdr = {**ALICE, "Idempotency-Key": "agent-handoff:run-42"}
    store_a = _store_over(db_url)
    with _client(store_a, repo) as c:
        sid1 = c.post("/api/v1/interviews", json=CONFIG, headers=hdr).json()["session_id"]
    store_b = DurableInterviewSessionStore(make_session_factory(make_engine(db_url)))
    with _client(store_b, repo) as c:
        sid2 = c.post("/api/v1/interviews", json=CONFIG, headers=hdr).json()["session_id"]
    assert sid1 == sid2  # same session after restart, no regeneration


# --- isolation / conflict / discovery ---------------------------------------


def test_user_isolation_on_all_reads_and_writes(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        assert c.get(f"/api/v1/interviews/{sid}", headers=BOB).status_code == 422
        assert c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "x"}, headers=BOB).status_code == 422
        assert c.get(f"/api/v1/interviews/{sid}/report", headers=BOB).status_code == 422


def test_stale_version_conflict_returns_409(db_url, monkeypatch):
    # A concurrent stale write (another tab/worker) surfaces to the client as HTTP 409
    # so the frontend can reload rather than silently overwrite. The store-level OCC is
    # covered directly in test_durable_session_store; here we assert the API mapping.
    from src.interview import session_repository as sr

    repo = _FakeRepo()
    store = _store_over(db_url)
    with _client(store, repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]

        def _always_conflict(self, *a, **k):
            raise sr.SessionConflictError("changed elsewhere")

        monkeypatch.setattr(sr.DurableInterviewSessionStore, "_save", _always_conflict)
        r = c.post(f"/api/v1/interviews/{sid}/complete", headers=ALICE)
        assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_active_list_and_delete(db_url):
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        listing = c.get("/api/v1/interviews", headers=ALICE).json()
        assert any(s["session_id"] == sid for s in listing["sessions"])
        assert listing["sessions"][0]["target_role"] == "Registered Nurse"
        # Bob sees none of Alice's sessions.
        assert c.get("/api/v1/interviews", headers=BOB).json()["sessions"] == []
        # Delete removes it.
        assert c.delete(f"/api/v1/interviews/{sid}", headers=ALICE).status_code == 200
        assert c.get(f"/api/v1/interviews/{sid}", headers=ALICE).status_code == 422


def test_options_exposes_deep_dive_modes(db_url):
    from src import constants
    repo = _FakeRepo()
    with _client(_store_over(db_url), repo) as c:
        body = c.get("/api/v1/interviews/options", headers=ALICE).json()
    assert body["deep_dive_modes"] == list(constants.BRANCH_MODES)
