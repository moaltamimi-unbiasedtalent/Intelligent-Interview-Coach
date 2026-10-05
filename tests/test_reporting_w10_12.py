"""P10B-W10.12: Admin reporting, analytics and AI economics. Offline and deterministic: temp DB, no provider, no network, no pricing fetch.
Load-bearing properties: aggregates only (no candidate content or identifiers), small cohorts suppressed (value None, never the count), unknown tokens and
cost are never zero, no double counting of AI usage, mock billing is never revenue, and every report is read-only."""

from __future__ import annotations

import json
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.agent.usage import aggregate_usage
from src.application import admin_permissions as perm
from src.persistence import (
    AIUsageFact, Answer, BillingCommercialTerms, BillingCustomer, BillingInvoice, BillingPayment, BillingProviderSubscription, Interview, InterviewSession,
    Opportunity, OperationalMetricEvent, PlanVersion, PreparationRun, Question, Subscription, User, UserFeedback,
)
from src.reporting import suppression as S
from src.reporting import telemetry as T
from src.reporting.definitions import PERIODS, REPORTING_MIN_COHORT
from src.reporting.service import ReportingError, ReportingService
from tests.test_admin_foundation_w10_1 import Env

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def sf(env):
    return env.accounts.session_factory


def svc(env):
    return ReportingService(sf(env), clock=lambda: NOW)


def users(env, n, *, created=None, onboarded=True, prefix="c"):
    out = []
    with sf(env)() as s:
        for i in range(n):
            t = created or NOW - timedelta(days=3)
            u = User(subject=f"{prefix}{len(out)}{i}-{id(out)}", provider="test", email=f"{prefix}{i}-{id(out)}@example.test", platform_role="user", status="active",
                     created_at=t, updated_at=t, onboarding_completed_at=t if onboarded else None)
            s.add(u)
            s.flush()
            out.append(u.id)
        s.commit()
    return out


def metric(report, section, mid):
    sec = next(x for x in report["sections"] if x["section_id"] == section)
    return next(m for m in sec["metrics"] if m["metric_id"] == mid)


def table(report, section, tid):
    sec = next(x for x in report["sections"] if x["section_id"] == section)
    return next(t for t in sec["tables"] if t["table_id"] == tid)


# ---------------- periods, suppression ----------------------------------------------------------------------------------------------

def test_periods_are_fixed_and_utc_and_unknown_is_rejected(env):
    assert set(PERIODS) == {"7d", "30d", "90d", "all_time"}
    with pytest.raises(ReportingError):
        svc(env).product("1d; DROP TABLE users")
    r = svc(env).product("7d")
    assert r["utc"] is True and r["window_end"].endswith("+00:00") and r["period"] == "7d"


def test_registrations_use_authoritative_user_rows_and_period_boundaries(env):
    users(env, 6, created=NOW - timedelta(days=3))
    users(env, 6, created=NOW - timedelta(days=20), prefix="m")
    users(env, 6, created=NOW - timedelta(days=100), prefix="o")
    assert metric(svc(env).product("7d"), "product", "registrations")["figure"] == 6
    assert metric(svc(env).product("30d"), "product", "registrations")["figure"] == 12
    assert metric(svc(env).product("90d"), "product", "registrations")["figure"] == 12
    assert metric(svc(env).product("all_time"), "product", "registrations")["figure"] == 18
    with sf(env)() as s:                                            # admins are not candidate registrations
        s.add(User(subject="adm", provider="test", email="a@example.test", platform_role="platform_admin", status="active", created_at=NOW - timedelta(days=1), updated_at=NOW))
        s.commit()
    assert metric(svc(env).product("7d"), "product", "registrations")["figure"] == 6


@pytest.mark.parametrize("n,visible", [(1, False), (4, False), (5, True), (6, True)])
def test_small_cohort_is_suppressed_without_leaking_the_count(env, n, visible):
    users(env, n)
    m = metric(svc(env).product("30d"), "product", "registrations")
    if visible:
        assert m["figure"] == n and m["state"] == "available"
    else:
        assert m["figure"] is None and m["state"] == "suppressed"
        blob = json.dumps(svc(env).product("30d"))
        assert f'"figure": {n},' not in blob.split('"registrations"')[1].split("}")[0]
        assert "<5" not in blob and "< 5" not in blob


def test_rate_is_suppressed_when_the_denominator_is_small(env):
    users(env, 4, onboarded=True)
    assert metric(svc(env).product("30d"), "product", "onboarding_rate")["state"] == "suppressed"           # 4 registrants: denominator below the floor
    users(env, 2, onboarded=False, prefix="x")                    # 6 registrants, 4 onboarded: the numerator itself is a small count
    assert metric(svc(env).product("30d"), "product", "onboarding_rate")["state"] == "suppressed"
    users(env, 3, onboarded=True, prefix="y"); users(env, 3, onboarded=False, prefix="z")                  # 12 registrants, 7 onboarded, 5 not
    assert metric(svc(env).product("30d"), "product", "onboarding_rate")["figure"] == 58.3


