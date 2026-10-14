"""W12.4B: secure provider and secret administration. No provider is ever contacted; the sentinel below must appear only in this file."""

from __future__ import annotations

import base64
import logging
import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import select

from src import integrations as I
from src.api import dependencies as deps
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.core import secrets as core_secrets
from src.persistence import AuditEvent, ManagedSecret, init_db, make_engine, make_session_factory
from src import secret_store as SS
from tests._role_gov import ensure_elevated
from tests.test_admin_foundation_w10_1 import PW, Env
from tests.test_integrations_w10_6 import mk

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "DO_NOT_LEAK_W12_04B_SECRET_SENTINEL"
SENTINEL2 = "DO_NOT_LEAK_W12_04B_SECOND_SENTINEL"
KEY = base64.b64encode(bytes(range(32))).decode()
OTHER_KEY = base64.b64encode(bytes(range(1, 33))).decode()
OR = "OPENROUTER_API_KEY"


def _sf(tmp_path, name="s.db"):
    eng = make_engine(f"sqlite:///{tmp_path / name}")
    init_db(eng)
    return eng, make_session_factory(eng)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for n in I.probe_environment_allowlist() + [SS.BACKEND_ENV, SS.MASTER_KEY_ENV]:
        monkeypatch.delenv(n, raising=False)
    SS.reset_secret_store_for_tests()
    yield
    SS.reset_secret_store_for_tests()


# ---------------- master key ------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,reason", [(None, "key_missing"), ("", "key_missing"), ("   ", "key_missing"),
                                         ("not base64!!", "key_malformed"), (base64.b64encode(b"x" * 16).decode(), "key_malformed"),
                                         (base64.b64encode(b"x" * 33).decode(), "key_malformed"), ("short", "key_malformed")])
def test_master_key_is_strict_and_never_derived_from_a_password(raw, reason):
    assert SS.master_key_state(raw) == reason
    with pytest.raises(SS.MasterKeyInvalid):
        SS.parse_master_key(raw)
    assert SS.master_key_state(KEY) is None and len(SS.parse_master_key(KEY)) == 32


# ---------------- encryption ------------------------------------------------------------------------------------

def test_round_trip_ciphertext_differs_and_plaintext_is_absent_from_row_and_file_bytes(tmp_path):
    eng, sf = _sf(tmp_path)
    store = SS.EncryptedDatabaseSecretStore(sf, KEY)
    r1 = store.set(OR, SENTINEL)
    assert r1 == {"action": "created", "revision": 1}
    assert store.get_for_runtime(OR).get_secret_value() == SENTINEL and SENTINEL not in repr(store.get_for_runtime(OR))
    with sf() as s:
        row = s.scalar(select(ManagedSecret))
        c1, n1 = bytes(row.ciphertext), bytes(row.nonce)
        assert SENTINEL.encode() not in c1 and len(n1) == 12 and row.key_id and len(row.key_id) == 8
        assert not any(SENTINEL in str(getattr(row, c)) for c in ("integration_code", "slot", "key_id"))
    store.set(OR, SENTINEL)                                   # same plaintext again: new nonce and ciphertext
    with sf() as s:
        row = s.scalar(select(ManagedSecret))
        assert (bytes(row.ciphertext), bytes(row.nonce)) != (c1, n1) and row.revision == 2
    eng.dispose()
    with sqlite3.connect(tmp_path / "s.db") as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    raw = (tmp_path / "s.db").read_bytes()
    assert SENTINEL.encode() not in raw and KEY.encode() not in raw and SS.parse_master_key(KEY) not in raw


def test_tampered_ciphertext_wrong_key_and_swapped_slot_fail_closed(tmp_path):
    _, sf = _sf(tmp_path)
    store = SS.EncryptedDatabaseSecretStore(sf, KEY)
    store.set(OR, SENTINEL)
    store.set("ADZUNA_APP_KEY", SENTINEL2)
    store.invalidate()
    with sf() as s:
        row = s.scalar(select(ManagedSecret).where(ManagedSecret.slot == "api_key"))
        flipped = bytearray(row.ciphertext)
        flipped[0] ^= 1
        row.ciphertext = bytes(flipped)
        s.commit()
    assert store.get_for_runtime(OR) is None and store.managed_meta(OR)["readable"] is False
    # wrong master key
    store2 = SS.EncryptedDatabaseSecretStore(sf, OTHER_KEY)
    assert store2.get_for_runtime("ADZUNA_APP_KEY") is None
    # a ciphertext moved to another slot does not authenticate (the slot is bound as associated data)
    store.invalidate()
    with sf() as s:
        a = s.scalar(select(ManagedSecret).where(ManagedSecret.slot == "app_key"))
        b = ManagedSecret(integration_code="google_oidc", slot="client_secret", ciphertext=a.ciphertext, nonce=a.nonce, key_id=a.key_id, revision=1)
        s.add(b)
        s.commit()
    assert store.get_for_runtime("GOOGLE_CLIENT_SECRET") is None and store.get_for_runtime("ADZUNA_APP_KEY").get_secret_value() == SENTINEL2


