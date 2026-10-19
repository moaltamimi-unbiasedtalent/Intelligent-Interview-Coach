"""Evidence integrity for the candidate knowledge path (P10D-R1): provenance classification, geographic applicability and the deterministic occupation-title test.

One small, pure module that the runtime (``StructuredRetrievalCoordinator``, ``CareerIntelligenceService``) and the coverage evaluator share, so "is this evidence real, applicable and about
what was asked" has ONE answer. It reuses the existing origin vocabulary (``constants.REAL_ORIGINS``, ``ORIGIN_SYNTHETIC_FIXTURE``) and the P10D country policy
(``countries.tag_matches_country``); it adds no database schema, no similarity threshold and no occupation mapping.

The facts it keeps SEPARATE (never collapsed into one score): source identity, country, publication year, dataset edition, ORIGIN class, QUALIFICATION state, runtime eligibility.
A verified real-world source is not human-qualified, engineering validation does not imply runtime authorisation, and an unknown origin is never silently treated as verified.
"""

from __future__ import annotations

import re

from src.copilot import constants
from src.copilot.knowledge.countries import SUPRANATIONAL_TAGS, tag_matches_country

__all__ = ["COUNTRY_BOUND_EVIDENCE_TYPES", "human_qualified_sources", "source_backed_assessment", "ORIGIN_VERIFIED_REAL", "ORIGIN_SYNTHETIC", "ORIGIN_MIXED_UNVERIFIABLE", "ORIGIN_UNKNOWN", "origin_class", "geography_applicable", "looks_like_occupation_title",
           "QUALIFICATION_NOT_QUALIFIED", "evidence_integrity_fields"]

ORIGIN_VERIFIED_REAL = "verified_real_source"
ORIGIN_SYNTHETIC = "synthetic_fixture"
ORIGIN_MIXED_UNVERIFIABLE = "mixed_origin_unverifiable"   # real and synthetic records share one source id and the origin of a single row is not recorded
ORIGIN_UNKNOWN = "unknown_origin"

# The legacy runtime sources carry NO qualification record: none is human-qualified (the P10C qualification workflow is isolated and not wired to the candidate runtime).
QUALIFICATION_NOT_QUALIFIED = "not_qualified"


def origin_class(origins: list[str] | None) -> str:
    """Classify a source from its recorded data origins (the git-ignored origin ledger).

    No record is UNKNOWN (never verified by default). Only fixtures is SYNTHETIC. Only real origins is VERIFIED REAL. Both is MIXED and is NOT counted as verified, because a
    single row cannot be attributed to its real or synthetic origin."""
    if not origins:
        return ORIGIN_UNKNOWN
    real = [o for o in origins if o in constants.REAL_ORIGINS]
    synthetic = [o for o in origins if o == constants.ORIGIN_SYNTHETIC_FIXTURE]
    if real and synthetic:
        return ORIGIN_MIXED_UNVERIFIABLE
    if real:
        return ORIGIN_VERIFIED_REAL
    if synthetic:
        return ORIGIN_SYNTHETIC
    return ORIGIN_UNKNOWN


def geography_applicable(evidence_geography: str | None, asked_country: str | None) -> bool:
    """Is evidence tagged ``evidence_geography`` acceptable for a question that names ``asked_country``?

    No country asked: always. Otherwise the same nation, a global or unspecified tag, or an EU-family tag for a European country (``tag_matches_country``). Another nation's evidence,
    and an EU aggregate for a non-European country, are not applicable. The country is never inferred from a language."""
    if not asked_country:
        return True
    return tag_matches_country(evidence_geography, asked_country)


# --- the deterministic occupation-title test (shared by answer() and retrieve_evidence()) -----------------------------------------------------------------
# A resolver "phrase" is whatever the question scaffolding left over, which for a general question is not an occupation at all ("What soft skills are valued across professions",
# "AI skills rising", "SHRM certification", "someone analysing data day to day"). Treating every such phrase as a named, unsupported occupation withheld legitimate general
# guidance (14 of 48 retrieval-evaluation questions). A phrase counts as a NAMED OCCUPATION only when it looks like a role title: short, with no topic, trend, credential or
# group words.
_GENERIC_TERMS = frozenset("""
skill skills competency competencies capability capabilities knowledge ability abilities trend trends demand supply growth rising rise falling decline outlook forecast shortage
sector sectors industry industries field fields profession professions professional professionals career careers move moving transition job jobs role roles market markets
technology technologies certification certifications certificate licence license credential credentials qualification qualifications requirement requirements
interview interviews question questions answer answers evidence soft hard core duties tasks responsibilities everyday daily day modern future new another other across
someone anyone everyone people person persons worker workers employee employees candidate candidates leader leaders manager managers
""".split())
# Plural group words are not a single title ("people operations professionals", "data roles"). "manager(s)" is deliberately in the list ONLY in the plural form below: a title such as
# "operations manager" must stay a title.
_PLURAL_ONLY = frozenset({"managers", "leaders", "workers", "employees", "candidates", "professionals", "people", "persons"})
_TITLE_STOPWORDS = frozenset(_GENERIC_TERMS - {"manager", "leader", "worker", "employee", "candidate", "professional", "person"})


