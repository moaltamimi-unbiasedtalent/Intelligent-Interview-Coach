"""Reconciliation scheduling contract (W12.4D-E): the SMALLEST durable mechanism, reusing the W10.9 job queue and worker.

``schedule_tick`` is a stateless, one-shot, idempotent "enqueue the bounded reconciliation sweep for this time bucket". Run it from any scheduler (cron, a
platform timer) as ``python -m src.billing.scheduler``; there is no resident loop, so shutdown is trivially safe (a tick that is interrupted has changed
nothing but, at most, one queued job). Idempotency is per time bucket and holds across concurrent scheduler instances (one job per bucket whatever the job's state).
Work is bounded by the sweep batch size; leases, retries, back-off and failure visibility are the job system's, and the sweep itself tolerates a provider
outage per item. DISABLED BY DEFAULT: ``policy.RECONCILE_SCHEDULER_ENABLED`` is a code constant that stays False until the real provider-state reader,
credentials, eligibility and operational approval exist, and a tick additionally refuses while the runtime reader is the Null reader. No Stripe call is made here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.billing import policy as P
from src.persistence import Job, utcnow


def schedule_tick(session_factory, jobs, *, reader_available: bool, enabled: bool = P.RECONCILE_SCHEDULER_ENABLED, now: datetime | None = None,
                  batch: int = P.RECONCILE_SWEEP_BATCH, bucket_seconds: int = P.RECONCILE_SCHEDULE_BUCKET_SECONDS) -> dict:
    now = now or utcnow()
    if enabled is not True:
        return {"scheduled": False, "reason": "scheduler_disabled"}
    if not reader_available:
        return {"scheduled": False, "reason": "provider_state_reader_unavailable"}
    key = f"bsweep:{int(now.timestamp()) // bucket_seconds}"
    with session_factory() as s:
        if s.scalar(select(Job.id).where(Job.job_type == P.JOB_PROVIDER_RECONCILE, Job.idempotency_key == key).limit(1)) is not None:
            return {"scheduled": False, "reason": "already_scheduled_for_this_bucket", "bucket": key}
    view, created = jobs.enqueue(P.JOB_PROVIDER_RECONCILE, {"batch": batch}, idempotency_key=key)
    return {"scheduled": bool(created), "reason": "scheduled" if created else "already_scheduled_for_this_bucket", "bucket": key, "job": view["public_id"]}


def main() -> int:   # pragma: no cover - process entrypoint
    from src.application.factories import build_repository
    from src.billing.wiring import build_provider_events
    from src.config import load_config
    from src.jobs.service import JobService

    repo = build_repository(load_config())
    svc = build_provider_events(repo.session_factory)
    out: dict[str, Any] = schedule_tick(repo.session_factory, JobService(repo.session_factory), reader_available=svc.reader_available())
    print(out)
    return 0


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(main())
