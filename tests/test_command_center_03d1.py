"""Package 03D1: the Command Center metrics and AI operations read model. Offline and deterministic: temp DB, no provider, no network.

Load-bearing properties: every figure is a 03K MetricResult defined in a validated registry; aggregates only (no identifier, content, e-mail, address, path or
credential in any response); small cohorts are suppressed (value null, never the count); missing data is a state, never zero; unknown token/cost is excluded and
labelled partial; nothing is double counted; every route is GET-only, permissioned with an EXISTING permission, and refused (403) for every non-authorised persona;
the numbers equal the underlying facts on seeded fixtures."""

from __future__ import annotations

import json
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text

from src.api.admin_route_invariant import admin_routes, ungated
from src.api.schemas import command_center as SCH
from src.application import admin_permissions as perm
from src.persistence import (
    AIOperationEvent, AIUsageFact, AdminNotification, AuditEvent, Job, JobWorker, KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion,
    OperationalMetricEvent, User,
)
from src.reporting import command_center as CC
from src.reporting import contract as K
from src.reporting.definitions import PERIODS, REPORTING_MIN_COHORT
from tests import _admin_matrix as M
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

API = "/api/v1/admin/command-center"
PW = "correcthorsebattery"
ROOT = Path(__file__).resolve().parents[1]
DENIED = "Administrator access required."
ROUTES = ("health", "ai-operations", "jobs", "knowledge", "alerts", "security-signals", "candidate-activity")
SECTION_OF_ROUTE = {"health": "health", "ai-operations": "ai_operations", "jobs": "jobs", "knowledge": "knowledge", "alerts": "alerts", "security-signals": "security",
                    "candidate-activity": "candidate_activity"}
# Hand-written expectation (so a preset drift is caught, not mirrored): who may read each route.
ALLOWED = {
    "definitions": {"platform_admin", "support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin"},
    "health": {"platform_admin", "support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin"},
    "ai-operations": {"platform_admin", "knowledge_admin", "operations_admin"},
    "jobs": {"platform_admin", "knowledge_admin", "operations_admin"},
    "knowledge": {"platform_admin", "knowledge_admin"},
    "alerts": {"platform_admin", "security_privacy_admin"},
    "security-signals": {"platform_admin", "security_privacy_admin"},
    "candidate-activity": {"platform_admin", "operations_admin"},
}
NOW = datetime.now(timezone.utc).replace(microsecond=0)
DAY = timedelta(days=1)


class World:
    """A real isolated app with the seven personas. ``seed()`` adds the fixtures once."""

    def __init__(self):
        from fastapi.testclient import TestClient

        self.app, self.repo, _ = build_auth_app()
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = account_repo(self.repo)
        self.sf = self.repo.session_factory
        self.n = 0
        self.cookies: dict[str, dict] = {}
        self.uids: dict[str, int] = {}
        for persona in M.PERSONAS:
            self.cookies[persona], self.uids[persona] = self.make(persona)

    def make(self, role="user"):
        self.n += 1
        email = f"cc{self.n}@x.com"
        register(self.c, email, PW)
        ck = cookies_for(login_token(self.c, email, PW))
        uid = self.c.get("/api/v1/auth/me", cookies=ck).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return ck, uid

    def candidates(self, n: int, *, tag: str = "k") -> list[int]:
        out = []
        with self.sf() as s:
            for i in range(n):
                self.n += 1
                u = User(subject=f"{tag}{self.n}-{uuid.uuid4().hex[:6]}", provider="test", email=f"sentinel-{tag}{self.n}@example.test", platform_role="user", status="active",
                         created_at=NOW - 3 * DAY, updated_at=NOW - 3 * DAY, onboarding_completed_at=NOW - 3 * DAY)
                s.add(u)
                s.flush()
                out.append(u.id)
            s.commit()
        return out

    def get(self, route: str, persona: str = "platform_admin", period: str | None = None):
        q = f"?period={period}" if period else ""
        return self.c.get(f"{API}/{route}{q}", cookies=self.cookies[persona])

    def metrics(self, route: str, period: str = "30d") -> dict[str, dict]:
        r = self.get(route, period=period)
        assert r.status_code == 200, r.text
        return {m["metric_id"]: m for m in r.json()["metrics"]}

    def close(self):
        self.c.__exit__(None, None, None)


