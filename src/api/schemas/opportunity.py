"""API schemas for the candidate Opportunity model (P10B Wave 6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpportunityCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    target_role: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    company_location: str | None = Field(default=None, max_length=200)
    company_country: str | None = Field(default=None, max_length=2)
    company_domain: str | None = Field(default=None, max_length=500)
    job_description_document_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=4000)


class OpportunityUpdateRequest(BaseModel):
    """Partial update; only provided fields change. `status` is a bounded lifecycle value."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    target_role: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    company_location: str | None = Field(default=None, max_length=200)
    company_country: str | None = Field(default=None, max_length=2)
    company_domain: str | None = Field(default=None, max_length=500)
    job_description_document_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, max_length=24)


class OpportunityOut(BaseModel):
    id: int
    title: str
    target_role: str
    company_name: str | None = None
    company_location: str | None = None
    company_country: str | None = None
    company_domain: str | None = None
    job_description_document_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    archived_at: str | None = None


class OpportunityListResponse(BaseModel):
    opportunities: list[OpportunityOut]


class OpportunityOverviewOut(OpportunityOut):
    jd_available: bool = False
    interview_ids: list[int] = Field(default_factory=list)
    interview_count: int = 0


class OpportunityContextOut(BaseModel):
    opportunity_id: int
    title: str
    target_role: str
    company_name: str | None = None
    company_location: str | None = None
    company_country: str | None = None
    company_domain: str | None = None
    job_description_document_id: int | None = None
    jd_available: bool = False