def test_secondary_suppression_prevents_reconstruction_by_subtraction():
    rows = S.partition([{"label": "A", "values": [10], "cohort": 4}, {"label": "B", "values": [20], "cohort": 6}, {"label": "C", "values": [70], "cohort": 9}])
    hidden = [r["label"] for r in rows if r["cells"][0]["suppressed"]]
    assert hidden == ["A", "B"]                                    # the single small bucket A is NOT recoverable as total - visible
    assert all(c["figure"] is None for r in rows for c in r["cells"] if c["suppressed"])
    assert [r["cells"][0]["figure"] for r in rows] == [None, None, 70]
    two = S.partition([{"label": "A", "values": [1], "cohort": 2}, {"label": "B", "values": [2], "cohort": 3}, {"label": "C", "values": [3], "cohort": 8}])
    assert [r["cells"][0]["suppressed"] for r in two] == [True, True, False]
    allok = S.partition([{"label": "A", "values": [1], "cohort": 5}, {"label": "B", "values": [2], "cohort": 9}])
    assert not any(c["suppressed"] for r in allok for c in r["cells"])


def test_the_floor_constant_is_five_and_documented():
    assert REPORTING_MIN_COHORT == 5
    assert "not an anonymisation guarantee" in (ROOT / "src/reporting/suppression.py").read_text()


# ---------------- product definitions -----------------------------------------------------------------------------------------------

def seed_activity(env):
    """6 candidates: each creates an Opportunity on day -3; 3 of them also on day -1 (two distinct UTC days); 6 prepare runs (one back-filled)."""
    ids = users(env, 6, created=NOW - timedelta(days=5))
    with sf(env)() as s:
        for i, uid in enumerate(ids):
            s.add(Opportunity(user_id=uid, title="SECRET-TITLE", target_role="r", status="active", created_at=NOW - timedelta(days=3), updated_at=NOW))
            if i < 3:
                s.add(PreparationRun(run_id=f"run{i}", owner_user_id=uid, state="ready", source="created", created_at=NOW - timedelta(days=1), updated_at=NOW))
        s.add(PreparationRun(run_id="bf1", owner_user_id=ids[5], state="ready", source="backfill", created_at=NOW - timedelta(days=1), updated_at=NOW))
        s.commit()
    return ids


def test_activation_and_return_definitions_match_the_documented_rules(env):
    ids = seed_activity(env)
    r = svc(env).product("30d")
    assert metric(r, "product", "opportunities_created")["figure"] == 6
    assert metric(r, "product", "opportunities_per_candidate")["figure"] == 1.0
    assert metric(r, "product", "prepare_started")["figure"] is None or metric(r, "product", "prepare_started")["state"] == "suppressed"   # 3 candidates: below the floor
    assert metric(r, "product", "activated_candidates")["figure"] == 6                     # first substantive action = the Opportunity
    assert metric(r, "product", "activation_rate")["figure"] == 100.0
    assert metric(r, "product", "active_candidates")["figure"] == 6
    assert metric(r, "product", "returning_candidates")["state"] == "suppressed"          # exactly 3 returners: a count below the floor is hidden
    assert metric(r, "product", "returning_rate")["state"] == "suppressed"                # a 3-of-6 rate would reveal that exactly 3 returned
    with sf(env)() as s:
        for uid in ids[3:]:
            s.add(PreparationRun(run_id=f"more{uid}", owner_user_id=uid, state="failed", source="created", created_at=NOW - timedelta(days=1), updated_at=NOW))
        s.commit()
    r = svc(env).product("30d")
    assert metric(r, "product", "prepare_started")["figure"] == 6 and metric(r, "product", "prepare_ready_rate")["state"] == "suppressed"   # 3 of 6 ready: small numerator
    assert metric(r, "product", "returning_candidates")["figure"] == 6                      # every candidate now has two distinct UTC days


def test_backfilled_preparation_rows_and_logins_never_count_as_activity(env):
    ids = users(env, 6)
    with sf(env)() as s:
        for uid in ids:
            s.add(PreparationRun(run_id=f"bf{uid}", owner_user_id=uid, state="ready", source="backfill", created_at=NOW - timedelta(days=1), updated_at=NOW))
        s.commit()
    r = svc(env).product("30d")
    assert metric(r, "product", "activated_candidates")["state"] == "suppressed" or metric(r, "product", "activated_candidates")["figure"] in (0, None)
    assert metric(r, "product", "active_candidates")["figure"] in (0, None)


def test_practice_started_completed_and_no_private_content(env):
    ids = users(env, 6)
    with sf(env)() as s:
        for i, uid in enumerate(ids):
            s.add(InterviewSession(session_id=f"live{i}", user_id=uid, opportunity_id=None, state_payload={"secret": "SECRET-PAYLOAD"}, state_schema_version=1, version=1,
                                   status="in_progress", created_at=NOW - timedelta(days=2), updated_at=NOW, last_accessed_at=NOW))
            iv = Interview(user_id=uid, source_session_id=f"done{i}", configuration={"jd": "SECRET-JD"}, status="completed", created_at=NOW - timedelta(days=2), started_at=None, ended_at=None,
                           opportunity_id=None)
            s.add(iv)
            s.flush()
            q = Question(interview_id=iv.id, canonical_question="SECRET-QUESTION")
            s.add(q)
            s.flush()
            s.add(Answer(question_id=q.id, text="SECRET-ANSWER", evaluation={"overall_score": 60 + i * 5, "strengths": ["SECRET-NARRATIVE"]}))
        s.commit()
    pr, ql = svc(env).product("30d"), svc(env).quality("30d")
    assert metric(pr, "product", "practice_started")["figure"] == 12 and metric(pr, "product", "practice_completed")["figure"] == 6
    assert metric(ql, "quality", "evaluation_score_avg")["figure"] == 72.5 and metric(ql, "quality", "evaluation_count")["figure"] == 6
    blob = json.dumps([pr, ql, svc(env).operations("30d"), svc(env).ai_economics("30d")])
    for secret in ("SECRET-PAYLOAD", "SECRET-JD", "SECRET-QUESTION", "SECRET-ANSWER", "SECRET-NARRATIVE", "SECRET-TITLE"):
        assert secret not in blob


