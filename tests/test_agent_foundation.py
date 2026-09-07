"""Sprint 4 Phase 4 — LangGraph agent foundation: lifecycle, safety, state.

No paid provider calls: a fake tool-calling model is injected. Covers the bounded
loop, the tool allowlist (unknown/invalid tools never execute), safe failure of
tool/model errors, safe events (no chain-of-thought), state transitions, the
registry, and user-isolation.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agent.errors import AgentToolError
from src.agent.policies import MAX_AGENT_STEPS
from src.agent.registry import ToolRegistry, default_registry
from src.agent.tools import ResolvePreparationGoal, resolve_preparation_goal
from src.application.agent_service import AgentApplicationService
from src.agent.models import AgentRunRequest


# --- fake models -------------------------------------------------------------


class _Model:
    """Base fake tool-calling model."""

    def bind_tools(self, schemas):
        return self


class AnswerOnce(_Model):
    def invoke(self, messages):
        return AIMessage(content="Here is your guidance.")


class ToolThenAnswer(_Model):
    """Requests the foundation tool, then answers once the result is present."""

    def invoke(self, messages):
        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content="Focus on executive communication.")
        return AIMessage(content="", tool_calls=[{"name": "ResolvePreparationGoal", "args": {"goal": "prep", "target_role": "PM"}, "id": "c1"}])


class AlwaysTool(_Model):
    def invoke(self, messages):
        return AIMessage(content="", tool_calls=[{"name": "ResolvePreparationGoal", "args": {"goal": "prep"}, "id": "c1"}])


class UnknownTool(_Model):
    def invoke(self, messages):
        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content="done")
        return AIMessage(content="", tool_calls=[{"name": "shell_command", "args": {"cmd": "rm -rf /"}, "id": "x1"}])


class BadArgs(_Model):
    def invoke(self, messages):
        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content="done")
        # 'goal' is required — omitting it is an invalid tool call.
        return AIMessage(content="", tool_calls=[{"name": "ResolvePreparationGoal", "args": {"target_role": "PM"}, "id": "b1"}])


class Boom(_Model):
    def invoke(self, messages):
        raise RuntimeError("provider exploded with secret-host detail")


def _svc(model) -> AgentApplicationService:
    return AgentApplicationService(model_factory=lambda: model)


def _run(model, **kw):
    return _svc(model).run(AgentRunRequest(goal="Help me prepare", **kw))


# --- §31 graph lifecycle -----------------------------------------------------


def test_simple_run_completes():
    res = _run(AnswerOnce())
    assert res.status == "completed"
    assert res.response == "Here is your guidance."
    assert res.step_count == 1


def test_allowed_tool_executes_and_returns_final():
    res = _run(ToolThenAnswer())
    assert res.status == "completed"
    assert res.response == "Focus on executive communication."
    assert res.tool_calls == [{"tool": "ResolvePreparationGoal", "status": "ok"}]


def test_unknown_tool_is_rejected_not_executed():
    res = _run(UnknownTool())
    assert {"tool": "shell_command", "status": "rejected"} in res.tool_calls
    assert any(e["event_type"] == "tool_rejected" for e in res.events)
    assert all(e["event_type"] != "tool_completed" for e in res.events)


def test_invalid_tool_args_fail_safely():
    res = _run(BadArgs())
    assert {"tool": "ResolvePreparationGoal", "status": "error"} in res.tool_calls
    assert any(e["event_type"] == "tool_failed" for e in res.events)
    assert res.status in ("completed", "failed")  # never raised


def test_step_limit_is_bounded():
    res = _run(AlwaysTool())
    assert res.status == "step_limit_reached"
    assert res.step_count == MAX_AGENT_STEPS
    assert any(e["event_type"] == "step_limit_reached" for e in res.events)


def test_model_failure_is_safe():
    res = _run(Boom())
    assert res.status == "failed"
    blob = (res.response + " ".join(str(e) for e in res.events)).lower()
    assert "secret-host" not in blob and "traceback" not in blob


def test_run_id_generated_and_events_recorded():
    res = _run(ToolThenAnswer())
    assert res.run_id and len(res.run_id) >= 16
    types = [e["event_type"] for e in res.events]
    assert "run_started" in types and "run_completed" in types


def test_events_contain_no_chain_of_thought():
    res = _run(ToolThenAnswer())
    forbidden = {"chain_of_thought", "reasoning", "system_prompt", "raw_response", "prompt"}
    for e in res.events:
        assert not (set(e.keys()) & forbidden), e
        # values must not carry reasoning-like leakage
        assert "chain-of-thought" not in str(e).lower()


# --- §31.12-14 import safety --------------------------------------------------


def test_agent_import_has_no_provider_or_streamlit_side_effects():
    code = (
        "import sys; import src.agent; import src.application.agent_service; "
        "assert 'streamlit' not in sys.modules, 'streamlit imported'; "
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


# --- §32 state ---------------------------------------------------------------


def test_state_tool_history_and_steps_accumulate():
    res = _run(ToolThenAnswer())
    assert res.step_count == 2  # tool step + final step
    assert len(res.tool_calls) == 1


# --- §22 user isolation ------------------------------------------------------


def test_run_owner_isolation():
    svc = _svc(AnswerOnce())
    res = svc.run(AgentRunRequest(goal="x", user_id="alice"))
    assert svc.owns(res.run_id, "alice") is True
    assert svc.owns(res.run_id, "bob") is False


# --- §33 registry ------------------------------------------------------------


def test_registry_lists_registered_tool():
    reg = default_registry()
    assert "ResolvePreparationGoal" in reg.names()
    assert reg.has("ResolvePreparationGoal")


def test_registry_rejects_unknown_tool():
    reg = default_registry()
    with pytest.raises(AgentToolError):
        reg.validate_and_run("shell_command", {"cmd": "x"})


def test_registry_rejects_invalid_args():
    reg = default_registry()
    with pytest.raises(AgentToolError):
        reg.validate_and_run("ResolvePreparationGoal", {"target_role": "PM"})  # missing goal


def test_registry_rejects_duplicate_registration():
    reg = ToolRegistry()
    reg.register(ResolvePreparationGoal, resolve_preparation_goal)
    with pytest.raises(ValueError):
        reg.register(ResolvePreparationGoal, resolve_preparation_goal)


def test_foundation_tool_is_deterministic_no_provider():
    out = resolve_preparation_goal(ResolvePreparationGoal(goal="prep", target_role="  Data Analyst  "))
    assert out["resolved_target_role"] == "Data Analyst"
