"""Cross-language citation attribution and language-aware abstention (package 06D, LG-06). Pure functions: no model call, no network.

THREE RULES, each minimal and deterministic
1. A citation is REAL: every ``[n]`` in an answer must name a retrieved source (marker, document id, chunk id, and the recorded source version must
   agree). :func:`check_citations` reports each violation by a fixed code; it never repairs or invents a mapping.
2. A source claim is never presented in a translation as if the source said it in that language. When a cited source is written in a language other
   than the Mo conversation language, :func:`apply_source_language_notices` appends, per such source, a notice in the CONVERSATION language that states
   the source language, says that what is reported is a translation, and quotes the source's ORIGINAL wording unchanged. Nothing is translated here:
   the quote is a verbatim excerpt (whitespace-normalised, optionally cut at a word boundary with an ellipsis) of the retrieved passage. A source whose
   language was not recorded is NOT assumed to be in any language (the marker is reported in ``unknown_language_markers`` and no claim is made).
3. Abstention: when sources exist but none clears the 02E relevance floor, :func:`decide_abstention` returns the abstention sentence in the answer
   language (the Mo conversation language, else the question's own language, else English), offers no citation, and names the reason.

Language ownership: the notice and the abstention are Mo-voiced, so they follow the Mo conversation language, never the interface language. All
sentences live in ``src.copilot.rag.localized`` (eight languages, parity enforced there).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.copilot.knowledge.router_lang import guess_language
from src.copilot.models import Citation
from src.copilot.rag import localized
from src.copilot.retrieval_quality.floor import RelevanceFloor, apply_floor

__all__ = ["RetrievedSource", "AttributionReport", "AbstentionDecision", "QUOTE_MAX_CHARS", "sources_from_citations", "check_citations",
           "apply_source_language_notices", "resolve_answer_language", "decide_abstention", "normalise_language", "verbatim_excerpt"]

QUOTE_MAX_CHARS = 200
_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class RetrievedSource:
    """One retrieved source as the answer path knows it. ``language`` / ``version`` are ``None`` when the source did not record them."""

    marker: str
    chunk_id: str
    doc_id: str
    text: str
    language: str | None = None
    version: str | None = None


@dataclass
class AttributionReport:
    issues: list[str] = field(default_factory=list)                 # fixed codes, e.g. "unmapped_marker:[9]"
    translated_markers: list[str] = field(default_factory=list)      # cited sources in another language than the conversation
    unknown_language_markers: list[str] = field(default_factory=list)  # cited sources whose language was not recorded

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class AbstentionDecision:
    abstain: bool
    language: str
    message: str | None
    sources_found: int
    kept: int
    cited: tuple = ()              # an abstention never carries a citation


def normalise_language(code: str | None) -> str | None:
    """``'de-AT'`` -> ``'de'``; ``None`` for an empty or unsupported code (an unsupported language is never named or asserted)."""
    c = (code or "").strip().lower().split("-")[0]
    return c if c in localized.LANGUAGE_ENDONYMS else None


def verbatim_excerpt(text: str, limit: int = QUOTE_MAX_CHARS) -> str:
    """The opening of ``text`` in the source's own words: whitespace collapsed, double quotes kept as single-quote-safe text, cut at a word boundary with
    an ellipsis when longer than ``limit``. Never translated or paraphrased."""
    flat = " ".join((text or "").split()).replace('"', "'")
    if len(flat) <= limit:
        return flat
    cut = flat[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return (cut or flat[:limit]) + "…"


def sources_from_citations(citations: Sequence[Citation], texts_by_marker: Mapping[str, str]) -> list[RetrievedSource]:
    """Build the retrieved-source list from the citation candidates the context builder produced (they carry language and version) and the passage
    text keyed by marker."""
    return [RetrievedSource(c.marker, c.chunk_id, c.doc_id, texts_by_marker.get(c.marker, ""), normalise_language(c.language) or c.language, c.version)
            for c in citations]


def _markers_in(answer: str) -> list[str]:
    seen: list[str] = []
    for n in _MARKER_RE.findall(answer or ""):
        m = f"[{n}]"
        if m not in seen:
            seen.append(m)
    return seen


def check_citations(answer: str, cited: Sequence[Citation], retrieved: Sequence[RetrievedSource]) -> list[str]:
    """Violations of rule 1, as fixed codes (empty = every citation maps to a real retrieved source and version).

    * ``unmapped_marker:[n]``      the answer cites a marker that no retrieved source carries;
    * ``citation_not_retrieved:[n]`` a citation object has no retrieved source with that marker;
    * ``citation_mismatch:[n]``    the citation's chunk or document id differs from the retrieved source's;
    * ``version_mismatch:[n]``     both record a version and the versions differ (a citation must not claim a version the source did not have)."""
    by_marker = {r.marker: r for r in retrieved}
    issues: list[str] = []
    for m in _markers_in(answer):
        if m not in by_marker:
            issues.append(f"unmapped_marker:{m}")
    for c in cited:
        r = by_marker.get(c.marker)
        if r is None:
            issues.append(f"citation_not_retrieved:{c.marker}")
            continue
        if (c.chunk_id, c.doc_id) != (r.chunk_id, r.doc_id):
            issues.append(f"citation_mismatch:{c.marker}")
        elif c.version and r.version and c.version != r.version:
            issues.append(f"version_mismatch:{c.marker}")
    return issues


def apply_source_language_notices(answer: str, retrieved: Sequence[RetrievedSource], *, conversation_language: str | None) -> tuple[str, AttributionReport]:
    """Rule 2. Append one notice per CITED source written in a language other than the conversation language. English/unknown conversation language
    means English. Returns the (possibly extended) answer and the report. The answer text itself is never rewritten."""
    report = AttributionReport()
    convo = localized.resolve_language(conversation_language)
    by_marker = {r.marker: r for r in retrieved}
    notices: list[str] = []
    for m in _markers_in(answer):
        r = by_marker.get(m)
        if r is None:
            report.issues.append(f"unmapped_marker:{m}")
            continue
        lang = normalise_language(r.language)
        if lang is None:
            report.unknown_language_markers.append(m)
            continue
        if lang == convo:
            continue
        report.translated_markers.append(m)
        notices.append(localized.source_language_notice(convo, marker=m, source_language=lang, quote=verbatim_excerpt(r.text)))
    if notices:
        answer = answer.rstrip() + "\n\n" + "\n".join(notices)
    return answer, report


def resolve_answer_language(conversation_language: str | None, question: str | None = None) -> str:
    """The language an answer or abstention is written in: the explicit Mo conversation language, else the language the question's stop words single
    out (a tie or no evidence is NOT guessed), else English. The interface language never takes part."""
    explicit = normalise_language(conversation_language)
    if explicit:
        return explicit
    guessed = normalise_language(guess_language(question or ""))
    return guessed or "en"


def decide_abstention(results: Sequence[Any], floor: RelevanceFloor | float, *, conversation_language: str | None = None, question: str | None = None,
                      score_of=lambda r: r.score) -> AbstentionDecision:
    """Rule 3. Nothing above the floor leaves no evidence: abstain in the answer language and cite nothing. ``sources_found`` > 0 means sources were
    retrieved but judged irrelevant (the message then says so); 0 means nothing was retrieved at all."""
    lang = resolve_answer_language(conversation_language, question)
    kept = apply_floor(results, floor, score_of=score_of)
    if kept:
        return AbstentionDecision(False, lang, None, len(results), len(kept))
    return AbstentionDecision(True, lang, localized.abstention_message(lang, sources_found=bool(results)), len(results), 0)
