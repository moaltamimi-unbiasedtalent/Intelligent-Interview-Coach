"""Operator-approved rebuild of the governed index for an incompatible or unproven embedder (package 02B, REVIEW-04 R4/R5).

WHY NOT AUTOMATIC: an incompatible index is REFUSED at query and write time (see ``src.copilot.index_manifest``), never repaired silently, and the
existing ``knowledge_reindex`` job refuses to extend it (it only adds missing chunks and must never mix two embedders in one collection). The
remedy is a rebuild from the APPROVED source files into a NEW, EMPTY index with an approved embedder:

* dry-run is the default (``execute=False`` only plans and estimates);
* the current index is never modified, deleted or overwritten; the target must be a new or empty directory different from the active index;
* the embedder must be acceptable for the environment (hosted: semantic, credentials present, dimensions known; the hash embedder is refused by
  ``build_embedder``) and, when it is not free, the operator must CONFIRM its exact ``provider:model`` and the paid-call approval environment
  (``src.copilot.embedding_budget``) must be present;
* the build runs the EXISTING reindex job handler (``knowledge_admin.runtime.run_reindex``) once per active or indexed version, so chunking, checksum
  verification of the private file and deterministic chunk ids are the production ones;
* afterwards the new index's manifest is verified against the live embedder. Switching to it (``COPILOT_CHROMA_DIR`` + restart of API and worker)
  is a separate, manual operator step.

Reports contain counts, field names and fixed codes only (never a path, key, URL, text or vector).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from sqlalchemy import select

from src.copilot.embedding_budget import PaidEmbeddingRefused, estimate_rebuild, guard_embedder
from src.copilot.embeddings import BaseEmbedder, EmbeddingConfigurationError, current_environment
from src.knowledge_admin import policy as P
from src.knowledge_admin.runtime import KnowledgeRuntime, run_reindex
from src.persistence import KnowledgeSourceVersion as V


@dataclass
class RebuildReport:
    ok: bool = True
    executed: bool = False
    codes: list[str] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    estimate: dict = field(default_factory=dict)
    index: dict | None = None
    notes: list[str] = field(default_factory=list)

    def refuse(self, code: str) -> "RebuildReport":
        self.ok = False
        if code not in self.codes:
            self.codes.append(code)
        return self

    def to_dict(self) -> dict:
        return {"ok": self.ok, "executed": self.executed, "codes": list(self.codes), "counts": dict(self.counts), "estimate": dict(self.estimate),
                "index": self.index, "notes": list(self.notes)}


def _versions(session_factory: Any) -> list[tuple[str, int]]:
    with session_factory() as s:
        return [(r[0], int(r[1] or 0)) for r in s.execute(select(V.public_id, V.chunk_count).where(V.state.in_(("active", "indexed")))
                                                          .order_by(V.public_id)).all()]


def _nonempty(path: Path) -> bool:
    return path.exists() and (not path.is_dir() or any(path.iterdir()))


def plan_rebuild(session_factory: Any, active_store: Any, *, environment: str | None = None) -> dict:
    """What the active index looks like and what a rebuild would cost. Read-only; no embedding call."""
    env = current_environment(environment)
    versions = _versions(session_factory)
    chunks = sum(n for _, n in versions)
    status = None
    if active_store is not None and hasattr(active_store, "index_status"):
        try:
            status = active_store.index_status(environment=env).to_safe_dict()
        except Exception:  # noqa: BLE001
            status = None
    return {"environment": env, "versions_to_rebuild": len(versions), "chunks_recorded": chunks, "active_index": status,
            "rebuild_needed": bool(status and status["refused"]), "estimate": estimate_rebuild(chunk_count=chunks),
            "steps": ["choose an approved embedder (hosted: semantic with credentials)", "run with --apply into a NEW empty directory and confirm the embedder",
                      "verify the new index manifest", "point COPILOT_CHROMA_DIR at the new directory and restart the API and the worker"]}


def rebuild_into_new_index(session_factory: Any, doc_store: Any, *, target_dir: str | Path, embedder: BaseEmbedder, active_index_dir: str | Path | None = None,
                           environment: str | None = None, confirm_embedder: str | None = None, execute: bool = False,
                           store_factory: Callable[[BaseEmbedder, str], Any] | None = None, env: dict | None = None) -> RebuildReport:
    rep = RebuildReport()
    environment = current_environment(environment)
    hosted = environment != "development"
    target = Path(target_dir)
    versions = _versions(session_factory)
    rep.counts = {"versions": len(versions), "chunks_expected": sum(n for _, n in versions)}
    rep.estimate = estimate_rebuild(chunk_count=rep.counts["chunks_expected"])
    ident = embedder.identity()

    if hosted and ident.provider == "local":
        rep.refuse("hash_embedder_not_allowed")                     # defence in depth: build_embedder already refuses this when hosted
    if not versions:
        rep.refuse("nothing_to_rebuild")
    if active_index_dir is not None and target.resolve() == Path(active_index_dir).resolve():
        rep.refuse("target_is_active_index")                        # the live index is never written to or replaced
    if _nonempty(target):
        rep.refuse("target_not_empty")
    paid = ident.provider != "local"
    if paid and (confirm_embedder or "") != f"{ident.provider}:{ident.model}":
        rep.refuse("embedder_not_confirmed")                        # the operator must name the exact provider:model being approved
    if not rep.ok or not execute:
        if rep.ok:
            rep.notes.append("dry run: nothing was written")
        return rep
    try:
        guarded = guard_embedder(embedder, env)                      # a paid embedder needs the owner's flag, budget marker and call ceiling
    except PaidEmbeddingRefused as exc:
        for c in exc.codes:
            rep.refuse(c)
        return rep
    except EmbeddingConfigurationError as exc:
        for c in exc.codes:
            rep.refuse(c)
        return rep

    if store_factory is None:
        from src.copilot.vectorstore import ChromaStore

        def store_factory(emb, path):  # type: ignore[misc]
            return ChromaStore(emb, persist_dir=path, collection_name=P.COLLECTION)
    target.mkdir(parents=True, exist_ok=True)
    store = store_factory(guarded, str(target))
    rt = KnowledgeRuntime(session_factory=session_factory, doc_store=doc_store, vector_store_factory=lambda: store)
    ctx = SimpleNamespace(services=SimpleNamespace(knowledge=rt), attempt=1, max_attempts=1)
    rep.executed = True
    failed: list[str] = []
    for vpid, _n in versions:
        try:
            run_reindex(vpid, ctx)                                   # the EXISTING reindex job handler: verified file, deterministic chunk ids, idempotent
        except Exception:  # noqa: BLE001 - fixed code only; a text or provider message is never recorded
            failed.append(vpid)
    rep.counts["chunks_built"] = int(store.count())
    rep.counts["versions_failed"] = len(failed)
    if failed:
        rep.refuse("version_rebuild_failed")
    status = store.index_status(environment=environment)
    rep.index = status.to_safe_dict()
    if not status.compatible:
        rep.refuse("new_index_manifest_unproven")
    if rep.counts["chunks_built"] < rep.counts["chunks_expected"]:
        rep.refuse("new_index_short")
    if rep.ok:
        rep.notes.append("new index built and verified; switching to it (COPILOT_CHROMA_DIR + restart of API and worker) is a manual step; the old index was not touched")
    return rep
