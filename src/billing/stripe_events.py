"""Stripe webhook contract (W12.4D-D): signature verification, environment validation, the explicit event allow-list and ALLOW-LISTED normalisation.

Nothing here touches the network or the database. Reviewed against Stripe's documentation (webhooks, subscription webhooks, Managed Payments):
* the ``Stripe-Signature`` header carries ``t=<unix>`` and one or more ``v1=<hmac>`` values (several while a signing secret is being rolled), the HMAC
  is over ``<t>.<raw body>``, and the body must be the UNMODIFIED raw bytes;
* event ids identify duplicate deliveries; ``created`` has one-second resolution, equal timestamps happen and it must not decide order; delivery
  order is NOT guaranteed; the live retry window is three days with exponential back-off, a sandbox retries three times within hours;
* after ``invoice.paid`` the subscription is RETRIEVED and must be ``active`` before access is extended; ``canceled`` and ``unpaid`` are the
  documented revocation states; refund and dispute events carry a charge or payment intent that must be mapped to an invoice and subscription;
* Managed Payments supports Billing subscriptions, handles disputes and support itself, and does not support Connect (an event carrying an
  ``account`` is therefore refused).
UNCONFIRMED for Managed Payments and therefore not relied on: ``refund.created`` / ``refund.updated`` event parity, sandbox event availability.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.billing import policy as P

# The ONLY event types processed. Anything else is acknowledged as ignored and never grants access.
EVENT_KINDS: dict[str, str] = {
    "checkout.session.completed": "checkout",
    "checkout.session.async_payment_succeeded": "checkout",
    "checkout.session.async_payment_failed": "checkout",
    "customer.subscription.created": "subscription",
    "customer.subscription.updated": "subscription",
    "customer.subscription.deleted": "subscription",
    "customer.subscription.paused": "subscription",
    "customer.subscription.resumed": "subscription",
    "invoice.paid": "invoice",
    "invoice.payment_failed": "invoice",
    "invoice.payment_action_required": "invoice",
    "charge.refunded": "refund",
    "charge.dispute.created": "dispute",
    "charge.dispute.closed": "dispute",
}
ALLOWED_EVENT_TYPES = tuple(EVENT_KINDS)
# Considered and deliberately NOT subscribed: refund.created / refund.updated (parity under Managed Payments unconfirmed; charge.refunded is the documented subscription
# refund signal), radar.early_fraud_warning.created, customer.updated, invoice.created / finalized / upcoming, payment_intent.*, subscription_schedule.*, entitlements.*.
NOT_SUBSCRIBED_EVENT_TYPES = ("refund.created", "refund.updated", "radar.early_fraud_warning.created", "customer.updated", "invoice.created", "invoice.finalized",
                              "invoice.upcoming", "payment_intent.succeeded", "customer.subscription.trial_will_end", "subscription_schedule.created")
SUPPORTED_API_VERSIONS = (P.STRIPE_API_VERSION,)

_EVENT_ID = re.compile(r"^evt_[A-Za-z0-9_]{1,76}$")
_OBJECT_ID = re.compile(r"^[a-z]{1,12}_[A-Za-z0-9_]{1,76}$")
_CLIENT_REF = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class WebhookError(Exception):
    """A bounded, safe failure. ``category`` is the only thing that leaves this module; ``status`` is the HTTP status the route returns."""

    def __init__(self, category: str, status: int) -> None:
        super().__init__(category)
        self.category, self.status = category, status


def verify_signature(raw_body: bytes, header: str | None, secrets: list[str], *, now: float | None = None,
                     tolerance: int = P.WEBHOOK_TOLERANCE_SECONDS) -> None:
    """Raise ``WebhookError`` unless the UNMODIFIED body is authentically signed by one of ``secrets`` within the timestamp tolerance (past AND future)."""
    import stripe

    if not header:
        raise WebhookError("signature_missing", 400)
    if not secrets:
        raise WebhookError("not_configured", 503)
    try:
        text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        raise WebhookError("malformed_body", 400) from None
    try:
        timestamp, signatures = stripe.WebhookSignature._get_timestamp_and_signatures(header, stripe.WebhookSignature.EXPECTED_SCHEME)
    except Exception:  # noqa: BLE001
        raise WebhookError("signature_malformed", 400) from None
    if not signatures:
        raise WebhookError("signature_malformed", 400)
    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance:
        raise WebhookError("timestamp_outside_tolerance", 400)       # old OR future: the SDK alone only rejects the past
    for secret in secrets:
        try:
            stripe.WebhookSignature.verify_header(text, header, secret, None)       # tolerance enforced above, in both directions
            return
        except stripe.SignatureVerificationError:
            continue
    raise WebhookError("signature_invalid", 400)


def parse_event(raw_body: bytes) -> dict:
    """Parse an ALREADY AUTHENTICATED body. Structural problems are a safe 400 (the sender is authentic but the payload is unusable)."""
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise WebhookError("malformed_body", 400) from None
    if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not _EVENT_ID.match(event["id"]) or not isinstance(event.get("type"), str) \
            or not isinstance(event.get("livemode"), bool) or not isinstance(event.get("data"), dict) or not isinstance(event["data"].get("object"), dict):
        raise WebhookError("malformed_event", 400)
    return event


def event_environment(event: dict) -> str:
    return "live" if event["livemode"] else "sandbox"


def require_environment(event: dict, configured_environment: str | None) -> str:
    """A valid signature never bypasses the configured environment: a sandbox event is refused by a live deployment and the reverse; unknown fails closed."""
    env = event_environment(event)
    if configured_environment not in P.STRIPE_ENVIRONMENTS or env != configured_environment:
        raise WebhookError("environment_mismatch", 400)
    return env


def _id(value: Any) -> str | None:
    return value if isinstance(value, str) and _OBJECT_ID.match(value) else None


def _expandable_id(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("id")
    return _id(value)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10**10 else None


def _created(event: dict) -> datetime | None:
    created = _int(event.get("created"))
    return datetime.fromtimestamp(created, tz=timezone.utc) if created is not None else None


@dataclass
class Normalised:
    kind: str
    object_id: str | None
    subscription_id: str | None
    fields: dict


def normalise(event: dict) -> Normalised:
    """ALLOW-LISTED fields only: ids, status words and integer amounts. No email, name, address, card data, description or metadata is copied."""
    kind = EVENT_KINDS[event["type"]]
    obj = event["data"]["object"]
    object_id = _id(obj.get("id"))
    f: dict = {}
    sub = None
    if kind == "subscription":
        sub = object_id
        f.update(customer_id=_expandable_id(obj.get("customer")), status=obj.get("status") if isinstance(obj.get("status"), str) else None,
                 cancel_at_period_end=obj.get("cancel_at_period_end") is True)
    elif kind == "invoice":
        parent = obj.get("parent") if isinstance(obj.get("parent"), dict) else {}
        details = parent.get("subscription_details") if isinstance(parent.get("subscription_details"), dict) else {}
        sub = _expandable_id(details.get("subscription")) or _expandable_id(obj.get("subscription"))       # current shape first, then the legacy field
        f.update(customer_id=_expandable_id(obj.get("customer")), status=obj.get("status") if isinstance(obj.get("status"), str) else None,
                 amount_paid=_int(obj.get("amount_paid")))
    elif kind == "checkout":
        sub = _expandable_id(obj.get("subscription"))
        ref = obj.get("client_reference_id")
        f.update(customer_id=_expandable_id(obj.get("customer")), checkout_session_id=object_id, client_reference_id=ref if isinstance(ref, str) and _CLIENT_REF.match(ref) else None,
                 payment_status=obj.get("payment_status") if isinstance(obj.get("payment_status"), str) else None,
                 mode=obj.get("mode") if isinstance(obj.get("mode"), str) else None)
    elif kind == "refund":
        f.update(charge_id=object_id, payment_intent=_expandable_id(obj.get("payment_intent")), refunded=obj.get("refunded") is True,
                 amount=_int(obj.get("amount")), amount_refunded=_int(obj.get("amount_refunded")))
    elif kind == "dispute":
        f.update(charge_id=_expandable_id(obj.get("charge")), payment_intent=_expandable_id(obj.get("payment_intent")),
                 dispute_status=obj.get("status") if isinstance(obj.get("status"), str) else None, dispute_id=object_id)
    return Normalised(kind=kind, object_id=object_id, subscription_id=sub, fields={k: v for k, v in f.items() if v is not None})


# W12.4D-F2-B1R: a validly signed FINANCIAL event delivered under an API version this code does not support is HELD for an operator, never ignored and never
# interpreted. Only the opaque id of the object the event names is kept, and only when its prefix matches the object type the event type promises; it is an
# untrusted lookup key for an authoritative provider read, not evidence. No other field of an incompatible payload is read.
INCOMPATIBLE_REFERENCE_PREFIX = {"subscription": "sub_", "invoice": "in_", "checkout": "cs_", "refund": "ch_", "dispute": "dp_"}


def reference_only(event: dict) -> dict:
    kind = EVENT_KINDS[event["type"]]
    object_id = _id(event["data"]["object"].get("id"))
    if object_id is not None and not object_id.startswith(INCOMPATIBLE_REFERENCE_PREFIX[kind]):
        object_id = None
    return {"kind": kind, "api_incompatible": True, "object_id": object_id}


def created_at(event: dict) -> datetime | None:
    return _created(event)
