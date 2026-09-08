"""Pre-Phase-10 — GenerateInterviewQuestions multi-turn role reliability.

A live multi-turn demo produced `Tool failed — Preparing interview questions · 0ms`:
the model understood a role stated only in natural conversation and selected the
question tool, but structured AgentState had no role, so the tool failed its
prerequisite check. The tool now accepts a bounded ``target_role`` the model may
supply from explicit conversation, resolved with conservative precedence (a
confirmed/structured role always wins; a model-supplied role is a last-resort
fallback that is then persisted so later turns retain it).

Handler-level tests exercise role precedence directly; service-level tests exercise
the real multi-turn graph. No provider calls (fake model + fake career).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agent.errors import (
    TOOL_FAILURE_MISSING_PREREQUISITE,
    AgentToolError,
)
from src.agent.models import AgentRunRequest
from src.agent.tooling import ToolContext
from src.agent.tools import GenerateInterviewQuestions, _generate_interview_questions
from src.application.agent_service import AgentApplicationService
from src.copilot.tools.schemas import (
    InterviewQuestionSet,
    QuestionCategory,
    RoleRequirements,
)


class FakeCareer:
    """Records the role passed to generate_questions so tests can assert which role
    won the precedence, and counts calls (duplicate/extra-call guards)."""

    def __init__(self):
        self.generate_calls: list[str] = []

    def analyze_job_description(self, jd):
        return SimpleNamespace(ok=True, value=RoleRequirements(
            role_title="Senior Product Manager", required_skills=["Roadmapping"]))

    def generate_questions(self, role, requirements, focus):
        self.generate_calls.append(role)
        return SimpleNamespace(ok=True, value=InterviewQuestionSet(
            role=role, categories=[QuestionCategory(name="Behavioral", questions=["Q1", "Q2"])]))


# --- handler-level: role resolution precedence (§2/§3) -----------------------


def _run_handler(ctx: ToolContext, **args):
    career = FakeCareer()
    outcome = _generate_interview_questions(career)(GenerateInterviewQuestions(**args), ctx)
    return career, outcome


def test_structured_target_role_succeeds():
    career, outcome = _run_handler(ToolContext(target_role="Staff Engineer"))
    assert career.generate_calls == ["Staff Engineer"]
    assert outcome.state_patch.get("questions")
    # Structured role was already known — nothing to persist.
    assert "target_role" not in outcome.state_patch


def test_requirements_role_title_succeeds():
    ctx = ToolContext(requirements={"role_title": "Data Scientist", "required_skills": ["SQL"]})
    career, outcome = _run_handler(ctx)
    assert career.generate_calls == ["Data Scientist"]
    assert "target_role" not in outcome.state_patch


def test_confirmed_hitl_role_succeeds_and_wins():
    # Confirmed role is highest precedence.
    ctx = ToolContext(confirmed_target_role="Engineering Manager", target_role=None)
    career, outcome = _run_handler(ctx)
    assert career.generate_calls == ["Engineering Manager"]
    assert "target_role" not in outcome.state_patch


def test_tool_argument_role_used_when_no_structured_role():
    career, outcome = _run_handler(ToolContext(), target_role="Senior Product Manager")
    assert career.generate_calls == ["Senior Product Manager"]


def test_fallback_role_is_persisted_into_state_patch():
    # Supplied via the tool ONLY because structured state was absent → persist it.
    _, outcome = _run_handler(ToolContext(), target_role="Senior Product Manager")
    assert outcome.state_patch.get("target_role") == "Senior Product Manager"


def test_structured_role_wins_over_conflicting_tool_arg_no_overwrite():
    ctx = ToolContext(target_role="Principal PM")
    career, outcome = _run_handler(ctx, target_role="Junior PM")
    assert career.generate_calls == ["Principal PM"]           # structured wins
    assert "target_role" not in outcome.state_patch            # no silent overwrite


def test_confirmed_role_wins_over_conflicting_tool_arg():
    ctx = ToolContext(confirmed_target_role="Group PM")
    career, outcome = _run_handler(ctx, target_role="Associate PM")
    assert career.generate_calls == ["Group PM"]
    assert "target_role" not in outcome.state_patch


def test_no_role_anywhere_is_controlled_prerequisite_failure():
    with pytest.raises(AgentToolError) as ei:
        _run_handler(ToolContext())
    assert ei.value.category == TOOL_FAILURE_MISSING_PREREQUISITE


# --- service-level: real multi-turn graph ------------------------------------


class _Model:
    def bind_tools(self, s):
        return self


def _humans(messages):
    return [m for m in messages if getattr(m, "type", None) == "human"
            and not str(getattr(m, "content", "")).startswith("USER-APPROVED")]


def _tools_since_last_human(messages) -> int:
    count = 0
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            break
        if isinstance(m, ToolMessage):
            count += 1
    return count


class NaturalRoleModel(_Model):
    """Turn 1: role named in conversation, answered directly (no tool). A later turn
    that asks for questions: request GenerateInterviewQuestions with target_role
    parsed from the conversation, then answer. Counts model invocations."""

    def __init__(self, *, arg_role: str | None = "Senior Product Manager"):
        self.invocations = 0
        self._arg_role = arg_role

    def invoke(self, messages):
        self.invocations += 1
        last = _humans(messages)[-1] if _humans(messages) else None
        wants_qs = last is not None and "question" in str(last.content).lower()
        if wants_qs and _tools_since_last_human(messages) == 0:
            args = {"focus": ["behavioral"]}
            if self._arg_role is not None:
                args["target_role"] = self._arg_role
            return AIMessage(content="", tool_calls=[{
                "name": "GenerateInterviewQuestions", "args": args, "id": "q0"}])
        return AIMessage(content=f"Answer turn {len(_humans(messages))}.")


def _svc(model, career=None):
    return AgentApplicationService(model_factory=lambda: model, career_service=career or FakeCareer())


def test_multiturn_natural_language_role_questions_succeed():
    career = FakeCareer()
    svc = _svc(NaturalRoleModel(), career)
    r1 = svc.run(AgentRunRequest(
        goal="I'm preparing for a Senior Product Manager interview at a fintech next week.",
        user_id="1"))
    assert r1.status == "completed"
    # No structured role after a conversational turn 1.
    assert not svc._snapshot(r1.run_id).values.get("target_role")

    r2 = svc.continue_run(r1.run_id, "1",
        "My background: 6y PM, led fraud roadmap. Give me behavioral questions.")
    assert r2.status == "completed"
    assert "GenerateInterviewQuestions" in r2.tools_used
    assert career.generate_calls == ["Senior Product Manager"]


def test_successful_call_in_tools_used_and_state_role_persisted():
    career = FakeCareer()
    svc = _svc(NaturalRoleModel(), career)
    r1 = svc.run(AgentRunRequest(goal="Prep for a Senior Product Manager role.", user_id="1"))
    r2 = svc.continue_run(r1.run_id, "1", "Give me interview questions.")
    assert "GenerateInterviewQuestions" in r2.tools_used
    # §3: a fallback role supplied via the tool is persisted for later turns.
    assert svc._snapshot(r2.run_id).values.get("target_role") == "Senior Product Manager"


def test_failed_call_excluded_from_tools_used_with_category():
    # Model asks for questions but supplies NO role, and none is structured → the
    # tool fails as a controlled prerequisite failure (not a crash).
    career = FakeCareer()
    svc = _svc(NaturalRoleModel(arg_role=None), career)
    r1 = svc.run(AgentRunRequest(goal="Prep for an unnamed role.", user_id="1"))
    r2 = svc.continue_run(r1.run_id, "1", "Give me interview questions.")
    assert r2.status == "completed"                                   # agent recovers
    assert "GenerateInterviewQuestions" not in r2.tools_used
    failed = [t for t in r2.tool_calls
              if t.get("tool") == "GenerateInterviewQuestions" and t.get("status") == "error"]
    assert failed and failed[-1].get("category") == TOOL_FAILURE_MISSING_PREREQUISITE
    assert career.generate_calls == []                               # never reached the service


def test_no_duplicate_or_extra_model_call():
    career = FakeCareer()
    model = NaturalRoleModel()
    svc = _svc(model, career)
    r1 = svc.run(AgentRunRequest(goal="Prep for a Senior Product Manager role.", user_id="1"))
    inv_after_turn1 = model.invocations
    assert inv_after_turn1 == 1                                       # one turn, one answer
    r2 = svc.continue_run(r1.run_id, "1", "Give me interview questions.")
    # Turn 2 is exactly: request the tool, then answer — two model calls, no extra
    # role-extraction/model call introduced by the fix.
    assert model.invocations - inv_after_turn1 == 2
    # The question tool ran exactly once (no duplicate provider/tool call).
    assert career.generate_calls == ["Senior Product Manager"]
    assert r2.status == "completed"