def test_unknown_slot_missing_key_and_unbound_store_fail_closed_without_plaintext(tmp_path):
    _, sf = _sf(tmp_path)
    with pytest.raises(SS.SecretSlotUnknown):
        SS.EncryptedDatabaseSecretStore(sf, KEY).set("AWS_SECRET_ACCESS_KEY", SENTINEL)
    for raw, reason in ((None, "key_missing"), ("garbage", "key_malformed")):
        st = SS.EncryptedDatabaseSecretStore(sf, raw)
        st._raw_key = raw
        assert st.write_state() == {"state": "unavailable", "reason": reason} and st.supports_write is False
        with pytest.raises(SS.SecretStoreUnavailable) as e:
            st.set(OR, SENTINEL)
        assert e.value.reason == reason and SENTINEL not in str(e.value)
    with sf() as s:
        assert s.scalar(select(ManagedSecret)) is None            # nothing was stored, in any form
    assert SS.EncryptedDatabaseSecretStore(None, KEY).write_state() == {"state": "unavailable", "reason": "not_bound"}


def test_optimistic_revision_prevents_a_lost_update_and_removal_deletes_the_row(tmp_path):
    _, sf = _sf(tmp_path)
    st = SS.EncryptedDatabaseSecretStore(sf, KEY)
    st.set(OR, SENTINEL, expected_revision=0)
    st.set(OR, SENTINEL2, expected_revision=1)
    with pytest.raises(SS.SecretStoreStale):
        st.set(OR, SENTINEL, expected_revision=1)
    with pytest.raises(SS.SecretStoreStale):
        st.remove(OR, expected_revision=1)
    st.remove(OR, expected_revision=2)
    assert not st.is_configured(OR) and st.get_for_runtime(OR) is None
    with sf() as s:
        assert s.scalar(select(ManagedSecret)) is None


# ---------------- precedence: managed > environment > not configured, through the REAL runtime consumers --------------

def _layered(tmp_path, monkeypatch):
    _, sf = _sf(tmp_path)
    monkeypatch.setenv(SS.BACKEND_ENV, SS.BACKEND_ENCRYPTED)
    monkeypatch.setenv(SS.MASTER_KEY_ENV, KEY)
    SS.reset_secret_store_for_tests()
    store = SS.bind_secret_store(sf)
    assert isinstance(store, SS.LayeredSecretStore)
    return store


def test_default_backend_is_the_environment_store_with_no_resolver_and_no_database_access():
    assert isinstance(SS.get_secret_store(), SS.EnvironmentSecretStore)
    assert core_secrets.read_managed(OR) is None


