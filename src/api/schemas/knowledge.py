"""Knowledge API schemas (read-only)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceEntryOut(BaseModel):
    source_id: str | None = None
    title: str | None = None
    group: str | None = None
    source_type: str | None = None
    # Safe provenance so a source is inspectable and (where a public record exists)
    # clickable. `source_url` is the curated official landing page from the source
    # manifest — never an authenticated/download endpoint. Absent when the governed
    # source has no appropriate public URL (then the source stays inspectable, not linked).
    source_url: str | None = None
    provider: str | None = None
    country: str | None = None
    reference_year: int | None = None


class KnowledgeSourcesResponse(BaseModel):
    sources: list[SourceEntryOut] = Field(default_factory=list)


class KnowledgeSnapshotResponse(BaseModel):
    """Narrative ingestion status — counts only, no local paths or internals."""

    documents: int = 0
    chunks: int = 0
    document_types: int = 0


class KnowledgeRuntimeCounts(BaseModel):
    """Governed knowledge-runtime counts + build provenance (no internals)."""

    occupations: int | None = None
    aliases: int | None = None
    skills: int | None = None
    tasks: int | None = None
    knowledge_areas: int | None = None
    work_activities: int | None = None
    compensation: int | None = None
    labour_market: int | None = None
    competencies: int | None = None
    credentials: int | None = None
    sources: int | None = None
    runtime_pipeline_version: str | None = None
    normalized_pipeline_version: str | None = None
    built_at: str | None = None


class RetrievalEvaluationSummary(BaseModel):
    """Offline deterministic retrieval-quality metrics (never a live/paid run)."""

    cases: int | None = None
    passed: int | None = None
    pass_rate: float | None = None
    evidence_coverage_rate: float | None = None
    citation_completeness_rate: float | None = None
    geography_correctness_rate: float | None = None
    unknown_role_safety_rate: float | None = None
    unsupported_geography_safety_rate: float | None = None
    no_fabricated_citation_rate: float | None = None
    safety_pass_rate: float | None = None


class KnowledgeDiagnosticsResponse(BaseModel):
    """Read-only Knowledge/RAG diagnostics: runtime counts + offline retrieval eval."""

    runtime: KnowledgeRuntimeCounts = Field(default_factory=KnowledgeRuntimeCounts)
    retrieval_evaluation: RetrievalEvaluationSummary = Field(
        default_factory=RetrievalEvaluationSummary)
    known_gaps: list[str] = Field(default_factory=list)
