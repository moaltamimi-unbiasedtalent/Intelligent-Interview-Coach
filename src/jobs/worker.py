"""Separate worker process (P10B-W10.9): ``python -m src.jobs.worker``. Never started by the API.

One job at a time per process; scale by running more processes (correctness comes from DB claiming, not locks).
The loop is split into :meth:`Worker.run_once` (fully injectable and testable) and :meth:`Worker.run_forever`.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from src.jobs.registry import REGISTRY, JobContext, JobError, JobTypeDef, RETRYABLE_CATEGORIES
from src.jobs.service import ClaimedJob, JobService, LeaseLost
from src.persistence import utcnow

log = logging.getLogger("ask4mo.jobs.worker")

POLL_MIN, POLL_MAX, POLL_DEFAULT = 0.5, 60.0, 2.0


def poll_seconds_from_env(env: dict[str, str] | None = None) -> float:
    raw = (env if env is not None else os.environ).get("JOB_WORKER_POLL_SECONDS")
    try:
        value = float(raw) if raw else POLL_DEFAULT
    except ValueError:
        value = POLL_DEFAULT
    return max(POLL_MIN, min(POLL_MAX, value))


class Worker:
    def __init__(self, service: JobService, registry: dict[str, JobTypeDef] | None = None, *,
                 worker_id: str | None = None, clock: Callable[[], datetime] = utcnow, secret_store: Any = None,
                 probes: Any = None, poll_seconds: float = POLL_DEFAULT, services: Any = None) -> None:
        self.service = service
        self.registry = registry if registry is not None else REGISTRY
        self.worker_id = worker_id or uuid.uuid4().hex[:16]     # an operational instance id: no host, no address
        self._clock = clock
        self._store = secret_store
        self._probes = probes
        self._services = services
        self.poll_seconds = max(POLL_MIN, min(POLL_MAX, poll_seconds))

    def run_once(self) -> str:
        """One cycle: presence, reap expired leases, claim at most one job, run it OUTSIDE any DB transaction,
        finalise. Returns idle | succeeded | retry_scheduled | failed | lease_lost."""
        self.service.touch_worker(self.worker_id, now=self._clock())
        self.service.reap_expired(now=self._clock())
        claim = self.service.claim(self.worker_id, now=self._clock())
        if claim is None:
            return "idle"
        outcome = self._execute(claim)
        self.service.touch_worker(self.worker_id, now=self._clock(),
                                  succeeded=int(outcome == "succeeded"), failed=int(outcome in ("failed", "retry_scheduled")))
        return outcome

    def _execute(self, claim: ClaimedJob) -> str:
        defn = self.registry.get(claim.job_type)
        try:
            if defn is None:
                return self.service.fail(claim, "unknown_job_type", retryable=False)
            try:
                payload = defn.payload_model.model_validate(claim.payload)
            except Exception:  # noqa: BLE001
                return self.service.fail(claim, "invalid_payload", retryable=False)
            ctx = JobContext(job_public_id=claim.public_id, attempt=claim.attempts,
                             created_by_user_id=claim.created_by_user_id, session_factory=self.service._sf,
                             secret_store=self._store, probes=self._probes, services=self._services,
                             max_attempts=claim.max_attempts,
                             heartbeat=lambda: self.service.heartbeat(claim, now=self._clock()))
            try:
                defn.handler(payload, ctx)
            except LeaseLost:
                raise
            except JobError as exc:
                return self.service.fail(claim, exc.category, retryable=exc.category in RETRYABLE_CATEGORIES)
            except Exception as exc:  # noqa: BLE001 - classify as a permanent internal error; text is never stored
                log.error("job %s (%s) failed: %s", claim.public_id, claim.job_type, type(exc).__name__)
                return self.service.fail(claim, "internal_error", retryable=False)
            self.service.complete(claim, now=self._clock())
            return "succeeded"
        except LeaseLost:
            log.warning("job %s lost its lease; result discarded", claim.public_id)
            return "lease_lost"

    def run_forever(self, stop: threading.Event, wait: Callable[[float], Any] | None = None) -> None:
        wait = wait or stop.wait
        try:
            while not stop.is_set():
                if self.run_once() == "idle":
                    wait(self.poll_seconds)
        finally:
            self.service.touch_worker(self.worker_id, now=self._clock(), status="stopped")


def main() -> None:   # pragma: no cover - process entrypoint
    from src.application.factories import build_repository
    from src.config import load_config
    from src.secret_store import get_secret_store

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    repo = build_repository(load_config())
    from src.copilot.config import load_config as load_copilot_config
    from src.knowledge_admin.wiring import build_worker_services

    from src.privacy.wiring import build_privacy_runtime

    services = build_worker_services(repo.session_factory, load_copilot_config())
    services.privacy = build_privacy_runtime(repo.session_factory, load_config())
    from src.billing.wiring import build_billing_runtime

    services.billing = build_billing_runtime(repo.session_factory, JobService(repo.session_factory))
    from types import SimpleNamespace

    services.ai_admin = SimpleNamespace(session_factory=repo.session_factory)    # W10.7 evaluation job (no provider, no secret)
    worker = Worker(JobService(repo.session_factory), secret_store=get_secret_store(), poll_seconds=poll_seconds_from_env(),
                    services=services)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    log.info("job worker %s started (poll %.1fs)", worker.worker_id, worker.poll_seconds)
    worker.run_forever(stop)
    log.info("job worker %s stopped", worker.worker_id)


if __name__ == "__main__":   # pragma: no cover
    main()
