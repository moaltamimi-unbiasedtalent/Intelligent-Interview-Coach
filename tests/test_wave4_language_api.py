"""P10B Wave 4 — interview API language acceptance + score independence (mocked generation).

Reuses the durable-store harness pattern (mocked domain/eval/report services, fake repo) so there
are NO live/paid calls. Proves the API accepts the 7 locales, rejects anything else at the schema
boundary, and returns identical scores regardless of the chosen conversation language.
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
    def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
        return f.report(), f.usage()


def _svc():
    return InterviewApplicationService(config=None, services=(_Domain(), _Eval(), _Report(), _FakeClient()))


def _client(store, repo):
    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = _svc
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    return TestClient(app)


ALICE = {"X-User-Subject": "alice"}


def _cfg(lang=None):
    cfg = {"target_role": "Registered Nurse", "industry_or_sector": "healthcare",
           "career_level": "senior", "number_of_questions": 2}
    if lang is not None:
        cfg["conversation_language"] = lang
    return {"configuration": cfg}


@pytest.fixture
def store(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path/'iv.db'}")
    init_db(engine, force=True)
    return DurableInterviewSessionStore(make_session_factory(engine))


@pytest.mark.parametrize("lang", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_all_seven_conversation_languages_accepted(store, lang):
    with _client(store, _FakeRepo()) as c:
        r = c.post("/api/v1/interviews", json=_cfg(lang), headers=ALICE)
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "AWAITING_ANSWER"


@pytest.mark.parametrize("bad", ["xx", "de-DE", "klingon", "en_US", "", "123"])
def test_invalid_conversation_language_rejected_422(store, bad):
    with _client(store, _FakeRepo()) as c:
        r = c.post("/api/v1/interviews", json=_cfg(bad), headers=ALICE)
        assert r.status_code == 422  # bounded Literal at the schema boundary


def test_no_language_still_works(store):
    with _client(store, _FakeRepo()) as c:
        r = c.post("/api/v1/interviews", json=_cfg(None), headers=ALICE)
        assert r.status_code == 200


def test_scores_are_independent_of_conversation_language(store):
    # Same mocked inputs → identical scores whether the interview language is English or German.
    scores = {}
    for lang in ("en", "de"):
        with _client(store, _FakeRepo()) as c:
            sid = c.post("/api/v1/interviews", json=_cfg(lang), headers=ALICE).json()["session_id"]
            body = c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "My structured answer."},
                          headers=ALICE).json()
            scores[lang] = body["last_evaluation"]["overall_score"]
    assert scores["en"] == scores["de"]  # language preference never changes the numeric score
