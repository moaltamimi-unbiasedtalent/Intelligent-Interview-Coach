"""Operator pause switch for costly/external capabilities (Capstone P8, §21).

A small, bounded, server-authoritative registry that lets an operator temporarily PAUSE a
costly or externally-dependent capability (e.g. during a provider incident or a cost spike)
without a deploy. It is intentionally NOT a general feature-management system — only a fixed
allow-list of capabilities can be paused.

Precedence: a capability is unavailable if it is either not configured/enabled at all OR
paused here. Pausing never deletes data and never affects security/privacy/data-rights
surfaces. State is process-local (seeded from ``PAUSED_CAPABILITIES`` env at boot); a
multi-replica deployment should drive it from shared config/DB — documented, not faked.
"""

from __future__ import annotations

import os
import threading

__all__ = [
    "PAUSABLE_CAPABILITIES",
    "PauseRegistry",
    "get_pause_registry",
    "reset_pause_registry",
    "is_paused",
]

# The FIXED set of capabilities an operator may pause. Bounded on purpose (§21).
PAUSABLE_CAPABILITIES: tuple[str, ...] = (
    "realtime_voice",       # P7.5 realtime session creation
    "current_market",       # external market research (Adzuna / web)
    "ocr",                  # document OCR (potentially costly)
    "agent",                # Mo / agent LLM runs
    "public_registration",  # open verified-email registration
)


class PauseRegistry:
    """Thread-safe set of currently-paused capabilities."""

    def __init__(self, initial: set[str] | None = None) -> None:
        self._paused: set[str] = set(initial or set())
        self._lock = threading.Lock()

    def is_paused(self, capability: str) -> bool:
        with self._lock:
            return capability in self._paused

    def pause(self, capability: str) -> None:
        if capability not in PAUSABLE_CAPABILITIES:
            raise ValueError(f"unknown pausable capability: {capability}")
        with self._lock:
            self._paused.add(capability)

    def resume(self, capability: str) -> None:
        if capability not in PAUSABLE_CAPABILITIES:
            raise ValueError(f"unknown pausable capability: {capability}")
        with self._lock:
            self._paused.discard(capability)

    def set(self, capability: str, paused: bool) -> None:
        (self.pause if paused else self.resume)(capability)

    def snapshot(self) -> dict[str, bool]:
        """{capability: paused?} for every pausable capability (stable order)."""
        with self._lock:
            return {c: (c in self._paused) for c in PAUSABLE_CAPABILITIES}


def _seed_from_env() -> set[str]:
    raw = os.environ.get("PAUSED_CAPABILITIES", "") or ""
    wanted = {c.strip() for c in raw.split(",") if c.strip()}
    return {c for c in wanted if c in PAUSABLE_CAPABILITIES}


_registry: PauseRegistry | None = None


def get_pause_registry() -> PauseRegistry:
    global _registry
    if _registry is None:
        _registry = PauseRegistry(_seed_from_env())
    return _registry


def reset_pause_registry(registry: PauseRegistry | None = None) -> None:
    """Test seam / boot reset: reseed from env (or install a supplied registry)."""
    global _registry
    _registry = registry if registry is not None else PauseRegistry(_seed_from_env())


def is_paused(capability: str) -> bool:
    return get_pause_registry().is_paused(capability)
