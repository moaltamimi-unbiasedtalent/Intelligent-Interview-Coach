# Owner Decision Register (Production Roadmap V2.2, corrected)

**Status:** corrected 2026-10-21 against the owner's authoritative requirements (`OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md`). Only decisions that are genuinely still awaiting the owner are listed as open. Decisions the owner has already made (languages, Russian exclusion, R1.3 languages, release train, free invitation-only beta, English-only Admin, Basic/Premium as free beta tiers, the owner-requested capabilities and the five reviewer findings) are **requirements**, not open decisions, and are no longer listed here. Earlier open items that were resolved by the recovered text: OD-LANG-01, OD-LANG-05, OD-LANG-06, OD-REQ-TEXT, OD-REVIEW-FINDINGS, OD-RELEASE-TRAIN.

## Genuinely open decisions

| ID | Decision | Detail | Release | Type |
|---|---|---|---|---|
| OD-SCOPE-01 | What happens if a mandatory R1.0 gate is not met by 30 November 2026 | The date is the owner's target and safety, privacy, licensing and operational gates are not waived. If a gate is not met: delay R1.0, remove the affected feature from scope, or keep it disabled. Phase 00 PROPOSES (not approved) a restricted free private beta of scope tiers T0 to T2 (small capped invitation-only cohort, languages and markets activated only where gates pass, Admin dashboards, plan editor and report builder moved to R1.2) and a capacity-based minimum safe beta (T0, T1 and journey reliability) as an alternative; the computed effort needs roughly 9 to 15 and 6 to 10 parallel streams respectively. See execution/DELIVERY_SCHEDULE.md and execution/PHASE_00_EXIT_REPORT.md. The owner supplies the real capacity. | R1.0 | AWAITING |
| OD-LANG-02 | Approve each proposed primary market individually | Ireland, Germany, Spain, Italy, Portugal, France, Netherlands are proposals only; none is an approved country qualification. Each needs owner approval and source qualification (licence, authority, coverage). | R1.0 | AWAITING |
| OD-LANG-03 | Name the native-language reviewer for each of the seven languages | No reviewer is named; needed before LG-11. | R1.0 | AWAITING |
| OD-LANG-04 | Name the legal and privacy translation qualifier(s) | Needed before real-user access in each language (LG-10). | R1.0 | AWAITING |
| OD-RU-FUTURE | Whether and when Russian is ever activated | Russian is excluded from R1.0; any later activation is a separate decision, not an automatic R2.0 commitment. | UNSCHEDULED | AWAITING (future) |
| OD-HOSTED | Authorise and choose the hosted environment | Secure hosting is R1.0 scope; the provider, region and approval to create a hosted staging and production environment are not decided (EX-12). | R1.0 | AWAITING |
| OD-BUDGET | Approve a bounded live-evaluation and live-provider budget for qualification | Native-review samples, live multilingual Mo checks, semantic embedding builds and a larger RAGAS run need an explicit budget; the EUR 10 capstone demonstration budget is not reusable. | R1.0 | AWAITING |
| OD-GATE-THRESHOLDS | Approve numeric thresholds for the quality and safety gates | Injection detection and false-positive rates (REVIEW-01), retrieval quality (REVIEW-04), latency and availability targets and human-rating thresholds need owner-approved numbers before the corpora are frozen. Proposals will be made, not assumed. | R1.0 | AWAITING |
| OD-PLAN-ENFORCE | Which entitlements are enforced during the free beta | Basic and Premium are both free beta tiers. Decide whether the history window and model-profile gating (currently disabled by code constants) stay disabled or are enforced for the beta; enabling either changes a gate constant that the reconciliation checks. | R1.0 | AWAITING |
| OD-ADMIN-NAV | Confirm the Admin navigation groups | The owner suggested Command Center; Customers and Workspaces; Products and Commercial; AI and Knowledge; Insights and Operations; Governance and Settings. | R1.0 | AWAITING |
| OD-BULK-ACTIONS | Which restricted bulk user actions are permitted | The owner asked for carefully restricted bulk actions; the permitted set is not defined. | R1.0 | AWAITING |
| OD-REPORT-EXPORT | Which export formats the reports support | The owner asked for export in supported formats; the set is not defined. | R1.0 | AWAITING |
| OD-WS-TRANSFER | Workspace ownership transfer rules | Safe transfer is required; the acceptance procedure and constraints are not defined. | R1.0 | AWAITING |
| OD-INVITE | Invitation mechanism for the private beta | Invitation-only registration is decided; whether it uses invitation codes, an email allow-list or another mechanism is not. | R1.0 | AWAITING |
| OD-MALWARE | Select the real malware-scanning provider for user uploads | Genuine fail-closed scanning is required (the fake scanner is development-only); the product choice and hosting are not decided. | R1.0 | AWAITING |
| OD-COVERAGE | Approve the separate frozen R1.0 beta-scope coverage measure | The historical 95% gate (386 of 412 against 392, FAIL) is preserved unchanged; a separate measure for the enabled beta scope and licensed markets needs approval. | R1.0 | AWAITING |
| OD-ACADEMIC-01 | Confirm retirement of the academic-only capstone-submission tasks | Six historical items concern the capstone submission only (see traceability); they are not production dependencies. They are retired only on the owner's confirmation; none is silently closed. | UNSCHEDULED | AWAITING |
| OD-EMBED | Choose the production embedding provider and model | Phase 00 options: OpenAI embeddings directly, an EU-hosted OpenAI-compatible endpoint, or a self-hosted multilingual model; the choice needs a frozen seven-language retrieval comparison, a data-processing review and a budget. Production must refuse the lexical hash embedder (REVIEW-04). | R1.0 | AWAITING |
| OD-US-CONTENT | Whether US-sourced content (O*NET, BLS) is enabled in the EU beta | The curated corpus is US-centred while the R1.0 markets are EU. Decide whether US content stays enabled for candidates, is limited to labelled general guidance, or is disabled; and whether the US occupational measurement and alias reviews (BL-5, BL-6 series, BL-7, BL-9) and Compensation V2 authorisation (BL-12) move out of R1.0 (proposed in Phase 00 package 00B). | R1.0 | AWAITING |
| OD-DEFER-PLACEMENT | Confirm placement of items that fit no agreed release theme | Items that are neither blockers nor part of an agreed release theme are placed in R1.1 (or R1.2 for Admin) as a proposal. | R1.1 | AWAITING |

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
