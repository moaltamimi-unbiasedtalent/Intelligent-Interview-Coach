"""Premium progress analytics API schemas (W12.4D-P4-B). Measurements only: no transcript, answer text, question text or feedback prose is ever returned.
Every non-data outcome is an explicit ``state`` with no data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RubricCell(BaseModel):
    average: float | None = None
    answers_measured: int = 0


class AnalyticsPoint(BaseModel):
    interview_id: int
    date: str | None = None
    practice_score: float | None = None
    answers_scored: int = 0
    low_sample: bool = False
    report_score: float | None = None
    target_role: str | None = None
    career_level: str | None = None
    opportunity_id: int | None = None
    question_count: int = 0
    rubric: dict[str, RubricCell] = Field(default_factory=dict)


class AnalyticsSummary(BaseModel):
    first_score: float | None = None
    latest_score: float | None = None
    change: float | None = None
    direction: str | None = None
    comparable_context: bool | None = None
    average_score: float | None = None
    best_score: float | None = None
    first_scope: str = "all"


class RubricDimension(BaseModel):
    id: str
    average: float | None = None
    answers_measured: int = 0


class RubricBreakdown(BaseModel):
    dimensions: list[RubricDimension] = Field(default_factory=list)
    strongest: str | None = None
    weakest: str | None = None


class QuestionTypeRow(BaseModel):
    type: str
    average_score: float | None = None
    answers_scored: int = 0


class MonthCount(BaseModel):
    month: str
    count: int


class Frequency(BaseModel):
    last_30_days: int = 0
    last_90_days: int = 0
    by_month: list[MonthCount] = Field(default_factory=list)


class ImprovementArea(BaseModel):
    area: str
    count: int
    origin: str = "model_generated"


class AnalyticsFilters(BaseModel):
    roles: list[str] = Field(default_factory=list)
    opportunity_ids: list[int] = Field(default_factory=list)


class AnalyticsCounts(BaseModel):
    completed_interviews: int = 0
    scored_interviews: int = 0
    unscored_interviews: int = 0


class AnalyticsOverviewResponse(BaseModel):
    """``state``: feature_disabled | not_entitled | no_data | insufficient_data | ready. Only ``insufficient_data`` and ``ready`` carry measurements."""

    state: str
    truncated: bool = False
    analyzed_limit: int | None = None
    counts: AnalyticsCounts | None = None
    points: list[AnalyticsPoint] = Field(default_factory=list)
    summary: AnalyticsSummary | None = None
    distribution: dict[str, int] = Field(default_factory=dict)
    rubric: RubricBreakdown | None = None
    by_question_type: list[QuestionTypeRow] = Field(default_factory=list)
    frequency: Frequency | None = None
    improvement_areas: list[ImprovementArea] = Field(default_factory=list)
    filters: AnalyticsFilters | None = None
    methodology: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RubricDifference(BaseModel):
    id: str
    base: float | None = None
    target: float | None = None
    difference: float | None = None


class AnalyticsCompareResponse(BaseModel):
    """``state``: feature_disabled | not_entitled | insufficient_data | ready. ``comparability``: comparable | limited (with reason codes)."""

    state: str
    base: AnalyticsPoint | None = None
    target: AnalyticsPoint | None = None
    score_difference: float | None = None
    direction: str | None = None
    rubric_differences: list[RubricDifference] = Field(default_factory=list)
    comparability: str | None = None
    comparability_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
