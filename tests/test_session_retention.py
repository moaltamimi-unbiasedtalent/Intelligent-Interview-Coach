"""Sprint 4 Phase 11 — durable in-progress session retention/cleanup.

Only stale in-progress sessions are removed; recent ones and (separately) completed
history are never touched. Dry-run counts without deleting.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import update

from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import (
    InterviewSession,
    User,
    init_db,
    make_engine,
    make_session_factory,
    utcnow,
)


def _ctx(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path/'ret.db'}")
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    with sf() as db:
        db.add(User(subject="alice", provider="test"))
        db.commit()
        uid = db.query(User).filter_by(subject="alice").first().id
    return DurableInterviewSessionStore(sf), sf, uid


def _age(sf, session_id, days):
    with sf() as db:
        db.execute(update(InterviewSession).where(InterviewSession.session_id == session_id)
                   .values(last_accessed_at=utcnow() - timedelta(days=days)))
        db.commit()


def test_cleanup_removes_only_stale_sessions(tmp_path):
    store, sf, uid = _ctx(tmp_path)
    old = store.create(uid)
    recent = store.create(uid)
    _age(sf, old, days=40)      # older than a 30-day window
    _age(sf, recent, days=1)    # recent — must be kept

    cutoff = utcnow() - timedelta(days=30)
    assert store.count_stale_sessions(before=cutoff) == 1  # dry-run count
    removed = store.cleanup_stale_sessions(before=cutoff)
    assert removed == 1
    # The recent session survives; the stale one is gone.
    assert store.load_state(recent, uid) is not None
    with sf() as db:
        assert db.get(InterviewSession, old) is None


def test_dry_run_count_does_not_delete(tmp_path):
    store, sf, uid = _ctx(tmp_path)
    sid = store.create(uid)
    _age(sf, sid, days=99)
    cutoff = utcnow() - timedelta(days=30)
    assert store.count_stale_sessions(before=cutoff) == 1
    # Counting must not delete.
    with sf() as db:
        assert db.get(InterviewSession, sid) is not None
