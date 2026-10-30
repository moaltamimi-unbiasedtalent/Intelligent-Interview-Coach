"""03E1: Admin report registry, governed builder, saved configurations and exports (backend). Offline and deterministic: temp DB, no provider, no network.

Load-bearing properties: the builder cannot express anything outside the 03K registry (no SQL, table, column, unregistered metric or dimension); every figure is the
existing suppressed pipeline's figure; filters never un-hide or recompute anything (cohort rule in ``src/reporting/report_builder.py``); saved configurations hold
definitions only, are owner-scoped and revision-protected; exports are bounded, formula-injection-safe, audited before sending, and carry no identifier."""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import re
import socket
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text

from src.api.admin_route_invariant import admin_routes, ungated
from src.api.schemas import report_builder as SCH
from src.application import admin_permissions as perm
from src.persistence import (
    AIUsageFact, AuditEvent, BillingCommercialTerms, BillingCustomer, BillingProviderSubscription, OperationalMetricEvent, PlanVersion, ReportConfiguration, Subscription,
    User, UserFeedback,
)
from src.reporting import contract as K
from src.reporting import report_builder as RB
from src.reporting.definitions import REPORTING_MIN_COHORT
from src.reporting.report_configs import MAX_CONFIGS_PER_OWNER, ConfigConflict, ReportConfigService
from tests import _admin_matrix as M
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

API = "/api/v1/admin/report-builder"
CAPI = f"{API}/commercial"
PW = "correcthorsebattery"
DENIED = "Administrator access required."
ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).replace(microsecond=0)
DAY = timedelta(days=1)
FORMULA_OPS = ("=SUM(1+1)", "+cmd", "-cmd", "@cmd", "GET /alpha")


class World:
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
        email = f"rb{self.n}@x.com"
        register(self.c, email, PW)
        ck = cookies_for(login_token(self.c, email, PW))
        uid = self.c.get("/api/v1/auth/me", cookies=ck).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return ck, uid

    def candidates(self, n: int, tag: str = "k") -> list[int]:
        out = []
        with self.sf() as s:
            for _ in range(n):
                self.n += 1
                u = User(subject=f"{tag}{self.n}-{uuid.uuid4().hex[:6]}", provider="test", email=f"sentinel-{tag}{self.n}@example.test", platform_role="user", status="active",
                         created_at=NOW - 3 * DAY, updated_at=NOW - 3 * DAY, onboarding_completed_at=NOW - 3 * DAY)
                s.add(u)
                s.flush()
                out.append(u.id)
            s.commit()
        return out

    def get(self, path: str, persona="platform_admin", base=API, **params):
        return self.c.get(f"{base}{path}", params=params or None, cookies=self.cookies[persona])

    def preview(self, persona="platform_admin", base=API, **q):
        return self.c.get(f"{base}/preview", params=q, cookies=self.cookies[persona])

    def close(self):
        self.c.__exit__(None, None, None)


def seed(w: World) -> dict:
    cands = w.candidates(8)                     # u0..u7
    basic_extra = w.candidates(4, "b")
    usd_owners = w.candidates(6, "d")
    fid = iter(range(10_000))
    with w.sf() as s:
        # feedback: accuracy 6 users (7 items), tone 2 users (2 items), clarity 7 users (7 items)
        def fb(uid, cat):
            s.add(UserFeedback(user_id=uid, surface="agent", target_id=f"t{next(fid)}", rating="helpful", category=cat, created_at=NOW - DAY, updated_at=NOW - DAY))
        for u in cands[:6]:
            fb(u, "accuracy")
        fb(cands[0], "accuracy")
        for u in cands[6:8]:
            fb(u, "tone")
        for u in cands[:7]:
            fb(u, "clarity")
        # AI usage: agent 6 users on terra (140 tokens, 1234 micro-USD), practice 6 users on luna (40 tokens), 2 users practice on sol with UNKNOWN tokens and cost
        for u in cands[:6]:
            s.add(AIUsageFact(usage_key=f"k{next(fid)}", user_id=u, workflow="agent", operation="run", model_profile="balanced", model_id="model/terra", model_calls=2,
                              input_tokens=100, output_tokens=40, total_tokens=140, cost_usd_micros=1234, cost_source="reported", token_coverage="complete",
                              cost_coverage="complete", occurred_at=NOW - DAY, updated_at=NOW - DAY))
            s.add(AIUsageFact(usage_key=f"k{next(fid)}", user_id=u, workflow="practice", operation="evaluate", model_profile="fast", model_id="model/luna", model_calls=1,
                              input_tokens=30, output_tokens=10, total_tokens=40, cost_usd_micros=100, cost_source="reported", token_coverage="complete",
                              cost_coverage="complete", occurred_at=NOW - DAY, updated_at=NOW - DAY))
        for u in cands[6:8]:
            s.add(AIUsageFact(usage_key=f"k{next(fid)}", user_id=u, workflow="practice", operation="evaluate", model_profile="advanced", model_id="model/sol", model_calls=1,
                              input_tokens=None, output_tokens=None, total_tokens=None, cost_usd_micros=None, cost_source="unavailable", token_coverage="unknown",
                              cost_coverage="unknown", occurred_at=NOW - DAY, updated_at=NOW - DAY))
        # operational request events: per operation, including formula-looking labels
        for i, op in enumerate(FORMULA_OPS):
            for j in range(3 + i):
                s.add(OperationalMetricEvent(event_type="request", subsystem="api", operation=op, outcome="success" if j else "server_error", duration_ms=10 * (j + 1),
                                             occurred_at=NOW - DAY))
        s.commit()
    from src.entitlements import seed_default_plans

    with w.sf() as s:
        seed_default_plans(s)
        s.commit()
    with w.sf() as s:
        pv = {p.plan_code: p.id for p in s.scalars(select(PlanVersion).where(PlanVersion.status == "active")).all()}
        for u in cands[:6]:
            s.add(Subscription(user_id=u, workspace_id=None, plan_version_id=pv["premium"], status="active", source="admin", started_at=NOW - 2 * DAY))
        for u in cands[6:8] + basic_extra:
            s.add(Subscription(user_id=u, workspace_id=None, plan_version_id=pv["basic"], status="active", source="system_default", started_at=NOW - 2 * DAY))
        terms = {}
        for cur, amt in (("EUR", 1999), ("USD", 2500)):
            t = BillingCommercialTerms(public_id=(cur + "t" * 31)[:32], plan_version_id=pv["premium"], version=1 + len(terms), amount_minor=amt, currency=cur,
                                       billing_interval="month", visibility="internal", state="retired", created_at=NOW)
            s.add(t)
            s.flush()
            terms[cur] = t
        for cur, owners in (("EUR", cands[:6]), ("USD", usd_owners)):
            for i, u in enumerate(owners):
                cust = BillingCustomer(public_id=f"c{cur}{i}{'0' * 32}"[:32], provider="mock", provider_customer_id=f"cus_{cur}{i}", state="active", user_id=u)
                s.add(cust)
                s.flush()
                s.add(BillingProviderSubscription(public_id=f"s{cur}{i}{'0' * 32}"[:32], provider="mock", provider_subscription_id=f"sub_{cur}{i}", customer_id=cust.id,
                                                  plan_version_id=pv["premium"], commercial_terms_id=terms[cur].id, provider_state="active"))
        s.commit()
    return {"cands": cands}


@pytest.fixture(scope="module")
def world():
    w = World()
    w.seeded = seed(w)
    yield w
    w.close()


@pytest.fixture(scope="module")
def empty():
    w = World()
    yield w
    w.close()


def n_rows(w, model) -> int:
    with w.sf() as s:
        return int(s.scalar(select(func.count()).select_from(model)) or 0)


def metric_of(body: dict, mid: str) -> dict:
    return next(m for m in body["metrics"] if m["metric_id"] == mid)


def buckets_of(body: dict, mid: str) -> dict[str, dict]:
    return {b["label"]: b for b in metric_of(body, mid)["buckets"]}


def banned_key_hits(node, path="$") -> list[str]:
    banned = {"content", "email", "ip", "token", "path", "secret", "password", "prompt", "user", "address", "cookie", "comment", "answer", "transcript", "owner"}
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


def definition_dict(**over) -> dict:
    base = {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "window": "30d", "group_by": "workflow", "filters": [], "chart": None}
    base.update(over)
    return base


def create_saved(w, persona="platform_admin", name=None, base=API, definition=None, shared=False):
    return w.c.post(f"{base}/saved", json={"name": name or f"cfg {uuid.uuid4().hex[:8]}", "definition": definition or definition_dict(), "shared": shared}, cookies=w.cookies[persona])


# ================================================================================================================ registry and the 03K contract
def test_registry_conforms_to_the_03k_contract_and_covers_every_registered_metric():
    metrics, dims, reports = K.default_registry()
    K.validate_registry(metrics, dims, reports)
    assert set(RB._SOURCES) == {m.metric_id for m in metrics}
    assert set(RB.REGISTRY.types) == {r.report_id for r in reports} == {"product", "quality", "ai_economics", "commercial"}
    for t in RB.REGISTRY.types.values():
        assert t.permission in perm.PERMISSION_SET and t.permission in (perm.REPORTS_READ, perm.REPORTS_COMMERCIAL)
        assert all(m.permission_required == t.permission for m in t.metrics.values())
        assert set(t.windows) <= set(RB.BUILDER_WINDOWS) and "all_time" not in t.windows
        for mid in t.metrics:
            assert set(t.dimensions_for(mid)) <= set(t.metrics[mid].dimensions_allowed)
    assert RB.REGISTRY.types["commercial"].permission == perm.REPORTS_COMMERCIAL
    assert len(perm.PERMISSIONS) == 44                                        # no permission was added


