"""Construction helpers (P10B-W10.5)."""

from __future__ import annotations

from src.billing import policy as P
from src.billing.runtime import BillingRuntime
from src.billing.provider import build_provider, safe_mode
from src.billing.service import BillingService


def build_billing_service(session_factory, jobs=None, *, env: str | None = None, provider_setting: str | None = None) -> BillingService:
    mode = safe_mode(env, provider_setting)
    return BillingService(session_factory, provider=build_provider(mode), mode=mode, jobs=jobs)


def build_provider_events(session_factory, mode=None):
    """The provider-event service as the RUNNING system uses it: a Null provider-state reader (every read is "not enabled") and the UNAPPROVED
    entitlement policy, so no paid entitlement can be granted or revoked until a reviewed release supplies both."""
    from src.auth_repository import AuditRepository
    from src.billing.entitlement_bridge import runtime_policy
    from src.billing.provider_state import build_runtime_reader
    from src.billing.reconcile import ProviderEventService

    mode = mode or safe_mode()
    env = mode.environment if mode.provider == P.PROVIDER_STRIPE_MP else None
    return ProviderEventService(session_factory, environment=env or "sandbox", reader=build_runtime_reader(), policy=runtime_policy(),
                                audit=AuditRepository(session_factory))


def build_billing_runtime(session_factory, jobs=None) -> BillingRuntime:
    mode = safe_mode()
    return BillingRuntime(session_factory=session_factory, provider=build_provider(mode), mode=mode, jobs=jobs,
                          provider_events=build_provider_events(session_factory, mode))
