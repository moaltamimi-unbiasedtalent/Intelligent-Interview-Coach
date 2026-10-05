"""P10B-W11 INTEGRATED CANDIDATE + ADMIN REQUALIFICATION: the cross-plane seams. Real HTTP on a temp database, deterministic doubles, no provider, no network, 0 paid/live
calls. Every test drives BOTH planes (a candidate and one or more Admin principals) on the same tree and proves a seam rather than re-proving a domain."""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
from pathlib import Path

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_w11_docs_"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.application import admin_audit as A
from src.entitlements import EntitlementService
from tests import _admin_matrix as M
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register, reset_token
from tests._role_gov import approve, change_role, request_change, step_up

API = "/api/v1"
PW = "correcthorsebattery"
ROOT = Path(__file__).resolve().parent.parent
DENIED = "Administrator access required."


class W:
    """One temp world: a candidate plane and every Admin persona."""

    def __init__(self):
        self.app, self.repo, self.mail = build_auth_app()
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = account_repo(self.repo)
        self.sf = self.repo.session_factory
        self.n = 0
        self.admins: dict[str, tuple[int, dict]] = {}

    def close(self):
        self.c.__exit__(None, None, None)

    def user(self, role="user", email=None):
        self.n += 1
        email = email or f"w11u{self.n}@x.com"
        register(self.c, email, PW)
        token = login_token(self.c, email, PW)
        ck = cookies_for(token)
        uid = self.c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return uid, ck, email, token

    def persona(self, role):
        if role not in self.admins:
            uid, ck, _e, _t = self.user(role)
            self.admins[role] = (uid, ck)
        return self.admins[role]

    def ck(self, role):
        return self.persona(role)[1]

    def get(self, path, ck, **p):
        return self.c.get(f"{API}{path}", cookies=ck, params=p)

    def post(self, path, ck, body=None):
        return self.c.post(f"{API}{path}", cookies=ck, json={} if body is None else body)


@pytest.fixture()
def w():
    x = W()
    yield x
    x.close()


def denied(r) -> bool:
    return r.status_code == 403 and DENIED in r.text


# ---- one rich candidate used by several seams ------------------------------------------------------------------------------------------------
SENT = {"opportunity": "W11-SENT-OPPORTUNITY-NOTE-4001", "document": "W11-SENT-CV-TEXT-4002", "memory": "W11-SENT-MEMORY-4003", "answer": "W11-SENT-ANSWER-4004",
        "evaluation": "W11-SENT-EVIDENCE-4005", "question": "W11-SENT-TRANSCRIPT-QUESTION-4006"}


def interview_payload():
    return {"configuration": {"target_role": "Registered Nurse"}, "mode": "Record", "status": "completed",
            "questions": [{"position": 0, "canonical_question": SENT["question"], "question_type": "behavioural", "difficulty": "moderate",
                           "timing_guidance": {"recommended_seconds": 100},
                           "answer": {"text": SENT["answer"], "evaluation": {"overall_score": 70, "evidence": SENT["evaluation"]}, "timing_metrics": {}, "visual_metrics": {}}}]}


def rich_candidate(w: W, email="rich@x.com", doc_text=None):
    uid, ck, _e, token = w.user("user", email)
    assert w.post("/auth/onboarding", ck, {"step": 3, "complete": True}).status_code == 200
    opp = w.post("/opportunities", ck, {"target_role": "Product Manager", "company_name": "Acme", "notes": SENT["opportunity"]})
    assert opp.status_code == 201, opp.text
    doc = w.c.post(f"{API}/documents", files={"file": ("cv.txt", (doc_text or SENT["document"]).encode(), "text/plain")}, data={"category": "cv"}, cookies=ck)
    assert doc.status_code in (200, 201), doc.text
    mem = w.post("/memory", ck, {"category": "preparation_goal", "summary": SENT["memory"]})
    assert mem.status_code in (200, 201), mem.text
    iid = w.repo.save_interview(uid, interview_payload())
    return {"uid": uid, "ck": ck, "token": token, "email": email, "opp": opp.json()["id"], "doc": doc.json()["id"], "mem": mem.json()["id"], "iid": iid}


def admin_get_routes():
    return [r for r in M.routes() if r.methods == ("GET",)]


def url(path: str) -> str:
    return API + re.sub(r"\{[^}]+\}", "0", path)


# ======================================================================== K1 candidate lifecycle + safe Admin metadata
def test_k1_candidate_lifecycle_admin_sees_only_safe_metadata(w):
    cand = rich_candidate(w)
    for role in M.ROLES:
        ck = w.ck(role)
        r = w.get(f"/admin/users/{cand['uid']}", ck)
        if "platform.users.read" in M.role_perms(role):
            assert r.status_code == 200, role
            body = r.text
            assert not [s for s in SENT.values() if s in body], role
            assert {"account", "access", "sessions"} <= set(r.json())
        else:
            assert denied(r), role
    # the account metadata an Admin may see is an allow-listed projection
    d = w.get(f"/admin/users/{cand['uid']}", w.ck("platform_admin")).json()["account"]
    assert set(d) <= {"user_id", "email", "display_name", "platform_role", "status", "email_verified", "tier", "created_at", "updated_at", "onboarding_completed",
                      "interface_locale", "workspace_count", "active_session_count"}


