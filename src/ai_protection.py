"""AI cost protection and usage metering foundation (W12.4D-P2-A).

One seam for the provider-backed Practice and Career operations:

* ADMISSION (``ai_operation`` dependency): operator pause (durable, refuses BEFORE any provider is built), then a per-user request ceiling
  (``cost_interview_user`` / ``cost_career_user``) plus the global ceiling. The unit of every ceiling is REQUESTS per window (not tokens, not money, not
  weighted operations). **Observe mode is the default**: ``AI_COST_LIMITS_ENFORCED = False`` is a code constant, so today nothing is refused for exceeding a
  ceiling; the would-be refusal is recorded (``limit_observed``) so a rollout can be sized from evidence. Enforcement is a reviewed, owner-approved release
  that flips the constant. The pause switch is always effective (it is an operator decision, not a quota).
* METERING: the provider clients report every HTTP attempt, every completed call (with the provider's token and cost figures when present) and every
  failure into the current operation scope. On exit ONE ``ai_operation_events`` row is written: a LOGICAL operation with its provider attempts, KNOWN tokens
  and cost (NULL when unknown, never 0), latency and a bounded failure category. No prompt, answer, document, transcript, model response or credential is
  ever recorded.

Nothing here reads a plan or entitlement: tier allowances are a later, separately approved wave (P2-B onward). Existing candidate access is unchanged.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

log = logging.getLogger("ai.protection")

# A code constant like the billing gates: no setting, startup or Admin action can turn limit ENFORCEMENT on. Observe mode records and refuses nothing.
AI_COST_LIMITS_ENFORCED = False

# workflow -> (pausable capability, per-user bucket). Existing, previously UNAPPLIED buckets are reused; no new number is invented.
WORKFLOWS = {
    "practice": ("practice_ai", "cost_interview_user"),
    "career": ("career_ai", "cost_career_user"),
}
PAUSE_CAPABILITIES = tuple(c for c, _b in WORKFLOWS.values())

_FAILURE_BOUND = 32


class AiUsageLimitError(Exception):
    """A per-user safety ceiling for AI-generated work was exceeded (enforcement mode only). Carries only safe, candidate-displayable facts."""

    def __init__(self, workflow: str, retry_after: int) -> None:
        super().__init__("ai_usage_limit")
        self.workflow = workflow
        self.retry_after = max(1, int(retry_after))


@dataclass
class AiOperationScope:
    """Mutable evidence for ONE logical operation. Written to from provider-client code (possibly other threads), so every update is locked."""

    user_id: int
    workflow: str
    operation: str
    op_key: str
    started: float = field(default_factory=time.perf_counter)
    started_at: datetime | None = None
    attempts: int = 0                  # HTTP attempts actually made (OpenRouter client: exact)
    llm_calls: int = 0                 # model invocations started (LangChain path: SDK-internal retries are invisible)
    exact_attempts: bool = False
    calls_ok: int = 0
    calls_failed: int = 0
    unknown_usage_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    known_usage_calls: int = 0
    cost_micros: int = 0
    cost_known_calls: int = 0
    latency_ms: int = 0
    models: list[str] = field(default_factory=list)
    failure_category: str | None = None
    limit_observed: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # -- evidence (called by provider clients through the module-level helpers below) --
    def attempt(self) -> None:
        with self._lock:
            self.attempts += 1
            self.exact_attempts = True

    def call_started(self) -> None:
        with self._lock:
            self.llm_calls += 1

    def call_ok(self, *, model: str | None, input_tokens: int | None, output_tokens: int | None, cost_usd: float | None, latency_ms: int | None) -> None:
        with self._lock:
            self.calls_ok += 1
            if model and model not in self.models and len(self.models) < 4:
                self.models.append(str(model)[:80])
            if input_tokens is None or output_tokens is None or (input_tokens == 0 and output_tokens == 0):
                self.unknown_usage_calls += 1            # a real completion consumes tokens: zero means "not reported", never "free"
            else:
                self.known_usage_calls += 1
                self.input_tokens += int(input_tokens)
                self.output_tokens += int(output_tokens)
            if cost_usd is not None:
                self.cost_known_calls += 1
                self.cost_micros += int(round(float(cost_usd) * 1_000_000))
            if latency_ms is not None:
                self.latency_ms += int(latency_ms)

    def call_failed(self, category: str | None, latency_ms: int | None) -> None:
        with self._lock:
            self.calls_failed += 1
            self.failure_category = (category or "provider_error")[:_FAILURE_BOUND]
            if latency_ms is not None:
                self.latency_ms += int(latency_ms)

    def touched(self) -> bool:
        """Did this operation reach a provider at all? Only then is a row written (bounds writes by costly work, never by raw request volume)."""
        with self._lock:
            return bool(self.attempts or self.llm_calls or self.calls_ok or self.calls_failed)

    # -- derived, honest summary --
    def summary(self, *, status: str, category: str | None) -> dict:
        with self._lock:
            total_calls = self.calls_ok
            known, unknown = self.known_usage_calls, self.unknown_usage_calls
            if total_calls == 0 or known == 0:
                token_cov = "unknown"
            elif unknown == 0:
                token_cov = "known"
            else:
                token_cov = "partial"
            tin = self.input_tokens if known else None
            tout = self.output_tokens if known else None
            cost_known = self.cost_known_calls > 0 and self.cost_known_calls == total_calls
            attempts = self.attempts if self.exact_attempts else (self.llm_calls if self.llm_calls else None)
            coverage = "exact" if self.exact_attempts else ("calls_only" if self.llm_calls else "none")
            model = self.models[0] if self.models else None
            return {
                "status": status, "failure_category": (category or self.failure_category) if status == "failed" else None,
                "provider_attempts": attempts, "attempt_coverage": coverage, "calls_ok": self.calls_ok, "calls_failed": self.calls_failed,
                "input_tokens": tin, "output_tokens": tout, "total_tokens": (tin + tout) if known else None, "token_coverage": token_cov,
                "cost_usd_micros": self.cost_micros if cost_known else None, "cost_source": "reported" if cost_known else "unavailable",
                "latency_ms": self.latency_ms if (self.calls_ok or self.calls_failed) else None, "model_id": model,
            }


_current: ContextVar[AiOperationScope | None] = ContextVar("ai_operation_scope", default=None)


def current_scope() -> AiOperationScope | None:
    return _current.get()


# Provider-client hooks. They are best-effort and can never raise into the provider path.
def note_attempt() -> None:
    try:
        s = _current.get()
        if s is not None:
            s.attempt()
    except Exception:  # noqa: BLE001
        pass


def note_call_started() -> None:
    try:
        s = _current.get()
        if s is not None:
            s.call_started()
    except Exception:  # noqa: BLE001
        pass


def note_call_ok(*, model: str | None, input_tokens: int | None, output_tokens: int | None, cost_usd: float | None, latency_ms: int | None) -> None:
    try:
        s = _current.get()
        if s is not None:
            s.call_ok(model=model, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd, latency_ms=latency_ms)
    except Exception:  # noqa: BLE001
        pass


def note_call_failed(category: str | None, latency_ms: int | None) -> None:
    try:
        s = _current.get()
        if s is not None:
            s.call_failed(category, latency_ms)
    except Exception:  # noqa: BLE001
        pass


# ----------------------------------------------------------------------------------------------------------------- persistence
def _bounded_category(exc: BaseException | None) -> str | None:
    if exc is None:
        return None
    if isinstance(exc, HTTPException):
        return f"http_{exc.status_code}"
    name = type(exc).__name__
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in name)[:_FAILURE_BOUND]


def persist_scope(session_factory, scope: AiOperationScope, *, status: str, category: str | None) -> bool:
    """Write the logical-operation row. Idempotent on ``op_key`` (a duplicate adds nothing). Never raises: metering must not break a request."""
    from sqlalchemy.exc import IntegrityError

    from src.llm.models import known_profile_for_slug
    from src.persistence import AIOperationEvent, utcnow

    try:
        data = scope.summary(status=status, category=category)
        prof = known_profile_for_slug(data["model_id"]) if data["model_id"] else None
        row = AIOperationEvent(op_key=scope.op_key, user_id=int(scope.user_id), workflow=scope.workflow, operation=scope.operation[:32], provider="openrouter",
                               model_profile=prof.value if prof else None, limit_observed=bool(scope.limit_observed),
                               started_at=scope.started_at or utcnow(), completed_at=utcnow(), **data)
        with session_factory() as s:
            s.add(row)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                return False
        return True
    except Exception:  # noqa: BLE001
        log.warning("ai operation event could not be recorded")
        return False


# ------------------------------------------------------------------------------------------------------------------- admission
def admit(workflow: str, user_id: int, *, pause_service: Any | None) -> bool:
    """Pause, then the per-user and global request ceilings. Returns ``limit_observed`` (True when a ceiling was exceeded in observe mode).

    Raises ``PlatformPausedError`` / ``PauseStateUnavailable`` (503, before any provider work) when paused or when the pause state cannot be read, and
    ``AiUsageLimitError`` (429) only when ``AI_COST_LIMITS_ENFORCED`` is true. The key is the AUTHENTICATED user id, never client input."""
    from src.api.guards import ensure_not_paused
    from src.api import rate_limit

    capability, bucket = WORKFLOWS[workflow]
    if pause_service is not None:
        ensure_not_paused(capability, pause_service)
    key = rate_limit.user_key(user_id)
    per_user = rate_limit.check(bucket, key)
    overall = rate_limit.check("cost_global", "all")
    exceeded = not (per_user.allowed and overall.allowed)
    if exceeded and AI_COST_LIMITS_ENFORCED:
        raise AiUsageLimitError(workflow, max(per_user.retry_after, overall.retry_after))
    return exceeded


def ai_operation(workflow: str, operation: str):
    """FastAPI dependency factory for a provider-backed route. Async on purpose: it sets the context variable in the request task so the sync endpoint
    (run in a worker thread with a copied context) reports into the same scope object. On exit it records one logical-operation row."""
    if workflow not in WORKFLOWS:
        raise ValueError(f"unknown AI workflow: {workflow!r}")

    from src.api.dependencies import get_current_user_id, get_pause_service, get_repository

    async def _dep(request: Request, user_id: int = Depends(get_current_user_id), pause=Depends(get_pause_service),
                   repo=Depends(get_repository)) -> AsyncIterator[AiOperationScope]:
        idem = request.headers.get("idempotency-key")
        path_id = str(request.path_params.get("session_id", ""))[:40]
        unique = f"{idem[:48]}" if idem else uuid.uuid4().hex
        scope = AiOperationScope(user_id=int(user_id), workflow=workflow, operation=operation, op_key=f"{workflow}:{operation}:{user_id}:{path_id}:{unique}"[:120])
        from src.persistence import utcnow

        scope.started_at = utcnow()
        scope.limit_observed = await run_in_threadpool(admit, workflow, int(user_id), pause_service=pause)
        token = _current.set(scope)
        status, category = "succeeded", None
        try:
            yield scope
        except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
            status, category = "failed", _bounded_category(exc)
            raise
        finally:
            _current.reset(token)
            if scope.touched():
                await run_in_threadpool(persist_scope, repo.session_factory, scope, status=status, category=category)

    _dep.ai_workflow = workflow  # type: ignore[attr-defined]
    return _dep


# ---------------------------------------------------------------------------------------------------------- LangChain (Career) hook
def langchain_callback():
    """A LangChain callback handler that reports each model invocation of the CURRENT scope (Career runs through LangChain, not ``OpenRouterClient``).
    Returns None when ``langchain_core`` is unavailable. SDK-internal retries are invisible here, so Career attempts are ``calls_only`` coverage."""
    try:
        from langchain_core.callbacks import BaseCallbackHandler
    except Exception:  # noqa: BLE001
        return None

    class _ScopeCallback(BaseCallbackHandler):
        raise_error = False

        def __init__(self) -> None:
            self._started: dict[Any, float] = {}

        def _begin(self, run_id: Any) -> None:
            self._started[run_id] = time.perf_counter()
            note_call_started()

        def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):  # noqa: D401, ANN001
            self._begin(run_id)

        def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):  # noqa: ANN001
            self._begin(run_id)

        def on_llm_end(self, response, *, run_id, **kwargs):  # noqa: ANN001
            try:
                began = self._started.pop(run_id, None)
                latency = int((time.perf_counter() - began) * 1000) if began is not None else None
                out = getattr(response, "llm_output", None) or {}
                usage = out.get("token_usage") if isinstance(out, dict) else None
                tin = tout = None
                if isinstance(usage, dict):
                    tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if tin is None:
                    gens = getattr(response, "generations", None) or []
                    msg = getattr(gens[0][0], "message", None) if gens and gens[0] else None
                    meta = getattr(msg, "usage_metadata", None)
                    if isinstance(meta, dict):
                        tin, tout = meta.get("input_tokens"), meta.get("output_tokens")
                model = out.get("model_name") if isinstance(out, dict) else None
                note_call_ok(model=model, input_tokens=tin, output_tokens=tout, cost_usd=None, latency_ms=latency)
            except Exception:  # noqa: BLE001
                pass

        def on_llm_error(self, error, *, run_id, **kwargs):  # noqa: ANN001
            began = self._started.pop(run_id, None)
            note_call_failed(type(error).__name__, int((time.perf_counter() - began) * 1000) if began is not None else None)

    return _ScopeCallback()
