"""Job repository + service (P10B-W10.9): enqueue, claim, lease, heartbeat, retry, cancel and diagnostics.

Concurrency lives in the DATABASE, never in process-local locks:

* PostgreSQL claim: ``SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`` then UPDATE in one short transaction.
* SQLite claim (no SKIP LOCKED): pick a candidate, then ONE conditional UPDATE guarded by ``state='queued'`` and the
  ``attempts`` value that was read. ``attempts`` changes on every claim, so it is a version token: exactly one
  competing worker sees ``rowcount == 1``; the others retry with a fresh read. SQLite's write lock serialises the
  UPDATEs; this is NOT equivalent to SKIP LOCKED (workers contend instead of skipping) and is documented as such.

The claim transaction ends before the handler runs. Every lifecycle write after the claim is guarded by
``state='running' AND lease_owner=<me> AND attempts=<claimed attempt>``, so a worker that lost its lease can never
overwrite a newer owner's result (it gets :class:`LeaseLost` and discards its outcome).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.admin_repository import _stage
from src.jobs.registry import (
    REGISTRY, SAFE_MESSAGES, JobTypeDef, backoff_seconds, reject_secret_like_keys,
)
from src.persistence import JOB_PRIORITIES, JOB_STATES, Job, JobWorker, utcnow

CLAIM_ATTEMPTS = 5
DEFAULT_LEASE_SECONDS = 60
WORKER_STALE_SECONDS = 60
MAX_PAGE_SIZE = 100
WORKER_RETENTION = timedelta(days=7)


class JobNotFound(Exception):
    pass


class JobValidationError(Exception):
    """Bad type, payload, priority or key. The message is safe to show (it never echoes the payload)."""


class JobStateConflict(Exception):
    pass


class LeaseLost(Exception):
    pass


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    public_id: str
    job_type: str
    payload: dict
    payload_version: int
    attempts: int
    max_attempts: int
    worker_id: str
    created_by_user_id: Optional[int]


def _utc(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt: datetime | None) -> str | None:
    dt = _utc(dt)
    return dt.isoformat() if dt else None


_PRIORITY_ORDER = case((Job.priority == "high", 0), (Job.priority == "normal", 1), else_=2)


class JobService:
    def __init__(self, session_factory: sessionmaker, registry: dict[str, JobTypeDef] | None = None,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._registry = registry if registry is not None else REGISTRY
        self._clock = clock

    # ------------------------------------------------------------------ enqueue
    def definition(self, job_type: str) -> JobTypeDef:
        defn = self._registry.get(job_type)
        if defn is None:
            raise JobValidationError("Unknown job type.")
        return defn

    def validate(self, job_type: str, payload: Any) -> tuple[JobTypeDef, dict]:
        defn = self.definition(job_type)
        if not isinstance(payload, dict):
            raise JobValidationError("The job input is not valid.")
        try:
            reject_secret_like_keys(payload)
            model = defn.payload_model.model_validate(payload)
        except Exception:  # noqa: BLE001 - never echo the submitted input
            raise JobValidationError("The job input is not valid.")
        return defn, model.model_dump()

    def enqueue(self, job_type: str, payload: Any, *, idempotency_key: str | None = None, priority: str = "normal",
                actor_user_id: int | None = None, available_at: datetime | None = None,
                audit: dict | None = None) -> tuple[dict, bool]:
        """The ONLY way to create a job. Returns (safe summary, created). With a key, an equivalent ACTIVE job
        (same type + key, queued or running) is returned instead of a duplicate (created=False)."""
        defn, clean = self.validate(job_type, payload)
        if priority not in JOB_PRIORITIES:
            raise JobValidationError("Unknown priority.")
        if idempotency_key is not None and not (1 <= len(idempotency_key) <= 120):
            raise JobValidationError("The idempotency key must be 1 to 120 characters.")
        now = self._clock()
        public_id = uuid.uuid4().hex
        try:
            with self._sf() as s:
                if idempotency_key is not None:
                    existing = self._active_by_key(s, job_type, idempotency_key)
                    if existing is not None:
                        return self._view(existing, now), False
                job = Job(public_id=public_id, job_type=job_type, state="queued", priority=priority,
                          payload_json=clean, payload_version=defn.payload_version, idempotency_key=idempotency_key,
                          attempts=0, max_attempts=defn.max_attempts, available_at=available_at or now,
                          created_by_user_id=actor_user_id, created_at=now, updated_at=now)
                s.add(job)
                _stage(s, {**audit, "target_id": public_id} if audit else None, job_public_id=public_id, job_type=job_type)
                s.commit()
                return self._view(job, now), True
        except IntegrityError:
            # Lost the enqueue race for the same active key: return the winner.
            with self._sf() as s:
                existing = self._active_by_key(s, job_type, idempotency_key) if idempotency_key else None
                if existing is None:
                    raise
                return self._view(existing, now), False

    @staticmethod
    def _active_by_key(s, job_type: str, key: str) -> Job | None:
        return s.scalar(select(Job).where(Job.job_type == job_type, Job.idempotency_key == key,
                                          Job.state.in_(("queued", "running"))))

    # ------------------------------------------------------------------ claim / lease
    def reap_expired(self, *, now: datetime | None = None) -> int:
        """Release leases that expired (worker crashed or stalled): back to queued, or terminal failed when attempts are
        exhausted. A crashed job is never marked succeeded."""
        now = now or self._clock()
        reaped = 0
        with self._sf() as s:
            rows = s.execute(select(Job.id, Job.attempts, Job.max_attempts, Job.lease_owner).where(
                Job.state == "running", Job.lease_expires_at < now)).all()
        for job_id, attempts, max_attempts, owner in rows:
            exhausted = attempts >= max_attempts
            values = dict(lease_owner=None, lease_expires_at=None, last_error_category="lease_expired",
                          last_error_message_safe=SAFE_MESSAGES["lease_expired"], updated_at=now)
            values.update(state="failed", finished_at=now) if exhausted else values.update(state="queued", available_at=now)
            with self._sf() as s:
                res = s.execute(update(Job).where(
                    Job.id == job_id, Job.state == "running", Job.lease_owner == owner, Job.attempts == attempts,
                    Job.lease_expires_at < now).values(**values))
                s.commit()
                reaped += res.rowcount or 0
                if exhausted and (res.rowcount or 0):
                    with self._sf() as s2:
                        pid = s2.scalar(select(Job.public_id).where(Job.id == job_id))
                        jtype = s2.scalar(select(Job.job_type).where(Job.id == job_id))
                    self._alert_failed(jtype or "unknown", pid or "")
        return reaped

    def claim(self, worker_id: str, *, now: datetime | None = None,
              job_types: tuple[str, ...] | None = None) -> ClaimedJob | None:
        now = now or self._clock()
        for _ in range(CLAIM_ATTEMPTS):
            with self._sf() as s:
                stmt = select(Job).where(Job.state == "queued", Job.available_at <= now,
                                         Job.attempts < Job.max_attempts)
                if job_types:
                    stmt = stmt.where(Job.job_type.in_(job_types))
                stmt = stmt.order_by(_PRIORITY_ORDER, Job.available_at, Job.id).limit(1)
                if s.get_bind().dialect.name == "postgresql":
                    row = s.scalars(stmt.with_for_update(skip_locked=True)).first()
                    if row is None:
                        return None
                    self._mark_running(row, worker_id, now)
                    s.commit()
                    return self._claimed(row, worker_id)
                row = s.scalars(stmt).first()
                if row is None:
                    return None
                seen, lease = row.attempts, self._lease_seconds(row.job_type)
                res = s.execute(update(Job).where(
                    Job.id == row.id, Job.state == "queued", Job.attempts == seen).values(
                    state="running", attempts=seen + 1, lease_owner=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease), heartbeat_at=now, started_at=now,
                    finished_at=None, updated_at=now))
                if res.rowcount != 1:      # another worker won the race: no attempt consumed, look again
                    s.rollback()
                    continue
                s.commit()
                return ClaimedJob(id=row.id, public_id=row.public_id, job_type=row.job_type,
                                  payload=dict(row.payload_json or {}), payload_version=row.payload_version,
                                  attempts=seen + 1, max_attempts=row.max_attempts, worker_id=worker_id,
                                  created_by_user_id=row.created_by_user_id)
        return None

    def _lease_seconds(self, job_type: str) -> int:
        defn = self._registry.get(job_type)
        return defn.lease_seconds if defn else DEFAULT_LEASE_SECONDS

    def _mark_running(self, row: Job, worker_id: str, now: datetime) -> None:
        row.state, row.attempts, row.lease_owner = "running", row.attempts + 1, worker_id
        row.lease_expires_at = now + timedelta(seconds=self._lease_seconds(row.job_type))
        row.heartbeat_at, row.started_at, row.finished_at, row.updated_at = now, now, None, now

    @staticmethod
    def _claimed(row: Job, worker_id: str) -> ClaimedJob:
        return ClaimedJob(id=row.id, public_id=row.public_id, job_type=row.job_type,
                          payload=dict(row.payload_json or {}), payload_version=row.payload_version,
                          attempts=row.attempts, max_attempts=row.max_attempts, worker_id=worker_id,
                          created_by_user_id=row.created_by_user_id)

    @staticmethod
    def _owned(claim: ClaimedJob):
        return (Job.id == claim.id, Job.state == "running", Job.lease_owner == claim.worker_id,
                Job.attempts == claim.attempts)

    def heartbeat(self, claim: ClaimedJob, *, now: datetime | None = None) -> None:
        """Renew the lease. Only the current owner of an UNEXPIRED lease on a running job may renew."""
        now = now or self._clock()
        with self._sf() as s:
            res = s.execute(update(Job).where(*self._owned(claim), Job.lease_expires_at > now).values(
                lease_expires_at=now + timedelta(seconds=self._lease_seconds(claim.job_type)),
                heartbeat_at=now, updated_at=now))
            s.commit()
        if res.rowcount != 1:
            raise LeaseLost(claim.public_id)

    def complete(self, claim: ClaimedJob, *, now: datetime | None = None) -> None:
        now = now or self._clock()
        with self._sf() as s:
            res = s.execute(update(Job).where(*self._owned(claim)).values(
                state="succeeded", finished_at=now, lease_owner=None, lease_expires_at=None,
                last_error_category=None, last_error_message_safe=None, updated_at=now))
            s.commit()
        if res.rowcount != 1:
            raise LeaseLost(claim.public_id)

    def fail(self, claim: ClaimedJob, category: str, *, retryable: bool, now: datetime | None = None) -> str:
        """Record a failed attempt. Returns 'retry_scheduled' (back to queued with a future available_at; the worker
        never sleeps waiting) or 'failed' (terminal: non-retryable, or max attempts reached)."""
        now = now or self._clock()
        if category not in SAFE_MESSAGES:
            category = "internal_error"
        defn = self._registry.get(claim.job_type)
        will_retry = retryable and defn is not None and claim.attempts < claim.max_attempts
        values = dict(lease_owner=None, lease_expires_at=None, last_error_category=category,
                      last_error_message_safe=SAFE_MESSAGES[category], updated_at=now)
        if will_retry:
            values.update(state="queued", available_at=now + timedelta(seconds=backoff_seconds(defn, claim.attempts)))
        else:
            values.update(state="failed", finished_at=now)
        with self._sf() as s:
            res = s.execute(update(Job).where(*self._owned(claim)).values(**values))
            s.commit()
        if res.rowcount != 1:
            raise LeaseLost(claim.public_id)
        if not will_retry:
            self._alert_failed(claim.job_type, claim.public_id)
        return "retry_scheduled" if will_retry else "failed"

    def _alert_failed(self, job_type: str, public_id: str) -> None:
        """A terminal job failure raises ONE deduplicated in-app Admin alert per job type (P10B-W10.13). Best-effort; never raises."""
        from src.admin_security.alerts import observe_job_failed

        observe_job_failed(self._sf, job_type=job_type, job_public_id=public_id)

    # ------------------------------------------------------------------ admin actions (state machine)
    def cancel(self, public_id: str, *, audit: dict | None = None) -> dict:
        """Queued jobs only. A running job cannot be interrupted safely, so it is never cancellable."""
        now = self._clock()
        with self._sf() as s:
            job = self._by_public(s, public_id)
            defn = self._registry.get(job.job_type)
            if job.state != "queued" or (defn is not None and not defn.cancellable_when_queued):
                raise JobStateConflict("Only a queued job can be cancelled.")
            res = s.execute(update(Job).where(Job.id == job.id, Job.state == "queued").values(
                state="cancelled", finished_at=now, updated_at=now))
            if res.rowcount != 1:
                s.rollback()
                raise JobStateConflict("The job is no longer queued.")
            _stage(s, audit, job_public_id=public_id, job_type=job.job_type, old_state="queued", new_state="cancelled")
            s.commit()
            s.refresh(job)
            return self._view(job, now)

    def retry(self, public_id: str, *, audit: dict | None = None) -> dict:
        """Requeue the SAME durable job from terminal 'failed' when its type allows it. attempts resets to 0 (the
        number of manual retries is kept in manual_retries); the handler must be replay-safe anyway."""
        now = self._clock()
        try:
            with self._sf() as s:
                job = self._by_public(s, public_id)
                defn = self._registry.get(job.job_type)
                if job.state != "failed" or defn is None or not defn.manual_retry:
                    raise JobStateConflict("Only a failed job of a retryable type can be retried.")
                res = s.execute(update(Job).where(Job.id == job.id, Job.state == "failed").values(
                    state="queued", attempts=0, manual_retries=job.manual_retries + 1, available_at=now,
                    finished_at=None, last_error_category=None, last_error_message_safe=None,
                    max_attempts=defn.max_attempts, updated_at=now))
                if res.rowcount != 1:
                    s.rollback()
                    raise JobStateConflict("The job is no longer failed.")
                _stage(s, audit, job_public_id=public_id, job_type=job.job_type, old_state="failed", new_state="queued")
                s.commit()
                s.refresh(job)
                return self._view(job, now)
        except IntegrityError:
            raise JobStateConflict("An equivalent job is already active.")

    # ------------------------------------------------------------------ read models
    @staticmethod
    def _by_public(s, public_id: str) -> Job:
        job = s.scalar(select(Job).where(Job.public_id == public_id))
        if job is None:
            raise JobNotFound(public_id)
        return job

    def _view(self, job: Job, now: datetime) -> dict:
        defn = self._registry.get(job.job_type)
        try:
            summary = defn.summarize(defn.payload_model.model_validate(job.payload_json)) if defn else {}
        except Exception:  # noqa: BLE001
            summary = {}
        expires = _utc(job.lease_expires_at)
        held = job.state == "running"
        return {
            "public_id": job.public_id, "job_type": job.job_type, "type_label": defn.label if defn else "Unknown job type",
            "state": job.state, "priority": job.priority, "attempts": job.attempts, "max_attempts": job.max_attempts,
            "manual_retries": job.manual_retries, "available_at": _iso(job.available_at),
            "created_at": _iso(job.created_at), "updated_at": _iso(job.updated_at),
            "started_at": _iso(job.started_at), "finished_at": _iso(job.finished_at),
            "error_category": job.last_error_category, "error_message": job.last_error_message_safe,
            "lease": {"held": held, "owner": job.lease_owner if held else None,
                      "expires_at": _iso(expires) if held else None,
                      "heartbeat_at": _iso(job.heartbeat_at) if held else None,
                      "stale": bool(held and expires is not None and expires < now)},
            "waiting_for_retry": bool(job.state == "queued" and job.attempts > 0 and _utc(job.available_at) > now),
            "payload_summary": summary,
            "can_retry": bool(job.state == "failed" and defn is not None and defn.manual_retry),
            "can_cancel": bool(job.state == "queued" and (defn is None or defn.cancellable_when_queued)),
        }

    def get(self, public_id: str) -> dict:
        now = self._clock()
        with self._sf() as s:
            return self._view(self._by_public(s, public_id), now)

    def list(self, *, state: str | None = None, job_type: str | None = None, priority: str | None = None,
             q: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = max(1, int(page)), max(1, min(int(page_size), MAX_PAGE_SIZE))
        now = self._clock()
        conds = []
        if state:
            if state not in JOB_STATES:
                raise JobValidationError("Unknown state.")
            conds.append(Job.state == state)
        if job_type:
            conds.append(Job.job_type == job_type)
        if priority:
            if priority not in JOB_PRIORITIES:
                raise JobValidationError("Unknown priority.")
            conds.append(Job.priority == priority)
        if q:
            conds.append(Job.public_id == q.strip().lower())    # public id only: payloads are never searched
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(Job).where(*conds)) or 0
            rows = s.scalars(select(Job).where(*conds).order_by(Job.created_at.desc(), Job.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._view(r, now) for r in rows], "total": total, "page": page, "page_size": page_size}

    # ------------------------------------------------------------------ diagnostics / workers
    def stats(self, *, now: datetime | None = None) -> dict:
        now = now or self._clock()
        with self._sf() as s:
            by_state = {st: 0 for st in JOB_STATES}
            by_type: dict[str, dict[str, int]] = {}
            for jt, st, n in s.execute(select(Job.job_type, Job.state, func.count()).group_by(Job.job_type, Job.state)):
                by_state[st] += n
                by_type.setdefault(jt, {k: 0 for k in JOB_STATES})[st] = n
            oldest = s.scalar(select(func.min(Job.available_at)).where(Job.state == "queued", Job.available_at <= now))
            stale = s.scalar(select(func.count()).select_from(Job).where(
                Job.state == "running", Job.lease_expires_at < now)) or 0
            waiting = s.scalar(select(func.count()).select_from(Job).where(
                Job.state == "queued", Job.attempts > 0, Job.available_at > now)) or 0
            workers = s.scalars(select(JobWorker).order_by(JobWorker.last_seen_at.desc()).limit(10)).all()
            recent = [w for w in workers if w.status == "running"
                      and _utc(w.last_seen_at) >= now - timedelta(seconds=WORKER_STALE_SECONDS)]
            last_seen = max((_utc(w.last_seen_at) for w in workers), default=None)
        oldest = _utc(oldest)
        return {
            "queue": {"queued": by_state["queued"], "running": by_state["running"], "failed": by_state["failed"],
                      "succeeded": by_state["succeeded"], "cancelled": by_state["cancelled"],
                      "retry_waiting": waiting, "stale_leases": stale,
                      "oldest_ready_age_seconds": int((now - oldest).total_seconds()) if oldest else None},
            "by_type": [{"job_type": t, "label": (self._registry[t].label if t in self._registry else t), **c}
                        for t, c in sorted(by_type.items())],
            # Worker presence is reported from worker heartbeats ONLY; queue depth never implies a healthy worker.
            "workers": {"seen_recently": len(recent), "last_seen_at": _iso(last_seen),
                        "stale_after_seconds": WORKER_STALE_SECONDS,
                        "items": [{"worker_id": w.worker_id, "status": w.status, "started_at": _iso(w.started_at),
                                   "last_seen_at": _iso(w.last_seen_at), "jobs_succeeded": w.jobs_succeeded,
                                   "jobs_failed": w.jobs_failed,
                                   "active": w in recent} for w in workers]},
        }

    def touch_worker(self, worker_id: str, *, now: datetime | None = None, status: str = "running",
                     succeeded: int = 0, failed: int = 0) -> None:
        now = now or self._clock()
        with self._sf() as s:
            row = s.get(JobWorker, worker_id)
            if row is None:
                s.execute(JobWorker.__table__.delete().where(
                    JobWorker.status == "stopped", JobWorker.last_seen_at < now - WORKER_RETENTION))
                row = JobWorker(worker_id=worker_id, status=status, started_at=now, last_seen_at=now,
                                jobs_succeeded=0, jobs_failed=0)
                s.add(row)
            row.status, row.last_seen_at = status, now
            row.jobs_succeeded += succeeded
            row.jobs_failed += failed
            s.commit()
