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

from src.application.errors import ConflictError, ValidationError
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

__all__ = ["MemoryApplicationService", "UNSET"]

# Sentinel distinguishing "field omitted" from an explicit value (e.g. target_role=None
# to clear it) in a partial update.
UNSET = object()


def _validate_category(category: str) -> str:
    try:
        return MemoryCategory.from_value(category).value
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _validate_summary(summary: str) -> str:
    cleaned = (summary or "").strip()
    if not cleaned:
        raise ValidationError("A memory summary is required.")
    if len(cleaned) > MEMORY_MAX_SUMMARY_CHARS:
        raise ValidationError(
            f"A memory summary must be {MEMORY_MAX_SUMMARY_CHARS} characters or fewer."
        )
    return cleaned


def _validate_role(target_role: str | None) -> str | None:
    role = (target_role or "").strip() or None
    if role and len(role) > MEMORY_MAX_TARGET_ROLE_CHARS:
        raise ValidationError(
            f"A target role must be {MEMORY_MAX_TARGET_ROLE_CHARS} characters or fewer."
        )
    return role


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
        cat = _validate_category(category)
        cleaned = _validate_summary(summary)
        role = _validate_role(target_role)

        # Deterministic duplicate protection: an exact equivalent is returned as-is.
        existing = self._repo.find_duplicate(
            user_id, category=cat, summary=cleaned, target_role=role
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
            user_id, category=cat, summary=cleaned,
            target_role=role, source_run_id=source_run_id,
        )

    def update(
        self,
        user_id: int,
        memory_id: int,
        *,
        category: object = UNSET,
        summary: object = UNSET,
        target_role: object = UNSET,
        pinned: object = UNSET,
    ) -> MemoryItem | None:
        """Apply a partial, validated edit to a user's memory.

        Returns the updated item, ``None`` when the memory does not exist for this user
        (a foreign id is indistinguishable from unknown), and raises
        :class:`ConflictError` if the edit would duplicate another of the user's
        memories. Fields left ``UNSET`` are untouched; ``target_role=None`` explicitly
        clears the role. Validation reuses the exact create rules.
        """
        current = self._repo.get(user_id, memory_id)
        if current is None:
            return None
        if category is UNSET and summary is UNSET and target_role is UNSET and pinned is UNSET:
            raise ValidationError("Provide at least one field to update.")

        fields: dict = {}
        merged_category = current.category
        merged_summary = current.summary
        merged_role = current.target_role
        if category is not UNSET:
            merged_category = _validate_category(category)  # type: ignore[arg-type]
            fields["category"] = merged_category
        if summary is not UNSET:
            merged_summary = _validate_summary(summary)  # type: ignore[arg-type]
            fields["summary"] = merged_summary
        if target_role is not UNSET:
            merged_role = _validate_role(target_role)  # type: ignore[arg-type]
            fields["target_role"] = merged_role
        if pinned is not UNSET:
            if not isinstance(pinned, bool):
                raise ValidationError("pinned must be true or false.")
            fields["pinned"] = pinned

        # Editing content must not create a duplicate of another owned memory.
        if any(k in fields for k in ("category", "summary", "target_role")):
            clash = self._repo.find_duplicate(
                user_id, category=merged_category, summary=merged_summary,
                target_role=merged_role, exclude_id=memory_id,
            )
            if clash is not None:
                raise ConflictError("An equivalent preparation memory already exists.")

        return self._repo.update(user_id, memory_id, fields=fields)

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

        Deterministic selection (no vector search, no LLM). Pinning is a priority
        signal WITHIN otherwise-relevant memories — never "always load" and never
        "trust over current context". Ordering by priority bucket, newest first
        within each bucket (``list_for_user`` returns newest-first and partitioning
        is stable):

        With a target role:
          1. role-matched + pinned
          2. role-matched + unpinned
          3. general + pinned
          4. general + unpinned
        Memories for a *different* role are excluded (they belong to a different
        preparation).

        Without a target role:
          1. general + pinned
          2. general + unpinned
          3. role-specific + pinned
          4. role-specific + unpinned

        Then capped at ``MEMORY_MAX_LOAD_PER_RUN``. Current explicit request/context
        always outranks loaded memory — memory is supplemental DATA, never authority.
        """
        items = self._repo.list_for_user(user_id)  # newest first
        run_role = normalize_role(target_role)

        def pinned_first(group: list[MemoryItem]) -> list[MemoryItem]:
            return [m for m in group if m.pinned] + [m for m in group if not m.pinned]

        if run_role:
            role_matched = [m for m in items if normalize_role(m.target_role) == run_role]
            general = [m for m in items if m.target_role is None]
            selected = pinned_first(role_matched) + pinned_first(general)
        else:
            general = [m for m in items if m.target_role is None]
            role_specific = [m for m in items if m.target_role is not None]
            selected = pinned_first(general) + pinned_first(role_specific)
        return selected[:MEMORY_MAX_LOAD_PER_RUN]

    def preview_for_agent(
        self, user_id: int, target_role: str | None = None
    ) -> list[dict]:
        """The exact memories a NEW run for ``target_role`` would load, as safe preview
        rows (id/category/summary/target_role/pinned + order + reason).

        Delegates to :meth:`load_for_agent` so the preview can never drift from the
        real loader (there is one selection implementation, not two).
        """
        run_role = normalize_role(target_role)
        items = self.load_for_agent(user_id, target_role)
        rows: list[dict] = []
        for order, m in enumerate(items):
            matches_role = bool(run_role) and normalize_role(m.target_role) == run_role
            reason = "Matches this role" if matches_role else "General preparation memory"
            rows.append({
                "id": m.id,
                "category": m.category,
                "summary": m.summary,
                "target_role": m.target_role,
                "pinned": m.pinned,
                "order": order,
                "reason": reason,
            })
        return rows
