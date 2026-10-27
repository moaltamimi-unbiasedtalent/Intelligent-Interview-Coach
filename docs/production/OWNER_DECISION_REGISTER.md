# Owner Decision Register (Production Roadmap V2.2, corrected)

> Task08 preparation, 27 October 2026: [complete staging authorization matrix and written budget/Redis/recovery worksheets](execution/WAVE4_TASK08_OWNER_DECISIONS.md) and [readiness preflight](execution/WAVE4_TASK08_AUTHORIZATION_PREFLIGHT.md) are READY FOR OWNER DECISION only. Existing approved directions remain unchanged; no open decision, spending/deployment authority, appointment or gate approval is resolved by that packet.

**Status:** updated 2026-10-22 after Wave 2 (new decisions raised while building are in their own table below); first written 2026-10-21 at the Phase 00 sign-off. **OD-SCOPE-01 is resolved: S1, the full originally agreed R1.0 scope, is OWNER-APPROVED.** Only decisions that are genuinely still awaiting the owner are listed as open. Decisions the owner has already made (languages, Russian exclusion, R1.3 languages, release train, free invitation-only beta, English-only Admin, Basic/Premium as free beta tiers, the owner-requested capabilities and the five reviewer findings) are **requirements**, not open decisions, and are no longer listed here. Earlier open items that were resolved by the recovered text: OD-LANG-01, OD-LANG-05, OD-LANG-06, OD-REQ-TEXT, OD-REVIEW-FINDINGS, OD-RELEASE-TRAIN.

## Owner-approved decisions (Phase 00 sign-off, 2026-10-21)

| ID | Decision | Resolution |
|---|---|---|
| OD-SCOPE-01 | Which R1.0 scope strategy | S1, the FULL originally agreed R1.0 scope, is selected. S2 (restricted free private beta) and S3 (minimum safe beta) are rejected as November release plans. No R1.0 product requirement is removed, downgraded or postponed to meet a delivery target. The 30 November 2026 date is the owner's target and does not override mandatory security, privacy, licensing, AI quality, source qualification or operational gates: if a gate is unmet the date moves, features are not cut. |
| OD-RESOURCE-DIRECTION | Resourcing direction | The owner is prepared to allocate additional time and engineering resources. This is a direction, not an allocation: nothing is assumed hired or assigned (the allocation itself is open as OD-RESOURCE). |
| OD-ADMIN-NAV | Admin navigation groups | Six grouped Admin menu sections are approved (Command Center; Customers and Workspaces; Products and Commercial; AI and Knowledge; Insights and Operations; Governance and Settings). |
| OD-INVITE | Beta invitation mechanism | Secure single-use beta invitations are approved; token design details (for example email-bound, hashed, expiring) are settled in package 04E. |
| OD-MALWARE | Upload malware scanning | Real fail-closed ClamAV scanning is approved; deployment details are settled in package 02C. |
| OD-PLAN-ENFORCE-DIRECTION | Entitlement enforcement | Strong server-enforced entitlements are approved in direction; concrete limits and allowances remain open as OD-PLAN-LIMITS. |
| OD-US-DIRECTION | US content as EU evidence | No unqualified US content is used as factual EU labour-market evidence (approved); the residual choice is open as OD-US-CONTENT. |
| OD-REPORTING-SCOPE | Reporting scope | The complete reporting scope (prebuilt and custom reports) is approved; export formats remain open as OD-REPORT-EXPORT. |
| OD-PRINCIPLES | Standing principles confirmed | Strict user and Workspace isolation; no live billing for R1.0; no production launch with failed gates; no unapproved reclassification of R1.0 obligations; the 394 historical issues, closure evidence and failed historical gates stay intact. |

## Genuinely open decisions

