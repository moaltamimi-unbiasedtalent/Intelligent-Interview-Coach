"""Assemble the single, bounded, tool-using LangGraph agent (with HITL).

    START → initialise → agent → (tool requested & within budget?) → tools
                                     └ otherwise ─────────────────→ finalize → END
    tools → (human decision requested?) → human_review → agent
              └ otherwise ─────────────→ agent

The loop is bounded by MAX_AGENT_STEPS (see policies). ``human_review`` pauses the
graph with LangGraph's ``interrupt`` and resumes with ``Command(resume=...)`` on the
SAME thread (Phase 8). The checkpointer defaults to in-memory (transient) but the
application wires a durable official saver; the model is injected via
``model_factory`` so tests run without a provider.
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agent.nodes import (
    make_agent_node,
    make_finalize_node,
    make_human_review_node,
    make_initialise_node,
    make_tools_node,
    route_after_agent,
    route_after_tools,
)
from src.agent.registry import ToolRegistry
from src.agent.state import AgentState

ModelFactory = Callable[[], Any]


def build_agent_graph(
    *,
    model_factory: ModelFactory,
    registry: ToolRegistry,
    checkpointer: Any | None = None,
    memory_service: Any | None = None,
):
    """Compile the agent graph. ``registry`` is the allowlisted tools; ``checkpointer``
    defaults to in-memory (transient); ``memory_service`` lets the human-review node
    persist an APPROVED memory."""
    graph = StateGraph(AgentState)
    graph.add_node("initialise", make_initialise_node())
    graph.add_node("agent", make_agent_node(model_factory, registry))
    graph.add_node("tools", make_tools_node(registry))
    graph.add_node("human_review", make_human_review_node(memory_service))
    graph.add_node("finalize", make_finalize_node())

    graph.add_edge(START, "initialise")
    graph.add_edge("initialise", "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "finalize": "finalize"})
    graph.add_conditional_edges("tools", route_after_tools, {"human_review": "human_review", "agent": "agent"})
    graph.add_edge("human_review", "agent")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
