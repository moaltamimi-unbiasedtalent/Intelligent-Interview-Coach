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


class ProviderStateConfiguration(ProviderStateError):
    """The provider refused US (credential, permission, API version, account, unsupported feature). Retrying cannot help: an operator must act."""


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


@dataclass(frozen=True)
class InvoiceSnapshot:
    invoice_id: str
    subscription_id: str | None
    status: str                             # draft | open | paid | uncollectible | void (Stripe's own word, validated)
    amount_paid: int
    amount_due: int
    currency: str | None
    payment_intent: str | None
    livemode: bool


@dataclass(frozen=True)
class RefundSnapshot:
    refund_id: str
    payment_intent: str | None
    charge: str | None
    status: str                             # pending | requires_action | succeeded | failed | canceled
    amount: int
    currency: str | None
    livemode: bool


@dataclass(frozen=True)
class DisputeSnapshot:
    dispute_id: str
    charge: str | None
    payment_intent: str | None
    status: str                             # Stripe's dispute status word, validated
    amount: int
    currency: str | None
    livemode: bool


SUBSCRIPTION_STATUSES = ("incomplete", "incomplete_expired", "trialing", "active", "past_due", "unpaid", "paused", "canceled")
INVOICE_STATUSES = ("draft", "open", "paid", "uncollectible", "void")
REFUND_STATUSES = ("pending", "requires_action", "succeeded", "failed", "canceled")
DISPUTE_STATUSES = ("warning_needs_response", "warning_under_review", "warning_closed", "needs_response", "under_review", "won", "lost", "prevented")
# The ONLY provider operations this module can perform: (SDK resource, method). Everything is a read; a create, update, cancel, refund or delete is not
# reachable because ``_invoke`` resolves the method through this table and refuses anything else.
READ_ONLY_OPERATIONS = frozenset({
    ("subscriptions", "retrieve"), ("checkout.sessions", "retrieve"), ("checkout.sessions", "list"), ("charges", "retrieve"),
    ("invoice_payments", "list"), ("invoices", "retrieve"), ("refunds", "retrieve"), ("disputes", "retrieve"),
})
_TS_MIN, _TS_MAX = 946_684_800, 4_102_444_800        # 2000-01-01 .. 2100-01-01: a timestamp outside this is malformed, never trusted


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


def _ref_id(value: Any) -> str | None:
    """An id that may arrive as a string or as an expanded object. Anything else is None (never guessed)."""
    got = value if isinstance(value, str) else _get(value, "id")
    return got if isinstance(got, str) and got else None


