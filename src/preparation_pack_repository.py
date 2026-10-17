"""Persistence for Opportunity Preparation Packs (W12.4D-P5-A). Owner-scoped: every read and write carries the trusted user id in its WHERE clause, so another
candidate's id is indistinguishable from a missing one. Holds only schema-validated structured content and bounded metadata (never raw model output)."""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import PreparationPack

__all__ = ["PreparationPackRepository"]


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class PreparationPackRepository:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    @staticmethod
    def _summary(p: PreparationPack) -> dict[str, Any]:
        gen = p.generation or {}
        return {"id": p.id, "opportunity_id": p.opportunity_id, "revision": p.revision, "status": p.status, "schema_version": p.schema_version,
                "failure_category": p.failure_category, "created_at": _aware(p.created_at).isoformat() if p.created_at else None,
                "completed_at": _aware(p.completed_at).isoformat() if p.completed_at else None, "section_statuses": gen.get("section_statuses") or {}}

    def _detail(self, p: PreparationPack) -> dict[str, Any]:
        return {**self._summary(p), "content": p.content, "generation": p.generation}

    # ------------------------------------------------------------------------------------------------ lifecycle
    @staticmethod
    def _last_alive(p: PreparationPack) -> datetime:
        """The last sign of life of a ``generating`` row: its latest stage heartbeat, else its creation time."""
        beat = (p.generation or {}).get("heartbeat_at")
        try:
            return _aware(datetime.fromisoformat(beat)) if beat else _aware(p.created_at)
        except (TypeError, ValueError):
            return _aware(p.created_at)

    def touch(self, pack_id: int, *, now: datetime | None = None) -> bool:
        """Heartbeat: a generation that is still doing work renews its lease at every stage boundary, so it can never be mistaken for an interrupted one."""
        with self._sf() as s:
            p = s.scalar(select(PreparationPack).where(PreparationPack.id == pack_id, PreparationPack.status == "generating"))
            if p is None:
                return False
            p.generation = {**(p.generation or {}), "heartbeat_at": (now or datetime.now(timezone.utc)).isoformat()}
            s.commit()
            return True

    def reap_stale(self, *, older_than_seconds: int, now: datetime | None = None, user_id: int | None = None, opportunity_id: int | None = None) -> int:
        """Mark a ``generating`` row with NO sign of life (heartbeat or creation) for ``older_than_seconds`` as failed/interrupted so it can never block or
        masquerade as complete. A generation that is legitimately still running keeps renewing its heartbeat and is never reaped or replaced."""
        moment = now or datetime.now(timezone.utc)
        cutoff = moment - timedelta(seconds=older_than_seconds)
        reaped = 0
        with self._sf() as s:
            stmt = select(PreparationPack).where(PreparationPack.status == "generating")
            if user_id is not None:
                stmt = stmt.where(PreparationPack.user_id == user_id)
            if opportunity_id is not None:
                stmt = stmt.where(PreparationPack.opportunity_id == opportunity_id)
            for p in s.scalars(stmt).all():                                   # ``generating`` rows are rare: Python-side comparison is portable and cheap
                if self._last_alive(p) < cutoff:
                    reaped += s.execute(update(PreparationPack).where(PreparationPack.id == p.id, PreparationPack.status == "generating")
                                        .values(status="failed", failure_category="interrupted", completed_at=moment)).rowcount or 0
            s.commit()
        return int(reaped)

    def start(self, *, user_id: int, opportunity_id: int, op_key: str, schema_version: str, now: datetime | None = None) -> tuple[str, dict[str, Any]]:
        """Begin one generation. Returns ``(outcome, row)`` where outcome is ``created``, ``duplicate`` (same ``op_key``: nothing new) or ``in_progress``
        (another generation for this opportunity is running: nothing new). The unique ``op_key``, the one-generating-per-opportunity partial index and the
        unique revision constraint arbitrate concurrent submissions inside the database; a revision collision recomputes the revision and retries."""
        moment = now or datetime.now(timezone.utc)
        for attempt in range(12):
            if attempt:
                time.sleep(random.uniform(0.005, 0.03) * attempt)           # brief jittered backoff: only a burst of simultaneous starts ever gets here
            with self._sf() as s:
                dup = s.scalar(select(PreparationPack).where(PreparationPack.op_key == op_key, PreparationPack.user_id == user_id))
                if dup is not None:
                    return "duplicate", self._summary(dup)
                running = s.scalar(select(PreparationPack).where(PreparationPack.user_id == user_id, PreparationPack.opportunity_id == opportunity_id,
                                                                  PreparationPack.status == "generating"))
                if running is not None:
                    return "in_progress", self._summary(running)
                rev = (s.scalar(select(func.max(PreparationPack.revision)).where(PreparationPack.user_id == user_id, PreparationPack.opportunity_id == opportunity_id)) or 0) + 1
                row = PreparationPack(op_key=op_key, user_id=user_id, opportunity_id=opportunity_id, revision=rev, status="generating", schema_version=schema_version,
                                      created_at=moment, generation={"heartbeat_at": moment.isoformat()})
                s.add(row)
                try:
                    s.commit()
                except IntegrityError:
                    s.rollback()
                    other = s.scalar(select(PreparationPack).where((PreparationPack.op_key == op_key) | ((PreparationPack.user_id == user_id)
                                     & (PreparationPack.opportunity_id == opportunity_id) & (PreparationPack.status == "generating"))))
                    if other is not None and other.user_id == user_id:
                        return ("duplicate" if other.op_key == op_key else "in_progress"), self._summary(other)
                    continue                                                    # a revision collision with a finished row: recompute and retry
                return "created", self._summary(row)
        raise RuntimeError("could not allocate a Pack revision")

    def finish(self, pack_id: int, *, status: str, content: dict | None, generation: dict | None, failure_category: str | None = None,
               now: datetime | None = None) -> bool:
        """generating -> completed | failed | insufficient_evidence. Single-use: a finished row is never altered. A failure never touches any other revision."""
        with self._sf() as s:
            n = s.execute(update(PreparationPack).where(PreparationPack.id == pack_id, PreparationPack.status == "generating")
                          .values(status=status, content=content, generation=generation, failure_category=failure_category,
                                  completed_at=now or datetime.now(timezone.utc))).rowcount
            s.commit()
            return n == 1

    # ------------------------------------------------------------------------------------------------ reads
    def list_for_opportunity(self, user_id: int, opportunity_id: int) -> list[dict[str, Any]]:
        with self._sf() as s:
            rows = s.scalars(select(PreparationPack).where(PreparationPack.user_id == user_id, PreparationPack.opportunity_id == opportunity_id)
                             .order_by(PreparationPack.revision.desc(), PreparationPack.id.desc())).all()
            return [self._summary(r) for r in rows]

    def get(self, user_id: int, pack_id: int) -> dict[str, Any] | None:
        with self._sf() as s:
            p = s.scalar(select(PreparationPack).where(PreparationPack.id == pack_id, PreparationPack.user_id == user_id))
            return self._detail(p) if p else None

    def delete(self, user_id: int, pack_id: int) -> bool:
        with self._sf() as s:
            p = s.scalar(select(PreparationPack).where(PreparationPack.id == pack_id, PreparationPack.user_id == user_id))
            if p is None:
                return False
            s.delete(p)
            s.commit()
            return True
