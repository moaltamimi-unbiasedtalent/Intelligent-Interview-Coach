"""Agent API schemas (experimental — Sprint 4 preview).

The agent runs side-by-side with the deterministic Career flow; this surface does
NOT replace /career/chat. Responses carry only safe, observable data (events, tool
calls, status) — never chain-of-thought, prompts or raw provider output.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    target_role: str | None = Field(default=None, max_length=200)
    job_description: str | None = Field(default=None, max_length=12000)
    candidate_background: str | None = Field(default=None, max_length=12000)


class PendingActionResponse(BaseModel):
    """The safe, user-visible decision a paused run is waiting for (Phase 8)."""

    action_id: str
    type: str
    message: str
    options: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    response: str
    tools_used: list[str] = Field(default_factory=list)
    retrieval_used: bool = False
    sources: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    resolved_occupation: str | None = None
    resolved_geography: str | None = None
    memory_used: bool = False
    memory_count: int = 0
    # HITL (Phase 8): a paused run carries the pending action; awaiting is a NORMAL
    # status, never an error.
    awaiting_human_input: bool = False
    pending_action: PendingActionResponse | None = None
    handoff_approved: bool = False
    events: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    step_count: int = 0
    turn_step_count: int = 0
    # Bounded, candidate-safe conversation ({role, content}) — never system/tool/
    # internal messages. Used by the Agent Coach for refresh/multi-turn UX.
    conversation: list[dict] = Field(default_factory=list)
    # A PreparationContext (safe dict) when the run gathered enough — else null.
    preparation_context: dict | None = None


class AgentContinueRequest(BaseModel):
    """A new user turn on an existing thread (short-term conversational memory).

    Carries ONLY the message — never a user_id, tool selection or graph state.
    """

    message: str = Field(min_length=1, max_length=4000)


class HumanDecisionRequest(BaseModel):
    """A validated human decision for a paused run. The client never sends a
    user_id or arbitrary state — only the action being answered and the choice."""

    action_id: str = Field(min_length=1, max_length=64)
    decision: Literal["select", "approve", "reject"]
    # Required only for a CONFIRM_ROLE 'select'; must be one of the offered options.
    selected_role: str | None = Field(default=None, max_length=200)