def test_managed_value_beats_environment_then_environment_returns_after_removal_for_every_consumer(tmp_path, monkeypatch):
    from src.config import load_config as interview_config
    from src.copilot.config import load_config as copilot_config
    from src.copilot.knowledge.providers import adzuna
    from src.mail.sender import BrevoEmailSender, build_email_sender
    from src.observability.config import load_config as obs_config
    from src.application.oidc import google_enabled

    monkeypatch.setenv("OPENROUTER_API_KEY", "env-openrouter-value-AAAA")
    monkeypatch.setenv("COPILOT_EMBEDDING_API_KEY", "env-embedding-value-AAAA")
    monkeypatch.setenv("ADZUNA_APP_ID", "env-adzuna-id-AAAA")
    monkeypatch.setenv("ADZUNA_APP_KEY", "env-adzuna-key-AAAA")
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("EMAIL_SENDER", "no-reply@example.test")
    monkeypatch.setenv("BREVO_API_KEY", "env-brevo-value-AAAA")
    monkeypatch.setenv("REALTIME_VOICE_API_KEY", "env-realtime-value-AAAA")
    store = _layered(tmp_path, monkeypatch)

    def seen():
        icfg, ccfg = interview_config(), copilot_config()
        sender = build_email_sender()
        assert isinstance(sender, BrevoEmailSender)
        from src.voice.realtime import _secrets as rt_secrets   # the realtime provider reads through the same module
        return {"interview": icfg.api_key.get_secret_value() if icfg.api_key else None,
                "copilot": ccfg.api_key.get_secret_value() if ccfg.api_key else None,
                "embedding": ccfg.embedding_api_key.get_secret_value() if ccfg.embedding_api_key else None,
                "adzuna": adzuna._creds(), "brevo": sender._api_key if hasattr(sender, "_api_key") else sender.__dict__.get("api_key"),
                "realtime": rt_secrets.read_secret("REALTIME_VOICE_API_KEY").get_secret_value()}

    before = seen()
    assert before["interview"] == before["copilot"] == "env-openrouter-value-AAAA" and before["adzuna"] == ("env-adzuna-id-AAAA", "env-adzuna-key-AAAA")
    store.set("OPENROUTER_API_KEY", "managed-openrouter-value-BBBB")
    store.set("COPILOT_EMBEDDING_API_KEY", "managed-embedding-value-BBBB")
    store.set("ADZUNA_APP_ID", "managed-adzuna-id-BBBB")
    store.set("ADZUNA_APP_KEY", "managed-adzuna-key-BBBB")
    store.set("BREVO_API_KEY", "managed-brevo-value-BBBB")
    store.set("REALTIME_VOICE_API_KEY", "managed-realtime-value-BBBB")
    during = seen()
    assert during["interview"] == during["copilot"] == "managed-openrouter-value-BBBB"
    assert during["embedding"] == "managed-embedding-value-BBBB" and during["adzuna"] == ("managed-adzuna-id-BBBB", "managed-adzuna-key-BBBB")
    assert during["realtime"] == "managed-realtime-value-BBBB"
    assert "managed-brevo-value-BBBB" in repr(during["brevo"]) or during["brevo"] == "managed-brevo-value-BBBB"
    assert store.source("OPENROUTER_API_KEY") == "managed" and os.environ["OPENROUTER_API_KEY"] == "env-openrouter-value-AAAA"   # env untouched
    for n in ("OPENROUTER_API_KEY", "COPILOT_EMBEDDING_API_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "BREVO_API_KEY", "REALTIME_VOICE_API_KEY"):
        store.remove(n)
    after = seen()
    assert after == before                                         # removed -> the environment fallback is back, byte for byte
    for n in ("OPENROUTER_API_KEY", "ADZUNA_APP_ID"):
        monkeypatch.delenv(n)
    assert interview_config().api_key is None and not store.is_configured("OPENROUTER_API_KEY")   # nothing anywhere -> not configured
    assert obs_config().secret_key_present is False and google_enabled() is False


def test_managed_langfuse_redis_and_google_values_are_seen_by_their_factories(tmp_path, monkeypatch):
    from src.api import rate_limit
    from src.observability.config import load_config as obs_config
    from src.application.oidc import google_enabled

    store = _layered(tmp_path, monkeypatch)
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "true")
    assert (obs_config().public_key_present, obs_config().secret_key_present, google_enabled()) == (False, False, False)
    for n, v in (("LANGFUSE_PUBLIC_KEY", "pk-managed-value-1"), ("LANGFUSE_SECRET_KEY", "sk-managed-value-1"),
                 ("GOOGLE_CLIENT_ID", "managed-google-id-1"), ("GOOGLE_CLIENT_SECRET", "managed-google-secret-1")):
        store.set(n, v)
    assert obs_config().public_key_present and obs_config().secret_key_present
    assert google_enabled() is True
    # the shared rate limiter consults the same resolver: a managed REDIS_URL makes the shared store REQUESTED (the optional package is absent here)
    assert store.set("REDIS_URL", "redis://managed-host:6379/0")["action"] == "created"
    rate_limit.build_rate_limiter()
    assert rate_limit._shared_store_requested is True


def test_resolver_answers_only_for_code_defined_credential_names(tmp_path, monkeypatch):
    store = _layered(tmp_path, monkeypatch)
    store.set(OR, SENTINEL)
    assert store.managed_value("DATABASE_URL") is None and store.managed_value("SECRET_STORE_MASTER_KEY") is None
    assert core_secrets.read_managed("SECRET_STORE_MASTER_KEY") is None


