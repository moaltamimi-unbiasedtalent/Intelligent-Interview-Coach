"""W10.9 job types for privacy operations (P10B-W10.10). Payloads are IDs only: never candidate data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.application import admin_permissions as perm
from src.jobs.registry import JobTypeDef
from src.privacy import policy as P, runtime as R


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeletePayload(_Strict):
    request_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


class BackfillPayload(_Strict):
    after_id: int = Field(default=0, ge=0)


class PurgePayload(_Strict):
    run_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


def job_types() -> list[JobTypeDef]:
    deps = ("privacy", "checkpoint_store")
    return [
        JobTypeDef(code=P.JOB_ACCOUNT_DELETE, label="Privacy: delete account (requested)", payload_model=DeletePayload,
                   handler=lambda p, ctx: R.run_account_delete(p.request_id, ctx), summarize=lambda p: {"request": p.request_id},
                   idempotency="AccountDeletionService is idempotent; leftover checkpoint runs are tracked in the ownership index until purged; completion is guarded.",
                   max_attempts=5, lease_seconds=300, backoff_base_seconds=60, backoff_cap_seconds=900, manual_retry=True,
                   admin_enqueue=False, dependencies=deps),
        JobTypeDef(code=P.JOB_BACKFILL, label="Privacy: index historical preparation runs", payload_model=BackfillPayload,
                   handler=lambda p, ctx: R.run_backfill(p.after_id, ctx), summarize=lambda p: {"after_id": str(p.after_id)},
                   idempotency="Upserts by run id after verifying the checkpoint's recorded owner; bounded batches; never scans the store.",
                   max_attempts=3, lease_seconds=300, backoff_base_seconds=60, backoff_cap_seconds=600, manual_retry=True,
                   admin_enqueue=False, requires_permission=perm.PRIVACY_EXECUTE, dependencies=deps),
        JobTypeDef(code=P.JOB_PURGE, label="Privacy: purge a preparation run", payload_model=PurgePayload,
                   handler=lambda p, ctx: R.run_purge(p.run_id, ctx), summarize=lambda p: {"run": p.run_id},
                   idempotency="Delete-thread is idempotent; the index row is removed only after a successful purge.",
                   max_attempts=5, lease_seconds=120, backoff_base_seconds=60, backoff_cap_seconds=900, manual_retry=True,
                   admin_enqueue=False, dependencies=deps),
    ]
