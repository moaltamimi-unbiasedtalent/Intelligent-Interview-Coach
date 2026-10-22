"""Governed Admin report builder (package 03E1): report registry, definition validation, preview and export rendering.

The builder is a PROJECTION over the existing, already-suppressed reporting pipeline (``ReportingService``, W10.12) and the frozen 03K contract
(``src/reporting/contract.py``). It never reads a table itself except one bounded aggregate (``feedback``), and it can express nothing outside closed sets:

* REGISTRY: report types are the 03K ``contract_reports()`` (product, quality, ai_economics, commercial) over registered 03K metrics. A definition names a
  report type, a SUBSET of that report's metric ids, a window, an optional grouping dimension, optional filters and an optional chart kind. Metric ids, dimension
  ids, windows and chart kinds are slugs / closed enums validated against the registry; there is no field that can carry SQL, a table, a column or an expression
  (``contract.reject_sql_like`` runs on every string, and filter values are bounded labels compared in Python, never interpolated anywhere).
* PERMISSIONS: a report type needs its 03K ``permission_required`` (``platform.reports.read`` or ``platform.reports.commercial.read``) and so does every metric. The
  caller's permissions come from the server-side role; a definition naming anything the caller may not read is refused (403), never silently trimmed.
* WINDOWS: the fixed 03K periods, narrowed for the builder to ``BUILDER_WINDOWS`` (7d, 30d, 90d). ``all_time`` is refused as over-wide for a custom definition; it stays
  available on the fixed ``/admin/reports/*`` endpoints.

COHORT RULE (documented and tested; ``tests/test_report_builder_03e1.py``):

1. Every figure comes from the existing pipeline, so candidate cohorts below ``REPORTING_MIN_COHORT`` (5) are suppressed (value null, never the count) and rates need a
   non-small numerator and complement. The builder never recomputes, rounds or re-aggregates a figure.
2. A FILTER selects ROWS of the grouped result AFTER primary and secondary suppression were decided on the full bucket set. A filter therefore cannot isolate, un-hide
   or subtotal anything: every cell any filtered preview shows is identical to the cell the unfiltered grouped preview shows, and a suppressed bucket stays suppressed
   under every filter. Filters must name the grouping dimension (a filter on another dimension would require a cross-tab, which would create new small cohorts
   and is refused as ``cross_dimension_filter``). A filter without a grouping is refused.
3. Consequently saved variants (different filters, selections or chart kinds of the same metric, window and grouping) differ only by which already-decided rows they
   show: differencing them yields nothing the unfiltered grouped preview does not already show. A grouped preview returns buckets only (no headline total in the same
   result), and secondary suppression guarantees that when exactly one bucket is hidden the smallest visible one is hidden too.
4. RESIDUAL LIMITATION (pre-existing, unchanged, not introduced here): the fixed windows are nested (7d within 30d within 90d), and the figures of two windows, or a
   total against its buckets when two or more buckets are hidden, can be subtracted by a reader who may read all of them. The builder adds no window, no finer grain
   and no new dimension beyond what ``/admin/reports/*`` already serves to the same permission, so it adds no differencing capability; it is an engineering control,
   not an anonymisation guarantee.

Nothing here writes, enqueues a job, calls a provider or model, or reads candidate content.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, select

from src.persistence import User, UserFeedback
from src.reporting import contract as K
from src.reporting import suppression as S
from src.reporting.definitions import PERIODS, REPORTING_MIN_COHORT
from src.reporting.service import ReportingService, _iso

BUILDER_WINDOWS: Final[tuple[str, ...]] = ("7d", "30d", "90d")
MAX_METRICS: Final = 12
MAX_FILTERS: Final = 3
MAX_FILTER_VALUES: Final = 10
MAX_DEFINITION_BYTES: Final = 2048
MAX_EXPORT_ROWS: Final = 2000
CHART_KINDS: Final[tuple[str, ...]] = ("trend", "funnel", "share_of_whole", "distribution", "table")

_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./:\-]{0,63}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{2,59}$")

PRIVACY_NOTE: Final = ("Aggregates only. Candidate cohorts below the engineering privacy floor are suppressed (this is not an anonymisation guarantee). "
                       "No candidate content, identifier, e-mail or credential is returned.")


# ------------------------------------------------------------------------------------------------------------------------------ errors
class BuilderError(Exception):
    pass


class ReportForbidden(BuilderError):
    """The caller may not read what the definition names (HTTP 403)."""


class ReportInvalid(BuilderError):
    """The definition is not valid against the registry (HTTP 422). ``problems`` are ``(code, field, message)`` with no echoed input."""

    def __init__(self, problems: list[tuple[str, str, str]]) -> None:
        self.problems = problems
        super().__init__("; ".join(f"{c}: {m}" for c, _f, m in problems))


# ------------------------------------------------------------------------------------------------------------------------------ definition
Slug = K.Slug


class FilterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    dimension_id: Slug
    values: list[str] = Field(min_length=1, max_length=MAX_FILTER_VALUES)

    @field_validator("values")
    @classmethod
    def _values(cls, v: list[str]) -> list[str]:
        for item in v:
            if not _LABEL.match(item):
                raise ValueError("filter values are short labels (letters, digits, space and _ . / : -)")
            K.reject_sql_like(item)
        if len(set(v)) != len(v):
            raise ValueError("filter values must be unique")
        return v


class BuilderDefinition(BaseModel):
    """What an Admin may express. Closed fields only (``extra=forbid``); every id is checked against the registry by ``validate_definition``."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    report_id: Slug
    metric_ids: list[Slug] = Field(min_length=1, max_length=MAX_METRICS)
    window: Literal["7d", "30d", "90d", "all_time"] = "30d"
    group_by: Slug | None = None
    filters: list[FilterSpec] = Field(default_factory=list, max_length=MAX_FILTERS)
    chart: Literal["trend", "funnel", "share_of_whole", "distribution", "table"] | None = None
    comparison: Literal["none", "previous_period"] = "none"

    @model_validator(mode="after")
    def _shape(self) -> "BuilderDefinition":
        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("metric_ids must be unique")
        if len({f.dimension_id for f in self.filters}) != len(self.filters):
            raise ValueError("one filter per dimension")
        return self

    def canonical(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()


def definition_from_query(*, report_id: str, metric_ids: list[str], window: str, group_by: str | None, filters: list[str], chart: str | None,
                          comparison: str = "none") -> BuilderDefinition:
    """Build a definition from GET query parameters. ``filters`` are ``dimension:value`` pairs (repeatable; same dimension merges). Raises ``ReportInvalid`` with no echoed input."""
    merged: dict[str, list[str]] = {}
    for item in filters:
        dim, sep, value = item.partition(":")
        if not sep:
            raise ReportInvalid([("bad_filter", "filter", "A filter is written dimension:value.")])
        merged.setdefault(dim, []).append(value)
    raw = {"report_id": report_id, "metric_ids": metric_ids, "window": window, "group_by": group_by or None,
           "filters": [{"dimension_id": d, "values": v} for d, v in merged.items()], "chart": chart or None,
           "comparison": comparison or "none"}
    return parse_definition(raw)


def parse_definition(raw: Any) -> BuilderDefinition:
    try:
        return BuilderDefinition.model_validate(raw)
    except ValidationError as exc:
        raise ReportInvalid([("malformed_definition", ".".join(str(p) for p in e["loc"]) or "definition", "This field is not valid.") for e in exc.errors()][:12])


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME.match(name.strip()) or "  " in name:
        raise ReportInvalid([("bad_name", "name", "A name is 3 to 60 characters: letters, digits, space, '.', '_' or '-', starting with a letter or digit.")])
    try:
        K.reject_sql_like(name)
    except ValueError:
        raise ReportInvalid([("bad_name", "name", "This name is not accepted.")])
    return name.strip()


# ------------------------------------------------------------------------------------------------------------------------------ registry
@dataclass(frozen=True)
class _Source:
    report: str                                       # ReportingService method that already applies suppression
    legacy_id: str | None                             # metric id inside that report (None: grouped-only metric)
    tables: dict[str, tuple[str, int]]                # dimension -> (table id, cell column index) in that report
    must_group_by: str | None = None
    comparable: bool = True                           # False: a CURRENT-STATE figure (not bound to the window), so a previous period would be the same number


_SOURCES: Final[dict[str, _Source]] = {
    "registrations": _Source("product", "registrations", {}),
    "onboarding_completed": _Source("product", "onboarding_completed", {}),
    "onboarding_rate": _Source("product", "onboarding_rate", {}),
    "opportunities_created": _Source("product", "opportunities_created", {}),
    "prepare_started": _Source("product", "prepare_started", {}),
    "prepare_ready_rate": _Source("product", "prepare_ready_rate", {}),
    "practice_started": _Source("product", "practice_started", {}),
    "practice_completed": _Source("product", "practice_completed", {}),
    "activation": _Source("product", "activated_candidates", {}),
    "returning": _Source("product", "returning_candidates", {}),
    "feedback": _Source("own", None, {"feedback_category": ("feedback_category", 0)}),
    "evaluation_score": _Source("quality", "evaluation_score_avg", {}),
    "retrieval_outcomes": _Source("quality", "retrieval_outcomes", {}),
    "request_outcomes": _Source("quality", "request_outcomes", {"operation": ("request_outcomes", 0)}),
    "provider_calls": _Source("quality", "provider_calls", {}),
    "ai_usage": _Source("ai_economics", "ai_tokens_known", {"workflow": ("ai_by_workflow", 1), "model": ("ai_by_model", 1)}),
    "ai_known_cost": _Source("ai_economics", "ai_known_cost_usd", {"workflow": ("ai_by_workflow", 2), "model": ("ai_by_model", 2)}),
    "access_plans": _Source("commercial", "access_active", {"plan": ("access_by_plan", 0)}, comparable=False),
    "mock_mrr": _Source("commercial", None, {"currency": ("mock_recurring", 1)}, must_group_by="currency", comparable=False),
    "mock_arr": _Source("commercial", None, {"currency": ("mock_recurring", 2)}, must_group_by="currency", comparable=False),
    "mock_failed_payments": _Source("commercial", "mock_failed_payments", {}),
}


@dataclass(frozen=True)
class ReportType:
    report: K.ReportDefinition
    metrics: dict[str, K.MetricDefinition]
    windows: tuple[str, ...]

    @property
    def permission(self) -> str:
        return self.report.permission_required

    def dimensions_for(self, metric_id: str) -> tuple[str, ...]:
        """Dimensions a metric can be grouped by: the 03K ``dimensions_allowed`` that the engine can actually produce from the suppressed pipeline."""
        return tuple(d for d in self.metrics[metric_id].dimensions_allowed if d in _SOURCES[metric_id].tables)


class Registry:
    def __init__(self) -> None:
        metrics, dimensions, reports = K.default_registry()                      # validate_registry runs here (03K invariants)
        self.metrics = {m.metric_id: m for m in metrics}
        self.dimensions = {d.dimension_id: d for d in dimensions}
        if set(_SOURCES) != set(self.metrics):
            raise RuntimeError("report builder sources and the 03K metric registry differ")
        self.types: dict[str, ReportType] = {}
        for r in reports:
            windows = tuple(p for p in BUILDER_WINDOWS if p in r.date_range.allowed_periods and all(p in self.metrics[m].period_kinds for m in r.metric_ids))
            self.types[r.report_id] = ReportType(r, {m: self.metrics[m] for m in r.metric_ids}, windows)
        for mid, src in _SOURCES.items():
            if src.must_group_by and src.must_group_by not in self.metrics[mid].dimensions_allowed:
                raise RuntimeError(f"{mid}: must_group_by is not an allowed dimension")

    def describe(self, caller_perms: frozenset[str], required: str) -> dict:
        types = []
        for rid, t in self.types.items():
            if t.permission != required or t.permission not in caller_perms:
                continue
            types.append({
                "report_id": rid, "title": t.report.title, "description": t.report.description, "permission_required": t.permission, "windows": list(t.windows),
                "metrics": [{"metric_id": m.metric_id, "label": m.label, "description": m.description, "unit": m.unit, "coverage": m.coverage.note,
                             "suppression": m.suppression.kind, "dimensions": list(t.dimensions_for(m.metric_id)),
                             "must_group_by": _SOURCES[m.metric_id].must_group_by, "comparable": _SOURCES[m.metric_id].comparable} for m in t.metrics.values()]})
        used = {d for t in types for m in t["metrics"] for d in m["dimensions"]}
        return {"report_types": types,
                "dimensions": [{"dimension_id": d.dimension_id, "label": d.label, "description": d.description, "kind": d.kind, "max_buckets": d.max_buckets}
                               for d in self.dimensions.values() if d.dimension_id in used],
                "windows": list(BUILDER_WINDOWS), "chart_kinds": list(CHART_KINDS), "comparisons": ["none", "previous_period"],
                "limits": {"max_metrics": MAX_METRICS, "max_filters": MAX_FILTERS, "max_filter_values": MAX_FILTER_VALUES, "max_export_rows": MAX_EXPORT_ROWS,
                           "max_definition_bytes": MAX_DEFINITION_BYTES},
                "min_cohort": REPORTING_MIN_COHORT,
                "rules": ["Filters choose rows of the grouped result after suppression and must name the grouping dimension.",
                          "Currencies are never combined: Mock MRR and Mock ARR must be grouped by currency.",
                          "all_time is not available to custom definitions.",
                          PRIVACY_NOTE]}


REGISTRY = Registry()


@dataclass(frozen=True)
class Plan:
    type: ReportType
    definition: BuilderDefinition


def validate_definition(defn: BuilderDefinition, caller_perms: frozenset[str], required: str) -> Plan:
    """Checks ``defn`` against the registry and the caller's permissions. Raises ``ReportForbidden`` (403) or ``ReportInvalid`` (422, all problems listed)."""
    t = REGISTRY.types.get(defn.report_id)
    if t is None:
        raise ReportInvalid([("unknown_report", "report_id", "This report type is not registered.")])
    if t.permission != required or t.permission not in caller_perms or not all(m.permission_required in caller_perms for m in t.metrics.values()):
        raise ReportForbidden("You may not read this report type here.")
    problems: list[tuple[str, str, str]] = []
    for mid in defn.metric_ids:
        if mid not in REGISTRY.metrics:
            problems.append(("unknown_metric", "metric_ids", "A metric id is not registered."))
        elif mid not in t.metrics:
            problems.append(("metric_not_in_report", "metric_ids", "A metric does not belong to this report type."))
    if defn.window not in t.windows:
        problems.append(("window_too_wide" if defn.window in PERIODS and defn.window not in BUILDER_WINDOWS else "window_not_allowed", "window",
                         f"The window must be one of {', '.join(t.windows)}."))
    known = [m for m in defn.metric_ids if m in t.metrics]
    gb = defn.group_by
    if gb is not None:
        d = REGISTRY.dimensions.get(gb)
        if d is None:
            problems.append(("unknown_dimension", "group_by", "This dimension is not registered."))
        elif d.kind != "category":
            problems.append(("dimension_not_supported", "group_by", "Only category dimensions can group a report; no registered metric has a time breakdown."))
        else:
            for mid in known:
                if gb not in t.dimensions_for(mid):
                    problems.append(("dimension_not_supported", "group_by", f"Metric '{mid}' cannot be grouped by '{gb}'."))
    for mid in known:
        need = _SOURCES[mid].must_group_by
        if need and gb != need:
            problems.append(("must_group", "group_by", f"Metric '{mid}' is per {need} and is never combined across {need} values: group by {need}."))
    for f in defn.filters:
        if f.dimension_id not in REGISTRY.dimensions:
            problems.append(("unknown_dimension", "filters", "A filter dimension is not registered."))
        elif gb is None:
            problems.append(("filter_needs_grouping", "filters", "A filter selects rows of the grouped result: set group_by."))
        elif f.dimension_id != gb:
            problems.append(("cross_dimension_filter", "filters", "A filter must name the grouping dimension (cross-tabs would create small cohorts)."))
    if defn.chart is not None:
        spec = None
        try:
            spec = K.ChartSpec(chart_id="builder", kind=defn.chart, metric_ids=list(defn.metric_ids), dimension_id=gb, title="Builder chart")
        except ValueError:
            problems.append(("chart_incompatible", "chart", "This chart cannot be built from the selected metrics."))
        if spec is not None:
            for p in K.chart_problems(spec, {m: REGISTRY.metrics[m] for m in known}, REGISTRY.dimensions):
                problems.append(("chart_incompatible", "chart", p.split(": ", 1)[-1][:160]))
    if defn.comparison == "previous_period":
        for mid in known:
            if not _SOURCES[mid].comparable:
                problems.append(("not_comparable", "comparison", f"Metric '{mid}' is a current-state figure; a previous period would be the same number."))
    if len(defn.canonical().encode()) > MAX_DEFINITION_BYTES:
        problems.append(("definition_too_large", "definition", "The definition is too large."))
    if problems:
        raise ReportInvalid(problems)
    return Plan(t, defn)


# ------------------------------------------------------------------------------------------------------------------------------ preview
def _normalise(legacy: dict, mdef: K.MetricDefinition, period: str) -> K.MetricResult:
    """Adapt one legacy (already suppressed) metric dict to a checked 03K ``MetricResult`` for ``mdef``."""
    res = K.result_from_legacy({**legacy, "metric_id": mdef.metric_id}, period)
    if res.state in ("unavailable", "not_captured") and res.state != mdef.missing_behaviour:
        res = K.MetricResult(metric_id=res.metric_id, period=res.period, state=mdef.missing_behaviour, coverage=res.coverage,
                             note=(f"{res.state}: {res.note}" if res.note else res.state)[:400])
    K.check_result(res, mdef)
    return res


def _bucket(row: dict, col: int) -> dict:
    cell = row["cells"][col]
    if cell["suppressed"]:
        return {"label": row["label"], "state": "suppressed", "value": None}
    if cell["figure"] is None:
        return {"label": row["label"], "state": "unavailable", "value": None}
    return {"label": row["label"], "state": "ok", "value": cell["figure"]}


class ReportBuilder:
    def __init__(self, service: ReportingService) -> None:
        self._svc = service

    # a report function is evaluated at most once per preview
    def _reports(self, svc: ReportingService, plan: Plan) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for mid in plan.definition.metric_ids:
            src = _SOURCES[mid]
            if src.report == "own" or src.report in out:
                continue
            out[src.report] = getattr(svc, src.report)(plan.definition.window)
        return out

    @staticmethod
    def _find_metric(report: dict, legacy_id: str) -> dict | None:
        for sec in report["sections"]:
            for m in sec["metrics"]:
                if m["metric_id"] == legacy_id:
                    return m
        return None

    @staticmethod
    def _find_table(report: dict, table_id: str) -> dict | None:
        for sec in report["sections"]:
            for t in sec["tables"]:
                if t["table_id"] == table_id:
                    return t
        return None

    def _feedback(self, svc: ReportingService, window: str, group: bool) -> tuple[dict | None, list[dict]]:
        """The ONE aggregate the builder reads itself: feedback items (count) with the distinct-candidate cohort behind it. Same suppression helpers as the service."""
        _p, since, now = svc.window(window)
        with svc._sf() as s:
            cand = select(User.id).where(User.platform_role == "user")
            base = [UserFeedback.user_id.in_(cand), *svc._in(UserFeedback.created_at, since, now)]
            total, users = s.execute(select(func.count(), func.count(func.distinct(UserFeedback.user_id))).where(*base)).one()
            rows = s.execute(select(UserFeedback.category, func.count(), func.count(func.distinct(UserFeedback.user_id))).where(*base).group_by(UserFeedback.category)).all() if group else []
        head = S.metric("feedback", "Candidate feedback", int(total) if total else None, cohort=int(users or 0), coverage="Historical, from authoritative rows")
        if not total:
            head = S.not_captured("feedback", "Candidate feedback", "No feedback was given in this period.", "Historical, from authoritative rows")
        part = S.partition([{"label": c or "uncategorised", "values": [int(n)], "cohort": int(u)} for c, n, u in sorted(rows, key=lambda r: (r[0] is None, r[0] or ""))]) if group else []
        return head, part

    def preview(self, plan: Plan) -> dict:
        d = plan.definition
        _w, since, now = self._svc.window(d.window)
        out_metrics = self._evaluate(self._svc, plan)
        out = {"report_id": d.report_id, "title": plan.type.report.title, "window": d.window, "window_start": _iso(since), "window_end": _iso(now),
               "generated_at": _iso(now), "utc": True, "group_by": d.group_by, "filters": [{"dimension_id": f.dimension_id, "values": list(f.values)} for f in d.filters],
               "chart": d.chart, "comparison": d.comparison, "previous_window_start": None, "previous_window_end": None, "metrics": out_metrics, "privacy": PRIVACY_NOTE}
        for m in out_metrics:
            m["previous"] = None
        if d.comparison == "previous_period":
            # The SAME pipeline, evaluated one window earlier (a shifted clock): the previous period is a disjoint, equally-suppressed window, never a derived figure.
            from datetime import timedelta

            days = PERIODS[d.window]
            prev_now = now - timedelta(days=days)
            prev_svc = ReportingService(self._svc._sf, clock=lambda: prev_now)
            _w2, p_since, p_now = prev_svc.window(d.window)
            out["previous_window_start"], out["previous_window_end"] = _iso(p_since), _iso(p_now)
            for cur, prev in zip(out_metrics, self._evaluate(prev_svc, plan)):
                cur["previous"] = {k: prev[k] for k in ("state", "value", "partial", "note", "buckets")}
        return out

    def _evaluate(self, svc: ReportingService, plan: Plan) -> list[dict]:
        d = plan.definition
        reports = self._reports(svc, plan)
        out_metrics: list[dict] = []
        for mid in d.metric_ids:
            mdef, src = REGISTRY.metrics[mid], _SOURCES[mid]
            grouped = d.group_by is not None
            if src.report == "own":
                head, rows = self._feedback(svc, d.window, grouped)
                legacy = head
            else:
                rep = reports[src.report]
                legacy = self._find_metric(rep, src.legacy_id) if src.legacy_id else None
                rows = []
                if grouped:
                    tid, _col = src.tables[d.group_by]
                    tbl = self._find_table(rep, tid)
                    rows = tbl["rows"] if tbl else []
            item = {"metric_id": mid, "label": mdef.label, "unit": mdef.unit, "period": d.window, "coverage": mdef.coverage.note, "suppression": mdef.suppression.kind,
                    "state": "unavailable", "value": None, "partial": False, "note": "", "group_dimension": d.group_by, "buckets": None}
            if grouped:
                col = src.tables[d.group_by][1]
                buckets = [_bucket(r, col) for r in rows]
                if d.filters:                                                     # a row selection AFTER suppression: nothing is recomputed
                    keep = set(d.filters[0].values)
                    buckets = [b for b in buckets if b["label"] in keep]
                if rows:
                    item["state"] = "ok"
                else:
                    item["note"] = "No data in this window for this grouping."
                item["buckets"] = buckets
                if d.filters and rows and not buckets:
                    item["note"] = "No bucket matches the filter."
            else:
                if legacy is None:
                    item["note"] = "No evidence for this metric in this window."
                else:
                    res = _normalise(legacy, mdef, d.window)
                    item.update(state=res.state, value=res.value, partial=res.partial, note=res.note)
            out_metrics.append(item)
        return out_metrics


# ------------------------------------------------------------------------------------------------------------------------------ export
EXPORT_COLUMNS: Final[tuple[str, ...]] = ("report_id", "window", "metric_id", "metric_label", "unit", "group_dimension", "group_value", "state", "value", "partial")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def csv_safe(value: Any) -> str:
    """One CSV cell, formula-injection safe: strings starting with = + - @ (or a tab/CR/LF) get a leading apostrophe, control characters are dropped, numbers are not touched."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    s = _CTRL.sub("", str(value).replace("\r", " ").replace("\n", " "))
    probe = s.lstrip(" ")
    if probe and probe[0] in "=+-@\t":
        s = "'" + s
    return s


def export_rows(preview: dict) -> list[dict]:
    rows: list[dict] = []
    for m in preview["metrics"]:
        base = {"report_id": preview["report_id"], "window": preview["window"], "metric_id": m["metric_id"], "metric_label": m["label"], "unit": m["unit"],
                "group_dimension": m["group_dimension"]}
        if m["buckets"] is None:
            rows.append({**base, "group_value": None, "state": m["state"], "value": m["value"], "partial": m["partial"]})
        elif not m["buckets"]:
            rows.append({**base, "group_value": None, "state": m["state"] if m["state"] != "ok" else "unavailable", "value": None, "partial": False})
        else:
            rows += [{**base, "group_value": b["label"], "state": b["state"], "value": b["value"], "partial": False} for b in m["buckets"]]
    return rows


def render_csv(rows: list[dict]) -> Iterator[str]:
    def line(cells: list[str]) -> str:
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL).writerow(cells)
        return buf.getvalue()
    yield line(list(EXPORT_COLUMNS))
    for r in rows:
        yield line([csv_safe(r[c]) for c in EXPORT_COLUMNS])


def render_json(preview: dict, rows: list[dict]) -> str:
    return json.dumps({"report_id": preview["report_id"], "window": preview["window"], "window_start": preview["window_start"], "window_end": preview["window_end"],
                       "generated_at": preview["generated_at"], "columns": list(EXPORT_COLUMNS), "rows": rows, "privacy": PRIVACY_NOTE}, separators=(",", ":"))


def export_filename(report_id: str, window: str, fmt: str, now: datetime) -> str:
    """Built only from registry slugs, a closed window and the format: never from a saved name or any request text."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", report_id) or window not in PERIODS or fmt not in ("csv", "json"):
        raise ValueError("unsafe filename part")
    return f"ask4mo-{report_id}-{window}-{now.strftime('%Y%m%d')}.{fmt}"


def check_export_size(rows: list[dict]) -> None:
    if len(rows) > MAX_EXPORT_ROWS:
        raise ReportInvalid([("export_too_large", "definition", f"The export would exceed {MAX_EXPORT_ROWS} rows; narrow the metrics or the grouping.")])