# ======================================================================== K2 support seam (the one domain-scoped content exception)
def test_k2_candidate_support_ticket_reaches_support_admin_and_internal_notes_never_reach_the_candidate(w):
    uid, ck, _e, _t = w.user("user")
    t = w.post("/support/tickets", ck, {"category": "technical", "subject": "Cannot upload", "message": "W11-TICKET-BODY-5001"})
    assert t.status_code == 201
    tid = t.json()["public_id"]
    sup = w.ck("support_operator")
    d = w.get(f"/admin/support/tickets/{tid}", sup)
    assert d.status_code == 200 and "W11-TICKET-BODY-5001" in d.text
    assert w.post(f"/admin/support/tickets/{tid}/reply", sup, {"body": "W11-CUSTOMER-REPLY-5002"}).status_code in (200, 201)
    assert w.post(f"/admin/support/tickets/{tid}/notes", sup, {"body": "W11-INTERNAL-NOTE-5003"}).status_code in (200, 201)
    mine = w.get(f"/support/tickets/{tid}", ck)
    assert mine.status_code == 200 and "W11-CUSTOMER-REPLY-5002" in mine.text and "W11-INTERNAL-NOTE-5003" not in mine.text
    assert "internal" not in json.dumps(list(mine.json().keys())).lower()
    for role in M.ROLES:                                                                       # only holders of platform.support.read may read the body
        r = w.get(f"/admin/support/tickets/{tid}", w.ck(role))
        if "platform.support.read" in M.role_perms(role):
            assert r.status_code == 200, role
        else:
            assert denied(r) and "W11-TICKET-BODY-5001" not in r.text, role
    assert w.get(f"/support/tickets/{tid}", w.user()[1]).status_code == 404                    # another candidate cannot see it


# ======================================================================== K3 deactivation <-> candidate session
def test_k3_admin_deactivation_revokes_candidate_session_and_reactivation_never_revives_it(w):
    cand = rich_candidate(w, "k3@x.com")
    assert w.get("/auth/me", cand["ck"]).status_code == 200
    adm = w.ck("platform_admin")
    r = w.post(f"/admin/users/{cand['uid']}/status", adm, {"status": "deactivated", "reason": "w11"})
    assert r.status_code == 200 and r.json()["sessions_revoked"] >= 1
    assert w.get("/auth/me", cand["ck"]).status_code == 401                                    # the candidate loses access at once
    assert w.c.post(f"{API}/auth/login", json={"email": "k3@x.com", "password": PW}).status_code == 401
    assert w.post(f"/admin/users/{cand['uid']}/status", adm, {"status": "active"}).status_code == 200
    assert w.get("/auth/me", cand["ck"]).status_code == 401                                    # the old session is NOT revived
    fresh = login_token(w.c, "k3@x.com", PW)
    assert fresh and w.get("/auth/me", cookies_for(fresh)).status_code == 200                  # a new login is required
    assert denied(w.post(f"/admin/users/{cand['uid']}/status", w.ck("support_operator"), {"status": "deactivated"}))


# ======================================================================== K5 pause <-> candidate behaviour
def test_k5_operations_pause_blocks_the_candidate_capability_with_the_bounded_contract_and_recovery_paths_stay_open(w):
    from types import SimpleNamespace
    from src.api import dependencies as deps

    calls = SimpleNamespace(built=0, ran=0)

    class Fake:
        def run(self, *a, **k):
            calls.ran += 1
            raise ValueError("fake agent ran")

    def factory():
        calls.built += 1
        return Fake()

    w.app.dependency_overrides[deps.get_agent_service] = factory
    cand = rich_candidate(w, "k5@x.com")
    ops = w.ck("operations_admin")
    body = {"goal": "Prepare me for an interview", "target_role": "Nurse"}
    p = w.post("/admin/pause/agent", ops, {"paused": True, "expected_revision": 0, "reason": "W11-SECRET-INTERNAL-REASON"})
    assert p.status_code == 200
    r = w.post("/agent/run", cand["ck"], body)
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_paused" and r.headers.get("X-Request-Id")
    assert "W11-SECRET-INTERNAL-REASON" not in r.text and "@" not in r.text                     # the reason stays Admin-only
    assert calls.built == 0 and calls.ran == 0                                                 # refused before any service or model is built
    for path in ("/auth/account/export", "/capabilities", "/privacy/legal", "/auth/me", "/auth/plan"):
        assert w.c.get(f"{API}{path}", cookies=cand["ck"]).status_code == 200, path           # recovery / account / privacy / legal / saved data stay available
    assert w.post("/admin/pause/agent", ops, {"paused": False, "expected_revision": 1, "reason": "resumed"}).status_code == 200
    assert w.post("/agent/run", cand["ck"], body).status_code != 503 and calls.built == 1       # resume restores admission under the existing rules
    assert denied(w.post("/admin/pause/agent", w.ck("platform_admin"), {"paused": True, "expected_revision": 2, "reason": "x"}))   # platform_admin has no config.manage


