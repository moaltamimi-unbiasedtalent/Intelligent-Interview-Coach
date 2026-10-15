"""Stripe Managed Payments provider FOUNDATION (W12.4D-B). No checkout, no webhook, no refund, no network call exists here.

What this module is: the secure, truthful scaffolding for the owner-selected provider (Stripe Managed Payments, where Stripe is the merchant of
record). It resolves credentials ONLY through the W12.4B SecretStore (managed encrypted value, then environment, then not configured), keeps
sandbox and live credentials in separate slots that can never be substituted for one another, builds a Stripe client from explicit per-client
configuration (never the SDK's global ``stripe.api_key``), reports bounded readiness, and fails closed for every capability that is not built.

What it deliberately is not: live billing (a code constant, ``policy.LIVE_BILLING_ENABLED = False``), a checkout, a webhook receiver, an entitlement
source, or proof that Managed Payments is available to this seller (eligibility and sandbox access are reported as NOT confirmed).

Reviewed Stripe contract for the later checkout wave (W12.4D-C), from Stripe's Managed Payments documentation:
* a Checkout Session must be created with ``managed_payments[enabled]=true`` (``mode=subscription`` for subscriptions) on API version
  ``2025-03-31.basil`` or later (this code pins the SDK's ``2026-09-30.endive``); without it Ask4Mo would be an ordinary Stripe merchant, not
  covered by the merchant of record, and would owe indirect tax itself. ``require_managed_payments`` below refuses any parameter set that lacks it.
* products must carry an approved Managed Payments tax code (for example SaaS or AI-as-a-service, personal use) and be fully automated digital products;
* the seller must accept the Managed Payments terms in the Stripe Dashboard and pass Stripe's eligibility review.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.billing import policy as P
from src.billing.provider import CheckoutRequest, CheckoutResult, ProviderRejected, ProviderRetryable

log = logging.getLogger("billing.stripe")

# Credential slots. Four DISTINCT slots (never one slot plus a mode flag): a sandbox value can never be read in live mode or the reverse.
SLOT_NAMES = {
    "sandbox": {"api": "STRIPE_SANDBOX_SECRET_KEY", "webhook": "STRIPE_SANDBOX_WEBHOOK_SECRET"},
    "live": {"api": "STRIPE_LIVE_SECRET_KEY", "webhook": "STRIPE_LIVE_WEBHOOK_SECRET"},
}
API_KEY_PREFIXES = {"sandbox": ("sk_test_", "rk_test_"), "live": ("sk_live_", "rk_live_")}
WEBHOOK_PREFIX = "whsec_"
ENVIRONMENT_SETTING = "STRIPE_ENVIRONMENT"
CLIENT_TIMEOUT_SECONDS = 10.0
ERROR_CATEGORIES = ("provider_auth_failed", "provider_permission_denied", "rate_limited", "provider_timeout", "provider_unavailable",
                    "invalid_request", "signature_invalid", "unknown")


class StripeConfigurationError(Exception):
    """A configuration that must not be used. ``category`` is bounded; the message never contains a credential."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


def selected_environment() -> str:
    """``STRIPE_ENVIRONMENT`` (default sandbox). An unknown value raises: it is never guessed."""
    from src.core import secrets as rt

    raw = (rt.read_setting(ENVIRONMENT_SETTING) or "sandbox").strip().lower()
    if raw not in P.STRIPE_ENVIRONMENTS:
        raise StripeConfigurationError("invalid_environment")
    return raw


def require_managed_payments(params: dict) -> dict:
    """Safety rail for W12.4D-C: refuse any Checkout Session parameter set that would make Ask4Mo the merchant of record."""
    mp = params.get("managed_payments")
    if not isinstance(mp, dict) or mp.get("enabled") is not True:
        raise StripeConfigurationError("managed_payments_not_enabled")
    return params


# ------------------------------------------------------------------------------------------------------------
# Credential state (booleans and source kinds only: no value, prefix, suffix or fingerprint ever leaves this module)
# ------------------------------------------------------------------------------------------------------------

def _kind(source: str) -> str:
    return "managed" if source == "managed" else ("environment" if source in ("environment", "secrets_file") else "none")


