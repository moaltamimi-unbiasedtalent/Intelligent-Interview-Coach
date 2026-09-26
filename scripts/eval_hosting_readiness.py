#!/usr/bin/env python
"""Capstone P8 hosting-readiness evaluation (§53).

Deterministic verification of LOCAL/config invariants for hosted operation: environment
validation (fail-fast in production), secure-cookie logic, CORS allowlist (no wildcard with
credentials), private storage, security headers, real readiness probe, rate-limit backend
reporting, operator pause switch, malware fail-safe, migration single-head, and backup/restore/
rollback documentation. This evaluator does NOT certify EX-12 — that needs an authorized
deployment. No provider calls, no network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Make the script runnable directly from a fresh CI checkout (python scripts/eval_*.py):
# add the repo root to sys.path before importing any `src.*` module (imported inside run()).
sys.path.insert(0, str(ROOT))


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    r: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        r[name] = (bool(ok), detail)

    # --- 1) Environment validation: dev permissive, production fails fast ---
    from src.api.env_validation import validate_runtime_config

    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update({"API_ENV": "development"})
        dev = validate_runtime_config("development")
        os.environ.clear()
        os.environ.update({"API_ENV": "production"})  # nothing else set
        prod_bad = validate_runtime_config("production")
        os.environ.update({
            "FRONTEND_ORIGINS": "https://app.example.com",
            "DATABASE_URL": "postgresql+psycopg://u:p@db/app",
            "APP_BASE_URL": "https://app.example.com",
            "OPENROUTER_API_KEY": "x",
            "EMAIL_PROVIDER": "brevo", "BREVO_API_KEY": "x", "EMAIL_SENDER": "no-reply@ex.com",
        })
        prod_ok = validate_runtime_config("production")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    check("env_dev_permissive", dev.ok, f"dev critical={dev.critical}")
    check("env_prod_fails_fast", not prod_bad.ok and len(prod_bad.critical) >= 3,
          f"prod critical={prod_bad.critical}")
    check("env_prod_ok_when_configured", prod_ok.ok, f"prod critical={prod_ok.critical}")

    # --- 2) Security headers present on API responses ---
    from fastapi.testclient import TestClient

    from src.api.main import create_app

    client = TestClient(create_app())
    resp = client.get("/api/health")
    h = resp.headers
    check("security_headers",
          h.get("X-Content-Type-Options") == "nosniff"
          and "Referrer-Policy" in h and "Content-Security-Policy" in h
          and h.get("X-Frame-Options") == "DENY",
          "nosniff + referrer-policy + CSP + frame options set")

    # --- 3) Real readiness probe (DB + config; 503 on failure) ---
    health_src = read("src/api/routes/health.py")
    check("readiness_probe_real",
          "SELECT 1" in health_src and "503" in health_src and "checks" in health_src,
          "/ready checks DB + config and can 503")

    # --- 4) CORS: never wildcard-with-credentials ---
    main_src = read("src/api/main.py")
    cors_ok = ("allow_origins=list(settings.frontend_origins)" in main_src
               and 'allow_origins=["*"]' not in main_src)
    check("cors_allowlist", cors_ok, "CORS uses the configured origin allowlist, never '*'")

    # --- 5) Secure cookies outside dev ---
    auth_src = read("src/api/routes/auth.py")
    check("secure_cookies", "_secure_cookies" in auth_src and "secure=_secure_cookies" in auth_src
          and "httponly=True" in auth_src and 'samesite="lax"' in auth_src,
          "session cookie is HttpOnly + SameSite=Lax + Secure outside dev")

    # --- 6) Private storage: env-configured dir, opaque keys, served as attachment ---
    storage_src = read("src/documents/storage.py")
    docs_src = read("src/api/routes/documents.py")
    check("private_storage",
          "DOCUMENT_STORAGE_DIR" in storage_src and "attachment" in docs_src,
          "uploads use a private dir + are served as attachments, never public URLs")

    # --- 7) Rate-limit backend reported honestly (not distributed by default) ---
    from src.api.rate_limit import get_rate_limiter, reset_rate_limiter

    reset_rate_limiter()
    check("rate_limit_backend", getattr(get_rate_limiter(), "distributed", None) is False,
          "default limiter is single-process (distributed=False), reported honestly")

    # --- 8) Operator pause switch exists ---
    from src.application.pause import PAUSABLE_CAPABILITIES

    check("pause_switch", len(PAUSABLE_CAPABILITIES) >= 3
          and "realtime_voice" in PAUSABLE_CAPABILITIES,
          f"pausable capabilities: {PAUSABLE_CAPABILITIES}")

    # --- 9) Malware fail-safe ---
    from src.documents.file_security import (
        EICAR, FakeScanner, FileScanUnavailable, NullScanner, enforce_scan)

    failed_closed = False
    try:
        enforce_scan(b"data", "f.pdf", scanner=NullScanner(), required=True)
    except FileScanUnavailable:
        failed_closed = True
    eicar_flagged = not FakeScanner().scan(EICAR, "x").clean
    clean_ok = enforce_scan(b"hello", "f.txt", scanner=FakeScanner(), required=True).clean
    check("malware_failsafe",
          failed_closed and eicar_flagged and clean_ok,
          "required+no real scanner → fail closed; EICAR flagged; real pass allowed")

    # --- 10) Migration single head ---
    import sys

    try:
        out = subprocess.run([sys.executable, "-m", "alembic", "heads"], cwd=ROOT,
                             capture_output=True, text=True, timeout=90,
                             env={**os.environ, "PYTHONPATH": str(ROOT)})
        heads = [ln for ln in out.stdout.splitlines() if "(head)" in ln]
        check("migration_single_head", len(heads) == 1, f"heads={heads or out.stdout.strip()[:120]}")
    except Exception as exc:  # noqa: BLE001
        check("migration_single_head", False, f"alembic error: {exc}")

    # --- 11) Backup / restore / rollback / runbook documented ---
    check("ops_docs_present",
          (ROOT / "deploy/scripts/backup.sh").exists()
          and (ROOT / "deploy/scripts/restore.sh").exists()
          and (ROOT / "deploy/scripts/migrate.sh").exists()
          and (ROOT / "docs/capstone/p8_hosting_operations.md").exists(),
          "backup/restore/migrate scripts + hosting runbook exist")

    # --- 12) Production error responses don't leak stack traces ---
    exc_src = read("src/api/exception_handlers.py")
    check("no_stacktrace_in_prod",
          "exc_info" in exc_src and ("dev" in exc_src.lower() or "DEV_ENVS" in exc_src),
          "stack traces only surfaced in dev")

    # --- 13) No server secret in the client bundle (NEXT_PUBLIC_* are non-secret only) ---
    fe_config = read("frontend/lib/config.ts")
    check("no_client_secret",
          "NEXT_PUBLIC_API_BASE_URL" in fe_config
          and "OPENROUTER_API_KEY" not in fe_config
          and "REALTIME_VOICE_API_KEY" not in fe_config,
          "frontend config reads only non-secret NEXT_PUBLIC_* vars")

    return r


def main() -> int:
    print("ASK4MO — CAPSTONE P8 HOSTING-READINESS EVALUATION")
    print("(local invariants only — does NOT certify EX-12 hosted operation)\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        failed = failed or not ok
        print(f"  {name:28s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid calls: 0   Network calls: 0   EX-12: NOT certified here")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (hosting-readiness invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
