"""Typed agent state (short-term / execution state only).

This is LangGraph in-run state — NOT long-term cross-session memory (that is a
later phase). It holds only what the bounded loop needs. Secrets, DB URLs, system
prompts and chain-of-thought are never stored here; candidate/JD text may live in
short-term state while a run executes but is never written to events or logs.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

# Terminal + transient run statuses.
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_STEP_LIMIT = "step_limit_reached"
STATUS_NEEDS_HUMAN = "needs_human"


class AgentState(TypedDict, total=False):
    # Conversation (LangGraph appends via add_messages).
    messages: Annotated[list, add_messages]

    # Identity / run bookkeeping.
    run_id: str
    user_id: str | None

    # Request context (short-term).
    goal: str
    target_role: str | None
    job_description: str | None
    candidate_background: str | None

    # Structured tool outputs carried between steps (short-term; safe dicts).
    requirements: dict[str, Any] | None  # from job-description analysis
    gaps: dict[str, Any] | None  # from candidate gap analysis
    preparation_plan: dict[str, Any] | None  # from the preparation planner
    questions: dict[str, Any] | None  # from the question generator

    # Long-term preparation memory loaded for this run (user-approved DATA; safe
    # projections — category/summary/target_role only, never raw private content).
    memory_items: list[dict[str, Any]] | None

    # Retrieval outputs (Agentic RAG; safe evidence/citations — no raw store rows).
    evidence: list[dict[str, Any]] | None
    citations: list[dict[str, Any]] | None
    retrieval_used: bool
    last_retrieval_query: str | None
    resolved_occupation: str | None
    resolved_geography: str | None

    # Orchestration bookkeeping.
    tool_history: list[dict[str, Any]]
    events: list[dict[str, Any]]
    step_count: int
    status: str
    last_error: str | None
    completed: bool
