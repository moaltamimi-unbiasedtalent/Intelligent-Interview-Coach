"""Cross-instance producer admission: real checkpoints, synthetic models, isolated DBs.

PostgreSQL cases require P5B_PG_ADMIN_URL (loopback disposable test server only).
They create/drop their own p5b_* databases and apply real migrations.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import multiprocessing
import os
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import Request
from langchain_core.messages import AIMessage
from sqlalchemy import select

from src.agent.checkpoint import build_checkpointer
from src.agent.eval import build_eval_career
from src.agent.models import AgentRunRequest
from src.agent.run_control import RunControlStore
from src.application.agent_service import AgentApplicationService, RunNotFoundError, RunNotResumableError
from src.persistence import AIUsageFact, Base, User, make_engine, make_session_factory
from src.privacy.preparation import PreparationRunIndex
from tests.test_agent_hitl import FakeCareer, _scripted


class Model:
    def __init__(self, calls=None):
        self.calls = calls

    def bind_tools(self, schemas):
        return self

    def invoke(self, messages):
        if self.calls is not None:
            self.calls.append(1)
        return AIMessage(content="Synthetic answer.", response_metadata={"cost": 0.0009},
                         usage_metadata={"input_tokens": 5, "output_tokens": 4, "total_tokens": 9})


@pytest.fixture(params=["sqlite", "postgres"])
def environment(request, tmp_path):
    resources = []
    pg_name = None
    if request.param == "postgres":
        if not os.environ.get("P5B_PG_ADMIN_URL"):
            pytest.skip("disposable loopback PostgreSQL not configured")
        from tests.test_pg_05b import _alembic, _create_db, _drop_db, _skip_reason
        assert _skip_reason() is None
        pg_name, url = _create_db("p5b_admission")
        migrated = _alembic(url, "upgrade", "head")
        assert migrated.returncode == 0, "disposable PostgreSQL migration failed"
    else:
        url = f"sqlite:///{tmp_path / 'application.sqlite'}"
    engine = make_engine(url)
    if request.param == "sqlite":
        Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        s.add_all([User(id=1, subject="synthetic-one", provider="test"),
                   User(id=2, subject="synthetic-two", provider="test")])
        s.commit()

    def build(factory=None, hitl=False):
        info = build_checkpointer(database_url=url)
        resources.append(info)
        return AgentApplicationService(model_factory=factory or (lambda: Model()),
            career_service=FakeCareer(ambiguous=True) if hitl else build_eval_career(),
            checkpointer=info.saver, checkpoint_durable=True,
            run_index=PreparationRunIndex(sf), usage_session_factory=sf)

    try:
        yield SimpleNamespace(sf=sf, build=build, url=url, kind=request.param, tmp=tmp_path)
    finally:
        for resource in resources:
            resource.close()
        engine.dispose()
        if pg_name:
            _drop_db(pg_name)


def fact(env, rid):
    with env.sf() as s:
        row = s.scalar(select(AIUsageFact).where(AIUsageFact.usage_key == "agent:" + rid))
        return (row.model_calls, row.total_tokens, row.cost_usd_micros, row.cost_coverage) if row else None


def hitl_model():
    return _scripted(("SearchCareerKnowledge", {"query": "pm interview"}))


def decision(result):
    return {"action_id": result.pending_action["action_id"], "decision": "select", "selected_role": "Product Manager"}


@pytest.mark.parametrize("hitl", [False, True])
def test_unsettled_checkpoint_refuses_second_service_without_mutation(environment, hitl):
    env = environment
    calls = []
    first = env.build(hitl_model if hitl else lambda: Model(calls), hitl=hitl)
    other = env.build(hitl_model if hitl else lambda: Model(calls), hitl=hitl)
    entered, release = threading.Event(), threading.Event()
    record = first._record_usage

    def hold(result, owner):
        entered.set()
        assert release.wait(20)
        return record(result, owner)
    first._record_usage = hold

    async def scenario():
        manager = first.streaming()
        rid = await manager.start(AgentRunRequest(goal="Prepare", user_id="1"))
        try:
            assert await asyncio.to_thread(entered.wait, 15)
            row = manager.controls.owned(rid, "1")
            assert row["status"] == "running" and not row["settled"]
            before = other._snapshot(rid)
            before_fact = fact(env, rid)
            with pytest.raises(RunNotResumableError):
                if hitl:
                    result = other.get_run(rid, "1")
                    other.resume(rid, "1", decision(result))
                else:
                    other.continue_run(rid, "1", "Next synthetic turn")
            after = other._snapshot(rid)
            assert after.values == before.values and after.config == before.config
            assert fact(env, rid) == before_fact
            if not hitl:
                assert calls == [1]
            with pytest.raises(RunNotFoundError):
                other.continue_run(rid, "2", "Foreign")
        finally:
            release.set()
            await asyncio.gather(*list(manager.tasks))
        if hitl:
            resumed = other.resume(rid, "1", decision(other.get_run(rid, "1")))
            assert resumed.status == "completed" and not resumed.awaiting_human_input
        else:
            continued = other.continue_run(rid, "1", "Next synthetic turn")
            assert continued.usage["model_calls"] == 2 and continued.usage["total_tokens"] == 18
            assert fact(env, rid) == (2, 18, 1800, "complete")
        assert manager.controls.owned(rid, "1")["settled"]
    asyncio.run(scenario())


@pytest.mark.parametrize("hitl", [False, True])
def test_concurrent_turns_have_one_winner_until_usage_settles(environment, hitl):
    env = environment
    first = env.build(hitl_model if hitl else None, hitl=hitl)
    result = first.run(AgentRunRequest(goal="Prepare", user_id="1"))
    other = env.build(hitl_model if hitl else None, hitl=hitl)
    entered, release = threading.Event(), threading.Event()
    record = first._record_usage
    def hold(value, owner):
        entered.set()
        assert release.wait(20)
        return record(value, owner)
    first._record_usage = hold
    def advance(service):
        if hitl:
            return service.resume(result.run_id, "1", decision(result))
        return service.continue_run(result.run_id, "1", "Next")
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(advance, first)
        try:
            assert entered.wait(15)
            with pytest.raises(RunNotResumableError):
                advance(other)
            with pytest.raises(RunNotResumableError):
                advance(first)  # local lock is nonblocking defense in depth
            with pytest.raises(RunNotFoundError):
                first.continue_run(result.run_id, "2", "Foreign busy run")
        finally:
            release.set()
        assert pending.result(timeout=20).status == "completed"
    if not hitl:
        assert fact(env, result.run_id) == (2, 18, 1800, "complete")


def test_invalid_decision_releases_claim_and_preserves_checkpoint(environment):
    env = environment
    svc = env.build(hitl_model, hitl=True)
    result = svc.run(AgentRunRequest(goal="Prepare", user_id="1"))
    before = svc._snapshot(result.run_id)
    from src.application.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.resume(result.run_id, "1", {"action_id": "wrong", "decision": "select"})
    assert svc._snapshot(result.run_id).values == before.values
    assert RunControlStore(env.sf).owned(result.run_id, "1")["settled"]
    assert svc.resume(result.run_id, "1", decision(result)).status == "completed"


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_stop_during_settlement_preserves_actual_cost_and_blocks_new_turn(environment, stop):
    env = environment
    first, other = env.build(), env.build()
    entered, release = threading.Event(), threading.Event()
    record = first._record_usage
    def hold(value, owner):
        entered.set()
        assert release.wait(20)
        return record(value, owner)
    first._record_usage = hold
    async def scenario():
        manager = first.streaming()
        rid = await manager.start(AgentRunRequest(goal="Prepare", user_id="1"))
        try:
            assert await asyncio.to_thread(entered.wait, 15)
            if stop == "cancel":
                manager.controls.cancel(rid, "1")
            else:
                RunControlStore(env.sf, clock=lambda: time.time() + 10000).probe(rid)
            pending = other.get_run(rid, "1")
            assert not pending.usage["usage_complete"] and pending.usage["estimated_cost_usd"] is None
            with pytest.raises(RunNotResumableError):
                other.continue_run(rid, "1", "Next")
        finally:
            release.set()
            await asyncio.gather(*list(manager.tasks))
        assert fact(env, rid) == (1, 9, 900, "complete")
        assert other.get_run(rid, "1").status == ("cancelled" if stop == "cancel" else "expired")
        with pytest.raises(RunNotResumableError):
            other.continue_run(rid, "1", "Next")
    asyncio.run(scenario())


def test_recording_failure_remains_unsettled_and_unknown(environment):
    env = environment
    first, other = env.build(), env.build()
    first._record_usage = lambda result, owner: False
    result = first.run(AgentRunRequest(goal="Prepare", user_id="1"))
    row = RunControlStore(env.sf).owned(result.run_id, "1")
    assert row["status"] == "failed" and not row["settled"]
    visible = other.get_run(result.run_id, "1")
    assert not visible.usage["usage_complete"] and visible.usage["estimated_cost_usd"] is None
    with pytest.raises(RunNotResumableError):
        other.continue_run(result.run_id, "1", "Next")
    assert fact(env, result.run_id) is None  # never write invented zero usage


def test_missing_required_control_cannot_be_recreated(environment):
    env = environment
    svc = env.build()
    result = svc.run(AgentRunRequest(goal="Prepare", user_id="1"))
    from src.persistence import AgentRunControl
    with env.sf() as s:
        s.delete(s.get(AgentRunControl, result.run_id))
        s.commit()
    before = svc._snapshot(result.run_id)
    with pytest.raises(RunNotResumableError):
        svc.continue_run(result.run_id, "1", "Next")
    assert svc._snapshot(result.run_id).values == before.values


def _process_turn(url, rid, entered, release, output):
    """Spawn target constructs entirely new service/DB/checkpoint connections."""
    import tests.conftest  # noqa: F401 - prevent .env/provider/development persistence
    engine = make_engine(url)
    sf = make_session_factory(engine)
    info = build_checkpointer(database_url=url)
    svc = AgentApplicationService(model_factory=lambda: Model(), career_service=build_eval_career(),
        checkpointer=info.saver, checkpoint_durable=True, run_index=PreparationRunIndex(sf), usage_session_factory=sf)
    record = svc._record_usage
    def hold(result, owner):
        entered.set()
        assert release.wait(30)
        return record(result, owner)
    svc._record_usage = hold
    try:
        svc.continue_run(rid, "1", "Independent process")
        output.put("completed")
    except RunNotResumableError:
        output.put("conflict")
    finally:
        info.close()
        engine.dispose()


def test_independent_processes_cannot_overlap_and_interruption_is_not_reclaimed(environment):
    env = environment
    first = env.build()
    result = first.run(AgentRunRequest(goal="Prepare", user_id="1"))
    ctx = multiprocessing.get_context("spawn")
    entered, release, output = ctx.Event(), ctx.Event(), ctx.Queue()
    producer = ctx.Process(target=_process_turn, args=(env.url, result.run_id, entered, release, output))
    producer.start()
    try:
        assert entered.wait(25)
        other = env.build()
        before = other._snapshot(result.run_id)
        with pytest.raises(RunNotResumableError):
            other.continue_run(result.run_id, "1", "Overlapping process")
        assert other._snapshot(result.run_id).values == before.values
        visible = other.get_run(result.run_id, "1")
        assert visible.usage["estimated_cost_usd"] is None and not visible.usage["usage_complete"]
        # Hard loss while usage is still unsettled: deadline never authorizes a takeover.
        producer.terminate()
        producer.join(10)
        store = RunControlStore(env.sf, clock=lambda: time.time() + 10000)
        assert store.probe(result.run_id) == "expired"
        assert not store.owned(result.run_id, "1")["settled"]
        with pytest.raises(RunNotResumableError):
            other.continue_run(result.run_id, "1", "Retry after loss")
        assert fact(env, result.run_id) == (1, 9, 900, "complete")  # previous actual call remains
        visible = other.get_run(result.run_id, "1")
        assert visible.usage["estimated_cost_usd"] is None and not visible.usage["usage_complete"]
    finally:
        # Never acquire a multiprocessing Event lock after forcibly killing its waiter.
        if producer.is_alive():
            producer.terminate()
        producer.join(10)
        output.close()


@pytest.mark.parametrize("hitl", [False, True])
def test_http_conflict_is_safe_and_does_not_touch_checkpoint_or_usage(environment, hitl):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from src.api import dependencies as deps
    from src.api.main import create_app
    env = environment
    service = env.build(hitl_model if hitl else None, hitl=hitl)
    result = service.run(AgentRunRequest(goal="Prepare", user_id="1"))
    other = env.build(hitl_model if hitl else None, hitl=hitl)
    store = RunControlStore(env.sf)
    store.claim(result.run_id, "1", required=True)
    before, usage = other._snapshot(result.run_id), fact(env, result.run_id)
    app = create_app()
    def principal(request: Request):
        owner = request.headers.get("X-Test-Owner")
        if owner not in ("1", "2"):
            raise HTTPException(status_code=401)
        return int(owner)
    app.dependency_overrides[deps.get_repository] = lambda: SimpleNamespace(session_factory=env.sf)
    app.dependency_overrides[deps.get_agent_service] = lambda: other
    app.dependency_overrides[deps.get_current_user_id] = principal
    path = f"/api/v1/agent/runs/{result.run_id}/" + ("resume" if hitl else "messages")
    body = decision(result) if hitl else {"message": "Next"}
    try:
        with TestClient(app) as client:
            assert client.post(path, json=body).status_code == 401
            assert client.post(path, json=body, headers={"X-Test-Owner": "2"}).status_code == 404
            response = client.post(path, json=body, headers={"X-Test-Owner": "1"})
            assert response.status_code == 409
            assert "Prepare" not in response.text and "settled" not in response.text
        assert other._snapshot(result.run_id).values == before.values
        assert fact(env, result.run_id) == usage
        assert not store.owned(result.run_id, "1")["settled"]
    finally:
        store.finish(result.run_id)


@pytest.mark.parametrize("hitl", [False, True])
def test_historical_run_without_control_metadata_is_adopted_safely(environment, hitl):
    env = environment
    other = env.build(hitl_model if hitl else None, hitl=hitl)
    legacy = AgentApplicationService(model_factory=hitl_model if hitl else lambda: Model(),
        career_service=FakeCareer(ambiguous=True) if hitl else build_eval_career(),
        checkpointer=other._checkpointer, checkpoint_durable=True)
    result = legacy.run(AgentRunRequest(goal="Prepare", user_id="1"))
    assert not legacy._snapshot(result.run_id).values.get("control_required")
    assert RunControlStore(env.sf).owned(result.run_id, "1") is None
    if hitl:
        final = other.resume(result.run_id, "1", decision(result))
    else:
        final = other.continue_run(result.run_id, "1", "Next")
    assert final.status == "completed"
    assert other._snapshot(result.run_id).values["control_required"]
    assert RunControlStore(env.sf).owned(result.run_id, "1")["settled"]


def test_pre_0048_sync_continue_still_works_without_creating_control_metadata(environment):
    from src.agent.errors import AgentConfigurationError
    from src.persistence import AgentRunControl
    env = environment
    with env.sf() as s:
        AgentRunControl.__table__.drop(s.get_bind())
    svc = env.build()
    result = svc.run(AgentRunRequest(goal="Prepare", user_id="1"))
    assert result.status == "completed"
    assert svc.continue_run(result.run_id, "1", "Next").usage["model_calls"] == 2
    assert not svc._snapshot(result.run_id).values.get("control_required")
    with pytest.raises(AgentConfigurationError):
        svc.streaming()


def test_unavailable_durable_admission_fails_before_mutation(environment, monkeypatch):
    from src.agent.errors import AgentConfigurationError
    env = environment
    svc = env.build()
    result = svc.run(AgentRunRequest(goal="Prepare", user_id="1"))
    before = svc._snapshot(result.run_id)
    def unavailable(self):
        raise RuntimeError("synthetic store outage")
    monkeypatch.setattr(RunControlStore, "available", unavailable)
    with pytest.raises(AgentConfigurationError):
        svc.continue_run(result.run_id, "1", "Next")
    assert svc._snapshot(result.run_id).values == before.values


def test_late_stop_does_not_reopen_a_settled_run_and_default_saver_survives(environment):
    env = environment
    svc = AgentApplicationService(model_factory=lambda: Model(), career_service=build_eval_career(),
        database_url=env.url, run_index=PreparationRunIndex(env.sf), usage_session_factory=env.sf)
    try:
        result = svc.run(AgentRunRequest(goal="Prepare", user_id="1"))
        row = RunControlStore(env.sf).cancel(result.run_id, "1")
        assert row["status"] == "completed" and row["settled"]
        assert svc.continue_run(result.run_id, "1", "Next").usage["model_calls"] == 2
    finally:
        svc._checkpoint_resource.close()


def test_task_cancellation_during_settlement_does_not_release_the_producer(environment):
    env = environment
    first, other = env.build(), env.build()
    entered, release, recorded = threading.Event(), threading.Event(), threading.Event()
    record = first._record_usage
    def hold(result, owner):
        entered.set()
        assert release.wait(20)
        value = record(result, owner)
        recorded.set()
        return value
    first._record_usage = hold
    async def scenario():
        manager = first.streaming()
        rid = await manager.start(AgentRunRequest(goal="Prepare", user_id="1"))
        try:
            assert await asyncio.to_thread(entered.wait, 15)
            for task in list(manager.tasks):
                task.cancel()
            await asyncio.gather(*list(manager.tasks), return_exceptions=True)
            row = manager.controls.owned(rid, "1")
            assert row["status"] == "failed" and not row["settled"]
            with pytest.raises(RunNotResumableError):
                other.continue_run(rid, "1", "Next")
        finally:
            release.set()
        assert await asyncio.to_thread(recorded.wait, 15)
        assert fact(env, rid) == (1, 9, 900, "complete")
        assert not other.get_run(rid, "1").usage["usage_complete"]
    asyncio.run(scenario())


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
@pytest.mark.parametrize("operation", ["run", "continue"])
def test_stop_winning_sync_settlement_is_reflected_in_return_value(environment, stop, operation):
    env = environment
    svc = env.build()
    previous = svc.run(AgentRunRequest(goal="Prepare", user_id="1")) if operation == "continue" else None
    record = svc._record_usage
    def stop_then_record(result, owner):
        if stop == "cancel":
            RunControlStore(env.sf).cancel(result.run_id, owner)
        else:
            RunControlStore(env.sf, clock=lambda: time.time() + 10000).probe(result.run_id)
        return record(result, owner)
    svc._record_usage = stop_then_record
    result = (svc.continue_run(previous.run_id, "1", "Next") if previous
              else svc.run(AgentRunRequest(goal="Prepare", user_id="1")))
    assert result.status == ("cancelled" if stop == "cancel" else "expired")
    assert result.response == "" and not result.awaiting_human_input and not result.handoff_approved
    calls = 2 if previous else 1
    assert fact(env, result.run_id) == (calls, calls * 9, calls * 900, "complete")


def test_stop_during_invalid_decision_validation_is_not_erased(environment, monkeypatch):
    from src.agent.human import InvalidHumanDecision
    from src.application.errors import ValidationError
    env = environment
    svc = env.build(hitl_model, hitl=True)
    result = svc.run(AgentRunRequest(goal="Prepare", user_id="1"))
    before = svc._snapshot(result.run_id)
    def invalid(pending, value):
        RunControlStore(env.sf).cancel(result.run_id, "1")
        raise InvalidHumanDecision("Invalid synthetic decision.")
    monkeypatch.setattr("src.application.agent_service.validate_decision", invalid)
    with pytest.raises(ValidationError):
        svc.resume(result.run_id, "1", decision(result))
    row = RunControlStore(env.sf).owned(result.run_id, "1")
    assert row["status"] == "cancelled" and row["settled"]
    assert svc._snapshot(result.run_id).values == before.values


def test_simultaneous_eligible_claims_have_exactly_one_producer(environment, monkeypatch):
    env = environment
    first = env.build()
    result = first.run(AgentRunRequest(goal="Prepare", user_id="1"))
    barrier, entered, release = threading.Barrier(2), threading.Event(), threading.Event()
    calls = []
    class Blocking(Model):
        def invoke(self, messages):
            entered.set()
            assert release.wait(20)
            return super().invoke(messages)
    services = [env.build(lambda: Blocking(calls)) for _ in range(2)]
    claim = RunControlStore.claim
    def simultaneous(self, *args, **kwargs):
        barrier.wait(timeout=10)
        return claim(self, *args, **kwargs)  # real independent SQL transactions
    monkeypatch.setattr(RunControlStore, "claim", simultaneous)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(svc.continue_run, result.run_id, "1", "Next") for svc in services]
        try:
            done, pending = wait(futures, timeout=15, return_when=FIRST_COMPLETED)
            assert len(done) == len(pending) == 1
            with pytest.raises(RunNotResumableError):
                next(iter(done)).result()
            assert entered.wait(10)
        finally:
            release.set()
        assert next(iter(pending)).result(timeout=20).status == "completed"
    assert calls == [1]
    assert fact(env, result.run_id) == (2, 18, 1800, "complete")


def test_stream_recording_failure_emits_unsettled_error_without_false_result(environment):
    env = environment
    first, other = env.build(), env.build()
    first._record_usage = lambda result, owner: False
    async def scenario():
        manager = first.streaming()
        rid = await manager.start(AgentRunRequest(goal="Prepare", user_id="1"))
        await asyncio.gather(*list(manager.tasks))
        chunks = [part async for part in manager.events(rid, "1")]
        assert any("agent_stream_interrupted" in part for part in chunks)
        assert not any("event: result" in part for part in chunks)
        assert not manager.controls.owned(rid, "1")["settled"]
        with pytest.raises(RunNotResumableError):
            other.continue_run(rid, "1", "Next")
        assert fact(env, rid) is None
    asyncio.run(scenario())
