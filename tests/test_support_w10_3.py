"""P10B-W10.3: customer support and ticketing. Real isolated SQLite; no provider/network call."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select, text

from src.application import admin_audit as A
from src.application import admin_permissions as perm
from tests._auth_factories import cookies_for, login_token, register
from tests.test_admin_foundation_w10_1 import PW, Env

API = "/api/v1"
SECRET_NOTE = "INTERNAL-ONLY-NOTE-7731"
HTML = '<script>alert("x")</script><img src=x onerror=alert(1)>'


@pytest.fixture()
def env():
    from src.api.rate_limit import reset_rate_limiter
    reset_rate_limiter()
    e = Env()
    yield e
    e.close()
    reset_rate_limiter()


def mk(env, role="user"):
    env.n += 1
    email = f"s{env.n}@x.com"
    register(env.c, email, PW)
    tok = login_token(env.c, email, PW)
    uid = env.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["user_id"]
    if role != "user":
        env.accounts.set_platform_role(uid, role)
    return uid, email, cookies_for(tok)


def new_ticket(env, ck, **over):
    body = {"category": "technical", "subject": "Cannot upload", "message": "It fails every time.", **over}
    r = env.c.post(f"{API}/support/tickets", json=body, cookies=ck)
    assert r.status_code == 201, r.text
    return r.json()


def admin_get(env, ck, ref):
    return env.c.get(f"{API}/admin/support/tickets/{ref}", cookies=ck)


# ---------------- candidate: create / list / detail / reply ----------------------------------------------

def test_create_ticket_persists_ticket_and_first_message_atomically(env):
    uid, _, ck = mk(env)
    t = new_ticket(env, ck, source_route="/documents?token=secret#x", request_id="req abc/../1")
    assert len(t["public_id"]) == 32 and t["status"] == "new" and t["category"] == "technical"
    d = env.c.get(f"{API}/support/tickets/{t['public_id']}", cookies=ck).json()
    assert [m["author_kind"] for m in d["messages"]] == ["candidate"] and d["can_reply"] is True
    _, _, adm = mk(env, "support_operator")
    a = admin_get(env, adm, t["public_id"]).json()["ticket"]
    assert a["source_route"] == "/documents" and "secret" not in json.dumps(a)   # path only, no query/fragment
    assert a["initial_request_id"] == "reqabc..1" and a["source_environment"] == "test"
    assert a["priority"] == "normal"            # candidate cannot set priority


def test_ticket_creation_rolls_back_without_its_first_message(env, monkeypatch):
    _, _, ck = mk(env)
    from src.persistence import SupportMessage
    monkeypatch.setattr(SupportMessage, "__init__", lambda self, **kw: (_ for _ in ()).throw(RuntimeError("x")))
    r = env.c.post(f"{API}/support/tickets", json={"category": "other", "subject": "s", "message": "m"}, cookies=ck)
    assert r.status_code == 500
    monkeypatch.undo()
    assert env.c.get(f"{API}/support/tickets", cookies=ck).json()["total"] == 0   # no empty ticket


def test_create_validation_and_limits(env):
    _, _, ck = mk(env)
    base = {"category": "other", "subject": "s", "message": "m"}
    for bad in ({**base, "category": "nope"}, {**base, "subject": "   "}, {**base, "message": ""},
                {**base, "subject": "x" * 201}, {**base, "message": "x" * 5001}, {**base, "extra": 1}):
        r = env.c.post(f"{API}/support/tickets", json=bad, cookies=ck)
        assert r.status_code in (400, 422), bad
    assert env.c.post(f"{API}/support/tickets", json={**base, "subject": "x" * 200, "message": "x" * 5000},
                      cookies=ck).status_code == 201
    assert env.c.get(f"{API}/support/tickets", cookies=ck).json()["total"] == 1


def test_every_category_is_accepted(env):
    from src.persistence import SUPPORT_CATEGORIES
    _, _, ck = mk(env)
    for c in SUPPORT_CATEGORIES[:5]:
        assert env.c.post(f"{API}/support/tickets", json={"category": c, "subject": "s", "message": "m"},
                          cookies=ck).status_code == 201
    assert len(SUPPORT_CATEGORIES) == 12


def test_candidate_list_is_paginated_owner_scoped_and_detail_has_no_internal_fields(env):
    _, _, a = mk(env)
    _, _, b = mk(env)
    for i in range(3):
        new_ticket(env, a, subject=f"A{i}")
    tb = new_ticket(env, b, subject="B only")
    p1 = env.c.get(f"{API}/support/tickets?page=1&page_size=2", cookies=a).json()
    p2 = env.c.get(f"{API}/support/tickets?page=2&page_size=2", cookies=a).json()
    assert p1["total"] == 3 and len(p1["items"]) == 2 and len(p2["items"]) == 1
    assert tb["public_id"] not in json.dumps([p1, p2])
    d = env.c.get(f"{API}/support/tickets/{p1['items'][0]['public_id']}", cookies=a).json()
    assert set(d) == {"public_id", "category", "status", "subject", "created_at", "updated_at", "can_reply", "messages"}
    assert set(d["messages"][0]) == {"id", "author_kind", "body", "created_at"}
    assert env.c.get(f"{API}/support/tickets?page_size=51", cookies=a).status_code == 422


def test_cross_user_isolation_for_read_and_reply(env):
    _, _, a = mk(env)
    _, _, b = mk(env)
    tb = new_ticket(env, b)["public_id"]
    assert env.c.get(f"{API}/support/tickets/{tb}", cookies=a).status_code == 404
    assert env.c.post(f"{API}/support/tickets/{tb}/messages", json={"message": "hi"}, cookies=a).status_code == 404
    assert env.c.get(f"{API}/support/tickets/{'0' * 32}", cookies=a).status_code == 404   # same 404 as foreign
    assert env.c.get(f"{API}/support/tickets/{tb}", cookies=b).status_code == 200


def test_candidate_reply_reopens_waiting_and_resolved_and_closed_rejects(env):
    _, _, ck = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, ck)["public_id"]
    st = lambda s: env.c.post(f"{API}/admin/support/tickets/{ref}/status", json={"status": s}, cookies=adm)
    assert st("waiting_for_customer").status_code == 200
    r = env.c.post(f"{API}/support/tickets/{ref}/messages", json={"message": "here is more"}, cookies=ck)
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and len(r.json()["messages"]) == 2
    assert st("resolved").status_code == 200
    r = env.c.post(f"{API}/support/tickets/{ref}/messages", json={"message": "still broken"}, cookies=ck)
    assert r.json()["status"] == "in_progress"
    assert st("closed").status_code == 200
    r = env.c.post(f"{API}/support/tickets/{ref}/messages", json={"message": "hello?"}, cookies=ck)
    assert r.status_code == 409
    assert env.c.get(f"{API}/support/tickets/{ref}", cookies=ck).json()["can_reply"] is False


def test_candidate_cannot_set_status_priority_assignee_or_notes(env):
    _, _, ck = mk(env)
    ref = new_ticket(env, ck)["public_id"]
    for path, body in (("status", {"status": "closed"}), ("priority", {"priority": "urgent"}),
                       ("assign", {"assignee_user_id": 1}), ("notes", {"body": "x"}), ("reply", {"body": "x"})):
        assert env.c.post(f"{API}/admin/support/tickets/{ref}/{path}", json=body, cookies=ck).status_code == 403, path
    for path in ("notes", "internal_notes", "internal-notes"):
        assert env.c.get(f"{API}/support/tickets/{ref}/{path}", cookies=ck).status_code in (404, 405)
    assert env.c.post(f"{API}/support/tickets/{ref}/messages", json={"message": "x", "priority": "urgent"},
                      cookies=ck).status_code == 422   # operational fields are rejected outright
    _, _, adm = mk(env, "support_operator")
    assert admin_get(env, adm, ref).json()["ticket"]["priority"] == "normal"


def test_rate_limit_on_ticket_creation(env):
    _, _, ck = mk(env)
    codes = [env.c.post(f"{API}/support/tickets", json={"category": "other", "subject": "s", "message": "m"},
                        cookies=ck).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429
    _, _, other = mk(env)   # per-user bucket: another candidate is unaffected
    assert env.c.post(f"{API}/support/tickets", json={"category": "other", "subject": "s", "message": "m"},
                      cookies=other).status_code == 201


# ---------------- admin: permissions -----------------------------------------------------------------------

def test_support_permission_matrix(env):
    _, _, cand = mk(env)
    ref = new_ticket(env, cand)["public_id"]
    allowed = {"support_operator": True, "platform_admin": True, "billing_admin": False,
               "knowledge_admin": False, "operations_admin": False, "security_privacy_admin": False}
    for role, ok in allowed.items():
        _, _, ck = mk(env, role)
        assert (env.c.get(f"{API}/admin/support/tickets", cookies=ck).status_code == 200) is ok, role
        assert (admin_get(env, ck, ref).status_code == 200) is ok, role
        assert (env.c.post(f"{API}/admin/support/tickets/{ref}/priority", json={"priority": "high"},
                           cookies=ck).status_code == 200) is ok, role
    assert env.c.get(f"{API}/admin/support/tickets", cookies=cand).status_code == 403
    assert env.c.get(f"{API}/admin/support/assignees", cookies=cand).status_code == 403
    assert perm.ROLE_PRESETS["support_operator"] >= {perm.SUPPORT_READ, perm.SUPPORT_REPLY, perm.SUPPORT_MANAGE, perm.SUPPORT_NOTE}


def test_read_only_support_permission_cannot_mutate(env, monkeypatch):
    # A hypothetical preset holding only support.read must not mutate (permission-by-permission enforcement).
    monkeypatch.setitem(perm.ROLE_PRESETS, "support_operator", frozenset({perm.OVERVIEW_READ, perm.SUPPORT_READ}))
    _, _, cand = mk(env)
    ref = new_ticket(env, cand)["public_id"]
    _, _, ck = mk(env, "support_operator")
    assert admin_get(env, ck, ref).status_code == 200
    for path, body in (("reply", {"body": "x"}), ("notes", {"body": "x"}), ("status", {"status": "triaged"}),
                       ("priority", {"priority": "low"}), ("assign", {"assignee_user_id": None})):
        assert env.c.post(f"{API}/admin/support/tickets/{ref}/{path}", json=body, cookies=ck).status_code == 403, path


# ---------------- admin: queue -------------------------------------------------------------------------------

def test_queue_filters_search_pagination_and_bounds(env):
    cid, cemail, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    refs = [new_ticket(env, cand, category=c, subject=f"T{i}")["public_id"] for i, c in enumerate(("billing", "technical", "other"))]
    env.c.post(f"{API}/admin/support/tickets/{refs[0]}/priority", json={"priority": "urgent"}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{refs[1]}/status", json={"status": "triaged"}, cookies=adm)
    sid = env.c.get(f"{API}/admin/support/assignees", cookies=adm).json()[0]["user_id"]
    env.c.post(f"{API}/admin/support/tickets/{refs[2]}/assign", json={"assignee_user_id": sid}, cookies=adm)
    q = lambda s: env.c.get(f"{API}/admin/support/tickets?{s}", cookies=adm).json()
    assert q("")["total"] == 3 and q("page_size=2")["items"].__len__() == 2 and q("page=2&page_size=2")["items"].__len__() == 1
    assert q("status=triaged")["items"][0]["public_id"] == refs[1]
    assert q("category=billing")["total"] == 1 and q("priority=urgent")["items"][0]["public_id"] == refs[0]
    assert q("assignee=unassigned")["total"] == 2 and q(f"assignee={sid}")["total"] == 1 and q("assignee=me")["total"] == 1
    assert q(f"q={refs[1]}")["total"] == 1 and q(f"q={cemail}")["total"] == 3 and q(f"q={cid}")["total"] == 3
    assert q("q=Cannot")["total"] == 0               # message/subject content is not searched
    for bad in ("status=x", "category=x", "priority=x", "assignee=bob", "page_size=101"):
        assert env.c.get(f"{API}/admin/support/tickets?{bad}", cookies=adm).status_code == 422, bad
    assert '"body"' not in json.dumps(q(""))        # queue rows carry no thread text


def test_admin_detail_contents_and_404(env):
    cid, cemail, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand)["public_id"]
    d = admin_get(env, adm, ref).json()
    assert set(d) == {"ticket", "messages", "internal_notes", "account", "priorities", "statuses"}
    assert d["account"]["email"] == cemail and d["ticket"]["allowed_statuses"][0] == "triaged"
    assert admin_get(env, adm, str(d["ticket"]["id"])).status_code == 200      # numeric id works for admins
    assert admin_get(env, adm, "0" * 32).status_code == 404 and admin_get(env, adm, "999999").status_code == 404
    blob = json.dumps(d).lower()
    for bad in ("resume", "cv_text", "interview answer", "memory_content", "transcript", "token_hash"):
        assert bad not in blob


# ---------------- admin: lifecycle, assignment, replies, notes ---------------------------------------------

def test_status_transitions_are_validated_server_side(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand)["public_id"]
    st = lambda s: env.c.post(f"{API}/admin/support/tickets/{ref}/status", json={"status": s}, cookies=adm)
    assert st("closed_maybe").status_code == 422
    assert st("new").status_code == 409                      # no self-transition
    assert st("triaged").status_code == 200 and st("in_progress").status_code == 200
    assert st("waiting_for_customer").status_code == 200 and st("in_progress").status_code == 200
    assert st("resolved").status_code == 200
    t = admin_get(env, adm, ref).json()["ticket"]
    assert t["resolved_at"] and t["status"] == "resolved"
    assert st("in_progress").status_code == 200              # reopen
    assert admin_get(env, adm, ref).json()["ticket"]["resolved_at"] is None
    assert st("resolved").status_code == 200 and st("closed").status_code == 200
    t = admin_get(env, adm, ref).json()["ticket"]
    assert t["closed_at"] and t["allowed_statuses"] == []
    assert st("in_progress").status_code == 409              # closed is terminal
    for path, body in (("priority", {"priority": "low"}), ("assign", {"assignee_user_id": None}),
                       ("reply", {"body": "x"})):
        assert env.c.post(f"{API}/admin/support/tickets/{ref}/{path}", json=body, cookies=adm).status_code == 409, path


def test_priority_and_assignment(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand)["public_id"]
    for p in ("low", "high", "urgent", "normal"):
        assert env.c.post(f"{API}/admin/support/tickets/{ref}/priority", json={"priority": p}, cookies=adm).status_code == 200
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/priority", json={"priority": "asap"}, cookies=adm).status_code == 422
    assignees = env.c.get(f"{API}/admin/support/assignees", cookies=adm).json()
    assert {a["platform_role"] for a in assignees} <= {"support_operator", "platform_admin"}
    sid = assignees[0]["user_id"]
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/assign", json={"assignee_user_id": sid}, cookies=adm).status_code == 200
    assert admin_get(env, adm, ref).json()["ticket"]["assigned_user_id"] == sid
    cid, *_ = mk(env)                                          # an ordinary candidate account
    bid, *_ = mk(env, "billing_admin")                         # admin without support.manage
    for bad in (cid, bid, 99999):
        assert env.c.post(f"{API}/admin/support/tickets/{ref}/assign", json={"assignee_user_id": bad}, cookies=adm).status_code == 409
    other_op, *_ = mk(env, "support_operator")
    env.accounts.set_status(other_op, "deactivated")
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/assign", json={"assignee_user_id": other_op}, cookies=adm).status_code == 409
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/assign", json={"assignee_user_id": None}, cookies=adm).status_code == 200
    assert admin_get(env, adm, ref).json()["ticket"]["assigned_user_id"] is None


def test_reply_is_customer_visible_and_note_is_not(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand)["public_id"]
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/reply", json={"body": "We are looking into it."}, cookies=adm).status_code == 200
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/notes", json={"body": SECRET_NOTE}, cookies=adm).status_code == 200
    d = admin_get(env, adm, ref).json()
    assert [m["author_kind"] for m in d["messages"]] == ["candidate", "support"]
    assert [n["body"] for n in d["internal_notes"]] == [SECRET_NOTE]
    cand_view = env.c.get(f"{API}/support/tickets/{ref}", cookies=cand)
    assert "We are looking into it." in cand_view.text and SECRET_NOTE not in cand_view.text
    assert "author_user_id" not in cand_view.text and "internal" not in cand_view.text.lower()
    assert SECRET_NOTE not in env.c.get(f"{API}/support/tickets", cookies=cand).text
    # not in the self-service export, not in any audit row
    export = env.c.get(f"{API}/auth/account/export", cookies=cand).text
    assert SECRET_NOTE not in export and "We are looking into it." in export
    with env.repo.session_factory() as s:
        from src.persistence import AuditEvent
        rows = s.scalars(select(AuditEvent)).all()
        assert SECRET_NOTE not in json.dumps([r.context for r in rows], default=str)
        assert "We are looking into it." not in json.dumps([r.context for r in rows], default=str)


def test_audit_events_carry_ids_and_enums_never_text(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand)["public_id"]
    tid = admin_get(env, adm, ref).json()["ticket"]["id"]
    sid = env.c.get(f"{API}/admin/support/assignees", cookies=adm).json()[0]["user_id"]
    r = env.c.post(f"{API}/admin/support/tickets/{ref}/assign", json={"assignee_user_id": sid}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{ref}/status", json={"status": "triaged"}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{ref}/priority", json={"priority": "high"}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{ref}/reply", json={"body": "reply text"}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{ref}/notes", json={"body": "note text"}, cookies=adm)
    for name in (A.ADMIN_SUPPORT_TICKET_ASSIGNED, A.ADMIN_SUPPORT_TICKET_STATUS_CHANGED,
                 A.ADMIN_SUPPORT_TICKET_PRIORITY_CHANGED, A.ADMIN_SUPPORT_REPLY_SENT,
                 A.ADMIN_SUPPORT_INTERNAL_NOTE_CREATED):
        assert name in A.ADMIN_EVENT_NAMES
        ev = env.events(name)[0]
        assert ev["target_id"] == str(tid) and ev["request_id"] and ev["actor_user_id"]
        assert "text" not in json.dumps(ev["context"])
    assert env.events(A.ADMIN_SUPPORT_TICKET_STATUS_CHANGED)[0]["context"]["after"] == "triaged"
    assert env.events(A.ADMIN_SUPPORT_TICKET_ASSIGNED)[0]["request_id"] == r.headers["X-Request-Id"]


@pytest.mark.parametrize("path,body", [("assign", {"assignee_user_id": None}), ("status", {"status": "triaged"}),
                                       ("priority", {"priority": "high"}), ("reply", {"body": "hello"}),
                                       ("notes", {"body": "private"})])
def test_admin_support_mutations_roll_back_when_audit_fails(env, monkeypatch, path, body):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand)["public_id"]
    sid = env.c.get(f"{API}/admin/support/assignees", cookies=adm).json()[0]["user_id"]
    if path == "assign":
        body = {"assignee_user_id": sid}
    before = admin_get(env, adm, ref).json()
    from src.auth_repository import AccountRepository
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(lambda s, a: (_ for _ in ()).throw(RuntimeError("x"))))
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/{path}", json=body, cookies=adm).status_code == 500
    monkeypatch.undo()
    after = admin_get(env, adm, ref).json()
    assert after["ticket"] == before["ticket"] and after["messages"] == before["messages"]
    assert after["internal_notes"] == before["internal_notes"]


def test_html_and_script_content_is_stored_and_returned_as_plain_text_with_limits(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand, subject=HTML[:60], message=HTML)["public_id"]
    d = env.c.get(f"{API}/support/tickets/{ref}", cookies=cand).json()
    assert d["messages"][0]["body"] == HTML and d["subject"] == HTML[:60]       # data, never interpreted
    assert env.c.get(f"{API}/support/tickets/{ref}", cookies=cand).headers["content-type"].startswith("application/json")
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/reply", json={"body": "x" * 5001}, cookies=adm).status_code == 422
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/notes", json={"body": "x" * 5001}, cookies=adm).status_code == 422
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/reply", json={"body": "  \x00 "}, cookies=adm).status_code == 422
    assert env.c.post(f"{API}/admin/support/tickets/{ref}/notes", json={"body": "a\x00b"}, cookies=adm).status_code == 200
    assert admin_get(env, adm, ref).json()["internal_notes"][0]["body"] == "ab"


# ---------------- privacy: export, deletion, boundary ------------------------------------------------------

def test_export_contains_the_visible_conversation_and_states_the_exclusion(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    ref = new_ticket(env, cand, subject="Export me")["public_id"]
    env.c.post(f"{API}/admin/support/tickets/{ref}/reply", json={"body": "Visible reply"}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{ref}/notes", json={"body": SECRET_NOTE}, cookies=adm)
    body = env.c.get(f"{API}/auth/account/export", cookies=cand).json()
    assert body["support_tickets"][0]["subject"] == "Export me"
    assert [m["author"] for m in body["support_tickets"][0]["messages"]] == ["candidate", "support"]
    assert any("support tickets" in i for i in body["scope"]["included"])
    assert any("internal notes" in i for i in body["scope"]["not_included"])
    assert "internal_notes" not in json.dumps(body)


def test_account_deletion_removes_support_content_and_keeps_other_peoples_threads(env):
    cid, _, cand = mk(env)
    oid, _, other = mk(env)
    oid2, _, adm = mk(env, "support_operator")
    mine = new_ticket(env, cand)["public_id"]
    theirs = new_ticket(env, other)["public_id"]
    env.c.post(f"{API}/admin/support/tickets/{mine}/notes", json={"body": SECRET_NOTE}, cookies=adm)
    env.c.post(f"{API}/admin/support/tickets/{theirs}/reply", json={"body": "from op"}, cookies=adm)
    sid = env.c.get(f"{API}/admin/support/assignees", cookies=adm).json()[0]["user_id"]
    env.c.post(f"{API}/admin/support/tickets/{theirs}/assign", json={"assignee_user_id": sid}, cookies=adm)
    assert env.c.post(f"{API}/auth/account/delete", cookies=cand).status_code == 200      # candidate deletes account
    with env.repo.session_factory() as s:
        counts = {t: s.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in
                  ("support_tickets", "support_messages", "support_internal_notes")}
    assert counts == {"support_tickets": 1, "support_messages": 2, "support_internal_notes": 0}
    # deleting the OPERATOR keeps the other candidate's thread, anonymising the operator reference
    assert env.c.post(f"{API}/auth/account/delete", cookies=adm).status_code == 200
    d = env.c.get(f"{API}/support/tickets/{theirs}", cookies=other).json()
    assert [m["author_kind"] for m in d["messages"]] == ["candidate", "support"]
    with env.repo.session_factory() as s:
        assert s.execute(text("SELECT assigned_user_id FROM support_tickets")).scalar() is None
        assert s.execute(text("SELECT COUNT(*) FROM support_messages WHERE author_user_id = :u"), {"u": oid2}).scalar() == 0


def test_command_center_support_counts_are_gated_and_text_free(env):
    _, _, cand = mk(env)
    _, _, adm = mk(env, "support_operator")
    _, _, ops = mk(env, "operations_admin")
    ref = new_ticket(env, cand, message="very private words")["public_id"]
    env.c.post(f"{API}/admin/support/tickets/{ref}/priority", json={"priority": "urgent"}, cookies=adm)
    home = env.c.get(f"{API}/admin/home", cookies=adm).json()
    assert home["support"] == {"open": 1, "unassigned": 1, "waiting_for_customer": 0, "high_or_urgent": 1, "total": 1}
    assert "very private words" not in json.dumps(home) and "sla" not in json.dumps(home).lower()
    assert "support" not in env.c.get(f"{API}/admin/home", cookies=ops).json()


# ---------------- boundaries, routes, schema ----------------------------------------------------------------

def test_candidate_schemas_cannot_carry_internal_or_operational_fields():
    from pydantic import BaseModel
    from src.api.schemas import support as S
    names = []
    for cls in vars(S).values():
        if (isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == S.__name__
                and not cls.__name__.endswith("Request")):   # response models only
            names += list(cls.model_fields)
    for banned in ("internal_notes", "note", "notes", "priority", "assigned_user_id", "assignee_email",
                   "author_user_id", "owner_user_id", "owner_email", "initial_request_id", "source_route"):
        assert banned not in names, banned


def test_new_admin_support_routes_are_all_permissioned_and_no_gateway_actions_exist():
    from src.api.admin_route_invariant import admin_routes, ungated
    routes = admin_routes()
    support = [r for r in routes if r.path.startswith("/admin/support")]
    assert len(support) == 8 and ungated(routes) == []
    assert {p for r in support for p in r.permissions} == {perm.SUPPORT_READ, perm.SUPPORT_REPLY, perm.SUPPORT_MANAGE, perm.SUPPORT_NOTE}
    joined = " ".join(r.path for r in routes).lower()
    for bad in ("impersonat", "break_glass", "view_as", "profile_data", "candidate_data"):
        assert bad not in joined


# ---------------- migration ---------------------------------------------------------------------------------

def _cfg(url):
    from alembic.config import Config
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_fresh_upgrade_from_0014_constraints_and_downgrade(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.exc import IntegrityError

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_cfg(url), "0014_opportunities")
    assert "support_tickets" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(_cfg(url), "head")                         # from an existing 0014 database
    eng = create_engine(url)
    insp = inspect(eng)
    assert {"support_tickets", "support_messages", "support_internal_notes"} <= set(insp.get_table_names())
    idx = {i["name"]: i for i in insp.get_indexes("support_tickets")}
    assert idx["ix_support_tickets_public_id"]["unique"] and "ix_support_tickets_status_updated" in idx
    assert {"ix_support_tickets_owner_updated", "ix_support_tickets_assignee_status"} <= set(idx)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users(id, subject, provider, platform_role, status, email_verified, onboarding_step, created_at, updated_at)"
                       " VALUES (1,'s','p','user','active',0,0,'2026-01-01','2026-01-01')"))
    for col, bad in (("status", "bogus"), ("category", "bogus"), ("priority", "bogus")):
        vals = {"status": "new", "category": "other", "priority": "normal", col: bad}
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text("INSERT INTO support_tickets(public_id, owner_user_id, category, priority, status, subject, created_at, updated_at)"
                               " VALUES ('p1',1,:category,:priority,:status,'s','2026-01-01','2026-01-01')"), vals)
    command.downgrade(_cfg(url), "0014_opportunities")
    assert "support_tickets" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(_cfg(url), "head")                         # round trip
    assert "support_tickets" in inspect(create_engine(url)).get_table_names()
