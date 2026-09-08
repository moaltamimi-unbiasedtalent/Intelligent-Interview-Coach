"""Sprint 4 Phase 8 — agent checkpoint saver selection.

Verifies the checkpointer factory picks an official durable SQLite saver for a
file DB, falls back to a transient MemorySaver for :memory:/unset, keeps the
checkpoint file separate from the application DB, and never leaks the URL.
"""

from __future__ import annotations

import pytest

from src.agent.checkpoint import build_checkpointer, sqlite_path_from_url
from src.agent.errors import AgentConfigurationError


def test_sqlite_path_normalisation():
    assert sqlite_path_from_url("sqlite:///app.db") == "app.db"
    assert sqlite_path_from_url("sqlite:////abs/app.db") == "/abs/app.db"
    assert sqlite_path_from_url("sqlite:///:memory:") == ":memory:"
    assert sqlite_path_from_url("bare/path.db") == "bare/path.db"
    assert sqlite_path_from_url("postgresql://x/y") is None


def test_file_sqlite_yields_durable_saver(tmp_path):
    db = tmp_path / "app.db"
    info = build_checkpointer(database_url=f"sqlite:///{db}")
    assert info.kind == "sqlite" and info.durable is True
    from langgraph.checkpoint.sqlite import SqliteSaver
    assert isinstance(info.saver, SqliteSaver)


def test_checkpoint_file_is_separate_from_application_db(tmp_path):
    db = tmp_path / "app.db"
    build_checkpointer(database_url=f"sqlite:///{db}")
    # A dedicated checkpoint file is created next to (not inside) the app DB.
    assert (tmp_path / "agent_checkpoints.sqlite").exists()


def test_memory_url_is_transient_fallback():
    info = build_checkpointer(database_url="sqlite:///:memory:")
    assert info.kind == "memory" and info.durable is False


def test_unset_url_is_transient_fallback(monkeypatch):
    monkeypatch.delenv("AGENT_CHECKPOINT_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    info = build_checkpointer(database_url=None)
    assert info.kind == "memory" and info.durable is False


def test_info_detail_never_contains_a_url(tmp_path):
    db = tmp_path / "secret-path.db"
    info = build_checkpointer(database_url=f"sqlite:///{db}")
    assert "secret-path" not in info.detail  # SAFE label only, never the URL/path


# --- fail-closed policy (pre-merge hardening §6, §7, §10) --------------------


def test_explicit_sqlite_config_that_cannot_build_fails_closed():
    # An explicit checkpoint URL whose directory cannot exist must NOT downgrade to
    # MemorySaver — it fails closed so durability is never silently lost.
    bad = "sqlite:////nonexistent-dir-xyz/does/not/exist/cp.db"
    with pytest.raises(AgentConfigurationError):
        build_checkpointer(checkpoint_url=bad)


def test_postgres_config_when_saver_unavailable_fails_closed():
    # Postgres is production durability; if the saver/driver is unavailable it must
    # fail closed rather than silently use MemorySaver.
    with pytest.raises(AgentConfigurationError):
        build_checkpointer(checkpoint_url="postgresql://user:pw@localhost:1/none")


def test_explicit_memory_url_is_allowed_transient(monkeypatch):
    monkeypatch.setenv("AGENT_CHECKPOINT_DATABASE_URL", "sqlite:///:memory:")
    info = build_checkpointer()
    assert info.kind == "memory" and info.durable is False


def test_error_text_never_contains_the_checkpoint_url():
    secret = "postgresql://user:sup3rsecret@db.internal:5432/prod"
    with pytest.raises(AgentConfigurationError) as ei:
        build_checkpointer(checkpoint_url=secret)
    msg = str(ei.value)
    assert "sup3rsecret" not in msg and "db.internal" not in msg


def test_durable_saver_resumes_across_service_recreation(tmp_path):
    # A durable saver built by the factory survives a fresh service instance.
    import sqlite3

    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.checkpoint.sqlite import SqliteSaver

    from src.application.agent_service import AgentApplicationService
    from src.agent.models import AgentRunRequest
    from src.copilot.models import KnowledgeEvidence
    from src.copilot.service import KnowledgeRetrievalResult, PipelineTrace

    path = str(tmp_path / "agent_checkpoints.sqlite")

    class FakeCareer:
        def search_knowledge(self, req, *, progress=None):
            return KnowledgeRetrievalResult(
                evidence=[KnowledgeEvidence(evidence_id="e", text="t", source_id="s", source_title="ESCO", source_url="u", evidence_type="role", occupation_title="PM", reference_year=2024)],
                citations=[], clarify="which?",
                trace=PipelineTrace(occupation_candidates=["Product Manager", "Technical Product Manager"]))

    class Model:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            done = sum(1 for m in messages if isinstance(m, ToolMessage))
            if done == 0:
                return AIMessage(content="", tool_calls=[{"name": "SearchCareerKnowledge", "args": {"query": "pm"}, "id": "c0"}])
            return AIMessage(content="done")

    def make():
        conn = sqlite3.connect(path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        return AgentApplicationService(model_factory=lambda: Model(), career_service=FakeCareer(),
                                       checkpointer=saver, checkpoint_durable=True), conn

    svc_a, conn_a = make()
    res = svc_a.run(AgentRunRequest(goal="Prep", user_id="u1"))
    assert svc_a.checkpoint_durable is True   # injected durability declared, not guessed
    run_id, aid = res.run_id, res.pending_action["action_id"]
    conn_a.close()

    svc_b, conn_b = make()
    done = svc_b.resume(run_id, "u1", {"action_id": aid, "decision": "select", "selected_role": "Product Manager"})
    assert done.status == "completed"
    conn_b.close()
