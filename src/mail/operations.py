"""Admin view of transactional-email readiness and delivery diagnostics (W12.4C). Metadata only.

Distinct questions, never collapsed: configured / connection tested / provider ACCEPTED a submission / delivery CONFIRMED. The last
one is never reported because no delivery evidence is collected (no webhook): the honest ceiling is ``provider_accepted``. Nothing
here returns a credential, token, link, recipient or message content, and the live-delivery state is reported as unverified.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from src.mail.sender import BrevoEmailSender, ConsoleEmailSender, MemoryEmailSender, NotConfiguredEmailSender

STATUSES = ("not_configured", "configured_not_tested", "last_test_passed", "provider_accepted", "delivery_failed", "delivery_unknown")


def adapter_name(sender) -> str:
    if isinstance(sender, BrevoEmailSender):
        return "brevo"
    if isinstance(sender, NotConfiguredEmailSender):
        return "not_configured"
    if isinstance(sender, MemoryEmailSender):
        return "memory"
    if isinstance(sender, ConsoleEmailSender):
        return "console"
    return "other"


def build_delivery_status(*, sender, integration: dict, attempts: dict, sender_is_current: bool) -> dict:
    """``integration`` is ``IntegrationService.get('email_brevo')``; ``attempts`` is ``EmailAttemptRepository.summary()``."""
    slot = integration["slots"][0]
    selected = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower() or "unset"
    sender_cfg = bool((os.environ.get("EMAIL_SENDER") or "").strip())
    adapter = adapter_name(sender)
    configured = selected == "brevo" and slot["configured"] and sender_cfg
    health = integration["health"]

    # Restart semantics (W12.4B): the in-process client keeps the credential it was built with.
    if adapter == "brevo":
        restart = not sender_is_current
        reason = "The running client uses an earlier credential; restart the API and the worker." if restart else None
    else:
        restart = configured          # Brevo is configured now, but this process built a different adapter
        reason = "Brevo is configured but this process is not using it; restart the API and the worker." if restart else None

    if health["status"] == "healthy":
        sender_verification = "verified_by_last_test"
    elif health["status"] == "unhealthy" and health.get("category") == "configuration_error":
        sender_verification = "not_verified_by_last_test"
    else:
        sender_verification = "unknown"

    last_attempt, last_failure, last_accepted = attempts["last_attempt"], attempts["last_failure"], attempts["last_accepted"]
    if not configured:
        status = "not_configured"
    elif last_attempt and last_attempt["status"] == "delivery_unknown":
        status = "delivery_unknown"
    elif last_attempt and last_attempt["status"] in ("failed", "not_configured"):
        status = "delivery_failed"
    elif last_accepted:
        status = "provider_accepted"
    elif health["status"] == "healthy":
        status = "last_test_passed"
    else:
        status = "configured_not_tested"

    origin = (os.environ.get("APP_BASE_URL") or "").strip() or (os.environ.get("FRONTEND_ORIGINS") or "").split(",")[0].strip()
    parsed = urlparse(origin) if origin else None
    ready = configured and not restart
    return {
        "status": status,
        "provider_selected": selected,
        "adapter_in_process": adapter,
        "provider_account": {"configured": slot["configured"], "source_kind": slot["source_kind"]},
        "sender_configured": sender_cfg,
        "sender_verification": sender_verification,
        "restart_required": restart,
        "restart_reason": reason,
        "last_test": {"state": {"not_tested": "not_tested", "healthy": "passed", "unhealthy": "failed"}[health["status"]],
                            "last_tested_at": health["last_tested_at"], "category": health["category"]},
        "delivery_confirmation": "not_collected",
        "live_delivery": "unverified",
        "link_origin": {"configured": bool(parsed and parsed.netloc), "https": bool(parsed and parsed.scheme == "https")},
        "identity_pipeline": {"verification": "ready" if ready else "not_ready", "recovery": "ready" if ready else "not_ready"},
        "diagnostics": attempts,
        "last_failure_category": last_failure["failure_category"] if last_failure else None,
        "note": "Provider accepted does not mean delivered. No delivery or bounce events are collected, so delivery is never confirmed here.",
    }
