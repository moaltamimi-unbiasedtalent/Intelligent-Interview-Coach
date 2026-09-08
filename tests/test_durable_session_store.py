"""Sprint 4 Phase 10 — durable interview session store.

Covers the store contract (section 66): create/load/save/delete, user isolation,
durable idempotency (incl. surviving store recreation), optimistic concurrency
(version increment + stale rejection), the operation lease, and durability across
service/engine recreation and a process-style restart (file-backed SQLite). No
provider calls — the SessionManager is driven directly.
"""

from __future__ import annotations

import pytest

from src.interview.session_codec import SESSION_STATE_SCHEMA_VERSION
from src.interview.session_repository import (
    DurableInterviewSessionStore,
    OperationInProgressError,
    SessionConflictError,
    SessionNotFoundError,
)
from src.persistence import InterviewSession, User, make_engine, make_session_factory, init_db
from src.session_manager import SessionState
from tests import _interview_factories as f


def _factory(url: str):
    engine = make_engine(url)
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    # Create two users so user_id FKs are valid even if FK enforcement is on.
    with sf() as db:
        for sub in ("alice", "bob"):
            if not db.query(User).filter_by(subject=sub, provider="test").first():
                db.add(User(subject=sub, provider="test"))
        db.commit()
        alice = db.query(User).filter_by(subject="alice").first().id
        bob = db.query(User).filter_by(subject="bob").first().id
    return engine, sf, alice, bob


@pytest.fixture
def mem():
    engine, sf, alice, bob = _factory("sqlite://")  # shared in-memory for this engine
    # NOTE: a bare in-memory URL gives a per-connection DB; use a file for realism.
    return engine, sf, alice, bob


@pytest.fixture
def store_ctx(tmp_path):
    url = f"sqlite:///{tmp_path/'sessions.db'}"
    engine, sf, alice, bob = _factory(url)
    return DurableInterviewSessionStore(sf), sf, alice, bob, url


# --- create / load / save / delete ------------------------------------------


def test_create_returns_opaque_id_and_row(store_ctx):
    store, sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    assert isinstance(sid, str) and len(sid) >= 16 and sid.isalnum()
    with sf() as db:
        row = db.get(InterviewSession, sid)
        assert row.user_id == alice and row.version == 1 and row.status == "SETUP"


def test_load_after_mutation_restores_state(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with store.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(2), f.settings())
        sm.save_strategy(f.strategy())
        sm.add_question(f.question(1))
    reloaded = store.load_state(sid, alice)
    assert reloaded.data.state == SessionState.AWAITING_ANSWER
    assert reloaded.data.questions[0].question_id == 1
    assert reloaded.data.config.target_role == "Registered Nurse"