def test_the_frozen_03k_contract_files_are_untouched():
    for rel in ("src/reporting/contract.py", "frontend/lib/admin/metricContract.ts"):
        if not (ROOT / rel).exists():
            continue
        base = subprocess.run(["git", "-C", str(ROOT), "show", f"origin/main:{rel}"], capture_output=True)
        if base.returncode != 0:
            pytest.skip("origin/main is not available in this checkout")
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == hashlib.sha256(base.stdout).hexdigest(), rel


@pytest.mark.parametrize("raw", [
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "sql": "SELECT 1"},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "table": "users"},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "column": "email"},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "where": "1=1"},
    {"report_id": "ai_economics", "metric_ids": []},
    {"report_id": "ai economics", "metric_ids": ["ai_usage"]},
    {"report_id": "ai_economics", "metric_ids": ["users.email"]},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage; DROP TABLE users"]},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage", "ai_usage"]},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "window": "1d"},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "window": "2026-01-01"},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "chart": "pie"},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "filters": [{"dimension_id": "workflow", "values": ["x' OR 1=1 --"]}]},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "filters": [{"dimension_id": "workflow", "values": ["a;DROP"]}]},
    {"report_id": "ai_economics", "metric_ids": ["ai_usage"], "filters": [{"dimension_id": "workflow", "values": ["ok"], "op": "like"}]},
    {"report_id": "ai_economics", "metric_ids": [f"m{i}" for i in range(13)]},
])
def test_the_definition_cannot_express_sql_a_table_a_column_or_an_open_value(raw):
    with pytest.raises(RB.ReportInvalid):
        RB.parse_definition(raw)


PLAT = perm.permissions_for_role("platform_admin")


def problems_of(**over) -> set[str]:
    with pytest.raises(RB.ReportInvalid) as e:
        RB.validate_definition(RB.parse_definition(definition_dict(**over)), PLAT, perm.REPORTS_READ)
    return {c for c, _f, _m in e.value.problems}


def test_the_registry_rejects_unknown_misplaced_and_unsupported_choices():
    assert problems_of(report_id="nope") == {"unknown_report"}
    assert problems_of(metric_ids=["nope"]) == {"unknown_metric"}
    assert problems_of(metric_ids=["registrations"]) == {"metric_not_in_report"}               # a real metric of ANOTHER report type
    assert problems_of(group_by="nope") == {"unknown_dimension"}
    assert problems_of(group_by="time") == {"dimension_not_supported"}                       # no registered metric has a time breakdown
    assert problems_of(group_by="plan") == {"dimension_not_supported"}                       # a registered dimension this metric does not allow
    assert problems_of(window="all_time") == {"window_too_wide"}
    assert problems_of(chart="trend") == {"chart_incompatible"}                              # trend needs a time dimension
    assert "chart_incompatible" in problems_of(chart="funnel")


def test_a_chart_kind_must_fit_the_meaning_of_the_metrics():
    ok = RB.validate_definition(RB.parse_definition(definition_dict(chart="distribution")), PLAT, perm.REPORTS_READ)
    assert ok.definition.chart == "distribution"
    for kind in ("share_of_whole", "table"):
        RB.validate_definition(RB.parse_definition(definition_dict(chart=kind)), PLAT, perm.REPORTS_READ)
    assert "chart_incompatible" in problems_of(metric_ids=["ai_usage", "ai_known_cost"], chart="share_of_whole")      # exactly one additive metric
    assert "chart_incompatible" in problems_of(group_by=None, chart="distribution")


def test_filters_must_name_the_grouping_dimension_and_need_a_grouping():
    f = lambda d, v: [{"dimension_id": d, "values": v}]               # noqa: E731
    assert problems_of(filters=f("model", ["model/terra"])) == {"cross_dimension_filter"}
    assert problems_of(group_by=None, filters=f("workflow", ["agent"])) == {"filter_needs_grouping"}
    assert problems_of(filters=f("nope", ["x"])) == {"unknown_dimension"}
    RB.validate_definition(RB.parse_definition(definition_dict(filters=f("workflow", ["agent"]))), PLAT, perm.REPORTS_READ)


def test_currencies_are_never_combined_and_a_money_metric_must_group_by_currency():
    d = lambda **o: RB.parse_definition({"report_id": "commercial", "metric_ids": ["mock_mrr"], "window": "30d", **o})        # noqa: E731
    with pytest.raises(RB.ReportInvalid) as e:
        RB.validate_definition(d(), PLAT, perm.REPORTS_COMMERCIAL)
    assert {c for c, _f, _m in e.value.problems} == {"must_group"}
    RB.validate_definition(d(group_by="currency"), PLAT, perm.REPORTS_COMMERCIAL)


def test_an_oversized_definition_is_refused():
    vals = [("v" * 63 + str(i))[:64] for i in range(10)]
    big = RB.parse_definition(definition_dict(filters=[{"dimension_id": d, "values": vals} for d in ("workflow", "model", "operation")]))
    assert len(big.canonical().encode()) > RB.MAX_DEFINITION_BYTES
    with pytest.raises(RB.ReportInvalid) as e:
        RB.validate_definition(big, PLAT, perm.REPORTS_READ)
    assert "definition_too_large" in {c for c, _f, _m in e.value.problems}


@pytest.mark.parametrize("name,ok", [("Weekly AI usage", True), ("a.b-c_d 9", True), ("ab", False), ("=cmd here", False), ("-minus", False), ("two  spaces", False),
                                      ("x" * 61, False), ("name; DROP TABLE x", False), ("select * from users", False), ("tab\tname", False), ("", False)])
def test_saved_names_are_validated(name, ok):
    if ok:
        assert RB.validate_name(name) == name.strip()
    else:
        with pytest.raises(RB.ReportInvalid):
            RB.validate_name(name)


# ================================================================================================================ authorization
def _builder_routes():
    return [r for r in admin_routes() if r.path.startswith("/admin/report-builder")]


def test_the_routes_are_gated_with_existing_permissions_only_and_known_to_the_invariants():
    rs = _builder_routes()
    assert len(rs) == 20 and ungated() == []
    assert all(len(r.permissions) == 1 and r.permissions <= {perm.REPORTS_READ, perm.REPORTS_COMMERCIAL} for r in rs)
    assert {r.path.startswith("/admin/report-builder/commercial") for r in rs if perm.REPORTS_COMMERCIAL in r.permissions} == {True}
    assert {r.path.startswith("/admin/report-builder/commercial") for r in rs if perm.REPORTS_READ in r.permissions} == {False}
    for r in rs:
        assert M.domain_of(r.path) == "reports"
    assert not [r for r in admin_routes() if M.domain_of(r.path) == "UNMAPPED"]
    reads = {r.path for r in rs if r.methods == ("GET",)}
    assert all(("/preview" in p or "/validate" in p or "registry" in p or "/saved" in p) for p in reads)
    assert {r.path for r in rs if r.methods == ("POST",)} == {f"/admin/report-builder{x}/{y}" for x in ("", "/commercial") for y in ("saved", "export")}
    assert len(perm.PERMISSIONS) == 44                                          # no new permission


def _call(w, persona, method, base, path, ck=None):
    ck = ck if ck is not None else w.cookies[persona]
    prod = base == API
    q = {"report_id": "product" if prod else "commercial", "metric_ids": "registrations" if prod else "access_plans", "window": "30d"}
    d = {"report_id": "product", "metric_ids": ["registrations"], "window": "30d"} if prod else {"report_id": "commercial", "metric_ids": ["mock_failed_payments"], "window": "30d"}
    url = f"{base}{path}"
    if path in ("/registry", "/saved", "/saved/987654", "/saved/987654/preview"):
        return w.c.get(url, cookies=ck)
    if path in ("/validate", "/preview"):
        return w.c.get(url, params=q, cookies=ck)
    if method == "POST" and path == "/saved":
        return w.c.post(url, json={"name": f"matrix {uuid.uuid4().hex[:6]}", "definition": d, "shared": False}, cookies=ck)
    if method == "PUT":
        return w.c.put(url, json={"name": "matrix cfg", "definition": d, "shared": False, "expected_revision": 1}, cookies=ck)
    if method == "DELETE":
        return w.c.delete(f"{url}?expected_revision=1", cookies=ck)
    return w.c.post(url, json={"format": "csv", "definition": d}, cookies=ck)


@pytest.mark.parametrize("base", [API, CAPI])
def test_every_persona_is_allowed_or_403_exactly_as_the_presets_say(world, base):
    required = perm.REPORTS_READ if base == API else perm.REPORTS_COMMERCIAL
    paths = [("GET", "/registry"), ("GET", "/validate"), ("GET", "/preview"), ("GET", "/saved"), ("POST", "/saved"), ("GET", "/saved/987654"), ("PUT", "/saved/987654"),
             ("DELETE", "/saved/987654"), ("GET", "/saved/987654/preview"), ("POST", "/export")]
    inv = {(r.methods[0], r.path.replace("/admin/report-builder", "").replace("/commercial", "")): r.permissions for r in _builder_routes()
           if r.path.startswith("/admin/report-builder/commercial") == (base == CAPI)}
    assert {k: next(iter(v)) for k, v in inv.items()} == {(m, p.replace("987654", "{config_id}")): required for m, p in paths}
    for persona in M.PERSONAS:
        allowed = M.expected_allowed(frozenset({required}), persona)
        for method, path in paths:
            resp = _call(world, persona, method, base, path)
            if allowed:
                assert resp.status_code in (200, 201, 204, 404), (base, persona, method, path, resp.status_code, resp.text[:200])
            else:
                assert resp.status_code == 403 and resp.json()["error"]["message"] == DENIED, (base, persona, method, path, resp.status_code)
                assert "metric_id" not in resp.text
    from fastapi.testclient import TestClient

    with TestClient(world.app) as anon:                                                  # a client with no cookie jar: no session
        for method, path in paths:
            holder = type("W", (), {"c": anon, "cookies": {"user": {}}})
            assert _call(holder, "user", method, base, path).status_code in (401, 403), (method, path)


