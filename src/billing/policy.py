"""Code-defined billing vocabulary (P10B-W10.5)."""

from __future__ import annotations

MODE_LABEL = "MOCK BILLING - NOT LIVE BILLING"
PROVIDER_MOCK = "mock"
PROVIDER_STRIPE_MP = "stripe_managed_payments"      # W12.4D-B: owner-selected provider (Stripe Managed Payments, merchant of record). FOUNDATION ONLY.
# PROVIDERS = providers whose EVENTS and mirrored rows the billing domain accepts today. It stays ("mock",): the billing tables pin the provider
# (`ck_bc_provider`) and no Stripe event ingestion exists until W12.4D-D, so a Stripe event is refused (fail closed), never half-stored.
PROVIDERS = (PROVIDER_MOCK,)
# SELECTABLE_PROVIDERS = the code-defined allow-list of values `BILLING_PROVIDER` may take (besides "disabled"). Anything else fails closed.
SELECTABLE_PROVIDERS = (PROVIDER_MOCK, PROVIDER_STRIPE_MP)
STRIPE_ENVIRONMENTS = ("sandbox", "live")
# Live billing is a CODE constant, not a setting: it cannot be switched on by configuration, startup or Admin in this release.
LIVE_BILLING_ENABLED = False
# W12.4D-C: external (Stripe-facing) checkout is NOT authorized. Like LIVE_BILLING_ENABLED this is a code constant, so no setting, startup or Admin action
# can turn it on: the adapter refuses to use a real Stripe client for a Checkout Session while it is False. Tests inject a fake client explicitly.
EXTERNAL_CHECKOUT_AUTHORIZED = False
CHECKOUT_SESSION_TTL_SECONDS = 30 * 60        # Stripe requires a Checkout Session to live 30 minutes to 24 hours; the shortest is used
CHECKOUT_IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"
PURCHASABLE_PLAN_CODES = ("premium",)          # Basic is free and never purchasable
STRIPE_MODE_LABEL = "STRIPE MANAGED PAYMENTS - SANDBOX FOUNDATION - NO CHECKOUT - LIVE BILLING DISABLED"
# Reviewed Stripe contract (W12.4D-B): the SDK pins this API version; Managed Payments needs 2025-03-31.basil or later.
STRIPE_API_VERSION = "2026-09-30.endive"
STRIPE_MIN_API_VERSION_FOR_MANAGED_PAYMENTS = "2025-03-31.basil"
# Readiness vocabulary (bounded; "healthy" and "merchant of record approved" are deliberately not states).
READINESS_STATES = ("not_configured", "configured_not_tested", "sandbox_access_unverified", "configuration_error", "provider_unavailable",
                    "eligibility_not_confirmed", "live_disabled")
INTERVALS = ("month", "year")
VISIBILITIES = ("public", "private", "internal")     # catalogue metadata only: "public" does NOT mean purchasable
TERMS_STATES = ("active", "retired")
MAX_AMOUNT_MINOR = 100_000_000                       # bounded sanity limit; integer minor units only, never floats
MAX_TRIAL_DAYS = 365
APPROVAL_ACTIONS = ("price_change", "refund")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "executed", "failed", "cancelled")
PROVIDER_SUB_STATES = ("trialing", "active", "past_due", "cancelled")
INVOICE_STATES = ("open", "paid", "past_due", "void")
PAYMENT_STATUSES = ("pending", "succeeded", "failed")
PAYMENT_FAILURE_CATEGORIES = ("declined", "insufficient_funds", "expired", "processing_error", "unknown")
REFUND_STATES = ("pending", "succeeded", "failed")
CUSTOMER_STATES = ("active", "closed")
EVENT_TYPES = ("customer_created", "subscription_updated", "invoice_opened", "invoice_paid", "payment_succeeded", "payment_failed")
EVENT_STATES = ("received", "processed", "failed")
JOB_PROCESS_EVENT = "billing_process_event"
JOB_REFUND = "billing_refund"
MAX_REASON = 300
