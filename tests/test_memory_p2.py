"""Post-Sprint-4 P2 — memory edit/pin, deterministic load order, and next-run preview.

Exercises the application service + repository against a real in-memory SQLite DB
(no mocks of the data layer). No provider calls anywhere.
"""

from __future__ import annotations

import pytest

from src.application.errors import ConflictError, ValidationError
from src.application.memory_service import MemoryApplicationService
from src.memory import MEMORY_MAX_LOAD_PER_RUN, MEMORY_MAX_SUMMARY_CHARS
from src.persistence import User, make_engine, make_session_factory, init_db
from src.repository import MemoryRepository


@pytest.fixture()
def service():
    engine = make_engine("sqlite://")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        s.add(User(subject="u1", provider="test"))
        s.add(User(subject="u2", provider="test"))
        s.commit()
    return MemoryApplicationService(MemoryRepository(sf))


def _mk(service, uid=1, *, category="recurring_gap", summary="Stakeholder comms",
        target_role=None):
    return service.create(uid, category=category, summary=summary, target_role=target_role)


# --- update -----------------------------------------------------------------


def test_update_summary(service):
    m = _mk(service)
    out = service.update(1, m.id, summary="Executive communication")
    assert out.summary == "Executive communication" and out.category == "recurring_gap"


def test_update_category(service):
    m = _mk(service)
    out = service.update(1, m.id, category="strength")
    assert out.category == "strength"


def test_clear_target_role(service):
    m = _mk(service, target_role="PM")
    out = service.update(1, m.id, target_role=None)
    assert out.target_role is None


def test_update_role(service):
    m = _mk(service, target_role="PM")
    out = service.update(1, m.id, target_role="Senior PM")
    assert out.target_role == "Senior PM"


def test_pin_and_unpin(service):
    m = _mk(service)
    assert service.update(1, m.id, pinned=True).pinned is True
    assert service.update(1, m.id, pinned=False).pinned is False


def test_no_field_update_rejected(service):
    m = _mk(service)
    with pytest.raises(ValidationError):
        service.update(1, m.id)


def test_invalid_category_rejected(service):
    m = _mk(service)
    with pytest.raises(ValidationError):
        service.update(1, m.id, category="medical_history")


def test_overlong_summary_rejected(service):
    m = _mk(service)
    with pytest.raises(ValidationError):
        service.update(1, m.id, summary="x" * (MEMORY_MAX_SUMMARY_CHARS + 1))


def test_overlong_role_rejected(service):
    m = _mk(service)
    with pytest.raises(ValidationError):
        service.update(1, m.id, target_role="r" * 201)


def test_foreign_memory_not_found(service):
    m = _mk(service, uid=1)
    assert service.update(2, m.id, summary="hijack") is None  # other user → not found


def test_duplicate_collision_rejected(service):
    a = _mk(service, summary="Alpha")
    _mk(service, summary="Beta")
    # Editing B to equal A (same category/summary/role) collides.
    b_id = [m.id for m in service.list(1) if m.summary == "Beta"][0]
    with pytest.raises(ConflictError):
        service.update(1, b_id, summary="Alpha")
    assert a.summary == "Alpha"


def test_updating_same_content_is_not_a_self_collision(service):
    m = _mk(service, summary="Same")
    # Re-saving the same summary (plus a pin) must not collide with itself.
    out = service.update(1, m.id, summary="Same", pinned=True)
    assert out.pinned is True


def test_updated_at_present_after_update(service):
    m = _mk(service)
    out = service.update(1, m.id, pinned=True)
    assert out.updated_at is not None


# --- load order (§11-13) -----------------------------------------------------


def test_load_order_role_run_prefers_matched_then_pinned(service):
    gp = _mk(service, summary="general pinned")
    service.update(1, gp.id, pinned=True)
    _mk(service, summary="general unpinned")
    _mk(service, summary="role match", target_role="PM")
    rmp = _mk(service, summary="role match pinned", target_role="PM")
    service.update(1, rmp.id, pinned=True)
    _mk(service, summary="other role", target_role="Nurse")

    loaded = service.load_for_agent(1, "PM")
    summaries = [m.summary for m in loaded]
    # role-matched pinned first, then role-matched unpinned, then general pinned, general unpinned.
    assert summaries[0] == "role match pinned"
    assert summaries[1] == "role match"
    assert "general pinned" in summaries and "general unpinned" in summaries
    # a DIFFERENT role's memory is excluded entirely.
    assert "other role" not in summaries


def test_load_order_no_role_prefers_general_pinned(service):
    g = _mk(service, summary="general")
    gp = _mk(service, summary="general pinned")
    service.update(1, gp.id, pinned=True)
    _mk(service, summary="role specific", target_role="PM")
    loaded = service.load_for_agent(1, None)
    summaries = [m.summary for m in loaded]
    assert summaries[0] == "general pinned"
    assert summaries[1] == "general"
    assert summaries[-1] == "role specific"
    assert g.id  # created


def test_load_cap_is_ten(service):
    for i in range(15):
        _mk(service, summary=f"m{i}")
    assert len(service.load_for_agent(1, None)) == MEMORY_MAX_LOAD_PER_RUN


# --- preview (§17-18) --------------------------------------------------------


def test_preview_matches_real_loader_order(service):
    for i in range(5):
        _mk(service, summary=f"pm{i}", target_role="PM")
    p = _mk(service, summary="pinned pm", target_role="PM")
    service.update(1, p.id, pinned=True)
    _mk(service, summary="general note")

    loaded = service.load_for_agent(1, "PM")
    preview = service.preview_for_agent(1, "PM")
    assert [r["id"] for r in preview] == [m.id for m in loaded]  # cannot drift
    assert [r["order"] for r in preview] == list(range(len(preview)))
    assert preview[0]["summary"] == "pinned pm" and preview[0]["reason"] == "Matches this role"


def test_preview_user_isolation(service):
    _mk(service, uid=1, summary="mine")
    assert service.preview_for_agent(2, None) == []  # other user sees nothing
