#!/usr/bin/env python
"""P10B-W10.0 admin architecture consistency guard (deterministic, offline, 0 paid/live calls).

W10.0 is a design gate, so this checks that the design documents are complete and internally consistent AND that the
current-vs-planned labels match the code: every route labelled CURRENT exists, nothing labelled PLANNED has been
built, and no migration or break-glass capability has been introduced.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "docs/capstone/admin"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    plan = read(ADMIN / "ADMIN_PLATFORM_MASTER_PLAN.md")
    adr = read(ADMIN / "ADMIN_ARCHITECTURE_DECISIONS.md")
    matrix = read(ADMIN / "ADMIN_CAPABILITY_MATRIX.md")

    sections = re.findall(r"^## (\d+)\. ", plan, re.M)
    check("master_plan_has_all_sections", len(sections) >= 30 and sections[:3] == ["1", "2", "3"], f"{len(sections)} numbered sections")
    check("adr_has_accepted_and_open_decisions",
          all(f"AD-0{i}" in adr for i in range(1, 9)) and all(f"ADR-{i:02d}" in adr for i in range(1, 16)), "AD-01..08, ADR-01..15")

    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in matrix.splitlines() if re.match(r"^\| .*\| (CURRENT|PLANNED) \|", l)]
    check("capability_matrix_rows_well_formed", len(rows) >= 45 and all(len(r) == 14 for r in rows), f"{len(rows)} rows x 14 columns")
    perms_used = {r[4] for r in rows if r[4].startswith("platform.")}
    undefined = sorted(p for p in perms_used if p not in plan)
    check("matrix_permissions_defined_in_plan", not undefined, ", ".join(undefined[:4]) or f"{len(perms_used)} permissions all defined")
    check("matrix_has_current_and_planned", {r[2] for r in rows} == {"CURRENT", "PLANNED"}, "both labels used")

    admin_py = read(ROOT / "src/api/routes/admin.py")
    current_routes = ["/home", "/users", "/workspaces", "/privacy-requests", "/feedback", "/pause", "/providers", "/audit"]
    missing = [r for r in current_routes if f'"{r}' not in admin_py]
    check("current_admin_routes_exist", not missing, ", ".join(missing) or f"{len(current_routes)} documented routes exist")

    routes_dir = ROOT / "src/api/routes"
    forbidden_files = [f for f in routes_dir.glob("*.py") if re.search(r"support|ticket|billing|plan|subscription|integration|incident|legal", f.name)]
    check("planned_domains_not_built_routes", not forbidden_files, ", ".join(f.name for f in forbidden_files) or "no support/billing/plans/integrations/incident/legal routes yet")

    persistence = read(ROOT / "src/persistence.py").lower()
    built = [t for t in ("support_ticket", "subscription_plan", "background_job", "feature_flag", "privacy_request", "legal_acceptance",
                         "preparation_run", "integration_config", "secret_reference", "incident") if t in persistence]
    check("planned_entities_not_in_schema", not built, ", ".join(built) or "no W10 entities in persistence.py")

    deps = read(ROOT / "src/api/dependencies.py")
    check("permission_framework_not_yet_built", "def require_permission" not in deps, "W10.1 builds it")
    src_text = "".join(read(p) for p in (ROOT / "src").rglob("*.py"))
    check("break_glass_not_implemented", "breakglass" not in src_text.lower() and "break_glass" not in src_text.lower(), "reserved design only")

    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("no_migration_added", mig[-1].startswith("0014_"), mig[-1])
    check("referenced_source_paths_exist",
          all((ROOT / p).exists() for p in re.findall(r"`(src/[A-Za-z0-9_/]+\.py)`", plan + adr)),
          "every `src/...py` path named in the plan exists")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.0 ADMIN DESIGN CONSISTENCY\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:42s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