def test_delete_removes_session(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    store.discard(sid, alice)
    with pytest.raises(SessionNotFoundError):
        store.load_state(sid, alice)


# --- user isolation ----------------------------------------------------------


def test_user_cannot_load_foreign_session(store_ctx):
    store, _sf, alice, bob, _ = store_ctx
    sid = store.create(alice)
    with pytest.raises(SessionNotFoundError):
        store.load_state(sid, bob)


def test_user_cannot_mutate_foreign_session(store_ctx):
    store, _sf, alice, bob, _ = store_ctx
    sid = store.create(alice)
    with pytest.raises(SessionNotFoundError):
        with store.mutate(sid, bob) as sm:
            sm.start_new_interview(f.config(), f.settings())


def test_discard_of_foreign_session_is_noop(store_ctx):
    store, _sf, alice, bob, _ = store_ctx
    sid = store.create(alice)
    store.discard(sid, bob)  # no error, no effect
    assert store.load_state(sid, alice) is not None


def test_unknown_and_foreign_are_indistinguishable(store_ctx):
    store, _sf, alice, bob, _ = store_ctx
    sid = store.create(alice)
    # Foreign existing id and a truly unknown id both raise the same error type.
    with pytest.raises(SessionNotFoundError):
        store.load_state(sid, bob)
    with pytest.raises(SessionNotFoundError):
        store.load_state("does-not-exist", bob)


# --- idempotency -------------------------------------------------------------


def test_idempotent_create_returns_same_session(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid1, created1 = store.create_or_get(alice, "agent-handoff:run-1")
    sid2, created2 = store.create_or_get(alice, "agent-handoff:run-1")
    assert created1 is True and created2 is False and sid1 == sid2


def test_idempotency_scoped_per_user_and_key(store_ctx):
    store, _sf, alice, bob, _ = store_ctx
    sid_a, _ = store.create_or_get(alice, "k")
    sid_b, _ = store.create_or_get(bob, "k")           # same key, different user
    sid_a2, _ = store.create_or_get(alice, "other")    # different key, same user
    assert len({sid_a, sid_b, sid_a2}) == 3


def test_idempotency_survives_store_recreation(store_ctx):
    store, sf, alice, _bob, url = store_ctx
    sid1, created1 = store.create_or_get(alice, "agent-handoff:run-9")
    assert created1 is True
    # Brand-new store object over the SAME database (simulates another worker/restart).
    store2 = DurableInterviewSessionStore(sf)
    sid2, created2 = store2.create_or_get(alice, "agent-handoff:run-9")
    assert sid2 == sid1 and created2 is False


# --- optimistic concurrency --------------------------------------------------


def test_version_increments_on_each_save(store_ctx):
    store, sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with store.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(), f.settings())
    with store.mutate(sid, alice) as sm:
        sm.save_strategy(f.strategy())
    with sf() as db:
        assert db.get(InterviewSession, sid).version == 3  # 1 (create) → 2 → 3


def test_stale_version_write_is_rejected(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    # First save advances the version to 2.
    with store.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(), f.settings())
        data_after = sm.data
    # A second writer that still believes version==1 must be rejected.
    with pytest.raises(SessionConflictError):
        store._save(sid, alice, data_after, expected_version=1)


def test_two_overlapping_mutations_second_conflicts(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)  # version 1
    # Simulate two tabs that both loaded version 1.
    a = store.load_state(sid, alice)
    b = store.load_state(sid, alice)
    a.start_new_interview(f.config(), f.settings())
    b.start_new_interview(f.config(), f.settings())
    store._save(sid, alice, a.data, expected_version=1)  # tab A wins → version 2
    with pytest.raises(SessionConflictError):
        store._save(sid, alice, b.data, expected_version=1)  # tab B stale


# --- operation lease ---------------------------------------------------------


def test_lease_blocks_concurrent_provider_operation(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    store._claim_lease(sid, alice, "create")
    with pytest.raises(OperationInProgressError):
        store._claim_lease(sid, alice, "create")


def test_stale_lease_is_reclaimable(store_ctx):
    store, sf, alice, _bob, url = store_ctx
    sid = store.create(alice)
    store._claim_lease(sid, alice, "create")
    # A store with a 0-second lease treats any existing lease as stale (crashed worker).
    fresh = DurableInterviewSessionStore(sf, lease_seconds=0)
    fresh._claim_lease(sid, alice, "create")  # must not raise


def test_mutate_with_operation_releases_lease_on_success(store_ctx):
    store, sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with store.mutate(sid, alice, operation="create") as sm:
        sm.start_new_interview(f.config(), f.settings())
    with sf() as db:
        row = db.get(InterviewSession, sid)
        assert row.active_operation is None and row.operation_leased_at is None


def test_mutate_releases_lease_on_error(store_ctx):
    store, sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with pytest.raises(RuntimeError):
        with store.mutate(sid, alice, operation="strategy") as sm:
            sm.start_new_interview(f.config(), f.settings())
            raise RuntimeError("boom")
    with sf() as db:
        assert db.get(InterviewSession, sid).active_operation is None


# --- persisted state variety -------------------------------------------------


def test_deep_dive_state_persists(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with store.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(), f.settings())
        sm.save_strategy(f.strategy())
        sm.add_question(f.question(1))
        sm.add_candidate_answer("answer")
        sm.add_evaluation(f.evaluation())
        sm.start_branch("deepen_reasoning")
    reloaded = store.load_state(sid, alice)
    assert reloaded.data.branch_active is True
    assert reloaded.data.branch_mode == "deepen_reasoning"


def test_report_and_error_state_persist(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with store.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(1), f.settings())
        sm.save_strategy(f.strategy())
        sm.add_question(f.question(1))
        sm.add_candidate_answer("a")
        sm.add_evaluation(f.evaluation())
        sm.advance_interview()  # → INTERVIEW_COMPLETE (1 planned)
        sm.save_final_report(f.report())
    reloaded = store.load_state(sid, alice)
    assert reloaded.data.state == SessionState.REPORT_READY
    assert reloaded.data.report.overall_readiness_score == 68


# --- durability across recreation / restart ----------------------------------


def test_durable_across_engine_recreation(tmp_path):
    url = f"sqlite:///{tmp_path/'restart.db'}"
    engine_a, sf_a, alice, _bob = _factory(url)
    store_a = DurableInterviewSessionStore(sf_a)
    sid = store_a.create(alice)
    with store_a.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(2), f.settings())
        sm.save_strategy(f.strategy())
        sm.add_question(f.question(1))
        sm.add_candidate_answer("durable answer")
        sm.add_evaluation(f.evaluation(88))
    engine_a.dispose()

    # Entirely new engine/session_factory/store over the SAME file — process restart.
    engine_b = make_engine(url)
    sf_b = make_session_factory(engine_b)
    store_b = DurableInterviewSessionStore(sf_b)
    reloaded = store_b.load_state(sid, alice)
    assert reloaded.data.evaluations[0].overall_score == 88
    assert reloaded.data.answers == ["durable answer"]
    # Can continue the interview on the new instance.
    with store_b.mutate(sid, alice) as sm:
        assert sm.advance_interview() is True  # 1 of 2 done → more remain


def test_list_active_returns_safe_summaries(store_ctx):
    store, _sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with store.mutate(sid, alice) as sm:
        sm.start_new_interview(f.config(3), f.settings())
        sm.save_strategy(f.strategy())
        sm.add_question(f.question(1))
    summaries = store.list_active(alice)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.session_id == sid and s.target_role == "Registered Nurse"
    assert s.questions_planned == 3 and s.question_number == 1
    # Safe summary carries no JD/background/answers.
    assert not hasattr(s, "job_description")


def test_schema_version_is_persisted(store_ctx):
    store, sf, alice, _bob, _ = store_ctx
    sid = store.create(alice)
    with sf() as db:
        assert db.get(InterviewSession, sid).state_schema_version == SESSION_STATE_SCHEMA_VERSION
