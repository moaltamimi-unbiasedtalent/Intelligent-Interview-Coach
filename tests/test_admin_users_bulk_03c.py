"""03C bulk Admin user actions (OD-BULK-ACTIONS provisional): force sign-out and expire verification only. Preview binding, partial failure, audit atomicity,
idempotency, protection rules, concurrency, rate limit, pause, privacy sentinels and the 7-persona matrix. Real isolated SQLite, offline."""

from __future__ import annotations

import itertools
import json
import threading

import pytest
from sqlalchemy import select

from src.admin_users import bulk as B
from src.admin_users.guards import AdminForbidden
from src.api.rate_limit import POLICIES
from src.api.schemas import admin_users_bulk as S
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application import pause
from src.persistence import AuditEvent, AuthSession, AuthToken, User
from tests import _admin_matrix as M
from tests._auth_factories import login_token
from tests.test_admin_foundation_w10_1 import PW, Env
from tests.test_admin_users_03c import BANNED, H

API = "/api/v1"
BASE = f"{API}/admin/users/bulk"
ACTIONS = ("force-signout", "expire-verification")
_SEQ = itertools.count(1)


@pytest.fixture()
def env():
    e = Env()
    e.mail = None
    yield e
    e.close()


@pytest.fixture()
def h(env):
    return H(env)


class Bulk:
    """Preview/execute helpers around the 03C harness."""

    def __init__(self, h: H):
        self.h = h

    def preview(self, ck, action, ids):
        return self.h.c.get(f"{BASE}/{action}/preview", params={"ids": ",".join(str(i) for i in ids)}, cookies=ck)

    def run(self, ck, action, ids, *, rev=None, reason="operator review", key=None):
        if rev is None:
            rev = self.preview(ck, action, ids).json()["preview_revision"]
        body = {"account_ids": list(ids), "preview_revision": rev, "reason": reason}
        return self.h.c.post(f"{BASE}/{action}/execute", json=body, cookies=ck, headers={"Idempotency-Key": key or f"auto-key-{next(_SEQ)}"})

    def live(self, uid) -> int:
        with self.h.sf() as s:
            return len(s.scalars(select(AuthSession).where(AuthSession.user_id == uid, AuthSession.revoked_at.is_(None))).all())

    def audit(self, *types):
        with self.h.sf() as s:
            return s.scalars(select(AuditEvent).where(AuditEvent.event_type.in_(types)).order_by(AuditEvent.id)).all()

    def uid(self, ck) -> int:
        return self.h.c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]


@pytest.fixture()
def b(h):
    return Bulk(h)


# ------------------------------------------------------------------------------------------------- registry, routes, matrix
def test_registry_unchanged_and_only_the_two_allow_listed_actions_exist():
    assert len(perm.PERMISSIONS) == 44
    rs = {(r.methods[0], r.path): r for r in M.routes() if r.path.startswith("/admin/users/bulk/")}
    assert set(rs) == {(m, f"/admin/users/bulk/{a}/{k}") for a in ACTIONS for m, k in (("GET", "preview"), ("POST", "execute"))}
    single = {r.path.rsplit("/", 1)[1]: r for r in M.routes() if r.path.startswith("/admin/users/{user_id}/actions/")}
    for (_, path), r in rs.items():
        assert r.permissions == single[path.split("/")[4]].permissions          # exactly the permission of the single-user action
        assert r.permissions <= perm.PERMISSION_SET
    assert set(B.ACTIONS) == set(ACTIONS)
    assert not set(B.ACTIONS) & set(B.NOT_OFFERED)


