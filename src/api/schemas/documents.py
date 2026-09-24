"""Typed contracts for private documents, claims, stories & export (Capstone P4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "DocumentSummary", "DocumentVersionOut", "ClaimOut", "DocumentDetail",
    "DocumentListResponse", "ClaimReviewRequest", "StoryOut", "StoryListResponse",
    "StoryCreateRequest", "StoryDraftRequest", "StoryUpdateRequest", "DeleteResponse",
]

DocCategory = Literal["cv", "job_description", "portfolio", "company_brief", "other"]
Locale = Literal["en", "de", "fr", "es", "it", "pt", "nl"]


class DocumentSummary(BaseModel):
    id: int
    category: str
    title: str
    status: str
    current_version: int
    updated_at: str | None = None


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
    competencies: list[str] = Field(default_factory=list)
    claim_ids: list[int] = Field(default_factory=list)


class StoryDraftRequest(BaseModel):
    title: str = Field(default="Untitled story", max_length=255)
    claim_ids: list[int] = Field(min_length=1)


class StoryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    situation: str | None = Field(default=None, max_length=4000)
    task: str | None = Field(default=None, max_length=4000)
    action: str | None = Field(default=None, max_length=4000)
    result: str | None = Field(default=None, max_length=4000)
    competencies: list[str] | None = None


class DeleteResponse(BaseModel):
    deleted: bool
