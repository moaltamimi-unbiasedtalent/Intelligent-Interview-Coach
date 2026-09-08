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
    confirmed_target_role: str | None = None  # role the user confirmed via HITL
    # Prior retrieval (for duplicate-retrieval protection within a run).
    last_retrieval_query: str | None = None
    evidence: list[dict[str, Any]] | None = None
    citations: list[dict[str, Any]] | None = None
    # Bounded per-thread retrieval cache (safe evidence entries; see usage/cache docs).
    retrieval_cache: list[dict[str, Any]] | None = None


@dataclass
class ToolOutcome:
    """A tool's result: model observation + state patch + safe event metadata."""

    result: dict[str, Any]  # returned to the model (may contain JD-derived DATA)
    state_patch: dict[str, Any] = field(default_factory=dict)  # merged into AgentState
    summary: str | None = None  # safe event summary — NEVER raw candidate/JD text
    source_count: int | None = None
    # Safe provider-usage for a model-backed tool call (token/call counts + model slug
    # only; never prompts/candidate text). None for deterministic tools. See usage.py.
    usage: dict[str, Any] | None = None
    # Retrieval cache outcome for observability: "hit" | "miss" | None (non-retrieval).
    cache: str | None = None
