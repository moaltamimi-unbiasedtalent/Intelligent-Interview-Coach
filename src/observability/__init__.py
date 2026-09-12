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
    safe_retrieval_metadata,
    safe_tool_events,
    safe_trace_projection,
)
from src.observability.config import ObservabilityConfig, load_config
from src.observability.noop import NoOpObservabilitySink
from src.observability.sanitizer import error_category, safe_metadata

logger = logging.getLogger(__name__)

__all__ = [
    "ObservabilitySink",
    "NoOpObservabilitySink",
    "ObservabilityConfig",
    "build_observability_sink",
    "load_config",
    "safe_trace_projection",
    "safe_tool_events",
    "safe_hitl_event",
    "safe_retrieval_metadata",
    "safe_metadata",
    "error_category",
]


def build_observability_sink(config: ObservabilityConfig | None = None) -> ObservabilitySink:
    """Return the configured sink. NoOp unless external observability is explicitly enabled
    AND the Langfuse SDK + credentials are available. Never raises — any setup problem
    degrades to NoOp (telemetry is non-critical, §5/§36). The Langfuse client is created with
    the resolved environment / release / sample-rate settings (§28/§29/§30)."""
    cfg = config or load_config()
    if not cfg.enabled:
        return NoOpObservabilitySink()
    if not cfg.credentials_present:
        logger.warning("External observability enabled but Langfuse credentials are "
                       "missing; using the no-op sink.")
        return NoOpObservabilitySink()
    try:
        from langfuse import Langfuse  # optional dependency, lazily imported

        from src.observability.langfuse import LangfuseObservabilitySink

        client = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip(),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY", "").strip(),
            host=cfg.host,
            release=cfg.release,
            environment=cfg.environment,
            sample_rate=cfg.sample_rate,
            timeout=int(cfg.flush_timeout_seconds) or None,
        )
        return LangfuseObservabilitySink(client, environment=cfg.environment,
                                         release=cfg.release)
    except Exception:  # noqa: BLE001 - any import/config issue → safe no-op
        logger.warning("Langfuse observability unavailable; using the no-op sink.")
        return NoOpObservabilitySink()