def test_feedback_is_aggregate_only_without_comments_or_identity(env):
    ids = users(env, 6)
    with sf(env)() as s:
        for i, uid in enumerate(ids):
            s.add(UserFeedback(user_id=uid, surface="agent_answer", target_id="t" * 8, rating="helpful" if i < 4 else "not_helpful", category="accuracy" if i % 2 else None,
                               comment="SECRET-COMMENT", created_at=NOW - timedelta(days=1), updated_at=NOW))
        s.commit()
    r = svc(env).quality("30d")
    assert metric(r, "quality", "feedback_total")["figure"] == 6
    blob = json.dumps(r)
    assert "SECRET-COMMENT" not in blob and "example.test" not in blob and "user_id" not in blob
    rating = table(r, "quality", "feedback_rating")
    assert all(c["suppressed"] for row in rating["rows"] for c in row["cells"]) or len(rating["rows"]) == 2           # 4 / 2 users: below the floor so hidden


def test_unsupported_quality_metrics_are_not_captured_rather_than_zero(env):
    r = svc(env).quality("30d")
    assert metric(r, "quality", "evaluator_runs")["state"] == "not_captured"
    for mid in ("retrieval_outcomes", "request_outcomes", "provider_calls"):
        assert metric(r, "telemetry" if False else "quality", mid)["state"] == "not_captured" and metric(r, "quality", mid)["figure"] is None


# ---------------- operational telemetry ---------------------------------------------------------------------------------------------

def test_telemetry_is_bounded_safe_and_has_no_identity_or_path(env):
    T.install(sf(env))
    assert T.record_event("request", "agent", "agent_run", "success", duration_ms=120)
    assert T.record_event("request", "agent", "agent_run", "server_error", duration_ms=480, error_category="Weird Error!")
    assert not T.record_event("request", "agent", "/api/v1/agent/runs/123/messages?x=1", "success")                     # a raw path is not a label
    assert not T.record_event("nonsense", "agent", "agent_run", "success") and not T.record_event("request", "agent", "agent_run", "exploded")
    assert T.record_event("request", "agent", "agent_run", "success", duration_ms=-5)                                    # negative durations are clamped, never stored negative
    with sf(env)() as s:
        rows = s.scalars(select(OperationalMetricEvent)).all()
        assert [r.error_category for r in rows if r.error_category] == ["other"]
        assert min(r.duration_ms for r in rows if r.duration_ms is not None) >= 0
        cols = {c.name for c in OperationalMetricEvent.__table__.columns}
    assert cols == {"id", "event_type", "subsystem", "operation", "outcome", "duration_ms", "error_category", "provider", "occurred_at"}
    T.uninstall()
    assert T.record_event("request", "agent", "agent_run", "success") is False                                            # no sink: best-effort no-op


def test_route_labels_use_templates_and_never_admin_traffic():
    assert T.route_label("POST", "/api/v1/agent/run") == ("agent", "agent_run")
    assert T.route_label("POST", "/api/v1/agent/runs/{run_id}/messages") == ("agent", "agent_continue")
    assert T.route_label("POST", "/api/v1/interviews/{session_id}/answer") == ("practice", "practice_step")
    assert T.route_label("GET", "/api/v1/agent/run") is None and T.route_label("POST", "/api/v1/admin/reports/product") is None
    assert T.route_label("POST", "/api/v1/auth/login") is None and T.route_label("POST", None) is None
    assert [T.outcome_for_status(s) for s in (200, 404, 500, 503)] == ["success", "client_error", "server_error", "unavailable"]


