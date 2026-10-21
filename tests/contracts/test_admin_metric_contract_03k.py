"""03K conformance suite: the Admin metric and report contract that 03D1 (dashboard backend) and 03E1 (report backend) must pass.

Consumers re-run this file against their own registry by replacing ``REGISTRY`` (see ``registry_under_test``) and keep the rule tests unchanged.
Offline and deterministic: no database, provider or network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.api.schemas.admin_metric_contract import contract_json_schema
from src.application import admin_permissions as perm
from src.reporting import contract as K
from src.reporting import suppression as S
from src.reporting.definitions import METRICS, REPORTING_MIN_COHORT
from src.reporting.service import ReportingService

ROOT = Path(__file__).resolve().parents[2]


def registry_under_test():
    """03D1/03E1: return (metrics, dimensions, reports) of YOUR registry here; the default is the adapted existing registry."""
    return K.default_registry()


def _metric(**over) -> dict:
    base = dict(
        metric_id="registrations", label="Registrations", description="Candidate accounts created in the period.",
        source={"kind": "fact_table", "name": "users"}, numerator={"aggregation": "count_distinct", "subject": "candidate_accounts"}, denominator=None,
        unit="count", period_kinds=["7d", "30d"], dimensions_allowed=["plan"], coverage={"kind": "historical", "note": "Historical"},
        missing_behaviour="unavailable", suppression={"kind": "cohort", "min_cohort": REPORTING_MIN_COHORT}, permission_required=perm.REPORTS_READ)
    base.update(over)
    return base


def _dim(i="plan", kind="category"):
    return K.DimensionDefinition(dimension_id=i, label=i.title(), description="A dimension.", kind=kind)


def _report(**over) -> dict:
    base = dict(report_id="r1", title="R", description="A report.", metric_ids=["registrations"],
                date_range={"allowed_periods": ["30d"], "default_period": "30d"}, permission_required=perm.REPORTS_READ)
    base.update(over)
    return base


# ------------------------------------------------------------------------------------------------------------- registry as shipped
def test_default_registry_is_valid_and_maps_every_existing_metric():
    metrics, dims, reports = registry_under_test()
    K.validate_registry(metrics, dims, reports)
    assert [m.metric_id for m in metrics][: len(METRICS)] == [m.metric_id for m in METRICS]


def test_existing_values_are_not_changed_by_the_adapter():
    """The contract is an additive view: the legacy definitions payload is exactly what it was."""
    payload = ReportingService(session_factory=None).definitions()
    assert [m["metric_id"] for m in payload["metrics"]] == [m.metric_id for m in METRICS]
    for legacy, m in zip(payload["metrics"], METRICS):
        assert legacy == {"metric_id": m.metric_id, "label": m.label, "source": m.source, "definition": m.definition, "cohort_policy": m.cohort_policy,
                          "coverage": m.coverage}
    for cm, m in zip(K.contract_metrics(), METRICS):          # the adapter carries the legacy wording verbatim and a cohort policy equal to the legacy one
        assert (cm.label, cm.description, cm.coverage.note) == (m.label, m.definition, m.coverage)
        assert (cm.suppression.kind == "operational") == (m.cohort_policy == "operational")


def test_no_source_text_or_column_name_leaks_into_the_contract():
    for m in K.contract_metrics():
        blob = json.dumps(m.model_dump())
        for legacy in METRICS:
            if legacy.metric_id == m.metric_id and ("." in legacy.source or "(" in legacy.source):    # legacy prose names columns; the contract must not carry it
                assert legacy.source not in blob
        assert "." not in m.source.name and "." not in m.numerator.subject


def test_cohort_floor_is_the_engineering_privacy_floor():
    for m in K.contract_metrics():
        if m.suppression.kind == "cohort":
            assert m.suppression.min_cohort >= REPORTING_MIN_COHORT


def test_commercial_metrics_need_the_commercial_permission_and_registry_stays_44():
    by = {m.metric_id: m for m in K.contract_metrics()}
    for mid in ("mock_mrr", "mock_arr", "access_plans", "mock_failed_payments"):
        assert by[mid].permission_required == perm.REPORTS_COMMERCIAL
    assert len(perm.PERMISSIONS) == 44
    for r in K.contract_reports():
        assert r.permission_required in perm.PERMISSION_SET


# ----------------------------------------------------------------------------------------------------------- negative: SQL and names
@pytest.mark.parametrize("bad", [
    "x; DROP TABLE users", "SELECT * FROM users WHERE id = 1", "1 OR 1=1", "a -- comment", "/* c */", "users.password_hash = 'x'",
    "UNION SELECT email", "select email from users",
])
def test_sql_like_text_is_rejected_in_every_free_text_field(bad):
    for field in ("label", "description"):
        with pytest.raises(ValidationError):
            K.MetricDefinition(**_metric(**{field: bad}))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(coverage={"kind": "historical", "note": bad}))
    with pytest.raises(ValidationError):
        K.ReportDefinition(**_report(description=bad))


@pytest.mark.parametrize("bad", ["users.email", "u;drop", "Users", "a b", "x'--", "", "1abc", "a" * 70])
def test_slugs_cannot_carry_column_names_or_expressions(bad):
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(numerator={"aggregation": "count", "subject": bad}))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(metric_id=bad))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(dimensions_allowed=[bad]))


def test_unregistered_fact_table_and_free_form_aggregation_are_rejected():
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(source={"kind": "fact_table", "name": "pg_shadow"}))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(source={"kind": "sql", "name": "users"}))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(numerator={"aggregation": "sum(users.salary)", "subject": "x"}))


def test_extra_fields_are_forbidden_so_no_query_field_can_be_smuggled():
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(sql="select 1"))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(source={"kind": "fact_table", "name": "users", "query": "select 1"}))
    with pytest.raises(ValidationError):
        K.MetricResult(metric_id="a", period="30d", state="ok", value=1, row_ids=[1])


def test_strict_types_no_coercion():
    with pytest.raises(ValidationError):
        K.MetricResult(metric_id="a", period="30d", state="ok", value=1, numerator="3")
    with pytest.raises(ValidationError):
        K.SuppressionPolicy(kind="cohort", min_cohort="5")


# ------------------------------------------------------------------------------------------------------------ definition rules
def test_unknown_permission_is_rejected():
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(permission_required="platform.nope.read"))


def test_cohort_minimum_cannot_be_lowered_and_operational_has_none():
    for floor in (0, 1, REPORTING_MIN_COHORT - 1, None):
        with pytest.raises(ValidationError):
            K.SuppressionPolicy(kind="cohort", min_cohort=floor)
    K.SuppressionPolicy(kind="cohort", min_cohort=REPORTING_MIN_COHORT + 5)
    with pytest.raises(ValidationError):
        K.SuppressionPolicy(kind="operational", min_cohort=5)


def test_missing_behaviour_is_never_zero():
    for bad in ("zero", "0", "empty", "default"):
        with pytest.raises(ValidationError):
            K.MetricDefinition(**_metric(missing_behaviour=bad))


def test_rate_needs_a_denominator_and_periods_are_the_fixed_set():
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(unit="percent"))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(period_kinds=["last_week"]))
    with pytest.raises(ValidationError):
        K.MetricDefinition(**_metric(period_kinds=["7d", "7d"]))


def test_date_range_rules():
    with pytest.raises(ValidationError):
        K.DateRangeRule(allowed_periods=["7d"], default_period="30d")
    with pytest.raises(ValidationError):
        K.DateRangeRule(allowed_periods=["7d"], default_period="7d", allow_custom_range=True)
    with pytest.raises(ValidationError):
        K.DateRangeRule(allowed_periods=["7d"], default_period="7d", max_custom_days=30)
    K.DateRangeRule(allowed_periods=["7d"], default_period="7d", allow_custom_range=True, max_custom_days=30)


# ---------------------------------------------------------------------------------------------------------------- registry rules
def test_duplicate_ids_are_rejected():
    m = K.MetricDefinition(**_metric())
    with pytest.raises(K.ContractError, match="duplicate metric id"):
        K.validate_registry([m, m], [_dim()])
    with pytest.raises(K.ContractError, match="duplicate dimension id"):
        K.validate_registry([m], [_dim(), _dim()])
    r = K.ReportDefinition(**_report())
    with pytest.raises(K.ContractError, match="duplicate report id"):
        K.validate_registry([m], [_dim()], [r, r])


def test_unknown_dimension_is_rejected():
    m = K.MetricDefinition(**_metric(dimensions_allowed=["nope"]))
    with pytest.raises(K.ContractError, match="unknown dimension 'nope'"):
        K.validate_registry([m], [_dim()])


def test_report_references_must_exist_and_filters_must_be_dimensions():
    m = K.MetricDefinition(**_metric())
    with pytest.raises(K.ContractError, match="unknown metric 'ghost'"):
        K.validate_registry([m], [_dim()], [K.ReportDefinition(**_report(metric_ids=["ghost"]))])
    with pytest.raises(K.ContractError, match="unknown filter dimension 'ghost'"):
        K.validate_registry([m], [_dim()], [K.ReportDefinition(**_report(allowed_filters=["ghost"]))])
    with pytest.raises(ValidationError):
        K.ReportDefinition(**_report(metric_ids=["registrations", "registrations"]))


def test_report_permission_must_match_its_metrics_and_periods_must_be_supported():
    m = K.MetricDefinition(**_metric(permission_required=perm.REPORTS_COMMERCIAL))
    with pytest.raises(K.ContractError, match="needs permission"):
        K.validate_registry([m], [_dim()], [K.ReportDefinition(**_report())])
    m2 = K.MetricDefinition(**_metric(period_kinds=["7d"]))
    with pytest.raises(K.ContractError, match="every allowed period"):
        K.validate_registry([m2], [_dim()], [K.ReportDefinition(**_report())])


def _chart(kind, metrics=("registrations",), dim=None):
    return {"chart_id": "c1", "kind": kind, "metric_ids": list(metrics), "dimension_id": dim, "title": "C"}


def _with_chart(chart, *metrics, dims=None):
    ms = list(metrics) or [K.MetricDefinition(**_metric())]
    return K.validate_registry(ms, dims or [_dim(), _dim("time", "time")],
                               [K.ReportDefinition(**_report(metric_ids=[m.metric_id for m in ms], charts=[chart]))])


def test_chart_kind_must_fit_the_metric_shape():
    count = K.MetricDefinition(**_metric(dimensions_allowed=["plan", "time"], period_kinds=["30d"]))
    count2 = K.MetricDefinition(**_metric(metric_id="b", dimensions_allowed=["plan"], period_kinds=["30d"]))
    rate = K.MetricDefinition(**_metric(metric_id="rate", unit="percent", denominator={"aggregation": "count", "subject": "x"},
                                        dimensions_allowed=["plan"], period_kinds=["30d"]))
    c = K.ChartSpec
    # valid shapes
    _with_chart(c(**_chart("trend", dim="time")), count)
    _with_chart(c(**_chart("share_of_whole", dim="plan")), count)
    _with_chart(c(**_chart("distribution", dim="plan")), count)
    _with_chart(c(**_chart("funnel", ("registrations", "b"))), count, count2)
    _with_chart(c(**_chart("table")), count)
    # incompatible shapes
    for bad, metrics in [(_chart("trend", dim="plan"), (count,)), (_chart("trend"), (count,)), (_chart("funnel"), (count,)),
                         (_chart("funnel", ("registrations", "rate")), (count, rate)), (_chart("share_of_whole", ("rate",), "plan"), (rate,)),
                         (_chart("share_of_whole", dim="time"), (count,)), (_chart("distribution"), (count,)),
                         (_chart("share_of_whole", dim="currency"), (count,))]:
        with pytest.raises(K.ContractError):
            _with_chart(c(**bad), *metrics, dims=[_dim(), _dim("time", "time"), _dim("currency")])


def test_chart_metric_must_belong_to_report():
    m, other = K.MetricDefinition(**_metric()), K.MetricDefinition(**_metric(metric_id="other"))
    r = K.ReportDefinition(**_report(charts=[_chart("table", ("other",))]))
    with pytest.raises(K.ContractError, match="not in the report"):
        K.validate_registry([m, other], [_dim()], [r])


# ---------------------------------------------------------------------------------------------------------- MetricResult / missing
def test_missing_is_never_a_bare_zero():
    for state in ("suppressed", "unavailable", "not_captured"):
        with pytest.raises(ValidationError):
            K.MetricResult(metric_id="a", period="30d", state=state, value=0)
        with pytest.raises(ValidationError):
            K.MetricResult(metric_id="a", period="30d", state=state, numerator=0)
        with pytest.raises(ValidationError):
            K.MetricResult(metric_id="a", period="30d", state=state, denominator=0)
        assert K.MetricResult(metric_id="a", period="30d", state=state).value is None
    with pytest.raises(ValidationError):
        K.MetricResult(metric_id="a", period="30d", state="ok")                      # ok needs a value
    assert K.MetricResult(metric_id="a", period="30d", state="ok", value=0).value == 0   # a real zero is allowed ONLY as ok
    with pytest.raises(ValidationError):
        K.MetricResult(metric_id="a", period="30d", state="unavailable", partial=True)


def test_build_result_missing_follows_the_definition():
    for behaviour in ("unavailable", "not_captured"):
        d = K.MetricDefinition(**_metric(missing_behaviour=behaviour))
        r = K.build_result(d, "30d", None, cohort=100)
        assert r.state == behaviour and r.value is None


def test_build_result_suppresses_small_cohorts_without_leaking():
    d = K.MetricDefinition(**_metric())
    for cohort in (None, 0, 1, REPORTING_MIN_COHORT - 1):
        r = K.build_result(d, "30d", 3, cohort=cohort, numerator=3, denominator=4)
        assert r.state == "suppressed" and r.value is None and r.numerator is None and r.denominator is None
        assert "3" not in json.dumps(r.model_dump()).replace('"30d"', "")
    ok = K.build_result(d, "30d", 12, cohort=REPORTING_MIN_COHORT, numerator=12)
    assert ok.state == "ok" and ok.value == 12


def test_operational_metrics_are_not_cohort_suppressed_and_cannot_be_reported_suppressed():
    d = K.MetricDefinition(**_metric(suppression={"kind": "operational"}))
    assert K.build_result(d, "30d", 2).state == "ok"
    with pytest.raises(K.ContractError):
        K.check_result(K.MetricResult(metric_id=d.metric_id, period="30d", state="suppressed"), d)


def test_check_result_enforces_definition():
    d = K.MetricDefinition(**_metric(missing_behaviour="not_captured", period_kinds=["30d"]))
    K.check_result(K.MetricResult(metric_id=d.metric_id, period="30d", state="not_captured"), d)
    with pytest.raises(K.ContractError, match="not_captured"):
        K.check_result(K.MetricResult(metric_id=d.metric_id, period="30d", state="unavailable"), d)
    with pytest.raises(K.ContractError, match="not supported"):
        K.check_result(K.MetricResult(metric_id=d.metric_id, period="7d", state="ok", value=1), d)
    with pytest.raises(K.ContractError, match="mismatch"):
        K.check_result(K.MetricResult(metric_id="other", period="30d", state="ok", value=1), d)


def test_legacy_metric_dicts_adapt_without_changing_figures():
    ok = K.result_from_legacy(S.metric("registrations", "R", 12, cohort=9), "30d")
    assert ok.state == "ok" and ok.value == 12 and not ok.partial
    part = K.result_from_legacy(S.metric("registrations", "R", 12, cohort=9, partial=True), "30d")
    assert part.state == "ok" and part.partial and part.value == 12
    sup = K.result_from_legacy(S.metric("registrations", "R", 3, cohort=3), "30d")
    assert sup.state == "suppressed" and sup.value is None
    assert K.result_from_legacy(S.unavailable("mock_mrr", "M", "n"), "30d").state == "unavailable"
    assert K.result_from_legacy(S.not_captured("x", "X", "n"), "30d").state == "not_captured"
    op = K.result_from_legacy(S.metric("x", "X", 0, cohort=0, operational=True), "30d")
    assert op.state == "ok" and op.value == 0


# ----------------------------------------------------------------------------------------------------------------- schema sync
def test_committed_json_schema_matches_python_models():
    committed = json.loads((ROOT / "frontend" / "lib" / "admin" / "metricContract.schema.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(contract_json_schema(), sort_keys=True)), (
        "regenerate frontend/lib/admin/metricContract.schema.json from contract_json_schema() and update metricContract.ts")


def test_every_schema_object_forbids_extra_properties():
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert node.get("additionalProperties") is False
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(contract_json_schema())


def test_contract_adds_no_route_and_no_permission():
    from src.api.main import create_app
    paths = {p for p in create_app().openapi()["paths"] if p.startswith("/api/v1/admin/reports")}
    assert paths == {"/api/v1/admin/reports/" + s for s in ("definitions", "product", "quality", "operations", "ai-economics", "commercial")}