def looks_like_occupation_title(phrase: str | None) -> bool:
    """True when ``phrase`` could be a single occupation title (so an unmatched one is a genuinely UNSUPPORTED named occupation and an ambiguous one deserves a clarification).

    Deterministic and conservative in the direction of ANSWERING: a phrase with a topic, trend, credential or plural-group word, a single-letter token, or more than four words is not
    treated as a named occupation, so general career guidance stays available. It maps nothing and claims no semantic understanding."""
    tokens = re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", (phrase or "").casefold())
    if not tokens or len(tokens) > 4:
        return False
    if any(len(t) == 1 for t in tokens):
        return False
    if any(t in _TITLE_STOPWORDS or t in _PLURAL_ONLY for t in tokens):
        return False
    return not (set(tokens) & {"what", "which", "how", "why", "when", "who", "does", "do", "is", "are", "can", "should"})


def evidence_integrity_fields(origin: str, country: str | None, geography: str | None, year: int | None, version: str | None, source_id: str) -> dict:
    """The separate provenance facts carried in ``KnowledgeEvidence.metadata`` (no schema change). Nothing here authorises runtime use."""
    return {"integrity": {"source_id": source_id, "country": country or None, "geography": geography or None, "reference_year": year, "edition": version, "origin_class": origin,
                          "qualification": QUALIFICATION_NOT_QUALIFIED, "source_backed": origin == ORIGIN_VERIFIED_REAL}}


# Re-exported so callers need one import for the policy vocabulary.
SUPRANATIONAL = SUPRANATIONAL_TAGS


# Evidence types whose CONTENT is specific to a country (statistics, projections, licensing, the entry-education attribute of a national handbook). Occupation DEFINITIONS (tasks,
# skills, knowledge, activities, technologies, competencies, transitions) are taxonomy content that applies across countries by design and are never country-filtered.
COUNTRY_BOUND_EVIDENCE_TYPES = frozenset({"compensation", "forecast", "openings", "shortage", "vacancy", "licence", "education", "training", "outlook"})


def human_qualified_sources() -> frozenset[str]:
    """Source ids whose evidence is HUMAN-QUALIFIED. Empty: no legacy runtime source has a qualification record, and the P10C qualification workflow is isolated (0 human-qualified
    records) and not wired to the candidate runtime. Returned as data so the coverage evaluator can report metric C from fact rather than assume it."""
    return frozenset()


def source_backed_assessment(evidence: list, asked_country: str | None, origin_of, *, citation_required: bool = False) -> dict:
    """Case-level assessment used by the V2 coverage evaluator (pure; no I/O). ``evidence`` items need ``source_id``, ``evidence_type``, ``country``, ``geography``, ``source_url``.

    ELIGIBLE evidence is real-origin (``verified_real_source``), country-applicable when the evidence type is country-bound, and carries provenance (a source id, and a URL when a citation
    is required). Everything else is reported with a reason. Qualification is reported separately and never implied."""
    eligible, reasons = [], {}
    for e in evidence:
        origin = origin_of(e.source_id)
        reason = None
        if not e.source_id:
            reason = "missing_provenance"
        elif origin == ORIGIN_SYNTHETIC:
            reason = "synthetic_fixture"
        elif origin == ORIGIN_MIXED_UNVERIFIABLE:
            reason = "mixed_origin_unverifiable"
        elif origin != ORIGIN_VERIFIED_REAL:
            reason = "unknown_origin"
        elif e.evidence_type in COUNTRY_BOUND_EVIDENCE_TYPES and asked_country and not (e.country or e.geography):
            reason = "unknown_geography"              # country-bound evidence with no country tag is not proven applicable; no country is ever fabricated for it
        elif e.evidence_type in COUNTRY_BOUND_EVIDENCE_TYPES and not geography_applicable(e.country or e.geography or "", asked_country):
            reason = "wrong_country"
        elif citation_required and not e.source_url:
            reason = "missing_citation_url"
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            eligible.append(e)
    qualified = human_qualified_sources()
    return {"eligible": len(eligible), "total": len(evidence), "reasons": reasons, "synthetic_only": bool(evidence) and all(origin_of(e.source_id) == ORIGIN_SYNTHETIC for e in evidence),
            "human_qualified": bool(eligible) and all(e.source_id.split(":", 1)[0] in qualified for e in eligible)}
