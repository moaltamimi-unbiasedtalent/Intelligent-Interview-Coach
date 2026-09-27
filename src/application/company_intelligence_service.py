"""Candidate-facing Company Intelligence (P10B Wave 5).

Turns the existing, security-hardened external research engine (`src/copilot/research/*`,
Phase 7F) into a DIRECTABLE, candidate-facing company-intelligence report - without building a
second research architecture and without weakening any safety boundary.

What this layer adds on top of `ExternalResearchService`:

* A candidate-shaped report (snapshot / business & market / recent developments / culture /
  role relevance / interview preparation / sources / limitations) built by orchestrating the
  existing governed research intents (COMPANY_CONTEXT + optional market intents).
* An EXPLICIT claim taxonomy the UI can never blur: FACT (evidence-backed, from official/
  company sources), REVIEW (third-party employee-review sentiment - NOT integrated in Wave 5),
  and MODEL_INFERENCE (deterministic, source-derived interview suggestions, never presented as a
  verified company fact).
* Deterministic company IDENTITY / disambiguation: a company is only researched against an
  explicit, validated website/domain. A name-only request is never silently resolved to a
  similarly named company - the report asks for the official website instead.
* Honest PROVIDER STATUS for every source the founder named (official web, Adzuna market,
  Glassdoor, Kununu, Google) so the UI can show configured / unavailable / not-integrated
  without ever faking a successful research state.

Everything here is deterministic and makes NO model call: MODEL_INFERENCE items are derived from
retrieved evidence by simple, auditable rules. Retrieved content stays untrusted DATA (the
underlying engine already SSRF-validates URLs, honours robots, strips scripts and flags prompt
injection); this layer never places document/web text into a model prompt. Owner scoping for the
optional JD is enforced by the injected resolver (a foreign/missing document yields no text).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from urllib.parse import quote_plus, urlparse

from pydantic import BaseModel, ConfigDict, Field

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
    "ClaimKind",
    "ProviderState",
    "IdentityConfidence",
    "ReportStatus",
    "CompanyIntelligenceQuery",
    "SourceRef",
    "Claim",
    "ProviderStatus",
    "CompanyIdentity",
    "CompanySnapshot",
    "InterviewPreparation",
    "CompanyIntelligenceReport",
    "CompanyIntelligenceService",
]


# --------------------------------------------------------------------------- taxonomy


class ClaimKind(str, Enum):
    """The kind of statement - the UI must render these visibly differently (§6)."""

    FACT = "fact"                       # evidence-backed, from an official/company source
    REVIEW = "review"                   # third-party employee-review sentiment (not integrated)
    MODEL_INFERENCE = "model_inference"  # source-derived suggestion, NEVER a verified fact


class ProviderState(str, Enum):
    """Honest per-source status - deterministic mode is never labelled live (§16)."""

    CONFIGURED = "configured"              # ready to serve (credentials/inputs present)
    UNAVAILABLE = "unavailable"            # configured concept but not usable now (e.g. no key)
    DISABLED = "disabled"                  # switched off by env/operator
    PARTIAL = "partial"                    # returned some but not all evidence
    FAILED = "failed"                      # attempted and errored (isolated, never raised)
    STALE = "stale"                        # served from cache past a freshness hint
    NOT_INTEGRATED = "not_integrated"      # provider review required (ToS/licensing) - link only
    LIVE_UNVALIDATED = "live_unvalidated"  # adapter exists; live path never validated here


class IdentityConfidence(str, Enum):
    CONFIRMED = "confirmed"                  # researched against an explicit validated website
    NEEDS_CLARIFICATION = "needs_clarification"  # name-only; official website required


class ReportStatus(str, Enum):
    READY = "ready"                        # company evidence retrieved
    PARTIAL = "partial"                    # some evidence; at least one provider degraded
    NEEDS_CLARIFICATION = "needs_clarification"  # identity not confirmed (no website)
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # confirmed identity but nothing found
    UNAVAILABLE = "unavailable"            # research disabled / no provider could serve


# --------------------------------------------------------------------------- request


class CompanyIntelligenceQuery(BaseModel):
    """Bounded, typed candidate request. No raw URL DSL/headers/credentials (mirrors §5)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=2, description="ISO-3166 alpha-2 hint.")
    website: str | None = Field(default=None, max_length=500,
                                description="Official company website/domain (enables web research).")
    target_role: str | None = Field(default=None, max_length=200)
    job_description_document_id: int | None = Field(default=None, ge=1)


# --------------------------------------------------------------------------- report parts


