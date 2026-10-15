"""Webhook receiver (W12.4D-D): authenticate -> validate environment -> durably accept -> schedule. NO reconciliation and NO entitlement change here.

The HTTP route is a thin shell over ``WebhookReceiver.handle``. Order matters and every step fails closed:
  1. authorized?  ``policy.STRIPE_WEBHOOK_AUTHORIZED`` is a code constant (False): until a reviewed release flips it the receiver refuses everything;
  2. the billing mode must be Stripe Managed Payments in the SANDBOX environment (live billing is disabled), and a signing secret must exist for it;
  3. the UNMODIFIED raw body is verified against the ``Stripe-Signature`` header with the CURRENT environment's signing secret (timestamp tolerance both ways);
  4. only now is the body parsed; the event's ``livemode`` must match the configured environment (a valid signature does not bypass this);
  5. the event is durably stored (``ProviderEventService.accept``); a storage failure is a retryable 503, NEVER an acknowledgement;
  6. a processing job is enqueued; if that fails the stored event is picked up by the sweep, so the acknowledgement is still honest.
The response never contains a payload, a signature, a secret or an internal reason.
"""

from __future__ import annotations

from typing import Any, Callable

from src.billing import policy as P
from src.billing import stripe_events as SE
from src.billing.reconcile import ProviderEventService


class WebhookReceiver:
    def __init__(self, events: ProviderEventService, *, jobs: Any = None, secrets: Callable[[], list[str]], environment: str | None,
                 provider_selected: str | None, authorized: bool = P.STRIPE_WEBHOOK_AUTHORIZED, audit: Any = None,
                 clock: Callable[[], float] | None = None) -> None:
        self._events, self._jobs, self._secrets, self._env = events, jobs, secrets, environment
        self._provider, self._authorized, self._audit, self._clock = provider_selected, authorized, audit, clock

    def _gate(self) -> list[str]:
        if self._authorized is not True:
            raise SE.WebhookError("not_enabled", 503)
        if self._provider != P.PROVIDER_STRIPE_MP:
            raise SE.WebhookError("not_enabled", 503)
        if self._env != "sandbox" or P.LIVE_BILLING_ENABLED is not False:
            raise SE.WebhookError("live_disabled", 503)                     # live webhooks are not operational in this release
        secrets = self._secrets()
        if not secrets:
            raise SE.WebhookError("not_configured", 503)
        return secrets

    def handle(self, raw_body: bytes, signature_header: str | None, *, correlation_id: str | None = None) -> dict:
        try:
            secrets = self._gate()          # a refusal here (not authorized / not configured) is NOT audited: nothing happened, and an unauthenticated caller must not be able to grow the audit log
            if len(raw_body) > P.WEBHOOK_MAX_BODY_BYTES:
                raise SE.WebhookError("payload_too_large", 413)
            SE.verify_signature(raw_body, signature_header, secrets, now=self._clock() if self._clock else None)
            event = SE.parse_event(raw_body)
            SE.require_environment(event, self._env)
        except SE.WebhookError as exc:
            if exc.category not in ("not_enabled", "live_disabled", "not_configured"):
                self._record("billing.webhook_signature_rejected" if exc.category.startswith(("signature", "timestamp")) else "billing.webhook_rejected",
                             "failure", correlation_id, category=exc.category)
            raise
        try:
            accepted = self._events.accept(event, correlation_id=correlation_id)
        except SE.WebhookError:
            raise
        except Exception:  # noqa: BLE001 - not stored: a retryable failure, never an acknowledgement
            self._record("billing.webhook_rejected", "failure", correlation_id, category="persistence_failed")
            raise SE.WebhookError("persistence_failed", 503) from None
        if accepted["disposition"] == "accepted" and self._jobs is not None:
            try:
                self._jobs.enqueue(P.JOB_PROCESS_PROVIDER_EVENT, {"event_id": accepted["public_id"]}, idempotency_key=f"bpe:{accepted['public_id']}")
            except Exception:  # noqa: BLE001 - the stored event is the outbox; the sweep recovers it
                self._record("billing.webhook_rejected", "failure", correlation_id, category="enqueue_failed_recoverable")
        return {"status": "accepted"}

    def _record(self, name: str, result: str, correlation_id: str | None, **ctx: Any) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=name, result=result, target_type="billing_webhook", request_id=correlation_id,
                               context={"environment": self._env or "unknown", **ctx})
        except Exception:  # noqa: BLE001
            pass
