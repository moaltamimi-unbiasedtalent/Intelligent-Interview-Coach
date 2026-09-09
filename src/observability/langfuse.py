"""Optional Langfuse observability sink — SANITISED events only (P5).

Privacy by construction: this sink NEVER attaches the Langfuse LangChain auto-trace
callback (which would capture prompts, model inputs/outputs and tool arguments). It only
emits the explicit, allow-listed operational fields it is handed (safe projections built
in :mod:`src.observability.base`). It is OFF by default, lazily imports the vendor SDK,
and is best-effort: any SDK/network failure is swallowed so an Agent run, interview or
feedback submission is never affected (§34, §42).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["LangfuseObservabilitySink"]


class LangfuseObservabilitySink:
    """Emits sanitised run/tool/HITL/feedback events to Langfuse.

    Construct via :func:`src.observability.build_observability_sink`, which only returns
    this when external observability is explicitly enabled AND credentials + the SDK are
    present. Every method is wrapped so a provider outage cannot break the product.
    """

    def __init__(self, client: Any) -> None:
        self._client = client  # a langfuse.Langfuse instance (injected/lazily built)

    # -- lifecycle ------------------------------------------------------------

    def run_started(self, *, run_id: str, profile: str | None = None) -> None:
        self._safe(lambda: self._trace(run_id, {"model_profile": profile, "status": "started"}))

    def tool_event(self, *, run_id: str, tool_name: str, status: str,
                   duration_ms: int | None = None, failure_category: str | None = None,
                   source_count: int | None = None) -> None:
        # Safe metadata only — never tool arguments or output bodies (§38).
        self._safe(lambda: self._observation(
            run_id, name=f"tool:{tool_name}",
            metadata={"tool_name": tool_name, "status": status, "duration_ms": duration_ms,
                      "failure_category": failure_category, "source_count": source_count}))

    def hitl_event(self, *, run_id: str, hitl_type: str, status: str) -> None:
        # Type + status only — never memory/role candidates/human response text (§39).
        self._safe(lambda: self._observation(
            run_id, name="hitl", metadata={"hitl_type": hitl_type, "status": status}))

    def run_completed(self, *, run_id: str, projection: dict[str, Any]) -> None:
        self._safe(lambda: self._trace(run_id, dict(projection)))

    def feedback_event(self, *, surface: str, rating: str) -> None:
        # Surface + rating only — never the comment or the rated content (§32).
        self._safe(lambda: self._event(name="feedback",
                                       metadata={"surface": surface, "rating": rating}))

    # -- best-effort SDK plumbing (defensive across SDK versions) -------------

    def _trace(self, run_id: str, metadata: dict[str, Any]) -> None:
        trace = getattr(self._client, "trace", None)
        if callable(trace):
            trace(id=run_id, name="agent_run", metadata=_clean(metadata))

    def _observation(self, run_id: str, *, name: str, metadata: dict[str, Any]) -> None:
        event = getattr(self._client, "event", None)
        if callable(event):
            event(trace_id=run_id, name=name, metadata=_clean(metadata))

    def _event(self, *, name: str, metadata: dict[str, Any]) -> None:
        event = getattr(self._client, "event", None)
        if callable(event):
            event(name=name, metadata=_clean(metadata))

    @staticmethod
    def _safe(fn) -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001 - telemetry is non-critical; never raise. No
            # exception string is logged (it could carry a network payload/credential).
            logger.warning("External observability event dropped (non-critical).")


def _clean(metadata: dict[str, Any]) -> dict[str, Any]:
    """Drop None values so only known, present safe fields are sent."""
    return {k: v for k, v in metadata.items() if v is not None}
