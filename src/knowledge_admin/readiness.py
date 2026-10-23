"""Knowledge readiness, active inventory and retrieval test (W12.4A). DERIVED, bounded, safe.

Everything here is computed from facts that already exist (the control-plane tables, the job and worker heartbeats, the governed store
the candidate path itself uses) so there is no new persisted state and no migration. READY is never inferred from configuration alone:
it needs at least one ACTIVE version whose index was BUILT and whose chunks are physically present in the store the candidate retriever
reads, with a usable embedder. Nothing here returns a filesystem path, a secret, a vector, a raw provider error or candidate data.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from src.knowledge_admin import policy as P
from src.persistence import Job, KnowledgeIndexRecord, KnowledgeSource
from src.persistence import KnowledgeSourceVersion as V

STATUSES = (
    "ready", "no_active_sources", "worker_unavailable", "index_pending", "index_failed", "store_unavailable",
    "collection_missing", "embedding_provider_unavailable", "configuration_error", "degraded",
)
KNOWLEDGE_JOB_TYPES = (P.JOB_PARSE, P.JOB_INDEX, P.JOB_REINDEX, P.JOB_REMOVE)
# Human, truthful one-liners for the Admin UI (never claims health that was not established).
MESSAGES = {
    "ready": "Governed knowledge is active, indexed and present in the store candidate retrieval reads.",
    "no_active_sources": "No governed knowledge source is active. Register, review, approve, index and activate a source.",
    "worker_unavailable": "Indexing is waiting for a worker, and no worker has reported recently. Start the job worker.",
    "index_pending": "Indexing work is queued or running. Active knowledge will appear when it finishes.",
    "index_failed": "An index build failed. Open the source to see the failure category, then retry.",
    "store_unavailable": "The vector store candidate retrieval reads could not be opened.",
    "collection_missing": "Active sources exist but the governed collection is empty or missing in the store. Re-index the active sources.",
    "embedding_provider_unavailable": "The configured embedder is not usable in this environment (no credential is configured for it, or a hosted environment refuses the lexical hash embedder).",
    "configuration_error": "The store configuration cannot serve governed retrieval (for example a non-persistent store).",
    "degraded": "Governed knowledge works, but something currently needs attention (an unrecovered failed build, a pending job without a worker, a missing index record or a failed removal).",
}


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _describe_store(store: Any) -> dict:
    """Safe facts about a vector store. Never a path, never a vector."""
    persistent = hasattr(store, "persist_dir")
    out = {"kind": "persistent" if persistent else "in_memory", "chunk_count": None, "collection": getattr(store, "collection_name", None),
           "embedder": type(getattr(store, "embedder", None)).__name__ if getattr(store, "embedder", None) is not None else None}
    try:
        out["chunk_count"] = int(store.count())
    except Exception:  # noqa: BLE001 - an unreadable store is reported as unavailable, text never recorded
        out["chunk_count"] = None
    out["index"] = None
    if hasattr(store, "index_status"):                       # 02B: the persisted manifest vs the live embedder (field names only, never values)
        try:
            out["index"] = store.index_status().to_safe_dict()
        except Exception:  # noqa: BLE001
            out["index"] = None
    return out


class KnowledgeReadinessService:
    """``governed_provider`` returns the shared GovernedKnowledgeRetriever (or None when it could not be built);
    ``curated_store_provider`` returns the shared curated corpus store (or None)."""

    def __init__(self, session_factory: sessionmaker, *, governed_provider: Callable[[], Any], curated_store_provider: Callable[[], Any],
                 job_service: Any, config: Any, guard: Any = None) -> None:
        self._sf = session_factory
        self._governed = governed_provider
        self._curated = curated_store_provider
        self._jobs = job_service
        self._config = config
        self._guard = guard          # 02A: KnowledgeServingGuard (optional so existing constructions keep working)

    # ------------------------------------------------------------------ workers
    def _worker(self) -> dict:
        try:
            w = self._jobs.stats()["workers"]
        except Exception:  # noqa: BLE001
            return {"status": "unknown", "seen_recently": 0, "last_seen_at": None, "stale_after_seconds": None}
        seen = int(w.get("seen_recently", 0))
        status = "available" if seen > 0 else ("stale" if w.get("items") else "none")
        return {"status": status, "seen_recently": seen, "last_seen_at": w.get("last_seen_at"), "stale_after_seconds": w.get("stale_after_seconds")}

    # ------------------------------------------------------------------ embedding
    def _embedding(self, store_info: dict | None) -> dict:
        """The ACTUAL embedder and its degradation (02B). ``status`` keeps its historical values; the new fields are additive."""
        from src.copilot.embeddings import resolve_embedding_plan

        plan = resolve_embedding_plan(self._config)
        provider = plan.configured_provider
        embedder = store_info.get("embedder") if store_info else None
        index = store_info.get("index") if store_info else None
        extra = {"model": plan.model, "version": plan.version, "dimensions": plan.dimensions, "quality_mode": plan.quality_mode,
                 "label": plan.label, "degraded": (not plan.semantic) and provider != "local", "environment": plan.environment,
                 "approved_for_environment": plan.approved, "problems": list(plan.problems), "warnings": list(plan.warnings),
                 "index_compatibility": index}
        if plan.problems:
            note = ("no credential configured" if "semantic_credentials_missing" in plan.problems and plan.semantic is True
                    else "the embedder is not acceptable for this environment")
            return {"status": "unavailable", "provider": plan.provider if plan.semantic else "local", "embedder": embedder, "note": note, **extra}
        remote = plan.semantic
        return {"status": "configured_not_tested" if remote else "available", "provider": "remote" if remote else "local", "embedder": embedder,
                "note": "remote provider: configured, not tested here" if remote else "offline local embedder (lexical, development only)", **extra}

    # ------------------------------------------------------------------ readiness
    def readiness(self) -> dict:
        with self._sf() as s:
            by_state = dict(s.execute(select(V.state, func.count()).group_by(V.state)).all())
            active_rows = s.execute(select(V.id, V.chunk_count).where(V.state == "active", V.language.in_(P.KB_LANGUAGES))).all()
            active_ids = [r[0] for r in active_rows]
            built = 0
            built_chunks = 0
            if active_ids:
                recs = s.scalars(select(KnowledgeIndexRecord).where(KnowledgeIndexRecord.version_id.in_(active_ids),
                                                                    KnowledgeIndexRecord.state == "built")).all()
                built, built_chunks = len(recs), sum(r.chunk_count for r in recs)
            sources_total = s.scalar(select(func.count()).select_from(KnowledgeSource)) or 0
            pending_jobs = s.scalar(select(func.count()).select_from(Job).where(
                Job.job_type.in_(KNOWLEDGE_JOB_TYPES), Job.state.in_(("queued", "running")))) or 0
            # HISTORY: every failed knowledge job ever recorded. Informational only (failed_job_count); a recovered failure stays visible here.
            failed_jobs = s.scalar(select(func.count()).select_from(Job).where(
                Job.job_type.in_(KNOWLEDGE_JOB_TYPES), Job.state == "failed")) or 0
            # CURRENT: an index whose vector removal failed (retired content may still be physically present; the SQL gate still protects candidates).
            removal_failed = s.scalar(select(func.count()).select_from(KnowledgeIndexRecord).where(KnowledgeIndexRecord.state == "removal_failed")) or 0
            last_indexed = s.scalar(select(func.max(V.indexed_at)))
            failed_row = s.execute(select(V.failure_category, V.failed_stage).where(V.state == "failed").order_by(V.updated_at.desc()).limit(1)).first()
        active_n = len(active_ids)
        failed_versions = by_state.get("failed", 0)
        pending_versions = by_state.get("approved", 0) + by_state.get("indexing", 0) + by_state.get("queued", 0) + by_state.get("processing", 0)
        worker = self._worker()

        retriever = None
        try:
            retriever = self._governed()
        except Exception:  # noqa: BLE001
            retriever = None
        store = getattr(retriever, "store", None) if retriever is not None else None
        store_info = _describe_store(store) if store is not None else None
        embedding = self._embedding(store_info)

        curated = self._curated_status()
        status = self._decide(active_n=active_n, built=built, built_chunks=built_chunks, failed_versions=failed_versions,
                              pending=pending_versions + pending_jobs, worker=worker, retriever=retriever, store_info=store_info,
                              embedding=embedding, removal_failed=removal_failed)
        governed_usable = status in ("ready", "degraded") and built > 0 and bool(store_info and (store_info["chunk_count"] or 0) > 0)
        collection = ("ok" if store_info and (store_info["chunk_count"] or 0) > 0 else ("empty_or_missing" if store_info else "unavailable"))
        message = MESSAGES[status]
        environment = None
        if self._guard is not None:
            from src.knowledge_admin.environment import environment_diagnostics

            try:
                environment = environment_diagnostics(self._sf, self._guard, governed_store=store, curated_store=self._safe_curated(), job_service=self._jobs)
                report = self._guard.check()
                if report.enforced and report.blocking:
                    # 02A: the environment guard refuses governed retrieval in a hosted deployment; readiness must say so, never "ready".
                    governed_usable = False
                    if status in ("ready", "degraded", "no_active_sources", "index_pending", "worker_unavailable"):
                        status = "configuration_error"
                    message = "The knowledge environment guard is refusing governed retrieval: " + " ".join(f.message for f in report.blocking)
            except Exception:  # noqa: BLE001 - diagnostics are additive; their failure never breaks readiness and never reports health
                environment = None
        idx = (store_info or {}).get("index") if store_info else None
        if idx and idx.get("refused"):
            # 02B: the index was built by a different or unproven embedder; candidate retrieval refuses it, so readiness must not say "ready".
            governed_usable = False
            if status in ("ready", "degraded", "no_active_sources", "index_pending", "worker_unavailable"):
                status = "configuration_error"
            message = "The governed index cannot be served with the live embedder (" + idx["state"] + (": " + ", ".join(idx["differing_fields"])
                                                                                                      if idx.get("differing_fields") else "") + "). Rebuild it with an approved embedder."
        views = self._views(status, active_n, built_chunks, store_info, curated)
        return {
            "status": status, "message": message,
            "candidate_retrieval_ready": bool(governed_usable or curated["status"] == "available"),
            "governed_retrieval_ready": bool(governed_usable),
            "source_count": sources_total, "active_source_count": active_n, "active_version_count": active_n, "indexed_active_version_count": built,
            "pending_job_count": pending_jobs, "failed_job_count": failed_jobs, "awaiting_review_count": by_state.get("review_required", 0),
            "failed_version_count": failed_versions,
            "worker": worker,
            "collection_status": collection, "collection": P.COLLECTION,
            "store": {"kind": store_info["kind"] if store_info else "unavailable", "chunk_count": store_info["chunk_count"] if store_info else None,
                      "location": ("default" if getattr(self._config, "chroma_persist_dir", None) == self._default_dir() else "configured_override")},
            "embedding_provider_status": embedding["status"], "embedder_state": embedding,
            "curated_corpus": curated,
            "last_indexed_at": _iso(last_indexed),
            "last_failure_category": (failed_row[0] if failed_row else None),
            "last_failure_stage": (failed_row[1] if failed_row else None),
            "environment": environment, "views": views,
        }

    def _safe_curated(self):
        try:
            return self._curated()
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _views(status: str, active_n: int, built_chunks: int, store_info: dict | None, curated: dict) -> dict:
        """Two clearly separated, labelled views (02A, builds on the curated panel). CURATED = the committed corpus shipped with the product
        (read-only, not Admin-managed). GOVERNED = Admin-managed sources (the only content an Admin controls). Counts are never merged."""
        return {
            "curated": {"label": "Curated knowledge base", "origin": "committed_corpus", "admin_managed": False,
                        "description": "The committed corpus that ships with the product. It is read-only here and is not Admin-managed.",
                        "status": curated["status"], "chunk_count": curated.get("chunk_count")},
            "governed": {"label": "Admin-governed knowledge", "origin": "admin_governed", "admin_managed": True,
                         "description": "Sources an administrator registered, reviewed, approved, indexed and activated. Only active sources reach candidates.",
                         "status": status, "chunk_count": (store_info["chunk_count"] if store_info else None), "active_source_count": active_n,
                         "recorded_built_chunk_count": built_chunks},
        }

    @staticmethod
    def _default_dir() -> str:
        from src.copilot import constants

        return constants.CHROMA_PERSIST_DIR

    def _curated_status(self) -> dict:
        try:
            store = self._curated()
        except Exception:  # noqa: BLE001
            store = None
        if store is None:
            return {"status": "unavailable", "chunk_count": None}
        info = _describe_store(store)
        n = info["chunk_count"]
        if n is None:
            return {"status": "unavailable", "chunk_count": None}
        return {"status": "available" if n > 0 else "empty", "chunk_count": n, "store_kind": info["kind"]}

    @staticmethod
    def _decide(*, active_n, built, built_chunks, failed_versions, pending, worker, retriever, store_info, embedding, removal_failed) -> str:
        if embedding["status"] == "unavailable":
            return "embedding_provider_unavailable"
        if retriever is None or store_info is None or store_info["chunk_count"] is None:
            return "store_unavailable"
        if store_info["kind"] != "persistent":
            return "configuration_error"          # an in-memory store is invisible to a separate worker process
        if active_n == 0:
            if failed_versions:
                return "index_failed"
            if pending:
                return "worker_unavailable" if worker["status"] != "available" else "index_pending"
            return "no_active_sources"
        if store_info["chunk_count"] == 0:
            return "collection_missing"
        if built < active_n or store_info["chunk_count"] < built_chunks:
            return "degraded"
        # Readiness describes CURRENT state. A failed job row is history (it stays in the job log and in failed_job_count) and does not by
        # itself degrade a corpus that has recovered; only CURRENT unresolved conditions do: a version still in a failed state, a failed index
        # removal, or pending work that no worker can progress.
        if failed_versions or removal_failed or (pending and worker["status"] != "available"):
            return "degraded"
        return "ready"

    def active_version_ids(self) -> set[str]:
        with self._sf() as s:
            return set(s.scalars(select(V.public_id).where(V.state == "active", V.language.in_(P.KB_LANGUAGES))).all())

    # ------------------------------------------------------------------ active inventory
    def active_inventory(self) -> list[dict]:
        out = []
        with self._sf() as s:
            rows = s.execute(select(V, KnowledgeSource).join(KnowledgeSource, KnowledgeSource.id == V.source_id)
                             .where(V.state == "active", V.language.in_(P.KB_LANGUAGES)).order_by(V.activated_at.desc())).all()
            for v, src in rows:
                rec = s.get(KnowledgeIndexRecord, v.id)
                ext = (v.original_filename or "").rsplit(".", 1)[-1].lower() if "." in (v.original_filename or "") else ""
                out.append({
                    "source_public_id": src.public_id, "title": src.title, "version_public_id": v.public_id, "version": v.version,
                    "source_type": ext if ext in P.ALLOWED_EXTENSIONS else "document", "authority_level": v.authority_level,
                    "authority_meaning": P.AUTHORITY_MEANING[v.authority_level], "language": v.language, "geography": None,
                    "chunk_count": (rec.chunk_count if rec else v.chunk_count), "embedder": (rec.embedder if rec else None),
                    "collection": (rec.collection if rec else None), "index_state": (rec.state if rec else "missing"),
                    "activated_at": _iso(v.activated_at), "built_at": _iso(rec.built_at) if rec else None, "status": v.state,
                })
        return out


# ---------------------------------------------------------------------- retrieval test
MAX_QUERY_CHARS = 300
MAX_RESULTS = 5
EXCERPT_CHARS = 240


def _latency_bucket(ms: float) -> str:
    return "under_250ms" if ms < 250 else ("under_1s" if ms < 1000 else "over_1s")


def run_retrieval_test(career_service: Any, query: str, *, governed_version_ids: frozenset | set = frozenset()) -> dict:
    """Retrieval ONLY, through the SAME boundary as the agent's SearchCareerKnowledge (`CareerApplicationService.search_knowledge`). No
    model, no synthesis, no override of collection, path, provider, embedder, user or filters. ``governed_version_ids`` only LABELS evidence
    whose source is an active Admin-governed version (evidence from governed chunks carries the version id as its source id)."""
    from src.application.models import KnowledgeSearchRequest

    q = (query or "").strip()
    started = time.perf_counter()
    result = career_service.search_knowledge(KnowledgeSearchRequest(query=q))
    bucket = _latency_bucket((time.perf_counter() - started) * 1000)
    blocked = bool(getattr(result, "blocked", False))
    evidence = list(getattr(result, "evidence", []) or [])[:MAX_RESULTS]
    sources = []
    seen = set()
    for e in evidence:
        governed = (e.source_id or "") in governed_version_ids
        key = (e.source_title or e.source_id, governed)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"title": e.source_title or e.source_id or "Source", "publisher": e.publisher, "authority_level": e.authority_level,
                        "evidence_type": e.evidence_type, "geography": e.country or e.geography,
                        "origin": "admin_governed" if governed else "curated"})
    return {
        "status": "blocked" if blocked else ("evidence_found" if evidence and not getattr(result, "insufficient_evidence", False) else "insufficient_evidence"),
        "query": q,
        "retrieval_mode": getattr(result, "retrieval_strategy", "") or "",
        "retrieval_lane": getattr(result, "retrieval_lane", "") or "",
        "result_count": len(evidence), "source_count": len(sources),
        "insufficient_evidence": bool(getattr(result, "insufficient_evidence", True)) or not evidence,
        "latency": bucket,
        "sources": sources,
        "excerpts": [{"title": e.source_title or e.source_id or "Source", "text": (e.text or "")[:EXCERPT_CHARS],
                      "origin": "admin_governed" if (e.source_id or "") in governed_version_ids else "curated"} for e in evidence],
        "note": "Retrieval only: no model or LLM was called.",
    }