# ======================================================================== K6 feature flag <-> candidate behaviour
def test_k6_flag_off_restricts_the_candidate_capability_without_touching_entitlement_or_authorization(w, monkeypatch):
    from src.platform_config import flags as F
    F.install(w.sf, environment="development")                                                # what build_repository does in a real process
    cand = rich_candidate(w, "k6@x.com")
    before_plan = w.get("/auth/plan", cand["ck"]).json()
    before_caps = w.c.get(f"{API}/capabilities").json()
    assert before_caps["company_research_enabled"] is True
    adm = w.ck("platform_admin")                                                               # holds platform.flags.manage
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    r = w.c.put(f"{API}/admin/flags/external_research", cookies=adm, json={"enabled": False, "expected_revision": 0, "reason": "w11 restriction"})
    assert r.status_code == 200, r.text
    assert w.c.get(f"{API}/capabilities").json()["company_research_enabled"] is False
    from src.copilot.research.service import default_research_service
    assert default_research_service().health()["enabled"] is False                            # the backend itself is restricted (not just the UI); no provider is called
    assert w.get("/auth/plan", cand["ck"]).json() == before_plan                               # no entitlement change
    assert denied(w.get("/admin/home", cand["ck"]))                                            # no authorization change
    assert w.c.put(f"{API}/admin/flags/external_research", cookies=adm, json={"enabled": None, "expected_revision": 1, "reason": "restore"}).status_code == 200
    assert w.c.get(f"{API}/capabilities").json()["company_research_enabled"] is True            # restored
    assert denied(w.c.put(f"{API}/admin/flags/external_research", cookies=cand["ck"], json={"enabled": True, "expected_revision": 2, "reason": "x"}))


# ======================================================================== K4 product subscription <-> candidate entitlement; billing never touches it
from tests.test_billing_w10_5 import TERMS, env, rig, snapshot  # noqa: E402,F401  (fixtures + helper)


def test_k4_admin_plan_assignment_drives_the_candidates_entitlement_and_billing_events_never_do(env, rig):  # noqa: F811 - fixtures imported from the W10.5 suite
    from sqlalchemy import select as sel
    from src.persistence import BillingPayment
    uid, cand = env.user("user")
    b1, _ = env.user("billing_admin")
    b2, _ = env.user("billing_admin")
    _, adm = env.user("platform_admin")
    assert env.c.get(f"{API}/auth/plan", cookies=cand).json()["plan"]["plan_code"] == "basic" if "plan" in env.c.get(f"{API}/auth/plan", cookies=cand).json() else True
    r = env.c.post(f"{API}/admin/users/{uid}/plan", json={"plan_code": "premium"}, cookies=adm)
    assert r.status_code == 200, r.text
    seen = env.c.get(f"{API}/auth/plan", cookies=cand).json()
    assert "premium" in json.dumps(seen).lower()                                              # the candidate's own plan view reflects the Admin-assigned subscription
    base = snapshot(env, uid)
    pv = rig.plan_version("premium")
    a = rig.svc.request_price_change(pv, **TERMS, reason="x", actor_user_id=b1)
    rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=b2)                # commercial-term change
    rig.ev("customer_created", "cus_w", customer_ref="cus_w", user_id=uid)
    rig.ev("subscription_updated", "s1", subscription_ref="sub_w", customer_ref="cus_w", plan_version_id=pv, state="active")
    rig.ev("invoice_opened", "i1", invoice_ref="inv_w", customer_ref="cus_w", subscription_ref="sub_w", amount_due_minor=1099, currency="EUR")
    rig.ev("payment_failed", "p1", payment_ref="pay_f", invoice_ref="inv_w", amount_minor=1099, currency="EUR", failure_category="declined")          # failed payment
    rig.ev("subscription_updated", "s2", subscription_ref="sub_w", customer_ref="cus_w", plan_version_id=pv, state="past_due", grace_until="2026-12-01T00:00:00+00:00")  # past_due
    rig.ev("payment_succeeded", "p2", payment_ref="pay_w", invoice_ref="inv_w", amount_minor=1099, currency="EUR")
    with rig.env.accounts.session_factory() as s:
        pay = s.scalar(sel(BillingPayment.public_id).where(BillingPayment.provider_payment_id == "pay_w"))
    ra = rig.svc.request_refund(pay, amount_minor=500, reason="x", actor_user_id=b1)
    rig.svc.decide_refund(ra["public_id"], approve=True, actor_user_id=b2)
    assert rig.drain() == ["succeeded"]                                                        # refund
    rig.ev("subscription_updated", "s3", subscription_ref="sub_w", customer_ref="cus_w", plan_version_id=pv, state="cancelled")                      # provider cancellation
    assert snapshot(env, uid) == base                                                          # entitlements, subscription rows and tier unchanged
    assert env.c.get(f"{API}/auth/plan", cookies=cand).json() == seen
    assert "premium" in json.dumps(env.c.get(f"{API}/auth/plan", cookies=cand).json()).lower()


# ======================================================================== K7 knowledge governance <-> candidate retrieval eligibility
from tests.test_knowledge_admin_w10_8 import Harness  # noqa: E402


def test_k7_only_approved_active_knowledge_is_retrieval_eligible_and_no_candidate_content_is_involved(tmp_path):
    h = Harness(tmp_path)
    r = h.upload()
    v = r["version_public_id"]
    h.drain()
    assert h.retriever.retrieve("product manager roadmap") == []                              # unapproved: not eligible
    h.svc.approve(v, actor_user_id=1)
    h.svc.request_index(v, actor_user_id=1)
    h.drain()
    assert h.retriever.retrieve("product manager roadmap") == []                              # indexed but not active: not eligible
    h.svc.activate(v, actor_user_id=1)
    hits = h.retriever.retrieve("product manager roadmap customer evidence")
    assert hits and all(x.chunk.metadata["knowledge_version_id"] == v for x in hits)           # active: eligible, and only that version (the allowlist)
    h.svc.retire(v, actor_user_id=1)
    assert h.retriever.retrieve("product manager roadmap customer evidence") == []             # retired: eligibility ends (SQL is authoritative)
    with h.sf() as s:                                                                          # the governed KB tables carry no candidate content columns
        cols = " ".join(row[1] for t in ("knowledge_sources", "knowledge_source_versions", "knowledge_index_records")
                        for row in s.execute(text(f"PRAGMA table_info({t})")).all()).lower()
    assert not re.search(r"candidate|answer|transcript|memory|owner_user_id|document_id|opportunity", cols)      # created_by is the ADMIN author, never a candidate link


