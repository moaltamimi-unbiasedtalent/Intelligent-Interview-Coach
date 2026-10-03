"""P10B-W10.6: integrations and API connections. No real provider is ever contacted: probes are fakes or an
httpx MockTransport, and the network is blocked in the tests that matter."""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text

from src import integrations as I
from src.api import dependencies as deps
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import IntegrationState
from src.secret_store import EnvironmentSecretStore, InMemorySecretStore, SecretStoreReadOnly
from tests._auth_factories import cookies_for, login_token, register
from tests.test_admin_foundation_w10_1 import PW, Env

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-or-v1-ABCD1234efgh5678IJKL9012SENTINEL"
ALL_SECRET_ENV = ["OPENROUTER_API_KEY", "COPILOT_EMBEDDING_API_KEY", "REALTIME_VOICE_API_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY",
                  "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "BREVO_API_KEY", "REDIS_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]


@pytest.fixture()
def env(monkeypatch):
    for n in I.probe_environment_allowlist():
        monkeypatch.delenv(n, raising=False)
    e = Env()
    yield e
    e.app.dependency_overrides.pop(deps.get_integration_probes, None)
    e.app.dependency_overrides.pop(deps.get_secret_store, None)
    e.close()


def mk(env, role="user"):
    env.n += 1
    email = f"i{env.n}@x.com"
    register(env.c, email, PW)
    tok = login_token(env.c, email, PW)
    uid = env.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["user_id"]
    if role != "user":
        env.accounts.set_platform_role(uid, role)
    return uid, cookies_for(tok)


def get_all(env, ck):
    r = env.c.get(f"{API}/admin/integrations", cookies=ck)
    assert r.status_code == 200
    return {i["code"]: i for i in r.json()["items"]}


def fake_probes(result):
    return lambda: {"openrouter": result if callable(result) else (lambda store: result),
                    "malware_scanner": lambda store: I.ProbeResult("success", "ok", 3)}


# ---------------- registry / inventory ----------------------------------------------------------------------

def test_registry_is_code_defined_and_has_no_user_controlled_destination():
    assert set(I.REGISTRY) == {"openrouter", "openai_embeddings", "realtime_voice", "adzuna", "google_oidc", "email_brevo",
                               "redis_rate_limit", "langfuse", "malware_scanner"}
    assert set(d.category for d in I.REGISTRY.values()) <= set(I.CATEGORIES)
    assert "billing" not in " ".join(I.REGISTRY).lower() and "stripe" not in json.dumps([d.name for d in I.REGISTRY.values()]).lower()
    # the only external destination any probe can reach is an adapter constant
    assert I.OPENROUTER_PROBE_URL == "https://openrouter.ai/api/v1/auth/key"
    assert set(I.PROBES) == {"openrouter", "malware_scanner"}
    # no integration setting or credential is an arbitrary endpoint field
    for d in I.REGISTRY.values():
        for s in d.settings:
            assert not re.search(r"url|host|endpoint|base", s.env_name, re.I)


def test_inventory_never_returns_a_secret_value_prefix_suffix_or_mask(env, monkeypatch):
    for n in ALL_SECRET_ENV:
        monkeypatch.setenv(n, SECRET)
    _, adm = mk(env, "platform_admin")
    blob = env.c.get(f"{API}/admin/integrations", cookies=adm).text
    blob += "".join(env.c.get(f"{API}/admin/integrations/{c}", cookies=adm).text for c in I.REGISTRY)
    for frag in (SECRET, SECRET[:6], SECRET[-6:], "ABCD1234", "SENTINEL", "sk-or", "..."):
        assert frag not in blob, frag
    items = get_all(env, adm)
    cred = items["openrouter"]["slots"][0]
    assert cred == {"slot": "api_key", "label": "API key", "external_name": "OPENROUTER_API_KEY", "configured": True,
                    "source": "environment", "writable": False}


