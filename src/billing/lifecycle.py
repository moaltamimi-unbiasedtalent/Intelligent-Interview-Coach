"""Normalised billing lifecycle (W12.4D-C): FOUR separate state dimensions, never one boolean.

* CHECKOUT state   - the local record of a candidate's checkout ATTEMPT (this wave owns it);
* SUBSCRIPTION state - what the provider says about the subscription (informational; owned by authenticated evidence, W12.4D-D);
* PAYMENT state    - what the provider says about money (informational; W12.4D-D);
* ENTITLEMENT state - what the candidate may DO: decided only by ``EntitlementService`` from the plan, never by any of the above.

Checkout moves are local and listed in ``CHECKOUT_TRANSITIONS``. Every subscription or payment state beyond "none" and "confirmation pending" REQUIRES
verified provider evidence: ``require_evidence`` refuses it otherwise, so a redirect, a client request or an unverified payload can never move them.
Nothing in this module reads or writes a subscription or an entitlement.
"""

from __future__ import annotations

CHECKOUT_STATES = ("none", "preparing", "open", "canceled", "expired", "failed")      # "preparing" = local pending_creation
CHECKOUT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending_creation": ("open", "failed"),
    "open": ("canceled", "expired"),
    "failed": ("pending_creation", "open"),     # a retry with the SAME idempotency key (retryable failures only)
    "canceled": (),
    "expired": (),
}

SUBSCRIPTION_STATES = ("none", "confirmation_pending", "active", "past_due", "cancel_scheduled", "canceled", "expired")
PAYMENT_STATES = ("none", "pending", "succeeded", "failed", "refunded", "disputed")
# States reachable only with authenticated provider evidence (W12.4D-D). "none" and "confirmation_pending" are local, evidence-free facts.
EVIDENCE_REQUIRED_SUBSCRIPTION = frozenset({"active", "past_due", "cancel_scheduled", "canceled", "expired"})
EVIDENCE_REQUIRED_PAYMENT = frozenset({"succeeded", "failed", "refunded", "disputed"})
SUBSCRIPTION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "none": ("confirmation_pending", "active"),
    "confirmation_pending": ("active", "canceled", "expired", "none"),
    "active": ("past_due", "cancel_scheduled", "canceled", "expired"),
    "past_due": ("active", "canceled", "expired"),
    "cancel_scheduled": ("active", "canceled", "expired"),
    "canceled": (),
    "expired": (),
}
CANCELLATION_CAUSES = ("customer", "seller", "provider", "expiry", "data_deletion")      # recorded by D; execution of seller cancels is E


class LifecycleError(ValueError):
    pass


def checkout_transition_allowed(old: str, new: str) -> bool:
    return new in CHECKOUT_TRANSITIONS.get(old, ())


def require_checkout_transition(old: str, new: str) -> None:
    if not checkout_transition_allowed(old, new):
        raise LifecycleError(f"checkout {old} -> {new} is not allowed")


def require_evidence(dimension: str, new_state: str, *, evidence_verified: bool) -> None:
    """Refuse a provider-owned state unless authenticated provider evidence backs it. There is no client or redirect path that can pass True."""
    needs = {"subscription": EVIDENCE_REQUIRED_SUBSCRIPTION, "payment": EVIDENCE_REQUIRED_PAYMENT}.get(dimension)
    if needs is None:
        raise LifecycleError("unknown dimension")
    if new_state in needs and evidence_verified is not True:
        raise LifecycleError(f"{dimension} state {new_state} requires verified provider evidence")


def subscription_transition_allowed(old: str, new: str, *, evidence_verified: bool) -> bool:
    if new not in SUBSCRIPTION_TRANSITIONS.get(old, ()):
        return False
    return new not in EVIDENCE_REQUIRED_SUBSCRIPTION or evidence_verified is True


_SUBSCRIPTION_FROM_PROVIDER = {"active": "active", "trialing": "confirmation_pending", "incomplete": "confirmation_pending", "paused": "confirmation_pending",
                               "past_due": "past_due", "unpaid": "past_due", "canceled": "canceled", "incomplete_expired": "expired"}
_PAYMENT_FROM_INVOICE = {"paid": "succeeded", "failed": "failed", "open": "pending", "action_required": "pending", "none": "none"}


def from_verified_link(*, provider_state: str, cancel_at_period_end: bool, latest_invoice_state: str, refund_state: str, dispute_state: str) -> tuple[str, str]:
    """(subscription, payment) as reconciled from AUTHENTICATED provider evidence (a ``BillingProviderLink``). ``active`` is only shown when the latest
    invoice is paid, and a scheduled cancellation is not a cancellation yet. Refund and dispute facts override the payment word."""
    sub = _SUBSCRIPTION_FROM_PROVIDER.get(provider_state, "confirmation_pending")
    if sub == "active" and latest_invoice_state != "paid":
        sub = "confirmation_pending"
    if sub == "active" and cancel_at_period_end:
        sub = "cancel_scheduled"
    pay = _PAYMENT_FROM_INVOICE.get(latest_invoice_state, "none")
    if refund_state == "full":
        pay = "refunded"
    if dispute_state in ("open", "lost"):
        pay = "disputed"
    return sub, pay


def candidate_view(*, checkout_status: str | None, browser_returned: bool, plan_code: str, verified_subscription: str | None = None) -> dict:
    """What a candidate may be shown. ``verified_subscription`` is only ever supplied from authenticated provider evidence (none exists yet), so
    today every candidate sees ``none`` or ``confirmation_pending``. The entitlement dimension is the plan the entitlement service resolved."""
    checkout = {None: "none", "pending_creation": "preparing"}.get(checkout_status, checkout_status or "none")
    if verified_subscription in SUBSCRIPTION_STATES and verified_subscription != "none":
        subscription = verified_subscription
    elif checkout == "open" and browser_returned:
        subscription = "confirmation_pending"
    else:
        subscription = "none"
    payment = "pending" if subscription == "confirmation_pending" else "none"
    return {"checkout": checkout, "subscription": subscription, "payment": payment,
            "entitlement": {"plan_code": plan_code, "source": "entitlement_service", "changed_by_billing": False},
            "confirmation": "pending" if subscription == "confirmation_pending" else "not_applicable"}
