"""04E (REQ-BETA-01): server-enforced invitation-only registration. Offline, real SQLite, no provider, no email."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from sqlalchemy import select

from src.api import rate_limit as RL
from src.api.dependencies import DEV_ENVS
from src.application import admin_permissions as perm
from src.authsec import passwords
from src.invitations import policy
from src.invitations import repository as R
from src.persistence import RegistrationInvitation, User, utcnow
from tests._invitations_04e import API, PW, REFUSAL, Env, full_database_text, refusal_body


@pytest.fixture()
def env():
    e = Env("staging")
    yield e
    e.close()


# ===================================================================== policy: when is an invitation required
@pytest.mark.parametrize("name", ["staging", "production", "prod", "staging2", "Production", "preview", "qa", "typo-env", "live", "anything-else"])
def test_hosted_and_unknown_environments_always_require_an_invitation(name):
    assert policy.invitation_required(name) is True
    for override in ("false", "0", "no", "off", "", "true"):
        assert policy.invitation_required(name, override=override) is True       # NOT overridable: hosted fails closed


def test_hosted_requirement_ignores_the_process_environment_override(monkeypatch):
    monkeypatch.setenv(policy.OVERRIDE_ENV_VAR, "false")
    assert policy.invitation_required("production") is True
    monkeypatch.setenv(policy.OVERRIDE_ENV_VAR, "0")
    assert policy.invitation_required("staging") is True


@pytest.mark.parametrize("name", ["development", "dev", "test", "testing", "local", " Development "])
def test_local_environments_default_off_and_can_be_turned_on(name, monkeypatch):
    monkeypatch.delenv(policy.OVERRIDE_ENV_VAR, raising=False)
    assert policy.invitation_required(name) is False
    for on in ("1", "true", "TRUE", "yes", "on"):
        assert policy.invitation_required(name, override=on) is True
    for off in ("", "false", "0", "maybe"):
        assert policy.invitation_required(name, override=off) is False
    monkeypatch.setenv(policy.OVERRIDE_ENV_VAR, "true")
    assert policy.invitation_required(name) is True


def test_unset_environment_label_is_the_documented_local_default(monkeypatch):
    monkeypatch.delenv(policy.OVERRIDE_ENV_VAR, raising=False)
    assert policy.invitation_required(None) is False and policy.invitation_required("") is False   # ApiSettings.from_env treats a missing API_ENV as development


def test_local_environment_list_equals_the_api_dev_environments():
    assert tuple(policy.LOCAL_ENVIRONMENTS) == tuple(DEV_ENVS)


def test_app_created_for_a_hosted_environment_requires_one_without_any_flag(monkeypatch):
    monkeypatch.delenv(policy.OVERRIDE_ENV_VAR, raising=False)
    for name in ("staging", "production", "totally-unknown"):
        e = Env(name)
        try:
            r = e.register("someone@example.com", None)
            assert r.status_code == 403 and refusal_body(r) == REFUSAL
            assert e.set_user_count("someone@example.com") == 0
        finally:
            e.close()


# ===================================================================== primitives
def test_codes_are_high_entropy_unique_and_hash_is_the_only_stored_form():
    codes = {R.new_code() for _ in range(200)}
    assert len(codes) == 200 and all(len(c) >= 43 for c in codes)
    c = R.new_code()
    assert R.hash_code(c) != c and len(R.hash_code(c)) == 64 and R.hash_code(c) == R.hash_code(f"  {c}  ")


def test_mask_email_never_reveals_the_address():
    assert R.mask_email("Jane.Doe@Example.co.uk") == "j***@e***.uk"
    assert "jane" not in R.mask_email("jane@example.com").lower()
    assert R.mask_email("nonsense") == "***"
    assert R.hash_email("A@B.com") == R.hash_email(" a@b.com ") != R.hash_email("a@c.com")


# ===================================================================== registration gate (password path)
def test_valid_invitation_registers_once_and_marks_it_redeemed(env):
    code, view = env.issue()
    r = env.register("alice@example.com", code)
    assert r.status_code == 201
    uid = env.accounts.find_by_email("alice@example.com").user_id
    row = env.row(view.id)
    assert row.redeemed_at is not None and row.redeemed_by_user_id == uid
    # replay: the same code can never create a second account
    r2 = env.register("bob@example.com", code)
    assert r2.status_code == 403 and refusal_body(r2) == REFUSAL
    assert env.set_user_count("bob@example.com") == 0


def test_uninvited_registration_is_refused_server_side_and_creates_nothing(env):
    for body in (None, "", "   ", "not-a-real-code", "x" * 100):
        r = env.register("eve@example.com", body)
        assert r.status_code == 403 and refusal_body(r) == REFUSAL
    assert env.set_user_count("eve@example.com") == 0
    assert not env.mail.sent                                                  # nothing was emailed either


def test_every_unusable_state_gets_the_identical_refusal_and_no_account(env):
    # expired
    c_exp, v_exp = env.issue()
    env.expire(v_exp.id)
    # revoked
    c_rev, v_rev = env.issue()
    env.invites.revoke(v_rev.id, actor_user_id=None)
    # used
    c_used, _ = env.issue()
    assert env.register("first@example.com", c_used).status_code == 201
    # email-bound to someone else
    c_bound, _ = env.issue(email="owner@example.com")
    cases = {"unknown": R.new_code(), "expired": c_exp, "revoked": c_rev, "used": c_used, "bound": c_bound, "missing": None}
    bodies = set()
    for name, code in cases.items():
        r = env.register("intruder@example.com", code)
        assert r.status_code == 403, name
        bodies.add(str(refusal_body(r)))
    assert len(bodies) == 1, "the responses must be indistinguishable"
    assert env.set_user_count("intruder@example.com") == 0


def test_refusal_does_not_depend_on_whether_the_email_exists(env):
    env.make_user(email="taken@example.com")
    existing = env.register("taken@example.com", "wrong-code")
    fresh = env.register("never-seen@example.com", "wrong-code")
    assert existing.status_code == fresh.status_code == 403
    assert refusal_body(existing) == refusal_body(fresh) == REFUSAL
    # and with NO code at all
    assert refusal_body(env.register("taken@example.com", None)) == refusal_body(env.register("never-seen@example.com", None))


def test_valid_code_with_an_existing_email_is_uniform_and_does_not_burn_the_code(env):
    env.make_user(email="taken@example.com")
    code, view = env.issue()
    ok_existing = env.register("taken@example.com", code)
    assert ok_existing.status_code == 201                                      # the same uniform success a new address gets
    assert env.row(view.id).redeemed_at is None                                # nothing consumed: no account was created
    assert env.set_user_count("taken@example.com") == 1                        # no duplicate
    assert env.register("fresh@example.com", code).status_code == 201          # the code still works for a real new address
    assert env.row(view.id).redeemed_at is not None


def test_expired_invitation_is_refused(env):
    code, view = env.issue()
    env.expire(view.id)
    assert env.register("late@example.com", code).status_code == 403
    assert env.row(view.id).redeemed_at is None


def test_revoked_invitation_is_refused_even_if_unexpired(env):
    code, view = env.issue()
    env.invites.revoke(view.id, actor_user_id=None)
    assert env.register("x@example.com", code).status_code == 403


def test_email_bound_invitation_only_works_for_that_address_case_insensitively(env):
    code, view = env.issue(email="Owner@Example.com")
    assert env.register("someone-else@example.com", code).status_code == 403
    assert env.row(view.id).redeemed_at is None                                # a wrong-address attempt does not consume it
    assert env.register("OWNER@example.COM", code).status_code == 201
    assert env.row(view.id).redeemed_at is not None


def test_a_refused_attempt_with_a_valid_code_for_another_email_leaves_it_usable(env):
    code, view = env.issue(email="a@example.com")
    for _ in range(3):
        assert env.register("b@example.com", code).status_code == 403
    assert env.register("a@example.com", code).status_code == 201


def test_invitation_code_in_the_request_is_bounded(env):
    r = env.register("big@example.com", "x" * 500)
    assert r.status_code == 422
    assert "x" * 50 not in r.text                                              # validation errors never echo the submitted value


def test_existing_users_and_sign_in_are_unaffected_when_the_requirement_is_on(env):
    uid, ck = env.make_user(email="old@example.com")
    me = env.c.get(f"{API}/auth/me", cookies=ck)
    assert me.status_code == 200 and me.json()["email"] == "old@example.com"
    bad = env.c.post(f"{API}/auth/login", json={"email": "old@example.com", "password": "wrong-wrong-wrong"})
    assert bad.status_code == 401 and bad.json()["error"]["message"] == "Incorrect email or password."
    assert env.c.post(f"{API}/auth/forgot-password", json={"email": "old@example.com"}).status_code == 200   # recovery still works


def test_registration_still_pauseable_and_still_sends_verification_after_a_valid_invitation(env):
    code, _ = env.issue()
    assert env.register("mail@example.com", code, locale="de").status_code == 201
    assert any(m.category == "email_verification" for m in env.mail.sent)       # the verified-email flow is unchanged


# ===================================================================== local default and the explicit flag
def test_local_environment_registers_without_a_code_by_default(monkeypatch):
    monkeypatch.delenv(policy.OVERRIDE_ENV_VAR, raising=False)
    e = Env("test")
    try:
        assert e.register("dev@example.com", None).status_code == 201
        assert e.register("dev2@example.com", "garbage-ignored").status_code == 201     # a code is ignored (and nothing is consumed) when not required
    finally:
        e.close()


def test_local_environment_enforces_the_gate_when_the_flag_is_on(monkeypatch):
    monkeypatch.setenv(policy.OVERRIDE_ENV_VAR, "true")
    e = Env("test")
    try:
        assert e.register("nope@example.com", None).status_code == 403
        code, _ = e.issue()
        assert e.register("yes@example.com", code).status_code == 201
    finally:
        e.close()


# ===================================================================== hash at rest, audit, logs
def test_plaintext_code_and_email_are_nowhere_at_rest_or_in_the_audit_trail(env):
    code, view = env.issue(email="secret.person@example.com")
    env.register("secret.person@example.com", code)
    env.register("other@example.com", code)                                    # a refusal (used)
    env.register("other@example.com", R.new_code())                            # a refusal (unknown)
    blob = env.audit_blob()
    db = full_database_text(env)
    for needle in (code, R.hash_code(code), "secret.person@example.com", "Secret.Person"):
        assert needle not in blob, f"{needle[:8]} leaked into an audit context"
    assert code not in db, "the plaintext code must not exist in the database"
    row = env.row(view.id)
    assert row.code_hash == R.hash_code(code) and row.code_hash != code
    assert "secret.person@example.com" not in " ".join(str(getattr(row, c.name)) for c in row.__table__.columns), "the invitation row holds no address"
    assert row.email_hint == "s***@e***.com" and row.email_hash == R.hash_email("secret.person@example.com")


def test_audit_records_issue_redeem_and_refusal_with_metadata_only(env):
    code, _ = env.issue()
    env.register("ok@example.com", code)
    env.register("bad@example.com", "nope")
    types = [e.event_type for e in env.audit_rows()]
    assert "account.invitation_redeemed" in types
    refused = [e for e in env.audit_rows() if e.event_type == "account.invitation_refused"]
    assert refused and refused[-1].result == "refused"
    assert refused[-1].context == {"reason": "invalid", "channel": "password"}
    reasons = {e.context["reason"] for e in refused}
    assert reasons <= set(R.REFUSAL_REASONS)


def test_each_refusal_reason_is_audited_precisely_but_never_shown_to_the_requester(env):
    c_used, _ = env.issue()
    env.register("a@example.com", c_used)
    c_exp, v_exp = env.issue()
    env.expire(v_exp.id)
    c_rev, v_rev = env.issue()
    env.invites.revoke(v_rev.id, actor_user_id=None)
    c_bound, _ = env.issue(email="who@example.com")
    for code in (None, "junk", c_used, c_exp, c_rev, c_bound):
        env.register("zz@example.com", code)
    reasons = [e.context["reason"] for e in env.audit_rows() if e.event_type == "account.invitation_refused"]
    assert reasons == ["missing", "invalid", "used", "expired", "revoked", "email_mismatch"]


def test_no_log_line_contains_the_code(env, caplog):
    caplog.set_level(logging.DEBUG)
    code, _ = env.issue()
    env.register("loggy@example.com", code)
    env.register("loggy2@example.com", code)
    assert code not in caplog.text and R.hash_code(code) not in caplog.text


# ===================================================================== atomic, race-safe redemption
def test_concurrent_redemption_yields_exactly_one_success_at_the_repository(env):
    code, view = env.issue()
    n = 8
    barrier = threading.Barrier(n)
    results: list[object] = []

    def attempt(i: int):
        barrier.wait()
        try:
            return env.accounts.create_password_account(
                email=f"racer{i}@example.com", password_hash=passwords.hash_password(PW), display_name=None, require_invitation=True, invitation_code=code)
        except R.InvitationRefused as exc:
            return exc

    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(attempt, range(n)))
    wins = [r for r in results if isinstance(r, int)]
    losses = [r for r in results if isinstance(r, R.InvitationRefused)]
    assert len(wins) == 1 and len(losses) == n - 1, results
    with env.sf() as s:
        racers = s.scalars(select(User).where(User.email.like("racer%@example.com"))).all()
    assert len(racers) == 1 and racers[0].id == wins[0], "every losing attempt must roll its account back"
    assert env.row(view.id).redeemed_by_user_id == wins[0]


def test_concurrent_registration_over_http_yields_exactly_one_account(env, monkeypatch):
    monkeypatch.setitem(RL.POLICIES, "auth_register_ip", replace(RL.POLICIES["auth_register_ip"], limit=1000))
    monkeypatch.setitem(RL.POLICIES, "auth_invitation_ip", replace(RL.POLICIES["auth_invitation_ip"], limit=1000))
    code, _ = env.issue()
    n = 6
    barrier = threading.Barrier(n)

    def go(i: int) -> int:
        barrier.wait()
        return env.register(f"web{i}@example.com", code).status_code

    with ThreadPoolExecutor(max_workers=n) as pool:
        statuses = list(pool.map(go, range(n)))
    assert statuses.count(201) == 1 and statuses.count(403) == n - 1, statuses
    with env.sf() as s:
        assert len(s.scalars(select(User).where(User.email.like("web%@example.com"))).all()) == 1


def test_revoke_and_redeem_race_has_one_winner(env):
    code, view = env.issue()
    barrier = threading.Barrier(2)
    out: dict[str, object] = {}

    def redeem():
        barrier.wait()
        try:
            out["redeem"] = env.accounts.create_password_account(email="rr@example.com", password_hash="h", display_name=None, require_invitation=True, invitation_code=code)
        except R.InvitationRefused as exc:
            out["redeem"] = exc

    def revoke():
        barrier.wait()
        try:
            out["revoke"] = env.invites.revoke(view.id, actor_user_id=None)
        except R.InvitationConflict as exc:
            out["revoke"] = exc

    ts = [threading.Thread(target=redeem), threading.Thread(target=revoke)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    redeemed = isinstance(out["redeem"], int)
    revoked = not isinstance(out["revoke"], Exception)
    assert redeemed != revoked, out                                           # exactly one of the two succeeded
    row = env.row(view.id)
    assert (row.redeemed_at is not None) != (row.revoked_at is not None)


# ===================================================================== rate limiting
def test_registration_attempts_are_rate_limited_per_ip_even_with_a_valid_code(env):
    codes = [env.issue()[0] for _ in range(14)]
    statuses = [env.register(f"u{i}@example.com", codes[i]).status_code for i in range(14)]
    assert 429 in statuses, statuses                                           # the existing per-IP register bucket (8 / hour) and the invitation bucket bound attempts
    first_429 = statuses.index(429)
    assert all(s == 429 for s in statuses[first_429:]), "once exhausted, even a valid code is not honoured"


def test_the_dedicated_invitation_bucket_bounds_attempts_on_its_own(env, monkeypatch):
    monkeypatch.setitem(RL.POLICIES, "auth_register_ip", replace(RL.POLICIES["auth_register_ip"], limit=1000))
    statuses = [env.register(f"g{i}@example.com", "guess").status_code for i in range(12)]
    assert statuses[:10] == [403] * 10 and statuses[10:] == [429, 429]
    r = env.register("g99@example.com", "guess")
    assert r.status_code == 429


def test_the_invitation_buckets_are_declared_with_a_bounded_policy():
    assert RL.POLICIES["auth_invitation_ip"].limit <= 20 and RL.POLICIES["auth_invitation_ip"].scope == "ip"
    assert RL.POLICIES["auth_invitation_global"].scope == "global"
    assert RL.POLICIES["invitation_issue_user"].scope == "user"


def test_local_registration_without_the_requirement_does_not_spend_the_invitation_bucket(monkeypatch):
    monkeypatch.delenv(policy.OVERRIDE_ENV_VAR, raising=False)
    e = Env("test")
    try:
        monkeypatch.setitem(RL.POLICIES, "auth_register_ip", replace(RL.POLICIES["auth_register_ip"], limit=1000))
        assert [e.register(f"l{i}@example.com", None).status_code for i in range(12)] == [201] * 12
    finally:
        e.close()


# ===================================================================== Admin surface
def _admin(env: Env):
    return env.make_user("platform_admin", email="owner@example.com")


def test_admin_issues_lists_and_revokes_with_the_code_shown_once(env):
    aid, ck = _admin(env)
    r = env.c.post(f"{API}/admin/invitations", json={"expires_in_days": 7}, cookies=ck)
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store"
    body = r.json()
    code = body["code"]
    assert len(code) >= 43 and body["link"].endswith(f"/register#invitation={code}") and "?" not in body["link"].split("#")[0]
    assert body["state"] == "pending" and body["issued_by_user_id"] == aid and body["email_bound"] is False
    # listing never carries the code, the hash, an address, or the redeeming account
    env.register("redeemer@example.com", code)
    listing = env.c.get(f"{API}/admin/invitations", cookies=ck)
    assert listing.status_code == 200
    text = listing.text
    assert code not in text and R.hash_code(code) not in text and "redeemer@example.com" not in text and "code_hash" not in text and "email_hash" not in text
    item = listing.json()["items"][0]
    assert item["state"] == "redeemed" and item["redeemed_at"] and "redeemed_by_user_id" not in item
    assert listing.json()["counts"]["redeemed"] == 1 and listing.json()["total"] == 1
    # the plaintext is stored nowhere
    assert code not in full_database_text(env)


def test_admin_issue_with_email_binding_shows_only_a_masked_hint(env):
    _, ck = _admin(env)
    r = env.c.post(f"{API}/admin/invitations", json={"email": "Candidate.Name@Example.com"}, cookies=ck)
    assert r.status_code == 201
    assert r.json()["email_bound"] is True and r.json()["email_hint"] == "c***@e***.com"
    assert "candidate" not in r.text.lower().replace(r.json()["code"].lower(), "")
    assert "candidate.name" not in env.c.get(f"{API}/admin/invitations", cookies=ck).text.lower()
    assert env.register("candidate.name@example.com", r.json()["code"]).status_code == 201


def test_admin_issue_validates_input(env):
    _, ck = _admin(env)
    assert env.c.post(f"{API}/admin/invitations", json={"expires_in_days": 0}, cookies=ck).status_code == 422
    assert env.c.post(f"{API}/admin/invitations", json={"expires_in_days": policy.MAX_TTL_DAYS + 1}, cookies=ck).status_code == 422
    assert env.c.post(f"{API}/admin/invitations", json={"email": "not-an-email"}, cookies=ck).status_code == 422
    assert env.c.post(f"{API}/admin/invitations", json={"code": "mine"}, cookies=ck).status_code == 422     # an operator cannot choose the code
    assert env.c.get(f"{API}/admin/invitations", params={"state": "bogus"}, cookies=ck).status_code == 422


def test_admin_revoke_is_idempotent_blocks_redeemed_and_404s_unknown(env):
    _, ck = _admin(env)
    issued = env.c.post(f"{API}/admin/invitations", json={}, cookies=ck).json()
    r1 = env.c.post(f"{API}/admin/invitations/{issued['id']}/revoke", cookies=ck)
    assert r1.status_code == 200 and r1.json()["state"] == "revoked"
    r2 = env.c.post(f"{API}/admin/invitations/{issued['id']}/revoke", cookies=ck)
    assert r2.status_code == 200 and r2.json()["state"] == "revoked"
    assert env.register("x@example.com", issued["code"]).status_code == 403
    used = env.c.post(f"{API}/admin/invitations", json={}, cookies=ck).json()
    env.register("y@example.com", used["code"])
    assert env.c.post(f"{API}/admin/invitations/{used['id']}/revoke", cookies=ck).status_code == 409
    assert env.c.post(f"{API}/admin/invitations/999999/revoke", cookies=ck).status_code == 404


def test_admin_list_filters_by_state(env):
    _, ck = _admin(env)
    c_pending, _ = env.issue()
    c_rev, v_rev = env.issue()
    env.invites.revoke(v_rev.id, actor_user_id=None)
    _, v_exp = env.issue()
    env.expire(v_exp.id)
    for state, n in (("pending", 1), ("revoked", 1), ("expired", 1), ("redeemed", 0)):
        got = env.c.get(f"{API}/admin/invitations", params={"state": state}, cookies=ck).json()
        assert got["total"] == n and all(i["state"] == state for i in got["items"]), state


def test_admin_audit_is_metadata_only(env):
    aid, ck = _admin(env)
    issued = env.c.post(f"{API}/admin/invitations", json={"email": "meta@example.com", "expires_in_days": 3}, cookies=ck).json()
    env.c.post(f"{API}/admin/invitations/{issued['id']}/revoke", cookies=ck)
    rows = {e.event_type: e for e in env.audit_rows() if e.event_type.startswith("admin.invitation_")}
    assert set(rows) == {"admin.invitation_issued", "admin.invitation_revoked"}
    assert rows["admin.invitation_issued"].actor_user_id == aid and rows["admin.invitation_issued"].target_type == "invitation"
    assert rows["admin.invitation_issued"].context["ttl_days"] == 3 and rows["admin.invitation_issued"].context["email_bound"] is True
    blob = env.audit_blob()
    assert issued["code"] not in blob and "meta@example.com" not in blob and R.hash_code(issued["code"]) not in blob


def test_admin_issue_is_rate_limited_per_admin(env):
    _, ck = _admin(env)
    codes = [env.c.post(f"{API}/admin/invitations", json={}, cookies=ck).status_code for _ in range(RL.POLICIES["invitation_issue_user"].limit + 2)]
    assert codes[: RL.POLICIES["invitation_issue_user"].limit] == [201] * RL.POLICIES["invitation_issue_user"].limit
    assert codes[-1] == 429


def test_outstanding_pending_invitations_are_bounded(env, monkeypatch):
    monkeypatch.setattr(policy, "MAX_OUTSTANDING_PENDING", 2)
    _, ck = _admin(env)
    assert [env.c.post(f"{API}/admin/invitations", json={}, cookies=ck).status_code for _ in range(3)] == [201, 201, 409]


def test_admin_authorization_matrix_403_for_everyone_without_the_permission(env):
    personas = ("user", "platform_admin", "support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin")
    cookies = {p: env.make_user(p, email=f"{p}@example.com")[1] for p in personas}
    _, v = env.issue()
    routes = [("GET", f"{API}/admin/invitations", perm.USERS_READ), ("POST", f"{API}/admin/invitations", perm.USERS_MANAGE),
              ("POST", f"{API}/admin/invitations/{v.id}/revoke", perm.USERS_MANAGE)]
    for method, url, needed in routes:
        assert env.c.request(method, url, json={} if method == "POST" and url.endswith("invitations") else None).status_code == 401, (method, url)
        for persona in personas:
            allowed = needed in perm.permissions_for_role(persona)
            r = env.c.request(method, url, json={"expires_in_days": 1} if url.endswith("invitations") and method == "POST" else None, cookies=cookies[persona])
            if allowed:
                assert r.status_code in (200, 201), (method, url, persona, r.status_code)
            else:
                assert r.status_code == 403, (method, url, persona, r.status_code)
    # a denied caller learns nothing: no code, no list
    denied = env.c.get(f"{API}/admin/invitations", cookies=cookies["user"])
    assert denied.status_code == 403 and "items" not in denied.text


def test_existing_permissions_were_reused_and_the_registry_is_unchanged():
    assert len(perm.PERMISSIONS) == 44
    from src.api.admin_route_invariant import admin_routes

    mine = {(m, r.path): tuple(sorted(r.permissions)) for r in admin_routes() if r.path.startswith("/admin/invitations") for m in r.methods}
    assert mine == {("GET", "/admin/invitations"): (perm.USERS_READ,), ("POST", "/admin/invitations"): (perm.USERS_MANAGE,),
                    ("POST", "/admin/invitations/{invitation_id}/revoke"): (perm.USERS_MANAGE,)}


def test_candidate_cannot_reach_invitations_and_an_invited_candidate_is_a_plain_user(env):
    code, _ = env.issue()
    env.register("cand@example.com", code)
    assert env.accounts.find_by_email("cand@example.com").platform_role == "user"
    assert env.accounts.find_by_email("cand@example.com").tier == "basic"


# ===================================================================== account deletion, privacy export
def test_deleting_the_redeemer_anonymises_the_linkage_but_the_code_stays_burned(env):
    code, view = env.issue(email="leaver@example.com")
    env.register("leaver@example.com", code)
    uid = env.accounts.find_by_email("leaver@example.com").user_id
    assert env.row(view.id).redeemed_by_user_id == uid
    from src.application.account_deletion_service import AccountDeletionService

    summary = AccountDeletionService(env.sf).delete_account(uid)
    assert summary.existed and summary.invitations_anonymized >= 1
    row = env.row(view.id)
    assert row.redeemed_by_user_id is None and row.email_hash is None and row.email_hint is None
    assert row.redeemed_at is not None and row.code_hash == R.hash_code(code)       # still consumed: replay stays impossible
    assert env.register("leaver@example.com", code).status_code == 403
    assert env.register("someone-new@example.com", code).status_code == 403
    assert env.set_user_count("leaver@example.com") == 0
    assert AccountDeletionService(env.sf).delete_account(uid).existed is False        # idempotent


def test_deleting_an_issuing_admin_keeps_pending_invitations_valid_and_anonymous(env):
    aid, _ = _admin(env)
    code, view = env.issue(issued_by=aid)
    from src.application.account_deletion_service import AccountDeletionService

    AccountDeletionService(env.sf).delete_account(aid)
    assert env.row(view.id).issued_by_user_id is None
    assert env.register("after@example.com", code).status_code == 201


def test_self_service_account_deletion_through_the_api_still_works_for_an_invited_user(env):
    code, view = env.issue()
    env.register("selfdel@example.com", code)
    env.accounts.mark_email_verified(env.accounts.find_by_email("selfdel@example.com").user_id)
    from tests._auth_factories import cookies_for, login_token

    ck = cookies_for(login_token(env.c, "selfdel@example.com", PW))
    r = env.c.post(f"{API}/auth/account/delete", cookies=ck)
    assert r.status_code == 200, r.text
    assert env.row(view.id).redeemed_by_user_id is None and env.set_user_count("selfdel@example.com") == 0


def test_privacy_export_contains_only_the_redemption_time_never_the_code_or_hash(env):
    code, view = env.issue(email="exp@example.com")
    env.register("exp@example.com", code)
    from tests._auth_factories import cookies_for, login_token

    env.accounts.mark_email_verified(env.accounts.find_by_email("exp@example.com").user_id)
    ck = cookies_for(login_token(env.c, "exp@example.com", PW))
    r = env.c.get(f"{API}/auth/account/export", cookies=ck)
    assert r.status_code == 200
    data = r.json()
    assert data["registration_invitation"]["redeemed_at"] and set(data["registration_invitation"]) == {"redeemed_at"}
    assert code not in r.text and R.hash_code(code) not in r.text and "email_hash" not in r.text and "code_hash" not in r.text
    assert any("invitation" in s for s in data["scope"]["included"])
    # an uninvited (pre-beta) account exports null
    _, ck2 = env.make_user(email="old@example.com")
    assert env.c.get(f"{API}/auth/account/export", cookies=ck2).json()["registration_invitation"] is None


def test_the_export_never_dumps_the_invitation_table_generically():
    import inspect

    from src.application import data_export

    assert "RegistrationInvitation" not in inspect.getsource(data_export)          # the section is built by hand (timestamp only), so no hash column can leak


# ===================================================================== state derivation
def test_state_is_derived_from_timestamps(env):
    _, v = env.issue()
    assert v.state == "pending"
    with env.sf() as s:
        row = s.get(RegistrationInvitation, v.id)
        assert R.derive_state(row) == "pending"
        row.revoked_at = utcnow()
        assert R.derive_state(row) == "revoked"
        row.revoked_at = None
        row.redeemed_at = utcnow()
        assert R.derive_state(row) == "redeemed"
        row.redeemed_at = None
        row.expires_at = utcnow() - timedelta_(1)
        assert R.derive_state(row) == "expired"
        s.rollback()


def timedelta_(days):
    from datetime import timedelta

    return timedelta(days=days)


def test_a_redeemed_row_cannot_be_redeemed_again_by_the_conditional_update(env):
    code, view = env.issue()
    with env.sf() as s:
        uid = s.scalar(select(User.id)) or env.make_user(email="seed@example.com")[0]
    with env.sf() as s:
        R.consume(s, code=code, email=None, user_id=uid)
        s.commit()
    with env.sf() as s:
        with pytest.raises(R.InvitationRefused) as exc:
            R.consume(s, code=code, email=None, user_id=uid)
        assert exc.value.reason == R.REASON_USED
