#!/usr/bin/env python
"""P10B-W10.3 support guard (deterministic, offline, 0 paid/live calls).

High-risk invariants of customer support and ticketing: the physical separation of internal notes, candidate
routes that are owner-scoped and cannot reach them, permissioned admin routes, localized candidate copy, the
privacy export/deletion contract, no SLA/live-integration/attachment claims, and one additive migration.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOCALES = ("en", "de", "fr", "es", "it", "pt", "nl", "ru")
BANNED_CANDIDATE_FIELDS = {"internal_notes", "note", "notes", "priority", "assigned_user_id", "assignee_email",
                           "author_user_id", "owner_user_id", "owner_email", "initial_request_id", "source_route"}


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from pydantic import BaseModel

    from src.api.admin_route_invariant import admin_routes, ungated
    from src.api.schemas import support as cand_schemas
    from src.application import admin_permissions as perm
    from src.persistence import SupportTicket

    mig = read("migrations/versions/0015_support_ticketing.py")
    check("one_additive_support_migration",
          all(t in mig for t in ('"support_tickets"', '"support_messages"', '"support_internal_notes"'))
          and 'down_revision = "0014_opportunities"' in mig and "drop_table" in mig, "0015 chains from 0014; reversible")
    heads = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("migration_head_is_support", heads[-1].startswith(("0015_", "0016_", "0017_", "0018_", "0019_", "0020_", "0021_", "0022_", "0023_", "0024_")), heads[-1])
    check("check_constraints_and_unique_public_id",
          all(c in mig for c in ("ck_support_tickets_status", "ck_support_tickets_category", "ck_support_tickets_priority"))
          and "unique=True" in mig, "status/category/priority CHECKs; unique public id")
    check("internal_notes_are_a_separate_table",
          "class SupportInternalNote" in read("src/persistence.py") and "internal_notes" not in read("src/persistence.py").split("class SupportMessage")[1].split("class SupportInternalNote")[0],
          "own table, own model")
    check("no_sla_or_attachment_columns",
          not {c.name for c in SupportTicket.__table__.columns} & {"sla_due_at", "due_at", "response_due_at", "first_response_at"}
          and "support_attachments" not in mig, "no SLA timestamps; no attachment table")

    repo = read("src/support_repository.py")
    candidate_part = repo.split("# -- admin side")[0]
    check("candidate_methods_never_touch_internal_notes", "SupportInternalNote" not in candidate_part.split("class SupportRepository")[1],
          "candidate side of the repository has no internal-note access")
    cand_routes = read("src/api/routes/support.py")
    check("candidate_routes_are_owner_scoped",
          cand_routes.count("Depends(get_current_user_id)") >= 4 and "SupportInternalNote" not in cand_routes and "internal_note" not in cand_routes
          and "require_permission" not in cand_routes, "authenticated owner only; no admin permission; no internal-note path")
    check("data_export_excludes_internal_notes",
          "support_tickets" in read("src/application/data_export.py") and "SupportInternalNote" not in read("src/application/data_export.py")
          and "internal notes" in read("src/application/data_export.py"), "visible thread exported; exclusion stated")
    deletion = read("src/application/account_deletion_service.py")
    check("account_deletion_covers_support",
          all(m in deletion for m in ("SupportTicket", "SupportMessage", "SupportInternalNote")), "tickets, messages, notes deleted; operator refs anonymized")

    names: list[str] = []
    for cls in vars(cand_schemas).values():
        if (isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == cand_schemas.__name__
                and not cls.__name__.endswith("Request")):
            names += list(cls.model_fields)
    check("candidate_schemas_have_no_internal_fields", not set(names) & BANNED_CANDIDATE_FIELDS, f"{len(names)} response fields")

    routes = admin_routes()
    support = [r for r in routes if r.path.startswith("/admin/support")]
    used = {p for r in support for p in r.permissions}
    check("admin_support_routes_permissioned",
          len(support) == 8 and not ungated(routes)
          and used == {perm.SUPPORT_READ, perm.SUPPORT_REPLY, perm.SUPPORT_MANAGE, perm.SUPPORT_NOTE},
          f"{len(support)} support routes; permissions {sorted(p.split('.')[-1] for p in used)}")
    check("no_impersonation_or_break_glass_or_private_data_routes",
          not re.search(r"impersonat|break_?glass|view_as|candidate_data|profile_data|login_as", " ".join(r.path for r in routes).lower()), "none")
    admin_src = read("src/api/routes/admin_support.py") + repo
    check("audit_payloads_carry_no_text",
          not re.search(r"_stage\([^)]*body", repo) and "ticket_id=t.id, message_id=m.id" in repo and "note_id=n.id" in repo,
          "ids and enum before/after only")
    check("no_live_integrations_in_support_code",
          not re.search(r"smtplib|import requests|httpx|stripe|sendgrid|brevo|build_email_sender|boto3", admin_src + cand_routes), "no email/payment/provider call")
    check("support_permissions_in_registry_only",
          all(p in perm.PERMISSION_SET for p in used) and len(perm.PERMISSIONS) == 43, "43-permission registry unchanged")

    keysets = {}
    for loc in LOCALES:
        src = read(f"frontend/lib/i18n/messages/w103/{loc}.ts")
        body = src.split("support: {")[1].split("dataPrivacy:")[0] if "support: {" in src else ""
        keysets[loc] = set(re.findall(r"^\s+([A-Za-z0-9_]+):", body, re.M))
    check("candidate_support_copy_in_all_eight_locales",
          all(keysets[loc] == keysets["en"] and len(keysets["en"]) > 60 for loc in LOCALES), f"{len(keysets['en'])} keys x 8 locales")
    en = "\n".join(l for l in read("frontend/lib/i18n/messages/w103/en.ts").splitlines() if not l.lstrip().startswith("//"))
    check("copy_makes_no_sla_or_availability_claim", not re.search(r"24/7|within \d+|\bSLA\b|guarantee|always available", en, re.I)
          and "We cannot promise a response time." in en and "do not send email notifications" in en, "no SLA / 24-7 / email promise")
    check("slogan_not_in_support_copy", "Ask More" not in "".join(read(f"frontend/lib/i18n/messages/w103/{l}.ts") for l in LOCALES), "protected slogan untouched")

    ui = "".join(read(f"frontend/components/{d}/{n}") for d, n in (("admin", "SupportQueueView.tsx"), ("admin", "SupportTicketAdminView.tsx"),
                                                                     ("support", "SupportHome.tsx"), ("support", "SupportTicketView.tsx")))
    check("support_ui_uses_verified_navigation_and_plain_text",
          'from "next/link"' not in ui and "dangerouslySetInnerHTML" not in ui and "innerHTML" not in ui, "VerifiedLink; no raw HTML sinks")
    check("support_ui_has_no_role_name_authorisation", not re.search(r'platform_role\s*===|===\s*"platform_admin"', ui), "permission-driven")

    tests = read("tests/test_support_w10_3.py")
    check("leakage_and_isolation_tests_exist",
          all(t in tests for t in ("test_reply_is_customer_visible_and_note_is_not", "test_cross_user_isolation_for_read_and_reply",
                                   "test_account_deletion_removes_support_content", "test_export_contains_the_visible_conversation",
                                   "test_migration_fresh_upgrade_from_0014", "test_html_and_script_content_is_stored")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.3 SUPPORT GUARD\n")
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
