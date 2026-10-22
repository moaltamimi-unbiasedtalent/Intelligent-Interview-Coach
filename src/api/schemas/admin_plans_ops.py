"""Allowlist schemas for plan administration (03B). Every model forbids extra fields, so a stray column can never reach a
response. Nothing here carries commercial terms, a candidate's content or an email address."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from src.api.schemas.admin import EntitlementBounds, Subscribers, SubscriptionEntry


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntitlementValueOut(_Strict):
    enabled: bool
    limit: int | None


class MatrixEntitlement(_Strict):
    code: str
    label: str
    description: str
    type: str
    bounds: EntitlementBounds


class MatrixVersion(_Strict):
    id: int
    plan_code: str
    version: int
    display_name: str
    status: str
    revision: str
    values: dict[str, EntitlementValueOut]


class PlanMatrix(_Strict):
    entitlements: list[MatrixEntitlement]
    versions: list[MatrixVersion]


class CompareHead(_Strict):
    id: int
    plan_code: str
    version: int
    display_name: str
    status: str
    subscribers: Subscribers


class CompareRow(_Strict):
    code: str
    label: str
    left: EntitlementValueOut
    right: EntitlementValueOut
    differs: bool


class PlanComparison(_Strict):
    left: CompareHead
    right: CompareHead
    rows: list[CompareRow]
    changed: int
    note: str


class SubjectPlanState(_Strict):
    subject_type: str
    subject_id: int
    current: SubscriptionEntry | None
    history: list[SubscriptionEntry]
    revision: str


class VersionAssignment(_Strict):
    subject_type: str
    subject_id: int
    status: str
    source: str
    started_at: str | None
    ended_at: str | None


class VersionAssignmentPage(_Strict):
    plan_code: str
    version: int
    total: int
    page: int
    page_size: int
    items: list[VersionAssignment]


class ExplainItem(_Strict):
    code: str
    label: str
    allowed: bool
    limit: int | None
    unlimited: bool
    reason: str


class ExplainLayer(_Strict):
    layer: str
    evaluated_here: bool
    note: str


class EntitlementExplanation(_Strict):
    subject_type: str
    subject_id: int
    plan_code: str
    plan_version: int | None
    plan_version_status: str | None
    source: str
    items: list[ExplainItem]
    layers: list[ExplainLayer]
    note: str


class EffectRow(_Strict):
    code: str
    label: str
    gain: int
    lose: int
    limit_changed: int


class ByCurrentPlan(_Strict):
    basic: int
    premium: int
    none: int


class AssignmentPreview(_Strict):
    plan_code: str
    target_version: int
    subject_type: str
    requested: int
    found: int
    missing: int
    unchanged: int
    would_change: int
    by_current_plan: ByCurrentPlan
    entitlement_effect: list[EffectRow]
    preview_revision: str


class AssignmentRequest(_Strict):
    plan_code: str = Field(min_length=1, max_length=32)
    subject_type: str = Field(min_length=1, max_length=16)
    subject_ids: list[StrictInt] = Field(min_length=1, max_length=100)


class BulkAssignRequest(AssignmentRequest):
    preview_revision: str = Field(min_length=1, max_length=64)


class SingleAssignRequest(_Strict):
    plan_code: str = Field(min_length=1, max_length=32)
    subject_type: str = Field(min_length=1, max_length=16)
    subject_id: StrictInt
    expected_revision: str = Field(min_length=1, max_length=64)


class AssignResult(_Strict):
    subject_type: str
    subject_id: int
    plan_code: str
    version: int
    changed: bool


class BulkAssignResult(_Strict):
    plan_code: str
    version: int
    subject_type: str
    requested: int
    changed: int
    unchanged: int


class RestoreRequest(_Strict):
    expected_revision: str = Field(min_length=1, max_length=64)


class RestoreResult(_Strict):
    id: int
    plan_code: str
    version: int
    copied_from: int