| ID | Decision | Detail | Release | Type |
|---|---|---|---|---|
| OD-RESOURCE | Allocate the additional time and engineering resources the owner is prepared to provide | The owner has said additional time and engineering resources can be allocated; none is yet allocated, named or budgeted. Needed: who is the technical integration lead, which engineers, QA and DevOps staff or Claude Code sessions, the review capacity, the external reviewers (seven native reviewers, legal counsel, independent evaluators, licensing reviewer), the budget and the start dates. The staffing and critical-path plan (execution/STAFFING_AND_CRITICAL_PATH_PLAN.md) states what the full scope needs; nothing is assumed hired. | R1.0 | AWAITING |
| OD-LANG-02 | Approve each proposed primary market individually | Ireland, Germany, Spain, Italy, Portugal, France, Netherlands are proposals only; none is an approved country qualification. Each needs owner approval and source qualification (licence, authority, coverage). | R1.0 | AWAITING |
| OD-LANG-03 | Name the native-language reviewer for each of the seven languages | No reviewer is named; needed before LG-11. | R1.0 | AWAITING |
| OD-LANG-04 | Name the legal and privacy translation qualifier(s) | Needed before real-user access in each language (LG-10). | R1.0 | AWAITING |
| OD-RU-FUTURE | Whether and when Russian is ever activated | Russian is excluded from R1.0; any later activation is a separate decision, not an automatic R2.0 commitment. | UNSCHEDULED | AWAITING (future) |
| OD-HOSTED | Authorise and choose the hosted environment | Secure hosting is R1.0 scope; the provider, region and approval to create a hosted staging and production environment are not decided (EX-12). | R1.0 | AWAITING |
| OD-BUDGET | Approve a bounded live-evaluation and live-provider budget for qualification | Native-review samples, live multilingual Mo checks, semantic embedding builds and a larger RAGAS run need an explicit budget; the EUR 10 capstone demonstration budget is not reusable. | R1.0 | AWAITING |
| OD-GATE-THRESHOLDS | Approve numeric thresholds for the quality and safety gates | Injection detection and false-positive rates (REVIEW-01), retrieval quality (REVIEW-04), latency and availability targets and human-rating thresholds need owner-approved numbers before the corpora are frozen. Proposals will be made, not assumed. | R1.0 | AWAITING |
| OD-BULK-ACTIONS | Which restricted bulk user actions are permitted | The owner asked for carefully restricted bulk actions; the permitted set is not defined. | R1.0 | AWAITING |
| OD-REPORT-EXPORT | Which export formats the reports support | The owner asked for export in supported formats; the set is not defined. | R1.0 | AWAITING |
| OD-WS-TRANSFER | Workspace ownership transfer rules | Safe transfer is required; the acceptance procedure and constraints are not defined. | R1.0 | AWAITING |
| OD-COVERAGE | Approve the separate frozen R1.0 beta-scope coverage measure | The historical 95% gate (386 of 412 against 392, FAIL) is preserved unchanged; a separate measure for the enabled beta scope and licensed markets needs approval. | R1.0 | AWAITING |
| OD-ACADEMIC-01 | Confirm retirement of the academic-only capstone-submission tasks | Six historical items concern the capstone submission only (see traceability); they are not production dependencies. They are retired only on the owner's confirmation; none is silently closed. | UNSCHEDULED | AWAITING |
| OD-EMBED | Choose the production embedding provider and model | Phase 00 options: OpenAI embeddings directly, an EU-hosted OpenAI-compatible endpoint, or a self-hosted multilingual model; the choice needs a frozen seven-language retrieval comparison, a data-processing review and a budget. Production must refuse the lexical hash embedder (REVIEW-04). | R1.0 | AWAITING |
| OD-DEFER-PLACEMENT | Confirm placement of items that fit no agreed release theme | Items that are neither blockers nor part of an agreed release theme are placed in R1.1 (or R1.2 for Admin) as a proposal. | R1.1 | AWAITING |
| OD-PLAN-LIMITS | Which limits and allowances Basic and Premium carry during the free beta | Server-enforced entitlements are approved in direction. Open: the concrete values (history window, model profile access, usage allowances) for each free beta tier and whether any is enforced from day one; enabling an enforcement flips a gate constant that the reconciliation checks. | R1.0 | AWAITING |
| OD-US-CONTENT | May US-sourced content appear at all, as clearly labelled non-EU general information? | The owner approved that no unqualified US content is used as factual EU labour-market evidence. Open: whether US sources (O*NET, BLS) stay available only as clearly labelled non-EU general information, or are removed from Candidate retrieval entirely in the beta. Implemented by package 02D and REQ-COV-02. | R1.0 | AWAITING |
| OD-RECLASS | Item-level disposition of the ten proposed reclassifications | The owner retains every R1.0 fix and verify obligation until an item-level disposition is explicitly approved; the ten-item proposal (BL-5, BL-6, BL-6.1 to BL-6.5, BL-9, BL-12, W12.4E-12) is NOT applied. Each approval must distinguish a genuine later-release dependency from an R1.0 product cut (R1_SCOPE_RECLASSIFICATION_PROPOSAL.md). | R1.0 | AWAITING |

