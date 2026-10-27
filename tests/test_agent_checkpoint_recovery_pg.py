"""Real PG16 outages, official saver, unchanged graphs, synthetic providers only.

Opt-in runner owns the labelled RAM-backed server; no arbitrary server control.
The ordinary suite reports these cases NOT RUN unless the explicit flag is set.
"""

from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import multiprocessing
import os
import threading
import time
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from fastapi import Request

ENABLED = os.environ.get("RUN_CHECKPOINT_RECOVERY_PG") == "1"
pytestmark = pytest.mark.skipif(
    not ENABLED,
    reason="disposable PostgreSQL checkpoint outage qualification NOT RUN; use its opt-in runner",
)


def _calls_model(calls, entered=None, release=None):
    from tests.test_agent_durable_admission import Model

    class Controlled(Model):
        def invoke(self, messages):
            if entered is not None:
                entered.set()
                assert release.wait(15), "synthetic_producer_release_timeout"
            return super().invoke(messages)

    return Controlled(calls)


@pytest.fixture
def env():
    from tests.test_pg_05b import _create_db, _drop_db, _alembic
    from src.persistence import User, make_engine, make_session_factory
    from src.privacy.preparation import PreparationRunIndex
    from src.application.agent_service import AgentApplicationService
    from src.agent.eval import build_eval_career
    from tests.test_agent_hitl import FakeCareer

    name, url = _create_db("p5b_checkpoint_recovery")
    result = _alembic(url, "upgrade", "head")
    assert result.returncode == 0, "disposable_migration_failed"
    engine = make_engine(url)
    sf = make_session_factory(engine)
    with sf() as session:
        session.add_all(
            [
                User(id=1, subject="synthetic-owner", provider="test"),
                User(id=2, subject="synthetic-other", provider="test"),
            ]
        )
        session.commit()
    services, calls = [], []

    def build(factory=None, *, hitl=False, legacy=False):
        service = AgentApplicationService(
            model_factory=factory or (lambda: _calls_model(calls)),
            career_service=FakeCareer(ambiguous=True) if hitl else build_eval_career(),
            checkpoint_url=url,
            database_url=url,
            run_index=None if legacy else PreparationRunIndex(sf),
            usage_session_factory=None if legacy else sf,
        )
        services.append(service)
        return service

    e = SimpleNamespace(
        url=url, name=name, sf=sf, engine=engine, build=build, calls=calls
    )
    try:
        yield e
    finally:
        from scripts.checkpoint_recovery.disposable import control
        import psycopg

        try:
            with psycopg.connect(_pq(url), autocommit=True, connect_timeout=2):
                pass
        except psycopg.Error:
            control("start")
        for service in services:
            service._checkpoint_resource.close()
        engine.dispose()
        _drop_db(name)


def _pq(url):
    return url.replace("postgresql+psycopg:", "postgresql:")


def _run(service):
    from src.agent.models import AgentRunRequest

    return service.run(
        AgentRunRequest(goal="Synthetic checkpoint recovery", user_id="1")
    )


def _sql(env, query, args=None):
    import psycopg

    with psycopg.connect(_pq(env.url), autocommit=True, connect_timeout=2) as conn:
        return (
            conn.execute(query, args).fetchall()
            if query.lstrip().upper().startswith(("SELECT", "SHOW"))
            else conn.execute(query, args)
        )


def _digest(env):
    tables = (
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "agent_run_controls",
        "ai_usage_facts",
        "preparation_runs",
    )
    rows = []
    for table in tables:
        rows += [
            table + row[0]
            for row in _sql(
                env, "SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"
            )
        ]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def _restart():
    from scripts.checkpoint_recovery.disposable import control

    control("stop")
    control("start")


def _interrupt(env):
    _sql(
        env,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND state='idle' AND pid<>pg_backend_pid()",
    )


