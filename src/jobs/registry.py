"""Code-defined job types, error classification and backoff (P10B-W10.9).

Admin can never name a handler, a function or a command: a job type exists only if it is defined here. Each type owns
its payload schema, handler, retry policy, lease length and idempotency strategy. Handlers receive a validated
payload and a context; they never touch job rows (the worker/service layer owns the lifecycle).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---- errors ---------------------------------------------------------------------------------------------------
RETRYABLE_CATEGORIES = frozenset({"transient", "timeout", "rate_limited", "unavailable"})

# Fixed, safe wording per category. Exception text is NEVER persisted: it may contain a credential or private data.
SAFE_MESSAGES = {
    "transient": "A temporary error occurred; the job will be retried.",
    "timeout": "The operation timed out.",
    "rate_limited": "The upstream service asked to slow down.",
    "unavailable": "A required service was unavailable.",
    "invalid_payload": "The job input was not valid.",
    "configuration_error": "A required integration is not configured or was rejected.",
    "unsupported": "This operation is not supported.",
    "unknown_job_type": "No handler is registered for this job type.",
    "lease_expired": "The worker stopped responding before the job finished.",
    "internal_error": "The job failed with an unexpected error.",
}


class JobError(Exception):
    """Base class: a handler raises one of the subclasses to classify its failure."""

    category = "internal_error"


class RetryableJobError(JobError):
    def __init__(self, category: str = "transient") -> None:
        if category not in RETRYABLE_CATEGORIES:
            raise ValueError("not a retryable category")
        super().__init__(category)
        self.category = category


class PermanentJobError(JobError):
    def __init__(self, category: str = "internal_error") -> None:
        if category in RETRYABLE_CATEGORIES or category not in SAFE_MESSAGES:
            raise ValueError("not a permanent category")
        super().__init__(category)
        self.category = category


# ---- handler context ------------------------------------------------------------------------------------------
@dataclass
class JobContext:
    job_public_id: str
    attempt: int
    created_by_user_id: Optional[int]
    session_factory: Any
    secret_store: Any = None
    probes: Any = None
    services: Any = None            # optional worker-provided runtime services (e.g. the knowledge runtime)
    max_attempts: int = 1           # lets a handler record a domain failure on its LAST attempt
    heartbeat: Callable[[], None] = lambda: None   # renews the lease for long handlers; short jobs never call it

    # Cancellation of a RUNNING job is not supported (documented): handlers are never interrupted.
    cancel_requested: bool = False


# ---- job type definition --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class JobTypeDef:
    code: str
    label: str
    payload_model: type[BaseModel]
    handler: Callable[[BaseModel, JobContext], None]
    summarize: Callable[[BaseModel], dict]
    idempotency: str                      # documented strategy (replay safety)
    max_attempts: int = 3
    lease_seconds: int = 60
    backoff_base_seconds: int = 30
    backoff_cap_seconds: int = 900
    manual_retry: bool = True
    cancellable_when_queued: bool = True
    admin_enqueue: bool = False
    requires_permission: Optional[str] = None      # additional permission needed to enqueue this type
    dependencies: tuple[str, ...] = ()
    payload_version: int = 1


def backoff_seconds(defn: JobTypeDef, attempt: int) -> int:
    """Deterministic bounded exponential backoff: base x 2^(attempt-1), capped. No jitter, no sleeping."""
    attempt = max(1, attempt)
    return min(defn.backoff_cap_seconds, defn.backoff_base_seconds * (2 ** min(attempt - 1, 20)))


_SECRET_KEY_FRAGMENTS = ("secret", "token", "password", "passwd", "credential", "authorization", "api_key",
                         "apikey", "bearer", "cookie", "private_key")


def reject_secret_like_keys(payload: Any) -> None:
    """Defence in depth: a payload may never carry a credential-shaped key, whatever the job type's schema says."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            low = str(key).lower()
            if any(f in low for f in _SECRET_KEY_FRAGMENTS):
                raise ValueError("payload key not allowed")
            reject_secret_like_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            reject_secret_like_keys(item)


# ---- initial job types ----------------------------------------------------------------------------------------
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DiagnosticPayload(_Strict):
    label: str = Field(min_length=1, max_length=40)

    @field_validator("label")
    @classmethod
    def _plain(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9 _.-]+", v):
            raise ValueError("label may contain letters, digits, space, '_', '.' and '-'")
        return v


def _diagnostic(payload: DiagnosticPayload, ctx: JobContext) -> None:
    """Operational no-op: proves the queue, worker and lease path end to end. It has no side effect at all."""
    return None


class IntegrationTestPayload(_Strict):
    integration_code: str = Field(min_length=1, max_length=40)

    @field_validator("integration_code")
    @classmethod
    def _known(cls, v: str) -> str:
        from src.integrations import REGISTRY

        defn = REGISTRY.get(v)
        if defn is None or not defn.test_supported:
            raise ValueError("unknown or untestable integration")
        return v


def _integration_test(payload: IntegrationTestPayload, ctx: JobContext) -> None:
    """Runs the SAME bounded W10.6 manual probe (adapter-defined destination, no admin URL). Replay-safe: the result
    row is an overwrite of the latest test, so running twice leaves exactly one current result."""
    from src.integrations import IntegrationNotFound, IntegrationService, IntegrationTestUnsupported

    service = IntegrationService(ctx.session_factory, ctx.secret_store, probes=ctx.probes)
    try:
        result = service.run_test(payload.integration_code, actor_user_id=ctx.created_by_user_id, audit=None)
    except IntegrationNotFound:
        raise PermanentJobError("invalid_payload")
    except IntegrationTestUnsupported:
        raise PermanentJobError("unsupported")
    if result["outcome"] == "success":
        return
    category = result["category"]
    if category in RETRYABLE_CATEGORIES:
        raise RetryableJobError(category)
    raise PermanentJobError("configuration_error")


def build_registry() -> dict[str, JobTypeDef]:
    from src.application import admin_permissions as perm

    defs = [
        JobTypeDef(
            code="diagnostic_noop", label="Operational diagnostic (no-op)", payload_model=DiagnosticPayload,
            handler=_diagnostic, summarize=lambda p: {"label": p.label},
            idempotency="No side effect, so replay is trivially safe.",
            max_attempts=2, lease_seconds=30, backoff_base_seconds=10, backoff_cap_seconds=60, admin_enqueue=True),
        JobTypeDef(
            code="integration_connection_test", label="Integration connection test",
            payload_model=IntegrationTestPayload, handler=_integration_test,
            summarize=lambda p: {"integration": p.integration_code},
            idempotency="The test result row is overwritten with the latest outcome; replay leaves one current result.",
            max_attempts=3, lease_seconds=60, backoff_base_seconds=30, backoff_cap_seconds=300,
            admin_enqueue=True, requires_permission=perm.INTEGRATIONS_MANAGE, dependencies=("integrations",)),
    ]
    from src.knowledge_admin import jobs as kjobs

    from src.privacy import jobs as pjobs

    defs += kjobs.job_types()
    defs += pjobs.job_types()
    return {d.code: d for d in defs}


REGISTRY: dict[str, JobTypeDef] = build_registry()
