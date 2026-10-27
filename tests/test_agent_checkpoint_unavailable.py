"""Public checkpoint outage projection must never expose driver details."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.agent.errors import AgentCheckpointUnavailable
from src.api.exception_handlers import register_exception_handlers


def test_checkpoint_unavailable_is_safe_503_even_with_unsafe_internal_message():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/checkpoint")
    def checkpoint():
        raise AgentCheckpointUnavailable("synthetic-sensitive-driver-detail")

    with TestClient(app) as client:
        response = client.get("/checkpoint")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "agent_checkpoint_unavailable"
    assert "synthetic-sensitive-driver-detail" not in response.text