def test_a_report_type_of_the_other_family_is_403_never_trimmed(world):
    assert world.preview("platform_admin", API, report_id="commercial", metric_ids="access_plans", window="30d").status_code == 403
    assert world.preview("platform_admin", CAPI, report_id="product", metric_ids="registrations", window="30d").status_code == 403
    assert world.preview("billing_admin", CAPI, report_id="commercial", metric_ids="access_plans", window="30d").status_code == 200
    assert world.preview("billing_admin", API, report_id="commercial", metric_ids="access_plans", window="30d").status_code == 403       # lacks reports.read
    assert world.preview("operations_admin", CAPI, report_id="commercial", metric_ids="access_plans", window="30d").status_code == 403
    assert world.preview("operations_admin", API, report_id="product", metric_ids="registrations", window="30d").status_code == 200
    saved = create_saved(world, "platform_admin", base=API, definition={"report_id": "commercial", "metric_ids": ["access_plans"], "window": "30d", "group_by": "plan"})
    assert saved.status_code == 403
    assert create_saved(world, "operations_admin", base=CAPI).status_code == 403


def test_registry_lists_only_what_the_caller_may_use(world):
    ops = world.get("/registry", "operations_admin").json()
    assert {t["report_id"] for t in ops["report_types"]} == {"product", "quality", "ai_economics"}
    assert {t["permission_required"] for t in ops["report_types"]} == {perm.REPORTS_READ}
    bill = world.get("/registry", "billing_admin", CAPI).json()
    assert {t["report_id"] for t in bill["report_types"]} == {"commercial"}
    owner = world.get("/registry", "platform_admin").json()
    assert owner["windows"] == ["7d", "30d", "90d"] and owner["chart_kinds"] == list(RB.CHART_KINDS) and owner["min_cohort"] == REPORTING_MIN_COHORT
    blob = json.dumps(owner)
    assert "SELECT" not in blob.upper().replace("SELECTED", "") and "sentinel" not in blob
    assert "commercial" not in {t["report_id"] for t in owner["report_types"]}                    # the commercial family has its own registry


def test_validate_reports_problems_with_codes_and_never_echoes_input(world):
    r = world.get("/validate", report_id="ai_economics", metric_ids=["ai_usage"], window="all_time")
    assert r.status_code == 200 and r.json()["valid"] is False and r.json()["problems"][0]["code"] == "window_too_wide"
    r = world.get("/validate", report_id="ai_economics", metric_ids=["ai_usage"], window="30d", group_by="workflow")
    assert r.json() == {"valid": True, "problems": []}
    secret = "zz_sentinel_metric_zz"
    r = world.c.get(f"{API}/validate", params={"report_id": "ai_economics", "metric_ids": secret}, cookies=world.cookies["platform_admin"])
    assert secret not in r.text
    r = world.c.get(f"{API}/preview", params={"report_id": "ai_economics", "metric_ids": ["ai_usage"], "window": secret}, cookies=world.cookies["platform_admin"])
    assert r.status_code == 422 and secret not in r.text
    r = world.c.get(f"{API}/preview", params={"report_id": "ai_economics", "metric_ids": ["ai_usage"], "filter": "no-colon-here"}, cookies=world.cookies["platform_admin"])
    assert r.status_code == 422


def test_a_deactivated_admin_has_no_authority(world):
    ck, uid = world.make("platform_admin")
    assert world.c.get(f"{API}/registry", cookies=ck).status_code == 200
    with world.sf() as s:
        s.execute(text("UPDATE users SET status='deactivated' WHERE id=:i"), {"i": uid})
        s.commit()
    assert world.c.get(f"{API}/registry", cookies=ck).status_code in (401, 403)


# ================================================================================================================ numbers equal facts
def db_scalar(w, stmt):
    with w.sf() as s:
        return s.scalar(stmt)


def test_product_figures_equal_the_database_facts_and_the_existing_report(world):
    cand = select(User.id).where(User.platform_role == "user")
    since = datetime.now(timezone.utc) - timedelta(days=30)
    regs = db_scalar(world, select(func.count()).select_from(User).where(User.platform_role == "user", User.created_at >= since))
    assert regs >= 18
    body = world.preview(report_id="product", metric_ids=["registrations", "onboarding_completed", "opportunities_created"], window="30d").json()
    assert metric_of(body, "registrations")["value"] == regs and metric_of(body, "registrations")["state"] == "ok"
    legacy = world.c.get("/api/v1/admin/reports/product?period=30d", cookies=world.cookies["platform_admin"]).json()
    figures = {m["metric_id"]: m for sec in legacy["sections"] for m in sec["metrics"]}
    assert metric_of(body, "registrations")["value"] == figures["registrations"]["figure"]
    assert metric_of(body, "onboarding_completed")["value"] == figures["onboarding_completed"]["figure"]
    assert metric_of(body, "opportunities_created")["state"] == "suppressed" and metric_of(body, "opportunities_created")["value"] is None      # none exist: never a zero
    del cand


def test_feedback_total_and_categories_equal_the_rows_with_suppression_applied(world):
    body = world.preview(report_id="quality", metric_ids=["feedback"], window="30d", group_by="feedback_category").json()
    assert body["group_by"] == "feedback_category"
    b = buckets_of(body, "feedback")
    assert b["clarity"] == {"label": "clarity", "state": "ok", "value": 7}
    assert b["tone"]["state"] == "suppressed" and b["tone"]["value"] is None            # 2 candidates
    assert b["accuracy"]["state"] == "suppressed" and b["accuracy"]["value"] is None    # secondary suppression: exactly one bucket was hidden
    total = world.preview(report_id="quality", metric_ids=["feedback"], window="30d").json()
    assert metric_of(total, "feedback")["value"] == db_scalar(world, select(func.count()).select_from(UserFeedback)) == 16
    assert "accuracy" not in json.dumps(total)


def test_ai_usage_and_cost_equal_the_usage_facts_and_exclude_unknown(world):
    body = world.preview(report_id="ai_economics", metric_ids=["ai_usage", "ai_known_cost"], window="30d", group_by="workflow").json()
    tokens, cost = buckets_of(body, "ai_usage"), buckets_of(body, "ai_known_cost")
    assert tokens["agent"]["value"] == 6 * 140 and tokens["practice"]["value"] == 6 * 40            # unknown-token units are excluded, never counted as zero
    assert cost["agent"]["value"] == round(6 * 1234 / 1_000_000, 6) and cost["practice"]["value"] == round(6 * 100 / 1_000_000, 6)
    with world.sf() as s:
        assert s.scalar(select(func.sum(AIUsageFact.total_tokens)).where(AIUsageFact.workflow == "agent")) == tokens["agent"]["value"]
        assert s.scalar(select(func.sum(AIUsageFact.cost_usd_micros))) == 6 * 1234 + 6 * 100
    total = world.preview(report_id="ai_economics", metric_ids=["ai_usage"], window="30d").json()
    assert metric_of(total, "ai_usage")["value"] == 6 * 140 + 6 * 40 and metric_of(total, "ai_usage")["partial"] is True
    models = buckets_of(world.preview(report_id="ai_economics", metric_ids=["ai_usage"], window="30d", group_by="model").json(), "ai_usage")
    assert models["model/sol"]["state"] == "suppressed"                                               # 2 candidates; known tokens are none


def test_request_outcomes_by_operation_equal_the_event_rows(world):
    body = world.preview(report_id="quality", metric_ids=["request_outcomes"], window="30d", group_by="operation").json()
    b = buckets_of(body, "request_outcomes")
    expected = {op: 3 + i for i, op in enumerate(FORMULA_OPS)}
    assert {k: v["value"] for k, v in b.items() if k in expected} == expected
    assert all(v["state"] == "ok" for k, v in b.items() if k in expected)                              # operational metrics have no candidate cohort
    assert metric_of(world.preview(report_id="quality", metric_ids=["request_outcomes"], window="30d").json(), "request_outcomes")["value"] >= sum(expected.values())


def test_commercial_figures_equal_the_rows_and_currencies_are_never_combined(world):
    body = world.preview("platform_admin", CAPI, report_id="commercial", metric_ids=["access_plans"], window="30d", group_by="plan").json()
    plans = buckets_of(body, "access_plans")
    with world.sf() as s:
        facts = {c: s.scalar(select(func.count(func.distinct(Subscription.user_id))).join(PlanVersion, Subscription.plan_version_id == PlanVersion.id).where(
            PlanVersion.plan_code == c, Subscription.status == "active", Subscription.ended_at.is_(None))) for c in ("basic", "premium")}
    assert facts["premium"] == 6 and facts["basic"] >= 6
    assert plans == {c: {"label": c, "state": "ok", "value": n} for c, n in facts.items()}
    money = world.preview("billing_admin", CAPI, report_id="commercial", metric_ids=["mock_mrr", "mock_arr"], window="30d", group_by="currency").json()
    mrr, arr = buckets_of(money, "mock_mrr"), buckets_of(money, "mock_arr")
    assert mrr["EUR"]["value"] == 6 * 19.99 and mrr["USD"]["value"] == 6 * 25.0 and arr["EUR"]["value"] == round(6 * 19.99 * 12, 2) and arr["USD"]["value"] == 6 * 300.0
    assert set(mrr) == {"EUR", "USD"} and metric_of(money, "mock_mrr")["value"] is None                # no combined figure exists
    assert world.preview("billing_admin", CAPI, report_id="commercial", metric_ids=["mock_mrr"], window="30d").status_code == 422