def seed_all(w: World) -> dict:
    """Fixtures with known answers. Returns the expectations that are NOT re-derivable from the rows themselves."""
    users = w.candidates(6)
    fid = iter(range(10_000))
    with w.sf() as s:
        # --- AI usage facts: 12 canonical units over 6 candidates. Tokens and cost known for 7 (all agent units and one practice unit); unknown for 5.
        for i, u in enumerate(users):
            for wf, prof, model in (("agent", "balanced", "model/terra"), ("practice", "fast", "model/luna")):
                unknown_tok = (wf == "practice" and i < 5)
                unknown_cost = (wf == "practice" and i < 5)
                s.add(AIUsageFact(usage_key=f"k{next(fid)}", user_id=u, workflow=wf, operation="evaluate" if wf == "practice" else "run", model_profile=prof, model_id=model,
                                  model_calls=2, input_tokens=None if unknown_tok else 100, output_tokens=None if unknown_tok else 40, total_tokens=None if unknown_tok else 140,
                                  cost_usd_micros=None if unknown_cost else 1234, cost_source="unavailable" if unknown_cost else "reported",
                                  token_coverage="unknown" if unknown_tok else "complete", cost_coverage="unknown" if unknown_cost else "complete",
                                  occurred_at=NOW - DAY, updated_at=NOW - DAY))
        # --- logical AI operations: 10 over 6 candidates, 5 failed, one limit observation, mixed attempt evidence
        for i in range(10):
            failed = i in (1, 3, 4, 6, 8)
            s.add(AIOperationEvent(op_key=f"op{i}-{uuid.uuid4().hex[:6]}", user_id=users[i % 6], workflow="practice" if i % 2 else "career", operation="evaluate" if i % 2 else "chat",
                                   status="failed" if failed else "succeeded", failure_category="http_502" if failed else None, provider_attempts=3 if i < 6 else 1,
                                   attempt_coverage="exact" if i < 6 else "none", calls_ok=0 if failed else 1, calls_failed=1 if failed else 0,
                                   latency_ms=100 * (i + 1) if i != 9 else None, limit_observed=(i == 2), started_at=NOW - DAY))
        # --- platform telemetry (no identity)
        for i in range(10):
            s.add(OperationalMetricEvent(event_type="request", subsystem="api", operation="GET /x", outcome="server_error" if i < 2 else "success", duration_ms=50 * (i + 1),
                                         occurred_at=NOW - DAY))
        for i in range(8):
            s.add(OperationalMetricEvent(event_type="provider_call", subsystem="llm", operation="chat", outcome="success" if i < 6 else "server_error", duration_ms=200 + i,
                                         provider="openrouter", occurred_at=NOW - DAY))
        # --- jobs: 3 queued, 1 stale running, 4 finished in the period (3 succeeded, 1 failed), 1 failed long ago
        for i in range(3):
            s.add(Job(public_id=uuid.uuid4().hex, job_type="knowledge_parse", state="queued", available_at=NOW - timedelta(hours=1 + i), created_at=NOW - DAY))
        s.add(Job(public_id=uuid.uuid4().hex, job_type="knowledge_index", state="running", lease_owner="w1", lease_expires_at=NOW - timedelta(hours=1), attempts=1,
                  started_at=NOW - 2 * timedelta(hours=1), available_at=NOW - DAY, created_at=NOW - DAY))
        for i in range(4):
            bad = i == 3
            s.add(Job(public_id=uuid.uuid4().hex, job_type="privacy_delete" if bad else "knowledge_parse", state="failed" if bad else "succeeded", attempts=1, started_at=NOW - DAY,
                      finished_at=NOW - DAY + timedelta(seconds=10 * (i + 1)), available_at=NOW - DAY, created_at=NOW - DAY))
        s.add(Job(public_id=uuid.uuid4().hex, job_type="knowledge_parse", state="failed", attempts=1, started_at=NOW - 200 * DAY, finished_at=NOW - 200 * DAY + timedelta(seconds=5),
                  available_at=NOW - 200 * DAY, created_at=NOW - 200 * DAY))
        s.add(JobWorker(worker_id="w-seed", status="running", last_seen_at=datetime.now(timezone.utc)))
        # --- alerts
        for cat, sev, st in (("knowledge_collection_lost", "high", "active"), ("knowledge_embedding_mismatch", "medium", "acknowledged"), ("auth_failure_burst", "high", "active"),
                             ("job_failed", "medium", "resolved")):
            src = "knowledge" if cat.startswith("knowledge") else ("account" if cat.startswith("auth") else "job")
            s.add(AdminNotification(public_id=uuid.uuid4().hex, category=cat, severity=sev, dedupe_key=f"d-{cat}", state=st, source_type=src, title=cat,
                                    first_seen_at=NOW - DAY, last_seen_at=NOW - DAY, resolved_at=NOW - DAY if st == "resolved" else None))
        # --- audit rows (security projection)
        actor = users[0]
        for etype, result, n in (("account.login", "failure", 3), ("account.login", "success", 4), ("admin.access.denied", "denied", 2), ("admin.step_up.failed", "failure", 1),
                                 ("admin.role_change.requested", "success", 1), ("account.reset_request", "success", 1), ("workspace.created", "success", 5)):
            for _ in range(n):
                s.add(AuditEvent(actor_user_id=actor, event_type=etype, result=result, created_at=NOW - DAY))
        # --- governed knowledge: review_required, failed, active (+ index record), queued
        for i, st in enumerate(("review_required", "failed", "active", "queued")):
            src = KnowledgeSource(public_id=uuid.uuid4().hex, title=f"src{i}")
            s.add(src)
            s.flush()
            v = KnowledgeSourceVersion(public_id=uuid.uuid4().hex, source_id=src.id, version=1, state=st, language="en", authority_level=1, original_filename=f"f{i}.txt",
                                       media_type="text/plain", byte_size=10, checksum_sha256=f"{i}" * 64, approved_by_user_id=users[0] if st == "active" else None,
                                       approved_at=NOW if st == "active" else None)
            s.add(v)
            s.flush()
            if st == "active":
                s.add(KnowledgeIndexRecord(version_id=v.id, collection="governed_knowledge", embedder="local", chunk_count=3, state="built"))
        s.commit()
    return {"users": users}


@pytest.fixture(scope="module")
def world():
    w = World()
    w.seeded = seed_all(w)
    yield w
    w.close()


@pytest.fixture(scope="module")
def empty():
    w = World()
    yield w
    w.close()


def svc(w: World) -> CC.CommandCenterService:
    return CC.CommandCenterService(w.sf)


def count(w: World, stmt) -> int:
    with w.sf() as s:
        return int(s.scalar(stmt) or 0)