def slot_state(store, environment: str, kind: str) -> dict:
    """``configured``, ``well_formed`` (right prefix for THIS environment) and ``other_environment`` (it looks like the OTHER environment's value)."""
    name = SLOT_NAMES[environment][kind]
    secret = store.get_for_runtime(name)
    state = {"configured": False, "well_formed": False, "other_environment": False, "source_kind": _kind(store.source(name))}
    if secret is None:
        return state
    value = secret.get_secret_value()
    state["configured"] = True
    if kind == "api":
        other = "live" if environment == "sandbox" else "sandbox"
        state["well_formed"] = value.startswith(API_KEY_PREFIXES[environment])
        state["other_environment"] = value.startswith(API_KEY_PREFIXES[other])
    else:
        state["well_formed"] = value.startswith(WEBHOOK_PREFIX)
    return state


def readiness(store, *, provider_selected: str, environment: str | None) -> dict:
    """Bounded, truthful readiness. Never "healthy", never "merchant of record approved": no check against Stripe has ever run."""
    checks: list[dict] = []
    err = None
    if provider_selected != P.PROVIDER_STRIPE_MP:
        status = "not_configured"
    elif environment not in P.STRIPE_ENVIRONMENTS:
        status, err = "configuration_error", "invalid_environment"
    elif environment == "live":
        status = "live_disabled"                       # live billing is a code constant, not a setting
    else:
        api, hook = slot_state(store, "sandbox", "api"), slot_state(store, "sandbox", "webhook")
        checks = [
            {"code": "api_credential_present", "passed": api["configured"]},
            {"code": "api_credential_matches_sandbox", "passed": api["configured"] and api["well_formed"] and not api["other_environment"]},
            {"code": "webhook_signing_present", "passed": hook["configured"]},
            {"code": "webhook_signing_format", "passed": hook["configured"] and hook["well_formed"]},
        ]
        if api["other_environment"]:
            status, err = "configuration_error", "credential_environment_mismatch"
        elif (api["configured"] and not api["well_formed"]) or (hook["configured"] and not hook["well_formed"]):
            status, err = "configuration_error", "credential_format"
        elif not api["configured"] or not hook["configured"]:
            status = "not_configured"
        else:
            status = "sandbox_access_unverified"       # configured and well formed, but no call has ever confirmed access
    live_present = {k: slot_state(store, "live", k)["configured"] for k in ("api", "webhook")}
    return {
        "status": status,
        "provider_selected": provider_selected,
        "environment": environment,
        "checks": checks,
        "configuration_problem": err,
        "sandbox": {k: {kk: v[kk] for kk in ("configured", "source_kind")} for k, v in
                    ((k, slot_state(store, "sandbox", k)) for k in ("api", "webhook"))},
        "live_slots_populated": live_present["api"] or live_present["webhook"],
        "eligibility": "not_confirmed",               # Stripe's Managed Payments eligibility review for the seller has not been evidenced
        "merchant_of_record": "not_confirmed",
        "sandbox_access": "unverified",
        "live_billing": "disabled",
        "checkout": "not_implemented",
        "refunds": "not_implemented",
        "webhooks": "not_implemented",
        "last_successful_check": None,
        "last_failure_category": None,
        "api_version": P.STRIPE_API_VERSION,
        "managed_payments_required": True,
    }


# ------------------------------------------------------------------------------------------------------------
# Client factory (explicit per-client configuration; nothing global)
# ------------------------------------------------------------------------------------------------------------

def build_stripe_client(store, environment: str, *, client_cls: Callable[..., Any] | None = None, http_client: Any = None,
                        timeout: float = CLIENT_TIMEOUT_SECONDS):
    """Build a Stripe client for ONE environment, or refuse. Constructing a client makes no network call.

    Refusals (``StripeConfigurationError``): live is disabled in this release; the sandbox key is missing; it is not a sandbox key (a live or malformed
    value is never accepted in a sandbox slot); only the selected environment's slot is ever read, so there is no cross-environment fallback.
    The API key is passed to THIS client only: the SDK's global ``stripe.api_key`` is never set. No automatic retries (``max_network_retries=0``): an
    ambiguous outcome is surfaced, never replayed silently. The timeout is bounded.
    """
    if environment != "sandbox":
        raise StripeConfigurationError("live_disabled" if environment == "live" else "invalid_environment")
    state = slot_state(store, "sandbox", "api")
    if not state["configured"]:
        raise StripeConfigurationError("not_configured")
    if state["other_environment"]:
        raise StripeConfigurationError("credential_environment_mismatch")
    if not state["well_formed"]:
        raise StripeConfigurationError("credential_format")
    key = store.get_for_runtime(SLOT_NAMES["sandbox"]["api"]).get_secret_value()
    if client_cls is None:
        import stripe

        client_cls = stripe.StripeClient
        http_client = http_client or stripe.RequestsClient(timeout=timeout)
    return client_cls(key, stripe_version=P.STRIPE_API_VERSION, max_network_retries=0, http_client=http_client)