def test_an_empty_database_reports_missing_states_not_zero(empty):
    body = empty.preview(report_id="ai_economics", metric_ids=["ai_usage", "ai_known_cost"], window="30d").json()
    for m in body["metrics"]:
        assert m["state"] in ("unavailable", "not_captured") and m["value"] is None
    g = empty.preview(report_id="ai_economics", metric_ids=["ai_usage"], window="30d", group_by="workflow").json()
    assert metric_of(g, "ai_usage")["buckets"] == [] and metric_of(g, "ai_usage")["state"] == "unavailable"
    f = empty.preview(report_id="quality", metric_ids=["feedback"], window="30d").json()
    assert metric_of(f, "feedback")["state"] in ("unavailable", "not_captured") and metric_of(f, "feedback")["value"] is None
    c = empty.preview("platform_admin", CAPI, report_id="commercial", metric_ids=["mock_mrr", "mock_arr"], window="30d", group_by="currency").json()
    for m in c["metrics"]:
        assert m["buckets"] == [] and m["state"] == "unavailable" and m["value"] is None                # unconfigured: never zero revenue


# ================================================================================================================ suppression and the cohort rule
def test_a_small_cohort_is_suppressed_and_the_count_never_appears(world):
    r = world.preview(report_id="quality", metric_ids=["feedback"], window="30d", group_by="feedback_category")
    body = r.json()
    for label in ("tone", "accuracy"):
        assert buckets_of(body, "feedback")[label]["value"] is None
    hidden = [b for b in metric_of(body, "feedback")["buckets"] if b["label"] in ("tone", "accuracy")]
    assert all(set(b) == {"label", "state", "value"} for b in hidden) and not re.findall(r"\d", json.dumps([{k: v for k, v in b.items() if k != "label"} for b in hidden]))
    assert "2 candidates" not in r.text and "<5" not in r.text and "< 5" not in r.text


def test_secondary_suppression_survives_the_builder(world):
    for dim, metric, rid in (("feedback_category", "feedback", "quality"), ("model", "ai_usage", "ai_economics")):
        b = buckets_of(world.preview(report_id=rid, metric_ids=[metric], window="30d", group_by=dim).json(), metric)
        hidden = [k for k, v in b.items() if v["state"] == "suppressed"]
        assert len(hidden) != 1, (dim, hidden)                                                         # never exactly one hidden bucket


def test_a_filter_selects_rows_after_suppression_and_never_unhides_or_recomputes(world):
    base = buckets_of(world.preview(report_id="quality", metric_ids=["feedback"], window="30d", group_by="feedback_category").json(), "feedback")
    labels = sorted(base)
    for k in range(1, len(labels) + 1):
        for combo in itertools.combinations(labels, k):
            r = world.c.get(f"{API}/preview", params={"report_id": "quality", "metric_ids": ["feedback"], "window": "30d", "group_by": "feedback_category",
                                                      "filter": [f"feedback_category:{c}" for c in combo]}, cookies=world.cookies["platform_admin"])
            assert r.status_code == 200
            got = buckets_of(r.json(), "feedback")
            assert set(got) == set(combo)
            for c in combo:
                assert got[c] == base[c], (combo, c)                                                   # identical to the unfiltered cell: no variant shows a new number
    only_hidden = buckets_of(world.preview(report_id="quality", metric_ids=["feedback"], window="30d", group_by="feedback_category", filter="feedback_category:tone").json(), "feedback")
    assert only_hidden == {"tone": {"label": "tone", "state": "suppressed", "value": None}}
    none = metric_of(world.preview(report_id="quality", metric_ids=["feedback"], window="30d", group_by="feedback_category", filter="feedback_category:nothing").json(), "feedback")
    assert none["buckets"] == [] and "No bucket matches" in none["note"]


def test_saved_variants_cannot_difference_into_a_hidden_cell(world):
    """Two saved variants of one definition (different filters) are two row selections of the same suppressed table: their cell sets are subsets of the base set."""
    base = buckets_of(world.preview(report_id="ai_economics", metric_ids=["ai_usage"], window="30d", group_by="model").json(), "ai_usage")
    seen = {}
    for combo in (["model/terra"], ["model/luna"], ["model/sol"], ["model/terra", "model/sol"]):
        d = definition_dict(group_by="model", filters=[{"dimension_id": "model", "values": combo}])
        sid = create_saved(world, definition=d).json()["id"]
        got = buckets_of(world.get(f"/saved/{sid}/preview").json(), "ai_usage")
        for label, cell in got.items():
            assert cell == base[label]
            seen[label] = cell
    assert seen == base                                                                                # the union of all variants is exactly the base: nothing new


def test_cross_dimension_and_ungrouped_filters_are_refused_over_http(world):
    for q in ({"filter": "model:model/terra"}, {"group_by": "workflow", "filter": "model:model/terra"}):
        r = world.c.get(f"{API}/preview", params={"report_id": "ai_economics", "metric_ids": ["ai_usage"], "window": "30d", **q}, cookies=world.cookies["platform_admin"])
        assert r.status_code == 422 and ("[filter_needs_grouping]" in r.text or "[cross_dimension_filter]" in r.text)


def test_windows_are_a_closed_set_and_all_time_is_over_wide(world):
    for p in RB.BUILDER_WINDOWS:
        assert world.preview(report_id="ai_economics", metric_ids=["ai_usage"], window=p).status_code == 200
    r = world.preview(report_id="ai_economics", metric_ids=["ai_usage"], window="all_time")
    assert r.status_code == 422 and "[window_too_wide]" in r.text
    assert world.preview(report_id="ai_economics", metric_ids=["ai_usage"], window="365d").status_code == 422
    assert world.c.get("/api/v1/admin/reports/ai-economics?period=all_time", cookies=world.cookies["platform_admin"]).status_code == 200      # still on the fixed endpoints


def test_previous_period_comparison_is_the_same_pipeline_one_window_earlier(world):
    with world.sf() as s:
        for j in range(6):
            s.add(OperationalMetricEvent(event_type="request", subsystem="api", operation="prev_op", outcome="success", duration_ms=5, occurred_at=NOW - 10 * DAY))
        s.commit()
    q = {"report_id": "quality", "metric_ids": ["request_outcomes"], "window": "7d", "comparison": "previous_period"}
    body = world.c.get(f"{API}/preview", params={**q, "group_by": "operation"}, cookies=world.cookies["platform_admin"]).json()
    m = metric_of(body, "request_outcomes")
    assert body["comparison"] == "previous_period" and body["previous_window_end"] == body["window_start"]
    cur = {b["label"]: b["value"] for b in m["buckets"]}
    prev = {b["label"]: b["value"] for b in m["previous"]["buckets"]}
    assert "prev_op" not in cur and prev == {"prev_op": 6}                                        # disjoint windows: nothing counted twice
    flat = world.c.get(f"{API}/preview", params=q, cookies=world.cookies["platform_admin"]).json()
    assert metric_of(flat, "request_outcomes")["previous"]["value"] == 6
    none = world.preview(report_id="quality", metric_ids=["request_outcomes"], window="7d").json()
    assert none["comparison"] == "none" and metric_of(none, "request_outcomes")["previous"] is None and none["previous_window_start"] is None


def test_a_current_state_metric_cannot_be_compared_and_comparison_is_a_closed_set(world):
    r = world.c.get(f"{CAPI}/preview", params={"report_id": "commercial", "metric_ids": ["access_plans"], "window": "7d", "comparison": "previous_period"},
                    cookies=world.cookies["billing_admin"])
    assert r.status_code == 422 and "[not_comparable]" in r.text
    assert world.preview(report_id="quality", metric_ids=["feedback"], window="7d", comparison="year_over_year").status_code == 422
    owner = world.get("/registry").json()
    assert owner["comparisons"] == ["none", "previous_period"]
    assert world.get("/registry", "billing_admin", CAPI).json()["report_types"][0]["metrics"][0]["comparable"] in (True, False)


