"""P0 regression: Mo → Practice handoff must not mask a setup failure as an ERROR-state.

Reproduced live: creating an interview with industry "Non-Profit Organization" and
career level "executive" surfaced "Cannot add a question from state ERROR. Allowed only
from: INTERVIEW_IN_PROGRESS, STRATEGY_READY." — a secondary illegal-transition error that
masked the real provider failure.

Root cause: ``generate_strategy`` catches a provider ``ServiceError`` by moving the
session to ERROR without re-raising; ``_run_setup`` then ran ``generate_next_question``,
whose ``add_question`` rejected the ERROR state and raised the masking error.

Fix: ``_run_setup`` stops as soon as a step enters ERROR and surfaces the ORIGINAL safe
message (HTTP 503). The state machine is untouched, and because ``store.mutate`` does not
persist on exception the durable session stays resumable for an idempotent retry.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.main import create_app
from src.application.interview_service import InterviewApplicationService
from src.interview.session_repository import DurableInterviewSessionStore
from src.interview_service import ServiceError
from src.persistence import init_db, make_engine, make_session_factory
from tests import _interview_factories as f
from tests.test_api import _FakeClient, _FakeRepo


class _OkDomain:
    def generate_strategy(self, config, settings):
        return f.strategy(), f.usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        return f.question(current_question_number), f.usage()


class _StrategyFailsDomain(_OkDomain):
    def generate_strategy(self, config, settings):
        raise ServiceError("The interview service is temporarily unavailable.")


class _QuestionFailsDomain(_OkDomain):
    def generate_next_question(self, config, settings, *, current_question_number, history):
        raise ServiceError("Question generation is temporarily unavailable.")


class _Eval:
    def evaluate_answer(self, config, question, answer, settings):
        return f.evaluation(), f.usage()


class _Report:
    def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
        return f.report(), f.usage()


def _svc(domain):
    return InterviewApplicationService(config=None, services=(domain, _Eval(), _Report(), _FakeClient()))


def _client(store, domain):
    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = lambda: _svc(domain)
    app.dependency_overrides[deps.get_repository] = lambda: _FakeRepo()
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    return TestClient(app)


@pytest.fixture
def store(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path/'iv.db'}")
    init_db(engine, force=True)
    return DurableInterviewSessionStore(make_session_factory(engine))


ALICE = {"X-User-Subject": "alice"}
# The exact reproduced values (industry supplied as a gap-filler; role from context).
NONPROFIT = {
    "preparation_context": {"target_role": "Executive Director"},
    "industry_or_sector": "Non-Profit Organization",
    "career_level": "executive",
}


def test_nonprofit_executive_succeeds_with_working_provider(store):
    with _client(store, _OkDomain()) as c:
        r = c.post("/api/v1/interviews", json=NONPROFIT, headers=ALICE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"]
    assert body["current_question"] is not None
    assert body["state"] != "ERROR"


def test_strategy_failure_holds_setup_without_leaking_the_provider_error(store):
    with _client(store, _StrategyFailsDomain()) as c:
        r = c.post("/api/v1/interviews", json=NONPROFIT, headers=ALICE)
    assert r.status_code == 409, r.text
    err = r.json()["error"]
    assert err["code"] == "practice_setup_outcome_uncertain"
    assert "Please contact support" in err["message"]
    assert "temporarily unavailable" not in err["message"]
    assert "Cannot add a question" not in err["message"]


def test_question_failure_surfaces_safe_error(store):
    with _client(store, _QuestionFailsDomain()) as c:
        r = c.post("/api/v1/interviews", json=NONPROFIT, headers=ALICE)
    assert r.status_code == 409, r.text
    err = r.json()["error"]
    assert err["code"] == "practice_setup_outcome_uncertain"
    assert "Question generation is temporarily unavailable" not in err["message"]
    assert "Cannot add a question" not in err["message"]


def test_uncertain_setup_keeps_its_key_and_refuses_regeneration_after_recovery(store):
    # The sealed historical test retried a generic provider error. That error does
    # not prove non-dispatch, so recovery now requires reconciliation of this attempt.
    key = {"Idempotency-Key": "practice-retry-np1", **ALICE}
    with _client(store, _StrategyFailsDomain()) as c:
        r1 = c.post("/api/v1/interviews", json=NONPROFIT, headers=key)
    assert r1.status_code == 409, r1.text

    with _client(store, _OkDomain()) as c:
        r2 = c.post("/api/v1/interviews", json=NONPROFIT, headers=key)
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "practice_setup_outcome_uncertain"
    from sqlalchemy import select
    from src.persistence import InterviewSession

    with store._session_factory() as db:
        rows = db.scalars(select(InterviewSession)).all()
        assert len(rows) == 1 and rows[0].idempotency_key == key["Idempotency-Key"]
        assert rows[0].active_operation.endswith(":hold")