def banned_key_hits(node, path="$") -> list[str]:
    """Keys are matched by ``_``-separated word, so 'description' is not an 'ip' hit but 'client_ip' or 'access_token' would be."""
    banned = {"content", "email", "ip", "token", "path", "secret", "password", "prompt", "user", "address", "cookie", "comment", "answer", "transcript"}   # "subject" is the 03K Quantity slug; user subjects are value-swept
    hits: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if set(k.lower().split("_")) & banned or k.lower() in ("user_id", "owner_user_id", "actor_user_id", "session_id", "run_id"):
                hits.append(f"{path}.{k}")
            hits += banned_key_hits(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits += banned_key_hits(v, f"{path}[{i}]")
    return hits


# ================================================================================================================ registry and contract
def test_registry_is_valid_and_conforms_to_the_03k_contract():
    K.validate_registry(CC.METRICS, CC.DIMENSIONS)
    ids = [m.metric_id for m in CC.METRICS]
    assert len(ids) == len(set(ids)) and len(ids) >= 59
    for m in CC.METRICS:
        # the definition is frozen contract data: it round-trips through the strict model with no SQL-like text and no column name
        assert K.MetricDefinition.model_validate(m.model_dump()) == m
        assert m.permission_required in perm.PERMISSION_SET
        assert "." not in m.source.name and "." not in m.numerator.subject
        assert m.missing_behaviour in ("unavailable", "not_captured")
        if m.suppression.kind == "cohort":
            assert m.suppression.min_cohort >= REPORTING_MIN_COHORT
        if m.unit in ("percent", "ratio"):
            assert m.denominator is not None
        for d in m.dimensions_allowed:
            assert d in {x.dimension_id for x in CC.DIMENSIONS}
        if m.source.kind == "fact_table":
            assert m.source.name in K.SOURCE_CATALOG
    assert len(perm.PERMISSIONS) == 44                       # no permission was added
    assert {m.permission_required for m in CC.METRICS} <= {perm.OVERVIEW_READ, perm.AI_READ, perm.JOBS_READ, perm.KNOWLEDGE_READ, perm.SECURITY_READ, perm.REPORTS_READ}


def test_missing_and_suppression_semantics_hold_for_every_registered_metric():
    for m in CC.METRICS:
        miss = K.build_result(m, "30d", None, cohort=100)
        assert miss.state == m.missing_behaviour and miss.value is None and miss.numerator is None
        if m.suppression.kind == "cohort":
            sup = K.build_result(m, "30d", 3, cohort=REPORTING_MIN_COHORT - 1, numerator=3, denominator=4)
            assert sup.state == "suppressed" and sup.value is None and sup.numerator is None and sup.denominator is None
        else:
            assert K.build_result(m, "30d", 0).state == "ok"           # a real operational zero is allowed ONLY as ok
        with pytest.raises(ValidationError):
            K.MetricResult(metric_id=m.metric_id, period="30d", state=m.missing_behaviour, value=0)


def test_the_frozen_03k_contract_files_are_untouched():
    import subprocess

    # 05E (PRIV-DIFF, lead to review): src/reporting/service.py and suppression.py are no longer pinned against origin/main. The owner-approved 05E package adds the nested-window
    # and total-versus-bucket differencing mitigation THERE (decorators, bucket scopes and the hidden-group rule; the 03K contract, the metric definitions and the cohort floor
    # are unchanged and still pinned). Their behaviour is covered by tests/test_differencing_05e.py and the W10.12 / 03E1 suites, which pass unchanged.
    out = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", "src/reporting/contract.py", "frontend/lib/admin/metricContract.ts",
                          "frontend/lib/admin/metricContract.schema.json", "src/reporting/definitions.py"],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode == 0:                                    # a detached or shallow checkout cannot compare; the evidence file records the diff
        assert out.stdout.strip() == ""


def test_every_route_returns_exactly_the_registered_metrics_of_its_section(world):
    for route, section in SECTION_OF_ROUTE.items():
        got = [m["metric_id"] for m in world.get(route).json()["metrics"]]
        assert sorted(got) == sorted(m.metric_id for m in CC.metrics_for_section(section)), route
        for item in world.get(route).json()["metrics"]:
            defn = CC._DEF[item["metric_id"]]
            result = K.MetricResult(**{k: item[k] for k in ("metric_id", "period", "state", "value", "numerator", "denominator", "coverage", "partial", "note")})
            K.check_result(result, defn)                       # period supported, missing state matches the definition, operational never suppressed
            assert item["unit"] == defn.unit and item["suppression"] == defn.suppression.kind
            assert item["evidence_source"] == f"{defn.source.kind}:{defn.source.name}"
            assert set(item["dimensions"]) == set(defn.dimensions_allowed)
            assert item["evidence"] in ("captured", "partial", "current_state", "not_captured", "unavailable", "suppressed")
            for b in item["breakdowns"]:
                assert b["dimension_id"] in defn.dimensions_allowed


def test_non_ok_metrics_carry_no_value_numerator_denominator_cost_or_breakdown(empty, world):
    for w in (empty, world):
        for route in ROUTES:
            for m in w.get(route).json()["metrics"]:
                if m["state"] != "ok":
                    assert m["value"] is None and m["numerator"] is None and m["denominator"] is None and m["cost_micro_usd"] is None and m["breakdowns"] == [], m["metric_id"]
                    assert m["evidence"] == m["state"] or m["evidence"] == "suppressed"


# ================================================================================================================ missing data is never zero
def test_empty_database_reports_missing_states_not_zero(empty):
    ai = empty.metrics("ai-operations")
    for mid in ("ai_op_usage_units", "ai_op_known_tokens", "ai_op_known_cost", "ai_op_operations", "ai_op_failure_rate", "ai_op_latency_p95_ms", "ai_op_provider_calls",
                "ai_op_provider_failure_rate", "ai_op_model_fallbacks"):
        assert ai[mid]["state"] == "not_captured" and ai[mid]["value"] is None and ai[mid]["evidence"] == "not_captured", mid
    h = empty.metrics("health")
    assert h["platform_request_failure_rate"]["state"] == "not_captured" and h["platform_request_latency_p95_ms"]["value"] is None
    j = empty.metrics("jobs")
    assert j["jobs_failure_rate"]["state"] == "unavailable" and j["jobs_duration_p95_s"]["state"] == "unavailable" and j["jobs_oldest_ready_age_s"]["state"] == "unavailable"
    assert j["jobs_queued"]["state"] == "ok" and j["jobs_queued"]["value"] == 0 and j["jobs_queued"]["evidence"] == "current_state"      # an empty queue is a real zero
    k = empty.metrics("knowledge")
    assert k["knowledge_active_versions"]["value"] == 0
    assert any(c["component_id"] == "governed_set" and c["status"] == "attention" for c in empty.get("knowledge").json()["components"])
    ca = empty.metrics("candidate-activity")
    assert all(m["state"] in ("ok", "suppressed") and (m["state"] == "suppressed") == (m["value"] is None) for m in ca.values())


def test_a_fallback_metric_is_never_reported_as_zero(world):
    m = world.metrics("ai-operations")["ai_op_model_fallbacks"]
    assert m["state"] == "not_captured" and m["value"] is None and "not zero" in m["note"]


