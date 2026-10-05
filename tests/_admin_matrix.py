"""Machine-generated Admin qualification matrices (P10B-W10.14). Everything here is DERIVED FROM CODE (the canonical permission registry, the role presets, the route
dependency graph and the frontend destination table); nothing is typed by hand. Used by ``tests/test_admin_qualification_w10_14.py`` and
``scripts/eval_admin_qualification.py`` (which also renders the tables for ``docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md``)."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from src.api.admin_route_invariant import admin_routes
from src.application import admin_permissions as perm

ROOT = Path(__file__).resolve().parent.parent
ROLES = ("platform_admin", "support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin")
PERSONAS = ("user", *ROLES)                      # candidate + the six Admin presets
# The specialist high-risk permissions that are INTENTIONALLY absent from platform_admin (ROLE-W10-01 final decision, W10.14).
PLATFORM_ADMIN_ABSENT = frozenset({
    "platform.audit.export", "platform.billing.read", "platform.billing.refund", "platform.config.manage", "platform.incidents.manage",
    "platform.integrations.secret.rotate", "platform.jobs.manage", "platform.jobs.read", "platform.knowledge.approve", "platform.knowledge.manage",
    "platform.legal.manage", "platform.plans.price.change", "platform.privacy.execute", "platform.reports.commercial.read", "platform.security.manage",
})
# Registry permissions that no current route requires (documented, informational).
UNROUTED_PERMISSIONS = frozenset({"platform.releases.read", "platform.subscriptions.read"})

DOMAINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("overview / releases", ("/admin/home",)),
    ("users", ("/admin/users",)),
    ("workspaces", ("/admin/workspaces",)),
    ("support", ("/admin/support",)),
    ("plans / subscriptions", ("/admin/plans",)),
    ("billing", ("/admin/billing",)),
    ("integrations / providers", ("/admin/integrations", "/admin/providers")),
    ("AI / model administration", ("/admin/ai", "/evaluation")),
    ("knowledge", ("/admin/knowledge", "/knowledge/diagnostics", "/reviewer/knowledge", "/reviewer/config-versions", "/reviewer/prompt-lab", "/reviewer/retention")),
    ("jobs", ("/admin/jobs",)),
    ("privacy / legal", ("/admin/privacy", "/admin/privacy-requests", "/admin/legal")),
    ("flags / configuration / pause", ("/admin/flags", "/admin/pause")),
    ("reports", ("/admin/reports", "/admin/feedback")),
    ("security / incidents / alerts", ("/admin/security",)),
    ("audit", ("/admin/audit", "/auth/admin/audit")),
    ("role approvals / step-up", ("/admin/role-changes", "/admin/step-up")),
)


def domain_of(path: str) -> str:
    for name, prefixes in DOMAINS:
        if any(path == p or path.startswith(p + "/") or path.startswith(p) and path[len(p):len(p) + 1] in ("", "/", "{") for p in prefixes):
            return name
    return "UNMAPPED"


def role_perms(role: str | None) -> frozenset[str]:
    return perm.permissions_for_role(role)


def permission_matrix() -> dict[str, dict[str, bool]]:
    return {p: {r: p in role_perms(r) for r in PERSONAS} for p in perm.PERMISSIONS}


def matrix_hash() -> str:
    return hashlib.sha256(json.dumps(permission_matrix(), sort_keys=True).encode()).hexdigest()[:16]


def expected_allowed(route_perms: frozenset[str], persona: str) -> bool:
    return bool(route_perms) and all(p in role_perms(persona) for p in route_perms)


def routes():
    return admin_routes()


def route_persona_expectations() -> list[tuple[object, str, bool]]:
    out = []
    for r in routes():
        for persona in PERSONAS:
            out.append((r, persona, expected_allowed(r.permissions, persona)))
    return out


def mutation_inventory() -> list[dict]:
    rows = []
    for r in routes():
        if r.methods == ("GET",):
            continue
        try:
            src = inspect.getsource(r.route.endpoint)
        except Exception:  # noqa: BLE001
            src = ""
        events = sorted(set(re.findall(r"\bA\.([A-Z][A-Z_]+)", src)))
        marker = [m for m in ("build_audit", "_audit(", "audit=", "audit_for", "audit(", "_ws_audit") if m in src]
        rows.append({"method": r.methods[0], "path": r.path, "permission": sorted(r.permissions)[0], "events": events, "audited_in_handler": bool(marker or events),
                     "reason_required": bool(re.search(r"reasonRequired|reason: str = Field\(min_length|reason_required|\"reason\" is required|A reason is required", src))})
    return rows


def admin_pages() -> list[str]:
    base = ROOT / "frontend/app/admin"
    return sorted("/admin" + ("/" + str(p.parent.relative_to(base)) if p.parent != base else "") for p in base.rglob("page.tsx"))


def destinations() -> list[dict]:
    """Parse the frontend destination table (UX only) into href + permission anyOf."""
    text = (ROOT / "frontend/lib/admin/capabilities.ts").read_text()
    pmap = dict(re.findall(r"^\s{2}(\w+): \"(platform\.[a-z.]+)\"", text, re.M))
    out = []
    for m in re.finditer(r"\{ id: \"(\w+)\", label: \"([^\"]+)\", href: \"([^\"]+)\", description: \"[^\"]*\", anyOf: \[([^\]]*)\] \}", text):
        keys = [k.strip().split(".")[-1] for k in m.group(4).split(",") if k.strip()]
        out.append({"id": m.group(1), "label": m.group(2), "href": m.group(3), "anyOf": [pmap[k] for k in keys]})
    return out


def nav_for(perms: frozenset[str]) -> list[str]:
    return [d["href"] for d in destinations() if any(p in perms for p in d["anyOf"])]


# ------------------------------------------------------------------ markdown renderers
def md_permission_matrix() -> str:
    short = {"user": "user", "platform_admin": "platform", "support_operator": "support", "billing_admin": "billing", "knowledge_admin": "knowledge",
             "security_privacy_admin": "security", "operations_admin": "operations"}
    head = "| Permission | " + " | ".join(short[p] for p in PERSONAS) + " | owners | W10.14 decision |\n|---|" + "---:|" * len(PERSONAS) + "---|---|\n"
    rows = []
    for p, m in permission_matrix().items():
        owners = [r for r in ROLES if m[r]]
        decision = ("unassigned by design (secret rotation stays externally managed)" if not owners else
                    "domain-owner only (absent from platform_admin)" if p in PLATFORM_ADMIN_ABSENT else "retained")
        rows.append(f"| `{p}` | " + " | ".join("Y" if m[x] else "-" for x in PERSONAS) + f" | {', '.join(owners) or 'none'} | {decision} |")
    return head + "\n".join(rows)


def md_route_inventory() -> str:
    rs = routes()
    by_domain: dict[str, list] = {}
    for r in rs:
        by_domain.setdefault(domain_of(r.path), []).append(r)
    lines = ["| Domain | Routes | GET | Mutating | Permissions required |", "|---|---:|---:|---:|---|"]
    for d, items in sorted(by_domain.items()):
        perms = sorted({p.replace("platform.", "") for r in items for p in r.permissions})
        g = sum(1 for r in items if r.methods == ("GET",))
        lines.append(f"| {d} | {len(items)} | {g} | {len(items) - g} | {', '.join(perms)} |")
    lines.append(f"| **Total** | **{len(rs)}** | **{sum(1 for r in rs if r.methods == ('GET',))}** | **{sum(1 for r in rs if r.methods != ('GET',))}** | |")
    return "\n".join(lines)


def md_mutation_inventory() -> str:
    rows = mutation_inventory()
    lines = ["| Method | Route | Permission | Audit events named in the handler | Audited in handler |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['method']} | `{r['path']}` | `{r['permission'].replace('platform.', '')}` | {', '.join(r['events']) or '(built in service)'} | {'yes' if r['audited_in_handler'] else 'in service'} |")
    return "\n".join(lines)


def md_page_inventory() -> str:
    dests = {d["href"]: d for d in destinations()}
    lines = ["| Admin page | Navigation permission(s) (any of) | Backend gate |", "|---|---|---|"]
    for p in admin_pages():
        d = dests.get(p)
        lines.append(f"| `{p}` | {', '.join(x.replace('platform.', '') for x in d['anyOf']) if d else '(detail/child of a listed page)'} | `require_permission` on every API it calls |")
    return "\n".join(lines)


def md_nav_matrix() -> str:
    hrefs = [d["href"] for d in destinations()]
    head = "| Persona | Visible destinations |\n|---|---|\n"
    rows = [f"| {p} | {', '.join(nav_for(role_perms(p))) or '(none)'} |" for p in PERSONAS]
    return head + "\n".join(rows) + f"\n\n({len(hrefs)} destinations in total.)"


def role_fixture() -> dict:
    """The cross-language fixture: each persona's server-resolved permissions and the destinations the frontend must show for them."""
    return {"permissions_total": len(perm.PERMISSIONS),
            "personas": {p: {"permissions": sorted(role_perms(p)), "nav": nav_for(role_perms(p))} for p in PERSONAS},
            "unknown_role_nav": nav_for(role_perms("ghost"))}
