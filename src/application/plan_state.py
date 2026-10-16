"""The single definition of "this candidate currently holds an authorized, ACTIVE Premium subscription" (W12.4D-P2-C, shared with P2-B history access).

Read from the EXISTING ``EntitlementService`` (the caller's active subscription, else the Basic fallback); this module writes nothing and creates no second
entitlement system. Premium means ``source == "subscription"`` AND the Premium plan family. Everything else is not Premium: no subscription, an ended one, the
Basic fallback, ``premium_preview`` (a different, unrelated key that is never consulted), a client-supplied label (never read), an unreadable entitlement
(``unresolved``, fail closed) and any unknown plan code. Stateless: nothing is cached, so a plan change applies on the next call.
"""

from __future__ import annotations

PREMIUM = "premium"
BASIC = "basic"
UNRESOLVED = "unresolved"


def resolve_plan_state(entitlements, user_id: int) -> str:
    """``premium`` | ``basic`` | ``unresolved``. ``unresolved`` is treated as Basic by every caller (never as Premium)."""
    try:
        plan = entitlements.plan_summary(int(user_id))
    except Exception:  # noqa: BLE001 - an unreadable entitlement must never grant anything
        return UNRESOLVED
    if plan.get("source") == "subscription" and plan.get("plan_code") == "premium":
        return PREMIUM
    return BASIC
