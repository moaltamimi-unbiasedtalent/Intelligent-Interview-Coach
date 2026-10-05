#!/usr/bin/env python
"""P10B-W10.12 reporting guard (deterministic, offline, 0 paid/live calls).

High-risk invariants: aggregate-only read-only APIs (no raw-event or per-user route); a code-defined minimum cohort whose suppressed cells are null and never
leak a count or "<5"; secondary suppression of partitions; authoritative sources (users, opportunities, the Prepare index, Practice metadata); explicit
activation and return definitions; metrics without evidence unavailable, never zero; bounded operational telemetry (no path ids, query, body, identity);
AI usage captured once per canonical unit, idempotent, unknown stays unknown, micro-USD, no live pricing; commercial behind its own permission, access
assignments are not revenue, MOCK BILLING labelled, no cross-currency sum, no invented price, no fabricated churn; reports are read-only; permissions stay 43.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (W10.14): importing the pytest isolation module redirects DATABASE_URL/Chroma to a temp directory, disables .env and makes any non-temp engine FAIL FAST,
# so this evaluator can never write a developer store.
import tests.conftest  # noqa: E402,F401


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from sqlalchemy import select, text
    from sqlalchemy.orm import sessionmaker

    from src.agent.usage import aggregate_usage
    from src.application import admin_permissions as perm
    from src.persistence import AIUsageFact, Base, Opportunity, User, make_engine
    from src.reporting import suppression as S
    from src.reporting import telemetry as T
    from src.reporting.definitions import METRICS, PERIODS, REPORTING_MIN_COHORT
    from src.reporting.service import ReportingService

    service_src = read("src/reporting/service.py")
    routes = read("src/api/routes/admin_reports.py")
    schemas = read("src/api/schemas/admin.py").split("# ---- W10.12")[-1]
    telemetry_src = read("src/reporting/telemetry.py")

    # --- API surface ----------------------------------------------------------------------------------------------------------------
    paths = re.findall(r'@router\.(get|post|put|patch|delete)\("([^"]+)"', routes)
    check("all_report_routes_are_get_only", paths and all(m == "get" for m, _p in paths), f"{len(paths)} GET routes")
    check("no_raw_event_or_per_user_route", not any(re.search(r"event|user|fact|export|drill", p) for _m, p in paths), ", ".join(p for _m, p in paths))
    check("commercial_has_its_own_permission", "REPORTS_COMMERCIAL" in routes.split("def commercial")[0].split("@router.get")[-1] + routes.split("def commercial")[1].split("def ")[0][:400]
          and routes.count("REPORTS_READ") >= 4 and "REPORTS_COMMERCIAL" not in routes.split("def commercial")[0].split("def definitions")[0], "reports.read vs reports.commercial.read")
    check("permission_registry_stays_43", len(perm.PERMISSIONS) == 43, "43")
    check("periods_are_a_fixed_code_defined_set", set(PERIODS) == {"7d", "30d", "90d", "all_time"} and "Query(default=\"30d\", max_length=12)" in routes, "no client date expression")

    # --- private-content boundary ---------------------------------------------------------------------------------------------------
    fields = set(re.findall(r"^    (\w+):", schemas, re.M))
    banned = {"email", "document_text", "answer", "conversation", "memory", "prompt", "report_body", "ticket_body", "comment", "query_text", "retrieved_text", "raw_response",
              "user_id", "owner_user_id", "run_id", "session_id"}
    check("report_schemas_have_no_private_or_identifier_fields", not (fields & banned), ", ".join(sorted(fields & banned)) or f"{len(fields)} fields")
    check("service_reads_no_private_content_columns", not any(b in service_src for b in ("Answer.text", "CandidateDocument", "PreparationMemory", "SupportMessage", "SupportInternalNote",
                                                                                     "DocumentClaim", "state_payload", "UserFeedback.comment", "AuditEvent")), "metadata only")
    check("service_is_read_only", not re.search(r"session\.add\(|\.commit\(|\binsert\(|\bdelete\(|\bupdate\(|\.enqueue\(|\.flush\(", service_src), "SELECT only")
    check("no_live_pricing_or_provider_in_reporting", not re.search(r"httpx|requests\.|urllib|openrouter\.ai|PricingService|build_chat_model|get_model_pricing", service_src + routes + telemetry_src), "none")
    check("evaluation_score_reads_the_numeric_field_only", 'Answer.evaluation["overall_score"].as_float()' in service_src and "Answer.text" not in service_src, "JSON path evaluated in the database")
    check("prepare_uses_the_index_not_checkpoints", "PreparationRun" in service_src and not re.search(r"checkpoint|SqliteSaver|graph", service_src, re.I), "preparation_runs only")
    check("activation_and_return_defined", "first substantive" in read("src/reporting/definitions.py").lower() or "FIRST substantive" in read("src/reporting/definitions.py")
          and "two distinct UTC dates" in read("src/reporting/definitions.py"), "explicit analytics definitions")
    check("metric_definitions_registry_complete", len(METRICS) >= 18 and all(m.definition and m.source and m.coverage for m in METRICS), f"{len(METRICS)} metrics defined")

    # --- suppression ----------------------------------------------------------------------------------------------------------------
    check("min_cohort_is_a_code_constant", REPORTING_MIN_COHORT == 5 and "not an anonymisation guarantee" in read("src/reporting/suppression.py"), "5")
    small = S.metric("x", "X", 3, cohort=3)
    big = S.metric("x", "X", 7, cohort=7)
    check("suppressed_metric_is_null_without_count_or_threshold", small["figure"] is None and small["state"] == "suppressed" and "<" not in json.dumps(small) and "3" not in json.dumps({k: v for k, v in small.items() if k != "metric_id"}).replace("suppressed", ""),
          "value null; no count; no <5")
    check("sufficient_cohort_is_shown", big["figure"] == 7 and big["state"] == "available", "7")
    check("rate_needs_denominator_numerator_and_complement", S.rate(3, 6) is None and S.rate(2, 4) is None and S.rate(7, 12) == 58.3 and S.rate(0, 6) == 0.0 and S.rate(6, 6) == 100.0, "small groups never leak")
    part = S.partition([{"label": "A", "values": [1], "cohort": 4}, {"label": "B", "values": [2], "cohort": 6}, {"label": "C", "values": [3], "cohort": 9}])
    check("secondary_suppression_blocks_subtraction", [r["cells"][0]["suppressed"] for r in part] == [True, True, False], "never exactly one hidden bucket")

    # --- behaviour on a temp database ----------------------------------------------------------------------------------------------
    now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as d:
        eng = make_engine(f"sqlite:///{d}/rep.db")
        Base.metadata.create_all(eng)
        sf = sessionmaker(bind=eng, expire_on_commit=False)
        with sf() as s:
            ids = []
            for i in range(6):
                u = User(subject=f"e{i}", provider="eval", email=f"e{i}@example.test", platform_role="user", status="active", created_at=now - timedelta(days=3), updated_at=now,
                         onboarding_completed_at=now - timedelta(days=3))
                s.add(u)
                s.flush()
                ids.append(u.id)
                s.add(Opportunity(user_id=u.id, title="SECRET-TITLE", target_role="r", status="active", created_at=now - timedelta(days=2), updated_at=now))
            s.commit()
        svc = ReportingService(sf, clock=lambda: now)
        product = svc.product("30d")
        regs = next(m for m in product["sections"][0]["metrics"] if m["metric_id"] == "registrations")
        check("registrations_come_from_user_rows", regs["figure"] == 6 and svc.product("7d")["period"] == "7d", "6 candidate accounts")
        check("no_private_content_in_reports", "SECRET-TITLE" not in json.dumps([product, svc.quality("30d"), svc.operations("30d"), svc.ai_economics("30d"), svc.commercial("30d")]), "titles never read")
        empty_ai = svc.ai_economics("30d")["sections"][0]["metrics"][0]
        check("no_usage_means_not_captured_not_zero", empty_ai["state"] == "not_captured" and empty_ai["figure"] is None, "not captured")
        empty_q = svc.quality("30d")["sections"][0]["metrics"]
        check("no_telemetry_means_not_captured", all(m["state"] == "not_captured" for m in empty_q if m["metric_id"] in ("retrieval_outcomes", "request_outcomes", "provider_calls")), "not captured")
        comm = svc.commercial("30d")
        mrr = next(m for sct in comm["sections"] for m in sct["metrics"] if m["metric_id"] == "mock_mrr")
        churn = next(m for sct in comm["sections"] for m in sct["metrics"] if m["metric_id"] == "mock_churn_rate")
        check("mock_mrr_unconfigured_is_unavailable_not_zero", mrr["state"] == "unavailable" and mrr["figure"] is None, "unconfigured")
        check("churn_not_fabricated", churn["state"] == "unavailable" and "unavailable with current historical evidence" in churn["note"], "unavailable")
        check("billing_is_labelled_mock", comm["mock_billing"] is True and comm["label"] == "MOCK BILLING - NOT LIVE REVENUE" and "MOCK BILLING - NOT LIVE REVENUE" in comm["sections"][1]["title"], "banner in the contract")
        check("access_assignments_are_not_revenue", "Access assignments, not payments" in json.dumps(comm) and "not paid conversion" in json.dumps(comm), "labelled")

        # AI usage: one canonical unit, idempotent, unknown stays unknown, micro-USD
        entries = [{"source": "agent", "kind": "agent", "model_calls": 1, "model": "m", "input_tokens": 100, "output_tokens": 20, "total_tokens": 120, "reported_cost_usd": 0.001, "has_usage": True},
                   {"source": "tool:AnalyzeJobDescription", "kind": "tool", "model_calls": 1, "model": "m", "input_tokens": 300, "output_tokens": 80, "total_tokens": 380, "reported_cost_usd": 0.003, "has_usage": True}]
        ledger = aggregate_usage(entries).to_dict()
        T.record_agent_usage(sf, ids[0], "run-1", ledger, "balanced")
        T.record_agent_usage(sf, ids[0], "run-1", ledger, "balanced")
        unknown = {"model_calls": 1, "input_tokens": None, "output_tokens": None, "total_tokens": None, "estimated_cost_usd": None, "usage_complete": False}
        T.record_agent_usage(sf, ids[1], "run-2", unknown, "fast")
        with sf() as s:
            facts = s.scalars(select(AIUsageFact).order_by(AIUsageFact.id)).all()
        check("agent_usage_captured_once_idempotently_without_double_count", len(facts) == 2 and facts[0].model_calls == ledger["model_calls"] == 2 and facts[0].total_tokens == ledger["total_tokens"], "ledger total once")
        check("unknown_usage_stays_null_never_zero", facts[1].total_tokens is None and facts[1].cost_usd_micros is None and facts[1].cost_source == "unavailable", "NULL")
        check("cost_is_integer_micro_usd", isinstance(facts[0].cost_usd_micros, int) and facts[0].cost_usd_micros == 4000, "4000 micro-USD")
        with sf() as s:
            before = {t: s.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("users", "opportunities", "subscriptions", "billing_customers", "jobs", "ai_usage_facts", "feature_flag_overrides")}
        for name in ("product", "quality", "operations", "ai_economics", "commercial"):
            getattr(svc, name)("90d")
        with sf() as s:
            after = {t: s.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in before}
        check("reports_leave_every_domain_unchanged", before == after, "row counts equal")
        eng.dispose()

    # --- telemetry ----------------------------------------------------------------------------------------------------------------
    check("telemetry_labels_are_code_defined_templates", T.route_label("POST", "/api/v1/agent/runs/{run_id}/messages") == ("agent", "agent_continue") and T.route_label("POST", "/api/v1/admin/x") is None,
          "no raw path or admin traffic")
    check("telemetry_schema_has_no_identity_body_or_path", {c.name for c in __import__("src.persistence", fromlist=["x"]).OperationalMetricEvent.__table__.columns}
          == {"id", "event_type", "subsystem", "operation", "outcome", "duration_ms", "error_category", "provider", "occurred_at"}, "bounded columns only")
    check("usage_has_one_capture_boundary_per_workflow", "_record_usage(result" in read("src/application/agent_service.py") and "_record_usage_facts" in read("src/interview/session_repository.py")
          and "usage_key" in telemetry_src, "agent aggregate once; practice record once")
    mig = read("migrations/versions/0024_reporting_analytics.py")
    check("migration_chain_valid_and_nothing_seeded", 'down_revision = "0023_platform_config"' in mig and "uq_aiuf_usage_key" in mig and "ck_aiuf_unavailable_is_null" in mig and "bulk_insert" not in mig and "INSERT" not in mig.upper().replace("INSERT_", ""), "0024 chains from 0023")
    check("usage_facts_cascade_with_the_account", 'ondelete="CASCADE"' in mig and "AIUsageFact" in read("src/application/account_deletion_service.py") and "ai_usage" in read("src/application/data_export.py"), "delete + owner export")
    check("tests_exist", all(x in read("tests/test_reporting_w10_12.py") for x in ("test_agent_usage_is_captured_once_per_run_and_equals_the_canonical_ledger", "test_secondary_suppression_prevents_reconstruction_by_subtraction",
                                                                         "test_reading_every_report_changes_nothing_and_enqueues_no_job_or_provider_call", "test_mock_mrr_arr_monthly_yearly_currency_separation_and_exclusions",
                                                                         "test_commercial_requires_its_own_permission_and_regular_reports_never_contain_commercial_fields")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.12 REPORTING GUARD (aggregates only; MOCK BILLING is not revenue)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:68s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
