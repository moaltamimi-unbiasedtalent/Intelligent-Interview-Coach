"""Candidate-feedback API schemas (user-scoped, safe projections) — P5.

Requests never accept ``user_id`` — the server owns identity. Responses expose only
safe fields (never the internal user id). The comment is bounded, untrusted user text.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.feedback import FEEDBACK_MAX_COMMENT_CHARS, FeedbackRating, FeedbackSurface


class FeedbackCreateRequest(BaseModel):
    """Submit / update one rating for a logical output (idempotent upsert)."""

    surface: FeedbackSurface = Field(description="Which output is being rated.")
    target_id: str = Field(min_length=1, max_length=128,
                           description="Stable reference to the exact rated output.")
    rating: FeedbackRating = Field(description="helpful | not_helpful.")
    comment: str | None = Field(default=None, max_length=FEEDBACK_MAX_COMMENT_CHARS,
                                description="Optional bounded comment (untrusted text).")


class FeedbackResponse(BaseModel):
    """A single saved feedback record (safe projection)."""

    id: int
    surface: str
    target_id: str
    rating: str
    comment: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeedbackDeleteResponse(BaseModel):
    deleted: bool
