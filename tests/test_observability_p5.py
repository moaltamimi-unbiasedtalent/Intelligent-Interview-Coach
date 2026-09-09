"""Post-Sprint-4 P5 — provider-neutral observability.

Default NoOp; a fake sink captures the sanitised lifecycle. Asserts safe fields flow,
unknown usage stays None, NO private markers ever reach the sink, and a failing provider
never breaks an Agent run. No provider/network calls.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService
from src.application.feedback_service import FeedbackApplicationService
from src.observability.noop import NoOpObservabilitySink
from src.persistence import User, init_db, make_engine, make_session_factory
from src.repository import FeedbackRepository

SECRETS = ["SECRET-JD-TEXT", "SECRET-CANDIDATE-TEXT", "SECRET-MEMORY-TEXT",
           "SECRET-ANSWER-TEXT", "SECRET-SYSTEM-PROMPT", "SECRET-TOOL-ARG"]


class FakeSink:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def run_started(self, **kw):
        self.events.append(("run_started", kw))

    def tool_event(self, **kw):
        self.events.append(("tool_event", kw))

    def hitl_event(self, **kw):
        self.events.append(("hitl_event", kw))

    def run_completed(self, **kw):
        self.events.append(("run_completed", kw))

    def feedback_event(self, **kw):
        self.events.append(("feedback_event", kw))

    def blob(self) -> str:
        return repr(self.events)


class _Career:
    def analyze_job_description(self, jd):
        from types import SimpleNamespace

        from src.copilot.tools.schemas import RoleRequirements
        role = RoleRequirements(role_title="PM", seniority="mid", required_skills=["a"],
                                technologies=[], responsibilities=[], likely_interview_themes=[])
        return SimpleNamespace(ok=True, value=role)


def _model_with_tool(answer="SECRET-ANSWER-TEXT here."):
    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            if not any(isinstance(m, ToolMessage) for m in messages):
                return AIMessage(content="", tool_calls=[{"name": "AnalyzeJobDescription",
                                 "args": {"job_description": "SECRET-JD-TEXT ... Python."}, "id": "c0"}],
                                 usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})
            return AIMessage(content=answer)
    return M()


# --- NoOp -------------------------------------------------------------------


def test_noop_sink_is_inert():
    sink = NoOpObservabilitySink()
    assert sink.run_started(run_id="r", profile="fast") is None
    assert sink.tool_event(run_id="r", tool_name="t", status="ok") is None
    assert sink.hitl_event(run_id="r", hitl_type="x", status="requested") is None
    assert sink.run_completed(run_id="r", projection={}) is None
    assert sink.feedback_event(surface="agent_answer", rating="helpful") is None


# --- fake sink over a real run ----------------------------------------------


def test_run_emits_started_tool_and_completed_with_safe_projection():
    sink = FakeSink()
    svc = AgentApplicationService(model_factory=lambda: _model_with_tool(), career_service=_Career(),
                                  observability=sink)
    svc.run(AgentRunRequest(goal="analyse this JD", job_description="SECRET-JD-TEXT ... Python.",
                            candidate_background="SECRET-CANDIDATE-TEXT", user_id="1"))
    names = [n for n, _ in sink.events]
    assert names[0] == "run_started"
    assert "tool_event" in names and names[-1] == "run_completed"
    # The completion projection carries safe fields.
    proj = next(kw["projection"] for n, kw in sink.events if n == "run_completed")
    assert proj["model_profile"] == "balanced"
    assert proj["model_calls"] == 3 and proj["agent_model_calls"] == 2 and proj["tool_model_calls"] == 1
    assert "latency_ms" in proj and "cache_hits" in proj
    assert proj["journey_understand"] in ("complete", "in_progress")
    assert "handoff_prepared" in proj


def test_unknown_usage_stays_none_not_zero():
    # A fake model with NO usage_metadata → unknown tokens (never 0).
    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            return AIMessage(content="tips")
    sink = FakeSink()
    svc = AgentApplicationService(model_factory=lambda: M(), career_service=object(), observability=sink)
    svc.run(AgentRunRequest(goal="tips?", user_id="1"))
    proj = next(kw["projection"] for n, kw in sink.events if n == "run_completed")
    assert proj["total_tokens"] is None and proj["usage_complete"] is False


def test_no_private_markers_reach_the_sink():
    sink = FakeSink()
    # memory service returns a memory carrying a secret marker.
    class Mem:
        def load_for_agent(self, uid, role=None):
            from src.memory import MemoryItem
            return [MemoryItem(id=1, user_id=1, category="strength", summary="SECRET-MEMORY-TEXT",
                               target_role=None, source_run_id=None, created_at=None, updated_at=None)]
    svc = AgentApplicationService(model_factory=lambda: _model_with_tool(), career_service=_Career(),
                                  memory_service=Mem(), observability=sink)
    svc.run(AgentRunRequest(goal="analyse JD", job_description="SECRET-JD-TEXT . Python.",
                            candidate_background="SECRET-CANDIDATE-TEXT", user_id="1"))
    blob = sink.blob()
    for marker in SECRETS:
        assert marker not in blob, f"LEAK: {marker}"


def test_provider_failure_does_not_break_the_run():
    class Boom:
        def run_started(self, **kw):
            raise RuntimeError("telemetry down")

        def tool_event(self, **kw):
            raise RuntimeError("telemetry down")

        def hitl_event(self, **kw):
            raise RuntimeError("telemetry down")

        def run_completed(self, **kw):
            raise RuntimeError("telemetry down")

        def feedback_event(self, **kw):
            raise RuntimeError("telemetry down")

    svc = AgentApplicationService(model_factory=lambda: _model_with_tool(), career_service=_Career(),
                                  observability=Boom())
    res = svc.run(AgentRunRequest(goal="analyse JD", job_description="x. Python.", user_id="1"))
    assert res.status in ("completed", "step_limit_reached")  # run still succeeds


def test_feedback_event_emitted_safely():
    engine = make_engine("sqlite://")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        s.add(User(subject="u1", provider="t"))
        s.commit()
    sink = FakeSink()
    svc = FeedbackApplicationService(
        FeedbackRepository(sf),
        target_verifiers={"agent_answer": lambda tid, uid: True},
        observability=sink)
    svc.submit(1, surface="agent_answer", target_id="run1:1", rating="not_helpful",
               comment="SECRET-COMMENT that must not be traced")
    fb = [kw for n, kw in sink.events if n == "feedback_event"]
    assert fb == [{"surface": "agent_answer", "rating": "not_helpful"}]  # no comment traced