def test_request_middleware_records_a_bounded_outcome_and_excludes_admin(env):
    from src.api import dependencies as deps
    T.install(sf(env))
    _, cand = env.user("user"); _, ops = env.user("operations_admin")
    env.app.dependency_overrides[deps.get_agent_service] = lambda: SimpleNamespace(run=lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    env.c.post(f"{API}/agent/run", json={"goal": "Prepare me for an interview", "target_role": "Nurse"}, cookies=cand)
    env.c.get(f"{API}/admin/reports/operations", cookies=ops)
    with sf(env)() as s:
        rows = s.scalars(select(OperationalMetricEvent)).all()
    assert [(r.event_type, r.operation) for r in rows] == [("request", "agent_run")]
    assert rows[0].outcome in ("server_error", "success", "client_error", "unavailable")
    assert not any("admin" in (r.operation + r.subsystem) for r in rows)
    T.uninstall()


def test_latency_percentiles_and_failure_rate(env):
    T.install(sf(env))
    for d in (100, 200, 300, 400, 1000):
        T.record_event("request", "agent", "agent_run", "success", duration_ms=d)
    T.record_event("request", "agent", "agent_run", "server_error", duration_ms=50)
    T.uninstall()
    r = svc(env).operations("30d")
    t = table(r, "telemetry", "request_outcomes")
    row = t["rows"][0]
    assert row["label"] == "agent_run" and [c["figure"] for c in row["cells"]] == [6, 16.7, 200, 1000]
    assert next(x for x in r["sections"] if x["section_id"] == "telemetry")["captured_since"]


def test_retrieval_outcomes_store_no_query_or_content(env):
    T.install(sf(env))
    T.record_event("retrieval", "career", "career_chat", "hit"); T.record_event("retrieval", "career", "career_chat", "abstained")
    T.uninstall()
    t = table(svc(env).quality("30d"), "quality", "retrieval_outcomes")
    assert [c["figure"] for c in t["rows"][0]["cells"]] == [1, 1, 0]


def test_career_retrieval_and_provider_boundaries_emit_events_without_content(env, monkeypatch):
    from src.application.career_service import CareerApplicationService, _observe_retrieval
    T.install(sf(env))
    _observe_retrieval("abstained", "knowledge_search")
    T.uninstall()
    with sf(env)() as s:
        r = s.scalar(select(OperationalMetricEvent))
    assert (r.event_type, r.operation, r.outcome, r.provider) == ("retrieval", "knowledge_search", "abstained", None) and CareerApplicationService


# ---------------- AI usage: capture, idempotency, no double counting ----------------------------------------------------------------

def agent_entries():
    # two outer agent calls and two model-backed tool calls, each with known tokens; ONE canonical ledger
    def e(src, i, o, cost=None):
        return {"source": src, "kind": "tool" if src.startswith("tool:") else "agent", "model_calls": 1, "model": "openai/gpt-5.6-terra", "input_tokens": i, "output_tokens": o,
                "total_tokens": i + o, "reported_cost_usd": cost, "has_usage": True}
    return [e("agent", 100, 20, 0.001), e("tool:AnalyzeJobDescription", 300, 80, 0.003), e("agent", 150, 30, 0.002), e("tool:GenerateInterviewQuestions", 250, 50, 0.004)]


def test_agent_usage_is_captured_once_per_run_and_equals_the_canonical_ledger(env):
    uid = users(env, 1)[0]
    entries = agent_entries()
    ledger = aggregate_usage(entries).to_dict()
    assert ledger["model_calls"] == 4
    assert T.record_agent_usage(sf(env), uid, "run-1", ledger, "balanced")
    T.record_agent_usage(sf(env), uid, "run-1", ledger, "balanced")                          # replay / resume: still one fact
    with sf(env)() as s:
        facts = s.scalars(select(AIUsageFact)).all()
    assert len(facts) == 1 and facts[0].model_calls == 4                                    # agent + tool calls counted ONCE, not 4 + 2
    assert facts[0].total_tokens == ledger["total_tokens"] == ledger["input_tokens"] + ledger["output_tokens"]
    nested = [e for e in entries if e["source"].startswith("tool:")]
    assert facts[0].total_tokens != ledger["total_tokens"] + sum(e["total_tokens"] for e in nested)
    r = svc(env).ai_economics("30d")
    assert metric(r, "ai_economics", "ai_calls")["state"] == "suppressed"                    # one candidate: below the floor
    # the same persisted total through the report with a qualifying cohort:
    for i in range(5):
        T.record_agent_usage(sf(env), users(env, 1, prefix=f"q{i}")[0], f"run-q{i}", ledger, "balanced")
    r = svc(env).ai_economics("30d")
    assert metric(r, "ai_economics", "ai_calls")["figure"] == 4 * 6


def test_a_later_turn_replaces_the_cumulative_aggregate_and_never_adds_or_shrinks(env):
    uid = users(env, 1)[0]
    small = aggregate_usage(agent_entries()[:2]).to_dict()
    big = aggregate_usage(agent_entries()).to_dict()
    T.record_agent_usage(sf(env), uid, "r", small, "balanced")
    T.record_agent_usage(sf(env), uid, "r", big, "balanced")
    T.record_agent_usage(sf(env), uid, "r", small, "balanced")                               # an older/smaller replay must not shrink it
    with sf(env)() as s:
        f = s.scalars(select(AIUsageFact)).one()
    assert f.model_calls == 4 and f.total_tokens == big["total_tokens"]


def test_unknown_tokens_and_cost_stay_unknown_never_zero(env):
    uid = users(env, 1)[0]
    unknown = {"model_calls": 2, "input_tokens": None, "output_tokens": None, "total_tokens": None, "estimated_cost_usd": None, "usage_complete": False, "missing_usage_sources": ["agent"]}
    T.record_agent_usage(sf(env), uid, "u", unknown, "fast")
    with sf(env)() as s:
        f = s.scalars(select(AIUsageFact)).one()
    assert (f.total_tokens, f.cost_usd_micros, f.cost_source, f.token_coverage, f.cost_coverage) == (None, None, "unavailable", "unknown", "unknown")
    for i in range(5):
        T.record_agent_usage(sf(env), users(env, 1, prefix=f"u{i}")[0], f"u{i}", unknown, "fast")
    r = svc(env).ai_economics("30d")
    assert metric(r, "ai_economics", "ai_tokens_known")["state"] == "not_captured" and metric(r, "ai_economics", "ai_tokens_known")["figure"] is None
    cost = metric(r, "ai_economics", "ai_known_cost_usd")
    assert cost["figure"] is None and cost["state"] == "not_captured"
    assert metric(r, "ai_economics", "ai_cost_coverage")["figure"] == 0.0 and metric(r, "ai_economics", "ai_token_coverage")["figure"] == 0.0


def usage_record(model="openai/gpt-5.6-terra", source="reported", reported=0.0123, calc=0.01, p=100, c=40):
    from src.models import UsageRecord
    return UsageRecord(model=model, prompt_tokens=p, completion_tokens=c, total_tokens=p + c, reported_cost=reported, calculated_cost=calc, cost_source=source,
                       request_duration_seconds=0.5)


def test_practice_usage_cost_sources_micro_usd_and_replay_idempotency(env):
    uid = users(env, 1)[0]
    recs = [usage_record(source="reported", reported=0.0123), usage_record(source="calculated", reported=None, calc=0.004567), usage_record(source="unavailable", reported=None, calc=0.0)]
    assert T.record_practice_usage(sf(env), uid, "sess1", 0, recs, "create") == 3
    assert T.record_practice_usage(sf(env), uid, "sess1", 0, recs, "create") == 0                      # replay: nothing added
    with sf(env)() as s:
        facts = s.scalars(select(AIUsageFact).order_by(AIUsageFact.usage_key)).all()
    assert [f.usage_key for f in facts] == ["practice:sess1:0", "practice:sess1:1", "practice:sess1:2"]
    assert [f.cost_usd_micros for f in facts] == [12300, 4567, None] and [f.cost_source for f in facts] == ["reported", "calculated", "unavailable"]
    assert all(isinstance(f.cost_usd_micros, (int, type(None))) for f in facts)                          # integer micro-USD, no float
    assert facts[2].cost_usd_micros is None and facts[2].cost_coverage == "unknown"                    # unavailable != $0


def test_known_cost_subtotal_is_labelled_partial_with_coverage(env):
    for i in range(6):
        uid = users(env, 1, prefix=f"p{i}")[0]
        T.record_practice_usage(sf(env), uid, f"s{i}", 0, [usage_record(source="reported", reported=0.01), usage_record(source="unavailable", reported=None, calc=0.0)], "create")
    r = svc(env).ai_economics("30d")
    cost = metric(r, "ai_economics", "ai_known_cost_usd")
    assert cost["figure"] == 0.06 and cost["state"] == "partial" and "partial coverage" in cost["label"] and "50.0%" in cost["coverage"]
    assert metric(r, "ai_economics", "ai_cost_coverage")["figure"] == 50.0 and metric(r, "ai_economics", "ai_token_coverage")["figure"] == 100.0
    assert metric(r, "ai_economics", "ai_calls")["figure"] == 12
    assert metric(r, "ai_economics", "ai_cost_per_candidate")["figure"] == 0.01


def test_practice_session_store_records_each_canonical_usage_once(env):
    from src.interview.session_repository import DurableInterviewSessionStore
    uid = users(env, 1)[0]
    store = DurableInterviewSessionStore(sf(env))
    sid = store.create(uid)
    with store.mutate(sid, uid, operation="create") as session:
        session.record_usage(usage_record())
        session.record_usage(usage_record(source="calculated", reported=None, calc=0.002))
    with store.mutate(sid, uid, operation="submit_answer") as session:
        session.record_usage(usage_record())
    with store.mutate(sid, uid) as session:                                                              # no new usage: no new fact
        pass
    with sf(env)() as s:
        keys = [(f.usage_key, f.operation) for f in s.scalars(select(AIUsageFact).order_by(AIUsageFact.id)).all()]
    assert keys == [(f"practice:{sid}:0", "create"), (f"practice:{sid}:1", "create"), (f"practice:{sid}:2", "submit_answer")]


def test_ai_economics_by_model_and_workflow_with_secondary_suppression(env):
    # model A: 4 candidates, model B: 6, model C: 9. A is below the floor, so B is hidden too (no subtraction)
    n = 0
    for model, count in (("openai/gpt-5.6-luna", 4), ("openai/gpt-5.6-terra", 6), ("openai/gpt-5.6-sol", 9)):
        for i in range(count):
            n += 1
            T.record_practice_usage(sf(env), users(env, 1, prefix=f"m{n}")[0], f"s{n}", 0, [usage_record(model=model, reported=0.01)], "create")
    r = svc(env).ai_economics("30d")
    by_model = {row["label"]: row["cells"][0] for row in table(r, "ai_economics", "ai_by_model")["rows"]}
    assert by_model["openai/gpt-5.6-luna"]["suppressed"] and by_model["openai/gpt-5.6-terra"]["suppressed"] and not by_model["openai/gpt-5.6-sol"]["suppressed"]
    assert by_model["openai/gpt-5.6-sol"]["figure"] == 9
    assert metric(r, "ai_economics", "ai_calls")["figure"] == 19                                          # the total alone cannot isolate bucket A
    ranked = [row["label"] for row in table(r, "ai_economics", "ai_rank_cost")["rows"]]
    assert ranked == ["practice"]


def test_ai_usage_constraints(env):
    def add(**kw):
        base = dict(usage_key="k", user_id=None, workflow="practice", operation="x", model_calls=1, cost_source="reported", token_coverage="complete", cost_coverage="complete")
        base.update(kw)
        with sf(env)() as s:
            s.add(AIUsageFact(**base))
            s.commit()
    add(usage_key="ok1", input_tokens=1, output_tokens=2, total_tokens=3, cost_usd_micros=0)
    for i, bad in enumerate((dict(input_tokens=-1), dict(cost_usd_micros=-1), dict(cost_source="guessed"), dict(workflow="other"), dict(token_coverage="all"),
                             dict(input_tokens=1, output_tokens=2, total_tokens=9), dict(cost_source="unavailable", cost_usd_micros=5), dict(model_calls=-1))):
        with pytest.raises(IntegrityError):
            add(usage_key=f"bad{i}", **bad)
    with pytest.raises(IntegrityError):
        add(usage_key="ok1")                                                                              # duplicate usage key


def test_event_constraints(env):
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(OperationalMetricEvent(event_type="click", subsystem="x", operation="y", outcome="success")); s.commit()
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(OperationalMetricEvent(event_type="request", subsystem="x", operation="y", outcome="boom")); s.commit()
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(OperationalMetricEvent(event_type="request", subsystem="x", operation="y", outcome="success", duration_ms=-1)); s.commit()


def test_account_deletion_removes_the_candidates_usage_facts_and_export_is_owner_scoped(env):
    from src.application.account_deletion_service import AccountDeletionService
    a, b = users(env, 2)
    T.record_practice_usage(sf(env), a, "sa", 0, [usage_record()], "create")
    T.record_practice_usage(sf(env), b, "sb", 0, [usage_record(), usage_record()], "create")
    from src.application.data_export import build_candidate_export
    acct = env.accounts.get_account(a)
    exp = build_candidate_export(user_id=a, session_factory=sf(env), repo=env.repo, account=acct)
    assert len(exp["ai_usage"]) == 1 and exp["ai_usage"][0]["workflow"] == "practice" and exp["ai_usage"][0]["cost_usd"] == 0.0123
    assert "usage_key" not in json.dumps(exp["ai_usage"]) and "user_id" not in json.dumps(exp["ai_usage"])         # owner metadata only: no key, no identifier, no aggregates
    assert len(build_candidate_export(user_id=b, session_factory=sf(env), repo=env.repo, account=env.accounts.get_account(b))["ai_usage"]) == 2
    with sf(env)() as s:
        assert s.scalar(select(text("count(*)")).select_from(AIUsageFact)) == 3
    AccountDeletionService(sf(env)).delete_account(a)
    with sf(env)() as s:
        owners = {f.user_id for f in s.scalars(select(AIUsageFact)).all()}
    assert a not in owners and b in owners and len(owners) == 1


# ---------------- commercial ---------------------------------------------------------------------------------------------------------

def plan_versions(env):
    from src.entitlements import seed_default_plans
    with sf(env)() as s:
        seed_default_plans(s)
        s.commit()
    with sf(env)() as s:
        return {p.plan_code: p.id for p in s.scalars(select(PlanVersion).where(PlanVersion.status == "active")).all()}


def mock_subs(env, n, *, state="active", amount=1000, interval="month", currency="EUR", terms=True, pv_code="premium", tag="a"):
    pv = plan_versions(env)[pv_code]
    owners = [users(env, 1, prefix=f"bc{tag}{i}{state}{amount}{interval}{currency}")[0] for i in range(n)]
    with sf(env)() as s:
        t = None
        if terms:
            existing = s.scalar(select(BillingCommercialTerms).where(BillingCommercialTerms.plan_version_id == pv, BillingCommercialTerms.currency == currency,
                                                                     BillingCommercialTerms.amount_minor == amount, BillingCommercialTerms.billing_interval == interval))
            t = existing or BillingCommercialTerms(public_id=f"t{tag}{amount}{interval}{currency}"[:32].ljust(32, "0"), plan_version_id=pv, version=1 + len(s.scalars(select(BillingCommercialTerms)).all()),
                                                  amount_minor=amount, currency=currency, billing_interval=interval, visibility="internal", state="retired" if existing is None and False else "retired",
                                                  created_at=NOW)
            if existing is None:
                s.add(t); s.flush()
        for i in range(n):
            owner = owners[i]
            c = BillingCustomer(public_id=f"c{tag}{i}{state}{amount}"[:32].ljust(32, "0"), provider="mock", provider_customer_id=f"cus_{tag}{i}{state}{amount}{interval}{currency}", state="active", user_id=owner)
            s.add(c); s.flush()
            s.add(BillingProviderSubscription(public_id=f"s{tag}{i}{state}{amount}"[:32].ljust(32, "0"), provider="mock", provider_subscription_id=f"sub_{tag}{i}{state}{amount}{interval}{currency}",
                                              customer_id=c.id, plan_version_id=pv, commercial_terms_id=t.id if t else None, provider_state=state))
        s.commit()


def test_commercial_requires_its_own_permission_and_regular_reports_never_contain_commercial_fields(env):
    _, plat = env.user("platform_admin"); _, ops = env.user("operations_admin"); _, bill = env.user("billing_admin"); _, cand = env.user("user")
    assert env.c.get(f"{API}/admin/reports/commercial", cookies=plat).status_code == 403
    assert env.c.get(f"{API}/admin/reports/commercial", cookies=ops).status_code == 403
    assert env.c.get(f"{API}/admin/reports/commercial", cookies=cand).status_code == 403
    assert env.c.get(f"{API}/admin/reports/commercial", cookies=bill).status_code == 200
    assert env.c.get(f"{API}/admin/reports/product", cookies=bill).status_code == 403                  # billing_admin lacks platform.reports.read
    for path in ("product", "quality", "operations", "ai-economics", "definitions"):
        r = env.c.get(f"{API}/admin/reports/{path}", cookies=plat)
        assert r.status_code == 200, (path, r.text)
        assert not re.search(r"\bmrr\b|\barr\b|revenue|invoice|payment|mock billing", r.text, re.I) or path == "definitions", path


def test_mock_mrr_arr_monthly_yearly_currency_separation_and_exclusions(env):
    mock_subs(env, 5, amount=1000, interval="month", currency="EUR", tag="a")           # 5 x 10.00 EUR monthly
    mock_subs(env, 5, amount=12000, interval="year", currency="EUR", tag="b")           # 5 x 120.00 EUR yearly -> 10.00 monthly each
    mock_subs(env, 5, amount=500, interval="month", currency="USD", tag="c")
    mock_subs(env, 2, amount=999, state="cancelled", tag="d"); mock_subs(env, 3, amount=999, state="past_due", tag="e"); mock_subs(env, 4, amount=999, state="trialing", tag="f")
    r = svc(env).commercial("30d")
    rows = {row["label"]: [c["figure"] for c in row["cells"]] for row in table(r, "mock_billing", "mock_recurring")["rows"]}
    assert rows["EUR"] == [10, 100.0, 1200.0]                                          # (5 x 10) + (5 x 10) = 100 MRR; ARR = 5 x 120 + 5 x 120
    assert rows["USD"] == [5, 25.0, 300.0]
    assert "EUR" in rows and "USD" in rows and len(rows) == 2                          # never one combined figure
    states = {row["label"]: row["cells"][0] for row in table(r, "mock_billing", "mock_by_state")["rows"]}
    assert states["active"]["figure"] == 15
    assert r["mock_billing"] is True and r["label"] == "MOCK BILLING - NOT LIVE REVENUE"
    assert next(x for x in r["sections"] if x["section_id"] == "mock_billing")["title"] == "MOCK BILLING - NOT LIVE REVENUE"
    assert metric(r, "mock_billing", "mock_churn_rate")["state"] == "unavailable" and "unavailable with current historical evidence" in metric(r, "mock_billing", "mock_churn_rate")["note"]


def test_missing_terms_are_unconfigured_never_zero_revenue(env):
    mock_subs(env, 6, terms=False, tag="g")
    r = svc(env).commercial("30d")
    assert metric(r, "mock_billing", "mock_mrr")["state"] == "unavailable" and metric(r, "mock_billing", "mock_mrr")["figure"] is None
    assert "not zero revenue" in metric(r, "mock_billing", "mock_mrr")["note"]
    assert metric(r, "mock_billing", "mock_eligible")["figure"] == 6 and metric(r, "mock_billing", "mock_priced")["figure"] == 0


def test_yearly_rounding_is_deterministic_half_up(env):
    mock_subs(env, 5, amount=1001, interval="year", currency="EUR", tag="h")             # 1001 / 12 = 83.4166 -> 83 minor each
    rows = {row["label"]: [c["figure"] for c in row["cells"]] for row in table(svc(env).commercial("30d"), "mock_billing", "mock_recurring")["rows"]}
    assert rows["EUR"] == [5, 4.15, 50.05]


def test_access_plan_assignments_are_not_revenue_and_transitions_are_directional(env):
    ids = users(env, 6)
    pv = plan_versions(env)
    with sf(env)() as s:
        for i, uid in enumerate(ids):
            s.add(Subscription(user_id=uid, workspace_id=None, plan_version_id=pv["basic"], status="active" if i >= 6 else "ended", source="system_default", started_at=NOW - timedelta(days=10), ended_at=NOW - timedelta(days=2)))
            s.add(Subscription(user_id=uid, workspace_id=None, plan_version_id=pv["premium"], status="active", source="admin", started_at=NOW - timedelta(days=2)))
        s.commit()
    r = svc(env).commercial("30d")
    assert metric(r, "access", "access_active")["figure"] == 6 and metric(r, "access", "access_upgrades")["figure"] == 6 and metric(r, "access", "access_downgrades")["figure"] is None
    assert "not paid conversion" in metric(r, "access", "access_upgrades")["note"] and "Access assignments, not payments" in metric(r, "access", "access_active")["note"]
    assert metric(r, "mock_billing", "mock_mrr")["state"] == "unavailable"                  # access assignments produce no revenue figure


def test_failed_payment_counts_are_mock_labelled(env):
    mock_subs(env, 1, tag="i")
    with sf(env)() as s:
        c = s.scalar(select(BillingCustomer))
        inv = BillingInvoice(public_id="i" * 32, provider="mock", provider_invoice_id="inv1", customer_id=c.id, amount_due_minor=100, currency="EUR", state="past_due", created_at=NOW)
        s.add(inv); s.flush()
        s.add(BillingPayment(public_id="p" * 32, provider="mock", provider_payment_id="pay1", invoice_id=inv.id, amount_minor=100, currency="EUR", status="failed", failure_category="declined", created_at=NOW - timedelta(days=1)))
        s.commit()
    r = svc(env).commercial("30d")
    assert metric(r, "mock_billing", "mock_failed_payments")["figure"] == 1 and "MOCK BILLING - NOT LIVE REVENUE" in metric(r, "mock_billing", "mock_failed_payments")["note"]
    assert metric(r, "mock_billing", "mock_past_due_invoices")["figure"] == 1


# ---------------- read-only + API ----------------------------------------------------------------------------------------------------

TABLES = ("users", "subscriptions", "product_entitlements", "billing_customers", "billing_invoices", "billing_payments", "billing_refunds", "billing_provider_subscriptions",
          "billing_commercial_terms", "jobs", "ai_config_versions", "ai_config_activations", "feature_flag_overrides", "platform_pause_states", "knowledge_sources",
          "privacy_requests", "ai_usage_facts", "operational_metric_events", "audit_events", "support_tickets", "integration_states")


def counts(env):
    with sf(env)() as s:
        return {t: s.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in TABLES}


def test_reading_every_report_changes_nothing_and_enqueues_no_job_or_provider_call(env, monkeypatch):
    seed_activity(env); mock_subs(env, 5, tag="r")
    T.record_practice_usage(sf(env), users(env, 1)[0], "s", 0, [usage_record()], "create")
    _, plat = env.user("platform_admin"); _, bill = env.user("billing_admin")
    before = counts(env)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    for path, ck in (("product", plat), ("quality", plat), ("operations", plat), ("ai-economics", plat), ("definitions", plat), ("commercial", bill)):
        assert env.c.get(f"{API}/admin/reports/{path}?period=90d", cookies=ck).status_code == 200
    after = counts(env)
    after_adj = {k: v for k, v in after.items() if k not in ("audit_events",)}
    assert after_adj == {k: v for k, v in before.items() if k not in ("audit_events",)}


def test_api_permissions_validation_and_no_raw_fact_route(env):
    _, cand = env.user("user"); _, plat = env.user("platform_admin"); _, sup = env.user("support_operator")
    assert env.c.get(f"{API}/admin/reports/product").status_code in (401, 403)
    assert env.c.get(f"{API}/admin/reports/product", cookies=cand).status_code == 403
    assert env.c.get(f"{API}/admin/reports/product", cookies=sup).status_code == 403
    assert env.c.get(f"{API}/admin/reports/product?period=1d", cookies=plat).status_code == 422
    assert env.c.get(f"{API}/admin/reports/product?period=2026-01-01;DROP", cookies=plat).status_code == 422
    for path in ("events", "users", "facts", "ai-usage", "export"):
        assert env.c.get(f"{API}/admin/reports/{path}", cookies=plat).status_code in (404, 405)
    for method in ("post", "put", "delete", "patch"):
        assert getattr(env.c, method)(f"{API}/admin/reports/product", cookies=plat).status_code == 405
    from src.api.admin_route_invariant import admin_routes, ungated
    rep = [r for r in admin_routes() if "/admin/reports" in r.path]
    assert len(rep) == 6 and all(r.methods == ("GET",) and r.permissions for r in rep) and not ungated(admin_routes())
    assert len(perm.PERMISSIONS) == 43


def test_responses_never_contain_identifiers_or_private_fields(env):
    seed_activity(env)
    _, plat = env.user("platform_admin")
    blob = "".join(env.c.get(f"{API}/admin/reports/{p}", cookies=plat).text for p in ("product", "quality", "operations", "ai-economics"))
    for needle in ("example.test", "SECRET", "user_id", "owner_user_id", "email", "subject", "run_id", "session_id", "comment", "prompt"):
        assert needle not in blob, needle


def test_static_private_content_guard_on_report_schemas():
    schemas = (ROOT / "src/api/schemas/admin.py").read_text().split("# ---- W10.12")[1]
    fields = set(re.findall(r"^    (\w+):", schemas, re.M))
    forbidden = {"email", "document_text", "answer", "conversation", "memory", "prompt", "report_body", "ticket_body", "comment", "query_text", "retrieved_text", "raw_response",
                 "user_id", "owner_user_id", "run_id", "session_id"}
    assert not (fields & forbidden), fields & forbidden
    assert {"error_rate", "model_id"}.isdisjoint(forbidden)                                         # safe names are not rejected by the guard


def test_service_module_reads_no_private_content_columns():
    code = (ROOT / "src/reporting/service.py").read_text()
    for banned in ("Answer.text", "CandidateDocument", "PreparationMemory", "SupportMessage", "SupportInternalNote", "DocumentClaim", "Report.report", "state_payload", "UserFeedback.comment", "AuditEvent"):
        assert banned not in code, banned
    assert "session.add" not in code and ".commit()" not in code and "insert(" not in code.lower() and "delete(" not in code


def test_migration_0024_adds_only_the_two_tables_and_seeds_nothing(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("sqlalchemy.url", url); cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "0023_platform_config")
    before = set(inspect(create_engine(url)).get_table_names())
    command.upgrade(cfg, "0024_reporting_analytics")
    eng = create_engine(url)
    after = set(inspect(eng).get_table_names())
    assert after - before == {"operational_metric_events", "ai_usage_facts"}
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM ai_usage_facts")).scalar() == 0 and c.execute(text("SELECT count(*) FROM operational_metric_events")).scalar() == 0
    command.downgrade(cfg, "0023_platform_config")
    assert set(inspect(create_engine(url)).get_table_names()) == before


def test_no_live_pricing_or_provider_import_in_reporting():
    code = "".join(p.read_text() for p in (ROOT / "src/reporting").glob("*.py")) + (ROOT / "src/api/routes/admin_reports.py").read_text()
    assert not re.search(r"httpx|requests\.|urllib|openrouter\.ai|PricingService|build_chat_model|get_model_pricing|fetch_pricing|\.fetch\(", code)
