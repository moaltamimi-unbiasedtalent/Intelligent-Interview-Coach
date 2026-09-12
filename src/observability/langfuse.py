"""Optional Langfuse observability sink — SANITISED events only (P5, extended Phase 7D).

Privacy by construction: this sink NEVER attaches the Langfuse LangChain auto-trace callback
(which would capture prompts, model inputs/outputs and tool arguments). It only emits explicit,
allow-listed operational fields, and every metadata dict additionally passes through the central
:func:`src.observability.sanitizer.safe_metadata` backstop (secrets/PII/URLs/error codes). It is
OFF by default, lazily imported, and best-effort: any SDK/network failure is swallowed so an
Agent run, interview or feedback submission is never affected (§5/§34/§42).
"""

from __future__ import annotations

import logging
from typing import Any

from src.observability.sanitizer import safe_metadata

logger = logging.getLogger(__name__)

__all__ = ["LangfuseObservabilitySink"]


class LangfuseObservabilitySink:
    """Emits sanitised run / tool / HITL / interview / feedback events to Langfuse.

    Construct via :func:`src.observability.build_observability_sink`, which only returns this
    when external observability is explicitly enabled AND credentials + the SDK are present.
    Every method is wrapped so a provider outage cannot break the product.
    """

    def __init__(self, client: Any, *, environment: str | None = None,
                 release: str | None = None) -> None:
        self._client = client  # a langfuse.Langfuse instance (injected/lazily built)
        self._tags = {"environment": environment, "release": release}

    def _meta(self, extra: dict[str, Any]) -> dict[str, Any]:
        """Merge the static environment/release tags with sanitised per-event metadata."""
        merged = {**self._tags, **(extra or {})}
        return safe_metadata(merged)

    # -- lifecycle ------------------------------------------------------------

    def run_started(self, *, run_id: str, profile: str | None = None) -> None:
        self._safe(lambda: self._trace(run_id, {"model_profile": profile, "status": "started"}))

    def tool_event(self, *, run_id: str, tool_name: str, status: str,
                   duration_ms: int | None = None, failure_category: str | None = None,
                   source_count: int | None = None) -> None:
        # Safe metadata only — never tool arguments or output bodies (§17/§38).
        self._safe(lambda: self._observation(
            run_id, name=f"tool:{tool_name}",
            metadata={"tool_name": tool_name, "status": status, "duration_ms": duration_ms,
                      "failure_category": failure_category, "source_count": source_count}))

    def hitl_event(self, *, run_id: str, hitl_type: str, status: str) -> None:
        # Type + status only — never memory/role candidates/human response text (§20/§39).
        self._safe(lambda: self._observation(
            run_id, name="hitl", metadata={"hitl_type": hitl_type, "status": status}))

    def run_completed(self, *, run_id: str, projection: dict[str, Any]) -> None:
        self._safe(lambda: self._trace(run_id, dict(projection)))

    def interview_event(self, *, session_id: str, operation: str, status: str,
                        duration_ms: int | None = None, failure_category: str | None = None,
                        metadata: dict[str, Any] | None = None) -> None:
        # Session id is an opaque server uuid (not user data); NEVER answer/CV/JD text (§22).
        md = {"operation": operation, "status": status, "duration_ms": duration_ms,
              "failure_category": failure_category, **(metadata or {})}
        self._safe(lambda: self._observation(session_id, name=f"interview:{operation}",
                                             metadata=md, trace_name="interview_session"))

    def retrieval_event(self, *, run_id: str | None = None,
                        metadata: dict[str, Any] | None = None) -> None:
        # Booleans/counts/labels only — never passages, chunks or vectors (§18).
        self._safe(lambda: self._observation(run_id or "retrieval", name="retrieval",
                                             metadata=dict(metadata or {})))

    def feedback_event(self, *, surface: str, rating: str,
                       run_id: str | None = None, category: str | None = None) -> None:
        # Surface + rating (+ safe category) only — never the comment or the rated content (§26).
        self._safe(lambda: self._event(name="feedback",
                                       metadata={"surface": surface, "rating": rating,
                                                 "category": category}))
        # §27 — attach a Langfuse score correlated to the run when a safe trace id exists.
        if run_id:
            value = 1.0 if rating == "helpful" else 0.0
            self._safe(lambda: self._score(run_id, name="user_feedback", value=value,
                                           comment=None))

    # -- flush / shutdown (§32) ----------------------------------------------

    def flush(self) -> None:
        self._safe(lambda: self._maybe_call("flush"))

    def shutdown(self) -> None:
        self._safe(lambda: self._maybe_call("shutdown"))

    # -- best-effort SDK plumbing (defensive across SDK versions) -------------

    def _trace(self, run_id: str, metadata: dict[str, Any]) -> None:
        trace = getattr(self._client, "trace", None)
        if callable(trace):
            trace(id=run_id, name="agent_run", metadata=self._meta(metadata))

    def _observation(self, run_id: str, *, name: str, metadata: dict[str, Any],
                     trace_name: str = "agent_run") -> None:
        event = getattr(self._client, "event", None)
        if callable(event):
            event(trace_id=run_id, name=name, metadata=self._meta(metadata))

    def _event(self, *, name: str, metadata: dict[str, Any]) -> None:
        event = getattr(self._client, "event", None)
        if callable(event):
            event(name=name, metadata=self._meta(metadata))

    def _score(self, run_id: str, *, name: str, value: float, comment: str | None) -> None:
        score = getattr(self._client, "score", None)
        if callable(score):
            score(trace_id=run_id, name=name, value=value)

    def _maybe_call(self, method: str) -> None:
        fn = getattr(self._client, method, None)
        if callable(fn):
            fn()

    @staticmethod
    def _safe(fn) -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001 - telemetry is non-critical; never raise. No exception
            # string is logged (it could carry a network payload / credential).
            logger.warning("External observability event dropped (non-critical).")
