"""Knowledge Base application boundary (Streamlit-free, read-only).

Callable operations a frontend needs to show knowledge-base status. Retrieval
logic, source precedence, hybrid retrieval, structured repositories, embeddings
and RAGAS are untouched — this only exposes existing read-only snapshots.
"""

from __future__ import annotations

from typing import Any


def get_ingestion_snapshot() -> dict:
    """Narrative ingestion status (documents, chunks, by_type, per_document…)."""
    from src.copilot.ingestion import indexer

    return indexer.load_manifest() or {}


def list_sources() -> list[Any]:
    """The curated source registry entries (id, group, licence disposition…)."""
    from src.copilot.knowledge import manifest as km

    return km.load_manifest()