@contextmanager
def _client(env, service, owner=1):
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.config import ApiSettings
    from src.api import dependencies as D
    from src.repository import InterviewRepository

    app = create_app(ApiSettings(env="test"))
    app.dependency_overrides[D.get_repository] = lambda: InterviewRepository(env.sf)
    app.dependency_overrides[D.get_agent_service] = lambda: service

    def identity(request: Request):
        return int(request.headers.get("X-Test-Owner", str(owner)))

    app.dependency_overrides[D.get_current_user_id] = identity
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_original_single_connection_retains_failure_and_records_survive(env):
    from langgraph.checkpoint.postgres import PostgresSaver
    from src.application.agent_service import AgentApplicationService
    from src.agent.eval import build_eval_career
    from src.privacy.preparation import PreparationRunIndex

    with PostgresSaver.from_conn_string(_pq(env.url)) as saver:
        saver.setup()
        old = AgentApplicationService(
            model_factory=lambda: _calls_model(env.calls),
            career_service=build_eval_career(),
            checkpointer=saver,
            checkpoint_durable=True,
            run_index=PreparationRunIndex(env.sf),
            usage_session_factory=env.sf,
        )
        result = _run(old)
        before = _digest(env)
        with _client(env, old) as client:
            assert client.get("/api/v1/agent/runs/" + result.run_id).status_code == 200
            _interrupt(env)
            assert client.get("/api/v1/ready").status_code == 200
            assert client.get("/api/v1/agent/runs/" + result.run_id).status_code == 500
        assert env.build().get_run(result.run_id, "1").status == "completed"
        assert len(env.calls) == 1 and _digest(env) == before


@pytest.mark.parametrize("fault", ["terminate", "restart"])
def test_original_service_recovers_read_without_replay_or_record_changes(env, fault):
    from src.application.agent_service import RunNotFoundError

    a = env.build()
    result = _run(a)
    identity = (id(a._graph), id(a._checkpointer), id(a._checkpoint_resource))
    before = _digest(env)
    _interrupt(env) if fault == "terminate" else _restart()
    with _client(env, a) as client:
        assert client.get("/api/v1/ready").status_code == 200
        assert client.get("/api/v1/agent/runs/" + result.run_id).status_code == 200
        assert (
            client.get(
                "/api/v1/agent/runs/" + result.run_id, headers={"X-Test-Owner": "2"}
            ).status_code
            == 404
        )
    with pytest.raises(RunNotFoundError):
        a.get_run(result.run_id, "2")
    assert identity == (id(a._graph), id(a._checkpointer), id(a._checkpoint_resource))
    assert _digest(env) == before and len(env.calls) == 1


def test_long_outage_refuses_with_finite_bound_and_recovers_same_service(env):
    from scripts.checkpoint_recovery.disposable import control

    service = env.build()
    result = _run(service)
    before = _digest(env)
    control("stop")
    with _client(env, service) as client:
        for _ in range(2):
            start = time.monotonic()
            response = client.get("/api/v1/agent/runs/" + result.run_id)
            assert response.status_code == 503 and time.monotonic() - start < 5
            body = response.json()
            assert body["error"]["code"] == "agent_checkpoint_unavailable"
            assert all(
                word not in response.text
                for word in ("synthetic-test-only", "127.0.0.1", "postgresql://")
            )
    control("start")
    assert service.get_run(result.run_id, "1").status == "completed"
    assert before == _digest(env) and len(env.calls) == 1


def test_repeated_disconnects_remain_bounded_and_do_not_mutate_state(env):
    service = env.build()
    result = _run(service)
    before = _digest(env)
    for _ in range(3):
        _restart()
        assert service.get_run(result.run_id, "1").status == "completed"
    assert _digest(env) == before and len(env.calls) == 1


def test_two_services_and_concurrent_readers_recover_without_replacement(env):
    a, b = env.build(), env.build()
    result = _run(a)
    before = _digest(env)
    ids = [id(x._checkpointer) for x in (a, b)]
    _restart()
    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(
            executor.map(
                lambda i: (a if i % 2 else b).get_run(result.run_id, "1").status,
                range(24),
            )
        )
    assert statuses == ["completed"] * 24 and ids == [
        id(x._checkpointer) for x in (a, b)
    ]
    assert len(env.calls) == 1 and before == _digest(env)


