"""Deterministic structured extraction (Capstone P4, §13).

Rule-based, NO LLM: every claim's text is a VERBATIM span from the source document, so
nothing is invented or inferred. Each claim carries provenance (page/section) back to the
segment it came from. LLM-assisted extraction is a possible later, authorised enhancement;
P4 keeps extraction deterministic so it is offline, testable and injection-proof (the
document never reaches a prompt). The candidate reviews every claim before it is reusable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.documents.parsing import ParseResult

__all__ = ["ExtractedClaim", "extract_claims", "MAX_CLAIMS"]

MAX_CLAIMS = 80
_MAX_PER_TYPE = 25

_TITLE_WORDS = (
    "engineer", "developer", "manager", "analyst", "designer", "lead", "director",
    "consultant", "architect", "scientist", "specialist", "administrator", "officer",
    "nurse", "teacher", "accountant", "coordinator", "head of", "vp", "founder",
)
_EDU_WORDS = (
    "bachelor", "master", "msc", "bsc", "b.sc", "m.sc", "mba", "phd", "diploma",
    "degree", "university", "college", "certified", "certification", "certificate",
)
_SKILL_HEADERS = ("skills", "technologies", "technical skills", "tech stack", "competencies")
_METRIC_RE = re.compile(r"(\d+\s?%|[$€£]\s?\d|\b\d[\d,\.]*\s?(k|m|bn|million|billion)\b|\b\d+\+?\s?(years?|yrs?)\b)", re.I)
_ACHIEVEMENT_VERBS = (
    "led", "delivered", "increased", "reduced", "improved", "launched", "built",
    "designed", "achieved", "grew", "saved", "managed", "drove", "shipped", "created",
)
_SPLIT = re.compile(r"[•·]|(?:^|\s)[-*]\s|,\s|\|\s|;\s")


@dataclass(frozen=True)
class ExtractedClaim:
    claim_type: str
    text: str
    page: int | None = None
    section: str | None = None


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" •·-*|;,").strip()


def _classify(line: str) -> str | None:
    low = line.lower()
    if any(w in low for w in _EDU_WORDS):
        return "education"
    if any(w in low for w in _TITLE_WORDS):
        return "experience"
    if _METRIC_RE.search(line) or any(low.startswith(v) or f" {v} " in f" {low} " for v in _ACHIEVEMENT_VERBS):
        return "achievement"
    return None


def extract_claims(parse: ParseResult, *, category: str) -> list[ExtractedClaim]:
    """Extract verbatim, provenance-bearing claims. Deterministic; never fabricates."""
    claims: list[ExtractedClaim] = []
    seen: set[tuple[str, str]] = set()
    per_type: dict[str, int] = {}

    def add(ctype: str, text: str, page, section) -> None:
        text = _clean(text)
        if len(text) < 3 or len(text) > 400:
            return
        key = (ctype, text.lower())
        if key in seen or per_type.get(ctype, 0) >= _MAX_PER_TYPE or len(claims) >= MAX_CLAIMS:
            return
        seen.add(key)
        per_type[ctype] = per_type.get(ctype, 0) + 1
        claims.append(ExtractedClaim(claim_type=ctype, text=text, page=page, section=section))

    for seg in parse.segments:
        lines = [ln for ln in seg.text.splitlines() if ln.strip()]
        i = 0
        while i < len(lines):
            raw = lines[i]
            low = raw.lower().strip().rstrip(":")
            # A "Skills:" header → treat the same or following line's tokens as skills.
            if low in _SKILL_HEADERS or any(low.startswith(h) for h in _SKILL_HEADERS):
                payload = raw.split(":", 1)[1] if ":" in raw else (lines[i + 1] if i + 1 < len(lines) else "")
                for tok in _SPLIT.split(payload):
                    add("skill", tok, seg.page, seg.section)
                i += 1
                continue
            ctype = _classify(raw)
            if ctype:
                add(ctype, raw, seg.page, seg.section)
            i += 1

    return claims
