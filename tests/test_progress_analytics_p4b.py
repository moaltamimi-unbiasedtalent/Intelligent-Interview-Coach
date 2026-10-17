"""W12.4D-P4-B: gated Premium progress analytics and interview comparison. FULLY OFFLINE over the real application with isolated databases and deterministic
fixtures (no provider, no LLM, no Stripe, every non-loopback socket fails the test). ``PREMIUM_ANALYTICS_ENABLED`` is a code constant that is OFF; tests flip it
on isolated module attributes only. Analytics are descriptive and deterministic: no live candidate data is used."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from src.application import history_access as HA
from src.application import progress_analytics as PA
from src.persistence import Answer, Interview, Opportunity, PlanVersion, Question, Report, Subscription
from tests._auth_factories import cookies_for
from tests.test_sharing_p6_5 import _setup, _uid

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
A, C = "/api/v1/progress/analytics", "/api/v1/progress/analytics/compare"
DIMS = PA.RUBRIC


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    real = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost", "testserver") and not str(host).startswith("/"):
            raise AssertionError(f"network access attempted: {address}")
        return real(self, address, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(PA, "PREMIUM_ANALYTICS_ENABLED", True)


@pytest.fixture()
def hist_on(monkeypatch):
    monkeypatch.setattr(HA, "HISTORY_RESTRICTIONS_ENFORCED", True)


def ev(overall, dim=7, areas=("clarity",)):
    return {"overall_score": overall, **{d: dim for d in DIMS}, "improvement_areas": list(areas), "improved_example_answer": "SECRET-EXAMPLE"}


def seed(repo, uid, specs):
    """specs: dicts with scores (per answer), role, level, opp, dim, areas, report, day, types."""
    ids = []
    for n, sp in enumerate(specs):
        scores = sp.get("scores", [70])
        types = sp.get("types") or ["behavioural"] * len(scores)
        payload = {"configuration": {"target_role": sp.get("role", "Nurse"), "career_level": sp.get("level", "mid"), "industry_or_sector": "health"},
                   "mode": "text", "status": "completed",
                   "questions": [{"position": i, "canonical_question": f"SECRET-Q{n}-{i}", "question_type": types[i], "difficulty": "easy",
                                  "answer": {"text": "SECRET-ANSWER", "evaluation": None if s is None else ev(s, sp.get("dim", 7), sp.get("areas", ("clarity",))), "timing_metrics": None}}
                                 for i, s in enumerate(scores)],
                   "report": {"report": {"overall_readiness_score": sp["report"], "performance_summary": "SECRET-SUMMARY"} if "report" in sp else {}, "usage": None, "cost_usd": None}}
        iid = repo.save_interview(uid, payload, source_session_id=f"a-{uid}-{n}-{time.time_ns()}")
        with repo.session_factory() as s:
            s.execute(update(Interview).where(Interview.id == iid).values(created_at=BASE + timedelta(days=sp.get("day", n)), opportunity_id=sp.get("opp")))
            s.commit()
        ids.append(iid)
    return ids


def premium(repo, uid):
    with repo.session_factory() as s:
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.status == "active"))
        sub.plan_version_id = s.scalar(select(PlanVersion.id).where(PlanVersion.plan_code == "premium", PlanVersion.status == "active"))
        s.commit()


def basic(repo, uid):
    with repo.session_factory() as s:
        sub = s.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.status == "active"))
        sub.plan_version_id = s.scalar(select(PlanVersion.id).where(PlanVersion.plan_code == "basic", PlanVersion.status == "active"))
        s.commit()


def get(c, tok, path=A, **params):
    return c.get(path, cookies=cookies_for(tok), params=params)


# ===================================================================== pure computation (deterministic fixtures) =====================================================================
def row(i, scores, **kw):
    return {"id": i, "created_at": BASE + timedelta(days=kw.get("day", i)), "opportunity_id": kw.get("opp"), "mode": "text", "target_role": kw.get("role", "Nurse"),
            "career_level": kw.get("level", "mid"), "questions": len(scores),
            "answers": [{"position": p, "question_type": (kw.get("types") or ["behavioural"] * len(scores))[p], "difficulty": "easy",
                         "evaluation": None if s is None else ev(s, kw.get("dim", 7), kw.get("areas", ("clarity",)))} for p, s in enumerate(scores)],
            "report_score": kw.get("report")}


def test_the_gate_is_a_disabled_code_constant():
    assert PA.PREMIUM_ANALYTICS_ENABLED is False


def test_empty_history_is_an_explicit_no_data_state_with_no_fabricated_points():
    o = PA.overview([], truncated=False)
    assert o["state"] == "no_data" and o["points"] == [] and o["summary"]["change"] is None and o["distribution"] == {b[0]: 0 for b in PA.BANDS}
    assert o["rubric"]["strongest"] is None and o["by_question_type"] == [] and o["improvement_areas"] == []


def test_a_single_interview_is_insufficient_data_with_no_trend_or_change():
    o = PA.overview([row(1, [80, 60, 70])], truncated=False)
    assert o["state"] == "insufficient_data" and o["summary"]["latest_score"] == 70.0 and o["summary"]["change"] is None and o["summary"]["direction"] is None


def test_two_and_three_interviews_trend_with_a_plain_difference_and_direction():
    two = PA.overview([row(1, [60, 60, 60]), row(2, [75, 75, 75])], truncated=False)
    assert two["state"] == "ready" and two["summary"]["change"] == 15.0 and two["summary"]["direction"] == "improved" and two["summary"]["best_score"] == 75.0
    three = PA.overview([row(1, [80, 80, 80]), row(2, [70, 70, 70]), row(3, [70, 70, 70])], truncated=False)
    assert three["summary"]["change"] == -10.0 and three["summary"]["direction"] == "declined" and [p["practice_score"] for p in three["points"]] == [80.0, 70.0, 70.0]
    flat = PA.overview([row(1, [70, 70, 70]), row(2, [70, 70, 70])], truncated=False)
    assert flat["summary"]["change"] == 0.0 and flat["summary"]["direction"] == "unchanged"


def test_missing_scores_are_excluded_never_zero():
    o = PA.overview([row(1, [None, None, None]), row(2, [80, None, 60]), row(3, [90, 90, 90])], truncated=False)
    assert o["counts"] == {"completed_interviews": 3, "scored_interviews": 2, "unscored_interviews": 1}
    assert o["points"][0]["practice_score"] is None and o["points"][1]["practice_score"] == 70.0 and o["points"][1]["answers_scored"] == 2
    assert o["summary"]["first_score"] == 70.0 and o["summary"]["average_score"] == 80.0


def test_corrupt_or_out_of_range_measurements_are_ignored_not_trusted():
    bad = row(1, [70])
    bad["answers"][0]["evaluation"] = {"overall_score": 250, "relevance": "ten", "structure": 99, "evidence": True, "communication": float("nan"), "credibility": 5,
                                       "improvement_areas": "not-a-list"}
    bad["answers"].append({"position": 1, "question_type": 5, "evaluation": "garbage"})
    bad["report_score"] = -4
    o = PA.overview([bad], truncated=False)
    p = o["points"][0]
    assert p["practice_score"] is None and p["report_score"] is None and p["rubric"]["credibility"]["average"] == 5.0
    assert all(p["rubric"][d]["average"] is None for d in ("relevance", "structure", "evidence", "communication")) and o["improvement_areas"] == []


def test_timestamp_ties_are_ordered_by_id_deterministically_and_repeat_identically():
    rows = [row(2, [60, 60, 60], day=5), row(3, [90, 90, 90], day=5)]
    assert PA.overview(rows, truncated=False) == PA.overview(list(rows), truncated=False)
    assert [p["interview_id"] for p in PA.overview(rows, truncated=False)["points"]] == [2, 3]


def test_rubric_breakdown_uses_only_the_seven_implemented_dimensions_and_has_no_star():
    r = row(1, [70, 70, 70])
    for a, v in zip(r["answers"], (9, 5, 7)):
        a["evaluation"]["structure"] = v
    o = PA.overview([r], truncated=False)
    assert [d["id"] for d in o["rubric"]["dimensions"]] == list(DIMS) and len(DIMS) == 7 and "star" not in str(o).lower()
    by = {d["id"]: d["average"] for d in o["rubric"]["dimensions"]}
    assert by["structure"] == 7.0 and by["relevance"] == 7.0
    assert o["rubric"]["strongest"] is None                                       # all equal after rounding: no invented ranking


def test_strongest_and_weakest_need_a_measurable_difference_and_a_minimum_sample():
    r = row(1, [70, 70, 70])
    for a in r["answers"]:
        a["evaluation"]["evidence"], a["evaluation"]["communication"] = 9, 4
    o = PA.overview([r], truncated=False)
    assert o["rubric"]["strongest"] == "evidence" and o["rubric"]["weakest"] == "communication"
    tiny = row(2, [70])
    tiny["answers"][0]["evaluation"]["evidence"] = 10
    assert PA.overview([tiny], truncated=False)["rubric"]["strongest"] is None      # one answer is below the minimum sample


def test_question_type_performance_distribution_and_frequency():
    rows = [row(1, [40, 90], types=["behavioural", "technical"], day=0), row(2, [60, 80], types=["behavioural", "technical"], day=1)]
    o = PA.overview(rows, truncated=False, now=BASE + timedelta(days=10))
    assert {t["type"]: (t["average_score"], t["answers_scored"]) for t in o["by_question_type"]} == {"behavioural": (50.0, 2), "technical": (85.0, 2)}
    assert o["distribution"]["60-79"] == 2 and o["frequency"]["last_30_days"] == 2 and o["frequency"]["by_month"] == [{"month": "2026-01", "count": 2}]
    far = PA.overview(rows, truncated=False, now=BASE + timedelta(days=400))
    assert far["frequency"]["last_30_days"] == 0 and far["frequency"]["last_90_days"] == 0


def test_recurring_improvement_areas_are_ranked_deterministically_and_labelled_model_generated():
    rows = [row(1, [60], areas=("b", "a")), row(2, [60], areas=("a", "c")), row(3, [60], areas=("b", "a"))]
    areas = PA.overview(rows, truncated=False)["improvement_areas"]
    assert [(a["area"], a["count"]) for a in areas] == [("a", 3), ("b", 2), ("c", 1)] and {a["origin"] for a in areas} == {"model_generated"}


def test_low_sample_is_flagged_and_truncation_is_reported():
    o = PA.overview([row(1, [70]), row(2, [80, 80, 80])], truncated=True)
    assert [p["low_sample"] for p in o["points"]] == [True, False] and o["truncated"] is True


def test_comparison_differences_use_only_values_measured_on_both_sides():
    a, b = row(1, [60, 60, 60]), row(2, [75, 75, 75])
    b["answers"][0]["evaluation"]["credibility"] = None
    for x in a["answers"]:
        x["evaluation"]["relevance"] = 5
    r = PA.compare(a, b)
    assert r["state"] == "ready" and r["score_difference"] == 15.0 and r["direction"] == "improved" and r["comparability"] == "comparable"
    d = {x["id"]: x for x in r["rubric_differences"]}
    assert d["relevance"]["difference"] == 2.0 and d["credibility"]["target"] == 7.0 and d["credibility"]["difference"] == 0.0
    assert {"scoring_version_not_recorded", "difference_is_not_proof_of_skill_change"} <= set(r["limitations"])


def test_comparison_of_different_contexts_is_limited_with_reasons_and_never_claims_causation():
    a = row(1, [60, 60, 60], role="Nurse", level="junior", opp=1, types=["behavioural"] * 3)
    b = row(2, [80, 80, 80, 80], role="Engineer", level="senior", opp=2, types=["technical"] * 4)
    r = PA.compare(a, b)
    assert r["comparability"] == "limited" and {"different_role", "different_level", "different_opportunity", "different_question_mix", "different_question_count"} <= set(r["comparability_reasons"])
    assert "difference_is_not_proof_of_skill_change" in r["limitations"]


def test_comparison_without_two_measured_scores_is_insufficient_and_negative_change_is_reported():
    assert PA.compare(row(1, [None]), row(2, [80, 80, 80]))["state"] == "insufficient_data"
    r = PA.compare(row(1, [90, 90, 90]), row(2, [70, 70, 70]))
    assert r["score_difference"] == -20.0 and r["direction"] == "declined"
    assert PA.compare(row(1, [70, 70, 70]), row(2, [70, 70, 70]))["direction"] == "unchanged"


def test_no_text_from_the_records_is_ever_in_the_computed_output():
    o = PA.overview([row(1, [70, 70, 70]), row(2, [80, 80, 80])], truncated=False)
    assert "SECRET" not in str(o) and "SECRET" not in str(PA.compare(row(1, [70]), row(2, [80])))


# ===================================================================== entitlement and gate (real application) =====================================================================
def test_gate_disabled_every_analytics_route_answers_feature_disabled_with_no_data_even_for_premium():
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        ids = seed(repo, uid, [{"scores": [60, 60, 60]}, {"scores": [80, 80, 80]}])
        r = get(c, a)
        assert r.status_code == 200 and r.json()["state"] == "feature_disabled" and r.json()["points"] == [] and r.json()["counts"] is None
        r2 = get(c, a, C, base=ids[0], target=ids[1])
        assert r2.json()["state"] == "feature_disabled" and r2.json()["base"] is None
        assert get(c, a, A, opportunity_id=99999).json()["state"] == "feature_disabled"          # no probing through the disabled route
        c.cookies.clear()
        assert c.get(A, cookies={"ask4mo_session": "bogus"}).status_code == 401
    finally:
        c.__exit__(None, None, None)


def test_basic_is_not_entitled_and_a_forged_plan_or_client_state_changes_nothing(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        ids = seed(repo, uid, [{"scores": [60, 60, 60]}, {"scores": [80, 80, 80]}])
        r = c.get(A, cookies=cookies_for(a), headers={"x-plan": "premium", "x-tier": "premium"}, params={"plan": "premium", "premium_preview": "true"})
        assert r.json()["state"] == "not_entitled" and r.json()["points"] == []
        assert get(c, a, C, base=ids[0], target=ids[1]).json()["state"] == "not_entitled"
    finally:
        c.__exit__(None, None, None)


def test_premium_preview_alone_is_never_premium(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        from src.application.plan_state import resolve_plan_state
        from src.entitlements import EntitlementService
        assert resolve_plan_state(EntitlementService(repo.session_factory), uid) == "basic"
        assert get(c, a).json()["state"] == "not_entitled"
    finally:
        c.__exit__(None, None, None)


def test_expired_unknown_and_unreadable_entitlement_are_not_entitled(on):
    class Boom:
        def plan_summary(self, *a, **k):
            raise RuntimeError("unreadable")

    class Weird:
        def plan_summary(self, *a, **k):
            return {"plan_code": "platinum", "source": "subscription"}

    class Ended:
        def plan_summary(self, *a, **k):
            return {"plan_code": "basic", "source": "fallback_default"}
    for ents in (Boom(), Weird(), Ended()):
        assert PA.PremiumAnalyticsPolicy(ents).decide(1) == "not_entitled"
    assert PA.PremiumAnalyticsPolicy(Boom(), override=lambda u: "premium").decide(1) == "allowed"


def test_a_synthetic_decision_is_refused_outside_test(monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ValueError):
        PA.PremiumAnalyticsPolicy(None, override=lambda u: "premium")


def test_premium_gets_deterministic_measurements_and_no_record_text(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        seed(repo, uid, [{"scores": [60, 60, 60], "report": 55}, {"scores": [75, 75, 75], "report": 70}, {"scores": [None, None]}])
        r = get(c, a)
        body = r.json()
        assert r.status_code == 200 and body["state"] == "ready" and body["summary"]["change"] == 15.0
        assert body["counts"] == {"completed_interviews": 3, "scored_interviews": 2, "unscored_interviews": 1}
        assert [p["report_score"] for p in body["points"]] == [55.0, 70.0, None]
        assert "SECRET" not in r.text and get(c, a).json() == body                                 # no transcript text; repeat requests are identical
    finally:
        c.__exit__(None, None, None)


def test_analytics_only_ever_cover_the_callers_own_interviews_cross_user_and_workspace(on):
    c, repo, a, b, m, adm, wid = _setup()
    try:
        ua, ub = _uid(c, a), _uid(c, b)                         # bob is a member of alice's workspace
        premium(repo, ua), premium(repo, ub), premium(repo, _uid(c, m))
        ida = seed(repo, ua, [{"scores": [90, 90, 90], "role": "AliceRole"}, {"scores": [95, 95, 95], "role": "AliceRole"}])
        seed(repo, ub, [{"scores": [50, 50, 50], "role": "BobRole"}])
        body = get(c, b).json()
        assert body["counts"]["completed_interviews"] == 1 and body["filters"]["roles"] == ["BobRole"] and "AliceRole" not in str(body)
        assert get(c, m).json()["state"] == "no_data"
        r = get(c, b, C, base=ida[0], target=ida[1])
        assert r.status_code == 404 and "AliceRole" not in r.text                                  # foreign ids look exactly like missing ones
        assert get(c, b, C, base=ida[0], target=424242).status_code == 404
    finally:
        c.__exit__(None, None, None)


def test_the_analytics_entitlement_cannot_widen_the_history_window_aggregation_or_comparison(on, hist_on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        ids = seed(repo, uid, [{"scores": [10, 10, 10], "role": "HiddenOldRole"}] + [{"scores": [60 + i * 5] * 3} for i in range(4)])
        # a synthetic Premium analytics decision with a still-restricted history window (e.g. a rollout activated independently in a test)
        from src.api.routes import progress_analytics as route
        c.app.dependency_overrides[route.get_analytics_policy] = lambda: PA.PremiumAnalyticsPolicy(None, override=lambda u: "premium")
        body = get(c, a).json()
        assert body["counts"]["completed_interviews"] == 3 and all(p["interview_id"] in ids[2:] for p in body["points"]) and "HiddenOldRole" not in str(body)
        r = get(c, a, C, base=ids[0], target=ids[-1])
        assert r.status_code == 403 and r.json()["error"]["code"] == "history_not_available"
        assert get(c, a, C, base=ids[-2], target=ids[-1]).json()["state"] == "ready"
    finally:
        c.__exit__(None, None, None)


def test_downgrade_restricts_analytics_without_touching_records_and_reupgrade_restores_them_with_no_stale_result(on, hist_on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        ids = seed(repo, uid, [{"scores": [50 + i * 5] * 3} for i in range(6)])
        premium(repo, uid)
        full = get(c, a).json()
        assert full["state"] == "ready" and full["counts"]["completed_interviews"] == 6
        basic(repo, uid)
        down = get(c, a)
        assert down.json()["state"] == "not_entitled" and down.json()["points"] == []             # a Premium result is not retained or served after downgrade
        assert get(c, a, C, base=ids[0], target=ids[1]).json()["state"] == "not_entitled"          # and comparison is not a history bypass
        with repo.session_factory() as s:
            assert len(s.scalars(select(Interview.id).where(Interview.user_id == uid)).all()) == 6
        assert len(c.get("/api/v1/history/interviews", cookies=cookies_for(a)).json()["interviews"]) == 3     # Basic history unchanged
        premium(repo, uid)
        assert get(c, a).json() == full                                                             # no duplication, no regeneration, no cache
    finally:
        c.__exit__(None, None, None)


def test_deleted_interviews_disappear_from_analytics_immediately(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        ids = seed(repo, uid, [{"scores": [60, 60, 60]}, {"scores": [70, 70, 70]}, {"scores": [80, 80, 80]}])
        assert c.delete(f"/api/v1/history/interviews/{ids[1]}", cookies=cookies_for(a)).status_code == 200
        body = get(c, a).json()
        assert [p["interview_id"] for p in body["points"]] == [ids[0], ids[2]] and body["summary"]["change"] == 20.0
        assert get(c, a, C, base=ids[0], target=ids[1]).status_code == 404
    finally:
        c.__exit__(None, None, None)


def test_the_comparison_endpoint_rejects_the_same_interview_and_bad_ids(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        ids = seed(repo, uid, [{"scores": [60, 60, 60]}])
        assert get(c, a, C, base=ids[0], target=ids[0]).status_code == 422
        assert get(c, a, C, base=0, target=1).status_code == 422
        assert get(c, a, C, base=ids[0]).status_code == 422
    finally:
        c.__exit__(None, None, None)


def test_opportunity_scoped_analytics_use_only_stored_links_and_check_ownership(on):
    c, repo, a, b, *_ = _setup()
    try:
        ua, ub = _uid(c, a), _uid(c, b)
        premium(repo, ua), premium(repo, ub)
        with repo.session_factory() as s:
            o1, o2, ob = (Opportunity(user_id=ua, title="One"), Opportunity(user_id=ua, title="Two"), Opportunity(user_id=ub, title="Bobs"))
            s.add_all([o1, o2, ob])
            s.commit()
            o1id, o2id, obid = o1.id, o2.id, ob.id
        seed(repo, ua, [{"scores": [60, 60, 60], "opp": o1id}, {"scores": [80, 80, 80], "opp": o1id}, {"scores": [20, 20, 20], "opp": o2id},
                        {"scores": [99, 99, 99], "role": "Nurse"}])                                  # the last one has the SAME role text but no stored link
        body = get(c, a, A, opportunity_id=o1id).json()
        assert body["counts"]["completed_interviews"] == 2 and body["summary"]["change"] == 20.0     # no similarity-based inference
        assert get(c, a, A, opportunity_id=obid).status_code == 404 and get(c, a, A, opportunity_id=999999).status_code == 404
        assert body["filters"]["opportunity_ids"] == [o1id]
    finally:
        c.__exit__(None, None, None)


def test_basic_progress_and_history_are_unchanged_by_the_analytics_code(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        seed(repo, uid, [{"scores": [60, 60, 60]}, {"scores": [80, 80, 80]}])
        prog = c.get("/api/v1/progress", cookies=cookies_for(a)).json()
        assert prog["interviews_completed"] == 2 and prog["average_practice_score"] == 70.0 and set(prog) == {
            "interviews_completed", "answers_evaluated", "average_practice_score", "most_common_improvement_area", "average_answer_seconds", "recent_interviews", "access"}
    finally:
        c.__exit__(None, None, None)


def test_the_analytics_path_makes_no_provider_stripe_or_write_call(on, monkeypatch):
    import src.billing  # noqa: F401  (imported only to assert nothing in it is invoked)
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        seed(repo, uid, [{"scores": [60, 60, 60]}, {"scores": [80, 80, 80]}])
        with repo.session_factory() as s:
            before = (s.scalar(select(Interview.id).order_by(Interview.id.desc())), len(s.scalars(select(Answer.id)).all()), len(s.scalars(select(Report.id)).all()))
        get(c, a), get(c, a)
        with repo.session_factory() as s:
            after = (s.scalar(select(Interview.id).order_by(Interview.id.desc())), len(s.scalars(select(Answer.id)).all()), len(s.scalars(select(Report.id)).all()))
        assert before == after                                                                       # read-only: nothing is written or generated
        import ast
        import pathlib
        tree = ast.parse(pathlib.Path(PA.__file__).read_text())
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not [m for m in imported if any(t in m for t in ("stripe", "openrouter", "llm", "requests", "httpx", "billing", "langchain"))], imported
    finally:
        c.__exit__(None, None, None)


# ===================================================================== scale and structure =====================================================================
def _bulk(repo, uid, n):
    with repo.session_factory() as s:
        for i in range(n):
            iv = Interview(user_id=uid, source_session_id=f"bulk-{uid}-{i}", configuration={"target_role": "Nurse", "career_level": "mid"}, mode="text",
                           status="completed", created_at=BASE + timedelta(hours=i))
            s.add(iv)
            s.flush()
            for p in range(3):
                q = Question(interview_id=iv.id, position=p, canonical_question="Q", question_type="behavioural", difficulty="easy")
                s.add(q)
                s.flush()
                s.add(Answer(question_id=q.id, text="A", evaluation=ev(40 + (i % 50) + p)))
            s.add(Report(interview_id=iv.id, report={"overall_readiness_score": 50}))
        s.commit()


@pytest.mark.parametrize("n", [0, 1, 3, 10, 100])
def test_analytics_scale_over_history_sizes(on, n):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        _bulk(repo, uid, n)
        t = time.perf_counter()
        body = get(c, a).json()
        assert time.perf_counter() - t < 5
        assert body["counts"]["completed_interviews"] == n and body["state"] == {0: "no_data", 1: "insufficient_data"}.get(n, "ready")
        assert [p["interview_id"] for p in body["points"]] == sorted(p["interview_id"] for p in body["points"])
    finally:
        c.__exit__(None, None, None)


def test_a_thousand_interviews_are_capped_reported_truncated_and_stay_fast(on):
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        _bulk(repo, uid, 1000)
        t = time.perf_counter()
        body = get(c, a).json()
        elapsed = time.perf_counter() - t
        assert body["truncated"] is True and body["counts"]["completed_interviews"] == PA.MAX_ANALYZED_INTERVIEWS and elapsed < 15
        newest = repo.analytics_rows(uid, None, limit=1)[0][0]["id"]
        assert body["points"][-1]["interview_id"] == newest                                          # the NEWEST are kept, chronological output
    finally:
        c.__exit__(None, None, None)


def test_the_overview_issues_a_bounded_number_of_queries_regardless_of_history_size(on):
    from sqlalchemy import event
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        _bulk(repo, uid, 120)
        counts = []
        eng = repo.session_factory.kw["bind"]
        for _ in range(1):
            n = [0]
            event.listen(eng, "before_cursor_execute", lambda *x, n=n: n.__setitem__(0, n[0] + 1))
            repo.analytics_rows(uid, None, limit=500)
            counts.append(n[0])
        assert counts[0] <= 6                                                                        # interviews, questions+answers, reports, counts: not per interview
    finally:
        c.__exit__(None, None, None)


def test_all_rollout_and_billing_gates_stay_off():
    from src import ai_protection as AP
    from src.application import usage_quota as UQ
    from src.application.model_profile_access import MODEL_PROFILE_ENFORCED
    from src.billing import policy as bp
    assert AP.AI_COST_LIMITS_ENFORCED is False and HA.HISTORY_RESTRICTIONS_ENFORCED is False and MODEL_PROFILE_ENFORCED is False
    assert UQ.USAGE_QUOTAS_ENFORCED is False and PA.PREMIUM_ANALYTICS_ENABLED is False
    for gate in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED",
                 "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, gate) is False


def test_no_migration_was_added_and_the_head_is_unchanged():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0035_knowledge_foundation"]


def test_a_truncated_history_never_calls_the_earliest_shown_score_the_first_ever_score(on, monkeypatch):
    """P5-B: beyond the cap the oldest interviews are not analysed, so the 'first' score is only the earliest SHOWN one; the response says so (first_scope)."""
    monkeypatch.setattr(PA, "MAX_ANALYZED_INTERVIEWS", 3)
    rows = [row(i, [50 + i * 5] * 3) for i in range(1, 4)]
    cut = PA.overview(rows, truncated=True)
    full = PA.overview(rows, truncated=False)
    assert cut["summary"]["first_scope"] == "window" and full["summary"]["first_scope"] == "all" and cut["truncated"] is True
    c, repo, a, *_ = _setup()
    try:
        uid = _uid(c, a)
        premium(repo, uid)
        seed(repo, uid, [{"scores": [40 + i] * 3} for i in range(6)])
        body = get(c, a).json()
        assert body["truncated"] is True and body["counts"]["completed_interviews"] == 3 and body["summary"]["first_scope"] == "window"
        assert body["analyzed_limit"] == 3
    finally:
        c.__exit__(None, None, None)
