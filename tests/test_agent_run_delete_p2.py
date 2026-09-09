"""Post-Sprint-4 P2 — explicit Coach-run (checkpoint thread) deletion.

Deletes ONLY the LangGraph checkpoint thread via the saver's official delete API —
never long-term memory, Interview History or another run, and never with raw SQL.
Owner-scoped; a foreign/unknown run is a not-found; an unsupported saver is truthful.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from src.agent.models import AgentRunRequest
from src.application.agent_service import (
    AgentApplicationService,
    CheckpointDeleteUnsupportedError,
    RunNotFoundError,
)
from src.application.memory_service import MemoryApplicationService
from src.persistence import User, init_db, make_engine, make_session_factory
from src.repository import MemoryRepository


class _Model:
    def bind_tools(self, s):
        return self

    def invoke(self, messages):
        return AIMessage(content="tips: use STAR.")


def _svc(memory=None):
    return AgentApplicationService(model_factory=lambda: _Model(), career_service=object(),
                                   memory_service=memory)


def test_delete_supported_with_default_saver():
    svc = _svc()
    assert svc.checkpoint_thread_delete_supported is True


def test_owned_run_delete_removes_thread():
    svc = _svc()
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1"))
    assert svc.delete_run(res.run_id, "u1") is True
    with pytest.raises(RunNotFoundError):
        svc.get_run(res.run_id, "u1")  # gone


def test_foreign_user_delete_is_not_found():
    svc = _svc()
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1"))
    with pytest.raises(RunNotFoundError):
        svc.delete_run(res.run_id, "u2")
    assert svc.get_run(res.run_id, "u1").run_id == res.run_id  # untouched


def test_unknown_run_delete_is_not_found():
    svc = _svc()
    with pytest.raises(RunNotFoundError):
        svc.delete_run("does-not-exist", "u1")


def test_delete_paused_hitl_run():
    # A paused run (awaiting a decision) can still be deleted by its owner.
    from langchain_core.messages import ToolMessage

    class Propose:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            if not any(isinstance(m, ToolMessage) for m in messages):
                return AIMessage(content="", tool_calls=[{"name": "ProposePreparationMemory",
                                 "args": {"category": "strength", "summary": "X", "target_role": None}, "id": "c0"}])
            return AIMessage(content="ok")

    engine = make_engine("sqlite://")
    init_db(engine)
    mem = MemoryApplicationService(MemoryRepository(make_session_factory(engine)))
    svc = AgentApplicationService(model_factory=lambda: Propose(), career_service=object(), memory_service=mem)
    res = svc.run(AgentRunRequest(goal="remember", user_id="u1"))
    assert res.awaiting_human_input is True
    assert svc.delete_run(res.run_id, "u1") is True
    with pytest.raises(RunNotFoundError):
        svc.get_run(res.run_id, "u1")


def test_delete_does_not_touch_long_term_memory():
    engine = make_engine("sqlite://")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        s.add(User(subject="u1", provider="test"))
        s.commit()
    mem = MemoryApplicationService(MemoryRepository(sf))
    mem.create(1, category="strength", summary="Durable fact")
    svc = AgentApplicationService(model_factory=lambda: _Model(), career_service=object(), memory_service=mem)
    res = svc.run(AgentRunRequest(goal="tips?", user_id="1"))
    svc.delete_run(res.run_id, "1")
    assert len(mem.list(1)) == 1  # memory survives run deletion


def test_unsupported_saver_is_truthful():
    svc = _svc()
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1"))  # an OWNED run first

    # Swap in a saver with no delete API: ownership still passes, but deletion must be
    # refused truthfully (never a fake success).
    class NoDelete:
        pass
    svc._checkpointer = NoDelete()
    assert svc.checkpoint_thread_delete_supported is False
    with pytest.raises(CheckpointDeleteUnsupportedError):
        svc.delete_run(res.run_id, "u1")
