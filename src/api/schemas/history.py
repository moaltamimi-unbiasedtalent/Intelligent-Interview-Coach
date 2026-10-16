"""History API schemas (read-only, user-scoped)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InterviewSummary(BaseModel):
    """A row in the user's interview history (safe list view)."""

    id: int
    model_config = {"extra": "allow"}  # repository summary carries safe fields


class HistoryAccessOut(BaseModel):
    """What the SERVER decided about this caller's history view (W12.4D-P3). The frontend only displays it; it never computes or grants access.
    ``restricted`` is false while the rollout gate is disabled (everyone sees everything, as before). ``hidden_count`` is a count only."""

    restricted: bool = False
    window: int | None = None
    hidden_count: int = 0


class InterviewListResponse(BaseModel):
    interviews: list[dict] = Field(default_factory=list)
    access: HistoryAccessOut = Field(default_factory=HistoryAccessOut)


class InterviewDetailResponse(BaseModel):
    interview: dict
