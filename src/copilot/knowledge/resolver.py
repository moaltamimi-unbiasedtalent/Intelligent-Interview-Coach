"""Occupation resolution: map a natural question to structured occupations.

Turns "What does a Senior Product Manager earn in Germany?" into candidate
occupations from the RoleRepository, handling aliases (HRBP → HR Business
Partner), punctuation, seniority prefixes and source crosswalks (SOC/ISCO/ESCO/
KldB). It never silently picks between genuinely different occupations — when the
result is ambiguous it returns the ranked candidates so the caller can ask the
user to clarify.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from src.copilot.knowledge.router import source_priority

__all__ = [
    "OccupationCandidate", "ResolvedOccupation",
    "extract_occupation_phrase", "resolve_occupation", "title_variants",
]


# Common alias / synonym expansions (bidirectional intent). Kept small and
# profession-neutral; extend as needed.
_ALIASES = {
    "hrbp": "hr business partner",
    "hr manager": "human resources manager",
    "hr business partner": "human resources business partner",
    "hr director": "human resources director",
    "people director": "human resources director",
    "people partner": "human resources business partner",
    "swe": "software engineer",
    "sw engineer": "software engineer",
    "software developer": "software engineer",
    "developer": "software developer",
    "pm": "product manager",
    "ba": "business analyst",
    "devops": "devops engineer",
    "sre": "site reliability engineer",
    "nursing": "nurse",
}

# Seniority prefixes to strip when matching a base occupation.
_SENIORITY = re.compile(
    r"^\s*(senior|junior|lead|principal|staff|chief|head of|deputy|associate|"
    r"entry[- ]level|graduate|trainee|mid[- ]level)\s+",
    re.I,
)

# Optional article ("a"/"an"/"the") with a real word boundary so "an HR" does
# not leave a dangling "n".
_ART = r"(?:(?:an?|the)\s+)?"

# Question scaffolding to remove when extracting the occupation phrase.
_PATTERNS = [
    re.compile(rf"what (?:does|do) {_ART}(.+?)\s+(?:do|earn|need|require|make)\b", re.I),
    re.compile(rf"(?:responsibilities|duties|tasks|role) of {_ART}(.+?)[\?\.]?$", re.I),
    re.compile(rf"skills? (?:for|of|does|do)\s+{_ART}(.+?)\s+(?:need|require|have)\b", re.I),
    re.compile(rf"(?:salary|pay|wage|compensation|earnings?) (?:for|of)\s+{_ART}(.+?)(?:\s+in\b|[\?\.]?$)", re.I),
    re.compile(rf"(?:how much (?:does|do))\s+{_ART}(.+?)\s+(?:earn|make|get paid)", re.I),
    re.compile(rf"(?:what is|what's) {_ART}(.+?)\s+(?:salary|pay)", re.I),
    re.compile(rf"(?:is|are)\s+{_ART}(.+?)\s+(?:in shortage|expected to|forecast)", re.I),
    re.compile(rf"shortage of\s+{_ART}(.+?)(?:\s+in\b|[\?\.]?$)", re.I),
    re.compile(rf"demand for\s+{_ART}(.+?)(?:\s+(?:expected|is|are|grow|in)\b|[\?\.]?$)", re.I),
    re.compile(rf"(?:openings?|vacancies|demand|shortage|forecast|outlook)\b.*?\bfor\s+{_ART}(.+?)[\?\.]?$", re.I),
    # Credential / entry questions: "... to work/practise as a X", "... for a X".
    re.compile(rf"(?:to\s+(?:work|practi[sc]e|become)\s+(?:as\s+)?){_ART}(.+?)[\?\.]?$", re.I),
    re.compile(rf"(?:licen[cs]e|certif\w*|training|degree|education)\b.*?\bfor\s+{_ART}(.+?)[\?\.]?$", re.I),
    re.compile(rf"\bdoes\s+{_ART}(.+?)\s+(?:need|require|use|do|perform|earn|make)\b", re.I),
]

# Country/qualifier/clause words to trim off a captured phrase tail. These are
# only ever applied to an already-extracted phrase, and are matched from the
# first occurrence onward — kept to words that do not begin a real occupation.
_TRAILING = re.compile(
    r"\s\b(in|the|us|usa|u\.s\.|uk|united states|united kingdom|germany|europe|eu|"
    r"typically|usually|role|position|job|occupation|"
    r"expected|grow|growing|forecast)\b.*$",
    re.I,
)
# Lead-ins that wrap the occupation in labour-market questions.
_LEADIN = re.compile(r"^(?:the\s+)?demand\s+for\s+", re.I)


class OccupationCandidate(BaseModel):
    occupation_code: str
    title: str
    source_id: str
    score: float = 0.0


class ResolvedOccupation(BaseModel):
    phrase: str = ""
    candidates: list[OccupationCandidate] = Field(default_factory=list)
    ambiguous: bool = False

    @property
    def best(self) -> OccupationCandidate | None:
        return self.candidates[0] if self.candidates else None


def _clean(text: str) -> str:
    text = re.sub(r"[^\w\s&/+-]", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def extract_occupation_phrase(query: str) -> str:
    """Best-effort occupation phrase from a natural-language question."""
    q = (query or "").strip()
    for pat in _PATTERNS:
        m = pat.search(q)
        if m:
            phrase = _TRAILING.sub("", _LEADIN.sub("", m.group(1).strip())).strip()
            if phrase:
                return _clean(phrase)
    # Fallback: strip common lead-ins and trailing qualifiers.
    q = re.sub(r"^(what|which|how|tell me about|describe|explain)\b.*?\b(a|an|the)\b", "", q, flags=re.I)
    q = _TRAILING.sub("", _LEADIN.sub("", q)).strip()
    return _clean(q)


def title_variants(phrase: str) -> list[str]:
    """Public alias for :func:`_normalise` — search variants for a title phrase."""
    return _normalise(phrase)


def _normalise(phrase: str) -> list[str]:
    """Return search variants for a phrase (alias-expanded, seniority-stripped)."""
    base = phrase.strip().lower()
    variants = [base]
    if base in _ALIASES:
        variants.append(_ALIASES[base])
    stripped = _SENIORITY.sub("", base).strip()
    if stripped and stripped != base:
        variants.append(stripped)
        if stripped in _ALIASES:
            variants.append(_ALIASES[stripped])
    # Naive singularisation so "nurses"/"analysts" match singular titles.
    for v in list(variants):
        if len(v) > 3 and v.endswith("s") and not v.endswith("ss"):
            variants.append(v[:-1])
    # De-duplicate, keep order.
    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v); out.append(v)
    return out


# Longest occupation-phrase window scanned when the whole extracted phrase does
# not resolve (e.g. verbose keyword queries that embed the role among other terms).
_MAX_WINDOW = 5


def _leading_windows(phrase: str, max_n: int = _MAX_WINDOW):
    """Yield the query's leading word windows, longest first.

    Anchored at the START of the phrase on purpose: in a non-scaffolded keyword
    query a candidate genuinely leads with the role ("Senior Product Manager
    typical responsibilities…", "registered nurse day-to-day duties…"), so the
    leading phrase is the occupation. Scanning every interior window instead would
    pluck a real occupation word out of an otherwise-unrelated phrase
    ("intergalactic vibe *curator*") and invent a role — exactly the wrong-role
    failure the spec forbids. Longest-first so a multi-word occupation is preferred
    over a shorter, noisier prefix; the caller stops at the first length that
    resolves anything.
    """
    tokens = _clean(phrase).split()
    for n in range(min(max_n, len(tokens)), 0, -1):
        yield " ".join(tokens[:n])


# Role-introducing scaffolding: a connective + an article strongly signals that an
# occupation follows, wherever it sits in the query ("… expected of a <role>",
# "for a <role>", "as a <role>", "skills needed by a <role>", "does a <role>…").
# This makes resolution position-agnostic (role at the start, middle or end)
# WITHOUT the "pick any occupation word found somewhere" failure the spec forbids:
# a bare noun with no connective ("intergalactic vibe curator") is never captured.
# "expected of a" is covered by the "of" alternative, "needed by a" by "by",
# "required for a" by "for". The captured phrase runs to the next clause boundary.
_SCAFFOLD = re.compile(
    r"\b(?:of|for|as|by|does|do)\s+(?:a|an|the)\s+([\w][\w\s&/+-]*?)(?=[,.;:?!]|$)",
    re.I,
)


def _scaffolded_candidates(query: str):
    """Yield occupation-candidate phrases that follow a role-introducing connective.

    Each captured phrase begins with the occupation (the connective + article are
    the anchor), so the caller resolves it with the same conservative leading-window
    matching. Multiple matches (e.g. two different roles) all surface, so genuinely
    ambiguous queries still resolve to ambiguity rather than a guess.
    """
    for m in _SCAFFOLD.finditer(query or ""):
        cand = _clean(m.group(1))
        if cand:
            yield cand


def resolve_occupation(repo, query: str, *, country: str | None = None,
                       limit: int = 5) -> ResolvedOccupation:
    """Resolve an occupation from ``query`` using the role repository.

    Candidates are ranked by source precedence for ``country`` (national official
    sources first), then by how closely the title matches the phrase. Ambiguity is
    reported rather than resolved silently.

    Resolution has three general stages (no role, prompt or query is special-cased),
    each tried only when the previous resolved nothing, so clean queries are
    unaffected:

    1. Extract the occupation phrase from the question scaffolding and look it up.
    2. Scaffold-anchored, position-agnostic: find candidates that follow a
       role-introducing connective + article ("… expected of a <role>", "for a
       <role>", "as a <role>") anywhere in the query — this resolves a trailing or
       mid-sentence occupation the Agent may generate.
    3. Leading-window: for a non-scaffolded keyword query that leads with the role
       ("Senior Product Manager typical responsibilities …"), scan the leading
       windows.

    Stages 2 and 3 keep only close (exact/prefix) title matches, so noise never
    invents a role; genuinely different occupations still surface as ambiguous and
    the caller then reports insufficient rather than guessing.
    """
    phrase = extract_occupation_phrase(query)
    if repo is None:
        return ResolvedOccupation(phrase=phrase)

    priority = source_priority(country)

    def _src_rank(sid: str) -> int:
        base = sid.split(":", 1)[0] if sid else sid
        return priority.index(base) if base in priority else len(priority)

    seen: dict[tuple, OccupationCandidate] = {}

    def _collect(variant: str, *, min_match: float = 1.0) -> None:
        """Look up one title variant and record candidates scoring >= ``min_match``."""
        for row in repo.search(variant, limit=limit * 4):
            title = row.get("title", "")
            sid = row.get("source_id", "")
            key = (title.lower(), sid)
            if key in seen:
                continue
            tl = title.lower()
            # Simple lexical closeness: exact > startswith > contains.
            if tl == variant:
                match = 3.0
            elif tl.startswith(variant) or variant.startswith(tl):
                match = 2.0
            else:
                match = 1.0
            if match < min_match:
                continue
            score = match - _src_rank(sid) * 0.1
            seen[key] = OccupationCandidate(
                occupation_code=row.get("occupation_code", ""),
                title=title, source_id=sid, score=score,
            )

    def _collect_leading(text: str) -> None:
        """Collect close matches from ``text``'s leading windows, longest first,
        stopping at the first window length that resolves anything."""
        for window in _leading_windows(text):
            before = len(seen)
            for variant in _normalise(window):
                _collect(variant, min_match=2.0)
            if len(seen) > before:
                break

    # Stage 1: the extracted phrase (unchanged behaviour for scaffolded questions).
    if phrase:
        for variant in _normalise(phrase):
            _collect(variant)

    # Stage 2: scaffold-anchored, position-agnostic. Each candidate begins with the
    # role (the connective + article are the anchor); every candidate is tried so
    # two distinct roles still surface as ambiguous.
    if not seen:
        for cand in _scaffolded_candidates(query):
            _collect_leading(cand)

    # Stage 3: leading-window fallback for occupation-leading keyword queries.
    if not seen:
        _collect_leading(query)

    candidates = sorted(seen.values(), key=lambda c: (-c.score, c.title))[:limit]
    # Ambiguous when the top candidates are materially different occupations
    # (distinct base titles) at a comparable score.
    distinct_titles = {re.sub(r"s$", "", c.title.lower()) for c in candidates}
    ambiguous = (
        len(candidates) > 1
        and len(distinct_titles) > 1
        and abs(candidates[0].score - candidates[1].score) < 0.25
    )
    return ResolvedOccupation(phrase=phrase, candidates=candidates, ambiguous=ambiguous)
