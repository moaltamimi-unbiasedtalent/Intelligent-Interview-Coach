"""Safe errors for W10.13 step-up. Messages are fixed, user-safe copy: no account detail, no provider hint."""

from __future__ import annotations

from src.application.errors import ApplicationError


class StepUpRequired(ApplicationError):
    """A recent password confirmation is required for this action."""


class StepUpUnavailable(ApplicationError):
    """Step-up cannot be performed for this session (no password credential, or not a server-side session). Fails closed."""


class StepUpFailed(ApplicationError):
    """The confirmation was not accepted (generic: no account enumeration)."""
