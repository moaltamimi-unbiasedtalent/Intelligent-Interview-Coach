"""Sprint 4 Phase 1 — application boundary regression tests.

Verifies the Streamlit-free application layer (``src/application``): it imports
and runs without Streamlit, produces parity results using mocked provider/
retrieval dependencies, drives the interview session, persists/reads history, and
never imports Streamlit or the UI. No network / no paid provider calls.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from src.application import (
    CareerApplicationService,
    CareerChatRequest,
    InterviewApplicationService,
    evaluation_service,
    history_service,
    knowledge_service,
)
from src.application.errors import ValidationError
from src.copilot.models import ChatResponse
from src.copilot.service import OrchestrationResult, PipelineTrace
from src.models import (
    AnswerEvaluation,
    InterviewConfiguration,
    InterviewQuestion,
    ModelSettings,
    UsageRecord,
)
from src.session_manager import SessionManager, SessionState

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "src" / "application"


# --- shared fakes / builders -------------------------------------------------


def _usage() -> UsageRecord:
    return UsageRecord(
        model="openai/gpt-5-mini", prompt_tokens=1, completion_tokens=1, total_tokens=2,
        calculated_cost=0.0, cost_source="calculated", request_duration_seconds=0.01)


def _question(qid: int = 1) -> InterviewQuestion:
    return InterviewQuestion(
        question_id=qid, question="Tell me about a challenge.",
        question_type="behavioural", competency="resilience", difficulty="moderate",
        interviewer_intent="probe", expected_answer_elements=["situation", "result"])


def _evaluation(score: int = 72) -> AnswerEvaluation:
    return AnswerEvaluation(
        overall_score=score, relevance=7, structure=7, evidence=7, role_knowledge=7,
        problem_solving=7, communication=7, credibility=7, strengths=["clear"],
        improvement_areas=["metrics"], missing_evidence=["numbers"],
        stronger_answer_structure="STAR", improved_example_answer="Better.",
        follow_up_question="And then?")


def _config() -> InterviewConfiguration:
    return InterviewConfiguration(
        target_role="Registered Nurse", industry_or_sector="healthcare",
        career_level="senior", interview_types=["behavioural"],
        interviewer_persona="neutral", difficulty="moderate", response_detail="standard")


class _FakeInterviewService:
    def generate_strategy(self, config, settings):
        from src.models import InterviewStrategy
        section = ["x"]
        return InterviewStrategy(
            role_summary="s", likely_interview_stages=section, critical_competencies=section,
            likely_question_themes=section, probable_challenges=section,
            evidence_to_prepare=section, technical_or_functional_topics=section,
            behavioural_topics=section, questions_for_interviewer=section,
            preparation_priorities=section), _usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        return _question(current_question_number), _usage()


class _FakeEvaluationService:
    def evaluate_answer(self, config, question, answer, settings):
        return _evaluation(), _usage()


class _FakeClient:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _interview_app(client=None):
    services = (_FakeInterviewService(), _FakeEvaluationService(), object(), client or _FakeClient())
    return InterviewApplicationService(config=None, services=services)


# --- 1 & 13: import safety / no import side effects --------------------------


def test_application_imports_without_streamlit_runtime():
    # Fresh interpreter: importing the application layer must not import Streamlit
    # and must not call any provider/retrieval/evaluation on import.
    code = (
        "import sys; import src.application as a; "
        "assert 'streamlit' not in sys.modules, 'streamlit imported'; "
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


# --- 2 & 21: architecture — no forbidden imports in the application layer -----


def test_application_modules_do_not_import_streamlit_or_ui():
    forbidden = ("import streamlit", "from streamlit", "src.career.ui",
                 "src.interview.studio_app", "career.ragas_panel", "interview.prompt_lab")
    offenders: list[str] = []
    for path in APP_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, offenders


# --- 3: career chat parity (mocked provider) ---------------------------------


class _FakeCareerService:
    def __init__(self):
        self.calls = []

    def answer(self, query, **kwargs):
        self.calls.append((query, kwargs))
        response = ChatResponse(answer="A grounded answer.")
        return OrchestrationResult(response=response, trace=PipelineTrace())


def test_career_chat_parity_safe_response_shape():
    fake = _FakeCareerService()
    svc = CareerApplicationService(config=None, service=fake)
    result = svc.chat(CareerChatRequest(query="What skills matter?", job_description="JD"))
    # Equivalent safe structure to the UI orchestration.
    assert result.answer == "A grounded answer."
    assert isinstance(result.response, ChatResponse)
    # The safe (API-facing) response exposes only safe fields — never the trace or
    # the handoff-only preparation artifacts.
    safe = result.response.model_dump()
    for leaked in ("trace", "preparation_artifacts", "system_prompt", "api_key"):
        assert leaked not in safe
    # The request values reached the domain unchanged.
    assert fake.calls[0][1]["job_description"] == "JD"


# --- 4: career tool parity (mocked invoker) ----------------------------------


class _Exec:
    def __init__(self, ok):
        self.tool_name = "tool"
        self.status = "ok" if ok else "error"
        self.error = None if ok else "boom"


class _InvokeResult:
    def __init__(self, ok, value):
        self.ok = ok
        self.result = value
        self.execution = _Exec(ok)


class _FakeInvoker:
    def __init__(self, ok=True, value="RESULT"):
        self._ok, self._value = ok, value
        self.invocations = []

    def invoke(self, name, args):
        self.invocations.append((name, args))
        return _InvokeResult(self._ok, self._value)


def test_career_tools_callable_without_streamlit():
    invoker = _FakeInvoker(ok=True, value="ROLE_REQS")
    svc = CareerApplicationService(config=None, tool_invoker=invoker)
    out = svc.analyze_job_description("Paste a JD")
    assert out.ok and out.value == "ROLE_REQS"
    assert invoker.invocations[0][0] == "job_description_analyzer"
    assert invoker.invocations[0][1] == {"job_description": "Paste a JD"}


def test_career_tool_failure_is_safe():
    svc = CareerApplicationService(config=None, tool_invoker=_FakeInvoker(ok=False))
    out = svc.generate_questions("Nurse", ["triage"], ["behavioural"])
    assert out.ok is False
    assert out.value is None
    assert out.error == "boom"  # safe summary, not a raw stack trace


# --- 5: preparation handoff without UI ---------------------------------------


def test_preparation_handoff_end_to_end_without_ui():
    from src.copilot.tools.schemas import RoleRequirements
    from src.integration import handoff
    from src.integration.preparation_context import build_preparation_context

    context = build_preparation_context(
        role_requirements=RoleRequirements(role_title="Data Analyst",
                                           required_skills=["SQL"]),
        target_role="Data Analyst")
    store: dict = {}
    handoff.request_practice(store, context)
    # Interview application service reads the prefill with no Streamlit dependency.
    prefill = _interview_app().preparation_prefill(store)
    assert prefill["target_role"] == "Data Analyst"


# --- 6, 7: interview session + answer submission -----------------------------


def _ready_session() -> SessionManager:
    session = SessionManager(store={})
    session.start_new_interview(_config(), ModelSettings())
    from src.models import InterviewStrategy
    section = ["x"]
    session.save_strategy(InterviewStrategy(
        role_summary="s", likely_interview_stages=section, critical_competencies=section,
        likely_question_themes=section, probable_challenges=section,
        evidence_to_prepare=section, technical_or_functional_topics=section,
        behavioural_topics=section, questions_for_interviewer=section,
        preparation_priorities=section))
    return session


def test_start_interview_and_next_question_without_streamlit():
    session = _ready_session()
    _interview_app().generate_next_question(session, first=True)
    assert len(session.data.questions) == 1
    assert session.state is SessionState.AWAITING_ANSWER


def test_submit_answer_updates_domain_state():
    session = _ready_session()
    _interview_app().generate_next_question(session, first=True)
    _interview_app().submit_answer(session, "A thoughtful STAR answer with a result.")
    assert len(session.data.answers) == 1
    assert len(session.data.evaluations) == 1
    assert session.state is SessionState.INTERVIEW_IN_PROGRESS


def test_injected_services_client_not_closed_by_service():
    # A caller-owned client is not closed by the application service.
    session = _ready_session()
    client = _FakeClient()
    app = InterviewApplicationService(
        config=None,
        services=(_FakeInterviewService(), _FakeEvaluationService(), object(), client))
    app.generate_next_question(session, first=True)
    assert client.closed is False


# --- 8, 9, 10: history persistence, read, safe failure -----------------------


class _FakeRepo:
    def __init__(self):
        self.saved = []

    def save_interview(self, user_id, payload, source_session_id=None):
        self.saved.append((user_id, payload))
        return 123

    def list_interviews(self, user_id):
        return [{"id": 123, "user": user_id}]

    def get_interview(self, user_id, interview_id):
        # User-scoped: only returns the report if it belongs to this user.
        return {"id": interview_id, "user": user_id} if user_id == 7 else None


def test_report_persistence_and_read(monkeypatch):
    repo = _FakeRepo()
    monkeypatch.setattr(history_service, "resolve_user_id", lambda config, r: 7)
    session = SessionManager(store={})
    history_service.save_completed_interview(session, config=None, repo=repo)
    assert session.data.saved_report_id == 123
    assert history_service.list_interview_reports(repo, 7) == [{"id": 123, "user": 7}]
    assert history_service.get_interview_report(repo, 7, 123) == {"id": 123, "user": 7}
    # Another user cannot read it.
    assert history_service.get_interview_report(repo, 99, 123) is None


def test_save_failure_becomes_safe_flag(monkeypatch):
    class _Boom:
        def save_interview(self, user_id, payload, source_session_id=None):
            raise RuntimeError("connection refused at db://secret-host:5432 password=x")

    monkeypatch.setattr(history_service, "resolve_user_id", lambda config, r: 7)
    session = SessionManager(store={})
    history_service.save_completed_interview(session, config=None, repo=_Boom())  # no raise
    assert session.data.save_failed is True
    assert session.data.saved_report_id is None  # nothing leaked, nothing saved


# --- 11, 12: knowledge & evaluation status without Streamlit ------------------


def test_knowledge_snapshot_without_streamlit():
    # Reads the ingestion manifest (or {} when absent) — no Streamlit, no retrieval.
    snapshot = knowledge_service.get_ingestion_snapshot()
    assert isinstance(snapshot, dict)
    assert isinstance(knowledge_service.list_sources(), list)


def test_evaluation_status_without_streamlit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no evaluations/ragas/runs here
    assert evaluation_service.latest_evaluation_run() is None
    assert evaluation_service.list_evaluation_runs() == []
    status = evaluation_service.check_ragas_configuration()
    assert isinstance(status, dict) and "can_run" in status  # safe snapshot, no secret


def test_evaluation_reads_latest_usable_run(tmp_path, monkeypatch):
    import json
    runs = tmp_path / "evaluations" / "ragas" / "runs"
    (runs / "20260101_000000").mkdir(parents=True)
    (runs / "20260101_000000" / "results.json").write_text(
        json.dumps({"metrics": {"faithfulness": 0.8}, "run_config": {"timestamp": "t"}}))
    monkeypatch.chdir(tmp_path)
    latest = evaluation_service.latest_evaluation_run()
    assert latest is not None and latest["metrics"]["faithfulness"] == 0.8


# --- 14: security guard invoked on the application path -----------------------


def test_submit_answer_invokes_security_guard():
    session = _ready_session()
    _interview_app().generate_next_question(session, first=True)
    # An empty answer is rejected by the same security guard, surfaced as a safe
    # application ValidationError (never a raw exception, no state mutation).
    with pytest.raises(ValidationError):
        _interview_app().submit_answer(session, "   ")
    assert session.data.answers == []
