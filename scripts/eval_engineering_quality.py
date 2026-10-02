#!/usr/bin/env python
"""P10B-W9.12 engineering-quality guard (deterministic, offline, 0 paid/live calls).

Static invariants for the debt closed in W9.12 so it cannot silently return: test isolation (TD-W9-02), the
colour-token opacity fix (TD-W9-01), the shared rate-limit adapter boundary, removed legacy auth surface, and
read-only evaluator defaults. (The runtime proof of isolation lives in tests/test_test_isolation.py; the
alpha-utility proof in frontend/tests/tailwind-token-opacity.test.ts.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    conftest = read("tests/conftest.py")
    check("test_env_dotenv_disabled", "PYTHON_DOTENV_DISABLED" in conftest and "_no_dotenv" in conftest, "tests/conftest.py")
    check("test_db_forced_to_temp_and_guarded",
          "_guarded_create_engine" in conftest and "DATABASE_URL" in conftest and "Test isolation" in conftest,
          "engine guard + temp DATABASE_URL")
    check("test_dev_store_fingerprint_fails_session",
          "pytest_sessionfinish" in conftest and "session.exitstatus = 1" in conftest, "dev stores fingerprinted")
    check("test_vector_store_redirected_and_guarded", "COPILOT_CHROMA_DIR" in conftest and "_guarded_persistent_client" in conftest,
          "Chroma persistence confined to the temp dir (found by the first CI run)")
    check("isolation_regression_tests_exist", "test_opening_the_development_database_is_refused" in read("tests/test_test_isolation.py"),
          "tests/test_test_isolation.py")

    tw = read("frontend/tailwind.config.ts")
    check("tailwind_tokens_alpha_capable",
          "color-mix(in srgb" in tw and not re.search(r':\s*"var\(--', tw.split("colors:")[1].split("fontFamily")[0]),
          "colour tokens use the alpha-capable helper, no raw var() strings")
    check("tailwind_guard_test_exists", "dead opacity-token utilities" in read("frontend/tests/tailwind-token-opacity.test.ts"),
          "frontend/tests/tailwind-token-opacity.test.ts")

    from src.api import rate_limit as rl

    check("rate_limit_adapter_boundary",
          hasattr(rl, "RedisRateLimiter") and hasattr(rl, "shared_store_active") and rl.InMemoryRateLimiter.distributed is False
          and rl.RedisRateLimiter.distributed is True, "in-memory default + optional Redis adapter")
    check("distributed_limiting_not_claimed_live", rl.get_rate_limiter().distributed is False and not rl.shared_store_active(),
          "default process uses the in-memory limiter")

    auth_routes = read("src/api/routes/auth.py")
    deps = read("src/api/dependencies.py")
    client = read("frontend/lib/api/client.ts")
    check("legacy_auth_surface_removed",
          "/account/delete-request" not in auth_routes and "def get_current_user(" not in deps and "requestDeletion" not in client,
          "unused delete-request route/client and unused get_current_user removed")
    check("account_delete_route_kept", '"/account/delete"' in auth_routes, "account deletion still available")

    for rel in ("scripts/eval_knowledge_expansion.py", "scripts/eval_product_coverage.py"):
        src = read(rel)
        check(f"evaluator_read_only_by_default:{Path(rel).name}",
              "tempfile.mkdtemp" in src and "--write" in src and "ASK4MO_EVAL_WRITE" in src, "results go to a temp dir unless --write")

    ci = read(".github/workflows/ci.yml")
    check("ci_enforces_clean_tree", "git status --porcelain" in ci, "CI fails if tests/evaluators dirty tracked files")
    check("no_new_migration", sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))[-1].startswith(("0014_", "0015_")), "head is a registered revision")
    return out


def main() -> int:
    print("ASK4MO - P10B-W9.12 ENGINEERING QUALITY GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:52s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
