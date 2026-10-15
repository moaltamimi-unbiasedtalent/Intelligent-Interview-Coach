"""Authoritative provider-state retrieval boundary (W12.4D-D): the SMALLEST set of read operations reconciliation needs.

A webhook says "something changed"; the provider-state reader says what is true NOW. Reconciliation prefers the reader over the event, because events can
arrive out of order, be duplicated or be stale. The reader is read-only, bounded (no retries inside; the job layer retries), and never infers success
from a failure: an unavailable, rate-limited or incomplete provider answer is an error, not a paid state.

``StripeStateReader`` builds its client only through the injected factory (``stripe_provider.build_stripe_client`` by default, sandbox only, per-client key)
and is constructed ONLY when ``policy.STRIPE_WEBHOOK_AUTHORIZED`` is true; no code path in this wave constructs it. Everything is tested with
``FakeStateReader`` below and with fake client objects: no Stripe call, sandbox or otherwise, is ever made.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol


class ProviderStateError(Exception):
    """Base. ``category`` is bounded and safe to store; the provider's message is never kept."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class ProviderStateUnavailable(ProviderStateError):
    """Transient: timeout, outage, rate limit, not enabled. Retryable."""


class ProviderStateNotFound(ProviderStateError):
    """The provider has no such resource (or it belongs to another account/environment). Not retryable."""


class ProviderStateInvalid(ProviderStateError):
    """The answer was incomplete or self-inconsistent. Not trusted, not retryable without operator review."""


@dataclass(frozen=True)
class SubscriptionSnapshot:
    subscription_id: str
    customer_id: str
    state: str                              # the provider's own status word
    price_id: str | None
    currency: str | None
    interval: str | None
    unit_amount: int | None
    cancel_at_period_end: bool
    current_period_end: datetime | None
    latest_invoice_state: str               # none | open | paid | failed | action_required
    livemode: bool
    observed_at: datetime


@dataclass(frozen=True)
class CheckoutAssociation:
    session_id: str
    client_reference_id: str | None
    subscription_id: str | None
    livemode: bool


class ProviderStateReader(Protocol):
    def get_subscription(self, subscription_id: str) -> SubscriptionSnapshot: ...
    def checkout_session(self, session_id: str) -> CheckoutAssociation: ...
    def checkout_for_subscription(self, subscription_id: str) -> CheckoutAssociation | None: ...
    def subscription_for_payment(self, *, payment_intent: str | None, charge: str | None) -> str | None: ...


class NullStateReader:
    """The runtime default while webhooks are not authorized: every read says "not enabled" (retryable, never a state)."""

    def _off(self, *a: Any, **k: Any):
        raise ProviderStateUnavailable("not_enabled")

    get_subscription = checkout_session = checkout_for_subscription = subscription_for_payment = _off


_INVOICE = {"paid": "paid", "open": "open", "uncollectible": "failed", "void": "failed", "draft": "open"}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


