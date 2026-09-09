"""Preparation-memory API schemas (user-scoped, safe projections).

Requests never accept ``user_id``, ``source_run_id`` or timestamps — the server
owns identity, provenance and timing. Responses expose only safe fields (never the
internal user id or DB internals).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.memory import MEMORY_MAX_SUMMARY_CHARS, MEMORY_MAX_TARGET_ROLE_CHARS, MemoryCategory


class MemoryCreateRequest(BaseModel):
    """Explicit, user-initiated memory write (Phase 7 has no automatic writes)."""

    category: MemoryCategory = Field(
        description="One of the fixed preparation-memory categories."
    )
    summary: str = Field(
        min_length=1, max_length=MEMORY_MAX_SUMMARY_CHARS,
        description="A concise, human-readable preparation fact (not a transcript/JD/CV).",
    )
    target_role: str | None = Field(
        default=None, max_length=MEMORY_MAX_TARGET_ROLE_CHARS,
        description="Optional role this memory relates to (e.g. 'Head of People').",
    )


class MemoryUpdateRequest(BaseModel):
    """A partial edit to one preparation memory (P2). At least one field required.

    A field left OUT is untouched; ``target_role: null`` explicitly clears the role.
    Never accepts ``user_id``, ``source_run_id`` or timestamps — the server owns those.
    """

    model_config = {"extra": "forbid"}

    category: MemoryCategory | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=MEMORY_MAX_SUMMARY_CHARS)
    target_role: str | None = Field(default=None, max_length=MEMORY_MAX_TARGET_ROLE_CHARS)
    pinned: bool | None = None


class MemoryResponse(BaseModel):
    """A single saved preparation memory (safe projection)."""

    id: int
    category: str
    summary: str
    target_role: str | None = None
    pinned: bool = False
    source_run_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoryListResponse(BaseModel):
    memories: list[MemoryResponse] = Field(default_factory=list)


class MemoryDeleteResponse(BaseModel):
    deleted: bool
    id: int


class MemoryPreviewItem(BaseModel):
    """One memory that WOULD be loaded for a run (safe projection + order/reason)."""

    id: int
    category: str
    summary: str
    target_role: str | None = None
    pinned: bool = False
    order: int
    reason: str


class MemoryPreviewResponse(BaseModel):
    """The memories a new run for ``target_role`` would load (matches the real loader)."""

    target_role: str | None = None
    load_limit: int
    items: list[MemoryPreviewItem] = Field(default_factory=list)
