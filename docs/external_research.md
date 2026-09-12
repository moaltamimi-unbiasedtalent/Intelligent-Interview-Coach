# External Current-Market Research (Phase 7F)

Ask4Mo can optionally supplement its governed local Career Intelligence with **bounded**
current-market evidence. This is **not** general web browsing: it is one Agent tool routing to a
small set of approved providers behind a strict policy.

## The sixth Agent tool

`ResearchCurrentMarket` joins the five existing tools (AnalyzeJobDescription, AnalyzeCandidateGaps,
BuildPreparationPlan, GenerateInterviewQuestions, SearchCareerKnowledge). Agent tool count: **6**
(+ 2 separate HITL action tools). LangGraph topology, the other tools, retrieval, memory, auth and
Interview Practice are unchanged.

## Architecture (who decides what)

- **Mo (the LLM) decides IF** current/external evidence is needed.
- The **ExternalResearchService decides WHICH** approved provider/endpoint/source serves the typed
  request. The model never chooses raw URLs or endpoints.

```
ResearchCurrentMarket (agent tool)
      └─ ExternalResearchService  (routing + TTL cache, src/copilot/research/service.py)
            ├─ AdzunaResearchProvider   → authorized_market_api   (advertised-market signals)
            └─ CompanyWebResearchProvider → company_official_web / official_public_web
                  └─ WebFetcher (SSRF-safe, bounded, robots-aware, no JS)
```

## Local-first rule

Use `SearchCareerKnowledge` for occupation facts, skills, responsibilities, abilities,
education/training, official historical/statistical compensation, labour-market forecasts,
credentials and governed frameworks. Use `ResearchCurrentMarket` **only** when the question
materially depends on: current vacancies, live advertised salary, current employer hiring, fresh
market activity, or an explicit company URL. A deterministic freshness heuristic
(`research/policy.py`) is used in evaluation to assert this (it is advisory — the LLM's decision
is authoritative). A general "what skills does a data analyst need?" question stays local.

## Adzuna — advertised-market semantics

Adzuna is an `authorized_market_api`. It supplies **advertised** salary ranges, current adverts
and a provider-reported matching-advert count. It is **NOT** official observed earnings, **NOT**
government statistics, and **NOT** the foundational occupation taxonomy. Advertised salary is kept
separate from BLS/ONS/Eurostat/Destatis (never merged). Aggregates over a bounded sample are
labelled a **sample statistic** with sample size + disclosure count — never a population median
(§16). A provider count is labelled provider coverage, not "all vacancies" (§17). Credentials
(`ADZUNA_APP_ID`/`ADZUNA_APP_KEY`) are env-only and never logged/serialised; only the public
`redirect_url` (query-stripped) is candidate-visible — never the authenticated API URL.

## Company / official web — bounded fetcher

Only when there is a **defensible public URL** (user-supplied, in the JD, or a verified company
domain). Never discovered from a name; no search engine (§22). A few (≤4) **same-origin** public
HTTPS pages (home/careers/jobs/about/company). Registered official domains (destatis.de,
arbeitsagentur.de, europa.eu, bls.gov, ons.gov.uk) are `official_public_web`. Company pages are
**self-reported** ("The company states…"), not independent verification (§42).

### SSRF & network safety (`research/web_fetch.py`)

- HTTPS only (no silent upgrade); credentialed URLs rejected.
- The hostname is resolved and **every** resolved IP must be public — private / loopback /
  link-local (incl. 169.254.169.254 metadata) / reserved / unique-local ranges are rejected,
  defeating SSRF and DNS-rebinding.
- Each redirect hop is revalidated; **cross-origin redirects are rejected**.
- Bounded timeout (8s), redirects (3), response bytes (~1 MB), pages (≤4), retries.
- `robots.txt` respected → disallowed paths are not fetched.
- HTML parsed WITHOUT executing scripts/iframes/forms; only human-readable text + title.
- A clear `Ask4Mo-Research/*` User-Agent; never a browser/Googlebot disguise.
- No headless browser, no crawler, no recursion, no login.

## Prompt-injection defence

External text is UNTRUSTED DATA. The primary control is structural: it only ever reaches the model
inside a typed `ExternalEvidence.snippet` field whose tool/system contract says it is quoted
evidence, never instructions. `research/content_guard.py` is the backstop: it caps length,
normalises whitespace, and **flags** override / secret-request / exfiltration / outbound-call
patterns. A flagged company page is still returned only as quoted evidence, with a warning — it
never gains policy authority, triggers another tool, or causes an outbound call.

## Citations & evidence labels

External evidence flows through the existing candidate-facing source projection with distinct
labels so a candidate can tell them apart: `advertised_market` (Adzuna), `company_web`,
`official_web` — separate from Ask4Mo governed knowledge and official statistics (§40/§41). Each
item carries provider, public URL, `retrieved_at`, geography and (for jobs) advertised-salary
fields. Freshness is explicit ("current advertised-market snapshot", retrieved date).

## Cache

A bounded TTL file cache under `data/cache/external/` (git-ignored) stores only **sanitised,
normalised** results, keyed by safe request parameters (provider/intent/role/geography/company/
limit). It never caches credentials, authenticated URLs, raw provider payloads, candidate CV/
background or free-text prompts. Default TTL 30 minutes (clamped 60s–24h).

## Privacy & permanence

The external request carries only market fields (role, location, company/URL, industry) — never
CV, candidate name/email/phone or background. External results are **ephemeral request-time
evidence**: they are NEVER written to `data/normalized/`, `data/knowledge/` or `data/chroma/`, and
large payloads are never stored in LangGraph checkpoints.

## Configuration

```
ADZUNA_APP_ID= / ADZUNA_APP_KEY=            # env only (reused from Phase 7A.1)
EXTERNAL_RESEARCH_ENABLED=true              # master switch (providers degrade gracefully)
COMPANY_WEB_RESEARCH_ENABLED=true           # company/official web fetch
EXTERNAL_RESEARCH_CACHE_TTL_SECONDS=1800    # optional
RUN_ADZUNA_INTEGRATION=0                    # explicit gate for the optional LIVE Adzuna test
```

## Testing & network policy

Normal `pytest`/CI make **zero** live external calls: Adzuna uses a fake transport, the web
fetcher an injected transport with forced public resolution. A minimal live Adzuna validation runs
only when `RUN_ADZUNA_INTEGRATION=1` AND credentials are configured. Evaluate with
`python scripts/eval_external_research.py` (deterministic) and audit with
`python scripts/audit_external_research.py`. Observability (Phase 7D) traces only safe metadata
(provider, intent, country, result_count, cache_hit, status) — never page text, job-query text,
authenticated URLs or credentials.

## Limitations

Adzuna is not the entire labour market; advertised salaries are not observed earnings; many ads
omit salary; company-website evidence is self-reported and needs a supplied/verified URL; there is
no generic search engine and no LinkedIn/Indeed/Glassdoor/StepStone/Kununu scraping; nothing is
ingested into the permanent knowledge base.
