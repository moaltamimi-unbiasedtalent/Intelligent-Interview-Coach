"""Safe agent-layer errors (messages are always safe to show)."""

from __future__ import annotations

from src.core.errors import SafeError

__all__ = [
    "AgentError",
    "AgentConfigurationError",
    "AgentToolError",
    "TOOL_FAILURE_MISSING_PREREQUISITE",
    "TOOL_FAILURE_INVALID_ARGUMENTS",
    "TOOL_FAILURE_EXECUTION_FAILED",
]


# Coarse, safe failure categories surfaced to the Inspector so a reader can tell
# WHY a tool call failed without ever exposing raw arguments, content or the
# underlying exception. These are the only permitted values.
TOOL_FAILURE_MISSING_PREREQUISITE = "missing_prerequisite"  # a required prior result/input was absent
TOOL_FAILURE_INVALID_ARGUMENTS = "invalid_arguments"        # arguments failed validation
TOOL_FAILURE_EXECUTION_FAILED = "execution_failed"          # the underlying operation did not produce a result


class AgentError(SafeError):
    """Base for agent-layer failures crossing the application boundary."""


class AgentConfigurationError(AgentError):
    """The agent cannot run because a required capability isn't configured."""


class AgentToolError(AgentError):
    """A tool could not be validated or executed (raw cause never exposed).

    ``category`` is one of the ``TOOL_FAILURE_*`` constants — a safe, coarse label for
    the Inspector. It never carries arguments, content or the underlying error.
    """

    def __init__(self, user_message: str, *, detail: str | None = None,
                 category: str | None = None) -> None:
        super().__init__(user_message, detail=detail)
        self.category = category