# ================================================================================================================ numbers equal facts
def test_ai_usage_figures_equal_the_underlying_usage_facts(world):
    m = world.metrics("ai-operations")
    F = AIUsageFact
    n = count(world, select(func.count()).select_from(F))
    assert n == 12 and m["ai_op_usage_units"]["value"] == n
    assert m["ai_op_model_calls"]["value"] == count(world, select(func.sum(F.model_calls)))
    known_tok = count(world, select(func.sum(F.total_tokens)))
    n_tok = count(world, select(func.count()).select_from(F).where(F.total_tokens.is_not(None)))
    assert m["ai_op_known_tokens"]["value"] == known_tok == 140 * 7 and m["ai_op_known_tokens"]["partial"] is True and m["ai_op_known_tokens"]["evidence"] == "partial"
    assert "58.3%" in m["ai_op_known_tokens"]["coverage"]
    micros = count(world, select(func.sum(F.cost_usd_micros)))
    c = m["ai_op_known_cost"]
    assert c["cost_micro_usd"] == micros == 1234 * 7 and c["value"] == round(micros / 1_000_000, 6) and c["unit"] == "usd" and c["partial"] is True
    assert isinstance(c["cost_micro_usd"], int)
    n_cost = count(world, select(func.count()).select_from(F).where(F.cost_usd_micros.is_not(None)))
    assert (n_tok, n_cost) == (7, 7)
    assert m["ai_op_token_coverage"]["value"] == round(100.0 * n_tok / n, 1) and m["ai_op_token_coverage"]["numerator"] == n_tok and m["ai_op_token_coverage"]["denominator"] == n
    assert m["ai_op_cost_coverage"]["value"] == round(100.0 * n_cost / n, 1)


def test_ai_breakdowns_partition_the_total_exactly_and_label_partial_buckets(world):
    m = world.metrics("ai-operations")
    units = m["ai_op_usage_units"]
    assert {b["dimension_id"] for b in units["breakdowns"]} == {"workflow", "model_profile", "operation", "model"}
    for b in units["breakdowns"]:
        assert all(x["state"] == "ok" for x in b["buckets"])
        assert sum(x["value"] for x in b["buckets"]) == units["value"], b["dimension_id"]
    wf = {x["key"]: x for b in m["ai_op_known_tokens"]["breakdowns"] if b["dimension_id"] == "workflow" for x in b["buckets"]}
    assert wf["agent"]["value"] == 140 * 6 and wf["agent"]["partial"] is False          # every agent unit has tokens
    assert wf["practice"]["value"] == 140 and wf["practice"]["partial"] is True          # five practice units do not: excluded, not zero
    cost_wf = {x["key"]: x for b in m["ai_op_known_cost"]["breakdowns"] if b["dimension_id"] == "workflow" for x in b["buckets"]}
    assert cost_wf["practice"]["value"] == round(1234 / 1_000_000, 6) and cost_wf["agent"]["value"] == round(1234 * 6 / 1_000_000, 6)


def test_a_bucket_with_no_known_value_is_unavailable_never_zero(empty):
    users = empty.candidates(6, tag="u")
    with empty.sf() as s:
        for i, u in enumerate(users):
            for model, tok in (("m/known", 10), ("m/blind", None)):
                s.add(AIUsageFact(usage_key=f"x{i}{model}", user_id=u, workflow="agent", operation="run", model_profile="balanced", model_id=model, model_calls=1,
                                  input_tokens=None if tok is None else 6, output_tokens=None if tok is None else 4, total_tokens=tok,
                                  token_coverage="unknown" if tok is None else "complete", occurred_at=NOW - DAY, updated_at=NOW - DAY))
        s.commit()
    tok = empty.metrics("ai-operations")["ai_op_known_tokens"]
    by_model = {x["key"]: x for b in tok["breakdowns"] if b["dimension_id"] == "model" for x in b["buckets"]}
    assert by_model["m/blind"]["state"] == "unavailable" and by_model["m/blind"]["value"] is None
    assert by_model["m/known"]["value"] == 60
    assert tok["value"] == 60 and tok["partial"] is True
    assert empty.metrics("ai-operations")["ai_op_known_cost"]["state"] == "not_captured"          # no cost anywhere: missing, not 0
    with empty.sf() as s:                                                                            # leave the shared fixture clean
        s.execute(AIUsageFact.__table__.delete())
        s.commit()


def test_operation_outcomes_retries_and_latency_equal_the_operation_events(world):
    m = world.metrics("ai-operations")
    E = AIOperationEvent
    n = count(world, select(func.count()).select_from(E))
    failed = count(world, select(func.count()).select_from(E).where(E.status == "failed"))
    assert (n, failed) == (10, 5)
    assert m["ai_op_operations"]["value"] == n
    assert m["ai_op_failed_operations"]["value"] == failed
    fr = m["ai_op_failure_rate"]
    assert fr["value"] == 50.0 and fr["numerator"] == 5 and fr["denominator"] == 10 and fr["unit"] == "percent"
    cats = {x["key"]: x["value"] for b in m["ai_op_failed_operations"]["breakdowns"] if b["dimension_id"] == "failure_category" for x in b["buckets"]}
    assert cats == {"http_502": 5}
    # retries: exact-coverage operations only (6 of 10): each had 3 attempts for 1 completed call
    assert m["ai_op_retry_attempts"]["value"] == 6 * 2 and m["ai_op_retry_attempts"]["partial"] is True
    # latency: nine operations have one; nearest-rank percentiles over 100..900
    assert m["ai_op_latency_p50_ms"]["value"] == 500 and m["ai_op_latency_p95_ms"]["value"] == 900 and m["ai_op_latency_p95_ms"]["partial"] is True
    assert m["ai_op_limit_observed"]["value"] == 1


def test_provider_call_telemetry_equals_operational_events(world):
    m = world.metrics("ai-operations")
    O = OperationalMetricEvent
    n = count(world, select(func.count()).select_from(O).where(O.event_type == "provider_call"))
    assert n == 8 and m["ai_op_provider_calls"]["value"] == n and m["ai_op_provider_calls"]["suppression"] == "operational"
    assert m["ai_op_provider_failure_rate"]["value"] == 25.0 and m["ai_op_provider_failure_rate"]["numerator"] == 2
    assert m["ai_op_provider_latency_p95_ms"]["value"] == 207
    outcomes = {x["key"]: x["value"] for b in m["ai_op_provider_calls"]["breakdowns"] if b["dimension_id"] == "outcome" for x in b["buckets"]}
    assert outcomes == {"success": 6, "server_error": 2}