# ================================================================================================================ saved configurations
def test_saved_configuration_lifecycle_is_audited_in_the_same_transaction(world):
    name = f"lifecycle {uuid.uuid4().hex[:6]}"
    r = create_saved(world, name=name, definition=definition_dict(chart="share_of_whole"))
    assert r.status_code == 201
    cfg = r.json()
    assert cfg["revision"] == 1 and cfg["editable"] and cfg["shared"] is False and cfg["definition"]["chart"] == "share_of_whole"
    assert cfg["name"] == name and "owner" not in " ".join(cfg) and banned_key_hits(cfg) == []
    assert world.get(f"/saved/{cfg['id']}").json() == cfg
    upd = world.c.put(f"{API}/saved/{cfg['id']}", json={"name": name + " v2", "definition": definition_dict(group_by="model"), "shared": False, "expected_revision": 1},
                      cookies=world.cookies["platform_admin"])
    assert upd.status_code == 200 and upd.json()["revision"] == 2 and upd.json()["definition"]["group_by"] == "model"
    assert world.c.delete(f"{API}/saved/{cfg['id']}", params={"expected_revision": 2}, cookies=world.cookies["platform_admin"]).status_code == 204
    assert world.get(f"/saved/{cfg['id']}").status_code == 404
    with world.sf() as s:
        rows = s.scalars(select(AuditEvent).where(AuditEvent.event_type.like("admin.report_config_%"), AuditEvent.target_id == str(cfg["id"])).order_by(AuditEvent.id)).all()
    assert [r.event_type for r in rows] == ["admin.report_config_created", "admin.report_config_updated", "admin.report_config_deleted"]
    assert all(r.actor_user_id == world.uids["platform_admin"] and r.result == "success" for r in rows)
    assert rows[1].context["changed_fields"] == ["name", "definition"] and rows[1].context["revision"] == 2
    dump = json.dumps([r.context for r in rows])
    assert name not in dump and "metric_ids" not in dump and "ai_usage" not in dump                     # no name, definition body or figure in an audit payload


def test_an_audit_failure_rolls_the_saved_configuration_change_back(world, monkeypatch):
    from src.auth_repository import AccountRepository

    def boom(session, audit):
        raise RuntimeError("audit store down")
    before = n_rows(world, ReportConfiguration)
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    with pytest.raises(Exception):
        ReportConfigService(world.sf).create(world.uids["platform_admin"], "audit fail", RB.parse_definition(definition_dict()), False,
                                             audit={"event_type": "admin.report_config_created", "actor_user_id": world.uids["platform_admin"]})
    monkeypatch.undo()
    assert n_rows(world, ReportConfiguration) == before


def test_a_saved_configuration_holds_the_definition_only(world):
    sid = create_saved(world, definition=definition_dict(filters=[{"dimension_id": "workflow", "values": ["agent"]}])).json()["id"]
    with world.sf() as s:
        row = s.get(ReportConfiguration, sid)
        stored = json.dumps(row.definition_json)
        cols = {c.name for c in ReportConfiguration.__table__.columns}
    assert set(row.definition_json) <= {"report_id", "metric_ids", "window", "group_by", "filters", "chart", "comparison"}
    assert not re.search(r"\b\d{3,}\b", stored.replace("30d", ""))                                       # no figure
    assert cols == {"id", "owner_user_id", "name", "report_id", "definition_json", "definition_hash", "shared", "revision", "created_at", "updated_at"}
    assert not (cols & {"result", "results", "data", "rows", "value", "values", "payload", "candidate_id", "user_ids"})
    assert row.definition_hash == RB.parse_definition(row.definition_json).digest()


def test_configurations_are_owner_scoped_and_sharing_needs_the_existing_permission(world):
    mine = create_saved(world, "platform_admin", name=f"private {uuid.uuid4().hex[:5]}").json()
    shared = create_saved(world, "platform_admin", name=f"shared {uuid.uuid4().hex[:5]}", shared=True).json()
    ops_ids = {c["id"] for c in world.get("/saved", "operations_admin").json()["items"]}
    assert shared["id"] in ops_ids and mine["id"] not in ops_ids                                        # shared is visible to an Admin who holds reports.read
    assert world.get(f"/saved/{mine['id']}", "operations_admin").status_code == 404                     # a private one is indistinguishable from a missing one
    assert world.get(f"/saved/{shared['id']}/preview", "operations_admin").status_code == 200           # the viewer runs it under the VIEWER's permissions
    put = world.c.put(f"{API}/saved/{shared['id']}", json={"name": "hijack name", "definition": definition_dict(), "shared": False, "expected_revision": 1},
                      cookies=world.cookies["operations_admin"])
    assert put.status_code == 403
    assert world.c.delete(f"{API}/saved/{shared['id']}", params={"expected_revision": 1}, cookies=world.cookies["operations_admin"]).status_code == 403
    assert world.c.put(f"{API}/saved/{mine['id']}", json={"name": "hijack name", "definition": definition_dict(), "shared": False, "expected_revision": 1},
                       cookies=world.cookies["operations_admin"]).status_code == 404
    assert world.get(f"/saved/{shared['id']}").json()["revision"] == 1
    assert [c for c in world.get("/saved", "operations_admin").json()["items"] if c["id"] == shared["id"]][0]["editable"] is False
    # a shared COMMERCIAL definition is invisible to an Admin without the commercial permission, on either family
    comm = create_saved(world, "platform_admin", base=CAPI, definition={"report_id": "commercial", "metric_ids": ["access_plans"], "window": "30d", "group_by": "plan"},
                        shared=True).json()
    assert world.get(f"/saved/{comm['id']}", "operations_admin", base=CAPI).status_code == 403
    assert world.get(f"/saved/{comm['id']}", "operations_admin").status_code == 404
    assert comm["id"] not in {c["id"] for c in world.get("/saved", "operations_admin").json()["items"]}
    assert world.get(f"/saved/{comm['id']}", "billing_admin", base=CAPI).status_code == 200
    assert comm["id"] not in {c["id"] for c in world.get("/saved", "platform_admin").json()["items"]}   # families are separate lists
    # an Admin's stale share is re-checked at read time: removing sharing hides it again
    world.c.put(f"{API}/saved/{shared['id']}", json={"name": shared["name"], "definition": definition_dict(), "shared": False, "expected_revision": 1},
                cookies=world.cookies["platform_admin"])
    assert world.get(f"/saved/{shared['id']}", "operations_admin").status_code == 404


def test_expected_revision_protects_updates_deletes_and_replays_are_idempotent(world):
    cfg = create_saved(world).json()
    put = lambda rev, **o: world.c.put(f"{API}/saved/{cfg['id']}", json={"name": cfg["name"], "definition": definition_dict(group_by="model"), "shared": False,  # noqa: E731
                                                                         "expected_revision": rev, **o}, cookies=world.cookies["platform_admin"])
    first = put(1)
    assert first.status_code == 200 and first.json()["revision"] == 2
    with world.sf() as s:
        n_audit = s.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.target_id == str(cfg["id"])))
    again = put(1)                                                                                        # a retried request: identical content, stale token
    assert again.status_code == 200 and again.json()["revision"] == 2
    with world.sf() as s:
        assert s.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.target_id == str(cfg["id"]))) == n_audit    # no duplicate audit
    conflict = world.c.put(f"{API}/saved/{cfg['id']}", json={"name": cfg["name"], "definition": definition_dict(group_by="workflow", chart="table"), "shared": False,
                                                            "expected_revision": 1}, cookies=world.cookies["platform_admin"])
    assert conflict.status_code == 409                                                                    # a DIFFERENT change on a stale token
    assert world.get(f"/saved/{cfg['id']}").json()["definition"]["group_by"] == "model"                   # the stale write changed nothing
    assert world.c.put(f"{API}/saved/{cfg['id']}", json={"name": cfg["name"], "definition": definition_dict(), "shared": False}, cookies=world.cookies["platform_admin"]).status_code == 422
    assert world.c.delete(f"{API}/saved/{cfg['id']}", params={"expected_revision": 1}, cookies=world.cookies["platform_admin"]).status_code == 409
    assert world.c.delete(f"{API}/saved/{cfg['id']}", cookies=world.cookies["platform_admin"]).status_code == 422
    assert world.c.delete(f"{API}/saved/{cfg['id']}", params={"expected_revision": 2}, cookies=world.cookies["platform_admin"]).status_code == 204


def test_concurrent_updates_with_one_expected_revision_have_exactly_one_winner(world):
    svc = ReportConfigService(world.sf)
    owner = world.uids["platform_admin"]
    view, _ = svc.create(owner, f"race {uuid.uuid4().hex[:5]}", RB.parse_definition(definition_dict()), False)
    readable = frozenset({"ai_economics"})
    results = []
    for chart in ("table", "distribution"):                                                                # both writers loaded revision 1
        try:
            svc.update(owner, view["id"], expected_revision=1, name=view["name"], definition=RB.parse_definition(definition_dict(chart=chart)), shared=False, readable_report_ids=readable)
            results.append("won")
        except ConfigConflict:
            results.append("conflict")
    assert results == ["won", "conflict"]
    assert svc.get_visible(owner, view["id"], readable)["revision"] == 2


def test_creating_the_same_configuration_twice_is_idempotent_and_a_name_clash_is_a_conflict(world):
    name = f"idem {uuid.uuid4().hex[:6]}"
    a = create_saved(world, name=name)
    b = create_saved(world, name=name)
    assert (a.status_code, b.status_code) == (201, 200) and a.json()["id"] == b.json()["id"]
    c = create_saved(world, name=name, definition=definition_dict(group_by="model"))
    assert c.status_code == 409
    other = create_saved(world, "operations_admin", name=name)                                             # names are per owner
    assert other.status_code == 201 and other.json()["id"] != a.json()["id"]


def test_the_count_per_owner_is_bounded(world):
    ck, uid = world.make("operations_admin")
    for i in range(MAX_CONFIGS_PER_OWNER):
        r = world.c.post(f"{API}/saved", json={"name": f"bound {i:02d}", "definition": definition_dict(), "shared": False}, cookies=ck)
        assert r.status_code == 201, r.text
    over = world.c.post(f"{API}/saved", json={"name": "bound over", "definition": definition_dict(), "shared": False}, cookies=ck)
    assert over.status_code == 409 and "at most" in over.json()["error"]["message"]
    assert world.c.get(f"{API}/saved", cookies=ck).json()["max_saved"] == MAX_CONFIGS_PER_OWNER


