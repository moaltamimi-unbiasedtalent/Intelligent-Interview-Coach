"""Shared types for agent tool execution.

A tool handler receives its validated ``args`` plus a :class:`ToolContext` built
from prior agent state (so a tool can enforce prerequisites produced by earlier
tools — e.g. gap analysis needs the requirements from a prior job analysis). It
returns a :class:`ToolOutcome`: the structured observation for the model, a safe
state patch, and privacy-safe event metadata (summary/counts only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolContext:
    """Prior structured results a tool may need (from earlier steps in the run)."""

    target_role: str | None = None
    job_description: str | None = None
    candidate_background: str | None = None
    requirements: dict[str, Any] | None = None  # prior job-analysis (RoleRequirements)
    gaps: dict[str, Any] | None = None  # prior gap-analysis (GapAnalysisResult)
    # Prior retrieval (for duplicate-retrieval protection within a run).
    last_retrieval_query: str | None = None
    evidence: list[dict[str, Any]] | None = None
    citations: list[dict[str, Any]] | None = None


@dataclass
class ToolOutcome:
    """A tool's result: model observation + state patch + safe event metadata."""

    result: dict[str, Any]  # returned to the model (may contain JD-derived DATA)
    state_patch: dict[str, Any] = field(default_factory=dict)  # merged into AgentState
    summary: str | None = None  # safe event summary — NEVER raw candidate/JD text
    source_count: int | None = None
