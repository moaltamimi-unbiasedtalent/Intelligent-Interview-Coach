"""Sprint 4 Phase 10 correction — crash-safe completed-history idempotency.

A completed interview maps to at most one History row per (user, durable session):
- repository: idempotent save keyed on ``source_session_id`` (DB unique index).
- history_service: repairs ``saved_report_id`` when a prior save committed the row but
  the durable session-state save failed.
- API report route: report is persisted BEFORE history, so a crash before/around the
  history save neither regenerates the model nor duplicates the History row.
No provider calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.main import create_app
from src.application import history_service
from src.application.interview_service import InterviewApplicationService
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import Interview, User, init_db, make_engine, make_session_factory
from src.repository import InterviewRepository
from tests import _interview_factories as f
from tests.test_api import _FakeClient, _FakeRepo


# --- repository-level idempotency (sections 16.5-16.9, 16.13) ----------------


def _repo(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path/'hist.db'}")
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    with sf() as db:
        for sub in ("alice", "bob"):
            db.add(User(subject=sub, provider="test"))
        db.commit()
        alice = db.query(User).filter_by(subject="alice").first().id
        bob = db.query(User).filter_by(subject="bob").first().id
    return InterviewRepository(sf), sf, alice, bob


def _payload():
    return {"configuration": {}, "status": "completed", "questions": [], "report": {"report": {}}}


def test_first_save_with_source_session_creates_row(tmp_path):
    repo, _sf, alice, _bob = _repo(tmp_path)
    iid = repo.save_interview(alice, _payload(), source_session_id="sess-1")
    assert iid and len(repo.list_interviews(alice)) == 1


def test_same_source_session_retry_returns_same_row(tmp_path):
    repo, _sf, alice, _bob = _repo(tmp_path)
    a = repo.save_interview(alice, _payload(), source_session_id="sess-1")
    b = repo.save_interview(alice, _payload(), source_session_id="sess-1")
    assert a == b and len(repo.list_interviews(alice)) == 1


def test_different_source_session_creates_different_row(tmp_path):
    repo, _sf, alice, _bob = _repo(tmp_path)
    a = repo.save_interview(alice, _payload(), source_session_id="sess-1")
    b = repo.save_interview(alice, _payload(), source_session_id="sess-2")
    assert a != b and len(repo.list_interviews(alice)) == 2


def test_same_source_session_different_user_is_isolated(tmp_path):
    repo, _sf, alice, bob = _repo(tmp_path)
    a = repo.save_interview(alice, _payload(), source_session_id="sess-1")
    b = repo.save_interview(bob, _payload(), source_session_id="sess-1")
    assert a != b
    assert len(repo.list_interviews(alice)) == 1 and len(repo.list_interviews(bob)) == 1


def test_db_unique_index_enforces_one_row_per_source_session(tmp_path):
    # The idempotent SELECT is backed by a real DB unique index (a concurrent racer
    # that bypassed the SELECT would still be rejected). Prove the constraint exists.
    from sqlalchemy.exc import IntegrityError
    repo, sf, alice, _bob = _repo(tmp_path)
    repo.save_interview(alice, _payload(), source_session_id="sess-1")
    with pytest.raises(IntegrityError):
        with sf() as db:
            db.add(Interview(user_id=alice, source_session_id="sess-1", configuration={}, status="completed"))
            db.commit()


def test_legacy_save_without_source_session_always_inserts(tmp_path):
    repo, _sf, alice, _bob = _repo(tmp_path)
    a = repo.save_interview(alice, _payload())
    b = repo.save_interview(alice, _payload())
    assert a != b and len(repo.list_interviews(alice)) == 2  # unchanged legacy behaviour


# --- history_service repair (section 16.11) ----------------------------------


def _completed_session():
    from src.session_manager import SessionData, SessionState
    data = SessionData(state=SessionState.REPORT_READY, config=f.config(1), settings=f.settings(),
                       questions=[f.question(1)], answers=["a"], evaluations=[f.evaluation()],
                       report=f.report(), current_question_number=1)

    class _S:
        pass
    s = _S()
    s.data = data
    return s


def test_history_repair_after_durable_save_failure(tmp_path):
    # Scenario B: history row committed, but the durable saved_report_id save failed.
    repo, _sf, alice, _bob = _repo(tmp_path)
    session = _completed_session()

    history_service.save_completed_interview(session, config=None, repo=repo, user_id=alice,
                                             source_session_id="sess-9")
    first_id = session.data.saved_report_id
    assert first_id is not None

    # Simulate the durable session-state save having failed (saved_report_id lost).
    session.data.saved_report_id = None
    session.data.save_failed = True

    # Retry repairs from the existing History row — no duplicate.
    history_service.save_completed_interview(session, config=None, repo=repo, user_id=alice,
                                             source_session_id="sess-9")
    assert session.data.saved_report_id == first_id
    assert session.data.save_failed is False
    assert len(repo.list_interviews(alice)) == 1


# --- API crash scenario (sections 16.10, 16.12) ------------------------------


class _Domain:
    def generate_strategy(self, config, settings):
        return f.strategy(), f.usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        return f.question(current_question_number), f.usage()


class _Eval:
    def evaluate_answer(self, config, question, answer, settings):
        return f.evaluation(), f.usage()


class _SpyReport:
    def __init__(self):
        self.calls = 0

    def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
        self.calls += 1
        return f.report(), f.usage()


CONFIG = {"configuration": {"target_role": "Registered Nurse", "industry_or_sector": "healthcare",
                            "career_level": "senior", "number_of_questions": 1}}
ALICE = {"X-User-Subject": "alice"}


def test_report_persist_then_history_crash_retry_does_not_regenerate(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path/'api.db'}")
    init_db(engine, force=True)
    store = DurableInterviewSessionStore(make_session_factory(engine))
    repo = _FakeRepo()
    report = _SpyReport()

    def _svc():
        return InterviewApplicationService(config=None, services=(_Domain(), _Eval(), report, _FakeClient()))

    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = _svc
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store

    import src.api.routes.interview as route_mod

    with TestClient(app) as c:
        sid = c.post("/api/v1/interviews", json=CONFIG, headers=ALICE).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a"}, headers=ALICE)
        c.post(f"/api/v1/interviews/{sid}/complete", headers=ALICE)

        # Crash the history save AFTER the report is generated + persisted (step A).
        def _crash(*a, **k):
            raise RuntimeError("crash before history save")

        monkeypatch.setattr(route_mod.history_service, "save_completed_interview", _crash)
        with pytest.raises(RuntimeError):
            c.post(f"/api/v1/interviews/{sid}/report", headers=ALICE)
        assert report.calls == 1  # report was generated once and persisted

        # Retry with history save restored: report is NOT regenerated, history saved once.
        monkeypatch.undo()
        r = c.post(f"/api/v1/interviews/{sid}/report", headers=ALICE)
        assert r.status_code == 200
        assert report.calls == 1  # NOT regenerated after the partial failure

        uid = repo.get_or_create_user(subject="alice", provider="dev")
        assert len(repo.list_interviews(uid)) == 1  # exactly one completed-history row


# Markers a real DB exception could carry (SQL statement, bound params with candidate
# content, and the DB URL with credentials). NONE may reach the logs.
_LEAK_MARKERS = [
    "SECRET-ANSWER-TEXT",
    "SECRET-JD-TEXT",
    "SECRET-REPORT-TEXT",
    "postgresql://user:password@secret-host/db",
    "password",
    "INSERT INTO",
    "parameters=",
    "Traceback",
]


def _assert_no_leak(caplog):
    blob = caplog.text
    for marker in _LEAK_MARKERS:
        assert marker not in blob, f"leaked {marker!r} into logs"
    assert "Interview persistence failed" in blob  # the safe message is present


def test_persistence_failure_log_omits_exception_message(tmp_path, caplog):
    # The exception message deliberately embeds SQL, bound params (candidate content)
    # and DB credentials — none may be logged (no exc_info, no str(exc)).
    repo, _sf, alice, _bob = _repo(tmp_path)
    session = _completed_session()

    class _BoomRepo:
        def save_interview(self, *a, **k):
            raise RuntimeError(
                "INSERT INTO interviews (...) VALUES (...) "
                "parameters={'answer':'SECRET-ANSWER-TEXT','jd':'SECRET-JD-TEXT',"
                "'report':'SECRET-REPORT-TEXT'} "
                "postgresql://user:password@secret-host/db")

    with caplog.at_level("WARNING"):
        history_service.save_completed_interview(session, config=None, repo=_BoomRepo(),
                                                 user_id=alice, source_session_id="sess-x")
    assert session.data.save_failed is True
    _assert_no_leak(caplog)
    # A coarse, safe category (class name only) is acceptable metadata.
    assert any(getattr(r, "error_category", None) == "RuntimeError" for r in caplog.records)


def test_persistence_failure_sqlalchemy_like_error_is_safe(tmp_path, caplog):
    # Emulate a SQLAlchemy StatementError, which stringifies to its statement + params.
    from sqlalchemy.exc import StatementError
    repo, _sf, alice, _bob = _repo(tmp_path)
    session = _completed_session()

    class _BoomRepo:
        def save_interview(self, *a, **k):
            raise StatementError(
                message="(psycopg2.OperationalError) connection failed to "
                        "postgresql://user:password@secret-host/db",
                statement="INSERT INTO answers (text) VALUES (%(text)s)",
                params={"text": "SECRET-ANSWER-TEXT", "jd": "SECRET-JD-TEXT"},
                orig=Exception("SECRET-REPORT-TEXT"),
            )

    with caplog.at_level("WARNING"):
        history_service.save_completed_interview(session, config=None, repo=_BoomRepo(),
                                                 user_id=alice, source_session_id="sess-y")
    assert session.data.save_failed is True
    _assert_no_leak(caplog)
