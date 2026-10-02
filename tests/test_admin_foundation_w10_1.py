"""P10B-W10.1: admin permission registry, resolver, atomic fail-closed audit, provider schema,
Command Center. Deterministic; real isolated SQLite; no provider/network call."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.application import admin_audit as A
from src.application import admin_permissions as perm
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"
ROOT = Path(__file__).resolve().parents[1]


class Env:
    def __init__(self):
        self.app, self.repo, _ = build_auth_app()
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = account_repo(self.repo)
        self.n = 0

    def close(self):
        self.c.__exit__(None, None, None)

    def user(self, role: str = "user"):
        self.n += 1
        email = f"u{self.n}@x.com"
        register(self.c, email, PW)
        tok = login_token(self.c, email, PW)
        uid = self.c.get("/api/v1/auth/me", cookies=cookies_for(tok)).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return uid, cookies_for(tok)

    def events(self, event_type=None):
        from src.auth_repository import AuditRepository
        return AuditRepository(self.repo.session_factory).recent(limit=200, event_type=event_type)


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def _routes():
    from src.api.admin_route_invariant import admin_routes
    return admin_routes()


# ---------------- permission matrix P1-P10 ----------------------------------------------------------

def test_p1_registry_is_the_canonical_43_with_no_break_glass():
    assert len(perm.PERMISSIONS) == 43 == len(set(perm.PERMISSIONS))
    doc = (ROOT / "docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md").read_text()
    block = re.search(r"```\n(platform\.ai\.activate.*?)```", doc, re.S).group(1).split()
    assert sorted(block) == sorted(perm.PERMISSIONS)
    for name in perm.PERMISSIONS:
        assert re.fullmatch(r"platform(\.[a-z]+)+", name)
        assert not any(f in name for f in ("break", "glass", "impersonat", "view_as", "candidate"))


def test_p2_presets_are_subsets_and_platform_admin_has_no_content_inspection():
    assert set(perm.ROLE_PRESETS) == set(perm.ADMIN_ROLES)
    for role, perms in perm.ROLE_PRESETS.items():
        assert perms <= perm.PERMISSION_SET, role
        assert perm.OVERVIEW_READ in perms
    for p in perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN]:
        assert not any(f in p for f in ("document", "answer", "conversation", "memory", "evidence", "chat"))


def test_p3_resolver_is_default_deny():
    for role in (None, "", "user", "root", "admin", "PLATFORM_ADMIN", "candidate", "platform_admin ", "x" * 99):
        assert perm.permissions_for_role(role) == frozenset(), role
    assert perm.permissions_for_role("platform_admin")


def test_p4_persistence_role_vocabulary_matches_presets():
    from src.persistence import PLATFORM_ROLES
    assert set(PLATFORM_ROLES) == {perm.ROLE_CANDIDATE, *perm.ADMIN_ROLES}


def test_p5_every_admin_route_has_an_explicit_known_permission():
    from src.api.admin_route_invariant import ungated
    routes = _routes()
    assert len(routes) >= 25
    assert ungated(routes) == []
    for r in routes:
        assert r.permissions <= perm.PERMISSION_SET


def test_p5b_invariant_detects_an_ungated_route():
    from fastapi import APIRouter
    from src.api import admin_route_invariant as inv
    router = APIRouter()

    @router.get("/admin/oops")
    def oops():  # no require_permission
        return {}

    gated = inv.AdminRoute("/admin/oops", ("GET",), inv._permissions(router.routes[0]), router.routes[0])
    assert inv.ungated([gated]) == [gated]


def test_p6_candidate_is_denied_everywhere_and_denial_is_403(env):
    _, ck = env.user("user")
    for r in _routes():
        path = "/api/v1" + re.sub(r"\{[^}]+\}", "1", r.path)
        method = r.methods[0]
        resp = env.c.request(method, path, cookies=ck, json={} if method != "GET" else None)
        assert resp.status_code == 403, (method, path, resp.status_code)


def test_p7_each_role_reaches_only_its_permissions(env):
    cases = {
        "/api/v1/admin/home": perm.OVERVIEW_READ,
        "/api/v1/admin/users": perm.USERS_READ,
        "/api/v1/admin/workspaces": perm.WORKSPACES_READ,
        "/api/v1/admin/providers": perm.INTEGRATIONS_READ,
        "/api/v1/admin/audit": perm.AUDIT_READ,
        "/api/v1/admin/pause": perm.FLAGS_READ,
    }
    for role in perm.ADMIN_ROLES:
        _, ck = env.user(role)
        for path, needed in cases.items():
            code = env.c.get(path, cookies=ck).status_code
            expected = 200 if needed in perm.ROLE_PRESETS[role] else 403
            assert code == expected, (role, path, code)


def test_p8_browser_supplied_role_or_permission_grants_nothing(env):
    _, ck = env.user("user")
    hdrs = {"X-Platform-Role": "platform_admin", "X-Permissions": "platform.overview.read",
            "X-User-Subject": "admin"}
    assert env.c.get("/api/v1/admin/home", cookies=ck, headers=hdrs).status_code == 403
    assert env.c.get("/api/v1/admin/home?role=platform_admin", cookies=ck).status_code == 403


def test_p9_deactivated_admin_is_denied(env):
    uid, ck = env.user("platform_admin")
    assert env.c.get("/api/v1/admin/home", cookies=ck).status_code == 200
    env.accounts.set_status(uid, "deactivated")
    assert env.c.get("/api/v1/admin/home", cookies=ck).status_code in (401, 403)


def test_p10_role_assign_needs_its_own_permission_and_validates_role(env):
    _, support = env.user("support_operator")
    target, _ = env.user("user")
    assert env.c.post(f"/api/v1/admin/users/{target}/role", json={"role": "billing_admin"},
                      cookies=support).status_code == 403
    _, admin = env.user("platform_admin")
    assert env.c.post(f"/api/v1/admin/users/{target}/role", json={"role": "root"},
                      cookies=admin).status_code == 422
    assert env.c.post(f"/api/v1/admin/users/{target}/role", json={"role": "billing_admin"},
                      cookies=admin).status_code == 200
    assert env.accounts.get_account(target).platform_role == "billing_admin"


def test_me_exposes_server_resolved_permissions(env):
    _, cand = env.user("user")
    _, adm = env.user("support_operator")
    assert env.c.get("/api/v1/auth/me", cookies=cand).json()["admin_permissions"] == []
    got = env.c.get("/api/v1/auth/me", cookies=adm).json()["admin_permissions"]
    assert got == perm.sorted_permissions("support_operator")


# ---------------- audit AUD1-AUD8 --------------------------------------------------------------------

def test_aud1_role_change_audited_with_request_id_and_before_after(env):
    _, admin = env.user("platform_admin")
    target, _ = env.user("user")
    r = env.c.post(f"/api/v1/admin/users/{target}/role", json={"role": "support_operator"}, cookies=admin)
    assert r.status_code == 200
    ev = env.events(A.ADMIN_PLATFORM_ROLE_CHANGE)[0]
    assert ev["request_id"] == r.headers["X-Request-Id"]
    assert ev["context"]["before"] == "user" and ev["context"]["after"] == "support_operator"
    assert ev["target_id"] == str(target) and ev["result"] == "success"


def test_aud2_audit_failure_rolls_back_the_mutation(env, monkeypatch):
    _, admin = env.user("platform_admin")
    target, _ = env.user("user")
    from src.auth_repository import AccountRepository

    def boom(session, audit):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    r = env.c.post(f"/api/v1/admin/users/{target}/role", json={"role": "support_operator"}, cookies=admin)
    assert r.status_code == 500
    monkeypatch.undo()
    assert env.accounts.get_account(target).platform_role == "user"
    assert not env.events(A.ADMIN_PLATFORM_ROLE_CHANGE)


def test_aud2b_commit_time_audit_failure_rolls_back_tier_and_status(env, monkeypatch):
    _, admin = env.user("platform_admin")
    target, _ = env.user("user")
    from src import auth_repository as ar

    real = ar.AuditEvent

    class Bad(real):  # a row the DB rejects at flush: NOT NULL violation on event_type
        def __init__(self, **kw):
            kw["event_type"] = None
            super().__init__(**kw)

    monkeypatch.setattr(ar, "AuditEvent", Bad)
    assert env.c.post(f"/api/v1/admin/users/{target}/status", json={"status": "deactivated"},
                      cookies=admin).status_code == 500
    assert env.c.post(f"/api/v1/admin/users/{target}/tier", json={"tier": "premium"},
                      cookies=admin).status_code == 500
    monkeypatch.undo()
    acct = env.accounts.get_account(target)
    assert acct.status == "active" and acct.tier == "basic"


def test_aud3_pause_toggle_is_audit_first_and_fail_closed(env, monkeypatch):
    from src.application.pause import get_pause_registry
    from src.auth_repository import AuditRepository
    _, admin = env.user("platform_admin")
    reg = get_pause_registry()
    reg.set("ocr", False)

    def boom(self, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(AuditRepository, "record", boom)
    r = env.c.post("/api/v1/admin/pause/ocr", json={"paused": True}, cookies=admin)
    assert r.status_code == 503 and not reg.is_paused("ocr")
    monkeypatch.undo()
    r = env.c.post("/api/v1/admin/pause/ocr", json={"paused": True}, cookies=admin)
    assert r.status_code == 200 and reg.is_paused("ocr")
    assert env.events(A.PLATFORM_PAUSE_TOGGLED)[0]["context"]["before"] is False
    reg.set("ocr", False)


def test_aud4_denied_access_is_audited_with_request_id(env):
    uid, ck = env.user("user")
    r = env.c.get("/api/v1/admin/users", cookies=ck)
    assert r.status_code == 403
    ev = env.events(A.ADMIN_ACCESS_DENIED)[0]
    assert ev["actor_user_id"] == uid and ev["result"] == "denied"
    assert ev["request_id"] == r.headers["X-Request-Id"]
    assert ev["target_id"] == perm.USERS_READ and ev["context"]["reason"] == "missing_permission"


def test_aud5_failed_denial_audit_never_grants_access(env, monkeypatch):
    from src.auth_repository import AuditRepository
    _, ck = env.user("user")

    def boom(self, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(AuditRepository, "record", boom)
    assert env.c.get("/api/v1/admin/users", cookies=ck).status_code == 403


def test_aud6_unknown_event_names_are_rejected():
    with pytest.raises(ValueError):
        A.build_audit(event_type="admin.made_up", actor_user_id=1, request_id="r")
    assert A.ADMIN_ACCESS_DENIED in A.ADMIN_EVENT_NAMES


def test_aud7_secret_or_content_context_keys_are_rejected():
    for key in ("password", "api_key", "token", "cv_text", "answer", "memory", "transcript"):
        with pytest.raises(ValueError):
            A.build_audit(event_type=A.ADMIN_ACCESS_DENIED, actor_user_id=1, request_id="r", **{key: "x"})


def test_aud8_status_and_tier_changes_are_audited_atomically(env):
    _, admin = env.user("platform_admin")
    target, _ = env.user("user")
    assert env.c.post(f"/api/v1/admin/users/{target}/status", json={"status": "deactivated"},
                      cookies=admin).status_code == 200
    assert env.c.post(f"/api/v1/admin/users/{target}/tier", json={"tier": "premium"},
                      cookies=admin).status_code == 200
    s = env.events(A.ADMIN_ACCOUNT_STATUS_CHANGE)[0]["context"]
    t = env.events(A.ADMIN_ENTITLEMENT_CHANGE)[0]["context"]
    assert (s["before"], s["after"]) == ("active", "deactivated")
    assert (t["before"], t["after"]) == ("basic", "premium")
    assert env.c.post("/api/v1/admin/users/99999/role", json={"role": "user"}, cookies=admin).status_code == 404


# ---------------- providers PR1-PR6 ------------------------------------------------------------------

SENTINELS = {"OPENROUTER_API_KEY": "sk-or-SENTINEL-1", "BREVO_API_KEY": "brevo-SENTINEL-2",
             "LANGFUSE_SECRET_KEY": "lf-SENTINEL-3", "LANGFUSE_PUBLIC_KEY": "pk-SENTINEL-4",
             "ADZUNA_APP_KEY": "adz-SENTINEL-5", "ADZUNA_APP_ID": "adzid-SENTINEL-6",
             "EMAIL_SENDER": "noreply-SENTINEL@x.test",
             "GOOGLE_CLIENT_ID": "g-SENTINEL-7", "OPENAI_REALTIME_API_KEY": "rt-SENTINEL-8"}


def _providers(env, monkeypatch, set_env=True):
    if set_env:
        for k, v in SENTINELS.items():
            monkeypatch.setenv(k, v)
    _, ck = env.user("platform_admin")
    return env.c.get("/api/v1/admin/providers", cookies=ck)


def test_pr1_no_env_value_or_secret_in_response(env, monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    body = _providers(env, monkeypatch).text
    for v in SENTINELS.values():
        assert v not in body
    assert "SENTINEL" not in body


def test_pr2_response_is_the_allowlist_schema(env, monkeypatch):
    j = _providers(env, monkeypatch).json()
    assert set(j) == {"providers", "speech", "ocr", "pause", "pause_durable", "rate_limit_mode",
                      "rate_limit_distributed", "note"}
    for row in j["providers"]:
        assert set(row) == {"provider_id", "label", "configured", "enabled", "externally_managed", "writable",
                            "status", "health", "live_validation", "mode"}
    with pytest.raises(Exception):
        from src.api.schemas.admin import ProviderRow
        ProviderRow(provider_id="k", label="l", configured=True, enabled=True, status="internal", api_key="x")


def test_pr3_configured_is_not_healthy(env, monkeypatch):
    for row in _providers(env, monkeypatch).json()["providers"]:
        assert row["health"] == "Health not tested"
        assert row["status"] in ("configured_health_not_tested", "not_configured")
        assert row["externally_managed"] is True and row["writable"] is False


def test_pr4_unconfigured_is_reported_not_configured(env, monkeypatch):
    for k in SENTINELS:
        monkeypatch.delenv(k, raising=False)
    rows = {r["provider_id"]: r for r in _providers(env, monkeypatch, set_env=False).json()["providers"]}
    assert rows["openrouter"]["configured"] is False and rows["openrouter"]["status"] == "not_configured"
    assert rows["email"]["mode"] == "console"


def test_pr5_no_network_or_subprocess_on_render(env, monkeypatch):
    import socket

    def no_net(*a, **k):
        raise AssertionError("network call during admin render")

    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.setattr(subprocess, "run", no_net)
    monkeypatch.setattr(subprocess, "Popen", no_net)
    _, ck = env.user("platform_admin")
    assert env.c.get("/api/v1/admin/providers", cookies=ck).status_code == 200
    assert env.c.get("/api/v1/admin/home", cookies=ck).status_code == 200


def test_pr6_providers_requires_integrations_read(env):
    for role in ("billing_admin", "knowledge_admin", "support_operator"):
        _, ck = env.user(role)
        assert env.c.get("/api/v1/admin/providers", cookies=ck).status_code == 403
    _, ck = env.user("operations_admin")
    assert env.c.get("/api/v1/admin/providers", cookies=ck).status_code == 200


# ---------------- Command Center C1-C10 ---------------------------------------------------------------

def _home(env, role="platform_admin"):
    _, ck = env.user(role)
    r = env.c.get("/api/v1/admin/home", cookies=ck)
    assert r.status_code == 200
    return r.json()


def test_c1_build_metadata_is_truthful_unknown_by_default(env, monkeypatch):
    monkeypatch.delenv("APP_GIT_SHA", raising=False)
    monkeypatch.delenv("APP_BUILD_TIME", raising=False)
    b = _home(env)["build"]
    assert b["git_sha"] == "unknown" and b["build_time"] == "unknown" and b["version"]
    assert b["environment"] in ("development", "test", "staging", "production", "unknown")


def test_c2_build_metadata_reads_injected_env_and_sanitizes(env, monkeypatch):
    monkeypatch.setenv("APP_GIT_SHA", "abc1234def; rm -rf /")
    monkeypatch.setenv("APP_BUILD_TIME", "2026-10-02T10:00:00Z")
    b = _home(env)["build"]
    assert b["git_sha"] == "abc1234defrm-rf" or re.fullmatch(r"[A-Za-z0-9._:+\-]+", b["git_sha"])
    assert " " not in b["git_sha"] and ";" not in b["git_sha"] and "/" not in b["git_sha"]
    assert b["build_time"] == "2026-10-02T10:00:00Z"


def test_c3_repository_head_is_the_real_alembic_head():
    from src.application.admin_command_center import repository_head
    assert repository_head() == "0015_support_ticketing"


def test_c4_migration_state_unknown_match_mismatch(env):
    from src.application.admin_command_center import migration_status
    sf = env.repo.session_factory
    assert migration_status(sf)["state"] == "unknown"           # test DB built by create_all
    with sf() as s:
        s.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        s.execute(text("INSERT INTO alembic_version VALUES ('0013_x')"))
        s.commit()
    m = migration_status(sf)
    assert m["state"] == "mismatch" and m["warning"] and "never migrates automatically" in m["warning"]
    with sf() as s:
        s.execute(text("UPDATE alembic_version SET version_num='0015_support_ticketing'"))
        s.commit()
    assert migration_status(sf)["state"] == "match"


def test_c5_command_center_never_runs_a_migration(env):
    _home(env)
    with env.repo.session_factory() as s:
        tables = {r[0] for r in s.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "alembic_version" not in tables


def test_c6_health_is_internal_only(env):
    h = _home(env)["health"]
    assert h["database"] == "reachable" and h["providers_probed"] is False


def test_c7_rate_limit_mode_is_truthfully_process_local(env):
    r = _home(env)["rate_limit"]
    assert r["mode"] == "in_memory_process_local" and r["distributed"] is False


def test_c8_pause_is_labelled_non_durable(env):
    p = _home(env)["pause"]
    assert p["durable"] is False and "non-durable" in p["note"]


def test_c9_privacy_queue_is_not_shown_as_operational_and_no_fake_zero(env):
    j = _home(env)
    assert j["privacy_requests"]["status"] == "not_operational"
    assert "count" not in j["privacy_requests"] and "open" not in j["privacy_requests"]


def test_c10_diagnostic_links_are_permission_gated_and_no_private_content(env):
    full = _home(env)
    assert {l["label"] for l in full["diagnostics_links"]} == {"Knowledge readiness", "Evaluation & agent review"}
    support = _home(env, "support_operator")
    assert support["diagnostics_links"] == []
    blob = str(full).lower()
    for bad in ("transcript", "cv_text", "answers", "conversation", "memory_summary", "password"):
        assert bad not in blob
