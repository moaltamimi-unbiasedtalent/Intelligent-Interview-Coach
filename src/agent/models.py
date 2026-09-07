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
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    step_count: int = 0
    request_id: str | None = None
