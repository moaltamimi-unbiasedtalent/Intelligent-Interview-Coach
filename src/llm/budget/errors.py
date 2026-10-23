"""Refusal type of the AI budget governor."""

from __future__ import annotations


class BudgetError(Exception):
    """A provider call or paid run was refused. ``reason`` is a stable machine code. The message never carries a prompt, a key, a marker value or provider text."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