def test_nothing_is_double_counted_between_usage_facts_and_operation_events(world):
    """Tokens and cost come ONLY from ai_usage_facts; operation counts, retries and latency ONLY from ai_operation_events; request telemetry from neither."""
    before = world.metrics("ai-operations")
    with world.sf() as s:
        s.add(AIOperationEvent(op_key=f"dbl-{uuid.uuid4().hex}", user_id=world.seeded["users"][0], workflow="practice", operation="evaluate", status="succeeded", calls_ok=1,
                               input_tokens=999_000, output_tokens=1, total_tokens=999_001, token_coverage="known", cost_usd_micros=777_000_000, cost_source="reported",
                               started_at=NOW - DAY))
        s.commit()
    after = world.metrics("ai-operations")
    try:
        assert after["ai_op_operations"]["value"] == before["ai_op_operations"]["value"] + 1                    # the operation is counted once ...
        for mid in ("ai_op_usage_units", "ai_op_model_calls", "ai_op_known_tokens", "ai_op_known_cost", "ai_op_token_coverage", "ai_op_cost_coverage"):
            assert after[mid]["value"] == before[mid]["value"], mid                                              # ... and its tokens/cost never enter the usage totals
        assert after["ai_op_known_cost"]["cost_micro_usd"] == before["ai_op_known_cost"]["cost_micro_usd"]
        assert after["ai_op_provider_calls"]["value"] == before["ai_op_provider_calls"]["value"]
    finally:
        with world.sf() as s:
            s.execute(text("DELETE FROM ai_operation_events WHERE op_key LIKE 'dbl-%'"))
            s.commit()


def test_health_figures_equal_the_request_events_and_report_components(world):
    r = world.get("health").json()
    m = {x["metric_id"]: x for x in r["metrics"]}
    assert m["platform_request_failure_rate"]["value"] == 20.0 and m["platform_request_failure_rate"]["numerator"] == 2 and m["platform_request_failure_rate"]["denominator"] == 10
    assert m["platform_request_latency_p95_ms"]["value"] == 500
    assert m["platform_workers_active"]["value"] == 1 and m["platform_paused_capabilities"]["value"] == 0
    comps = {c["component_id"]: c for c in r["components"]}
    assert comps["database"]["status"] == "ok" and set(comps) >= {"database", "migrations", "pause", "rate_limit", "providers"}
    assert comps["providers"]["status"] == "info" and "not probed" in comps["providers"]["note"]
    assert all(c["evidence"] in ("current_state", "unavailable") for c in r["components"])


def test_ai_component_state_reports_observe_mode_pause_and_quota_truthfully(world):
    comps = {c["component_id"]: c for c in world.get("ai-operations").json()["components"]}
    assert "Observe mode" in comps["ai_request_ceilings"]["note"] and "Not enforced" in comps["usage_quotas"]["note"]
    assert comps["model_configuration"]["status"] in ("ok", "attention") and "code defaults" in comps["model_configuration"]["note"] or "governed configuration is active" in comps["model_configuration"]["note"]
    pauses = [c for k, c in comps.items() if k.startswith("pause_")]
    assert pauses and all(c["status"] == "ok" for c in pauses)


def test_job_figures_equal_the_job_rows(world):
    m = world.metrics("jobs")
    J = Job
    for mid, state in (("jobs_queued", "queued"), ("jobs_running", "running"), ("jobs_failed_current", "failed")):
        assert m[mid]["value"] == count(world, select(func.count()).select_from(J).where(J.state == state)), mid
    assert (m["jobs_queued"]["value"], m["jobs_running"]["value"], m["jobs_failed_current"]["value"]) == (3, 1, 2)
    assert m["jobs_stale_leases"]["value"] == 1 and m["jobs_workers_active"]["value"] == 1
    assert m["jobs_oldest_ready_age_s"]["value"] >= 3 * 3600 - 60 and m["jobs_oldest_ready_age_s"]["unit"] == "seconds"
    by_type = {x["key"]: x["value"] for b in m["jobs_queued"]["breakdowns"] for x in b["buckets"]}
    assert by_type == {"knowledge_parse": 3}
    # windowed: 30 days sees the four recent finishes, not the one from 200 days ago; all_time sees five
    assert m["jobs_finished"]["value"] == 4 and m["jobs_failure_rate"]["value"] == 25.0 and m["jobs_failure_rate"]["denominator"] == 4
    assert m["jobs_duration_p95_s"]["value"] == 40.0
    assert world.metrics("jobs", "all_time")["jobs_finished"]["value"] == 5
    assert world.metrics("jobs", "7d")["jobs_finished"]["value"] == 4


def test_job_metrics_carry_no_payload_or_error_text(world):
    blob = world.get("jobs").text
    for needle in ("payload", "last_error", "message", "lease_owner", "w1", "w-seed"):
        assert needle not in blob, needle


def test_knowledge_figures_equal_the_registry(world):
    m = world.metrics("knowledge")
    V = KnowledgeSourceVersion
    for mid, st in (("knowledge_active_versions", "active"), ("knowledge_awaiting_review", "review_required"), ("knowledge_failed_versions", "failed")):
        assert m[mid]["value"] == count(world, select(func.count()).select_from(V).where(V.state == st)) == 1, mid
    assert m["knowledge_versions"]["value"] == count(world, select(func.count()).select_from(V)) == 4
    states = {x["key"]: x["value"] for b in m["knowledge_versions"]["breakdowns"] for x in b["buckets"]}
    assert states == {"review_required": 1, "failed": 1, "active": 1, "queued": 1}
    assert m["knowledge_index_records"]["value"] == 1
    assert m["knowledge_retrieval_outcomes"]["state"] == "not_captured"               # nothing captured: missing, not zero
    assert m["knowledge_open_alerts"]["value"] == 2                                  # the resolved and the non-knowledge alerts are excluded
    r = world.get("knowledge").json()
    comps = {c["component_id"]: c for c in r["components"]}
    assert comps["governed_set"]["status"] == "ok" and comps["knowledge_alerts"]["status"] == "attention"
    assert "src0" not in json.dumps(r) and "f0.txt" not in json.dumps(r)             # no title, file name or text


def test_alert_figures_equal_the_alert_rows_without_alert_text(world):
    m = world.metrics("alerts")
    A = AdminNotification
    assert m["alerts_unresolved"]["value"] == count(world, select(func.count()).select_from(A).where(A.state != "resolved")) == 3
    assert m["alerts_active_high"]["value"] == 2 and m["alerts_opened"]["value"] == 4 and m["alerts_resolved"]["value"] == 1
    cats = {x["key"]: x["value"] for b in m["alerts_unresolved"]["breakdowns"] if b["dimension_id"] == "alert_category" for x in b["buckets"]}
    assert cats == {"knowledge_collection_lost": 1, "knowledge_embedding_mismatch": 1, "auth_failure_burst": 1}
    sev = {x["key"]: x["value"] for b in m["alerts_unresolved"]["breakdowns"] if b["dimension_id"] == "severity" for x in b["buckets"]}
    assert sev == {"high": 2, "medium": 1}
    assert "dedupe" not in world.get("alerts").text and "source_id" not in world.get("alerts").text


