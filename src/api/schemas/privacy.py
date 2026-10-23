"""Candidate-facing privacy/legal schemas (P10B-W10.10). Allowlist, ``extra="forbid"``: no operator identity, no internal field."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrivacyRequestCreate(_Strict):
    request_type: str = Field(max_length=24)
    note: str | None = Field(default=None, max_length=4000)   # hard cap; the service enforces the 1000-character rule


class PrivacyRequestView(_Strict):
    public_id: str
    request_type: str
    type_label: str
    status: str
    result_category: str | None
    created_at: str | None
    updated_at: str | None


class PrivacyRequestList(_Strict):
    items: list[PrivacyRequestView]
    total: int
    page: int
    page_size: int


class LegalAcceptanceInfo(_Strict):
    version: str
    accepted_at: str | None
    source: str
    is_current: bool


class LegalDocView(_Strict):
    code: str
    title: str
    path: str
    current_version: str | None
    effective_at: str | None
    version_is_baseline: bool | None
    accepted_current: bool
    last_acceptance: LegalAcceptanceInfo | None


class LegalStatus(_Strict):
    documents: list[LegalDocView]


class LegalHistoryItem(_Strict):
    """05E: one recorded acknowledgement of one document version. ``content_hash`` and ``version_effective_at`` are null for baseline versions."""

    document: str
    title: str
    version: str
    version_state: str
    is_baseline: bool
    content_hash: str | None
    version_effective_at: str | None
    accepted_at: str | None
    source: str
    is_current: bool
    current_version: str | None


class LegalHistoryScope(_Strict):
    records: str
    optional_processing_consent_recorded: bool
    back_filled: bool
    note: str


class LegalHistory(_Strict):
    history: list[LegalHistoryItem]
    scope: LegalHistoryScope
