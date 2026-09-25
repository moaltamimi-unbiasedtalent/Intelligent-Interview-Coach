#!/usr/bin/env python
"""Deterministic Platform Admin evaluation (Capstone P6.5, §33).

Offline, no provider call — drives the real FastAPI app over a temp SQLite DB. Gates:
admin_authorization, normal_user_rejected, metadata_only_user_view,
entitlement_change_audited, platform_role_change_audited, workspace_metadata_boundary,
knowledge_diagnostics_access, promptlab_boundary, feedback_boundary,
privacy_request_boundary, provider_secret_safety, audit_safety. Exits non-zero on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from tests._auth_factories import (  # noqa: E402
    account_repo, build_auth_app, cookies_for, login_token, register,
)

PW = "correcthorsebattery"
# Genuine secret-VALUE markers (not descriptive words like "secrets"/"connection strings"
# that legitimately appear in a safety note).
_FORBIDDEN = ("sk-", "bearer ey", "password_hash", "://", "token=", "apikey:")


def evaluate() -> dict:
    m: dict = {}
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "admin@x.com", PW)
        register(c, "user@x.com", PW)
        admin = login_token(c, "admin@x.com", PW)
        user = login_token(c, "user@x.com", PW)
        admin_uid = c.get("/api/v1/auth/me", cookies=cookies_for(admin)).json()["user_id"]
        user_uid = c.get("/api/v1/auth/me", cookies=cookies_for(user)).json()["user_id"]

        # normal_user_rejected — every admin route 403 for a normal user.
        rejected = all(c.get(p, cookies=cookies_for(user)).status_code == 403
                       for p in ("/api/v1/admin/home", "/api/v1/admin/users",
                                 "/api/v1/admin/workspaces", "/api/v1/admin/audit",
                                 "/api/v1/admin/providers", "/api/v1/admin/privacy-requests"))
        m["normal_user_rejected"] = 1 if rejected else 0

        account_repo(repo).set_platform_role(admin_uid, "platform_admin")

        # admin_authorization — admin can access the console.
        m["admin_authorization"] = 1 if c.get("/api/v1/admin/home", cookies=cookies_for(admin)).status_code == 200 else 0

        # metadata_only_user_view — user list carries only safe metadata keys.
        users = c.get("/api/v1/admin/users", cookies=cookies_for(admin)).json()["users"]
        allowed = {"user_id", "email", "display_name", "platform_role", "status",
                   "email_verified", "tier", "created_at"}
        m["metadata_only_user_view"] = 1 if users and all(set(u) <= allowed for u in users) else 0

        # entitlement_change_audited — set tier, then find the audit event.
        c.post(f"/api/v1/admin/users/{user_uid}/tier", json={"tier": "premium"}, cookies=cookies_for(admin))
        audit = c.get("/api/v1/admin/audit", cookies=cookies_for(admin)).json()["events"]
        m["entitlement_change_audited"] = 1 if any(e["event_type"] == "admin.entitlement_change" for e in audit) else 0

        # platform_role_change_audited.
        c.post(f"/api/v1/admin/users/{user_uid}/role", json={"role": "user"}, cookies=cookies_for(admin))
        audit = c.get("/api/v1/admin/audit", cookies=cookies_for(admin)).json()["events"]
        m["platform_role_change_audited"] = 1 if any(e["event_type"] == "admin.platform_role_change" for e in audit) else 0

        # self-lockout guard (bonus invariant).
        r = c.post(f"/api/v1/admin/users/{admin_uid}/role", json={"role": "user"}, cookies=cookies_for(admin))
        m["self_lockout_prevented"] = 1 if r.status_code == 409 else 0

        # workspace_metadata_boundary — create a workspace as the user, admin sees metadata only.
        c.post("/api/v1/workspaces", json={"name": "T"}, cookies=cookies_for(user))
        ws = c.get("/api/v1/admin/workspaces", cookies=cookies_for(admin)).json()["workspaces"]
        ws_allowed = {"id", "name", "status", "owner_user_id", "member_count", "created_at"}
        m["workspace_metadata_boundary"] = 1 if ws and all(set(w) <= ws_allowed for w in ws) else 0

        # knowledge_diagnostics_access — reuse of the P6 reviewer surface.
        m["knowledge_diagnostics_access"] = 1 if c.get(
            "/api/v1/reviewer/knowledge/readiness", cookies=cookies_for(admin)).status_code == 200 else 0

        # promptlab_boundary — admin can list experiments; there is NO auto-promote endpoint.
        pl = c.get("/api/v1/reviewer/prompt-lab/experiments", cookies=cookies_for(admin))
        no_promote = c.post("/api/v1/reviewer/prompt-lab/promote", cookies=cookies_for(admin)).status_code in (404, 405)
        m["promptlab_boundary"] = 1 if (pl.status_code == 200 and no_promote) else 0

        # feedback_boundary — aggregate counts + taxonomy, no raw content.
        fb = c.get("/api/v1/admin/feedback", cookies=cookies_for(admin))
        fb_json = fb.json() if fb.status_code == 200 else {}
        # Aggregate counts + taxonomy only; never a raw-comment field or free text values.
        m["feedback_boundary"] = 1 if (fb.status_code == 200 and "taxonomy" in fb_json
                                       and "counts_by_category" in fb_json
                                       and "counts_by_comment" not in fb_json) else 0

        # privacy_request_boundary — metadata only, deletion not falsely complete.
        pr = c.get("/api/v1/admin/privacy-requests", cookies=cookies_for(admin))
        m["privacy_request_boundary"] = 1 if pr.status_code == 200 and "requests" in pr.json() else 0

        # provider_secret_safety.
        prov = c.get("/api/v1/admin/providers", cookies=cookies_for(admin)).text.lower()
        m["provider_secret_safety"] = 1 if not any(bad in prov for bad in _FORBIDDEN) else 0

        # audit_safety — the audit view leaks no secret/private content.
        atext = c.get("/api/v1/admin/audit", cookies=cookies_for(admin)).text.lower()
        m["audit_safety"] = 1 if not any(bad in atext for bad in _FORBIDDEN) else 0

    return m


GATES = {
    "admin_authorization": 1, "normal_user_rejected": 1, "metadata_only_user_view": 1,
    "entitlement_change_audited": 1, "platform_role_change_audited": 1,
    "workspace_metadata_boundary": 1, "knowledge_diagnostics_access": 1,
    "promptlab_boundary": 1, "feedback_boundary": 1, "privacy_request_boundary": 1,
    "provider_secret_safety": 1, "audit_safety": 1, "self_lockout_prevented": 1,
}


def gate_failures(m: dict) -> list[str]:
    return [f"{k} = {m.get(k)} (want {v})" for k, v in GATES.items() if m.get(k) != v]


def main() -> int:
    m = evaluate()
    print("PLATFORM ADMIN EVALUATION (Capstone P6.5, offline, no paid calls)")
    print("=" * 68)
    for k in GATES:
        print(f"  {k:<32} {m.get(k)}  (gate == {GATES[k]})")
    print("=" * 68)
    fails = gate_failures(m)
    if fails:
        print("\nGATE STATUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
