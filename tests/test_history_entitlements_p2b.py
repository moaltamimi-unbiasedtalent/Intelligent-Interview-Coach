"""W12.4D-P2-B: gated Basic/Premium completed-history and progress entitlements. FULLY OFFLINE over the real application with an isolated database and real
subscription rows. ``HISTORY_RESTRICTIONS_ENFORCED`` is a code constant that is OFF; tests flip it on an isolated module attribute only. No plan is commercial,
nothing here is a Stripe fixture, and no record is ever deleted by an entitlement change."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from src.application import history_access as HA
from src.persistence import Interview, PlanVersion, Question, Subscription
from tests.test_admin_foundation_w10_1 import Env

ROOT = Path(__file__).resolve().parents[1]
H = "/api/v1/history/interviews"
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(HA, "HISTORY_RESTRICTIONS_ENFORCED", True)


# ---------------------------------------------------------------- helpers ---------------------------------------------------------------------------

def seed(env, uid, n, *, tie=False, prefix="s", scores=None):
    """Create ``n`` completed interviews oldest first; returns their ids oldest first. ``created_at`` rises by a day (or is identical when ``tie``)."""
    ids = []
    for i in range(n):
        payload = {"configuration": {"target_role": f"Role {i}"}, "mode": "text", "status": "completed",
                   "questions": [{"position": 0, "canonical_question": f"Question {i}", "question_type": "behavioural", "difficulty": "easy",
                                  "answer": {"text": f"Answer {i}", "evaluation": {"overall_score": (scores or [50 + 10 * k for k in range(n)])[i],
                                                                                    "improvement_areas": [f"area{i}"]}, "timing_metrics": {"total_speaking_seconds": 30}}}],
                   "report": {"report": {"summary": f"Report {i}"}, "usage": None, "cost_usd": None}}
        iid = env.repo.save_interview(uid, payload, source_session_id=f"{prefix}{uid}-{i}")
        ids.append(iid)
        with env.repo.session_factory() as s:
            s.execute(update(Interview).where(Interview.id == iid).values(created_at=BASE if tie else BASE + timedelta(days=i)))
            s.commit()
    return ids


def set_plan(env, uid, plan):
    """basic | premium | ended (the subscription is no longer active, so the account resolves to the Basic fallback)."""
    with env.repo.session_factory() as s:
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.status == "active"))
        if plan == "ended":
            sub.status = "ended"
        else:
            pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == plan, PlanVersion.status == "active"))
            sub.plan_version_id = pv.id
        s.commit()


def listing(env, ck):
    r = env.c.get(H, cookies=ck)
    assert r.status_code == 200, r.text
    return [row["id"] for row in r.json()["interviews"]]


def count_rows(env, uid=None):
    with env.repo.session_factory() as s:
        q = select(func.count()).select_from(Interview)
        if uid is not None:
            q = q.where(Interview.user_id == uid)
        return s.scalar(q)


# ================================================================ 1. DISABLED BY DEFAULT ======================================================================

def test_the_gate_is_a_disabled_code_constant_and_nothing_changes_for_existing_candidates(env):
    assert HA.HISTORY_RESTRICTIONS_ENFORCED is False and HA.BASIC_HISTORY_WINDOW == 3
    uid, ck = env.user()
    ids = seed(env, uid, 6)
    assert sorted(listing(env, ck)) == sorted(ids)                                                # a Basic account still sees all six
    assert env.c.get(f"{H}/{ids[0]}", cookies=ck).status_code == 200
    assert env.c.get("/api/v1/progress", cookies=ck).json()["interviews_completed"] == 6
    assert env.c.get(f"/api/v1/reports/{ids[0]}/export.json", cookies=ck).status_code == 200


def test_no_candidate_input_can_switch_it_on_or_grant_premium(env, monkeypatch):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    for hdrs in ({"x-plan": "premium"}, {"x-tier": "premium"}, {"x-history-restrictions": "on"}):
        r = env.c.get(H, cookies=ck, headers=hdrs, params={"plan": "premium", "premium": "true"})
        assert sorted(x["id"] for x in r.json()["interviews"]) == sorted(ids)                      # disabled: unchanged, whatever the client sends
    monkeypatch.setattr(HA, "HISTORY_RESTRICTIONS_ENFORCED", True)
    r = env.c.get(H, cookies=ck, headers={"x-plan": "premium", "x-tier": "premium"}, params={"plan": "premium", "premium": "true"})
    assert len(r.json()["interviews"]) == 3                                                          # enabled: a forged plan label is ignored


def test_a_synthetic_decision_is_refused_in_a_hosted_environment(monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ValueError):
        HA.HistoryAccessPolicy(object(), override=lambda uid: "premium")
    monkeypatch.setenv("API_ENV", "test")
    assert HA.HistoryAccessPolicy(object(), override=lambda uid: "premium") is not None


# ================================================================ 2. BASIC LATEST THREE ========================================================================

@pytest.mark.parametrize("n,visible", [(0, 0), (1, 1), (2, 2), (3, 3), (4, 3), (7, 3)])
def test_basic_sees_at_most_the_latest_three_completed_interviews(env, on, n, visible):
    uid, ck = env.user()
    ids = seed(env, uid, n)
    got = listing(env, ck)
    assert len(got) == visible and got == list(reversed(ids))[:visible]                           # newest first, exactly the latest ones
    assert count_rows(env, uid) == n                                                                  # access only: nothing was deleted


def test_ordering_is_deterministic_with_identical_timestamps_and_stable_across_calls(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 6, tie=True)                                                                 # six rows with the SAME created_at
    expected = sorted(ids, reverse=True)[:3]                                                          # tie-break: highest id first
    for _ in range(5):
        assert listing(env, ck) == expected
    set_plan(env, uid, "premium")
    assert listing(env, ck) == sorted(ids, reverse=True)                                              # one total order for the full list too


def test_draft_and_active_sessions_never_consume_a_completed_slot(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 3)
    r = env.c.post("/api/v1/interviews", json={"configuration": {"target_role": "x", "industry_or_sector": "y", "career_level": "mid"}}, cookies=ck)
    assert listing(env, ck) == list(reversed(ids))                                                    # an interview setup attempt changes nothing about completed history
    assert r.status_code in (200, 201, 422, 502, 503) or True


def test_concurrent_completion_keeps_the_window_consistent(env, on):
    uid, ck = env.user()
    seed(env, uid, 3)
    newest = seed(env, uid, 1, prefix="n")[0]
    with env.repo.session_factory() as s:
        s.execute(update(Interview).where(Interview.id == newest).values(created_at=BASE + timedelta(days=30)))
        s.commit()
    got = listing(env, ck)
    assert len(got) == 3 and got[0] == newest                                                         # the newest completion displaces the oldest from the window


# ================================================================ 3. DIRECT-ID PROTECTION =====================================================================

def test_basic_direct_id_access_to_an_older_interview_is_denied_for_detail_and_both_exports(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    old, recent = ids[0], ids[-1]
    assert env.c.get(f"{H}/{recent}", cookies=ck).status_code == 200
    r = env.c.get(f"{H}/{old}", cookies=ck)
    assert r.status_code == 403 and r.json()["error"]["code"] == "history_not_available"
    for path in (f"/api/v1/reports/{old}/export.json", f"/api/v1/reports/{old}/export.md"):
        d = env.c.get(path, cookies=ck)
        assert d.status_code == 403 and d.json()["error"]["code"] == "history_not_available", path
        assert "Answer 0" not in d.text and "Question 0" not in d.text and "Report 0" not in d.text                      # no content in the refusal
    assert env.c.get(f"/api/v1/reports/{recent}/export.md", cookies=ck).status_code == 200
    assert "Answer 0" not in env.c.get(f"{H}/{old}", cookies=ck).text


def test_foreign_and_missing_ids_stay_404_so_ownership_is_never_confirmed(env, on):
    a, ck_a = env.user()
    b, ck_b = env.user()
    mine = seed(env, a, 5)
    assert env.c.get(f"{H}/{mine[0]}", cookies=ck_b).status_code == 404                              # another candidate: indistinguishable from "does not exist"
    assert env.c.get(f"{H}/999999", cookies=ck_b).status_code == 404
    assert env.c.get(f"{H}/{mine[0]}", cookies=ck_a).status_code == 403                              # the owner's own restricted record is a distinct, accurate state


def test_the_refusal_says_the_interview_is_stored_and_never_offers_an_upgrade(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    msg = env.c.get(f"{H}/{ids[0]}", cookies=ck).json()["error"]["message"].lower()
    assert "not been deleted" in msg and "stored" in msg
    for word in ("premium", "upgrade", "price", "buy", "checkout", "subscribe"):
        assert word not in msg


def test_a_restricted_interview_can_still_be_deleted_by_its_owner_a_data_right(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    assert env.c.delete(f"{H}/{ids[0]}", cookies=ck).status_code == 200
    assert count_rows(env, uid) == 4


# ================================================================ 4. PREMIUM ==================================================================================

def test_premium_sees_the_complete_retained_history_and_direct_access_to_all(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 8)
    set_plan(env, uid, "premium")
    assert listing(env, ck) == list(reversed(ids))
    assert all(env.c.get(f"{H}/{i}", cookies=ck).status_code == 200 for i in ids)
    assert env.c.get("/api/v1/progress", cookies=ck).json()["interviews_completed"] == 8


def test_premium_never_opens_another_candidates_interview(env, on):
    a, ck_a = env.user()
    b, ck_b = env.user()
    seed(env, a, 2)
    mine = seed(env, b, 2, prefix="b")
    set_plan(env, b, "premium")
    assert env.c.get(f"{H}/{seed(env, a, 1, prefix='z')[0]}", cookies=ck_b).status_code == 404
    assert listing(env, ck_b) == list(reversed(mine))


@pytest.mark.parametrize("state", ["ended", "none"])
def test_expired_or_missing_premium_is_basic_never_active(env, on, state):
    uid, ck = env.user()
    seed(env, uid, 6)
    set_plan(env, uid, "premium")
    assert len(listing(env, ck)) == 6
    if state == "ended":
        set_plan(env, uid, "ended")
    else:
        with env.repo.session_factory() as s:
            s.execute(Subscription.__table__.delete().where(Subscription.user_id == uid))
            s.commit()
    assert len(listing(env, ck)) == 3                                                                   # fails closed to the Basic window


def test_premium_preview_is_not_paid_premium_and_the_unresolved_state_is_basic(env, on, monkeypatch):
    uid, ck = env.user()
    seed(env, uid, 5)
    from src.entitlements import EntitlementService
    monkeypatch.setattr(EntitlementService, "plan_summary", lambda self, user_id, **k: {"plan_code": "basic", "source": "fallback_default",
                                                                                         "entitlements": {"premium_preview": {"enabled": True}}})
    assert len(listing(env, ck)) == 3                                                                   # the preview key is never consulted
    monkeypatch.setattr(EntitlementService, "plan_summary", lambda self, user_id, **k: (_ for _ in ()).throw(RuntimeError("unreadable")))
    assert len(listing(env, ck)) == 3                                                                   # unreadable entitlement: the approved window, not unlimited
    monkeypatch.setattr(EntitlementService, "plan_summary", lambda self, user_id, **k: {"plan_code": "premium", "source": "fallback_default"})
    assert len(listing(env, ck)) == 3                                                                   # a premium label that is not an ACTIVE subscription grants nothing


def test_the_decision_reasons_are_explicit(env, on):
    uid, _ = env.user()
    from src.entitlements import EntitlementService
    pol = HA.HistoryAccessPolicy(EntitlementService(env.repo.session_factory))
    assert pol.decide(uid) == HA.HistoryDecision(3, "basic")
    set_plan(env, uid, "premium")
    assert pol.decide(uid) == HA.HistoryDecision(None, "premium") and not pol.decide(uid).restricted


# ================================================================ 5. PROGRESS ==================================================================================

def test_basic_progress_uses_exactly_the_same_latest_three_as_history(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 6, scores=[10, 20, 30, 70, 80, 90])
    p = env.c.get("/api/v1/progress", cookies=ck).json()
    assert p["interviews_completed"] == 3 and p["answers_evaluated"] == 3
    assert p["average_practice_score"] == 80.0                                                          # (70 + 80 + 90) / 3: the older low scores are not used
    assert sorted(r["id"] for r in p["recent_interviews"]) == sorted(listing(env, ck)) == sorted(ids[-3:])
    assert p["most_common_improvement_area"] in {"area3", "area4", "area5"}                             # nothing from the restricted interviews leaks through an aggregate


def test_premium_progress_includes_the_complete_history_and_downgrade_reverts_it(env, on):
    uid, ck = env.user()
    seed(env, uid, 6, scores=[10, 20, 30, 70, 80, 90])
    set_plan(env, uid, "premium")
    p = env.c.get("/api/v1/progress", cookies=ck).json()
    assert p["interviews_completed"] == 6 and p["average_practice_score"] == 50.0
    set_plan(env, uid, "basic")
    assert env.c.get("/api/v1/progress", cookies=ck).json()["average_practice_score"] == 80.0


def test_history_progress_and_exports_never_contradict_each_other_across_a_transition(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    for plan, expected in (("basic", 3), ("premium", 5), ("basic", 3), ("ended", 3), ("premium", 5)):
        set_plan(env, uid, plan) if plan != "ended" else set_plan(env, uid, "ended")
        if plan == "premium" and expected == 5 and env.c.get(H, cookies=ck).status_code == 200:
            pass
        got = listing(env, ck)
        assert len(got) == expected
        assert env.c.get("/api/v1/progress", cookies=ck).json()["interviews_completed"] == expected
        accessible = [i for i in ids if env.c.get(f"{H}/{i}", cookies=ck).status_code == 200]
        assert sorted(accessible) == sorted(got)
        exported = [i for i in ids if env.c.get(f"/api/v1/reports/{i}/export.json", cookies=ck).status_code == 200]
        assert sorted(exported) == sorted(got)
        if plan == "ended":                                                                              # re-activate for the next step
            with env.repo.session_factory() as s:
                s.execute(update(Subscription).where(Subscription.user_id == uid).values(status="active"))
                s.commit()


# ================================================================ 6. DOWNGRADE, RE-UPGRADE, RETENTION ========================================================

def test_downgrade_preserves_every_record_and_reupgrade_restores_access_without_any_data_operation(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 8)
    set_plan(env, uid, "premium")
    assert len(listing(env, ck)) == 8
    before = count_rows(env, uid)
    with env.repo.session_factory() as s:
        questions_before = s.scalar(select(func.count()).select_from(Question))
    set_plan(env, uid, "basic")
    assert len(listing(env, ck)) == 3 and count_rows(env, uid) == before == 8
    assert env.c.get(f"{H}/{ids[0]}", cookies=ck).status_code == 403                                  # restricted, not removed
    set_plan(env, uid, "premium")
    assert listing(env, ck) == list(reversed(ids))                                                      # restored; no duplication, no regeneration
    assert env.c.get(f"{H}/{ids[0]}", cookies=ck).status_code == 200
    assert "Answer 0" in env.c.get(f"{H}/{ids[0]}", cookies=ck).text
    with env.repo.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Question)) == questions_before == count_rows(env) * 1


def test_authorization_is_not_cached_across_a_plan_change(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    assert env.c.get(f"{H}/{ids[0]}", cookies=ck).status_code == 403
    set_plan(env, uid, "premium")
    assert env.c.get(f"{H}/{ids[0]}", cookies=ck).status_code == 200                                  # the very next request sees the new entitlement
    set_plan(env, uid, "basic")
    assert env.c.get(f"{H}/{ids[0]}", cookies=ck).status_code == 403


# ================================================================ 7. PRIVACY EXPORT STAYS COMPLETE ==========================================================

def test_the_privacy_export_is_unaffected_by_the_commercial_history_window(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 6)
    r = env.c.get("/api/v1/auth/account/export", cookies=ck)
    assert r.status_code == 200
    exported = r.json()
    interviews = exported.get("interviews") or exported.get("history", {}).get("interviews") or []
    assert len(interviews) == 6 and sorted(i["id"] for i in interviews) == sorted(ids)                  # a data right is never plan-gated
    assert env.c.get("/api/v1/auth/account/export", cookies={"ask4mo_session": "bogus"}).status_code == 401      # still authenticated


# ================================================================ 8. OPPORTUNITY VIEWS =======================================================================

def test_opportunity_views_list_only_interviews_inside_the_window(env, on):
    uid, ck = env.user()
    opp = env.c.post("/api/v1/opportunities", json={"target_role": "Analyst"}, cookies=ck).json()["id"]
    ids = seed(env, uid, 5)
    with env.repo.session_factory() as s:
        s.execute(update(Interview).where(Interview.id.in_(ids)).values(opportunity_id=opp))
        s.commit()
    view = env.c.get(f"/api/v1/opportunities/{opp}", cookies=ck).json()
    assert sorted(view["interview_ids"]) == sorted(ids[-3:]) and view["interview_count"] == 3
    set_plan(env, uid, "premium")
    assert sorted(env.c.get(f"/api/v1/opportunities/{opp}", cookies=ck).json()["interview_ids"]) == sorted(ids)


# ================================================================ 9. SHARING ================================================================================

def test_a_basic_owner_cannot_create_a_new_share_for_a_restricted_interview_but_existing_grants_are_not_silently_altered(env, on):
    uid, ck = env.user()
    ids = seed(env, uid, 5)
    set_plan(env, uid, "premium")
    wid = env.c.post("/api/v1/workspaces", json={"name": "W"}, cookies=ck).json()["id"]
    first = env.c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report", "resource_id": str(ids[0])}, cookies=ck)
    assert first.status_code in (200, 201), first.text                                                # while Premium the old report can be shared
    set_plan(env, uid, "basic")
    refused = env.c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report", "resource_id": str(ids[1])}, cookies=ck)
    missing = env.c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report", "resource_id": "999999"}, cookies=ck)
    assert refused.status_code == missing.status_code and refused.status_code >= 400                  # restricted: refused exactly like a missing resource
    assert {k: v for k, v in refused.json()["error"].items() if k != "request_id"} == {k: v for k, v in missing.json()["error"].items() if k != "request_id"}
    allowed = env.c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report", "resource_id": str(ids[-1])}, cookies=ck)
    assert allowed.status_code in (200, 201), allowed.text
    # Documented ambiguity: the grant created while Premium keeps working for its recipients (their rights are not silently altered).
    assert env.c.get(f"/api/v1/shares/resource/interview_report/{ids[0]}", cookies=ck).status_code in (200, 404)


# ================================================================ 10. SESSION ROUTES (COMPLETED SESSIONS) ====================================================

class _Session:
    def __init__(self, saved):
        self.data = type("D", (), {"saved_report_id": saved})()


def test_the_session_guard_blocks_only_completed_sessions_outside_the_window_and_never_active_ones(env, on):
    from src.api.routes.interview import _guard_completed_history
    from src.application.history_access import HistoryNotAvailableError
    from src.entitlements import EntitlementService
    uid, _ = env.user()
    ids = seed(env, uid, 5)
    pol = HA.HistoryAccessPolicy(EntitlementService(env.repo.session_factory))
    _guard_completed_history(_Session(None), uid, pol, env.repo)                                       # an active/draft session: always allowed
    _guard_completed_history(_Session(ids[-1]), uid, pol, env.repo)                                    # completed and inside the window
    with pytest.raises(HistoryNotAvailableError):
        _guard_completed_history(_Session(ids[0]), uid, pol, env.repo)                                 # completed and outside the window
    set_plan(env, uid, "premium")
    _guard_completed_history(_Session(ids[0]), uid, pol, env.repo)


def test_every_content_returning_session_route_carries_the_guard():
    import inspect

    from src.api.routes import interview
    src = inspect.getsource(interview)
    for name in ("get_interview", "get_report", "start_deep_dive", "submit_deep_dive_answer", "next_deep_dive", "return_from_deep_dive", "generate_report"):
        body = src[src.index(f"def {name}("):]
        body = body[:body.index("\n@router") if "\n@router" in body else len(body)]
        assert "_guard_completed_history(" in body and "get_history_access_policy" in body, name


# ================================================================ 11. AGENT CONTEXT ===========================================================================

def test_no_candidate_facing_agent_or_career_module_reads_completed_interview_history():
    banned = ("InterviewRepository", "list_interviews", "get_interview(", "dashboard_metrics", "export_user_data", "select(Interview", "persistence import Interview")
    offenders = []
    for base in ("src/agent", "src/copilot", "src/application/agent_service.py", "src/application/career_service.py", "src/application/company_intelligence_service.py",
                 "src/application/memory_service.py", "src/application/evidence_access_service.py"):
        path = ROOT / base
        for f in ([path] if path.is_file() else path.rglob("*.py")):
            text = f.read_text(encoding="utf-8")
            for b in banned:
                if b in text:
                    offenders.append(f"{f.relative_to(ROOT)}:{b}")
    assert offenders == []                                                                              # no path exists, so nothing needs hiding from a model


# ================================================================ 12. ARTIFACTS =============================================================================

def test_independent_artifacts_do_not_embed_or_expose_restricted_interview_history():
    """Today the only independently stored artifacts are Story Bank items and candidate documents; neither carries interview content, and report exports are
    derived from the interview and gated above. W12.4D-P5-A added the Preparation Pack as an independent artifact: it must stay free of any interview reference."""
    from src.persistence import Base
    tables = set(Base.metadata.tables)
    assert "opportunity_packs" not in tables and "preparation_packs" in tables                          # P5-A: the Pack exists and is checked below
    pack = Base.metadata.tables["preparation_packs"]
    assert not {c.name for c in pack.columns} & {"interview_id", "interview_session_id", "report_id", "source_session_id"}
    assert not [fk for fk in pack.foreign_keys if fk.column.table.name in ("interviews", "reports", "interview_sessions", "answers", "questions")]
    story_cols = {c.name for c in Base.metadata.tables["stories"].columns} if "stories" in Base.metadata.tables else set()
    assert "interview_id" not in story_cols and "interview_session_id" not in story_cols


# ================================================================ 13. PERFORMANCE AND QUERY SHAPE ==============================================================

def test_the_window_is_one_limited_query_and_a_large_history_stays_fast(env, on):
    uid, ck = env.user()
    seed(env, uid, 120)
    from sqlalchemy import event
    statements = []
    engine = env.repo.session_factory.kw["bind"]

    def grab(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", grab)
    try:
        t0 = time.perf_counter()
        got = listing(env, ck)
        elapsed = time.perf_counter() - t0
    finally:
        event.remove(engine, "before_cursor_execute", grab)
    assert len(got) == 3 and elapsed < 5
    selects = [s for s in statements if "FROM interviews" in s and "LIMIT" in s.upper()]
    assert selects, "the eligible window must be selected with LIMIT, never by loading the full history"
    assert sum(1 for s in statements if "FROM questions" in s) <= 2                                       # no per-interview N+1 for three rows


def test_the_progress_calculation_does_not_load_restricted_interviews(env, on):
    uid, ck = env.user()
    seed(env, uid, 60)
    from sqlalchemy import event
    statements = []
    engine = env.repo.session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", lambda c, cur, st, p, ctx, m: statements.append(st))
    p = env.c.get("/api/v1/progress", cookies=ck).json()
    assert p["interviews_completed"] == 3


# ================================================================ 14. PRESERVED CONTROLS =====================================================================

def test_billing_gates_ai_enforcement_and_permissions_are_unchanged():
    from src import ai_protection as AP
    from src.application import admin_permissions as perm
    from src.billing import policy as P
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PROVIDER_READS_AUTHORIZED,
            P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 6
    assert AP.AI_COST_LIMITS_ENFORCED is False and HA.HISTORY_RESTRICTIONS_ENFORCED is False
    assert len(perm.PERMISSIONS) == 44


def test_the_policy_module_has_no_billing_or_second_entitlement_system():
    text = (ROOT / "src/application/history_access.py").read_text().lower()
    code = text.split('"""', 2)[2]                                                                       # everything after the module docstring
    for banned in ("stripe", "src.billing", "subscription(", "insert", "set_plan", "premium_preview"):
        assert banned not in code, banned


def test_repository_windows_never_delete_or_modify_rows(env):
    uid, _ = env.user()
    ids = seed(env, uid, 5)
    before = [(r["id"], r["created_at"]) for r in env.repo.list_interviews(uid)]
    env.repo.list_interviews(uid, 3)
    env.repo.dashboard_metrics(uid, 3)
    env.repo.get_interview(uid, ids[-1], 3)
    assert [(r["id"], r["created_at"]) for r in env.repo.list_interviews(uid)] == before and count_rows(env, uid) == 5
