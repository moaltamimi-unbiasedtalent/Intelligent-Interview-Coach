"""Sprint 4 Phase 7 — preparation-memory API (user-scoped, explicit writes).

Drives the real FastAPI app with a real MemoryApplicationService over in-memory
SQLite; identity uses the transitional X-User-Subject boundary. No provider calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.main import create_app
from src.application.memory_service import MemoryApplicationService
from src.persistence import init_db, make_engine, make_session_factory
from src.repository import MemoryRepository


class _FakeRepo:
    """Maps subjects → stable internal ids (mirrors the real identity seam)."""

    def __init__(self):
        self._users: dict[str, int] = {}
        self._next = 1

    def get_or_create_user(self, *, subject, provider, display_name=None, email=None):
        if subject not in self._users:
            self._users[subject] = self._next
            self._next += 1
        return self._users[subject]


@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = create_app()
    # A file DB (not :memory:) so the schema is visible from TestClient's worker
    # thread, which uses a different connection than the fixture thread.
    engine = make_engine(f"sqlite:///{tmp_path/'memory.db'}")
    init_db(engine)
    service = MemoryApplicationService(MemoryRepository(make_session_factory(engine)))
    repo = _FakeRepo()  # one instance → stable subject→id mapping across requests
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_memory_service] = lambda: service
    return TestClient(app)


ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}


def _create(client, headers, **body):
    body.setdefault("category", "recurring_gap")
    body.setdefault("summary", "Executive communication")
    return client.post("/api/v1/memory", json=body, headers=headers)


def test_create_list_get_delete_roundtrip(client):
    created = _create(client, ALICE, target_role="Head of People")
    assert created.status_code == 201, created.text
    mem = created.json()
    assert mem["category"] == "recurring_gap" and mem["target_role"] == "Head of People"
    assert "user_id" not in mem  # internal id never exposed

    listing = client.get("/api/v1/memory", headers=ALICE).json()["memories"]
    assert [m["id"] for m in listing] == [mem["id"]]

    got = client.get(f"/api/v1/memory/{mem['id']}", headers=ALICE)
    assert got.status_code == 200 and got.json()["summary"] == "Executive communication"

    deleted = client.delete(f"/api/v1/memory/{mem['id']}", headers=ALICE)
    assert deleted.status_code == 200 and deleted.json() == {"deleted": True, "id": mem["id"]}
    assert client.get("/api/v1/memory", headers=ALICE).json()["memories"] == []


def test_invalid_category_returns_422(client):
    r = client.post("/api/v1/memory", json={"category": "health", "summary": "x"}, headers=ALICE)
    assert r.status_code == 422


def test_summary_required(client):
    r = client.post("/api/v1/memory", json={"category": "strength", "summary": ""}, headers=ALICE)
    assert r.status_code == 422


def test_request_body_cannot_set_user_id_or_source_run_id(client):
    # Extra/forbidden fields are ignored by the schema; server owns identity/provenance.
    r = client.post("/api/v1/memory", json={
        "category": "strength", "summary": "Board comms",
        "user_id": 999, "source_run_id": "evil", "created_at": "2000-01-01",
    }, headers=ALICE)
    assert r.status_code == 201
    assert r.json()["source_run_id"] is None  # not taken from the body


def test_category_filter(client):
    _create(client, ALICE, category="strength", summary="A strength")
    _create(client, ALICE, category="recurring_gap", summary="A gap")
    only = client.get("/api/v1/memory", params={"category": "strength"}, headers=ALICE).json()["memories"]
    assert [m["category"] for m in only] == ["strength"]


# --- user isolation (§8) -----------------------------------------------------


def test_user_cannot_see_or_delete_another_users_memory(client):
    a = _create(client, ALICE, summary="Alice private").json()
    assert client.get("/api/v1/memory", headers=BOB).json()["memories"] == []
    assert client.get(f"/api/v1/memory/{a['id']}", headers=BOB).status_code == 404
    assert client.delete(f"/api/v1/memory/{a['id']}", headers=BOB).status_code == 404
    # Still intact for Alice.
    assert client.get(f"/api/v1/memory/{a['id']}", headers=ALICE).status_code == 200


def test_duplicate_create_is_idempotent(client):
    first = _create(client, ALICE, summary="Executive communication").json()
    second = _create(client, ALICE, summary="  executive   communication ").json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/v1/memory", headers=ALICE).json()["memories"]) == 1
