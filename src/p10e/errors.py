"""Stable refusal types shared by the P10E guard, ledger and HTTP guard (no dependencies)."""

from __future__ import annotations


class LiveRunRefused(Exception):
    """A paid call was refused. ``reason`` is a stable machine-readable code; the message never contains a credential."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class BudgetExceeded(LiveRunRefused):
    pass
