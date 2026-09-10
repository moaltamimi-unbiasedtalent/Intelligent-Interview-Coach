"""Demo identity + persistence contract (Phase 5.1, Defect A).

The first golden-demo rehearsal failed user-scoped persistence because the local SQLite
file was stale — created before a migration, so it lacked the `pinned` column and every
memory write 500'd. These tests pin the invariant that must hold once the schema is at
head:

  * one demo subject resolves to ONE persisted user id, idempotently and consistently;
  * that single id is the SAME id every user-scoped subsystem uses — memory, interview
    history and feedback — so nothing "saves under a different user" between Agent runs
    and later reads;
  * on a schema that IS at Alembic head, each of those writes round-trips (proving the
    rehearsal failure was stale schema, not an auth/user-scoping defect).

The identity resolution asserted here is exactly `InterviewRepository.get_or_create_user`
— the same call the API uses. Production auth is unchanged and stays fail-closed; this
only proves a resolved subject is used consistently.
"""

from __future__ import annotations

import importlib.util

import pytest

from src.application.memory_service import MemoryApplicationService
from src.memory import MemoryCategory
from src.persistence import make_engine, make_session_factory
from src.repository import FeedbackRepository, InterviewRepository, MemoryRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("alembic") is None,
    reason='alembic not installed (pip install -e ".[db]")',
)

_SUBJECT = "demo-reviewer"
_OTHER = "another-reviewer"


def _alembic_config(db_url: str):
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture()
def session_factory(tmp_path, monkeypatch):
    """A temp SQLite DB migrated to Alembic head (matches production schema)."""
    from alembic import command

    db_url = f"sqlite:///{tmp_path/'demo.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)  # migrations/env.py reads this
    command.upgrade(_alembic_config(db_url), "head")
    return make_session_factory(make_engine(db_url))


def _interview_payload(role: str = "Senior Product Manager") -> dict:
    return {
        "configuration": {"target_role": role},
        "mode": "Record",
        "status": "completed",
        "questions": [
            {
                "position": 0,
                "canonical_question": "Tell me about a product decision.",
                "question_type": "behavioural",
                "difficulty": "moderate",
                "answer": {"text": "I started from the customer problem.",
                           "evaluation": {"overall_score": 74}},
            }
        ],
        "report": {"report": {"overall_readiness_score": 70}},
    }


def test_same_subject_resolves_to_same_user_id(session_factory):
    repo = InterviewRepository(session_factory)

    first = repo.get_or_create_user(subject=_SUBJECT, provider="dev")
    again = repo.get_or_create_user(subject=_SUBJECT, provider="dev",
                                    display_name="Demo reviewer")

    assert first == again  # idempotent — no duplicate user for the same subject
    # A different subject is a different persisted user (scoping preserved).
    assert repo.get_or_create_user(subject=_OTHER, provider="dev") != first


def test_resolved_id_is_consistent_across_subsystems(session_factory):
    """The one id a subject resolves to is the id memory, history and feedback all use."""
    repo = InterviewRepository(session_factory)
    memory = MemoryApplicationService(MemoryRepository(session_factory))
    feedback = FeedbackRepository(session_factory)

    uid = repo.get_or_create_user(subject=_SUBJECT, provider="dev")

    # Memory persists and reads back under uid.
    item = memory.create(uid, category=MemoryCategory.RECURRING_GAP.value,
                         summary="priority gap: payments/regulated-compliance workflows")
    assert [m.id for m in memory.list(uid)] == [item.id]

    # Interview history persists and reads back under uid.
    interview_id = repo.save_interview(uid, _interview_payload())
    assert [row["id"] for row in repo.list_interviews(uid)] == [interview_id]

    # Feedback persists and reads back under uid.
    fb = feedback.upsert(uid, surface="agent", target_id="run-1:1",
                         rating="helpful", comment=None)
    assert feedback.get(uid, "agent", "run-1:1").id == fb.id

    # Re-resolving the subject returns the SAME id — every subsystem above is reachable
    # for that identity on a later Agent run / page load, not orphaned under another id.
    assert repo.get_or_create_user(subject=_SUBJECT, provider="dev") == uid


def test_other_subject_cannot_see_demo_user_records(session_factory):
    """User scoping holds — a different subject sees none of the demo user's data."""
    repo = InterviewRepository(session_factory)
    memory = MemoryApplicationService(MemoryRepository(session_factory))

    demo = repo.get_or_create_user(subject=_SUBJECT, provider="dev")
    memory.create(demo, category=MemoryCategory.RECURRING_GAP.value, summary="demo-only")
    repo.save_interview(demo, _interview_payload())

    other = repo.get_or_create_user(subject=_OTHER, provider="dev")
    assert memory.list(other) == []
    assert repo.list_interviews(other) == []
