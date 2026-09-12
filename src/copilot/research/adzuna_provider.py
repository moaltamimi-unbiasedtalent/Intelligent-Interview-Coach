"""Adzuna current-market research provider (Phase 7F).

Wraps the Phase 7A.1 ``AdzunaProvider`` (unchanged) and normalises its job-search results into
bounded :class:`ExternalEvidence`. Adzuna is an ``authorized_market_api`` — it supplies CURRENT
ADVERTISED-market signals (advertised salary ranges, current adverts, provider-reported counts),
NEVER official observed earnings or the foundational occupation taxonomy (§10/§15). Credentials
are env-only and never logged/serialised/exposed; candidate-facing URLs are the public
``redirect_url`` only — never the authenticated API URL (§9/§39).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.copilot.knowledge.providers import adzuna as az
from src.copilot.research.content_guard import guard_external_text
from src.copilot.research.models import (
    AdvertisedSalary,
    CurrentMarketResearchRequest,
    CurrentMarketResearchResult,
    ExternalEvidence,
    Geography,
    ResearchIntent,
    ResearchStatus,
    SampleStatistic,
    SourceCategory,
)

# Intents Adzuna can serve (current market / advertised salary / current vacancies / hiring).
_SUPPORTED = {ResearchIntent.JOB_MARKET, ResearchIntent.ADVERTISED_SALARY,
              ResearchIntent.CURRENT_VACANCIES, ResearchIntent.HIRING_ACTIVITY}


def _public_url(job: dict) -> str | None:
    """Only the provider's public redirect URL — never an authenticated API URL (§39)."""
    url = job.get("redirect_url")
    if isinstance(url, str) and url.startswith("https://"):
        return url.split("?", 1)[0]  # strip tracking/query params
    return None


def _parse_created(job: dict):
    raw = job.get("created")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


class AdzunaResearchProvider:
    provider_name = "adzuna"
    source_category = SourceCategory.AUTHORIZED_MARKET_API

    def __init__(self, provider: az.AdzunaProvider | None = None) -> None:
        # Injectable underlying provider (tests pass one with a fake transport → no network).
        self._provider = provider or az.AdzunaProvider()

    def supports(self, request: CurrentMarketResearchRequest) -> bool:
        return request.intent in _SUPPORTED

    def health(self) -> dict:
        return {"provider": self.provider_name, "source_category": self.source_category.value,
                "configured": az.credentials_configured(),
                # Verified in 7A.1 for Germany; other endpoints/countries are NOT_TESTED.
                "capabilities": {"de:search": "VERIFIED", "de:categories": "VERIFIED",
                                 "de:version": "NOT_REQUIRED"}}

    def research(self, request: CurrentMarketResearchRequest) -> CurrentMarketResearchResult:
        intent = request.intent
        country = (request.location.country if request.location else None) or "de"
        where = None
        if request.location:
            where = request.location.city or request.location.region
        if not az.credentials_configured():
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=intent, provider=self.provider_name,
                source_category=self.source_category,
                warnings=["Adzuna credentials are not configured (ADZUNA_APP_ID/ADZUNA_APP_KEY)."])
        try:
            res = self._provider.search_jobs(
                country=country.lower(), what=(request.role or request.industry or "").strip(),
                where=(where or "").strip(), results_per_page=request.results_limit)
        except az.AdzunaError as exc:
            status = (ResearchStatus.RATE_LIMITED if exc.category == "rate_limit"
                      else ResearchStatus.UNAVAILABLE)
            return CurrentMarketResearchResult(
                status=status, intent=intent, provider=self.provider_name,
                source_category=self.source_category,
                warnings=[f"Adzuna request failed ({exc.category})."])
        except Exception:  # noqa: BLE001 - provider failure is isolated (§47)
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=intent, provider=self.provider_name,
                source_category=self.source_category, warnings=["Adzuna request failed."])

        data = res.data or {}
        jobs = (data.get("results") or [])[: request.results_limit]
        now = datetime.now(timezone.utc)
        evidence: list[ExternalEvidence] = []
        disclosed: list[float] = []
        for i, job in enumerate(jobs):
            sal = az.parse_salary(job)
            smin, smax = sal.get("salary_min"), sal.get("salary_max")
            predicted = sal.get("salary_is_predicted")
            if not predicted and isinstance(smin, (int, float)) and isinstance(smax, (int, float)):
                disclosed.append((smin + smax) / 2)
            snippet = guard_external_text(str(job.get("description") or "")).text or None
            evidence.append(ExternalEvidence(
                source_type=self.source_category, provider=self.provider_name,
                title=str(job.get("title") or "Advertised role")[:200],
                public_url=_public_url(job), snippet=snippet, retrieved_at=now,
                effective_date=_parse_created(job),
                country=country.upper(),
                region=(job.get("location", {}) or {}).get("display_name"),
                company=(job.get("company", {}) or {}).get("display_name"),
                role=request.role,
                category=(job.get("category", {}) or {}).get("label"),
                advertised_salary=AdvertisedSalary(
                    salary_min=smin, salary_max=smax,
                    currency=_currency_for(country), is_predicted=bool(predicted)),
                source_record_id=f"adzuna:{country.lower()}:{job.get('id') or i}",
                metadata={"contract_type": job.get("contract_type")}))

        provider_total = data.get("count") if isinstance(data.get("count"), int) else None
        result = CurrentMarketResearchResult(
            status=ResearchStatus.READY if evidence else ResearchStatus.INSUFFICIENT_EVIDENCE,
            intent=intent, provider=self.provider_name, source_category=self.source_category,
            retrieved_at=now, effective_as_of="current advertised-market snapshot",
            geography=Geography(country=country.upper(), city=(where or None)),
            role=request.role, result_count=len(evidence),
            provider_reported_total=provider_total, evidence=evidence)

        # For advertised-salary intent, compute an HONEST sample statistic (never a population
        # median), clearly labelled with sample size + disclosure count (§16).
        if intent == ResearchIntent.ADVERTISED_SALARY and disclosed:
            disclosed.sort()
            mid = disclosed[len(disclosed) // 2]
            result.sample_statistic = SampleStatistic(
                label="advertised salary (sample median of disclosed adverts)",
                value=round(mid, 2), currency=_currency_for(country),
                sample_size=len(evidence), salary_disclosure_count=len(disclosed),
                query=(request.role or ""), location=(where or country.upper()), retrieved_at=now)
        if provider_total is not None:
            result.summary_facts.append(
                f"Provider-reported matching advertisements: {provider_total} "
                f"(Adzuna coverage — not all vacancies in the market).")
        return result


def _currency_for(country: str) -> str:
    return {"de": "EUR", "gb": "GBP", "uk": "GBP", "us": "USD"}.get(country.lower(), "")
