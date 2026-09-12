"""Bounded external current-market research (Phase 7F).

One Agent tool (``ResearchCurrentMarket``) → :class:`ExternalResearchService` → bounded providers
(Adzuna authorized market API; SSRF-safe company/official web fetcher). Never generic web search,
never a crawler, never permanent KB ingestion. Nothing here is imported by the runtime retrieval
path; external data is request-time, ephemeral evidence only.
"""

from __future__ import annotations

from src.copilot.research.models import (
    CurrentMarketResearchRequest,
    CurrentMarketResearchResult,
    ExternalEvidence,
    Geography,
    ResearchIntent,
    ResearchStatus,
    SourceCategory,
)
from src.copilot.research.service import ExternalResearchService

__all__ = [
    "CurrentMarketResearchRequest",
    "CurrentMarketResearchResult",
    "ExternalEvidence",
    "Geography",
    "ResearchIntent",
    "ResearchStatus",
    "SourceCategory",
    "ExternalResearchService",
]