def test_security_signal_counts_equal_the_audit_rows_and_exclude_successful_sign_ins(world):
    m = world.metrics("security-signals")
    A = AuditEvent
    assert m["security_failed_logins"]["value"] == count(world, select(func.count()).select_from(A).where(A.event_type == "account.login", A.result != "success")) == 3
    denied_rows = count(world, select(func.count()).select_from(A).where(A.event_type == "admin.access.denied"))
    assert m["security_access_denied"]["value"] == denied_rows >= 2
    assert m["security_step_up_failures"]["value"] == 1 and m["security_role_change_events"]["value"] == 1
    # 3 failed sign-ins + denied + 1 step-up failure + 1 role change + 1 reset request; successful sign-ins and unrelated audit rows are not security events
    assert m["security_events"]["value"] == 3 + denied_rows + 1 + 1 + 1
    cats = {x["key"]: x["value"] for b in m["security_events"]["breakdowns"] if b["dimension_id"] == "security_category" for x in b["buckets"]}
    assert sum(cats.values()) == m["security_events"]["value"] and cats["authentication"] == 3 and cats["role_change"] == 1 and cats["password_reset"] == 1


def test_candidate_activity_equals_the_existing_product_report(world):
    ca = world.metrics("candidate-activity")
    rep = world.c.get("/api/v1/admin/reports/product?period=30d", cookies=world.cookies["platform_admin"]).json()
    legacy = {x["metric_id"]: x for x in rep["sections"][0]["metrics"]}
    for cid, lid in CC._ACTIVITY.items():
        lm = legacy[lid]
        if lm["state"] in ("available", "partial"):
            assert ca[cid]["state"] == "ok" and ca[cid]["value"] == lm["figure"] and ca[cid]["partial"] == (lm["state"] == "partial"), cid
        else:
            assert ca[cid]["state"] == "suppressed" and ca[cid]["value"] is None, cid
    assert ca["registrations"]["state"] == "ok" and ca["registrations"]["value"] == count(world, select(func.count()).select_from(User).where(User.platform_role == "user")) == 7   # the candidate persona + 6 seeded


# ================================================================================================================ suppression
def test_small_cohorts_are_suppressed_without_leaking_the_count(empty):
    small = empty.candidates(REPORTING_MIN_COHORT - 1, tag="s")
    with empty.sf() as s:
        for i, u in enumerate(small):
            s.add(AIUsageFact(usage_key=f"sm{i}", user_id=u, workflow="agent", operation="run", model_profile="fast", model_id="m/x", model_calls=7, total_tokens=4242,
                              input_tokens=4000, output_tokens=242, cost_usd_micros=31337, cost_source="reported", token_coverage="complete", cost_coverage="complete",
                              occurred_at=NOW - DAY, updated_at=NOW - DAY))
            s.add(AIOperationEvent(op_key=f"smo{i}", user_id=u, workflow="career", operation="chat", status="failed", failure_category="x", provider_attempts=1,
                                   attempt_coverage="exact", calls_failed=1, latency_ms=777, started_at=NOW - DAY))
        s.commit()
    r = empty.get("ai-operations")
    m = {x["metric_id"]: x for x in r.json()["metrics"]}
    cohort_ids = [d.metric_id for d in CC.metrics_for_section("ai_operations") if d.suppression.kind == "cohort" and d.metric_id != "ai_op_model_fallbacks"]
    for mid in cohort_ids:
        assert m[mid]["state"] == "suppressed" and m[mid]["value"] is None and m[mid]["cost_micro_usd"] is None and m[mid]["breakdowns"] == [], mid
        assert m[mid]["evidence"] == "suppressed"
    for secret in ("4242", "31337", "777", str(len(small))):
        assert f'"value": {secret}' not in r.text.replace('":', '": ') and f'"value":{secret}' not in r.text
    with empty.sf() as s:                                                                            # the floor itself: one more candidate lifts the suppression
        extra = empty.candidates(1, tag="t")[0]
        s.add(AIUsageFact(usage_key="sm-extra", user_id=extra, workflow="agent", operation="run", model_profile="fast", model_id="m/x", model_calls=7, total_tokens=4242,
                          input_tokens=4000, output_tokens=242, cost_usd_micros=31337, cost_source="reported", token_coverage="complete", cost_coverage="complete",
                          occurred_at=NOW - DAY, updated_at=NOW - DAY))
        s.commit()
    m2 = empty.metrics("ai-operations")
    assert m2["ai_op_usage_units"]["state"] == "ok" and m2["ai_op_usage_units"]["value"] == REPORTING_MIN_COHORT
    with empty.sf() as s:
        s.execute(AIUsageFact.__table__.delete())
        s.execute(AIOperationEvent.__table__.delete())
        s.commit()


def test_breakdown_buckets_get_primary_and_secondary_suppression():
    groups = {"a": [1] * 9, "b": [1] * 6, "c": [1] * 2}                    # one small bucket; a total of 17 would reveal it by subtraction
    users = lambda g: len(g)   # noqa: E731
    out = CC.CommandCenterService._breakdown("workflow", groups, len, cohort_fn=users)
    states = {b.key: b.state for b in out.buckets}
    assert states["c"] == "suppressed" and states["b"] == "suppressed" and states["a"] == "ok"      # the smallest remaining bucket is hidden too
    assert all(b.value is None for b in out.buckets if b.state != "ok")
    all_ok = CC.CommandCenterService._breakdown("workflow", {"a": [1] * 9, "b": [1] * 6}, len, cohort_fn=users)
    assert {b.state for b in all_ok.buckets} == {"ok"}