class SourceRef(BaseModel):
    """Provenance for one piece of evidence (the SOURCE panel)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str | None = None
    source_type: str                       # SourceCategory value
    provider: str
    retrieved_at: str | None = None
    effective_date: str | None = None
    self_reported: bool = False            # first-party (company said this) vs independent


class Claim(BaseModel):
    """A single statement with its kind and provenance (empty source_ids ⇒ inference)."""

    model_config = ConfigDict(extra="forbid")

    kind: ClaimKind
    text: str
    source_ids: list[str] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str                               # company_web | adzuna | glassdoor | kununu | google
    label: str
    state: ProviderState
    detail: str | None = None
    external_url: str | None = None        # a user link where copying content is not permitted


class CompanyIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    location: str | None = None
    country: str | None = None
    website: str | None = None
    domain: str | None = None
    confidence: IdentityConfidence
    note: str | None = None


class CompanySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    industry: str | None = None
    description: str | None = None
    website: str | None = None
    retrieved_at: str | None = None


class InterviewPreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[Claim] = Field(default_factory=list)          # MODEL_INFERENCE
    questions_to_ask: list[Claim] = Field(default_factory=list)  # MODEL_INFERENCE
    clarify: list[Claim] = Field(default_factory=list)          # things to verify


class CompanyIntelligenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReportStatus
    identity: CompanyIdentity
    snapshot: CompanySnapshot
    business_market: list[Claim] = Field(default_factory=list)
    recent_developments: list[Claim] = Field(default_factory=list)
    culture: list[Claim] = Field(default_factory=list)         # first-party FACTs
    review_signals: list[Claim] = Field(default_factory=list)  # REVIEW (not integrated in W5)
    role_relevance: list[Claim] = Field(default_factory=list)  # MODEL_INFERENCE
    interview_preparation: InterviewPreparation = Field(default_factory=InterviewPreparation)
    sources: list[SourceRef] = Field(default_factory=list)
    provider_statuses: list[ProviderStatus] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieved_at: str | None = None
    cache_hit: bool = False
    jd_linked: bool = False


# --------------------------------------------------------------------------- service


# Culture / values keywords used to sort first-party facts into the culture section. Deliberately
# small and language-agnostic-ish (English + common German cognates); this only ROUTES a fact into
# a section, it never invents one.
_CULTURE_HINTS = re.compile(
    r"\b(values?|culture|mission|belief|integrity|diversity|inclusion|sustainab|"
    r"kultur|werte|nachhaltig|vielfalt)\b",
    re.I,
)
_DEV_HINTS = re.compile(
    r"\b(announce|launch|acqui|partnership|funding|raised|expand|new\s|release|report|"
    r"quarter|q[1-4]\s|20\d{2})\b",
    re.I,
)


class CompanyIntelligenceService:
    """Directable company research over the governed `ExternalResearchService` (Wave 5)."""

    def __init__(
        self,
        research_service: ExternalResearchService,
        *,
        resolve_jd: Callable[[int], str | None] | None = None,
        adzuna_configured: bool = False,
    ) -> None:
        """`research_service` is the governed engine (inject a fake for deterministic tests).
        `resolve_jd` returns owner-scoped JD text for a document id, or None (foreign/missing).
        `adzuna_configured` is a safe, credential-free hint for honest provider status only."""
        self._research = research_service
        self._resolve_jd = resolve_jd
        self._adzuna_configured = adzuna_configured

    # -- public API --------------------------------------------------------

    def research(self, query: CompanyIntelligenceQuery, *, user_id: int) -> CompanyIntelligenceReport:
        """Build a candidate-facing report. Never raises for provider failure (mirrors §47)."""
        identity = self._identify(query)
        jd_keywords, jd_linked = self._jd_keywords(query, user_id=user_id)

        sources: list[SourceRef] = []
        facts: list[Claim] = []
        developments: list[Claim] = []
        culture: list[Claim] = []
        warnings: list[str] = []
        limitations: list[str] = []
        snapshot = CompanySnapshot(website=identity.website)
        company_result: CurrentMarketResearchResult | None = None
        market_result: CurrentMarketResearchResult | None = None

        # 1) Company web research - ONLY against an explicit, validated website (identity-safe).
        if identity.confidence is IdentityConfidence.CONFIRMED and identity.website:
            company_result = self._research.research(
                CurrentMarketResearchRequest(
                    intent=ResearchIntent.COMPANY_CONTEXT,
                    company=identity.company_name,
                    company_url=identity.website,
                    location=self._geo(query),
                )
            )
            # Company-fetch warnings ARE meaningful (they describe this company's page) - surface them.
            self._ingest(company_result, sources, facts, developments, culture, warnings,
                         include_warnings=True)
            if company_result.retrieved_at:
                snapshot.retrieved_at = _iso(company_result.retrieved_at)
            # Industry is not modelled by the research engine; left None rather than guessed.
            if facts:
                snapshot.description = facts[0].text[:600]
        else:
            limitations.append("company_website_missing")

        # 2) Market context - optional, role-scoped; degrades to UNAVAILABLE without credentials.
        # Its engine-internal routing notes are NOT surfaced as report warnings; the Adzuna
        # provider status reflects its outcome honestly instead.
        if query.target_role:
            market_result = self._research.research(
                CurrentMarketResearchRequest(
                    intent=ResearchIntent.JOB_MARKET,
                    role=query.target_role,
                    location=self._geo(query),
                    company=identity.company_name,
                    results_limit=5,
                )
            )
            self._ingest(market_result, sources, facts, developments, culture, warnings,
                         include_warnings=False)

        # 3) Deterministic, source-derived inference (clearly MODEL_INFERENCE).
        role_relevance = self._role_relevance(facts, query, jd_keywords)
        interview_prep = self._interview_prep(facts, developments, culture, query, jd_keywords)

        provider_statuses = self._provider_statuses(identity, company_result, market_result)
        status = self._overall_status(identity, company_result, facts)
        limitations += self._limitations(identity, company_result, facts)

        return CompanyIntelligenceReport(
            status=status,
            identity=identity,
            snapshot=snapshot,
            business_market=facts,
            recent_developments=developments,
            culture=culture,
            review_signals=[],   # REVIEW providers are NOT integrated in Wave 5 (see statuses)
            role_relevance=role_relevance,
            interview_preparation=interview_prep,
            sources=sources,
            provider_statuses=provider_statuses,
            limitations=_dedupe(limitations),
            warnings=_dedupe(warnings),
            retrieved_at=snapshot.retrieved_at,
            cache_hit=bool(company_result and company_result.cache_hit),
            jd_linked=jd_linked,
        )

    # -- identity / disambiguation ----------------------------------------

    def _identify(self, query: CompanyIntelligenceQuery) -> CompanyIdentity:
        website = _normalise_website(query.website)
        domain = urlparse(website).netloc if website else None
        if website:
            return CompanyIdentity(
                company_name=query.company_name, location=query.location,
                country=(query.country or None), website=website, domain=domain,
                confidence=IdentityConfidence.CONFIRMED,
                note="Researched against the official website you provided.",
            )
        return CompanyIdentity(
            company_name=query.company_name, location=query.location,
            country=(query.country or None), website=None, domain=None,
            confidence=IdentityConfidence.NEEDS_CLARIFICATION,
            note=("Several companies can share a name. Add the official website to research this "
                  "exact company - Ask4Mo does not guess a domain from a name."),
        )

    def _geo(self, query: CompanyIntelligenceQuery) -> Geography | None:
        if not (query.country or query.location):
            return None
        return Geography(country=(query.country or None), city=(query.location or None))

    # -- JD integration (owner-scoped; untrusted DATA; never prompted) -----

    def _jd_keywords(self, query: CompanyIntelligenceQuery, *, user_id: int) -> tuple[list[str], bool]:
        if not query.job_description_document_id or not self._resolve_jd:
            return [], False
        text = self._resolve_jd(query.job_description_document_id)  # None ⇒ foreign/missing
        if not text:
            return [], False
        return _keywords(text, limit=8), True

    # -- evidence ingest ---------------------------------------------------

    def _ingest(self, result: CurrentMarketResearchResult, sources: list[SourceRef],
                facts: list[Claim], developments: list[Claim], culture: list[Claim],
                warnings: list[str], *, include_warnings: bool) -> None:
        if include_warnings:
            warnings.extend(result.warnings or [])
        for ev in result.evidence:
            ref = self._source_ref(ev)
            sources.append(ref)
            snippet = (ev.snippet or ev.title or "").strip()
            if not snippet:
                continue
            claim = Claim(kind=ClaimKind.FACT, text=snippet[:600], source_ids=[ref.id])
            if _DEV_HINTS.search(snippet) and (ev.effective_date or ""):
                developments.append(claim)
            elif ref.self_reported and _CULTURE_HINTS.search(snippet):
                culture.append(claim)
            else:
                facts.append(claim)
        for fact in result.summary_facts or []:
            facts.append(Claim(kind=ClaimKind.FACT, text=str(fact)[:600], source_ids=[]))

    def _source_ref(self, ev: ExternalEvidence) -> SourceRef:
        self_reported = bool(ev.metadata.get("self_reported")) or (
            ev.source_type == SourceCategory.COMPANY_OFFICIAL_WEB)
        return SourceRef(
            id=ev.source_record_id,
            title=ev.title[:300],
            url=ev.public_url,
            source_type=ev.source_type.value,
            provider=ev.provider,
            retrieved_at=_iso(ev.retrieved_at),
            effective_date=(ev.effective_date.isoformat() if ev.effective_date else None),
            self_reported=self_reported,
        )

    # -- deterministic inference (MODEL_INFERENCE, never a fact) -----------

    def _role_relevance(self, facts: list[Claim], query: CompanyIntelligenceQuery,
                        jd_keywords: list[str]) -> list[Claim]:
        if not query.target_role and not jd_keywords:
            return []
        out: list[Claim] = []
        role = query.target_role or "this role"
        if facts:
            out.append(Claim(
                kind=ClaimKind.MODEL_INFERENCE,
                text=(f"Connect what the company publicly says (above) to the {role} role - be "
                      "ready to explain how you would contribute to it."),
                source_ids=[s for f in facts[:2] for s in f.source_ids],
            ))
        for kw in jd_keywords[:4]:
            out.append(Claim(
                kind=ClaimKind.MODEL_INFERENCE,
                text=(f"Your selected job description emphasises \"{kw}\" - prepare a concrete "
                      "example relevant to it."),
                source_ids=[],
            ))
        return out

    def _interview_prep(self, facts: list[Claim], developments: list[Claim],
                        culture: list[Claim], query: CompanyIntelligenceQuery,
                        jd_keywords: list[str]) -> InterviewPreparation:
        topics: list[Claim] = []
        for claim in (developments[:2] + culture[:2] + facts[:2]):
            topics.append(Claim(
                kind=ClaimKind.MODEL_INFERENCE,
                text=f"Understand: {claim.text[:160]}",
                source_ids=list(claim.source_ids),
            ))
        # A small, evidence-aware set of questions the candidate could ASK the employer.
        role = query.target_role or "this role"
        questions = [
            f"How does the team measure success for {role} in the first 6 months?",
            "What are the biggest priorities for this team over the next year?",
        ]
        if developments:
            questions.append("How do the recent developments above affect this team's roadmap?")
        if culture:
            questions.append("How do the stated company values show up day to day?")
        questions_to_ask = [Claim(kind=ClaimKind.MODEL_INFERENCE, text=q) for q in questions]

        clarify: list[Claim] = []
        if not facts:
            clarify.append(Claim(
                kind=ClaimKind.MODEL_INFERENCE,
                text=("No first-party company evidence was retrieved - verify the company's "
                      "products, market and recent news from its official website before interviewing."),
            ))
        return InterviewPreparation(topics=topics, questions_to_ask=questions_to_ask, clarify=clarify)

    # -- provider status (honest; never fakes success) --------------------

    def _provider_statuses(self, identity: CompanyIdentity,
                           company_result: CurrentMarketResearchResult | None,
                           market_result: CurrentMarketResearchResult | None = None,
                           ) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []

        # Official company website (the one live-capable first-party source).
        if identity.confidence is not IdentityConfidence.CONFIRMED:
            statuses.append(ProviderStatus(
                key="company_web", label="Official company website",
                state=ProviderState.UNAVAILABLE,
                detail="Add the official website to research this company."))
        elif company_result is None:
            statuses.append(ProviderStatus(
                key="company_web", label="Official company website",
                state=ProviderState.DISABLED, detail="Company web research is switched off."))
        else:
            statuses.append(ProviderStatus(
                key="company_web", label="Official company website",
                state=_state_from_result(company_result),
                detail=_detail_from_result(company_result),
                external_url=identity.website))

        # Adzuna market data - adapter exists; live path unvalidated / needs credentials. If a
        # market query actually ran, reflect its real outcome.
        if market_result is not None and market_result.status in (
                ResearchStatus.READY, ResearchStatus.PARTIAL):
            adzuna_state = _state_from_result(market_result)
            adzuna_detail = "Live market data returned results (not validated in this build)."
        elif self._adzuna_configured:
            adzuna_state = ProviderState.LIVE_UNVALIDATED
            adzuna_detail = "Adzuna is configured; live results are not validated in this build."
        else:
            adzuna_state = ProviderState.UNAVAILABLE
            adzuna_detail = "Live market data requires a configured provider (only Germany verified)."
        statuses.append(ProviderStatus(
            key="adzuna", label="Job-market data (Adzuna)",
            state=adzuna_state, detail=adzuna_detail))

        # Employee-review sources the founder named - NOT integrated (ToS/licensing review required).
        # We link to the source rather than copying any review content.
        loc = identity.location or ""
        for key, label, host in (
            ("glassdoor", "Glassdoor reviews", "www.glassdoor.com"),
            ("kununu", "Kununu reviews", "www.kununu.com"),
            ("google", "Google / web search", "www.google.com"),
        ):
            statuses.append(ProviderStatus(
                key=key, label=label, state=ProviderState.NOT_INTEGRATED,
                detail="Provider review required (terms/licensing) - opens the source; no content is copied.",
                external_url=_search_url(host, identity.company_name, loc)))
        return statuses

    # -- status / limitations ---------------------------------------------

    def _overall_status(self, identity: CompanyIdentity,
                        company_result: CurrentMarketResearchResult | None,
                        facts: list[Claim]) -> ReportStatus:
        if identity.confidence is IdentityConfidence.NEEDS_CLARIFICATION:
            return ReportStatus.NEEDS_CLARIFICATION
        if company_result is None:
            return ReportStatus.UNAVAILABLE
        if company_result.status in (ResearchStatus.UNAVAILABLE, ResearchStatus.RATE_LIMITED):
            return ReportStatus.UNAVAILABLE
        if not facts:
            return ReportStatus.INSUFFICIENT_EVIDENCE
        if company_result.status == ResearchStatus.PARTIAL or company_result.warnings:
            return ReportStatus.PARTIAL
        return ReportStatus.READY

    def _limitations(self, identity: CompanyIdentity,
                     company_result: CurrentMarketResearchResult | None,
                     facts: list[Claim]) -> list[str]:
        out: list[str] = []
        if company_result and company_result.status in (
                ResearchStatus.UNAVAILABLE, ResearchStatus.RATE_LIMITED):
            out.append("company_web_unavailable")
        if identity.confidence is IdentityConfidence.CONFIRMED and not facts:
            out.append("no_company_evidence")
        out.append("reviews_not_integrated")   # always true in Wave 5
        out.append("market_data_unvalidated")
        return out


# --------------------------------------------------------------------------- helpers


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _normalise_website(url: str | None) -> str | None:
    """Return an https URL for a user-supplied website/domain, or None if not a web URL.

    Tolerates a bare domain (adds https://). Does NOT perform SSRF validation here - the
    underlying `web_fetch.validate_url` is the authoritative guard when the page is fetched."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "." not in parsed.netloc:
        return None
    # Normalise to https (the fetcher is https-only anyway) and strip any path fragment noise.
    return f"https://{parsed.netloc}{parsed.path or ''}".rstrip("/") or f"https://{parsed.netloc}"


def _search_url(host: str, company: str, location: str) -> str:
    """A user-facing SEARCH link (never scraped content). For non-integrated review providers we
    link via a web search that names the provider, rather than guessing its URL scheme or copying
    any review text."""
    if host == "www.google.com":
        q = quote_plus(f"{company} {location}".strip())
        return f"https://www.google.com/search?q={q}"
    name = {"www.glassdoor.com": "Glassdoor", "www.kununu.com": "Kununu"}.get(host, host)
    q = quote_plus(f"{company} {location} {name}".strip())
    return f"https://www.google.com/search?q={q}"


_STOPWORDS = frozenset(
    "the a an and or of to for in on with your you we our are is be as at by from will role team "
    "work working experience years strong ability skills knowledge including etc job description "
    "responsibilities requirements".split()
)


def _keywords(text: str, *, limit: int) -> list[str]:
    """Deterministic keyword extraction from JD text (bounded; no model call).

    Frequency-ranked alphanumeric tokens, stopwords removed. The JD is untrusted DATA - this only
    derives short keyword strings for display; it never becomes a model prompt."""
    counts: dict[str, int] = {}
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}", text.lower()):
        if raw in _STOPWORDS or len(raw) < 3:
            continue
        counts[raw] = counts.get(raw, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


def _state_from_result(result: CurrentMarketResearchResult) -> ProviderState:
    if result.status == ResearchStatus.READY:
        return ProviderState.STALE if result.cache_hit else ProviderState.CONFIGURED
    if result.status == ResearchStatus.PARTIAL:
        return ProviderState.PARTIAL
    if result.status in (ResearchStatus.UNAVAILABLE, ResearchStatus.RATE_LIMITED):
        return ProviderState.UNAVAILABLE
    return ProviderState.FAILED


def _detail_from_result(result: CurrentMarketResearchResult) -> str | None:
    if result.warnings:
        # Warnings are engine-authored, safe strings (never raw provider errors).
        return result.warnings[0]
    if result.cache_hit:
        return "Served from a recent cached snapshot."
    return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
