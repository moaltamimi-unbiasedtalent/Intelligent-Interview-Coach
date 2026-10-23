"""Brevo delivery-event webhook: authenticate, validate, allow-list, store (05D, PG-02). Offline engineering; LIVE verification is NOT RUN.

Truth model (unchanged): ``EmailAttempt.status`` is what the provider said when it ACCEPTED a submission. It is never rewritten by this module.
A verified webhook may add a SEPARATE ``delivery_state`` (delivered / soft_bounced / hard_bounced / blocked / complained). Provider
acceptance is not delivery; a state exists only when an authenticated event says so.

Gate: ``DELIVERY_EVENTS_AUTHORIZED`` is a code constant that stays ``False`` until the owner authorises delivery-event collection. While it is
False the receiver refuses everything (503) and stores nothing, whatever the configuration or signature.

Authentication (fail closed; there is no "unsigned" mode):
  * ``hmac`` (default): header ``X-Ask4Mo-Webhook-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>." + raw body)>``. A relay or
    gateway in front of Brevo (or Brevo itself, if staging proves it can) supplies it. The timestamp must be within
    ``SIGNATURE_TOLERANCE_SECONDS`` of now in BOTH directions (old and future-dated are refused).
  * ``bearer``: Brevo's webhook can send a custom ``Authorization: Bearer <secret>`` header. Compared in constant time. The exact scheme Brevo
    offers must be confirmed on staging (NOT RUN); that is why both are implemented and the choice is configuration (``BREVO_WEBHOOK_AUTH``).
Secrets come from ``BREVO_WEBHOOK_SECRET`` (and ``BREVO_WEBHOOK_SECRET_PREVIOUS`` for rotation) via the secret store / environment, never a default.

Replay protection: (1) signature timestamp window (hmac mode); (2) event freshness: the payload's own ``ts_event`` must be within
``EVENT_MAX_AGE_SECONDS`` (and not in the future); (3) a durable per-attempt digest of the last applied event makes a replay a no-op, and a
state machine that only moves forward (rank) makes an out-of-order or re-sent older event harmless.

Bounded storage: only the allow-listed state, its event time and a one-way digest. The recipient address, subject, links, tags, IP, user agent and
the raw payload are NEVER stored or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable

log = logging.getLogger("mail.webhook")

# Code gate. Do NOT flip without an owner decision and the staging round trip (docs/production/identity_live_verification_05D.md).
DELIVERY_EVENTS_AUTHORIZED = False

SIGNATURE_HEADER = "x-ask4mo-webhook-signature"
SIGNATURE_TOLERANCE_SECONDS = 300
EVENT_MAX_AGE_SECONDS = 3600
MAX_BODY_BYTES = 16 * 1024
MAX_REF_LENGTH = 80
AUTH_MODES = ("hmac", "bearer")

# provider event name -> internal state. Anything not listed (opened, click, request, deferred, unsubscribed, ...) is acknowledged and ignored.
EVENT_TO_STATE = {
    "delivered": "delivered",
    "soft_bounce": "soft_bounced", "softbounce": "soft_bounced",
    "hard_bounce": "hard_bounced", "hardbounce": "hard_bounced",
    "blocked": "blocked",
    "spam": "complained", "complaint": "complained",
}
DELIVERY_STATES = ("delivered", "soft_bounced", "blocked", "hard_bounced", "complained")
_RANK = {"delivered": 1, "soft_bounced": 2, "blocked": 2, "hard_bounced": 3, "complained": 4}


class WebhookError(Exception):
    """A refusal with a bounded category and an HTTP status. Never carries a payload, header or secret."""

    def __init__(self, category: str, status: int) -> None:
        super().__init__(category)
        self.category, self.status = category, status


def sign(secret: str, body: bytes, timestamp: int) -> str:
    """The header value a sender (or a test) produces for ``body`` at ``timestamp``."""
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify_hmac(body: bytes, header: str | None, secrets: list[str], *, now: float) -> None:
    if not header or len(header) > 256:
        raise WebhookError("signature_missing", 401)
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        k, sep, v = item.strip().partition("=")
        if not sep:
            raise WebhookError("signature_malformed", 400)
        parts.setdefault(k, []).append(v)
    ts, sigs = parts.get("t", []), parts.get("v1", [])
    if len(ts) != 1 or not sigs or not ts[0].isdigit() or len(ts[0]) > 12:
        raise WebhookError("signature_malformed", 400)
    timestamp = int(ts[0])
    if abs(now - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
        raise WebhookError("timestamp_out_of_tolerance", 401)       # old (replayed) and future-dated alike
    ok = False
    for secret in secrets:                                           # no early exit: constant work per configured secret
        expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        for sig in sigs:
            ok |= hmac.compare_digest(expected, sig.lower())
    if not ok:
        raise WebhookError("signature_invalid", 401)


def verify_bearer(header: str | None, secrets: list[str]) -> None:
    if not header or len(header) > 512:
        raise WebhookError("signature_missing", 401)
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise WebhookError("signature_malformed", 400)
    ok = False
    for secret in secrets:
        ok |= hmac.compare_digest(secret.encode(), token.strip().encode())
    if not ok:
        raise WebhookError("signature_invalid", 401)


def normalise_ref(ref: str) -> str:
    return ref.strip().strip("<>")[:MAX_REF_LENGTH]


def parse_event(body: bytes, *, now: float) -> dict | None:
    """Parse and allow-list. Returns ``{"state", "ref", "at", "digest"}``, or ``None`` for a well-formed event we deliberately ignore.
    Raises ``WebhookError`` for a malformed or stale payload. Nothing outside the allow-list is read into the result."""
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        raise WebhookError("payload_malformed", 400) from None
    if not isinstance(data, dict):
        raise WebhookError("payload_malformed", 400)
    name = data.get("event")
    if not isinstance(name, str) or not name or len(name) > 40:
        raise WebhookError("payload_malformed", 400)
    ts = data.get("ts_event", data.get("ts"))
    if isinstance(ts, bool) or not isinstance(ts, (int, float)) or ts <= 0 or ts > 4_102_444_800:
        raise WebhookError("payload_malformed", 400)
    if ts > now + SIGNATURE_TOLERANCE_SECONDS:
        raise WebhookError("event_in_future", 400)
    if now - ts > EVENT_MAX_AGE_SECONDS:
        raise WebhookError("event_too_old", 400)
    ref = data.get("message-id", data.get("message_id"))
    if not isinstance(ref, str) or not ref or len(ref) > MAX_REF_LENGTH * 2 or not ref.isprintable():
        raise WebhookError("payload_malformed", 400)
    state = EVENT_TO_STATE.get(name.strip().lower().replace("-", "_"))
    if state is None:
        return None
    ref = normalise_ref(ref)
    digest = hashlib.sha256(f"{ref}|{state}|{int(ts)}".encode()).hexdigest()
    return {"state": state, "ref": ref, "at": datetime.fromtimestamp(int(ts), tz=timezone.utc), "digest": digest}


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def should_apply(current_state: str | None, current_digest: str | None, current_at: datetime | None, event: dict) -> str:
    """'replay' (same event again), 'stale' (would move backwards) or 'apply'."""
    if current_digest == event["digest"]:
        return "replay"
    if current_state is None:
        return "apply"
    cur, new = _RANK.get(current_state, 0), _RANK[event["state"]]
    if new > cur:
        return "apply"
    if new == cur and current_at is not None and _aware(event["at"]) > _aware(current_at):
        return "apply"
    return "stale"


class DeliveryEventReceiver:
    """authorised? -> configured? -> authenticate raw body -> parse/allow-list -> apply. Responses never echo payload, signature or reason."""

    def __init__(self, store, *, secrets: Callable[[], list[str]], auth_mode: str = "hmac", authorized: bool | None = None,
                 clock: Callable[[], float] | None = None, audit=None) -> None:
        self._store, self._secrets, self._mode = store, secrets, auth_mode
        self._authorized = DELIVERY_EVENTS_AUTHORIZED if authorized is None else authorized
        self._clock, self._audit = clock or time.time, audit

    def handle(self, raw_body: bytes, headers: dict[str, str | None], *, correlation_id: str | None = None) -> dict:
        if self._authorized is not True:
            raise WebhookError("not_enabled", 503)                  # stores nothing, audits nothing
        if self._mode not in AUTH_MODES:
            raise WebhookError("not_configured", 503)
        secrets = [s for s in self._secrets() if s]
        if not secrets:
            raise WebhookError("not_configured", 503)
        if len(raw_body) > MAX_BODY_BYTES:
            raise WebhookError("payload_too_large", 413)
        now = self._clock()
        try:
            if self._mode == "hmac":
                verify_hmac(raw_body, headers.get(SIGNATURE_HEADER), secrets, now=now)
            else:
                verify_bearer(headers.get("authorization"), secrets)
            event = parse_event(raw_body, now=now)
        except WebhookError as exc:
            self._record("mail.webhook_rejected", correlation_id, category=exc.category)
            raise
        if event is None:
            return {"status": "accepted"}
        try:
            outcome = self._store.apply_delivery_event(event)
        except Exception:  # noqa: BLE001 - not stored: retryable, never an acknowledgement
            log.warning("delivery event not stored")
            raise WebhookError("persistence_failed", 503) from None
        self._record("mail.delivery_event", correlation_id, outcome=outcome, state=event["state"])
        return {"status": "accepted"}

    def _record(self, name: str, correlation_id: str | None, **ctx) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=name, result="failure" if name.endswith("rejected") else "success", target_type="mail_webhook",
                               request_id=correlation_id, context=ctx)
        except Exception:  # noqa: BLE001
            pass
