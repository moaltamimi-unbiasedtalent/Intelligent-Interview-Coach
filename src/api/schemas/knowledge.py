"""Knowledge API schemas (read-only)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceEntryOut(BaseModel):
    source_id: str | None = None
    title: str | None = None
    group: str | None = None
    source_type: str | None = None


class KnowledgeSourcesResponse(BaseModel):
    sources: list[SourceEntryOut] = Field(default_factory=list)


class KnowledgeSnapshotResponse(BaseModel):
    """Narrative ingestion status — counts only, no local paths or internals."""

    documents: int = 0
    chunks: int = 0
    document_types: int = 0
