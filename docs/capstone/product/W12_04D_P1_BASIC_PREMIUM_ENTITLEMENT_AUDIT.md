# W12.4D-P1: Basic and Premium product entitlement audit

Status: **AUDIT PLUS FINAL OWNER-APPROVED PRODUCT SPECIFICATION (SECTION 0). NUMERICAL LIMITS, PRICES AND POLICIES REMAIN UNAPPROVED. NOTHING IS IMPLEMENTED OR ENFORCED; PREMIUM IS NOT A DIFFERENTIATED OPERATIONAL SUBSCRIPTION.** Documentation only: no code, no migration, no Stripe call, no price, no policy change. Nothing here approves a price, a plan or a limit.
Method: static inspection of the repository at `main` = `112f9ef8782ca384e477006bc0375ed00b710a25` (PR #165, F2-B1R merged; Alembic head `0031_account_closure`), existing tests re-run read-only (`tests/test_plans_entitlements_w10_4.py`, `tests/test_pricing_truth_v4.py`: 34 passed), and two external price reads (section 16).
Evidence labels: **VERIFIED** (read in code or test), **OBSERVED** (external page read on 2026-10-16), **ASSUMPTION**, **UNKNOWN**. Where a claim could not be verified it is said so.

## 0. Final owner-approved Basic and Premium specification (amendments W12.4D-P1-A and W12.4D-P1-A final decisions)

The owner approved **Option B (value-led Premium)** and the allocation below, and then made three final decisions (model names, history policy, artifact policy). This section is the **binding product specification** and **supersedes** any earlier conflicting recommendation in this document (sections 18 to 21 and 26 are the original audit proposals and stay for the record; the technical audit findings in sections 1 to 17 and 22 to 29 are unchanged).
Every row is **owner-approved product requirements, not implemented capabilities.** **Premium is not currently a differentiated operational subscription**: today Premium equals Basic plus a `premium_preview` flag, nothing below is enforced, no billing or entitlement enforcement is activated, no Stripe call was made, and the EUR 19.99 figure remains an unapproved preview.

Status vocabulary used below: **APPROVED** (owner-approved product requirement), **IMPLEMENTED** (exists in code today), **NOT IMPLEMENTED**, **QUALITY VALIDATION REQUIRED**, **COMMERCIAL APPROVAL REQUIRED**, **LEGAL REVIEW REQUIRED**.

### 0.1 Approved matrix versus what exists today

| # | Capability | Approved Basic | Approved Premium | Implemented today (VERIFIED) | Enforced by plan today | Gap and gate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | AI interview practice | included with sustainable limits | higher allowances | yes, unbounded; no per-user ceiling on Practice | no | P2-A ceilings and metering, P4 quota enforcement; numbers COMMERCIAL APPROVAL REQUIRED |
| 2 | Role and job-description personalisation | included | included | yes | n/a | none |
| 3 | Competency-based questions | included | included | yes | n/a | none |
| 4 | AI answer feedback | included | included | yes | n/a | none |
| 5 | Interview readiness reports | included | included | yes | n/a | none |
| 6 | Interview history | latest 3 completed interviews | complete eligible retained history | yes, complete list for everyone | no | P2-B (binding requirements in 0.3); retention LEGAL REVIEW REQUIRED |
| 7 | Progress statistics | basic statistics over the latest 3 completed interviews | complete eligible historical statistics, trends, improvement comparisons | aggregate over ALL interviews; no trends or comparisons | no | P2-B scope; P4 trends and comparisons (NOT IMPLEMENTED) |
| 8 | Company research | core access with quality and usage safeguards | higher allowances once qualified | yes (30 per hour rate ceiling; provider live-unvalidated) | entitlement granted to both | allowance entitlements (P4); "qualified" bar QUALITY VALIDATION REQUIRED |
| 9 | Interview attempt comparison | not included | included | NOT IMPLEMENTED | no | P4 |
| 10 | Opportunity preparation pack | not included | personalised pack | NOT IMPLEMENTED (only MD and JSON report export) | no | P5-A |
| 11 | AI model profiles | Fast | Fast, Balanced, Advanced | three profiles exist; Mo accepts a candidate `profile`; Practice has none and uses the server default (Balanced) | no | P2-C; runtime change gated, see 0.4 |
| 12 | Saved resume and historical work | preserved per retention policy | preserved per retention policy | kept until the candidate or an account deletion removes it; no approved retention policy | n/a | retention LEGAL REVIEW REQUIRED |
| 13 | Real-time voice | not promised | future capability, not part of the initial paid launch commitment | implemented, default OFF, live-unvalidated | rate limit and pause only | out of launch scope (W12.4E, validation) |

### 0.2 Binding principles

1. Basic history limits restrict **access**, not physical retention or storage. 2. Older records are **never deleted** because an account downgrades. 3. Premium history access stays subject to the approved retention policy (not yet approved). 4. Unlimited history access is **not** unlimited AI generation. 5. Tier differences are enforced on the **backend**; frontend hiding alone is never sufficient. 6. Existing candidate data stays protected across entitlement transitions. 7. Account ownership checks, privacy rights, export and deletion are never weakened or plan-gated. 8. Numerical AI limits stay unapproved. 9. The EUR 19.99 price stays an unapproved preview. 10. Approved requirements are kept distinct from implemented features.

### 0.3 History policy: binding P2-B acceptance requirements (APPROVED requirement, NOT IMPLEMENTED)

* **Policy.** Basic: the latest **three completed** interviews are accessible. Premium: complete eligible retained history. The Basic limit is an **access** restriction. An account with 20 completed interviews that is or becomes Basic keeps all 20 stored (per the applicable retention policy), can access only the latest 3 through the product, and regains access to all eligible history on re-upgrade. Nothing is deleted, anonymised or moved on a plan change.
* **Surfaces that P2-B must restrict (an interview ID in a direct request must never bypass the entitlement).** Inventory from this audit (to be re-verified by P2-B): history listing (`GET /history/interviews`); direct retrieval and detail (`GET /history/interviews/{id}`, report fetch `GET /interviews/{session_id}/report`); the associated answers and feedback; history export and the self-service data export (privacy export of the candidate's own data stays complete because it is a data right, which is a **LEGAL REVIEW REQUIRED** point to resolve explicitly); MD and JSON report export; progress statistics (`repository.dashboard_metrics` reads all interviews today); workspace sharing of an interview report (a Basic account sharing a restricted interview: policy decision); Opportunity views that list linked interviews; the agent and Mo context that may reference prior interviews; feedback targets that reference an interview. Any other API that exposes a completed interview.
* **Which interviews count.** Only **completed** interviews occupy the three slots. Draft, in-progress and resumable sessions (stored in `interview_sessions`, not in the completed `interviews` history) must never consume a slot. Completed history rows are saved after the report is durably persisted (existing crash-safe ordering), which gives a clean completed set.
* **Deterministic ordering, including ties.** Today the list orders by `created_at` descending with no tie-breaker (`repository.list_interviews`). P2-B must define one total order for "latest" (for example completion time, then record id) and use it identically for the list, direct-access eligibility, progress scope and exports; behaviour at ties and for clock skew must be tested. Which timestamp defines "latest" (creation versus completion) is a P2-B design decision.
* **Direct access rule (recommended).** Refuse reads of interviews outside the entitled set with a distinct "available with Premium" response that reveals no content and no metadata beyond a count; hiding only in lists is not acceptable.
* **Counts and transparency.** The candidate may see how many records are hidden, never their content.
* **Tests required.** Direct-ID bypass attempts per surface, tie ordering, draft exclusion, downgrade then re-upgrade restoring access, 20-record account keeps 20 rows, cross-account isolation, export and deletion rights intact.

### 0.4 Model profiles (APPROVED naming and target allocation; runtime change NOT approved)

* **Official customer-facing names: Fast, Balanced, Advanced**, matching the internal identifiers `fast`, `balanced`, `advanced` (`ModelProfile`, `src/llm/models.py`). **There is no "Medium" profile and Balanced must not be renamed Medium.** The word "medium" in the code is only a documented reasoning-effort hint for the Advanced tier (metadata, not sent to the provider) and is not a model profile; this specification does not use it as a tier name.
* **Target allocation (APPROVED):** Basic: Fast. Premium: Fast, Balanced, Advanced.
* **Runtime behaviour is NOT approved to change.** Practice currently uses the server default, Balanced, and must **not** be switched to Fast automatically for existing Basic sessions. P2-C must first qualify, and only after qualification may enforcement change behaviour:
  Fast versus Balanced **question quality** and **feedback quality**; role-specific relevance; consistency of generated questions; model availability; the actual provider model identifiers; cost per operation; latency; failure and retry behaviour. (QUALITY VALIDATION REQUIRED and COMMERCIAL APPROVAL REQUIRED; costs are UNKNOWN, model prices were not verifiable in the P1 audit, and no model ids are assumed here.)
* **Enforcement needed in P2-C:** clamp the Mo `profile` parameter by entitlement (refuse or downgrade by a documented rule, never silently); add a Practice profile rule and entitlement; entitlements authorise profile ids, never provider slugs; the governed AI configuration (W10.7) remains the only place model mappings change. **Model routing is not modified by this task.**

### 0.5 Premium artifacts after a downgrade (APPROVED requirement, NOT IMPLEMENTED)

* **Rule.** Previously generated Premium artifacts remain **readable and downloadable** after a downgrade, subject to ownership and retention (examples: a previously generated Opportunity Preparation Pack, eligible saved Premium reports, other independently stored Premium outputs). Nothing is deleted on downgrade.

| After downgrade | Status |
| --- | --- |
| Read existing eligible Premium artifacts | ALLOWED |
| Download existing eligible Premium artifacts | ALLOWED |
| Create new Premium-only artifacts | RESTRICTED |
| Regenerate an existing artifact with Premium AI | RESTRICTED |
| Run new Premium-only analytics | RESTRICTED |

* **Non-bypass rule.** The artifact rule must **not** become a bypass of the three-interview Basic history policy: an artifact read or download endpoint must not expose complete restricted interview histories merely because the artifact is described as Premium. A saved, independently stored preparation pack may stay readable; **previously generated interview feedback and interview reports remain subject to the interview-history access policy (0.3).**
* **Ambiguities recorded for P2-B resolution (do not silently broaden access):** which stored outputs count as "independently stored Premium artifacts" (a pack is; a saved interview report is governed by the history rule, so "eligible saved Premium reports" needs a precise definition); whether a pack that embeds excerpts of restricted interviews is readable on Basic; whether a Premium-generated comparison snapshot is an artifact or restricted history; whether artifacts shared with a workspace stay shared after downgrade; whether a re-upgrade restores regeneration of old artifacts. These need an artifact classification list and an owner or legal decision before P5-A creates the first artifact type.

### 0.6 Approved development sequence (proposed work packages; each needs its own specification and approval gate; none starts automatically)

| Package | Scope |
| --- | --- |
| **P2-A** | AI cost protection, request safeguards, usage metering and concurrency controls (per-user ceilings and a pause capability on Practice and Career, which today have none; atomic counters; concurrency limits; idempotent operation accounting) |
| **P2-B** | History visibility, progress access, and downgrade and re-upgrade entitlement enforcement (the binding requirements in 0.3, and the artifact boundary in 0.5) |
| **P2-C** | Fast, Balanced and Advanced model-profile authorisation and the quality and cost qualification in 0.4 |
| **P3** | Premium candidate UX, plan messaging and truthful marketing (eight locales; copy matches the enforced matrix) |
| **P4** | Quota enforcement, cost qualification, progress trends and attempt comparisons |
| **P5-A** | Opportunity Preparation Pack implementation |
| **P5-B** | Integrated Basic and Premium acceptance |
| **Billing** | **F2-B2** controlled Stripe sandbox connection; **F3** end-to-end subscription acceptance (separate approval gates; no Stripe account exists yet) |
Note: this sequence replaces the earlier P2 to P5 outline in section 26.

### 0.7 Remaining owner decisions (all UNRESOLVED; none is invented here)

Basic Practice numerical allowance; Premium Practice numerical allowance; company research allowances; other AI feature quotas (Mo coach, Deep Dive, documents and storage); quota reset periods; existing-user transition or grandfathering policy; Premium price (EUR 19.99 is an unapproved preview); annual pricing; trial period; failed-payment grace period; cancellation and refund policies; dispute-related access policy; financial-data retention; country and currency coverage; B2B offering; Premium commercial terms. Design-level questions assigned to P2-B and P2-C: the ordering timestamp for "latest", direct-access refusal behaviour, privacy-export scope versus the Basic history limit, artifact classification, and the Basic Practice model profile after qualification.

### 0.8 Legal business structure (recorded owner decision; not an incorporation)

Ask4Mo will be operated by a **separate German company**; planned form **Ask4Mo UG (haftungsbeschränkt)**; **registration is pending**; initial share capital is **not finalized**; the Stripe account must be **separate from Unbiased Talent**. The company is not represented as registered and no Stripe account was created.

### 0.9 Current implementation gaps and preserved safeguards

Gaps: no quotas or counters; no Practice or Career cost ceiling (the defined `cost_interview_user` and `cost_career_user` buckets are applied by no route); no history, progress or model-profile entitlement enforcement; history ordered by `created_at` without a tie-breaker; progress computed over all interviews; no attempt comparison, trends or preparation pack; no approved retention policy; homepage and footer copy describing benefits no entitlement enforces. Billing gates verified False and unchanged: `LIVE_BILLING_ENABLED`, `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`, `RECONCILE_SCHEDULER_ENABLED`, `PROVIDER_READS_AUTHORIZED`, `PAID_ENTITLEMENT_POLICY_APPROVED`. No application code, model routing, migration, price or plan changed.

## 1. Executive assessment

1. **Premium has no functional benefit today.** `DEFAULT_PLANS["premium"]` is the Basic key set plus `premium_preview` (`src/entitlements.py:69-72`). The only route that checks that key is `GET /auth/premium/status` (a demonstration endpoint, `src/api/routes/auth.py:376-387`). The public pricing page says so itself ("Today the two plans differ only in the Premium preview", `frontend/lib/i18n/messages/v4/en.ts`). VERIFIED.
2. **Almost nothing is gated by plan.** Only two routes use `require_entitlement`: company research (granted to Basic too) and the premium demo endpoint. The keys `standard_history`, `standard_progress` and `standard_model_profiles` are carried in the plan data but are enforced by no route. VERIFIED (grep over `src`).
3. **There is no quota or usage-limit entitlement.** The entitlement model supports an integer LIMIT type, but no limit key exists, there are no consumption counters, no reset windows and no session, question, opportunity, document or history cap per user. VERIFIED.
4. **Cost protection is incomplete for the most expensive workflow.** Per-user hourly cost ceilings exist for the agent (60/h), company research (30/h), uploads (40/h) and realtime voice (12/h), plus a global ceiling (5,000/h). The policies `cost_interview_user` (120/h) and `cost_career_user` (60/h) are **defined in `src/api/rate_limit.py` but applied by no route**; Practice (`/interviews/*`, the dominant LLM spend) and Career chat have no per-user rate ceiling and no operator pause capability. This is the most important security and cost finding. VERIFIED.
5. **The product has real, differentiated substance** that could support a paid tier: role, industry and seniority-specific mock interviews with 12 interview types and 6 personas, rubric-scored feedback across 7 dimensions with improved-answer guidance, Deep Dive branching, a final readiness report, owner-scoped private documents with approved-evidence reuse, Opportunities, company intelligence with fact/inference labelling, an agentic Prepare coach (Mo) with citations, eight interface languages and browser voice. VERIFIED, with limits listed in sections 3 to 9.
6. **Progress is thin.** One aggregate endpoint (counts, average score, most common improvement area, average answer seconds, five recent interviews); no trend over time, per-competency or per-opportunity view. VERIFIED.
7. **Speech beyond the browser is not available to candidates.** Whisper STT and Pocket TTS are planned (W12.4E, not started); the Google Chirp 3 service is wired only into the legacy Streamlit studio; realtime voice is off by default and live-unvalidated. VERIFIED.
8. **Unit economics cannot be computed honestly yet.** There is no measured per-user cost data, the model price inputs could not be verified (section 16), and the one verified fee input is Stripe's 3.5 % Managed Payments fee plus unspecified payment fees. The audit gives formulas and the measurements required.
9. **Recommendation (section 30):** do not sell Premium until the matrix in section 21 is approved and enforced server-side with metering. Recommended direction is **Option B (value-led Premium)**, built in dependency order: close the Practice cost-ceiling gap first (independent of Premium), then entitlement limits with atomic counters, then Premium UX. The €19.99 figure remains an unapproved preview.

## 2. Actual product architecture (VERIFIED)

Next.js 15 / React 19 frontend (`frontend/`) over FastAPI (`src/api`, `/api/v1`) over an application layer (`src/application`) and domain code (`src/agent`, `src/copilot`, `src/interview`, `src/*.py`). SQLAlchemy over SQLite (dev) or PostgreSQL (production, Alembic). LLM calls go through OpenRouter (`src/openrouter_client.py`, `src/llm/*`); embeddings are OpenAI-compatible with a deterministic local fallback (`src/copilot/constants.py`: `text-embedding-3-small`); vector search is Chroma plus BM25. Identity is server-side accounts and sessions. Background work is a DB-backed job queue and a separate worker. Billing is the W12.4D stack, all gates off. Admin is a permission-gated operations console (44 permissions). Model profiles resolve through one registry (`src/llm/models.py`: Fast `openai/gpt-5.6-luna`, Balanced `openai/gpt-5.6-terra`, Advanced `openai/gpt-5.6-sol`, environment-overridable, plus a governed Admin configuration layer).

## 3. Verified feature inventory

Status vocabulary: FULL (implemented and user-accessible), PARTIAL, OFF (implemented, disabled by default), PREVIEW, PLANNED. "Enforced" = server-side plan or quota enforcement (not rate limits or ownership).

| Feature | User benefit | Implementation evidence | AI / data / config | Plan today | Limits today | Enforced | Tests | Status | Limitations | Recommended tier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Practice interviews | role-specific mock interviews with questions generated per session | `src/api/routes/interview.py`, `src/application/interview_service.py`, `src/interview_service.py`; frontend practice flow | LLM (OpenRouter), `interview_sessions` / `interviews`; OpenRouter key | all | 1 to 20 questions per session; answer 6,000 chars; JD 8,000 (API 12,000) | none by plan; no rate ceiling | `test_interview_service.py`, `test_interview_api_durable.py`, `test_interview_idempotency.py`, e2e | FULL | live LLM quality UNVALIDATED by humans; no per-user ceiling | Basic (limited) and Premium (more) |
| Interview setup breadth | industry, seniority, type, persona, difficulty, detail level | `src/constants.py`: 10 career levels, 12 interview types, 6 personas, 3 difficulties, 3 detail levels | LLM prompts (`src/prompts.py`) | all | enumerated choices | none | `test_interview_service.py` | FULL | free-text role and industry; no profession restriction | Basic (core), Premium (all) is a decision |
| Answer feedback | rubric feedback, strengths, gaps, improved example, follow-up | `AnswerEvaluation` in `src/models.py`; `src/evaluation_service.py` | LLM structured output | all | none | none | `test_evaluation_contract.py`, `test_evaluation_service.py` | FULL | model-inferred scores, not deterministic | Basic |
| Final report | readiness summary, priorities, checklist | `FinalInterviewReport` in `src/models.py`; `report_service.py`; `POST /interviews/{id}/report` | LLM | all | one report per session | none | `test_interview_report_deepdive.py` | FULL | practice feedback, not a hiring signal | Basic (summary), Premium (richer) |
| Deep Dive | branching deeper question from an evaluated answer | `routes/interview.py` deep-dive endpoints; `DeepDive*` models | LLM | all | none | none | `test_interview_deep_dive_api.py` | FULL | | Premium candidate |
| Mo coach (Prepare) | agentic prep: JD analysis, gap analysis, plan, knowledge search with citations | `src/agent/*`, `routes/agent.py`; `/prepare` | LLM + RAG; `AGENT_COACH_ENABLED` | all | 60 runs/h per user; step budget | rate limit only | agent eval (56 cases), e2e | FULL when enabled | per-turn step cap; cost per run unmeasured at scale | Basic (limited), Premium (more) |
| Career chat (deterministic flow) | grounded Q&A over the knowledge base | `routes/career.py`, `src/copilot/*` | LLM + RAG | all | none | none (policy `cost_career_user` unused) | copilot tests, evals | FULL | no ceiling | Basic |
| Company intelligence | official-source company facts, labelled inference | `routes/company.py`, `company_intelligence_service.py` | web fetch + Adzuna; deterministic (no model) | all (entitlement `current_market_research` granted to Basic) | 30/h per user | entitlement + rate limit + pause | `test_company_intelligence.py` | FULL, provider live UNVALIDATED | no reviews integration (not integrated) | Basic (limited), Premium (more) |
| Opportunities | private per-job context linking research, prepare, practice | `opportunity_service.py`, `routes/opportunity.py` | DB only | all | none | none | `test_opportunity_journey.py` | FULL | no count cap exists | Basic (1 active), Premium (more) |
| Documents + Story Bank | private upload, extraction, approved evidence reuse | `src/documents/*`, `documents_service.py`, `stories_service.py` | deterministic, no LLM; OCR optional | all | 10 MB per file, 50 pages, 40 uploads/h | rate limit, pause (OCR) | `test_documents_api.py`, `test_documents_pipeline.py` | FULL; OCR runtime depends on deployment | no document count or storage cap | Basic (limited), Premium (more) |
| History | list and read saved interviews | `routes/history.py`, `history_service.py` | DB | all | none | none (`standard_history` unused) | `test_career_history.py`, `test_history_idempotency.py` | FULL | | Basic |
| Progress | aggregate counts and average | `routes/progress.py` -> `repository.dashboard_metrics` | DB | all | loads all of a user's interviews per call | none (`standard_progress` unused) | `test_service_progress.py` | PARTIAL | no trends, competencies or per-opportunity; scales linearly with history | Basic (summary), Premium (trends, once built) |
| Model profiles | Fast, Balanced, Advanced | `src/llm/models.py`, `policy.py`; agent request `profile`; Practice has no candidate profile field in `CreateInterviewRequest` | LLM | all (`standard_model_profiles`) | none | **not enforced** | `test_model_registry.py`, `test_model_policy.py` | PARTIAL: selectable on Mo runs only | Practice uses the server default (Balanced) | Premium candidate (Advanced) |
| Voice dictation and playback | speak answers, hear questions | `frontend/lib/speech/*` (browser SpeechRecognition and speechSynthesis) | browser-native; no audio stored | all | browser support | none | `test_voice_experience_p7.py`, e2e | FULL (browser dependent) | quality varies by browser and language | Basic |
| Realtime voice | live voice interviewer | `src/voice/realtime.py`, `routes/voice.py` | OpenAI realtime (provider); `REALTIME_VOICE_ENABLED` default false | all if enabled | 12 sessions/h, concurrency and duration caps | rate limit, pause | `test_realtime_voice.py` (offline) | OFF, live UNVALIDATED | costly; not validated with real audio | Premium candidate, only after validation |
| Sharing and workspaces | VIEW-only sharing with others | `workspace_service.py`, `sharing_service.py` | DB | all | none | ownership and grants | `test_workspaces_p6_5.py` | FULL | separate from Premium | Basic |
| Report export | MD and JSON export | `application/report_export.py` | deterministic | all | none | none | `test_documents_api.py` (export safety) | FULL | | Premium candidate (richer packs) |
| Premium preview | demo of server-side gating | `GET /auth/premium/status` | none | Premium plan | n/a | **yes (the only functional gate)** | `test_plans_entitlements_w10_4.py` | PREVIEW | no real feature behind it | n/a |
| Upgrade / checkout | buy Premium | `PremiumSubscriptionPanel`, `/billing/checkout-*` | Stripe (disabled) | n/a | n/a | gates off | `checkout-w12-4d-c.test.tsx` | MOCK/DISABLED | cannot be purchased | n/a |
| Speech STT/TTS providers | server-side Whisper and Pocket TTS | `docs` only; Chirp 3 in `src/speech_service.py` for Streamlit | n/a | none | n/a | n/a | n/a | PLANNED (W12.4E) | no code for Whisper/Pocket | future Premium differentiator |

## 4. Interview practice capabilities (VERIFIED, each assessed independently)

| Capability | Status | Evidence | Note |
| --- | --- | --- | --- |
| Role-specific | FULL | `target_role` required (`InterviewConfigIn`) | free text, any profession |
| Industry-specific | FULL | `industry_or_sector` required | |
| Seniority-specific | FULL | 10 `CAREER_LEVELS` from internship to executive | |
| Job-description customisation | FULL | JD text or owner-scoped document, screened as DATA | JD never enters a raw prompt unscreened |
| Company-specific | PARTIAL | `company_context` free text (4,000 chars), Opportunity and company intelligence feed it | no automatic company model |
| Competency-based, behavioural, technical, situational, leadership, executive | FULL | `INTERVIEW_TYPES`: screening, behavioural, technical, situational, competency, case_study, portfolio, panel, leadership, culture_values, stakeholder, executive_board | quality depends on the LLM |
| Follow-up questions | FULL | `follow_up_question` in the evaluation; Deep Dive branching | |
| Adaptive questioning | PARTIAL | next question receives compact prior evaluations (`src/constants.py` comments on difficulty adaptation); no deterministic adaptation policy | prompt-based |
| Difficulty | FULL | 3 bands, candidate-chosen | |
| Question generation | FULL | per question, plus strategy generation first | |
| Session duration | NOT IMPLEMENTED | no time limit per session | |
| Session continuation | FULL | durable resume, operation lease, recover endpoint | |
| Session and question limits | PARTIAL | questions per session 1 to 20 (`MAX_QUESTIONS`); no limit on number of sessions | |
The product is profession-generic; nothing here targets HR professionals.

## 5. AI interview feedback (VERIFIED)

Per answer (`AnswerEvaluation`): overall score 0 to 100; rubric 1 to 10 on relevance, structure, evidence, role knowledge, problem solving, communication and credibility; strengths; improvement areas; missing evidence; a suggested stronger structure; an illustrative improved example answer; a follow-up question. Per session (`FinalInterviewReport`): readiness score, summary, strongest competencies, development priorities, recurring answer patterns, highest-risk questions, evidence gaps, recommended practice actions, final checklist.
Distinctions: all scores and text are **LLM-generated, model-inferred, structured-output** feedback; not deterministic and not retrieval-grounded (the feedback path does not cite the knowledge base); the coaching style only changes wording, never scoring. STAR-method feedback is **not a named dimension** (structure feedback and a suggested structure exist; STAR is not explicitly scored). Feedback history exists through saved reports; **longitudinal improvement is not implemented** (only aggregate average). Marketing must not present scores as objective or as hiring probability (no such probability exists and none should be created).

## 6. Resume and job context (VERIFIED)

Documents: owner-scoped upload (PDF, DOCX, TXT; 10 MB per file; 50 pages; OCR optional and deployment-dependent), private store, deterministic verbatim extraction with provenance, user review, Story Bank, MD/JSON export; documents are untrusted DATA and are never placed into a model prompt; candidate context for Practice comes only from APPROVED evidence. JD: text or selected document, screened. Company information: company intelligence from official sources. Skill identification and candidate-to-requirement mapping: gap analysis in the Prepare agent (deterministic) and the Candidate Evidence specialist (deterministic selection of approved claims). Privacy: no public URLs, deletion with the account, retention for in-progress sessions via cleanup script; **no document count or storage-size cap** per user and no plan-dependent retention. Distinctive value for Premium: evidence-grounded personalisation is the strongest differentiator in the codebase, but today it is free for everyone.

## 7. Knowledge and RAG (VERIFIED)

Shared infrastructure: Chroma vector store, BM25 hybrid fusion, deterministic lane router, structured stores (roles, competency, compensation, labour market, credentials), governed datasets, Admin-governed knowledge (approval workflow, separate collection). Candidate-accessible RAG: Mo's `SearchCareerKnowledge` tool and the deterministic Career chat, both with citations and abstention-first behaviour; company intelligence (no model). Admin-only: knowledge management, readiness, prompt lab. Coverage quality: `eval_product_coverage` insufficient-evidence **94 % (n = 412), BELOW GATE and unresolved**; retrieval quality baselines exist but live corpus behaviour in production is UNVALIDATED. Embeddings: `text-embedding-3-small` via an OpenAI-compatible endpoint or a deterministic local embedder (cost is per query; not metered per user). A working vector store is not a commercial differentiator by itself; the candidate-visible differentiator is cited, grounded Prepare answers, which is available to everyone today.

## 8. Progress and analytics (VERIFIED)

Measured: interviews completed, answers evaluated, average practice score, most common improvement area, average answer seconds (from timing metrics), five most recent interviews. Not measured or shown: trends, per-competency performance, per-opportunity progress, readiness over time, personalised learning plans beyond the report's recommended actions. Evidence base: the persisted LLM evaluations, so every score inherits model variance. **No hiring probability is computed and none should be introduced.** Technical note: `dashboard_metrics` reads all of a user's interviews per request (linear cost with history).

## 9. Speech readiness (VERIFIED)

| Item | State |
| --- | --- |
| Browser dictation (Web Speech) and playback (speechSynthesis) | implemented, free to the platform, browser dependent, no audio stored |
| Google Chirp 3 server STT | implemented in `src/speech_service.py`, used only by the legacy Streamlit studio; no Next.js route |
| Realtime voice (OpenAI) | implemented, default OFF (`REALTIME_VOICE_ENABLED`), tested offline, **live and human validation not run**, bounded sessions (12/h, concurrency and duration caps), seven languages |
| Whisper STT, Pocket TTS | **PLANNED only (W12.4E not started)**; no code, only provider decisions in docs |
| Latency, cost, privacy of planned providers | UNKNOWN until built; server-side STT would process audio and needs a retention and privacy decision |
Speech must not be counted as an existing Premium benefit; it is a candidate future differentiator.

## 10. Current Basic experience (VERIFIED)

A free user (registered, verified email) can use everything, with no plan-based restriction: unlimited practice sessions up to 20 questions each, feedback, reports, Deep Dive, Mo coach (60 runs per hour), company research (30 per hour), unlimited Opportunities, documents and Story Bank (40 uploads per hour, 10 MB each), history, progress, all three model profiles on Mo, browser voice, export and sharing. Restrictions that exist: per-hour rate ceilings on agent, research, upload and realtime; input size limits; the global cost ceiling; operator pause (agent, market research, OCR, realtime, registration). Enforcement locations: backend rate limiter (`src/api/rate_limit.py`, in-process or Redis), backend pause service, backend validation. **Frontend-only restrictions: none found.** Not enforced anywhere: session count, Opportunity count, document count, history length, model profile choice, report count, Practice call rate.

## 11. Current Premium experience (VERIFIED)

Still accurate: **Premium = Basic + `premium_preview`**, and `premium_preview` unlocks only `GET /auth/premium/status`. Surfaces: the pricing page (honestly labelled "differ only in the Premium preview"; EUR 19.99 shown as a preview; "Under consideration" rows are explicitly not enforced); the Account page plan summary and a Premium panel that offers no purchase while checkout is unavailable; homepage and marketing copy ("Premium adds deeper preparation across multiple opportunities for 19.99 per month", footer "Premium is 19.99 per month") that **describes benefits no entitlement enforces**. Premium badges and flags exist only as the preview. **There are no enforceable functional differences.** The Premium product definition must not be derived from the existing copy.

## 12. Entitlement architecture (VERIFIED)

Plans are versioned rows (`plan_versions`: draft, active, retired; immutable once active) with `plan_entitlements` (boolean or integer LIMIT). `EntitlementService` is the single authority (`src/entitlements.py`): active user subscription, else the explicit Basic fallback (never Premium), workspace subscriptions only for explicit workspace scope. `require_entitlement(key)` is the route gate. The registry is code-defined (five keys). Subscriptions record `source` (system default, admin, migration, provider); only the entitlement bridge writes `source = 'provider'`, under an owner-approved policy (unapproved today). Admin can assign plans (audited, two-person where specified). Billing never reads or writes entitlements except through the bridge.
**Can it support feature-specific entitlements?** Boolean: yes today. Limits: the data model and `validate_value` support LIMIT entitlements, but there is **no consumption, counter, reset window or enforcement helper**; a `require_quota` mechanism does not exist and must be built.
**Bypass test:** the existing suite proves a Basic account gets 403 on `/auth/premium/status` and on research when the entitlement is removed, over real HTTP (`tests/test_plans_entitlements_w10_4.py`). Gated features cannot be bypassed by direct API calls; ungated features have nothing to bypass.

## 13. Server-side enforcement assessment

| Topic | Today |
| --- | --- |
| Feature authorization | two routes only (research, premium demo) |
| Usage limits and counters | none |
| Quota reset | none |
| Subscription expiry | resolves to Basic fallback; no content deleted (no plan-dependent deletion code found) |
| Cancellation, refund, dispute | bridge policy (unapproved); no runtime effect |
| Admin-assigned access | supported (`source=admin`, never overridden by the provider) |
| Trial, grace | policy fields exist; values unapproved (None = hold) |
| Provider grants | bridge only; unapproved |

Required to add or change (not done here): per-feature entitlements with limit keys (sessions per period, active Opportunities, documents, research runs per period, report exports, model profile allowance, Deep Dive allowance); an atomic usage counter or ledger keyed by user and window, with idempotency by operation id; `require_quota` dependencies on Practice, Career, Prepare and Documents routes; downgrade semantics (existing content stays readable and exportable); Admin visibility of limits; tests for race conditions and cross-account isolation.

## 14. Usage metering and abuse control

| Quantity | Reliable today? | Evidence |
| --- | --- | --- |
| Practice sessions, questions, evaluations | partially: rows exist in `interview_sessions` and `interviews` with owner and timestamps; no counters | schema |
| AI requests, input and output tokens, cost | partially: `ai_usage_facts` records one canonical unit per Agent run (cumulative) or per Practice operation; unknown tokens and cost are NULL, never 0; started at W10.12 with no back-fill | `AIUsageFact` |
| Embedding requests | NO per-user record | |
| RAG retrievals | counted inside agent usage only (cache hits and misses), not per user ledger | |
| Document processing | upload rate only; no per-user processing count or storage total | |
| Research requests | rate limit only (30 per hour); cache hits are not attributed per user | |
| Storage usage | NO | |
| Concurrent sessions | realtime voice only (limiter); no limit for Practice | |
| Speech minutes | none (not implemented) | |
Gaps: retry accounting (failed requests may or may not appear as usage; not defined), quota race conditions (no quota exists), reset windows (none), account switching (a person can register several accounts; verified email and per-IP registration limit 8/h are the only controls). The rate limiter is process-local unless Redis is configured, which weakens ceilings across multiple API processes. Candidate isolation is strong (every repository filters by user). `ai_usage_facts` is a reporting source with partial coverage and must not become the quota authority without a coverage review.

## 15. AI cost structure

Providers: OpenRouter for all chat completions (Fast, Balanced, Advanced slugs above, overridable); an OpenAI-compatible embeddings endpoint (`text-embedding-3-small`) or the local embedder; OpenAI realtime (optional, off); Adzuna and web fetch for research (not LLM); Google Chirp 3 (Streamlit only). Prompt and output bounds: `DEFAULT_MAX_OUTPUT_TOKENS` 3,072 and `MAX_OUTPUT_TOKENS_LIMIT` 4,096 for Practice; Career default 1,024, structured 4,096, synthesis 4,096; candidate answer 6,000 chars, JD 8,000, background 4,000, company context 4,000; prior answer text is limited to the most recent few when generating the next question. Retry: bounded transient retries per call (`MAX_TRANSIENT_RETRIES`), structured-output repair rounds exist, so one logical operation can cost more than one call; accounting counts calls once at the canonical boundary. Caching: per-thread retrieval cache for Mo, research cache for company research. Fallbacks: bounded lower-tier fallback by policy; no provider fallback beyond OpenRouter routing. Token accounting: OpenRouter-reported cost when present, else calculated from live `/models` pricing, else unavailable.
**Prices: UNVERIFIED.** `PricingService` reads prices from the OpenRouter `/models` endpoint at runtime and never hard-codes them. A read of `https://openrouter.ai/api/v1/models` on 2026-10-16 did not contain the slugs `openai/gpt-5.6-luna`, `-terra`, `-sol` (nor `gpt-5-nano` or `gpt-5-mini`) and exposed no pricing fields in the form read, so no price is stated in this document. Missing inputs: current per-token input and output prices of the three configured slugs, embedding price, realtime audio price.

## 16. Unit economics (transparent model, no invented inputs)

Verified or observed inputs:
* Stripe Managed Payments fee: **3.5 % per successful Managed Payments transaction, in addition to payment fees** (OBSERVED on the German `stripe.com/pricing` page, 2026-10-16; the payment fees, any fixed fee, currency and the fee base were **not stated**).
* The visible EUR 19.99 is an unapproved preview; whether it is tax-inclusive is undecided.
* Code ceilings that bound worst-case volume per user per hour: agent 60, research 30, uploads 40, realtime 12 (Practice: none).
Illustrative arithmetic that IS supportable: on EUR 19.99 the 3.5 % component is EUR 0.70 if the base were the full price (the base after tax is UNKNOWN), before unspecified payment fees. No other cost can be computed.

Model: monthly contribution per subscriber = net revenue after tax and provider fees − variable cost.
`contribution = P_net − (0.035 × P_base) − F_payment − [ S·(q·(c_q + c_e) + c_r) + A·(t_in·p_in + t_out·p_out) + R·c_research + V·c_voice ] − c_storage − c_support − c_hosting_alloc`
with S practice sessions, q questions per session, c_q cost per question cycle (generation plus evaluation), c_e embedding cost, c_r report cost, A agent runs, t tokens, p prices, R research runs, V voice minutes.

| Persona | Usage inputs | Status |
| --- | --- | --- |
| Low | few sessions, 1 Opportunity | UNKNOWN: no telemetry; do not infer |
| Typical | | UNKNOWN: needs measured distribution from `ai_usage_facts` once real usage exists |
| Heavy | | UNKNOWN |
| Extreme or abusive | bounded today only by agent, research, upload and realtime ceilings; **Practice is unbounded** | the unbounded exposure is the finding, not a number |
Measurements required before any margin claim: per-operation token and cost distribution by workflow and model profile (from `ai_usage_facts`, after reviewing coverage); retries and repair rate; embedding calls per query; research cache hit rate; storage per user; support tickets per subscriber; verified OpenRouter prices; Stripe payment fee schedule and the Managed Payments fee base; tax treatment of the listed price. **No profitability is inferred.**

## 17. Commercial product positioning

Supported by implementation: personalised preparation (role, industry, seniority, JD, approved evidence); repeatable automated practice with structured feedback and an improved-answer example; company context from official sources with explicit fact versus inference labelling; cited, grounded Prepare answers with abstention; private documents; eight interface languages (interface language is not market eligibility); browser voice; privacy controls (export and delete, no audio stored, no admin content browsing); independent preparation at any hour. The repository's dated benchmark (reviewed 2026-10-09, `frontend/lib/pricing.ts`) lists human interview coaching at roughly EUR 100 to 175 per hour or GBP 60 to 195 per hour (observed prices of 11 providers in their own currencies, not re-verified here), which positions an automated tool as a practice complement, not a substitute for a coach.
Hypotheses (unproven): candidates value repeatable low-cost practice enough to pay monthly; a job-search-length subscription fits better than a perpetual one. Forbidden claims: placement or interview outcome guarantees, being a recruiter, live human coaching, objective scores, hiring probability, bias-free, certified compliance.

## 18. Option A: Lean Premium MVP

* **Idea:** enforce what already exists. Basic: all current functionality but with hard, cost-bounding limits on the expensive paths (limit keys on Practice sessions per month, active Opportunities, research runs per month, saved sessions in history view). Premium: raised limits plus the Advanced model profile on Mo and richer export.
* Reused: all existing features; entitlement model; rate limiter. New: limit keys, atomic counters, `require_quota`, upgrade prompts at limit, downgrade-safe reads. Complexity: M (touches Practice, Career, Opportunity, Documents, History routes and the account UI). AI cost: bounded by limits. Abuse exposure: multi-account signup; counters per user. UX: limit messaging in 8 locales. Risks: introducing limits for current users; "premium is just higher limits" may convert poorly. Effort: relative M, no duration claimed. Assumptions: higher limits and Advanced model are valued. Dependencies: P2 entitlement implementation, metering, approved matrix.

## 19. Option B: Value-led Premium (APPROVED by the owner; see section 0)

* **Idea:** Option A plus two capabilities that deliver visible new value and can be built from existing assets: (1) **progress over time** (score and competency trends per Opportunity, attempt-to-attempt comparison) computed from persisted evaluations; (2) **interview pack and richer export** (a per-Opportunity preparation pack from the existing report and plan).
* Free: complete evaluation experience (a few full sessions, one active Opportunity, one research brief, basic history and report). Premium: unlimited-under-fair-use practice, multiple Opportunities, Advanced model, trends and comparison, pack export.
* Reused: evaluations, reports, Opportunity model, export. New: analytics queries and UI, pack builder, counters. Complexity: L (analytics and UX plus Option A). AI cost: trends and packs are deterministic or reuse stored text (no new model calls by default). Abuse: fair-use ceilings on practice per period. UX: charts and comparison need honest labelling (model-inferred scores). Risks: trend metrics inherit model variance and must not imply hiring probability. Dependencies: Option A plus evaluation-variance review. Effort: relative L.

## 20. Option C: Advanced Premium

* **Idea:** Option B plus realtime and server-side speech (W12.4E), richer coaching, and B2B or team plans.
* New: validated realtime voice, Whisper STT, Pocket TTS, speech cost metering, workspace plans. Complexity: XL; speech cost and latency UNKNOWN; privacy decisions for audio; B2B needs legal and tax work (tax code business variants, contracts). Abuse: voice minutes are the costliest unit; concurrency caps needed. Risks: depends on not-started W12.4E and unvalidated realtime; marketing must not pre-sell it. Assumptions: voice is a paid differentiator. Effort: relative XL. Not recommended as the launch scope; keep as roadmap.

## 21. Original audit matrix proposal (SUPERSEDED where it differs from section 0; limits here were illustrative and are not approved)

| Feature | Basic | Premium | Proposed limit (illustrative) | Implementation | Enforcement today | Development required | Cost implication | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Practice sessions | yes | yes | Basic: a few full sessions per month; Premium: fair-use ceiling | FULL | none | counters, `require_quota`, ceiling policy | highest variable cost | lets users evaluate fully without unlimited spend |
| Questions per session | up to a moderate cap | up to 20 | cap decision | FULL | schema max 20 | cap entitlement | linear in questions | |
| Feedback and report | full | full | same quality on both | FULL | none | none | included in session cost | withholding feedback would break evaluation |
| Deep Dive | limited | full | per-session allowance | FULL | none | allowance entitlement | per branch | natural upgrade lever |
| Opportunities | 1 active | multiple | Basic 1; Premium owner-defined | FULL | none | limit key, archive semantics | negligible | matches job-search workflow |
| Company research | 1 brief | more | per-period runs | FULL | 30/h rate only | counters | external fetch cost | |
| Mo coach runs | limited | higher | per-period | FULL | 60/h rate | counters | LLM tokens | |
| Documents and Story Bank | yes | yes | count and storage caps | FULL | upload rate only | caps | storage, OCR | privacy features should stay available on all plans |
| Model profile | Fast or Balanced | adds Advanced | allowed profiles | PARTIAL (Mo only) | not enforced | enforce `standard_model_profiles`-style key per profile; add Practice profile choice | Advanced costs most (price UNKNOWN) | clear value lever |
| History | full list | full | no limit on stored content | FULL | none | none | storage | never delete content on downgrade |
| Progress | summary | trends and comparison | | PARTIAL | none | build analytics | compute only | requires new work |
| Export | basic | pack | | FULL | none | pack builder | negligible | |
| Voice dictation and playback | yes | yes | | FULL | none | none | none (browser) | accessibility, must stay free |
| Realtime voice | no | candidate (after validation) | minutes cap | OFF | rate and pause | validation, metering | high | not before W12.4E and live validation |
| Privacy, export, deletion | yes | yes | | FULL | n/a | none | none | always free (already stated publicly) |

Comparison table (required summary):

| Area | CURRENT BASIC | CURRENT PREMIUM | RECOMMENDED BASIC | RECOMMENDED PREMIUM | IMPLEMENTATION GAP | COST / RISK |
| --- | --- | --- | --- | --- | --- | --- |
| Practice volume | unbounded (no ceiling) | same | bounded sessions per period | fair-use ceiling | counters, quota gate, Practice rate ceiling | highest LLM cost; abuse |
| Opportunities | unbounded | same | 1 active | multiple | limit key | low cost |
| Research | 30/h | same | 1 brief per period | more | counters | fetch cost |
| Mo coach | 60/h | same | limited | higher | counters | tokens |
| Model tier | all three (Mo) | same | Fast or Balanced | adds Advanced | enforcement and Practice choice | Advanced price UNKNOWN |
| Progress | aggregate | same | aggregate | trends, comparison | analytics build | model-variance honesty |
| Export | MD, JSON | same | basic | pack | pack builder | low |
| Voice | browser | same | browser | browser plus realtime later | W12.4E, validation | high, UNKNOWN |
| Functional difference | none | none (preview flag) | n/a | defined by the matrix | everything above | unapproved |

## 22. Pricing considerations

The EUR 19.99 monthly preview is not approved and is not validated by any evidence in the repository: there is no usage telemetry, no cost data, no willingness-to-pay research and no conversion data. Observed reference points (from the repository's dated benchmark, OBSERVED by an earlier wave on 2026-10-09 and not re-verified): human interview coaching at several providers costs about EUR 100 to 175 per hour or GBP 60 to 195 per hour; this shows a high-priced human alternative, not what candidates would pay for automated practice. Considerations: monthly versus annual (job searches are episodic, which argues for monthly with an annual option later; annual price is undecided); free-to-paid conversion depends on the Basic experience being meaningful but bounded; variable cost sensitivity is highest for Practice and Advanced-model use; B2B (careers services, bootcamps) is an unexplored channel with different tax and contract needs; Managed Payments adds 3.5 % plus payment fees (section 16). **Recommended validation methodology (not executed):** (1) instrument cost per session from `ai_usage_facts` over a pilot; (2) fix the matrix and limits; (3) run a willingness-to-pay study (for example Van Westendorp or a priced waitlist) with a defined candidate sample before showing any price as an offer; (4) test price points in a closed pilot only after billing is operational; (5) compute contribution margin from measured cost and the verified fee schedule. No conversion rate is forecast here.

## 23. Security and fairness implications

* Accessibility and privacy features (voice dictation and playback, data export and deletion, localisation) should remain on Basic.
* Candidate ownership: every repository filters by user; limits must key on the authenticated user, never on client input.
* Unauthorized entitlement access: gating must be server-side only; the existing pattern (dependency per route) is sound; quota checks must be atomic to avoid races on concurrent create calls (Practice creation is idempotent per key but not quota-aware).
* Subscription and AI-cost abuse: add the missing per-user ceiling on Practice and Career before any pricing exposure; consider multi-account abuse (verified email and the per-IP registration limit are the only controls); keep the global ceiling.
* Rate-limit bypass: the in-process limiter is per process unless Redis is configured; paid launch needs the shared limiter validated (Redis is listed as not validated live).
* Misleading claims: homepage and footer text implies benefits that are not enforced; align copy to the approved matrix before any sale (the pricing page already states the truth).
* Unexpected feature loss: introducing Basic limits changes what current users can do; needs a decision on grandfathering and clear notice.
* Expiry, refund and dispute transitions: access resolves to Basic; **existing candidate content must never be silently deleted**; read, export and delete must stay possible; retention under a future approved policy.
* Cross-account access: unchanged ownership model; shared (VIEW) grants are independent of plan.

## 24. Internationalization

Eight UI locales (en, de, fr, es, it, pt, nl, ru). Plan and benefit text is localised through the i18n catalogues; the pricing page and account text must be updated in all eight when the matrix is approved (the scanner and the "fragment must cover every locale" rule enforce completeness). Entitlements are locale-independent (resolved by account, never by language). **Interface language is not sales eligibility:** Managed Payments restricts purchasers in Ascension, China, Cuba, Iran, Kosovo, North Korea, Russia, Syria and Tristan da Cunha (documentation); Russian is a supported interface language yet Russia is a restricted purchase country, and the supported selling countries are an owner decision. Billing terms (cancel, refund, renew) need review per locale; translations are engineering translations pending native and legal review. The protected slogan stays untranslated.

## 25. Premium activation dependencies

Approved feature matrix; server-side limit entitlements with atomic counters; per-user ceilings on every costly route; accurate metering and a coverage review of `ai_usage_facts`; approved prices, currency, tax display, trial, grace, cancellation, refund and dispute policies; approved product descriptions; operational Stripe integration (F2-B2, F3); entitlement bridge approved policy; cancellation handling; account closure; refund and dispute reconciliation; candidate support experience; consumer-law and privacy review; the actual legal entity; Stripe Managed Payments eligibility on the dedicated account; shared rate limiter validated; live Brevo validation (verification and billing mail); retention review. Payment success alone is not sufficient for activation.

## 26. Original audit roadmap (superseded by the P2-A to P5 sequence in section 0.6; proposals, not approved waves)

| Package | Objective | Key changes | Tests and security acceptance | Depends on | Definition of done |
| --- | --- | --- | --- | --- | --- |
| **P2 Product entitlement implementation** | close the cost gap and add enforceable limits | apply `cost_interview_user` and `cost_career_user` (or replace) and a Practice pause capability; limit entitlement keys; `usage_counters` (or ledger) migration with unique operation ids; `require_quota`; Admin plan editor shows limits | race and idempotency tests, cross-account isolation, downgrade keeps content, no frontend-only gates | approved matrix | every costly route has a per-user ceiling; limits enforced server-side; counters atomic |
| **P3 Premium UX and feature enforcement** | candidate experience of limits and Premium | upgrade prompts at limit, plan page driven by server limits, localisation x8, honest copy, model-profile enforcement incl. Practice profile choice | UI states in 8 locales, e2e of limit and upgrade-disabled states | P2 | UI mirrors server state only |
| **P4 Usage metering and cost safeguards** | reliable per-user usage and cost | per-user usage records for embeddings, research, documents, storage; retry accounting; coverage review; Admin cost report; shared rate limiter validated | coverage tests, failure charging rules, reset-window tests | P2 | measured cost per workflow available per cohort |
| **P5 Integrated Premium acceptance** | end-to-end readiness | analytics for Option B, pack export, billing-to-entitlement under approved policy, sandbox acceptance (F3) | integrated acceptance matrix, security review | P2 to P4, F2-B2, F3, owner approvals | release candidate with all gates reviewed |
Prioritise: P2 cost ceilings first; they are valuable regardless of Premium.

## 27. Owner decisions required

Limit values and the remaining items in section 0.5 (the proposition, Option B, and the feature allocation in section 0 are approved); whether Basic limits apply to existing users (grandfathering); prices, currency, tax-inclusive display, annual plan; trial, grace, cancellation, refund and dispute policies; supported customer countries; B2B; billing data retention and content retention after downgrade; support commitment; product classification and tax code; copy corrections to the homepage and footer; priority of P2 relative to other waves.

## 28. Business structure (recorded owner decision; not an incorporation)

Ask4Mo will operate as a **separate German company**: planned legal form **Ask4Mo UG (haftungsbeschränkt)**. Company registration: **PENDING**. Initial share capital: **NOT FINALIZED**. A **dedicated Stripe account is required**; Unbiased Talent's existing Stripe account **must not** be used for Ask4Mo subscriptions. The UG is not incorporated, no company was registered and no Stripe account was created. The legal seller entity decision in the F2-B1 register therefore resolves to "the future Ask4Mo UG" and stays blocked until registration.

## 29. Risks, limitations and preserved controls

Limitations of this audit: static inspection and existing tests; no live provider, no live candidate data, no telemetry from real usage; LLM quality unvalidated by humans; model prices unverified; Stripe payment fee schedule unknown. Billing safeguards verified unchanged: 44 Admin permissions, `platform.billing.recover` plus fresh step-up, two-person financial approvals, signed webhooks, held-event recovery, provider-read authorization, ownership checks, bridge-only entitlement writes, subscription-aware closure, privacy-erasure separation. Gates verified False in `src/billing/policy.py`: `LIVE_BILLING_ENABLED`, `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`, `RECONCILE_SCHEDULER_ENABLED`, `PROVIDER_READS_AUTHORIZED`, `PAID_ENTITLEMENT_POLICY_APPROVED`. Open programme dependencies: W12.4C live Brevo validation, research-cache evaluator isolation, product coverage below gate, Managed Payments eligibility unverified, Ask4Mo UG incorporation, commercial policy approval, financial-data retention review, Google-only (password) step-up limitation.

## 30. Evidence references and final recommendation

Evidence: `src/entitlements.py`; `src/api/dependencies.py` (`require_entitlement`); `src/api/routes/auth.py:376`; `src/api/routes/company.py`; `src/api/guards.py`; `src/api/rate_limit.py` (policies; `cost_interview_user` and `cost_career_user` referenced nowhere else); `src/application/pause.py` (`PAUSABLE_CAPABILITIES`); `src/constants.py`; `src/models.py` (`AnswerEvaluation`, `FinalInterviewReport`); `src/repository.py` (`dashboard_metrics`); `src/api/schemas/interview.py`, `agent.py`; `src/speech_service.py`; `src/voice/realtime.py`; `src/persistence.py` (`AIUsageFact`); `src/pricing_service.py`; `frontend/lib/pricing.ts`; `frontend/lib/i18n/messages/v4/en.ts`; `frontend/components/account/PlanSummary.tsx`; tests `tests/test_plans_entitlements_w10_4.py`, `tests/test_pricing_truth_v4.py` (34 passed on this run). External: OpenRouter models endpoint and Stripe German pricing page read on 2026-10-16.

**Final recommendation (updated by W12.4D-P1-A: Option B and the section 0 matrix are owner-approved):** do not launch Premium on today's code (it has no benefit and Basic is unbounded). Adopt **Option B** as the target proposition, delivered in the order P2 (cost ceilings and limit entitlements) then P3, P4, P5, with Option C items kept on the roadmap. Fix the Practice and Career cost-ceiling gap first, independently of billing. Approve the matrix and policies, then validate price with measured cost and a willingness-to-pay study. The EUR 19.99 figure stays an unapproved preview. No Premium feature, price or plan change was made in this wave.
