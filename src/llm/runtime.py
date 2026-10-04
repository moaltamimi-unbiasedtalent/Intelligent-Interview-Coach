"""Runtime consumers of the governed AI configuration (P10B-W10.7).

Two tiny helpers used at the REAL call sites (Agent factory, Career structured producer and responder, Interview Practice):

* ``governed_slug``: a KNOWN profile slug (code default, env override, legacy app slug) is mapped to the slug the ACTIVE governed configuration
  assigns to that profile; with nothing active, or for any unknown string, the input is returned unchanged.
* ``tunables``: the bounded numeric overrides (max output tokens, timeout, retries) for one operation, or an empty dict.

Tunable operations and the call sites that consume them (kept in sync with ``src/ai_admin/config.py``):
  ORCHESTRATION       -> ``application/agent_service._default_model_factory`` (max tokens, timeout, retries)
  STRUCTURED_GENERATION -> ``copilot/tools/structured.build_structured_producer`` (Career JD analysis, question generation, role specialist) and
                           Interview Practice strategy/question/branch (``interview_service._generate``)
  EVALUATION          -> Interview Practice evaluation and report (``interview_service._generate``)
"""

from __future__ import annotations

from typing import Mapping

from src.llm import governed
from src.llm.models import known_profile_for_slug, model_id
from src.llm.policy import ModelOperation

__all__ = ["governed_slug", "tunables"]


def governed_slug(slug: str | None) -> str | None:
    if not slug or governed.current() is None:
        return slug
    profile = known_profile_for_slug(slug)
    return model_id(profile) if profile is not None else slug


def tunables(operation: ModelOperation) -> Mapping[str, float | int]:
    return governed.operation_override(operation.value) or {}