def test_unreadable_managed_credential_falls_back_to_the_environment_and_is_reported(tmp_path, monkeypatch):
    store = _layered(tmp_path, monkeypatch)
    monkeypatch.setenv(OR, "env-openrouter-value-AAAA")
    store.set(OR, SENTINEL)
    store.managed._raw_key = OTHER_KEY      # the deployment key no longer matches the stored ciphertext
    store.managed.invalidate()
    assert core_secrets.read_secret(OR).get_secret_value() == "env-openrouter-value-AAAA"
    svc = I.IntegrationService(store.managed._sf, store)
    slot = svc.get("openrouter")["slots"][0]
    assert slot["managed"] is True and slot["managed_readable"] is False and SENTINEL not in str(slot)


# ---------------- HTTP: authorization, step-up, audit, leakage ----------------------------------------------------

@pytest.fixture()
def env(monkeypatch):
    e = Env()
    eng_store = SS.LayeredSecretStore(SS.EncryptedDatabaseSecretStore(e.repo.session_factory, KEY))
    e.store = eng_store
    e.app.dependency_overrides[deps.get_secret_store] = lambda: eng_store
    yield e
    e.app.dependency_overrides.pop(deps.get_secret_store, None)
    core_secrets.set_managed_resolver(None)
    e.close()


URL = f"{API}/admin/integrations/openrouter/credentials/api_key"


def _rows(env):
    with env.repo.session_factory() as s:
        return s.scalars(select(ManagedSecret)).all()


def test_authorization_matrix_candidates_and_every_specialist_are_denied_before_anything_else(env):
    assert [r for r, p in perm.ROLE_PRESETS.items() if perm.SECRET_ROTATE in p] == ["platform_admin"] and len(perm.PERMISSIONS) == 43
    _, cand = mk(env)
    assert env.c.post(URL, json={"value": SENTINEL}, cookies=cand).status_code == 403
    for role in ("operations_admin", "knowledge_admin", "billing_admin", "support_operator", "security_privacy_admin"):
        _, ck = mk(env, role)
        assert env.c.post(URL, json={"value": SENTINEL}, cookies=ck).status_code == 403, role
        assert env.c.post(f"{URL}/remove", json={"confirm": True}, cookies=ck).status_code == 403, role
    assert _rows(env) == []
    _, ops = mk(env, "operations_admin")
    assert env.c.get(f"{API}/admin/integrations/openrouter", cookies=ops).status_code == 200      # may inspect, never rotate
    assert env.c.get(f"{API}/admin/integrations/openrouter", cookies=cand).status_code == 403


def test_a_fresh_step_up_is_required_expired_and_other_sessions_do_not_count_and_the_owner_cannot_bypass(env):
    _, adm = mk(env, "platform_admin")
    r = env.c.post(URL, json={"value": SENTINEL}, cookies=adm)
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required" and SENTINEL not in r.text
    assert env.c.post(f"{URL}/remove", json={"confirm": True}, cookies=adm).status_code == 403
    assert _rows(env) == []
    ensure_elevated(env.c, adm, PW)
    assert env.c.post(URL, json={"value": SENTINEL}, cookies=adm).status_code == 200
    # expire the elevation: denied again
    from sqlalchemy import text
    with env.repo.session_factory() as s:
        s.execute(text("UPDATE auth_sessions SET elevated_until = '2000-01-01 00:00:00'"))
        s.commit()
    assert env.c.post(URL, json={"value": SENTINEL2}, cookies=adm).status_code == 403
    # a second login (different server-side session) of the same account is not elevated
    from tests._auth_factories import cookies_for, login_token
    email = env.c.get(f"{API}/auth/me", cookies=adm).json()["email"]
    other = cookies_for(login_token(env.c, email, PW))
    assert env.c.post(URL, json={"value": SENTINEL2}, cookies=other).status_code == 403


def test_oidc_only_or_passwordless_accounts_fail_closed_with_a_bounded_message(env):
    from src.admin_security.errors import StepUpUnavailable
    from src.admin_security.stepup import StepUpService

    with pytest.raises(StepUpUnavailable) as e:
        StepUpService(env.repo.session_factory).confirm(user_id=987654, session_token="tok", password="x", request_id=None)
    assert "not available" in str(e.value)


