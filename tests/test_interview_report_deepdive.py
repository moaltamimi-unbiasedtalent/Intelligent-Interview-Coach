"""Sprint 4 Phase 10 correction — Deep Dive evidence reaches the final report.

InterviewApplicationService.generate_report must pass deterministic, bounded Deep
Dive summaries into ReportService.generate_report (which already accepts
``branch_summaries``). No Deep Dive → empty summaries. Deep Dive turns never count as
scheduled main questions, and no extra model call is introduced. No provider calls.
"""

from __future__ import annotations

from src.application.interview_service import (
    _MAX_BRANCH_SUMMARIES,
    InterviewApplicationService,
    _build_branch_summaries,
)
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import User, init_db, make_engine, make_session_factory
from src.session_manager import SessionManager, SessionState
from tests import _interview_factories as f


class _Domain:
    def generate_strategy(self, config, settings):
        return f.strategy(), f.usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        return f.question(current_question_number), f.usage()


class _Eval:
    def __init__(self):
        self.calls = 0

    def evaluate_answer(self, config, question, answer, settings):
        self.calls += 1
        return f.evaluation(80), f.usage()


class _SpyReport:
    def __init__(self):
        self.calls = 0
        self.last_branch_summaries = None

    def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
        self.calls += 1
        self.last_branch_summaries = list(branch_summaries)
        return f.report(), f.usage()


class _Client:
    def close(self):
        pass


def _svc(domain, eval_, report):
    return InterviewApplicationService(config=None, services=(domain, eval_, report, _Client()))


def _one_q_evaluated(store: dict | None = None, n: int = 1) -> SessionManager:
    sm = SessionManager(store if store is not None else {}, clock=lambda: 1000.0)
    sm.start_new_interview(f.config(n), f.settings())
    sm.save_strategy(f.strategy())
    sm.add_question(f.question(1))
    sm.add_candidate_answer("main answer")
    sm.add_evaluation(f.evaluation(70))
    return sm


def _do_deep_dive(sm: SessionManager, levels: int = 1) -> None:
    sm.start_branch("deepen_reasoning")
    for i in range(1, levels + 1):
        sm.add_branch_question(f.branch_question(qid=i, depth=i))
        sm.add_branch_answer(f"branch answer {i}")
        sm.add_branch_evaluation(f.evaluation(78))
    sm.return_to_main_interview()


# --- helper-level -----------------------------------------------------------


def test_no_deep_dive_yields_empty_branch_summaries():
    sm = _one_q_evaluated()
    assert _build_branch_summaries(sm.data) == []


def test_archived_deep_dive_produces_summaries_with_evidence():
    sm = _one_q_evaluated()
    _do_deep_dive(sm, levels=1)
    summaries = _build_branch_summaries(sm.data)
    assert summaries and "deepen reasoning, level 1" in summaries[0]
    assert "78/100" in summaries[0]


def test_multiple_levels_are_bounded():
    sm = _one_q_evaluated(n=1)
    # Two branches of 2 levels each = 4 summaries (under the ceiling), all present.
    _do_deep_dive(sm, levels=2)
    # Re-open another branch after returning (still on the same main question).
    sm.start_branch("challenge_assumptions")
    sm.add_branch_question(f.branch_question(qid=1, depth=1))
    sm.add_branch_answer("b")
    sm.add_branch_evaluation(f.evaluation(66))
    sm.return_to_main_interview()
    summaries = _build_branch_summaries(sm.data)
    assert 0 < len(summaries) <= _MAX_BRANCH_SUMMARIES
    assert any("challenge assumptions" in s for s in summaries)


# --- service-level: report actually receives the summaries -------------------


def test_generate_report_passes_branch_summaries_and_preserves_main_count():
    domain, eval_, report = _Domain(), _Eval(), _SpyReport()
    svc = _svc(domain, eval_, report)
    sm = _one_q_evaluated(n=1)
    _do_deep_dive(sm, levels=1)
    main_count_before = sm.data.current_question_number
    sm.advance_interview()  # 1 of 1 done → INTERVIEW_COMPLETE
    assert sm.state == SessionState.INTERVIEW_COMPLETE
    eval_calls_before = eval_.calls

    svc.generate_report(sm)

    assert report.calls == 1                       # exactly one report model call
    assert report.last_branch_summaries            # non-empty Deep Dive evidence
    assert any("deepen reasoning" in s for s in report.last_branch_summaries)
    # Deep Dive did not change the main question count, and produced NO extra report
    # model call (summaries are built deterministically, not by a model).
    assert sm.data.current_question_number == main_count_before == 1
    assert eval_.calls == eval_calls_before        # generate_report evaluated nothing


def test_report_without_deep_dive_gets_empty_summaries():
    domain, eval_, report = _Domain(), _Eval(), _SpyReport()
    svc = _svc(domain, eval_, report)
    sm = _one_q_evaluated(n=1)
    sm.advance_interview()  # → INTERVIEW_COMPLETE
    svc.generate_report(sm)
    assert report.calls == 1 and report.last_branch_summaries == []


def test_branch_summaries_preserved_across_restart(tmp_path):
    url = f"sqlite:///{tmp_path/'r.db'}"
    engine = make_engine(url)
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    with sf() as db:
        db.add(User(subject="alice", provider="test"))
        db.commit()
        uid = db.query(User).filter_by(subject="alice").first().id

    store_a = DurableInterviewSessionStore(sf)
    sid = store_a.create(uid)
    with store_a.mutate(sid, uid) as sm:
        sm.start_new_interview(f.config(1), f.settings())
        sm.save_strategy(f.strategy())
        sm.add_question(f.question(1))
        sm.add_candidate_answer("main answer")
        sm.add_evaluation(f.evaluation(70))
        _do_deep_dive(sm, levels=2)
        sm.advance_interview()  # → INTERVIEW_COMPLETE

    # New store/engine over the SAME db (restart), then generate the report.
    store_b = DurableInterviewSessionStore(make_session_factory(make_engine(url)))
    report = _SpyReport()
    svc = _svc(_Domain(), _Eval(), report)
    with store_b.mutate(sid, uid) as sm:
        svc.generate_report(sm)
    assert report.last_branch_summaries and len(report.last_branch_summaries) == 2
