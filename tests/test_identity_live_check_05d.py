"""05D: the live-verification harness and operator script, exercised OFFLINE against fakes (mock Google, in-process webhook, fake Redis). The script is dry-run by
default, refuses to act without explicit authorisation, and never prints a secret. The live runs themselves are NOT RUN."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from src.application import identity_live_check as L
from src.application.oidc import GoogleOidcProvider, new_pkce_verifier, pkce_challenge
from tests._fake_redis import FakeRedis
from tests.test_mail_webhook_05d import Env as WebhookEnv, REF, SECRET
from tests.test_oidc_hardening_w12_4c import CB, CID, CSEC, Google, NOW

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_identity_live_05d.py"
GOOD_ENV = {"LIVE_VERIFY_AUTHORISED": L.AUTHORISATION_VALUE, "API_ENV": "staging"}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    real = socket.socket.connect

    def guard(self, addr, *a, **k):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("/"):
            raise AssertionError(f"outbound network attempt to {host}")
        return real(self, addr, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guard)


# ---- authorisation ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("env,flag", [
    (GOOD_ENV, False),
    ({"API_ENV": "staging"}, True),
    ({**GOOD_ENV, "LIVE_VERIFY_AUTHORISED": "yes"}, True),
    ({**GOOD_ENV, "API_ENV": "production"}, True),
    ({**GOOD_ENV, "API_ENV": "development"}, True),
    ({**GOOD_ENV, "API_ENV": ""}, True),
    ({"LIVE_VERIFY_AUTHORISED": L.AUTHORISATION_VALUE}, True),
])
def test_live_actions_refuse_unless_flag_variable_and_staging_all_hold(env, flag):
    with pytest.raises(L.LiveCheckRefused):
        L.require_live_authorisation(env, flag=flag)


def test_full_authorisation_on_staging_is_accepted():
    L.require_live_authorisation(GOOD_ENV, flag=True)


# ---- google: authorization request ----------------------------------------------------------------------------------------------
def _auth_url(verifier, state="s" * 22):
    return GoogleOidcProvider(client_id=CID, client_secret=CSEC).authorization_url(state=state, redirect_uri=CB, code_challenge=pkce_challenge(verifier))


def test_a_correct_authorization_request_passes_every_check():
    v = new_pkce_verifier()
    rep = L.check_authorization_url(_auth_url(v), verifier=v, state="s" * 22, redirect_uri=CB, client_id=CID)
    assert rep.passed, rep.to_dict()


@pytest.mark.parametrize("mutate,failing", [
    (lambda u, v: u.replace("code_challenge_method=S256", "code_challenge_method=plain"), "pkce_method_s256"),
    (lambda u, v: u.replace(pkce_challenge(v), pkce_challenge("another-verifier")), "pkce_challenge_matches_verifier"),
    (lambda u, v: u.replace("state=" + "s" * 22, "state=other"), "state_present_and_matches"),
    (lambda u, v: u.replace("accounts.google.com", "evil.example"), "host_is_google"),
    (lambda u, v: u.replace("client_id=" + CID, "client_id=intruder"), "client_id_is_ours"),
    (lambda u, v: u.replace("openid+email+profile", "email"), "scope_has_openid"),
])
def test_each_authorization_defect_is_caught(mutate, failing):
    v = new_pkce_verifier()
    rep = L.check_authorization_url(mutate(_auth_url(v), v), verifier=v, state="s" * 22, redirect_uri=CB, client_id=CID)
    assert rep.checks[failing]["state"] == L.FAIL and not rep.passed


def test_a_url_without_pkce_fails():
    v = new_pkce_verifier()
    url = GoogleOidcProvider(client_id=CID, client_secret=CSEC).authorization_url(state="s" * 22, redirect_uri=CB)
    assert L.check_authorization_url(url, verifier=v, state="s" * 22, redirect_uri=CB, client_id=CID).checks["pkce_method_s256"]["state"] == L.FAIL


# ---- google: callback against the mock Google ---------------------------------------------------------------------------------
def _run(g: Google, *, verifier=None, issue_verifier=None, existing=None, required=True):
    verifier = verifier or new_pkce_verifier()
    code = g.issue_code(_auth_url(issue_verifier or verifier))

    def factory(rec):
        return GoogleOidcProvider(client_id=CID, client_secret=CSEC, transport=rec, clock=lambda: NOW)
    return L.run_callback_check(factory, code=code, redirect_uri=CB, verifier=verifier, transport=g.transport, existing_account=existing, invitation_required=required)


def test_a_good_callback_proves_pkce_idtoken_userinfo_and_the_invitation_rule():
    rep = _run(Google(), existing=lambda sub, email: False)
    d = rep.to_dict()
    assert rep.passed, d
    assert d["checks"]["invitation_only_new_account"]["state"] == L.PASS and d["subject_hash"] and len(d["subject_hash"]) == 8
    assert "g-sub-1" not in json.dumps(d) and "owner@example.test" not in json.dumps(d)


def test_an_existing_account_makes_the_invitation_check_not_run_not_pass():
    rep = _run(Google(), existing=lambda sub, email: True)
    assert rep.checks["invitation_only_new_account"]["state"] == L.NOT_RUN and not rep.passed


def test_registration_without_the_requirement_is_a_failed_invitation_check():
    rep = _run(Google(), existing=lambda s, e: False, required=False)
    assert rep.checks["invitation_only_new_account"]["state"] == L.FAIL


def test_no_account_lookup_means_the_invitation_check_is_not_run():
    assert _run(Google()).checks["invitation_only_new_account"]["state"] == L.NOT_RUN


@pytest.mark.parametrize("g", [
    Google(userinfo={"sub": "someone-else", "email": "owner@example.test", "email_verified": True}),
    Google(id_claims={"aud": "another-client"}),
    Google(id_claims={"exp": NOW - 3600}),
    Google(id_header={"alg": "none"}),
    Google(token_status=400),
])
def test_every_provider_refusal_is_a_failed_exchange_with_the_rest_not_run(g):
    rep = _run(g)
    assert rep.checks["exchange_succeeded"]["state"] == L.FAIL and rep.checks["id_token_validated"]["state"] == L.NOT_RUN and not rep.passed
    assert CSEC not in json.dumps(rep.to_dict())


def test_a_wrong_pkce_verifier_is_refused_by_the_authorization_server():
    rep = _run(Google(), verifier=new_pkce_verifier(), issue_verifier=new_pkce_verifier())
    assert rep.checks["exchange_succeeded"]["state"] == L.FAIL


def test_the_recording_transport_records_shapes_never_values():
    g = Google()
    v = new_pkce_verifier()
    code = g.issue_code(_auth_url(v))
    rec = L.RecordingTransport(g.transport)
    GoogleOidcProvider(client_id=CID, client_secret=CSEC, transport=rec, clock=lambda: NOW).exchange(code=code, redirect_uri=CB, code_verifier=v)
    assert rec.token_form_keys >= {"code", "code_verifier", "client_secret", "redirect_uri"} and rec.userinfo_bearer
    blob = json.dumps({k: str(getattr(rec, k)) for k in vars(rec) if not k.startswith("_")})
    assert v not in blob and CSEC not in blob and code not in blob


# ---- webhook probes against the real receiver (gate opened in the test only) ------------------------------------------------
def test_probes_produce_the_expected_statuses_against_the_real_receiver_hmac_mode():
    e = WebhookEnv()
    e.submit()
    probes = L.build_webhook_probes(SECRET, message_ref=REF, now=NOW)
    rep = L.run_webhook_probes(lambda body, h: e.c.post("/api/v1/mail/webhooks/brevo", content=body, headers={"content-type": "application/json", **h}).status_code, probes)
    assert rep.passed, rep.to_dict()
    assert e.row().delivery_state == "delivered"
    assert {p["name"] for p in probes} >= {"forged_signature", "old_signature_timestamp", "replay_of_valid_event", "malformed_payload", "missing_signature"}


def test_probes_in_bearer_mode_have_no_timestamp_probe_and_pass():
    e = WebhookEnv(mode="bearer")
    e.submit()
    probes = L.build_webhook_probes(SECRET, message_ref=REF, now=NOW, mode="bearer")
    assert "old_signature_timestamp" not in {p["name"] for p in probes}
    assert L.run_webhook_probes(lambda b, h: e.post(b, h).status_code, probes).passed


def test_with_the_gate_closed_the_probes_fail_loudly_so_a_closed_gate_is_visible():
    e = WebhookEnv(authorized=None)
    rep = L.run_webhook_probes(lambda b, h: e.post(b, h).status_code, L.build_webhook_probes(SECRET, message_ref=REF, now=NOW))
    assert not rep.passed and all("got 503" in c["reason"] for c in rep.checks.values())


def test_probe_transport_errors_are_failures_not_crashes():
    def boom(b, h):
        raise OSError("x")
    assert not L.run_webhook_probes(boom, L.build_webhook_probes(SECRET, message_ref=REF, now=NOW)).passed


# ---- limiter checks against the fake store ----------------------------------------------------------------------------------
def test_limiter_checks_pass_against_a_correct_store_and_clean_up_only_their_own_keys():
    clock = [1000.0]
    store = FakeRedis(clock=lambda: clock[0])
    store.zsets["someone-elses-key"] = [(1.0, "m")]
    rep = L.run_limiter_checks(store, clock=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s))
    assert rep.passed, rep.to_dict()
    assert store.keys() == ["someone-elses-key"]


def test_limiter_checks_report_a_dead_store_as_failed():
    store = FakeRedis()
    store.fail = ConnectionError("down")
    rep = L.run_limiter_checks(store, sleep=lambda s: None)
    assert not rep.passed and rep.checks["store_not_degraded"]["state"] == L.FAIL


# ---- the operator script ----------------------------------------------------------------------------------------------------
def _run_script(*args, env=None):
    import os

    base = {k: v for k, v in os.environ.items() if k not in ("LIVE_VERIFY_AUTHORISED", "BREVO_API_KEY", "BREVO_WEBHOOK_SECRET", "REDIS_URL", "GOOGLE_CLIENT_SECRET")}
    base.update({"API_ENV": "development", "PYTHONDONTWRITEBYTECODE": "1", **(env or {})})
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, env=base, timeout=120)


@pytest.mark.parametrize("args", [
    ["oidc-finish", "--state-file", "/nonexistent", "--callback-url", "https://x/cb?code=a&state=b"],
    ["email-send", "--recipient", "owner@example.com"],
    ["webhook-probe", "--url", "https://staging.example.test/api/v1/mail/webhooks/brevo"],
    ["redis-check"],
])
def test_live_subcommands_are_dry_run_by_default_and_send_nothing(args):
    r = _run_script(*args)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["mode"] == "dry_run" and out["sent"] is False and "owner@example.com" not in r.stdout


@pytest.mark.parametrize("env", [{}, {"API_ENV": "production", "LIVE_VERIFY_AUTHORISED": L.AUTHORISATION_VALUE}, {"API_ENV": "staging"}])
def test_the_flag_alone_or_a_wrong_environment_still_refuses(env):
    r = _run_script("email-send", "--recipient", "owner@example.com", "--authorise-live", env=env)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["mode"] == "dry_run" and out["sent"] is False


def test_oidc_config_fails_closed_with_nothing_configured_and_prints_no_secret():
    r = _run_script("oidc-config", env={"GOOGLE_CLIENT_SECRET": "SECRET-SENTINEL-123"})
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["checks"]["google_sign_in_enabled"]["state"] == L.FAIL and "SECRET-SENTINEL-123" not in r.stdout + r.stderr


def test_oidc_start_refuses_when_google_is_disabled_and_writes_nothing(tmp_path):
    r = _run_script("oidc-start", "--state-file", str(tmp_path / "s"), "--url-file", str(tmp_path / "u"))
    assert r.returncode == 1 and not (tmp_path / "s").exists() and not (tmp_path / "u").exists()


def test_oidc_start_writes_private_single_use_files_and_never_prints_the_verifier(tmp_path):
    env = {"FEATURE_GOOGLE_LOGIN": "true", "GOOGLE_CLIENT_ID": "id-123.apps.example", "GOOGLE_CLIENT_SECRET": "SECRET-SENTINEL-456",
           "OIDC_REDIRECT_URI": "https://api.example.test/api/v1/auth/oidc/google/callback"}
    r = _run_script("oidc-start", "--state-file", str(tmp_path / "s"), "--url-file", str(tmp_path / "u"), env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    saved = json.loads((tmp_path / "s").read_text())
    assert (tmp_path / "s").stat().st_mode & 0o077 == 0 and (tmp_path / "u").stat().st_mode & 0o077 == 0
    assert saved["verifier"] not in r.stdout and "SECRET-SENTINEL-456" not in r.stdout + r.stderr and json.loads(r.stdout)["overall"] == L.PASS


def test_the_script_never_contacts_a_network_in_dry_run(monkeypatch):
    # In-process: patching sockets proves the dry-run path opens none.
    import importlib.util

    spec = importlib.util.spec_from_file_location("verify05d", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.delenv("LIVE_VERIFY_AUTHORISED", raising=False)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("socket opened")))
    for argv in (["email-send", "--recipient", "a@b.example"], ["redis-check", "--authorise-live"], ["webhook-probe", "--url", "https://x.example/h"]):
        assert mod.main(argv) == 0


def test_the_script_and_harness_hold_no_secret_literal_and_no_production_target():
    text = SCRIPT.read_text() + (ROOT / "src" / "application" / "identity_live_check.py").read_text()
    assert "api.brevo.com" not in text and "sk_live" not in text and "password" not in text.lower().replace("passwords", "")
    assert 'AUTHORISATION_VALUE = "I-AUTHORISE-STAGING-LIVE-CHECKS"' in text