def test_seven_persona_matrix_for_preview_and_execute(h, b):
    uid, _, _ = h.mk()
    cookies = {p: (h.mk(p)[2] if p != "user" else h.mk()[2]) for p in M.PERSONAS}
    for action in ACTIONS:
        route = next(r for r in M.routes() if r.path == f"/admin/users/bulk/{action}/preview")
        for persona in M.PERSONAS:
            p = b.preview(cookies[persona], action, [uid])
            x = h.c.post(f"{BASE}/{action}/execute", json={"account_ids": [uid], "preview_revision": "0" * 16, "reason": "matrix probe"},
                         cookies=cookies[persona], headers={"Idempotency-Key": f"matrix-{action}-{persona}"})
            if M.expected_allowed(route.permissions, persona):
                assert p.status_code == 200, (action, persona, p.status_code)
                assert x.status_code == 409, (action, persona, x.status_code, x.text)     # authorised, stopped by the deliberately stale preview
            else:
                assert p.status_code == 403 and x.status_code == 403, (action, persona, p.status_code, x.status_code)
    assert h.c.get(f"{BASE}/force-signout/preview", params={"ids": "1"}).status_code in (401, 403)
    assert h.c.post(f"{BASE}/force-signout/execute", json={"account_ids": [1], "preview_revision": "0" * 16, "reason": "abc"},
                    headers={"Idempotency-Key": "anon-key-1"}).status_code in (401, 403)


# ------------------------------------------------------------------------------------------------- preview: counts only
def test_preview_returns_counts_and_reason_counts_only(h, b):
    _, admin_email, admin = h.mk("platform_admin")
    admin_id = b.uid(admin)
    u1, e1, _ = h.mk()
    u2, e2, _ = h.mk()
    quiet, eq, _ = h.mk()
    h.act(admin, quiet, "force-signout")                      # nothing left to revoke
    before = len(b.audit(A.ADMIN_USER_BULK_ACTION, A.ADMIN_USER_BULK_SUBJECT))
    r = b.preview(admin, "force-signout", [u1, u2, quiet, admin_id, 99999999, u1])
    assert r.status_code == 200
    body = r.json()
    assert body["requested"] == 6 and body["unique"] == 5 and body["eligible"] == 2 and body["excluded"] == 3
    assert body["excluded_by_reason"] == {"self": 1, "higher_authority": 0, "last_active_platform_admin": 0, "not_found": 1, "no_live_sessions": 1}
    assert body["max_batch"] == 100 and len(body["preview_revision"]) == 16
    for secret in (e1, e2, eq, admin_email, "@"):
        assert secret not in r.text
    assert set(body) == set(S.BulkPreview.model_fields)
    assert b.live(u1) == 1 and b.live(u2) == 1                 # a preview never changes anything
    assert len(b.audit(A.ADMIN_USER_BULK_ACTION, A.ADMIN_USER_BULK_SUBJECT)) == before


def test_preview_input_validation(h, b):
    _, _, admin = h.mk("platform_admin")
    assert h.c.get(f"{BASE}/force-signout/preview", params={"ids": "a,b"}, cookies=admin).status_code == 422
    assert h.c.get(f"{BASE}/force-signout/preview", params={"ids": "0"}, cookies=admin).status_code == 422
    assert b.preview(admin, "force-signout", list(range(1, 102))).status_code == 422
    assert h.c.get(f"{BASE}/deactivate/preview", params={"ids": "1"}, cookies=admin).status_code in (404, 405, 422)       # not offered: no such route


def test_schemas_carry_no_banned_field_names():
    for model in (S.BulkPreview, S.BulkResult, S.BulkExecuteBody):
        assert model.model_config.get("extra") == "forbid"
        for name in model.model_fields:
            assert not any(x in name.lower() for x in BANNED), name


# ------------------------------------------------------------------------------------------------- execute
def test_force_signout_applies_audits_each_subject_and_one_batch_row(h, b):
    _, _, admin = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(3)]
    r = b.run(admin, "force-signout", ids, reason="suspected shared device")
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["status"], out["applied"], out["skipped"], out["failed"], out["replayed"]) == ("complete", 3, 0, 0, False)
    assert set(out) == set(S.BulkResult.model_fields)
    assert all(b.live(i) == 0 for i in ids)
    subj = b.audit(A.ADMIN_SESSIONS_REVOKED)
    assert sorted(int(e.target_id) for e in subj) == sorted(ids)
    assert all(e.context["bulk"] is True and e.context["batch_id"] == out["batch_id"] and e.context["reason"] == "suspected shared device" for e in subj)
    batch = b.audit(A.ADMIN_USER_BULK_ACTION)
    assert len(batch) == 1 and batch[0].context["applied"] == 3 and batch[0].context["action"] == "force-signout"
    blob = json.dumps([(e.context, e.target_id) for e in b.audit(A.ADMIN_SESSIONS_REVOKED, A.ADMIN_USER_BULK_ACTION)])
    assert "@" not in blob and "http" not in blob