def map_stripe_error(exc: BaseException) -> str:
    """Reduce ANY Stripe SDK exception to a bounded category. The exception text (which can embed identifiers or keys) is discarded."""
    name = type(exc).__name__
    text = str(exc).lower()
    if name == "AuthenticationError":
        return "provider_auth_failed"
    if name == "PermissionError":
        return "provider_permission_denied"
    if name == "RateLimitError":
        return "rate_limited"
    if name == "APIConnectionError":
        return "provider_timeout" if "timed out" in text or "timeout" in text else "provider_unavailable"
    if name in ("APIError", "ServiceUnavailableError"):
        return "provider_unavailable"
    if name in ("InvalidRequestError", "IdempotencyError"):
        return "invalid_request"
    if name == "SignatureVerificationError":
        return "signature_invalid"
    return "unknown"


class StripeManagedPaymentsProvider:
    """BillingProvider for Stripe Managed Payments. FOUNDATION: every operation beyond reporting its own state fails closed."""

    name = P.PROVIDER_STRIPE_MP
    live = False

    def __init__(self, *, environment: str = "sandbox", store=None, client_factory: Callable[..., Any] | None = None) -> None:
        self.environment = environment
        self._store = store
        self._client_factory = client_factory

    def capabilities(self) -> dict:
        return {"provider": self.name, "live": False, "mode": "sandbox_foundation", "environment": self.environment, "refund": False, "checkout": False,
                "payment_methods": False, "tax": False, "network": False, "managed_payments_required": True, "label": P.STRIPE_MODE_LABEL}

    def refund(self, *, idempotency_key: str, provider_payment_id: str, amount_minor: int, currency: str):
        # Refund handling against Stripe is not built or qualified: refuse deterministically and never return mock success. The framework treats
        # ProviderRejected as permanent (no retry), so a queued refund fails visibly instead of pretending.
        raise ProviderRejected("capability_unavailable")

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutResult:
        """Create ONE hosted Managed Payments subscription Checkout Session (W12.4D-C). No money moves here: the customer pays on Stripe's page.

        Fails closed unless external checkout is authorized: with ``policy.EXTERNAL_CHECKOUT_AUTHORIZED`` False (the code constant, off in this
        release) the adapter refuses UNLESS a test explicitly injected a fake ``client_factory``, so a real Stripe client can never be built for a
        checkout by configuration alone. The parameter set always passes ``require_managed_payments`` (``managed_payments.enabled = true``,
        ``mode = subscription``) so Ask4Mo is never an ordinary merchant, and a rejected/ambiguous Stripe failure is reduced to a bounded category.
        """
        if self._client_factory is None and not P.EXTERNAL_CHECKOUT_AUTHORIZED:
            raise ProviderRejected("checkout_not_authorized")
        if self.environment != "sandbox":
            raise ProviderRejected("live_disabled")
        params: dict = {
            "mode": "subscription",
            "managed_payments": {"enabled": True},
            "line_items": [{"price": request.provider_price_id, "quantity": 1}],
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "client_reference_id": request.client_reference_id,
            "metadata": {"ask4mo_checkout": request.client_reference_id},
        }
        if request.expires_at:
            params["expires_at"] = request.expires_at
        try:
            require_managed_payments(params)
            client = self.client()
            session = client.v1.checkout.sessions.create(params, {"idempotency_key": request.idempotency_key})
        except StripeConfigurationError as exc:
            raise ProviderRejected(exc.category) from None
        except Exception as exc:  # noqa: BLE001 - reduced to a bounded category; the SDK message is discarded
            category = map_stripe_error(exc)
            if category in ("provider_timeout", "provider_unavailable", "rate_limited"):
                raise ProviderRetryable(category) from None
            raise ProviderRejected(category) from None
        sid, url = getattr(session, "id", None), getattr(session, "url", None)
        if not isinstance(sid, str) or not sid or not isinstance(url, str) or not url.startswith("https://"):
            raise ProviderRejected("unknown")
        return CheckoutResult(provider_session_id=sid, url=url, expires_at=getattr(session, "expires_at", None))

    def client(self):
        """A per-call Stripe client for later waves (explicit credentials, sandbox only). Unused by any code path in this wave."""
        store = self._store
        if store is None:
            from src.secret_store import get_secret_store

            store = get_secret_store()
        factory = self._client_factory or build_stripe_client
        return factory(store, self.environment)