# ======================================================================== K8 AI configuration <-> candidate operation resolution
from tests.test_ai_admin_w10_7 import cfg as ai_cfg  # noqa: E402
from tests.test_ai_admin_w10_7 import env as ai_env  # noqa: E402,F401
from tests.test_ai_admin_w10_7 import rig as ai_rig  # noqa: E402,F401


def test_k8_only_an_approved_active_configuration_changes_what_the_candidate_session_resolves(ai_env, ai_rig):  # noqa: F811 - fixtures imported from the W10.7 suite
    from src.interview_service import InterviewService
    from src.llm import models as MM
    from tests.test_ai_runtime_w10_7 import FakeClient, _icfg, _strategy_json, balanced_session, pricing
    session = balanced_session()
    terra, sol = MM.default_slug(MM.ModelProfile.BALANCED), MM.default_slug(MM.ModelProfile.ADVANCED)

    def strategy_model():
        c = FakeClient([_strategy_json()])
        InterviewService(c, pricing()).generate_strategy(_icfg(), session)
        return c.calls[0]["model"]

    assert strategy_model() == terra                                                           # nothing active: code defaults
    draft = ai_rig.svc.create_draft(name="w11", notes="", config=ai_cfg(balanced="sol"), base_version_id=None, actor_user_id=ai_rig.a)
    ai_rig.svc.validate(draft["public_id"], actor_user_id=ai_rig.a)
    assert strategy_model() == terra                                                           # a draft is never active
    pid = ai_rig.approved(ai_cfg(balanced="sol"))
    assert strategy_model() == terra                                                           # approved is not active
    ai_rig.svc.activate(pid, reason="go", actor_user_id=ai_rig.c)
    assert strategy_model() == sol                                                             # the candidate's Balanced session resolves the governed mapping
    assert MM.effective_interview_profile(session.model) is MM.ModelProfile.BALANCED          # the session still means Balanced; the marker is never rewritten
    ai_rig.svc.rollback(to_code=True, reason="back to code defaults", actor_user_id=ai_rig.c)
    assert strategy_model() == terra                                                           # rollback restores the code-defined mapping
    cand_req = ai_env.c.post(f"{API}/interviews", json={"configuration": {"target_role": "Nurse"}, "model": "evil/arbitrary-model"}, cookies=ai_env.user("user")[1])
    assert cand_req.status_code in (400, 401, 404, 405, 422) or "evil/arbitrary-model" not in cand_req.text      # a browser-supplied model is never honoured


# ======================================================================== K9 account deletion <-> Admin / audit / reporting
def _db_contains(w: W, needle: str) -> list[str]:
    hit = []
    with w.sf() as s:
        for (name,) in s.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")).all():
            if needle in " ".join(str(r) for r in s.execute(text(f"SELECT * FROM {name}")).all()):
                hit.append(name)
    return hit


def _files_contain(needle: str) -> bool:
    base = Path(os.environ["DOCUMENT_STORAGE_DIR"])
    return any(needle.encode() in p.read_bytes() for p in base.rglob("*") if p.is_file())


def test_k9_candidate_deletion_removes_candidate_data_keeps_anonymised_audit_and_leaves_nothing_visible_to_admin(w):
    from src.persistence import AIUsageFact
    K9_DOC = "W11-K9-UNIQUE-CV-FILE-TEXT-7001"
    cand = rich_candidate(w, "k9@x.com", doc_text=K9_DOC)
    other = w.user("user", "k9-other@x.com")
    assert w.post("/opportunities", other[1], {"target_role": "Other"}).status_code == 201
    assert w.post("/support/tickets", cand["ck"], {"category": "technical", "subject": "help", "message": "W11-K9-TICKET-BODY"}).status_code == 201
    with w.sf() as s:
        s.add(AIUsageFact(usage_key="agent:w11-k9", user_id=cand["uid"], workflow="agent", operation="run", model_calls=1, cost_source="unavailable",
                          token_coverage="unknown", cost_coverage="unknown"))
        s.commit()
    audit_before = w.sf().__enter__().execute(text("SELECT count(*) FROM audit_events WHERE actor_user_id=:u"), {"u": cand["uid"]}).scalar()
    assert audit_before > 0 and _db_contains(w, SENT["answer"]) and _files_contain(K9_DOC)
    r = w.c.post(f"{API}/auth/account/delete", cookies=cand["ck"])
    assert r.status_code == 200, r.text                                                        # the audit append-only trigger does not block deletion
    assert "instantly erased" not in r.text.lower() and "all backups" not in r.text.lower()   # no overclaim about backups
    with w.sf() as s:
        assert s.execute(text("SELECT count(*) FROM users WHERE id=:u"), {"u": cand["uid"]}).scalar() == 0
        for table, col in (("opportunities", "user_id"), ("candidate_documents", "user_id"), ("preparation_memories", "user_id"), ("interviews", "user_id"),
                           ("support_tickets", "owner_user_id"), ("ai_usage_facts", "user_id")):
            assert s.execute(text(f"SELECT count(*) FROM {table} WHERE {col}=:u"), {"u": cand["uid"]}).scalar() == 0, table
        assert s.execute(text("SELECT count(*) FROM audit_events WHERE actor_user_id=:u"), {"u": cand["uid"]}).scalar() == 0
        assert s.execute(text("SELECT count(*) FROM audit_events WHERE actor_user_id IS NULL AND event_type LIKE 'account.%'")).scalar() >= audit_before   # evidence survives, anonymised
    assert not _files_contain(K9_DOC)                                                          # the deleted candidate's private file is purged
    for needle in (*SENT.values(), K9_DOC, "W11-K9-TICKET-BODY"):
        assert not _db_contains(w, needle), needle                                             # no row in ANY table still holds the candidate's content
    assert w.get("/opportunities", other[1]).status_code == 200                                # another candidate is untouched
    # nothing about the deleted candidate is visible to any Admin persona
    for role in M.ROLES:
        for route in admin_get_routes():
            if M.expected_allowed(route.permissions, role):
                body = w.c.get(url(route.path), cookies=w.ck(role)).text
                assert "k9@x.com" not in body and "W11-K9-TICKET-BODY" not in body, (role, route.path)
    assert w.get(f"/admin/users/{cand['uid']}", w.ck("platform_admin")).status_code == 404
    assert w.get("/auth/me", cand["ck"]).status_code == 401