def test_a_small_failure_numerator_is_suppressed_by_the_rate_rule(empty):
    users = empty.candidates(8, tag="r")
    with empty.sf() as s:
        for i in range(8):
            s.add(AIOperationEvent(op_key=f"rate{i}", user_id=users[i], workflow="career", operation="chat", status="failed" if i < 2 else "succeeded", calls_ok=1,
                                   started_at=NOW - DAY))
        s.commit()
    m = empty.metrics("ai-operations")
    assert m["ai_op_operations"]["value"] == 8 and m["ai_op_failed_operations"]["value"] == 2
    assert m["ai_op_failure_rate"]["state"] == "suppressed" and m["ai_op_failure_rate"]["value"] is None          # 2 of 8 would reveal exactly 2
    with empty.sf() as s:
        s.execute(AIOperationEvent.__table__.delete())
        s.commit()


def test_operational_metrics_are_never_cohort_suppressed(empty):
    with empty.sf() as s:
        s.add(Job(public_id=uuid.uuid4().hex, job_type="knowledge_parse", state="failed", attempts=1, started_at=NOW - DAY, finished_at=NOW - DAY + timedelta(seconds=3),
                  available_at=NOW - DAY, created_at=NOW - DAY))
        s.commit()
    m = empty.metrics("jobs")
    assert m["jobs_finished"]["state"] == "ok" and m["jobs_finished"]["value"] == 1 and m["jobs_failure_rate"]["value"] == 100.0
    with empty.sf() as s:
        s.execute(Job.__table__.delete())
        s.commit()


# ================================================================================================================ authorization
def _all_routes():
    return [r for r in admin_routes() if r.path.startswith("/admin/command-center")]


def test_the_new_routes_are_get_only_permissioned_and_known_to_the_invariants():
    rs = _all_routes()
    assert sorted(r.path for r in rs) == sorted(f"/admin/command-center/{p}" for p in ("definitions", *ROUTES))
    assert all(r.methods == ("GET",) and len(r.permissions) == 1 and r.permissions <= perm.PERMISSION_SET for r in rs)
    assert ungated() == []
    assert len(perm.PERMISSIONS) == 44 and len(set(perm.PERMISSIONS) - {"platform.billing.recover"}) == 43
    for r in rs:
        assert M.domain_of(r.path) == "command center metrics" and M.domain_of(r.path) != "UNMAPPED"
    assert not [r for r in admin_routes() if M.domain_of(r.path) == "UNMAPPED"]
    expected = {"definitions": perm.OVERVIEW_READ, "health": perm.OVERVIEW_READ, "ai-operations": perm.AI_READ, "jobs": perm.JOBS_READ, "knowledge": perm.KNOWLEDGE_READ,
                "alerts": perm.SECURITY_READ, "security-signals": perm.SECURITY_READ, "candidate-activity": perm.REPORTS_READ}
    assert {r.path.rsplit("/", 1)[1]: next(iter(r.permissions)) for r in rs} == expected


@pytest.mark.parametrize("route", ["definitions", *ROUTES])
def test_every_persona_is_allowed_or_403_exactly_as_the_presets_say(world, route):
    for persona in M.PERSONAS:
        resp = world.c.get(f"{API}/{route}", cookies=world.cookies[persona])
        if persona in ALLOWED[route]:
            assert resp.status_code == 200, (route, persona, resp.text[:200])
            # the hand-written table agrees with the code-derived one
            assert M.expected_allowed(frozenset({next(iter(r.permissions)) for r in _all_routes() if r.path.endswith("/" + route)}), persona)
        else:
            assert resp.status_code == 403 and resp.json()["error"]["message"] == DENIED, (route, persona)
            assert not M.expected_allowed(frozenset({next(iter(r.permissions)) for r in _all_routes() if r.path.endswith("/" + route)}), persona)
    from fastapi.testclient import TestClient

    with TestClient(world.app) as anon:                                                  # a client with no cookie jar: no session
        assert anon.get(f"{API}/{route}").status_code in (401, 403)
    assert "user" not in ALLOWED[route]                                                  # the candidate is denied everywhere


def test_a_denied_persona_receives_no_metric_field(world):
    for route in ROUTES:
        body = world.c.get(f"{API}/{route}", cookies=world.cookies["user"]).text
        assert "metric_id" not in body and "value" not in body


def test_deactivated_admin_has_no_authority(world):
    ck, uid = world.make("platform_admin")
    assert world.c.get(f"{API}/health", cookies=ck).status_code == 200
    with world.sf() as s:
        s.execute(text("UPDATE users SET status='deactivated' WHERE id=:i"), {"i": uid})
        s.commit()
    assert world.c.get(f"{API}/health", cookies=ck).status_code in (401, 403)


def test_only_get_is_allowed_and_unknown_routes_do_not_exist(world):
    for route in ("definitions", *ROUTES):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(world.c, method)(f"{API}/{route}", cookies=world.cookies["platform_admin"]).status_code == 405, (route, method)
    for path in ("events", "users", "facts", "raw", "export", "ai-usage", "candidates", "jobs/1", "sql"):
        assert world.get(path).status_code in (404, 405), path


def test_definitions_are_filtered_to_the_metrics_the_caller_may_read(world):
    full = world.get("definitions").json()
    assert {m["metric_id"] for m in full["metrics"]} == {m.metric_id for m in CC.METRICS}
    assert full["periods"] == list(PERIODS) and full["default_period"] == "30d"
    ke = world.get("definitions", "knowledge_admin").json()
    assert {m["permission_required"] for m in ke["metrics"]} == {perm.OVERVIEW_READ, perm.AI_READ, perm.KNOWLEDGE_READ, perm.JOBS_READ}
    su = world.get("definitions", "support_operator").json()
    assert {m["permission_required"] for m in su["metrics"]} == {perm.OVERVIEW_READ} and len(su["metrics"]) == 4
    used = {d for m in ke["metrics"] for d in m["dimensions_allowed"]}
    assert {d["dimension_id"] for d in ke["dimensions"]} == used
    # contract data only: no SQL text, no column names, no row data
    blob = json.dumps(full)
    assert "SELECT" not in blob.upper().replace("SELECTED", "") and "sentinel" not in blob


# ================================================================================================================ privacy
SENTINEL_VALUES = ("example.test", "sentinel-", "@", "SECRET", PW, "cookie")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def test_responses_carry_no_banned_fields_identifiers_or_sentinel_values(world):
    for route in ("definitions", *ROUTES):
        r = world.get(route)
        data = r.json()
        assert banned_key_hits(data) == [], (route, banned_key_hits(data))
        for needle in SENTINEL_VALUES:
            assert needle.lower() not in r.text.lower(), (route, needle)
        assert not IP_RE.search(r.text), route
        for seeded in world.seeded["users"]:
            assert f'"{seeded}"' not in r.text                                             # no user id appears as a value either


