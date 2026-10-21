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
_DIRECTIVES: dict[str, str] = {
    COACHING_STYLE_SUPPORTIVE: (
        "Use an encouraging, constructive coaching tone: lead with what worked, then name gaps "
        "kindly and specifically."
    ),
    COACHING_STYLE_DIRECT: (
        "Use concise, candid coaching language: state the key gaps plainly and briefly, while "
        "remaining respectful."
    ),
    COACHING_STYLE_CHALLENGING: (
        "Use a stretching coaching tone: probe harder, raise the bar and push the candidate to go "
        "deeper, while remaining respectful and fair."
    ),
    # Balanced is the neutral default and needs no directive.
}


def coaching_style_directive(code: str | None) -> str | None:
    """Return a trusted 'coaching tone' directive for an allow-listed style, or None.

    None for balanced/unknown/blank (the default tone needs no directive). The directive text
    comes ONLY from the fixed map above — never from the code string — and always ends with an
    explicit reminder that the tone changes wording, not scoring/evidence/rubric.
    """
    directive = _DIRECTIVES.get((code or "").strip().lower())
    if not directive:
        return None
    return (
        "COACHING STYLE (trusted, chosen from fixed options)\n"
        f"{directive} This changes ONLY how feedback is worded: keep the same rubric, scores, "
        "evidence requirements, grounding and safety - never make feedback harsher or more lenient "
        "because of the tone, and never invent achievements, metrics or outcomes."
    )
