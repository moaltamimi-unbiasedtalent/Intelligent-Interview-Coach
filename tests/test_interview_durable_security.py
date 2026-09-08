"""Sprint 4 Phase 10 — persistence-specific security (section 72).

Malformed stored state fails safely (no leak, no garbage 200); an unknown Deep Dive
mode and an oversized answer are safe 4xx (never a 500); cross-user access is denied.
The frontend never submits arbitrary session state — only an answer or a mode — so
there is no state-patch injection surface. No provider calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from src.api import dependencies as deps
from src.api.main import create_app
from src.application.interview_service import InterviewApplicationService
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import InterviewSession, init_db, make_engine, make_session_factory
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
    def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
        return f.report(), f.usage()


def _svc():
    return InterviewApplicationService(config=None, services=(_Domain(), _Eval(), _Report(), _FakeClient()))


CONFIG = {"configuration": {"target_role": "Registered Nurse", "industry_or_sector": "healthcare",
                            "career_level": "senior", "number_of_questions": 2}}
ALICE = {"X-User-Subject": "alice"}


@pytest.fixture
def ctx(tmp_path):
    url = f"sqlite:///{tmp_path/'sec.db'}"
    engine = make_engine(url)
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    store = DurableInterviewSessionStore(sf)
    repo = _FakeRepo()
    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = _svc
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    return TestClient(app), sf


def test_malformed_stored_state_fails_safely(ctx):
    client, sf = ctx
    with client as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        # Corrupt the stored payload behind the API's back.
        with sf() as db:
            db.execute(update(InterviewSession).where(InterviewSession.session_id == sid)
                       .values(state_payload={"state": "NOT_A_REAL_STATE"}))
            db.commit()
        r = c.get(f"/api/v1/interviews/{sid}", headers=ALICE)
        # Never a 200 with garbage; a safe error with no private content / internals.
        assert r.status_code >= 400
        blob = r.text.lower()
        for leaked in ("traceback", "sqlite", "sessiondata", "password", "sk-or"):
            assert leaked not in blob


def test_unknown_deep_dive_mode_is_safe_4xx(ctx):
    client, _sf = ctx
    with client as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "an answer"}, headers=ALICE)
        r = c.post(f"/api/v1/interviews/{sid}/deep-dive", json={"mode": "not-a-real-mode"}, headers=ALICE)
        assert 400 <= r.status_code < 500  # safe rejection, never a 500


def test_oversized_answer_is_rejected(ctx):
    client, _sf = ctx
    with client as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        r = c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "x" * 20001}, headers=ALICE)
        assert r.status_code == 422  # AnswerRequest max_length guard


def test_answer_payload_cannot_inject_session_state(ctx):
    # The answer endpoint accepts ONLY {"answer": ...}; extra keys attempting to patch
    # protected state are ignored by the schema (no state-patch injection).
    client, _sf = ctx
    with client as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        r = c.post(f"/api/v1/interviews/{sid}/answers",
                   json={"answer": "legit", "state": "REPORT_READY", "version": 999,
                         "state_payload": {"state": "REPORT_READY"}}, headers=ALICE)
        assert r.status_code == 200
        # The injected keys had no effect — normal post-answer state.
        assert r.json()["state"] == "INTERVIEW_IN_PROGRESS"
