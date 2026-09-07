"""Graph nodes for the single, bounded, tool-using agent.

Each node returns only safe state updates. Tool execution goes through the
allowlist registry (unknown names are rejected, never executed). Events record
observable actions only — never chain-of-thought or raw provider output.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agent.errors import AgentConfigurationError, AgentToolError
from src.agent.events import AgentEvent, AgentEventType
from src.agent.policies import MAX_AGENT_STEPS, SYSTEM_PROMPT
from src.agent.registry import ToolRegistry
from src.agent.tooling import ToolContext
from src.agent.state import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_STEP_LIMIT,
    AgentState,
)

ModelFactory = Callable[[], Any]

_SAFE_MODEL_ERROR = "The assistant is temporarily unavailable. Please try again."
_SAFE_CONFIG_ERROR = "The assistant isn't configured in this environment."
_SAFE_STEP_LIMIT = "I've reached the limit of steps for this request. Here's what I have so far."


def _append(state: AgentState, key: str, value: Any) -> list:
    items = list(state.get(key, []) or [])
    items.append(value)
    return items


def make_initialise_node() -> Callable[[AgentState], dict]:
    def initialise(state: AgentState) -> dict:
        events = _append(state, "events", AgentEvent(AgentEventType.RUN_STARTED, step=0, status="running").to_dict())
        return {
            "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=state["goal"])],
            "status": STATUS_RUNNING,
            "step_count": 0,
            "tool_history": list(state.get("tool_history", []) or []),
            "events": events,
            "completed": False,
            "last_error": None,
        }

    return initialise


def make_agent_node(model_factory: ModelFactory, registry: ToolRegistry) -> Callable[[AgentState], dict]:
    def agent(state: AgentState) -> dict:
        step = int(state.get("step_count", 0)) + 1
        events = list(state.get("events", []) or [])
        if step == 1:
            events.append(AgentEvent(AgentEventType.REQUEST_UNDERSTOOD, step=step, status="ok").to_dict())
        try:
            model = model_factory()
            bound = model.bind_tools(registry.bind_schemas())
            ai = bound.invoke(state["messages"])
        except AgentConfigurationError:
            events.append(AgentEvent(AgentEventType.RUN_FAILED, step=step, status="not_configured", message=_SAFE_CONFIG_ERROR).to_dict())
            return {"messages": [AIMessage(content="")], "step_count": step, "status": STATUS_FAILED, "last_error": "not_configured", "events": events, "completed": True}
        except Exception:  # noqa: BLE001 - never leak a raw provider error
            events.append(AgentEvent(AgentEventType.RUN_FAILED, step=step, status="error", message=_SAFE_MODEL_ERROR).to_dict())
            return {"messages": [AIMessage(content="")], "step_count": step, "status": STATUS_FAILED, "last_error": "model_unavailable", "events": events, "completed": True}
        return {"messages": [ai], "step_count": step, "events": events}

    return agent


def _tool_context(state: AgentState) -> ToolContext:
    return ToolContext(
        target_role=state.get("target_role"),
        job_description=state.get("job_description"),
        candidate_background=state.get("candidate_background"),
        requirements=state.get("requirements"),
        gaps=state.get("gaps"),
    )


def make_tools_node(registry: ToolRegistry) -> Callable[[AgentState], dict]:
    def tools(state: AgentState) -> dict:
        last = state["messages"][-1]
        events = list(state.get("events", []) or [])
        history = list(state.get("tool_history", []) or [])
        out_messages: list[ToolMessage] = []
        step = int(state.get("step_count", 0))
        ctx = _tool_context(state)
        state_updates: dict[str, Any] = {}

        for call in getattr(last, "tool_calls", []) or []:
            name = call.get("name", "")
            call_id = call.get("id", "")
            args = call.get("args", {}) or {}
            events.append(AgentEvent(AgentEventType.TOOL_REQUESTED, step=step, tool_name=name).to_dict())

            if not registry.has(name):
                events.append(AgentEvent(AgentEventType.TOOL_REJECTED, step=step, tool_name=name, status="rejected", message="Tool not available.").to_dict())
                history.append({"tool": name, "status": "rejected"})
                out_messages.append(ToolMessage(content=json.dumps({"error": "This tool is not available."}), tool_call_id=call_id))
                continue

            events.append(AgentEvent(AgentEventType.TOOL_STARTED, step=step, tool_name=name).to_dict())
            t0 = time.perf_counter()
            try:
                # Later tool calls in the same step see earlier patches this step.
                outcome = registry.validate_and_run(name, args, _merge_ctx(ctx, state_updates))
                dur = int((time.perf_counter() - t0) * 1000)
                state_updates.update(outcome.state_patch or {})
                events.append(AgentEvent(
                    AgentEventType.TOOL_COMPLETED, step=step, tool_name=name, duration_ms=dur,
                    status="ok", message=outcome.summary, source_count=outcome.source_count,
                ).to_dict())
                history.append({"tool": name, "status": "ok"})
                out_messages.append(ToolMessage(content=json.dumps(outcome.result), tool_call_id=call_id))
            except AgentToolError as exc:
                dur = int((time.perf_counter() - t0) * 1000)
                events.append(AgentEvent(AgentEventType.TOOL_FAILED, step=step, tool_name=name, duration_ms=dur, status="error", message="The tool could not run with those inputs.").to_dict())
                history.append({"tool": name, "status": "error"})
                # The safe message (never a raw cause) goes back to the model as data.
                out_messages.append(ToolMessage(content=json.dumps({"error": str(exc)}), tool_call_id=call_id))

        return {"messages": out_messages, "events": events, "tool_history": history, **state_updates}

    return tools


def _merge_ctx(ctx: ToolContext, updates: dict[str, Any]) -> ToolContext:
    """A ToolContext reflecting patches applied earlier in this same tools step."""
    if not updates:
        return ctx
    return ToolContext(
        target_role=updates.get("target_role", ctx.target_role),
        job_description=updates.get("job_description", ctx.job_description),
        candidate_background=updates.get("candidate_background", ctx.candidate_background),
        requirements=updates.get("requirements", ctx.requirements),
        gaps=updates.get("gaps", ctx.gaps),
    )


def make_finalize_node() -> Callable[[AgentState], dict]:
    def finalize(state: AgentState) -> dict:
        events = list(state.get("events", []) or [])
        step = int(state.get("step_count", 0))
        last = state["messages"][-1]

        if state.get("status") == STATUS_FAILED:
            msg = _SAFE_CONFIG_ERROR if state.get("last_error") == "not_configured" else _SAFE_MODEL_ERROR
            # A RUN_FAILED event was already recorded by the agent node.
            return {"messages": [AIMessage(content=msg)], "completed": True}

        pending = bool(getattr(last, "tool_calls", []) or [])
        if pending and step >= MAX_AGENT_STEPS:
            events.append(AgentEvent(AgentEventType.STEP_LIMIT_REACHED, step=step, status="step_limit").to_dict())
            return {"messages": [AIMessage(content=_SAFE_STEP_LIMIT)], "status": STATUS_STEP_LIMIT, "events": events, "completed": True}

        events.append(AgentEvent(AgentEventType.RUN_COMPLETED, step=step, status="completed").to_dict())
        return {"status": STATUS_COMPLETED, "events": events, "completed": True}

    return finalize


def route_after_agent(state: AgentState) -> str:
    """Bounded routing: run a requested tool only within the step budget."""
    if state.get("status") == STATUS_FAILED:
        return "finalize"
    last = state["messages"][-1]
    pending = bool(getattr(last, "tool_calls", []) or [])
    if pending and int(state.get("step_count", 0)) < MAX_AGENT_STEPS:
        return "tools"
    return "finalize"
