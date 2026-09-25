"""Bounded candidate-feedback taxonomy (Capstone P6/E7, §21/§33).

A closed, safe vocabulary of the ISSUE categories a piece of feedback can be about. It is
the controlled bridge between raw candidate feedback (helpful/not_helpful + optional
comment) and the governed Feedback Intelligence loop: signals are classified into these
categories, aggregated, and turned into human-reviewed improvement candidates. The
taxonomy never infers sensitive personal traits and never carries candidate content.

This is deliberately a governed-layer vocabulary. Candidate-facing category SELECTION in
the UI (a dropdown) is a separate follow-up (needs a DB column + i18n) and is tracked in
the quality register; the taxonomy + learning loop ship now.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["FeedbackCategory", "CATEGORY_TO_CHANGE_AREA", "normalize_category"]


class FeedbackCategory(str, Enum):
    INCORRECT = "incorrect"
    IRRELEVANT = "irrelevant"
    TOO_VERBOSE = "too_verbose"
    TOO_BRIEF = "too_brief"
    MISSING_EVIDENCE = "missing_evidence"
    POOR_SOURCE = "poor_source"
    TOOL_CHOICE = "tool_choice"
    LANGUAGE_QUALITY = "language_quality"
    RETRIEVAL_PROBLEM = "retrieval_problem"
    PRACTICE_QUALITY = "practice_quality"
    OTHER = "other"

    @classmethod
    def from_value(cls, value: str | None) -> "FeedbackCategory":
        try:
            return cls(str(value).strip().lower())
        except (ValueError, AttributeError):
            return cls.OTHER


# Each category maps to the engineering CHANGE AREA an improvement would touch — used to
# route an improvement candidate to the right kind of experiment (never auto-applied).
CATEGORY_TO_CHANGE_AREA: dict[FeedbackCategory, str] = {
    FeedbackCategory.INCORRECT: "grounding",
    FeedbackCategory.IRRELEVANT: "retrieval",
    FeedbackCategory.TOO_VERBOSE: "ux",
    FeedbackCategory.TOO_BRIEF: "ux",
    FeedbackCategory.MISSING_EVIDENCE: "retrieval",
    FeedbackCategory.POOR_SOURCE: "knowledge",
    FeedbackCategory.TOOL_CHOICE: "tool_policy",
    FeedbackCategory.LANGUAGE_QUALITY: "prompt",
    FeedbackCategory.RETRIEVAL_PROBLEM: "retrieval",
    FeedbackCategory.PRACTICE_QUALITY: "interview_practice",
    FeedbackCategory.OTHER: "evaluation",
}


def normalize_category(value: str | None) -> str:
    """Return a valid taxonomy value (unknown/blank → 'other')."""
    return FeedbackCategory.from_value(value).value
