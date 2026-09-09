"""The default observability sink: does nothing, makes no network call (P5)."""

from __future__ import annotations

from typing import Any

__all__ = ["NoOpObservabilitySink"]


class NoOpObservabilitySink:
    """No-op :class:`~src.observability.base.ObservabilitySink`.

    Every method is a safe no-op — external observability is OFF by default, so the
    Agent, interview and feedback paths run with zero external dependency or latency.
    """

    def run_started(self, *, run_id: str, profile: str | None = None) -> None:
        return None

    def tool_event(self, *, run_id: str, tool_name: str, status: str,
                   duration_ms: int | None = None, failure_category: str | None = None,
                   source_count: int | None = None) -> None:
        return None

    def hitl_event(self, *, run_id: str, hitl_type: str, status: str) -> None:
        return None

    def run_completed(self, *, run_id: str, projection: dict[str, Any]) -> None:
        return None

    def feedback_event(self, *, surface: str, rating: str) -> None:
        return None
