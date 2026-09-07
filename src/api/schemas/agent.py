"""Agent API schemas (experimental — Sprint 4 preview).

The agent runs side-by-side with the deterministic Career flow; this surface does
NOT replace /career/chat. Responses carry only safe, observable data (events, tool
calls, status) — never chain-of-thought, prompts or raw provider output.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    target_role: str | None = Field(default=None, max_length=200)
    job_description: str | None = Field(default=None, max_length=12000)
    candidate_background: str | None = Field(default=None, max_length=12000)


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    response: str
    events: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    step_count: int = 0