def test_banned_key_scanner_actually_detects_what_it_claims_to():
    assert banned_key_hits({"client_ip": 1, "access_token": 2, "user_email": 3, "file_path": 4, "api_secret": 5, "content": 6, "description": 7, "ok": 8}) == [
        "$.client_ip", "$.access_token", "$.user_email", "$.file_path", "$.api_secret", "$.content"]
    assert banned_key_hits([{"nested": {"user_id": 1}}]) == ["$[0].nested.user_id"]


def test_response_schemas_are_allowlists_with_no_open_fields():
    def walk(model, seen=None):
        seen = seen or set()
        if model in seen:
            return
        seen.add(model)
        if issubclass(model, SCH.BaseModel):
            if model.__module__ == SCH.__name__:
                assert model.model_config.get("extra") == "forbid", model.__name__
            for f in model.model_fields.values():
                assert "dict" not in str(f.annotation).lower() and "Any" not in str(f.annotation), (model.__name__, f.annotation)
    for name in ("BucketOut", "BreakdownOut", "MetricItemOut", "ComponentOut", "CommandCenterResponse", "CommandCenterDefinitions"):
        walk(getattr(SCH, name))
    with pytest.raises(ValidationError):
        SCH.ComponentOut(component_id="x", label="x", status="ok", evidence="current_state", user_id=1)
    with pytest.raises(ValidationError):
        SCH.MetricItemOut(metric_id="x", label="x", unit="count", period="30d", state="ok", value=1, evidence="captured", evidence_source="s", suppression="operational",
                          email="a@b.c")
    fields = {f for name in ("BucketOut", "BreakdownOut", "MetricItemOut", "ComponentOut", "CommandCenterResponse") for f in getattr(SCH, name).model_fields}
    assert not {"user_id", "email", "content", "path", "secret", "token", "ip", "prompt", "comment", "subject"} & fields


def test_the_read_model_reads_no_private_content_and_returns_no_row_level_data():
    code = (ROOT / "src/reporting/command_center.py").read_text().split('"""', 2)[2]          # code only, not the module docstring
    for banned in ("Answer.", "CandidateDocument", "PreparationMemory", "SupportMessage", "SupportInternalNote", "DocumentClaim", "state_payload", "UserFeedback", "payload_json",
                   "last_error_message_safe", "preview_text", "AuditEvent.context", "AuditEvent.actor_user_id", "AuditEvent.target_id", "AuditEvent.request_id",
                   "AdminNotification.source_id", "AdminNotification.title", "KnowledgeSource.title", "original_filename", "User.email", "User.subject"):
        assert banned not in code, banned
    assert not re.search(r"^\s*(import|from)\s+(requests|httpx|urllib|openai|langchain|subprocess)\b", code, re.M) and "enqueue" not in code and ".add(" not in code and "commit(" not in code
    route = (ROOT / "src/api/routes/admin_command_center.py").read_text()
    assert "@router.post" not in route and "@router.put" not in route and "@router.patch" not in route and "@router.delete" not in route


# ================================================================================================================ behaviour
def test_periods_are_a_fixed_set_and_unknown_periods_are_rejected(world):
    for route in ROUTES:
        for p in PERIODS:
            r = world.get(route, period=p)
            assert r.status_code == 200 and r.json()["period"] == p and r.json()["utc"] is True, (route, p)
        for bad in ("1d", "2026-01-01", "30d;DROP TABLE users", "ALL_TIME", "0", "x" * 40):
            assert world.get(route, period=bad).status_code == 422, (route, bad)
    assert world.get("health").json()["period"] == "30d"
    assert world.get("health", period="all_time").json()["window_start"] is None


def test_the_period_window_changes_the_figures_it_should(world):
    assert world.metrics("jobs", "all_time")["jobs_finished"]["value"] == 5 and world.metrics("jobs", "30d")["jobs_finished"]["value"] == 4
    older = NOW - 120 * DAY
    with world.sf() as s:
        s.add(OperationalMetricEvent(event_type="request", subsystem="api", operation="GET /old", outcome="server_error", duration_ms=1, occurred_at=older))
        s.commit()
    try:
        assert world.metrics("health", "30d")["platform_request_failure_rate"]["denominator"] == 10
        assert world.metrics("health", "all_time")["platform_request_failure_rate"]["denominator"] == 11
    finally:
        with world.sf() as s:
            s.execute(text("DELETE FROM operational_metric_events WHERE operation='GET /old'"))
            s.commit()


def test_reading_every_route_changes_nothing_and_makes_no_network_or_provider_call(world, monkeypatch):
    tables = ("ai_usage_facts", "ai_operation_events", "operational_metric_events", "jobs", "job_workers", "admin_notifications", "knowledge_source_versions",
              "knowledge_index_records", "users", "audit_events", "platform_pause_states")

    def snapshot():
        with world.sf() as s:
            return {t: s.scalar(text(f"SELECT COUNT(*) FROM {t}")) for t in tables}
    before = snapshot()
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    for route in ("definitions", *ROUTES):
        assert world.get(route, period="90d").status_code == 200
    assert snapshot() == before


def test_retrieval_outcomes_and_open_incidents_equal_their_rows(world):
    with world.sf() as s:
        for i in range(6):
            s.add(OperationalMetricEvent(event_type="retrieval", subsystem="career", operation="career_chat", outcome="error" if i < 2 else "hit", occurred_at=NOW - DAY))
        s.commit()
    try:
        k = world.metrics("knowledge")
        assert k["knowledge_retrieval_outcomes"]["value"] == 6
        assert k["knowledge_retrieval_error_rate"]["value"] == round(100 * 2 / 6, 1) and k["knowledge_retrieval_error_rate"]["numerator"] == 2
        out = {x["key"]: x["value"] for b in k["knowledge_retrieval_outcomes"]["breakdowns"] if b["dimension_id"] == "outcome" for x in b["buckets"]}
        assert out == {"error": 2, "hit": 4}
        assert world.metrics("security-signals")["security_open_incidents"]["value"] == 0
    finally:
        with world.sf() as s:
            s.execute(text("DELETE FROM operational_metric_events WHERE event_type='retrieval'"))
            s.commit()
