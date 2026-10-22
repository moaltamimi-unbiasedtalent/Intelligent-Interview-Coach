"""The ONE safe answer to "can this stack reach a real AI provider?" (04D, DEMO-02).

A keyless review stack and the live stack used to look identical in the UI, and a candidate who pressed Start Interview on the keyless one saw a generic
"temporarily unavailable" message. The mode below is what both the Candidate and Admin surfaces show, so a keyless or offline stack can never masquerade as live.

* ``live``           : a provider credential is configured and the offline switch is NOT set. A call WOULD reach the provider. This is configuration, not health: it never
                       means the provider is reachable, funded or qualified (health is "not tested").
* ``offline``        : ``ASK4MO_PROVIDER_MODE=offline``. No provider credential is read from any source and the HTTP guard refuses every non-loopback request. Any AI answer on
                       such a stack comes from a test double or fixture, never from a live model.
* ``not_configured`` : no provider credential is configured and nothing is offline: AI features cannot run.
* ``unknown``        : the configuration could not be read. Never reported as live.

Only a fixed vocabulary leaves this module: no key, prefix, suffix, length, URL or model id.
"""

from __future__ import annotations

from typing import Mapping

__all__ = ["MODE_LIVE", "MODE_OFFLINE", "MODE_NOT_CONFIGURED", "MODE_UNKNOWN", "PROVIDER_MODES", "resolve_provider_mode", "provider_credential_configured"]

MODE_LIVE = "live"
MODE_OFFLINE = "offline"
MODE_NOT_CONFIGURED = "not_configured"
MODE_UNKNOWN = "unknown"
PROVIDER_MODES = (MODE_LIVE, MODE_OFFLINE, MODE_NOT_CONFIGURED, MODE_UNKNOWN)


def provider_credential_configured() -> bool:
    """Whether an OpenRouter credential is configured by ANY layer (Admin-managed, Streamlit secrets, environment). False under the offline switch."""
    from src.core import secrets

    return bool(secrets.read_setting("OPENROUTER_API_KEY"))


def resolve_provider_mode(configured: bool | None = None, environ: Mapping[str, str] | None = None) -> str:
    """``configured`` lets a caller that already holds the cached app config avoid a second read; None reads the layers now."""
    from src.core import secrets

    if secrets.offline_switch_active(environ):
        return MODE_OFFLINE
    try:
        has_key = provider_credential_configured() if configured is None else bool(configured)
    except Exception:  # noqa: BLE001 - an unreadable configuration is unknown, never "live"
        return MODE_UNKNOWN
    return MODE_LIVE if has_key else MODE_NOT_CONFIGURED
