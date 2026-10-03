"""Preparation-run ownership index and checkpoint purge (PRIV-W9-01, P10B-W10.10).

The index (``preparation_runs``) records WHO owns a durable preparation run and its lifecycle. It never holds chat content. Because
it is a plain indexed table, per-user discovery is one indexed query: nothing here ever scans the checkpoint store.

* New runs: registered BEFORE the checkpoint is created (fail-closed sequencing; SQL and the checkpoint store cannot be atomic).
* Historical runs: indexed from deterministic relational references (saved-memory ``source_run_id``) after the checkpoint's own
  recorded owner is verified; ambiguous or ownerless references are NOT assigned. Anything unreachable stays unindexed and is
  documented as a limitation. A run is also indexed lazily when its verified owner touches it.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy import func, select

from src.persistence import PreparationMemory, PreparationRun, utcnow
from src.privacy import policy as P

log = logging.getLogger("ask4mo.privacy.preparation")


class RunOwnershipConflict(Exception):
    pass


class PreparationRunIndex:
    def __init__(self, session_factory, clock: Callable = utcnow) -> None:
        self._sf = session_factory
        self._clock = clock

    def register(self, run_id: str, owner_user_id: int, *, source: str = "created") -> bool:
        """Idempotent. Returns True if a row was created. A run can never change owner."""
        if source not in P.RUN_SOURCES:
            raise ValueError("unknown source")
        now = self._clock()
        with self._sf() as s:
            row = s.scalar(select(PreparationRun).where(PreparationRun.run_id == run_id))
            if row is not None:
                if row.owner_user_id != owner_user_id:
                    raise RunOwnershipConflict(run_id)
                return False
            s.add(PreparationRun(run_id=run_id, owner_user_id=owner_user_id, state="started", source=source,
                                 coverage_version=P.COVERAGE_VERSION, created_at=now, updated_at=now))
            s.commit()
            return True

    def mark(self, run_id: str, state: str) -> None:
        if state not in P.RUN_STATES:
            raise ValueError("unknown state")
        with self._sf() as s:
            row = s.scalar(select(PreparationRun).where(PreparationRun.run_id == run_id))
            if row is not None and row.state != state:
                row.state, row.updated_at = state, self._clock()
                s.commit()

    def run_ids_for_owner(self, owner_user_id: int) -> list[str]:
        with self._sf() as s:   # one indexed lookup (ix_preparation_runs_owner_state): never a checkpoint scan
            return list(s.scalars(select(PreparationRun.run_id).where(PreparationRun.owner_user_id == owner_user_id)
                                  .order_by(PreparationRun.id)).all())

    def owner_of(self, run_id: str) -> int | None:
        with self._sf() as s:
            return s.scalar(select(PreparationRun.owner_user_id).where(PreparationRun.run_id == run_id))

    def remove(self, run_id: str) -> None:
        with self._sf() as s:
            row = s.scalar(select(PreparationRun).where(PreparationRun.run_id == run_id))
            if row is not None:
                s.delete(row)
                s.commit()

    def pending_purge(self, owner_user_id: int | None = None) -> list[tuple[str, int]]:
        with self._sf() as s:
            q = select(PreparationRun.run_id, PreparationRun.owner_user_id).where(PreparationRun.state == "purge_failed")
            if owner_user_id is not None:
                q = q.where(PreparationRun.owner_user_id == owner_user_id)
            return [(r, o) for r, o in s.execute(q).all()]

    def coverage(self) -> dict:
        with self._sf() as s:
            by_state = dict(s.execute(select(PreparationRun.state, func.count()).group_by(PreparationRun.state)).all())
            by_source = dict(s.execute(select(PreparationRun.source, func.count()).group_by(PreparationRun.source)).all())
            return {"indexed_runs": sum(by_state.values()), "by_state": by_state, "by_source": by_source,
                    "coverage_version": P.COVERAGE_VERSION,
                    "note": "Counts indexed runs only. Historical runs with no relational reference cannot be discovered and are not included."}


def checkpoint_owner(checkpointer: Any, run_id: str) -> str | None:
    """The owner recorded INSIDE the checkpoint for one known run id (a single-thread lookup, never a scan)."""
    try:
        tup = checkpointer.get_tuple({"configurable": {"thread_id": run_id}})
    except Exception:  # noqa: BLE001
        return None
    if tup is None:
        return None
    values = (getattr(tup, "checkpoint", None) or {}).get("channel_values") or {}
    owner = values.get("user_id")
    return str(owner) if owner is not None else None


class CheckpointAdapter:
    """Purge/ownership helper over a LangGraph saver. Uses ONLY the saver's official ``delete_thread`` (no raw SQL)."""

    def __init__(self, checkpointer: Any) -> None:
        self._cp = checkpointer

    @property
    def supported(self) -> bool:
        return callable(getattr(self._cp, "delete_thread", None))

    def owner_of(self, run_id: str) -> str | None:
        return checkpoint_owner(self._cp, run_id)

    def purge_run(self, run_id: str) -> bool:
        if not self.supported:
            raise RuntimeError("checkpoint store does not support deletion")
        self._cp.delete_thread(run_id)
        return True

    def delete_run(self, run_id: str, user_id: str | None) -> bool:     # same shape as AgentApplicationService.delete_run
        if self.owner_of(run_id) != user_id:
            return False
        return self.purge_run(run_id)


def backfill_batch(index: PreparationRunIndex, adapter: Any, session_factory, *, after_memory_id: int = 0,
                   batch: int = P.BACKFILL_BATCH) -> dict:
    """Index runs referenced by saved memories, verifying the checkpoint's own recorded owner. Idempotent and bounded."""
    out = {"examined": 0, "indexed": 0, "already_indexed": 0, "missing_checkpoint": 0, "ambiguous_skipped": 0, "next_after_id": None}
    with session_factory() as s:
        rows = s.execute(select(PreparationMemory.id, PreparationMemory.user_id, PreparationMemory.source_run_id)
                         .where(PreparationMemory.id > after_memory_id, PreparationMemory.source_run_id.is_not(None))
                         .order_by(PreparationMemory.id).limit(batch)).all()
    for mem_id, user_id, run_id in rows:
        out["examined"] += 1
        out["next_after_id"] = mem_id
        if index.owner_of(run_id) is not None:
            out["already_indexed"] += 1
            continue
        owner = adapter.owner_of(run_id)
        if owner is None:
            out["missing_checkpoint"] += 1
        elif owner != str(user_id):
            out["ambiguous_skipped"] += 1        # the memory owner is not the checkpoint's recorded owner: never assigned
        else:
            index.register(run_id, int(user_id), source="backfill")
            out["indexed"] += 1
    if len(rows) < batch:
        out["next_after_id"] = None              # reached the end
    return out
