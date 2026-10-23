"""Deterministic retrieval router: pick the knowledge lane for a question.

Obvious intents route deterministically (keyword rules); an optional LLM
classifier is only consulted when the deterministic signal is ambiguous. Nothing
is sent blindly to vector search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.copilot import constants

__all__ = ["RetrievalLane", "RouteDecision", "route_question", "source_priority", "detect_country"]


class RetrievalLane:
    STRUCTURED_ROLE = constants.LANE_STRUCTURED_ROLE
    VECTOR = constants.LANE_VECTOR
    COMPENSATION = constants.LANE_COMPENSATION
    FORECAST = constants.LANE_FORECAST
    MIXED = constants.LANE_MIXED
    COMPETENCY = constants.LANE_COMPETENCY
    CYBERSECURITY = constants.LANE_CYBERSECURITY
    SHORTAGE = constants.LANE_SHORTAGE
    OPENINGS = constants.LANE_OPENINGS
    SENIORITY = constants.LANE_SENIORITY
    TRANSITION = constants.LANE_TRANSITION
    EDUCATION = constants.LANE_EDUCATION
    TRAINING = constants.LANE_TRAINING
    CERTIFICATION = constants.LANE_CERTIFICATION
    LICENCE = constants.LANE_LICENCE
    CURRENT_VACANCY = constants.LANE_CURRENT_VACANCY
    SHORT_TERM_OUTLOOK = constants.LANE_SHORT_TERM_OUTLOOK


@dataclass
class RouteDecision:
    lane: str
    reason: str
    confidence: float = 1.0


_COMP = re.compile(r"\b(salary|salaries|earn|earns|earning|pay|paid|wage|wages|compensation|income|remuneration|how much)\b", re.I)
_ROLE = re.compile(
    r"\b(responsibilities|duties|tasks|day.to.day|role of)\b|what\s+(?:does|do)\s+.*\bdo\b",
    re.I,
)
_SKILL = re.compile(r"\b(skills?|competenc|capabilit|knowledge|proficienc)\b", re.I)
_TREND = re.compile(r"\b(demand|grow|growth|growing|outlook|trend|trends|future|forecast|projected|decline)\b", re.I)

# New, more specific lanes. These are checked BEFORE the generic role/skill/trend
# rules, but each is written narrowly so existing generic queries still route as
# before (e.g. "what skills do cybersecurity analysts need?" stays structured_role).
_TRANSITION = re.compile(
    r"\b(transition|transitioning|switch|switching|move|moving|pivot|change career|career change|from\s+.+\s+to)\b.*\b(role|career|job|into|to)\b",
    re.I,
)
_SHORTAGE = re.compile(r"\b(shortage|shortages|hard[- ]to[- ]fill|talent gap|skills gap|bottleneck occupation)\b", re.I)
_OPENINGS = re.compile(r"\b(job openings|openings|vacancies|replacement demand|how many (?:jobs|roles|positions))\b", re.I)
_CYBER = re.compile(
    r"\b(cyber ?security|cyber|information security|infosec)\b.*\b(responsibilit|task|duties|work role|incident|framework|nice)"
    r"|\bincident respon(?:se|der|ders|ding)\b",
    re.I,
)
_DIGITAL = re.compile(r"\b(digital)\b.*\b(competenc|capabilit|literac|skill)", re.I)
_SENIORITY = re.compile(
    r"\b(behaviours?|leadership expectation|seniority|success profile|grade|career level"
    r"|what makes a (?:senior|junior|lead|principal)"
    r"|expected at (?:a |an )?(?:senior|junior|lead|principal|entry)"
    r"|at (?:a |an )?(?:senior|junior|lead|principal) \w+ level)\b",
    re.I,
)
_TECH = re.compile(r"\b(software|tools?|technolog|tech stack|applications? (?:used|for)|systems? (?:used|for))\b", re.I)
_LICENCE = re.compile(r"\b(licen[cs]|licensure|registration to practi[sc]e)", re.I)
_CERT = re.compile(r"\b(certif|credential|accreditation)", re.I)
_EDUCATION = re.compile(r"\b(degree|education|qualification needed|what (?:degree|education)|do i need a degree|study to become|major)\b", re.I)
_TRAINING = re.compile(r"\b(training|apprenticeship|on[- ]the[- ]job|work experience|how much experience|prior experience)\b", re.I)
_CURRENT_VACANCY = re.compile(r"\b(right now|currently hiring|current (?:demand|vacanc)|hiring now|job postings?|in demand right now|demand like)\b", re.I)
_SHORT_OUTLOOK = re.compile(r"\b(short[- ]term outlook|short[- ]term demand|near[- ]term|next (?:year|few years))\b", re.I)

# Country detection for geographic source precedence. The names live in ``countries`` (P10D): any EXPLICITLY named country is detected, in the
# supported product languages, so the structured lanes can abstain instead of substituting another country's statistics. A language never implies one.
from src.copilot.knowledge.countries import detect_country_code


def detect_country(query: str) -> str | None:
    """Best-effort country/region code from the question, or None if unspecified (never inferred from the language)."""
    return detect_country_code(query)


def source_priority(country: str | None) -> list[str]:
    """Ordered source ids to prefer for a country-specific question.

    Country-specific official statistics outrank generic international material;
    an unknown country returns the EU/international default order.
    """
    if country and country in constants.COUNTRY_SOURCE_PRIORITY:
        return list(constants.COUNTRY_SOURCE_PRIORITY[country])
    return list(constants.COUNTRY_SOURCE_PRIORITY["EU"])


def _english_rules(text: str) -> RouteDecision | None:
    """The deterministic English keyword rules; ``None`` when none applies (the caller falls back to the classifier or the default lane)."""
    # Specific lanes first (narrowly scoped so they don't shadow generic queries).
    if _TRANSITION.search(text):
        return RouteDecision(RetrievalLane.TRANSITION, "career transition comparison", 0.85)
    if _SHORTAGE.search(text):
        return RouteDecision(RetrievalLane.SHORTAGE, "labour/skills shortage terms", 0.9)
    if _OPENINGS.search(text):
        return RouteDecision(RetrievalLane.OPENINGS, "job openings / replacement demand", 0.9)
    if _CYBER.search(text):
        return RouteDecision(RetrievalLane.CYBERSECURITY, "cybersecurity work-role terms (NICE)", 0.85)
    if _DIGITAL.search(text):
        return RouteDecision(RetrievalLane.COMPETENCY, "digital competency terms (DigComp)", 0.8)
    # Credential / entry-requirement / real-time lanes (CI-PH3).
    if _LICENCE.search(text):
        return RouteDecision(RetrievalLane.LICENCE, "occupational licence terms", 0.85)
    if _CERT.search(text):
        return RouteDecision(RetrievalLane.CERTIFICATION, "professional certification terms", 0.85)
    if _EDUCATION.search(text):
        return RouteDecision(RetrievalLane.EDUCATION, "entry-education terms", 0.8)
    if _CURRENT_VACANCY.search(text):
        return RouteDecision(RetrievalLane.CURRENT_VACANCY, "real-time vacancy/demand terms", 0.8)
    if _SHORT_OUTLOOK.search(text):
        return RouteDecision(RetrievalLane.SHORT_TERM_OUTLOOK, "short-term outlook terms", 0.78)
    if _TRAINING.search(text):
        return RouteDecision(RetrievalLane.TRAINING, "training/experience terms", 0.75)

    comp = bool(_COMP.search(text))
    role = bool(_ROLE.search(text))
    skill = bool(_SKILL.search(text))
    tech = bool(_TECH.search(text))
    trend = bool(_TREND.search(text))
    seniority = bool(_SENIORITY.search(text))

    # Compensation combined with role/skill → mixed (e.g. "skills and pay").
    if comp and (role or skill):
        return RouteDecision(RetrievalLane.MIXED, "compensation + role/skill terms", 0.9)
    if comp:
        return RouteDecision(RetrievalLane.COMPENSATION, "compensation terms", 0.95)
    if trend:
        return RouteDecision(RetrievalLane.FORECAST, "labour-market trend terms", 0.85)
    if seniority and not role and not skill:
        return RouteDecision(RetrievalLane.SENIORITY, "seniority/behaviour framework terms", 0.8)
    if role:
        return RouteDecision(RetrievalLane.STRUCTURED_ROLE, "role/responsibility terms", 0.9)
    if skill:
        return RouteDecision(RetrievalLane.STRUCTURED_ROLE, "skill terms (structured + vector context)", 0.7)
    if tech:
        return RouteDecision(RetrievalLane.STRUCTURED_ROLE, "technology/tools terms (structured)", 0.7)
    return None


def route_question(query: str, llm_classifier=None, language: str | None = None) -> RouteDecision:
    """Return the retrieval lane for ``query``.

    ``llm_classifier`` (optional) is a callable ``str -> lane`` used only when the
    deterministic rules are ambiguous. ``language`` (optional, the language of the QUESTION) selects the keyword table; when omitted a
    deterministic stop-word guess is used (02E, L-ROUTE-1). English questions never reach the localized tables, so English routing is unchanged.
    """
    text = query or ""

    # 02E (L-ROUTE-1): a question with stop-word evidence of a non-English language is matched against that language's keyword table first (same lanes,
    # same precedence). A question with NO language evidence keeps the English rules first (English routing is unchanged) and falls back to the
    # tables only when the English rules found nothing. English questions never reach the localized tables.
    from src.copilot.knowledge.router_lang import has_language_evidence, route_localized

    evidence = language is not None or has_language_evidence(text)
    if evidence:
        localized = route_localized(text, language)
        if localized is not None:
            return RouteDecision(localized[0], localized[1], localized[2])
    decision = _english_rules(text)
    if decision is None and language is None:
        # nothing decided: a question that quotes a foreign keyword inside English text (or has no stop words at all) still reaches the tables
        localized = route_localized(text, any_language=True)
        if localized is not None:
            return RouteDecision(localized[0], localized[1], localized[2])
    if decision is not None:
        return decision

    # Ambiguous: consult the LLM classifier if provided, else default to vector.
    if llm_classifier is not None:
        try:
            lane = llm_classifier(text)
            if lane in constants.RETRIEVAL_LANES:
                return RouteDecision(lane, "llm disambiguation", 0.6)
        except Exception:  # pragma: no cover - classifier must never break routing
            pass
    return RouteDecision(RetrievalLane.VECTOR, "default narrative/vector", 0.5)
