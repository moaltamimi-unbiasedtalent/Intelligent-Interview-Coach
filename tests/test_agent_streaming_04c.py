"""04C integration: real graph + temporary official saver, no network/provider."""
import asyncio
import threading

import pytest
from langchain_core.messages import AIMessage

from src.agent.eval import build_eval_career
from src.agent.models import AgentRunRequest
from src.agent.run_control import RunControlStore
from src.application.agent_service import AgentApplicationService, RunNotFoundError, RunNotResumableError
from src.application.agent_streaming import safe_progress
from src.persistence import Base, User, make_engine, make_session_factory
from src.privacy.preparation import PreparationRunIndex


@pytest.fixture
def environment(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'app.sqlite'}")
    Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        s.add_all([User(id=1, subject="one", provider="test"), User(id=2, subject="two", provider="test")])
        s.commit()
    def build(factory):
        return AgentApplicationService(model_factory=factory, career_service=build_eval_career(),
            database_url=f"sqlite:///{tmp_path / 'app.sqlite'}", run_index=PreparationRunIndex(sf), usage_session_factory=sf)
    yield sf, build
    engine.dispose()


class Model:
    def __init__(self, entered=None, release=None, calls=None, tool=False):
        self.entered, self.release, self.calls, self.tool = entered, release, calls, tool
    def bind_tools(self, schemas):
        return self
    def invoke(self, messages):
        if self.calls is not None:
            self.calls.append(1)
        if self.entered:
            self.entered.set()
            assert self.release.wait(5), "test release missing"
        if self.tool:
            return AIMessage(content="", tool_calls=[{"id": "one", "name": "GenerateInterviewQuestions", "args": {"role": "Nurse"}}])
        return AIMessage(content="A concise preparation answer.", usage_metadata={"input_tokens": 5, "output_tokens": 4, "total_tokens": 9})


def test_sse_uses_same_durable_run_and_sync_lookup_after_restart(environment):
    sf, build = environment
    service = build(lambda: Model())
    async def scenario():
        manager = service.streaming()
        run_id = await manager.start(AgentRunRequest(goal="Hello", user_id="1"))
        chunks = [chunk async for chunk in manager.events(run_id, "1")]
        assert any('event: progress' in chunk for chunk in chunks)
        assert any('event: result' in chunk for chunk in chunks)
        assert manager.controls.owned(run_id, "1")["settled"]
        assert all(x not in ''.join(chunks) for x in ('SystemMessage', 'You are Mo', 'job_description'))
        return run_id
    run_id = asyncio.run(scenario())
    recreated = build(lambda: Model())
    assert recreated.get_run(run_id, "1").run_id == run_id
    with pytest.raises(RunNotFoundError):
        recreated.streaming().require_owned(run_id, "2")
    assert RunControlStore(sf).owned(run_id, "2") is None


def test_cancel_during_provider_call_drains_usage_and_blocks_followup_tools(environment):
    sf, build = environment
    entered, release, calls = threading.Event(), threading.Event(), []
    service = build(lambda: Model(entered, release, calls, tool=True))
    async def scenario():
        manager = service.streaming()
        run_id = await manager.start(AgentRunRequest(goal="Generate questions", user_id="1"))
        assert await asyncio.to_thread(entered.wait, 5)
        assert manager.controls.cancel(run_id, "2") is None
        first = manager.controls.cancel(run_id, "1")
        assert first["status"] == "cancelled" and not first["settled"]
        # A separate service/process sees the durable cancellation immediately.
        other = build(lambda: Model())
        assert other._registry.authorizer.run_control(run_id) == "cancelled"
        release.set()
        await asyncio.gather(*list(manager.tasks))
        result = service.get_run(run_id, "1")
        assert result.status == "cancelled" and not result.tools_used
        assert result.usage["model_calls"] == 1
        assert result.usage["usage_complete"] is False  # this model intentionally omitted usage
        assert calls == [1]
        assert manager.controls.owned(run_id, "1")["settled"]
        with pytest.raises(RunNotResumableError):
            other.continue_run(run_id, "1", "continue")
    asyncio.run(scenario())