def _timestamp(value: Any) -> datetime | None:
    """Unix seconds -> aware UTC. Missing is None; a present but malformed value (bool, float, string, out of range) is INVALID, not ignored."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not _TS_MIN <= value <= _TS_MAX:
        raise ProviderStateInvalid("malformed_timestamp")
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _amount(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProviderStateInvalid("malformed_amount")
    return value


def _currency(value: Any, allowed: frozenset[str] | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 3 or not value.isalpha():
        raise ProviderStateInvalid("malformed_currency")
    code = value.upper()
    if allowed is not None and code not in allowed:
        raise ProviderStateInvalid("unsupported_currency")
    return code


def _status(value: Any, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProviderStateInvalid("unsupported_status")         # an unknown status is never mapped to a paid or active state
    return value


class StripeStateReader:
    """Reads through the official SDK client. READ-ONLY and NOT constructed at runtime (``provider_read_gate`` refuses while unauthorized).

    Defence in depth against a mis-wired or future caller: every SDK call goes through ``_invoke``, which only resolves operations listed in
    ``READ_ONLY_OPERATIONS``; the client is built per call by the injected factory (never at import or startup)."""

    def __init__(self, client_factory: Callable[[], Any], *, environment: str = "sandbox", clock: Callable[[], datetime] | None = None,
                 allowed_currencies: frozenset[str] | None = None) -> None:
        if environment != "sandbox":
            raise ProviderStateConfiguration("environment_not_readable")      # live is never read by this release; no sandbox -> live fallback exists
        self._factory = client_factory
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._currencies = allowed_currencies

    # ---- error classification ------------------------------------------------------------------------------------------------------------------
    def _call(self, fn: Callable[[], Any]) -> Any:
        from src.billing.stripe_provider import map_stripe_error

        try:
            return fn()
        except ProviderStateError:
            raise
        except Exception as exc:  # noqa: BLE001 - reduced to a bounded category; the SDK message and payload are discarded
            category = map_stripe_error(exc)
            text = str(exc).lower()
            if category in ("provider_timeout", "provider_unavailable", "rate_limited"):
                raise ProviderStateUnavailable(category) from None
            if category in ("provider_auth_failed", "provider_permission_denied"):
                raise ProviderStateConfiguration(category) from None
            if category == "invalid_request":
                if "no such" in text or "resource_missing" in text:
                    raise ProviderStateNotFound("not_found") from None
                if "api version" in text or "stripe-version" in text:
                    raise ProviderStateConfiguration("invalid_api_version") from None
                if "managed payments" in text or "not supported" in text or "unsupported" in text:
                    raise ProviderStateConfiguration("unsupported_feature") from None
                if "does not have access" in text or "wrong account" in text or "connected account" in text:
                    raise ProviderStateConfiguration("wrong_account") from None
                raise ProviderStateInvalid("invalid_request") from None
            raise ProviderStateUnavailable("provider_unavailable") from None       # unknown failure: retryable, bounded by the job layer, never a state

    def _invoke(self, resource: str, method: str, *args: Any) -> Any:
        if (resource, method) not in READ_ONLY_OPERATIONS:
            raise ProviderStateConfiguration("operation_not_read_only")
        target = self._factory().v1
        for part in resource.split("."):
            target = getattr(target, part)
        return self._call(lambda: getattr(target, method)(*args))

    def _livemode(self, obj: Any) -> bool:
        live = _get(obj, "livemode")
        if not isinstance(live, bool):
            raise ProviderStateInvalid("incomplete_response")
        if live:
            raise ProviderStateInvalid("environment_mismatch")             # a live object in a sandbox read is refused, never normalised
        return live

    # ---- subscription ------------------------------------------------------------------------------------------------------------------------
    def get_subscription(self, subscription_id: str) -> SubscriptionSnapshot:
        sub = self._invoke("subscriptions", "retrieve", subscription_id, {"expand": ["latest_invoice"]})
        items = _get(_get(sub, "items"), "data") or []
        item = items[0] if len(items) == 1 else None            # exactly one line item is the supported shape
        price = _get(item, "price")
        recurring = _get(price, "recurring")
        customer_id = _ref_id(_get(sub, "customer"))
        if customer_id is None or _get(sub, "id") != subscription_id or item is None:
            raise ProviderStateInvalid("incomplete_response")
        status = _status(_get(sub, "status"), SUBSCRIPTION_STATUSES)
        livemode = self._livemode(sub)
        end = _timestamp(_get(item, "current_period_end") if _get(item, "current_period_end") is not None else _get(sub, "current_period_end"))
        inv = _get(sub, "latest_invoice")
        inv_status = _get(inv, "status") if inv is not None and not isinstance(inv, str) else None
        unit_amount = _get(price, "unit_amount")
        if unit_amount is not None:
            unit_amount = _amount(unit_amount)
        return SubscriptionSnapshot(
            subscription_id=subscription_id, customer_id=customer_id, state=status, price_id=_ref_id(price), currency=_currency(_get(price, "currency"), self._currencies),
            interval=_get(recurring, "interval"), unit_amount=unit_amount, cancel_at_period_end=_get(sub, "cancel_at_period_end") is True,
            current_period_end=end, latest_invoice_state=_INVOICE.get(inv_status, "none") if isinstance(inv_status, str) else "none", livemode=livemode, observed_at=self._clock())

    # ---- checkout association ------------------------------------------------------------------------------------------------------------------
    def _association(self, s: Any) -> CheckoutAssociation:
        sid = _get(s, "id")
        if not isinstance(sid, str):
            raise ProviderStateInvalid("incomplete_response")
        return CheckoutAssociation(session_id=sid, client_reference_id=_get(s, "client_reference_id") if isinstance(_get(s, "client_reference_id"), str) else None,
                                   subscription_id=_ref_id(_get(s, "subscription")), livemode=self._livemode(s))

    def checkout_session(self, session_id: str) -> CheckoutAssociation:
        assoc = self._association(self._invoke("checkout.sessions", "retrieve", session_id))
        if assoc.session_id != session_id:
            raise ProviderStateInvalid("incomplete_response")
        return assoc

    def checkout_for_subscription(self, subscription_id: str) -> CheckoutAssociation | None:
        page = self._invoke("checkout.sessions", "list", {"subscription": subscription_id, "limit": 2})
        data = _get(page, "data") or []
        if len(data) > 1:
            raise ProviderStateInvalid("ambiguous_checkout")
        return self._association(data[0]) if data else None

    # ---- payment -> subscription ---------------------------------------------------------------------------------------------------------------
    def subscription_for_payment(self, *, payment_intent: str | None, charge: str | None) -> str | None:
        """API 2025-03-31.basil or later: payment intent -> InvoicePayment list -> invoice -> ``parent.subscription_details.subscription``."""
        if payment_intent is None and charge is not None:
            ch = self._invoke("charges", "retrieve", charge)
            payment_intent = _get(ch, "payment_intent") if isinstance(_get(ch, "payment_intent"), str) else None
        if not isinstance(payment_intent, str):
            return None                                           # not a Billing payment: documented as not applicable
        subs: set[str] = set()
        payments = self._invoke("invoice_payments", "list", {"payment": {"type": "payment_intent", "payment_intent": payment_intent}, "status": "paid", "limit": 10})
        for ip in _get(payments, "data") or []:
            inv_id = _ref_id(_get(ip, "invoice"))
            if inv_id is None:
                raise ProviderStateInvalid("incomplete_response")
            inv = self._invoke("invoices", "retrieve", inv_id)
            parent = _get(inv, "parent")
            if _get(parent, "type") == "subscription_details":
                s = _ref_id(_get(_get(parent, "subscription_details"), "subscription"))
                if s is None:
                    raise ProviderStateInvalid("incomplete_response")
                subs.add(s)
        if len(subs) > 1:
            raise ProviderStateInvalid("ambiguous_subscription")
        return next(iter(subs)) if subs else None

    # ---- evidence reads (invoice, refund, dispute): normalised, never inferred -----------------------------------------------------------------
    def get_invoice(self, invoice_id: str) -> InvoiceSnapshot:
        inv = self._invoke("invoices", "retrieve", invoice_id)
        if _get(inv, "id") != invoice_id:
            raise ProviderStateInvalid("incomplete_response")
        parent = _get(inv, "parent")
        sub = None
        if _get(parent, "type") == "subscription_details":
            sub = _ref_id(_get(_get(parent, "subscription_details"), "subscription"))
        pi = _get(inv, "payment_intent")
        return InvoiceSnapshot(invoice_id=invoice_id, subscription_id=sub, status=_status(_get(inv, "status"), INVOICE_STATUSES), amount_paid=_amount(_get(inv, "amount_paid")),
                               amount_due=_amount(_get(inv, "amount_due")), currency=_currency(_get(inv, "currency"), self._currencies), payment_intent=_ref_id(pi), livemode=self._livemode(inv))

    def get_refund(self, refund_id: str) -> RefundSnapshot:
        r = self._invoke("refunds", "retrieve", refund_id)
        if _get(r, "id") != refund_id:
            raise ProviderStateInvalid("incomplete_response")
        return RefundSnapshot(refund_id=refund_id, payment_intent=_ref_id(_get(r, "payment_intent")), charge=_ref_id(_get(r, "charge")), status=_status(_get(r, "status"), REFUND_STATUSES),
                              amount=_amount(_get(r, "amount")), currency=_currency(_get(r, "currency"), self._currencies), livemode=self._livemode(r))

    def get_dispute(self, dispute_id: str) -> DisputeSnapshot:
        d = self._invoke("disputes", "retrieve", dispute_id)
        if _get(d, "id") != dispute_id:
            raise ProviderStateInvalid("incomplete_response")
        return DisputeSnapshot(dispute_id=dispute_id, charge=_ref_id(_get(d, "charge")), payment_intent=_ref_id(_get(d, "payment_intent")), status=_status(_get(d, "status"), DISPUTE_STATUSES),
                               amount=_amount(_get(d, "amount")), currency=_currency(_get(d, "currency"), self._currencies), livemode=self._livemode(d))


class FakeStateReader:
    """Deterministic in-memory reader for tests. Holds the provider's TRUE state and can be told to fail. Makes no network call."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.subscriptions: dict[str, dict] = {}
        self.checkouts: dict[str, CheckoutAssociation] = {}
        self.payments: dict[str, str] = {}
        self.invoices: dict[str, InvoiceSnapshot] = {}
        self.refunds: dict[str, RefundSnapshot] = {}
        self.disputes: dict[str, DisputeSnapshot] = {}
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

    def get_invoice(self, invoice_id: str) -> InvoiceSnapshot:
        self._maybe_fail("get_invoice")
        if invoice_id not in self.invoices:
            raise ProviderStateNotFound("not_found")
        return self.invoices[invoice_id]

    def get_refund(self, refund_id: str) -> RefundSnapshot:
        self._maybe_fail("get_refund")
        if refund_id not in self.refunds:
            raise ProviderStateNotFound("not_found")
        return self.refunds[refund_id]

    def get_dispute(self, dispute_id: str) -> DisputeSnapshot:
        self._maybe_fail("get_dispute")
        if dispute_id not in self.disputes:
            raise ProviderStateNotFound("not_found")
        return self.disputes[dispute_id]


