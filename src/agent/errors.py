"""Safe agent-layer errors (messages are always safe to show)."""

from __future__ import annotations

from src.core.errors import SafeError

__all__ = [
    "AgentError",
    "AgentConfigurationError",
    "AgentToolError",
]


class AgentError(SafeError):
    """Base for agent-layer failures crossing the application boundary."""


class AgentConfigurationError(AgentError):
    """The agent cannot run because a required capability isn't configured."""


class AgentToolError(AgentError):
    """A tool could not be validated or executed (raw cause never exposed)."""
