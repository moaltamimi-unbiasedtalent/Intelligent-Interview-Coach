"""Admin report builder, saved report configurations and exports (package 03E1). Backend only.

Two route families, one per EXISTING read permission (no permission is added; the registry stays 44), mirroring how W10.12 separates the commercial report:

* ``/admin/report-builder/...``            requires ``platform.reports.read``            (product, quality, AI economics report types)
* ``/admin/report-builder/commercial/...`` requires ``platform.reports.commercial.read`` (the commercial report type ONLY)

Each family offers: ``GET registry`` (the code-defined report types, metrics, dimensions, windows and chart kinds the caller may use), ``GET validate`` and
``GET preview`` (a definition arrives as query parameters, so a read stays a GET; both are read-only and unaudited like every other report read),
``GET/POST/PUT/DELETE saved`` (the Admin's saved DEFINITIONS: owner-scoped, expected-revision protected, bounded, audited in the same transaction),
``GET saved/{id}/preview`` and ``POST export`` (CSV or JSON of ALREADY-SUPPRESSED aggregates only, bounded rows, formula-injection-safe, audited BEFORE any byte is sent;
if the audit cannot be written nothing is exported). A definition naming anything the caller may not read is 403; an invalid one is 422 with stable problem codes
and no echoed input. Nothing here writes candidate data, enqueues a job, calls a provider or model, or reads candidate content. The cohort rule is documented in
``src/reporting/report_builder.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import StringConstraints

from src.api.dependencies import get_audit_repository, get_repository, get_request_id, require_permission
from src.api.schemas.report_builder import (
    ExportRequest, PreviewResponse, ProblemOut, RegistryResponse, SavedList, SavedOut, SavedWrite, ValidateResponse,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import utcnow
from src.reporting import report_builder as RB
from src.reporting.report_configs import (
    MAX_CONFIGS_PER_OWNER, ConfigConflict, ConfigForbidden, ConfigNotFound, ReportConfigService,
)
from src.reporting.service import ReportingError, ReportingService

Label = Annotated[str, StringConstraints(max_length=96)]
Slug64 = Annotated[str, StringConstraints(max_length=64)]
ReportId = Annotated[str, Query(max_length=64)]
Metrics = Annotated[list[Slug64], Query(min_length=1, max_length=RB.MAX_METRICS)]
Window = Annotated[str, Query(max_length=12)]
Group = Annotated[str | None, Query(max_length=64)]
Filters = Annotated[list[Label], Query(max_length=RB.MAX_FILTERS * RB.MAX_FILTER_VALUES)]
Chart = Annotated[str | None, Query(max_length=20)]
Comparison = Annotated[str, Query(max_length=20)]
ExpectedRevision = Annotated[int, Query(ge=1)]


def _problems(exc: RB.ReportInvalid) -> list[ProblemOut]:
    return [ProblemOut(code=c, field=f, message=m) for c, f, m in exc.problems]


def _http(exc: Exception) -> HTTPException:
    """Stable, input-free errors. 422 lists problem codes in the message; nothing the caller sent is echoed."""
    if isinstance(exc, RB.ReportForbidden):
        return HTTPException(status_code=403, detail="Administrator access required.")
    if isinstance(exc, RB.ReportInvalid):
        return HTTPException(status_code=422, detail="; ".join(f"[{c}] {m}" for c, _f, m in exc.problems)[:900])
    if isinstance(exc, ConfigNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConfigForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ConfigConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ReportingError):
        return HTTPException(status_code=422, detail=str(exc))
    raise exc


def saved_out(view: dict) -> SavedOut:
    """A stored definition is re-parsed on every read: one that no longer validates is listed as ``valid: false`` with no definition (never a 500, never trusted)."""
    try:
        defn, ok = RB.parse_definition(view["definition"]), True
    except RB.ReportInvalid:
        defn, ok = None, False
    return SavedOut(**{**view, "definition": defn, "valid": ok})


def _caller_perms(principal) -> frozenset[str]:
    return perm.permissions_for_role(principal.platform_role)


def _build_router(prefix: str, required: str, tag: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    gate = require_permission(required)

    def readable(principal) -> frozenset[str]:
        caps = _caller_perms(principal)
        return frozenset(rid for rid, t in RB.REGISTRY.types.items() if t.permission == required and t.permission in caps)

    def cfg_svc(repo=Depends(get_repository)) -> ReportConfigService:
        return ReportConfigService(repo.session_factory)

    def builder(repo=Depends(get_repository)) -> RB.ReportBuilder:
        return RB.ReportBuilder(ReportingService(repo.session_factory))

    def plan_for(defn: RB.BuilderDefinition, principal) -> RB.Plan:
        try:
            return RB.validate_definition(defn, _caller_perms(principal), required)
        except (RB.ReportForbidden, RB.ReportInvalid) as exc:
            raise _http(exc)

    def query_definition(report_id, metric_ids, window, group_by, filters, chart, comparison) -> RB.BuilderDefinition:
        try:
            return RB.definition_from_query(report_id=report_id, metric_ids=metric_ids, window=window, group_by=group_by, filters=filters, chart=chart, comparison=comparison)
        except RB.ReportInvalid as exc:
            raise _http(exc)

    def run_preview(plan: RB.Plan, b: RB.ReportBuilder) -> dict:
        try:
            return b.preview(plan)
        except ReportingError as exc:
            raise _http(exc)

    # ------------------------------------------------------------------ registry, validate, preview (GET, read-only)
    @router.get("/registry", response_model=RegistryResponse, summary="Code-defined report types, metrics, dimensions, windows and chart kinds this caller may use")
    def registry(principal=Depends(gate)) -> RegistryResponse:
        return RegistryResponse(**RB.REGISTRY.describe(_caller_perms(principal), required))

    @router.get("/validate", response_model=ValidateResponse, summary="Validate a report definition against the registry and the caller's permissions")
    def validate(report_id: ReportId, metric_ids: Metrics, window: Window = "30d", group_by: Group = None, filter: Filters = [], chart: Chart = None, comparison: Comparison = "none",  # noqa: A002,B006
                 principal=Depends(gate)) -> ValidateResponse:
        try:
            RB.validate_definition(RB.definition_from_query(report_id=report_id, metric_ids=metric_ids, window=window, group_by=group_by, filters=filter, chart=chart, comparison=comparison),
                                   _caller_perms(principal), required)
        except RB.ReportForbidden as exc:
            raise _http(exc)
        except RB.ReportInvalid as exc:
            return ValidateResponse(valid=False, problems=_problems(exc))
        return ValidateResponse(valid=True, problems=[])

    @router.get("/preview", response_model=PreviewResponse, summary="Preview a report definition through the existing suppression pipeline (aggregates only)")
    def preview(report_id: ReportId, metric_ids: Metrics, window: Window = "30d", group_by: Group = None, filter: Filters = [], chart: Chart = None, comparison: Comparison = "none",  # noqa: A002,B006
                principal=Depends(gate), b: RB.ReportBuilder = Depends(builder)) -> PreviewResponse:
        defn = query_definition(report_id, metric_ids, window, group_by, filter, chart, comparison)
        return PreviewResponse(**run_preview(plan_for(defn, principal), b))

    # ------------------------------------------------------------------ saved configurations
    @router.get("/saved", response_model=SavedList, summary="Your saved report definitions, plus definitions other Admins shared and you may read")
    def saved_list(principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc)) -> SavedList:
        return SavedList(items=[saved_out(v) for v in svc.list_visible(principal.user_id, readable(principal))], max_saved=MAX_CONFIGS_PER_OWNER)

    @router.post("/saved", response_model=SavedOut, status_code=201, summary="Save a report definition (definition only; never results or candidate data)")
    def saved_create(body: SavedWrite, request: Request, response: Response, principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc)) -> SavedOut:
        try:
            name = RB.validate_name(body.name)
        except RB.ReportInvalid as exc:
            raise _http(exc)
        plan_for(body.definition, principal)
        audit = A.build_audit(event_type=A.ADMIN_REPORT_CONFIG_CREATED, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="report_config")
        try:
            view, created = svc.create(principal.user_id, name, body.definition, body.shared, audit=audit)
        except ConfigConflict as exc:
            raise _http(exc)
        if not created:
            response.status_code = 200                                    # idempotent replay of the identical request
        return saved_out(view)

    @router.get("/saved/{config_id}", response_model=SavedOut, summary="One saved definition (yours, or one shared with you)")
    def saved_get(config_id: int, principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc)) -> SavedOut:
        try:
            return saved_out(svc.get_visible(principal.user_id, config_id, readable(principal)))
        except ConfigNotFound as exc:
            raise _http(exc)

    @router.put("/saved/{config_id}", response_model=SavedOut, summary="Replace a saved definition you own (expected revision required; an identical repeat is a no-op)")
    def saved_update(config_id: int, body: SavedWrite, request: Request, principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc)) -> SavedOut:
        if body.expected_revision is None:
            raise HTTPException(status_code=422, detail="[expected_revision_required] An expected revision is required.")
        try:
            name = RB.validate_name(body.name)
        except RB.ReportInvalid as exc:
            raise _http(exc)
        plan_for(body.definition, principal)
        audit = A.build_audit(event_type=A.ADMIN_REPORT_CONFIG_UPDATED, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="report_config")
        try:
            view, _changed = svc.update(principal.user_id, config_id, expected_revision=body.expected_revision, name=name, definition=body.definition, shared=body.shared,
                                        readable_report_ids=readable(principal), audit=audit)
        except (ConfigNotFound, ConfigForbidden, ConfigConflict) as exc:
            raise _http(exc)
        return saved_out(view)

    @router.delete("/saved/{config_id}", status_code=204, summary="Delete a saved definition you own (expected_revision query parameter required)")
    def saved_delete(config_id: int, expected_revision: ExpectedRevision, request: Request, principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc)) -> Response:
        audit = A.build_audit(event_type=A.ADMIN_REPORT_CONFIG_DELETED, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="report_config")
        try:
            svc.delete(principal.user_id, config_id, expected_revision=expected_revision, readable_report_ids=readable(principal), audit=audit)
        except (ConfigNotFound, ConfigForbidden, ConfigConflict) as exc:
            raise _http(exc)
        return Response(status_code=204)

    def stored_definition(svc: ReportConfigService, principal, config_id: int) -> RB.BuilderDefinition:
        try:
            view = svc.get_visible(principal.user_id, config_id, readable(principal))
            return svc.definition_of(view)                                 # re-parsed: a stored definition is never trusted
        except (ConfigNotFound, RB.ReportInvalid) as exc:
            raise _http(exc)

    @router.get("/saved/{config_id}/preview", response_model=PreviewResponse, summary="Run a saved definition now (re-validated against the current registry and your permissions)")
    def saved_preview(config_id: int, principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc), b: RB.ReportBuilder = Depends(builder)) -> PreviewResponse:
        return PreviewResponse(**run_preview(plan_for(stored_definition(svc, principal, config_id), principal), b))

    # ------------------------------------------------------------------ export (POST on purpose, like the audit export: it records an audit event)
    @router.post("/export", summary="Export the already-suppressed aggregates of a definition as CSV or JSON (bounded rows, audited before sending)")
    def export(body: ExportRequest, request: Request, principal=Depends(gate), svc: ReportConfigService = Depends(cfg_svc), b: RB.ReportBuilder = Depends(builder),
               audit_repo=Depends(get_audit_repository)) -> Response:
        defn = body.definition if body.definition is not None else stored_definition(svc, principal, body.saved_id)
        plan = plan_for(defn, principal)
        result = run_preview(plan, b)
        rows = RB.export_rows(result)
        try:
            RB.check_export_size(rows)
        except RB.ReportInvalid as exc:
            raise _http(exc)
        now = utcnow()
        filename = RB.export_filename(defn.report_id, defn.window, body.format, now)
        try:                                                                  # fail closed: no audit row, no export
            audit_repo.record(**A.build_audit(
                event_type=A.ADMIN_REPORT_EXPORTED, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="report_type", target_id=defn.report_id,
                report_id=defn.report_id, window=defn.window, format=body.format, row_count=len(rows), metric_count=len(defn.metric_ids),
                grouped_by=defn.group_by, source="saved" if body.saved_id is not None else "inline", config_id=body.saved_id))
        except Exception:                                                     # noqa: BLE001 - the cause is never surfaced
            raise HTTPException(status_code=503, detail="The export could not be audited, so nothing was exported.")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Export-Rows": str(len(rows))}
        if body.format == "csv":
            return StreamingResponse(RB.render_csv(rows), media_type="text/csv; charset=utf-8", headers=headers)
        return Response(content=RB.render_json(result, rows), media_type="application/json", headers=headers)

    return router


standard_router = _build_router("/admin/report-builder", perm.REPORTS_READ, "admin-report-builder")
commercial_router = _build_router("/admin/report-builder/commercial", perm.REPORTS_COMMERCIAL, "admin-report-builder-commercial")
# ``src.api.admin_route_invariant`` discovers every APIRouter attribute of a route module; the main app includes both through ``routers``.
routers = (standard_router, commercial_router)
