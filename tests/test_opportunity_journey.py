"""Opportunity model + candidate journey (P10B Wave 6).

Deterministic (0 paid/live): API-level lifecycle + owner-scoping, plus repository/store-level
association (a completed interview or in-progress session carries an owner-scoped opportunity_id
without running the paid interview flow). Covers create/read/update/archive/delete, foreign access
denied, JD owner scoping + deleted-JD safety, interview/session/report association, historical
sessions staying valid, context precedence inputs, and account deletion.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_opp_test_"))

from fastapi.testclient import TestClient

from src.interview.session_repository import DurableInterviewSessionStore
from src.opportunity_repository import OpportunityRepository
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def _clients():
    app, repo, _mail = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    register(c, "a@example.com", PW)
    register(c, "b@example.com", PW)
    a = login_token(c, "a@example.com", PW)
    b = login_token(c, "b@example.com", PW)
    return c, a, b, repo


def _create(c, cookies, **body):
    body.setdefault("target_role", "Senior PM")
    return c.post("/api/v1/opportunities", json=body, cookies=cookies)


def _upload_jd(c, cookies):
    up = c.post("/api/v1/documents", files={"file": ("jd.txt", b"Platform Engineer role", "text/plain")},
                data={"category": "job_description"}, cookies=cookies)
    assert up.status_code in (200, 201), up.text
    return up.json()["id"]


# --------------------------------------------------------------------------- lifecycle


def test_create_lists_gets_and_derives_title():
    c, a, _b, _repo = _clients()
    r = _create(c, cookies_for(a), company_name="Acme", company_location="Berlin", company_country="de")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Senior PM - Acme - Berlin"      # deterministic derivation
    assert body["status"] == "active"
    assert body["company_country"] == "DE"                     # normalised, not inferred
    oid = body["id"]

    assert len(c.get("/api/v1/opportunities", cookies=cookies_for(a)).json()["opportunities"]) == 1
    ov = c.get(f"/api/v1/opportunities/{oid}", cookies=cookies_for(a)).json()
    assert ov["interview_count"] == 0 and ov["jd_available"] is False


def test_update_and_archive_lifecycle():
    c, a, _b, _repo = _clients()
    oid = _create(c, cookies_for(a)).json()["id"]
    upd = c.patch(f"/api/v1/opportunities/{oid}", json={"status": "interviewing"}, cookies=cookies_for(a))
    assert upd.status_code == 200 and upd.json()["status"] == "interviewing"

    arch = c.post(f"/api/v1/opportunities/{oid}/archive", cookies=cookies_for(a))
    assert arch.status_code == 200 and arch.json()["status"] == "archived"
    assert arch.json()["archived_at"]
    # Archived is hidden from the default list, visible with include_archived.
    assert len(c.get("/api/v1/opportunities", cookies=cookies_for(a)).json()["opportunities"]) == 0
    assert len(c.get("/api/v1/opportunities?include_archived=true",
                     cookies=cookies_for(a)).json()["opportunities"]) == 1


def test_invalid_status_and_country_rejected():
    c, a, _b, _repo = _clients()
    oid = _create(c, cookies_for(a)).json()["id"]
    assert c.patch(f"/api/v1/opportunities/{oid}", json={"status": "hired"}, cookies=cookies_for(a)).status_code == 422
    assert _create(c, cookies_for(a), company_country="DEU").status_code == 422


# --------------------------------------------------------------------------- authorization


def test_foreign_access_is_denied_everywhere():
    c, a, b, _repo = _clients()
    oid = _create(c, cookies_for(a)).json()["id"]
    assert c.get(f"/api/v1/opportunities/{oid}", cookies=cookies_for(b)).status_code == 404
    assert c.get(f"/api/v1/opportunities/{oid}/context", cookies=cookies_for(b)).status_code == 404
    assert c.patch(f"/api/v1/opportunities/{oid}", json={"target_role": "x"}, cookies=cookies_for(b)).status_code == 404
    assert c.post(f"/api/v1/opportunities/{oid}/archive", cookies=cookies_for(b)).status_code == 404
    assert c.delete(f"/api/v1/opportunities/{oid}", cookies=cookies_for(b)).status_code == 404
    # A guessed id nobody owns is also a 404.
    assert c.get("/api/v1/opportunities/999999", cookies=cookies_for(a)).status_code == 404


# --------------------------------------------------------------------------- JD owner scoping


def test_jd_link_owner_scoped_and_foreign_rejected():
    c, a, b, _repo = _clients()
    a_doc = _upload_jd(c, cookies_for(a))
    # Own JD links; context reports it available.
    oid = _create(c, cookies_for(a), job_description_document_id=a_doc).json()["id"]
    ctx = c.get(f"/api/v1/opportunities/{oid}/context", cookies=cookies_for(a)).json()
    assert ctx["job_description_document_id"] == a_doc and ctx["jd_available"] is True
    # B cannot link A's document.
    assert _create(c, cookies_for(b), job_description_document_id=a_doc).status_code == 422


def test_deleted_jd_becomes_unavailable_and_opportunity_survives():
    c, a, _b, _repo = _clients()
    doc = _upload_jd(c, cookies_for(a))
    oid = _create(c, cookies_for(a), job_description_document_id=doc).json()["id"]
    assert c.delete(f"/api/v1/documents/{doc}", cookies=cookies_for(a)).status_code in (200, 204)
    # The opportunity survives; the JD link is cleared / reported unavailable (no stale content).
    ov = c.get(f"/api/v1/opportunities/{oid}", cookies=cookies_for(a)).json()
    assert ov["jd_available"] is False
    ctx = c.get(f"/api/v1/opportunities/{oid}/context", cookies=cookies_for(a)).json()
    assert ctx["job_description_document_id"] is None


# --------------------------------------------------------------------------- interview / session association


def test_session_and_interview_association_owner_scoped():
    c, a, _b, repo = _clients()
    oid = _create(c, cookies_for(a)).json()["id"]
    a_uid = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["user_id"]

    store = DurableInterviewSessionStore(repo.session_factory)
    sid = store.create(a_uid, opportunity_id=oid)
    assert store.opportunity_id_for(sid, a_uid) == oid
    # Foreign read of the link returns None (never another user's data).
    assert store.opportunity_id_for(sid, a_uid + 999) is None

    # A completed interview carries the link and is discoverable from the Opportunity overview.
    iid = repo.save_interview(a_uid, {"configuration": {}, "status": "completed"},
                              source_session_id=sid, opportunity_id=oid)
    ov = c.get(f"/api/v1/opportunities/{oid}", cookies=cookies_for(a)).json()
    assert iid in ov["interview_ids"] and ov["interview_count"] == 1


def test_historical_session_without_opportunity_remains_valid():
    c, a, _b, repo = _clients()
    a_uid = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["user_id"]
    store = DurableInterviewSessionStore(repo.session_factory)
    sid = store.create(a_uid)                       # no opportunity
    assert store.opportunity_id_for(sid, a_uid) is None
    iid = repo.save_interview(a_uid, {"configuration": {}, "status": "completed"}, source_session_id=sid)
    assert iid > 0                                  # saved fine with a NULL link


def test_deleting_opportunity_preserves_linked_history():
    c, a, _b, repo = _clients()
    a_uid = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["user_id"]
    oid = _create(c, cookies_for(a)).json()["id"]
    iid = repo.save_interview(a_uid, {"configuration": {}, "status": "completed"},
                              source_session_id="s-keep", opportunity_id=oid)
    assert c.delete(f"/api/v1/opportunities/{oid}", cookies=cookies_for(a)).status_code == 200
    # The completed interview survives (history is never destroyed by deleting an Opportunity).
    assert repo.get_interview(a_uid, iid) is not None


# --------------------------------------------------------------------------- account deletion


def test_account_deletion_removes_opportunities():
    c, a, _b, repo = _clients()
    from src.application.account_deletion_service import AccountDeletionService
    a_uid = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["user_id"]
    _create(c, cookies_for(a))
    assert OpportunityRepository(repo.session_factory).list_for_user(a_uid)
    AccountDeletionService(repo.session_factory).delete_account(a_uid)
    assert OpportunityRepository(repo.session_factory).list_for_user(a_uid) == []