@pytest.mark.parametrize("mode", ["sync", "stream"])
def test_running_producer_survives_recovery_without_resource_replacement(
    env, mode, monkeypatch
):
    from src.agent.errors import AgentCheckpointUnavailable
    from src.application.agent_service import RunNotResumableError
    from src.persistence import AgentRunControl

    entered, release = threading.Event(), threading.Event()
    a = env.build(lambda: _calls_model(env.calls, entered, release))
    b = env.build()
    graph, saver = a._graph, a._checkpointer
    close = []
    realclose = a._checkpoint_resource.saver.conn.close
    monkeypatch.setattr(
        a._checkpoint_resource.saver.conn,
        "close",
        lambda *args, **kw: (close.append(1), realclose(*args, **kw))[1],
    )

    def exercise():
        assert entered.wait(10)
        with env.sf() as session:
            rid = session.scalar(select(AgentRunControl.run_id))
        try:
            from scripts.checkpoint_recovery.disposable import control

            control("stop")
            with pytest.raises(AgentCheckpointUnavailable):
                b.get_run(rid, "1")
            control("start")
            with pytest.raises(RunNotResumableError):
                b.continue_run(rid, "1", "Synthetic competing continuation")
            assert a._graph is graph and a._checkpointer is saver and not close
        finally:
            release.set()
        return rid

    if mode == "sync":
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run, a)
            exercise()
            assert future.result(timeout=15).status == "completed"
    else:

        async def drive():
            from src.agent.models import AgentRunRequest

            manager = a.streaming()
            rid = await manager.start(
                AgentRunRequest(goal="Synthetic streaming", user_id="1"), None
            )
            await asyncio.to_thread(exercise)
            await asyncio.wait_for(asyncio.gather(*tuple(manager.tasks)), 15)
            assert a.get_run(rid, "1").status == "completed"

        asyncio.run(drive())
    assert len(env.calls) == 1 and not close


def test_ambiguous_checkpoint_write_is_not_replayed_and_unsettled_cannot_continue(env):
    from src.agent.errors import AgentError
    from src.application.agent_service import RunNotResumableError
    from src.persistence import AgentRunControl
    from tests.test_agent_durable_admission import fact

    service = env.build()
    result = _run(service)
    old = fact(env, result.run_id)
    persisted_before = _sql(
        env, "SELECT row_to_json(t)::text FROM checkpoints t ORDER BY 1"
    )
    entered, release = threading.Event(), threading.Event()
    continued = env.build(lambda: _calls_model(env.calls, entered, release))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            continued.continue_run, result.run_id, "1", "Synthetic second turn"
        )
        assert entered.wait(10)
        _sql(
            env,
            "CREATE FUNCTION checkpoint_test_delay() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(10); RETURN NEW; END $$",
        )
        _sql(
            env,
            "CREATE TRIGGER checkpoint_test_delay BEFORE INSERT ON checkpoints FOR EACH ROW EXECUTE FUNCTION checkpoint_test_delay()",
        )
        release.set()
        for _ in range(100):
            rows = _sql(
                env,
                "SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND application_name='ask4mo_agent_checkpoint' AND wait_event='PgSleep'",
            )
            if rows:
                break
            time.sleep(0.02)
        assert rows, "actual_checkpoint_write_not_observed"
        _sql(env, "SELECT pg_terminate_backend(%s)", (rows[0][0],))
        with pytest.raises(AgentError):
            future.result(timeout=15)
    _sql(env, "DROP TRIGGER checkpoint_test_delay ON checkpoints")
    _sql(env, "DROP FUNCTION checkpoint_test_delay()")
    assert len(env.calls) == 2
    with env.sf() as session:
        row = session.get(AgentRunControl, result.run_id)
        assert row.settled is False
    after = fact(env, result.run_id)
    assert after[0] >= old[0] and after[2] is None and after[3] == "unknown"
    assert set(persisted_before).issubset(
        set(_sql(env, "SELECT row_to_json(t)::text FROM checkpoints t ORDER BY 1"))
    )
    before = _digest(env)
    with pytest.raises(RunNotResumableError):
        env.build().continue_run(result.run_id, "1", "No unsafe retry")
    assert before == _digest(env) and len(env.calls) == 2
    public = service.get_run(result.run_id, "1")
    assert (
        public.usage["usage_complete"] is False
        and public.usage["estimated_cost_usd"] is None
    )


