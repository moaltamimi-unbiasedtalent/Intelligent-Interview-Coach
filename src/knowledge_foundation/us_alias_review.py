"""P10C-F2A-R: engineering evidence review of the curated US alias proposals and of the two unresolved market titles. Every judgement below is an ENGINEERING RECOMMENDATION for a named human
alias reviewer, never an approval. Evidence is limited to the already-approved official SOC 2018 structure and definitions (public text, quoted by code); nothing is acquired and no model
knowledge is used as evidence. Word containment (the proposal rule) is NOT treated as sufficient: each review reads the target definition, names the competing SOC occupations, states the
relationship in the existing vocabulary and records the scope risk."""

from __future__ import annotations

from typing import Any

from src.knowledge_foundation.us_sources import SocNode

__all__ = ["RECOMMENDATIONS", "build_alias_reviews", "REVIEW_VERSION"]

REVIEW_VERSION = "p10c-f2ar-alias-review/1"
RECOMMENDATIONS = ("APPROVE_RECOMMENDED", "CONDITIONAL_APPROVAL_RECOMMENDED", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE")

# relationship values reuse the existing alias vocabulary: ``exact`` (a grammatical variant of the official title), ``narrower`` (the market title is narrower than the occupation),
# ``context_dependent`` (valid only with context), ``ambiguous`` (several occupations), ``unsupported`` (no evidence). Graph relationship types (broader/narrower/related) are untouched.
_REVIEWS: list[dict[str, Any]] = [
    {"case": "pc_compensation_187", "title": "Software Developer", "target": "15-1252", "relationship": "exact", "recommendation": "APPROVE_RECOMMENDED",
     "competing": ["15-1251", "15-1253", "15-1254", "15-1299"],
     "scope_finding": "The target's official definition (research, design and develop computer and network software; analyse user needs; enhance existing software) is what the market title names. SOC separates programmers, QA testers and web developers into their own occupations, so those are neighbours, not alternatives for this title.",
     "overbroad_risk": "low: market usage sometimes includes web developers or programmers, which SOC classifies separately; the alias maps only to the SOC-defined occupation.", "context_required": None, "conditions": []},
    {"case": "pc_compensation_195", "title": "Human Resources Manager", "target": "11-3121", "relationship": "exact", "recommendation": "APPROVE_RECOMMENDED",
     "competing": ["11-3111", "11-3131", "11-1021"],
     "scope_finding": "The definition (plan, direct or coordinate human resources activities and staff) matches the market title; the definition itself excludes the specialised compensation-and-benefits and training-and-development managers, which keep their own codes.",
     "overbroad_risk": "low: a specialised HR manager is a SOC neighbour, not covered by this alias.", "context_required": None, "conditions": []},
    {"case": "pc_compensation_207", "title": "Sales Manager", "target": "11-2022", "relationship": "exact", "recommendation": "APPROVE_RECOMMENDED",
     "competing": ["11-2021", "41-1012", "41-1011"],
     "scope_finding": "The definition (plan, direct or coordinate distribution of a product or service to the customer; sales territories, quotas and goals; training sales representatives) matches the market title. Marketing managers and first-line sales supervisors are separate occupations.",
     "overbroad_risk": "low to moderate: informal use of the title for first-line sales supervisors falls under 41-1011 and 41-1012.", "context_required": None, "conditions": []},
    {"case": "pc_compensation_199", "title": "Accountant", "target": "13-2011", "relationship": "narrower", "recommendation": "CONDITIONAL_APPROVAL_RECOMMENDED",
     "competing": ["13-2082", "13-2081", "43-3031"],
     "scope_finding": "SOC publishes ONE occupation, Accountants and Auditors, whose definition covers preparing financial statements and auditing statements prepared by others. The market title is narrower than the occupation, and the wage statistic describes the combined occupation. Tax preparers and bookkeeping clerks are separate occupations.",
     "overbroad_risk": "moderate: a salary shown for 'Accountant' is the combined Accountants and Auditors statistic.",
     "context_required": None, "conditions": ["every answer must carry the scope caveat that the figure is for Accountants and Auditors combined (implemented through the alias limitation text)"]},
    {"case": "pc_compensation_203", "title": "Financial Analyst", "target": "13-2051", "relationship": "context_dependent", "recommendation": "CONDITIONAL_APPROVAL_RECOMMENDED",
     "competing": ["13-2031", "13-2041", "13-2054", "41-3031"],
     "scope_finding": "The official occupation is Financial and Investment Analysts: quantitative analyses of investment programs or financial data, including valuation. Its definition excludes budget analysts, financial risk specialists and securities sales agents, and credit analysts are a separate occupation. Market usage of 'financial analyst' spans those neighbours (for example corporate planning or credit work).",
     "overbroad_risk": "moderate to high: the title may refer to an adjacent SOC occupation depending on the employer function.",
     "context_required": "investment or valuation work (otherwise the occupation scope caveat applies)",
     "conditions": ["every answer must carry the scope caveat naming Financial and Investment Analysts and the excluded neighbouring occupations", "the reviewer decides whether the alias may be the default reading of the bare title or must require investment/valuation context; if neither is acceptable the title should be treated as ambiguous"]},
]

_UNRESOLVED: list[dict[str, Any]] = [
    {"case": "pc_compensation_183", "title": "Data Analyst", "identity_status": "multiple_candidate_occupations", "recommendation": "AMBIGUOUS",
     "candidates": ["15-2051", "15-2041", "15-2031", "13-1111", "15-1211", "13-1161"],
     "finding": "SOC 2018 has no occupation titled Data Analyst. Several occupations are defined around analysing data (data mining and modelling; statistical methods; mathematical optimisation; organisational studies; systems analysis; market research), and nothing in the approved sources says which one the market title denotes. A unique identity is not supported; a context-based identity would need the analyst's field, which is not known.",
     "safe_behaviour": "no alias; the resolver keeps returning not_found; a product contract could ask for occupational context, which is a product decision",
     "needed_for_resolution": "an approved occupational-title source that evidences the title, or candidate-supplied context plus an owner-approved ambiguity handling rule"},
    {"case": "pc_compensation_191", "title": "Product Manager", "identity_status": "multiple_candidate_occupations_context_dependent", "recommendation": "INSUFFICIENT_EVIDENCE",
     "candidates": ["11-2021", "11-3021", "11-1021", "13-1082", "11-9199"],
     "finding": "SOC 2018 has no Product Manager occupation. The official definition of Marketing Managers mentions overseeing product development, and Computer and Information Systems Managers, General and Operations Managers, Project Management Specialists and Managers, All Other are conceivable homes depending on industry. The approved sources contain no evidence that selects one; a context-based identity (software versus consumer products) is conceivable but unsupported today.",
     "safe_behaviour": "no alias; abstention preserved",
     "needed_for_resolution": "an approved occupational-title source that evidences the title, or an owner policy on context-based identity with candidate-supplied context"},
]


def _def(definitions: dict[str, dict[str, str]], code: str, n: int = 320) -> str:
    return definitions.get(code, {}).get("definition", "")[:n]


def build_alias_reviews(structure: list[SocNode], definitions: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Attach the official labels and definition excerpts to the curated judgements, verifying that every referenced code exists in the SOC structure. Raises if one does not."""
    by = {n.code: n for n in structure}

    def lab(code: str) -> dict[str, str]:
        if code not in by:
            raise ValueError(f"unknown SOC code in an alias review: {code}")
        return {"code": code, "label": by[code].title, "level": by[code].level, "definition_excerpt": _def(definitions, code, 240)}

    aliases = []
    for r in _REVIEWS:
        t = lab(r["target"])
        aliases.append({**r, "version": REVIEW_VERSION, "taxonomy": "soc", "taxonomy_edition": "2018", "country_applicability": ["US"], "target_detail": {**t, "definition_excerpt": _def(definitions, r["target"], 420)},
                        "competing_detail": [lab(c) for c in r["competing"]], "status": "ENGINEERING_RECOMMENDATION_ONLY (no human decision exists)"})
    unresolved = [{**u, "version": REVIEW_VERSION, "candidate_detail": [lab(c) for c in u["candidates"]], "status": "ENGINEERING_RECOMMENDATION_ONLY (no human decision exists)"} for u in _UNRESOLVED]
    return {"version": REVIEW_VERSION, "aliases": aliases, "unresolved_titles": unresolved,
            "counts": {k: sum(1 for a in aliases + unresolved if a["recommendation"] == k) for k in RECOMMENDATIONS}}