def test_reconnect_observes_without_executing_again(environment):
    _, build = environment
    calls = []
    service = build(lambda: Model(calls=calls))
    async def scenario():
        manager = service.streaming()
        rid = await manager.start(AgentRunRequest(goal="Hello", user_id="1"))
        await asyncio.gather(*list(manager.tasks))
        before = len(calls)
        chunks = [x async for x in manager.events(rid, "1", after=10000)]
        assert not any('event: progress' in x for x in chunks)
        assert any('event: result' in x for x in chunks)
        assert len(calls) == before == 1
    asyncio.run(scenario())


def test_deadline_is_durable_and_fails_closed_before_another_call(environment):
    sf, _ = environment
    store = RunControlStore(sf, clock=lambda: 100)
    store.create("expired-test", "1", timeout_s=1)
    later = RunControlStore(sf, clock=lambda: 102)
    assert later.probe("expired-test") == "expired"
    assert store.owned("expired-test", "1")["status"] == "expired"
    assert store.cancel("expired-test", "2") is None


def test_projection_drops_free_text_unknown_types_and_bad_values():
    event = {"event_type": "tool_completed", "step": 2, "message": "PRIVATE", "tool_name": "PRIVATE",
             "duration_ms": -1, "source_count": "PRIVATE", "arguments": {"key": "PRIVATE"}, "raw": "PRIVATE"}
    assert safe_progress(event) == {"event_type": "tool_completed", "step": 2}
    assert safe_progress({"event_type": "on_chat_model_stream", "text": "PRIVATE"}) is None




def test_real_chat_model_never_enables_provider_streaming_from_callbacks():
    from pydantic import SecretStr
    from src.copilot.config import CopilotConfig
    from src.copilot.llm.openrouter import build_chat_model

    model = build_chat_model(CopilotConfig(api_key=SecretStr("synthetic-key-not-used")))
    assert model.disable_streaming is True  # construction only; no provider/network call


def test_http_stream_and_reconnect_are_owner_scoped_and_sync_remains_usable(environment):
    from types import SimpleNamespace
    from fastapi import HTTPException, Request
    from fastapi.testclient import TestClient
    from src.api import dependencies as deps
    from src.api.main import create_app

    sf, build = environment
    service = build(lambda: Model())
    app = create_app()
    def principal(request: Request):
        value = request.headers.get("X-Test-Owner")
        if value not in ("1", "2"):
            raise HTTPException(status_code=401)
        return int(value)
    app.dependency_overrides[deps.get_repository] = lambda: SimpleNamespace(session_factory=sf)
    app.dependency_overrides[deps.get_agent_service] = lambda: service
    app.dependency_overrides[deps.get_current_user_id] = principal
    with TestClient(app) as client:
        assert client.post("/api/v1/agent/run/stream", json={"goal": "Hello"}).status_code == 401
        response = client.post("/api/v1/agent/run/stream", json={"goal": "Hello"}, headers={"X-Test-Owner": "1"})
        assert response.status_code == 200 and 'event: result' in response.text
        import json
        first = next(line[6:] for line in response.text.splitlines() if line.startswith('data: '))
        rid = json.loads(first)["run_id"]
        for path in (f"/api/v1/agent/runs/{rid}/events", "/api/v1/agent/runs/unknown/events"):
            assert client.get(path, headers={"X-Test-Owner": "2"}).status_code == 404
        assert client.post(f"/api/v1/agent/runs/{rid}/cancel", headers={"X-Test-Owner": "2"}).status_code == 404
        assert client.get(f"/api/v1/agent/runs/{rid}/events", headers={"X-Test-Owner": "1", "Last-Event-ID": "10000"}).status_code == 200
        assert client.get(f"/api/v1/agent/runs/{rid}/events", headers={"X-Test-Owner": "1", "Last-Event-ID": "bad"}).status_code == 422
        assert client.post("/api/v1/agent/run", json={"goal": "Hello"}, headers={"X-Test-Owner": "1"}).status_code == 200


