"""Canonical AI model-PROFILE authorization policy (W12.4D-P2-C).

Owner-approved target: BASIC may use ``fast`` only; PREMIUM may use ``fast``, ``balanced`` and ``advanced``. The official names are Fast, Balanced and Advanced
(internal ``fast``, ``balanced``, ``advanced``); there is NO "medium" profile (a reasoning-effort hint is unrelated metadata).

* **Default disabled.** ``MODEL_PROFILE_ENFORCED = False`` is a code constant (like the billing gates, ``AI_COST_LIMITS_ENFORCED`` and
  ``HISTORY_RESTRICTIONS_ENFORCED``). While False NOTHING changes for any real candidate: Practice keeps its existing Balanced default (no Basic account is moved
  to Fast), Mo keeps accepting the profile it accepts today, and no new paid restriction exists. The runtime behaviour change to "Basic = Fast" is NOT approved until
  P2-C quality and cost qualification succeeds and a separate release flips this constant.
* **One authority.** Premium is read from the existing ``EntitlementService`` through ``plan_state.resolve_plan_state`` (an ACTIVE Premium-plan subscription).
  ``premium_preview``, client plan labels, unknown or unreadable state are never Premium. No subscription system, writer or Stripe code lives here.
* **Profiles only, never slugs.** The only accepted values are the three profile ids; a provider model id, an alias, a different case or any other string is rejected
  before anything else happens. Authorization runs BEFORE any provider invocation.
* **No selector is exposed while inactive.** For Practice (which has no candidate selector today) a profile other than the existing default is refused while the gate is
  disabled, so the new request field is not a working free selector for everyone. Mo's existing ``profile`` field keeps its current behaviour while disabled.
* **Fallback never escalates.** ``authorized_fallbacks`` and ``assert_effective_authorized`` keep any future fallback inside the caller's authorized profiles; with none
  available the caller gets a controlled failure, never a silent switch to a more expensive profile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from src.llm.models import ModelProfile

# A code constant: nothing but a reviewed release can enable it. Tests flip it on an isolated module attribute.
MODEL_PROFILE_ENFORCED = False
PRACTICE_DEFAULT_PROFILE = ModelProfile.BALANCED          # the EXISTING Practice default, preserved while disabled
_ALL = frozenset(ModelProfile)
_BASIC_ALLOWED = frozenset({ModelProfile.FAST})
_TEST_ENVS = ("development", "dev", "local", "test", "testing")
_TIER_ORDER = {ModelProfile.FAST: 0, ModelProfile.BALANCED: 1, ModelProfile.ADVANCED: 2}

# Neutral descriptions for a future candidate UI. No comparative quality claim (quality is UNVALIDATED), no price, no upgrade wording.
PROFILE_DESCRIPTIONS = {
    ModelProfile.FAST: "Entry-level model profile.",
    ModelProfile.BALANCED: "Balanced quality and performance profile.",
    ModelProfile.ADVANCED: "Advanced profile, subject to validation.",
}

__all__ = ["MODEL_PROFILE_ENFORCED", "PRACTICE_DEFAULT_PROFILE", "ModelProfileNotAuthorized", "ModelProfileInvalid", "ModelProfileNotAvailable",
           "ModelProfileDecision", "ModelProfileAccessPolicy", "authorized_fallbacks", "assert_effective_authorized", "PROFILE_DESCRIPTIONS"]


class ModelProfileInvalid(ValueError):
    """The supplied value is not one of the three profile ids (a raw provider model id, an alias or a malformed value)."""


class ModelProfileNotAvailable(ValueError):
    """A profile selector is not active for this workflow yet (Practice while the rollout gate is disabled)."""


class ModelProfileNotAuthorized(Exception):
    """The caller's entitlement does not include the requested profile. Carries only the profile id."""

    def __init__(self, profile: ModelProfile | None = None) -> None:
        super().__init__("model_profile_not_authorized")
        self.profile = profile


@dataclass(frozen=True)
class ModelProfileDecision:
    allowed: frozenset
    default: ModelProfile
    enforced: bool
    reason: str            # gate_disabled | premium | basic | unresolved | override_premium | override_basic


