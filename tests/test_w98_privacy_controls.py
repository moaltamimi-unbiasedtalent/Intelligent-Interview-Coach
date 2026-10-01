"""P10B-W9.8 - candidate data controls (deterministic, 0 paid/live calls).

Covers the backend capabilities the Data & Privacy Center relies on:
  * export (P11/P12): owner-scoped, broad, truthful scope, no secrets/storage keys;
  * completed-interview delete (P6/P13/P14): cascade, source-session discard, share revocation, 404 on
    foreign/repeat, metadata-only audit;
  * story delete revokes share grants (no dangling active grant);
  * document / memory / opportunity / share semantics (P3-P5, P8, P13);
  * account deletion cascade and audit anonymisation (P9/P10);
  * writes are never transport-retried (P15, source-level).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_w98_test_"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src import persistence as P
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"
ROOT = Path(__file__).resolve().parent.parent


def _payload(role="Registered Nurse"):
    return {
        "configuration": {"target_role": role}, "mode": "Record", "status": "completed",
        "questions": [{
            "position": 0, "canonical_question": "Tell me about a challenge.",
            "question_type": "behavioural", "difficulty": "moderate",
            "timing_guidance": {"recommended_seconds": 100},
            "answer": {"text": "SECRET-ANSWER-TEXT", "evaluation": {"overall_score": 70},
                       "timing_metrics": {}, "visual_metrics": {}},
        }],
    }


_OPEN: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_clients():
    yield
    while _OPEN:
        _OPEN.pop().__exit__(None, None, None)


def _setup():
    app, repo, mail = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    _OPEN.append(c)
    register(c, "a@example.com", PW)
    register(c, "b@example.com", PW)
    a = login_token(c, "a@example.com", PW)
    b = login_token(c, "b@example.com", PW)
    ida = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["user_id"]
    idb = c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()["user_id"]
    return c, repo, mail, a, b, ida, idb


def _seed(c, repo, token, uid):
    ck = cookies_for(token)
    opp = c.post("/api/v1/opportunities", json={"target_role": "PM", "company_name": "Acme"}, cookies=ck).json()["id"]
    doc = c.post("/api/v1/documents", files={"file": ("cv.txt", b"Led a team of five engineers.", "text/plain")},
                 data={"category": "cv"}, cookies=ck)
    assert doc.status_code in (200, 201), doc.text
    mem = c.post("/api/v1/memory", json={"category": "preparation_goal", "summary": "Prepare for PM interviews"},
                 cookies=ck)
    assert mem.status_code in (200, 201), mem.text
    iid = repo.save_interview(uid, _payload())
    return {"opp": opp, "doc": doc.json()["id"], "mem": mem.json()["id"], "iid": iid}


# ---- P11 / P12: export ----------------------------------------------------------------------------
def test_export_contains_owner_data_with_truthful_scope_and_headers():
    c, repo, _m, a, _b, ida, _idb = _setup()
    ids = _seed(c, repo, a, ida)
    r = c.get("/api/v1/auth/account/export", cookies=cookies_for(a))
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["format"] == "ask4mo.candidate-export.v1"
    assert body["account"]["email"] == "a@example.com"
    assert [o["id"] for o in body["opportunities"]] == [ids["opp"]]
    assert [d["id"] for d in body["documents"]] == [ids["doc"]]
    assert [m["id"] for m in body["memories"]] == [ids["mem"]]
    assert [i["id"] for i in body["interviews"]] == [ids["iid"]]
    assert body["legal_acceptance"] == {"recorded": False}  # never fabricated
    assert body["scope"]["included"] and body["scope"]["not_included"]


def test_export_excludes_secrets_storage_keys_and_other_users_data():
    c, repo, _m, a, b, ida, idb = _setup()
    _seed(c, repo, a, ida)
    ids_b = _seed(c, repo, b, idb)
    text = c.get("/api/v1/auth/account/export", cookies=cookies_for(a)).text
    assert '"storage_key"' not in text and "password_hash" not in text
    assert "token_hash" not in text
    body = c.get("/api/v1/auth/account/export", cookies=cookies_for(a)).json()
    assert ids_b["iid"] not in [i["id"] for i in body["interviews"]] or ids_b["iid"] == ida  # distinct owner rows
    assert all(o["id"] != ids_b["opp"] for o in body["opportunities"])
    assert "b@example.com" not in text


def test_privacy_endpoints_require_authentication_in_production():
    app, _repo, _mail = build_auth_app(env="production")
    with TestClient(app) as c:
        assert c.get("/api/v1/auth/account/export").status_code == 401
        assert c.delete("/api/v1/history/interviews/1").status_code == 401
        assert c.delete("/api/v1/shares/1").status_code == 401


# ---- P6 / P13 / P14: interview delete ----------------------------------------------------------------
def test_delete_interview_cascades_and_is_idempotent_safe():
    c, repo, _m, a, _b, ida, _idb = _setup()
    iid = repo.save_interview(ida, _payload())
    r = c.delete(f"/api/v1/history/interviews/{iid}", cookies=cookies_for(a))
    assert r.status_code == 200 and r.json() == {"deleted": True}
    sf = repo.session_factory
    with sf() as s:
        assert s.scalars(select(P.Interview).where(P.Interview.id == iid)).first() is None
        assert s.scalars(select(P.Question).where(P.Question.interview_id == iid)).first() is None
        assert s.scalars(select(P.Report)).first() is None
        assert s.scalars(select(P.Answer)).first() is None
    assert c.get(f"/api/v1/history/interviews/{iid}", cookies=cookies_for(a)).status_code == 404
    assert c.delete(f"/api/v1/history/interviews/{iid}", cookies=cookies_for(a)).status_code == 404  # not 5xx


def test_delete_interview_foreign_is_404_and_leaves_data():
    c, repo, _m, a, b, ida, _idb = _setup()
    iid = repo.save_interview(ida, _payload())
    assert c.delete(f"/api/v1/history/interviews/{iid}", cookies=cookies_for(b)).status_code == 404
    assert repo.get_interview(ida, iid) is not None


def test_delete_interview_audit_is_metadata_only():
    c, repo, _m, a, _b, ida, _idb = _setup()
    iid = repo.save_interview(ida, _payload())
    c.delete(f"/api/v1/history/interviews/{iid}", cookies=cookies_for(a))
    with repo.session_factory() as s:
        ev = s.scalars(select(P.AuditEvent).where(P.AuditEvent.event_type == "interview.deleted")).all()
    assert len(ev) == 1 and ev[0].target_id == str(iid)
    assert "SECRET-ANSWER-TEXT" not in repr((ev[0].context, ev[0].target_id, ev[0].target_type))


# ---- share revocation on source deletion ------------------------------------------------------------
def _workspace_with_member(c, mail, a, b):
    wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
    c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "b@example.com"}, cookies=cookies_for(a))
    tok = mail.sent[-1].body.split("token=")[1].split()[0]
    assert c.post("/api/v1/workspaces/invitations/accept", json={"token": tok},
                  cookies=cookies_for(b)).status_code in (200, 201)
    return wid


def test_deleting_a_shared_interview_revokes_its_grant():
    c, repo, mail, a, b, ida, _idb = _setup()
    wid = _workspace_with_member(c, mail, a, b)
    iid = repo.save_interview(ida, _payload())
    sh = c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report",
                                         "resource_id": str(iid)}, cookies=cookies_for(a))
    assert sh.status_code in (200, 201), sh.text
    assert len(c.get("/api/v1/shares/mine", cookies=cookies_for(a)).json()["shares"]) == 1
    assert c.delete(f"/api/v1/history/interviews/{iid}", cookies=cookies_for(a)).status_code == 200
    assert c.get("/api/v1/shares/mine", cookies=cookies_for(a)).json()["shares"] == []
    assert c.get(f"/api/v1/shares/resource/interview_report/{iid}", cookies=cookies_for(b)).status_code == 404


def test_revoke_share_removes_member_access_and_foreign_revoke_fails():
    c, repo, mail, a, b, ida, _idb = _setup()
    wid = _workspace_with_member(c, mail, a, b)
    iid = repo.save_interview(ida, _payload())
    assert c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report",
                                           "resource_id": str(iid)}, cookies=cookies_for(a)).status_code in (200, 201)
    sid = c.get("/api/v1/shares/mine", cookies=cookies_for(a)).json()["shares"][0]["id"]
    assert c.get(f"/api/v1/shares/resource/interview_report/{iid}", cookies=cookies_for(b)).status_code == 200
    assert c.delete(f"/api/v1/shares/{sid}", cookies=cookies_for(b)).status_code in (403, 404)  # not owner
    assert c.delete(f"/api/v1/shares/{sid}", cookies=cookies_for(a)).status_code == 200
    assert c.get(f"/api/v1/shares/resource/interview_report/{iid}", cookies=cookies_for(b)).status_code == 404


# ---- P3 / P4 / P5 / P13: documents, memory, opportunities -------------------------------------------
def test_document_delete_cascades_versions_claims_and_foreign_is_denied():
    c, repo, _m, a, b, ida, idb = _setup()
    ids = _seed(c, repo, a, ida)
    assert c.delete(f"/api/v1/documents/{ids['doc']}", cookies=cookies_for(b)).status_code == 404
    assert c.delete(f"/api/v1/documents/{ids['doc']}", cookies=cookies_for(a)).status_code == 200
    with repo.session_factory() as s:
        assert s.scalars(select(P.CandidateDocument)).first() is None
        assert s.scalars(select(P.DocumentVersion)).first() is None
        assert s.scalars(select(P.DocumentClaim)).first() is None
    assert c.delete(f"/api/v1/documents/{ids['doc']}", cookies=cookies_for(a)).status_code == 404


def test_memory_delete_leaves_history_and_foreign_is_denied():
    c, repo, _m, a, b, ida, _idb = _setup()
    ids = _seed(c, repo, a, ida)
    assert c.delete(f"/api/v1/memory/{ids['mem']}", cookies=cookies_for(b)).status_code == 404
    assert c.delete(f"/api/v1/memory/{ids['mem']}", cookies=cookies_for(a)).status_code in (200, 204)
    assert repo.get_interview(ida, ids["iid"]) is not None  # unrelated history untouched
    assert c.delete(f"/api/v1/memory/{ids['mem']}", cookies=cookies_for(a)).status_code == 404


def test_opportunity_archive_is_not_delete_and_delete_keeps_history():
    c, repo, _m, a, b, ida, _idb = _setup()
    ids = _seed(c, repo, a, ida)
    arch = c.post(f"/api/v1/opportunities/{ids['opp']}/archive", cookies=cookies_for(a)).json()
    assert arch["status"] == "archived"  # still exists
    assert c.get(f"/api/v1/opportunities/{ids['opp']}", cookies=cookies_for(a)).status_code == 200
    assert c.delete(f"/api/v1/opportunities/{ids['opp']}", cookies=cookies_for(b)).status_code == 404
    assert c.delete(f"/api/v1/opportunities/{ids['opp']}", cookies=cookies_for(a)).status_code == 200
    assert c.get(f"/api/v1/opportunities/{ids['opp']}", cookies=cookies_for(a)).status_code == 404
    assert repo.get_interview(ida, ids["iid"]) is not None


def test_story_delete_revokes_shared_grants():
    c, repo, mail, a, b, ida, _idb = _setup()
    wid = _workspace_with_member(c, mail, a, b)
    st = c.post("/api/v1/stories", json={"title": "S", "status": "user_created", "situation": "x", "task": "y",
                                          "action": "z", "result": "r", "competencies": [], "claim_ids": []},
                cookies=cookies_for(a))
    assert st.status_code == 201, st.text
    sid = st.json()["id"]
    assert c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "story",
                                           "resource_id": str(sid)}, cookies=cookies_for(a)).status_code in (200, 201)
    assert c.delete(f"/api/v1/stories/{sid}", cookies=cookies_for(a)).status_code == 200
    assert c.get("/api/v1/shares/mine", cookies=cookies_for(a)).json()["shares"] == []


# ---- P1 / P2: owner-scoped inventory reads ------------------------------------------------------------
def test_inventory_reads_are_owner_scoped():
    c, repo, _m, a, b, ida, idb = _setup()
    _seed(c, repo, a, ida)
    ckb = cookies_for(b)
    assert c.get("/api/v1/opportunities", cookies=ckb).json()["opportunities"] == []
    assert c.get("/api/v1/documents", cookies=ckb).json()["documents"] == []
    assert c.get("/api/v1/history/interviews", cookies=ckb).json()["interviews"] == []
    assert c.get("/api/v1/memory", cookies=ckb).json()["memories"] == []


# ---- P9 / P10: account deletion -----------------------------------------------------------------------
def test_account_deletion_cascades_and_anonymises_audit():
    c, repo, _m, a, b, ida, idb = _setup()
    _seed(c, repo, a, ida)
    ids_b = _seed(c, repo, b, idb)
    assert c.post("/api/v1/auth/account/delete", cookies=cookies_for(a)).status_code in (200, 204)
    with repo.session_factory() as s:
        for model, col in ((P.Opportunity, P.Opportunity.user_id), (P.CandidateDocument, P.CandidateDocument.user_id),
                           (P.PreparationMemory, P.PreparationMemory.user_id), (P.Interview, P.Interview.user_id)):
            assert s.scalars(select(model).where(col == ida)).first() is None
        assert s.get(P.User, ida) is None
        # other user's data intact
        assert s.scalars(select(P.Opportunity).where(P.Opportunity.user_id == idb)).first() is not None
        assert s.scalars(select(P.AuditEvent).where(P.AuditEvent.actor_user_id == ida)).first() is None
    assert c.get("/api/v1/auth/me", cookies=cookies_for(a)).status_code == 401  # session gone
    assert ids_b["iid"]


# ---- P15: writes are never transport-retried ----------------------------------------------------------
def test_frontend_never_auto_retries_writes():
    src = (ROOT / "frontend/lib/api/retry.ts").read_text()
    body = src.split("function isIdempotent")[1].split("}")[0]
    assert '"GET"' in body and '"HEAD"' in body
    for verb in ("POST", "PATCH", "PUT", "DELETE"):
        assert verb not in body
    assert "if (!isIdempotent(method)) return false;" in src


# ---- opportunity delete unlinks history explicitly (SQLite has no SET NULL FK) -------------------------
def test_opportunity_delete_unlinks_interviews_but_keeps_them():
    c, repo, _m, a, _b, ida, _idb = _setup()
    oid = c.post("/api/v1/opportunities", json={"target_role": "PM"}, cookies=cookies_for(a)).json()["id"]
    iid = repo.save_interview(ida, _payload(), opportunity_id=oid)
    assert c.delete(f"/api/v1/opportunities/{oid}", cookies=cookies_for(a)).status_code == 200
    with repo.session_factory() as s:
        row = s.get(P.Interview, iid)
        assert row is not None and row.opportunity_id is None