# ======================================================================== K10 workspace / member isolation
def _invite_token(mail):
    return mail.sent[-1].body.split("token=")[1].split()[0]


def test_k10_workspace_membership_shares_and_admin_metadata_stay_scoped(w):
    a = rich_candidate(w, "k10a@x.com")
    b = rich_candidate(w, "k10b@x.com")
    c3 = w.user("user", "k10c@x.com")
    wid = w.post("/workspaces", a["ck"], {"name": "Alpha"}).json()["id"]
    w.post(f"/workspaces/{wid}/invite", a["ck"], {"email": "k10b@x.com"})
    assert w.post("/workspaces/invitations/accept", b["ck"], {"token": _invite_token(w.mail)}).status_code in (200, 201)
    assert w.get(f"/workspaces/{wid}", c3[1]).status_code in (403, 404)                       # a non-member cannot read the workspace (IDOR)
    assert w.post(f"/workspaces/{wid}/members/{a['uid']}/remove", b["ck"]).status_code == 403   # a member cannot remove the owner
    sh = w.post("/shares", b["ck"], {"workspace_id": wid, "resource_type": "interview_report", "resource_id": str(b["iid"])})
    assert sh.status_code in (200, 201), sh.text
    assert w.get(f"/shares/resource/interview_report/{b['iid']}", a["ck"]).status_code == 200  # the owner may view what the member shared
    assert w.get(f"/shares/resource/interview_report/{b['iid']}", c3[1]).status_code in (403, 404)
    assert w.post("/shares", c3[1], {"workspace_id": wid, "resource_type": "interview_report", "resource_id": str(a["iid"])}).status_code in (403, 404)
    for role in ("platform_admin", "support_operator"):                                        # Admin workspace metadata is not content access
        det = w.get(f"/admin/workspaces/{wid}", w.ck(role))
        assert det.status_code == 200 and not [x for x in SENT.values() if x in det.text], role
    assert denied(w.get(f"/admin/workspaces/{wid}", w.ck("billing_admin")))
    assert w.post(f"/workspaces/{wid}/members/{b['uid']}/remove", a["ck"]).status_code in (200, 204)
    assert w.get(f"/shares/resource/interview_report/{b['iid']}", a["ck"]).status_code == 404   # removing the member revoked the grants they made
    assert w.get(f"/workspaces/{wid}", b["ck"]).status_code in (403, 404)


# ======================================================================== K11 role governance does not change candidate entitlement
def test_k11_two_person_role_change_changes_admin_permissions_only_never_product_entitlement(w):
    req = w.persona("platform_admin")[1]
    appr = w.user("platform_admin")
    tgt = rich_candidate(w, "k11@x.com")
    by = w.user("user", "k11-bystander@x.com")
    es = EntitlementService(w.sf)
    snap = lambda uid: {k: (v.enabled, v.limit, v.plan_code) for k, v in es.resolve_all(uid).items()}
    t0, b0 = snap(tgt["uid"]), snap(by[0])
    plan0 = w.get("/auth/plan", tgt["ck"]).json()
    r1, r2 = change_role(w.c, req, appr[1], tgt["uid"], "operations_admin", password=PW)
    assert r1.status_code == 200 and r2.status_code == 200 and r2.json()["outcome"] == "applied"
    perms = set(w.get("/auth/me", tgt["ck"]).json()["admin_permissions"])
    assert perms == set(M.role_perms("operations_admin"))                                      # Admin permissions changed appropriately
    assert snap(tgt["uid"]) == t0 and snap(by[0]) == b0                                        # product entitlements unchanged
    assert w.get("/auth/plan", tgt["ck"]).json() == plan0
    assert w.get("/auth/premium/status", tgt["ck"]).status_code == 403                         # an Admin role does not unlock a Premium-only feature
    assert not any("premium" in p for p in perms)


