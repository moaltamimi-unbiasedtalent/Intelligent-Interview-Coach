#!/usr/bin/env python
"""P10B-W10.6 integrations guard (deterministic, offline, 0 paid/live calls).

High-risk invariants of the integration control plane: a code-defined registry (no custom integrations, no
admin-entered URL), a SecretStore with no administrator read path, metadata-only responses, manual-only
bounded probes with adapter-defined destinations, honest status wording (Google, Redis, email, health), no
background polling and no billing provider. It does not duplicate the test suite.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BANNED_FIELDS = {"api_key", "secret", "client_secret", "password", "authorization", "bearer", "token_value",
                 "credential_value", "private_key", "value", "url", "base_url", "endpoint"}
LOCALES = ()


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def code_only(src: str) -> str:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and node.body \
                and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from pydantic import BaseModel

    from src import integrations as I
    from src.api.admin_route_invariant import admin_routes, ungated
    from src.api.schemas import admin as schemas
    from src.application import admin_permissions as perm
    from src.persistence import IntegrationState
    from src.secret_store import EnvironmentSecretStore, SecretStoreReadOnly

    check("registry_is_code_defined", len(I.REGISTRY) == 9 and set(I.CATEGORIES) >= {d.category for d in I.REGISTRY.values()},
          f"{len(I.REGISTRY)} integrations, {len(I.CATEGORIES)} categories")
    check("no_billing_provider_in_registry", not re.search(r"stripe|paypal|billing|payment|checkout", " ".join(
        f"{d.code} {d.name} {d.adapter}" for d in I.REGISTRY.values()), re.I), "none")
    check("no_registry_field_is_an_admin_supplied_endpoint",
          not any(re.search(r"url|host|endpoint|base", s.env_name, re.I) for d in I.REGISTRY.values() for s in d.settings), "settings are vocabularies, not endpoints")
    routes = [r for r in admin_routes() if r.path.startswith("/admin/integrations")]
    check("no_route_creates_or_edits_an_integration",
          len(routes) == 4 and not any(r.path == "/admin/integrations" and "POST" in r.methods for r in routes)
          and not any(re.search(r"enable|disable|toggle|config", r.path) for r in routes), "list, detail, test, credentials only")
    check("integration_routes_permissioned",
          not ungated(admin_routes()) and {p for r in routes for p in r.permissions} == {perm.INTEGRATIONS_READ, perm.INTEGRATIONS_MANAGE, perm.SECRET_ROTATE}
          and len(perm.PERMISSIONS) == 43, "canonical permissions only; registry unchanged at 43")

    store = EnvironmentSecretStore()
    check("environment_store_is_read_only", store.supports_write is False, "supports_write = False")
    try:
        store.set("X", "y")
        raised = False
    except SecretStoreReadOnly:
        raised = True
    check("environment_store_write_raises", raised, "SecretStoreReadOnly")
    ss = read("src/secret_store.py")
    check("secret_store_has_no_admin_read_path", not re.search(r"get_for_admin|def reveal|def get\(|def mask|\[-\d+:\]|\[:\d+\]", code_only(ss)), "runtime-only read; no reveal/mask/partial")
    users = [str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py") if "get_for_runtime" in p.read_text(encoding="utf-8")]
    allowed = {"src/secret_store.py", "src/integrations.py"}
    check("runtime_secret_read_is_confined", set(users) <= allowed, ", ".join(sorted(set(users) - allowed)) or "only the secret store and the adapter probe")
    admin_files = ["src/api/routes/admin_integrations.py", "src/api/routes/admin.py", "src/api/schemas/admin.py",
                   "src/application/admin_providers.py", "src/application/admin_command_center.py"]
    check("no_admin_surface_reads_a_secret", not any("get_for_runtime" in read(f) for f in admin_files), "no admin route, schema or summary can obtain a value")

    names: list[str] = []
    for cls in vars(schemas).values():
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == schemas.__name__:
            names += list(cls.model_fields)
    check("admin_schemas_have_no_secret_or_url_fields", not set(names) & BANNED_FIELDS, f"{len(names)} fields")
    check("integration_state_has_no_secret_url_or_body_columns",
          {c.name for c in IntegrationState.__table__.columns} == {"integration_code", "last_test_at", "last_test_outcome", "last_test_category",
                                                                    "last_test_latency_ms", "last_test_by_user_id", "updated_at"}, "safe result columns only")

    svc = read("src/integrations.py")
    code = code_only(svc)
    check("probes_run_only_from_run_test", code.count("run_probe(") == 2 and "def run_test" in code and "run_probe(code, self._store" in code, "no probe on list, detail or page render")
    check("probe_is_bounded_adapter_defined_and_no_redirect",
          I.PROBE_TIMEOUT_SECONDS <= 10 and I.OPENROUTER_PROBE_URL.startswith("https://openrouter.ai/") and "follow_redirects=False" in code
          and not re.search(r"client\.(get|post)\(\s*(request|body|url|payload)", code), f"timeout {I.PROBE_TIMEOUT_SECONDS}s, constant https destination")
    check("probe_exceptions_are_discarded", "except Exception" in code and "never surface exception text" in svc, "mapped to bounded categories")
    check("no_background_monitoring",
          not re.search(r"apscheduler|celery|threading\.Timer|asyncio\.create_task|BackgroundTasks|while True|schedule\.", code + code_only(read("src/api/routes/admin_integrations.py"))), "manual only")
    check("health_is_never_assumed",
          'status": "healthy" if state.last_test_outcome == "success"' in svc.replace("\n", " ").replace("  ", " ") or '"healthy" if state.last_test_outcome == "success"' in svc,
          "healthy only from a recorded successful test")

    google, redis, email = I.REGISTRY["google_oidc"], I.REGISTRY["redis_rate_limit"], I.REGISTRY["email_brevo"]
    check("google_oidc_truth_is_qualified", "not validated" in google.validation_note.lower() and not google.test_supported, "not validated; no probe")
    check("redis_truth_is_qualified", "NOT LIVE" in redis.validation_note, "distributed limiting not live")
    check("email_truth_is_qualified", "never emailed" in email.validation_note and not email.test_supported, "support replies are not emailed; no probe")

    route = read("src/api/routes/admin_integrations.py")
    req, wr = route.find("ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED"), route.find("service.write_credential(")
    check("credential_route_audits_request_before_write_and_claims_no_rollback",
          0 < req < wr and "NOT atomic" in route and "request.json()" in route, "requested -> write -> succeeded/failed")
    check("validation_errors_never_echo_input", '"input", "ctx", "url"' in read("src/api/exception_handlers.py"), "422 details drop the submitted value")
    check("audit_payloads_never_carry_a_value",
          not re.search(r"audit\([^)]*value|_stage\([^)]*value", code_only(route + svc)), "codes, slots, outcome and category only")

    mig = read("migrations/versions/0017_integrations.py")
    check("migration_chain_valid", 'down_revision = "0016_plans_entitlements"' in mig and "ck_integration_states_outcome" in mig, "0017 chains from 0016")
    tests = read("tests/test_integrations_w10_6.py")
    check("tests_exist", all(t in tests for t in ("test_inventory_never_returns_a_secret_value_prefix_suffix_or_mask",
                                                  "test_environment_credentials_cannot_be_replaced_through_the_api",
                                                  "test_write_only_replacement_with_a_writable_store_never_returns_or_records_the_value",
                                                  "test_no_network_on_list_or_detail",
                                                  "test_real_openrouter_probe_uses_the_constant_url")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.6 INTEGRATIONS GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:62s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