def test_expire_verification_applies_and_skips_accounts_without_links(h, b):
    _, _, admin = h.mk("platform_admin")
    with_link, no_link = h.mk()[0], h.mk()[0]
    assert h.act(admin, no_link, "expire-verification").status_code == 200        # registration issued a link; this account has none left
    out = b.run(admin, "expire-verification", [with_link, no_link]).json()
    assert (out["status"], out["applied"], out["skipped"], out["skipped_by_reason"]) == ("partial", 1, 1, {"no_pending_verification": 1})
    with h.sf() as s:
        assert s.scalar(select(AuthToken).where(AuthToken.user_id == with_link, AuthToken.consumed_at.is_(None))) is None
    assert [e.result for e in b.audit(A.ADMIN_USER_BULK_SUBJECT)] == ["skipped"]
    assert [int(e.target_id) for e in b.audit(A.ADMIN_USER_VERIFICATION_EXPIRED) if e.context.get("bulk")] == [with_link]


def test_body_validation_is_strict(h, b):
    _, _, admin = h.mk("platform_admin")
    u = h.mk()[0]
    rev = b.preview(admin, "force-signout", [u]).json()["preview_revision"]
    ok = {"account_ids": [u], "preview_revision": rev, "reason": "valid reason"}
    hdr = {"Idempotency-Key": "strict-body-1"}

    def post(body, headers=hdr):
        return h.c.post(f"{BASE}/force-signout/execute", json=body, cookies=admin, headers=headers)

    assert post({**ok, "reason": "ab"}).status_code == 422
    assert post({**ok, "reason": "x" * 201}).status_code == 422
    assert post({k: v for k, v in ok.items() if k != "reason"}).status_code == 422
    assert post({k: v for k, v in ok.items() if k != "preview_revision"}).status_code == 422
    assert post({**ok, "account_ids": []}).status_code == 422
    assert post({**ok, "account_ids": list(range(1, 102))}).status_code == 422          # hard cap 100
    assert post({**ok, "account_ids": [0]}).status_code == 422
    assert post({**ok, "extra": 1}).status_code == 422
    assert post(ok, headers={}).status_code == 422                                      # Idempotency-Key is mandatory
    assert post(ok, headers={"Idempotency-Key": "short"}).status_code == 422
    assert post(ok, headers={"Idempotency-Key": "bad key with spaces!"}).status_code == 422
    assert b.live(u) == 1
    assert post(ok).status_code == 200 and b.live(u) == 0


def test_one_hundred_subjects_are_accepted_and_missing_ones_are_skipped_not_failed(h, b):
    _, _, admin = h.mk("platform_admin")
    r = b.run(admin, "force-signout", list(range(2_000_000, 2_000_100)))
    assert r.status_code == 200
    assert r.json()["skipped_by_reason"] == {"not_found": 100} and r.json()["status"] == "none_applied" and r.json()["failed"] == 0


def test_stale_preview_is_refused_with_409_and_nothing_is_applied(h, b):
    _, _, admin = h.mk("platform_admin")
    u1, e1, _ = h.mk()
    u2 = h.mk()[0]
    rev = b.preview(admin, "force-signout", [u1, u2]).json()["preview_revision"]
    login_token(h.c, e1, PW)                                   # a new session after the preview changes the account revision
    r = b.run(admin, "force-signout", [u1, u2], rev=rev)
    assert r.status_code == 409
    assert b.live(u1) == 2 and b.live(u2) == 1
    assert b.audit(A.ADMIN_USER_BULK_ACTION) == []
    assert b.run(admin, "force-signout", [u1, u2]).status_code == 200      # a fresh preview works
    other = b.preview(admin, "expire-verification", [u1]).json()["preview_revision"]
    assert b.run(admin, "force-signout", [u1], rev=other).status_code == 409      # a token from another action never applies


