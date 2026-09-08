"""Deterministic final-answer grounding guard (post-Sprint 4, P0).

Reuses the Sprint 3 citation/provenance principle for the LangGraph agent's final
answer: any bracketed citation marker in the answer (e.g. ``[1]``) MUST correspond to
a real citation produced by ``SearchCareerKnowledge`` in the CURRENT run/thread.
Fabricated or stale markers (invented by the model, or referencing a different run's
evidence, which is not in this run's citation set) are removed, and a safe warning is
recorded. Markers from an actual retrieval are preserved.

This is a cheap, deterministic check — it does NOT call a model. Optional semantic
faithfulness checks remain evaluation-time only (RAGAS / the live benchmark).
"""

from __future__ import annotations

import re
from typing import Any

# Bracketed numeric citation markers, e.g. [1], [12]. (The retrieval layer emits
# markers of this shape; anything matching that the model invents is caught.)
_MARKER_RE = re.compile(r"\[(\d+)\]")


def _valid_markers(citations: list[dict[str, Any]] | None) -> set[str]:
    markers: set[str] = set()
    for c in citations or []:
        m = c.get("marker") if isinstance(c, dict) else None
        if isinstance(m, str) and m.strip():
            markers.add(m.strip())
    return markers


def validate_citations(answer: str, citations: list[dict[str, Any]] | None) -> tuple[str, list[str]]:
    """Return ``(clean_answer, warnings)``.

    Removes any ``[n]`` marker in ``answer`` that is not present in ``citations`` (the
    current run's retrieved evidence). Never invents or renumbers citations. If
    everything is grounded (or the answer cites nothing) the text is returned
    unchanged with no warnings.
    """
    if not answer:
        return answer, []
    valid = _valid_markers(citations)
    found = _MARKER_RE.findall(answer)
    if not found:
        return answer, []

    unsupported = {f"[{n}]" for n in found if f"[{n}]" not in valid}
    if not unsupported:
        return answer, []

    clean = answer
    for marker in unsupported:
        clean = clean.replace(marker, "")
    # Tidy doubled spaces / space-before-punctuation left by removed markers.
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\s+([.,;:])", r"\1", clean).strip()
    warnings = [
        f"Removed {len(unsupported)} unsupported citation marker(s) not backed by "
        "retrieved evidence."
    ]
    return clean, warnings
