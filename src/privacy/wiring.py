"""Construction helpers for the privacy runtime used by the W10.9 worker (P10B-W10.10)."""

from __future__ import annotations

from src.privacy.preparation import CheckpointAdapter
from src.privacy.runtime import PrivacyRuntime


def build_privacy_runtime(session_factory, app_config) -> PrivacyRuntime:
    from src.agent.checkpoint import build_checkpointer
    from src.auth_repository import AuditRepository
    from src.documents.storage import build_document_store
    from src.jobs.service import JobService

    adapter = None
    try:
        info = build_checkpointer(checkpoint_url=None, database_url=getattr(app_config, "database_url", None))
        adapter = CheckpointAdapter(info.saver)
    except Exception:  # noqa: BLE001 - without a checkpoint store, privacy jobs fail closed with configuration_error
        adapter = None
    return PrivacyRuntime(session_factory=session_factory, adapter=adapter, doc_store=build_document_store(),
                          audit_repository=AuditRepository(session_factory), jobs=JobService(session_factory))
