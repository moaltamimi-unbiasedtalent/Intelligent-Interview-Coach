"""Progress API schemas (read-only, user-scoped).

Practice progress derived only from the caller's own completed interviews. It is
practice guidance, never a score or a hiring signal, and invents no metric the
persisted data does not support (unknown values are null).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecentInterview(BaseModel):
    id: int
    target_role: str | None = None
    mode: str | None = None
    status: str | None = None
    questions: int | None = None
    created_at: str | None = None


class ProgressResponse(BaseModel):
    interviews_completed: int = 0
    answers_evaluated: int = 0
    average_practice_score: float | None = None
    most_common_improvement_area: str | None = None
    average_answer_seconds: float | None = None
    recent_interviews: list[RecentInterview] = Field(default_factory=list)
