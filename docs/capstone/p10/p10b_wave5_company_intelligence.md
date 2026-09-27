# P10B Wave 5 - Company Intelligence, Employer Research & Interview Preparation

**Status:** DELIVERED (implementation complete; gates green).
**Branch:** `feature/capstone-p10b-wave5-company-intelligence` - **not merged**.
**Baseline:** `main` @ `99423b5` (Waves 1-4 + Wave 2 reintroduction merged; PRs #87/#88/#89/#93).
**Migration:** none (read-mostly; the Opportunity persistence model is Wave 6).
**Release candidate:** none. RC-P9-001 immutable; RC-P10-002 only at Wave 8.
**Paid/live calls:** 0.

Turns the existing, security-hardened external-research engine (`src/copilot/research/*`, Phase 7F)
into a **directable, candidate-facing Company Intelligence** experience - the capability the founder
could not find ("I could not see anywhere the area for researching a company ... enter the name of
the company and the location"). It does **not** build a second research architecture and does not
weaken any safety boundary.

## What was already there (audit)
- **`src/copilot/research/*` (Phase 7F):** a bounded engine (Adzuna market API + an SSRF-safe
  company/official-web fetcher) with a typed contract (`CurrentMarketResearchResult`,
  `ExternalEvidence`, `SourceCategory`), a durable TTL file cache, robots/redirect/size guards,
  HTML-script stripping and prompt-injection flagging. **Reachable only through the Mo agent tool** -
  no REST endpoint, no candidate UI (the core gap).
- **`src/copilot/company/*` + Streamlit `career/ui.py`:** a legacy, Streamlit-only "company context"
  (user-supplied URLs/uploads, `NullResearchProvider`). Reference only - not the foundation.

## What Wave 5 adds
- **A directable endpoint** `POST /api/v1/research/company` (`src/api/routes/company.py`) over a new
  application service `CompanyIntelligenceService` (`src/application/company_intelligence_service.py`),
  gated by the existing controls: authorization capability `current_market_research`, the operator
  pause switch `current_market`, and the per-user cost ceiling `cost_research_user`.
- **A candidate experience** at `/company` (`frontend/app/company/page.tsx` +
  `frontend/components/company/{CompanyResearchClient,CompanyReport}.tsx`), **discoverable** from the
  "More" navigation and from a restrained link at the top of **Prepare**.
- **An explicit claim taxonomy** the UI never blurs: **FACT** (from an official/company source),
  **REVIEW** (third-party opinion - not integrated in Wave 5), **MODEL_INFERENCE** (a deterministic,
  source-derived Ask4Mo suggestion, never a verified fact). Every fact carries provenance; the source
  panel shows type + freshness + a link.
- **Deterministic identity disambiguation:** a company is researched **only** against an explicit,
  validated website. A name-only request returns a `needs_clarification` state asking for the official
  website - Ask4Mo never guesses a domain from a name or silently researches a similarly named company.
- **Honest provider status** for every source the founder named (official web, Adzuna market,
  Glassdoor, Kununu, Google) so a partial/unavailable result never looks complete.

## Company research journey
1. Candidate opens **Company research** (from Prepare or "More").
2. Enters **company name** (required) and, ideally, the **official website**; optionally location,
   country, target role and a stored **job description** (via the one governed `DocumentPicker`).
3. Submits deliberately (never an invisible side effect of Mo).
4. The server confirms identity, runs governed COMPANY_CONTEXT research against the provided website
   (and, when a role is given, an optional market-context intent), and returns a sectioned report:
   **Snapshot -> Business & market -> Recent developments -> Culture & values (company-stated) ->
   Employee review signals -> How it relates to your role -> Interview preparation -> Sources ->
   Providers -> Limitations**.
5. Every claim is labelled FACT / REVIEW / AI-suggestion; sources and freshness are always shown; a
   disclaimer states this is interview-preparation intelligence, not an employer rating.

## Source & claim model
- **FACT** - `summary_facts` / `ExternalEvidence` snippets from `company_official_web` /
  `official_public_web` / `authorized_market_api`. Self-reported (company-stated) facts are marked as
  such and separated from independent ones.
- **REVIEW** - employee-review sentiment. **No REVIEW claims are produced in Wave 5** (no review
  provider is integrated); the section links out honestly instead.
- **SOURCE** - the provenance panel: title, type, `retrieved_at` (freshness), optional
  `effective_date`, and a sanitised public link (never an authenticated API URL).
- **MODEL_INFERENCE** - role relevance + interview topics/questions, derived deterministically from
  the retrieved evidence (no model call), each tied to its source ids and clearly labelled as an
  Ask4Mo suggestion.

## Provider feasibility matrix

| Provider | Intended information | Official integration | Auth | Cost | Licensing / ToS | Attribution | Storage restriction | Implementation status | Live validation |
|---|---|---|---|---|---|---|---|---|---|
| Official company website | Business, products, values, news (first-party facts) | Direct HTTPS fetch via the SSRF-safe `web_fetch` (robots-honouring) | none | free | Public pages; robots respected; no bulk harvch | Link to page | Cache only sanitised snippets (no raw HTML) | **IMPLEMENTED** (server path); candidate provides the URL | **LIVE UNVALIDATED** (no live fetch exercised in this build) |
| Adzuna (job market) | Advertised roles/salary/market activity | Existing `AdzunaResearchProvider` (env `ADZUNA_APP_ID`/`_KEY`) | API key | free tier | Adzuna API terms | Required | Sanitised evidence only | **CONFIGURED** (adapter exists; degrades to UNAVAILABLE without keys) | **LIVE UNVALIDATED** (only Germany search previously verified) |
| Glassdoor | Employee reviews/ratings | No public, licensable review API for this use | - | - | ToS/licensing prohibit scraping; review content reuse restricted | - | Do not store review content | **NOT INTEGRATED / PROVIDER REVIEW REQUIRED** (link-only) | n/a |
| Kununu | Employee reviews/ratings (DACH) | No public licensable review API assessed | - | - | ToS/licensing; scraping not permitted | - | Do not store review content | **NOT INTEGRATED / PROVIDER REVIEW REQUIRED** (link-only) | n/a |
| Google / Google Places | Company discovery / basic profile | Google Places / Custom Search are paid, keyed, licence-restricted | API key | paid | Google API ToS; display/caching restrictions | Required | Storage restricted | **NOT INTEGRATED / PROVIDER REVIEW REQUIRED** (link-only) | n/a |
| LinkedIn | Company profile | No general-use company API for this purpose | - | - | ToS prohibit scraping | - | - | **NOT INTEGRATED / PROVIDER REVIEW REQUIRED** | n/a |

**We did not scrape any of the above.** For non-integrated sources the UI offers a **search link**
(the candidate opens the source themselves); Ask4Mo copies no review content.

## JD / document integration
Reuses the Wave 3/4 governed document system: the candidate may select an existing
`job_description` via `DocumentPicker`; the server resolves it **owner-scoped** through the shared
`resolve_document_text` (`extracted_text`) helper. A foreign/missing/deleted document yields no text
and is never disclosed (`jd_linked=false`). JD text is **untrusted DATA**: it is reduced to bounded
keywords for display only and is **never placed in a model prompt** (there is no model call in this
service). No second uploader/store/pipeline was created.

## Mo integration
Company research is **useful without Mo** and is not an invisible side effect. The existing agent tool
`ResearchCurrentMarket` (bounded, allow-listed, injection-guarded) is unchanged; no unrestricted
browsing tool was added, and retrieved content remains untrusted DATA behind the tool boundary.

## Multilingual behaviour
The interface uses the existing 7-locale catalogue (new `company` namespace, parity enforced by
`tsc`). Geography comes only from the explicit country/location inputs - **never inferred from the
interface language**, and career geography is never inferred from company location. Company names are
never translated. Deterministic suggestions reference source text as-is (source language), never
presented as translated facts.

## Security & privacy
- **SSRF/robots/size/redirect/injection guards reused unchanged** (`web_fetch.py`,
  `content_guard.py`); a private-IP or credentialed website yields no evidence (no fetch), proved by
  test + eval. No generic web/crawler symbols introduced.
- **Owner scoping:** the endpoint resolves the JD by the authenticated `user_id`; foreign ids return
  no data. Admin gains no candidate research data (the admin surface is unchanged).
- **No secret leakage:** no API key / authenticated endpoint / credential appears in the report
  (asserted). Raw provider errors are never exposed - failures degrade to honest status/warnings.
- **Privacy:** nothing new is persisted. The only research storage is the pre-existing ephemeral
  file cache (`data/cache/external/`, keyed on safe request params only, never candidate data). The
  privacy/data inventory is updated to record "no new persistence in Wave 5".

## Provider failure / offline mode
A deterministic offline fixture provider (`src/copilot/research/fake_provider.py`) powers dev/tests
with **0 live calls** and is **never labelled live** (`health.fixture=true`; results warn "fixture
data"). Report/provider states are explicit: configured / unavailable / disabled / partial / failed /
stale / not_integrated / live_unvalidated. A paused capability returns a truthful 503.

## Status ladder (do not collapse)
- **CONFIGURED:** Adzuna adapter (env-gated), capability + pause + cost gating, capability flag.
- **IMPLEMENTED:** directable endpoint, application service, candidate UI, claim taxonomy,
  disambiguation, JD integration, provider-status model, i18n, evaluator.
- **DETERMINISTICALLY TESTED:** backend unit/API tests, frontend unit tests, Playwright e2e (fake
  provider), `scripts/eval_company_intelligence.py` (24 invariants) - all 0 paid/live calls.
- **LIVE VALIDATED:** none. Live company-web fetch and live Adzuna are **NOT RUN** in this build.
- **HUMAN VALIDATED:** none (engineering-draft translations; no human pilot in this wave).

## Tests & evaluation
- Backend: `tests/test_company_intelligence.py` (identity, taxonomy, provenance, SSRF degradation,
  JD owner-scoping own/foreign/deleted, gating/pause, no-secret, no-fabrication, capability flag).
- Frontend: `frontend/tests/company-research.test.tsx` (claim separation, provenance, link-only
  reviews, lifecycle states); `frontend/e2e/company.spec.ts` (report render + clarification).
- Evaluator: `scripts/eval_company_intelligence.py` - 24 deterministic invariants, PASS, 0 paid/live.

## Files changed
Backend: `src/application/company_intelligence_service.py` (new), `src/copilot/research/fake_provider.py`
(new), `src/api/routes/company.py` (new), `src/api/dependencies.py`, `src/api/main.py`,
`src/api/routes/health.py`, `src/api/schemas/common.py`, `tests/test_company_intelligence.py` (new),
`scripts/eval_company_intelligence.py` (new).
Frontend: `frontend/app/company/page.tsx` (new), `frontend/components/company/*` (new),
`frontend/components/preparation/PrepareEntry.tsx`, `frontend/components/layout/nav-items.ts`,
`frontend/lib/api/{client,types}.ts`, `frontend/lib/useCapabilities.ts`,
`frontend/lib/i18n/messages/*.ts` (7 locales), `frontend/tests/company-research.test.tsx` (new),
`frontend/e2e/company.spec.ts` (new).
Docs: this file, `p10b_remediation_plan.md`, `capstone_requirements_matrix.md`,
`p4_privacy_data_inventory.md`, `CLAUDE.md`.

## Known limitations
- Live company-web fetch and live Adzuna are unvalidated (no live call in this build).
- Employee-review platforms (Glassdoor/Kununu) and Google/LinkedIn are not integrated (ToS/licensing);
  the UI links out instead of copying content.
- Industry is not modelled by the research engine (left blank rather than guessed).
- MODEL_INFERENCE is deterministic/heuristic (source-derived), not an LLM synthesis - intentionally,
  to keep 0 paid calls; a live-model synthesis path is a later enhancement behind Mo.
- Engineering-draft translations (not human/legal reviewed).

## RC impact
No RC created. RC-P9-001 immutable; RC-P10-002 only at Wave 8. This wave changes runtime (a new
endpoint + UI); a pilot on it before Wave 8 would require a new RC first.

## Next recommended wave
**Wave 6** - Opportunity vs Workspace information architecture (new model + additive migration), which
will embed this Company Intelligence experience inside an Opportunity. Not started.