def parse_profile(value: object) -> ModelProfile | None:
    """None -> None. A string must EXACTLY equal a profile id; nothing else (no slug, no alias, no other case, no padding) is accepted."""
    if value is None:
        return None
    if isinstance(value, ModelProfile):
        return value
    if isinstance(value, str) and value in {p.value for p in ModelProfile}:
        return ModelProfile(value)
    raise ModelProfileInvalid("Unknown model profile.")


class ModelProfileAccessPolicy:
    """Stateless per request: nothing is cached, so a plan change applies on the next request."""

    def __init__(self, entitlements, *, override: Callable[[int], str] | None = None) -> None:
        if override is not None and (os.environ.get("API_ENV") or "development").strip().lower() not in _TEST_ENVS:
            raise ValueError("A synthetic model-profile decision cannot be used outside development and test.")
        self._entitlements = entitlements
        self._override = override

    def decide(self, user_id: int) -> ModelProfileDecision:
        if not MODEL_PROFILE_ENFORCED:
            return ModelProfileDecision(_ALL, ModelProfile.BALANCED, False, "gate_disabled")
        if self._override is not None:
            premium = self._override(int(user_id)) == "premium"
            return ModelProfileDecision(_ALL if premium else _BASIC_ALLOWED, ModelProfile.BALANCED if premium else ModelProfile.FAST, True,
                                        "override_premium" if premium else "override_basic")
        from src.application.plan_state import PREMIUM, UNRESOLVED, resolve_plan_state

        state = resolve_plan_state(self._entitlements, user_id)
        if state == PREMIUM:
            return ModelProfileDecision(_ALL, ModelProfile.BALANCED, True, "premium")           # Premium keeps the existing Balanced default
        return ModelProfileDecision(_BASIC_ALLOWED, ModelProfile.FAST, True, "unresolved" if state == UNRESOLVED else "basic")

    def authorize(self, user_id: int, requested: object, *, workflow: str) -> ModelProfile | None:
        """Validate and authorize the profile for ``workflow`` (``practice`` or ``agent``) BEFORE any provider work.

        Returns the profile to use, or ``None`` meaning "leave the existing behaviour untouched" (only while the gate is disabled and nothing was requested).
        Raises ``ModelProfileInvalid`` (malformed or a raw model id), ``ModelProfileNotAvailable`` (Practice selector inactive) or ``ModelProfileNotAuthorized``."""
        profile = parse_profile(requested)
        decision = self.decide(user_id)
        if not decision.enforced:
            if workflow == "practice" and profile not in (None, PRACTICE_DEFAULT_PROFILE):
                raise ModelProfileNotAvailable("Model profile selection is not available yet.")   # no working selector while Premium is inactive
            return profile                                                                         # agent: exactly the existing behaviour
        chosen = profile if profile is not None else decision.default
        if chosen not in decision.allowed:
            raise ModelProfileNotAuthorized(chosen)
        return chosen

    def assert_authorized(self, user_id: int, profile: object) -> None:
        """Re-check an already chosen profile (for example one stored on an older agent run) when the gate is on."""
        decision = self.decide(user_id)
        if decision.enforced:
            chosen = parse_profile(profile) or decision.default
            if chosen not in decision.allowed:
                raise ModelProfileNotAuthorized(chosen)

    def catalogue(self, user_id: int) -> dict:
        """Plan-aware metadata for a FUTURE candidate UI. ``selector_active`` is False while the gate is disabled; nothing here grants or changes anything."""
        d = self.decide(user_id)
        return {"selector_active": d.enforced, "default": d.default.value,
                "profiles": [{"id": p.value, "authorized": p in d.allowed, "description": PROFILE_DESCRIPTIONS[p]} for p in ModelProfile]}


def authorized_fallbacks(effective: ModelProfile, floor: ModelProfile, allowed: frozenset) -> list[ModelProfile]:
    """The bounded LOWER tiers from just below ``effective`` down to ``floor`` that the caller is also authorized to use (never higher, never unauthorized)."""
    return [p for p in sorted(ModelProfile, key=lambda x: -_TIER_ORDER[x])
            if _TIER_ORDER[floor] <= _TIER_ORDER[p] < _TIER_ORDER[effective] and p in allowed]


def assert_effective_authorized(effective: ModelProfile, allowed: frozenset) -> None:
    """A floor-raised or fallback profile must still be authorized; otherwise a controlled failure (never a silent switch)."""
    if effective not in allowed:
        raise ModelProfileNotAuthorized(effective)