def build_runtime_reader() -> ProviderStateReader:
    """The runtime reader: ALWAYS the Null reader in this release. Nothing here consults credentials, configuration or the gate, so no startup path,
    readiness probe, credential rotation, webhook, recovery action or scheduler can cause an external read."""
    return NullStateReader()


def build_authorized_reader(store, environment: str, *, client_factory: Callable[[], Any] | None = None,
                            allowed_currencies: frozenset[str] | None = None) -> StripeStateReader:
    """The provider-read authorization boundary. Returns a real reader ONLY when ``policy.PROVIDER_READS_AUTHORIZED`` is true AND the environment is a
    readable one (sandbox). No caller in the application invokes this; a future reviewed sandbox-validation wave would be the first. Refusals carry a
    bounded category and never mention a credential. Building a reader makes no network call: the client is built lazily, per read."""
    from src.billing import policy as P

    if not P.PROVIDER_READS_AUTHORIZED:
        raise ProviderStateConfiguration("provider_reads_not_authorized")
    if environment not in P.PROVIDER_READ_ENVIRONMENTS:
        raise ProviderStateConfiguration("environment_not_readable")
    if client_factory is None:
        from src.billing.stripe_provider import StripeConfigurationError, build_stripe_client

        def client_factory():  # noqa: E306 - default: sandbox-only, SecretStore-backed, per-instance client
            try:
                return build_stripe_client(store, environment)
            except StripeConfigurationError as exc:
                raise ProviderStateConfiguration(exc.category) from None
    return StripeStateReader(client_factory, environment=environment, allowed_currencies=allowed_currencies)
