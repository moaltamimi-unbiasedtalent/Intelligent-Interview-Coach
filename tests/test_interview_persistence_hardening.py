"""Phase 1 regression tests: interview persistence integrity.

Now exercised at the Streamlit-free application boundary
(``src.application.history_service``): a second interview persists after a reset
(the saved-report marker is session-owned), completed Deep Dives (archived
branches) are included in the persistence payload, and a persistence failure is
surfaced safely (flagged, never raised, no raw DB detail).
"""

from __future__ import annotations

import pytest

from src.application import history_service
from src.models import AnswerEvaluation
from src.session_manager import BranchQuestion, SessionData, SessionManager
from tests import _interview_factories as f


class _FakeRepo:
    def __init__(self):
        self.saved = []
        self._next = 100

    def save_interview(self, user_id, payload, source_session_id=None, opportunity_id=None):
        self._next += 1
        self.saved.append((user_id, payload))
        return self._next


class _BoomRepo:
    def save_interview(self, user_id, payload, source_session_id=None, opportunity_id=None):
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


def _branch_q(text: str, parent_id: int = 1) -> BranchQuestion:
    return BranchQuestion(
        branch_id=f"branch-{parent_id}-1", parent_question_id=parent_id, question=text,
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
    data.questions = [f.question(1)]
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
    assert deep[0]["parent_position"] == 0
    assert payload["questions"][0]["canonical_question"] == data.questions[0].question
    assert payload["questions"][0]["is_deep_dive"] is False


def test_payload_includes_active_and_archived_deep_dives():
    data = SessionData()
    data.questions = [f.question(1), f.question(7)]
    data.branches = [{
        "branch_id": "branch-0-1", "parent_question_id": 1, "mode": "deepen_reasoning",
        "questions": [_branch_q("Archived DD?")], "answers": ["a1"],
        "evaluations": [_evaluation(70)],
    }]
    # A still-active branch at completion.
    data.branch_parent_question_id = 7
    data.branch_questions = [_branch_q("Active DD?", parent_id=7)]
    data.branch_answers = ["a2"]
    data.branch_evaluations = [_evaluation(80)]

    payload = history_service.build_interview_payload(data, mode=None)
    texts = [q["canonical_question"] for q in payload["questions"] if q["is_deep_dive"]]
    assert "Archived DD?" in texts and "Active DD?" in texts
    positions = [q["position"] for q in payload["questions"]]
    assert len(positions) == len(set(positions))  # unique positions, no collision
    parents = {q["canonical_question"]: q["parent_position"] for q in payload["questions"] if q["is_deep_dive"]}
    assert parents == {"Archived DD?": 0, "Active DD?": 1}


def _add_branch(data, placement, parent_id):
    """Use real branch models; legacy/corrupt metadata is only the stored linkage."""
    valid_parent = parent_id if type(parent_id) is int and parent_id >= 1 else 1
    question = _branch_q("Synthetic deep question?", parent_id=valid_parent)
    answer = "Synthetic branch answer"
    evaluation = _evaluation(79)
    if placement == "archived":
        data.branches = [{
            "branch_id": question.branch_id, "parent_question_id": parent_id,
            "mode": "deepen_reasoning", "questions": [question],
            "answers": [answer], "evaluations": [evaluation],
        }]
    else:
        data.branch_parent_question_id = parent_id
        data.branch_questions = [question]
        data.branch_answers = [answer]
        data.branch_evaluations = [evaluation]


@pytest.mark.parametrize("placement", ("active", "archived"))
@pytest.mark.parametrize("question_ids,parent_id,expected_position", (
    ((1,), 1, 0),
    ((1, 2, 3), 2, 1),
    ((11, 42, 103), 11, 0),
    ((11, 42, 103), 42, 1),
    ((11, 42, 103), 103, 2),
))
def test_deep_dive_parent_id_resolves_to_actual_main_question_position(placement, question_ids, parent_id, expected_position):
    data = SessionData(questions=[f.question(qid) for qid in question_ids])
    _add_branch(data, placement, parent_id)
    payload = history_service.build_interview_payload(data)
    main = [q for q in payload["questions"] if not q["is_deep_dive"]]
    deep = [q for q in payload["questions"] if q["is_deep_dive"]]
    assert len(main) == len(question_ids) and len(deep) == 1
    assert deep[0]["parent_position"] == expected_position
    assert main[expected_position]["canonical_question"] == f.question(parent_id).question
    assert deep[0]["position"] == len(question_ids)
    assert deep[0]["answer"] == {"text": "Synthetic branch answer", "evaluation": _evaluation(79).model_dump()}


@pytest.mark.parametrize("placement,omit_key", (("active", False), ("archived", False), ("archived", True)))
def test_missing_parent_metadata_retains_last_main_question_legacy_fallback(placement, omit_key):
    data = SessionData(questions=[f.question(11), f.question(42)])
    _add_branch(data, placement, None)
    if omit_key:
        del data.branches[0]["parent_question_id"]
    payload = history_service.build_interview_payload(data)
    deep = [q for q in payload["questions"] if q["is_deep_dive"]]
    assert deep[0]["parent_position"] == 1
    assert payload["questions"][1]["canonical_question"] == f.question(42).question


@pytest.mark.parametrize("placement", ("active", "archived"))
@pytest.mark.parametrize("parent_id", (999, 0, -1, "1", 1.0, True, False))
def test_invalid_parent_metadata_never_creates_a_false_main_question_association(placement, parent_id):
    data = SessionData(questions=[f.question(1), f.question(7)])
    _add_branch(data, placement, parent_id)
    payload = history_service.build_interview_payload(data)
    deep = [q for q in payload["questions"] if q["is_deep_dive"]]
    assert len(deep) == 1
    assert deep[0]["parent_position"] is None
    assert deep[0]["canonical_question"] == "Synthetic deep question?"
    assert deep[0]["answer"]["text"] == "Synthetic branch answer"


@pytest.mark.parametrize("placement", ("active", "archived"))
@pytest.mark.parametrize("parent_id", (None, 1))
def test_no_main_question_cannot_produce_a_parent_association(placement, parent_id):
    data = SessionData()
    _add_branch(data, placement, parent_id)
    payload = history_service.build_interview_payload(data)
    assert len(payload["questions"]) == 1
    assert payload["questions"][0]["is_deep_dive"] is True
    assert payload["questions"][0]["parent_position"] is None


def test_distinct_archived_and_active_branches_keep_their_own_parent_positions():
    data = SessionData(questions=[f.question(11), f.question(42), f.question(103)])
    _add_branch(data, "archived", 11)
    _add_branch(data, "active", 103)
    payload = history_service.build_interview_payload(data)
    deep = [q for q in payload["questions"] if q["is_deep_dive"]]
    assert [q["parent_position"] for q in deep] == [0, 2]
    assert [q["position"] for q in payload["questions"]] == list(range(5))
    assert len(deep) == 2


def test_payload_carries_practice_mode():
    data = SessionData()
    assert history_service.build_interview_payload(data, mode="Record")["mode"] == "Record"
