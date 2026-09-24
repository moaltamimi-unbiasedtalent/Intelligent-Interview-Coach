"""Authorization foundation (Capstone P1/E1).

A small, composable authorization core that keeps the orthogonal concepts the
platform will need cleanly separated:

* **authenticated principal** — who is making the request (never the request body);
* **ownership** — enforced in the data layer (every repo query is ``user_id``-scoped);
* **platform role** — ``user`` vs ``platform_admin`` (control-plane access);
* **product entitlement** — ``basic`` vs ``premium`` → a capability set;
* **feature flag** — deployment-time on/off (env-driven);
* **workspace role** — membership-scoped (CONTRACT ONLY in P1; Teams phase builds it);
* **explicit share** — deferred to the Teams phase (contract documented below).

P1 builds the mechanism and enforces it server-side; it deliberately does NOT
remove any capability current users already have (see :data:`BASIC_CAPABILITIES`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.persistence import (
    PLATFORM_ROLE_ADMIN,
    TIER_BASIC,
    TIER_PREMIUM,
)

__all__ = [
    "Principal",
    "Capability",
    "capabilities_for",
    "has_capability",
    "is_platform_admin",
    "flag_enabled",
    "WORKSPACE_OWNER",
    "WORKSPACE_MEMBER",
]

# --- workspace-role contract (foundation only; no tables in P1) ---------------
# Workspace role is membership-scoped and NEVER stored on the principal. The Teams
# phase will add workspace + membership tables carrying this role; recording the
# vocabulary here keeps future authorization composition source-compatible.
WORKSPACE_OWNER = "workspace_owner"
WORKSPACE_MEMBER = "workspace_member"


class Capability:
    """String capabilities an entitlement can grant (stable identifiers)."""

    # Currently-free capabilities — kept in BASIC so no current user loses anything.
    CURRENT_MARKET_RESEARCH = "current_market_research"
    STANDARD_HISTORY = "standard_history"
    STANDARD_PROGRESS = "standard_progress"
    STANDARD_MODEL_PROFILES = "standard_model_profiles"
    # Premium-only in P1: a safe, NON-destructive demonstration capability that gates
    # only a new premium endpoint (it removes nothing existing).
    PREMIUM_PREVIEW = "premium_preview"


# Tier → capability set. BASIC intentionally contains every capability that is free
# today; PREMIUM is a strict superset. The richer FUTURE mapping (document limits,
# speech, export, advanced models, …) is documented in
# docs/capstone/p1_e1_identity_platform.md and applied in later phases — NOT here,
# so P1 does not regress current behaviour.
BASIC_CAPABILITIES: frozenset[str] = frozenset(
    {
        Capability.CURRENT_MARKET_RESEARCH,
        Capability.STANDARD_HISTORY,
        Capability.STANDARD_PROGRESS,
        Capability.STANDARD_MODEL_PROFILES,
    }
)
PREMIUM_CAPABILITIES: frozenset[str] = BASIC_CAPABILITIES | {Capability.PREMIUM_PREVIEW}

_TIER_CAPABILITIES: dict[str, frozenset[str]] = {
    TIER_BASIC: BASIC_CAPABILITIES,
    TIER_PREMIUM: PREMIUM_CAPABILITIES,
}


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, resolved server-side (never from the request body)."""

    user_id: int
    platform_role: str
    tier: str
    status: str
    email: str | None = None
    email_verified: bool = False
    # "session" (trusted cookie), "dev_header" (transitional dev fallback) or
    # "anonymous" (dev only). Never used to grant privilege beyond identity.
    auth_method: str = "session"


def capabilities_for(tier: str) -> frozenset[str]:
    """Return the capability set for a product tier (unknown tier → basic)."""
    return _TIER_CAPABILITIES.get(tier, BASIC_CAPABILITIES)


def has_capability(principal: Principal, capability: str) -> bool:
    """True when the principal's tier grants ``capability`` (server-side check)."""
    return capability in capabilities_for(principal.tier)


def is_platform_admin(principal: Principal) -> bool:
    """True only for a persisted platform-admin role — never a superuser bypass.

    A platform admin gains access to the (future) admin control plane; it does NOT
    grant ownership of another user's candidate resources. Object-level ownership is
    still enforced separately in the data layer.
    """
    return principal.platform_role == PLATFORM_ROLE_ADMIN


def flag_enabled(name: str, *, default: bool = False) -> bool:
    """Resolve a deployment feature flag from the environment (``FEATURE_<NAME>``)."""
    raw = os.environ.get(f"FEATURE_{name.upper()}", "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")
