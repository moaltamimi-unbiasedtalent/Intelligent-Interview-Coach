"""Construction helpers for the knowledge control plane (P10B-W10.8)."""

from __future__ import annotations

import os
from types import SimpleNamespace

from src.documents.storage import LocalDocumentStore
from src.knowledge_admin import policy as P


def build_knowledge_doc_store() -> LocalDocumentStore:
    """Private storage for uploaded knowledge files: opaque random keys, outside any web root."""
    root = os.environ.get("KNOWLEDGE_STORAGE_DIR", "").strip() or os.path.join(os.environ.get("TMPDIR", "/tmp"), "ask4mo_knowledge")
    return LocalDocumentStore(root)


def build_governed_store(config, *, embedder=None, in_memory: bool = False):
    """The GOVERNED collection: separate from the legacy corpus collection, so unapproved or legacy content never shares it."""
    from src.copilot.embeddings import build_embedder
    from src.copilot.vectorstore import ChromaStore, InMemoryVectorStore, _chroma_available

    embedder = embedder or build_embedder(config)
    if in_memory or not _chroma_available():
        return InMemoryVectorStore(embedder)
    return ChromaStore(embedder, persist_dir=config.chroma_persist_dir, collection_name=P.COLLECTION)


def build_worker_services(session_factory, config):
    """Services the W10.9 worker hands to knowledge job handlers."""
    from src.documents.file_security import build_file_scanner
    from src.knowledge_admin.runtime import KnowledgeRuntime

    cache: dict = {}

    def store():
        if "s" not in cache:
            cache["s"] = build_governed_store(config)
        return cache["s"]

    return SimpleNamespace(knowledge=KnowledgeRuntime(session_factory=session_factory, doc_store=build_knowledge_doc_store(),
                                                      scanner=build_file_scanner(), vector_store_factory=store))
