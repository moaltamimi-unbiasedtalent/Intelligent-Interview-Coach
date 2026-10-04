"""Governed AI configuration seam (P10B-W10.7).

The model registry (``models.py``) and the operation policy (``policy.py``) stay the code-defined source of truth. This module is the ONE
narrow seam through which an ACTIVE, evaluated and second-approved configuration (managed in ``src/ai_admin``) may change two things, and
nothing else:

* which APPROVED CATALOGUE model a Fast/Balanced/Advanced profile resolves to (a slug the catalogue defines in code, never a candidate or
  admin supplied string), and
* bounded numeric execution tunables per model-backed operation (max output tokens, timeout, retries).

When no snapshot is installed or the provider returns ``None`` the registry behaves exactly as it did before W10.7 (environment override,
then the code default). The seam performs no database access itself and no provider call; the provider is installed by the application
wiring (``src/ai_admin/resolver.py``) and is always optional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

__all__ = ["GovernedSnapshot", "set_provider", "current", "operation_override", "clear"]


@dataclass(frozen=True)
class GovernedSnapshot:
    """An immutable view of the active configuration for one environment."""

    version_public_id: str
    version: int
    config_hash: str
    environment: str
    profile_slugs: Mapping[str, str]                                  # profile value -> catalogue slug
    operation_overrides: Mapping[str, Mapping[str, float | int]] = field(default_factory=dict)  # operation value -> tunables


_provider: Callable[[], GovernedSnapshot | None] | None = None


def set_provider(provider: Callable[[], GovernedSnapshot | None] | None) -> None:
    """Install (or remove) the snapshot provider. Safe to call repeatedly."""
    global _provider
    _provider = provider


def clear() -> None:
    set_provider(None)


def current() -> GovernedSnapshot | None:
    """The active snapshot, or None. A provider failure NEVER propagates: the registry falls back to code defaults."""
    provider = _provider
    if provider is None:
        return None
    try:
        return provider()
    except Exception:  # noqa: BLE001 - fail closed to code-defined behaviour
        return None


def operation_override(operation_value: str) -> Mapping[str, float | int] | None:
    snap = current()
    if snap is None:
        return None
    return snap.operation_overrides.get(operation_value)
