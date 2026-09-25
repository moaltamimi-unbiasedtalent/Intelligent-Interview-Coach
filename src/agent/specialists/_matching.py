"""Deterministic keyword-overlap matching shared by the evidence + coaching specialists.

Intentionally simple and transparent: lower-cased alphanumeric tokens minus a small
stop-word set, with an overlap score. No model, no external data — so specialist
ranking is reproducible, explainable in a review, and inert to prompt injection (the
text is only ever tokenised, never interpreted as instructions).
"""

from __future__ import annotations

import re

__all__ = ["tokens", "overlap_score", "matches_any"]

_STOP = {
    "the", "and", "for", "with", "you", "your", "are", "was", "were", "has", "have",
    "had", "this", "that", "from", "into", "our", "their", "them", "they", "a", "an",
    "to", "of", "in", "on", "at", "by", "or", "as", "is", "it", "be", "we", "i",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str | None) -> set[str]:
    """Lower-cased alphanumeric tokens (length ≥ 3, minus stop-words)."""
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3 and t not in _STOP}


def overlap_score(query_tokens: set[str], text: str | None) -> int:
    """Count of query tokens present in ``text`` (deterministic relevance signal)."""
    if not query_tokens or not text:
        return 0
    return len(query_tokens & tokens(text))


def matches_any(needle_tokens: set[str], text: str | None) -> bool:
    """Whether any needle token appears in ``text``."""
    return overlap_score(needle_tokens, text) > 0
