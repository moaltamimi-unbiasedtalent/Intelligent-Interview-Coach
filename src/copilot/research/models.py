"""Typed contract for bounded external current-market research (Phase 7F).

One Agent tool — ``ResearchCurrentMarket`` — routes to bounded providers (an authorized market
API, and a validated company/official public-web fetcher). These models are the ONLY shapes that
cross the boundary: the LLM never chooses raw URLs/endpoints, and providers never return raw
payloads. Everything here is safe, serialisable, source-labelled and freshness-stamped.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResearchIntent(str, Enum):
    """What kind of CURRENT/external evidence the question needs."""

    JOB_MARKET = "job_market"                # current openings / market activity
    ADVERTISED_SALARY = "advertised_salary"  # live advertised salary ranges
    CURRENT_VACANCIES = "current_vacancies"  # count of current matching adverts
    COMPANY_CONTEXT = "company_context"      # what a company says about itself (its URL)
    HIRING_ACTIVITY = "hiring_activity"      # is a company hiring for X


class SourceCategory(str, Enum):
    """Deterministic external source categories (no generic web / social / scraped sites)."""

    AUTHORIZED_MARKET_API = "authorized_market_api"   # Adzuna
    OFFICIAL_PUBLIC_WEB = "official_public_web"       # registered official domains
    COMPANY_OFFICIAL_WEB = "company_official_web"     # a validated company domain


class ResearchStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"


class Geography(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    country: str | None = Field(default=None, description="ISO-3166 alpha-2, e.g. DE/US/UK.")
    region: str | None = None
    city: str | None = None


class CurrentMarketResearchRequest(BaseModel):
    """Bounded, typed request. NO arbitrary headers/method/body/URL DSL/credentials (§5)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    intent: ResearchIntent
    role: str | None = Field(default=None, max_length=120)
    location: Geography | None = None
    company: str | None = Field(default=None, max_length=120)
    company_url: str | None = Field(default=None, max_length=500,
                                    description="Explicit public company URL (company_context only).")
    industry: str | None = Field(default=None, max_length=120)
    time_horizon_days: int | None = Field(default=None, ge=1, le=365)
    results_limit: int = Field(default=10, ge=1, le=25)  # hard-capped; never bulk-harvest (§13)


class AdvertisedSalary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    is_predicted: bool | None = Field(default=None, description="Provider-predicted, not disclosed.")


class ExternalEvidence(BaseModel):
    """One bounded, provenance-preserving external evidence item (never a raw payload, §6)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_type: SourceCategory
    provider: str                              # e.g. "adzuna", "company_web", "official_web"
    title: str
    public_url: str | None = None              # sanitised; never an authenticated API URL (§39)
    snippet: str | None = Field(default=None, max_length=1000)  # bounded, sanitised text only
    retrieved_at: datetime
    effective_date: date | None = None         # listing created_at / publication date if known
    country: str | None = None
    region: str | None = None
    company: str | None = None
    role: str | None = None
    category: str | None = None
    advertised_salary: AdvertisedSalary | None = None
    source_record_id: str                      # stable id for this evidence item
    metadata: dict = Field(default_factory=dict)


class SampleStatistic(BaseModel):
    """An aggregate over a BOUNDED sample of adverts — never presented as a population stat (§16)."""

    model_config = ConfigDict(extra="forbid")
    label: str                                 # e.g. "advertised salary (sample median)"
    value: float | None = None
    currency: str | None = None
    sample_size: int = 0
    salary_disclosure_count: int = 0
    query: str | None = None
    location: str | None = None
    retrieved_at: datetime | None = None


class CurrentMarketResearchResult(BaseModel):
    """Typed tool result. Compact + safe for LangGraph state and candidate citations (§6/§55)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: ResearchStatus
    intent: ResearchIntent
    provider: str | None = None
    source_category: SourceCategory | None = None
    retrieved_at: datetime | None = None
    effective_as_of: str | None = None
    geography: Geography | None = None
    role: str | None = None
    company: str | None = None
    result_count: int = 0
    provider_reported_total: int | None = Field(
        default=None, description="Provider's matching-advert count — coverage, NOT all vacancies (§17).")
    summary_facts: list[str] = Field(default_factory=list)
    sample_statistic: SampleStatistic | None = None
    evidence: list[ExternalEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    cache_hit: bool = False
