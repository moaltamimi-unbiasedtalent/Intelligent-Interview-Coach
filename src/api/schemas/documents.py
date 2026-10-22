"""Typed contracts for private documents, claims, stories & export (Capstone P4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.locales import DocumentLanguage

__all__ = [
    "DocumentSummary", "DocumentVersionOut", "ClaimOut", "DocumentDetail",
    "DocumentListResponse", "ClaimReviewRequest", "StoryOut", "StoryListResponse",
    "StoryCreateRequest", "StoryDraftRequest", "StoryUpdateRequest", "DeleteResponse",
    "StoryEvidenceRequest", "StorySuggestRequest", "StorySuggestion", "StorySuggestResponse", "StoryTagsResponse",
]

DocCategory = Literal["cv", "job_description", "portfolio", "company_brief", "other"]
Locale = DocumentLanguage  # OCR/document language, NOT the app locale (see src/locales.py)


class DocumentSummary(BaseModel):
    id: int
    category: str
    title: str
    status: str
    current_version: int
    updated_at: str | None = None
    # P10B Wave 3: the current version's failure taxonomy + extraction origin, so the
    # inventory can render a localized, actionable state without fetching the full detail.
    failure_kind: str | None = None
    extraction_origin: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


class DocumentVersionOut(BaseModel):
    version: int
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: int | None = None
    extraction_origin: str | None = None
    status: str
    failure_reason: str | None = None
    failure_kind: str | None = None
    language_hint: str | None = None


class ClaimOut(BaseModel):
    id: int
    document_id: int
    version_id: int
    claim_type: str
    text: str
    edited_text: str | None = None
    display_text: str
    source_page: int | None = None
    source_section: str | None = None
    review_state: str


class DocumentDetail(BaseModel):
    id: int
    category: str
    title: str
    status: str
    current_version: int
    created_at: str | None = None
    versions: list[DocumentVersionOut]
    claims: list[ClaimOut]


class ClaimReviewRequest(BaseModel):
    action: Literal["accept", "edit", "reject", "reset"]
    edited_text: str | None = Field(default=None, max_length=2000)


class StoryOut(BaseModel):
    id: int
    title: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    competencies: list[str] = Field(default_factory=list)
    status: str
    evidence_state: str
    evidence_claim_ids: list[int] = Field(default_factory=list)
    # 04A. ``verification`` is DERIVED on every read: evidence_verified (a live document claim), source_revoked, answer_linked (the candidate's own practice
    # answer, weaker than a document), self_confirmed (the candidate's attestation, NOT evidence) or unverified.
    verification: str = "unverified"
    evidence_answer_ids: list[int] = Field(default_factory=list)
    opportunity_id: int | None = None
    archived_at: str | None = None
    confirmed_at: str | None = None
    use_count: int = 0
    last_used_at: str | None = None
    quality_prompts: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class StoryListResponse(BaseModel):
    stories: list[StoryOut]


class StoryCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    status: Literal["source_backed", "user_created", "model_suggested"] = "user_created"
    situation: str | None = Field(default=None, max_length=4000)
    task: str | None = Field(default=None, max_length=4000)
    action: str | None = Field(default=None, max_length=4000)
    result: str | None = Field(default=None, max_length=4000)
    competencies: list[str] = Field(default_factory=list, max_length=40)
    claim_ids: list[int] = Field(default_factory=list, max_length=50)
    opportunity_id: int | None = Field(default=None, ge=1)


class StoryDraftRequest(BaseModel):
    title: str = Field(default="Untitled story", max_length=255)
    claim_ids: list[int] = Field(min_length=1, max_length=50)
    opportunity_id: int | None = Field(default=None, ge=1)


class StoryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    situation: str | None = Field(default=None, max_length=4000)
    task: str | None = Field(default=None, max_length=4000)
    action: str | None = Field(default=None, max_length=4000)
    result: str | None = Field(default=None, max_length=4000)
    competencies: list[str] | None = Field(default=None, max_length=40)
    # Present (even null) = set or clear the Opportunity link; absent = leave it unchanged.
    opportunity_id: int | None = Field(default=None, ge=1)


class StoryEvidenceRequest(BaseModel):
    model_config = {"extra": "forbid"}
    kind: Literal["claim", "answer"]
    ref_id: int = Field(ge=1)


class StorySuggestRequest(BaseModel):
    """Words describing the interview (role, competencies, themes). A POST so the words are never in a URL or an access log."""
    model_config = {"extra": "forbid"}
    terms: list[str] = Field(default_factory=list, max_length=20)
    opportunity_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=5, ge=1, le=10)


class StorySuggestion(BaseModel):
    id: int
    title: str
    verification: str
    competencies: list[str] = Field(default_factory=list)
    matched: list[str] = Field(default_factory=list)
    requires_approval: bool = True


class StorySuggestResponse(BaseModel):
    suggestions: list[StorySuggestion]


class StoryTagsResponse(BaseModel):
    tags: list[str]


class DeleteResponse(BaseModel):
    deleted: bool
