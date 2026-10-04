"""ReportingService (P10B-W10.12). READ-ONLY, aggregate-only, evidence-driven.

Every method is a SELECT over authoritative domains or the bounded telemetry tables. Nothing here writes, enqueues a job, calls a provider or model, reads
candidate content (answers, reports, chats, documents, queries), or returns an identifier. A metric without evidence is reported ``unavailable`` or
``not_captured``, never zero; a candidate cohort below ``REPORTING_MIN_COHORT`` is suppressed (value ``None``, never the count).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from sqlalchemy import func, select

from src.persistence import (
    AIUsageFact, Answer, BillingCommercialTerms, BillingInvoice, BillingPayment, BillingProviderSubscription, Interview, InterviewSession,
    Opportunity, OperationalMetricEvent, PlanVersion, PreparationRun, Question, Subscription, SupportTicket, User, UserFeedback, utcnow,
)
from src.reporting import suppression as S
from src.reporting.definitions import (
    DEFAULT_PERIOD, METRICS, PERIODS, PLAN_ORDER, STATE_NOT_CAPTURED,
)


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    d = _utc(dt)
    return d.isoformat() if d else None


class ReportingError(ValueError):
    pass


class ReportingService:
    def __init__(self, session_factory, *, clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._clock = clock

    # ------------------------------------------------------------------ periods
    def window(self, period: str | None) -> tuple[str, datetime | None, datetime]:
        period = period or DEFAULT_PERIOD
        if period not in PERIODS:
            raise ReportingError("Unknown reporting period.")
        now = _utc(self._clock())
        days = PERIODS[period]
        return period, (now - timedelta(days=days) if days else None), now

    @staticmethod
    def _in(col, since, now):
        conds = [col < now]
        if since is not None:
            conds.append(col >= since)
        return conds

    def _envelope(self, period: str, since, now, sections: list[dict]) -> dict:
        return {"period": period, "window_start": _iso(since), "window_end": _iso(now), "generated_at": _iso(now), "utc": True,
                "privacy": "Aggregates only. Candidate cohorts below the engineering privacy floor are suppressed (this is not an anonymisation guarantee).",
                "sections": sections}

    def definitions(self) -> dict:
        return {"min_cohort_policy": "suppressed", "periods": list(PERIODS), "default_period": DEFAULT_PERIOD,
                "metrics": [{"metric_id": m.metric_id, "label": m.label, "source": m.source, "definition": m.definition, "cohort_policy": m.cohort_policy,
                             "coverage": m.coverage} for m in METRICS]}

    # ------------------------------------------------------------------ product
    def product(self, period: str | None = None) -> dict:
        period, since, now = self.window(period)
        with self._sf() as s:
            cand = select(User.id).where(User.platform_role == "user")
            regs = s.execute(select(User.id, User.onboarding_completed_at).where(User.platform_role == "user", *self._in(User.created_at, since, now))).all()
            n_regs = len(regs)
            onboarded_now = sum(1 for _i, c in regs if c is not None)
            n_onb_period = s.scalar(select(func.count()).select_from(User).where(User.platform_role == "user", User.onboarding_completed_at.is_not(None),
                                                                                  *self._in(User.onboarding_completed_at, since, now))) or 0

            opp = s.execute(select(Opportunity.user_id, func.count()).where(Opportunity.user_id.in_(cand), *self._in(Opportunity.created_at, since, now))
                            .group_by(Opportunity.user_id)).all()
            prep = s.execute(select(PreparationRun.owner_user_id, PreparationRun.state).where(
                PreparationRun.owner_user_id.in_(cand), PreparationRun.source == "created", *self._in(PreparationRun.created_at, since, now))).all()
            sessions = s.execute(select(InterviewSession.session_id, InterviewSession.user_id).where(
                InterviewSession.user_id.in_(cand), *self._in(InterviewSession.created_at, since, now))).all()
            live_ids = {sid for sid, _u in sessions}
            interviews = s.execute(select(Interview.id, Interview.user_id, Interview.source_session_id, Interview.status).where(
                Interview.user_id.in_(cand), *self._in(Interview.created_at, since, now))).all()
            practice_users: set[int] = {u for _sid, u in sessions}
            extra = [(i, u) for i, u, src, _st in interviews if not src or src not in live_ids]
            practice_started = len(live_ids) + len(extra)
            practice_users |= {u for _i, u in extra}
            completed = [(i, u) for i, u, _src, st in interviews if st == "completed"]
            completed_users = {u for _i, u in completed}

            first_action, days = self._activity(s, cand)
        opp_total = sum(n for _u, n in opp)
        opp_users = len(opp)
        prep_users = {u for u, _st in prep}
        prep_ready = sum(1 for _u, st in prep if st == "ready")

        regs_ids = {i for i, _c in regs}
        activated_of_regs = sum(1 for u in regs_ids if u in first_action)
        activated_in_period = [u for u, t in first_action.items() if (since is None or t >= since) and t < now]
        in_period_days: dict[int, set] = defaultdict(set)
        for u, ds in days.items():
            for d in ds:
                dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                if (since is None or dt >= since.replace(hour=0, minute=0, second=0, microsecond=0)) and dt < now:
                    in_period_days[u].add(d)
        active = len(in_period_days)
        returning = sum(1 for ds in in_period_days.values() if len(ds) >= 2)

        m = S.metric
        coverage_hist = "Historical, from authoritative rows"
        metrics = [
            m("registrations", "Registrations", n_regs, cohort=n_regs, coverage=coverage_hist),
            m("onboarding_completed", "Onboarding completed in the period", n_onb_period, cohort=n_onb_period, coverage=coverage_hist,
              note="Uses the exact completion timestamp. Accounts that predate onboarding were back-filled as completed."),
            m("onboarding_rate", "Onboarding completion of period registrants", S.rate(onboarded_now, n_regs), cohort=n_regs, unit="percent", coverage=coverage_hist,
              note="Current completion state of the accounts registered in the period."),
            m("opportunities_created", "Opportunities created", opp_total, cohort=opp_users, coverage=coverage_hist),
            m("opportunities_per_candidate", "Opportunities per candidate using them", round(opp_total / opp_users, 2) if opp_users else None, cohort=opp_users, unit="ratio", coverage=coverage_hist),
            m("prepare_started", "Prepare runs started", len(prep), cohort=len(prep_users), coverage="From the W10.10 ownership index onward",
              note="Back-filled index rows are excluded: their creation time is the back-fill time, not the run time."),
            m("prepare_ready_rate", "Prepare runs reaching ready", S.rate(prep_ready, len(prep), cohort=len(prep_users)), cohort=len(prep_users), unit="percent",
              coverage="From the W10.10 ownership index onward", note="'Ready' means the run finished without failing; it is not a quality judgement."),
            m("practice_started", "Practice sessions started", practice_started, cohort=len(practice_users), partial=True, coverage="Lower bound",
              note="Live sessions plus completed history. Sessions abandoned and pruned by retention are not recoverable."),
            m("practice_completed", "Practice sessions completed", len(completed), cohort=len(completed_users), coverage=coverage_hist),
            m("practice_completion_rate", "Practice completion", S.rate(len(completed_users & practice_users), len(practice_users)),
              cohort=len(practice_users), unit="percent", partial=True, coverage="Lower bound", note="Share of candidates who started Practice and completed at least one interview in the period."),
            m("activated_candidates", "Candidates whose first substantive action fell in the period", len(activated_in_period), cohort=len(activated_in_period), partial=True,
              coverage="Lower bound", note="Product activation = a candidate's first Opportunity, Prepare run or Practice session. It is an analytics definition, not an access or billing state."),
            m("activation_rate", "Period registrants with a substantive action", S.rate(activated_of_regs, n_regs), cohort=n_regs, unit="percent", partial=True, coverage="Lower bound",
              note="Registrants of the period with any Opportunity, Prepare run or Practice session to date."),
            m("active_candidates", "Candidates with substantive activity", active, cohort=active, partial=True, coverage="Lower bound"),
            m("returning_candidates", "Returning candidates", returning, cohort=returning, partial=True, coverage="Lower bound",
              note="Substantive activity on at least two distinct UTC dates inside the period."),
            m("returning_rate", "Returning share of active candidates", S.rate(returning, active), cohort=active, unit="percent", partial=True, coverage="Lower bound"),
        ]
        return self._envelope(period, since, now, [{
            "section_id": "product", "title": "Product", "coverage": "Historical from authoritative rows; Prepare from the W10.10 index; Practice is a lower bound.",
            "captured_since": None, "note": "No page-view, click or device tracking exists or is used.", "metrics": metrics, "tables": []}])

    def _activity(self, s, cand) -> tuple[dict[int, datetime], dict[int, set]]:
        """(first substantive action time per candidate, distinct UTC activity dates per candidate) over Opportunity, Prepare (created) and Practice."""
        first: dict[int, datetime] = {}
        days: dict[int, set] = defaultdict(set)
        rows = []
        rows += s.execute(select(Opportunity.user_id, Opportunity.created_at).where(Opportunity.user_id.in_(cand))).all()
        rows += s.execute(select(PreparationRun.owner_user_id, PreparationRun.created_at).where(PreparationRun.owner_user_id.in_(cand), PreparationRun.source == "created")).all()
        rows += s.execute(select(InterviewSession.user_id, InterviewSession.created_at).where(InterviewSession.user_id.in_(cand))).all()
        rows += s.execute(select(Interview.user_id, Interview.created_at).where(Interview.user_id.in_(cand))).all()
        for uid, at in rows:
            t = _utc(at)
            if t is None:
                continue
            if uid not in first or t < first[uid]:
                first[uid] = t
            days[uid].add(t.date())
        return first, days

    # ------------------------------------------------------------------ quality
    def quality(self, period: str | None = None) -> dict:
        period, since, now = self.window(period)
        with self._sf() as s:
            cand = select(User.id).where(User.platform_role == "user")
            fb = s.execute(select(UserFeedback.rating, UserFeedback.category, func.count(), func.count(func.distinct(UserFeedback.user_id))).where(
                UserFeedback.user_id.in_(cand), *self._in(UserFeedback.created_at, since, now)).group_by(UserFeedback.rating, UserFeedback.category)).all()
            fb_users = s.scalar(select(func.count(func.distinct(UserFeedback.user_id))).where(UserFeedback.user_id.in_(cand), *self._in(UserFeedback.created_at, since, now))) or 0
            rating_rows = s.execute(select(UserFeedback.rating, func.count(), func.count(func.distinct(UserFeedback.user_id))).where(
                UserFeedback.user_id.in_(cand), *self._in(UserFeedback.created_at, since, now)).group_by(UserFeedback.rating)).all()
            # numeric field only: the JSON path is evaluated inside the database, so no answer text or narrative is ever loaded
            score = Answer.evaluation["overall_score"].as_float()
            ev = s.execute(select(func.count(), func.avg(score), func.count(func.distinct(Interview.user_id))).select_from(Answer).join(Question, Answer.question_id == Question.id)
                           .join(Interview, Question.interview_id == Interview.id).where(Interview.user_id.in_(cand), score.is_not(None),
                                                                                       *self._in(Interview.created_at, since, now))).one()
            ops = self._operational(s, since, now)
        m = S.metric
        rating_table = S.partition([{"label": r or "unknown", "values": [n], "cohort": u} for r, n, u in rating_rows])
        cat_buckets = [{"label": c or "uncategorised", "values": [n], "cohort": u} for r, c, n, u in fb]
        metrics = [
            m("feedback_total", "Candidates who gave feedback", fb_users, cohort=fb_users, coverage="Historical, from authoritative rows",
              note="Counts distinct candidates. Comment text and the rated content are never read."),
            m("evaluation_score_avg", "Average answer evaluation score", round(float(ev[1]), 1) if ev[1] is not None else None, cohort=int(ev[2] or 0), unit="score",
              coverage="Historical, from authoritative rows", note="Mean of the stored numeric overall score only. No individual score, answer or narrative is shown."),
            m("evaluation_count", "Evaluated answers", int(ev[0] or 0), cohort=int(ev[2] or 0), coverage="Historical, from authoritative rows"),
            S.not_captured("evaluator_runs", "Offline evaluator results", "No safe structured store of evaluator runs exists in production; the repository's offline reports are not read by Admin reporting.", "Not captured"),
        ] + ops["metrics"]
        tables = [
            {"table_id": "feedback_rating", "title": "Feedback by rating (answers counted)", "columns": ["Answers"], "rows": rating_table, "note": "Buckets below the floor are suppressed; the smallest remaining bucket may be suppressed too."},
            {"table_id": "feedback_category", "title": "Feedback by category (answers counted)", "columns": ["Answers"], "rows": S.partition(cat_buckets), "note": "Safe, code-defined categories only."},
        ] + ops["tables"]
        return self._envelope(period, since, now, [{
            "section_id": "quality", "title": "Quality", "coverage": "Feedback and evaluation scores are historical; retrieval, request and provider outcomes are captured since W10.12.",
            "captured_since": ops["captured_since"], "note": "", "metrics": metrics, "tables": tables}])

    def _operational(self, s, since, now) -> dict:
        """Retrieval / request / provider telemetry (pure operational facts: no candidate cohort, no identifiers)."""
        first = s.scalar(select(func.min(OperationalMetricEvent.occurred_at)))
        base = self._in(OperationalMetricEvent.occurred_at, since, now)
        captured = _iso(first)
        if first is None:
            nc = lambda mid, label: S.not_captured(mid, label, "No event has been captured yet.", "Captured since first event")   # noqa: E731
            return {"captured_since": None, "metrics": [nc("retrieval_outcomes", "Retrieval outcomes"), nc("request_outcomes", "Request outcomes"), nc("provider_calls", "Provider call outcomes")], "tables": []}
        rows = s.execute(select(OperationalMetricEvent.event_type, OperationalMetricEvent.operation, OperationalMetricEvent.outcome, func.count(),
                                func.avg(OperationalMetricEvent.duration_ms)).where(*base).group_by(
            OperationalMetricEvent.event_type, OperationalMetricEvent.operation, OperationalMetricEvent.outcome)).all()
        durations: dict[tuple[str, str], list[int]] = defaultdict(list)
        for et, op, d in s.execute(select(OperationalMetricEvent.event_type, OperationalMetricEvent.operation, OperationalMetricEvent.duration_ms).where(
                *base, OperationalMetricEvent.duration_ms.is_not(None), OperationalMetricEvent.event_type.in_(("request", "provider_call")))).all():
            durations[(et, op)].append(int(d))
        agg: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for et, op, outcome, n, _avg in rows:
            agg[(et, op)][outcome] += int(n)
        tables, metrics = [], []
        for et, title, mid in (("retrieval", "Retrieval outcomes", "retrieval_outcomes"), ("request", "Request outcomes", "request_outcomes"), ("provider_call", "Provider call outcomes", "provider_calls")):
            keys = sorted(k for k in agg if k[0] == et)
            total = sum(sum(agg[k].values()) for k in keys)
            if not keys:
                metrics.append(S.not_captured(mid, title, "No event of this type has been captured in the period.", "Captured since first event"))
                continue
            metrics.append(S.metric(mid, title + " (events)", total, operational=True, coverage="Captured since first event"))
            if et == "retrieval":
                trows = [{"label": k[1], "cells": [{"figure": agg[k].get("hit", 0), "suppressed": False}, {"figure": agg[k].get("abstained", 0), "suppressed": False},
                                                   {"figure": agg[k].get("error", 0), "suppressed": False}]} for k in keys]
                tables.append({"table_id": mid, "title": title, "columns": ["Evidence found", "Abstained", "Errors"], "rows": trows, "note": "Counts of events. No query or evidence is stored."})
            else:
                trows = []
                for k in keys:
                    ds = sorted(durations.get(k, []))
                    n_all = sum(agg[k].values())
                    bad = n_all - agg[k].get("success", 0)
                    trows.append({"label": k[1], "cells": [{"figure": n_all, "suppressed": False}, {"figure": round(100.0 * bad / n_all, 1), "suppressed": False},
                                                           {"figure": _pct(ds, 0.5), "suppressed": False}, {"figure": _pct(ds, 0.95), "suppressed": False}]})
                tables.append({"table_id": mid, "title": title, "columns": ["Events", "Failure rate %", "p50 ms", "p95 ms"], "rows": trows,
                               "note": "Observed real calls only; failure rate = anything other than success."})
        return {"captured_since": captured, "metrics": metrics, "tables": tables}

    # ------------------------------------------------------------------ operations
    def operations(self, period: str | None = None, *, job_stats: dict | None = None, integration_stats: dict | None = None, knowledge_stats: dict | None = None,
                   support_stats: dict | None = None, pause_stats: dict | None = None, flag_stats: dict | None = None) -> dict:
        period, since, now = self.window(period)
        with self._sf() as s:
            tickets = s.execute(select(SupportTicket.status, func.count()).group_by(SupportTicket.status)).all()
            resolved = s.execute(select(SupportTicket.created_at, SupportTicket.resolved_at).where(SupportTicket.resolved_at.is_not(None),
                                                                                                   *self._in(SupportTicket.resolved_at, since, now))).all()
            ops = self._operational(s, since, now)
        hours = sorted((_utc(r) - _utc(c)).total_seconds() / 3600.0 for c, r in resolved if r and c)
        m = lambda mid, label, v, **k: S.metric(mid, label, v, operational=True, **k)   # noqa: E731
        sections: list[dict] = []
        q = (job_stats or {}).get("queue")
        sections.append({"section_id": "jobs", "title": "Jobs", "coverage": "Current state (W10.9)", "captured_since": None, "note": "Reads the queue; never enqueues, retries or cancels.",
                         "metrics": [m(f"jobs_{k}", k.replace("_", " ").capitalize(), (q or {}).get(k), coverage="Current state") if q else S.not_captured(f"jobs_{k}", k, "Job statistics unavailable.")
                                     for k in ("queued", "running", "retry_waiting", "failed", "succeeded", "stale_leases")]
                                    + [m("jobs_oldest_ready_age_s", "Oldest ready job age (s)", (q or {}).get("oldest_ready_age_seconds"), unit="seconds") if q else S.not_captured("jobs_oldest", "Oldest ready job age", "Unavailable.")],
                         "tables": []})
        ig = integration_stats
        sections.append({"section_id": "integrations", "title": "Integrations", "coverage": "Current state (W10.6)", "captured_since": None,
                         "note": "Health is only what a manual test recorded; no connection is tested for reporting.",
                         "metrics": [m(f"integrations_{k}", k.replace("_", " ").capitalize(), (ig or {}).get(k)) if ig else S.not_captured(f"integrations_{k}", k, "Unavailable.")
                                     for k in ("total", "configured", "runtime_active", "not_tested", "unhealthy")], "tables": []})
        kn = knowledge_stats
        sections.append({"section_id": "knowledge", "title": "Knowledge", "coverage": "Current state (W10.8)", "captured_since": None, "note": "Counts only; no source text.",
                         "metrics": [m(f"knowledge_{k}", k.replace("_", " ").capitalize(), (kn or {}).get(k)) if kn else S.not_captured(f"knowledge_{k}", k, "Unavailable.")
                                     for k in ("sources", "awaiting_review", "indexing", "failed", "indexed_not_active", "active")], "tables": []})
        sup_rows = [{"label": st, "cells": [{"figure": n, "suppressed": False}]} for st, n in sorted(tickets)]
        sections.append({"section_id": "support", "title": "Support", "coverage": "Historical, from ticket timestamps", "captured_since": None, "note": "Counts and timings only; no ticket text.",
                         "metrics": [m("support_resolved", "Tickets resolved in the period", len(hours), coverage="Historical"),
                                     m("support_resolution_median_h", "Median resolution time (hours)", round(hours[len(hours) // 2], 1) if hours else None, unit="hours",
                                       state=STATE_NOT_CAPTURED if not hours else None, note="No ticket was resolved in the period." if not hours else "")],
                         "tables": [{"table_id": "support_status", "title": "Tickets by status", "columns": ["Tickets"], "rows": sup_rows, "note": ""}]})
        ps, fs = pause_stats, flag_stats
        sections.append({"section_id": "runtime", "title": "Runtime state", "coverage": "Current state (W10.11)", "captured_since": None, "note": "",
                         "metrics": [m("runtime_paused", "Paused capabilities", (ps or {}).get("paused_count")) if ps else S.not_captured("runtime_paused", "Paused capabilities", "Unavailable."),
                                     m("runtime_overrides", "Feature overrides", (fs or {}).get("overrides")) if fs and "overrides" in fs else S.not_captured("runtime_overrides", "Feature overrides", "Unavailable.")],
                         "tables": []})
        sections.append({"section_id": "telemetry", "title": "Requests, providers and retrieval", "coverage": "Captured since W10.12", "captured_since": ops["captured_since"],
                         "note": "Operational telemetry has no candidate identity. Provider calls are real runtime calls only.", "metrics": ops["metrics"], "tables": ops["tables"]})
        return self._envelope(period, since, now, sections)

    # ------------------------------------------------------------------ AI economics
    def ai_economics(self, period: str | None = None) -> dict:
        period, since, now = self.window(period)
        with self._sf() as s:
            facts = s.execute(select(AIUsageFact.user_id, AIUsageFact.workflow, AIUsageFact.model_id, AIUsageFact.model_calls, AIUsageFact.input_tokens, AIUsageFact.output_tokens,
                                     AIUsageFact.total_tokens, AIUsageFact.cost_usd_micros, AIUsageFact.token_coverage, AIUsageFact.cost_coverage, AIUsageFact.occurred_at).where(
                *self._in(AIUsageFact.occurred_at, since, now))).all()
            first = s.scalar(select(func.min(AIUsageFact.occurred_at)))
        captured = _iso(first)
        if not facts:
            nc = S.not_captured("ai_usage", "AI usage", "No AI usage has been captured in this period." if first else "No AI usage has been captured yet.", "Captured since first fact")
            return self._envelope(period, since, now, [{"section_id": "ai_economics", "title": "AI economics", "coverage": "Captured since W10.12", "captured_since": captured,
                                                         "note": "Unknown tokens and unknown cost are never shown as zero.", "metrics": [nc], "tables": []}])

        def totals(rows) -> dict:
            calls = sum(r[3] for r in rows)
            known_tok = [r for r in rows if r[6] is not None]
            known_cost = [r for r in rows if r[7] is not None]
            return {"facts": len(rows), "calls": calls, "tokens": sum(r[6] for r in known_tok), "tok_facts": len(known_tok), "cost_micros": sum(r[7] for r in known_cost),
                    "cost_facts": len(known_cost), "users": len({r[0] for r in rows if r[0] is not None})}
        t = totals(facts)
        m = S.metric
        tok_cov = round(100.0 * t["tok_facts"] / t["facts"], 1)
        cost_cov = round(100.0 * t["cost_facts"] / t["facts"], 1)
        partial_cost = t["cost_facts"] < t["facts"]
        users = t["users"]
        metrics = [
            m("ai_calls", "Model calls captured", t["calls"], cohort=users, coverage="Captured since first fact"),
            m("ai_tokens_known", "Known tokens", t["tokens"] if t["tok_facts"] else None, cohort=users, partial=t["tok_facts"] < t["facts"], coverage=f"Token coverage {tok_cov}% of usage units",
              state=STATE_NOT_CAPTURED if not t["tok_facts"] else None, note="Units without token data are excluded, not counted as zero."),
            m("ai_token_coverage", "Token coverage", tok_cov, cohort=users, unit="percent", coverage="Share of usage units with token data"),
            m("ai_known_cost_usd", "Known cost (USD, " + ("partial coverage" if partial_cost else "full coverage") + ")", round(t["cost_micros"] / 1_000_000, 6) if t["cost_facts"] else None,
              cohort=users, unit="usd", partial=partial_cost, coverage=f"Cost coverage {cost_cov}% of usage units", state=STATE_NOT_CAPTURED if not t["cost_facts"] else None,
              note="Sum of costs that are known (reported or calculated). Unknown cost is not zero and is excluded."),
            m("ai_cost_coverage", "Cost coverage", cost_cov, cohort=users, unit="percent", coverage="Share of usage units with a known cost"),
            m("ai_tokens_per_candidate", "Average known tokens per candidate", round(t["tokens"] / users, 1) if users and t["tok_facts"] else None, cohort=users, unit="tokens", partial=True),
            m("ai_cost_per_candidate", "Average known cost per candidate (USD)", round(t["cost_micros"] / 1_000_000 / users, 6) if users and t["cost_facts"] else None, cohort=users, unit="usd", partial=True),
        ]
        by_workflow: dict[str, list] = defaultdict(list)
        by_model: dict[str, list] = defaultdict(list)
        for r in facts:
            by_workflow[r[1]].append(r)
            by_model[r[2] or "unknown model"].append(r)

        def bucket(label, rows):
            x = totals(rows)
            return {"label": label, "cohort": x["users"], "values": [x["calls"], x["tokens"] if x["tok_facts"] else None,
                                                                   round(x["cost_micros"] / 1_000_000, 6) if x["cost_facts"] else None,
                                                                   round(100.0 * x["cost_facts"] / x["facts"], 1)]}
        cols = ["Model calls", "Known tokens", "Known cost USD", "Cost coverage %"]
        wf = S.partition([bucket(k, v) for k, v in sorted(by_workflow.items())])
        md = S.partition([bucket(k, v) for k, v in sorted(by_model.items())])
        ranked_cost = sorted(((round(totals(v)["cost_micros"] / 1_000_000, 6), k) for k, v in by_workflow.items() if totals(v)["cost_facts"]), reverse=True)
        ranked_tok = sorted(((totals(v)["tokens"], k) for k, v in by_workflow.items() if totals(v)["tok_facts"]), reverse=True)
        # a ranking is a function of bucket values, so it only lists buckets whose cells are visible after suppression
        visible = {r["label"] for r in wf if not r["cells"][0]["suppressed"]}
        tables = [
            {"table_id": "ai_by_workflow", "title": "Usage by workflow", "columns": cols, "rows": wf, "note": "Agent usage is one cumulative aggregate per run; Practice usage is one record per operation."},
            {"table_id": "ai_by_model", "title": "Usage by approved model", "columns": cols, "rows": md,
             "note": "Agent usage is attributed to the model of its run profile; models are the W10.7-approved identifiers."},
            {"table_id": "ai_rank_cost", "title": "Workflows ranked by known cost", "columns": ["Known cost USD"], "rows": [{"label": k, "cells": [{"figure": v, "suppressed": False}]} for v, k in ranked_cost if k in visible], "note": "Ranked by known cost only."},
            {"table_id": "ai_rank_tokens", "title": "Workflows ranked by known tokens", "columns": ["Known tokens"], "rows": [{"label": k, "cells": [{"figure": v, "suppressed": False}]} for v, k in ranked_tok if k in visible], "note": "Ranked separately by tokens."},
        ]
        return self._envelope(period, since, now, [{"section_id": "ai_economics", "title": "AI economics", "coverage": "Captured since " + (captured or "first fact"), "captured_since": captured,
                                                     "note": "Observed usage only: no live pricing is fetched. Unknown tokens and unknown cost are never shown as zero.", "metrics": metrics, "tables": tables}])

    # ------------------------------------------------------------------ commercial (separate permission)
    def commercial(self, period: str | None = None) -> dict:
        period, since, now = self.window(period)
        with self._sf() as s:
            subs = s.execute(select(Subscription.user_id, Subscription.workspace_id, Subscription.status, Subscription.source, Subscription.started_at, Subscription.ended_at,
                                    PlanVersion.plan_code).join(PlanVersion, Subscription.plan_version_id == PlanVersion.id)).all()
            ps = s.execute(select(BillingProviderSubscription.id, BillingProviderSubscription.provider_state, BillingProviderSubscription.customer_id,
                                  BillingProviderSubscription.commercial_terms_id, BillingProviderSubscription.plan_version_id)).all()
            terms = {t.id: t for t in s.scalars(select(BillingCommercialTerms)).all()}
            active_terms = {t.plan_version_id: t for t in terms.values() if t.state == "active"}
            failed = s.scalar(select(func.count()).select_from(BillingPayment).where(BillingPayment.status == "failed", *self._in(BillingPayment.created_at, since, now))) or 0
            past_due_inv = s.scalar(select(func.count()).select_from(BillingInvoice).where(BillingInvoice.state == "past_due")) or 0
        m = S.metric
        mock_note = "MOCK BILLING - NOT LIVE REVENUE"

        def subject(u, w):
            return ("u", u) if u is not None else ("w", w)
        active_now = [x for x in subs if x[2] == "active" and x[5] is None]
        by_plan: dict[str, set] = defaultdict(set)
        by_source: dict[str, set] = defaultdict(set)
        for x in active_now:
            by_plan[x[6]].add(subject(x[0], x[1]))
            by_source[x[3]].add(subject(x[0], x[1]))
        n_active = len({subject(x[0], x[1]) for x in active_now})
        up = down = 0
        history: dict[tuple, list] = defaultdict(list)
        for x in subs:
            history[subject(x[0], x[1])].append((_utc(x[4]), x[6]))
        movers_up, movers_down = set(), set()
        for sub_key, rows in history.items():
            rows.sort()
            for (t0, p0), (t1, p1) in zip(rows, rows[1:]):
                if p0 in PLAN_ORDER and p1 in PLAN_ORDER and p0 != p1 and (since is None or t1 >= since) and t1 < now:
                    if PLAN_ORDER[p1] > PLAN_ORDER[p0]:
                        movers_up.add(sub_key)
                    else:
                        movers_down.add(sub_key)
        up, down = len(movers_up), len(movers_down)
        access = [
            m("access_active", "Active access-plan assignments (subjects)", n_active, cohort=n_active, coverage="Historical, from subscriptions",
              note="Access assignments, not payments. Nothing here is revenue."),
            m("access_upgrades", "Access-plan upgrades in the period", up, cohort=up, coverage="Historical, from subscriptions", note="Basic to Premium access assignments; not paid conversion."),
            m("access_downgrades", "Access-plan downgrades in the period", down, cohort=down, coverage="Historical, from subscriptions"),
        ]
        plan_rows = S.partition([{"label": k, "values": [len(v)], "cohort": len(v)} for k, v in sorted(by_plan.items())])
        src_rows = S.partition([{"label": k, "values": [len(v)], "cohort": len(v)} for k, v in sorted(by_source.items())])

        # mock MRR / ARR: ACTIVE mock provider subscriptions with terms; per currency; integer minor units; ROUND_HALF_UP
        eligible = [p for p in ps if p[1] == "active"]
        per_cur: dict[str, dict[str, int]] = defaultdict(lambda: {"priced": 0, "mrr": 0, "arr": 0})
        priced = 0
        for sid, state, cust, term_id, pv in eligible:
            t = terms.get(term_id) if term_id else active_terms.get(pv)
            if t is None:
                continue
            priced += 1
            amt = Decimal(t.amount_minor)
            if t.billing_interval == "year":
                mrr, arr = (amt / Decimal(12)).quantize(Decimal(1), rounding=ROUND_HALF_UP), amt
            else:
                mrr, arr = amt, amt * 12
            c = per_cur[t.currency]
            c["priced"] += 1
            c["mrr"] += int(mrr)
            c["arr"] += int(arr)
        by_state: dict[str, int] = defaultdict(int)
        for p in ps:
            by_state[p[1]] += 1
        billing = [
            m("mock_eligible", "Active mock provider subscriptions", len(eligible), cohort=len(eligible), coverage="Mock billing state", note=mock_note),
            m("mock_priced", "Of which priced (configured terms)", priced, cohort=len(eligible), coverage="Mock billing state", note="A subscription without terms is excluded, never valued at zero."),
            m("mock_failed_payments", "Failed mock payments in the period", failed, operational=True, coverage="Mock billing state", note=mock_note),
            m("mock_past_due_invoices", "Past-due mock invoices", past_due_inv, operational=True, coverage="Mock billing state", note=mock_note),
            S.unavailable("mock_churn_rate", "Churn rate", "Churn rate unavailable with current historical evidence: only the CURRENT mock subscription state is stored, not cancellation events.", "Mock billing state"),
        ]
        if not eligible or not priced:
            billing += [S.unavailable("mock_mrr", "Mock MRR", "Unconfigured: no active mock subscription has commercial terms. This is not zero revenue.", "Mock billing state"),
                        S.unavailable("mock_arr", "Mock ARR", "Unconfigured: no active mock subscription has commercial terms. This is not zero revenue.", "Mock billing state")]
            cur_rows = []
        else:
            cur_rows = S.partition([{"label": cur, "values": [v["priced"], round(v["mrr"] / 100, 2), round(v["arr"] / 100, 2)], "cohort": v["priced"]} for cur, v in sorted(per_cur.items())])
        state_rows = S.partition([{"label": k, "values": [n], "cohort": n} for k, n in sorted(by_state.items())])
        tables = [
            {"table_id": "access_by_plan", "title": "Active access-plan assignments by plan", "columns": ["Subjects"], "rows": plan_rows, "note": "Access assignments, not payments."},
            {"table_id": "access_by_source", "title": "Active assignments by source", "columns": ["Subjects"], "rows": src_rows, "note": ""},
            {"table_id": "mock_recurring", "title": "Mock recurring value by currency (major units; never combined across currencies)", "columns": ["Priced subscriptions", "Mock MRR", "Mock ARR"],
             "rows": cur_rows, "note": mock_note + ". Active subscriptions only. Trialing, past due and cancelled are listed separately and excluded."},
            {"table_id": "mock_by_state", "title": "Mock provider subscriptions by state", "columns": ["Subscriptions"], "rows": state_rows, "note": mock_note},
        ]
        return self._envelope(period, since, now, [
            {"section_id": "access", "title": "Access-plan assignments", "coverage": "Historical, from subscriptions", "captured_since": None,
             "note": "Product subscriptions are access assignments, not payments.", "metrics": access, "tables": tables[:2]},
            {"section_id": "mock_billing", "title": "MOCK BILLING - NOT LIVE REVENUE", "coverage": "Mock billing state", "captured_since": None,
             "note": mock_note + ". No live provider, no collected revenue.", "metrics": billing, "tables": tables[2:]}]) | {"mock_billing": True, "label": mock_note}


def _pct(sorted_values: list[int], q: float) -> int | None:
    if not sorted_values:
        return None
    import math

    idx = min(len(sorted_values) - 1, max(0, math.ceil(q * len(sorted_values)) - 1))      # nearest-rank percentile
    return sorted_values[idx]
