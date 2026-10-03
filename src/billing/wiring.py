"""Construction helpers (P10B-W10.5)."""

from __future__ import annotations

from src.billing.runtime import BillingRuntime
from src.billing.provider import build_provider, safe_mode
from src.billing.service import BillingService


def build_billing_service(session_factory, jobs=None, *, env: str | None = None, provider_setting: str | None = None) -> BillingService:
    mode = safe_mode(env, provider_setting)
    return BillingService(session_factory, provider=build_provider(mode), mode=mode, jobs=jobs)


def build_billing_runtime(session_factory, jobs=None) -> BillingRuntime:
    mode = safe_mode()
    return BillingRuntime(session_factory=session_factory, provider=build_provider(mode), mode=mode, jobs=jobs)
