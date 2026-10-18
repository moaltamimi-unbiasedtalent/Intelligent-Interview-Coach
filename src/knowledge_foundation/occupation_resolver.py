"""Deterministic multilingual occupation resolver (GKB-13; INTERNAL, NON-OPERATIONAL). Extends the P10C-A contract without replacing it and is imported by no candidate-facing path.

Evidence ladder (strongest first): known canonical key, exact native code (edition-explicit; ISCO zero padding restored only against the authority), exact alias (exact normalized
key), tolerant alias (diacritics folded, Latin script only), canonical label with unknown language. Title similarity alone is never equivalence; RELATED, BROADER and NARROWER links
never join occupations (only a VERIFIED, source-provided EQUIVALENT does); a conflicting title never overrides an official code.

Policy (RECOMMENDED OWNER POLICY, pending formal adoption; implemented conservatively): never guess an occupation to produce compensation evidence. Outcomes: RESOLVED (one canonical
identity is supported), AMBIGUOUS (several remain; candidates listed, curated context may narrow them), INSUFFICIENT_CONTEXT (more information is needed for a safe choice, e.g. an
unverified alias language or no usable input), UNSUPPORTED (country or language outside supported coverage) and NOT_FOUND (no credible candidate). The first match is never chosen silently.

Language and geography are separate parameters: ``title_language`` is the language OF THE INPUT TEXT, explicitly supplied; the request has no interface-locale field, and the country is
only ever the explicit ``country`` value (never derived from any language). ``seniority`` does not change occupation identity and is reported as ignored. ``operational`` is true only
when the supporting alias is qualified and its source is approved for runtime use, which no source is today."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.knowledge_foundation.aliases import AliasStore
from src.knowledge_foundation.codes import restore_isco_zero_padding
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.normalize import normalize_label, normalize_language_tag
from src.knowledge_foundation.resolver_contract import GraphResolver, ResolutionOutcome

__all__ = ["MultilingualRequest", "MultilingualCandidate", "MultilingualResult", "OccupationResolver", "ResolutionOutcome"]


@dataclass(frozen=True)
class MultilingualRequest:
    """Only inputs actually available. There is deliberately NO interface-language or locale field."""

    title: str | None = None
    title_language: str | None = None                # the language of ``title`` as supplied by the caller (never the UI locale)
    country: str | None = None                       # explicit employment country; never inferred
    taxonomy_scheme: str | None = None
    taxonomy_code: str | None = None
    taxonomy_edition: str | None = None
    role_context: str | None = None
    industry: str | None = None
    seniority: str | None = None
    known_occupation_keys: tuple[str, ...] = ()
    allow_cross_language: bool = False               # opt in to matching aliases of other languages (reported as such)
    accept_unverified_language: bool = False         # opt in to aliases whose language is UNKNOWN (reported as such)


@dataclass(frozen=True)
class MultilingualCandidate:
    occupation_key: str
    canonical_label: str
    grade: str          # known_key | code_exact | code_zero_padding_restored | alias_exact | alias_folded | alias_cross_language | alias_language_unverified | canonical_label_language_unknown
    evidence: dict = field(default_factory=dict)


@dataclass
class MultilingualResult:
    outcome: ResolutionOutcome
    candidates: list[MultilingualCandidate] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    context_needed: list[str] = field(default_factory=list)
    ignored_inputs: list[str] = field(default_factory=list)
    country_used: str | None = None
    title_language_used: str | None = None
    operational: bool = False


class OccupationResolver:
    def __init__(self, graph: OccupationGraph, aliases: AliasStore, *, coverage=None, language_coverage=None, registry=None) -> None:
        self._g, self._a, self._cov, self._lang, self._reg = graph, aliases, coverage, language_coverage, registry
        self._joiner = GraphResolver(graph)

    # ------------------------------------------------------------------------------------------------------------------------------- public
    def resolve(self, req: MultilingualRequest) -> MultilingualResult:
        res = MultilingualResult(ResolutionOutcome.INSUFFICIENT_CONTEXT, country_used=req.country)
        if req.seniority:
            res.ignored_inputs.append("seniority_does_not_change_occupation_identity")
        if req.country and self._cov is not None:
            row = self._cov.get(req.country)
            if row is None or row["taxonomy_level"] == "unsupported":
                return self._done(res, ResolutionOutcome.UNSUPPORTED, reasons=["country_not_supported"])
        lang = None
        if req.title_language is not None:
            try:
                lang = normalize_language_tag(req.title_language)
            except ValueError:
                lang = "malformed"
            res.title_language_used = lang
        if req.known_occupation_keys:
            out = self._by_known_keys(req, res)
            if out is not None:
                return out
        if req.taxonomy_code:
            return self._by_code(req, res, lang)
        if req.title and normalize_label(req.title):
            return self._by_title(req, res, lang)
        return self._done(res, ResolutionOutcome.INSUFFICIENT_CONTEXT, reasons=["no_title_or_code"], context_needed=["title", "taxonomy_code"])

    # ------------------------------------------------------------------------------------------------------------------------------ identity paths
    def _by_known_keys(self, req: MultilingualRequest, res: MultilingualResult) -> MultilingualResult | None:
        found: dict[str, dict] = {}
        for k in req.known_occupation_keys:
            n = self._g.get(k) or self._g.find_by_legacy_key(k)
            if n:
                found[n["occupation_key"]] = n
        if not found:
            return None
        cands = [MultilingualCandidate(n["occupation_key"], n["canonical_label"], "known_key") for n in found.values()]
        if len(cands) == 1:
            return self._done(res, ResolutionOutcome.RESOLVED, cands, reasons=["known_canonical_key"])
        return self._done(res, ResolutionOutcome.AMBIGUOUS, cands, reasons=["several_known_keys"])

    def _by_code(self, req: MultilingualRequest, res: MultilingualResult, lang: str | None) -> MultilingualResult:
        if not req.taxonomy_scheme:
            return self._done(res, ResolutionOutcome.INSUFFICIENT_CONTEXT, reasons=["code_without_taxonomy"], context_needed=["taxonomy_scheme"])
        scheme, ed, code = req.taxonomy_scheme, req.taxonomy_edition, req.taxonomy_code.strip()
        hits = self._g.find_by_identifier(scheme, code, ed)
        grade = "code_exact"
        if not hits and scheme == "isco":
            restored, why = restore_isco_zero_padding(code, lambda c: bool(self._g.find_by_identifier("isco", c, ed)))
            if restored:
                hits, grade = self._g.find_by_identifier("isco", restored, ed), "code_zero_padding_restored"
                res.warnings.append(f"isco_zero_padding_restored:{code}->{restored}")
            elif why == "ambiguous_padding":
                return self._done(res, ResolutionOutcome.AMBIGUOUS, reasons=["ambiguous_zero_padding"], context_needed=["taxonomy_code"])
        if not hits:
            return self._done(res, ResolutionOutcome.NOT_FOUND, reasons=["identifier_not_in_graph"])
        keys = {h["occupation_key"] for h in hits}
        cands = [MultilingualCandidate(h["occupation_key"], h["canonical_label"], grade, {"scheme": h["scheme"], "edition": h["edition"], "code": code}) for h in hits]
        if len(keys) > 1:
            return self._done(res, ResolutionOutcome.AMBIGUOUS, cands, reasons=["code_exists_in_several_editions_with_different_occupations" if ed is None else "identifier_maps_to_several_occupations"],
                              context_needed=["taxonomy_edition"] if ed is None else [])
        if req.title and normalize_label(req.title):                                      # a conflicting title never overrides an official code
            titled = {h["occupation_key"] for h in self._alias_hits(req)}
            if titled and keys.isdisjoint(titled):
                res.warnings.append("title_conflicts_with_official_code")
        return self._done(res, ResolutionOutcome.RESOLVED, cands[:1], reasons=["official_code"])

    # ------------------------------------------------------------------------------------------------------------------------------- title path
    def _alias_hits(self, req: MultilingualRequest) -> list[dict[str, Any]]:
        hits = self._a.lookup(req.title)
        folded = False
        if not hits:
            hits, folded = self._a.lookup(req.title, folded=True), True
        out = []
        for h in hits:
            if req.taxonomy_edition and h["edition_ref"] and req.taxonomy_scheme and h["edition_ref"] != f"{req.taxonomy_scheme}@{req.taxonomy_edition}":
                continue                                                                # an edition-specific alias is not valid for another (or an unknown) edition
            if h.get("country_applicability") and (req.country or "").strip().upper() not in {c.upper() for c in h["country_applicability"]}:
                continue                                                                # a country-scoped alias is never valid for another (or an unstated) country
            out.append({**h, "_folded": folded})
        return out

    def _by_title(self, req: MultilingualRequest, res: MultilingualResult, lang: str | None) -> MultilingualResult:
        if lang == "malformed":
            return self._done(res, ResolutionOutcome.UNSUPPORTED, reasons=["malformed_language_identifier"])
        if lang and lang != "und" and self._lang is not None and not self._lang.resolver_supports(lang):
            return self._done(res, ResolutionOutcome.UNSUPPORTED, reasons=["title_language_not_supported"])
        hits = self._alias_hits(req)
        canonical = [] if hits else [{"occupation_key": n["occupation_key"], "canonical_label": n["canonical_label"], "language": "und", "_canonical": True, "_folded": False,
                                      "alias_type": "canonical_label", "qualification_status": "unqualified", "source_ref": "", "source_origin": None, "evidence_eligible_origin": False}
                                     for n in self._g.find_by_label(req.title)]
        pool = hits or canonical
        if not pool:
            return self._done(res, ResolutionOutcome.NOT_FOUND, reasons=["title_not_in_graph"])
        selected, grade_override = self._select_by_language(pool, req, lang, res)
        if selected is None:
            return res
        selected = self._in_requested_taxonomy(selected, req)
        if not selected:
            return self._done(res, ResolutionOutcome.NOT_FOUND, reasons=["title_not_in_requested_taxonomy"])
        by_occ: dict[str, list[dict]] = {}
        for h in selected:
            by_occ.setdefault(h["occupation_key"], []).append(h)
        cands = [self._candidate(k, hs, grade_override) for k, hs in sorted(by_occ.items())]
        if len(cands) == 1:
            only = cands[0]
            if only.grade in ("alias_language_unverified", "canonical_label_language_unknown") and not req.accept_unverified_language:
                return self._done(res, ResolutionOutcome.INSUFFICIENT_CONTEXT, cands, reasons=["alias_language_unverified"], context_needed=["alias_language_metadata"])
            return self._done(res, ResolutionOutcome.RESOLVED, cands, reasons=["unique_alias_match"])
        if self._joiner._joined_by_verified_equivalence([c.occupation_key for c in cands]):
            return self._done(res, ResolutionOutcome.RESOLVED, cands[:1], reasons=["several_nodes_joined_by_verified_equivalence"])
        narrowed = self._narrow(cands, by_occ, req)
        if narrowed is not None and len(narrowed) == 1:
            return self._done(res, ResolutionOutcome.RESOLVED, narrowed, reasons=["narrowed_by_curated_context"])
        if narrowed:
            cands = narrowed
            res.reasons.append("context_narrowed_but_ambiguous")
        elif narrowed is not None:
            res.reasons.append("context_matched_no_candidate")
        needed = ["role_context", "taxonomy_code"] + ([] if req.title_language else ["title_language"])
        return self._done(res, ResolutionOutcome.AMBIGUOUS, cands, reasons=["title_matches_several_distinct_occupations"], context_needed=needed)

    def _select_by_language(self, pool: list[dict], req: MultilingualRequest, lang: str | None, res: MultilingualResult):
        if lang and lang != "und":
            same = [h for h in pool if h["language"] == lang]
            unk = [h for h in pool if h["language"] == "und"]
            other = [h for h in pool if h["language"] not in (lang, "und")]
            if same:
                if {h["occupation_key"] for h in other} - {h["occupation_key"] for h in same}:
                    res.warnings.append("same_text_in_other_languages_ignored")
                return same, None
            if req.allow_cross_language and other:
                return other, "alias_cross_language"
            if unk:
                return unk, "alias_language_unverified"
            if other:
                self._done(res, ResolutionOutcome.NOT_FOUND, reasons=["title_exists_only_in_other_languages"])
                return None, None
            return pool, None
        langs = {h["language"] for h in pool if h["language"] != "und"}
        if len(langs) > 1:
            res.warnings.append("title_matches_aliases_in_several_languages")
        if all(h["language"] == "und" for h in pool):
            return pool, "alias_language_unverified"
        return pool, None

    def _in_requested_taxonomy(self, selected: list[dict], req: MultilingualRequest) -> list[dict]:
        """With a requested taxonomy (and edition), keep only occupations that actually hold an identifier there; otherwise the pool is unchanged."""
        if not req.taxonomy_scheme:
            return selected
        keep: dict[str, bool] = {}
        for h in selected:
            k = h["occupation_key"]
            if k not in keep:
                keep[k] = any(i["scheme"] == req.taxonomy_scheme and (req.taxonomy_edition is None or i["edition"] == req.taxonomy_edition) for i in self._g.identifiers(k))
        return [h for h in selected if keep[h["occupation_key"]]]

    def _candidate(self, key: str, hs: list[dict], override: str | None) -> MultilingualCandidate:
        best = sorted(hs, key=lambda h: (0 if h["alias_type"].startswith("official") else 1, h.get("alias_type", ""), h.get("language", "")))[0]
        if best.get("_canonical"):
            grade = "canonical_label_language_unknown"
        elif override:
            grade = override
        elif best["_folded"]:
            grade = "alias_folded"
        elif best["language"] == "und":
            grade = "alias_language_unverified"
        else:
            grade = "alias_exact"
        eligible = bool(self._reg and best.get("source_ref") and self._reg.can_serve_as_evidence(best["source_ref"]))
        evidence = {"language": best["language"], "alias_type": best["alias_type"], "qualification_status": best["qualification_status"], "source_ref": best.get("source_ref", ""),
                    "source_origin": best.get("source_origin"), "evidence_eligible": eligible, "matched_aliases": len(hs)}
        return MultilingualCandidate(key, hs[0]["canonical_label"], grade, evidence)

    def _narrow(self, cands: list[MultilingualCandidate], by_occ: dict[str, list[dict]], req: MultilingualRequest) -> list[MultilingualCandidate] | None:
        """Curated context terms only. None = no usable context was supplied; [] = context supplied but matched no candidate."""
        ctx = normalize_label(f"{req.role_context or ''} {req.industry or ''}")
        if not ctx:
            return None
        padded = f" {ctx} "
        out = []
        for c in cands:
            terms = {t for h in by_occ[c.occupation_key] for t in h.get("context_terms", [])}
            if any(f" {t} " in padded for t in terms):
                out.append(c)
        return out

    # ------------------------------------------------------------------------------------------------------------------------------- result
    def _done(self, res: MultilingualResult, outcome: ResolutionOutcome, cands: list[MultilingualCandidate] | None = None, *, reasons: list[str] | None = None,
              context_needed: list[str] | None = None) -> MultilingualResult:
        res.outcome = outcome
        res.candidates = list(cands or [])
        res.reasons = [*res.reasons, *(reasons or [])]
        res.context_needed = list(context_needed or [])
        res.operational = bool(outcome is ResolutionOutcome.RESOLVED and res.candidates and res.candidates[0].evidence.get("evidence_eligible")
                               and res.candidates[0].evidence.get("qualification_status") == "qualified")
        return res
