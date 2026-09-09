"""Post-Sprint-4 P2 — memory PATCH / preview API + cross-user isolation.

Drives the real FastAPI app with a real MemoryApplicationService over file-backed
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
    engine = make_engine(f"sqlite:///{tmp_path/'memory.db'}")
    init_db(engine)
    service = MemoryApplicationService(MemoryRepository(make_session_factory(engine)))
    repo = _FakeRepo()
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_memory_service] = lambda: service
    return TestClient(app)


ALICE = {"X-User-Subject": "alice"}
BOB = {"X-User-Subject": "bob"}


def _create(client, headers, **body):
    body.setdefault("category", "recurring_gap")
    body.setdefault("summary", "Executive communication")
    return client.post("/api/v1/memory", json=body, headers=headers)


# --- PATCH ------------------------------------------------------------------


def test_patch_edits_and_pins(client):
    mid = _create(client, ALICE).json()["id"]
    r = client.patch(f"/api/v1/memory/{mid}", json={"summary": "Refined", "pinned": True}, headers=ALICE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"] == "Refined" and body["pinned"] is True
    assert "user_id" not in body


def test_patch_clear_role_vs_omit(client):
    mid = _create(client, ALICE, target_role="PM").json()["id"]
    # Explicit null clears the role.
    r = client.patch(f"/api/v1/memory/{mid}", json={"target_role": None}, headers=ALICE)
    assert r.json()["target_role"] is None
    # Omitting target_role leaves the (now-null) role untouched while editing summary.
    r2 = client.patch(f"/api/v1/memory/{mid}", json={"summary": "S2"}, headers=ALICE)
    assert r2.json()["target_role"] is None and r2.json()["summary"] == "S2"


def test_patch_empty_body_rejected(client):
    mid = _create(client, ALICE).json()["id"]
    assert client.patch(f"/api/v1/memory/{mid}", json={}, headers=ALICE).status_code == 422


def test_patch_invalid_category_rejected(client):
    mid = _create(client, ALICE).json()["id"]
    assert client.patch(f"/api/v1/memory/{mid}", json={"category": "medical"}, headers=ALICE).status_code == 422


def test_patch_extra_field_rejected(client):
    mid = _create(client, ALICE).json()["id"]
    # source_run_id / user_id are not accepted (schema forbids extras).
    assert client.patch(f"/api/v1/memory/{mid}", json={"source_run_id": "r"}, headers=ALICE).status_code == 422
    assert client.patch(f"/api/v1/memory/{mid}", json={"user_id": 9}, headers=ALICE).status_code == 422


def test_patch_duplicate_collision_409(client):
    _create(client, ALICE, summary="Alpha")
    bid = _create(client, ALICE, summary="Beta").json()["id"]
    r = client.patch(f"/api/v1/memory/{bid}", json={"summary": "Alpha"}, headers=ALICE)
    assert r.status_code == 409


def test_patch_foreign_memory_not_found(client):
    mid = _create(client, ALICE).json()["id"]
    assert client.patch(f"/api/v1/memory/{mid}", json={"pinned": True}, headers=BOB).status_code == 404


# --- preview ----------------------------------------------------------------


def test_preview_matches_and_is_ordered(client):
    _create(client, ALICE, summary="general note")
    pmid = _create(client, ALICE, summary="pinned pm", target_role="PM").json()["id"]
    client.patch(f"/api/v1/memory/{pmid}", json={"pinned": True}, headers=ALICE)
    _create(client, ALICE, summary="pm note", target_role="PM")

    r = client.get("/api/v1/memory/preview?target_role=PM", headers=ALICE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_role"] == "PM" and body["load_limit"] == 10
    items = body["items"]
    assert items[0]["summary"] == "pinned pm" and items[0]["reason"] == "Matches this role"
    assert [i["order"] for i in items] == list(range(len(items)))


def test_preview_empty_for_role(client):
    r = client.get("/api/v1/memory/preview?target_role=Nurse", headers=ALICE)
    assert r.status_code == 200 and r.json()["items"] == []


# --- cross-user isolation (§48) ---------------------------------------------


def test_cross_user_isolation(client):
    a = _create(client, ALICE, summary="alice-secret").json()["id"]
    # Bob cannot read, edit, pin, delete or preview Alice's memory.
    assert client.get(f"/api/v1/memory/{a}", headers=BOB).status_code == 404
    assert client.patch(f"/api/v1/memory/{a}", json={"summary": "hijacked"}, headers=BOB).status_code == 404
    assert client.patch(f"/api/v1/memory/{a}", json={"pinned": True}, headers=BOB).status_code == 404
    assert client.delete(f"/api/v1/memory/{a}", headers=BOB).status_code == 404
    assert client.get("/api/v1/memory/preview", headers=BOB).json()["items"] == []
    # Alice's memory is unchanged.
    assert client.get(f"/api/v1/memory/{a}", headers=ALICE).json()["summary"] == "alice-secret"