def test_invalid_and_unreadable_definitions_cannot_be_saved_and_nothing_is_stored(world):
    before = n_rows(world, ReportConfiguration)
    bad = [
        {"name": "bad window", "definition": definition_dict(window="all_time"), "shared": False},
        {"name": "bad metric", "definition": definition_dict(metric_ids=["nope"]), "shared": False},
        {"name": "bad name; DROP", "definition": definition_dict(), "shared": False},
        {"name": "extra field", "definition": definition_dict(), "shared": False, "owner_user_id": 1},
        {"name": "extra def field", "definition": {**definition_dict(), "sql": "x"}, "shared": False},
        {"name": "str shared", "definition": definition_dict(), "shared": "yes"},
    ]
    for body in bad:
        assert world.c.post(f"{API}/saved", json=body, cookies=world.cookies["platform_admin"]).status_code == 422, body["name"]
    assert world.c.post(f"{CAPI}/saved", json={"name": "unreadable", "definition": definition_dict(), "shared": False}, cookies=world.cookies["billing_admin"]).status_code == 403
    assert n_rows(world, ReportConfiguration) == before


def test_a_stored_definition_is_revalidated_when_it_is_run(world):
    sid = create_saved(world).json()["id"]
    with world.sf() as s:
        s.execute(text("UPDATE report_configurations SET definition_json = :d WHERE id = :i"),
                  {"d": json.dumps({"report_id": "ai_economics", "metric_ids": ["ai_usage"], "window": "all_time"}), "i": sid})
        s.commit()
    r = world.get(f"/saved/{sid}/preview")
    assert r.status_code == 422 and "[window_too_wide]" in r.text
    with world.sf() as s:
        s.execute(text("UPDATE report_configurations SET definition_json = :d WHERE id = :i"), {"d": json.dumps({"report_id": "ai_economics", "metric_ids": ["users.email"]}), "i": sid})
        s.commit()
    assert world.get(f"/saved/{sid}/preview").status_code == 422
    assert world.c.post(f"{API}/export", json={"format": "csv", "saved_id": sid}, cookies=world.cookies["platform_admin"]).status_code == 422


# ================================================================================================================ exports
def export(w, persona="platform_admin", base=API, **body):
    return w.c.post(f"{base}/export", json=body, cookies=w.cookies[persona])


def test_csv_export_equals_the_preview_and_is_bounded_and_safe(world):
    d = definition_dict(group_by="workflow")
    pv = world.preview(report_id="ai_economics", metric_ids=["ai_usage", "ai_known_cost"], window="30d", group_by="workflow").json()
    r = export(world, format="csv", definition={**d, "metric_ids": ["ai_usage", "ai_known_cost"]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    cd = r.headers["content-disposition"]
    assert re.fullmatch(r'attachment; filename="ask4mo-ai_economics-30d-\d{8}\.csv"', cd) and r.headers["cache-control"] == "no-store"
    rows = list(csv.reader(io.StringIO(r.text)))
    assert tuple(rows[0]) == RB.EXPORT_COLUMNS
    data = [dict(zip(rows[0], x)) for x in rows[1:]]
    expected = {(m["metric_id"], b["label"]): b for m in pv["metrics"] for b in m["buckets"]}
    assert len(data) == len(expected) == int(r.headers["x-export-rows"])
    for row in data:
        b = expected[(row["metric_id"], row["group_value"])]
        assert row["state"] == b["state"] and row["value"] == ("" if b["value"] is None else str(b["value"]))
    assert {row["report_id"] for row in data} == {"ai_economics"}


def test_json_export_has_the_same_rows(world):
    r = export(world, format="json", definition=definition_dict(group_by="workflow"))
    body = r.json()
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json") and r.headers["content-disposition"].endswith('.json"')
    assert body["columns"] == list(RB.EXPORT_COLUMNS) and {x["group_value"] for x in body["rows"]} == {"agent", "practice"}
    assert next(x for x in body["rows"] if x["group_value"] == "agent")["value"] == 840


def test_exports_are_formula_injection_safe_end_to_end(world):
    r = export(world, format="csv", definition={"report_id": "quality", "metric_ids": ["request_outcomes"], "window": "30d", "group_by": "operation"})
    assert r.status_code == 200
    cells = [c for row in csv.reader(io.StringIO(r.text)) for c in row]
    for evil in ("=SUM(1+1)", "+cmd", "-cmd", "@cmd"):
        assert "'" + evil in cells and evil not in cells, evil
    assert not [c for c in cells if c and c[0] in "=+-@\t\r"]                                              # no cell can open as a formula
    assert "GET /alpha" in cells


@pytest.mark.parametrize("raw,safe", [("=1+1", "'=1+1"), ("+1", "'+1"), ("-1", "'-1"), ("@SUM(A1)", "'@SUM(A1)"), ("\t=1", "'\t=1"), ("\r=1", "' =1"), ("\n=1", "' =1"), ("  =1", "'  =1"),
                                      ("plain", "plain"), ("a=b", "a=b"), ("", ""), (None, ""), ("x\x00y\x1fz", "xyz"), ("line1\nline2", "line1 line2")])
def test_csv_safe_neutralises_leading_formula_characters(raw, safe):
    assert RB.csv_safe(raw) == safe


def test_csv_safe_does_not_alter_numbers_or_booleans():
    assert RB.csv_safe(-5) == "-5" and RB.csv_safe(1.5) == "1.5" and RB.csv_safe(True) == "true" and RB.csv_safe(0) == "0"
    out = "".join(RB.render_csv([{c: ("=evil" if c == "metric_label" else None) for c in RB.EXPORT_COLUMNS}]))
    assert "'=evil" in out and out.count("\r\n") == 2


def test_the_export_filename_comes_only_from_registry_values():
    now = datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert RB.export_filename("product", "30d", "csv", now) == "ask4mo-product-30d-20261022.csv"
    for args in (("../x", "30d", "csv"), ("product", "30d; rm", "csv"), ("product", "30d", "exe"), ("Product", "30d", "csv"), ('a"b', "30d", "csv")):
        with pytest.raises(ValueError):
            RB.export_filename(*args, now)


def test_every_export_is_audited_without_data_and_before_sending(world):
    with world.sf() as s:
        already = s.scalar(select(func.max(AuditEvent.id)).where(AuditEvent.event_type == "admin.report_exported")) or 0       # audit_events is append-only: count from here
    r = export(world, format="csv", definition=definition_dict(group_by="workflow"))
    sid = create_saved(world, definition=definition_dict(group_by="model")).json()["id"]
    r2 = export(world, format="json", saved_id=sid)
    assert r.status_code == r2.status_code == 200
    with world.sf() as s:
        rows = s.scalars(select(AuditEvent).where(AuditEvent.event_type == "admin.report_exported", AuditEvent.id > already).order_by(AuditEvent.id)).all()
    assert len(rows) == 2 and all(x.actor_user_id == world.uids["platform_admin"] and x.target_id == "ai_economics" and x.result == "success" for x in rows)
    c0, c1 = rows[0].context, rows[1].context
    assert c0["report_id"] == "ai_economics" and c0["window"] == "30d" and c0["format"] == "csv" and c0["row_count"] == 2 and c0["source"] == "inline"
    assert c1["format"] == "json" and c1["source"] == "saved" and c1["config_id"] == sid and c1["grouped_by"] == "model"
    dump = json.dumps([c0, c1])
    for needle in ("840", "agent", "practice", "model/terra", "sentinel", "@"):
        assert needle not in dump                                                                           # who / report / window / count only, no data


def _assert_audit_failure_response(response, *, export_events_before: int, export_events_after: int) -> None:
    """The correlation UUID is opaque metadata; everything else must be a fixed safe error."""
    assert response.status_code == 503
    assert response.headers["content-type"].split(";", 1)[0].lower() == "application/json"
    assert "content-disposition" not in response.headers
    assert "x-export-rows" not in response.headers
    body = response.json()
    assert isinstance(body, dict) and set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict) and set(error) == {"code", "message", "request_id"}
    assert error["code"] == "http_error"
    assert error["message"] == "The export could not be audited, so nothing was exported."
    request_id = error["request_id"]
    assert isinstance(request_id, str) and re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert uuid.UUID(hex=request_id).version == 4
    assert response.headers["x-request-id"] == request_id
    # Remove exactly the validated opaque identifier, not arbitrary response data.
    assert response.text.count(request_id) == 1
    non_identifier_text = response.text.replace(request_id, "", 1)
    non_identifier_headers = json.dumps({key: value for key, value in response.headers.items() if key.lower() != "x-request-id"})
    for forbidden in ("agent", "metric_id", "840"):
        assert forbidden not in non_identifier_text
        assert forbidden not in non_identifier_headers
    assert export_events_after == export_events_before


def _export_audit_event_count(world) -> int:
    with world.sf() as session:
        return session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "admin.report_exported"))


def test_an_export_that_cannot_be_audited_is_not_sent(world, monkeypatch):
    from src.auth_repository import AuditRepository

    def boom(self, **kw):
        raise RuntimeError("audit down")
    monkeypatch.setattr(AuditRepository, "record", boom)
    before = _export_audit_event_count(world)
    r = export(world, format="csv", definition=definition_dict(group_by="workflow"))
    _assert_audit_failure_response(r, export_events_before=before, export_events_after=_export_audit_event_count(world))


