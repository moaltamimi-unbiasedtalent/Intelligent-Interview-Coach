"""Sprint 4 Phase 7 — preparation-memory repository + application service.

User-scoped CRUD, strict cross-user isolation, deterministic duplicate detection,
bounds (max items / summary length), category validation and optional target role.
Backed by a throwaway in-memory SQLite DB — no provider, no network.
"""

from __future__ import annotations

import pytest

from src.application.errors import ValidationError
from src.application.memory_service import MemoryApplicationService
from src.memory import MEMORY_MAX_ITEMS_PER_USER, MEMORY_MAX_SUMMARY_CHARS
from src.persistence import init_db, make_engine, make_session_factory
from src.repository import MemoryRepository

USER_A, USER_B = 1, 2


@pytest.fixture()
def service() -> MemoryApplicationService:
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return MemoryApplicationService(MemoryRepository(make_session_factory(engine)))


def test_create_and_get_memory(service):
    item = service.create(USER_A, category="recurring_gap",
                          summary="Executive communication", target_role="Head of People")
    assert item.id > 0 and item.category == "recurring_gap"
    fetched = service.get(USER_A, item.id)
    assert fetched is not None and fetched.summary == "Executive communication"


def test_list_returns_user_memories_newest_first(service):
    service.create(USER_A, category="strength", summary="First")
    second = service.create(USER_A, category="strength", summary="Second")
    items = service.list(USER_A)
    assert [i.summary for i in items][:1] == ["Second"]  # newest first
    assert second.id == items[0].id


def test_delete_memory(service):
    item = service.create(USER_A, category="strength", summary="Board communication")
    assert service.delete(USER_A, item.id) is True
    assert service.get(USER_A, item.id) is None
    assert service.delete(USER_A, item.id) is False  # already gone


def test_target_role_is_optional(service):
    item = service.create(USER_A, category="preparation_goal", summary="Improve pacing")
    assert item.target_role is None


# --- user isolation (§8) -----------------------------------------------------


def test_user_cannot_list_another_users_memory(service):
    service.create(USER_A, category="strength", summary="A only")
    service.create(USER_B, category="strength", summary="B only")
    assert [i.summary for i in service.list(USER_A)] == ["A only"]
    assert [i.summary for i in service.list(USER_B)] == ["B only"]


def test_user_cannot_get_or_delete_another_users_memory(service):
    a_item = service.create(USER_A, category="strength", summary="A private")
    assert service.get(USER_B, a_item.id) is None        # not found for B
    assert service.delete(USER_B, a_item.id) is False     # no-op for B
    assert service.get(USER_A, a_item.id) is not None     # still there for A


# --- duplicate detection (§14) ----------------------------------------------


def test_exact_duplicate_returns_existing_row(service):
    a = service.create(USER_A, category="recurring_gap",
                       summary="Executive communication", target_role="Head of People")
    b = service.create(USER_A, category="recurring_gap",
                       summary="  executive   COMMUNICATION ", target_role="head of people")
    assert a.id == b.id  # normalized summary + role → same row, not a new one
    assert len(service.list(USER_A)) == 1


def test_different_role_is_not_a_duplicate(service):
    a = service.create(USER_A, category="strength", summary="Communication", target_role="PM")
    b = service.create(USER_A, category="strength", summary="Communication", target_role="HoP")
    assert a.id != b.id and len(service.list(USER_A)) == 2


# --- bounds (§13) ------------------------------------------------------------


def test_summary_length_is_bounded(service):
    with pytest.raises(ValidationError):
        service.create(USER_A, category="strength", summary="x" * (MEMORY_MAX_SUMMARY_CHARS + 1))
    # Exactly at the limit is allowed.
    ok = service.create(USER_A, category="strength", summary="x" * MEMORY_MAX_SUMMARY_CHARS)
    assert ok.id > 0


def test_empty_summary_is_rejected(service):
    with pytest.raises(ValidationError):
        service.create(USER_A, category="strength", summary="   ")


def test_max_items_per_user_is_enforced(service):
    for i in range(MEMORY_MAX_ITEMS_PER_USER):
        service.create(USER_A, category="strength", summary=f"item {i}")
    with pytest.raises(ValidationError):
        service.create(USER_A, category="strength", summary="one too many")
    # A different user is unaffected by another user's cap.
    assert service.create(USER_B, category="strength", summary="fresh").id > 0


def test_resaving_an_existing_item_does_not_trip_the_cap(service):
    for i in range(MEMORY_MAX_ITEMS_PER_USER):
        service.create(USER_A, category="strength", summary=f"item {i}")
    # Re-saving an exact duplicate returns the existing row rather than erroring.
    again = service.create(USER_A, category="strength", summary="item 0")
    assert again.summary == "item 0"


# --- category validation (§3) ------------------------------------------------


@pytest.mark.parametrize("bad", ["health", "religion", "", "random_thing"])
def test_invalid_category_is_rejected(service, bad):
    with pytest.raises(ValidationError):
        service.create(USER_A, category=bad, summary="something")


def test_all_valid_categories_are_accepted(service):
    from src.memory import MemoryCategory
    for cat in MemoryCategory:
        item = service.create(USER_A, category=cat.value, summary=f"note for {cat.value}")
        assert item.category == cat.value


def test_public_projection_omits_internal_user_id(service):
    item = service.create(USER_A, category="strength", summary="Board communication")
    public = item.to_public()
    assert "user_id" not in public
    assert set(public) >= {"id", "category", "summary", "target_role", "created_at", "updated_at"}
