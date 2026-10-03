"""BillingProvider interface, MockBillingAdapter and the production guard (P10B-W10.5).

MOCK BILLING: NOT LIVE BILLING. The Capstone has exactly one provider: the mock adapter. It performs no network call, moves no money,
handles no card, calculates no tax and creates no external invoice. A future hosted-checkout adapter would implement the same small
interface (and own card data, tax and payment authorisation); none is built here. The guard fails closed: the mock adapter can never be
enabled in a production/live environment, and nothing in the API or UI may call it live.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Protocol

from src.billing import policy as P

# Environments in which the MOCK adapter may run (mirrors src.api.dependencies.DEV_ENVS; pinned by a test).
MOCK_ALLOWED_ENVS = ("development", "dev", "test", "testing", "local")
PROVIDER_SETTING = "BILLING_PROVIDER"        # "disabled" (default) | "mock"


class BillingConfigurationError(RuntimeError):
    """A billing configuration that must not run (for example the mock adapter in a production environment)."""


class ProviderRetryable(Exception):
    """A transient provider failure (the framework retries)."""


class ProviderRejected(Exception):
    """A deterministic refusal (never retried)."""


@dataclass(frozen=True)
class ProviderRefundResult:
    provider_refund_id: str
    amount_minor: int
    currency: str


class BillingProvider(Protocol):
    """Deliberately small: only what W10.5 needs. No checkout, payment-method collection, tokenisation, tax or portal."""

    name: str
    live: bool

    def capabilities(self) -> dict: ...

    def refund(self, *, idempotency_key: str, provider_payment_id: str, amount_minor: int, currency: str) -> ProviderRefundResult: ...


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class MockBillingAdapter:
    """Deterministic, offline, labelled MOCK. ``calls`` records every refund call so tests can prove idempotency."""

    name = P.PROVIDER_MOCK
    live = False

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_next: list[str] = []        # test fixture: "retryable" | "rejected"

    def capabilities(self) -> dict:
        return {"provider": self.name, "live": False, "mode": "mock", "refund": True, "checkout": False, "payment_methods": False,
                "tax": False, "network": False, "label": P.MODE_LABEL}

    def refund(self, *, idempotency_key: str, provider_payment_id: str, amount_minor: int, currency: str) -> ProviderRefundResult:
        self.calls.append(idempotency_key)
        if self.fail_next:
            kind = self.fail_next.pop(0)
            raise ProviderRetryable("mock provider unavailable") if kind == "retryable" else ProviderRejected("mock provider rejected")
        # The SAME idempotency key always yields the SAME provider refund id (a real provider would also dedupe on it).
        return ProviderRefundResult(provider_refund_id="mock_re_" + _digest("refund", idempotency_key)[:20], amount_minor=amount_minor, currency=currency)

    # ---- deterministic fixture helpers: they only BUILD normalised events; ingestion goes through BillingService ----
    @staticmethod
    def event(kind: str, ref: str, **data: Any) -> dict:
        return {"provider": P.PROVIDER_MOCK, "provider_event_id": "mock_evt_" + _digest(kind, ref)[:20], "event_type": kind, "data": data}


@dataclass(frozen=True)
class BillingMode:
    provider: str | None          # "mock" or None (disabled)
    enabled: bool
    live: bool                    # always False: no live provider exists
    label: str
    configuration_error: str | None = None

    def as_dict(self) -> dict:
        return {"provider": self.provider or "none", "enabled": self.enabled, "live": False, "mode": "mock" if self.enabled else "disabled",
                "label": self.label, "configuration_error": self.configuration_error, "checkout": False,
                "note": "No live payments are processed. No checkout, payment method or tax engine exists."}


def resolve_mode(env: str | None = None, provider_setting: str | None = None) -> BillingMode:
    """Fail closed. Raises BillingConfigurationError for mock-in-production and for any provider other than disabled/mock."""
    env = (env if env is not None else os.environ.get("API_ENV") or "development").strip().lower()
    setting = (provider_setting if provider_setting is not None else os.environ.get(PROVIDER_SETTING) or "disabled").strip().lower()
    if setting in ("", "disabled", "none"):
        return BillingMode(None, False, False, "BILLING DISABLED")
    if setting != P.PROVIDER_MOCK:
        raise BillingConfigurationError("Only the mock billing provider exists. No live billing provider is available.")
    if env not in MOCK_ALLOWED_ENVS:
        raise BillingConfigurationError("The mock billing adapter cannot be enabled in a production or live environment.")
    return BillingMode(P.PROVIDER_MOCK, True, False, P.MODE_LABEL)


def safe_mode(env: str | None = None, provider_setting: str | None = None) -> BillingMode:
    """Never raises: a rejected configuration becomes DISABLED with the reason, and is never presented as live."""
    try:
        return resolve_mode(env, provider_setting)
    except BillingConfigurationError as exc:
        return BillingMode(None, False, False, "BILLING DISABLED", str(exc))


def build_provider(mode: BillingMode) -> MockBillingAdapter | None:
    return MockBillingAdapter() if mode.enabled and mode.provider == P.PROVIDER_MOCK else None
