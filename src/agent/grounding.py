"""Deterministic final-answer output guard for the LangGraph agent (post-Sprint 4, P0.1).

This is the AGENT-specific grounding *policy* layer. It does NOT reimplement the shared
output protections: it delegates secret redaction, system-instruction leakage flagging
and citation-provenance validation to the Sprint-3 generic output guard
(``src.copilot.security.output_guard.guard_output``), so the Career path and the Agent
path share one implementation instead of two divergent ones. On top of that shared guard
it adds one agent-specific *observability* signal: when retrieval genuinely ran and
produced citations but the final answer includes no inline source reference, a safe
warning is recorded — it never blocks and never claims a hallucination.

Scope of the citation check is PROVENANCE only: it validates that every inline ``[n]``
marker maps to a real citation produced by ``SearchCareerKnowledge`` in the CURRENT run
and removes fabricated/stale markers. This is NOT semantic claim-level faithfulness —
that remains an evaluation concern (RAGAS / the live benchmark), never a runtime model
call. Removing an unsupported citation marker is a provenance fix; it is not a claim that
the surrounding sentence is factually wrong.
"""

from __future__ import annotations

import re
from typing import Any

from src.copilot.security.output_guard import guard_output

# Bracketed numeric citation markers, e.g. [1], [12] — the shape the retrieval layer
# emits. Used only to test whether ANY valid inline reference survived the guard.
_MARKER_RE = re.compile(r"\[\d+\]")

# Safe, candidate-appropriate observability message (never claims a hallucination).
_UNCITED_RETRIEVAL_WARNING = (
    "Retrieved evidence was used, but the final response did not include an inline "
    "source reference."
)


def _valid_markers(citations: list[dict[str, Any]] | None) -> set[str]:
    markers: set[str] = set()
    for c in citations or []:
        m = c.get("marker") if isinstance(c, dict) else None
        if isinstance(m, str) and m.strip():
            markers.add(m.strip())
    return markers


def guard_agent_answer(
    answer: str,
    citations: list[dict[str, Any]] | None,
    *,
    retrieval_used: bool = False,
) -> tuple[str, list[str]]:
    """Return ``(safe_answer, warnings)`` for an agent final answer.

    Order of protection (defence in depth):
      1. Shared generic output guard — redact secret-like strings, flag verbatim
         system-instruction leakage, and remove citation markers not backed by the
         CURRENT run's retrieved evidence (fabricated/stale).
      2. Agent-specific grounding policy — if retrieval genuinely ran and produced
         citations but no valid inline marker survived, record a safe observability
         warning.

    Deterministic; makes NO model call. ``warnings`` are safe, candidate-appropriate
    strings (never raw errors, secrets or provider content).
    """
    if not answer:
        return answer, []

    allowed = _valid_markers(citations)
    result = guard_output(answer, allowed_markers=allowed)
    safe = result.safe_answer
    warnings = list(result.findings)

    # Agent-specific grounding policy: retrieval genuinely ran and produced citations,
    # but the answer carries no valid inline source reference. Observability only — not
    # a block and not a claim that anything was hallucinated. When retrieval produced no
    # citations at all (e.g. an honest "insufficient evidence" reply), there is nothing
    # to cite, so no warning is raised.
    if retrieval_used and allowed and not _MARKER_RE.search(safe):
        warnings.append(_UNCITED_RETRIEVAL_WARNING)

    return safe, warnings


def validate_citations(
    answer: str, citations: list[dict[str, Any]] | None
) -> tuple[str, list[str]]:
    """Provenance-only wrapper (no retrieval-context signal).

    Retained for callers that only need citation-provenance validation. Prefer
    :func:`guard_agent_answer`, which also applies secret/leakage protection and the
    uncited-retrieval observability policy.
    """
    return guard_agent_answer(answer, citations, retrieval_used=False)
