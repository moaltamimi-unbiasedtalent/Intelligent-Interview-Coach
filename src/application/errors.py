"""Safe application-layer errors for Intelligent Interview Coach.

These are the errors the application layer (``src/application``) may raise across
its boundary. They are deliberately few and build on the existing
:class:`src.core.errors.SafeError`, whose message is guaranteed safe to show a
user — no secrets, DB URLs, SQL, credentials or stack traces.

Streamlit maps these to existing user-friendly messages today; a future FastAPI
backend will map the same classes to HTTP status codes. No new error framework is
introduced — this is a small, explicit vocabulary shared by both frontends.
"""

from __future__ import annotations

from src.core.errors import ConfigError, InterviewOSError, SafeError

__all__ = [
    "InterviewOSError",
    "SafeError",
    "ConfigError",
    "ApplicationError",
    "ValidationError",
    "ConfigurationError",
    "UnavailableServiceError",
    "PersistenceError",
    "ConflictError",
]


class ApplicationError(SafeError):
    """Base for errors crossing the application boundary (message is user-safe)."""


class ValidationError(ApplicationError):
    """The caller supplied invalid input (e.g. a missing/empty target role)."""


class ConfigurationError(ApplicationError, ConfigError):
    """A required capability is not configured (e.g. no model API key)."""


class UnavailableServiceError(ApplicationError):
    """A downstream service failed in a way the caller cannot fix (retry later)."""


class PersistenceError(ApplicationError):
    """Saving or loading persisted data failed; the raw cause is never exposed."""


class ConflictError(ApplicationError):
    """The resource changed concurrently (e.g. another tab/worker), or an operation
    is already in progress; the caller should reload the latest state and retry."""
