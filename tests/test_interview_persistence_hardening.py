"""Phase 1 regression tests: interview persistence integrity.

Now exercised at the Streamlit-free application boundary
(``src.application.history_service``): a second interview persists after a reset
(the saved-report marker is session-owned), completed Deep Dives (archived
branches) are included in the persistence payload, and a persistence failure is
surfaced safely (flagged, never raised, no raw DB detail).
"""

from __future__ import annotations

from src.application import history_service
from src.models import AnswerEvaluation
from src.session_manager import BranchQuestion, SessionData, SessionManager


class _FakeRepo:
    def __init__(self):
        self.saved = []
        self._next = 100

    def save_interview(self, user_id, payload):
        self._next += 1
        self.saved.append((user_id, payload))
        return self._next


class _BoomRepo:
    def save_interview(self, user_id, payload):
        raise RuntimeError("database connection refused at db://secret-host")


def _persist(session, repo, monkeypatch):
    """Save via the application boundary with a stubbed user id and repo."""
    monkeypatch.setattr(history_service, "resolve_user_id", lambda config, repo: 7)
    history_service.save_completed_interview(session, config=None, repo=repo)


# --- 1A: second interview saves after reset ---------------------------------


def test_second_interview_persists_after_reset(monkeypatch):
    repo = _FakeRepo()
    session = SessionManager(store={})

    _persist(session, repo, monkeypatch)
    first_id = session.data.saved_report_id
    assert first_id is not None
    _persist(session, repo, monkeypatch)  # dedup within same interview
    assert len(repo.saved) == 1  # not saved twice

    session.reset_interview()  # start interview 2
    assert session.data.saved_report_id is None  # marker cleared by reset

    _persist(session, repo, monkeypatch)
    assert len(repo.saved) == 2  # second interview persisted
    assert session.data.saved_report_id != first_id


# --- 1C: persistence failure surfaced safely --------------------------------


def test_persistence_failure_is_flagged_not_raised(monkeypatch):
    session = SessionManager(store={})

    _persist(session, _BoomRepo(), monkeypatch)  # must not raise
    assert session.data.save_failed is True
    assert session.data.saved_report_id is None


def test_retry_after_failure_can_succeed(monkeypatch):
    repo = _FakeRepo()
    session = SessionManager(store={})
    _persist(session, _BoomRepo(), monkeypatch)
    assert session.data.save_failed is True

    session.data.save_failed = False
    _persist(session, repo, monkeypatch)  # DB recovers
    assert session.data.saved_report_id is not None
    assert len(repo.saved) == 1


def test_anonymous_user_is_not_persisted(monkeypatch):
    repo = _FakeRepo()
    session = SessionManager(store={})
    monkeypatch.setattr(history_service, "resolve_user_id", lambda config, repo: None)
    history_service.save_completed_interview(session, config=None, repo=repo)
    assert session.data.saved_report_id is None
    assert len(repo.saved) == 0


# --- 1B: completed Deep Dives are in the payload ----------------------------


def _branch_q(text: str) -> BranchQuestion:
    return BranchQuestion(
        branch_id="branch-1-1", parent_question_id=1, question=text,
        branch_mode="deepen_reasoning", focus_area="metrics",
        interviewer_intent="probe", expected_answer_elements=["metric"],
        difficulty="moderate", depth=1)


def _evaluation(score: int) -> AnswerEvaluation:
    return AnswerEvaluation(
        overall_score=score, relevance=7, structure=7, evidence=7,
        role_knowledge=7, problem_solving=7, communication=7,
        credibility=7, strengths=["clear"], improvement_areas=["add metrics"],
        missing_evidence=["numbers"], stronger_answer_structure="STAR",
        improved_example_answer="A better answer.", follow_up_question="And then?")


def test_payload_includes_archived_deep_dive():
    data = SessionData()
    # An archived, completed Deep Dive (returned to main → moved to data.branches,
    # active lists cleared).
    data.branches = [{
        "branch_id": "branch-0-1", "parent_question_id": 1, "mode": "deepen_reasoning",
        "questions": [_branch_q("What metric improved?")],
        "answers": ["Latency dropped 30%."],
        "evaluations": [_evaluation(74)],
    }]
    assert data.branch_questions == []  # active branch already cleared

    payload = history_service.build_interview_payload(data, mode=None)
    deep = [q for q in payload["questions"] if q["is_deep_dive"]]
    assert len(deep) == 1
    assert deep[0]["canonical_question"] == "What metric improved?"
    assert deep[0]["answer"]["text"] == "Latency dropped 30%."
    assert deep[0]["parent_position"] == 1


def test_payload_includes_active_and_archived_deep_dives():
    data = SessionData()
    data.branches = [{
        "branch_id": "branch-0-1", "parent_question_id": 1, "mode": "deepen_reasoning",
        "questions": [_branch_q("Archived DD?")], "answers": ["a1"],
        "evaluations": [_evaluation(70)],
    }]
    # A still-active branch at completion.
    data.branch_parent_question_id = 1
    data.branch_questions = [_branch_q("Active DD?")]
    data.branch_answers = ["a2"]
    data.branch_evaluations = [_evaluation(80)]

    payload = history_service.build_interview_payload(data, mode=None)
    texts = [q["canonical_question"] for q in payload["questions"] if q["is_deep_dive"]]
    assert "Archived DD?" in texts and "Active DD?" in texts
    positions = [q["position"] for q in payload["questions"]]
    assert len(positions) == len(set(positions))  # unique positions, no collision


def test_payload_carries_practice_mode():
    data = SessionData()
    assert history_service.build_interview_payload(data, mode="Record")["mode"] == "Record"
