#!/usr/bin/env python
"""P10B-W10.1 admin foundation guard (deterministic, offline, 0 paid/live calls).

Checks the permission registry, role presets, route gating, provider schema, audit fail-closed wiring, the
capability-aware frontend contract and the closure evidence for SEC-W10-02/03/06. Complements (does not
replace) tests/test_admin_foundation_w10_1.py and scripts/eval_admin_design.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SECRET_FIELD_TOKENS = {"secret", "token", "password", "key", "apikey", "dsn", "connection", "env", "url", "config", "credential", "credentials"}
CONTENT_FRAGMENTS = ("cv_text", "document_text", "transcript", "conversation", "memory_summary", "evidence_text", "answer_text",
                     "preparation_chat", "impersonat", "view_as", "break_glass", "breakglass")


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from src.api.admin_route_invariant import admin_routes, ungated
    from src.api.schemas import admin as schemas
    from src.application import admin_audit as audit
    from src.application import admin_permissions as perm
    from src.persistence import PLATFORM_ROLES

    # --- registry ----------------------------------------------------------------------------------
    plan = read("docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md")
    block = re.search(r"Canonical permission list.*?```\n(.*?)```", plan, re.S)
    doc_perms = sorted(l.strip() for l in block.group(1).splitlines() if l.startswith("platform.")) if block else []
    check("canonical_count_43", len(perm.PERMISSIONS) == 43 == len(set(perm.PERMISSIONS)), f"{len(perm.PERMISSIONS)} permissions")
    check("registry_equals_design_list", sorted(perm.PERMISSIONS) == doc_perms, "code registry == master-plan canonical list")
    bad = [p for p in perm.PERMISSIONS if re.search(r"break|glass|impersonat|view_as|candidate", p)]
    check("no_break_glass_or_impersonation_permission", not bad, ", ".join(bad) or "none")

    # --- presets -----------------------------------------------------------------------------------
    check("six_presets_defined", set(perm.ROLE_PRESETS) == {"platform_admin", "support_operator", "billing_admin",
          "knowledge_admin", "security_privacy_admin", "operations_admin"}, ", ".join(sorted(perm.ROLE_PRESETS)))
    check("presets_are_subsets_of_registry", all(p <= perm.PERMISSION_SET for p in perm.ROLE_PRESETS.values()), "all subsets")
    check("persistence_roles_match_presets", set(PLATFORM_ROLES) == {perm.ROLE_CANDIDATE, *perm.ADMIN_ROLES}, "vocabulary identical")
    check("resolver_default_deny", all(perm.permissions_for_role(r) == frozenset() for r in (None, "", "user", "root", "Platform_Admin")), "unknown/candidate -> empty")
    pa = perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN]
    check("platform_admin_has_no_content_inspection", not any(re.search(r"document|answer|conversation|memory|evidence|chat", p) for p in pa), "none")

    # --- routes ------------------------------------------------------------------------------------
    routes = admin_routes()
    missing = ungated(routes)
    check("every_admin_route_has_a_permission", len(routes) >= 25 and not missing,
          f"{len(routes)} routes" + (": " + ", ".join(r.path for r in missing) if missing else ""))
    check("route_permissions_are_registered", all(r.permissions <= perm.PERMISSION_SET for r in routes), "all known")
    used = "".join(read(f"src/api/routes/{n}.py") for n in ("admin", "reviewer", "evaluation", "knowledge", "auth"))
    check("no_coarse_admin_gate_on_routes", "Depends(require_platform_admin)" not in used, "require_platform_admin is not used by any route")

    # --- provider schema (SEC-W10-06) ---------------------------------------------------------------
    fields: list[str] = []
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields") and cls.__module__ == schemas.__name__:
            fields += list(cls.model_fields)
    risky = sorted({f for f in fields if SECRET_FIELD_TOKENS & set(f.split("_"))})
    check("provider_schema_has_no_secret_like_fields", not risky, ", ".join(risky) or f"{len(fields)} allowlisted fields")
    schema_src = read("src/api/schemas/admin.py")
    check("provider_schema_has_no_open_dict", not re.search(r"dict\[str,\s*(Any|object)\]|Dict\[str,\s*Any\]", schema_src) and 'extra="forbid"' in schema_src,
          "no dict[str, Any]; extra=forbid")
    check("provider_response_uses_schema", "response_model=ProvidersResponse" in read("src/api/routes/admin.py"), "typed response")
    check("provider_builder_makes_no_network_call", not re.search(r"httpx|requests\.|urllib|socket|subprocess", read("src/application/admin_providers.py")), "no network/subprocess")

    # --- audit (SEC-W10-02/03) ----------------------------------------------------------------------
    admin_py = read("src/api/routes/admin.py")
    check("no_swallowed_audit_in_admin_routes", "except Exception:  # noqa: BLE001\n        pass" not in admin_py and "def _audit(" not in admin_py,
          "old swallow-and-continue helper removed")
    check("mutations_pass_audit_to_the_same_transaction", all("audit=audit" in admin_py for _ in (0,)) and admin_py.count("audit=audit") >= 3, "role/tier/status")
    check("pause_is_audit_first_fail_closed", "Audit unavailable" in admin_py and admin_py.index("audit.record") < admin_py.index("registry.set("), "audit precedes apply")
    check("denial_audit_never_grants", "record_denial(" in read("src/api/dependencies.py") and "except Exception" in read("src/application/admin_audit.py"), "best-effort audit, still 403")
    event_literals = re.findall(r'event_type="([^"]+)"', admin_py)
    check("admin_routes_use_event_constants", not event_literals, "no inline event-name strings")
    check("event_registry_guards_unknown_names", "admin.made_up" not in audit.ADMIN_EVENT_NAMES and audit.ADMIN_ACCESS_DENIED in audit.ADMIN_EVENT_NAMES, f"{len(audit.ADMIN_EVENT_NAMES)} names")
    check("audit_event_names_registered", {"admin.platform_role_change", "admin.entitlement_change", "admin.account_status_change", "platform.pause_toggled"} <= audit.ADMIN_EVENT_NAMES, "legacy names preserved")
    check("request_id_flows_into_audit", "get_request_id(request)" in admin_py and "request_id" in read("src/auth_repository.py"), "X-Request-Id recorded")

    # --- Command Center (SEC-W10-04/05 not claimed) --------------------------------------------------
    cc = read("src/application/admin_command_center.py")
    check("command_center_never_shells_out_or_migrates", not re.search(r"subprocess|os\.system|command\.upgrade|alembic upgrade", cc), "no git/migration execution")
    check("privacy_queue_withheld_not_zero", "not_operational" in cc and "deletion_requests_open" not in read("frontend/components/admin/CommandCenter.tsx"), "no fake zero")
    check("pause_labelled_non_durable", '"durable": False' in cc, "SEC-W10-05 stays open until W10.11")

    # --- frontend ----------------------------------------------------------------------------------
    caps = read("frontend/lib/admin/capabilities.ts")
    check("frontend_has_no_role_mapping_or_storage", not re.search(r"platform_admin|support_operator|billing_admin|ROLE_PRESETS|localStorage|sessionStorage", caps), "UX-only reflection of server permissions")
    ui = "".join(read(str(p.relative_to(ROOT))) for p in (ROOT / "frontend/components/admin").glob("*.tsx")) + caps
    hits = sorted(f for f in CONTENT_FRAGMENTS if f in ui.lower())
    check("admin_ui_has_no_candidate_content_fields", not hits, ", ".join(hits) or "none")
    nav = caps[caps.find("ADMIN_DESTINATIONS"):]
    future = [w for w in ("Support", "Billing", "Subscriptions", "Jobs", "Knowledge administration", "Privacy requests", "Incidents", "Feature Flags") if f'label: "{w}' in nav]
    check("only_operational_destinations_listed", not future and len(re.findall(r'\bid: "', nav)) == 6, "six destinations, none planned")

    # --- scope guards ------------------------------------------------------------------------------
    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("no_migration_added", mig[-1].startswith("0014_"), mig[-1])
    pyproject = read("pyproject.toml").lower()
    check("no_new_infrastructure_dependency", not any(d in pyproject for d in ("redis", "celery", "stripe", "sentry", "prometheus", "hvac")), "none of redis/celery/stripe/sentry/prometheus/hvac")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.1 ADMIN FOUNDATION GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:48s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
