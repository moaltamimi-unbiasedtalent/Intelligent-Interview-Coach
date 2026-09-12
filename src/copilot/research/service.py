"""External current-market research service (Phase 7F, §2/§8).

The ONE place that routes a typed ``CurrentMarketResearchRequest`` to the ONE bounded provider
that supports it, applies a short TTL cache, and returns a typed, sanitised result. The Agent
tool calls THIS service — it never chooses providers/endpoints/URLs. Provider/network failures
are isolated into an ``unavailable``/``rate_limited`` result, never an exception (§47).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from src.copilot.research import cache as _cache
from src.copilot.research.adzuna_provider import AdzunaResearchProvider
from src.copilot.research.company_provider import CompanyWebResearchProvider
from src.copilot.research.models import (
    CurrentMarketResearchRequest,
    CurrentMarketResearchResult,
    ResearchStatus,
)
from src.copilot.research.providers import ExternalResearchProvider


class ExternalResearchService:
    """Deterministic provider router with a bounded TTL cache."""

    def __init__(self, providers: list[ExternalResearchProvider], *, enabled: bool = True,
                 cache_ttl_seconds: int = _cache.DEFAULT_TTL_SECONDS) -> None:
        self._providers = providers
        self._enabled = enabled
        self._cache_ttl = cache_ttl_seconds

    @classmethod
    def default(cls, *, enabled: bool = True, company_web_enabled: bool = True,
                cache_ttl_seconds: int = _cache.DEFAULT_TTL_SECONDS) -> "ExternalResearchService":
        providers: list[ExternalResearchProvider] = [AdzunaResearchProvider()]
        if company_web_enabled:
            providers.append(CompanyWebResearchProvider(enabled=True))
        return cls(providers, enabled=enabled, cache_ttl_seconds=cache_ttl_seconds)

    def health(self) -> dict:
        return {"enabled": self._enabled,
                "providers": [p.health() for p in self._providers]}

    def _select(self, request: CurrentMarketResearchRequest):
        return next((p for p in self._providers if p.supports(request)), None)

    def research(self, request: CurrentMarketResearchRequest) -> CurrentMarketResearchResult:
        if not self._enabled:
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=request.intent,
                warnings=["External current-market research is disabled."])
        provider = self._select(request)
        if provider is None:
            return CurrentMarketResearchResult(
                status=ResearchStatus.INSUFFICIENT_EVIDENCE, intent=request.intent,
                warnings=["No permitted provider can serve this request "
                          "(e.g. company_context needs an explicit company_url)."])

        loc = request.location
        key = _cache.cache_key(
            provider.provider_name, request.intent.value, role=request.role,
            country=(loc.country if loc else None), region=(loc.region if loc else None),
            company=(request.company_url or request.company), limit=request.results_limit)
        cached = _cache.read(key, ttl_seconds=self._cache_ttl)
        if cached is not None:
            try:
                result = CurrentMarketResearchResult.model_validate(cached)
                result.cache_hit = True
                return result
            except Exception:  # noqa: BLE001 - a bad cache entry is ignored, never fatal
                pass

        try:
            result = provider.research(request)
        except Exception:  # noqa: BLE001 - provider failure isolation (§47)
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=request.intent,
                provider=provider.provider_name,
                retrieved_at=datetime.now(timezone.utc),
                warnings=["The research provider failed."])

        # Cache only sanitised, successful/partial snapshots (never credentials/raw payloads, §20).
        if result.status in (ResearchStatus.READY, ResearchStatus.PARTIAL,
                             ResearchStatus.INSUFFICIENT_EVIDENCE):
            _cache.write(key, result.model_dump(mode="json"))
        return result


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def default_research_service() -> ExternalResearchService:
    """Build the service from environment flags (§79). External research is enabled by default
    (providers degrade gracefully: Adzuna without credentials → unavailable). Company-web
    research is enabled by default because the SSRF/robots safety layer is in place."""
    ttl_raw = os.environ.get("EXTERNAL_RESEARCH_CACHE_TTL_SECONDS", "").strip()
    try:
        ttl = int(ttl_raw) if ttl_raw else _cache.DEFAULT_TTL_SECONDS
    except ValueError:
        ttl = _cache.DEFAULT_TTL_SECONDS
    return ExternalResearchService.default(
        enabled=_flag("EXTERNAL_RESEARCH_ENABLED", True),
        company_web_enabled=_flag("COMPANY_WEB_RESEARCH_ENABLED", True),
        cache_ttl_seconds=max(60, min(ttl, 86400)))
