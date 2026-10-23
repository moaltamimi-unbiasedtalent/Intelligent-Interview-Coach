"""Single source of truth for reading secrets and settings.

Precedence is **Streamlit secrets → environment variables**, with no default
real keys. Both the Career and Interview config modules delegate their raw
reads here, so the precedence, the tolerant Streamlit access, and the SecretStr
masking live in exactly one place.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import SecretStr

__all__ = [
    "OFFLINE_SWITCH",
    "PROVIDER_CREDENTIAL_NAMES",
    "offline_switch_active",
    "load_dotenv_once",
    "read_streamlit",
    "read_env",
    "read_setting",
    "read_bool",
    "read_float",
    "read_secret",
    "read_environment_setting",
    "set_managed_resolver",
    "read_managed",
]


# 04D (IR-DEMO-KEY). The explicit OFFLINE switch. ``ASK4MO_PROVIDER_MODE=offline`` already makes the HTTP guard (src/demo_live/guard.py) refuse every non-loopback request; it did NOT
# stop a provider key from being DISCOVERED (a working copy's .env, Streamlit secrets, an exported variable), so a keyed working copy still looked "live" and a stray call could be
# attempted. With the switch set, no provider credential is read from ANY source below: not .env, not Streamlit secrets, not the environment, not the Admin-managed store.
OFFLINE_SWITCH = "ASK4MO_PROVIDER_MODE"

# Credentials of the paid or external AI, labour-market and observability providers. Identity, billing, email and storage secrets are NOT in this set: the switch is about
# provider calls, and it must not make an unrelated subsystem look unconfigured.
PROVIDER_CREDENTIAL_NAMES = frozenset({
    "OPENROUTER_API_KEY", "COPILOT_EMBEDDING_API_KEY", "GEMINI_API_KEY", "REALTIME_VOICE_API_KEY",
    "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
})


def offline_switch_active(environ=None) -> bool:
    """True when ``ASK4MO_PROVIDER_MODE`` is ``offline``. Read from the process environment only (never from a file the switch is meant to distrust)."""
    raw = (environ if environ is not None else os.environ).get(OFFLINE_SWITCH)
    return bool(raw) and raw.strip().lower() == "offline"


def _withheld(name: str) -> bool:
    return name in PROVIDER_CREDENTIAL_NAMES and offline_switch_active()


def load_dotenv_once() -> None:
    """Load a local ``.env`` for development, never overriding real env vars. Skipped entirely when the offline switch is set (a ``.env`` may hold a provider key)."""
    if offline_switch_active():
        return
    load_dotenv(override=False)


def read_streamlit(name: str) -> str | None:
    """Read a value from Streamlit secrets, tolerating a no-secrets environment.

    Streamlit raises when no secrets file exists at all — expected in local dev
    and tests — so that is treated as "not configured", never a failure.
    """
    if _withheld(name):
        return None
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def read_env(name: str) -> str | None:
    """Read a value from the environment (local-development fallback)."""
    if _withheld(name):
        return None
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


_managed_resolver = None   # W12.4B: set by the encrypted SecretStore when it is the active backend; None otherwise


def set_managed_resolver(resolver) -> None:
    """Install (or clear) the Admin-managed credential resolver. It receives a setting NAME and returns a
    plaintext value or None; it only ever answers for code-defined credential slots and never raises."""
    global _managed_resolver
    _managed_resolver = resolver


def read_managed(name: str) -> str | None:
    """The Admin-managed credential for ``name`` (W12.4B), or None. Never raises."""
    resolver = _managed_resolver
    if resolver is None or _withheld(name):
        return None
    try:
        return resolver(name) or None
    except Exception:  # noqa: BLE001
        return None


def read_environment_setting(name: str) -> str | None:
    """The deployment-managed value only (Streamlit secrets, then environment). This is the FALLBACK layer."""
    return read_streamlit(name) or read_env(name)


def read_setting(name: str) -> str | None:
    """Precedence (W12.4B): Admin-managed encrypted credential, then Streamlit secrets, then the environment."""
    return read_managed(name) or read_environment_setting(name)


def read_bool(name: str, default: bool = False) -> bool:
    raw = read_setting(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def read_float(name: str, default: float) -> float:
    raw = read_setting(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def read_secret(name: str) -> SecretStr | None:
    """Read a credential as ``SecretStr`` (masked if printed/logged), or None."""
    raw = read_setting(name)
    return SecretStr(raw) if raw else None
