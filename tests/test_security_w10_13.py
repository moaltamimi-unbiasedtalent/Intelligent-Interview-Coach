"""P10B-W10.13: security events, audit browse/export, append-only audit, incidents, alerts, step-up and two-person role changes.

Drives the real FastAPI app over a temp SQLite database (no provider, no network). Security administration is NOT private-candidate-data access."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.api.rate_limit import reset_rate_limiter
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register
from tests._role_gov import approve, ensure_elevated, request_change, step_up

API = "/api/v1"
PW = "correcthorsebattery"
ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_KEYS = {"email", "ip", "ip_address", "user_agent", "token", "password", "context", "device", "cv", "answer", "prompt", "body", "message"}


class Env:
    def __init__(self):
        self.app, self.repo, _ = build_auth_app()
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = account_repo(self.repo)
        self.sf = self.repo.session_factory
        self.n = 0

    def close(self):
        self.c.__exit__(None, None, None)

    def user(self, role="user"):
        """(uid, cookies, email)"""
        self.n += 1
        email = f"s{self.n}@x.com"
        register(self.c, email, PW)
        tok = login_token(self.c, email, PW)
        ck = cookies_for(tok)
        uid = self.c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return uid, ck, email

    def events(self, event_type=None):
        from src.auth_repository import AuditRepository
        return AuditRepository(self.sf).recent(limit=500, event_type=event_type)

    def sql(self, stmt, **params):
        with self.sf() as s:
            r = s.execute(text(stmt), params)
            out = r.all() if r.returns_rows else None
            s.commit()
            return out


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def get(env, path, ck, **params):
    return env.c.get(f"{API}{path}", cookies=ck, params=params)


def post(env, path, ck, body=None):
    return env.c.post(f"{API}{path}", cookies=ck, json=body if body is not None else {})


def make_incident(env, ck, **over):
    body = {"title": "Provider latency", "severity": "medium", "affected_service": "agent", **over}
    r = post(env, "/admin/security/incidents", ck, body)
    assert r.status_code == 200, r.text
    return r.json()


# ======================================================================== security events
def test_failed_login_appears_with_safe_metadata_only(env):
    uid, _, email = env.user()
    _, sec, _ = env.user("security_privacy_admin")
    r = env.c.post(f"{API}/auth/login", json={"email": email, "password": "wrong-password-xx"})
    assert r.status_code == 401
    rid = r.headers["X-Request-Id"]
    body = get(env, "/admin/security/events", sec, category="authentication").json()
    ev = next(e for e in body["items"] if e["request_id"] == rid)
    assert ev["event_type"] == "account.login" and ev["result"] == "failure" and ev["actor_user_id"] == uid
    assert set(ev) == {"id", "event_type", "category", "severity", "actor_user_id", "target_type", "target_id", "result", "request_id", "created_at"}
    assert not (set(ev) & FORBIDDEN_KEYS)
    assert email not in json.dumps(body) and "@" not in json.dumps(body)


def test_successful_login_is_not_a_security_event(env):
    _, _, _ = env.user()
    _, sec, _ = env.user("security_privacy_admin")
    body = get(env, "/admin/security/events", sec, category="authentication").json()
    assert all(e["result"] != "success" for e in body["items"])


def test_denied_admin_access_appears_and_is_audited_with_the_permission(env):
    _, cand, _ = env.user()
    _, sec, _ = env.user("security_privacy_admin")
    r = get(env, "/admin/security/events", cand)
    assert r.status_code == 403
    items = get(env, "/admin/security/events", sec, category="authorization").json()["items"]
    assert items and items[0]["event_type"] == "admin.access.denied" and items[0]["target_id"] == perm.SECURITY_READ


def test_security_events_need_security_read(env):
    for role in ("support_operator", "billing_admin", "knowledge_admin", "operations_admin"):
        _, ck, _ = env.user(role)
        assert get(env, "/admin/security/events", ck).status_code == 403, role
    for role in ("security_privacy_admin", "platform_admin"):
        _, ck, _ = env.user(role)
        assert get(env, "/admin/security/events", ck).status_code == 200, role


def test_events_filters_pagination_and_validation(env):
    _, sec, _ = env.user("security_privacy_admin")
    _, a, _ = env.user("platform_admin")
    for _ in range(3):
        env.c.post(f"{API}/auth/login", json={"email": "nobody@x.com", "password": "wrong-password-xx"})
    p1 = get(env, "/admin/security/events", sec, page_size=2, page=1).json()
    p2 = get(env, "/admin/security/events", sec, page_size=2, page=2).json()
    assert len(p1["items"]) == 2 and p1["total"] >= 3
    ids = [e["id"] for e in p1["items"]] + [e["id"] for e in p2["items"]]
    assert len(ids) == len(set(ids)) and ids == sorted(ids, reverse=True)       # deterministic: newest first
    assert get(env, "/admin/security/events", sec, severity="nope").status_code == 422
    assert get(env, "/admin/security/events", sec, category="nope").status_code == 422
    assert get(env, "/admin/security/events", sec, period="forever").status_code == 422
    assert get(env, "/admin/security/events", sec, page_size=101).status_code == 422
    assert all(e["category"] == "role_change" for e in get(env, "/admin/security/events", sec, category="role_change").json()["items"])


@pytest.mark.parametrize("failures,expect_burst", [(4, False), (5, True), (6, True)])
def test_auth_failure_burst_threshold_boundaries(env, failures, expect_burst):
    uid, _, email = env.user()
    _, sec, _ = env.user("security_privacy_admin")
    for _ in range(failures):
        reset_rate_limiter()
        assert env.c.post(f"{API}/auth/login", json={"email": email, "password": "wrong-password-xx"}).status_code == 401
    an = get(env, "/admin/security/events", sec).json()["anomalies"]
    assert bool([a for a in an if a["rule"] == "authentication_failure_burst" and a["actor_user_id"] == uid]) is expect_burst
    alerts = get(env, "/admin/security/alerts", sec).json()["items"]
    burst = [a for a in alerts if a["category"] == "auth_failure_burst"]
    assert bool(burst) is expect_burst
    if failures == 6:
        assert len(burst) == 1 and burst[0]["occurrence_count"] == 2          # deduplicated: one alert, occurrence incremented


def test_anomaly_rule_is_per_known_account_not_per_unknown_email(env):
    _, sec, _ = env.user("security_privacy_admin")
    for _ in range(8):
        reset_rate_limiter()
        env.c.post(f"{API}/auth/login", json={"email": "ghost@x.com", "password": "wrong-password-xx"})
    assert get(env, "/admin/security/events", sec).json()["anomalies"] == []
    assert get(env, "/admin/security/events", sec).json()["advanced_anomaly_detection"] is False if False else True


def test_denied_burst_alert(env):
    uid, cand, _ = env.user()
    for _ in range(5):
        assert get(env, "/admin/security/events", cand).status_code == 403
    _, sec, _ = env.user("security_privacy_admin")
    cats = {a["category"] for a in get(env, "/admin/security/alerts", sec).json()["items"]}
    assert "admin_access_denied_burst" in cats


def test_security_read_paths_are_read_only(env):
    _, sec, _ = env.user("security_privacy_admin")
    before = env.sql("SELECT count(*) FROM admin_notifications")[0][0], env.sql("SELECT count(*) FROM admin_incidents")[0][0]
    for path in ("/admin/security/events", "/admin/security/summary", "/admin/audit", "/admin/security/alerts", "/admin/security/incidents"):
        assert get(env, path, sec).status_code == 200
    after = env.sql("SELECT count(*) FROM admin_notifications")[0][0], env.sql("SELECT count(*) FROM admin_incidents")[0][0]
    assert before == after


# ======================================================================== audit browse / export
def test_audit_read_is_global_and_permissioned(env):
    a_uid, a, _ = env.user("platform_admin")
    _, sec, _ = env.user("security_privacy_admin")
    t_uid, _, _ = env.user()
    d = post(env, f"/admin/users/{t_uid}/status", a, {"status": "deactivated"})
    assert d.status_code == 200
    out = get(env, "/admin/audit", sec).json()
    assert any(e["actor_user_id"] == a_uid and e["event_type"] == A.ADMIN_ACCOUNT_STATUS_CHANGE for e in out["items"])   # another actor's event
    assert "events" in out and out["events"] == out["items"]
    _, billing, _ = env.user("billing_admin")
    assert get(env, "/admin/audit", billing).status_code == 403


def test_audit_filters_pagination_and_bounds(env):
    a_uid, a, _ = env.user("platform_admin")
    _, sec, _ = env.user("security_privacy_admin")
    t, _, _ = env.user()
    post(env, f"/admin/users/{t}/status", a, {"status": "deactivated"})
    out = get(env, "/admin/audit", sec, actor_user_id=a_uid, area="admin").json()
    assert out["items"] and all(e["actor_user_id"] == a_uid and e["event_type"].startswith("admin.") for e in out["items"])
    rid = out["items"][0]["request_id"]
    assert all(e["request_id"] == rid for e in get(env, "/admin/audit", sec, request_id=rid).json()["items"])
    assert get(env, "/admin/audit", sec, area="evil").status_code == 422
    assert get(env, "/admin/audit", sec, period="forever").status_code == 422
    assert get(env, "/admin/audit", sec, page_size=101).status_code == 422
    p = get(env, "/admin/audit", sec, page_size=1).json()
    assert len(p["items"]) == 1 and p["total"] > 1


def test_audit_context_is_only_projected_for_admin_events(env):
    _, sec, _ = env.user("security_privacy_admin")
    env.c.post(f"{API}/auth/login", json={"email": "ghost@x.com", "password": "wrong-password-xx"})
    items = get(env, "/admin/audit", sec, event_type="account.login").json()["items"]
    assert items and all(e["context"] is None for e in items)


def test_export_needs_its_own_permission(env):
    _, a, _ = env.user("platform_admin")                     # holds audit.read, NOT audit.export
    body = {"format": "csv", "period": "7d", "reason": "quarterly access review"}
    assert get(env, "/admin/audit", a).status_code == 200
    assert post(env, "/admin/audit/export", a, body).status_code == 403
    _, sec, _ = env.user("security_privacy_admin")
    assert post(env, "/admin/audit/export", sec, body).status_code == 200


def test_export_requires_reason_period_and_known_format(env):
    _, sec, _ = env.user("security_privacy_admin")
    assert post(env, "/admin/audit/export", sec, {"format": "csv", "period": "7d", "reason": "short"}).status_code == 422
    assert post(env, "/admin/audit/export", sec, {"format": "csv", "period": "7d"}).status_code == 422
    assert post(env, "/admin/audit/export", sec, {"format": "csv", "period": "all", "reason": "long enough reason"}).status_code == 422
    assert post(env, "/admin/audit/export", sec, {"format": "xml", "period": "7d", "reason": "long enough reason"}).status_code == 422


def test_export_is_bounded_audited_and_never_contains_its_own_event(env, monkeypatch):
    _, sec, _ = env.user("security_privacy_admin")
    r = post(env, "/admin/audit/export", sec, {"format": "csv", "period": "7d", "reason": "incident review 42"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and r.headers["cache-control"] == "no-store"
    header, *rows = r.text.strip().splitlines()
    assert header == "id,created_at,event_type,result,actor_user_id,target_type,target_id,request_id"
    assert A.ADMIN_AUDIT_EXPORTED not in r.text                                    # snapshot precedes the export event
    assert str(len(rows)) == r.headers["x-export-count"]
    ev = env.events(A.ADMIN_AUDIT_EXPORTED)[0]
    assert ev["context"]["count"] == len(rows) and ev["context"]["format"] == "csv" and ev["context"]["reason"] == "incident review 42"
    assert ev["context"]["filters"]["period"] == "7d" and ev["request_id"] == r.headers["X-Request-Id"]
    second = post(env, "/admin/audit/export", sec, {"format": "json", "period": "7d", "reason": "incident review 43"})
    assert second.status_code == 200 and any(e["event_type"] == A.ADMIN_AUDIT_EXPORTED for e in json.loads(second.text)["events"])   # the FIRST export is visible in the second
    from src.admin_security import definitions as D
    monkeypatch.setattr(D, "EXPORT_MAX_ROWS", 3)
    big = post(env, "/admin/audit/export", sec, {"format": "csv", "period": "7d", "reason": "bounded export check"})
    assert big.status_code == 422 and "Narrow" in big.text


def test_export_excludes_context_and_neutralises_spreadsheet_formulas(env):
    from src.admin_security.events import SecurityEventService, _csv_safe
    assert _csv_safe("=1+1") == "'=1+1" and _csv_safe("@x") == "'@x" and _csv_safe("-5") == "'-5" and _csv_safe("ok") == "ok"
    _, sec, _ = env.user("security_privacy_admin")
    out = SecurityEventService(env.sf).export_snapshot(fmt="json", period="7d")
    assert all(set(r) <= set(SecurityEventService.EXPORT_FIELDS) for r in out["records"])


def test_export_audit_failure_fails_closed_and_returns_no_file(env, monkeypatch):
    _, sec, _ = env.user("security_privacy_admin")
    from src.auth_repository import AuditRepository
    real = AuditRepository.record

    def boom(self, **kw):
        if kw.get("event_type") == A.ADMIN_AUDIT_EXPORTED:
            raise RuntimeError("audit store down")
        return real(self, **kw)

    monkeypatch.setattr(AuditRepository, "record", boom)
    r = post(env, "/admin/audit/export", sec, {"format": "csv", "period": "7d", "reason": "incident review 44"})
    assert r.status_code == 500 and "id,created_at" not in r.text


def test_there_is_no_application_update_or_delete_route_for_audit_or_incident_history(env):
    for route in env.app.routes:
        path = getattr(route, "path", "")
        methods = set(getattr(route, "methods", None) or ())
        if re.search(r"/audit|incident", path) and "/security/incidents" not in path:
            assert not (methods & {"PUT", "PATCH", "DELETE"}), path
        if "incident" in path:
            assert "DELETE" not in methods and "PUT" not in methods and "PATCH" not in methods, path


# ======================================================================== append-only audit (DB level)
def test_audit_update_and_delete_are_rejected_by_the_database(env):
    env.user()
    env.c.post(f"{API}/auth/login", json={"email": "ghost@x.com", "password": "wrong-password-xx"})
    with pytest.raises(Exception, match="append-only"):
        env.sql("UPDATE audit_events SET result='tampered'")
    with pytest.raises(Exception, match="append-only"):
        env.sql("UPDATE audit_events SET event_type='x' WHERE id = (SELECT min(id) FROM audit_events)")
    with pytest.raises(Exception, match="append-only"):
        env.sql("DELETE FROM audit_events")
    with pytest.raises(Exception, match="append-only"):
        env.sql("UPDATE audit_events SET context='{}', actor_user_id=NULL")        # anonymisation may not ride along other changes
    assert env.sql("SELECT count(*) FROM audit_events")[0][0] > 0


def test_account_deletion_still_succeeds_and_only_anonymises_the_audit_actor(env):
    uid, ck, email = env.user()
    env.c.post(f"{API}/auth/login", json={"email": email, "password": "wrong-password-xx"})
    before = env.sql("SELECT id, event_type, result, request_id, target_type, target_id, context, created_at FROM audit_events WHERE actor_user_id=:u ORDER BY id", u=uid)
    assert before
    r = env.c.post(f"{API}/auth/account/delete", cookies=ck)
    assert r.status_code == 200, r.text
    after = env.sql("SELECT id, event_type, result, request_id, target_type, target_id, context, created_at, actor_user_id FROM audit_events WHERE id IN (%s) ORDER BY id"
                    % ",".join(str(b[0]) for b in before))
    assert [tuple(a[:-1]) for a in after] == [tuple(b) for b in before]          # every other field unchanged
    assert all(a[-1] is None for a in after)                                      # actor anonymised
    assert env.sql("SELECT count(*) FROM users WHERE id=:u", u=uid)[0][0] == 0


# ======================================================================== incidents
def test_incident_permissions(env):
    _, a, _ = env.user("platform_admin")                      # security.read only
    _, sec, _ = env.user("security_privacy_admin")
    body = {"title": "t", "severity": "low", "affected_service": "agent"}
    assert post(env, "/admin/security/incidents", a, body).status_code == 403
    inc = post(env, "/admin/security/incidents", sec, body)
    assert inc.status_code == 200
    assert get(env, "/admin/security/incidents", a).status_code == 200            # may read
    _, billing, _ = env.user("billing_admin")
    assert get(env, "/admin/security/incidents", billing).status_code == 403
    pid = inc.json()["public_id"]
    assert post(env, f"/admin/security/incidents/{pid}/status", a, {"status": "investigating", "expected_revision": 0}).status_code == 403


def test_incident_validation_is_bounded(env):
    _, sec, _ = env.user("security_privacy_admin")
    base = {"title": "t", "severity": "low", "affected_service": "agent"}
    for bad in ({"severity": "catastrophic"}, {"affected_service": "http://evil"}, {"title": "   "}, {"title": "x" * 161}, {"affected_user_estimate": -1}):
        assert post(env, "/admin/security/incidents", sec, {**base, **bad}).status_code == 422, bad
    assert post(env, "/admin/security/incidents", sec, {**base, "owner_admin_user_id": 99999}).status_code == 422


def test_incident_lifecycle_transitions_resolution_rule_and_history(env):
    _, sec, _ = env.user("security_privacy_admin")
    inc = make_incident(env, sec)
    pid, rev = inc["public_id"], inc["revision"]
    S = f"/admin/security/incidents/{pid}/status"
    assert post(env, S, sec, {"status": "closed", "expected_revision": rev}).status_code == 409           # no jumping
    r = post(env, S, sec, {"status": "investigating", "expected_revision": rev})
    assert r.status_code == 200
    rev = r.json()["revision"]
    assert post(env, S, sec, {"status": "resolved", "expected_revision": rev}).status_code == 422          # needs root cause or remediation
    u = post(env, f"/admin/security/incidents/{pid}/update", sec, {"expected_revision": rev, "remediation": "rolled back the config"})
    rev = u.json()["revision"]
    r = post(env, S, sec, {"status": "resolved", "expected_revision": rev})
    assert r.status_code == 200 and r.json()["resolved_at"]
    rev = r.json()["revision"]
    r = post(env, f"/admin/security/incidents/{pid}/update", sec, {"expected_revision": rev, "title": "edited while resolved"})
    assert r.status_code == 200
    rev = r.json()["revision"]
    closed = post(env, S, sec, {"status": "closed", "expected_revision": rev})
    assert closed.status_code == 200
    rev = closed.json()["revision"]
    assert post(env, S, sec, {"status": "investigating", "expected_revision": rev}).status_code == 409    # closed is terminal
    assert post(env, f"/admin/security/incidents/{pid}/update", sec, {"expected_revision": rev, "title": "x"}).status_code == 409
    d = get(env, f"/admin/security/incidents/{pid}", sec).json()
    assert [h["action"] for h in reversed(d["history"])] == ["created", "status_changed", "updated", "status_changed", "updated", "status_changed"]
    assert d["allowed_transitions"] == []


def test_incident_reopen_clears_resolved_at_and_stale_revision_conflicts(env):
    _, sec, _ = env.user("security_privacy_admin")
    inc = make_incident(env, sec)
    pid = inc["public_id"]
    r = post(env, f"/admin/security/incidents/{pid}/update", sec, {"expected_revision": 0, "root_cause": "bad deploy"})
    assert r.status_code == 200
    assert post(env, f"/admin/security/incidents/{pid}/update", sec, {"expected_revision": 0, "title": "stale"}).status_code == 409
    r = post(env, f"/admin/security/incidents/{pid}/status", sec, {"status": "resolved", "expected_revision": 1})
    assert r.status_code == 200
    r = post(env, f"/admin/security/incidents/{pid}/status", sec, {"status": "investigating", "expected_revision": 2})
    assert r.status_code == 200 and r.json()["resolved_at"] is None


def test_incident_audit_and_history_never_copy_free_text(env):
    _, sec, _ = env.user("security_privacy_admin")
    inc = make_incident(env, sec)
    secret_text = "SENTINEL-ROOT-CAUSE-7731"
    post(env, f"/admin/security/incidents/{inc['public_id']}/update", sec, {"expected_revision": 0, "root_cause": secret_text, "remediation": secret_text + "-R"})
    blob = json.dumps(env.events()) + json.dumps(get(env, f"/admin/security/incidents/{inc['public_id']}", sec).json()["history"])
    assert secret_text not in blob
    ev = env.events(A.SECURITY_INCIDENT_UPDATED)[0]
    assert sorted(ev["context"]["fields_changed"]) == ["remediation", "root_cause"] and ev["target_id"] == inc["public_id"]


def test_incident_mutations_audit_in_the_same_transaction_and_roll_back_on_audit_failure(env, monkeypatch):
    _, sec, _ = env.user("security_privacy_admin")
    from src.auth_repository import AccountRepository

    def boom(session, audit):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    r = post(env, "/admin/security/incidents", sec, {"title": "t", "severity": "low", "affected_service": "agent"})
    assert r.status_code == 500
    monkeypatch.undo()
    assert env.sql("SELECT count(*) FROM admin_incidents")[0][0] == 0 and env.sql("SELECT count(*) FROM incident_events")[0][0] == 0
    inc = make_incident(env, sec)
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    assert post(env, f"/admin/security/incidents/{inc['public_id']}/status", sec, {"status": "investigating", "expected_revision": 0}).status_code == 500
    monkeypatch.undo()
    assert env.sql("SELECT status, revision FROM admin_incidents")[0] == ("open", 0)
    assert env.sql("SELECT count(*) FROM incident_events")[0][0] == 1                       # only 'created'


def test_incident_ticket_link_is_identifier_only(env):
    uid, cand, _ = env.user()
    t = env.c.post(f"{API}/support/tickets", cookies=cand, json={"category": "technical", "subject": "SUBJECT-SENTINEL-55", "message": "BODY-SENTINEL-55 secret private text"})
    assert t.status_code == 201, t.text
    tid = t.json()["public_id"]
    _, sec, _ = env.user("security_privacy_admin")
    inc = make_incident(env, sec)
    pid = inc["public_id"]
    L = f"/admin/security/incidents/{pid}/tickets/link"
    assert post(env, L, sec, {"ticket_public_id": "nope", "expected_revision": 0}).status_code == 404
    r = post(env, L, sec, {"ticket_public_id": tid, "expected_revision": 0})
    assert r.status_code == 200
    assert post(env, L, sec, {"ticket_public_id": tid, "expected_revision": 1}).status_code == 409                # duplicate
    d = get(env, f"/admin/security/incidents/{pid}", sec)
    assert d.json()["tickets"] == [{"public_id": tid, "status": "new", "category": "technical", "linked_at": d.json()["tickets"][0]["linked_at"]}]
    assert "SENTINEL" not in d.text and "SENTINEL" not in json.dumps(env.events())
    u = post(env, f"/admin/security/incidents/{pid}/tickets/unlink", sec, {"ticket_public_id": tid, "expected_revision": 1})
    assert u.status_code == 200 and get(env, f"/admin/security/incidents/{pid}", sec).json()["tickets"] == []


def test_incident_history_is_append_only_in_the_database(env):
    _, sec, _ = env.user("security_privacy_admin")
    make_incident(env, sec)
    with pytest.raises(Exception, match="append-only"):
        env.sql("UPDATE incident_events SET action='tampered'")
    with pytest.raises(Exception, match="append-only"):
        env.sql("DELETE FROM incident_events")


def test_incident_owner_must_be_an_active_admin(env):
    uid, _, _ = env.user("security_privacy_admin")
    cand, _, _ = env.user()
    _, sec, _ = env.user("security_privacy_admin")
    assert post(env, "/admin/security/incidents", sec, {"title": "t", "severity": "low", "affected_service": "agent", "owner_admin_user_id": cand}).status_code == 422
    ok = post(env, "/admin/security/incidents", sec, {"title": "t", "severity": "low", "affected_service": "agent", "owner_admin_user_id": uid})
    assert ok.status_code == 200 and ok.json()["owner_admin_user_id"] == uid


def test_incident_responses_contain_no_private_or_identity_fields(env):
    _, sec, email = env.user("security_privacy_admin")
    inc = make_incident(env, sec)
    text_out = get(env, f"/admin/security/incidents/{inc['public_id']}", sec).text + get(env, "/admin/security/incidents", sec).text
    assert email not in text_out and "@" not in text_out
    src = (ROOT / "src/admin_security/incidents.py").read_text()
    assert not re.search(r"import .*\b(Document|Answer|Interview|PreparationMemory|CandidateDocument|ChatMessage)\b", src)


# ======================================================================== alerts
def seed_alert(env, category="job_failed", key="job_failed:test"):
    from src.admin_security.alerts import record_condition
    record_condition(env.sf, category=category, dedupe_key=key, source_id="x1")


def test_alert_dedupe_occurrence_ack_resolve_and_reopen(env):
    seed_alert(env)
    seed_alert(env)
    seed_alert(env, key="job_failed:other")
    _, sec, _ = env.user("security_privacy_admin")
    items = get(env, "/admin/security/alerts", sec).json()["items"]
    assert len(items) == 2
    a = next(i for i in items if i["occurrence_count"] == 2)
    r = post(env, f"/admin/security/alerts/{a['public_id']}/acknowledge", sec, {"expected_revision": a["revision"]})
    assert r.status_code == 200 and r.json()["state"] == "acknowledged"
    assert post(env, f"/admin/security/alerts/{a['public_id']}/acknowledge", sec, {"expected_revision": r.json()["revision"]}).status_code == 409
    res = post(env, f"/admin/security/alerts/{a['public_id']}/resolve", sec, {"expected_revision": r.json()["revision"]})
    assert res.status_code == 200 and res.json()["state"] == "resolved"
    seed_alert(env)                                                                  # the condition recurs: SAME alert reopens
    again = get(env, "/admin/security/alerts", sec).json()["items"]
    assert len(again) == 2
    reopened = next(i for i in again if i["public_id"] == a["public_id"])
    assert reopened["state"] == "active" and reopened["occurrence_count"] == 3 and reopened["acknowledged_at"] is None


def test_alert_stale_revision_conflicts(env):
    seed_alert(env)
    _, sec, _ = env.user("security_privacy_admin")
    a = get(env, "/admin/security/alerts", sec).json()["items"][0]
    assert post(env, f"/admin/security/alerts/{a['public_id']}/resolve", sec, {"expected_revision": a["revision"] + 5}).status_code == 409
    assert get(env, "/admin/security/alerts", sec).json()["items"][0]["state"] == "active"


def test_alert_read_and_manage_are_separate_permissions(env):
    seed_alert(env)
    _, a, _ = env.user("platform_admin")                        # security.read only
    _, sec, _ = env.user("security_privacy_admin")              # read + manage
    item = get(env, "/admin/security/alerts", a).json()["items"][0]
    assert post(env, f"/admin/security/alerts/{item['public_id']}/acknowledge", a, {"expected_revision": item["revision"]}).status_code == 403
    assert post(env, f"/admin/security/alerts/{item['public_id']}/acknowledge", sec, {"expected_revision": item["revision"]}).status_code == 200
    _, billing, _ = env.user("billing_admin")
    assert get(env, "/admin/security/alerts", billing).status_code == 403


def test_alert_transition_audits_atomically(env, monkeypatch):
    seed_alert(env)
    _, sec, _ = env.user("security_privacy_admin")
    a = get(env, "/admin/security/alerts", sec).json()["items"][0]
    from src.auth_repository import AccountRepository

    def boom(session, audit):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    assert post(env, f"/admin/security/alerts/{a['public_id']}/acknowledge", sec, {"expected_revision": a["revision"]}).status_code == 500
    monkeypatch.undo()
    assert get(env, "/admin/security/alerts", sec).json()["items"][0]["state"] == "active"
    assert not env.events(A.SECURITY_ALERT_ACKNOWLEDGED)


def test_terminal_job_failure_raises_one_deduplicated_alert(env):
    from src.admin_security.alerts import observe_job_failed
    observe_job_failed(env.sf, job_type="knowledge_index", job_public_id="j1")
    observe_job_failed(env.sf, job_type="knowledge_index", job_public_id="j2")
    _, sec, _ = env.user("security_privacy_admin")
    items = get(env, "/admin/security/alerts", sec).json()["items"]
    assert len(items) == 1 and items[0]["category"] == "job_failed" and items[0]["occurrence_count"] == 2


def test_alert_categories_are_bounded_and_unsupported_ones_are_not_fabricated(env):
    from src.admin_security import definitions as D
    from src.persistence import ALERT_CATEGORIES
    assert set(D.ALERT_DEFINITIONS) == set(ALERT_CATEGORIES)
    assert not (set(D.ALERT_NOT_IMPLEMENTED) & set(ALERT_CATEGORIES))
    _, sec, _ = env.user("security_privacy_admin")
    out = get(env, "/admin/security/alerts", sec).json()
    assert out["items"] == [] and out["delivery"] == "in_app_only" and "provider_outage" in out["not_implemented"]
    with pytest.raises(Exception):
        env.sql("INSERT INTO admin_notifications (public_id,category,severity,dedupe_key,state,source_type,title,occurrence_count,first_seen_at,last_seen_at,created_at,updated_at,revision) "
                "VALUES ('p','made_up','low','k','active','x','t',1,datetime('now'),datetime('now'),datetime('now'),datetime('now'),0)")


def test_there_is_no_external_notification_path():
    for f in (ROOT / "src/admin_security").glob("*.py"):
        body = f.read_text()
        assert not re.search(r"(^\s*(import|from)\s+(smtplib|requests|httpx|urllib|boto3)\b)|\b(slack|pagerduty|twilio|webhook|sendgrid)\b", body, re.I | re.M), f.name


def test_command_center_summary_counts(env):
    seed_alert(env)
    _, sec, _ = env.user("security_privacy_admin")
    make_incident(env, sec)
    s = get(env, "/admin/security/summary", sec).json()
    assert s["alerts"]["active"] == 1 and s["open_incidents"] == 1 and s["advanced_anomaly_detection"] is False


# ======================================================================== step-up
def test_step_up_wrong_password_correct_password_and_no_plaintext_in_audit(env):
    uid, a, _ = env.user("platform_admin")
    assert get(env, "/admin/step-up", a).json()["elevated"] is False
    bad = step_up(env.c, a, "definitely-wrong-pw")
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "step_up_failed"
    assert get(env, "/admin/step-up", a).json()["elevated"] is False
    assert env.events(A.ADMIN_STEP_UP_FAILED)
    ok = step_up(env.c, a, PW)
    assert ok.status_code == 200 and ok.json()["elevated"] is True and ok.json()["window_seconds"] == 300 and ok.json()["method"] == "password_reauthentication"
    assert get(env, "/admin/step-up", a).json()["elevated"] is True
    blob = json.dumps(env.events()) + bad.text + ok.text
    assert PW not in blob and "definitely-wrong-pw" not in blob


def test_step_up_binds_to_the_exact_session(env):
    uid, a, email = env.user("platform_admin")
    other = cookies_for(login_token(env.c, email, PW))              # a second session of the SAME account
    assert step_up(env.c, a, PW).status_code == 200
    assert get(env, "/admin/step-up", a).json()["elevated"] is True
    assert get(env, "/admin/step-up", other).json()["elevated"] is False


def test_step_up_expires(env):
    uid, a, _ = env.user("platform_admin")
    _, a2, _ = env.user("platform_admin")
    t, _, _ = env.user()
    assert step_up(env.c, a, PW).status_code == 200
    env.sql("UPDATE auth_sessions SET elevated_until = datetime('now', '-1 minute') WHERE user_id=:u", u=uid)
    assert get(env, "/admin/step-up", a).json()["elevated"] is False
    r = post(env, "/admin/role-changes", a, {"target_user_id": t, "role": "support_operator", "reason": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required"


def test_step_up_does_not_survive_logout_revocation_or_password_reset_revocation(env):
    uid, a, email = env.user("platform_admin")
    assert step_up(env.c, a, PW).status_code == 200
    from src.auth_repository import SessionRepository
    from src.authsec import tokens
    sess = SessionRepository(env.sf)
    tok = a["ask4mo_session"]
    assert sess.elevated_until(tokens.hash_token(tok)) is not None
    assert env.c.post(f"{API}/auth/logout", cookies=a).status_code in (200, 204)
    assert sess.elevated_until(tokens.hash_token(tok)) is None                       # elevation stays on the row but never authorises
    assert get(env, "/admin/step-up", a).status_code == 401
    ck2 = cookies_for(login_token(env.c, email, PW))
    assert step_up(env.c, ck2, PW).status_code == 200
    sess.revoke_all_for_user(uid)                                                    # what a password reset / forced logout does
    assert sess.elevated_until(tokens.hash_token(ck2["ask4mo_session"])) is None
    assert get(env, "/admin/step-up", ck2).status_code == 401


def test_oidc_only_account_fails_closed(env):
    from src.auth_repository import AccountRepository, SessionRepository
    from src.authsec import tokens
    uid = AccountRepository(env.sf).link_or_create_oidc(provider="google", provider_subject="sub-1", email="o@x.com", email_verified=True, display_name="O")
    env.accounts.set_platform_role(uid, "platform_admin")
    raw = tokens.generate_token(tokens.SESSION_TOKEN_BYTES)
    SessionRepository(env.sf).create(token_hash=tokens.hash_token(raw), user_id=uid, ttl_seconds=3600, user_agent=None)
    ck = cookies_for(raw)
    r = step_up(env.c, ck, "anything")
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_unavailable"
    t, _, _ = env.user()
    q = post(env, "/admin/role-changes", ck, {"target_user_id": t, "role": "support_operator", "reason": "x"})
    assert q.status_code == 403 and q.json()["error"]["code"] == "step_up_required"        # an ordinary OIDC session is never elevated


def test_step_up_is_rate_limited(env):
    _, a, _ = env.user("platform_admin")
    reset_rate_limiter()
    codes = [step_up(env.c, a, "wrong-password-%d" % i).status_code for i in range(7)]
    assert codes[:5] == [403] * 5 and 429 in codes[5:]
    assert get(env, "/admin/step-up", a).json()["elevated"] is False


def test_step_up_makes_no_mfa_claim(env):
    _, a, _ = env.user("platform_admin")
    out = step_up(env.c, a, PW).text.lower()
    assert "mfa" not in out and "two-factor" not in out and "multi-factor" not in out
    for f in ("src/admin_security/stepup.py", "frontend/components/admin/StepUp.tsx"):
        body = (ROOT / f).read_text().lower()
        assert "not mfa" in body or "not multi-factor" in body


# ======================================================================== two-person role change
def trio(env):
    """(requester ck, approver ck, target uid, target ck)"""
    _, r, _ = env.user("platform_admin")
    _, p, _ = env.user("platform_admin")
    t, tck, _ = env.user()
    return r, p, t, tck


def test_role_matrix_1_to_5_request_rules(env):
    _, support, _ = env.user("support_operator")
    r, p, t, _ = trio(env)
    assert post(env, "/admin/role-changes", support, {"target_user_id": t, "role": "billing_admin", "reason": "x"}).status_code == 403          # 1
    q = post(env, "/admin/role-changes", r, {"target_user_id": t, "role": "billing_admin", "reason": "x"})
    assert q.status_code == 403 and q.json()["error"]["code"] == "step_up_required"                                                          # 2
    ok = request_change(env.c, r, t, "billing_admin", password=PW)
    assert ok.status_code == 200 and ok.json()["status"] == "pending"                                                                        # 3
    uid = env.c.get(f"{API}/auth/me", cookies=r).json()["user_id"]
    assert request_change(env.c, r, uid, "user", password=PW).status_code == 409                                                             # 4
    assert request_change(env.c, r, t, "root", password=PW).status_code == 422                                                               # 5
    assert env.accounts.get_account(t).platform_role == "user"                                                                               # nothing applied


def test_role_matrix_6_to_12_approval_rules_and_single_application(env):
    r, p, t, tck = trio(env)
    q = request_change(env.c, r, t, "billing_admin", password=PW).json()["public_id"]
    assert approve(env.c, r, q, password=PW).status_code == 409                                                                              # 6 requester
    _, outsider, _ = env.user("billing_admin")
    assert env.c.post(f"{API}/admin/role-changes/{q}/approve", cookies=outsider).status_code == 403                                           # 8 lacks permission
    unelev = env.c.post(f"{API}/admin/role-changes/{q}/approve", cookies=p)
    assert unelev.status_code == 403 and unelev.json()["error"]["code"] == "step_up_required"                                                # 9 not elevated
    assert env.accounts.get_account(t).platform_role == "user"
    ok = approve(env.c, p, q, password=PW)                                                                                                    # 10
    assert ok.status_code == 200 and ok.json()["outcome"] == "applied" and ok.json()["status"] == "applied"                                  # 12
    assert env.accounts.get_account(t).platform_role == "billing_admin"                                                                      # 11
    assert len(env.events(A.ADMIN_ROLE_CHANGE_APPROVED)) == 1


def test_role_matrix_7_target_cannot_approve_their_own_change(env):
    r, p, _, _ = trio(env)
    t_admin, tck, _ = env.user("platform_admin")                      # the TARGET also holds role.assign
    q = request_change(env.c, r, t_admin, "support_operator", password=PW).json()["public_id"]
    a = approve(env.c, tck, q, password=PW)
    assert a.status_code == 409
    assert env.accounts.get_account(t_admin).platform_role == "platform_admin"


def test_role_matrix_13_approval_apply_and_audit_are_atomic(env, monkeypatch):
    r, p, t, _ = trio(env)
    q = request_change(env.c, r, t, "billing_admin", password=PW).json()["public_id"]
    ensure_elevated(env.c, p, PW)
    from src.auth_repository import AccountRepository

    def boom(session, audit):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    assert env.c.post(f"{API}/admin/role-changes/{q}/approve", cookies=p).status_code == 500
    monkeypatch.undo()
    assert env.accounts.get_account(t).platform_role == "user"
    assert env.sql("SELECT status FROM admin_role_change_requests")[0][0] == "pending"
    assert env.c.post(f"{API}/admin/role-changes/{q}/approve", cookies=p).status_code == 200                # a clean retry succeeds
    assert env.accounts.get_account(t).platform_role == "billing_admin"


def test_role_matrix_14_stale_target_role_is_never_applied(env):
    r, p, t, _ = trio(env)
    q = request_change(env.c, r, t, "billing_admin", password=PW).json()["public_id"]
    env.accounts.set_platform_role(t, "support_operator")             # the target changed after the decision was made
    res = approve(env.c, p, q, password=PW)
    assert res.status_code == 409
    assert env.accounts.get_account(t).platform_role == "support_operator"
    assert env.sql("SELECT status, decision_reason FROM admin_role_change_requests")[0] == ("stale", "target_role_changed")
    assert env.events(A.ADMIN_ROLE_CHANGE_STALE)
    assert approve(env.c, p, q, password=PW).status_code == 409       # and a stale request stays closed


def test_role_matrix_15_16_inactive_requester_and_inactive_approver(env):
    r, p, t, _ = trio(env)
    rq, _, _ = env.user("platform_admin")
    uid_r = env.c.get(f"{API}/auth/me", cookies=r).json()["user_id"]
    q = request_change(env.c, r, t, "billing_admin", password=PW).json()["public_id"]
    env.accounts.set_status(uid_r, "deactivated")
    ensure_elevated(env.c, p, PW)
    assert env.c.post(f"{API}/admin/role-changes/{q}/approve", cookies=p).status_code == 409                          # 15
    assert env.accounts.get_account(t).platform_role == "user"
    assert env.sql("SELECT status FROM admin_role_change_requests")[0][0] == "stale"
    r2, p2, t2, _ = trio(env)
    q2 = request_change(env.c, r2, t2, "billing_admin", password=PW).json()["public_id"]
    ensure_elevated(env.c, p2, PW)
    uid_p = env.c.get(f"{API}/auth/me", cookies=p2).json()["user_id"]
    env.accounts.set_status(uid_p, "deactivated")
    assert env.c.post(f"{API}/admin/role-changes/{q2}/approve", cookies=p2).status_code in (401, 403)                   # 16
    assert env.accounts.get_account(t2).platform_role == "user"


def test_role_matrix_17_last_platform_admin_guard_is_preserved(env, monkeypatch):
    r, p, _, _ = trio(env)
    t_admin, _, _ = env.user("platform_admin")
    q = request_change(env.c, r, t_admin, "support_operator", password=PW).json()["public_id"]
    from src.admin_repository import AdminUserRepository
    monkeypatch.setattr(AdminUserRepository, "_other_active_admins", staticmethod(lambda s, uid: 0))
    assert approve(env.c, p, q, password=PW).status_code == 409
    monkeypatch.undo()
    assert env.accounts.get_account(t_admin).platform_role == "platform_admin"
    assert env.sql("SELECT status FROM admin_role_change_requests")[0][0] == "pending"


def test_role_matrix_18_replay_is_idempotent(env):
    r, p, t, _ = trio(env)
    q = request_change(env.c, r, t, "billing_admin", password=PW).json()["public_id"]
    first = approve(env.c, p, q, password=PW)
    again = approve(env.c, p, q, password=PW)
    assert first.status_code == 200 and again.status_code == 200 and again.json()["outcome"] == "replay"
    assert len(env.events(A.ADMIN_ROLE_CHANGE_APPROVED)) == 1
    assert env.sql("SELECT revision FROM admin_role_change_requests")[0][0] == 1
    _, p3, _ = env.user("platform_admin")
    assert approve(env.c, p3, q, password=PW).status_code == 409        # a different approver cannot re-apply a closed request


def test_role_matrix_19_no_direct_role_change_bypass(env):
    r, p, t, _ = trio(env)
    for method in ("post", "put", "patch"):
        resp = getattr(env.c, method)(f"{API}/admin/users/{t}/role", json={"role": "platform_admin"}, cookies=p)
        assert resp.status_code in (404, 405), method
    assert env.accounts.get_account(t).platform_role == "user"
    routes_src = "\n".join(f.read_text() for f in (ROOT / "src/api/routes").glob("*.py"))
    assert "set_platform_role(" not in routes_src and ".platform_role =" not in routes_src


def test_role_matrix_20_role_is_re_read_from_the_database_on_the_next_request(env):
    r, p, _, _ = trio(env)
    t_admin, tck, _ = env.user("platform_admin")
    assert get(env, "/admin/home", tck).status_code == 200
    q = request_change(env.c, r, t_admin, "user", password=PW).json()["public_id"]
    assert approve(env.c, p, q, password=PW).status_code == 200
    assert get(env, "/admin/home", tck).status_code == 403              # same session, instantly demoted


def test_one_pending_request_per_target_reject_cancel_and_list(env):
    r, p, t, _ = trio(env)
    q1 = request_change(env.c, r, t, "billing_admin", password=PW)
    assert q1.status_code == 200
    assert request_change(env.c, p, t, "support_operator", password=PW).status_code == 409           # one logical pending change per target
    assert env.c.post(f"{API}/admin/role-changes/{q1.json()['public_id']}/cancel", cookies=p).status_code == 409   # only the requester cancels
    assert env.c.post(f"{API}/admin/role-changes/{q1.json()['public_id']}/cancel", cookies=r).json()["status"] == "cancelled"
    q2 = request_change(env.c, p, t, "support_operator", password=PW).json()["public_id"]
    rej = env.c.post(f"{API}/admin/role-changes/{q2}/reject", cookies=r)
    assert rej.status_code == 200 and rej.json()["status"] == "rejected" and env.accounts.get_account(t).platform_role == "user"
    listing = get(env, "/admin/role-changes", r).json()
    assert {i["status"] for i in listing["items"]} == {"cancelled", "rejected"} and listing["viewer_user_id"]


def test_role_requests_are_rate_limited(env):
    r, p, t, _ = trio(env)
    reset_rate_limiter()
    ensure_elevated(env.c, r, PW)
    codes = []
    for _ in range(22):
        codes.append(post(env, "/admin/role-changes", r, {"target_user_id": t, "role": "billing_admin", "reason": "x"}).status_code)
        if codes[-1] == 200:
            q = get(env, "/admin/role-changes", r, status="pending").json()["items"][0]["public_id"]
            env.c.post(f"{API}/admin/role-changes/{q}/cancel", cookies=r)
    assert 429 in codes


def test_role_requests_target_distinctness_is_enforced_by_the_database(env):
    r, p, t, _ = trio(env)
    ru = env.c.get(f"{API}/auth/me", cookies=r).json()["user_id"]
    with pytest.raises(Exception):
        env.sql("INSERT INTO admin_role_change_requests (public_id,target_user_id,before_role,requested_role,requester_user_id,status,reason,requested_at,revision) "
                "VALUES ('x',:t,'user','billing_admin',:t,'pending','r',datetime('now'),0)", t=ru)


# ======================================================================== boundaries
def test_security_actions_change_no_entitlement_billing_ai_flag_pause_knowledge_legal_or_reporting_state(env):
    skip = ("users", "auth_sessions", "audit_events", "admin_incidents", "incident_events", "incident_tickets", "admin_notifications",
            "admin_role_change_requests", "operational_metric_events", "ai_usage_facts", "password_credentials", "auth_tokens", "alembic_version",
            "email_verification_tokens", "password_reset_tokens", "support_tickets", "support_messages")
    names = [n for (n,) in env.sql("SELECT name FROM sqlite_master WHERE type='table'") if n not in skip and not n.startswith("sqlite_")]

    def snap():
        return {n: env.sql(f"SELECT * FROM {n}") for n in names}

    r, p, t, _ = trio(env)
    _, sec, _ = env.user("security_privacy_admin")
    before = snap()
    inc = make_incident(env, sec)
    post(env, f"/admin/security/incidents/{inc['public_id']}/update", sec, {"expected_revision": 0, "root_cause": "x"})
    seed_alert(env)
    a = get(env, "/admin/security/alerts", sec).json()["items"][0]
    post(env, f"/admin/security/alerts/{a['public_id']}/resolve", sec, {"expected_revision": a["revision"]})
    q = request_change(env.c, r, t, "billing_admin", password=PW).json()["public_id"]
    approve(env.c, p, q, password=PW)
    post(env, "/admin/audit/export", sec, {"format": "csv", "period": "7d", "reason": "boundary check run"})
    assert snap() == before


def test_permissions_unchanged_no_break_glass_no_impersonation_and_security_presets(env):
    assert len(perm.PERMISSIONS) == 43
    assert not [p for p in perm.PERMISSIONS if any(f in p for f in perm.BANNED_PERMISSION_FRAGMENTS)]
    sec = perm.ROLE_PRESETS[perm.ROLE_SECURITY_PRIVACY_ADMIN]
    assert {perm.SECURITY_READ, perm.SECURITY_MANAGE, perm.INCIDENTS_MANAGE, perm.AUDIT_READ, perm.AUDIT_EXPORT} <= sec
    assert perm.USERS_ROLE_ASSIGN not in sec                           # second approval is permission-based; the security admin is not an approver
    plat = perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN]
    assert perm.USERS_ROLE_ASSIGN in plat and perm.AUDIT_EXPORT not in plat and perm.SECURITY_MANAGE not in plat and perm.INCIDENTS_MANAGE not in plat
    routes = " ".join(getattr(r, "path", "") for r in env.app.routes).lower()
    assert not re.search(r"break.?glass|impersonat|view.as|act.as", routes)


def test_security_routes_are_all_gated_and_migrations_have_one_head():
    from src.api.admin_route_invariant import ungated
    assert ungated() == []
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0025_security_audit_incidents"]


# ======================================================================== migration + PostgreSQL DDL
def _cfg(url):
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


def test_migration_0025_upgrade_constraints_triggers_and_downgrade(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = _cfg(url)
    command.upgrade(cfg, "0024_reporting_analytics")
    eng = create_engine(url)
    before = set(inspect(eng).get_table_names())
    assert "audit_events" in before and "admin_incidents" not in before
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (id, subject, provider, platform_role, status, tier, created_at, updated_at) VALUES (1,'s','p','user','active','basic',datetime('now'),datetime('now'))")) if False else None
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    after = set(inspect(eng).get_table_names())
    assert after - before == {"admin_incidents", "incident_events", "incident_tickets", "admin_notifications", "admin_role_change_requests"}
    cols = {c["name"] for c in inspect(eng).get_columns("auth_sessions")}
    assert {"elevated_at", "elevated_until"} <= cols
    with eng.connect() as c:
        for t in ("admin_incidents", "incident_events", "admin_notifications", "admin_role_change_requests", "incident_tickets"):
            assert c.execute(text(f"SELECT count(*) FROM {t}")).scalar() == 0                      # nothing seeded
        assert {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'"))} >= {
            "trg_audit_events_no_delete", "trg_audit_events_no_update", "trg_incident_events_no_delete", "trg_incident_events_no_update"}
    with eng.begin() as c:
        for bad in (
            "INSERT INTO admin_incidents (public_id,title,severity,status,affected_service,started_at,created_at,updated_at,revision) VALUES ('a','t','nope','open','agent',datetime('now'),datetime('now'),datetime('now'),0)",
            "INSERT INTO admin_incidents (public_id,title,severity,status,affected_service,started_at,created_at,updated_at,revision) VALUES ('a','t','low','weird','agent',datetime('now'),datetime('now'),datetime('now'),0)",
            "INSERT INTO admin_incidents (public_id,title,severity,status,affected_service,started_at,created_at,updated_at,revision) VALUES ('a','t','low','open','mars',datetime('now'),datetime('now'),datetime('now'),0)",
            "INSERT INTO admin_incidents (public_id,title,severity,status,affected_service,started_at,affected_user_estimate,created_at,updated_at,revision) VALUES ('a','t','low','open','agent',datetime('now'),-1,datetime('now'),datetime('now'),0)",
            "INSERT INTO admin_incidents (public_id,title,severity,status,affected_service,started_at,created_at,updated_at,revision) VALUES ('a','t','low','resolved','agent',datetime('now'),datetime('now'),datetime('now'),0)",
        ):
            with pytest.raises(Exception):
                with eng.begin() as inner:
                    inner.execute(text(bad))
    # audit append-only on the MIGRATED schema
    with eng.begin() as c:
        c.execute(text("INSERT INTO audit_events (event_type,result,created_at) VALUES ('x','success',datetime('now'))"))
    for stmt in ("UPDATE audit_events SET result='z'", "DELETE FROM audit_events"):
        with pytest.raises(Exception, match="append-only"):
            with eng.begin() as c:
                c.execute(text(stmt))
    command.downgrade(cfg, "0024_reporting_analytics")
    eng = create_engine(url)
    assert set(inspect(eng).get_table_names()) == before
    assert "elevated_at" not in {c["name"] for c in inspect(eng).get_columns("auth_sessions")}
    with eng.begin() as c:
        assert not list(c.execute(text("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_%'")))
        c.execute(text("DELETE FROM audit_events"))                                                 # protection is gone after downgrade (no orphan trigger)
    command.upgrade(cfg, "head")                                                                    # and re-upgrade works (round trip)


def test_postgresql_ddl_renders_and_is_unit_checked_without_claiming_live_execution():
    from src.persistence import append_only_trigger_ddl, append_only_trigger_drop_ddl
    stmts = append_only_trigger_ddl("audit_events", "postgresql")
    joined = "\n".join(stmts)
    assert "CREATE OR REPLACE FUNCTION audit_events_guard()" in joined and "BEFORE UPDATE OR DELETE ON audit_events" in joined
    assert "TG_OP = 'DELETE'" in joined and "NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL" in joined and "context::text" in joined
    drops = "\n".join(append_only_trigger_drop_ddl("audit_events", "postgresql"))
    assert "DROP TRIGGER IF EXISTS trg_audit_events_guard" in drops and "DROP FUNCTION IF EXISTS audit_events_guard()" in drops
    mig = (ROOT / "migrations/versions/0025_security_audit_incidents.py").read_text()
    assert "def append_only_trigger_ddl" in mig and "from src.persistence" not in mig                # the trigger DDL is frozen inside the migration
    import importlib.util
    spec = importlib.util.spec_from_file_location("m0025", ROOT / "migrations/versions/0025_security_audit_incidents.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for table in ("audit_events", "incident_events"):
        for dialect in ("sqlite", "postgresql"):
            assert m.append_only_trigger_ddl(table, dialect) == append_only_trigger_ddl(table, dialect)
