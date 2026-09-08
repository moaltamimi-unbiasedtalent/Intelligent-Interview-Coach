"""Safe agent run events — the data model a future Agent Inspector will render.

Events describe *what the agent did* (observable actions), never *how it reasoned*.
They deliberately exclude chain-of-thought, model reasoning, system prompts, raw
provider responses, and raw candidate/JD text. Only safe metadata is recorded.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum


class AgentEventType(str, Enum):
    RUN_STARTED = "run_started"
    MEMORY_LOADED = "memory_loaded"  # long-term memory loaded into the run (counts only)
    REQUEST_UNDERSTOOD = "request_understood"
    TOOL_REQUESTED = "tool_requested"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TOOL_REJECTED = "tool_rejected"  # unknown/unregistered tool
    HUMAN_INPUT_REQUIRED = "human_input_required"
    STEP_LIMIT_REACHED = "step_limit_reached"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


@dataclass
class AgentEvent:
    """A single safe event. `message` must be a safe summary, never private content."""

    event_type: AgentEventType
    step: int = 0
    tool_name: str | None = None
    duration_ms: int | None = None
    source_count: int | None = None
    status: str | None = None
    message: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d
