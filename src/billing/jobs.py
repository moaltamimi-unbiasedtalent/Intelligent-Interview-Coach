"""W10.9 job types for billing (P10B-W10.5). IDs only: a job payload never holds money, card data, a credential or a provider body."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.billing import policy as P
from src.billing.provider import ProviderRejected, ProviderRetryable
from src.billing.service import BillingNotFound, BillingService, BillingValidationError
from src.jobs.registry import JobTypeDef, PermanentJobError, RetryableJobError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventPayload(_Strict):
    event_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


class RefundPayload(_Strict):
    refund_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


def _service(ctx) -> BillingService:
    rt = getattr(ctx.services, "billing", None) if ctx.services is not None else None
    if rt is None:
        raise PermanentJobError("configuration_error")
    return BillingService(rt.session_factory, provider=rt.provider, mode=rt.mode, jobs=rt.jobs)


def _process_event(p: EventPayload, ctx) -> None:
    svc = _service(ctx)
    try:
        svc.process_event(p.event_id)
    except (BillingValidationError, BillingNotFound):
        raise PermanentJobError("invalid_payload")


def _refund(p: RefundPayload, ctx) -> None:
    svc = _service(ctx)
    try:
        svc.execute_refund(p.refund_id, last_attempt=ctx.attempt >= ctx.max_attempts)
    except ProviderRetryable:
        raise RetryableJobError("unavailable")
    except ProviderRejected:
        raise PermanentJobError("unsupported")
    except BillingNotFound:
        raise PermanentJobError("invalid_payload")


def job_types() -> list[JobTypeDef]:
    deps = ("billing",)
    return [
        JobTypeDef(code=P.JOB_PROCESS_EVENT, label="Billing: process a normalised event (mock)", payload_model=EventPayload, handler=_process_event,
                   summarize=lambda p: {"event": p.event_id}, max_attempts=5, lease_seconds=60, backoff_base_seconds=30, backoff_cap_seconds=600,
                   idempotency="Events are unique per provider event id; every upsert is keyed on provider ids; a processed event is a no-op.",
                   manual_retry=True, admin_enqueue=False, dependencies=deps),
        JobTypeDef(code=P.JOB_REFUND, label="Billing: execute an approved MOCK refund", payload_model=RefundPayload, handler=_refund,
                   summarize=lambda p: {"refund": p.refund_id}, max_attempts=4, lease_seconds=120, backoff_base_seconds=60, backoff_cap_seconds=900,
                   idempotency="The provider gets a stable idempotency key (same key, same provider refund id); the local update is state-guarded, so a replay after a crash counts once.",
                   manual_retry=True, admin_enqueue=False, dependencies=deps),
    ]