def test_status_separates_configuration_runtime_and_health_and_classifies_honestly(env, monkeypatch):
    _, adm = mk(env, "platform_admin")
    items = get_all(env, adm)
    assert items["openrouter"]["classification"] == "supported_unconfigured"
    assert items["openrouter"]["configuration_status"] == "unconfigured" and items["openrouter"]["health"]["status"] == "not_tested"
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    o = get_all(env, adm)["openrouter"]
    assert (o["classification"], o["configuration_status"], o["health"]["status"]) == ("runtime_active", "configured", "not_tested")   # configured != healthy
    # Google: configured AND flagged is still NOT validated and not claimed as live
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", SECRET)
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "true")
    g = get_all(env, adm)["google_oidc"]
    assert g["classification"] == "code_present_not_validated" and g["runtime"]["enabled"] is True
    assert "not validated" in g["validation_note"].lower() and g["test"]["supported"] is False
    # Redis: requested but the shared store is not active -> not claimed as live
    monkeypatch.setenv("REDIS_URL", "redis://:" + SECRET + "@h:6379/0")
    r = get_all(env, adm)["redis_rate_limit"]
    assert r["classification"] == "configured_inactive" and r["runtime"]["enabled"] is False and "NOT LIVE" in r["validation_note"]
    # Langfuse: keys without the flag are configured but inactive; with the flag they are active
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", SECRET)
    assert get_all(env, adm)["langfuse"]["classification"] == "configured_inactive"
    monkeypatch.setenv("AGENT_EXTERNAL_OBSERVABILITY_ENABLED", "true")
    assert get_all(env, adm)["langfuse"]["classification"] == "runtime_active"
    # Email: console provider is not a connection; support emails are stated as not sent
    e = get_all(env, adm)["email_brevo"]
    assert e["classification"] == "supported_unconfigured" and "never emailed" in e["validation_note"]
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "fake")
    assert get_all(env, adm)["malware_scanner"]["classification"] == "development_only"


