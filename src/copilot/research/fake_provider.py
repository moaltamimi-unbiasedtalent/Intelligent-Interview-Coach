"""Deterministic, offline research provider for development and tests (P10B Wave 5).

Returns fixture `CurrentMarketResearchResult`s WITHOUT any network call, so the Company
Intelligence experience can be exercised end to end with 0 paid/live provider calls. It is
NEVER labelled live: `health()` reports ``fixture=True`` and results carry a warning that the
data is a deterministic fixture. Wire it in only when ``COMPANY_RESEARCH_FIXTURE`` is set (dev)
or via a dependency override (tests); production uses the real, SSRF-safe providers.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import urlparse

from src.copilot.research.models import (
    CurrentMarketResearchRequest,
    CurrentMarketResearchResult,
    ExternalEvidence,
    ResearchIntent,
    ResearchStatus,
    SourceCategory,
)

__all__ = ["FakeCompanyResearchProvider"]

_FIXTURE_UTC = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)


class FakeCompanyResearchProvider:
    """Serves COMPANY_CONTEXT from a deterministic fixture (no network, no credentials)."""

    provider_name = "company_web"
    source_category = SourceCategory.COMPANY_OFFICIAL_WEB

    def supports(self, request: CurrentMarketResearchRequest) -> bool:
        # Mirror the real CompanyWebResearchProvider: only COMPANY_CONTEXT with an explicit URL.
        return request.intent is ResearchIntent.COMPANY_CONTEXT and bool(request.company_url)

    def research(self, request: CurrentMarketResearchRequest) -> CurrentMarketResearchResult:
        url = request.company_url or "https://example.com"
        host = urlparse(url).netloc or "example.com"
        company = request.company or host
        ev = [
            ExternalEvidence(
                source_type=SourceCategory.COMPANY_OFFICIAL_WEB, provider="company_web",
                title=f"{company} - About",
                public_url=f"https://{host}/about",
                snippet=(f"{company} builds software products for small businesses and describes "
                         "its business as helping teams collaborate."),
                retrieved_at=_FIXTURE_UTC, effective_date=None, company=company,
                source_record_id="fixture-about", metadata={"self_reported": True}),
            ExternalEvidence(
                source_type=SourceCategory.COMPANY_OFFICIAL_WEB, provider="company_web",
                title=f"{company} - Values",
                public_url=f"https://{host}/culture",
                snippet=("Our values: customer obsession, integrity and sustainability guide how "
                         "we work."),
                retrieved_at=_FIXTURE_UTC, effective_date=None, company=company,
                source_record_id="fixture-values", metadata={"self_reported": True}),
            ExternalEvidence(
                source_type=SourceCategory.COMPANY_OFFICIAL_WEB, provider="company_web",
                title=f"{company} - Newsroom",
                public_url=f"https://{host}/news",
                snippet=(f"In Q1 2026 {company} announced a new partnership to expand into new "
                         "markets."),
                retrieved_at=_FIXTURE_UTC, effective_date=date(2026, 1, 10), company=company,
                source_record_id="fixture-news", metadata={"self_reported": True}),
        ]
        return CurrentMarketResearchResult(
            status=ResearchStatus.READY, intent=ResearchIntent.COMPANY_CONTEXT,
            provider="company_web", source_category=SourceCategory.COMPANY_OFFICIAL_WEB,
            retrieved_at=_FIXTURE_UTC, company=company, geography=request.location,
            result_count=len(ev), evidence=ev,
            warnings=["Deterministic fixture data (not a live fetch)."])

    def health(self) -> dict:
        return {"provider": self.provider_name, "source_category": self.source_category.value,
                "configured": True, "fixture": True}
