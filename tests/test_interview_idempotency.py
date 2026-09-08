"""Sprint 4 Phase 9 hardening — idempotent interview creation + config options.

Covers the transitional session store's user-scoped idempotency and the create route:
the same Idempotency-Key returns the SAME session WITHOUT re-running strategy/first-
question generation (spy call counts), while no key preserves the create-every-time
behaviour. Also the safe options endpoint (single taxonomy source). No provider calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.main import create_app
from src.api.session_store import InMemorySessionStore
from src.application.interview_service import InterviewApplicationService
from tests.test_api import _FakeClient, _FakeEval, _FakeRepo, _FakeReport


# --- session store idempotency (unit) ----------------------------------------


def test_store_same_key_same_session():
    store = InMemorySessionStore()
    a, created_a = store.create_or_get(1, "k")
    b, created_b = store.create_or_get(1, "k")
    assert a == b and created_a is True and created_b is False


def test_store_different_key_and_user_isolation():
    store = InMemorySessionStore()
    a, _ = store.create_or_get(1, "k")
    assert store.create_or_get(1, "k2")[0] != a          # different key → different session
    assert store.create_or_get(2, "k")[0] != a           # different user, same key → isolated


def test_store_no_key_always_creates():
    store = InMemorySessionStore()
    assert store.create(1) != store.create(1)


def test_store_eviction_cleans_idempotency_mapping():
    store = InMemorySessionStore(max_sessions=2)
    first, _ = store.create_or_get(1, "k")
    store.create(1)
    store.create(1)  # evicts `first` (cap 2)
    again, created = store.create_or_get(1, "k")
    assert again != first and created is True             # stale mapping was removed
    assert len(store._idem) <= 2                          # no unbounded growth


def test_store_discard_removes_idempotency_mapping():
    store = InMemorySessionStore()
    sid, _ = store.create_or_get(1, "k")
    store.discard(sid, 1)
    again, created = store.create_or_get(1, "k")
    assert again != sid and created is True


# --- route idempotency (spy generation counts) -------------------------------


class _CountingDomain:
    def __init__(self):
        self.strategies = 0
        self.questions = 0

    def generate_strategy(self, config, settings):
        self.strategies += 1
        from tests.test_api import _strategy, _usage
        return _strategy(), _usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        self.questions += 1
        from tests.test_api import _question, _usage
        return _question(current_question_number), _usage()


@pytest.fixture()
def ctx():
    app = create_app()
    domain = _CountingDomain()
    svc = InterviewApplicationService(config=None, services=(domain, _FakeEval(), _FakeReport(), _FakeClient()))
    repo = _FakeRepo()  # one instance → stable subject→id mapping across requests
    from tests._interview_factories import make_durable_store
    store = make_durable_store()
    app.dependency_overrides[deps.get_interview_service] = lambda: svc
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    return app, domain


PREP = {"preparation_context": {"target_role": "Senior Product Manager", "industry": "Tech", "seniority": "senior"}}
ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}


def test_no_key_creates_two_sessions(ctx):
    app, domain = ctx
    with TestClient(app) as c:
        s1 = c.post("/api/v1/interviews", json=PREP, headers=ALICE).json()["session_id"]
        s2 = c.post("/api/v1/interviews", json=PREP, headers=ALICE).json()["session_id"]
    assert s1 != s2 and domain.strategies == 2 and domain.questions == 2


def test_same_key_returns_same_session_without_regenerating(ctx):
    app, domain = ctx
    hdr = {**ALICE, "Idempotency-Key": "agent-handoff:run_1"}
    with TestClient(app) as c:
        r1 = c.post("/api/v1/interviews", json=PREP, headers=hdr).json()
        r2 = c.post("/api/v1/interviews", json=PREP, headers=hdr).json()
        r3 = c.post("/api/v1/interviews", json=PREP, headers=hdr).json()  # a further retry
    assert r1["session_id"] == r2["session_id"] == r3["session_id"]
    # Generation ran exactly ONCE despite three creates (no duplicate provider work).
    assert domain.strategies == 1 and domain.questions == 1


def test_different_key_creates_different_session(ctx):
    app, _ = ctx
    with TestClient(app) as c:
        a = c.post("/api/v1/interviews", json=PREP, headers={**ALICE, "Idempotency-Key": "k1"}).json()["session_id"]
        b = c.post("/api/v1/interviews", json=PREP, headers={**ALICE, "Idempotency-Key": "k2"}).json()["session_id"]
    assert a != b


def test_same_key_different_users_are_isolated(ctx):
    app, _ = ctx
    hdr_key = "agent-handoff:run_1"
    with TestClient(app) as c:
        a = c.post("/api/v1/interviews", json=PREP, headers={**ALICE, "Idempotency-Key": hdr_key}).json()["session_id"]
        b = c.post("/api/v1/interviews", json=PREP, headers={**BOB, "Idempotency-Key": hdr_key}).json()["session_id"]
    assert a != b


def test_missing_config_returns_422_not_fabricated(ctx):
    app, _ = ctx
    # PreparationContext without industry/seniority → the backend requires them,
    # it never invents "General"/"senior".
    with TestClient(app) as c:
        r = c.post("/api/v1/interviews", json={"preparation_context": {"target_role": "PM"}}, headers=ALICE)
    assert r.status_code == 422


def test_options_endpoint_exposes_career_levels(ctx):
    app, _ = ctx
    from src import constants
    with TestClient(app) as c:
        body = c.get("/api/v1/interviews/options", headers=ALICE).json()
    assert body["career_levels"] == list(constants.CAREER_LEVELS)
    assert "senior" in body["career_levels"] and "executive" in body["career_levels"]