def test_hitl_authorization_and_duplicate_resume_survive_restart(env):
    from tests.test_agent_durable_admission import hitl_model, decision
    from src.application.agent_service import RunNotFoundError, RunNotResumableError

    service = env.build(hitl_model, hitl=True)
    result = _run(service)
    action = result.pending_action.copy()
    before = _digest(env)
    _restart()
    read = service.get_run(result.run_id, "1")
    assert read.pending_action == action and _digest(env) == before
    with pytest.raises(RunNotFoundError):
        service.resume(result.run_id, "2", decision(result))
    completed = service.resume(result.run_id, "1", decision(result))
    assert completed.status == "completed"
    with pytest.raises(RunNotResumableError):
        service.resume(result.run_id, "1", decision(result))


@pytest.mark.parametrize("legacy", [False, True])
def test_database_quarantine_still_blocks_existing_service_after_physical_recovery(
    env, legacy
):
    from src.agent.errors import AgentCheckpointUnavailable

    service = env.build(legacy=legacy)
    result = _run(service)
    before = _digest(env)
    import psycopg
    from psycopg import sql

    with psycopg.connect(_pq(env.url), autocommit=True) as conn:
        conn.execute(
            sql.SQL("ALTER DATABASE {} SET ask4mo.recovery_pending = 'on'").format(
                sql.Identifier(env.name)
            )
        )
    _restart()
    assert _sql(env, "SELECT 1") == [(1,)]
    with pytest.raises(AgentCheckpointUnavailable):
        service.get_run(result.run_id, "1")
    with _client(env, service) as client:
        assert client.get("/api/v1/agent/runs/" + result.run_id).status_code == 503
    assert _digest(env) == before
    assert _sql(env, "SELECT current_setting('ask4mo.recovery_pending',true)") == [
        ("on",)
    ]


def test_sse_readonly_reconnection_preserves_usage_after_database_restart(env):
    service = env.build()
    result = _run(service)
    manager = service.streaming()
    before = _digest(env)
    graph = manager.graph
    _restart()

    async def read():
        return [event async for event in manager.events(result.run_id, "1")]

    first, second = asyncio.run(read()), asyncio.run(read())
    assert first and second and any("event: result" in item for item in first)
    assert manager.graph is graph and len(env.calls) == 1 and _digest(env) == before


def test_privacy_official_thread_deletion_works_after_recovery(env):
    from src.privacy.preparation import CheckpointAdapter

    service = env.build()
    result = _run(service)
    adapter = CheckpointAdapter(service._checkpointer)
    _restart()
    assert adapter.owner_of(result.run_id) == "1"
    assert adapter.purge_run(result.run_id)
    assert service._checkpointer.get_tuple(service._config(result.run_id)) is None


def test_unknown_usage_reservations_and_kill_switch_are_unchanged(env):
    from src.llm.budget.config import parse_config
    from src.llm.budget.ledger import DbBudgetLedger
    from tests.test_budget_task05 import synthetic_config, reserve
    from src.application.agent_service import RunNotResumableError

    service = env.build()
    service._record_usage = lambda result, owner: False
    result = _run(service)
    ledger, cfg = DbBudgetLedger(env.sf), parse_config(synthetic_config())
    unknown = reserve(ledger, cfg, fingerprint="synthetic-unknown")
    ledger.settle(unknown, outcome="unknown")
    reserve(ledger, cfg, fingerprint="synthetic-reserved")
    ledger.kill("synthetic-recovery-test")
    snapshot = ledger.snapshot(cfg, "production")
    assert snapshot["killed"] and snapshot["unknown_held_usd"] != "0.000000"
    tables = ("ai_budget_entries", "ai_budget_controls")

    def rows():
        return [
            _sql(env, "SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1")
            for table in tables
        ]

    budget_before, run_before = rows(), _digest(env)
    _restart()
    visible = service.get_run(result.run_id, "1")
    assert (
        not visible.usage["usage_complete"]
        and visible.usage["estimated_cost_usd"] is None
    )
    with pytest.raises(RunNotResumableError):
        env.build().continue_run(result.run_id, "1", "No unknown-usage takeover")
    assert ledger.snapshot(cfg, "production") == snapshot
    assert rows() == budget_before and _digest(env) == run_before
    assert len(env.calls) == 1