def test_runtime_state_is_environment_owned_with_no_toggle_and_no_rotate_for_env_secrets(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    _, adm = mk(env, "platform_admin")
    for it in get_all(env, adm).values():
        assert it["runtime"]["toggle_supported"] is False and it["runtime"]["managed"] == "environment"
        assert it["store"] == {"name": "environment", "writable": False}
        assert all(c["writable"] is False for c in it["slots"])
    from src.api.admin_route_invariant import admin_routes
    paths = [r.path for r in admin_routes() if r.path.startswith("/admin/integrations")]
    assert not any("enable" in p or "disable" in p or "toggle" in p for p in paths)   # no runtime toggle exists


# ---------------- permissions ---------------------------------------------------------------------------------

def test_integration_permission_matrix(env):
    _, cand = mk(env)
    for role, can_read, can_test in (("platform_admin", True, True), ("operations_admin", True, True), ("billing_admin", False, False),
                                     ("knowledge_admin", False, False), ("support_operator", False, False), ("security_privacy_admin", False, False)):
        _, ck = mk(env, role)
        assert (env.c.get(f"{API}/admin/integrations", cookies=ck).status_code == 200) is can_read, role
        assert (env.c.get(f"{API}/admin/integrations/openrouter", cookies=ck).status_code == 200) is can_read, role
    env.app.dependency_overrides[deps.get_integration_probes] = fake_probes(I.ProbeResult("success", "ok", 5))
    for role, ok in (("platform_admin", True), ("operations_admin", True), ("support_operator", False), ("billing_admin", False)):
        _, ck = mk(env, role)
        assert (env.c.post(f"{API}/admin/integrations/openrouter/test", cookies=ck).status_code == 200) is ok, role
    assert env.c.get(f"{API}/admin/integrations", cookies=cand).status_code == 403
    assert env.c.post(f"{API}/admin/integrations/openrouter/test", cookies=cand).status_code == 403
    # credential replacement needs the distinct, currently unassigned permission
    assert not any(perm.SECRET_ROTATE in p for p in perm.ROLE_PRESETS.values())
    _, adm = mk(env, "platform_admin")
    assert env.c.post(f"{API}/admin/integrations/openrouter/credentials/api_key", json={"value": "x" * 20}, cookies=adm).status_code == 403


def test_read_only_integration_permission_has_no_test_or_credential_access(env, monkeypatch):
    monkeypatch.setitem(perm.ROLE_PRESETS, "support_operator", frozenset({perm.OVERVIEW_READ, perm.INTEGRATIONS_READ}))
    _, ck = mk(env, "support_operator")
    assert env.c.get(f"{API}/admin/integrations", cookies=ck).status_code == 200
    assert env.c.post(f"{API}/admin/integrations/openrouter/test", cookies=ck).status_code == 403
    assert env.c.post(f"{API}/admin/integrations/openrouter/credentials/api_key", json={"value": "x" * 20}, cookies=ck).status_code == 403


# ---------------- manual connection tests ---------------------------------------------------------------------

@pytest.mark.parametrize("result,outcome,category", [
    (I.ProbeResult("success", "ok", 12), "success", "ok"),
    (I.ProbeResult("failure", "unauthorized", 9), "failure", "unauthorized"),
    (I.ProbeResult("failure", "timeout"), "failure", "timeout"),
    (I.ProbeResult("failure", "unavailable", 4), "failure", "unavailable"),
    (I.ProbeResult("failure", "rate_limited", 4), "failure", "rate_limited"),
    (I.ProbeResult("failure", "configuration_error"), "failure", "configuration_error"),
    (I.ProbeResult("failure", "made_up", 1), "failure", "unknown"),
    (I.ProbeResult("success", "made_up", 1), "failure", "unknown"),
])
def test_manual_test_maps_every_result_to_a_bounded_category_and_persists_it(env, result, outcome, category):
    env.app.dependency_overrides[deps.get_integration_probes] = fake_probes(result)
    _, adm = mk(env, "platform_admin")
    r = env.c.post(f"{API}/admin/integrations/openrouter/test", cookies=adm)
    assert r.status_code == 200 and (r.json()["outcome"], r.json()["category"]) == (outcome, category)
    h = get_all(env, adm)["openrouter"]["health"]
    assert h["status"] == ("healthy" if outcome == "success" else "unhealthy") and h["category"] == category and h["last_tested_at"]
    ev = env.events(A.ADMIN_INTEGRATION_TEST_RUN)[0]
    assert ev["request_id"] == r.headers["X-Request-Id"] and ev["context"]["category"] == category and ev["target_id"] == "openrouter"


def test_a_probe_exception_is_discarded_and_never_leaks_its_text(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    def boom(store):
        raise RuntimeError(f"HTTP 401 for Authorization: Bearer {SECRET}")
    env.app.dependency_overrides[deps.get_integration_probes] = fake_probes(boom)
    _, adm = mk(env, "platform_admin")
    r = env.c.post(f"{API}/admin/integrations/openrouter/test", cookies=adm)
    assert r.json()["category"] == "unknown" and SECRET not in r.text
    with env.repo.session_factory() as s:
        row = s.scalar(select(IntegrationState))
        assert SECRET not in json.dumps([row.last_test_outcome, row.last_test_category])
    assert SECRET not in json.dumps([e["context"] for e in env.events()], default=str)


def test_unsupported_and_unknown_integrations_and_no_url_input(env):
    _, adm = mk(env, "platform_admin")
    for code in ("adzuna", "google_oidc", "email_brevo", "redis_rate_limit", "langfuse", "realtime_voice", "openai_embeddings"):
        assert env.c.post(f"{API}/admin/integrations/{code}/test", cookies=adm).status_code == 409, code
    assert env.c.post(f"{API}/admin/integrations/nope/test", cookies=adm).status_code == 404
    for hostile in ("http%3A%2F%2Flocalhost%3A8020%2F", "127.0.0.1", "169.254.169.254", "http%3A%2F%2F10.0.0.1"):
        assert env.c.post(f"{API}/admin/integrations/{hostile}/test", cookies=adm).status_code in (404, 405)
        assert env.c.get(f"{API}/admin/integrations/{hostile}", cookies=adm).status_code in (404, 405)
    assert env.c.post(f"{API}/admin/integrations", json={"code": "x", "url": "http://localhost"}, cookies=adm).status_code in (404, 405)
    assert env.c.post(f"{API}/admin/integrations/openrouter/test", json={"url": "http://localhost"}, cookies=adm).status_code in (200, 409)   # body ignored


def test_no_network_on_list_or_detail_and_probe_failure_audit_rolls_back(env, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("network call from the admin surface")
    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_net)
    _, adm = mk(env, "platform_admin")
    get_all(env, adm)
    assert env.c.get(f"{API}/admin/integrations/openrouter", cookies=adm).status_code == 200
    assert env.c.get(f"{API}/admin/home", cookies=adm).status_code == 200
    env.app.dependency_overrides[deps.get_integration_probes] = fake_probes(I.ProbeResult("success", "ok", 1))
    from src.auth_repository import AccountRepository
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(lambda s, a: (_ for _ in ()).throw(RuntimeError("x"))))
    assert env.c.post(f"{API}/admin/integrations/openrouter/test", cookies=adm).status_code == 500
    monkeypatch.undo()
    with env.repo.session_factory() as s:
        assert s.scalar(select(IntegrationState)) is None             # the result was rolled back with the audit


def test_real_openrouter_probe_uses_the_constant_url_bearer_header_no_redirect_and_never_reads_the_body(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        return httpx.Response(seen.get("status", 200), text=f"BODY-{SECRET}")

    store = EnvironmentSecretStore()
    for status, expected in ((200, ("success", "ok")), (401, ("failure", "unauthorized")), (403, ("failure", "unauthorized")),
                             (429, ("failure", "rate_limited")), (503, ("failure", "unavailable")), (418, ("failure", "unknown"))):
        seen["status"] = status
        r = I.probe_openrouter(store, transport=httpx.MockTransport(handler))
        assert (r.outcome, r.category) == expected, status
    assert seen["url"] == I.OPENROUTER_PROBE_URL and seen["auth"] == f"Bearer {SECRET}"
    assert SECRET not in repr(r) and "BODY" not in repr(r)

    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def down(request):
        raise httpx.ConnectError(f"cannot reach {SECRET}", request=request)

    assert I.probe_openrouter(store, transport=httpx.MockTransport(timeout)).category == "timeout"
    d = I.probe_openrouter(store, transport=httpx.MockTransport(down))
    assert d.category == "unavailable" and SECRET not in repr(d)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert I.probe_openrouter(store, transport=httpx.MockTransport(handler)).category == "configuration_error"


def test_malware_probe_needs_clamav_selected_and_makes_no_live_call(monkeypatch):
    store = EnvironmentSecretStore()
    monkeypatch.delenv("FILE_SCAN_PROVIDER", raising=False)
    assert I.probe_malware_scanner(store).category == "configuration_error"
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "clamav")
    import src.documents.file_security as fs
    monkeypatch.setattr(fs.ClamAvScanner, "available", lambda self: True)
    assert I.probe_malware_scanner(store).outcome == "success"
    monkeypatch.setattr(fs.ClamAvScanner, "available", lambda self: (_ for _ in ()).throw(OSError("conn refused")))
    assert I.probe_malware_scanner(store).category == "unavailable"


# ---------------- SecretStore ------------------------------------------------------------------------------------

def test_environment_store_is_read_only_and_exposes_metadata_only(monkeypatch):
    s = EnvironmentSecretStore()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert (s.is_configured("OPENROUTER_API_KEY"), s.source("OPENROUTER_API_KEY"), s.supports_write) == (False, "none", False)
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    assert s.is_configured("OPENROUTER_API_KEY") and s.source("OPENROUTER_API_KEY") == "environment"
    assert s.get_for_runtime("OPENROUTER_API_KEY").get_secret_value() == SECRET        # runtime path only
    assert SECRET not in repr(s.get_for_runtime("OPENROUTER_API_KEY")) and SECRET not in str(s.get_for_runtime("OPENROUTER_API_KEY"))
    with pytest.raises(SecretStoreReadOnly):
        s.set("OPENROUTER_API_KEY", "new-secret-value-1234")
    import os
    assert os.environ["OPENROUTER_API_KEY"] == SECRET                                   # never mutated
    assert not hasattr(s, "get_for_admin") and not hasattr(s, "reveal") and not hasattr(s, "get")


def test_writable_store_contract():
    s = InMemorySecretStore()
    assert (s.supports_write, s.is_configured("K")) == (True, False)
    s.set("K", "value-one-12345")
    assert s.is_configured("K") and s.source("K") == "in_memory_test"
    s.set("K", "value-two-67890")
    assert s.get_for_runtime("K").get_secret_value() == "value-two-67890" and "value-two" not in repr(s.get_for_runtime("K"))


# ---------------- credential replacement route ---------------------------------------------------------------------

def _allow_rotate(monkeypatch):
    monkeypatch.setitem(perm.ROLE_PRESETS, "platform_admin", perm.ROLE_PRESETS["platform_admin"] | {perm.SECRET_ROTATE})


def test_environment_credentials_cannot_be_replaced_through_the_api(env, monkeypatch):
    _allow_rotate(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    _, adm = mk(env, "platform_admin")
    new = "brand-new-credential-9999"
    r = env.c.post(f"{API}/admin/integrations/openrouter/credentials/api_key", json={"value": new}, cookies=adm)
    assert r.status_code == 409 and "managed outside Ask4Mo" in r.text and new not in r.text
    import os
    assert os.environ["OPENROUTER_API_KEY"] == SECRET
    kinds = [e["event_type"] for e in env.events()]
    assert A.ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED in kinds and A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED in kinds
    assert A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED not in kinds
    assert new not in json.dumps([e["context"] for e in env.events()], default=str)


def test_write_only_replacement_with_a_writable_store_never_returns_or_records_the_value(env, monkeypatch):
    _allow_rotate(monkeypatch)
    store = InMemorySecretStore()
    env.app.dependency_overrides[deps.get_secret_store] = lambda: store
    _, adm = mk(env, "platform_admin")
    first = "first-credential-value-0001"
    r = env.c.post(f"{API}/admin/integrations/openrouter/credentials/api_key", json={"value": first}, cookies=adm)
    assert r.status_code == 200 and r.json() == {"integration": "openrouter", "slot": "api_key", "configured": True}
    assert first not in r.text
    d = env.c.get(f"{API}/admin/integrations/openrouter", cookies=adm)
    assert d.json()["slots"][0]["configured"] is True and d.json()["slots"][0]["writable"] is True and first not in d.text
    second = "second-credential-value-0002"
    assert env.c.post(f"{API}/admin/integrations/openrouter/credentials/api_key", json={"value": second}, cookies=adm).status_code == 200
    assert store.get_for_runtime("OPENROUTER_API_KEY").get_secret_value() == second       # runtime-only read
    events = env.events()
    kinds = [e["event_type"] for e in events]
    assert kinds.count(A.ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED) == 2 and kinds.count(A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED) == 2
    blob = json.dumps([e["context"] for e in events], default=str) + d.text
    assert first not in blob and second not in blob
    ev = env.events(A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED)[0]
    assert ev["context"]["slot"] == "api_key" and ev["target_id"] == "openrouter" and ev["request_id"]


def test_invalid_credential_input_is_rejected_without_echo_and_audit_failure_blocks_the_write(env, monkeypatch):
    _allow_rotate(monkeypatch)
    store = InMemorySecretStore()
    env.app.dependency_overrides[deps.get_secret_store] = lambda: store
    _, adm = mk(env, "platform_admin")
    url = f"{API}/admin/integrations/openrouter/credentials/api_key"
    for body in ({"value": "short"}, {"value": "has whitespace in it 123"}, {"value": 12345678901234}, {"value": "a" * 5000},
                 {"value": "x" * 20, "extra": 1}, {}, ["x"]):
        r = env.c.post(url, json=body, cookies=adm)
        assert r.status_code == 422, body
        for frag in ("short", "whitespace in it", "aaaa", "x" * 20, "12345678901234"):
            assert frag not in r.text, (body, frag)
    assert env.c.post(f"{API}/admin/integrations/openrouter/credentials/nope", json={"value": "x" * 20}, cookies=adm).status_code == 404
    assert not store.is_configured("OPENROUTER_API_KEY")
    from src.auth_repository import AuditRepository
    real = AuditRepository.record
    monkeypatch.setattr(AuditRepository, "record", lambda self, **kw: (_ for _ in ()).throw(RuntimeError("down")))
    assert env.c.post(url, json={"value": "valid-credential-0003"}, cookies=adm).status_code == 503
    monkeypatch.setattr(AuditRepository, "record", real)
    assert not store.is_configured("OPENROUTER_API_KEY")                           # nothing was written without the request audited


def test_store_errors_that_embed_the_value_are_never_surfaced(env, monkeypatch):
    _allow_rotate(monkeypatch)
    class Bad(InMemorySecretStore):
        def set(self, name, value):
            raise RuntimeError(f"backend rejected {value}")
    env.app.dependency_overrides[deps.get_secret_store] = lambda: Bad()
    _, adm = mk(env, "platform_admin")
    val = "leaky-credential-value-0004"
    r = env.c.post(f"{API}/admin/integrations/openrouter/credentials/api_key", json={"value": val}, cookies=adm)
    assert r.status_code == 502 and val not in r.text
    assert val not in json.dumps([e["context"] for e in env.events()], default=str)
    assert A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED in [e["event_type"] for e in env.events()]


# ---------------- no retrieval path, no leak by construction ---------------------------------------------------------

def test_no_admin_code_path_can_return_a_secret():
    for rel in ("src/api/routes/admin_integrations.py", "src/api/routes/admin.py", "src/api/schemas/admin.py",
                "src/application/admin_providers.py", "src/application/admin_command_center.py"):
        assert "get_for_runtime" not in (ROOT / rel).read_text(), rel
    assert "get_for_runtime" in (ROOT / "src/integrations.py").read_text()    # only the adapter probe reads it
    from pydantic import BaseModel
    from src.api.schemas import admin as S
    banned = {"api_key", "secret", "client_secret", "password", "authorization", "bearer", "token_value", "credential_value",
              "private_key", "value"}
    names = []
    for cls in vars(S).values():
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == S.__name__:
            names += list(cls.model_fields)
    assert not [n for n in names if n in banned]
    assert "credential_configured" not in banned and any(n == "configured" for n in names)


def test_validation_errors_never_echo_submitted_input(env):
    _, ck = mk(env)
    body = {"category": "other", "subject": "s" * 500, "message": "private-sentinel-text"}
    r = env.c.post(f"{API}/support/tickets", json=body, cookies=ck)
    assert r.status_code == 422 and "private-sentinel-text" not in r.text and "ssss" not in r.text


def test_no_background_polling_or_scheduler_in_the_integration_code():
    for rel in ("src/integrations.py", "src/secret_store.py", "src/api/routes/admin_integrations.py"):
        src = (ROOT / rel).read_text()
        assert not re.search(r"apscheduler|celery|threading\.Timer|sched\.|asyncio\.create_task|BackgroundTasks|while True|setInterval|schedule\.", src), rel


def test_command_center_integration_counts_are_gated_and_never_claim_health(env):
    _, adm = mk(env, "platform_admin")
    _, sup = mk(env, "support_operator")
    home = env.c.get(f"{API}/admin/home", cookies=adm).json()
    assert set(home["integrations"]) == {"total", "configured", "runtime_active", "not_tested", "unhealthy"}
    assert home["integrations"]["total"] == 9 and home["integrations"]["unhealthy"] == 0 and home["integrations"]["not_tested"] == 2
    assert "integrations" not in env.c.get(f"{API}/admin/home", cookies=sup).json()
    assert '"healthy"' not in json.dumps(home["integrations"])


def test_integration_routes_are_permissioned_and_no_entry_point_creates_integrations():
    from src.api.admin_route_invariant import admin_routes, ungated
    routes = admin_routes()
    mine = [r for r in routes if r.path.startswith("/admin/integrations")]
    assert len(mine) == 4 and ungated(routes) == []
    assert {p for r in mine for p in r.permissions} == {perm.INTEGRATIONS_READ, perm.INTEGRATIONS_MANAGE, perm.SECRET_ROTATE}
    assert not [r for r in mine if r.methods == ("POST",) and r.path == "/admin/integrations"]
    assert len(perm.PERMISSIONS) == 43


# ---------------- migration -----------------------------------------------------------------------------------------

def test_migration_0017_fresh_from_0016_constraints_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.exc import IntegrityError

    def cfg(url):
        c = Config("alembic.ini")
        c.set_main_option("script_location", "migrations")
        c.set_main_option("sqlalchemy.url", url)
        return c

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(cfg(url), "0016_plans_entitlements")
    assert "integration_states" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    eng = create_engine(url)
    assert "integration_states" in inspect(eng).get_table_names()
    cols = {c["name"] for c in inspect(eng).get_columns("integration_states")}
    assert cols == {"integration_code", "last_test_at", "last_test_outcome", "last_test_category", "last_test_latency_ms",
                    "last_test_by_user_id", "updated_at"}                        # no secret, URL or response column
    ins = "INSERT INTO integration_states(integration_code, last_test_outcome, last_test_category, updated_at) VALUES (:c,:o,:k,'2026-01-01')"
    with eng.begin() as c:
        c.execute(text(ins), {"c": "openrouter", "o": "success", "k": "ok"})
    for params in ({"c": "x1", "o": "great", "k": "ok"}, {"c": "x2", "o": "failure", "k": "exploded"}, {"c": "openrouter", "o": "failure", "k": "timeout"}):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(ins), params)
    command.downgrade(cfg(url), "0016_plans_entitlements")
    assert "integration_states" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    assert "integration_states" in inspect(create_engine(url)).get_table_names()
