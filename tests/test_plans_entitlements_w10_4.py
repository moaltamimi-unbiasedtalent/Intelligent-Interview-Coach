"""P10B-W10.4: plans, subscriptions and entitlements. Real isolated SQLite; no billing, no provider."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select, text

from src import entitlements as E
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import PlanEntitlement, PlanVersion, Subscription
from tests._auth_factories import cookies_for, login_token, register
from tests.test_admin_foundation_w10_1 import PW, Env

API = "/api/v1"


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def mk(env, role="user"):
    env.n += 1
    email = f"p{env.n}@x.com"
    register(env.c, email, PW)
    tok = login_token(env.c, email, PW)
    uid = env.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["user_id"]
    if role != "user":
        env.accounts.set_platform_role(uid, role)
    return uid, cookies_for(tok)


def svc(env, registry=None):
    return E.EntitlementService(env.repo.session_factory, registry)


def assign(env, ck, uid, plan):
    return env.c.post(f"{API}/admin/users/{uid}/plan", json={"plan_code": plan}, cookies=ck)


def versions(env, ck):
    return {(v["plan_code"], v["version"]): v for v in env.c.get(f"{API}/admin/plans", cookies=ck).json()["items"]}


def make_active_v2(env, adm, code, patch=None):
    """draft v2 -> (optional edit) -> activate; returns the new version id."""
    vid = env.c.post(f"{API}/admin/plans/{code}/versions", cookies=adm).json()["id"]
    if patch:
        assert env.c.patch(f"{API}/admin/plans/versions/{vid}/entitlements", json={"entitlements": patch}, cookies=adm).status_code == 200
    assert env.c.post(f"{API}/admin/plans/versions/{vid}/activate", cookies=adm).status_code == 200
    return vid


# ---------------- registry and value rules --------------------------------------------------------------------

def test_registry_is_code_defined_and_matches_the_pre_w10_4_access_gates():
    assert set(E.REGISTRY) == {"current_market_research", "standard_history", "standard_progress",
                               "standard_model_profiles", "premium_preview"}
    assert all(d.type is E.EntitlementType.BOOLEAN for d in E.REGISTRY.values())   # no quota was invented
    assert E.PLAN_CODES == ("basic", "premium") and E.DEFAULT_PLAN_CODE == "basic"
    from src.application.authorization import BASIC_CAPABILITIES, PREMIUM_CAPABILITIES
    assert E.BASIC_KEYS == BASIC_CAPABILITIES and E.DEFAULT_PLANS["premium"]["enabled"] == PREMIUM_CAPABILITIES


LIMIT_REG = {**E.REGISTRY, "documents_max": E.EntitlementDef("documents_max", E.EntitlementType.LIMIT, "Docs", "test only")}


def test_value_validation_distinguishes_disabled_unlimited_and_limited():
    v = E.validate_value
    assert v("standard_history", True, None) == (True, None)             # enabled
    assert v("standard_history", False, None) == (False, None)           # disabled
    assert v("documents_max", True, None, LIMIT_REG) == (True, None)     # enabled, unlimited
    assert v("documents_max", True, 5, LIMIT_REG) == (True, 5)           # limited
    for bad in (("nope", True, None), ("standard_history", "yes", None), ("standard_history", True, 3),
                ("documents_max", True, 0), ("documents_max", True, -1), ("documents_max", True, 2.5),
                ("documents_max", True, True), ("documents_max", False, 5)):
        with pytest.raises(E.EntitlementError):
            v(*bad, registry=LIMIT_REG)


# ---------------- seeds, default subscription, backfill semantics ----------------------------------------------

def test_seed_is_idempotent_and_new_accounts_get_the_default_basic_subscription(env):
    uid, _ = mk(env)
    with env.repo.session_factory() as s:
        E.seed_default_plans(s)
        E.seed_default_plans(s)
        s.commit()
        assert s.scalar(select(text("count(*)")).select_from(PlanVersion)) == 2
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid))
        pv = s.get(PlanVersion, sub.plan_version_id)
        assert (pv.plan_code, sub.status, sub.source) == ("basic", "active", "system_default")
    assert svc(env).enabled_keys(uid) == sorted(E.BASIC_KEYS)


def test_dev_and_legacy_principals_also_get_the_default_subscription_once(env):
    uid = env.repo.get_or_create_user(subject="dev-sub", provider="dev")
    again = env.repo.get_or_create_user(subject="dev-sub", provider="dev")
    assert uid == again
    with env.repo.session_factory() as s:
        rows = s.scalars(select(Subscription).where(Subscription.user_id == uid)).all()
        assert [(r.status, r.source) for r in rows] == [("active", "system_default")]


def test_account_creation_fails_closed_without_a_half_created_account(env, monkeypatch):
    from src import auth_repository as ar
    monkeypatch.setattr(ar, "ensure_default_subscription", lambda *a, **k: (_ for _ in ()).throw(E.DefaultPlanUnavailable("x")))
    r = register(env.c, "half@x.com", PW)
    assert r.status_code in (500, 503)
    monkeypatch.undo()
    assert env.accounts.find_by_email("half@x.com") is None          # no account without a plan state


# ---------------- resolver -------------------------------------------------------------------------------------

def test_basic_and_premium_resolve_to_their_own_entitlements(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    basic = svc(env).resolve_all(uid)
    assert {k for k, r in basic.items() if r.enabled} == E.BASIC_KEYS
    assert basic["premium_preview"].enabled is False and basic["premium_preview"].plan_version == 1
    assert assign(env, adm, uid, "premium").status_code == 200
    prem = svc(env).resolve_all(uid)
    assert all(r.enabled for r in prem.values()) and prem["premium_preview"].plan_code == "premium"
    assert prem["standard_history"].source == "subscription"


def test_no_subscription_falls_back_to_basic_never_premium_and_tier_is_not_authoritative(env):
    uid, _ = mk(env)
    with env.repo.session_factory() as s:
        s.execute(text("UPDATE product_entitlements SET tier='premium' WHERE user_id=:u"), {"u": uid})
        s.execute(text("DELETE FROM subscriptions WHERE user_id=:u"), {"u": uid})
        s.commit()
    r = svc(env).resolve(uid, "premium_preview")
    assert (r.enabled, r.source, r.plan_code) == (False, "fallback_default", "basic")      # legacy tier says premium
    with env.repo.session_factory() as s:        # and with no database plan at all: code default, still Basic
        s.execute(text("DELETE FROM plan_entitlements"))
        s.execute(text("DELETE FROM subscriptions"))
        s.execute(text("DELETE FROM plan_versions"))
        s.commit()
    r = svc(env).resolve(uid, "standard_history")
    assert (r.enabled, r.plan_version, r.source) == (True, None, "fallback_default")
    assert svc(env).resolve(uid, "premium_preview").enabled is False


def test_workspace_scope_is_explicit_and_never_raises_personal_access(env):
    uid, ck = mk(env)
    _, adm = mk(env, "platform_admin")
    wid = env.c.post(f"{API}/workspaces", json={"name": "Team"}, cookies=ck).json()
    wid = wid.get("id") or wid["workspace"]["id"]
    r = env.c.post(f"{API}/admin/workspaces/{wid}/plan", json={"plan_code": "premium"}, cookies=adm)
    assert r.status_code == 200 and r.json()["subject_type"] == "workspace"
    assert svc(env).resolve(uid, "premium_preview").enabled is False                        # personal: unchanged
    assert svc(env).resolve(uid, "premium_preview", workspace_id=wid).enabled is True       # explicit workspace scope
    assign(env, adm, uid, "premium")
    other = env.c.post(f"{API}/workspaces", json={"name": "Free team"}, cookies=ck).json()
    other = other.get("id") or other["workspace"]["id"]
    assert svc(env).resolve(uid, "premium_preview").enabled is True                          # personal premium stays
    assert svc(env).resolve(uid, "premium_preview", workspace_id=other).enabled is False     # workspace w/o plan: Basic fallback
    detail = env.c.get(f"{API}/admin/workspaces/{wid}", cookies=adm).json()
    assert detail["plan"]["current"]["plan_code"] == "premium"


def test_limit_unlimited_disabled_and_unlisted_keys_resolve_deny_by_default(env):
    uid, _ = mk(env)
    with env.repo.session_factory() as s:
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid))
        s.execute(text("DELETE FROM plan_entitlements WHERE plan_version_id=:p AND entitlement_key IN ('standard_progress','standard_history')"),
                  {"p": sub.plan_version_id})
        s.add(PlanEntitlement(plan_version_id=sub.plan_version_id, entitlement_key="standard_history", enabled=True, limit_value=None))
        s.commit()
    r = svc(env, LIMIT_REG).resolve_all(uid)
    assert r["standard_history"].to_dict() == {"enabled": True, "limit": None, "unlimited": True}
    assert r["standard_progress"].enabled is False                  # key missing from the version: disabled
    assert r["documents_max"].enabled is False                      # not listed: disabled
    with env.repo.session_factory() as s:
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid))
        s.add(PlanEntitlement(plan_version_id=sub.plan_version_id, entitlement_key="documents_max", enabled=True, limit_value=7))
        s.commit()
    assert svc(env, LIMIT_REG).resolve(uid, "documents_max").to_dict() == {"enabled": True, "limit": 7, "unlimited": False}
    with pytest.raises(E.EntitlementError):
        svc(env).resolve(uid, "not_a_key")


# ---------------- plan versions: immutability, lifecycle, pinning ----------------------------------------------

def test_catalogue_detail_and_the_two_real_plans_only(env):
    _, adm = mk(env, "platform_admin")
    v = versions(env, adm)
    assert set(v) == {("basic", 1), ("premium", 1)} and v[("premium", 1)]["display_name"] == "Premium (preview)"
    assert v[("basic", 1)]["enabled_entitlements"] == 4 and v[("premium", 1)]["enabled_entitlements"] == 5
    d = env.c.get(f"{API}/admin/plans/{v[('premium', 1)]['id']}", cookies=adm).json()
    assert d["editable"] is False and {e["code"] for e in d["entitlements"]} == set(E.REGISTRY)
    assert env.c.post(f"{API}/admin/plans/enterprise/versions", cookies=adm).status_code == 422   # no invented plan
    assert env.c.get(f"{API}/admin/plans/99999", cookies=adm).status_code == 404


def test_draft_is_editable_active_and_retired_are_immutable_and_activation_pins_existing_subscribers(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    assign(env, adm, uid, "premium")
    v1 = versions(env, adm)[("premium", 1)]["id"]
    # active is immutable
    assert env.c.patch(f"{API}/admin/plans/versions/{v1}/entitlements", json={"entitlements": {"standard_history": {"enabled": False}}}, cookies=adm).status_code == 409
    draft = env.c.post(f"{API}/admin/plans/premium/versions", cookies=adm).json()
    assert draft["version"] == 2
    assert env.c.post(f"{API}/admin/plans/premium/versions", cookies=adm).status_code == 409        # one draft at a time
    body = {"entitlements": {"premium_preview": {"enabled": False}}}
    assert env.c.patch(f"{API}/admin/plans/versions/{draft['id']}/entitlements", json=body, cookies=adm).status_code == 200
    d = env.c.get(f"{API}/admin/plans/{draft['id']}", cookies=adm).json()
    assert d["editable"] and {e["code"]: e["enabled"] for e in d["entitlements"]}["premium_preview"] is False
    assert env.c.get(f"{API}/admin/plans/{v1}", cookies=adm).json()["entitlements"][-1]["enabled"] is True   # v1 untouched
    r = env.c.post(f"{API}/admin/plans/versions/{draft['id']}/activate", cookies=adm)
    assert r.status_code == 200 and r.json()["retired_version"] == 1
    v = versions(env, adm)
    assert (v[("premium", 1)]["status"], v[("premium", 2)]["status"]) == ("retired", "active")
    # the existing subscriber stays pinned to v1 (still has premium_preview); retired/active are immutable
    pinned = svc(env).resolve(uid, "premium_preview")
    assert (pinned.plan_version, pinned.enabled) == (1, True)
    assert v[("premium", 1)]["subscribers"]["users"] == 1 and v[("premium", 2)]["subscribers"]["users"] == 0
    assert env.c.patch(f"{API}/admin/plans/versions/{v1}/entitlements", json=body, cookies=adm).status_code == 409
    assert env.c.post(f"{API}/admin/plans/versions/{v1}/activate", cookies=adm).status_code == 409
    # a NEW assignment uses the active version
    new_uid, _ = mk(env)
    assign(env, adm, new_uid, "premium")
    assert svc(env).resolve(new_uid, "premium_preview").plan_version == 2 and svc(env).resolve(new_uid, "premium_preview").enabled is False


def test_edit_validation_registry_keys_only_and_types(env):
    _, adm = mk(env, "platform_admin")
    draft = env.c.post(f"{API}/admin/plans/premium/versions", cookies=adm).json()["id"]
    put = lambda ents: env.c.patch(f"{API}/admin/plans/versions/{draft}/entitlements", json={"entitlements": ents}, cookies=adm)
    assert put({"made_up_key": {"enabled": True}}).status_code == 422
    assert put({"standard_history": {"enabled": True, "limit": 5}}).status_code == 422      # boolean key takes no limit
    assert put({"standard_history": {"enabled": "yes"}}).status_code == 422
    assert put({}).status_code == 422
    assert put({"standard_history": {"enabled": False}}).status_code == 200


def test_retire_rules_and_assignability(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    ids = {k: v["id"] for k, v in versions(env, adm).items()}
    assert env.c.post(f"{API}/admin/plans/versions/{ids[('basic', 1)]}/retire", cookies=adm).status_code == 409   # default plan
    assert env.c.post(f"{API}/admin/plans/versions/{ids[('premium', 1)]}/retire", cookies=adm).status_code == 200
    assert env.c.post(f"{API}/admin/plans/versions/{ids[('premium', 1)]}/retire", cookies=adm).status_code == 409
    assert assign(env, adm, uid, "premium").status_code == 409                                   # nothing assignable
    assert {p["plan_code"] for p in env.c.get(f"{API}/admin/plans/assignable", cookies=adm).json()} == {"basic"}
    draft = env.c.post(f"{API}/admin/plans/premium/versions", cookies=adm).json()["id"]
    assert assign(env, adm, uid, "premium").status_code == 409                                   # a draft is not assignable
    env.c.post(f"{API}/admin/plans/versions/{draft}/activate", cookies=adm)
    assert assign(env, adm, uid, "premium").status_code == 200


# ---------------- subscription changes ---------------------------------------------------------------------------

def test_plan_change_ends_the_old_subscription_keeps_history_and_the_tier_in_step(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    r = assign(env, adm, uid, "premium")
    assert r.status_code == 200 and r.json()["changed"] is True
    assign(env, adm, uid, "basic")
    d = env.c.get(f"{API}/admin/users/{uid}", cookies=adm).json()
    assert d["plan"]["current"]["plan_code"] == "basic"
    hist = [(h["plan_code"], h["status"], h["source"]) for h in d["plan"]["history"]]
    assert hist == [("basic", "active", "admin"), ("premium", "ended", "admin"), ("basic", "ended", "system_default")]
    assert d["account"]["tier"] == "basic" and env.accounts.get_account(uid).tier == "basic"
    with env.repo.session_factory() as s:
        assert s.scalar(select(text("count(*)")).select_from(Subscription).where(Subscription.user_id == uid, Subscription.status == "active")) == 1
    again = assign(env, adm, uid, "basic")
    assert again.status_code == 200 and again.json()["changed"] is False
    assert assign(env, adm, uid, "pro").status_code == 422 and assign(env, adm, 99999, "basic").status_code == 404
    ev = env.events(A.ADMIN_SUBSCRIPTION_ASSIGNED)[1]
    assert ev["context"]["after"] == "basic" and ev["context"]["before"] == "premium" and ev["request_id"]


def test_legacy_tier_bridge_uses_the_subscription_path_only(env):
    uid, _ = mk(env)
    assert env.accounts.set_tier(uid, "premium", source="test") is True
    assert svc(env).resolve(uid, "premium_preview").enabled is True and env.accounts.get_account(uid).tier == "premium"
    assert env.accounts.set_tier(99999, "premium") is False


@pytest.mark.parametrize("call", ["assign", "create_draft", "update", "activate", "retire"])
def test_every_privileged_plan_mutation_rolls_back_when_audit_fails(env, monkeypatch, call):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    ids = {k: v["id"] for k, v in versions(env, adm).items()}
    draft = None
    if call in ("update", "activate"):
        draft = env.c.post(f"{API}/admin/plans/premium/versions", cookies=adm).json()["id"]
    before = json.dumps(env.c.get(f"{API}/admin/plans", cookies=adm).json(), sort_keys=True)
    sub_before = env.c.get(f"{API}/admin/users/{uid}", cookies=adm).json()["plan"]
    from src.auth_repository import AccountRepository
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(lambda s, a: (_ for _ in ()).throw(RuntimeError("x"))))
    reqs = {"assign": lambda: assign(env, adm, uid, "premium"),
            "create_draft": lambda: env.c.post(f"{API}/admin/plans/premium/versions", cookies=adm),
            "update": lambda: env.c.patch(f"{API}/admin/plans/versions/{draft}/entitlements", json={"entitlements": {"standard_history": {"enabled": False}}}, cookies=adm),
            "activate": lambda: env.c.post(f"{API}/admin/plans/versions/{draft}/activate", cookies=adm),
            "retire": lambda: env.c.post(f"{API}/admin/plans/versions/{ids[('premium', 1)]}/retire", cookies=adm)}
    assert reqs[call]().status_code == 500
    monkeypatch.undo()
    after = json.dumps(env.c.get(f"{API}/admin/plans", cookies=adm).json(), sort_keys=True)
    assert after == before
    assert env.c.get(f"{API}/admin/users/{uid}", cookies=adm).json()["plan"] == sub_before
    if call == "update":
        d = env.c.get(f"{API}/admin/plans/{draft}", cookies=adm).json()
        assert {e["code"]: e["enabled"] for e in d["entitlements"]}["standard_history"] is True


def test_plan_audit_events_carry_codes_versions_and_key_names_only(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    vid = make_active_v2(env, adm, "premium", {"premium_preview": {"enabled": False}})
    assign(env, adm, uid, "premium")
    for name in (A.ADMIN_PLAN_VERSION_CREATED, A.ADMIN_PLAN_VERSION_UPDATED, A.ADMIN_PLAN_VERSION_ACTIVATED,
                 A.ADMIN_SUBSCRIPTION_ASSIGNED):
        assert name in A.ADMIN_EVENT_NAMES
        ev = env.events(name)[0]
        assert ev["actor_user_id"] and ev["request_id"]
    upd = env.events(A.ADMIN_PLAN_VERSION_UPDATED)[0]["context"]
    assert upd["changed_keys"] == "premium_preview" and upd["plan_code"] == "premium" and upd["version"] == 2
    act = env.events(A.ADMIN_PLAN_VERSION_ACTIVATED)[0]
    assert act["target_id"] == str(vid) and act["context"]["retired_version"] == 1
    blob = json.dumps([e["context"] for t in (A.ADMIN_PLAN_VERSION_CREATED, A.ADMIN_SUBSCRIPTION_ASSIGNED) for e in env.events(t)]).lower()
    for bad in ("price", "currency", "payment", "invoice", "card"):
        assert bad not in blob


# ---------------- the gates and the candidate surface -----------------------------------------------------------

def test_entitlement_gate_not_the_tier_decides_product_access(env):
    uid, ck = mk(env)
    _, adm = mk(env, "platform_admin")
    assert env.c.get(f"{API}/auth/premium/status", cookies=ck).status_code == 403
    env.c.post(f"{API}/research/company", json={}, cookies=ck)       # allowed by Basic: not a 403
    assert env.c.post(f"{API}/research/company", json={}, cookies=ck).status_code != 403
    assign(env, adm, uid, "premium")
    assert env.c.get(f"{API}/auth/premium/status", cookies=ck).status_code == 200
    # a new active Basic version that disables market research removes access for NEW assignments
    make_active_v2(env, adm, "basic", {"current_market_research": {"enabled": False}})
    uid2, ck2 = mk(env)
    assert assign(env, adm, uid2, "basic").json()["version"] == 2
    assert env.c.post(f"{API}/research/company", json={}, cookies=ck2).status_code == 403
    assert env.c.post(f"{API}/research/company", json={}, cookies=ck).status_code != 403     # premium user unaffected
    assert "current_market_research" not in env.c.get(f"{API}/auth/me", cookies=ck2).json()["capabilities"]


def test_candidate_account_and_plan_views_are_read_only_price_free_and_entitlement_driven(env):
    uid, ck = mk(env)
    me = env.c.get(f"{API}/auth/me", cookies=ck).json()
    assert sorted(me["capabilities"]) == sorted(E.BASIC_KEYS) and me["tier"] == "basic"
    p = env.c.get(f"{API}/auth/plan", cookies=ck).json()
    assert set(p) == {"plan_code", "plan_version", "entitlements"} and p["plan_code"] == "basic"
    assert p["entitlements"]["premium_preview"] == {"enabled": False, "limit": None, "unlimited": False}
    blob = json.dumps(p).lower()
    for bad in ("price", "currency", "payment", "invoice", "eur", "checkout"):
        assert bad not in blob
    for method in ("post", "put", "patch", "delete"):
        assert getattr(env.c, method)(f"{API}/auth/plan", cookies=ck).status_code == 405


def test_candidate_cannot_change_any_plan_or_subscription(env):
    uid, ck = mk(env)
    other, _ = mk(env)
    _, sup = mk(env, "support_operator")
    for path, body in ((f"/admin/users/{uid}/plan", {"plan_code": "premium"}), (f"/admin/users/{other}/plan", {"plan_code": "premium"}),
                       ("/admin/workspaces/1/plan", {"plan_code": "premium"})):
        assert env.c.post(API + path, json=body, cookies=ck).status_code == 403
        assert env.c.post(API + path, json=body, cookies=sup).status_code == 403
    assert env.c.post(f"{API}/auth/preferences", json={"tier": "premium"}, cookies=ck).status_code in (404, 405, 422)
    assert svc(env).resolve(uid, "premium_preview").enabled is False


def test_plan_permission_matrix(env):
    expectations = {"platform_admin": (True, True), "billing_admin": (True, True), "support_operator": (False, False),
                    "knowledge_admin": (False, False), "operations_admin": (False, False), "security_privacy_admin": (False, False)}
    for role, (can_plans, can_assign) in expectations.items():
        _, ck = mk(env, role)
        tid, _ = mk(env)
        assert (env.c.get(f"{API}/admin/plans", cookies=ck).status_code == 200) is can_plans, role
        assert (env.c.post(f"{API}/admin/plans/premium/versions", cookies=ck).status_code in (200, 409)) is can_plans, role
        assert (assign(env, ck, tid, "basic").status_code == 200) is can_assign, role
    _, cand = mk(env)
    assert env.c.get(f"{API}/admin/plans", cookies=cand).status_code == 403


# ---------------- privacy -------------------------------------------------------------------------------------------

def test_export_includes_own_plan_history_without_payment_or_admin_data(env):
    uid, ck = mk(env)
    _, adm = mk(env, "platform_admin")
    assign(env, adm, uid, "premium")
    body = env.c.get(f"{API}/auth/account/export", cookies=ck).json()
    assert body["plan"]["current"]["plan_code"] == "premium"
    assert [h["status"] for h in body["plan"]["history"]] == ["active", "ended"]
    assert any("plan" in i for i in body["scope"]["included"])
    blob = json.dumps(body["plan"]).lower()
    for bad in ("price", "payment", "invoice", "actor", "request_id"):
        assert bad not in blob


def test_account_deletion_removes_own_subscriptions_but_not_plan_definitions_or_others(env):
    uid, ck = mk(env)
    oid, other = mk(env)
    _, adm = mk(env, "platform_admin")
    wid = env.c.post(f"{API}/workspaces", json={"name": "Solo"}, cookies=ck).json()
    wid = wid.get("id") or wid["workspace"]["id"]
    env.c.post(f"{API}/admin/workspaces/{wid}/plan", json={"plan_code": "premium"}, cookies=adm)
    assign(env, adm, uid, "premium")
    assert env.c.post(f"{API}/auth/account/delete", cookies=ck).status_code == 200
    with env.repo.session_factory() as s:
        assert s.scalar(select(text("count(*)")).select_from(Subscription).where(Subscription.user_id == uid)) == 0
        assert s.scalar(select(text("count(*)")).select_from(Subscription).where(Subscription.workspace_id == wid)) == 0   # sole-owner workspace deleted
        assert s.scalar(select(text("count(*)")).select_from(PlanVersion)) == 2                                          # definitions stay
    assert svc(env).resolve(oid, "standard_history").enabled is True and env.c.get(f"{API}/auth/me", cookies=other).status_code == 200


def test_command_center_plan_counts_are_gated_and_have_no_revenue(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    _, sup = mk(env, "support_operator")
    assign(env, adm, uid, "premium")
    home = env.c.get(f"{API}/admin/home", cookies=adm).json()
    assert home["plans"]["by_plan"]["premium"]["users"] == 1 and home["plans"]["accounts_without_subscription"] == 0
    assert "plans" not in env.c.get(f"{API}/admin/home", cookies=sup).json()
    blob = json.dumps(home).lower()
    for bad in ("mrr", "arr", "revenue", "churn", "price"):
        assert bad not in blob


# ---------------- structure ---------------------------------------------------------------------------------------

def test_plan_routes_are_permissioned_and_schemas_carry_no_price_fields():
    from pydantic import BaseModel
    from src.api.admin_route_invariant import admin_routes, ungated
    from src.api.schemas import admin as S
    routes = admin_routes()
    plan_routes = [r for r in routes if r.path.startswith("/admin/plans") or r.path.endswith("/plan")]
    assert len(plan_routes) == 9 and ungated(routes) == []
    assert {p for r in plan_routes for p in r.permissions} == {perm.PLANS_READ, perm.PLANS_MANAGE, perm.SUBSCRIPTIONS_MANAGE}
    names = []
    for cls in vars(S).values():
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == S.__name__:
            names += list(cls.model_fields)
    assert not [n for n in names if any(w in n for w in ("price", "currency", "payment", "invoice", "amount", "interval", "trial", "card"))]


# ---------------- migration ---------------------------------------------------------------------------------------

def _cfg(url):
    from alembic.config import Config
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_backfill_constraints_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.exc import IntegrityError

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_cfg(url), "0015_support_ticketing")
    eng = create_engine(url)
    with eng.begin() as c:
        for uid in (1, 2, 3):
            c.execute(text("INSERT INTO users(id, subject, provider, platform_role, status, email_verified, onboarding_step, created_at, updated_at)"
                           " VALUES (:i,:s,'p','user','active',0,0,'2026-01-01','2026-01-01')"), {"i": uid, "s": f"s{uid}"})
        c.execute(text("INSERT INTO product_entitlements(user_id, tier, source, created_at, updated_at) VALUES (1,'premium','admin','2026-01-01','2026-01-01'),(2,'basic','default','2026-01-01','2026-01-01')"))
        c.execute(text("INSERT INTO workspaces(id, owner_user_id, name, status, created_at, updated_at) VALUES (1,1,'w','active','2026-01-01','2026-01-01')"))
    command.upgrade(_cfg(url), "head")
    insp = inspect(eng)
    assert {"plan_versions", "plan_entitlements", "subscriptions"} <= set(insp.get_table_names())
    with eng.begin() as c:
        rows = c.execute(text("SELECT s.user_id, v.plan_code, v.version, s.source, s.status FROM subscriptions s JOIN plan_versions v ON v.id=s.plan_version_id ORDER BY s.user_id")).all()
        assert rows == [(1, "premium", 1, "migration", "active"), (2, "basic", 1, "migration", "active"), (3, "basic", 1, "migration", "active")]
        assert c.execute(text("SELECT COUNT(*) FROM subscriptions WHERE workspace_id IS NOT NULL")).scalar() == 0   # workspaces: optional
        ents = dict(c.execute(text("SELECT v.plan_code, SUM(e.enabled) FROM plan_entitlements e JOIN plan_versions v ON v.id=e.plan_version_id GROUP BY 1")).all())
        assert ents == {"basic": 4, "premium": 5}
        assert c.execute(text("SELECT tier FROM product_entitlements WHERE user_id=1")).scalar() == "premium"      # legacy column untouched
        pv = c.execute(text("SELECT id FROM plan_versions WHERE plan_code='basic'")).scalar()

    # NO ACCESS REGRESSION: every migrated user resolves to exactly what the pre-W10.4 tier map granted.
    from sqlalchemy.orm import sessionmaker

    from src.application.authorization import capabilities_for
    svc_after = E.EntitlementService(sessionmaker(bind=eng, future=True))
    legacy_tier = {1: "premium", 2: "basic", 3: "basic"}          # user 3 had no tier row: treated as basic
    for uid, tier in legacy_tier.items():
        assert set(svc_after.enabled_keys(uid)) == set(capabilities_for(tier)), (uid, tier)

    def bad(sql, params=None):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(sql), params or {})

    base = "INSERT INTO subscriptions(user_id, workspace_id, plan_version_id, status, source, started_at) VALUES "
    bad(base + f"(NULL, NULL, {pv}, 'active', 'admin', '2026-01-01')")            # neither subject
    bad(base + f"(1, 1, {pv}, 'ended', 'admin', '2026-01-01')")                   # both subjects
    bad(base + f"(3, NULL, {pv}, 'trialing', 'admin', '2026-01-01')")             # invalid lifecycle
    bad(base + f"(3, NULL, {pv}, 'ended', 'stripe', '2026-01-01')")               # invalid source
    bad(base + f"(1, NULL, {pv}, 'active', 'admin', '2026-01-01')")               # second ACTIVE user subscription
    with eng.begin() as c:
        c.execute(text(base + f"(1, NULL, {pv}, 'ended', 'admin', '2026-01-01')"))   # history rows are allowed
        c.execute(text(base + f"(NULL, 1, {pv}, 'active', 'admin', '2026-01-01')"))
    bad(base + f"(NULL, 1, {pv}, 'active', 'admin', '2026-01-01')")               # second ACTIVE workspace subscription
    bad("INSERT INTO plan_entitlements(plan_version_id, entitlement_key, enabled, limit_value) VALUES (:p,'standard_history',1,NULL)", {"p": pv})   # duplicate key
    bad("INSERT INTO plan_entitlements(plan_version_id, entitlement_key, enabled, limit_value) VALUES (:p,'x',1,0)", {"p": pv})                    # 0 is never a limit
    bad("INSERT INTO plan_entitlements(plan_version_id, entitlement_key, enabled, limit_value) VALUES (:p,'y',0,5)", {"p": pv})                    # disabled + limit
    bad("INSERT INTO plan_versions(plan_code, version, display_name, status, created_at) VALUES ('basic', 2, 'B', 'active', '2026-01-01')")        # second active version
    bad("INSERT INTO plan_versions(plan_code, version, display_name, status, created_at) VALUES ('basic', 1, 'B', 'retired', '2026-01-01')")       # duplicate version
    bad("INSERT INTO plan_versions(plan_code, version, display_name, status, created_at) VALUES ('basic', 3, 'B', 'weird', '2026-01-01')")        # invalid status
    command.downgrade(_cfg(url), "0015_support_ticketing")
    assert "subscriptions" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(_cfg(url), "head")                                                      # round trip re-backfills
    with create_engine(url).begin() as c:
        assert c.execute(text("SELECT COUNT(*) FROM subscriptions")).scalar() == 3
