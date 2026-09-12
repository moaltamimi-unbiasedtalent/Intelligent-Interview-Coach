"""Company / official public-web research provider (Phase 7F, §22–§42).

Bounded, SSRF-safe fetch of a FEW same-origin public pages from an EXPLICIT, validated company or
official URL — never discovered from a name, never a crawler, never a search engine. Content is
authoritative only about what the company/site SAYS about itself (self-reported, not independent
verification, §42). Returns bounded evidence with a prompt-injection flag on each snippet (§34).
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from src.copilot.research.content_guard import guard_external_text
from src.copilot.research.models import (
    CurrentMarketResearchRequest,
    CurrentMarketResearchResult,
    ExternalEvidence,
    ResearchIntent,
    ResearchStatus,
    SourceCategory,
)
from src.copilot.research.web_fetch import WebFetcher, WebFetchError, validate_url

# Candidate same-origin paths to try (bounded), most useful first (§23). Max pages capped below.
_CANDIDATE_PATHS = ("", "/careers", "/jobs", "/about", "/company", "/culture")
_MAX_PAGES = 4

# Registered official public domains permitted for OFFICIAL_PUBLIC_WEB (no generic gov search, §37).
OFFICIAL_DOMAINS = ("destatis.de", "arbeitsagentur.de", "europa.eu", "bls.gov",
                    "ons.gov.uk", "ec.europa.eu")


def _registered_official(host: str) -> bool:
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)


class CompanyWebResearchProvider:
    provider_name = "company_web"
    source_category = SourceCategory.COMPANY_OFFICIAL_WEB

    def __init__(self, fetcher: WebFetcher | None = None, *, enabled: bool = True) -> None:
        self._fetcher = fetcher or WebFetcher()
        self._enabled = enabled

    def supports(self, request: CurrentMarketResearchRequest) -> bool:
        # Only for company-context intent WITH an explicit URL — never invents a domain (§22).
        return (request.intent == ResearchIntent.COMPANY_CONTEXT
                and bool(request.company_url))

    def health(self) -> dict:
        return {"provider": self.provider_name, "source_category": self.source_category.value,
                "enabled": self._enabled, "max_pages": _MAX_PAGES,
                "official_domains": list(OFFICIAL_DOMAINS)}

    def research(self, request: CurrentMarketResearchRequest) -> CurrentMarketResearchResult:
        intent = request.intent
        now = datetime.now(timezone.utc)
        if not self._enabled:
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=intent, provider=self.provider_name,
                source_category=self.source_category,
                warnings=["Company-web research is disabled."])
        base = request.company_url or ""
        try:
            norm_base, host = validate_url(base)
        except WebFetchError as exc:
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=intent, provider=self.provider_name,
                source_category=self.source_category,
                warnings=[f"Company URL rejected ({exc.category})."])

        source_type = (SourceCategory.OFFICIAL_PUBLIC_WEB if _registered_official(host)
                       else SourceCategory.COMPANY_OFFICIAL_WEB)
        origin = f"{urlparse(norm_base).scheme}://{urlparse(norm_base).netloc}"
        # Bounded same-origin page set: the provided page + a few common sections.
        seen: set[str] = set()
        targets: list[str] = []
        for path in _CANDIDATE_PATHS:
            u = norm_base if path == "" else urljoin(origin + "/", path.lstrip("/"))
            if u not in seen:
                seen.add(u); targets.append(u)
            if len(targets) >= _MAX_PAGES:
                break

        evidence: list[ExternalEvidence] = []
        warnings: list[str] = []
        robots_hits = 0
        for i, url in enumerate(targets):
            try:
                page = self._fetcher.fetch_page(url)
            except WebFetchError as exc:
                if exc.category == "robots_disallowed":
                    robots_hits += 1
                # A missing section (404) / robots / type mismatch is normal — skip, don't fail.
                warnings.append(f"{url.rsplit('/', 1)[-1] or 'home'}: {exc.category}")
                continue
            except Exception:  # noqa: BLE001 - isolate any fetch failure
                warnings.append("fetch_error")
                continue
            guarded = guard_external_text(page.text)
            if not guarded.text:
                continue
            evidence.append(ExternalEvidence(
                source_type=source_type, provider=self.provider_name,
                title=page.title or host, public_url=page.url, snippet=guarded.text,
                retrieved_at=now, company=request.company or host, role=request.role,
                source_record_id=f"web:{host}:{i}",
                metadata={"self_reported": True, "injection_flagged": guarded.flagged,
                          "injection_indicators": guarded.indicators}))
            if guarded.flagged:
                warnings.append("A fetched page contained instruction-like text; it is treated "
                                "strictly as quoted evidence, never as instructions.")

        if robots_hits and not evidence:
            return CurrentMarketResearchResult(
                status=ResearchStatus.UNAVAILABLE, intent=intent, provider=self.provider_name,
                source_category=source_type, warnings=["robots_disallowed"] + warnings)
        status = ResearchStatus.READY if evidence else ResearchStatus.INSUFFICIENT_EVIDENCE
        return CurrentMarketResearchResult(
            status=status, intent=intent, provider=self.provider_name, source_category=source_type,
            retrieved_at=now, effective_as_of="company self-reported (as of retrieval)",
            role=request.role, company=request.company or host,
            result_count=len(evidence), evidence=evidence, warnings=warnings,
            summary_facts=(["Evidence is self-reported by the source; not independent verification."]
                           if evidence else []))