# ======================================================================== P authorization != capability != entitlement != billing
def test_p_authorization_capability_entitlement_and_billing_are_separate_planes(w):
    pa_uid, pa = w.persona("platform_admin")
    prem = rich_candidate(w, "premium@x.com")
    assert w.post(f"/admin/users/{prem['uid']}/plan", pa, {"plan_code": "premium"}).status_code == 200
    assert w.get("/auth/premium/status", prem["ck"]).status_code == 200                       # the product plan grants the product feature...
    assert denied(w.get("/admin/home", prem["ck"])) and denied(w.get("/admin/users", prem["ck"]))   # ...and grants no Admin permission
    assert w.get("/auth/premium/status", pa).status_code == 403                                # an Admin role grants no product feature
    assert "premium" not in json.dumps(w.get("/auth/plan", pa).json()).lower().replace("premium_preview", "")
    plan_before = w.get("/auth/plan", prem["ck"]).json()
    ops = w.ck("operations_admin")
    from src.platform_config import flags as F
    F.install(w.sf, environment="development")
    w.post("/admin/pause/ocr", ops, {"paused": True, "expected_revision": 0, "reason": "w11"})
    w.c.put(f"{API}/admin/flags/external_research", cookies=pa, json={"enabled": False, "expected_revision": 0, "reason": "w11"})
    for kind in ("product", "quality", "operations", "ai-economics"):
        assert w.get(f"/admin/reports/{kind}", ops).status_code == 200                          # reporting is observational
    assert w.get("/auth/plan", prem["ck"]).json() == plan_before                               # pause, flag, reports and AI economics never change the plan
    assert w.get("/auth/premium/status", prem["ck"]).status_code == 200
    assert denied(w.get("/admin/home", prem["ck"]))                                            # pause/flag state never grants authorization
    w.c.put(f"{API}/admin/flags/external_research", cookies=pa, json={"enabled": None, "expected_revision": 1, "reason": "restore"})


# ======================================================================== Q candidate/Admin privacy sentinels on EVERY Admin read surface
def test_q_private_sentinels_never_appear_on_any_admin_read_surface_for_any_persona(w):
    cand = rich_candidate(w, "q@x.com")
    t = w.post("/support/tickets", cand["ck"], {"category": "technical", "subject": "help", "message": "W11-Q-TICKET-BODY-6001"}).json()
    leaks = []
    routes = admin_get_routes()
    for role in M.ROLES:
        for route in routes:
            if not M.expected_allowed(route.permissions, role):
                continue
            body = w.c.get(url(route.path), cookies=w.ck(role)).text
            for name, sent in SENT.items():
                if sent in body:
                    leaks.append((role, route.path, name))
        for extra in (f"/admin/users/{cand['uid']}", f"/admin/support/tickets/{t['public_id']}"):
            r = w.c.get(API + extra, cookies=w.ck(role))
            if any(sent in r.text for sent in SENT.values()):
                leaks.append((role, extra, "detail"))
            if "W11-Q-TICKET-BODY-6001" in r.text and "platform.support.read" not in M.role_perms(role):
                leaks.append((role, extra, "ticket-body-without-support.read"))
    assert not leaks, leaks[:8]
    # Mo conversation / preparation chat live in the agent checkpoint store, which no Admin code path can open
    admin_code = "\n".join(p.read_text() for p in list((ROOT / "src/api/routes").glob("admin*.py")) + list((ROOT / "src/admin_security").glob("*.py")) + list((ROOT / "src/reporting").glob("*.py")))
    assert not re.search(r"checkpoint|AsyncSqliteSaver|SqliteSaver|get_agent_service|chroma", admin_code, re.I)


# ======================================================================== R secret sentinels (candidate + Admin + audit + reporting + errors + logs)
SECRETS = {"OPENROUTER_API_KEY": "sk-or-W11-SENTINEL-SECRET-1", "ADZUNA_APP_KEY": "W11-SENTINEL-ADZUNA-2", "GOOGLE_CLIENT_SECRET": "W11-SENTINEL-GOOGLE-3",
           "BREVO_API_KEY": "W11-SENTINEL-BREVO-4", "REDIS_URL": "redis://:W11-SENTINEL-REDIS-PW-5@h:6379", "DOCUMENT_ENCRYPTION_KEY": "W11-SENTINEL-DOCKEY-6"}


def test_r_secret_sentinels_never_appear_in_candidate_or_admin_surfaces_audit_reports_errors_or_logs(w, monkeypatch, caplog):
    import logging
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    caplog.set_level(logging.DEBUG)
    cand = rich_candidate(w, "r@x.com")
    texts = []
    for path in ("/capabilities", "/auth/me", "/auth/plan", "/auth/account/export"):
        texts.append(w.c.get(f"{API}{path}", cookies=cand["ck"]).text)
    texts.append(w.c.get(f"{API}/no-such-route", cookies=cand["ck"]).text)
    texts.append(w.post("/opportunities", cand["ck"], {"target_role": ""}).text)                # validation error
    texts.append(w.c.post(f"{API}/auth/login", json={"email": "r@x.com", "password": "wrong-password-xx"}).text)
    texts.append(w.c.get(f"{API}/admin/home", cookies=cand["ck"]).text)                          # denial
    for role in M.ROLES:
        for route in admin_get_routes():
            if M.expected_allowed(route.permissions, role):
                texts.append(w.c.get(url(route.path), cookies=w.ck(role)).text)
    with w.sf() as s:
        texts.append(" ".join(str(r) for r in s.execute(text("SELECT event_type, target_id, context FROM audit_events")).all()))
    texts.append(caplog.text)
    blob = "\n".join(texts)
    assert not [v for v in SECRETS.values() if v in blob]
    assert "Bearer " not in blob.replace("Bearer token", "") or "Bearer ey" not in blob


