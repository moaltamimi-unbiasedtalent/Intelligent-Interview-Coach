"""W12.4D-P3: server-provided access metadata for the candidate experience, and the bounded shared-link correction. FULLY OFFLINE over the real application with an
isolated database. The rollout gates are code constants that are OFF; tests flip them on isolated module attributes only. Nothing here is a Stripe fixture."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from src.application import history_access as HA
from src.persistence import Interview, PlanVersion, ShareGrant, Subscription
from tests._auth_factories import cookies_for
from tests.test_sharing_p6_5 import _setup, _uid

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
H = "/api/v1/history/interviews"


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(HA, "HISTORY_RESTRICTIONS_ENFORCED", True)


def seed(repo, uid, n):
    ids = []
    for i in range(n):
        payload = {"configuration": {"target_role": f"Role {i}"}, "mode": "text", "status": "completed",
                   "questions": [{"position": 0, "canonical_question": f"Q{i}", "question_type": "behavioural", "difficulty": "easy",
                                  "answer": {"text": f"A{i}", "evaluation": {"overall_score": 60 + i, "improvement_areas": [f"area{i}"]}, "timing_metrics": None}}],
                   "report": {"report": {"summary": f"R{i}"}, "usage": None, "cost_usd": None}}
        iid = repo.save_interview(uid, payload, source_session_id=f"p3-{uid}-{i}")
        with repo.session_factory() as s:
            s.execute(update(Interview).where(Interview.id == iid).values(created_at=BASE + timedelta(days=i)))
            s.commit()
        ids.append(iid)
    return ids


def set_plan(repo, uid, plan):
    with repo.session_factory() as s:
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.status == "active"))
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == plan, PlanVersion.status == "active"))
        sub.plan_version_id = pv.id
        s.commit()


def test_access_metadata_is_unrestricted_while_the_gate_is_disabled():
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        seed(repo, uid, 6)
        body = c.get(H, cookies=cookies_for(a)).json()
        assert len(body["interviews"]) == 6 and body["access"] == {"restricted": False, "window": None, "hidden_count": 0}
        prog = c.get("/api/v1/progress", cookies=cookies_for(a)).json()
        assert prog["interviews_completed"] == 6 and prog["access"] == {"restricted": False, "window": None}
    finally:
        c.__exit__(None, None, None)


def test_access_metadata_tells_a_restricted_caller_how_many_are_outside_the_view_without_any_content(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        ids = seed(repo, uid, 6)
        body = c.get(H, cookies=cookies_for(a)).json()
        assert [r["id"] for r in body["interviews"]] == list(reversed(ids))[:3]
        assert body["access"] == {"restricted": True, "window": 3, "hidden_count": 3}
        assert all("Role 0" not in str(r) for r in body["interviews"])                      # nothing from the hidden records
        prog = c.get("/api/v1/progress", cookies=cookies_for(a)).json()
        assert prog["access"] == {"restricted": True, "window": 3} and prog["interviews_completed"] == 3
        set_plan(repo, uid, "premium")
        full = c.get(H, cookies=cookies_for(a)).json()
        assert len(full["interviews"]) == 6 and full["access"] == {"restricted": False, "window": None, "hidden_count": 0}
        assert c.get("/api/v1/progress", cookies=cookies_for(a)).json()["access"] == {"restricted": False, "window": None}
    finally:
        c.__exit__(None, None, None)


def test_a_forged_plan_value_cannot_change_the_server_metadata(on):
    c, repo, a, *_ = _setup()
    try:
        seed(repo, _uid(c, a), 5)
        r = c.get(H, cookies=cookies_for(a), headers={"x-plan": "premium"}, params={"plan": "premium"})
        assert r.json()["access"]["restricted"] is True and len(r.json()["interviews"]) == 3
    finally:
        c.__exit__(None, None, None)


def test_a_share_never_exposes_an_interview_outside_the_owners_current_window_and_is_restored_not_recreated(monkeypatch):
    c, repo, a, b, m, adm, wid = _setup()
    try:
        owner = _uid(c, a)
        ids = seed(repo, owner, 5)
        old, newest = ids[0], ids[-1]
        set_plan(repo, owner, "premium")
        monkeypatch.setattr(HA, "HISTORY_RESTRICTIONS_ENFORCED", True)
        share = {"workspace_id": wid, "resource_type": "interview_report"}
        assert c.post("/api/v1/shares", json={**share, "resource_id": str(old)}, cookies=cookies_for(a)).status_code == 200      # shared while Premium
        assert c.post("/api/v1/shares", json={**share, "resource_id": str(newest)}, cookies=cookies_for(a)).status_code == 200
        read = lambda rid, who=b: c.get(f"/api/v1/shares/resource/interview_report/{rid}", cookies=cookies_for(who)).status_code  # noqa: E731
        assert read(old) == 200 and read(newest) == 200
        set_plan(repo, owner, "basic")                                                                                           # the owner downgrades
        assert read(old) == 404                                                                                                  # the share no longer exposes a restricted interview
        assert read(newest) == 200                                                                                               # the latest three stay shareable and readable
        with repo.session_factory() as s:
            grants = s.scalars(select(ShareGrant).where(ShareGrant.resource_id == str(old))).all()
        assert len(grants) == 1 and grants[0].status == "active"                                                                  # NOT deleted or revoked by the downgrade
        set_plan(repo, owner, "premium")
        assert read(old) == 200                                                                                                  # restored with no new share and no data operation
        assert read(old, m) == 404                                                                                               # a non-member still cannot read it
        set_plan(repo, owner, "basic")
        monkeypatch.setattr(HA, "HISTORY_RESTRICTIONS_ENFORCED", False)
        assert read(old) == 200                                                                                                  # gate disabled: the existing contract is unchanged
    finally:
        c.__exit__(None, None, None)


def test_revocation_still_removes_access_whatever_the_window(on):
    c, repo, a, b, m, adm, wid = _setup()
    try:
        owner = _uid(c, a)
        newest = seed(repo, owner, 2)[-1]
        r = c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report", "resource_id": str(newest)}, cookies=cookies_for(a))
        assert r.status_code == 200
        assert c.delete(f"/api/v1/shares/{r.json()['share_id']}", cookies=cookies_for(a)).status_code == 200
        assert c.get(f"/api/v1/shares/resource/interview_report/{newest}", cookies=cookies_for(b)).status_code == 404
    finally:
        c.__exit__(None, None, None)


def test_rollout_gates_and_billing_gates_stay_off():
    from src import ai_protection as AP
    from src.application import model_profile_access as MP
    from src.billing import policy as P
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PROVIDER_READS_AUTHORIZED,
            P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 6
    assert AP.AI_COST_LIMITS_ENFORCED is False and HA.HISTORY_RESTRICTIONS_ENFORCED is False and MP.MODEL_PROFILE_ENFORCED is False
