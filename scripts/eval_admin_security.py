#!/usr/bin/env python
"""P10B-W10.13 security, audit and incident guard (deterministic, offline, 0 paid/live calls).

High-risk invariants: permissions stay 43 and no break-glass/impersonation; the security-event schema carries no email/IP/token/user-agent/context/private
content; audit read is global but metadata-only and export needs its own permission, a reason and a bound; the audit table is append-only at the database
level (UPDATE/DELETE rejected) while account deletion's actor anonymisation still works; incidents have a bounded lifecycle, append-only history, identifier-only
ticket links and no delete; alerts are code-defined, deduplicated, acknowledged/resolved only with security.manage and are in-app only; a role change needs a
request, a DIFFERENT approver, neither of them the target, a recent password step-up from both, a fresh DB re-check (stale fails) and applies atomically; there
is no direct role-change bypass; step-up is password re-authentication (not MFA) and an OIDC-only account fails closed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): this evaluator drives the real app, so it MUST NOT inherit the developer's DATABASE_URL, .env or stores. Importing the pytest
# isolation module redirects DATABASE_URL/Chroma to a temp directory, disables .env loading and makes any engine outside the system temp directory FAIL FAST.
import tests.conftest  # noqa: E402,F401  (side effect: isolation)

PW = "correcthorsebattery"
API = "/api/v1"


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from src.admin_security import definitions as D
    from src.api.admin_route_invariant import admin_routes, ungated
    from src.api.rate_limit import reset_rate_limiter
    from src.api.schemas.admin import SecurityEventOut
    from src.application import admin_audit as A
    from src.application import admin_permissions as perm
    from src.persistence import ALERT_CATEGORIES, append_only_trigger_ddl
    from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register
    from tests._role_gov import approve, request_change, step_up

    routes_src = read("src/api/routes/admin_security.py")
    all_routes = "\n".join(f.read_text(encoding="utf-8") for f in (ROOT / "src/api/routes").glob("*.py"))
    pkg_src = "\n".join(f.read_text(encoding="utf-8") for f in (ROOT / "src/admin_security").glob("*.py"))
    ui_src = read("frontend/components/admin/SecurityView.tsx") + read("frontend/components/admin/StepUp.tsx")

    # ---- boundaries
    check("permissions_unchanged_at_43", len(perm.PERMISSIONS) == 43, str(len(perm.PERMISSIONS)))
    check("security_permissions_mapped_to_existing_presets",
          {perm.SECURITY_READ, perm.SECURITY_MANAGE, perm.INCIDENTS_MANAGE, perm.AUDIT_READ, perm.AUDIT_EXPORT} <= perm.ROLE_PRESETS[perm.ROLE_SECURITY_PRIVACY_ADMIN]
          and perm.USERS_ROLE_ASSIGN in perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN] and perm.USERS_ROLE_ASSIGN not in perm.ROLE_PRESETS[perm.ROLE_SECURITY_PRIVACY_ADMIN]
          and perm.AUDIT_EXPORT not in perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN])
    check("no_break_glass_or_impersonation_permission_or_route",
          not [p for p in perm.PERMISSIONS if any(f in p for f in perm.BANNED_PERMISSION_FRAGMENTS)]
          and not re.search(r"break.?glass|impersonat|view.as", " ".join(re.findall(r'@router\.\w+\(\s*"([^"]+)"', all_routes)), re.I)
          and not re.search(r"^\s*(def|class)\s+\w*(break_?glass|impersonat)", pkg_src + all_routes, re.I | re.M))
    check("all_privileged_routes_gated", ungated() == [] and len(admin_routes()) > 128, f"{len(admin_routes())} admin routes, {len(ungated())} ungated")

    # ---- schema / privacy (static)
    fields = set(SecurityEventOut.model_fields)
    check("security_event_schema_safe", not (fields & {"email", "ip", "ip_address", "user_agent", "token", "password", "context", "device", "body"}) and "context" not in fields, ",".join(sorted(fields)))
    check("no_ip_or_device_collection_added", not re.search(r"client_ip|x-forwarded|remote_addr|fingerprint", pkg_src + routes_src, re.I)
          and "user_agent" not in read("migrations/versions/0025_security_audit_incidents.py"))
    check("no_private_content_import", not re.search(r"\b(CandidateDocument|Answer|Interview|PreparationMemory|ChatMessage|SupportMessage|Opportunity)\b", pkg_src.replace("SupportTicket", "")), "no candidate model in admin_security")
    check("no_external_paging", not re.search(r"(^\s*(import|from)\s+(smtplib|requests|httpx|urllib|boto3)\b)|\b(slack|pagerduty|twilio|webhook|sendgrid)\b", pkg_src, re.I | re.M) and "in_app_only" in pkg_src)

    # ---- behaviour on a temp DB
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        accounts = account_repo(repo)
        sf = repo.session_factory
        n = [0]

        def user(role="user"):
            n[0] += 1
            email = f"e{n[0]}@x.com"
            register(c, email, PW)
            ck = cookies_for(login_token(c, email, PW))
            uid = c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
            if role != "user":
                accounts.set_platform_role(uid, role)
            return uid, ck, email

        def sql(stmt, **kw):
            with sf() as s:
                r = s.execute(text(stmt), kw)
                rows = r.all() if r.returns_rows else None
                s.commit()
                return rows

        def raises(stmt, match="append-only"):
            try:
                sql(stmt)
            except Exception as exc:  # noqa: BLE001
                return match in str(exc)
            return False

        get = lambda path, ck, **p: c.get(f"{API}{path}", cookies=ck, params=p)  # noqa: E731
        post = lambda path, ck, body=None: c.post(f"{API}{path}", cookies=ck, json=body or {})  # noqa: E731

        sec_uid, sec, _ = user("security_privacy_admin")
        pa_uid, pa, _ = user("platform_admin")
        pb_uid, pb, _ = user("platform_admin")
        cand_uid, cand, cand_email = user()

        # security events
        c.post(f"{API}/auth/login", json={"email": cand_email, "password": "wrong-password-xx"})
        ev = get("/admin/security/events", sec).json()
        check("security_events_show_failed_auth_without_identity", any(e["event_type"] == "account.login" for e in ev["items"])
              and cand_email not in json.dumps(ev) and all(set(e) == fields for e in ev["items"]))
        check("security_events_gated", get("/admin/security/events", cand).status_code == 403 and get("/admin/security/events", user("billing_admin")[1]).status_code == 403)
        for _ in range(5):
            reset_rate_limiter()
            c.post(f"{API}/auth/login", json={"email": cand_email, "password": "wrong-password-xx"})
        check("auth_burst_rule_deterministic_and_alerts_once",
              any(a["rule"] == "authentication_failure_burst" for a in get("/admin/security/events", sec).json()["anomalies"])
              and len([a for a in get("/admin/security/alerts", sec).json()["items"] if a["category"] == "auth_failure_burst"]) == 1
              and D.AUTH_FAILURE_BURST_THRESHOLD == 5)

        # audit browse / export
        check("audit_global_read_permissioned", any(e["actor_user_id"] != sec_uid for e in get("/admin/audit", sec).json()["items"])
              and get("/admin/audit", user("billing_admin")[1]).status_code == 403)
        body = {"format": "csv", "period": "7d", "reason": "evaluator export check"}
        check("audit_export_separate_permission", post("/admin/audit/export", pa, body).status_code == 403 and post("/admin/audit/export", sec, body).status_code == 200)
        check("audit_export_bounded_and_reasoned", post("/admin/audit/export", sec, {**body, "reason": "no"}).status_code == 422
              and post("/admin/audit/export", sec, {**body, "period": "all"}).status_code == 422 and D.EXPORT_MAX_ROWS == 5000)
        check("audit_export_is_audited", bool(sql("SELECT 1 FROM audit_events WHERE event_type=:t", t=A.ADMIN_AUDIT_EXPORTED)))
        check("no_audit_update_or_delete_route", not [r for r in app.routes if re.search(r"audit", getattr(r, "path", ""))
                                                       and set(getattr(r, "methods", None) or ()) & {"PUT", "PATCH", "DELETE"}])

        # append-only audit + deletion-safe anonymisation
        check("audit_update_blocked_by_database", raises("UPDATE audit_events SET result='x'"))
        check("audit_delete_blocked_by_database", raises("DELETE FROM audit_events"))
        del_uid, del_ck, del_email = user()
        c.post(f"{API}/auth/login", json={"email": del_email, "password": "wrong-password-xx"})
        before = sql("SELECT id, event_type, result, request_id, context, created_at FROM audit_events WHERE actor_user_id=:u ORDER BY id", u=del_uid)
        gone = c.post(f"{API}/auth/account/delete", cookies=del_ck).status_code == 200
        after = sql("SELECT id, event_type, result, request_id, context, created_at, actor_user_id FROM audit_events WHERE id IN (%s) ORDER BY id" % ",".join(str(b[0]) for b in before))
        check("account_deletion_anonymises_actor_only", gone and before and [tuple(a[:-1]) for a in after] == [tuple(b) for b in before] and all(a[-1] is None for a in after))
        ddl = "\n".join(append_only_trigger_ddl("audit_events", "sqlite") + append_only_trigger_ddl("audit_events", "postgresql"))
        check("postgresql_trigger_ddl_rendered_not_claimed_live", "audit_events_guard" in ddl and "NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL" in ddl)

        # incidents
        r = post("/admin/security/incidents", sec, {"title": "Evaluator incident", "severity": "low", "affected_service": "agent"})
        pid = r.json().get("public_id", "")
        check("incident_permission_and_bounded_lifecycle",
              r.status_code == 200 and post("/admin/security/incidents", pa, {"title": "t", "severity": "low", "affected_service": "agent"}).status_code == 403
              and post("/admin/security/incidents", sec, {"title": "t", "severity": "nope", "affected_service": "agent"}).status_code == 422
              and post("/admin/security/incidents", sec, {"title": "t", "severity": "low", "affected_service": "http://x"}).status_code == 422
              and post(f"/admin/security/incidents/{pid}/status", sec, {"status": "closed", "expected_revision": 0}).status_code == 409
              and post(f"/admin/security/incidents/{pid}/status", sec, {"status": "resolved", "expected_revision": 0}).status_code == 422)
        check("incident_history_append_only", raises("UPDATE incident_events SET action='x'") and raises("DELETE FROM incident_events") and bool(sql("SELECT 1 FROM incident_events")))
        check("no_incident_delete_route", not [r for r in app.routes if "incident" in getattr(r, "path", "") and "DELETE" in (getattr(r, "methods", None) or ())])
        t = c.post(f"{API}/support/tickets", cookies=cand, json={"category": "technical", "subject": "EVAL-SUBJECT-SENTINEL", "message": "EVAL-BODY-SENTINEL"})
        tid = t.json().get("public_id", "")
        post(f"/admin/security/incidents/{pid}/tickets/link", sec, {"ticket_public_id": tid, "expected_revision": 0})
        dtl = get(f"/admin/security/incidents/{pid}", sec).text
        check("incident_ticket_links_are_identifier_only", tid in dtl and "SENTINEL" not in dtl and "SENTINEL" not in str(sql("SELECT context FROM audit_events")))

        # alerts
        from src.admin_security.alerts import record_condition
        record_condition(sf, category="job_failed", dedupe_key="job_failed:eval", source_id="j")
        record_condition(sf, category="job_failed", dedupe_key="job_failed:eval", source_id="j")
        al = [a for a in get("/admin/security/alerts", sec).json()["items"] if a["category"] == "job_failed"]
        check("alert_dedupe_and_categories_bounded", len(al) == 1 and al[0]["occurrence_count"] == 2 and set(D.ALERT_DEFINITIONS) == set(ALERT_CATEGORIES) and not set(D.ALERT_NOT_IMPLEMENTED) & set(ALERT_CATEGORIES))
        a0 = al[0]
        check("alert_ack_resolve_need_manage_permission", post(f"/admin/security/alerts/{a0['public_id']}/acknowledge", pa, {"expected_revision": a0["revision"]}).status_code == 403
              and post(f"/admin/security/alerts/{a0['public_id']}/acknowledge", sec, {"expected_revision": a0["revision"] + 9}).status_code == 409
              and post(f"/admin/security/alerts/{a0['public_id']}/acknowledge", sec, {"expected_revision": a0["revision"]}).status_code == 200)

        # step-up + role change
        check("step_up_wrong_password_fails_correct_elevates_session_only",
              step_up(c, pa, "wrong-password-xx").status_code == 403 and get("/admin/step-up", pa).json()["elevated"] is False
              and step_up(c, pa, PW).status_code == 200 and get("/admin/step-up", pa).json()["elevated"] is True
              and get("/admin/step-up", pb).json()["elevated"] is False)
        check("step_up_is_not_mfa", "password_reauthentication" in json.dumps(get("/admin/step-up", pa).json()) and "not multi-factor" in read("src/admin_security/stepup.py").lower()
              and not re.search(r"\b(two-factor|multi-factor|2fa)\b", ui_src, re.I))
        check("role_change_requires_step_up", post("/admin/role-changes", pb, {"target_user_id": cand_uid, "role": "support_operator", "reason": "x"}).status_code == 403)
        q = request_change(c, pa, cand_uid, "support_operator", password=PW)
        qid = q.json().get("public_id", "")
        check("role_change_is_a_pending_request_not_an_application", q.status_code == 200 and accounts.get_account(cand_uid).platform_role == "user")
        check("requester_cannot_approve_or_target_self", approve(c, pa, qid, password=PW).status_code == 409 and request_change(c, pa, pa_uid, "user", password=PW).status_code == 409)
        check("approver_needs_step_up", c.post(f"{API}/admin/role-changes/{qid}/approve", cookies=pb).status_code == 403)
        done = approve(c, pb, qid, password=PW)
        check("distinct_elevated_approver_applies_once_and_audits",
              done.status_code == 200 and accounts.get_account(cand_uid).platform_role == "support_operator"
              and len(sql("SELECT 1 FROM audit_events WHERE event_type=:t", t=A.ADMIN_ROLE_CHANGE_APPROVED)) == 1
              and approve(c, pb, qid, password=PW).json().get("outcome") == "replay" and len(sql("SELECT 1 FROM audit_events WHERE event_type=:t", t=A.ADMIN_ROLE_CHANGE_APPROVED)) == 1)
        q2 = request_change(c, pa, cand_uid, "billing_admin", password=PW).json()["public_id"]
        accounts.set_platform_role(cand_uid, "knowledge_admin")
        check("stale_role_request_fails_and_applies_nothing", approve(c, pb, q2, password=PW).status_code == 409 and accounts.get_account(cand_uid).platform_role == "knowledge_admin"
              and sql("SELECT status FROM admin_role_change_requests WHERE public_id=:p", p=q2)[0][0] == "stale")
        check("no_direct_role_bypass", c.post(f"{API}/admin/users/{cand_uid}/role", cookies=pb, json={"role": "platform_admin"}).status_code in (404, 405)
              and "set_platform_role(" not in all_routes and "/users/{user_id}/role" not in all_routes)

        # OIDC-only fails closed
        from src.auth_repository import AccountRepository, SessionRepository
        from src.authsec import tokens
        oid = AccountRepository(sf).link_or_create_oidc(provider="google", provider_subject="eval-sub", email="o@x.com", email_verified=True, display_name="O")
        accounts.set_platform_role(oid, "platform_admin")
        raw = tokens.generate_token(tokens.SESSION_TOKEN_BYTES)
        SessionRepository(sf).create(token_hash=tokens.hash_token(raw), user_id=oid, ttl_seconds=3600, user_agent=None)
        r = step_up(c, cookies_for(raw), "x")
        check("oidc_only_step_up_fails_closed", r.status_code == 403 and r.json()["error"]["code"] == "step_up_unavailable")

    # ---- structure
    mig = read("migrations/versions/0025_security_audit_incidents.py")
    check("migration_chain_and_nothing_seeded", 'down_revision = "0024_reporting_analytics"' in mig and "bulk_insert" not in mig and "INSERT INTO" not in mig and "def downgrade" in mig and "trg_" in mig)
    heads = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("alembic_head_is_0025", heads[-1].startswith("0025_security_audit_incidents"), heads[-1])
    check("no_w10_14_code", not (ROOT / "docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md").exists())
    check("tests_exist", all(x in read("tests/test_security_w10_13.py") for x in ("test_audit_update_and_delete_are_rejected_by_the_database", "test_role_matrix_14_stale_target_role_is_never_applied",
                                                                             "test_account_deletion_still_succeeds_and_only_anonymises_the_audit_actor", "test_step_up_binds_to_the_exact_session")))
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.13 SECURITY / AUDIT / INCIDENT GUARD (metadata only; no break-glass; step-up is not MFA)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:68s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0   External paging: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