def _recovered_process(url, rid, ready, start, entered, release, output, counter):
    """Independent API/worker-shaped consumers; real graphs and DB arbitration."""
    import tests.conftest  # noqa: F401 - isolate provider/environment state
    from src.application.agent_service import (
        AgentApplicationService,
        RunNotResumableError,
    )
    from src.agent.eval import build_eval_career
    from src.persistence import make_engine, make_session_factory
    from src.privacy.preparation import PreparationRunIndex
    from tests.test_agent_durable_admission import Model

    class ProcessModel(Model):
        def invoke(self, messages):
            with counter.get_lock():
                counter.value += 1
            entered.set()
            assert release.wait(30)
            return super().invoke(messages)

    engine = make_engine(url)
    sf = make_session_factory(engine)
    service = AgentApplicationService(
        model_factory=lambda: ProcessModel(),
        career_service=build_eval_career(),
        checkpoint_url=url,
        database_url=url,
        run_index=PreparationRunIndex(sf),
        usage_session_factory=sf,
    )
    try:
        service.get_run(rid, "1")
        ready.put("ready")
        assert start.wait(30)
        try:
            completed = service.continue_run(
                rid, "1", "Synthetic independent continuation"
            )
            output.put(("completed", completed.usage))
        except RunNotResumableError:
            output.put("conflict")
    except Exception as exc:
        output.put(type(exc).__name__)  # never serialize exception text/DSNs
    finally:
        service._checkpoint_resource.close()
        engine.dispose()


@pytest.mark.parametrize("unsettled", [False, True])
def test_independent_process_competition_after_recovery(env, unsettled):
    from src.agent.run_control import RunControlStore
    from tests.test_agent_durable_admission import fact

    service = env.build()
    result = _run(service)
    prior_fact = fact(env, result.run_id)
    if unsettled:
        RunControlStore(env.sf).claim(result.run_id, "1", required=True)
    before = _digest(env)
    _restart()
    ctx = multiprocessing.get_context("spawn")
    ready, output = ctx.Queue(), ctx.Queue()
    start, entered, release = ctx.Event(), ctx.Event(), ctx.Event()
    counter = ctx.Value("i", 0)
    workers = [
        ctx.Process(
            target=_recovered_process,
            args=(
                env.url,
                result.run_id,
                ready,
                start,
                entered,
                release,
                output,
                counter,
            ),
        )
        for _ in range(2)
    ]
    for process in workers:
        process.start()
    try:
        assert [ready.get(timeout=30) for _ in workers] == ["ready", "ready"]
        start.set()
        assert output.get(timeout=30) == "conflict"
        if unsettled:
            assert output.get(timeout=30) == "conflict" and counter.value == 0
            assert before == _digest(env) and fact(env, result.run_id) == prior_fact
        else:
            assert entered.wait(10) and counter.value == 1
            release.set()
            completed = output.get(timeout=30)
            assert completed[0] == "completed"
            after = fact(env, result.run_id)
            assert after[0] == 2 and after[1] == 18 and after[2] == 1800
        for process in workers:
            process.join(10)
            assert process.exitcode == 0
    finally:
        release.set()
        for process in workers:
            if process.is_alive():
                process.terminate()
            process.join(10)
        ready.close()
        output.close()
