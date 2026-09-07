"""History API schemas (read-only, user-scoped)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InterviewSummary(BaseModel):
    """A row in the user's interview history (safe list view)."""

    id: int
    model_config = {"extra": "allow"}  # repository summary carries safe fields


class InterviewListResponse(BaseModel):
    interviews: list[dict] = Field(default_factory=list)


class InterviewDetailResponse(BaseModel):
    interview: dict
