"""Plans, entitlements and the effective-entitlement resolver (P10B-W10.4).

Four layers stay separate, and this module owns ONLY the third:
1. AUTHORIZATION   who may perform an operation (ownership, Admin ``require_permission``);
2. CAPABILITY      what the deployment technically supports (flags, providers, ``/capabilities``);
3. ENTITLEMENT     what a subject's plan grants (this module);
4. BILLING         payment state, price, invoices (W10.5, not here).

The registry is code-defined: Admin input can never invent an entitlement key. Today's keys are exactly the
product-access gates that already existed (the former tier-to-capability map), carried over one-for-one so no
user gains or loses anything. The model supports integer LIMIT entitlements, but no limit key exists because no
approved product quota exists; none is invented and no usage is metered.

Value representation (one canonical form, DB and API):
    enabled=False                  -> DISABLED
    enabled=True,  limit=None      -> ENABLED, unlimited
    enabled=True,  limit=N (>= 1)  -> ENABLED with a limit of N        (0 is never used)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.persistence import (
    PLAN_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_ACTIVE,
    PlanEntitlement,
    PlanVersion,
    Subscription,
    utcnow,
)


class EntitlementType(str, Enum):
    BOOLEAN = "boolean"
    LIMIT = "limit"


@dataclass(frozen=True)
class EntitlementDef:
    key: str
    type: EntitlementType
    label: str          # English operator label (Admin UI); candidate wording is localized in the frontend
    description: str


# Keys mirror the pre-W10.4 ``Capability`` identifiers (stable strings; never renamed).
REGISTRY: dict[str, EntitlementDef] = {d.key: d for d in (
    EntitlementDef("current_market_research", EntitlementType.BOOLEAN, "Current-market research",
                   "Company and market research (gates POST /research/company)."),
    EntitlementDef("standard_history", EntitlementType.BOOLEAN, "Standard history",
                   "Practice history access (currently free for everyone)."),
    EntitlementDef("standard_progress", EntitlementType.BOOLEAN, "Standard progress",
                   "Progress access (currently free for everyone)."),
    EntitlementDef("standard_model_profiles", EntitlementType.BOOLEAN, "Standard model profiles",
                   "Fast, Balanced and Advanced model profiles (currently free for everyone)."),
    EntitlementDef("premium_preview", EntitlementType.BOOLEAN, "Premium preview features",
                   "Non-destructive Premium preview endpoint (preview only; not purchasable)."),
)}

# The real, existing plan families. No other plan code can be created. Premium is a PREVIEW (not purchasable).
PLAN_CODES = ("basic", "premium")
DEFAULT_PLAN_CODE = "basic"
BASIC_KEYS = frozenset({"current_market_research", "standard_history", "standard_progress", "standard_model_profiles"})
DEFAULT_PLANS: dict[str, dict] = {
    "basic": {"display_name": "Basic", "enabled": BASIC_KEYS},
    "premium": {"display_name": "Premium (preview)", "enabled": BASIC_KEYS | {"premium_preview"}},
}


class DefaultPlanUnavailable(RuntimeError):
    """The default plan has no active version (an operator retired it): account creation fails closed."""


class EntitlementError(ValueError):
    """An entitlement value or key is invalid (mapped to 422 by the routes)."""


def validate_value(key: str, enabled: object, limit: object, registry: dict[str, EntitlementDef] | None = None) -> tuple[bool, int | None]:
    """Validate one entitlement value against the registry. Returns the canonical (enabled, limit)."""
    reg = registry if registry is not None else REGISTRY
    d = reg.get(key)
    if d is None:
        raise EntitlementError(f"Unknown entitlement key: {key!r}.")
    if not isinstance(enabled, bool):
        raise EntitlementError(f"{key}: 'enabled' must be true or false.")
    if limit is None:
        return enabled, None
    if d.type is EntitlementType.BOOLEAN:
        raise EntitlementError(f"{key} is a boolean entitlement and takes no limit.")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise EntitlementError(f"{key}: the limit must be a whole number.")
    if limit < 1:
        raise EntitlementError(f"{key}: the limit must be at least 1 (use 'disabled' to turn it off).")
    if not enabled:
        raise EntitlementError(f"{key}: a disabled entitlement cannot carry a limit.")
    return enabled, limit


@dataclass(frozen=True)
class Resolved:
    key: str
    enabled: bool
    limit: int | None            # None with enabled=True means unlimited
    plan_code: str
    plan_version: int | None     # None when the code default was used (no database plan)
    source: str                  # "subscription" | "fallback_default"

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "limit": self.limit, "unlimited": self.enabled and self.limit is None}


def default_value(plan_code: str, key: str) -> tuple[bool, int | None]:
    return key in DEFAULT_PLANS[plan_code]["enabled"], None


class EntitlementService:
    """The single product-access authority.

    Resolution (explicit and deterministic):
    * personal/account-scoped (``workspace_id`` omitted): the subject's ACTIVE user subscription;
    * explicitly workspace-scoped (``workspace_id`` given): that workspace's ACTIVE subscription. Workspace
      membership never raises a user's personal access, and plans never combine ("highest wins" is not a rule);
    * no active subscription: the explicit least-privilege fallback, the Basic plan (the active Basic version
      if one exists, else the code default). It never fails open to Premium.
    """

    def __init__(self, session_factory: sessionmaker, registry: dict[str, EntitlementDef] | None = None) -> None:
        self._sf = session_factory
        self._registry = registry if registry is not None else REGISTRY

    def _active_subscription_version(self, s: Session, *, user_id: int | None, workspace_id: int | None) -> PlanVersion | None:
        cond = Subscription.workspace_id == workspace_id if workspace_id is not None else Subscription.user_id == user_id
        return s.scalar(
            select(PlanVersion).join(Subscription, Subscription.plan_version_id == PlanVersion.id)
            .where(cond, Subscription.status == SUBSCRIPTION_STATUS_ACTIVE))

    def _fallback_version(self, s: Session) -> PlanVersion | None:
        return s.scalar(select(PlanVersion).where(PlanVersion.plan_code == DEFAULT_PLAN_CODE,
                                                  PlanVersion.status == PLAN_STATUS_ACTIVE))

    def resolve_all(self, user_id: int, *, workspace_id: int | None = None) -> dict[str, Resolved]:
        with self._sf() as s:
            pv = self._active_subscription_version(s, user_id=user_id, workspace_id=workspace_id)
            source = "subscription"
            if pv is None:
                pv, source = self._fallback_version(s), "fallback_default"
            if pv is None:  # no database plan at all: code default (still Basic, never Premium)
                return {k: Resolved(k, *default_value(DEFAULT_PLAN_CODE, k), DEFAULT_PLAN_CODE, None, "fallback_default")
                        for k in self._registry}
            rows = {e.entitlement_key: e for e in s.scalars(
                select(PlanEntitlement).where(PlanEntitlement.plan_version_id == pv.id)).all()}
            out = {}
            for key in self._registry:
                e = rows.get(key)
                # A key the plan version does not list is DISABLED (deny by default), never silently granted.
                out[key] = Resolved(key, bool(e.enabled) if e else False, e.limit_value if e else None,
                                    pv.plan_code, pv.version, source)
            return out

    def resolve(self, user_id: int, key: str, *, workspace_id: int | None = None) -> Resolved:
        if key not in self._registry:
            raise EntitlementError(f"Unknown entitlement key: {key!r}.")
        return self.resolve_all(user_id, workspace_id=workspace_id)[key]

    def is_enabled(self, user_id: int, key: str, *, workspace_id: int | None = None) -> bool:
        return self.resolve(user_id, key, workspace_id=workspace_id).enabled

    def enabled_keys(self, user_id: int) -> list[str]:
        return sorted(k for k, r in self.resolve_all(user_id).items() if r.enabled)

    def plan_summary(self, user_id: int, *, workspace_id: int | None = None) -> dict:
        res = self.resolve_all(user_id, workspace_id=workspace_id)
        first = next(iter(res.values()))
        return {"plan_code": first.plan_code, "plan_version": first.plan_version, "source": first.source,
                "entitlements": {k: r.to_dict() for k, r in res.items()}}


def seed_default_plans(s: Session, *, source_note: str = "seed") -> dict[str, PlanVersion]:
    """Idempotently ensure an ACTIVE version 1 exists for each real plan code (used by account creation, dev
    SQLite bootstrap and tests that build the schema with create_all; the Alembic migration seeds the same data)."""
    out: dict[str, PlanVersion] = {}
    for code, spec in DEFAULT_PLANS.items():
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == code, PlanVersion.status == PLAN_STATUS_ACTIVE))
        if pv is None:
            exists = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == code))
            if exists is not None:   # versions exist but none active: an operator retired it; never re-create silently
                continue
            pv = PlanVersion(plan_code=code, version=1, display_name=spec["display_name"],
                             status=PLAN_STATUS_ACTIVE, activated_at=utcnow())
            s.add(pv)
            s.flush()
            for key in REGISTRY:
                s.add(PlanEntitlement(plan_version_id=pv.id, entitlement_key=key, enabled=key in spec["enabled"],
                                      limit_value=None))
            s.flush()
        out[code] = pv
    return out


def ensure_default_subscription(s: Session, user_id: int, *, source: str = "system_default") -> None:
    """Give a NEW account its deterministic default (Basic) subscription inside the caller's transaction, so an
    account is never left with ambiguous plan state. Idempotent: an existing active subscription is kept."""
    if s.scalar(select(Subscription.id).where(Subscription.user_id == user_id,
                                              Subscription.status == SUBSCRIPTION_STATUS_ACTIVE)) is not None:
        return
    basic = seed_default_plans(s).get(DEFAULT_PLAN_CODE)
    if basic is None:  # the default plan was retired by an operator: fail closed rather than create a half state
        raise DefaultPlanUnavailable("No active default plan is available.")
    s.add(Subscription(user_id=user_id, plan_version_id=basic.id, status=SUBSCRIPTION_STATUS_ACTIVE, source=source))
    s.flush()