class StripeStateReader:
    """Reads through the official SDK client. NOT constructed in this wave."""

    def __init__(self, client_factory: Callable[[], Any], *, environment: str = "sandbox", clock: Callable[[], datetime] | None = None) -> None:
        self._factory = client_factory
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _call(self, fn: Callable[[], Any]) -> Any:
        from src.billing.stripe_provider import map_stripe_error

        try:
            return fn()
        except ProviderStateError:
            raise
        except Exception as exc:  # noqa: BLE001 - reduced to a bounded category; the SDK message is discarded
            category = map_stripe_error(exc)
            if category in ("provider_timeout", "provider_unavailable", "rate_limited"):
                raise ProviderStateUnavailable(category) from None
            if type(exc).__name__ == "InvalidRequestError" and "no such" in str(exc).lower():
                raise ProviderStateNotFound("not_found") from None
            raise ProviderStateUnavailable("provider_unavailable" if category == "unknown" else category) from None

    def get_subscription(self, subscription_id: str) -> SubscriptionSnapshot:
        sub = self._call(lambda: self._factory().v1.subscriptions.retrieve(subscription_id, {"expand": ["latest_invoice"]}))
        items = _get(_get(sub, "items"), "data") or []
        item = items[0] if len(items) == 1 else None            # exactly one line item is the supported shape
        price = _get(item, "price")
        recurring = _get(price, "recurring")
        customer = _get(sub, "customer")
        customer_id = customer if isinstance(customer, str) else _get(customer, "id")
        status = _get(sub, "status")
        if not isinstance(customer_id, str) or not isinstance(status, str) or _get(sub, "id") != subscription_id or item is None:
            raise ProviderStateInvalid("incomplete_response")
        end = _get(item, "current_period_end") or _get(sub, "current_period_end")
        inv = _get(sub, "latest_invoice")
        inv_status = _get(inv, "status") if inv is not None and not isinstance(inv, str) else None
        return SubscriptionSnapshot(
            subscription_id=subscription_id, customer_id=customer_id, state=status, price_id=_get(price, "id"), currency=(_get(price, "currency") or "").upper() or None,
            interval=_get(recurring, "interval"), unit_amount=_get(price, "unit_amount"), cancel_at_period_end=bool(_get(sub, "cancel_at_period_end")),
            current_period_end=datetime.fromtimestamp(end, tz=timezone.utc) if isinstance(end, int) else None,
            latest_invoice_state=_INVOICE.get(inv_status, "none") if inv_status else "none", livemode=bool(_get(sub, "livemode")), observed_at=self._clock())

    def _association(self, s: Any) -> CheckoutAssociation:
        sub = _get(s, "subscription")
        return CheckoutAssociation(session_id=_get(s, "id"), client_reference_id=_get(s, "client_reference_id"),
                                   subscription_id=sub if isinstance(sub, str) else _get(sub, "id"), livemode=bool(_get(s, "livemode")))

    def checkout_session(self, session_id: str) -> CheckoutAssociation:
        return self._association(self._call(lambda: self._factory().v1.checkout.sessions.retrieve(session_id)))

    def checkout_for_subscription(self, subscription_id: str) -> CheckoutAssociation | None:
        page = self._call(lambda: self._factory().v1.checkout.sessions.list({"subscription": subscription_id, "limit": 2}))
        data = _get(page, "data") or []
        if len(data) > 1:
            raise ProviderStateInvalid("ambiguous_checkout")
        return self._association(data[0]) if data else None

    def subscription_for_payment(self, *, payment_intent: str | None, charge: str | None) -> str | None:
        """API 2025-03-31.basil or later: payment intent -> InvoicePayment list -> invoice -> ``parent.subscription_details.subscription``."""
        if payment_intent is None and charge is not None:
            ch = self._call(lambda: self._factory().v1.charges.retrieve(charge))
            payment_intent = _get(ch, "payment_intent")
        if not isinstance(payment_intent, str):
            return None                                           # not a Billing payment: documented as not applicable
        subs: set[str] = set()
        payments = self._call(lambda: self._factory().v1.invoice_payments.list({"payment": {"type": "payment_intent", "payment_intent": payment_intent}, "status": "paid", "limit": 10}))
        for ip in _get(payments, "data") or []:
            inv_ref = _get(ip, "invoice")
            inv_id = inv_ref if isinstance(inv_ref, str) else _get(inv_ref, "id")
            inv = self._call(lambda i=inv_id: self._factory().v1.invoices.retrieve(i))
            parent = _get(inv, "parent")
            if _get(parent, "type") == "subscription_details":
                s = _get(_get(parent, "subscription_details"), "subscription")
                subs.add(s if isinstance(s, str) else _get(s, "id"))
        if len(subs) > 1:
            raise ProviderStateInvalid("ambiguous_subscription")
        return next(iter(subs)) if subs else None


class FakeStateReader:
    """Deterministic in-memory reader for tests. Holds the provider's TRUE state and can be told to fail. Makes no network call."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.subscriptions: dict[str, dict] = {}
        self.checkouts: dict[str, CheckoutAssociation] = {}
        self.payments: dict[str, str] = {}
        self.fail: ProviderStateError | None = None
        self.fail_times = 0
        self.calls: list[str] = []

    def set_subscription(self, subscription_id: str, **kw: Any) -> None:
        base = dict(customer_id="cus_1", state="active", price_id="price_test_1", currency="EUR", interval="month", unit_amount=1999, cancel_at_period_end=False,
                    current_period_end=None, latest_invoice_state="paid", livemode=False)
        base.update(self.subscriptions.get(subscription_id, {}))
        base.update(kw)
        self.subscriptions[subscription_id] = base

    def _maybe_fail(self, what: str) -> None:
        """``fail`` raises on every call while set; with ``fail_times = n`` it raises n times and then clears itself."""
        self.calls.append(what)
        if self.fail is None:
            return
        err = self.fail
        if self.fail_times > 0:
            self.fail_times -= 1
            if self.fail_times == 0:
                self.fail = None
        raise err

    def get_subscription(self, subscription_id: str) -> SubscriptionSnapshot:
        self._maybe_fail("get_subscription")
        raw = self.subscriptions.get(subscription_id)
        if raw is None:
            raise ProviderStateNotFound("not_found")
        return SubscriptionSnapshot(subscription_id=subscription_id, observed_at=self.clock(), **raw)

    def checkout_session(self, session_id: str) -> CheckoutAssociation:
        self._maybe_fail("checkout_session")
        if session_id not in self.checkouts:
            raise ProviderStateNotFound("not_found")
        return self.checkouts[session_id]

    def checkout_for_subscription(self, subscription_id: str) -> CheckoutAssociation | None:
        self._maybe_fail("checkout_for_subscription")
        return next((c for c in self.checkouts.values() if c.subscription_id == subscription_id), None)

    def subscription_for_payment(self, *, payment_intent: str | None, charge: str | None) -> str | None:
        self._maybe_fail("subscription_for_payment")
        return self.payments.get(payment_intent or "") or self.payments.get(charge or "")


def build_runtime_reader() -> ProviderStateReader:
    """The runtime reader: never a real one while webhooks are unauthorized."""
    return NullStateReader()