# ------------------------------------------------------------------------------------------------- idempotency
def test_idempotent_replay_returns_the_first_result_and_changes_nothing(h, b):
    _, _, admin = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(2)]
    rev = b.preview(admin, "force-signout", ids).json()["preview_revision"]
    first = b.run(admin, "force-signout", ids, rev=rev, key="replay-key-0001")
    assert first.status_code == 200
    rows_before = len(b.audit(A.ADMIN_SESSIONS_REVOKED, A.ADMIN_USER_BULK_SUBJECT, A.ADMIN_USER_BULK_ACTION))
    again = b.run(admin, "force-signout", ids, rev=rev, key="replay-key-0001")
    assert again.status_code == 200
    a, f = again.json(), first.json()
    assert a["replayed"] is True and f["replayed"] is False
    assert {k: v for k, v in a.items() if k != "replayed"} == {k: v for k, v in f.items() if k != "replayed"}
    assert len(b.audit(A.ADMIN_SESSIONS_REVOKED, A.ADMIN_USER_BULK_SUBJECT, A.ADMIN_USER_BULK_ACTION)) == rows_before
    clash = b.run(admin, "force-signout", ids[:1], rev=rev, key="replay-key-0001")       # same key, different request: refused, never a silent replay
    assert clash.status_code == 409


def test_idempotency_is_scoped_to_the_actor(h, b):
    _, _, a1 = h.mk("platform_admin")
    _, _, a2 = h.mk("platform_admin")
    u = h.mk()[0]
    assert b.run(a1, "force-signout", [u], key="shared-key-0001").json()["replayed"] is False
    again = b.run(a2, "force-signout", [u], key="shared-key-0001")            # another administrator's key never replays someone else's batch
    assert again.status_code == 200 and again.json()["replayed"] is False and again.json()["applied"] == 0


# ------------------------------------------------------------------------------------------------- protection
def test_self_is_excluded_and_a_peer_admin_is_eligible(h, b):
    _, _, admin = h.mk("platform_admin")
    admin_id = b.uid(admin)
    peer = h.mk("platform_admin")[0]
    plain = h.mk()[0]
    out = b.run(admin, "force-signout", [admin_id, peer, plain]).json()
    assert out["applied"] == 2 and out["skipped_by_reason"] == {"self": 1}
    assert b.live(admin_id) >= 1                                          # my own session is untouched


def test_higher_authority_accounts_are_excluded(h, b):
    _, _, admin = h.mk("platform_admin")
    admin_id = b.uid(admin)
    peer_admin = h.mk("platform_admin")[0]
    _, _, support = h.mk("security_privacy_admin")           # holds sessions.revoke, but only a slice of platform_admin's authority
    support_id = b.uid(support)
    plain = h.mk()[0]
    ids = [admin_id, peer_admin, support_id, plain]
    pv = b.preview(support, "force-signout", ids).json()
    assert pv["excluded_by_reason"]["higher_authority"] == 2 and pv["excluded_by_reason"]["self"] == 1 and pv["eligible"] == 1
    live = (b.live(admin_id), b.live(peer_admin))
    out = b.run(support, "force-signout", ids).json()
    assert out["applied"] == 1 and out["skipped_by_reason"] == {"higher_authority": 2, "self": 1}
    assert (b.live(admin_id), b.live(peer_admin)) == live and b.live(plain) == 0


def test_last_active_platform_admin_is_excluded_by_the_classifier(h):
    actor_id = h.mk("platform_admin")[0]
    target = h.mk("platform_admin")[0]
    svc = B.BulkUserActions(h.sf)
    with h.sf() as s:
        actor, victim = s.get(User, actor_id), s.get(User, target)
        # A peer admin implies two active admins, so the rule is structurally redundant; it is still evaluated explicitly and must fire at one.
        assert svc.classify(s, B.ACTIONS["force-signout"], actor, victim, 1) == B.LAST_ADMIN
        assert svc.classify(s, B.ACTIONS["force-signout"], actor, victim, 2) is None


def test_acting_administrator_must_be_active(h, b):
    _, _, admin = h.mk("platform_admin")
    admin_id = b.uid(admin)
    u = h.mk()[0]
    with h.sf() as s:
        s.get(User, admin_id).status = "deactivated"
        s.commit()
    svc = B.BulkUserActions(h.sf)
    with pytest.raises(AdminForbidden):
        svc.preview("force-signout", [u], actor_user_id=admin_id)
    with pytest.raises(AdminForbidden):
        svc.execute("force-signout", [u], preview_revision="0" * 16, reason="reason", actor_user_id=admin_id, idempotency_key="inactive-key-1", request_id=None)
    assert b.live(u) == 1


