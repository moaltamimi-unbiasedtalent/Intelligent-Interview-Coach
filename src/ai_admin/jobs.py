"""W10.9 job type for AI configuration evaluation (P10B-W10.7). The payload is one id; the job makes no provider call."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.jobs.registry import JobTypeDef, PermanentJobError


class EvaluationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


def _evaluate(p: EvaluationPayload, ctx) -> None:
    from src.ai_admin.service import AINotFound, AIConfigService

    rt = getattr(ctx.services, "ai_admin", None) if ctx.services is not None else None
    if rt is None:
        raise PermanentJobError("configuration_error")
    try:
        AIConfigService(rt.session_factory).run_evaluation(p.evaluation_id)
    except AINotFound:
        raise PermanentJobError("invalid_payload")


def job_types() -> list[JobTypeDef]:
    from src.application import admin_permissions as perm

    return [JobTypeDef(
        code="ai_evaluate_config", label="AI configuration: deterministic evaluation", payload_model=EvaluationPayload, handler=_evaluate,
        summarize=lambda p: {"evaluation": p.evaluation_id}, max_attempts=3, lease_seconds=120, backoff_base_seconds=30, backoff_cap_seconds=300,
        idempotency="A terminal evaluation is a no-op; the result is bound to one config hash and replay re-derives the same verdict.",
        manual_retry=True, admin_enqueue=False, requires_permission=perm.AI_MANAGE, dependencies=("ai_admin",))]
