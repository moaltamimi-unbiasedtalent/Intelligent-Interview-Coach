"""Bounded Mo coaching style (Capstone P10B Wave 2).

ONE Mo, configured — not multiple personas. The candidate chooses HOW Mo communicates coaching;
this is a bounded enum mapped to a TRUSTED, repository-authored system directive. The user's raw
choice never reaches the model as free text (only the fixed directive for an allow-listed code
does), mirroring the language-directive pattern in `src/agent/policies.py` / `src/prompts.py`.

CRITICAL BOUNDARY: coaching style affects ONLY the tone/wording of candidate-facing coaching prose.
It must NEVER change factuality, evidence requirements, scoring criteria, the interview rubric,
safety, authorization, model policy, retrieval, HITL, candidate evidence, hiring suitability,
confidence thresholds or any security boundary. A "challenging" style must not score harder; a
"supportive" style must not inflate scores.
"""

from __future__ import annotations

from src.prompt_assets import render, table

__all__ = [
    "COACHING_STYLE_SUPPORTIVE", "COACHING_STYLE_BALANCED", "COACHING_STYLE_DIRECT",
    "COACHING_STYLE_CHALLENGING", "COACHING_STYLES", "DEFAULT_COACHING_STYLE",
    "coaching_style_directive",
]

COACHING_STYLE_SUPPORTIVE = "supportive"
COACHING_STYLE_BALANCED = "balanced"
COACHING_STYLE_DIRECT = "direct"
COACHING_STYLE_CHALLENGING = "challenging"

# Bounded allow-list; anything else is rejected at the boundary and never persisted.
COACHING_STYLES: tuple[str, ...] = (
    COACHING_STYLE_SUPPORTIVE,
    COACHING_STYLE_BALANCED,
    COACHING_STYLE_DIRECT,
    COACHING_STYLE_CHALLENGING,
)
DEFAULT_COACHING_STYLE = COACHING_STYLE_BALANCED

# Trusted, repository-authored directives. The text is fixed here — never composed from user input.
# Each states explicitly that only tone changes, not scoring/evidence — a defence-in-depth reminder
# to the model that reinforces the boundary the code already enforces.
# The directive texts and the wrapper sentence are versioned assets (package 01B):
# prompts/coaching/directives (key: text per allow-listed style; balanced has none) and
# prompts/coaching/wrapper. Balanced is the neutral default and needs no directive.
_CONSUMER = "coaching.style"
_DIRECTIVES: dict[str, str] = table("coaching/directives", _CONSUMER)


def coaching_style_directive(code: str | None) -> str | None:
    """Return a trusted 'coaching tone' directive for an allow-listed style, or None.

    None for balanced/unknown/blank (the default tone needs no directive). The directive text
    comes ONLY from the fixed map above — never from the code string — and always ends with an
    explicit reminder that the tone changes wording, not scoring/evidence/rubric.
    """
    directive = _DIRECTIVES.get((code or "").strip().lower())
    if not directive:
        return None
    return render("coaching/wrapper", _CONSUMER, directive=directive)
