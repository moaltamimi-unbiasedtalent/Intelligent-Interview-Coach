"""Central per-operation model policy (Capstone P5/E4).

This is the ONE place that answers, for every LLM-backed operation in the product,
"which model, at what capability, with which structured-output / timeout / retry /
fallback discipline?" — instead of that choice being scattered across call sites.

Design rules (mirroring ``src/llm/models.py``):
- **No provider call and no secret** at import or resolution — this is a pure
  resolver over the typed model registry. It constructs no client.
- It does NOT replace the registry: an operation's *capability* is expressed as a
  ``ModelProfile`` floor and resolved through the existing ``ModelProfile`` tiers and
  env-overridable slugs. The registry stays the single source of truth for slugs.
- **Two independent dimensions.** The USER PROFILE (Fast/Balanced/Advanced) is the
  candidate's chosen cost/latency *envelope*; the OPERATION POLICY declares the
  *minimum capability* an operation needs to run safely. The effective tier is the
  higher of the two (an operation never runs below the capability it needs), capped
  at Advanced. These are orthogonal to Brief/Detailed and to interface/conversation
  language — none of those ever change the model, and vice-versa.
- **A raw client model slug is never an input here.** Callers pass an operation and a
  validated ``ModelProfile`` (the browser can only ever send fast|balanced|advanced —
  see ``AgentApplicationService._resolve_profile``); an unknown operation raises.
- **Deterministic operations are first-class.** An operation may declare
  ``capability=NONE`` to state, in policy, that it uses NO model (e.g. the Candidate
  Evidence specialist is deterministic). Callers must honour that and never build a
  client for it.
- Bounded fallback + graceful degradation: each policy carries an ordered, bounded
  fallback chain of *lower* tiers (never below its declared fallback floor) so a
  provider failure degrades safely rather than hard-failing, without ever silently
  upgrading past the user's need or exposing provider internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.llm.models import ModelProfile, ModelSpec, model_id, spec

__all__ = [
    "ModelOperation",
    "ModelCapability",
    "OperationPolicy",
    "ResolvedModelPolicy",
    "OPERATION_POLICY",
    "resolve_policy",
    "operation_uses_model",
    "all_policies",
]


# Ordered capability tiers, low → high, for the max/clamp arithmetic below.
_TIER_ORDER: dict[ModelProfile, int] = {
    ModelProfile.FAST: 0,
    ModelProfile.BALANCED: 1,
    ModelProfile.ADVANCED: 2,
}
_TIER_BY_RANK: dict[int, ModelProfile] = {v: k for k, v in _TIER_ORDER.items()}


class ModelCapability(str, Enum):
    """The capability an operation demands from its model.

    - ``TOOL_CALLING``: the model must support bound-tool calling (Mo's ReAct loop).
    - ``STRUCTURED``: the model must support JSON-schema-constrained output.
    - ``TEXT``: plain grounded generation is enough.
    - ``REALTIME``: a bidirectional low-latency audio/session model (Capstone P7.5).
      This is NOT an OpenRouter chat slug — the effective provider/model is resolved by
      the dedicated realtime registry (``src/voice/realtime.py``), server-authoritatively.
      Declared here so realtime is a first-class operation in the single policy view and a
      raw client slug is still rejected, without pretending a realtime model is a chat tier.
    - ``NONE``: the operation is DETERMINISTIC — it uses no model at all. A policy
      with this capability resolves to no slug; callers must not build a client.
    """

    TOOL_CALLING = "tool_calling"
    STRUCTURED = "structured"
    TEXT = "text"
    REALTIME = "realtime"
    NONE = "none"


class ModelOperation(str, Enum):
    """Every distinct LLM-backed (or explicitly deterministic) operation the product
    routes through this policy. New agentic operations are added HERE, not inline at a
    call site."""

    ORCHESTRATION = "orchestration"                          # Mo's ReAct loop (tool-using)
    SPECIALIST_ROLE_ANALYSIS = "specialist_role_analysis"    # Role & Opportunity specialist
    SPECIALIST_EVIDENCE_ANALYSIS = "specialist_evidence_analysis"  # Candidate Evidence specialist
    SPECIALIST_COACHING = "specialist_coaching"              # Interview Strategy / Coach specialist
    FINAL_RESPONSE = "final_response"                        # High-stakes candidate-facing synthesis
    STRUCTURED_GENERATION = "structured_generation"          # Generic schema-constrained generation
    EVALUATION = "evaluation"                                # Answer/report evaluation (Practice)
    REALTIME_VOICE = "realtime_voice"                        # P7.5 realtime voice session (audio)


@dataclass(frozen=True)
class OperationPolicy:
    """The immutable policy for one operation.

    ``min_capability`` is the profile FLOOR (correctness), independent of the user's
    envelope. ``fallback_floor`` bounds how far graceful degradation may drop on a
    provider failure (never below it). No secret and no slug live here — the slug is
    resolved from the registry at :func:`resolve_policy` time.
    """

    operation: "ModelOperation"
    capability: ModelCapability
    min_capability: ModelProfile
    fallback_floor: ModelProfile
    structured_output: bool
    requires_tools: bool
    temperature: float | None      # None ⇒ omit (the gpt-5.x reasoning family)
    max_output_tokens: int
    timeout_s: float
    max_retries: int
    rationale: str


@dataclass(frozen=True)
class ResolvedModelPolicy:
    """The effective, resolved policy for (operation, user profile).

    Safe to log/observe: contains no secret and no prompt. ``model_id`` is a public,
    env-overridable OpenRouter slug (never a key). For a deterministic operation
    (``uses_model`` False) ``profile``/``model_id`` are None.
    """

    operation: "ModelOperation"
    capability: ModelCapability
    uses_model: bool
    profile: ModelProfile | None
    model_id: str | None
    spec: ModelSpec | None
    structured_output: bool
    requires_tools: bool
    temperature: float | None
    max_output_tokens: int
    timeout_s: float
    max_retries: int
    fallback_profiles: list[ModelProfile] = field(default_factory=list)
    fallback_model_ids: list[str] = field(default_factory=list)
    capability_capped: bool = False  # True when the operation floor raised the user tier

    def to_dict(self) -> dict:
        """A safe, JSON-ready projection for observability / the reviewer diagnostic.

        Contains only the model SLUG and bounded numeric policy — never a secret,
        prompt, candidate content or chain-of-thought.
        """
        return {
            "operation": self.operation.value,
            "capability": self.capability.value,
            "uses_model": self.uses_model,
            "profile": self.profile.value if self.profile else None,
            "model_id": self.model_id,
            "structured_output": self.structured_output,
            "requires_tools": self.requires_tools,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "timeout_s": self.timeout_s,
            "max_retries": self.max_retries,
            "fallback_profiles": [p.value for p in self.fallback_profiles],
            "fallback_model_ids": list(self.fallback_model_ids),
            "capability_capped": self.capability_capped,
        }


# The central policy table. Every operation declares its capability, floors and
# bounded execution discipline. Kept small and explicit on purpose (§ E4).
OPERATION_POLICY: dict[ModelOperation, OperationPolicy] = {
    ModelOperation.ORCHESTRATION: OperationPolicy(
        operation=ModelOperation.ORCHESTRATION,
        capability=ModelCapability.TOOL_CALLING,
        min_capability=ModelProfile.BALANCED,   # Mo needs reliable tool calling
        fallback_floor=ModelProfile.BALANCED,   # never orchestrate on Fast
        structured_output=False,
        requires_tools=True,
        temperature=None,
        max_output_tokens=1536,
        timeout_s=60.0,
        max_retries=2,
        rationale="Mo's bounded ReAct loop; tool calling is mandatory, so Fast is "
        "never sufficient. Degradation stays at Balanced.",
    ),
    ModelOperation.SPECIALIST_ROLE_ANALYSIS: OperationPolicy(
        operation=ModelOperation.SPECIALIST_ROLE_ANALYSIS,
        capability=ModelCapability.STRUCTURED,
        min_capability=ModelProfile.BALANCED,
        fallback_floor=ModelProfile.FAST,       # a role brief may degrade to Fast
        structured_output=True,
        requires_tools=False,
        temperature=None,
        max_output_tokens=1024,
        timeout_s=45.0,
        max_retries=1,
        rationale="Structured role/opportunity synthesis. Reuses the governed "
        "JD-analysis operation; may degrade to Fast for the synthesis step.",
    ),
    ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS: OperationPolicy(
        operation=ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS,
        capability=ModelCapability.NONE,        # DETERMINISTIC — no model, by policy
        min_capability=ModelProfile.FAST,
        fallback_floor=ModelProfile.FAST,
        structured_output=False,
        requires_tools=False,
        temperature=None,
        max_output_tokens=0,
        timeout_s=5.0,
        max_retries=0,
        rationale="Owner-scoped selection/ranking of APPROVED evidence is deterministic "
        "(no model): injection-inert and privacy-safe. Declared NONE so no client is built.",
    ),
    ModelOperation.SPECIALIST_COACHING: OperationPolicy(
        operation=ModelOperation.SPECIALIST_COACHING,
        capability=ModelCapability.STRUCTURED,
        min_capability=ModelProfile.BALANCED,
        fallback_floor=ModelProfile.FAST,
        structured_output=True,
        requires_tools=False,
        temperature=None,
        max_output_tokens=1024,
        timeout_s=45.0,
        max_retries=1,
        rationale="Coaching synthesis over role requirements + bounded evidence. Never "
        "invents metrics; emits CLARIFICATION_NEEDED instead. Live model UNVALIDATED — "
        "a deterministic fallback owns this path today.",
    ),
    ModelOperation.FINAL_RESPONSE: OperationPolicy(
        operation=ModelOperation.FINAL_RESPONSE,
        capability=ModelCapability.TEXT,
        min_capability=ModelProfile.BALANCED,
        fallback_floor=ModelProfile.BALANCED,
        structured_output=False,
        requires_tools=False,
        temperature=None,
        max_output_tokens=1536,
        timeout_s=60.0,
        max_retries=2,
        rationale="High-stakes candidate-facing synthesis; never degrades to Fast.",
    ),
    ModelOperation.STRUCTURED_GENERATION: OperationPolicy(
        operation=ModelOperation.STRUCTURED_GENERATION,
        capability=ModelCapability.STRUCTURED,
        min_capability=ModelProfile.BALANCED,
        fallback_floor=ModelProfile.FAST,
        structured_output=True,
        requires_tools=False,
        temperature=None,
        max_output_tokens=1024,
        timeout_s=45.0,
        max_retries=1,
        rationale="Generic JSON-schema-constrained generation (e.g. JD analysis, "
        "question generation) — the existing structured Career operations.",
    ),
    ModelOperation.EVALUATION: OperationPolicy(
        operation=ModelOperation.EVALUATION,
        capability=ModelCapability.STRUCTURED,
        min_capability=ModelProfile.ADVANCED,   # RECOMMENDED tier for evaluation/report
        fallback_floor=ModelProfile.BALANCED,
        structured_output=True,
        requires_tools=False,
        temperature=None,
        max_output_tokens=2048,
        timeout_s=90.0,
        max_retries=2,
        rationale="Answer/report evaluation quality tier. Documented here for a single "
        "policy view; Interview Practice keeps its session-selected effective model "
        "(no interview redesign in P5 — see src/llm/models.py INTERVIEW_SESSION).",
    ),
    ModelOperation.REALTIME_VOICE: OperationPolicy(
        operation=ModelOperation.REALTIME_VOICE,
        capability=ModelCapability.REALTIME,      # audio session — NOT an OpenRouter tier
        min_capability=ModelProfile.BALANCED,     # advisory only (realtime slug is separate)
        fallback_floor=ModelProfile.BALANCED,
        structured_output=False,
        requires_tools=False,
        temperature=None,
        max_output_tokens=0,                      # audio session, not token-capped here
        timeout_s=60.0,
        max_retries=0,                            # no auto-retry of a live audio session
        rationale="Capstone P7.5 realtime voice. The effective provider/model is chosen "
        "server-side by the dedicated realtime registry (src/voice/realtime.py), never by a "
        "client slug. Declared here so realtime is a first-class, observable operation and "
        "the model-policy boundary rejects client overrides; falls back to P7 turn-based "
        "voice when unavailable. Live model UNVALIDATED (no realtime provider authorised).",
    ),
}


def _clamp_up(user: ModelProfile, floor: ModelProfile) -> tuple[ModelProfile, bool]:
    """Return (max(user, floor), capped) in tier order, capped ⇔ floor raised the user."""
    if _TIER_ORDER[floor] > _TIER_ORDER[user]:
        return floor, True
    return user, False


def _fallback_chain(effective: ModelProfile, floor: ModelProfile) -> list[ModelProfile]:
    """Ordered lower tiers from just below ``effective`` down to ``floor`` (inclusive).

    Bounded and never below the operation's fallback floor, so graceful degradation on
    a provider failure stays safe (e.g. orchestration never degrades below Balanced).
    """
    top = _TIER_ORDER[effective] - 1
    bottom = _TIER_ORDER[floor]
    return [_TIER_BY_RANK[r] for r in range(top, bottom - 1, -1) if r >= 0]


def resolve_policy(
    operation: "ModelOperation | str", user_profile: ModelProfile | None
) -> ResolvedModelPolicy:
    """Resolve the effective model policy for an operation and a validated user profile.

    ``operation`` must be a known :class:`ModelOperation` (an unknown value raises —
    a caller can never smuggle an arbitrary operation). ``user_profile`` is the
    candidate's validated Fast/Balanced/Advanced envelope; None defaults to Balanced.
    A raw provider slug is NEVER accepted as ``user_profile``.
    """
    op = operation if isinstance(operation, ModelOperation) else ModelOperation(str(operation))
    policy = OPERATION_POLICY[op]
    profile = user_profile if isinstance(user_profile, ModelProfile) else ModelProfile.BALANCED

    if policy.capability is ModelCapability.NONE:
        # Deterministic by policy — resolve to NO model. Callers must not build a client.
        return ResolvedModelPolicy(
            operation=op, capability=policy.capability, uses_model=False,
            profile=None, model_id=None, spec=None,
            structured_output=False, requires_tools=False, temperature=None,
            max_output_tokens=0, timeout_s=policy.timeout_s, max_retries=0,
            fallback_profiles=[], fallback_model_ids=[], capability_capped=False,
        )

    if policy.capability is ModelCapability.REALTIME:
        # Realtime is a separate provider surface (audio session), not an OpenRouter chat
        # tier — so it resolves to NO chat slug here. The effective realtime provider/model
        # is chosen server-side by src/voice/realtime.py. uses_model=True marks it as a
        # provider-backed operation (for the reviewer diagnostic) while keeping model_id None
        # so no chat slug is ever attributed to it.
        return ResolvedModelPolicy(
            operation=op, capability=policy.capability, uses_model=True,
            profile=None, model_id=None, spec=None,
            structured_output=False, requires_tools=policy.requires_tools, temperature=None,
            max_output_tokens=policy.max_output_tokens, timeout_s=policy.timeout_s,
            max_retries=policy.max_retries,
            fallback_profiles=[], fallback_model_ids=[], capability_capped=False,
        )

    effective, capped = _clamp_up(profile, policy.min_capability)
    fallbacks = _fallback_chain(effective, policy.fallback_floor)
    return ResolvedModelPolicy(
        operation=op,
        capability=policy.capability,
        uses_model=True,
        profile=effective,
        model_id=model_id(effective),
        spec=spec(effective),
        structured_output=policy.structured_output,
        requires_tools=policy.requires_tools,
        temperature=policy.temperature,
        max_output_tokens=policy.max_output_tokens,
        timeout_s=policy.timeout_s,
        max_retries=policy.max_retries,
        fallback_profiles=fallbacks,
        fallback_model_ids=[model_id(p) for p in fallbacks],
        capability_capped=capped,
    )


def operation_uses_model(operation: "ModelOperation | str") -> bool:
    """Whether an operation is model-backed (False for a deterministic policy)."""
    op = operation if isinstance(operation, ModelOperation) else ModelOperation(str(operation))
    return OPERATION_POLICY[op].capability is not ModelCapability.NONE


def all_policies(user_profile: ModelProfile | None = None) -> list[ResolvedModelPolicy]:
    """Resolve every operation for a profile — for the reviewer diagnostic / docs."""
    return [resolve_policy(op, user_profile) for op in ModelOperation]