# ------------------------------------------------------------------------------------------------- partial failure and audit atomicity
def test_one_failing_subject_does_not_undo_the_others_and_is_reported(h, b, monkeypatch):
    _, _, admin = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(3)]
    bad = ids[1]
    real = B.ACTIONS["force-signout"]

    def flaky(s, user):
        if user.id == bad:
            raise RuntimeError("boom: internal detail that must never leak")
        return real.apply(s, user)

    monkeypatch.setitem(B.ACTIONS, "force-signout", B.BulkAction(real.code, real.permission, real.event, real.noop, real.has_effect, flaky))
    r = b.run(admin, "force-signout", ids)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["status"], out["applied"], out["failed"], out["failed_by_reason"], out["skipped"]) == ("partial", 2, 1, {"apply_error": 1}, 0)
    assert "boom" not in r.text and "internal detail" not in r.text
    assert b.live(bad) == 1 and b.live(ids[0]) == 0 and b.live(ids[2]) == 0
    rows = {int(e.target_id): e for e in b.audit(A.ADMIN_SESSIONS_REVOKED, A.ADMIN_USER_BULK_SUBJECT)}
    assert rows[bad].result == "failed" and rows[bad].context["reason_code"] == "apply_error" and "boom" not in json.dumps(rows[bad].context)
    assert rows[ids[0]].result == "success"
    assert b.audit(A.ADMIN_USER_BULK_ACTION)[0].context["failed"] == 1


def test_audit_failure_aborts_the_whole_batch(h, b, monkeypatch):
    _, _, admin = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(3)]
    rev = b.preview(admin, "force-signout", ids).json()["preview_revision"]
    real, calls = B._stage, {"n": 0}

    def flaky_stage(s, spec, **kw):
        calls["n"] += 1
        if calls["n"] == 3:                                     # the third subject's audit row cannot be written
            raise RuntimeError("audit store down")
        return real(s, spec, **kw)

    monkeypatch.setattr("src.admin_users.bulk._stage", flaky_stage)
    r = b.run(admin, "force-signout", ids, rev=rev, key="audit-fail-key1")
    assert r.status_code == 503, r.text
    assert all(b.live(i) == 1 for i in ids)                     # nothing applied, not even the two before the failure
    assert b.audit(A.ADMIN_SESSIONS_REVOKED, A.ADMIN_USER_BULK_SUBJECT, A.ADMIN_USER_BULK_ACTION) == []
    monkeypatch.undo()
    ok = b.run(admin, "force-signout", ids, rev=rev, key="audit-fail-key1")     # the failed attempt left no idempotency record: a retry works
    assert ok.status_code == 200 and ok.json()["applied"] == 3 and ok.json()["replayed"] is False


def test_batch_row_failure_also_aborts_everything(h, b, monkeypatch):
    _, _, admin = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(2)]
    real = B._stage

    def fail_batch(s, spec, **kw):
        if spec["event_type"] == A.ADMIN_USER_BULK_ACTION:
            raise RuntimeError("down")
        return real(s, spec, **kw)

    monkeypatch.setattr("src.admin_users.bulk._stage", fail_batch)
    assert b.run(admin, "force-signout", ids).status_code == 503
    assert all(b.live(i) == 1 for i in ids)


# ------------------------------------------------------------------------------------------------- concurrency
def test_two_overlapping_batches_never_apply_a_subject_twice(h, b):
    _, _, admin = h.mk("platform_admin")
    _, _, admin2 = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(4)]
    rev1 = b.preview(admin, "force-signout", ids).json()["preview_revision"]
    rev2 = b.preview(admin2, "force-signout", ids[1:]).json()["preview_revision"]
    results: list = []
    gate = threading.Barrier(2)

    def go(ck, sub, rev, key):
        gate.wait()
        results.append(h.c.post(f"{BASE}/force-signout/execute", json={"account_ids": sub, "preview_revision": rev, "reason": "overlap run"},
                                cookies=ck, headers={"Idempotency-Key": key}))

    ts = [threading.Thread(target=go, args=(admin, ids, rev1, "overlap-key-a1")), threading.Thread(target=go, args=(admin2, ids[1:], rev2, "overlap-key-b1"))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409], [r.text for r in results]          # the loser's preview is stale because the winner changed the shared subjects
    winner = next(r for r in results if r.status_code == 200).json()
    revoked = [i for i in ids if b.live(i) == 0]
    assert len(revoked) == winner["applied"]
    success = sorted(int(e.target_id) for e in b.audit(A.ADMIN_SESSIONS_REVOKED))
    assert success == sorted(revoked) and len(success) == len(set(success))        # exactly one applied row per changed subject, never two
    assert len(b.audit(A.ADMIN_USER_BULK_ACTION)) == 1