def test_missing_control_for_a_streamed_thread_fails_closed(environment):
    sf, build = environment
    service = build(lambda: Model())
    assert service._registry.authorizer.run_control("not-indexed", required=True) == "expired"
    assert service._registry.authorizer.run_control("historical-sync", required=False) is None


def test_shutdown_interruption_is_never_reported_as_settled(environment):
    sf, _ = environment
    store = RunControlStore(sf)
    store.create("shutdown-test", "1")
    store.interrupt("shutdown-test")
    assert store.owned("shutdown-test", "1") == {"run_id": "shutdown-test", "status": "failed", "settled": False,
                                                  "deadline_epoch": store.owned("shutdown-test", "1")["deadline_epoch"]}


def test_tool_execution_fails_closed_when_a_required_control_record_disappears():
    from src.agent.registry import career_tool_registry
    from src.agent.tool_authorization import RunAuthContext, Reason
    from src.agent.tooling import ToolContext
    registry = career_tool_registry(None)
    registry.authorizer.set_run_control(lambda rid: None)
    decision = registry.authorize("AnalyzeJobDescription", {}, ToolContext(), RunAuthContext(run_id="gone", user_id="1", control_required=True))
    assert not decision.allowed and decision.reason is Reason.RUN_NOT_ACTIVE


def test_durable_stop_wins_over_a_completed_checkpoint_and_hides_late_actions(environment):
    sf, build = environment
    service = build(lambda: Model())
    completed = service.run(AgentRunRequest(goal="Hello", user_id="1"))
    rid = completed.run_id
    RunControlStore(sf).claim(rid, "1", required=True)
    service._graph.update_state(service._config(rid), {"control_required": True})
    RunControlStore(sf).cancel(rid, "1")
    stopped = service.get_run(rid, "1")
    assert stopped.status == "cancelled" and stopped.response == ""
    assert not stopped.handoff_approved and not stopped.awaiting_human_input
    assert stopped.usage["estimated_cost_usd"] is None and not stopped.usage["usage_complete"]
    assert all(m["role"] != "assistant" for m in stopped.conversation)


def test_cancelled_provider_usage_is_settled_from_actual_checkpoint_values(environment):
    _, build = environment
    entered, release = threading.Event(), threading.Event()
    captured = []
    service = build(lambda: Model(entered, release))
    service._record_usage = lambda result, owner: captured.append(dict(result.usage))
    async def scenario():
        manager = service.streaming()
        rid = await manager.start(AgentRunRequest(goal="Hello", user_id="1"))
        assert await asyncio.to_thread(entered.wait, 5)
        manager.controls.cancel(rid, "1")
        release.set()
        await asyncio.gather(*list(manager.tasks))
        assert captured[-1]["model_calls"] == 1 and captured[-1]["total_tokens"] == 9
        assert "stream_settlement_pending" not in captured[-1]["missing_usage_sources"]
        assert manager.controls.owned(rid, "1")["settled"]
    asyncio.run(scenario())


def test_pre_0048_database_keeps_sync_working_and_refuses_streaming_before_admission(environment):
    from src.agent.errors import AgentConfigurationError
    from src.persistence import AgentRunControl
    sf, build = environment
    with sf() as session:
        AgentRunControl.__table__.drop(session.get_bind())
    calls = []
    service = build(lambda: Model(calls=calls))
    assert service._registry.authorizer.run_control("controlled-with-missing-table", required=True) == "expired"
    result = service.run(AgentRunRequest(goal="Hello", user_id="1"))
    assert calls == [1]
    assert result.status == "completed"
    with pytest.raises(AgentConfigurationError):
        service.streaming()
    assert calls == [1]
