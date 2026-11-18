"""F1-P1: fenced SQLite operations and durable setup uncertainty, without providers.

The existing version supplies a per-session acquisition generation. The existing
lease column stores the generation and setup intent, leaving the database and
SessionData schemas unchanged. Fault fixtures never open development databases.
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from threading import Event
from unittest.mock import patch

import pytest
from sqlalchemy import event, select

from src import constants
from src.api.routes.interview import _run_setup
from src.application.interview_service import InterviewApplicationService
from src.interview.session_repository import (
    DurableInterviewSessionStore,
    OperationInProgressError,
    SessionConflictError,
    SetupOutcomeUncertainError,
)
from src.interview import session_repository as protocol
from src.persistence import InterviewSession, make_engine, make_session_factory, utcnow
from tests import _interview_factories as f
from tests.test_api import _FakeClient, _FakeEval, _FakeReport
from tests.test_durable_session_store import _factory
from tests.test_interview_idempotency import _CountingDomain


def _service(domain):
    return InterviewApplicationService(config=None, services=(domain, _FakeEval(), _FakeReport(), _FakeClient()))


def test_non_setup_operations_preserve_the_existing_conflict_error_contract():
    from src.api.routes.interview import _translate_store_error
    from src.application.errors import ConflictError

    assert isinstance(_translate_store_error(OperationInProgressError("internal detail")), ConflictError)


def test_claim_cannot_erase_intent_committed_after_its_read(ctx, monkeypatch):
    store, sf, owner, sid, url = ctx
    engine = sf.kw["bind"]
    other_engine = make_engine(url)
    other = DurableInterviewSessionStore(make_session_factory(other_engine))
    prepared, allow_sql, read_ready, generated, allow_save = [Event() for _ in range(5)]
    first, second = _CountingDomain(), _CountingDomain()
    original_guard = other._guard_setup_intent
    observed = False

    def pause_intent(connection, cursor, statement, parameters, context, many):
        values = parameters.values() if isinstance(parameters, dict) else parameters
        if statement.startswith("UPDATE interview_sessions") and any(
            isinstance(value, str) and value.startswith("create@") and value.endswith(":dispatch") for value in values
        ):
            prepared.set()
            assert allow_sql.wait(15)

    def pause_claim(row):
        nonlocal observed
        original_guard(row)
        if not observed:
            observed = True
            read_ready.set()
            assert generated.wait(15)

    def original_worker():
        with store.mutate(sid, owner, operation="create") as session:
            _run_setup(_service(first), session, f.config())
            generated.set()
            assert allow_save.wait(15)

    event.listen(engine, "before_cursor_execute", pause_intent)
    monkeypatch.setattr(other, "_guard_setup_intent", pause_claim)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(original_worker)
            assert prepared.wait(15)
            future = utcnow() + timedelta(seconds=constants.INTERVIEW_OPERATION_LEASE_SECONDS + 5)
            with patch.object(protocol, "utcnow", return_value=future):
                b = pool.submit(_setup, other, owner, sid, second)
                assert read_ready.wait(15)
                allow_sql.set()
                assert generated.wait(15)
                try:
                    with pytest.raises(SetupOutcomeUncertainError):
                        b.result(timeout=15)
                    with sf() as db:
                        row = db.get(InterviewSession, sid)
                        assert row.version == 2 and row.active_operation == "create@2:dispatch"
                finally:
                    allow_save.set()
                a.result(timeout=15)
        assert first.strategies == first.questions == 1
        assert second.strategies == second.questions == 0
        assert store.create_or_get(owner, "practice:fenced-setup") == (sid, False)
    finally:
        allow_sql.set()
        generated.set()
        allow_save.set()
        event.remove(engine, "before_cursor_execute", pause_intent)
        other_engine.dispose()


@pytest.mark.parametrize("expired", [False, True])
def test_delete_cannot_erase_dispatch_committed_after_its_read(ctx, monkeypatch, expired):
    store, sf, owner, sid, _ = ctx
    other = DurableInterviewSessionStore(sf)
    original_guard = store._guard_setup_intent
    held = None
    domain = _CountingDomain()

    def begin_after_delete_check(row):
        nonlocal held
        original_guard(row)
        held = other.mutate(sid, owner, operation="create")
        session = held.__enter__()
        _run_setup(_service(domain), session, f.config())
        if expired:
            _expire(sf, sid)

    monkeypatch.setattr(store, "_guard_setup_intent", begin_after_delete_check)
    try:
        error = SetupOutcomeUncertainError if expired else OperationInProgressError
        with pytest.raises(error):
            store.discard(sid, owner)
        with sf() as db:
            row = db.get(InterviewSession, sid)
            assert row.version == 2 and row.active_operation == "create@2:dispatch"
        assert other.create_or_get(owner, "practice:fenced-setup") == (sid, False)
        assert domain.strategies == domain.questions == 1
    finally:
        if held is not None:
            held.__exit__(None, None, None)
    _setup(other, owner, sid, domain)
    assert domain.strategies == domain.questions == 1


def test_delete_preserves_a_new_non_setup_lease(ctx, monkeypatch):
    store, sf, owner, sid, _ = ctx
    other = DurableInterviewSessionStore(sf)
    original_guard = store._guard_setup_intent
    token = None

    def acquire_after_check(row):
        nonlocal token
        original_guard(row)
        if token is None:
            token = other._claim_lease(sid, owner, "report")

    monkeypatch.setattr(store, "_guard_setup_intent", acquire_after_check)
    with pytest.raises(SessionConflictError):
        store.discard(sid, owner)
    with sf() as db:
        row = db.get(InterviewSession, sid)
        assert row.active_operation == token
    other._release_lease(sid, owner, token)
    other.discard(sid, owner)
    assert other.find_idempotent_session(owner, "practice:fenced-setup") is None


@pytest.fixture
def ctx(tmp_path):
    url = f"sqlite:///{tmp_path / 'sessions.sqlite'}"
    engine, sf, owner, _ = _factory(url)
    store = DurableInterviewSessionStore(sf)
    sid, created = store.create_or_get(owner, "practice:fenced-setup")
    assert created
    yield store, sf, owner, sid, url
    engine.dispose()


def _expire(sf, sid):
    with sf() as db:
        row = db.get(InterviewSession, sid)
        row.operation_leased_at = utcnow() - timedelta(seconds=constants.INTERVIEW_OPERATION_LEASE_SECONDS + 1)
        db.commit()


def _setup(store, owner, sid, domain):
    with store.mutate(sid, owner, operation="create") as session:
        if session.data.state.value == "SETUP" and not session.data.questions:
            _run_setup(_service(domain), session, f.config())


def test_exact_generation_fences_stale_save_release_and_third_claim(ctx):
    store, sf, owner, sid, _ = ctx
    first = store._claim_lease(sid, owner, "create")
    first_version = int(first.split("@", 1)[1])
    data = store.load_state(sid, owner).data
    _expire(sf, sid)
    other = DurableInterviewSessionStore(sf)
    replacement = other._claim_lease(sid, owner, "create")
    assert first != replacement and int(replacement.split("@")[1]) > first_version
    with pytest.raises(SessionConflictError):
        store._save(sid, owner, data, expected_version=first_version, lease=first)
    store._release_lease(sid, owner, first)
    with sf() as db:
        assert db.get(InterviewSession, sid).active_operation == replacement
    with pytest.raises(OperationInProgressError):
        DurableInterviewSessionStore(sf)._claim_lease(sid, owner, "create")
    other._save(sid, owner, data, expected_version=int(replacement.split("@")[1]), lease=replacement)
    with sf() as db:
        assert db.get(InterviewSession, sid).active_operation is None


def test_unleased_writer_cannot_clear_another_workers_lease(ctx):
    store, sf, owner, sid, _ = ctx
    token = store._claim_lease(sid, owner, "create")
    version = int(token.split("@")[1])
    data = store.load_state(sid, owner).data
    with pytest.raises(SessionConflictError):
        store._save(sid, owner, data, expected_version=version)
    with sf() as db:
        assert db.get(InterviewSession, sid).active_operation == token


def test_expired_undispatched_owner_cannot_commit_dispatch_intent(ctx):
    store, sf, owner, sid, _ = ctx
    token = store._claim_lease(sid, owner, "create")
    _expire(sf, sid)
    with pytest.raises(SessionConflictError):
        store._begin_setup_dispatch(sid, owner, token, int(token.split("@")[1]))
    store._release_lease(sid, owner, token)
    domain = _CountingDomain()
    _setup(store, owner, sid, domain)
    assert domain.strategies == domain.questions == 1


def test_live_setup_intent_blocks_takeover_and_stale_release_even_after_expiry(ctx):
    store, sf, owner, sid, _ = ctx
    domain = _CountingDomain()
    with store.mutate(sid, owner, operation="create") as session:
        with sf() as db:
            row = db.get(InterviewSession, sid)
            assert row.active_operation.endswith(":dispatch")
            token = row.active_operation
        _expire(sf, sid)
        for other in (store, DurableInterviewSessionStore(sf)):
            with pytest.raises(SetupOutcomeUncertainError):
                other._claim_lease(sid, owner, "create")
            other._release_lease(sid, owner, token)
        _run_setup(_service(domain), session, f.config())
    assert domain.strategies == domain.questions == 1
    assert store.load_state(sid, owner).data.state.value == "AWAITING_ANSWER"


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_failures_after_intent_retain_usage_and_refuse_retry_after_restart(ctx, failure):
    store, sf, owner, sid, url = ctx
    domain = _CountingDomain()
    expected = SetupOutcomeUncertainError if failure is RuntimeError else failure
    with pytest.raises(expected):
        with store.mutate(sid, owner, operation="create") as session:
            _run_setup(_service(domain), session, f.config())
            raise failure("synthetic cancellation or failure")
    with sf() as db:
        row = db.get(InterviewSession, sid)
        assert row.active_operation.endswith(":hold")
        assert len(row.state_payload["usage_records"]) == 2
    _expire(sf, sid)
    engine = make_engine(url)
    restarted = DurableInterviewSessionStore(make_session_factory(engine))
    try:
        with pytest.raises(SetupOutcomeUncertainError):
            _setup(restarted, owner, sid, domain)
        assert restarted.create_or_get(owner, "practice:fenced-setup") == (sid, False)
        assert restarted.list_active(owner) == []
        assert domain.strategies == domain.questions == 1
    finally:
        engine.dispose()


def test_failed_state_save_keeps_intent_and_known_usage(ctx, monkeypatch):
    store, sf, owner, sid, _ = ctx
    domain = _CountingDomain()

    def failed_save(*args, **kwargs):
        raise RuntimeError("save failed")

    with monkeypatch.context() as m:
        m.setattr(store, "_save", failed_save)
        with pytest.raises(SetupOutcomeUncertainError):
            _setup(store, owner, sid, domain)
    with pytest.raises(SetupOutcomeUncertainError):
        _setup(store, owner, sid, domain)
    with sf() as db:
        row = db.get(InterviewSession, sid)
        assert row.active_operation.endswith(":hold") and len(row.state_payload["usage_records"]) == 2
    assert domain.strategies == domain.questions == 1


def test_lost_successful_save_acknowledgement_recovers_committed_result(ctx, monkeypatch):
    store, sf, owner, sid, _ = ctx
    domain = _CountingDomain()
    save = store._save

    def lost_ack(*args, **kwargs):
        save(*args, **kwargs)
        raise RuntimeError("lost acknowledgement")

    with monkeypatch.context() as m:
        m.setattr(store, "_save", lost_ack)
        with pytest.raises(SetupOutcomeUncertainError):
            _setup(store, owner, sid, domain)
    _setup(DurableInterviewSessionStore(sf), owner, sid, domain)
    assert domain.strategies == domain.questions == 1
    assert store.load_state(sid, owner).data.state.value == "AWAITING_ANSWER"


@pytest.mark.parametrize("committed", [False, True])
def test_intent_commit_failure_never_yields_to_provider_body(ctx, monkeypatch, committed):
    store, sf, owner, sid, _ = ctx
    token = store._claim_lease(sid, owner, "create")
    store._release_lease(sid, owner, token)
    real_commit = sf.class_.commit

    def fail_intent(db):
        row = db.get(InterviewSession, sid)
        if row is not None and (row.active_operation or "").endswith(":dispatch"):
            if committed:
                real_commit(db)
            raise RuntimeError("intent commit acknowledgement failed")
        return real_commit(db)

    calls = []
    with monkeypatch.context() as m:
        m.setattr(sf.class_, "commit", fail_intent)
        with pytest.raises(RuntimeError):
            with store.mutate(sid, owner, operation="create"):
                calls.append("must not dispatch")
    assert calls == []
    if committed:
        _expire(sf, sid)
        with pytest.raises(SetupOutcomeUncertainError):
            _setup(store, owner, sid, _CountingDomain())
    else:
        domain = _CountingDomain()
        _setup(store, owner, sid, domain)
        assert domain.strategies == domain.questions == 1


def test_uncertain_intents_survive_retention_cleanup(ctx):
    store, sf, owner, sid, _ = ctx
    with pytest.raises(SetupOutcomeUncertainError):
        with store.mutate(sid, owner, operation="create"):
            raise RuntimeError("uncertain setup")
    cutoff = utcnow() + timedelta(days=365)
    assert store.count_stale_sessions(cutoff) == 0
    assert store.cleanup_stale_sessions(cutoff) == 0
    assert store.find_idempotent_session(owner, "practice:fenced-setup") == sid
    with pytest.raises(SetupOutcomeUncertainError):
        store.discard(sid, owner)


def test_legacy_unqualified_create_lease_is_held_after_expiry(ctx):
    store, sf, owner, sid, _ = ctx
    with sf() as db:
        row = db.get(InterviewSession, sid)
        row.active_operation = "create"
        row.operation_leased_at = utcnow() - timedelta(days=1)
        db.commit()
    with pytest.raises(SetupOutcomeUncertainError):
        _setup(store, owner, sid, _CountingDomain())
    assert store.find_idempotent_session(owner, "practice:fenced-setup") == sid


def test_failure_before_intent_and_failed_release_preserve_the_primary_error(ctx, monkeypatch):
    store, sf, owner, sid, _ = ctx
    begin = store._begin_setup_dispatch
    commit = sf.class_.commit
    release_started = False

    def before_intent(*args):
        nonlocal release_started
        release_started = True
        raise RuntimeError("original pre-dispatch failure")

    def failed_release(db):
        if release_started:
            raise RuntimeError("release failure")
        return commit(db)

    with monkeypatch.context() as m:
        m.setattr(store, "_begin_setup_dispatch", before_intent)
        m.setattr(sf.class_, "commit", failed_release)
        with pytest.raises(RuntimeError, match="original pre-dispatch failure"):
            _setup(store, owner, sid, _CountingDomain())
    monkeypatch.setattr(store, "_begin_setup_dispatch", begin)
    _expire(sf, sid)
    domain = _CountingDomain()
    _setup(store, owner, sid, domain)
    assert domain.strategies == domain.questions == 1


def test_successful_credential_preflight_retries_a_conclusively_undispatched_key():
    from scripts.e2e import journey_fakes as F
    from tests.test_provider_failures_04d import API, CREATE, _stack, _user

    app, repo, _, _store = _stack("keyless")
    client, cookies = _user(app, "pre-dispatch@example.invalid")
    headers = {"Idempotency-Key": "practice:configuration-refusal"}
    try:
        refused = client.post(f"{API}/interviews", json=CREATE, headers=headers, cookies=cookies)
        assert refused.status_code == 503 and refused.json()["error"]["code"] == "ai_not_configured"
        with repo.session_factory() as db:
            from sqlalchemy import select

            row = db.scalar(select(InterviewSession))
            assert row.idempotency_key == headers["Idempotency-Key"] and row.active_operation is None
        fake = F.install_offline_interview_services(app, "healthy")
        created = client.post(f"{API}/interviews", json=CREATE, headers=headers, cookies=cookies)
        assert created.status_code == 200
        repeated = client.post(f"{API}/interviews", json=CREATE, headers=headers, cookies=cookies)
        assert repeated.json() == created.json()
        assert fake.calls == ["InterviewStrategy", "InterviewQuestion"]
    finally:
        client.close()


def _child(url, sid, owner, stage):
    import tests.conftest  # noqa: F401 - child process uses the same database isolation guard

    if stage in ("claim_race_a", "claim_race_b"):
        return _claim_race_worker(url, sid, int(owner), stage[-1])
    engine = make_engine(url)
    store = DurableInterviewSessionStore(make_session_factory(engine))
    domain = _CountingDomain()

    def boundary(name):
        if stage == name:
            with store._session_factory() as db:
                row = db.get(InterviewSession, sid)
                print(json.dumps({"stage": name, "version": row.version, "lease": row.active_operation,
                                  "strategies": domain.strategies, "questions": domain.questions}), flush=True)
            assert sys.stdin.readline().strip() == "continue"

    service = _service(domain)
    strategy, question = service.generate_strategy, service.generate_next_question

    def slow_strategy(session):
        boundary("during_strategy")
        strategy(session)
        boundary("after_strategy")

    def slow_question(session, *, first=False):
        boundary("during_question")
        question(session, first=first)

    service.generate_strategy = slow_strategy
    service.generate_next_question = slow_question
    try:
        if stage == "acquired":
            store._claim_lease(sid, int(owner), "create")
            boundary("acquired")
            return
        with store.mutate(sid, int(owner), operation="create") as session:
            boundary("intent")
            _run_setup(service, session, f.config())
            boundary("results")
        print(json.dumps({"result": "committed", "strategies": domain.strategies, "questions": domain.questions}), flush=True)
    finally:
        engine.dispose()


def _claim_race_worker(url, sid, owner, label):
    engine = make_engine(url)
    sf = make_session_factory(engine)
    store = DurableInterviewSessionStore(sf)
    domain = _CountingDomain()
    paused = False
    original_guard = store._guard_setup_intent

    def pause_statement(connection, cursor, statement, parameters, context, many):
        nonlocal paused
        values = parameters.values() if isinstance(parameters, dict) else parameters
        if not paused and statement.startswith("UPDATE interview_sessions") and any(
            isinstance(value, str) and value.startswith("create@") and value.endswith(":dispatch") for value in values
        ):
            paused = True
            print(json.dumps({"stage": "prepared"}), flush=True)
            assert sys.stdin.readline().strip() == "continue"

    def pause_read(row):
        nonlocal paused
        original_guard(row)
        if not paused:
            paused = True
            print(json.dumps({"stage": "checked", "lease": row.active_operation, "version": row.version}), flush=True)
            assert sys.stdin.readline().strip() == "continue"

    if label == "a":
        event.listen(engine, "before_cursor_execute", pause_statement)
    else:
        store._guard_setup_intent = pause_read
    future = utcnow() + timedelta(seconds=constants.INTERVIEW_OPERATION_LEASE_SECONDS + 5)
    clock = patch.object(protocol, "utcnow", return_value=future) if label == "b" else nullcontext()
    try:
        with clock:
            with store.mutate(sid, owner, operation="create") as session:
                _run_setup(_service(domain), session, f.config())
                print(json.dumps({"stage": "generated"}), flush=True)
                assert sys.stdin.readline().strip() == "save"
        outcome = "COMMITTED"
    except Exception as exc:
        outcome = type(exc).__name__
    finally:
        engine.dispose()
    print(json.dumps({"result": outcome, "strategies": domain.strategies, "questions": domain.questions}), flush=True)


def test_separate_process_claim_cannot_replace_committed_intent(ctx):
    store, sf, owner, sid, url = ctx
    children = []

    def send(process, value):
        process.stdin.write(value + "\n")
        process.stdin.flush()

    def receive(process):
        line = process.stdout.readline()
        assert line, "the fixture worker ended without its expected observation"
        return json.loads(line)

    try:
        for label in ("a", "b"):
            child = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "worker", url,
                                      sid, str(owner), "claim_race_" + label],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            children.append(child)
            observed = receive(child)
            assert observed["stage"] == ("prepared" if label == "a" else "checked")
        a, b = children
        send(a, "continue")
        assert receive(a) == {"stage": "generated"}
        send(b, "continue")
        assert receive(b) == {"result": "SetupOutcomeUncertainError", "strategies": 0, "questions": 0}
        send(a, "save")
        assert receive(a) == {"result": "COMMITTED", "strategies": 1, "questions": 1}
        with sf() as db:
            row = db.get(InterviewSession, sid)
            assert row.version == 3 and row.active_operation is None
        assert store.create_or_get(owner, "practice:fenced-setup") == (sid, False)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)


@pytest.mark.parametrize("phase", ["dispatch", "expired", "hold"])
def test_all_practice_routes_return_consistent_safe_setup_errors(tmp_path, phase):
    from fastapi.testclient import TestClient
    from src.api import dependencies as deps
    from src.persistence import User
    from tests.test_opportunity_persistence_ac03_04d import API, _approved_handoff, _boot, _install_agent, _opp, _user

    client, repo, fake = _boot(tmp_path / "held-routes.sqlite")
    _install_agent(client, repo, tmp_path / "checkpoints.sqlite")
    safe = TestClient(client.app, raise_server_exceptions=False)
    try:
        cookies, _ = _user(client, "hold-owner@example.invalid")
        foreign, _ = _user(client, "hold-foreign@example.invalid")
        selected = _opp(client, cookies, "Senior Product Manager")
        headers = _approved_handoff(client, cookies, selected["id"])
        with repo.session_factory() as db:
            owner = db.scalar(select(User.id).where(User.email == "hold-owner@example.invalid"))
        store = client.app.dependency_overrides[deps.get_session_store]()
        sid, created = store.create_or_get(owner, headers["Idempotency-Key"], opportunity_id=selected["id"])
        assert created
        token = store._claim_lease(sid, owner, "create")
        version = int(token.split("@")[1])
        data = store.load_state(sid, owner).data
        intent = store._begin_setup_dispatch(sid, owner, token, version)
        if phase == "hold":
            store._retain_setup_hold(sid, owner, intent, version, data)
        elif phase == "expired":
            _expire(store._session_factory, sid)
        code = "interview_operation_in_progress" if phase == "dispatch" else "practice_setup_outcome_uncertain"
        routes = [
            ("GET", "", None), ("DELETE", "", None),
            ("POST", "/answers", {"answer": "SYNTHETIC_PRIVATE_ANSWER"}),
            ("POST", "/next-question", None), ("POST", "/complete", None), ("POST", "/recover", None),
            ("POST", "/deep-dive", {"mode": "deepen_reasoning"}),
            ("POST", "/deep-dive/answers", {"answer": "SYNTHETIC_PRIVATE_ANSWER"}),
            ("POST", "/deep-dive/next", None), ("POST", "/deep-dive/return", None), ("POST", "/report", None),
        ]
        for method, suffix, body in routes:
            options = {"cookies": cookies}
            if body is not None:
                options["json"] = body
            response = safe.request(method, f"{API}/interviews/{sid}{suffix}", **options)
            assert response.status_code == 409 and response.json()["error"]["code"] == code
            assert response.json()["error"]["request_id"]
            assert "SYNTHETIC_PRIVATE_ANSWER" not in response.text and "Traceback" not in response.text
        retry = safe.post(f"{API}/interviews", json={}, headers=headers, cookies=cookies)
        assert retry.status_code == 409 and retry.json()["error"]["code"] == code
        assert safe.get(f"{API}/interviews/{sid}", cookies=foreign).status_code == 422
        safe.delete(f"{API}/interviews/{sid}", cookies=foreign)
        assert store.create_or_get(owner, headers["Idempotency-Key"]) == (sid, False)
        assert store.list_active(owner) == [] and fake.calls == []
        with repo.session_factory() as db:
            row = db.get(InterviewSession, sid)
            assert row.opportunity_id == selected["id"]
            assert row.active_operation.endswith(":hold" if phase == "hold" else ":dispatch")
    finally:
        safe.close()
        client.__exit__(None, None, None)


def test_process_crash_before_intent_is_conclusively_undispatched_and_retryable(ctx):
    store, sf, owner, sid, url = ctx
    child = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "worker", url, sid, str(owner), "acquired"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        boundary = json.loads(child.stdout.readline())
        assert boundary["stage"] == "acquired" and ":" not in boundary["lease"]
        assert boundary["strategies"] == boundary["questions"] == 0
        child.kill()
        child.wait(timeout=10)
        _expire(sf, sid)
        domain = _CountingDomain()
        _setup(DurableInterviewSessionStore(sf), owner, sid, domain)
        assert domain.strategies == domain.questions == 1
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)


@pytest.mark.parametrize("stage", ["intent", "during_strategy", "after_strategy", "during_question", "results"])
def test_process_crash_at_each_setup_boundary_holds_same_key(ctx, stage):
    store, sf, owner, sid, url = ctx
    child = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "worker", url, sid, str(owner), stage],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        boundary = json.loads(child.stdout.readline())
        assert boundary["stage"] == stage and boundary["lease"].endswith(":dispatch")
        child.kill()
        child.wait(timeout=10)
        _expire(sf, sid)
        retry = _CountingDomain()
        with pytest.raises(SetupOutcomeUncertainError):
            _setup(DurableInterviewSessionStore(sf), owner, sid, retry)
        assert retry.strategies == retry.questions == 0
        assert store.create_or_get(owner, "practice:fenced-setup") == (sid, False)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)


@pytest.mark.parametrize("stage", ["during_strategy", "during_question"])
def test_live_process_with_expired_intent_allows_no_replacement_dispatch(ctx, stage):
    store, sf, owner, sid, url = ctx
    child = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "worker", url, sid, str(owner), stage],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        boundary = json.loads(child.stdout.readline())
        assert boundary["stage"] == stage
        _expire(sf, sid)
        retry = _CountingDomain()
        with pytest.raises(SetupOutcomeUncertainError):
            _setup(DurableInterviewSessionStore(sf), owner, sid, retry)
        assert retry.strategies == retry.questions == 0
        child.stdin.write("continue\n")
        child.stdin.flush()
        assert json.loads(child.stdout.readline()) == {"result": "committed", "strategies": 1, "questions": 1}
        child.wait(timeout=10)
        _setup(store, owner, sid, retry)
        assert retry.strategies == retry.questions == 0
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)


@pytest.mark.parametrize("step", ["InterviewStrategy", "InterviewQuestion"])
def test_two_application_instances_share_one_setup_and_recover_after_response(ctx, tmp_path, monkeypatch, step):
    from tests.test_opportunity_persistence_ac03_04d import API, _approved_handoff, _boot, _install_agent, _opp, _user

    db = tmp_path / "two-apps.sqlite"
    first, repo, fake = _boot(db)
    second, other_repo, other_fake = _boot(db)
    _install_agent(first, repo, tmp_path / "checkpoints.sqlite")
    _install_agent(second, other_repo, tmp_path / "checkpoints.sqlite")
    entered, finish = Event(), Event()
    callback = fake.create_chat_completion

    def slow_callback(**kwargs):
        schema = ((kwargs.get("response_format") or {}).get("json_schema") or {}).get("name")
        if schema == step:
            entered.set()
            assert finish.wait(10)
        return callback(**kwargs)

    monkeypatch.setattr(fake, "create_chat_completion", slow_callback)
    try:
        cookies, _ = _user(first, "two-apps@example.invalid")
        opp = _opp(first, cookies, "Senior Product Manager")
        headers = _approved_handoff(first, cookies, opp["id"])
        body = {"industry_or_sector": "Software", "career_level": "senior", "number_of_questions": 1}
        with ThreadPoolExecutor(max_workers=1) as pool:
            one = pool.submit(first.post, f"{API}/interviews", json=body, headers=headers, cookies=cookies)
            assert entered.wait(10)
            refused = second.post(f"{API}/interviews", json=body, headers=headers, cookies=cookies)
            assert refused.status_code == 409 and refused.json()["error"]["code"] == "interview_operation_in_progress"
            assert other_fake.calls == []
            finish.set()
            created = one.result(timeout=10)
        assert created.status_code == 200
        reopened = second.post(f"{API}/interviews", json={}, headers=headers, cookies=cookies)
        assert reopened.status_code == 200 and reopened.json() == created.json()
        assert fake.calls == ["InterviewStrategy", "InterviewQuestion"] and other_fake.calls == []
        sid = created.json()["session_id"]
        with other_repo.session_factory() as db_session:
            assert db_session.get(InterviewSession, sid).opportunity_id == opp["id"]
    finally:
        finish.set()
        first.__exit__(None, None, None)
        second.__exit__(None, None, None)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "worker":
    _child(*sys.argv[2:])
