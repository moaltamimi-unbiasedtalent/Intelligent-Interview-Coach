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


def load_dotenv_once() -> None:
    """Load a local ``.env`` for development, never overriding real env vars."""
    load_dotenv(override=False)


def read_streamlit(name: str) -> str | None:
    """Read a value from Streamlit secrets, tolerating a no-secrets environment.

    Streamlit raises when no secrets file exists at all — expected in local dev
    and tests — so that is treated as "not configured", never a failure.
    """
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
    if resolver is None:
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
