"""Construction helpers for the knowledge control plane (P10B-W10.8)."""

from __future__ import annotations

from types import SimpleNamespace

from src.documents.storage import LocalDocumentStore
from src.knowledge_admin import policy as P


def build_knowledge_doc_store(runtime=None) -> LocalDocumentStore:
    """Private storage for uploaded knowledge files: opaque random keys, outside any web root.

    02A: the directory comes from the ONE runtime configuration (``KNOWLEDGE_STORAGE_DIR`` when set, otherwise a directory UNDER THE DATA
    ROOT, so private files live on the same persistent volume as the indexes). It used to default to the system temporary directory, which
    silently lost every uploaded source on a restart or redeploy."""
    from src.knowledge_admin.config import resolve_knowledge_runtime_config

    return LocalDocumentStore((runtime or resolve_knowledge_runtime_config()).private_files_dir)


def build_governed_store(config, *, embedder=None, in_memory: bool = False):
    """The GOVERNED collection: separate from the legacy corpus collection, so unapproved or legacy content never shares it."""
    from src.copilot.embeddings import build_embedder
    from src.copilot.vectorstore import ChromaStore, InMemoryVectorStore, _chroma_available

    embedder = embedder or build_embedder(config)
    if in_memory or not _chroma_available():
        return InMemoryVectorStore(embedder, collection_name=P.COLLECTION)
    return ChromaStore(embedder, persist_dir=config.chroma_persist_dir, collection_name=P.COLLECTION)


def build_serving_guard(session_factory, app_config, copilot_config, *, store_provider, doc_store=None, job_service=None, on_report=None,
                        ttl_seconds: float = 15.0, curated_store_provider=None):
    """The environment guard over the ONE runtime configuration (shared by the API and, for its identity record, the worker)."""
    from src.knowledge_admin.config import resolve_knowledge_runtime_config
    from src.knowledge_admin.environment import KnowledgeServingGuard

    from src.knowledge_admin.alerts import observe_guard_report

    if on_report is None:                    # each evaluation also derives the in-app knowledge health alerts (never raises, never pages anyone)
        on_report = lambda report: observe_guard_report(session_factory, report)  # noqa: E731
    runtime = resolve_knowledge_runtime_config(app_config, copilot_config, session_factory=session_factory)
    return KnowledgeServingGuard(session_factory, runtime, store_provider=store_provider, doc_store=doc_store or build_knowledge_doc_store(runtime),
                                 job_service=job_service, copilot_config=copilot_config, ttl_seconds=ttl_seconds, on_report=on_report,
                                 curated_store_provider=curated_store_provider)


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
