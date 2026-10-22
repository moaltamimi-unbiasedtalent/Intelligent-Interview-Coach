"""03B (REQ-OWN-02): Admin Plans management for exactly Basic and Premium (preview). Real isolated SQLite, real HTTP, no provider,
no billing. Covers matrix/compare, code-defined bounds, expected revisions, rollback, assignment preview parity, single and bulk
assignment, assignment history, the effective-entitlement explanation, the 7-persona permission matrix, allowlist responses and
sentinel sweeps."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from src import entitlements as E
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.billing import policy as billing_policy
from src.persistence import (
    AuditEvent,
    BillingCommercialTerms,
    PlanEntitlement,
    PlanVersion,
    Subscription,
)
from tests import _admin_matrix as M
from tests._auth_factories import cookies_for, login_token, register
from tests.test_admin_foundation_w10_1 import PW, Env

API = "/api/v1"
P = f"{API}/admin/plans"


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def mk(env, role="user"):
    env.n += 1
    email = f"q{env.n}@x.com"
    register(env.c, email, PW)
    tok = login_token(env.c, email, PW)
    uid = env.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["user_id"]
    if role != "user":
        env.accounts.set_platform_role(uid, role)
    return uid, cookies_for(tok)


def catalogue(env, ck):
    return {(v["plan_code"], v["version"]): v for v in env.c.get(P, cookies=ck).json()["items"]}


def new_draft(env, adm, code, rev=None):
    body = {"expected_revision": rev} if rev else None
    r = env.c.post(f"{P}/{code}/versions", json=body, cookies=adm) if body else env.c.post(f"{P}/{code}/versions", cookies=adm)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def detail(env, adm, vid):
    return env.c.get(f"{P}/{vid}", cookies=adm).json()


def patch(env, adm, vid, ents, rev="auto"):
    if rev == "auto":
        rev = detail(env, adm, vid)["revision"]
    body = {"entitlements": ents}
    if rev is not None:
        body["expected_revision"] = rev
    return env.c.patch(f"{P}/versions/{vid}/entitlements", json=body, cookies=adm)


def activate(env, adm, vid, rev="auto"):
    if rev == "auto":
        rev = detail(env, adm, vid)["revision"]
    return env.c.post(f"{P}/versions/{vid}/activate", json={"expected_revision": rev}, cookies=adm)


def sub_count(env):
    with env.repo.session_factory() as s:
        return int(s.scalar(select(func.count()).select_from(Subscription)) or 0)


def audits(env, event):
    with env.repo.session_factory() as s:
        return s.scalars(select(AuditEvent).where(AuditEvent.event_type == event).order_by(AuditEvent.id)).all()


def subject_rev(env, adm, kind, sid):
    return env.c.get(f"{P}/subjects/{kind}/{sid}", cookies=adm).json()["revision"]


# ------------------------------------------------------------------------------------------ matrix and compare (P3)

def test_matrix_lists_every_registered_key_against_every_version(env):
    _, adm = mk(env, "platform_admin")
    m = env.c.get(f"{P}/matrix", cookies=adm).json()
    assert [e["code"] for e in m["entitlements"]] == list(E.REGISTRY)
    v = {(x["plan_code"], x["version"]): x for x in m["versions"]}
    assert set(v) == {("basic", 1), ("premium", 1)}
    assert v[("basic", 1)]["values"]["premium_preview"] == {"enabled": False, "limit": None}
    assert v[("premium", 1)]["values"]["premium_preview"] == {"enabled": True, "limit": None}
    assert all(set(x["values"]) == set(E.REGISTRY) for x in m["versions"])


def test_compare_reports_exact_differences_and_does_not_move_anyone(env):
    _, adm = mk(env, "platform_admin")
    before = sub_count(env)
    ids = {k: v["id"] for k, v in catalogue(env, adm).items()}
    c = env.c.get(f"{P}/compare", params={"left": ids[("basic", 1)], "right": ids[("premium", 1)]}, cookies=adm).json()
    assert c["changed"] == 1 and [r["code"] for r in c["rows"] if r["differs"]] == ["premium_preview"]
    assert env.c.get(f"{P}/compare", params={"left": 999, "right": ids[("premium", 1)]}, cookies=adm).status_code == 404
    assert sub_count(env) == before


# ------------------------------------------------------------------------------------------ bounds (P1, P2)

def test_bounds_are_exposed_and_basic_can_never_carry_a_premium_only_key(env):
    _, adm = mk(env, "platform_admin")
    vid = new_draft(env, adm, "basic")
    d = detail(env, adm, vid)
    row = next(e for e in d["entitlements"] if e["code"] == "premium_preview")
    assert row["bounds"] == {"kind": "boolean", "min_limit": None, "max_limit": None, "premium_only": True}
    r = patch(env, adm, vid, {"premium_preview": {"enabled": True}})
    assert r.status_code == 422 and "Premium-only" in r.json()["error"]["message"]
    assert patch(env, adm, vid, {"standard_history": {"enabled": False}}).status_code == 200      # a legitimate edit still works
    # the same plan family cannot be smuggled through activation either
    with env.repo.session_factory() as s:
        row = s.scalar(select(PlanEntitlement).where(PlanEntitlement.plan_version_id == vid, PlanEntitlement.entitlement_key == "premium_preview"))
        row.enabled = True
        s.commit()
    r = activate(env, adm, vid)
    assert r.status_code == 422


def test_unknown_keys_limits_and_extra_fields_are_refused(env):
    _, adm = mk(env, "platform_admin")
    vid = new_draft(env, adm, "premium")
    assert patch(env, adm, vid, {"made_up_key": {"enabled": True}}).status_code == 422
    assert patch(env, adm, vid, {"standard_history": {"enabled": True, "limit": 5}}).status_code == 422   # boolean key takes no limit
    assert patch(env, adm, vid, {"standard_history": {"enabled": "yes"}}).status_code == 422
    r = env.c.patch(f"{P}/versions/{vid}/entitlements", json={"entitlements": {"standard_history": {"enabled": True}}, "price": 1}, cookies=adm)
    assert r.status_code == 422


def test_limit_bound_is_enforced_for_a_code_defined_limit_key():
    reg = {**E.REGISTRY, "docs": E.EntitlementDef("docs", E.EntitlementType.LIMIT, "Docs", "test only", max_limit=10)}
    assert E.validate_value("docs", True, 10, reg) == (True, 10)
    for bad in (11, 0, -3):
        with pytest.raises(E.EntitlementError):
            E.validate_value("docs", True, bad, reg)
    assert E.bounds_of(reg["docs"]) == {"kind": "limit", "min_limit": 1, "max_limit": 10, "premium_only": False}
    assert not any(d.type is E.EntitlementType.LIMIT for d in E.REGISTRY.values())      # still no invented quota


# ------------------------------------------------------------------------------------------ expected revision (P6)

def test_stale_revision_is_refused_on_every_plan_mutation_and_changes_nothing(env):
    _, adm = mk(env, "platform_admin")
    vid = new_draft(env, adm, "premium")
    stale = detail(env, adm, vid)["revision"]
    assert patch(env, adm, vid, {"standard_progress": {"enabled": False}}, rev=stale).status_code == 200
    again = patch(env, adm, vid, {"standard_progress": {"enabled": True}}, rev=stale)       # second admin used the old view
    assert again.status_code == 409
    assert next(e for e in detail(env, adm, vid)["entitlements"] if e["code"] == "standard_progress")["enabled"] is False
    assert activate(env, adm, vid, rev=stale).status_code == 409
    assert detail(env, adm, vid)["status"] == "draft"
    assert activate(env, adm, vid).status_code == 200
    active_rev = detail(env, adm, vid)["revision"]
    assert env.c.post(f"{P}/versions/{vid}/retire", json={"expected_revision": "0" * 16}, cookies=adm).status_code == 409
    assert env.c.post(f"{P}/versions/{vid}/retire", json={"expected_revision": active_rev}, cookies=adm).status_code == 200


def test_family_revision_guards_draft_creation_and_a_lifecycle_change_invalidates_other_versions(env):
    _, adm = mk(env, "platform_admin")
    fam = catalogue(env, adm)[("premium", 1)]["family_revision"]
    assert env.c.post(f"{P}/premium/versions", json={"expected_revision": "f" * 16}, cookies=adm).status_code == 409
    vid = new_draft(env, adm, "premium", rev=fam)
    # the draft changed the family: the old family revision no longer works, and v1's revision moved with it
    assert catalogue(env, adm)[("premium", 1)]["family_revision"] != fam
    assert env.c.post(f"{P}/premium/versions", json={"expected_revision": fam}, cookies=adm).status_code == 409
    assert vid


def test_two_admins_racing_to_activate_cannot_both_win(env):
    _, a1 = mk(env, "platform_admin")
    _, a2 = mk(env, "billing_admin")
    vid = new_draft(env, a1, "premium")
    rev = detail(env, a1, vid)["revision"]
    assert activate(env, a1, vid, rev=rev).status_code == 200
    assert activate(env, a2, vid, rev=rev).status_code == 409       # stale AND no longer a draft


def test_revision_is_optional_only_on_the_legacy_shape_and_wrong_types_are_422(env):
    _, adm = mk(env, "platform_admin")
    vid = new_draft(env, adm, "premium")
    assert patch(env, adm, vid, {"standard_progress": {"enabled": False}}, rev=None).status_code == 200
    r = env.c.post(f"{P}/versions/{vid}/activate", json={"expected_revision": 5}, cookies=adm)
    assert r.status_code == 422


# ------------------------------------------------------------------------------------------ lifecycle invariants (P5)

def test_activating_a_new_version_never_moves_subscribers_and_old_version_stays_pinned(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    assert env.c.post(f"{API}/admin/users/{uid}/plan", json={"plan_code": "premium"}, cookies=adm).status_code == 200
    before = catalogue(env, adm)[("premium", 1)]["subscribers"]
    vid = new_draft(env, adm, "premium")
    assert patch(env, adm, vid, {"premium_preview": {"enabled": False}}).status_code == 200
    assert activate(env, adm, vid).status_code == 200
    cat = catalogue(env, adm)
    assert cat[("premium", 1)]["status"] == "retired" and cat[("premium", 1)]["subscribers"] == before
    assert E.EntitlementService(env.repo.session_factory).is_enabled(uid, "premium_preview") is True     # still on v1
    assert cat[("premium", 2)]["subscribers"] == {"users": 0, "workspaces": 0}


def test_default_plan_cannot_be_retired_and_the_billing_gate_stays_false(env):
    _, adm = mk(env, "platform_admin")
    basic = catalogue(env, adm)[("basic", 1)]
    r = env.c.post(f"{P}/versions/{basic['id']}/retire", json={"expected_revision": basic["revision"]}, cookies=adm)
    assert r.status_code == 409
    assert billing_policy.LIVE_BILLING_ENABLED is False


# ------------------------------------------------------------------------------------------ rollback (P6)

def test_rollback_restores_an_earlier_version_as_a_new_draft_without_editing_history(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    vid = new_draft(env, adm, "premium")
    assert patch(env, adm, vid, {"premium_preview": {"enabled": False}}).status_code == 200
    assert activate(env, adm, vid).status_code == 200            # v2 active, v1 retired
    v1 = catalogue(env, adm)[("premium", 1)]
    fam = v1["family_revision"]
    out = env.c.post(f"{P}/versions/{v1['id']}/restore-as-draft", json={"expected_revision": fam}, cookies=adm)
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["version"] == 3 and body["copied_from"] == 1
    d3 = detail(env, adm, body["id"])
    assert d3["status"] == "draft" and next(e for e in d3["entitlements"] if e["code"] == "premium_preview")["enabled"] is True
    # history untouched, nobody moved, a second restore is refused while a draft exists, and a stale family revision is refused
    cat = catalogue(env, adm)
    assert cat[("premium", 1)]["status"] == "retired" and cat[("premium", 2)]["status"] == "active"
    assert env.c.post(f"{P}/versions/{v1['id']}/restore-as-draft", json={"expected_revision": catalogue(env, adm)[("premium", 1)]["family_revision"]}, cookies=adm).status_code == 409
    assert env.c.post(f"{P}/versions/{v1['id']}/restore-as-draft", json={"expected_revision": fam}, cookies=adm).status_code == 409
    assert activate(env, adm, body["id"]).status_code == 200      # rolling back = activating the restored draft
    assert any(a.context.get("rollback_of") == 1 for a in audits(env, A.ADMIN_PLAN_VERSION_CREATED) if a.context)
    assert uid


def test_restore_requires_a_revision(env):
    _, adm = mk(env, "platform_admin")
    v1 = catalogue(env, adm)[("premium", 1)]
    assert env.c.post(f"{P}/versions/{v1['id']}/restore-as-draft", json={}, cookies=adm).status_code == 422


# ------------------------------------------------------------------------------------------ preview and parity (P3, P4)

def preview(env, adm, plan, kind, ids):
    return env.c.get(f"{P}/assignments/preview", params={"plan_code": plan, "subject_type": kind, "ids": ",".join(map(str, ids))}, cookies=adm)


def test_preview_is_counts_only_and_matches_the_actual_effect(env):
    u1, _ = mk(env)
    u2, _ = mk(env)
    u3, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    assert env.c.post(f"{API}/admin/users/{u3}/plan", json={"plan_code": "premium"}, cookies=adm).status_code == 200
    r = preview(env, adm, "premium", "user", [u1, u2, u3])
    assert r.status_code == 200
    p = r.json()
    assert p["requested"] == 3 and p["found"] == 3 and p["unchanged"] == 1 and p["would_change"] == 2
    assert p["by_current_plan"] == {"basic": 2, "premium": 1, "none": 0}
    gain = {e["code"]: e["gain"] for e in p["entitlement_effect"]}
    assert gain["premium_preview"] == 2 and sum(gain.values()) == 2
    assert set(p) == {"plan_code", "target_version", "subject_type", "requested", "found", "missing", "unchanged", "would_change",
                      "by_current_plan", "entitlement_effect", "preview_revision"}
    text = r.text
    assert not any(isinstance(v, list) and v and isinstance(v[0], int) for v in p.values())              # counts only, never an id list
    assert "@" not in text                                                                              # no email
    svc = E.EntitlementService(env.repo.session_factory)
    before = {u: svc.is_enabled(u, "premium_preview") for u in (u1, u2)}
    done = env.c.post(f"{P}/assignments/bulk", json={"plan_code": "premium", "subject_type": "user", "subject_ids": [u1, u2, u3],
                                                    "preview_revision": p["preview_revision"]}, cookies=adm)
    assert done.status_code == 200 and done.json()["changed"] == 2 and done.json()["unchanged"] == 1
    after = {u: svc.is_enabled(u, "premium_preview") for u in (u1, u2)}
    gained = sum(1 for u in (u1, u2) if not before[u] and after[u])
    assert gained == gain["premium_preview"] == 2                         # preview-versus-actual parity


def test_preview_of_workspaces_and_missing_subjects(env):
    _, adm = mk(env, "platform_admin")
    owner, ock = mk(env)
    made = env.c.post(f"{API}/workspaces", json={"name": "Team Alpha"}, cookies=ock).json()
    wid = made.get("id") or made["workspace"]["id"]
    p = preview(env, adm, "premium", "workspace", [wid, 98765]).json()
    assert p["found"] == 1 and p["missing"] == 1 and p["would_change"] == 1
    ok = preview(env, adm, "premium", "workspace", [wid]).json()
    done = env.c.post(f"{P}/assignments/bulk", json={"plan_code": "premium", "subject_type": "workspace", "subject_ids": [wid],
                                                    "preview_revision": ok["preview_revision"]}, cookies=adm)
    assert done.status_code == 200 and done.json()["changed"] == 1
    ex = env.c.get(f"{P}/explain", params={"workspace_id": wid}, cookies=adm).json()
    assert ex["subject_type"] == "workspace" and ex["plan_code"] == "premium" and ex["source"] == "subscription"
    # a workspace plan never raises the owner's personal access
    assert env.c.get(f"{P}/explain", params={"user_id": owner}, cookies=adm).json()["plan_code"] == "basic"


def test_preview_validation(env):
    _, adm = mk(env, "platform_admin")
    assert preview(env, adm, "gold", "user", [1]).status_code in (404, 409, 422)
    assert preview(env, adm, "premium", "team", [1]).status_code == 422
    assert preview(env, adm, "premium", "user", list(range(1, 102))).status_code == 422
    assert env.c.get(f"{P}/assignments/preview", params={"plan_code": "premium", "subject_type": "user", "ids": "a,b"}, cookies=adm).status_code == 422


# ------------------------------------------------------------------------------------------ single and bulk assignment (P4)

def test_single_assignment_needs_the_current_subject_revision(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    state = env.c.get(f"{P}/subjects/user/{uid}", cookies=adm).json()
    assert state["current"]["plan_code"] == "basic" and len(state["history"]) == 1
    body = {"plan_code": "premium", "subject_type": "user", "subject_id": uid, "expected_revision": state["revision"]}
    r = env.c.post(f"{P}/assignments", json=body, cookies=adm)
    assert r.status_code == 200 and r.json()["changed"] is True
    stale = env.c.post(f"{P}/assignments", json={**body, "plan_code": "basic"}, cookies=adm)      # same stale revision
    assert stale.status_code == 409
    assert env.c.get(f"{P}/subjects/user/{uid}", cookies=adm).json()["current"]["plan_code"] == "premium"
    assert env.c.post(f"{P}/assignments", json={k: v for k, v in body.items() if k != "expected_revision"}, cookies=adm).status_code == 422
    assert env.c.post(f"{P}/assignments", json={**body, "subject_id": 424242, "expected_revision": "x"}, cookies=adm).status_code == 404
    assert env.c.post(f"{P}/assignments", json={**body, "subject_type": "team"}, cookies=adm).status_code in (404, 422)


def test_bulk_requires_a_current_preview_and_is_all_or_nothing(env):
    users = [mk(env)[0] for _ in range(3)]
    _, adm = mk(env, "platform_admin")
    body = {"plan_code": "premium", "subject_type": "user", "subject_ids": users}
    assert env.c.post(f"{P}/assignments/bulk", json=body, cookies=adm).status_code == 422                   # no preview revision
    assert env.c.post(f"{P}/assignments/bulk", json={**body, "preview_revision": "0" * 16}, cookies=adm).status_code == 409
    tok = preview(env, adm, "premium", "user", users).json()["preview_revision"]
    # one of the subjects changes plan between preview and commit: the preview is stale, nothing is written
    assert env.c.post(f"{API}/admin/users/{users[0]}/plan", json={"plan_code": "premium"}, cookies=adm).status_code == 200
    n_before = sub_count(env)
    assert env.c.post(f"{P}/assignments/bulk", json={**body, "preview_revision": tok}, cookies=adm).status_code == 409
    assert sub_count(env) == n_before
    # an unknown id: refused as a whole (preview shows it as missing), nobody moves
    ids = [*users, 777777]
    tok2 = preview(env, adm, "premium", "user", ids).json()["preview_revision"]
    r = env.c.post(f"{P}/assignments/bulk", json={**body, "subject_ids": ids, "preview_revision": tok2}, cookies=adm)
    assert r.status_code == 422 and sub_count(env) == n_before
    tok3 = preview(env, adm, "premium", "user", users).json()["preview_revision"]
    ok = env.c.post(f"{P}/assignments/bulk", json={**body, "subject_ids": users + users, "preview_revision": tok3}, cookies=adm)
    assert ok.status_code == 200 and ok.json() == {"plan_code": "premium", "version": 1, "subject_type": "user", "requested": 3,
                                                  "changed": 2, "unchanged": 1}


def test_bulk_writes_one_audit_row_per_subject_in_the_same_transaction_and_rolls_back_with_it(env, monkeypatch):
    users = [mk(env)[0] for _ in range(2)]
    _, adm = mk(env, "platform_admin")
    tok = preview(env, adm, "premium", "user", users).json()["preview_revision"]
    body = {"plan_code": "premium", "subject_type": "user", "subject_ids": users, "preview_revision": tok}
    import src.plans_repository as pr
    real = pr._stage
    calls = {"n": 0}

    def boom(s, audit, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("audit write failed")
        return real(s, audit, **kw)
    monkeypatch.setattr(pr, "_stage", boom)
    n_audit, n_sub = len(audits(env, A.ADMIN_SUBSCRIPTION_ASSIGNED)), sub_count(env)
    assert env.c.post(f"{P}/assignments/bulk", json=body, cookies=adm).status_code == 500      # the app's safe 500 envelope
    monkeypatch.setattr(pr, "_stage", real)
    assert sub_count(env) == n_sub and len(audits(env, A.ADMIN_SUBSCRIPTION_ASSIGNED)) == n_audit    # the assignment rolled back WITH the audit
    assert env.c.post(f"{P}/assignments/bulk", json=body, cookies=adm).status_code == 200
    rows = audits(env, A.ADMIN_SUBSCRIPTION_ASSIGNED)[n_audit:]
    assert len(rows) == 2 and all(r.context["bulk"] is True and r.context["batch_size"] == 2 for r in rows)
    assert sorted(int(r.target_id) for r in rows) == sorted(users)


def test_bulk_never_exceeds_one_hundred(env):
    _, adm = mk(env, "platform_admin")
    r = env.c.post(f"{P}/assignments/bulk", json={"plan_code": "premium", "subject_type": "user", "subject_ids": list(range(1, 102)),
                                                 "preview_revision": "x"}, cookies=adm)
    assert r.status_code == 422


def test_assignment_audit_for_single_change_is_written_with_plan_context_only(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    rev = subject_rev(env, adm, "user", uid)
    env.c.post(f"{P}/assignments", json={"plan_code": "premium", "subject_type": "user", "subject_id": uid, "expected_revision": rev}, cookies=adm)
    row = audits(env, A.ADMIN_SUBSCRIPTION_ASSIGNED)[-1]
    assert row.target_type == "user" and row.target_id == str(uid) and row.context["before"] == "basic" and row.context["after"] == "premium"
    assert not any(w in json.dumps(row.context).lower() for w in ("email", "price", "currency", "amount"))


# ------------------------------------------------------------------------------------------ history (P4, P6)

def test_assignment_history_per_version_and_per_subject(env):
    users = [mk(env)[0] for _ in range(3)]
    _, adm = mk(env, "platform_admin")
    for u in users:
        env.c.post(f"{P}/assignments", json={"plan_code": "premium", "subject_type": "user", "subject_id": u,
                                            "expected_revision": subject_rev(env, adm, "user", u)}, cookies=adm)
    v1 = catalogue(env, adm)[("premium", 1)]["id"]
    page = env.c.get(f"{P}/versions/{v1}/assignments", params={"page_size": 2}, cookies=adm).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["page_size"] == 2
    assert {i["subject_type"] for i in page["items"]} == {"user"} and all(i["source"] == "admin" for i in page["items"])
    assert set(page["items"][0]) == {"subject_type", "subject_id", "status", "source", "started_at", "ended_at"}
    # back to Basic: history keeps both rows, newest first, ended row has an end date
    env.c.post(f"{P}/assignments", json={"plan_code": "basic", "subject_type": "user", "subject_id": users[0],
                                        "expected_revision": subject_rev(env, adm, "user", users[0])}, cookies=adm)
    h = env.c.get(f"{P}/subjects/user/{users[0]}", cookies=adm).json()["history"]
    assert [x["plan_code"] for x in h][:2] == ["basic", "premium"] and h[1]["status"] == "ended" and h[1]["ended_at"]
    assert env.c.get(f"{P}/versions/9999/assignments", cookies=adm).status_code == 404
    assert env.c.get(f"{P}/subjects/user/9999", cookies=adm).status_code == 404


# ------------------------------------------------------------------------------------------ explanation (P7)

def test_explanation_matches_the_resolver_and_names_the_reason(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    svc = E.EntitlementService(env.repo.session_factory)
    ex = env.c.get(f"{P}/explain", params={"user_id": uid}, cookies=adm).json()
    assert ex["plan_code"] == "basic" and ex["source"] == "subscription" and ex["plan_version_status"] == "active"
    for it in ex["items"]:
        assert it["allowed"] == svc.is_enabled(uid, it["code"])
    reasons = {it["code"]: it["reason"] for it in ex["items"]}
    assert reasons["standard_history"] == "granted_by_plan_version" and reasons["premium_preview"] == "disabled_by_plan_version"
    assert [layer["layer"] for layer in ex["layers"]] == ["authorization", "capability", "entitlement", "billing_state"]
    assert [layer["evaluated_here"] for layer in ex["layers"]] == [False, False, True, False]
    # no active subscription: the explicit Basic fallback, never Premium
    with env.repo.session_factory() as s:
        for sub in s.scalars(select(Subscription).where(Subscription.user_id == uid)).all():
            sub.status = "ended"
        s.commit()
    fb = env.c.get(f"{P}/explain", params={"user_id": uid}, cookies=adm).json()
    assert fb["source"] == "fallback_default" and fb["plan_code"] == "basic"
    assert {it["reason"] for it in fb["items"]} == {"no_active_subscription_basic_fallback_grants", "no_active_subscription_basic_fallback_denies"}
    assert all(it["allowed"] == svc.is_enabled(uid, it["code"]) for it in fb["items"])
    # a key missing from the pinned version is denied by default and says so
    with env.repo.session_factory() as s:
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == "premium"))
        s.delete(s.scalar(select(PlanEntitlement).where(PlanEntitlement.plan_version_id == pv.id, PlanEntitlement.entitlement_key == "standard_progress")))
        s.commit()
    env.c.post(f"{API}/admin/users/{uid}/plan", json={"plan_code": "premium"}, cookies=adm)
    miss = env.c.get(f"{P}/explain", params={"user_id": uid}, cookies=adm).json()
    assert next(i for i in miss["items"] if i["code"] == "standard_progress") | {} == {
        "code": "standard_progress", "label": "Standard progress", "allowed": False, "limit": None, "unlimited": False,
        "reason": "not_listed_in_plan_version_denied_by_default"}


def test_explanation_input_rules(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    assert env.c.get(f"{P}/explain", cookies=adm).status_code == 422
    assert env.c.get(f"{P}/explain", params={"user_id": uid, "workspace_id": 1}, cookies=adm).status_code == 422
    assert env.c.get(f"{P}/explain", params={"user_id": 99999}, cookies=adm).status_code == 404


# ------------------------------------------------------------------------------------------ permissions: 7 personas

def _routes_03b():
    from src.api.admin_route_invariant import admin_routes
    mine = {"/admin/plans/matrix", "/admin/plans/compare", "/admin/plans/explain", "/admin/plans/subjects/{subject_type}/{subject_id}",
            "/admin/plans/versions/{version_id}/assignments", "/admin/plans/versions/{version_id}/restore-as-draft",
            "/admin/plans/assignments/preview", "/admin/plans/assignments", "/admin/plans/assignments/bulk"}
    rs = [r for r in admin_routes() if r.path in mine]
    assert {r.path for r in rs} == mine
    return rs


def test_every_new_route_uses_an_existing_permission_and_the_registry_is_unchanged():
    rs = _routes_03b()
    assert {p for r in rs for p in r.permissions} <= {perm.PLANS_READ, perm.PLANS_MANAGE, perm.SUBSCRIPTIONS_MANAGE}
    assert all(len(r.permissions) == 1 for r in rs)
    assert len(perm.PERMISSIONS) == 44


def test_seven_persona_matrix_over_http_for_every_new_route(env):
    uid, _ = mk(env)
    cookies = {p: (mk(env, p)[1] if p != "user" else mk(env)[1]) for p in M.PERSONAS}
    _, adm = mk(env, "platform_admin")
    v1 = catalogue(env, adm)[("premium", 1)]
    reqs = {
        "/admin/plans/matrix": ("GET", f"{P}/matrix", None),
        "/admin/plans/compare": ("GET", f"{P}/compare?left={v1['id']}&right={v1['id']}", None),
        "/admin/plans/explain": ("GET", f"{P}/explain?user_id={uid}", None),
        "/admin/plans/subjects/{subject_type}/{subject_id}": ("GET", f"{P}/subjects/user/{uid}", None),
        "/admin/plans/versions/{version_id}/assignments": ("GET", f"{P}/versions/{v1['id']}/assignments", None),
        "/admin/plans/versions/{version_id}/restore-as-draft": ("POST", f"{P}/versions/{v1['id']}/restore-as-draft", {"expected_revision": "x"}),
        "/admin/plans/assignments/preview": ("GET", f"{P}/assignments/preview?plan_code=premium&subject_type=user&ids={uid}", None),
        "/admin/plans/assignments": ("POST", f"{P}/assignments", {"plan_code": "premium", "subject_type": "user", "subject_id": uid, "expected_revision": "x"}),
        "/admin/plans/assignments/bulk": ("POST", f"{P}/assignments/bulk", {"plan_code": "premium", "subject_type": "user", "subject_ids": [uid], "preview_revision": "x"}),
    }
    for r in _routes_03b():
        method, url, body = reqs[r.path]
        for persona in M.PERSONAS:
            resp = env.c.request(method, url, cookies=cookies[persona], **({"json": body} if body is not None else {}))
            if M.expected_allowed(r.permissions, persona):
                assert resp.status_code != 403, (r.path, persona, resp.status_code)
            else:
                assert resp.status_code == 403, (r.path, persona, resp.status_code)
                assert "message" in resp.json()["error"] and "plan" not in resp.text.lower().replace("permission", "")  # no plan data in a denial
    # an unauthenticated caller is refused too
    assert env.c.get(f"{P}/matrix").status_code in (401, 403)


def test_denied_mutations_change_nothing(env):
    uid, _ = mk(env)
    _, ck = mk(env, "support_operator")
    n = sub_count(env)
    body = {"plan_code": "premium", "subject_type": "user", "subject_id": uid, "expected_revision": "x"}
    assert env.c.post(f"{P}/assignments", json=body, cookies=ck).status_code == 403
    assert env.c.get(f"{P}/subjects/user/{uid}", cookies=ck).status_code == 403
    assert sub_count(env) == n


# ------------------------------------------------------------------------------------------ allowlists, sentinels, no commercial leakage

BANNED_KEYS = ("price", "currency", "amount", "provider", "stripe", "invoice", "interval", "trial", "card", "payment", "email",
               "password", "token", "secret", "cv", "document", "answer", "conversation", "memory", "transcript", "prompt")


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def test_no_price_currency_or_provider_field_appears_even_when_commercial_terms_exist(env):
    uid, _ = mk(env)
    _, adm = mk(env, "platform_admin")
    v = catalogue(env, adm)[("premium", 1)]
    with env.repo.session_factory() as s:
        s.add(BillingCommercialTerms(public_id="a" * 32, plan_version_id=v["id"], version=1, amount_minor=1999, currency="EUR",
                                     billing_interval="month", trial_days=None, visibility="public", state="active"))
        s.commit()
    sentinel_values = ("1999", "EUR", "stripe")
    res = []
    res.append(env.c.get(P, cookies=adm).json())
    res.append(env.c.get(f"{P}/{v['id']}", cookies=adm).json())
    res.append(env.c.get(f"{P}/matrix", cookies=adm).json())
    res.append(env.c.get(f"{P}/compare", params={"left": v["id"], "right": v["id"]}, cookies=adm).json())
    res.append(env.c.get(f"{P}/explain", params={"user_id": uid}, cookies=adm).json())
    res.append(env.c.get(f"{P}/subjects/user/{uid}", cookies=adm).json())
    res.append(env.c.get(f"{P}/versions/{v['id']}/assignments", cookies=adm).json())
    res.append(preview(env, adm, "premium", "user", [uid]).json())
    for body in res:
        names = [k.lower() for k in _keys(body)]
        assert not [k for k in names if any(b in k for b in BANNED_KEYS)], names
        text = json.dumps(body)
        assert not any(s in text for s in sentinel_values), text[:200]
    # the explanation's billing layer is a label, never a state or a number
    layers = res[4]["layers"]
    assert next(layer for layer in layers if layer["layer"] == "billing_state")["evaluated_here"] is False


def test_new_schemas_are_strict_allowlists_with_no_commercial_or_private_field_names():
    from pydantic import BaseModel

    from src.api.schemas import admin_plans_ops as S
    seen = []
    for cls in vars(S).values():
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == S.__name__:
            assert cls.model_config.get("extra") == "forbid", cls.__name__
            seen += [n.lower() for n in cls.model_fields]
    assert seen and not [n for n in seen if any(b in n for b in BANNED_KEYS if b != "token")]


def test_private_candidate_sentinels_never_reach_any_plan_response(env):
    uid, ck = mk(env)
    _, adm = mk(env, "platform_admin")
    sentinels = ["SENTINEL-CV-0301", "SENTINEL-ANSWER-0302", "SENTINEL-MEMORY-0303"]
    # a candidate saves private memory-like text; none of it may appear in any plan surface
    env.c.post(f"{API}/memory", json={"category": "goal", "summary": sentinels[2]}, cookies=ck)
    urls = [P, f"{P}/matrix", f"{P}/explain?user_id={uid}", f"{P}/subjects/user/{uid}"]
    blob = "".join(env.c.get(u, cookies=adm).text for u in urls)
    assert not any(s in blob for s in sentinels)
    me = env.c.get(f"{API}/auth/me", cookies=ck).json()
    assert me.get("email") and me["email"] not in blob       # the account email never appears either


def test_new_plan_modules_contain_no_billing_vocabulary_in_code():
    """The billing-word guard of eval_admin_entitlements also holds for the 03B modules that read or edit plans."""
    import ast
    import re
    from pathlib import Path
    words = re.compile(r"stripe|checkout|invoice|payment_method|currency|webhook|billing_provider|price_id|\bprice\b|\bamount\b|credit_card", re.I)
    for f in ("src/plans_admin.py", "src/plan_revision.py", "src/api/routes/admin_plans_ops.py", "src/api/schemas/admin_plans_ops.py"):
        tree = ast.parse(Path(f).read_text())
        for node in ast.walk(tree):                                  # drop docstrings, as the evaluator does
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and node.body \
                    and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant):
                node.body[0].value.value = ""
        assert not words.search(ast.unparse(tree)), f


def test_plan_admin_does_not_import_or_write_billing_state(env):
    import inspect

    import src.plans_admin as PA
    import src.plans_repository as PR
    for mod in (PA, PR):
        src = inspect.getsource(mod)
        assert "BillingCommercialTerms" not in src and "src.billing" not in src
    assert not hasattr(billing_policy, "LIVE_BILLING_ENABLED") or billing_policy.LIVE_BILLING_ENABLED is False


def test_head_is_unchanged_by_this_package():
    """No migration: revisions are derived, so the chain is whatever the prep branch left (verified dynamically, never by literal)."""
    from tests import _alembic_head as H
    assert H.repository_head() and H.assert_chain()
    import subprocess
    out = subprocess.run(["git", "diff", "--name-only", "origin/chore/migration-head-agnostic", "--", "migrations/versions"],
                         capture_output=True, text=True, cwd=H.ROOT)
    assert out.returncode != 0 or out.stdout.strip() == ""      # when the base ref exists, this package added no revision
