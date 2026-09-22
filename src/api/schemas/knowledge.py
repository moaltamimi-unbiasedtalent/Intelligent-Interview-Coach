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
