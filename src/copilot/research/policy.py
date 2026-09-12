"""Deterministic freshness/company-intent heuristic for external research (Phase 7F, §44).

This is an ADVISORY signal for evaluation and documentation — it is NOT the authoritative
decision. At runtime, Mo (the LLM) decides IF external research is needed; this heuristic only
lets the deterministic test-suite assert local-first behaviour (a general skills question should
NOT warrant external research; a "currently advertised salary" question may). It is intentionally
conservative: absent a clear freshness/company signal, it returns needs_external=False so the
default stays local-first (§3/§45).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.copilot.research.models import ResearchIntent

# Freshness signals (current/live/company-specific). Word-boundary matched, case-insensitive.
_FRESHNESS = (
    "right now", "currently", "current ", "today", "this week", "latest", "recent",
    "recently", "at the moment", "these days", "hiring", "advertised", "advert", "openings",
    "vacanc", "job market", "in the market", "actively", "live ",
)
_SALARY = ("salary", "salaries", "pay", "wage", "compensation", "earn")
_COMPANY = ("this company", "the company", "their careers", "careers page", "about page",
            "company website", "company's")


def _has(text: str, needles) -> bool:
    return any(n in text for n in needles)


@dataclass
class ExternalNeed:
    needs_external: bool
    intent: ResearchIntent | None
    reason: str


def classify_external_need(query: str, *, has_company_url: bool = False) -> ExternalNeed:
    """Heuristic: would this question benefit from bounded current-market/company research?

    Returns a suggested :class:`ResearchIntent` when so. Historical/official statistical questions
    and general occupation/skill questions return needs_external=False (local-first)."""
    q = " " + re.sub(r"\s+", " ", (query or "").lower()).strip() + " "

    # Explicit company URL + company-context phrasing → company research.
    if has_company_url and _has(q, _COMPANY + ("careers", "about", "culture", "values")):
        return ExternalNeed(True, ResearchIntent.COMPANY_CONTEXT, "explicit company url + company intent")

    fresh = _has(q, _FRESHNESS)
    # Historical/official statistics stay local even if they mention salary.
    historical = _has(q, ("historical", "official statistic", "average salary", "typical salary",
                          "median salary", "government", "bls", "eurostat", "ons "))

    if fresh and _has(q, _SALARY):
        return ExternalNeed(True, ResearchIntent.ADVERTISED_SALARY, "current + salary")
    if fresh and _has(q, ("hiring", "hire")):
        return ExternalNeed(True, ResearchIntent.HIRING_ACTIVITY, "current hiring")
    if fresh and _has(q, ("vacanc", "openings", "jobs", "roles", "opportunities", "market")):
        return ExternalNeed(True, ResearchIntent.JOB_MARKET, "current job market")
    if _has(q, _COMPANY) and has_company_url:
        return ExternalNeed(True, ResearchIntent.COMPANY_CONTEXT, "company context")
    if historical:
        return ExternalNeed(False, None, "historical/official → local-first")
    if fresh:
        return ExternalNeed(True, ResearchIntent.JOB_MARKET, "freshness signal")
    return ExternalNeed(False, None, "no freshness/company signal → local-first")
