"""Stable application-level agent request/result — no LangGraph objects leak out."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRunRequest:
    """Plain typed input for one agent run (no Streamlit/FastAPI objects)."""

    goal: str
    target_role: str | None = None
    job_description: str | None = None
    candidate_background: str | None = None
    user_id: str | None = None


@dataclass
class AgentRunResult:
    """The safe, serialisable outcome of a run. Contains no chain-of-thought."""

    run_id: str
    status: str
    response: str
    events: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    retrieval_used: bool = False
    resolved_occupation: str | None = None
    resolved_geography: str | None = None
    # Long-term preparation memory read into this run (counts only — never content).
    memory_used: bool = False
    memory_count: int = 0
    # Human-in-the-loop (Phase 8). When paused, `pending_action` is the safe
    # PendingHumanAction dict the client must resolve via the resume endpoint.
    awaiting_human_input: bool = False
    pending_action: dict[str, Any] | None = None
    handoff_approved: bool = False
    warnings: list[str] = field(default_factory=list)
    step_count: int = 0
    request_id: str | None = None
    # A typed PreparationContext (as a dict) when enough tool data exists — else None.
    preparation_context: dict[str, Any] | None = None
