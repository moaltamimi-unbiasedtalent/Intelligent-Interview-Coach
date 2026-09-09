"""Long-term preparation memory — domain vocabulary, bounds and safe DTO.

This is **long-term** memory: selective, user-scoped, structured preparation facts
that persist across sessions (a durable DB table). It is deliberately distinct from
the LangGraph agent's **short-term execution state** (messages / tool_history /
checkpoints), which is transient and per-run — see docs/sprint4_architecture.md.

Only a concise, human-readable ``summary`` is stored per item. Whole conversations,
job descriptions, CVs, transcripts, interview answers, retrieved evidence, provider
responses and system prompts are NEVER stored here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

__all__ = [
    "MemoryCategory",
    "MemoryItem",
    "MEMORY_MAX_ITEMS_PER_USER",
    "MEMORY_MAX_SUMMARY_CHARS",
    "MEMORY_MAX_TARGET_ROLE_CHARS",
    "MEMORY_MAX_LOAD_PER_RUN",
    "normalize_summary",
    "normalize_role",
]


class MemoryCategory(str, Enum):
    """The closed set of preparation-memory categories (no arbitrary names).

    Deliberately small and preparation-focused. There is intentionally NO category
    for health, religion, politics, race, sexuality, criminal history or any other
    protected/sensitive characteristic — the coach never infers or stores those.
    """

    TARGET_ROLE = "target_role"          # a role the user repeatedly prepares for
    RECURRING_GAP = "recurring_gap"      # an approved area the user wants to improve
    STRENGTH = "strength"                # an approved preparation strength
    COMPLETED_TOPIC = "completed_topic"  # an area already practised/completed
    INTERVIEW_PREFERENCE = "interview_preference"  # e.g. a challenging interview style
    PREPARATION_GOAL = "preparation_goal"          # an explicit ongoing objective

    @classmethod
    def from_value(cls, value: str) -> "MemoryCategory":
        """Parse a category (accepts the enum value, case-insensitively)."""
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:  # pragma: no cover - message asserted in tests
            allowed = ", ".join(c.value for c in cls)
            raise ValueError(f"Unknown memory category. Allowed: {allowed}.") from exc


# Conservative bounds — memory is selective, not a data lake. Documented in
# docs/sprint4_architecture.md and enforced by the application service.
MEMORY_MAX_ITEMS_PER_USER = 100
MEMORY_MAX_SUMMARY_CHARS = 500
MEMORY_MAX_TARGET_ROLE_CHARS = 200
MEMORY_MAX_LOAD_PER_RUN = 10

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_summary(text: str) -> str:
    """Collapse whitespace + lowercase for deterministic duplicate detection."""
    return _WHITESPACE_RE.sub(" ", (text or "").strip()).lower()


def normalize_role(role: str | None) -> str | None:
    """Normalise a target role for case-insensitive matching/deduplication."""
    if not role:
        return None
    collapsed = _WHITESPACE_RE.sub(" ", role.strip())
    return collapsed.lower() or None


@dataclass
class MemoryItem:
    """A safe, serialisable view of one preparation memory (no internal ids).

    ``user_id`` is the internal owner id used for scoping; it is never serialised
    into API responses or agent events (see the API schema / event mapping).
    """

    id: int
    user_id: int
    category: str
    summary: str
    target_role: str | None
    source_run_id: str | None
    created_at: datetime | None
    updated_at: datetime | None
    pinned: bool = False

    def to_public(self) -> dict:
        """Public projection for API/UI — deliberately omits ``user_id``."""
        return {
            "id": self.id,
            "category": self.category,
            "summary": self.summary,
            "target_role": self.target_role,
            "pinned": self.pinned,
            "source_run_id": self.source_run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_agent_context(self) -> dict:
        """Minimal projection the agent loads as DATA (category + summary + role).

        Pinning is deliberately absent: it affects selection/order only, never what
        the model sees — the model still receives category/summary/target_role as DATA.
        """
        return {
            "category": self.category,
            "summary": self.summary,
            "target_role": self.target_role,
        }