def test_two_overlapping_requests_with_the_same_key_yield_one_batch(h, b):
    _, _, admin = h.mk("platform_admin")
    ids = [h.mk()[0] for _ in range(3)]
    rev = b.preview(admin, "force-signout", ids).json()["preview_revision"]
    results: list = []
    gate = threading.Barrier(2)

    def go():
        gate.wait()
        results.append(h.c.post(f"{BASE}/force-signout/execute", json={"account_ids": ids, "preview_revision": rev, "reason": "same key"},
                                cookies=admin, headers={"Idempotency-Key": "same-key-0001"}))

    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert [r.status_code for r in results] == [200, 200]
    assert len({r.json()["batch_id"] for r in results}) == 1 and sorted(r.json()["replayed"] for r in results) == [False, True]
    assert len(b.audit(A.ADMIN_USER_BULK_ACTION)) == 1 and len(b.audit(A.ADMIN_SESSIONS_REVOKED)) == 3


# ------------------------------------------------------------------------------------------------- rate limit and pause
def test_per_batch_rate_limit(h, b):
    assert "admin_bulk_user_actions" in POLICIES
    _, _, admin = h.mk("platform_admin")
    u = h.mk()[0]
    codes = [b.run(admin, "force-signout", [u]).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429
    again = b.run(admin, "force-signout", [u], key="auto-key-first-replay")
    assert again.status_code == 429


def test_replay_does_not_consume_rate_budget(h, b):
    _, _, admin = h.mk("platform_admin")
    u = h.mk()[0]
    rev = b.preview(admin, "force-signout", [u]).json()["preview_revision"]
    assert b.run(admin, "force-signout", [u], rev=rev, key="budget-key-0001").status_code == 200
    assert all(b.run(admin, "force-signout", [u], rev=rev, key="budget-key-0001").json()["replayed"] for _ in range(15))


def test_unreadable_platform_state_refuses_the_batch(h, b, monkeypatch):
    _, _, admin = h.mk("platform_admin")
    u = h.mk()[0]
    rev = b.preview(admin, "force-signout", [u]).json()["preview_revision"]
    svc = pause.PauseService(h.sf)
    monkeypatch.setattr(pause, "_installed", svc)

    def down():
        raise pause.PauseStateUnavailable("down")

    monkeypatch.setattr(svc, "snapshot", down)
    r = b.run(admin, "force-signout", [u], rev=rev)
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_state_unavailable"
    assert b.live(u) == 1
    monkeypatch.undo()
    monkeypatch.setattr(pause, "_installed", svc)
    assert b.run(admin, "force-signout", [u], rev=rev).status_code == 200


# ------------------------------------------------------------------------------------------------- privacy sentinels
def test_no_email_or_secret_in_responses_or_audit(h, b):
    _, admin_email, admin = h.mk("platform_admin")
    u, email, _ = h.mk()
    h.act(admin, u, "resend-verification")
    texts = [b.preview(admin, a, [u, 99999999]).text for a in ACTIONS]
    texts += [b.run(admin, a, [u, 99999999]).text for a in ACTIONS]
    rows = b.audit(A.ADMIN_USER_BULK_ACTION, A.ADMIN_USER_BULK_SUBJECT, A.ADMIN_SESSIONS_REVOKED, A.ADMIN_USER_VERIFICATION_EXPIRED)
    assert rows
    blob = " ".join(texts) + json.dumps([(e.context, e.target_id, e.target_type, e.result) for e in rows])
    for forbidden in (email, admin_email, "@", "password", "cookie", "http"):
        assert forbidden not in blob
    for key in ('"email"', '"token"', '"link"', '"session_id"', '"account_ids"'):
        assert key not in " ".join(texts)
