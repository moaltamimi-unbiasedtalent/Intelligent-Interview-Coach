"""Plain typed request/response values for the application boundary.

Inputs are ordinary dataclasses (no Streamlit widgets, no ``st.session_state``,
no UI callbacks) so both the Streamlit UI and a future FastAPI backend can
construct them. Domain result types (``OrchestrationResult``, ``ChatResponse``,
tool results, ``FinalInterviewReport`` …) are reused unchanged — the application
layer does not re-wrap what the domain already models safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CareerChatRequest:
    """A single Career Intelligence chat turn, as plain typed values.

    Mirrors the arguments the Streamlit chat page passed to
    ``CareerIntelligenceService.answer`` — nothing UI-specific.
    """

    query: str
    job_description: str | None = None
    candidate_background: str | None = None
    days_until_interview: int | None = None
    hours_per_week: float | None = None
    company_context: Any | None = None
    model: str | None = None
    retrieval_mode: str | None = None


@dataclass
class ToolCallResult:
    """Safe result of one Career tool invocation.

    ``value`` is the typed domain result (or ``None`` on failure); ``execution``
    is the tool's safe execution summary (already redacted for logging/UI); ``ok``
    and ``error`` describe success. This is the same information the UI showed in
    "Tools used", exposed without any Streamlit dependency.
    """

    value: Any | None
    execution: Any
    ok: bool
    error: str | None = None
