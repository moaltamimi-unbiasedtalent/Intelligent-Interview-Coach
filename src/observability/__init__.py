"""Provider-neutral agent observability (P5).

Default is a no-op with NO external network. An external sink (Langfuse) is returned
ONLY when explicitly enabled AND its SDK + credentials are present, and even then it
emits only sanitised operational fields (see :mod:`src.observability.base`).
"""

from __future__ import annotations

import logging
import os

from src.observability.base import (
    ObservabilitySink,
    safe_hitl_event,
    safe_tool_events,
    safe_trace_projection,
)
from src.observability.noop import NoOpObservabilitySink

logger = logging.getLogger(__name__)

__all__ = [
    "ObservabilitySink",
    "NoOpObservabilitySink",
    "build_observability_sink",
    "safe_trace_projection",
    "safe_tool_events",
    "safe_hitl_event",
]

_ENABLED_ENV = "AGENT_EXTERNAL_OBSERVABILITY_ENABLED"


def _enabled() -> bool:
    return os.environ.get(_ENABLED_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def build_observability_sink() -> ObservabilitySink:
    """Return the configured sink. NoOp unless external observability is explicitly
    enabled AND the Langfuse SDK + credentials are available. Never raises — any setup
    problem degrades to NoOp (telemetry is non-critical)."""
    if not _enabled():
        return NoOpObservabilitySink()
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        logger.warning("External observability enabled but Langfuse credentials are "
                       "missing; using the no-op sink.")
        return NoOpObservabilitySink()
    try:
        from langfuse import Langfuse  # optional dependency, lazily imported

        from src.observability.langfuse import LangfuseObservabilitySink

        host = os.environ.get("LANGFUSE_HOST", "").strip() or None
        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        return LangfuseObservabilitySink(client)
    except Exception:  # noqa: BLE001 - any import/config issue → safe no-op
        logger.warning("Langfuse observability unavailable; using the no-op sink.")
        return NoOpObservabilitySink()
