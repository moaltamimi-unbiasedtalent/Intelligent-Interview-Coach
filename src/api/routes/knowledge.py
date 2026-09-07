"""Knowledge routes — read-only status for the future frontend.

Exposes only what KnowledgeApplicationService already provides: the curated source
registry and the narrative ingestion snapshot (counts). No local paths, provider
config, embeddings or index internals are returned.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas.knowledge import (
    KnowledgeSnapshotResponse,
    KnowledgeSourcesResponse,
    SourceEntryOut,
)
from src.application import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/sources", response_model=KnowledgeSourcesResponse,
            summary="Curated knowledge sources")
def sources() -> KnowledgeSourcesResponse:
    entries = knowledge_service.list_sources()
    out = [
        SourceEntryOut(
            source_id=getattr(e, "source_id", None),
            title=getattr(e, "title", None),
            group=getattr(e, "group", None),
            source_type=getattr(e, "source_type", None),
        )
        for e in entries
    ]
    return KnowledgeSourcesResponse(sources=out)


@router.get("/snapshot", response_model=KnowledgeSnapshotResponse,
            summary="Narrative ingestion snapshot (counts)")
def snapshot() -> KnowledgeSnapshotResponse:
    data = knowledge_service.get_ingestion_snapshot()
    return KnowledgeSnapshotResponse(
        documents=int(data.get("documents", 0)),
        chunks=int(data.get("chunks", 0)),
        document_types=len(data.get("by_type", {}) or {}),
    )
