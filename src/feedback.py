"""Candidate feedback — domain vocabulary, bounds and safe DTO (post-Sprint 4, P5).

Feedback is a small, user-scoped rating (helpful / not helpful) plus an optional
bounded comment, attached to ONE logical output the candidate saw: an Agent answer, an
Interview evaluation, or a final report. It stores REFERENCES, a rating and an optional
comment ONLY — never a copy of the answer, prompt, JD, CV, evaluation prose, report,
memory, retrieved evidence, system prompt, provider output or checkpoint.

The comment is UNTRUSTED USER DATA: it is stored and displayed as bounded text and is
NEVER fed back into any prompt, memory, tool or policy (the feedback learning loop is a
human-reviewed engineering process, not autonomous self-modification).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

__all__ = [
    "FeedbackSurface",
    "FeedbackRating",
    "FEEDBACK_MAX_COMMENT_CHARS",
    "FeedbackItem",
    "normalize_comment",
]

FEEDBACK_MAX_COMMENT_CHARS = 1000


class FeedbackSurface(str, Enum):
    """The exact logical outputs a candidate may rate (a closed set)."""

    AGENT_ANSWER = "agent_answer"
    INTERVIEW_EVALUATION = "interview_evaluation"
    FINAL_REPORT = "final_report"

    @classmethod
    def from_value(cls, value: str) -> "FeedbackSurface":
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            allowed = ", ".join(s.value for s in cls)
            raise ValueError(f"Unknown feedback surface. Allowed: {allowed}.") from exc


class FeedbackRating(str, Enum):
    """A deliberately binary rating (no arbitrary strings, no free-form score)."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"

    @classmethod
    def from_value(cls, value: str) -> "FeedbackRating":
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            allowed = ", ".join(r.value for r in cls)
            raise ValueError(f"Unknown rating. Allowed: {allowed}.") from exc


def normalize_comment(comment: str | None) -> str | None:
    """Trim a comment; empty → None. (Length is validated by the service.)"""
    if comment is None:
        return None
    cleaned = comment.strip()
    return cleaned or None


@dataclass
class FeedbackItem:
    """A safe, serialisable view of one feedback record (no internal owner id)."""

    id: int
    user_id: int
    surface: str
    target_id: str
    rating: str
    comment: str | None
    created_at: datetime | None
    updated_at: datetime | None

    def to_public(self) -> dict:
        """Public projection for API/UI — deliberately omits ``user_id``."""
        return {
            "id": self.id,
            "surface": self.surface,
            "target_id": self.target_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
