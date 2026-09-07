"""Career API schemas — request/response shapes over CareerApplicationService.

Responses expose only safe, serialisable values already produced in Phase 1
(answer, citations, source/tool metadata, flags). They never expose chain-of-
thought, prompts, raw provider payloads, embeddings, Chroma objects or DB
entities. Company-document uploads are deferred to a later phase, so
``company_context`` is intentionally not a chat input here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.copilot import constants


class CareerChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=constants.MAX_QUERY_CHARS)
    job_description: str | None = Field(default=None, max_length=constants.MAX_JOB_DESCRIPTION_CHARS)
    candidate_background: str | None = Field(default=None, max_length=constants.MAX_JOB_DESCRIPTION_CHARS)
    days_until_interview: int | None = Field(default=None, ge=0, le=365)
    hours_per_week: float | None = Field(default=None, ge=0, le=168)


class CitationOut(BaseModel):
    marker: str | None = None
    title: str | None = None
    source: str | None = None
    source_url: str | None = None
    page: int | None = None


class SourceOut(BaseModel):
    title: str | None = None
    source_url: str | None = None
    evidence_type: str | None = None
    authority_level: str | None = None
    geography: str | None = None
    occupation_title: str | None = None
    reference_year: int | None = None


class ToolOut(BaseModel):
    tool_name: str
    status: str
    summary: str | None = None


class CareerChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    sources: list[SourceOut] = Field(default_factory=list)
    tools: list[ToolOut] = Field(default_factory=list)
    input_flagged: bool = False
    has_evidence: bool = False
    preparation_available: bool = False

    @classmethod
    def from_orchestration(cls, result) -> "CareerChatResponse":
        response = result.response
        citations = [
            CitationOut(marker=c.marker, title=c.title, source=c.source,
                        source_url=c.source_url, page=c.page)
            for c in (response.citations or [])
        ]
        sources = [
            SourceOut(
                title=e.source_title, source_url=e.source_url,
                evidence_type=e.evidence_type, authority_level=e.authority_level,
                geography=e.geography, occupation_title=e.occupation_title,
                reference_year=e.reference_year,
            )
            for e in (response.evidence or [])
        ]
        tools = [
            ToolOut(tool_name=t.tool_name, status=t.status,
                    summary=t.safe_result_summary)
            for t in (response.tool_calls or [])
        ]
        trace = result.trace
        artifacts = result.preparation_artifacts
        return cls(
            answer=response.answer,
            citations=citations,
            sources=sources,
            tools=tools,
            input_flagged=bool(getattr(trace, "blocked", False)
                               or getattr(trace, "input_indicators", [])),
            has_evidence=bool(citations or sources),
            preparation_available=bool(artifacts and not artifacts.is_empty()),
        )


# --- tool endpoints ----------------------------------------------------------


class JobAnalysisRequest(BaseModel):
    job_description: str = Field(min_length=1, max_length=constants.MAX_JOB_DESCRIPTION_CHARS)


class GapAnalysisRequest(BaseModel):
    candidate_background: str = Field(min_length=1, max_length=constants.MAX_JOB_DESCRIPTION_CHARS)
    # The role requirements from a prior job analysis (as returned by that tool).
    role_requirements: dict


class PreparationPlanRequest(BaseModel):
    priority_gaps: list[dict] = Field(default_factory=list)
    days_until_interview: int = Field(ge=1, le=365)
    hours_per_week: float = Field(gt=0, le=168)


class QuestionsRequest(BaseModel):
    role: str = Field(min_length=1, max_length=200)
    requirements: list[str] = Field(default_factory=list)
    focus: list[str] = Field(default_factory=list)


class ToolResultResponse(BaseModel):
    """A generic safe tool result: the typed value plus its execution summary."""

    ok: bool
    tool_name: str
    status: str
    result: dict | None = None
    error: str | None = None

    @classmethod
    def from_tool_call(cls, call) -> "ToolResultResponse":
        value = call.value
        # Typed domain results are Pydantic models → dump to a safe dict.
        if value is not None and hasattr(value, "model_dump"):
            value = value.model_dump()
        return cls(
            ok=call.ok,
            tool_name=getattr(call.execution, "tool_name", ""),
            status=getattr(call.execution, "status", ""),
            result=value if call.ok else None,
            error=call.error,
        )
