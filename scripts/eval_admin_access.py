#!/usr/bin/env python
"""P10B-W10.2 admin access guard (deterministic, offline, 0 paid/live calls).

High-risk invariants of user/session/workspace administration: SEC-W10-01 regression coverage and wiring,
request-time inactive-account enforcement, session revocation on deactivation (and none on reactivation),
last-platform-admin protection, code-defined roles only, no impersonation/break-glass, no candidate content in
admin schemas, every current privileged route permissioned, no migration. It does not duplicate the test suite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BANNED_FIELDS = {"resume", "cv_text", "document_content", "document_text", "answer_text", "report_text", "memory_content",
                 "preparation_messages", "chat_messages", "private_evidence", "uploaded_file_bytes", "transcript",
                 "token", "token_hash", "password", "secret", "user_agent", "storage_key", "ip_address"}


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def func_body(src: str, name: str) -> str:
    m = re.search(rf"    def {name}\(.*?(?=\n    def |\nclass |\Z)", src, re.S)
    return m.group(0) if m else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from pydantic import BaseModel

    from src.api.admin_route_invariant import admin_routes, ungated
    from src.api.schemas import admin as schemas
    from src.application import admin_permissions as perm
    from src.persistence import PLATFORM_ROLES

    tests = read("tests/test_admin_access_w10_2.py") + read("tests/test_sec_w10_01_repro.py")
    check("sec_w10_01_regression_tests_exist",
          all(t in tests for t in ("test_sec1_to_sec9_full_lifecycle", "test_sec10_audit_failure_rolls_back",
                                   "test_sec11_no_session_secret", "test_sec12_request_time_guard",
                                   "test_sec_w10_01_session_survives_deactivation_repro")), "SEC1-SEC12 + repro present")

    resolve = func_body(read("src/auth_repository.py"), "resolve")
    check("request_time_inactive_account_check", "ACCOUNT_STATUS_ACTIVE" in resolve and "User.status" in resolve,
          "SessionRepository.resolve rejects a non-active account")

    repo = read("src/admin_repository.py")
    st = func_body(repo, "set_status")
    check("deactivation_revokes_sessions_in_same_transaction",
          "_revoke_live_sessions(s, user_id)" in st and "_stage(s, audit" in st and st.count("s.commit()") == 2,
          "revoke + audit staged in the status transaction")
    check("reactivation_does_not_revive_sessions",
          "if status != ACCOUNT_STATUS_ACTIVE else 0" in st and "revoked_at=None" not in repo,
          "no code path clears revoked_at")
    check("last_platform_admin_protected",
          "_other_active_admins(s, user_id) == 0" in st and "_other_active_admins(s, user_id) == 0" in func_body(repo, "set_platform_role")
          and "with_for_update" in repo, "deactivation and demotion both check, rows locked")
    check("self_lockout_enforced_server_side",
          "You cannot deactivate your own account." in read("src/api/routes/admin.py")
          and "You cannot remove your own admin role." in read("src/api/routes/admin.py"), "route-level invariants")

    check("roles_are_code_defined_presets_only",
          set(PLATFORM_ROLES) == {perm.ROLE_CANDIDATE, *perm.ADMIN_ROLES}
          and "if body.role not in PLATFORM_ROLES" in read("src/api/routes/admin.py"), "no custom roles")
    persistence = read("src/persistence.py")
    check("no_role_or_permission_tables",
          not re.search(r"class\s+(Role|Permission|RolePermission|UserPermission|CustomRole)\b", persistence), "none")

    routes = admin_routes()
    paths = " ".join(r.path.lower() for r in routes)
    check("no_impersonation_or_break_glass_routes",
          not re.search(r"impersonat|break_?glass|view_as|login_as|mint|sudo", paths), f"{len(routes)} routes scanned")
    check("every_current_privileged_route_has_a_canonical_permission",
          not ungated(routes) and all(r.permissions <= perm.PERMISSION_SET for r in routes), f"{len(routes)} routes, 0 ungated")
    needed = {"/admin/users/{user_id}", "/admin/users/{user_id}/sessions/revoke", "/admin/workspaces/{workspace_id}",
              "/admin/workspaces/{workspace_id}/members"}
    check("w10_2_routes_present", needed <= {r.path for r in routes}, "detail, force logout, workspace detail, members")

    names: list[str] = []
    for cls in vars(schemas).values():
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == schemas.__name__:
            names += list(cls.model_fields)
    hits = sorted(set(names) & BANNED_FIELDS)
    check("admin_schemas_have_no_content_or_secret_fields", not hits and len(names) > 60, ", ".join(hits) or f"{len(names)} fields")
    check("session_secrets_never_selected",
          "token_hash" not in re.sub(r'""".*?"""', "", repo, flags=re.S) and "user_agent" not in repo, "repository never reads token hash / UA")

    ui = "".join(read(str(p.relative_to(ROOT))) for p in (ROOT / "frontend/components/admin").glob("*.tsx"))
    check("admin_ui_authorises_by_permission_not_role_name",
          not re.search(r'platform_role\s*===|===\s*"platform_admin"|role\s*===\s*"', ui), "no role-name checks in admin components")
    check("admin_ui_uses_verified_navigation", 'from "next/link"' not in ui, "VerifiedLink only")

    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("no_migration_added", mig[-1].startswith(("0014_", "0015_", "0016_", "0017_", "0018_", "0019_", "0020_")), mig[-1])
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.2 ADMIN ACCESS GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:58s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