def test_audit_failure_response_allows_uuid_containing_report_value(world, monkeypatch):
    from src.auth_repository import AuditRepository

    def boom(self, **kw):
        raise RuntimeError("audit down")
    monkeypatch.setattr(AuditRepository, "record", boom)
    # UUID v4, deliberately containing the synthetic report value that formerly collided.
    monkeypatch.setattr("src.api.middleware.uuid.uuid4", lambda: uuid.UUID("08400000-0000-4000-8000-000000000000"))
    before = _export_audit_event_count(world)
    response = export(world, format="csv", definition=definition_dict(group_by="workflow"))
    assert "840" in response.json()["error"]["request_id"]
    _assert_audit_failure_response(response, export_events_before=before, export_events_after=_export_audit_event_count(world))


@pytest.mark.parametrize("mutation", ["report_value", "business_field", "outside_field", "invalid_id", "mismatched_id", "attachment", "export_rows", "header_leak", "audit_committed"])
def test_audit_failure_response_rejects_leaks_and_invalid_metadata(mutation):
    import httpx

    request_id = "08400000000040008000000000000000"
    body = {"error": {"code": "http_error", "message": "The export could not be audited, so nothing was exported.", "request_id": request_id}}
    headers = {"x-request-id": request_id}
    after = 0
    if mutation == "report_value":
        body["error"]["message"] += " 840"
    elif mutation == "business_field":
        body["error"]["metric_id"] = "agent"
    elif mutation == "outside_field":
        body["rows"] = [{"value": "840"}]
    elif mutation == "invalid_id":
        body["error"]["request_id"] = "invalid"
    elif mutation == "mismatched_id":
        headers["x-request-id"] = "12345678901240008000000000000000"
    elif mutation == "attachment":
        headers["content-disposition"] = "attachment; filename=report.csv"
    elif mutation == "export_rows":
        headers["x-export-rows"] = "1"
    elif mutation == "header_leak":
        headers["x-unexpected"] = "agent"
    else:
        after = 1
    response = httpx.Response(503, json=body, headers=headers)
    with pytest.raises(AssertionError):
        _assert_audit_failure_response(response, export_events_before=0, export_events_after=after)


def test_commercial_exports_need_the_commercial_permission(world):
    d = {"report_id": "commercial", "metric_ids": ["access_plans"], "window": "30d", "group_by": "plan"}
    assert export(world, "operations_admin", CAPI, format="csv", definition=d).status_code == 403
    assert export(world, "operations_admin", API, format="csv", definition=d).status_code == 403
    assert export(world, "user", CAPI, format="csv", definition=d).status_code == 403
    assert export(world, "billing_admin", API, format="csv", definition=d).status_code == 403
    ok = export(world, "billing_admin", CAPI, format="csv", definition=d)
    assert ok.status_code == 200 and "basic" in ok.text and "6" in ok.text
    assert export(world, "platform_admin", CAPI, format="json", definition=d).status_code == 200
    money = export(world, "billing_admin", CAPI, format="csv", definition={"report_id": "commercial", "metric_ids": ["mock_mrr"], "window": "30d", "group_by": "currency"})
    rows = [dict(zip(RB.EXPORT_COLUMNS, x)) for x in list(csv.reader(io.StringIO(money.text)))[1:]]
    assert {(x["group_value"], x["value"]) for x in rows} == {("EUR", str(6 * 19.99)), ("USD", "150.0")}       # one row per currency, never summed
    sid = create_saved(world, "platform_admin", base=CAPI, definition=d, shared=True).json()["id"]
    assert export(world, "operations_admin", CAPI, format="csv", saved_id=sid).status_code == 403
    assert export(world, "operations_admin", API, format="csv", saved_id=sid).status_code == 404
    assert export(world, "billing_admin", CAPI, format="csv", saved_id=sid).status_code == 200


def test_export_request_shape_and_row_bound(world):
    assert export(world, format="csv").status_code == 422                                                   # neither definition nor saved id
    assert export(world, format="csv", definition=definition_dict(), saved_id=1).status_code == 422         # both
    assert export(world, format="xlsx", definition=definition_dict()).status_code == 422
    assert export(world, format="csv", saved_id=987654).status_code == 404
    assert export(world, format="csv", definition=definition_dict(window="all_time")).status_code == 422
    assert export(world, format="csv", definition=definition_dict(), email="a@b.c").status_code == 422
    with pytest.raises(RB.ReportInvalid):
        RB.check_export_size([{}] * (RB.MAX_EXPORT_ROWS + 1))
    RB.check_export_size([{}] * RB.MAX_EXPORT_ROWS)


def test_exports_carry_no_candidate_identifiers(world):
    outs = [export(world, format=f, definition=d) for f in ("csv", "json") for d in (
        definition_dict(group_by="workflow"), {"report_id": "quality", "metric_ids": ["feedback", "request_outcomes"], "window": "90d"},
        {"report_id": "product", "metric_ids": ["registrations", "onboarding_completed", "activation", "returning"], "window": "7d"})]
    for r in outs:
        assert r.status_code == 200
        low = r.text.lower()
        for needle in ("example.test", "sentinel-", "@", PW):
            assert needle.lower() not in low
        for uid in world.seeded["cands"]:
            assert not re.search(rf"\buser_id\b|\b{uid}\b.*user", low)
    assert not [c for c in RB.EXPORT_COLUMNS if re.search(r"user|email|candidate|subject|owner|session|token|name$", c)]


# ================================================================================================================ privacy and schema
def test_responses_carry_no_banned_fields_identifiers_or_sentinel_values(world):
    saved = create_saved(world, shared=True).json()
    calls = [world.get("/registry"), world.get("/validate", report_id="ai_economics", metric_ids=["ai_usage"]), world.get("/saved"), world.get(f"/saved/{saved['id']}"),
             world.preview(report_id="quality", metric_ids=["feedback", "request_outcomes", "evaluation_score"], window="90d"),
             world.preview(report_id="ai_economics", metric_ids=["ai_usage", "ai_known_cost"], window="7d", group_by="model"),
             world.preview(report_id="product", metric_ids=["registrations", "onboarding_rate", "activation", "returning", "practice_started"], window="30d"),
             world.get(f"/saved/{saved['id']}/preview"), world.get("/registry", "billing_admin", CAPI),
             world.preview("billing_admin", CAPI, report_id="commercial", metric_ids=["mock_failed_payments", "access_plans"], window="30d")]
    for r in calls:
        assert r.status_code == 200, r.text[:200]
        assert banned_key_hits(r.json()) == [], banned_key_hits(r.json())
        for needle in ("example.test", "sentinel-", "@", PW, "cookie"):
            assert needle.lower() not in r.text.lower()
        assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", r.text)
    assert banned_key_hits({"owner_user_id": 1, "client_ip": 2, "user_email": 3}) == ["$.owner_user_id", "$.client_ip", "$.user_email"]


def test_response_and_request_schemas_are_allowlists():
    def walk(model, seen=None):
        seen = seen or set()
        if model in seen:
            return
        seen.add(model)
        if issubclass(model, SCH.BaseModel):
            if model.__module__ in (SCH.__name__, RB.__name__):
                assert model.model_config.get("extra") == "forbid", model.__name__
            for f in model.model_fields.values():
                assert "dict" not in str(f.annotation).lower() and "Any" not in str(f.annotation), (model.__name__, f.annotation)
    for name in ("RegistryResponse", "ValidateResponse", "PreviewResponse", "SavedOut", "SavedList", "SavedWrite", "ExportRequest", "BucketOut", "PreviewMetricOut"):
        walk(getattr(SCH, name))
    walk(RB.BuilderDefinition)
    with pytest.raises(ValidationError):
        SCH.PreviewMetricOut(metric_id="x", label="x", unit="count", period="30d", coverage="", suppression="cohort", state="ok", value=1, partial=False, note="",
                             group_dimension=None, buckets=None, user_id=1)
    with pytest.raises(ValidationError):
        SCH.SavedOut(id=1, name="n", report_id="r", definition=RB.parse_definition(definition_dict()), shared=False, revision=1, editable=True, valid=True, created_at=None, updated_at=None,
                     owner_user_id=3)
    fields = {f for n in ("PreviewMetricOut", "PreviewResponse", "SavedOut", "BucketOut", "RegistryResponse") for f in getattr(SCH, n).model_fields}
    assert not {"user_id", "owner_user_id", "email", "content", "path", "secret", "token", "ip", "prompt", "comment", "subject", "numerator", "denominator", "cohort"} & fields


def test_the_builder_reads_no_private_content_and_the_get_routes_are_read_only():
    code = (ROOT / "src/reporting/report_builder.py").read_text().split('"""', 2)[2]
    for banned in ("Answer.", "CandidateDocument", "PreparationMemory", "SupportMessage", "SupportInternalNote", "UserFeedback.comment", "state_payload", "payload_json", "User.email",
                   "User.subject", "AuditEvent", "text(", "exec(", "eval(", "f\"SELECT", "execute(\""):
        assert banned not in code, banned
    assert not re.search(r"^\s*(import|from)\s+(requests|httpx|urllib|openai|langchain|subprocess)\b", code, re.M) and "enqueue" not in code and ".add(" not in code and "commit(" not in code
    for r in _builder_routes():
        if r.methods == ("GET",):
            import inspect

            assert not re.search(r"\.(add|delete|commit)\(|\.enqueue\(|build_audit\(|audit_repo", inspect.getsource(r.route.endpoint)), r.path


