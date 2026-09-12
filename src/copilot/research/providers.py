"""External research provider interface (Phase 7F, §8).

The Agent tool never talks to a provider directly — it calls the ExternalResearchService, which
routes a typed request to the ONE provider that ``supports`` it. Each provider owns its bounded
source category and returns typed evidence, never a raw payload.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.copilot.research.models import (
    CurrentMarketResearchRequest,
    CurrentMarketResearchResult,
    SourceCategory,
)


@runtime_checkable
class ExternalResearchProvider(Protocol):
    provider_name: str
    source_category: SourceCategory

    def supports(self, request: CurrentMarketResearchRequest) -> bool:
        """True if this provider can serve the request's intent + inputs (deterministic)."""
        ...

    def research(self, request: CurrentMarketResearchRequest) -> CurrentMarketResearchResult:
        """Perform the bounded research and return a typed, sanitised result. Never raises for a
        provider/network failure — returns an ``unavailable``/``rate_limited`` result instead."""
        ...

    def health(self) -> dict:
        """Safe, credential-free readiness view (configured? category? capabilities)."""
        ...
