"""Sprint 4 Phase 2 — FastAPI contract, isolation and integration tests.

Uses FastAPI's TestClient with dependency overrides so no real provider, vector
store or database is built. Covers health/capabilities, the career + interview +
history + knowledge + evaluation surfaces, safe error translation, request ids,
CORS, user isolation, and route→application integration with mocked providers.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.main import create_app
from src.application.career_service import CareerApplicationService
from src.application.errors import ConfigurationError
from src.application.interview_service import InterviewApplicationService
from src.copilot.models import ChatResponse
from src.copilot.service import OrchestrationResult, PipelineTrace
from src.models import (
    AnswerEvaluation,
    FinalInterviewReport,
    InterviewQuestion,
    InterviewStrategy,
    UsageRecord,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# --- domain builders / fakes -------------------------------------------------


def _usage():
    return UsageRecord(model="openai/gpt-5-mini", prompt_tokens=1, completion_tokens=1,
                       total_tokens=2, calculated_cost=0.0, cost_source="calculated",
                       request_duration_seconds=0.01)


def _question(qid=1):
    return InterviewQuestion(
        question_id=qid, question=f"Question {qid}?", question_type="behavioural",
        competency="resilience", difficulty="moderate", interviewer_intent="probe",
        expected_answer_elements=["situation"])


def _strategy():
    s = ["x"]
    return InterviewStrategy(
        role_summary="s", likely_interview_stages=s, critical_competencies=s,
        likely_question_themes=s, probable_challenges=s, evidence_to_prepare=s,
        technical_or_functional_topics=s, behavioural_topics=s,
        questions_for_interviewer=s, preparation_priorities=s)


def _evaluation(score=72):
    return AnswerEvaluation(
        overall_score=score, relevance=7, structure=7, evidence=7, role_knowledge=7,
        problem_solving=7, communication=7, credibility=7, strengths=["clear"],
        improvement_areas=["metrics"], missing_evidence=["numbers"],
        stronger_answer_structure="STAR", improved_example_answer="Better.",
        follow_up_question="And then?")


def _report():
    s = ["x"]
    return FinalInterviewReport(
        overall_readiness_score=70, performance_summary="ok", strongest_competencies=s,
        development_priorities=s, recurring_answer_patterns=s, highest_risk_questions=s,
        evidence_gaps=s, recommended_practice_actions=s, final_interview_checklist=s)


class _FakeCareer:
    """Stub CareerIntelligenceService injected into CareerApplicationService."""

    def __init__(self, answer="A grounded answer."):
        self._answer = answer

    def answer(self, query, **kwargs):
        return OrchestrationResult(response=ChatResponse(answer=self._answer),
                                   trace=PipelineTrace())


class _FakeInvoker:
    def __init__(self, ok=True, value=None):
        self._ok, self._value = ok, value

    def invoke(self, name, args):
        class _Exec:
            tool_name = name
            status = "ok" if self._ok else "error"
            error = None if self._ok else "boom"

        class _R:
            ok = self._ok
            result = self._value
            execution = _Exec()
        return _R()


class _FakeInterviewDomain:
    def generate_strategy(self, config, settings):
        return _strategy(), _usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        return _question(current_question_number), _usage()


class _FakeEval:
    def evaluate_answer(self, config, question, answer, settings):
        return _evaluation(), _usage()


class _FakeReport:
    def generate_report(self, config, questions, answers, evaluations, settings):
        return _report(), _usage()


class _FakeClient:
    def close(self):
        pass


class _FakeRepo:
    """User-scoped fake repository (subject -> id; reports own a user_id)."""

    def __init__(self):
        self._users: dict[str, int] = {}
        self._interviews: dict[int, dict] = {}
        self._next_user = 1
        self._next_iv = 100

    def get_or_create_user(self, *, subject, provider, display_name=None, email=None):
        if subject not in self._users:
            self._users[subject] = self._next_user
            self._next_user += 1
        return self._users[subject]

    def save_interview(self, user_id, payload):
        self._next_iv += 1
        self._interviews[self._next_iv] = {"user_id": user_id, "payload": payload}
        return self._next_iv

    def list_interviews(self, user_id):
        return [{"id": i} for i, r in self._interviews.items() if r["user_id"] == user_id]

    def get_interview(self, user_id, interview_id):
        row = self._interviews.get(interview_id)
        return {"id": interview_id} if row and row["user_id"] == user_id else None


# --- client factory with overrides -------------------------------------------


def _make_client(*, career=None, interview_domain_fail=None, repo=None):
    app = create_app()
    fake_repo = repo or _FakeRepo()

    def _career():
        return CareerApplicationService(config=None, service=career or _FakeCareer(),
                                        tool_invoker=_FakeInvoker(ok=True))

    def _interview():
        services = (_FakeInterviewDomain(), _FakeEval(), _FakeReport(), _FakeClient())
        return InterviewApplicationService(config=None, services=services)

    app.dependency_overrides[deps.get_career_service] = _career
    app.dependency_overrides[deps.get_interview_service] = _interview
    app.dependency_overrides[deps.get_repository] = lambda: fake_repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    return TestClient(app)


# --- 1, 2: health + capabilities ---------------------------------------------


def test_health_ok():
    with _make_client() as c:
        r = c.get("/api/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok" and body["service"] == "intelligent-interview-coach"


def test_capabilities_safe_metadata():
    with _make_client() as c:
        body = c.get("/api/v1/capabilities").json()
        assert body["career_intelligence"] is True
        assert body["live_interview_enabled"] is False
        # Planned features are advertised as not-yet-available.
        assert body["agentic_rag"] is False and body["agent_memory"] is False


# --- 3, 4, 5, 6: career chat happy path + error translation ------------------


def test_career_chat_ok():
    with _make_client() as c:
        r = c.post("/api/v1/career/chat", json={"question": "What skills matter?"})
        assert r.status_code == 200
        assert r.json()["answer"] == "A grounded answer."


def test_career_chat_validation_failure_is_safe_4xx():
    with _make_client() as c:
        r = c.post("/api/v1/career/chat", json={"question": ""})  # min_length=1
        assert r.status_code == 422
        assert r.json()["error"]["code"] in ("invalid_request", "validation_error")


def test_career_configuration_error_maps_to_503():
    class _Boom:
        def answer(self, query, **kwargs):
            raise ConfigurationError("No model configured.")

    with _make_client(career=_Boom()) as c:
        r = c.post("/api/v1/career/chat", json={"question": "hi"})
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "not_configured"


def test_unknown_exception_is_safe_500():
    class _Boom:
        def answer(self, query, **kwargs):
            raise RuntimeError("secret db://host password=hunter2 traceback...")

    with _make_client(career=_Boom()) as c:
        r = c.post("/api/v1/career/chat", json={"question": "hi"})
        assert r.status_code in (500, 503)
        blob = r.text.lower()
        for leaked in ("traceback", "password", "hunter2", "db://"):
            assert leaked not in blob


# --- 7-10: career tools ------------------------------------------------------


def test_job_analysis_endpoint():
    from src.copilot.tools.schemas import RoleRequirements

    invoker_value = RoleRequirements(role_title="Data Analyst")

    def _career():
        return CareerApplicationService(
            config=None, tool_invoker=_FakeInvoker(ok=True, value=invoker_value))

    app = create_app()
    app.dependency_overrides[deps.get_career_service] = _career
    with TestClient(app) as c:
        r = c.post("/api/v1/career/job-analysis", json={"job_description": "JD text"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["result"]["role_title"] == "Data Analyst"


def test_gap_analysis_endpoint():
    with _make_client() as c:
        r = c.post("/api/v1/career/gap-analysis", json={
            "candidate_background": "CV", "role_requirements": {"role_title": "X"}})
        assert r.status_code == 200


def test_preparation_plan_endpoint():
    with _make_client() as c:
        r = c.post("/api/v1/career/preparation-plan", json={
            "priority_gaps": [], "days_until_interview": 14, "hours_per_week": 6})
        assert r.status_code == 200


def test_questions_endpoint():
    with _make_client() as c:
        r = c.post("/api/v1/career/questions", json={
            "role": "Nurse", "requirements": ["triage"], "focus": []})
        assert r.status_code == 200


# --- 11-14: interview lifecycle + handoff ------------------------------------


def _config_body():
    return {"configuration": {
        "target_role": "Registered Nurse", "industry_or_sector": "healthcare",
        "career_level": "senior", "number_of_questions": 2}}


def test_interview_create_and_first_question():
    with _make_client() as c:
        r = c.post("/api/v1/interviews", json=_config_body())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["state"] == "AWAITING_ANSWER"
        assert body["current_question"]["question"] == "Question 1?"
        assert body["session_id"]


def test_interview_answer_and_next_question():
    with _make_client() as c:
        sid = c.post("/api/v1/interviews", json=_config_body()).json()["session_id"]
        r = c.post(f"/api/v1/interviews/{sid}/answers",
                   json={"answer": "A thoughtful STAR answer."})
        assert r.status_code == 200
        assert r.json()["last_evaluation"]["overall_score"] == 72
        r2 = c.post(f"/api/v1/interviews/{sid}/next-question")
        assert r2.status_code == 200
        # Two planned questions: after Q1 a Q2 is generated.
        assert r2.json()["current_question"]["question"] == "Question 2?"


def test_interview_handoff_from_preparation_context():
    body = {
        "preparation_context": {
            "target_role": "Data Analyst", "industry": "tech", "seniority": "senior"},
        "number_of_questions": 1,
    }
    with _make_client() as c:
        r = c.post("/api/v1/interviews", json=body)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["current_question"] is not None
        # The resolved target role is returned so the frontend Practice page can
        # show the session's role (Phase 3C additive field).
        assert payload["target_role"] == "Data Analyst"


def test_interview_report_generation_and_fetch():
    with _make_client() as c:
        sid = c.post("/api/v1/interviews", json=_config_body()).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "answer one"})
        c.post(f"/api/v1/interviews/{sid}/next-question")
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "answer two"})
        c.post(f"/api/v1/interviews/{sid}/next-question")  # → complete
        r = c.post(f"/api/v1/interviews/{sid}/report")
        assert r.status_code == 200, r.text
        assert r.json()["report"]["overall_readiness_score"] == 70
        assert c.get(f"/api/v1/interviews/{sid}/report").status_code == 200


def test_unknown_interview_session_is_safe_error():
    with _make_client() as c:
        r = c.get("/api/v1/interviews/does-not-exist")
        assert r.status_code == 422
        assert "error" in r.json()


# --- 15, 16: history list/get + user isolation -------------------------------


def test_history_list_and_get_user_scoped():
    repo = _FakeRepo()
    # Seed a saved interview owned by alice.
    with _make_client(repo=repo) as c:
        alice = {"X-User-Subject": "alice"}
        bob = {"X-User-Subject": "bob"}
        # Drive a full interview as alice, then persist a report.
        sid = c.post("/api/v1/interviews", json=_config_body(), headers=alice).json()["session_id"]
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a1"}, headers=alice)
        c.post(f"/api/v1/interviews/{sid}/next-question", headers=alice)
        c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a2"}, headers=alice)
        c.post(f"/api/v1/interviews/{sid}/next-question", headers=alice)
        report = c.post(f"/api/v1/interviews/{sid}/report", headers=alice).json()
        saved_id = report["saved_report_id"]
        assert saved_id is not None

        # Alice sees it; Bob cannot fetch it.
        alice_list = c.get("/api/v1/history/interviews", headers=alice).json()["interviews"]
        assert any(row["id"] == saved_id for row in alice_list)
        assert c.get(f"/api/v1/history/interviews/{saved_id}", headers=alice).status_code == 200
        r = c.get(f"/api/v1/history/interviews/{saved_id}", headers=bob)
        assert r.status_code == 404
        assert c.get("/api/v1/history/interviews", headers=bob).json()["interviews"] == []


# --- 17, 18: knowledge + evaluation ------------------------------------------


def test_knowledge_snapshot_and_sources():
    with _make_client() as c:
        assert c.get("/api/v1/knowledge/snapshot").status_code == 200
        assert c.get("/api/v1/knowledge/sources").status_code == 200


def test_evaluation_latest_and_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no runs present
    with _make_client() as c:
        assert c.get("/api/v1/evaluation/latest").json()["available"] is False
        assert c.get("/api/v1/evaluation/runs").json()["runs"] == []
        cfg = c.get("/api/v1/evaluation/ragas/configuration").json()
        assert "can_run" in cfg


# --- 19: request id ----------------------------------------------------------


def test_request_id_header_present():
    with _make_client() as c:
        r = c.get("/api/v1/health")
        assert r.headers.get("X-Request-Id")


# --- 20, 21: CORS ------------------------------------------------------------


def test_cors_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://localhost:3000")
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_disallows_unknown_origin(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://localhost:3000")
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/v1/health", headers={"Origin": "http://evil.example"})
        assert r.headers.get("access-control-allow-origin") != "http://evil.example"


# --- 23, 24: import safety + OpenAPI -----------------------------------------


def test_api_import_has_no_side_effects():
    code = (
        "import sys; import src.api.main as m; "
        "assert 'streamlit' not in sys.modules, 'streamlit imported'; "
        "assert m.app is not None; print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_openapi_schema_generates():
    app = create_app()
    schema = app.openapi()
    assert schema["info"]["title"] == "Intelligent Interview Coach API"
    assert "/api/v1/career/chat" in schema["paths"]


# --- 29: contract — no sensitive fields leak in schemas ----------------------


def test_openapi_schemas_do_not_expose_secrets():
    app = create_app()
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    forbidden = {"api_key", "token", "system_prompt", "chain_of_thought",
                 "raw_response", "database_url", "embedding", "password"}
    for name, model in components.items():
        for field in (model.get("properties") or {}):
            assert field.lower() not in forbidden, f"{name}.{field} leaks"


# --- 31: session-store isolation + bounded eviction --------------------------


def test_session_store_is_user_scoped_and_bounded():
    from src.api.session_store import InMemorySessionStore, SessionNotFoundError

    store = InMemorySessionStore(max_sessions=2)
    sid_a = store.create(user_id=1)
    store.store_for(sid_a, 1)["x"] = 1  # owner can access
    with pytest.raises(SessionNotFoundError):
        store.store_for(sid_a, 2)  # another user cannot
    with pytest.raises(SessionNotFoundError):
        store.store_for("nonexistent", 1)
    # Bounded: creating past the cap evicts the oldest.
    store.create(user_id=1)
    store.create(user_id=1)
    assert len(store) == 2
    with pytest.raises(SessionNotFoundError):
        store.store_for(sid_a, 1)  # evicted
