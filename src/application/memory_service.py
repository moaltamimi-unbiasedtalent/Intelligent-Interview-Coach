"""Long-term preparation memory application service (Streamlit-free).

Thin, safe boundary over :class:`src.repository.MemoryRepository`. It validates the
category and content, enforces conservative bounds, keeps every operation
user-scoped, de-duplicates deterministically, and returns safe typed
:class:`src.memory.MemoryItem` values. It imports no Streamlit and no FastAPI.

Two critical rules (Phase 7):
- **Explicit consent only.** Nothing here persists memory on the agent's behalf; a
  write happens only because a user/API caller explicitly asked for it.
- **Selective, bounded, user-scoped.** Whole conversations, JDs, CVs, transcripts,
  answers, retrieved evidence, provider responses and system prompts are never
  stored — only a concise summary, capped in length and count.
"""

from __future__ import annotations

from src.application.errors import ValidationError
from src.memory import (
    MEMORY_MAX_ITEMS_PER_USER,
    MEMORY_MAX_LOAD_PER_RUN,
    MEMORY_MAX_SUMMARY_CHARS,
    MEMORY_MAX_TARGET_ROLE_CHARS,
    MemoryCategory,
    MemoryItem,
    normalize_role,
)
from src.repository import MemoryRepository

__all__ = ["MemoryApplicationService"]


class MemoryApplicationService:
    """User-scoped preparation-memory operations for any frontend."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repo = repository

    # -- writes ---------------------------------------------------------------

    def create(
        self,
        user_id: int,
        *,
        category: str,
        summary: str,
        target_role: str | None = None,
        source_run_id: str | None = None,
    ) -> MemoryItem:
        """Validate + persist one memory (idempotent on an exact duplicate).

        ``source_run_id`` is server-set only (never accepted from a public request
        body) — ownership is always enforced via ``user_id``.
        """
        try:
            cat = MemoryCategory.from_value(category)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        cleaned = (summary or "").strip()
        if not cleaned:
            raise ValidationError("A memory summary is required.")
        if len(cleaned) > MEMORY_MAX_SUMMARY_CHARS:
            raise ValidationError(
                f"A memory summary must be {MEMORY_MAX_SUMMARY_CHARS} characters or fewer."
            )

        role = (target_role or "").strip() or None
        if role and len(role) > MEMORY_MAX_TARGET_ROLE_CHARS:
            raise ValidationError(
                f"A target role must be {MEMORY_MAX_TARGET_ROLE_CHARS} characters or fewer."
            )

        # Deterministic duplicate protection: an exact equivalent is returned as-is.
        existing = self._repo.find_duplicate(
            user_id, category=cat.value, summary=cleaned, target_role=role
        )
        if existing is not None:
            return existing

        # Bound total stored memory per user (checked after dedupe so re-saving an
        # existing item never trips the cap).
        if self._repo.count_for_user(user_id) >= MEMORY_MAX_ITEMS_PER_USER:
            raise ValidationError(
                "You've reached the maximum number of saved preparation memories. "
                "Remove some before adding more."
            )

        return self._repo.create(
            user_id, category=cat.value, summary=cleaned,
            target_role=role, source_run_id=source_run_id,
        )

    # -- reads (all user-scoped) ---------------------------------------------

    def list(
        self, user_id: int, *, category: str | None = None,
        target_role: str | None = None,
    ) -> list[MemoryItem]:
        cat = MemoryCategory.from_value(category).value if category else None
        role = (target_role or "").strip() or None
        return self._repo.list_for_user(user_id, category=cat, target_role=role)

    def get(self, user_id: int, memory_id: int) -> MemoryItem | None:
        return self._repo.get(user_id, memory_id)

    def exists(self, user_id: int, *, category: str, summary: str,
               target_role: str | None = None) -> bool:
        """True if an equivalent memory already exists (deterministic dedupe key).

        Lets a caller distinguish a fresh write from an idempotent duplicate without
        exposing the repository. Invalid categories simply return False.
        """
        try:
            cat = MemoryCategory.from_value(category).value
        except ValueError:
            return False
        role = (target_role or "").strip() or None
        return self._repo.find_duplicate(
            user_id, category=cat, summary=(summary or "").strip(), target_role=role) is not None

    def delete(self, user_id: int, memory_id: int) -> bool:
        return self._repo.delete(user_id, memory_id)

    # -- agent read (deterministic, bounded, no model call) -------------------

    def load_for_agent(
        self, user_id: int, target_role: str | None = None
    ) -> list[MemoryItem]:
        """Select a bounded set of relevant memories for an agent run.

        Deterministic selection (no vector search, no LLM):
          1. memories whose target role matches the current run's role (if any),
          2. then general (role-less) memories,
          3. capped at ``MEMORY_MAX_LOAD_PER_RUN``, newest first within each group.

        When the run has a target role, memories for a *different* role are NOT
        loaded (they belong to a different preparation). When the run has no role,
        general memories come first, then role-specific ones as supplemental
        context. Current explicit request/context always takes precedence over
        loaded memory (see docs) — memory is supplemental DATA, never authority.
        """
        items = self._repo.list_for_user(user_id)  # newest first
        run_role = normalize_role(target_role)
        if run_role:
            role_matched = [m for m in items if normalize_role(m.target_role) == run_role]
            general = [m for m in items if m.target_role is None]
            selected = role_matched + general
        else:
            general = [m for m in items if m.target_role is None]
            role_specific = [m for m in items if m.target_role is not None]
            selected = general + role_specific
        return selected[:MEMORY_MAX_LOAD_PER_RUN]
