"""Typed OpenRouter model registry — the single source of truth for model choice.

Sprint 4 Phase 9.5 replaces model identifiers scattered across the app with three
workload **profiles** (Fast / Balanced / Advanced) and one registry that resolves
each profile to an OpenRouter slug (environment-overridable), plus safe capability
metadata (tool calling, structured output, temperature, a documented reasoning hint).

Design rules:
- **No provider call and no secret** at import or resolution (offline-safe for tests).
- The strongest model is not automatically the right model for every workload — the
  ``WORKLOAD_PROFILE`` policy makes the cost/quality/latency trade-off explicit.
- Capability flags are conservative per-profile declarations for validation and
  documentation; runtime provider parameter support (e.g. temperature) is still
  honoured by the existing pricing metadata where the interview path uses it.
- Reasoning hints are documentation only; provider reasoning output is NEVER stored,
  logged or exposed (see the agent result/events/inspector).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ModelProfile",
    "ModelSpec",
    "ModelSelectionMode",
    "Workload",
    "WORKLOAD_PROFILE",
    "INTERVIEW_SESSION_DEFAULT_PROFILE",
    "INTERVIEW_RECOMMENDED_PROFILE",
    "model_id",
    "spec",
    "all_specs",
    "selection_mode",
    "workload_profile",
    "workload_model",
    "recommended_profile",
    "effective_interview_profile",
    "profile_for_model",
    "legacy_synonyms",
    "supports_temperature",
    "supports_tools",
]


class ModelProfile(str, Enum):
    """The three workload tiers exposed to the app (and, as Fast/Balanced/Advanced,
    to candidates). Internal vocabulary — not raw provider slugs."""

    FAST = "fast"
    BALANCED = "balanced"
    ADVANCED = "advanced"


# Current defaults at implementation time (Sept 2026). These are OpenRouter slugs and
# are expected to evolve — override per deployment with the env vars below rather than
# editing business logic. Not promised to be available forever.
_DEFAULT_SLUG: dict[ModelProfile, str] = {
    ModelProfile.FAST: "openai/gpt-5.6-luna",
    ModelProfile.BALANCED: "openai/gpt-5.6-terra",
    ModelProfile.ADVANCED: "openai/gpt-5.6-sol",
}

_ENV_VAR: dict[ModelProfile, str] = {
    ModelProfile.FAST: "OPENROUTER_MODEL_FAST",
    ModelProfile.BALANCED: "OPENROUTER_MODEL_BALANCED",
    ModelProfile.ADVANCED: "OPENROUTER_MODEL_ADVANCED",
}

_PURPOSE: dict[ModelProfile, str] = {
    ModelProfile.FAST: "Bounded, lower-risk utility tasks (repair, classification).",
    ModelProfile.BALANCED: "Default: agent orchestration, grounded synthesis, structured Career ops.",
    ModelProfile.ADVANCED: "Higher-stakes synthesis: answer evaluation and the final report.",
}

# Documented reasoning hint per tier (provider-supported values vary; NOT sent by the
# current LangChain/OpenRouter abstraction — kept as metadata only, see §18).
_REASONING: dict[ModelProfile, str] = {
    ModelProfile.FAST: "low",
    ModelProfile.BALANCED: "low",
    ModelProfile.ADVANCED: "medium",
}

# The gpt-5.x reasoning family runs at the provider default temperature (a custom
# temperature is rejected) — consistent with the previous gpt-5 family. Declared here
# so temperature is omitted for these models rather than guessed at each call site.
_SUPPORTS_TEMPERATURE: dict[ModelProfile, bool] = {
    ModelProfile.FAST: False,
    ModelProfile.BALANCED: False,
    ModelProfile.ADVANCED: False,
}

# Previous APP model slugs that may appear in saved settings → the closest profile, so
# old sessions/config never crash when the registry changes (§11/§44). Deliberately
# limited to the prior app family — arbitrary/other-provider models are NOT coerced and
# remain unapproved (RAGAS's own evaluator model is configured separately).
_LEGACY_PROFILE: dict[ModelProfile, tuple[str, ...]] = {
    ModelProfile.FAST: ("openai/gpt-5-nano", "gpt-5-nano"),
    ModelProfile.BALANCED: ("openai/gpt-5-mini", "gpt-5-mini"),
    ModelProfile.ADVANCED: ("openai/gpt-5", "gpt-5"),
}


@dataclass(frozen=True)
class ModelSpec:
    profile: ModelProfile
    openrouter_id: str
    purpose: str
    supports_tools: bool
    supports_structured_output: bool
    supports_temperature: bool
    default_reasoning: str


def model_id(profile: ModelProfile) -> str:
    """Resolve a profile to its OpenRouter slug (env override wins, else the default).

    An empty/whitespace override is ignored (falls back to the default) so a blank
    env var can never yield an invalid model id.
    """
    override = os.environ.get(_ENV_VAR[profile], "").strip()
    return override or _DEFAULT_SLUG[profile]


def spec(profile: ModelProfile) -> ModelSpec:
    return ModelSpec(
        profile=profile,
        openrouter_id=model_id(profile),
        purpose=_PURPOSE[profile],
        supports_tools=True,               # the gpt-5.x family supports tool calling
        supports_structured_output=True,   # …and JSON-schema-constrained output
        supports_temperature=_SUPPORTS_TEMPERATURE[profile],
        default_reasoning=_REASONING[profile],
    )


def all_specs() -> list[ModelSpec]:
    return [spec(p) for p in ModelProfile]


class Workload(str, Enum):
    """Every LLM-backed operation in the app (deterministic ops are absent on purpose)."""

    AGENT = "agent"                      # LangGraph orchestration / Agent Coach
    CAREER_SYNTHESIS = "career_synthesis"  # /career/chat grounded answer
    JD_ANALYSIS = "jd_analysis"          # AnalyzeJobDescription (structured)
    QUESTION_GENERATION = "question_generation"  # GenerateInterviewQuestions (structured)
    INTERVIEW_STRATEGY = "interview_strategy"
    INTERVIEW_QUESTION = "interview_question"
    ANSWER_EVALUATION = "answer_evaluation"
    FINAL_REPORT = "final_report"
    UTILITY = "utility"                  # bounded repair / normalisation / translation
    RAGAS = "ragas"                      # optional offline evaluator (paid, manual)


class ModelSelectionMode(str, Enum):
    """How a workload's EFFECTIVE model is chosen.

    - ``REGISTRY``: application policy picks the profile centrally (this registry).
    - ``INTERVIEW_SESSION``: the effective model is the candidate/session-selected
      ``ModelSettings.model`` (one profile per interview session, reused for all its
      model-backed operations); the registry only records a *recommended* tier.
    """

    REGISTRY = "registry"
    INTERVIEW_SESSION = "interview_session"


# Centrally-selected workloads: the registry profile IS the effective runtime model.
# Gap analysis and the preparation planner are DETERMINISTIC (no model) and absent.
WORKLOAD_PROFILE: dict[Workload, ModelProfile] = {
    Workload.AGENT: ModelProfile.BALANCED,
    Workload.CAREER_SYNTHESIS: ModelProfile.BALANCED,
    Workload.JD_ANALYSIS: ModelProfile.BALANCED,
    Workload.QUESTION_GENERATION: ModelProfile.BALANCED,
    Workload.UTILITY: ModelProfile.FAST,
    Workload.RAGAS: ModelProfile.FAST,
}

# Interview Practice uses ONE session-selected profile for all of these operations
# (default Balanced). The registry does NOT control their effective tier — it only
# records the recommended quality tier. Per-operation routing is intentionally
# deferred (would require an interview-service redesign). Effective model resolution
# is via ``effective_interview_profile(ModelSettings.model)``.
INTERVIEW_SESSION_DEFAULT_PROFILE: ModelProfile = ModelProfile.BALANCED

INTERVIEW_RECOMMENDED_PROFILE: dict[Workload, ModelProfile] = {
    Workload.INTERVIEW_STRATEGY: ModelProfile.BALANCED,
    Workload.INTERVIEW_QUESTION: ModelProfile.BALANCED,
    Workload.ANSWER_EVALUATION: ModelProfile.ADVANCED,  # RECOMMENDED, not effective
    Workload.FINAL_REPORT: ModelProfile.ADVANCED,       # RECOMMENDED, not effective
}


def selection_mode(workload: Workload) -> ModelSelectionMode:
    return (ModelSelectionMode.INTERVIEW_SESSION
            if workload in INTERVIEW_RECOMMENDED_PROFILE
            else ModelSelectionMode.REGISTRY)


def workload_profile(workload: Workload) -> ModelProfile:
    """The EFFECTIVE profile for a centrally-selected (REGISTRY) workload.

    Raises for INTERVIEW_SESSION workloads — their effective model comes from the
    session; use :func:`effective_interview_profile` / :func:`recommended_profile`.
    """
    if workload not in WORKLOAD_PROFILE:
        raise ValueError(
            f"{workload.value} is session-selected, not registry-selected; use "
            "effective_interview_profile(settings.model) or recommended_profile().")
    return WORKLOAD_PROFILE[workload]


def workload_model(workload: Workload) -> str:
    """The effective OpenRouter slug for a centrally-selected workload."""
    return model_id(workload_profile(workload))


def recommended_profile(workload: Workload) -> ModelProfile:
    """The recommended quality tier for any workload (effective for REGISTRY
    workloads; a documented recommendation for INTERVIEW_SESSION ones)."""
    if workload in WORKLOAD_PROFILE:
        return WORKLOAD_PROFILE[workload]
    return INTERVIEW_RECOMMENDED_PROFILE[workload]


def effective_interview_profile(model_slug: str | None) -> ModelProfile:
    """The EFFECTIVE profile for an interview session: resolved from the session's
    ``ModelSettings.model`` (all four interview operations share it)."""
    return profile_for_model(model_slug)


def profile_for_model(model_slug: str | None) -> ModelProfile:
    """Best-effort profile for a slug (current or legacy), defaulting to BALANCED.

    Never raises — a saved/legacy/unknown model id always resolves to a usable
    profile so historical sessions and configs keep working.
    """
    if not model_slug:
        return ModelProfile.BALANCED
    for profile in ModelProfile:
        if model_slug == _DEFAULT_SLUG[profile] or model_slug == model_id(profile):
            return profile
    for profile, legacy in _LEGACY_PROFILE.items():
        if model_slug in legacy:
            return profile
    s = model_slug.lower()
    if "nano" in s:
        return ModelProfile.FAST
    if "mini" in s:
        return ModelProfile.BALANCED
    return ModelProfile.BALANCED


def legacy_synonyms() -> dict[str, str]:
    """Map every known legacy slug → the CURRENT model id of its profile, for tolerant
    coercion of persisted values (e.g. an ApprovedModel enum's synonyms)."""
    out: dict[str, str] = {}
    for profile, legacy in _LEGACY_PROFILE.items():
        current = model_id(profile)
        for slug in legacy:
            out[slug] = current
    return out


def supports_temperature(model_slug: str | None) -> bool:
    """Whether a custom temperature may be sent to this model (else use the provider
    default). Resolved via the model's profile; unknown → conservatively True to
    preserve prior behaviour for non-registry models."""
    if not model_slug:
        return True
    for profile in ModelProfile:
        if model_slug == model_id(profile) or model_slug == _DEFAULT_SLUG[profile]:
            return _SUPPORTS_TEMPERATURE[profile]
    return True


def supports_tools(profile: ModelProfile) -> bool:
    return spec(profile).supports_tools