## Owner direction 2026-10-22: provisional recommendations (NOT approvals, NOT completed verification)

The owner authorised Wave 3a engineering and gave recommended defaults for nine decisions. They are recorded here as **PROVISIONAL recommendations**: each keeps its gate open until its own evidence, legal judgment or owner approval exists. Standing owner directions recorded with them: S1 full scope retained; reviewers (native-language, legal, security, independent AI) are appointed later and are never replaced by automated verification; OpenRouter is the primary LLM provider with configurable ceilings and no assumption of unlimited credit; non-destructive development-environment repair is authorised; the owner keeps authority over scope changes, spending limits, production deployment and release.

| ID | Provisional recommendation (owner's default) | What still keeps the decision open |
|---|---|---|
| OD-RESOURCE | Claude Code-led engineering; the owner retains integration and release authority; external specialists appointed for formal qualification | Appointing the specialists (calendar-bound; see the start-by dates) |
| OD-EMBED | Benchmark suitable multilingual embedding models through OpenRouter (39 embedding models are reachable, including `openai/text-embedding-3-large` and `-small`; see `execution/evidence/OPENROUTER_EMBEDDING_AVAILABILITY_2026-10-22.md`) and select by reproducible metrics: recall@k, nDCG@k, cross-language retrieval, citation accuracy, latency, cost, dimensions and index compatibility | The benchmark has not run; it needs the 05C budget governor and an owner-set ceiling; the selection is not made |
| OD-HOSTED | Staging-first, containerised, keeping the 05A topology; production needs separate authorisation | No hosting provider, region or authorisation; nothing is deployed |
| OD-BUDGET | OpenRouter-funded engineering and evaluation with configurable ceilings, usage monitoring and safeguards (built by 05C) | The ceiling values are the owner's to set; no paid run starts before the governor exists and a ceiling is configured |
| OD-COVERAGE | Preserve the historical targets; report overall coverage and the frozen beta-scope coverage separately | The beta-scope measure is defined and frozen by 02E and approved by the owner; the historical gate stays FAIL (386 of 412) |
| OD-BULK-ACTIONS | Previewed, authorised, audited bulk user operations with transaction and partial-failure handling | Not built (completion PR under 03C is scheduled); the permitted set of actions is to be fixed with the owner at review |
| OD-PLAN-LIMITS | Basic and Premium both free during the beta; define limits from measured operational and token costs, subject to owner approval | No measurement exists yet; values are not set |
| OD-WS-TRANSFER | Explicit transfer requiring authorisation, verified acceptance and immutable audit evidence | Not built (completion PR under 04B is scheduled, needs a migration); the exact procedure is for owner review |
| OD-REPORT-EXPORT | Governed CSV, JSON and PDF exports with authorisation, privacy protection and safe handling | CSV and JSON exist (03E1); PDF is scheduled in 03E2; other formats are out of scope |

## Decisions raised while building Waves 1 and 2 (2026-10-22; all awaiting the owner)

| ID | Decision | Detail | Release | Type |
|---|---|---|---|---|
| OD-INVITE-EMAIL | Send invitation emails? | 04E delivers copy-the-link only. An email needs eight locale templates, the guarded email service and a provider decision. | R1.0 | AWAITING |
| OD-INVITE-ISSUERS | Who may issue and revoke invitations | Only the `platform_admin` preset holds the permission (`platform.users.manage`); a delegated role needs a deliberate decision, not a new permission by default. | R1.0 | AWAITING |
| OD-PLAN-ACTIVATION-APPROVAL | Second approver for plan activation and bulk assignment | No existing rule requires one (two-person approval exists for price changes, refunds and role changes). | R1.0 | AWAITING |
| OD-STAGING-LANGUAGES | How to test a hosted stack while no language is qualified | 06H fails closed: staging and production accept no registration, chat or interview until a language has a complete approved record. Options: use a development-class API environment for synthetic testing, or qualify one language first. | R1.0 | AWAITING |
| OD-APPROVED-UNTIL | Is `approved_until` mandatory, and must the release SHA descend from the deployed build | 06H leaves both optional; 08A must compare the record's SHA with the real release SHA. | R1.0 | AWAITING |
| OD-SCANNER-ALERT | Own alert category for a scanner outage | The outage alert reuses `job_failed`, so its title reads "A background job failed terminally". A correct title needs a new category and a migration. | R1.0 | AWAITING |
| OD-FAKE-SCANNER-GUARD | Make fake-scanner records a blocking serving-guard finding in hosted environments | Detected and reported in readiness and approval is blocked; making serving blocking needs the 02A hosted test fixtures updated. | R1.0 | AWAITING |
| OD-WS-ADMIN-ENROL | Platform Admin enrolling an ordinary account into a Workspace | Staff accounts can no longer be enrolled; an operator can still enrol an ordinary account, which then reads what members share. Remove admin enrolment or require the owner's consent. | R1.0 | AWAITING |
| OD-STORY-PREPARE-CONSENT | Per-story picker and per-run consent in Prepare | Mo's Candidate Evidence specialist still reads usable stories under the existing opt-in; a per-run choice changes the agent request contract and belongs with the 01D and 01C order. | R1.0 | AWAITING |
| OD-HELDOUT-AUTHOR | Who authors the independent injection held-out set | A different author, several hundred cases with per-language quotas, frozen by hash; needed before thresholds can be approved. | R1.0 | AWAITING |
| OD-INPUT-GUARD-LANGUAGES | Multilingual rules for the interview input guard | The input guard is English-only; the corpus work found no non-English rule there. | R1.0 | AWAITING |
| OD-LEGACY-ROUTES | Retire the legacy Admin user status, plan and revoke routes | They remain because many tests pin them; a client calling them directly skips the mandatory reason. | R1.0 | AWAITING |
| OD-LOCAL-TEST-ENV | Rebuild the local fresh-dependency venv and Playwright browser cache | Both were deleted by something outside the work; rebuilding them needs downloads. Until then GitHub CI is the verification for fresh dependencies and browsers. | R1.0 | AWAITING |
| OD-STALE-02A-TEST | Retire or rebase the branch-relative 02A forbidden-files test | Fails on any local tree with later merges, passes in CI; a follow-up task is open. | R1.0 | AWAITING |

## Start-now schedule (planning model: assumed calendar floors, no holidays; see `execution/WAVE3_EXECUTION_PLAN.md` section 7)

Native reviewers and legal qualifiers named and engaged by Tue 27 Oct for a freeze finished by Fri 27 Nov; OD-EMBED and OD-REPORT-EXPORT by Mon 26 Oct; OD-HOSTED, OD-BUDGET, OD-COVERAGE, OD-BULK-ACTIONS, OD-PLAN-LIMITS and OD-WS-TRANSFER by Mon 2 Nov; licensing reviewer and counsel by Fri 6 Nov at the latest (earlier is better); independent evaluators by Fri 13 Nov. Each working day of delay moves the full-scope date by a working day; no scope is cut and no gate is waived.

## Historical pending owner decisions (72, preserved with their register IDs)

| ID | Decision | Owner action recorded | Priority | If approved: release | WP |
|---|---|---|---|---|---|
| IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20 | REQUIRED: confirm the deadline and time zone | P0 | UNSCHEDULED | WP-07 |
| IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | REQUIRED: ask the course lead; decide hosted versus local demonstration | P0 | UNSCHEDULED | WP-02 |
| IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | REQUIRED: approve or amend the recorded entry conditions; separate approval to create RC-P10-004 | P0 | UNSCHEDULED | WP-07 |
| B-EMBED-SEL | Embedding provider and model selection | Choose embedding provider/model | P1 | R1.0 | WP-06 |
| C-PROTO | Reviewer protocols and rating rubric for AI quality | Reviewer appointments, rating protocol | P1 | R1.0 | WP-16 |
| C-THRESH | Owner thresholds for AI quality | Owner sets thresholds and spend cap before final evaluation (evaluation-plan rule) | P1 | R1.0 | WP-16 |
| D-21 | D-21 name who performs qualified legal review | Owner to name legal reviewer | P1 | R1.0 | WP-04 |
| F2B1-OD-01 | Legal seller entity | Owner decision required | P1 | R1.1 | WP-11 |
| F2B1-OD-02 | Product classification (automated digital product) | Owner decision required | P1 | R1.1 | WP-11 |
| F2B1-OD-03 | Product tax code | Owner decision required | P1 | R1.1 | WP-11 |
| F2B1-OD-04 | What Premium includes beyond Basic | Owner decision required | P1 | R1.1 | WP-11 |
| F2B1-OD-05 | Premium monthly price | Owner decision required | P1 | R1.1 | WP-11 |
| I-ALLOW | Numerical Basic/Premium allowances not approved | Owner approval of numbers | P1 | R1.1 | WP-11 |
| I-ENT-POLICY | Paid entitlement policy unapproved | Approve trial/grace/refund/cancel/dispute rules | P1 | R1.1 | WP-11 |
| I-FAST | Basic-to-Fast transition not approved | Approve transition and notice | P1 | R1.1 | WP-11 |
| I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | Approve price | P1 | R1.1 | WP-11 |
| IR-DEVDB-STALE | The developer database is 12 Alembic revisions behind the code head | REQUIRED: migrate the developer database or leave it | P1 | R1.0 | WP-07 |
| IR-RAGAS-LIVE-APPROVAL | Live RAGAS evaluation awaits the owner's spending approval and three prerequisit | REQUIRED: approve the ceiling, the new ledger and the code change; provide the key | P1 | R1.0 | WP-06 |
| K-PROVIDER | Third-party model provider data handling for real candidate data | None recorded | P1 | R1.0 | WP-04 |
| SJA-05 | Knowledge approval has no distinct-actor rule or step-up | REQUIRED: whether knowledge approval and activation need a distinct-actor rule and/or fresh-password step-up (related A-04). Source qualific | P1 | R1.0 | WP-15 |
| B-COVEVAL | Decision whether to change coverage evaluator to check data origin/country (F-CO | Owner decision (c) in P10D s12 | P2 | R1.1 | WP-06 |
| C-USD15 | USD 15 extra ceiling not approved; 15 calls remain | Owner approval to raise limits | P2 | R1.1 | WP-16 |
| D-01 | D-01 adopt or amend recovered GKB/C1-C4 specification | D-01 | P2 | R1.1 | WP-06 |
| D-02 | D-02 adopt ambiguity-state and recency/eligibility policy | D-02 | P2 | R1.1 | WP-06 |
| F2B-D22 | D-22 ASHE weekly never annualised; unanswered | D-03, D-22, D-04, D-12, D-13, D-15 | P2 | R1.1 | WP-06 |
| F2B1-OD-06 | Premium annual price (no annual plan exists) | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-07 | Currency | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-08 | Tax-inclusive presentation | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-09 | Supported customer countries | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-10 | B2B subscriptions | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-11 | Trial policy | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-12 | Failed-payment grace period | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-13 | Cancellation policy | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-14 | Refund policy | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-15 | Dispute entitlement policy | Owner decision required | P2 | R1.1 | WP-11 |
| F2B1-OD-16 | Billing data retention | Owner decision required | P2 | R1.1 | WP-11 |
| H-REDIS-POLICY | Redis failure policy per bucket undecided | Failure policy per bucket | P2 | R1.0 | WP-02 |
| I-GRANDFATHER | Grandfathering of existing candidates | Decision | P2 | R1.1 | WP-11 |
| I-HISTORY-SHARE | Existing-share policy before history activation | Decision | P2 | R1.1 | WP-09 |
| I-RESET | Quota reset periods not approved | Owner approval | P2 | R1.1 | WP-11 |
| K-ATTR | Attribution wording decisions | None recorded | P2 | R1.0 | WP-04 |
| K-LEGALACC | Legal acceptance of owner policy decisions | None recorded | P2 | R1.0 | WP-04 |
| M-LEDGER | Mo and company-research cost-ledger gap | Whether Mo/company research must enter ledger before launch | P2 | R1.0 | WP-15 |
| PRIV-BILL-RET | Billing data retention and erasure review | Owner and legal retention decision | P2 | R1.1 | WP-04 |
| PRIV-POLICY01 | Verified-email policy (POLICY-01) | Policy decision before public launch | P2 | R1.0 | WP-04 |
| PRIV-RET | No retention periods for candidate content | Retention schedule | P2 | R1.0 | WP-04 |
| W9.8-D7 | Original-file export bundle | Scope decision | P2 | R1.0 | WP-04 |
| A-AGG | Five BLS-specific aggregates quarantined | Later policy review | P3 | R1.1 | WP-06 |
| D-05 | D-05 padded ISCO identity and plan for 21 legacy rows | D-05 | P3 | R1.1 | WP-06 |
| D-06 | D-06 baseline manifest freeze (GKB-0) | D-06 (status ambiguous between documents) | P3 | R1.1 | WP-06 |
| D-07 | D-07 ESCO language releases | D-07 | P3 | UNSCHEDULED | WP-06 |
| D-10 | D-10 FX and PPP sources and methodology | D-10 | P3 | R1.1 | WP-06 |
| D-11 | D-11 secondary-data qualification criteria | D-11 | P3 | R1.1 | WP-06 |
| D-14 | D-14 regional-geography classification rule (policy p10c-d/1) | D-14 | P3 | R1.1 | WP-06 |
| D-16 | D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT) | D-16 | P3 | R1.0 | WP-06 |
| D-17 | D-17 evidence-state vocabulary adoption | D-17 | P3 | R1.1 | WP-06 |
| D-18-19 | D-18 / D-19 South America region vocabularies and national classifications | D-18, D-19 | P3 | R1.1 | WP-06 |
| IR-REHEARSAL-CALL | One unplanned live agent run during the P11 rehearsal (outside the P10E ledger) | REQUIRED: acknowledge the unplanned call | P3 | R1.1 | WP-15 |
| J-OIDC-PWD | OIDC-only users cannot set a password via recovery | Product decision | P3 | R1.1 | WP-03 |
| M-LEGACY01 | Legacy Streamlit UI retained (LEGACY-01) | Retirement task | P3 | R1.1 | WP-15 |
| M-POLICY02 | Evaluation score consistency (POLICY-02) | Decision | P3 | R1.1 | WP-15 |
| PRIV-SUPPORT-NOTICE | Support data / privacy request response time | Whether to commit to response-time statements | P3 | R1.0 | WP-04 |
| SJA-01 | AI config: second approver must be a second Platform Admin | Possible future permission review; none made | P3 | R1.1 | WP-15 |
| SJA-02 | Knowledge Admin cannot retry/cancel failed jobs | Possible future permission review; none made | P3 | R1.1 | WP-15 |
| SJA-03 | Billing/Security-Privacy admins cannot see queue state | Possible future permission review; none made | P3 | R1.1 | WP-15 |
| SJA-04 | Operations Admin partly useful Review/Diagnostics | Whether to add permission or hide the destination | P3 | R1.2 | WP-10 |
| W9.8-D1b | Preparation-chat selective deletion | Prioritisation not recorded | P3 | R1.0 | WP-04 |
| W9.8-D3 | Bulk memory deletion | Not scheduled; no decision recorded | P3 | R1.0 | WP-04 |
| W9.8-D4 | Per-version document deletion | Not scheduled | P3 | R1.0 | WP-04 |
| W9.8-D5 | Auth-session list/revoke UI | Not scheduled | P3 | R1.0 | WP-04 |
| W9.8-D6 | Feedback list and deletion page | Not scheduled | P3 | R1.0 | WP-04 |
| W9.8-D8 | Orphan workspace invitations to a deleted user's email | Not scheduled | P3 | R1.0 | WP-09 |

## Academic-only capstone tasks awaiting confirmation of retirement (6; OD-ACADEMIC-01)

| ID | Title | Historical status | Why academic only |
|---|---|---|---|
| G-WALK-ENV | Admin walkthrough used dev server and seeded data | DEFERRED - POST SUBMISSION | the capstone Admin walkthrough used a development server and seeded data |
| IR-AC-LEDGER | Acceptance criteria dispositions are P9-era and spread over three documents | OPEN - PRE-SUBMISSION QUALIFICATION | single reconciled capstone acceptance ledger for the submission (the historical ledger stays as recorded) |
| IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20 | PENDING OWNER DECISION | the course deadline and time zone concern the capstone submission |
| IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | PENDING OWNER DECISION | the course deployment expectation concerns the capstone submission (production hosting is tracked separately in WP-02) |
| IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | PENDING OWNER DECISION | RC-P10-004 entry specification for the capstone release-candidate convention |
| IR-TURING-RUBRIC | The Turing College capstone brief and rubric are not in the repository | PARTIALLY REMEDIATED | the course brief and rubric concern the capstone submission |

## New items needing an owner decision (12)

| ID | Title | Proposed release | Provenance |
|---|---|---|---|
| REQ-COV-01 | Define a separate frozen R1.0 beta-scope coverage measure | R1.0 | AWAITING_APPROVAL |
| REQ-LANG-16 | Approve and qualify each proposed primary market individually | R1.0 | AWAITING_APPROVAL |
| XC-AC-AC-18 | Acceptance ledger (current) AC-18: Review surfaces: owned recent runs, safe specialist events, bound | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-AC-AC-23 | Acceptance ledger (current) AC-23: Voice measurement: defined sample, reference transcripts, correct | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-AC-AC-24 | Acceptance ledger (current) AC-24: Pilot and lessons: actual participant observations distinguished  | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-AC-AC-25 | Acceptance ledger (current) AC-25: Submission consistency: README, three decks, selected ten-minute  | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-P9-Deep-page-localization-debt | P9 quality register (carried items) Deep-page-localization-debt: Deep-page localization debt | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-P9-Live-multi-agent-provider-qual | P9 quality register (carried items) Live-multi-agent-provider-qual: Live multi-agent/provider qualit | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-P9-Live-transactional-email | P9 quality register (carried items) Live-transactional-email: Live transactional email | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-P9-Untracked-checkpoint-deletion | P9 quality register (carried items) Untracked-checkpoint-deletion-: Untracked checkpoint deletion re | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-REL-R-33 | Release acceptance matrix (P10B) R-33: Email-verification behaviour pinned | R1.0 | DISCOVERED_BY_CROSS_CHECK |
| XC-REL-R-97 | Release acceptance matrix (P10B) R-97: Google OIDC live behaviour unvalidated | R1.0 | DISCOVERED_BY_CROSS_CHECK |

Task 04 Redis preparation: [topology, outage matrix, readiness and monitoring recommendation](execution/WAVE4_TASK04_REDIS_DECISIONS.md). **H-REDIS-POLICY and OD-HOSTED remain OPEN**; disposable tests and a generated profile are not owner approval or staging authorization.