def test_configure_rotate_remove_return_metadata_only_and_the_sentinel_never_leaks(env, caplog):
    caplog.set_level(logging.DEBUG)
    uid, adm = mk(env, "platform_admin")
    ensure_elevated(env.c, adm, PW)
    r1 = env.c.post(URL, json={"value": SENTINEL}, cookies=adm)
    assert r1.status_code == 200 and r1.json() == {"integration": "openrouter", "slot": "api_key", "configured": True, "action": "created", "revision": 1}
    d = env.c.get(f"{API}/admin/integrations/openrouter", cookies=adm)
    slot = d.json()["slots"][0]
    assert slot["source_kind"] == "managed" and slot["managed"] is True and slot["revision"] == 1 and slot["last_rotated_at"]
    assert d.json()["health"]["status"] == "not_tested"          # saving a credential never claims health and never calls the provider
    r2 = env.c.post(URL, json={"value": SENTINEL2, "expected_revision": 1}, cookies=adm)
    assert r2.json()["action"] == "rotated" and r2.json()["revision"] == 2
    assert env.store.get_for_runtime(OR).get_secret_value() == SENTINEL2     # old value no longer resolves
    stale = env.c.post(URL, json={"value": SENTINEL, "expected_revision": 1}, cookies=adm)
    assert stale.status_code == 409 and "changed since" in stale.text
    assert env.c.post(f"{URL}/remove", json={}, cookies=adm).status_code == 422                       # explicit confirmation
    assert env.c.post(f"{URL}/remove", json={"confirm": True, "expected_revision": 1}, cookies=adm).status_code == 409
    rem = env.c.post(f"{URL}/remove", json={"confirm": True, "expected_revision": 2}, cookies=adm)
    assert rem.status_code == 200 and rem.json()["removed"] is True and _rows(env) == []
    after = env.c.get(f"{API}/admin/integrations/openrouter", cookies=adm).json()["slots"][0]
    assert after["source_kind"] == "none" and after["configured"] is False
    # leakage sweep: every response, every audit row, and the captured logs
    blob = " ".join([r1.text, r2.text, stale.text, rem.text, d.text, env.c.get(f"{API}/admin/integrations", cookies=adm).text, caplog.text])
    with env.repo.session_factory() as s:
        events = s.scalars(select(AuditEvent)).all()
        blob += " ".join(f"{e.event_type} {e.context} {e.target_id}" for e in events)
    for frag in (SENTINEL, SENTINEL2, SENTINEL[:12], SENTINEL2[-8:], KEY):
        assert frag not in blob, frag
    kinds = [e.event_type for e in events]
    assert A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED in kinds and A.ADMIN_CREDENTIAL_REMOVED in kinds
    ev = [e for e in events if e.event_type == A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED][0]
    assert ev.context["slot"] == "api_key" and ev.context["action"] == "created" and ev.actor_user_id == uid and ev.request_id
    assert not any(k in str(ev.context).lower() for k in ("ciphertext", "nonce", "fingerprint", "mask", "suffix"))


def test_validation_errors_and_unknown_targets_never_echo_the_input(env):
    _, adm = mk(env, "platform_admin")
    ensure_elevated(env.c, adm, PW)
    for body in ({"value": "short"}, {"value": SENTINEL + " has spaces"}, {"value": 12345678901234}, {"value": "a" * 5000},
                 {"value": SENTINEL, "extra": 1}, {}, ["x"]):
        r = env.c.post(URL, json=body, cookies=adm)
        assert r.status_code == 422 and SENTINEL not in r.text and "spaces" not in r.text, body
    assert env.c.post(f"{API}/admin/integrations/openrouter/credentials/nope", json={"value": SENTINEL}, cookies=adm).status_code == 404
    assert env.c.post(f"{API}/admin/integrations/not_real/credentials/api_key", json={"value": SENTINEL}, cookies=adm).status_code == 404
    assert _rows(env) == []


def test_audit_and_store_are_one_transaction_a_failed_audit_stores_nothing(env, monkeypatch):
    from src.auth_repository import AccountRepository

    _, adm = mk(env, "platform_admin")
    ensure_elevated(env.c, adm, PW)
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(lambda s, spec: (_ for _ in ()).throw(RuntimeError(f"down {SENTINEL}"))))
    r = env.c.post(URL, json={"value": SENTINEL}, cookies=adm)
    assert r.status_code in (502, 503) and SENTINEL not in r.text
    assert _rows(env) == []


