"""Provider-neutral observability interface + a SAFE trace projection (P5).

Core Agent code never depends on any vendor SDK — it talks to an
:class:`ObservabilitySink`. The default is a no-op (external network OFF). Any external
sink receives ONLY the explicit, sanitised operational fields produced by
:func:`safe_trace_projection` — never prompts, candidate text, JD/CV, memory summaries,
retrieved chunks, interview answers, evaluation/report prose, the system prompt, tool
arguments or tool output bodies, and never ``dict(state)``.

Privacy is a hard gate: everything here is allow-listed. Unknown usage stays ``None``
(never coerced to 0). Telemetry is best-effort and NEVER fails an Agent run, an
interview or a feedback submission.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["ObservabilitySink", "safe_trace_projection", "safe_tool_events", "safe_hitl_event"]


@runtime_checkable
class ObservabilitySink(Protocol):
    """The only observability surface Agent/feedback code depends on."""

    def run_started(self, *, run_id: str, profile: str | None = None) -> None: ...

    def tool_event(self, *, run_id: str, tool_name: str, status: str,
                   duration_ms: int | None = None, failure_category: str | None = None,
                   source_count: int | None = None) -> None: ...

    def hitl_event(self, *, run_id: str, hitl_type: str, status: str) -> None: ...

    def run_completed(self, *, run_id: str, projection: dict[str, Any]) -> None: ...

    def feedback_event(self, *, surface: str, rating: str) -> None: ...


def _usage(result: Any) -> dict[str, Any]:
    u = getattr(result, "usage", None)
    return u if isinstance(u, dict) else {}


def safe_trace_projection(result: Any) -> dict[str, Any]:
    """Build the ONLY dict that may leave the process for a completed run.

    Every field is an explicit, safe scalar/label derived from the already-safe
    ``AgentRunResult`` — no raw state, no content. Unknown usage is preserved as
    ``None`` (never 0). See §37.
    """
    usage = _usage(result)
    journey = getattr(result, "journey", None) or {}
    handoff = getattr(result, "handoff_summary", None)

    def stage(name: str) -> str | None:
        s = journey.get(name) if isinstance(journey, dict) else None
        return s.get("status") if isinstance(s, dict) else None

    return {
        "run_id": getattr(result, "run_id", None),
        "status": getattr(result, "status", None),
        "model_profile": getattr(result, "profile", None),
        "step_count": getattr(result, "step_count", None),
        "turn_step_count": getattr(result, "turn_step_count", None),
        "retrieval_used": bool(getattr(result, "retrieval_used", False)),
        "source_count": len(getattr(result, "sources", []) or []),
        "citation_count": len(getattr(result, "citations", []) or []),
        "memory_count": getattr(result, "memory_count", 0),
        "agent_model_calls": usage.get("agent_model_calls"),
        "tool_model_calls": usage.get("tool_model_calls"),
        "model_calls": usage.get("model_calls"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "estimated_cost_usd": usage.get("estimated_cost_usd"),
        "usage_complete": usage.get("usage_complete"),
        "latency_ms": getattr(result, "latency_ms", None),
        "cache_hits": getattr(result, "cache_hits", 0),
        "cache_misses": getattr(result, "cache_misses", 0),
        "journey_understand": stage("understand"),
        "journey_prepare": stage("prepare"),
        "journey_practise": stage("practise"),
        "handoff_prepared": handoff is not None,
        "handoff_approved": bool(getattr(result, "handoff_approved", False)),
    }


def safe_tool_events(result: Any) -> list[dict[str, Any]]:
    """Safe per-tool metadata from the run's tool history (name/status/category only —
    never tool arguments or output body)."""
    events: list[dict[str, Any]] = []
    for call in getattr(result, "tool_calls", []) or []:
        if not isinstance(call, dict):
            continue
        events.append({
            "tool_name": call.get("tool"),
            "status": call.get("status"),
            "failure_category": call.get("category"),
        })
    return events


def safe_hitl_event(result: Any) -> dict[str, Any] | None:
    """Safe HITL descriptor (type + status only — never candidate/role/response text)."""
    pending = getattr(result, "pending_action", None)
    if isinstance(pending, dict) and pending.get("type"):
        return {"hitl_type": pending.get("type"), "status": "requested"}
    return None
