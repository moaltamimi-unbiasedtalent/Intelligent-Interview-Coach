"""Internal occupation-resolution CONTRACT (GKB-2; consumed by P10C-B). Not wired into any candidate-facing path in P10C-A.

Outcomes: RESOLVED, AMBIGUOUS, INSUFFICIENT_CONTEXT, UNSUPPORTED, NOT_FOUND. The request has NO language or locale field by construction: geography is only an explicit ISO
country code, never inferred from the interface or conversation language. A title alone is never an identity: several graph nodes sharing a title are AMBIGUOUS unless a verified
equivalence joins them. The resolver never guesses an occupation in order to return a compensation result."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.knowledge_foundation.graph import OccupationGraph

__all__ = ["ResolutionOutcome", "ResolutionRequest", "ResolutionCandidate", "ResolutionResult", "GraphResolver"]


class ResolutionOutcome(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    UNSUPPORTED = "unsupported"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ResolutionRequest:
    """Everything the resolver may use. No ``language``/``locale`` field exists on purpose."""

    title: str | None = None
    taxonomy_scheme: str | None = None
    taxonomy_code: str | None = None
    taxonomy_edition: str | None = None
    country: str | None = None                       # explicit ISO-3166 alpha-2 (or the registry's code), never derived from language
    role_context: str | None = None
    industry: str | None = None
    seniority: str | None = None
    known_occupation_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionCandidate:
    occupation_key: str
    canonical_label: str
    basis: str                                        # identifier_exact | label_exact | known_key | legacy_key
    scheme: str | None = None
    edition: str | None = None


@dataclass
class ResolutionResult:
    outcome: ResolutionOutcome
    candidates: list[ResolutionCandidate] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    context_needed: list[str] = field(default_factory=list)   # what additional context would let the resolver decide (never a guess)


class GraphResolver:
    """Reference implementation over the persisted graph. Deterministic, read-only, language-independent. Intended for P10C-B to extend; used only by tests in P10C-A."""

    def __init__(self, graph: OccupationGraph, coverage=None) -> None:
        self._g, self._coverage = graph, coverage

    def resolve(self, req: ResolutionRequest) -> ResolutionResult:
        if req.country and self._coverage is not None:
            row = self._coverage.get(req.country)
            if row is None or row["taxonomy_level"] == "unsupported":
                return ResolutionResult(ResolutionOutcome.UNSUPPORTED, reasons=["country_not_supported"])
        if req.known_occupation_keys:
            found = [self._g.get(k) or self._g.find_by_legacy_key(k) for k in req.known_occupation_keys]
            found = [f for f in found if f]
            uniq = {f["occupation_key"]: f for f in found}
            if len(uniq) == 1:
                f = next(iter(uniq.values()))
                return ResolutionResult(ResolutionOutcome.RESOLVED, [ResolutionCandidate(f["occupation_key"], f["canonical_label"], "known_key")])
            if len(uniq) > 1:
                return ResolutionResult(ResolutionOutcome.AMBIGUOUS, [ResolutionCandidate(f["occupation_key"], f["canonical_label"], "known_key") for f in uniq.values()],
                                        ["several_known_keys"])
        if req.taxonomy_code:
            if not req.taxonomy_scheme:
                return ResolutionResult(ResolutionOutcome.INSUFFICIENT_CONTEXT, reasons=["code_without_taxonomy"], context_needed=["taxonomy_scheme"])
            hits = self._g.find_by_identifier(req.taxonomy_scheme, req.taxonomy_code, req.taxonomy_edition)
            if not hits:
                return ResolutionResult(ResolutionOutcome.NOT_FOUND, reasons=["identifier_not_in_graph"])
            keys = {h["occupation_key"] for h in hits}
            cands = [ResolutionCandidate(h["occupation_key"], h["canonical_label"], "identifier_exact", h["scheme"], h["edition"]) for h in hits]
            if len(keys) == 1:
                return ResolutionResult(ResolutionOutcome.RESOLVED, cands[:1])
            if req.taxonomy_edition is None:
                return ResolutionResult(ResolutionOutcome.AMBIGUOUS, cands, ["code_exists_in_several_editions_with_different_occupations"], ["taxonomy_edition"])
            return ResolutionResult(ResolutionOutcome.AMBIGUOUS, cands, ["identifier_maps_to_several_occupations"])
        if req.title and req.title.strip():
            hits = self._g.find_by_label(req.title)
            cands = [ResolutionCandidate(h["occupation_key"], h["canonical_label"], "label_exact") for h in hits]
            if not hits:
                return ResolutionResult(ResolutionOutcome.NOT_FOUND, reasons=["title_not_in_graph"])
            if len(hits) == 1:
                return ResolutionResult(ResolutionOutcome.RESOLVED, cands)
            if self._joined_by_verified_equivalence([h["occupation_key"] for h in hits]):
                return ResolutionResult(ResolutionOutcome.RESOLVED, cands[:1], ["several nodes joined by verified equivalence"])
            return ResolutionResult(ResolutionOutcome.AMBIGUOUS, cands, ["title_matches_several_distinct_occupations"], ["taxonomy_scheme", "taxonomy_code", "role_context"])
        return ResolutionResult(ResolutionOutcome.INSUFFICIENT_CONTEXT, reasons=["no_title_or_code"], context_needed=["title", "taxonomy_code"])

    def _joined_by_verified_equivalence(self, keys: list[str]) -> bool:
        """True only when every node is linked to the first by a VERIFIED, source-provided EQUIVALENT relationship (RELATED, BROADER and unverified links never join nodes)."""
        first = keys[0]
        linked = {r["to_key"] for r in self._g.relationships(first) if r["relationship_type"] == "equivalent" and r["mapping_status"] == "verified"}
        linked |= {r["from_key"] for r in self._g.relationships(first, direction="in") if r["relationship_type"] == "equivalent" and r["mapping_status"] == "verified"}
        return all(k in linked for k in keys[1:])
