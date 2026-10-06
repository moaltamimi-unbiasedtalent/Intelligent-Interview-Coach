#!/usr/bin/env python
"""Generate the W11 Admin visual-QA fixture (NOT a CI evaluator): record the real response of every parameterless Admin GET route, plus a few detail routes, from the real
FastAPI app on a temp database seeded with a small, content-free fixture. The Playwright visual/a11y spec serves these recordings so every Admin page renders with realistic
shapes. Isolation bootstrap first: this script can never touch a developer store."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (temp DB, no .env, non-temp engines fail fast)

from fastapi.testclient import TestClient  # noqa: E402

from tests import _admin_matrix as M  # noqa: E402
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register  # noqa: E402

PW = "correcthorsebattery"
API = "/api/v1"


def main() -> int:
    app, repo, _mail = build_auth_app()
    out: dict[str, object] = {}
    with TestClient(app) as c:
        acc = account_repo(repo)
        cks = {}
        ids = {}
        for i, role in enumerate(("user", *M.ROLES)):
            email = f"fx{i}@example.com"
            register(c, email, PW)
            ck = cookies_for(login_token(c, email, PW))
            uid = c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
            if role != "user":
                acc.set_platform_role(uid, role)
            cks[role], ids[role] = ck, uid
        t = c.post(f"{API}/support/tickets", cookies=cks["user"], json={"category": "technical", "subject": "Example ticket", "message": "Example message"}).json()
        c.post(f"{API}/admin/security/incidents", cookies=cks["security_privacy_admin"], json={"title": "Example incident", "severity": "low", "affected_service": "agent"})
        c.post(f"{API}/admin/jobs", cookies=cks["operations_admin"], json={"job_type": "diagnostic_noop", "payload": {"label": "Example job"}, "dedupe_id": "fx"})
        for route in M.routes():
            if route.methods != ("GET",) or "{" in route.path:
                continue
            for role in M.ROLES:
                if M.expected_allowed(route.permissions, role):
                    r = c.get(API + route.path, cookies=cks[role])
                    if r.status_code == 200:
                        out[route.path] = r.json()
                    break
        details = {f"/admin/users/{ids['user']}": "platform_admin", f"/admin/support/tickets/{t['public_id']}": "support_operator"}
        for path, role in details.items():
            r = c.get(API + path, cookies=cks[role])
            if r.status_code == 200:
                out[re.sub(r"/[0-9a-f]{32}$|/\d+$", "/{id}", path)] = r.json()
    dest = ROOT / "frontend/e2e/fixtures/admin-responses.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"recorded {len(out)} responses -> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