def test_reads_change_nothing_and_make_no_network_or_provider_call(world, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(socket.socket, "connect", no_net)
    sid = create_saved(world).json()["id"]
    counts = lambda: (n_rows(world, ReportConfiguration), n_rows(world, AuditEvent), n_rows(world, AIUsageFact), n_rows(world, UserFeedback), n_rows(world, User))      # noqa: E731
    before = counts()
    for call in (lambda: world.get("/registry"), lambda: world.get("/saved"), lambda: world.get(f"/saved/{sid}"), lambda: world.get(f"/saved/{sid}/preview"),
                 lambda: world.get("/validate", report_id="ai_economics", metric_ids=["ai_usage"]),
                 lambda: world.preview(report_id="quality", metric_ids=["feedback", "evaluation_score", "retrieval_outcomes", "provider_calls"], window="90d")):
        assert call().status_code == 200
    after = counts()
    assert after[0] == before[0] and after[2:] == before[2:]
    assert after[1] == before[1]                                                                               # a successful GET writes no audit row


def test_only_the_documented_methods_exist(world):
    for path in ("/registry", "/preview", "/validate", "/saved/1/preview"):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(world.c, method)(f"{API}{path}", cookies=world.cookies["platform_admin"]).status_code == 405, (path, method)
    for path in ("/export", "/saved"):
        for method in ("patch",):
            assert getattr(world.c, method)(f"{API}{path}", cookies=world.cookies["platform_admin"]).status_code == 405
    for path in ("/sql", "/raw", "/tables", "/candidates", "/events", "/query", "/results", "/saved/1/results"):
        assert world.get(path).status_code in (404, 405), path


def test_the_audit_vocabulary_includes_only_the_new_events_and_registry_is_unchanged():
    from src.application import admin_audit as A

    new = {A.ADMIN_REPORT_CONFIG_CREATED, A.ADMIN_REPORT_CONFIG_UPDATED, A.ADMIN_REPORT_CONFIG_DELETED, A.ADMIN_REPORT_EXPORTED}
    assert new <= A.ADMIN_EVENT_NAMES and len(new) == 4
    with pytest.raises(ValueError):
        A.build_audit(event_type=A.ADMIN_REPORT_EXPORTED, actor_user_id=1, request_id=None, candidate_answer="x")
    assert len(perm.PERMISSIONS) == 44


# ================================================================================================================ migration
def _alembic(tmp_path, monkeypatch):
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'rb.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def test_migration_adds_the_table_additively_and_the_downgrade_is_fail_closed(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    cfg, url = _alembic(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(cfg)
    mine = next(r for r in script.walk_revisions() if "report_configurations" in r.revision)
    assert len(script.get_heads()) == 1                                                                  # no second head
    assert script.get_revision(mine.down_revision) is not None
    command.upgrade(cfg, mine.revision)
    eng = create_engine(url)
    insp = inspect(eng)
    assert "report_configurations" in insp.get_table_names()
    migrated = {c["name"] for c in insp.get_columns("report_configurations")}
    assert migrated == {c.name for c in ReportConfiguration.__table__.columns}                            # ORM and migration agree
    assert ("owner_user_id", "name") in {tuple(u["column_names"]) for u in insp.get_unique_constraints("report_configurations")}
    assert any(fk["referred_table"] == "users" and fk["options"].get("ondelete") == "CASCADE" for fk in insp.get_foreign_keys("report_configurations"))
    with eng.begin() as c:
        c.execute(text("insert into users (subject, provider, email, platform_role, status, created_at, updated_at) values ('s','t','e@x.test','platform_admin','active','2026-01-01','2026-01-01')"))
        uid = c.execute(text("select id from users")).scalar()
        c.execute(text("insert into report_configurations (owner_user_id, name, report_id, definition_json, definition_hash, shared, revision, created_at, updated_at) "
                       "values (:u, 'keep me', 'product', '{}', :h, 0, 1, '2026-01-01', '2026-01-01')"), {"u": uid, "h": "a" * 64})
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(text("insert into report_configurations (owner_user_id, name, report_id, definition_json, definition_hash, shared, revision, created_at, updated_at) "
                           "values (:u, 'keep me', 'product', '{}', :h, 0, 1, '2026-01-01', '2026-01-01')"), {"u": uid, "h": "a" * 64})          # unique per owner
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(text("insert into report_configurations (owner_user_id, name, report_id, definition_json, definition_hash, shared, revision, created_at, updated_at) "
                           "values (:u, 'bad rev', 'product', '{}', :h, 0, 0, '2026-01-01', '2026-01-01')"), {"u": uid, "h": "a" * 64})
    with pytest.raises(RuntimeError, match="Refusing to downgrade 0041_report_configurations"):
        command.downgrade(cfg, mine.down_revision)
    with eng.connect() as c:
        assert c.execute(text("select count(*) from report_configurations")).scalar() == 1                # nothing was deleted
        assert c.execute(text("select version_num from alembic_version")).scalar() == mine.revision
    with eng.begin() as c:
        c.execute(text("delete from report_configurations"))
    command.downgrade(cfg, mine.down_revision)
    assert "report_configurations" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, mine.revision)                                                                   # and it re-applies
    assert "report_configurations" in inspect(create_engine(url)).get_table_names()


def test_the_migration_touches_only_its_own_table_and_deleting_the_owner_cascades(tmp_path):
    src = next((ROOT / "migrations/versions").glob("0*_report_configurations.py")).read_text()
    assert re.findall(r'op\.(?:create_table|drop_table|add_column|alter_column|create_index|drop_index)\(\s*"([a-z_]+)"', src) and set(
        re.findall(r'op\.(?:create_table|drop_table|add_column|alter_column)\(\s*"([a-z_]+)"', src)) == {"report_configurations"}
    assert "ON DELETE" not in src and 'ondelete="CASCADE"' in src
    fk = next(iter(ReportConfiguration.__table__.c.owner_user_id.foreign_keys))
    assert fk.ondelete == "CASCADE" and fk.column.table.name == "users"


def test_account_deletion_removes_the_admins_saved_configurations(world):
    ck, uid = world.make("operations_admin")
    assert world.c.post(f"{API}/saved", json={"name": "to be erased", "definition": definition_dict(), "shared": True}, cookies=ck).status_code == 201
    assert n_rows_for(world, uid) == 1
    with world.sf() as s:
        s.execute(text("PRAGMA foreign_keys=ON"))
        s.execute(text("DELETE FROM users WHERE id = :i"), {"i": uid})
        s.commit()
    assert n_rows_for(world, uid) == 0


def n_rows_for(w, uid: int) -> int:
    with w.sf() as s:
        return int(s.scalar(select(func.count()).select_from(ReportConfiguration).where(ReportConfiguration.owner_user_id == uid)) or 0)


def test_the_privacy_schema_invariant_allows_a_foreign_key_reference_but_still_catches_every_mutation(tmp_path):
    """03E1 refined scripts/eval_privacy_controls.migration_tables_touched: a ForeignKey target ("users.id") of a NEW table is a reference, not a change."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("eval_privacy_controls_03e1", ROOT / "scripts/eval_privacy_controls.py")
    EV = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(EV)
    from src.persistence import Base

    known = set(Base.metadata.tables)
    mine = next((ROOT / "migrations/versions").glob("0*_report_configurations.py")).read_text()
    assert EV.migration_tables_touched(mine, known) == {"report_configurations"}
    head = "import sqlalchemy as sa\nfrom alembic import op\n"
    for body in ('def upgrade():\n    op.add_column("users", sa.Column("x", sa.Text()))\n',
                 'def upgrade():\n    op.execute("UPDATE users SET status = 1")\n',
                 'def upgrade():\n    op.drop_table("users")\n',
                 'def upgrade():\n    op.create_foreign_key("fk", "report_configurations", "users", ["a"], ["id"])\n',
                 'def upgrade():\n    op.create_table("t", sa.Column("a", sa.Integer()), sa.ForeignKeyConstraint(["a"], ["x.id"]))\n    op.alter_column("answers", "a")\n'):
        assert EV.migration_tables_touched(head + body, known) & EV.PRIVACY_TABLES, body
    ok = head + 'def upgrade():\n    op.create_table("t", sa.Column("a", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")), sa.ForeignKeyConstraint(["a"], ["interviews.id"]))\n'
    assert not EV.migration_tables_touched(ok, known) & EV.PRIVACY_TABLES


def test_builder_windows_cannot_be_subtracted_into_a_small_group_05e():
    """05E (PRIV-DIFF) through the real builder route: 6 candidates registered inside 7d and 3 more only inside 30d. The wider window must not expose the group of 3.
    Full attack matrix and residual risk: tests/test_differencing_05e.py."""
    w = World()
    try:
        w.candidates(6)
        with w.sf() as s:
            for i in range(3):
                t = NOW - 20 * DAY
                tag = uuid.uuid4().hex[:6]
                s.add(User(subject=f"old{i}-{tag}", provider="test", email=f"old{i}-{tag}@example.test", platform_role="user", status="active", created_at=t, updated_at=t))
            s.commit()
        seven = w.preview(report_id="product", metric_ids="registrations", window="7d").json()["metrics"][0]
        thirty = w.preview(report_id="product", metric_ids="registrations", window="30d").json()["metrics"][0]
        assert seven["state"] == "ok" and seven["value"] >= REPORTING_MIN_COHORT           # (the World also holds one candidate persona: the figure is the registrations of the window)
        assert thirty["value"] is None and thirty["state"] == "suppressed"
    finally:
        w.close()
