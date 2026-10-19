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
from typing import Any, NamedTuple

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


class PolicyOutcome(NamedTuple):
    answer: str
    warnings: list
    response_class: str
    flags: list
    removed_markers: list


def apply_candidate_policy(
    answer: str,
    *,
    citations: list[dict[str, Any]] | None,
    evidence: list[dict[str, Any]] | None,
    query: str,
    resolved_geography: str | None,
    retrieval_used: bool,
    language: str | None,
    allowed_text: str = "",
    completed: bool = True,
) -> PolicyOutcome:
    """Owner-approved candidate grounding policies A, B and C for an agent final answer (2026-10-19).

    Delegates to the ONE shared layer (``src.copilot.security.grounding_policy``): contextual citations only, no unsourced compensation estimates, no unsupported figures
    (another country's compensation evidence never authorises a figure). Policy B, conservative: for a recognised external-fact question answered WITHOUT retrieval, a
    sentence that states a statistic or figure is removed (it would be an unverified assertion presented as an answer) and replaced by a localized evidence limitation;
    general guidance without such a figure is kept and labelled as not source-backed. A clarification or an abstention is never touched and no tool call is forced.
    Deterministic, no model call. ``removed_markers`` lets the caller keep citation metadata consistent with the final text.
    """
    from src.copilot.rag import localized
    from src.copilot.security import grounding_policy as GP

    sources = list(evidence or [])
    cits = list(citations or [])
    views = []
    for i, c in enumerate(cits, start=1):
        meta = sources[i - 1] if i - 1 < len(sources) and isinstance(sources[i - 1], dict) else {}
        views.append(GP.EvidenceView(marker=str(c.get("marker") or f"[{i}]"), text="", evidence_type=str(meta.get("evidence_type") or ""), country=meta.get("geography") or None))
    text, warnings, flags = answer, [], []
    # Policy B first: with no retrieval, a statistic is never presented as an answer (and the limitation is the TRUE one: nothing was retrieved).
    if completed and not retrieval_used and text and GP.is_external_fact_query(query):
        is_clarification = len(text) <= 500 and "?" in text
        if not is_clarification and not GP.states_insufficient(text):
            kept, dropped = [], 0
            for line in text.split("\n"):
                parts = list(re.split(r"(?<=[.!?])\s+", line)) if line.strip() else [line]
                keep = [p for p in parts if not (p.strip() and GP.statistic_figures(p))]
                dropped += len(parts) - len(keep)
                if (keep and any(k.strip() for k in keep)) or not line.strip():
                    kept.append(" ".join(keep))
            if dropped:
                text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
                text = (text + "\n\n" if text else "") + localized.unretrieved_limitation(language)
                warnings.append("An external statistic was stated without retrieval; the unsupported figure was removed and an evidence limitation given.")
                flags.append("external_statistic_removed_without_retrieval")
            elif not _MARKER_RE.search(text):
                text = text.rstrip() + "\n\n" + localized.unverified_general_notice(language)
                warnings.append("An external factual question was answered without retrieval; the answer is labelled as not source-backed.")
                flags.append("external_factual_question_without_retrieval")
    res = GP.enforce(text, evidence=views, query=query, resolved_country=resolved_geography, language=language, allowed_text=allowed_text)
    text = res.answer
    warnings += list(res.findings)
    flags += list(res.flags)
    return PolicyOutcome(text, warnings, res.response_class, flags, list(res.removed_markers))