def test_master_key_failures_return_a_bounded_unavailable_state_and_never_store_plaintext(env):
    _, adm = mk(env, "platform_admin")
    ensure_elevated(env.c, adm, PW)
    for raw, frag in ((None, "not configured"), ("%%%", "not valid")):
        env.store.managed._raw_key = raw
        r = env.c.post(URL, json={"value": SENTINEL}, cookies=adm)
        assert r.status_code == 503 and frag in r.text and SENTINEL not in r.text
        view = env.c.get(f"{API}/admin/integrations/openrouter", cookies=adm).json()["store"]
        assert view["state"] == "unavailable" and view["writable"] is False and view["reason"] in ("key_missing", "key_malformed")
    assert _rows(env) == []


def test_environment_only_deployments_are_read_only_and_nothing_is_imported(env, monkeypatch):
    monkeypatch.setenv(OR, "env-openrouter-value-AAAA")
    env.app.dependency_overrides[deps.get_secret_store] = lambda: SS.EnvironmentSecretStore()
    _, adm = mk(env, "platform_admin")
    ensure_elevated(env.c, adm, PW)
    r = env.c.post(URL, json={"value": SENTINEL}, cookies=adm)
    assert r.status_code == 409 and "managed outside Ask4Mo" in r.text
    assert env.c.get(f"{API}/admin/integrations/openrouter", cookies=adm).json()["store"]["state"] == "read_only"
    assert _rows(env) == []                                        # no automatic environment -> database copy


# ---------------- contract, config, migration, hygiene -----------------------------------------------------------

def test_openapi_marks_the_value_write_only_and_no_route_can_read_a_secret(env):
    spec = env.c.get(f"{API}/openapi.json").json() if env.c.get(f"{API}/openapi.json").status_code == 200 else env.app.openapi()
    body = spec["paths"]["/api/v1/admin/integrations/{code}/credentials/{slot}"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["properties"]["value"]["writeOnly"] is True and body["properties"]["value"]["format"] == "password"
    for path, item in spec["paths"].items():
        if path.startswith("/api/v1/admin/integrations"):
            assert not (set(item) - {"get", "post"})                # no PUT/PATCH/DELETE; reads are metadata schemas only
    blob = str(spec["components"]["schemas"].get("CredentialStatus"))
    for forbidden in ("value", "ciphertext", "nonce", "mask", "suffix", "prefix", "fingerprint", "hash"):
        assert f"'{forbidden}'" not in blob


def test_production_fails_closed_when_the_encrypted_store_is_selected_without_a_valid_key(monkeypatch):
    from src.api.env_validation import validate_runtime_config
    monkeypatch.setenv(SS.BACKEND_ENV, SS.BACKEND_ENCRYPTED)
    assert any("SECRET_STORE_MASTER_KEY" in c for c in validate_runtime_config("production").critical)
    monkeypatch.setenv(SS.MASTER_KEY_ENV, "nope")
    assert any("SECRET_STORE_MASTER_KEY" in c for c in validate_runtime_config("production").critical)
    monkeypatch.setenv(SS.MASTER_KEY_ENV, KEY)
    assert not any("SECRET_STORE" in c for c in validate_runtime_config("production").critical)
    monkeypatch.setenv(SS.BACKEND_ENV, "plaintext_file")
    assert any("SECRET_STORE_BACKEND" in c for c in validate_runtime_config("production").critical)


def test_migration_0026_single_head_fresh_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    def cfg(url):
        c = Config("alembic.ini")
        c.set_main_option("script_location", "migrations")
        c.set_main_option("sqlalchemy.url", url)
        return c

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    assert ScriptDirectory.from_config(cfg(url)).get_heads() == ["0026_managed_secrets"]
    command.upgrade(cfg(url), "0025_security_audit_incidents")
    assert "managed_secrets" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    cols = {c["name"] for c in inspect(create_engine(url)).get_columns("managed_secrets")}
    assert cols == {"id", "integration_code", "slot", "ciphertext", "nonce", "key_id", "revision", "created_at", "updated_at", "updated_by_user_id"}
    command.downgrade(cfg(url), "0025_security_audit_incidents")
    assert "managed_secrets" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")


def test_the_sentinel_and_master_keys_exist_only_in_test_sources():
    import subprocess

    out = subprocess.run(["git", "grep", "-l", "W12_04B_SECRET_SENTINEL", "--", "."], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert set(out) <= {"tests/test_secret_admin_w12_4b.py", "frontend/tests/secret-admin-w12-4b.test.tsx"}, out
    assert not (ROOT / ".env.example").read_text().count("SECRET_STORE_MASTER_KEY=") or "SECRET_STORE_MASTER_KEY=\n" in (ROOT / ".env.example").read_text()
