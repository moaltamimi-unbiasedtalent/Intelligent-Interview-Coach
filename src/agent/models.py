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
    # Optional Agent model profile (fast | balanced | advanced). Validated server-side;
    # a raw provider slug is never accepted. Defaults to Balanced when unset/invalid.
    profile: str | None = None


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
    # Safe summaries of the memories loaded this run (category/summary/target_role) so
    # the candidate can inspect exactly what was used — never internal ids or raw state.
    memory_loaded: list[dict[str, Any]] = field(default_factory=list)
    # Human-in-the-loop (Phase 8). When paused, `pending_action` is the safe
    # PendingHumanAction dict the client must resolve via the resume endpoint.
    awaiting_human_input: bool = False
    pending_action: dict[str, Any] | None = None
    handoff_approved: bool = False
    # Per-turn step count (bounds a turn); step_count is the thread-lifetime total.
    turn_step_count: int = 0
    # Bounded, candidate-safe conversation projection ({role, content}); never
    # contains system/tool/internal messages.
    conversation: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    step_count: int = 0
    request_id: str | None = None
    # A typed PreparationContext (as a dict) when enough tool data exists — else None.
    preparation_context: dict[str, Any] | None = None
    # Safe provider-usage aggregate for the run (AgentRunUsage.to_dict); never prompts,
    # reasoning or candidate text. See src/agent/usage.py.
    usage: dict[str, Any] | None = None
    # Wall-clock latency of the model/graph work for THIS call (run/resume/continue).
    latency_ms: int | None = None
    # The Agent model profile in effect for the run (fast | balanced | advanced).
    profile: str | None = None
    # Safe retrieval-cache observability (thread-lifetime counts only — never keys).
    cache_hits: int = 0
    cache_misses: int = 0
