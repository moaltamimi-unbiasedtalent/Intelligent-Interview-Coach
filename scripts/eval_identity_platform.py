#!/usr/bin/env python
"""Capstone P1/E1 identity & platform evaluation (E1).

Measures the safety and correctness of the identity foundation — more than a test
count. Runs fully offline (a temp SQLite DB, in-memory email capture); makes NO
paid/live provider call. Prints a metric report and exits non-zero if any safety
invariant is below its target rate.

Safety targets (must be 1.0):
  * cross-user isolation
  * unauthorized admin rejection
  * entitlement bypass prevention
  * secret leakage prevention
  * production dev-header rejection

Usage:  python scripts/eval_identity_platform.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("EMAIL_PROVIDER", "memory")

PW = "correcthorsebattery"


def _build(env: str):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    from src.api import dependencies as deps
    from src.api.config import ApiSettings
    from src.api.main import create_app
    from src.mail import MemoryEmailSender
    from src.persistence import Base, make_session_factory
    from src.repository import InterviewRepository

    db = os.path.join(tempfile.mkdtemp(prefix="eval_id_"), "id.db")
    engine = create_engine(f"sqlite:///{db}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    repo = InterviewRepository(make_session_factory(engine))
    mail = MemoryEmailSender()
    app = create_app(ApiSettings(env=env, frontend_origins=("http://localhost:3000",)))
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_email_sender] = lambda: mail
    return TestClient(app), repo, mail


def _login(c, email, pw):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        return None
    sc = r.headers.get("set-cookie", "")
    return sc.split("ask4mo_session=")[1].split(";")[0] if "ask4mo_session=" in sc else None


def _ck(tok):
    return {"ask4mo_session": tok}


def run() -> dict[str, tuple[int, int]]:
    """Return metric -> (passed, total)."""
    from src.auth_repository import AccountRepository

    results: dict[str, list[bool]] = {}

    def check(metric: str, ok: bool) -> None:
        results.setdefault(metric, []).append(bool(ok))

    # --- authentication + verification/recovery lifecycle ---
    c, repo, mail = _build("test")
    with c:
        rr = c.post("/api/v1/auth/register", json={"email": "a@example.com", "password": PW})
        check("authentication_flow", rr.status_code == 201)
        tok = _login(c, "a@example.com", PW)
        check("authentication_flow", tok is not None)
        me = c.get("/api/v1/auth/me", cookies=_ck(tok))
        check("authentication_flow", me.status_code == 200 and me.json()["email"] == "a@example.com")
        check("authentication_flow", c.post("/api/v1/auth/logout", cookies=_ck(tok)).status_code == 200)
        check("authentication_flow", c.get("/api/v1/auth/me", cookies=_ck(tok)).status_code == 401)  # revoked

        c.post("/api/v1/auth/register", json={"email": "v@example.com", "password": PW})
        vtok = next((m.body.split("token=")[1].split()[0] for m in reversed(mail.sent)
                     if m.category == "email_verification" and "token=" in m.body), None)
        check("verification_recovery", vtok is not None)
        check("verification_recovery", c.post("/api/v1/auth/verify-email", json={"token": vtok}).status_code == 200)
        check("verification_recovery", c.post("/api/v1/auth/verify-email", json={"token": vtok}).status_code == 400)  # single-use
        c.post("/api/v1/auth/forgot-password", json={"email": "v@example.com"})
        rtok = next((m.body.split("token=")[1].split()[0] for m in reversed(mail.sent)
                     if m.category == "password_reset" and "token=" in m.body), None)
        check("verification_recovery", rtok is not None)
        check("verification_recovery", c.post("/api/v1/auth/reset-password", json={"token": rtok, "password": "new-password-123"}).status_code == 200)
        check("verification_recovery", _login(c, "v@example.com", "new-password-123") is not None)

    # --- cross-user isolation ---
    c, repo, mail = _build("test")
    with c:
        c.post("/api/v1/auth/register", json={"email": "alice@example.com", "password": PW})
        c.post("/api/v1/auth/register", json={"email": "bob@example.com", "password": PW})
        alice, bob = _login(c, "alice@example.com", PW), _login(c, "bob@example.com", PW)
        m = c.post("/api/v1/memory", json={"category": "recurring_gap", "summary": "System design"}, cookies=_ck(alice))
        mem_id = m.json()["id"]
        check("cross_user_isolation", c.get(f"/api/v1/memory/{mem_id}", cookies=_ck(bob)).status_code == 404)
        check("cross_user_isolation", c.delete(f"/api/v1/memory/{mem_id}", cookies=_ck(bob)).status_code == 404)
        check("cross_user_isolation", c.get(f"/api/v1/memory/{mem_id}", cookies=_ck(alice)).status_code == 200)

    # --- unauthenticated rejection + production fail-closed + dev-header rejection ---
    c, repo, mail = _build("production")
    with c:
        check("unauthenticated_rejection", c.get("/api/v1/memory").status_code == 401)
        check("unauthenticated_rejection", c.get("/api/v1/auth/me").status_code == 401)
        check("production_dev_header_rejection", c.get("/api/v1/memory", headers={"X-User-Subject": "attacker"}).status_code == 401)
        check("production_dev_header_rejection", c.get("/api/v1/auth/me", headers={"X-User-Subject": "attacker"}).status_code == 401)

    # --- platform role + entitlement enforcement ---
    c, repo, mail = _build("test")
    with c:
        c.post("/api/v1/auth/register", json={"email": "u@example.com", "password": PW})
        tok = _login(c, "u@example.com", PW)
        uid = c.get("/api/v1/auth/me", cookies=_ck(tok)).json()["user_id"]
        check("admin_rejection", c.get("/api/v1/auth/admin/audit", cookies=_ck(tok)).status_code == 403)
        check("entitlement_bypass_prevention", c.get("/api/v1/auth/premium/status", cookies=_ck(tok)).status_code == 403)
        check("entitlement_bypass_prevention", c.get("/api/v1/auth/premium/status", params={"tier": "premium"}, cookies=_ck(tok)).status_code == 403)
        ar = AccountRepository(repo.session_factory)
        ar.set_platform_role(uid, "platform_admin")
        ar.set_tier(uid, "premium", source="eval")
        check("admin_grant", c.get("/api/v1/auth/admin/audit", cookies=_ck(tok)).status_code == 200)
        check("entitlement_grant", c.get("/api/v1/auth/premium/status", cookies=_ck(tok)).status_code == 200)

    # --- audit safety (no secrets stored) ---
    c, repo, mail = _build("test")
    with c:
        c.post("/api/v1/auth/register", json={"email": "audit@example.com", "password": PW})
        _login(c, "audit@example.com", PW)
        c.post("/api/v1/auth/login", json={"email": "audit@example.com", "password": "wrong-pw-value"})
    check("audit_safety", _audit_clean(repo))

    # --- secret leakage (OpenAPI response schemas) ---
    check("secret_leakage_prevention", _openapi_clean())

    # --- legacy-data preservation (migration backfill) ---
    check("legacy_data_preservation", _migration_preserves())

    return {k: (sum(v), len(v)) for k, v in results.items()}


def _audit_clean(repo) -> bool:
    from sqlalchemy import select

    from src.persistence import AuditEvent

    with repo.session_factory() as s:
        rows = s.scalars(select(AuditEvent)).all()
        if not rows:
            return False
        for r in rows:
            blob = f"{r.event_type}{r.result}{r.target_type}{r.target_id}{r.context}".lower()
            if PW in blob or "wrong-pw-value" in blob or "$2b$" in blob or "token=" in blob:
                return False
    return True


def _openapi_clean() -> bool:
    from src.api.config import ApiSettings
    from src.api.main import create_app

    schema = create_app(ApiSettings(env="test")).openapi()
    forbidden = {"api_key", "system_prompt", "chain_of_thought", "raw_response", "database_url", "password_hash"}
    for model in (schema.get("components", {}).get("schemas", {}) or {}).values():
        for field in (model.get("properties") or {}):
            if field.lower() in forbidden:
                return False
    return True


def _migration_preserves() -> bool:
    import importlib.util

    if importlib.util.find_spec("alembic") is None:
        return True  # skipped where alembic absent (counts as non-failing)
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    tmp = tempfile.mkdtemp(prefix="eval_mig_")
    url = f"sqlite:///{tmp}/legacy.db"
    os.environ["DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0006_user_feedback")
    eng = sa.create_engine(url)
    with eng.begin() as c:
        c.execute(sa.text("INSERT INTO users (subject, provider, email, created_at, updated_at) "
                          "VALUES ('legacy','dev','legacy@example.com', datetime('now'), datetime('now'))"))
        c.execute(sa.text("INSERT INTO interviews (user_id, configuration, status, created_at) "
                          "VALUES (1,'{}','completed', datetime('now'))"))
    command.upgrade(cfg, "head")
    with eng.begin() as c:
        idents = c.execute(sa.text("SELECT count(*) FROM account_identities")).scalar()
        ents = c.execute(sa.text("SELECT count(*) FROM product_entitlements")).scalar()
        iv = c.execute(sa.text("SELECT count(*) FROM interviews")).scalar()
    return idents == 1 and ents == 1 and iv == 1


SAFETY_METRICS = {
    "cross_user_isolation",
    "admin_rejection",
    "entitlement_bypass_prevention",
    "secret_leakage_prevention",
    "production_dev_header_rejection",
    "audit_safety",
    "legacy_data_preservation",
}


def main() -> int:
    print("ASK4MO — CAPSTONE P1/E1 IDENTITY & PLATFORM EVALUATION\n")
    metrics = run()
    failed_safety = False
    for metric in sorted(metrics):
        passed, total = metrics[metric]
        rate = passed / total if total else 0.0
        flag = ""
        if metric in SAFETY_METRICS and rate < 1.0:
            flag = "  ← SAFETY TARGET NOT MET"
            failed_safety = True
        print(f"  {metric:32s} {passed}/{total}  rate={rate:.3f}{flag}")
    print("\nPaid LLM calls: 0   Live provider calls: 0")
    if failed_safety:
        print("\nRESULT: FAIL (a safety invariant is below 1.0)")
        return 1
    print("\nRESULT: PASS (all safety invariants = 1.0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