# ======================================================================== S candidate / Admin session boundaries
def test_s_session_boundaries_role_cannot_be_self_assigned_revocation_logout_reset_and_exact_session_step_up(w):
    cand = rich_candidate(w, "s@x.com")
    for path, body in (("/auth/role", {"platform_role": "platform_admin"}), ("/auth/preferences", {"platform_role": "platform_admin"}),
                       ("/auth/onboarding", {"platform_role": "platform_admin"}), ("/auth/account/role", {"role": "platform_admin"})):
        r = w.c.request("POST" if path != "/auth/preferences" else "PATCH", f"{API}{path}", cookies=cand["ck"], json=body)
        assert r.status_code in (404, 405, 422), (path, r.status_code)                         # no API path lets a candidate change a role
    assert w.accounts.get_account(cand["uid"]).platform_role == "user" and denied(w.get("/admin/home", cand["ck"]))
    assert "token" not in json.dumps(w.get("/auth/me", cand["ck"]).json()).lower()               # no token/cookie value in the profile
    # logout invalidates the CURRENT session, and a revoked session stays revoked
    assert w.c.post(f"{API}/auth/logout", cookies=cand["ck"]).status_code in (200, 204)
    assert w.get("/auth/me", cand["ck"]).status_code == 401
    assert w.get("/auth/me", cand["ck"]).status_code == 401
    # password reset revokes every live session
    other = w.user("user", "s2@x.com")
    w.c.post(f"{API}/auth/forgot-password", json={"email": "s2@x.com"})
    tok = reset_token(w.mail)
    assert tok and w.c.post(f"{API}/auth/reset-password", json={"token": tok, "password": "Another-long-passw0rd!"}).status_code == 200
    assert w.get("/auth/me", other[1]).status_code == 401
    # Admin step-up is exact-session only and never touches the candidate plan
    uid, a1, email, _t = w.user("platform_admin", "s-admin@x.com")
    a2 = cookies_for(login_token(w.c, email, PW))
    plan = w.get("/auth/plan", a1).json()
    assert step_up(w.c, a1, PW).status_code == 200
    assert w.get("/admin/step-up", a1).json()["elevated"] is True and w.get("/admin/step-up", a2).json()["elevated"] is False
    assert w.get("/auth/plan", a1).json() == plan


# ======================================================================== AH two candidates + Admin adversarial scenario
def test_ah_cross_user_and_cross_plane_identifier_misuse_leaks_and_mutates_nothing(w):
    a = rich_candidate(w, "aha@x.com")
    b = rich_candidate(w, "ahb@x.com")
    before = {"opp": w.get(f"/opportunities/{b['opp']}", b["ck"]).json(), "mem": len(w.get("/memory", b["ck"]).json() if isinstance(w.get("/memory", b["ck"]).json(), list) else [1])}
    assert w.get(f"/opportunities/{b['opp']}", a["ck"]).status_code in (403, 404)
    assert w.c.patch(f"{API}/opportunities/{b['opp']}", cookies=a["ck"], json={"notes": "hacked"}).status_code in (403, 404)
    assert w.post(f"/opportunities/{b['opp']}/archive", a["ck"]).status_code in (403, 404)
    assert w.c.delete(f"{API}/history/interviews/{b['iid']}", cookies=a["ck"]).status_code in (403, 404)
    assert w.get(f"/documents/{b['doc']}", a["ck"]).status_code in (403, 404)
    assert w.c.delete(f"{API}/documents/{b['doc']}", cookies=a["ck"]).status_code in (403, 404)
    assert w.c.delete(f"{API}/memory/{b['mem']}", cookies=a["ck"]).status_code in (403, 404)
    assert w.post("/shares", a["ck"], {"workspace_id": 1, "resource_type": "interview_report", "resource_id": str(b["iid"])}).status_code in (400, 403, 404, 422)
    assert w.get(f"/opportunities/{b['opp']}", b["ck"]).json() == before["opp"] and w.get(f"/documents/{b['doc']}", b["ck"]).status_code == 200   # B's data intact
    # Admin personas: lacking permission, or holding only metadata permission
    assert denied(w.get("/admin/support/tickets", w.ck("billing_admin"))) and denied(w.get("/admin/privacy/requests", w.ck("support_operator")))
    for role in ("billing_admin", "support_operator", "security_privacy_admin", "platform_admin"):
        for p in (f"/admin/users/{b['uid']}/documents", f"/admin/users/{b['uid']}/interviews", f"/admin/users/{b['uid']}/memory", f"/admin/users/{b['uid']}/transcript"):
            assert w.get(p, w.ck(role)).status_code in (403, 404, 405), (role, p)                # no private-content route exists, even for a metadata persona
    assert denied(w.get("/admin/role-changes", w.ck("support_operator"))) and denied(w.get("/admin/security/incidents", a["ck"]))
    inc = w.post("/admin/security/incidents", w.ck("security_privacy_admin"), {"title": "adv", "severity": "low", "affected_service": "agent"}).json()
    assert w.post(f"/admin/security/incidents/{inc['public_id']}/tickets/link", w.ck("security_privacy_admin"), {"ticket_public_id": "not-a-ticket", "expected_revision": 0}).status_code == 404
    t = w.post("/support/tickets", b["ck"], {"category": "technical", "subject": "s", "message": "W11-AH-TICKET"}).json()
    assert w.get(f"/support/tickets/{t['public_id']}", a["ck"]).status_code == 404               # a ticket identifier is not a capability
    assert w.post(f"/support/tickets/{t['public_id']}/messages", a["ck"], {"body": "x"}).status_code in (403, 404, 422)


