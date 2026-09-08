"""Sprint 4 Phase 8 — HITL FastAPI surface (run / get / resume).

Drives the real FastAPI app with a real AgentApplicationService (fake model + fake
career + in-memory checkpointer) so the interrupt/resume lifecycle runs end-to-end
over HTTP. Identity uses the transitional X-User-Subject boundary. No provider calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from src.api import dependencies as deps
from src.api.main import create_app
from src.application.agent_service import AgentApplicationService
from src.copilot.models import KnowledgeEvidence
from src.copilot.service import KnowledgeRetrievalResult, PipelineTrace


class _FakeRepo:
    def __init__(self):
        self._users: dict[str, int] = {}
        self._next = 1

    def get_or_create_user(self, *, subject, provider, display_name=None, email=None):
        if subject not in self._users:
            self._users[subject] = self._next
            self._next += 1
        return self._users[subject]


class _FakeCareer:
    def search_knowledge(self, req, *, progress=None):
        return KnowledgeRetrievalResult(
            evidence=[KnowledgeEvidence(evidence_id="e", text="t", source_id="s", source_title="ESCO", source_url="u", evidence_type="role", occupation_title="PM", reference_year=2024)],
            citations=[], clarify="Which occupation?",
            trace=PipelineTrace(occupation_candidates=["Product Manager", "Technical Product Manager"]),
        )


class _Model:
    def bind_tools(self, schemas):
        return self

    def invoke(self, messages):
        done = sum(1 for m in messages if isinstance(m, ToolMessage))
        if done == 0:
            return AIMessage(content="", tool_calls=[{"name": "SearchCareerKnowledge", "args": {"query": "pm"}, "id": "c0"}])
        if done == 1:
            return AIMessage(content="", tool_calls=[{"name": "ProposePreparationMemory", "args": {"category": "strength", "summary": "Board comms", "target_role": "Product Manager"}, "id": "c1"}])
        return AIMessage(content="All set.")


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    repo = _FakeRepo()
    # One app-lifetime agent service (in-memory checkpointer keeps the thread within
    # this client) shared across requests.
    service = AgentApplicationService(model_factory=lambda: _Model(), career_service=_FakeCareer())
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_agent_service] = lambda: service
    return TestClient(app)


ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}


def test_run_returns_awaiting_human_input_with_pending_action(client):
    r = client.post("/api/v1/agent/run", json={"goal": "Prep for PM"}, headers=ALICE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "awaiting_human_input"
    assert body["awaiting_human_input"] is True
    assert body["pending_action"]["type"] == "confirm_role"
    assert len(body["pending_action"]["options"]) >= 2


def test_get_run_shows_paused_status(client):
    run_id = client.post("/api/v1/agent/run", json={"goal": "Prep"}, headers=ALICE).json()["run_id"]
    got = client.get(f"/api/v1/agent/runs/{run_id}", headers=ALICE)
    assert got.status_code == 200 and got.json()["status"] == "awaiting_human_input"


def test_resume_can_pause_again_then_complete(client):
    run = client.post("/api/v1/agent/run", json={"goal": "Prep"}, headers=ALICE).json()
    run_id = run["run_id"]
    # Resume role selection → pauses again for memory approval.
    r2 = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                     json={"action_id": run["pending_action"]["action_id"], "decision": "select", "selected_role": "Product Manager"},
                     headers=ALICE).json()
    assert r2["run_id"] == run_id and r2["pending_action"]["type"] == "approve_memory"
    # Resume approval → completes.
    r3 = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                     json={"action_id": r2["pending_action"]["action_id"], "decision": "approve"},
                     headers=ALICE).json()
    assert r3["run_id"] == run_id and r3["status"] == "completed"


def test_foreign_user_cannot_get_or_resume(client):
    run = client.post("/api/v1/agent/run", json={"goal": "Prep"}, headers=ALICE).json()
    run_id = run["run_id"]
    assert client.get(f"/api/v1/agent/runs/{run_id}", headers=BOB).status_code == 404
    resume = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                         json={"action_id": run["pending_action"]["action_id"], "decision": "select", "selected_role": "Product Manager"},
                         headers=BOB)
    assert resume.status_code == 404


def test_invalid_decision_returns_422_and_keeps_run_paused(client):
    run = client.post("/api/v1/agent/run", json={"goal": "Prep"}, headers=ALICE).json()
    run_id = run["run_id"]
    bad = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                      json={"action_id": run["pending_action"]["action_id"], "decision": "select", "selected_role": "Astronaut"},
                      headers=ALICE)
    assert bad.status_code == 422
    assert client.get(f"/api/v1/agent/runs/{run_id}", headers=ALICE).json()["status"] == "awaiting_human_input"


def test_unknown_decision_value_rejected_by_schema(client):
    run = client.post("/api/v1/agent/run", json={"goal": "Prep"}, headers=ALICE).json()
    run_id = run["run_id"]
    r = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                    json={"action_id": run["pending_action"]["action_id"], "decision": "explode"}, headers=ALICE)
    assert r.status_code == 422  # Literal decision validation


def test_unknown_run_resume_returns_404(client):
    r = client.post("/api/v1/agent/runs/nope/resume",
                    json={"action_id": "x", "decision": "reject"}, headers=ALICE)
    assert r.status_code == 404


def test_resume_completed_run_returns_409(client):
    run = client.post("/api/v1/agent/run", json={"goal": "Prep"}, headers=ALICE).json()
    run_id = run["run_id"]
    r2 = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                     json={"action_id": run["pending_action"]["action_id"], "decision": "select", "selected_role": "Product Manager"},
                     headers=ALICE).json()
    client.post(f"/api/v1/agent/runs/{run_id}/resume",
                json={"action_id": r2["pending_action"]["action_id"], "decision": "approve"}, headers=ALICE)
    # Now completed — a further resume is a 409 (not awaiting).
    again = client.post(f"/api/v1/agent/runs/{run_id}/resume",
                        json={"action_id": r2["pending_action"]["action_id"], "decision": "approve"}, headers=ALICE)
    assert again.status_code == 409
