"""Assemble the single, bounded, tool-using LangGraph agent.

    START → initialise → agent → (tool requested & within budget?) → tools → agent
                                     └ otherwise ─────────────────→ finalize → END

The loop is bounded by MAX_AGENT_STEPS (see policies). Short-term state uses an
in-memory checkpointer by default (NOT durable production memory — cross-session
memory is a later phase). The model is injected via ``model_factory`` so tests run
without a provider.
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agent.nodes import (
    make_agent_node,
    make_finalize_node,
    make_initialise_node,
    make_tools_node,
    route_after_agent,
)
from src.agent.registry import ToolRegistry
from src.agent.state import AgentState

ModelFactory = Callable[[], Any]


def build_agent_graph(
    *,
    model_factory: ModelFactory,
    registry: ToolRegistry,
    checkpointer: Any | None = None,
):
    """Compile the agent graph. ``registry`` is the (allowlisted) Career tools;
    ``checkpointer`` defaults to in-memory (transient)."""
    graph = StateGraph(AgentState)
    graph.add_node("initialise", make_initialise_node())
    graph.add_node("agent", make_agent_node(model_factory, registry))
    graph.add_node("tools", make_tools_node(registry))
    graph.add_node("finalize", make_finalize_node())

    graph.add_edge(START, "initialise")
    graph.add_edge("initialise", "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "finalize": "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