# ======================================================================== AI write retry / idempotency across planes
def test_ai_writes_are_idempotent_and_never_transport_retried(w):
    ops = w.ck("operations_admin")
    body = {"job_type": "diagnostic_noop", "payload": {"label": "W11 once"}, "dedupe_id": "w11-k"}
    r1, r2 = w.post("/admin/jobs", ops, body), w.post("/admin/jobs", ops, body)
    assert r1.status_code == 201 and r2.status_code == 201 and r1.json()["created"] is True and r2.json()["created"] is False
    assert r1.json()["job"]["public_id"] == r2.json()["job"]["public_id"]                      # job enqueue idempotency
    req, apr = w.persona("platform_admin")[1], w.user("platform_admin")[1]
    tgt = w.user("user")[0]
    q = request_change(w.c, req, tgt, "support_operator", password=PW).json()["public_id"]
    first, again = approve(w.c, apr, q, password=PW), approve(w.c, apr, q, password=PW)
    assert first.json()["outcome"] == "applied" and again.json()["outcome"] == "replay"         # role approval replay is safe
    assert len(w.sf().__enter__().execute(text("SELECT 1 FROM audit_events WHERE event_type=:t"), {"t": A.ADMIN_ROLE_CHANGE_APPROVED}).all()) == 1
    from sqlalchemy.exc import IntegrityError
    from src.persistence import AIUsageFact
    uid = w.user("user")[0]
    with w.sf() as s:
        s.add(AIUsageFact(usage_key="practice:w11:0", user_id=uid, workflow="practice", operation="evaluate", model_calls=1, cost_source="unavailable", token_coverage="unknown", cost_coverage="unknown"))
        s.commit()
        s.add(AIUsageFact(usage_key="practice:w11:0", user_id=uid, workflow="practice", operation="evaluate", model_calls=1, cost_source="unavailable", token_coverage="unknown", cost_coverage="unknown"))
        with pytest.raises(IntegrityError):
            s.commit()                                                                         # an AI usage unit is counted once
    retry = (ROOT / "frontend/lib/api/retry.ts").read_text()
    assert 'return method === "GET" || method === "HEAD"' in retry                              # transport retry is GET/HEAD only; writes are never re-sent


# ======================================================================== AJ deterministic outage matrix
def test_aj_outages_fail_closed_where_security_requires_and_never_leak(w, monkeypatch):
    from src.api import dependencies as deps
    from src.application.errors import UnavailableServiceError
    from src.application.pause import PauseService, PauseStateUnavailable
    from src.platform_config import flags as F
    from src.platform_config.flags import FeatureFlagService, FeatureFlagStateUnavailable
    cand = rich_candidate(w, "aj@x.com")
    # model/provider unavailable: bounded safe error, request id, no raw provider error
    class Down:
        def run(self, *a, **k):
            raise UnavailableServiceError("The assistant is temporarily unavailable.")
    w.app.dependency_overrides[deps.get_agent_service] = lambda: Down()
    r = w.post("/agent/run", cand["ck"], {"goal": "Prepare me for an interview", "target_role": "Nurse"})
    assert r.status_code == 503 and r.headers.get("X-Request-Id") and "Traceback" not in r.text and "openrouter" not in r.text.lower()
    # pause store unreadable: refused, fail closed, request id, no private data
    monkeypatch.setattr(PauseService, "is_paused", lambda self, cap: (_ for _ in ()).throw(PauseStateUnavailable("x")))
    r = w.post("/agent/run", cand["ck"], {"goal": "Prepare me for an interview", "target_role": "Nurse"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_state_unavailable" and r.headers.get("X-Request-Id")
    monkeypatch.undo()
    # feature-flag store unreadable: the capability is reported OFF (never fail-open)
    F.install(w.sf, environment="development")
    monkeypatch.setattr(FeatureFlagService, "effective", lambda self, key: (_ for _ in ()).throw(FeatureFlagStateUnavailable("x")))
    assert w.c.get(f"{API}/capabilities").json()["company_research_enabled"] is False
    monkeypatch.undo()
    # expired step-up and stale role approval
    req = w.persona("platform_admin")[1]
    apr_uid, apr, _e, _t = w.user("platform_admin")
    tgt = w.user("user")[0]
    q = request_change(w.c, req, tgt, "support_operator", password=PW).json()["public_id"]
    w.accounts.set_platform_role(tgt, "knowledge_admin")                                        # the world moved on: the request is stale
    assert approve(w.c, apr, q, password=PW).status_code == 409 and w.accounts.get_account(tgt).platform_role == "knowledge_admin"
    with w.sf() as s:
        s.execute(text("UPDATE auth_sessions SET elevated_until = datetime('now', '-1 minute') WHERE user_id=:u"), {"u": apr_uid})
        s.commit()
    tgt2 = w.user("user")[0]
    r = w.post("/admin/role-changes", apr, {"target_user_id": tgt2, "role": "support_operator", "reason": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required"
    # terminal job failure becomes ONE in-app alert; billing adapter cannot run outside dev/test
    from src.jobs.service import JobService
    js = JobService(w.sf)
    js.enqueue("diagnostic_noop", {"label": "will fail"})
    js.fail(js.claim("w11-worker"), "configuration_error", retryable=False)
    alerts = w.get("/admin/security/alerts", w.ck("security_privacy_admin")).json()["items"]
    assert [a for a in alerts if a["category"] == "job_failed"] and denied(w.get("/admin/security/alerts", cand["ck"]))
    from src.billing.provider import BillingConfigurationError, resolve_mode
    with pytest.raises(BillingConfigurationError):
        resolve_mode("production", "mock")
