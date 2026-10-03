"""Code-defined billing vocabulary (P10B-W10.5)."""

from __future__ import annotations

MODE_LABEL = "MOCK BILLING - NOT LIVE BILLING"
PROVIDER_MOCK = "mock"
PROVIDERS = (PROVIDER_MOCK,)            # the Capstone has exactly one provider; there is no live adapter
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
