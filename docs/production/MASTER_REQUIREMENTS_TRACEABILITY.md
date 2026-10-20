# Master Requirements Traceability (Production Roadmap V2.2)

**Status:** PROPOSED baseline for owner review, generated 2026-10-21 by `scripts/production/reconcile_issues.py`. Nothing here upgrades a historical status or gate. The full per-item record (acceptance criteria, required tests, security/privacy impact, dependencies, evidence of closure, the verbatim historical row) is in [`PRODUCTION_ISSUE_RECONCILIATION.json`](PRODUCTION_ISSUE_RECONCILIATION.json); the tables below are the readable index.

Baseline: 394 register issues (52 closed, 342 active) + 58 new items = 452 traced rows. Unmapped: **0**.

Dispositions: FIX BEFORE R1.0, VERIFY BEFORE R1.0, OWNER DECISION, DEFER TO NAMED RELEASE (only while the feature stays disabled), CLOSE WITH EVIDENCE.

## Work packages

| WP | Name | Owner role (person not yet named) | Items |
|---|---|---|---|
| WP-01 | Governance, reviewers and owner decisions | Product Owner | 5 |
| WP-02 | Hosted deployment, operations and resilience | Platform and operations lead | 46 |
| WP-03 | Identity, email and access | Security lead | 8 |
| WP-04 | Privacy, data rights and legal | Privacy and legal lead | 33 |
| WP-05 | AI security and grounding policy | AI safety lead | 20 |
| WP-06 | Knowledge sources and retrieval (seven markets) | Knowledge and data lead | 92 |
| WP-07 | Candidate journeys, Mo and Practice quality | Product lead (candidate) | 17 |
| WP-08 | Multilingual programme (seven languages) | Localisation lead | 28 |
| WP-09 | Story Bank, Workspaces and shared reports | Product lead (collaboration) | 10 |
| WP-10 | Admin 2.0 (English-only): users, plans, reports, knowledge, navigation | Product lead (operations) | 36 |
| WP-11 | Commercial and billing (gated) | Commercial lead | 35 |
| WP-12 | Speech and realtime voice (gated) | Speech lead | 27 |
| WP-13 | External integrations | Integrations lead | 9 |
| WP-14 | Human validation and native review | Quality and human-review lead | 11 |
| WP-15 | Quality engineering, accessibility and technical debt | Engineering lead | 51 |
| WP-16 | Live evaluation and measurement | Evaluation lead | 21 |
| WP-17 | AI platform engineering: versioned prompts, tool catalogue, streaming | AI platform lead | 3 |

## Rules (proposed)

| Rule | Meaning |
|---|---|
| C0 | Historically CLOSED - VERIFIED: closure evidence preserved |
| O0 | Historically PENDING OWNER DECISION: owner decides; release shown is proposed if approved |
| B1 | Blocks any production release and is not in an R1.0-excluded feature family: FIX (or VERIFY when never run/verified/human-reviewed) before R1.0 |
| B2 | Safety/privacy/public-claim relevance for an enabled R1.0 feature: VERIFY before R1.0 |
| B3 | Production impact unknown at P0/P1: VERIFY before R1.0 |
| S1 | AI-safety (D), privacy (F) or legal (K) item at P0-P2 or with a security/privacy impact: VERIFY before R1.0, never deferred while its feature is enabled |
| M1 | Source qualification for one of the seven R1.0 markets: VERIFY before R1.0 |
| D-GEN | No production impact, no enabled-feature dependency, no agreed release theme: R1.1 (placement proposed, OD-DEFER-PLACEMENT) |
| D-ADM | As D-GEN but Admin-related: R1.2 (placement proposed) |
| D-COM | Commercial activation and plan expansion: R1.1 while billing gates stay False |
| D-INT | Later integrations: R1.2 (alerts), R1.5 (market data) or R1.7 (enterprise) while not configured |
| D-INTL | Additional-country evidence R1.5, compensation R1.6, while Compensation V2 and international sources stay disabled |
| D-SPEECH | Server speech and voice practice: R1.4 while governed speech gates stay False |
| U-RU | Russian: excluded from R1.0; any activation is a separate future owner decision (UNSCHEDULED) |
| A0 | Academic-only capstone-submission task: not a production dependency; owner confirms retirement (UNSCHEDULED) |
| D-FL | Mandarin, Hindi, Arabic: R1.3 |
| +dup | Same meaning as an earlier issue: shares its disposition |

## R1.0: 30 November 2026: free, invitation-only private production beta; seven languages each subject to individual qualification; Admin 2.0 essentials; reliable Knowledge Sources; Story Bank and Workspaces; core reporting; the five reviewer corrections; no live billing

197 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| BL-1 | Verify reviewer identities and accounts | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 | P0 | DEFERRED - POST SUBMISSION | B1 |
| BL-2 | Appoint named human reviewers A, B, C | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 | P0 | DEFERRED - POST SUBMISSION | B1 |
| BL-3 | Complete two-person role changes for appointments | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 | P0 | DEFERRED - POST SUBMISSION | B1 |
| BL-8 | Legal review of commercial use of BLS content outside US (RB-LIC-1) | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P0 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| K-PRIV | Privacy, Terms and AI-transparency pages are engineering drafts | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P0 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| REQ-BETA-01 | Invitation-only registration for the private beta | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-03 | P0 | NOT VERIFIED - no invitation-only registration control is re | NEW |
| REQ-CAND-01 | Real Candidate end-to-end journey tests including Start interview | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-07 | P0 | NOT STARTED | NEW |
| REQ-COV-02 | Exclude unsupported or unlicensed market evidence from enabled features | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-06 | P0 | NOT VERIFIED | NEW |
| REQ-DEFER-01 | Verify every deferral leaves the feature inaccessible through UI and backend | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-15 | P0 | PARTIAL - gate constants are checked False; no consolidated  | NEW |
| REQ-OWN-05 | Knowledge Sources: permanent persistence and reliability | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-06 | P0 | PARTIAL - governed lifecycle, worker, readiness and curated- | NEW |
| REVIEW-01 | Prompt-injection defence depth (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-05 | P0 | PARTIAL - heuristic detector and tool allow-list exist; none | NEW |
| REVIEW-04 | Silent embedding degradation (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-06 | P0 | PARTIAL - local hash embedder is the working default; readin | NEW |
| A-K1 | Germany K1 governed compensation set is an engineering draft | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| B-SCANNER | Real malware scanner not configured for governed knowledge uploads | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| BL-11 | Satisfy the 95% product-coverage gate (392 of 412) | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | OPEN - PRE-SUBMISSION QUALIFICATION | B1 |
| BL-12 | Separate runtime authorisation and deployment review for Compensation V2 | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-18 | Human measurement/alias reviews, appointments, persistent authorisation, licensing clearan | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-19 | P10F targeted human validation | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-14 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-4 | Decide on privileged reviewer endpoints | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-5 | Review and decide the 12 measurement batches | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6 | Review the five alias proposals individually | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.1 | Alias decision: Software Developer to 15-1252 | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.2 | Alias decision: Human Resources Manager to 11-3121 | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.3 | Alias decision: Sales Manager to 11-2022 | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.4 | Alias decision: Accountant to 13-2011 | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.5 | Alias decision: Financial Analyst to 13-2051 | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.6 | Data Analyst and Product Manager remain unresolved | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-7 | Resolve Data Analyst / Product Manager evidence gaps | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-9 | Persistent-registry authorisation and promotion of us_soc_2018 and bls_oews | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| DEMO-02 | Wrong stack mode silently broke Start interview (keyless stack, generic unavailable messag | DEMO-OBSERVED | FIX BEFORE R1.0 | WP-02 | P1 | NEW - NOT STARTED | NEW |
| EX-12.1 | EX-12 #1: TLS + HSTS live | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.10 | EX-12 #10: Private storage isolation | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.3 | EX-12 #3: Same-site session cookie | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.7 | EX-12 #7: Backup produces restorable artifacts | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.8 | EX-12 #8: Restore drill into *_restore DB | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.9 | EX-12 #9: Rollback | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| H-KB-INGEST | Knowledge-ingestion security hardening | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | PARTIALLY REMEDIATED | B1 |
| H-MONITOR | Production monitoring and observability | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P1 | DEFERRED - POST SUBMISSION | B1 |
| K-GDPR | No GDPR compliance/certification claim permitted | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P1 | DEFERRED - POST SUBMISSION | B1 |
| K-HUMANSRC | Human source qualification | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P1 | DEFERRED - POST SUBMISSION | B1 |
| K-TRANS-LEGAL | Engineering translations of legal/privacy/trust text | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-08 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| L-AC24 | AC-24 Pilot and lessons remains PARTIAL | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-14 | P1 | OPEN - PRE-SUBMISSION QUALIFICATION | B1 |
| REQ-LANG-01 | Audit every existing locale | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-02 | Verify all Candidate journeys in all seven languages | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-03 | Prompts and system policies work correctly in each language | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-04 | Validate localized interview questions, scoring, feedback and explanations | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-05 | Verify Story Bank and Workspaces in all seven languages | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-06 | Evaluate multilingual RAG and cross-language source attribution | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-07 | Language must never change labour-market country silently | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-08 | Language-specific injection, security and privacy regression suites | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-09 | Native-language human review | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-10 | Qualify legal and privacy translations before real-user access | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-11 | Track readiness and quality separately per language | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-12 | Keep Platform Admin English-only for R1.0 | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-13 | No language is called production-qualified before its gates pass | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-LANG-14 | Remove Russian from active Candidate language selection for R1.0 | LANGUAGE-DECISION | FIX BEFORE R1.0 | WP-08 | P1 | NOT STARTED | NEW |
| REQ-OWN-01 | Admin Platform 2.0: Command Center and AI operations | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-10 | P1 | PARTIAL - Command Center, AI administration, provider readin | NEW |
| REQ-OWN-02 | Admin Plans: Basic/Premium management | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-10 | P1 | PARTIAL - versioned plans, assignment and an entitlement ser | NEW |
| REQ-OWN-03 | Admin Users: complete operational user management | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-10 | P1 | PARTIAL - user list, lifecycle, role-change approval and ses | NEW |
| REQ-OWN-04 | Admin Reports: prebuilt reports and governed custom report builder | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-10 | P1 | PARTIAL - aggregate reporting with suppression exists (W10.1 | NEW |
| REQ-OWN-06 | Story Bank: complete functional Story Bank | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-09 | P1 | PARTIAL - source-backed, revocation-aware story bank exists  | NEW |
| REQ-OWN-07 | Workspaces: complete functional Workspaces | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-09 | P1 | PARTIAL - Workspaces, invitations, VIEW-only shares and revo | NEW |
| REQ-OWN-08 | Admin navigation redesign and Review and Diagnostics relocation | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-10 | P1 | PARTIAL - flat Admin navigation exists; Review and Diagnosti | NEW |
| REVIEW-02 | Externalized, versioned prompts (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-17 | P1 | NOT STARTED - prompts are code literals; a prompt registry a | NEW |
| REVIEW-03 | Tool catalogue parity (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-17 | P1 | NOT STARTED - registry exists; descriptions are duplicated i | NEW |
| REVIEW-05 | Agent streaming and feedback (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-17 | P1 | NOT STARTED - synchronous run API only | NEW |
| A-04 | Step-up only for role changes (journey finding) | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-15 | P2 | PARTIALLY REMEDIATED | B1 |
| EX-12.15 | EX-12 #15: Single-replica limits documented and honoured | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | PARTIALLY REMEDIATED | B1 |
| EX-12.2 | EX-12 #2: Automatic cert issuance/renewal | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.4 | EX-12 #4: CORS allowlist enforced | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| H-ENV | Cross-environment configuration | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | PARTIALLY REMEDIATED | B1 |
| H-MFA | Step-up is password re-authentication, not MFA | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | DEFERRED - POST SUBMISSION | B1 |
| H-REAPER | Quota reservation reaper not scheduled | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | DEFERRED - POST SUBMISSION | B1 |
| H-RESILIENCE | Provider operational resilience live behaviour | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P2 | PARTIALLY REMEDIATED | B1 |
| I-D02 | Pricing page vs account page inconsistency (journey D-02) | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-11 | P2 | PARTIALLY REMEDIATED | B1 |
| J-BREVO-HOOK | Brevo delivery/bounce webhooks not implemented | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-03 | P2 | DEFERRED - POST SUBMISSION | B1 |
| J-INTEG-READY | Production integration readiness | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-13 | P2 | DEFERRED - POST SUBMISSION | B1 |
| J-OPENROUTER | OpenRouter live behaviour beyond P10E sample | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-13 | P2 | PARTIALLY REMEDIATED | B1 |
| M-DOC-COVERAGE | Stale committed product-coverage summary (97%) | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-15 | P2 | PARTIALLY REMEDIATED | B1 |
| PRIV-BACKUP | Backup erasure after account deletion | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P2 | DEFERRED - POST SUBMISSION | B1 |
| W12.4E-12 | Server-side browser recording client | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-12 | P2 | DEFERRED - POST SUBMISSION | B1 |
| W12.4E-16 | Browser disclosure legal/privacy review | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-12 | P2 | DEFERRED - POST SUBMISSION | B1 |
| W9.8-D10 | Additional account-deletion safeguards | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| W9.8-D1a | Preparation-chat ownership index | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| W9.8-D2 | Consent/legal acceptance version history | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| W9.8-D9 | Audit context allow-list enforcement | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| H-CSRF | CSRF posture | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P3 | DEFERRED - POST SUBMISSION | B1 |
| H-WORKER | Governed knowledge and jobs depend on a separate worker | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-02 | P3 | DEFERRED - POST SUBMISSION | B1 |
| B-EMBED-CRED | Embedding credential and guard coverage absent | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P1 | NOT RUN | B2 |
| B-SEMCAL | Semantic live calibration NOT RUN | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P1 | NOT RUN | B2 |
| C-CITE | Citation claim-support (faithfulness) review | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-16 | P1 | PENDING HUMAN REVIEW | B1 |
| C-INT-HUMAN | Human-rated interview question/answer-evaluation quality | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-16 | P1 | PENDING HUMAN REVIEW | B1 |
| C-KB-HUMAN | Human review of KB model answers (citation support, language, abstention) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-16 | P1 | PENDING HUMAN REVIEW | B1 |
| C-NATIVE | Native-language review of multilingual model answers | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-08 | P1 | PENDING HUMAN REVIEW | B1 |
| CJ-D-02 | Pricing page versus account page wording for Premium | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| D-08 | D-08 who curates aliases | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P1 | PARTIALLY REMEDIATED | B2 |
| D-LANG | Localized policy sentences are engineering translations | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-08 | P1 | PENDING HUMAN REVIEW | B1 |
| D-NOT-LIVE | Final corrections not live-validated | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P1 | NOT RUN | S1 |
| DEMO-01 | Admin Knowledge Sources looked empty although the curated corpus was intact | DEMO-OBSERVED | VERIFY BEFORE R1.0 | WP-10 | P1 | CLOSED IN CODE (PR #210); verification pending | NEW |
| DEMO-03 | Live RAGAS result is PARTIAL (7 of 8 valid), relevancy 0.0 and context recall 0.0 | DEMO-OBSERVED | VERIFY BEFORE R1.0 | WP-16 | P1 | NEW - NOT STARTED | NEW |
| H-BACKUP | Deployment and backup qualification | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P1 | NOT RUN | B1 |
| H-PG-MULTI | Hosted multi-instance PostgreSQL not tested | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P1 | NOT RUN | B1 |
| H-REDIS-LIVE | Live Redis validation | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P1 | NOT RUN | B1 |
| IR-AC03-TESTS | AC-03 has no test for two-opportunity context selection, restart persistence or legacy-row | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| IR-AC18-RUNLIST | AC-18: no owner-scoped list of recent agent runs; selected-run retrieval evidence not show | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| IR-DEMO-KEY | A working copy with .env or .streamlit/secrets.toml makes the local backend contact the pr | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| J-BREVO | Brevo live verification | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-03 | P1 | NOT RUN | B1 |
| J-CLAMAV | Real malware scanner not configured | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-13 | P1 | NOT RUN | B1 |
| J-REDIS | Redis integration unverified | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-13 | P1 | NOT RUN | B1 |
| K-AIGUID | Legal/privacy review of AI-guidance and source-excerpt wording | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P1 | PENDING HUMAN REVIEW | B1 |
| L-PRODQ | Production-quality human evaluation overall | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| L-REL-1 | No calibrated relevance floor | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P1 | PARTIALLY REMEDIATED | B2 |
| L-ROUTE-1 | Non-English routing and structured lanes are English-keyword driven | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B2 |
| L-XLANG-1 | No cross-language semantic retrieval; native-phrasing queries unmeasured | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-08 | P1 | PARTIALLY REMEDIATED | B2 |
| P2-01 | Human revalidation: Sharing and revocation discoverability | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| P2-02 | Human revalidation: Source-backed experience in a representative knowledge environment | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| P2-03 | Human revalidation: Answer score interpretation | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1+dup |
| P2-04 | Human revalidation: AI-generated vs sourced vs verified provenance clarity | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| PRIV-LEGAL | Legal counsel review of Privacy, Terms and policy drafts | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P1 | PENDING HUMAN REVIEW | B1 |
| REQ-SCOPE-01 | A disabled feature must not block an unrelated safe beta feature | OWNER-REQUIREMENT | VERIFY BEFORE R1.0 | WP-01 | P1 | APPLIED IN THIS RECONCILIATION | NEW |
| AC-13/AC-23-A | Live browser STT correction burden NOT RUN | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-12 | P2 | NOT RUN | B1 |
| BL-14 | P10C-F2C ESCO/ISCO | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P2 | DEFERRED - POST SUBMISSION | M1 |
| BL-15 | P10C-F2D Germany and EU | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-06 | P2 | DEFERRED - POST SUBMISSION | M1 |
| D-AGENT-TXT | Agent figure verification limited to tool results and candidate text | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-CITE-PROXY | Citation relevance is a shared-content-word proxy | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-09 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-EST-FLAG | Unsourced-estimate offer in abstentions (flag fired 7/7) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | PARTIALLY REMEDIATED | S1 |
| D-LEX | Lexical detection limits | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-MISS-AMB | Historical agent miss: ambiguous_role_hitl (no retrieval, no confirm_role pause) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | PARTIALLY REMEDIATED | S1 |
| D-MISS-INS | Historical agent miss: insufficient_evidence (no retrieval) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | PARTIALLY REMEDIATED | S1 |
| D-MISS-PREP | Historical agent miss: prep_plan_request (no tool, no gaps in state) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | PENDING HUMAN REVIEW | S1 |
| D-NONNUM | Nonnumeric unsupported factual claims | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-POLB | Policy B retrieval decision remains model-driven | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| DEMO-04 | Blocking calls inside async request paths can deadlock the event loop | DEMO-OBSERVED | VERIFY BEFORE R1.0 | WP-15 | P2 | FIXED IN GUARD; audit not started | NEW |
| DEMO-05 | Optional-dependency tests failed in the base CI install | DEMO-OBSERVED | VERIFY BEFORE R1.0 | WP-15 | P2 | FIXED FOR RAGAS; audit not started | NEW |
| EX-12.11 | EX-12 #11: Pause switch (hosted) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.12 | EX-12 #12: Email verification flow (hosted) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.13 | EX-12 #13: Malware fail-closed (hosted) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.14 | EX-12 #14: CSP / mic permissions | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.5 | EX-12 #5: Readiness gating | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.6 | EX-12 #6: Migration step (single head) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| H-FAILPATH | Remaining failure-path testing | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| H-PG-QUERY | Analytics PostgreSQL query-plan review open | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| J-OCR | Live OCR quality unvalidated | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-13 | P2 | NOT RUN | B1 |
| J-OIDC | Google OIDC live validation and frontend wiring | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-03 | P2 | NOT RUN | B1 |
| J-RATE | Provider rate limits and failure handling live | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-03 | P2 | NOT RUN | B1 |
| J-SEMANTIC | Semantic live calibration (L-REL-1/L-XLANG-1) NOT RUN | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-08 | P2 | NOT RUN | B1 |
| K-LIC-DE | German Entgeltatlas (no terms) and Destatis (third-party catalogue licence) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-08 | P2 | PENDING HUMAN REVIEW | B1 |
| K-LIC-ESCO | ESCO data licence not named | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P2 | PENDING HUMAN REVIEW | B1 |
| K-LIC-ISCO | ISCO-08 reuse beyond short excerpts needs ILO permission | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P2 | PENDING HUMAN REVIEW | B1 |
| K-LIC-OGL | Commercial use outside home territory of OGL/Eurostat/INEGI content | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P2 | PENDING HUMAN REVIEW | B1 |
| M-OR-KEY | Shared OpenRouter credential concerns | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-09 | P2 | NOT VERIFIED | B1 |
| R-96a | PostgreSQL job claim (SKIP LOCKED) not executed live | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT VERIFIED | B1 |
| R-96b | PostgreSQL audit-trigger DDL not executed live | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT VERIFIED | B1 |
| D-COUNTRY | Country-name coverage table | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P3 | DEFERRED - POST SUBMISSION | S1 |
| D-MISS-5TH | Fifth miss behind 0.773 unidentified | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P3 | NOT VERIFIED | S1 |
| D-MISS-PRAC | Historical agent miss: practice_handoff_hitl (no approve_practice_handoff pause) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P3 | PARTIALLY REMEDIATED | S1 |
| D-SENT | Sentence-removal precision | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P3 | DEFERRED - POST SUBMISSION | S1 |
| D-SRC-LIST | Career-chat sources still list retrieved-but-uncited evidence | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-05 | P3 | DEFERRED - POST SUBMISSION | S1 |
| H-PG-SECRETS | managed_secrets PostgreSQL path migration-tested on SQLite only | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-02 | P3 | NOT VERIFIED | B1 |
| PRIV-DIFF | Report differencing across overlapping periods | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P3 | DEFERRED - POST SUBMISSION | S1 |
| PRIV-DSAR | No Admin export of candidate data (DSAR) | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P3 | DEFERRED - POST SUBMISSION | S1 |
| W10.10-AUDIT-CTX | Privacy workflow cross-store atomicity | REGISTER-HISTORICAL | VERIFY BEFORE R1.0 | WP-04 | P3 | PARTIALLY REMEDIATED | S1 |
| REQ-COV-01 | Define a separate frozen R1.0 beta-scope coverage measure | OWNER-REQUIREMENT | OWNER DECISION | WP-06 | P0 | AWAITING OWNER APPROVAL OF THE MEASURE | NEW |
| B-EMBED-SEL | Embedding provider and model selection | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P1 | PENDING OWNER DECISION | O0 |
| C-PROTO | Reviewer protocols and rating rubric for AI quality | REGISTER-HISTORICAL | OWNER DECISION | WP-16 | P1 | PENDING OWNER DECISION | O0 |
| C-THRESH | Owner thresholds for AI quality | REGISTER-HISTORICAL | OWNER DECISION | WP-16 | P1 | PENDING OWNER DECISION | O0 |
| D-21 | D-21 name who performs qualified legal review | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P1 | PENDING OWNER DECISION | O0 |
| IR-DEVDB-STALE | The developer database is 12 Alembic revisions behind the code head | REGISTER-HISTORICAL | OWNER DECISION | WP-07 | P1 | PENDING OWNER DECISION | O0 |
| IR-RAGAS-LIVE-APPROVAL | Live RAGAS evaluation awaits the owner's spending approval and three prerequisites | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P1 | PENDING OWNER DECISION | O0 |
| K-PROVIDER | Third-party model provider data handling for real candidate data | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P1 | PENDING OWNER DECISION | O0 |
| REQ-LANG-16 | Approve and qualify each proposed primary market individually | LANGUAGE-DECISION | OWNER DECISION | WP-08 | P1 | NOT STARTED | NEW |
| SJA-05 | Knowledge approval has no distinct-actor rule or step-up | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P1 | PENDING OWNER DECISION | O0 |
| H-REDIS-POLICY | Redis failure policy per bucket undecided | REGISTER-HISTORICAL | OWNER DECISION | WP-02 | P2 | PENDING OWNER DECISION | O0 |
| K-ATTR | Attribution wording decisions | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| K-LEGALACC | Legal acceptance of owner policy decisions | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| M-LEDGER | Mo and company-research cost-ledger gap | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P2 | PENDING OWNER DECISION | O0 |
| PRIV-POLICY01 | Verified-email policy (POLICY-01) | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| PRIV-RET | No retention periods for candidate content | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| W9.8-D7 | Original-file export bundle | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| XC-AC-AC-18 | Acceptance ledger (current) AC-18: Review surfaces: owned recent runs, safe specialist eve | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-AC-AC-23 | Acceptance ledger (current) AC-23: Voice measurement: defined sample, reference transcript | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-AC-AC-24 | Acceptance ledger (current) AC-24: Pilot and lessons: actual participant observations dist | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-AC-AC-25 | Acceptance ledger (current) AC-25: Submission consistency: README, three decks, selected t | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-P9-Deep-page-localization-debt | P9 quality register (carried items) Deep-page-localization-debt: Deep-page localization de | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (NBL) | NEW |
| XC-P9-Live-multi-agent-provider-qual | P9 quality register (carried items) Live-multi-agent-provider-qual: Live multi-agent/provi | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (OPT) | NEW |
| XC-P9-Live-transactional-email | P9 quality register (carried items) Live-transactional-email: Live transactional email | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (**BPL**) | NEW |
| XC-P9-Untracked-checkpoint-deletion | P9 quality register (carried items) Untracked-checkpoint-deletion-: Untracked checkpoint d | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (NBL) | NEW |
| XC-REL-R-33 | Release acceptance matrix (P10B) R-33: Email-verification behaviour pinned | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (ACCEPTED) | NEW |
| XC-REL-R-97 | Release acceptance matrix (P10B) R-97: Google OIDC live behaviour unvalidated | CROSS-CHECK | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (ACCEPTED) | NEW |
| D-16 | D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT) | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| PRIV-SUPPORT-NOTICE | Support data / privacy request response time | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D1b | Preparation-chat selective deletion | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D3 | Bulk memory deletion | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D4 | Per-version document deletion | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D5 | Auth-session list/revoke UI | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D6 | Feedback list and deletion page | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D8 | Orphan workspace invitations to a deleted user's email | REGISTER-HISTORICAL | OWNER DECISION | WP-09 | P3 | PENDING OWNER DECISION | O0 |

## R1.1: Indicative December 2026: paid beta and plan expansion (Stripe and subscription lifecycle after provider/legal qualification; pricing, tax, cancellation, refunds, reconciliation; new plan families)

132 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| F2B1-OD-01 | Legal seller entity | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-02 | Product classification (automated digital product) | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-03 | Product tax code | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-04 | What Premium includes beyond Basic | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-05 | Premium monthly price | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-ALLOW | Numerical Basic/Premium allowances not approved | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-ENT-POLICY | Paid entitlement policy unapproved | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-FAST | Basic-to-Fast transition not approved | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| B-COVEVAL | Decision whether to change coverage evaluator to check data origin/country (F-COV-1) | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| C-USD15 | USD 15 extra ceiling not approved; 15 calls remain | REGISTER-HISTORICAL | OWNER DECISION | WP-16 | P2 | PENDING OWNER DECISION | O0 |
| D-01 | D-01 adopt or amend recovered GKB/C1-C4 specification | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| D-02 | D-02 adopt ambiguity-state and recency/eligibility policy | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| F2B-D22 | D-22 ASHE weekly never annualised; unanswered | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-06 | Premium annual price (no annual plan exists) | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-07 | Currency | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-08 | Tax-inclusive presentation | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-09 | Supported customer countries | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-10 | B2B subscriptions | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-11 | Trial policy | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-12 | Failed-payment grace period | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-13 | Cancellation policy | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-14 | Refund policy | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-15 | Dispute entitlement policy | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-16 | Billing data retention | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| I-GRANDFATHER | Grandfathering of existing candidates | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| I-HISTORY-SHARE | Existing-share policy before history activation | REGISTER-HISTORICAL | OWNER DECISION | WP-09 | P2 | PENDING OWNER DECISION | O0 |
| I-RESET | Quota reset periods not approved | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| PRIV-BILL-RET | Billing data retention and erasure review | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| A-AGG | Five BLS-specific aggregates quarantined | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-05 | D-05 padded ISCO identity and plan for 21 legacy rows | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-06 | D-06 baseline manifest freeze (GKB-0) | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-10 | D-10 FX and PPP sources and methodology | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-11 | D-11 secondary-data qualification criteria | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-14 | D-14 regional-geography classification rule (policy p10c-d/1) | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-17 | D-17 evidence-state vocabulary adoption | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-18-19 | D-18 / D-19 South America region vocabularies and national classifications | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| IR-REHEARSAL-CALL | One unplanned live agent run during the P11 rehearsal (outside the P10E ledger) | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| J-OIDC-PWD | OIDC-only users cannot set a password via recovery | REGISTER-HISTORICAL | OWNER DECISION | WP-03 | P3 | PENDING OWNER DECISION | O0 |
| M-LEGACY01 | Legacy Streamlit UI retained (LEGACY-01) | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| M-POLICY02 | Evaluation score consistency (POLICY-02) | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| SJA-01 | AI config: second approver must be a second Platform Admin | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| SJA-02 | Knowledge Admin cannot retry/cancel failed jobs | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| SJA-03 | Billing/Security-Privacy admins cannot see queue state | REGISTER-HISTORICAL | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| F1-07 | Account deletion cannot cancel a live provider subscription | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P1 | PARTIALLY REMEDIATED | D-COM |
| I-GATES | 12 rollout and billing gates all False | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P1 | DEFERRED - POST SUBMISSION | D-COM |
| I-P1P3 | Unverified Stripe provider contracts (P-1..P-3) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P1 | NOT VERIFIED | D-COM |
| I-STRIPE-SANDBOX | Stripe sandbox qualification (F2-B2/F3) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P1 | NOT RUN | D-COM |
| I-UG | Ask4Mo UG incorporation and legal dependencies | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | D-COM |
| A-COV-SYN | Synthetic vs real source gaps in coverage | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | PARTIALLY REMEDIATED | D-GEN |
| A-OOH | BLS OOH / employment projections package unapproved | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| A-OPT-CAND | Other Package 3-7 items with unverified terms | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-GEN |
| B-COV-REMEAS | Source-backed coverage re-measurement after real qualification (metric C) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| B-RAGAS-CRED | RAGAS evaluator credential absent (RAGAS_EVAL_API_KEY) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT RUN | D-GEN |
| B-RAGAS-GUARD | Guarded RAGAS judge path on the P10E ledger | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT RUN | D-GEN |
| BL-10 | Reassess product coverage after qualification steps | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| C-AC22 | AC-22 live comparative benchmark | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-GEN |
| C-AGENT22 | Agent tool-selection recall 0.773 (22 cases): 5 misses not itemised | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-GEN |
| C-MODELCONTRACT | KB model-quality contract (mode C) remains unauthorised in full | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-GEN |
| C-NAT-P208 | Mo response naturalness (P2-08) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| C-PACK | Opportunity Pack and analytics narrative model quality | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | NOT RUN | D-GEN |
| C-PROFILE | Model-profile comparison (Fast vs Balanced vs Advanced) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-GEN |
| C-SMALL | Small-sample limits of all live AI results | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| CJ-D-01 | No candidate control to invite members or share a report or story | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-09 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| CJ-D-05 | 'Reviewed by you' provenance badge not rendered; no AI-suggested story path | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| CJ-D-06 | Opportunity fields other than status cannot be edited after creation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| CJ-D-07 | No provider-specific failure copy | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| CJ-D-08 | Dictation language is per device, not per account | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| F2B-ASHE-ED | ASHE Table 14 SOC classification edition unverified | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-GEN |
| F2B-ASHE-GUIDE | ASHE guide to tables and Table 14 notes unread | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-GEN |
| F2B-ASHE-REV | Revised ASHE 2025 dataset expected Oct/Nov 2026 | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-GEN |
| H-RESCACHE | Research-cache evaluator isolation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P2 | PARTIALLY REMEDIATED | D-GEN |
| I-LIFECYCLE | Stripe subscription lifecycle never exercised against a real provider | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P2 | NOT RUN | D-COM |
| I-MOCK | Billing is mock only | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P2 | DEFERRED - POST SUBMISSION | D-COM |
| I-REFUND-EXEC | Seller-initiated refund execution and billing alert delivery | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P2 | DEFERRED - POST SUBMISSION | D-COM |
| I-SCHED | Reconciliation scheduler and real StripeStateReader | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-11 | P2 | DEFERRED - POST SUBMISSION | D-COM |
| IR-RETRIEVAL-DEFERRED | Native-phrasing cross-language retrieval remains an offline-measured gap | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-08 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| L-LIVE-LANG | Live generated-language validation (R-50) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-08 | P2 | PARTIALLY REMEDIATED | D-GEN |
| L-PILOT-COV | Pilot 2 coverage gaps | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-14 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| L-STALE-1 | No staleness/publication-date handling in narrative lane | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-GEN |
| M-ISOLATION | Evaluators without test-isolation bootstrap | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P2 | PARTIALLY REMEDIATED | D-GEN |
| P2-09 | Opera voice recording failure needs reproduction | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-14 | P2 | NOT VERIFIED | D-GEN |
| A-09 | Jobs have no dead-letter state | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| A-CL | Chile INE CC BY-SA ShareAlike review | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-09 | P3 | PENDING HUMAN REVIEW | D-GEN |
| A-ILO | ILOSTAT site terms and per-indicator terms unread | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-GEN |
| A-ONET | O*NET crosswalks (Component 1c) deferred | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| A-OTHER19 | 19 'other' registered sources never researched | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-GEN |
| A-SA10 | Ten South American markets terms unverified | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-GEN |
| B-BM25 | BM25 pure-Python scoring about 22 ms p50 over 14k chunks | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| B-CIPARITY | CI parity of clean-checkout coverage baseline on GitHub | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-COM |
| B-FRESH | Freshness / supersession policy for sources | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| B-NOSNAP | Governed knowledge has no snapshot/rollback model; depends on a worker | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| B-RC-TRANSIENT | Unexplained transient eval_product_coverage failure and macOS exit-134 aborts | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-GEN |
| B-TOKENISER | Offline hash embedder ASCII tokeniser | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| BL-17 | P10C-F2F wider South America and ILOSTAT | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| C-AGENT-REPEAT | Agent behaviour consistency across repeats | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT RUN | D-GEN |
| C-COST | Provider cost reconciliation gaps | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P3 | PARTIALLY REMEDIATED | D-GEN |
| C-LANGFUSE | Live Langfuse not validated | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT VERIFIED | D-GEN |
| C-OCR | Live OCR quality sample | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT RUN | D-GEN |
| D-09 | D-09 five-category relationship qualification for crosswalks | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| D-20 | D-20 no official SOC/NOC to ISCO-08 crosswalk | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| F-11 | Refund amount in minor units | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-COM |
| F2B-ASHE-SUPP | ASHE December 2025 correction: exact suppressed cells unverified | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | PARTIALLY REMEDIATED | D-GEN |
| G-WS-DEACT | Admin workspace deactivation and universal operator search not built | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-09 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| H-BROWSER | Full browser matrix | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| H-CI-PERF | CI test-setup cost | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| H-DEVDB | Developer DB migration lag / W10.13 dev-DB incident | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P3 | PARTIALLY REMEDIATED | D-GEN |
| H-FK | SQLite PRAGMA foreign_keys not enabled | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| J-BREVO-CACHE | Cached Brevo/provider clients need restart on rotation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-03 | P3 | PARTIALLY REMEDIATED | D-GEN |
| J-INVITE-MAIL | Workspace invitation mail not instrumented | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-09 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| J-LANGFUSE | Langfuse live validation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-13 | P3 | NOT RUN | D-GEN |
| J-OIDC-STEPUP | OIDC-only admin cannot step up | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-03 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| J-RAGAS | RAGAS live NOT RUN | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-13 | P3 | NOT RUN | D-GEN |
| L-CODE-1 | Occupation codes in questions do not resolve | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| L-INGEST-SIZE | No per-file size limit in legacy ingestion loaders | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| L-META-1 | Sidecar .meta.json can override provenance metadata | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-GEN |
| M-DOC-C1 | CLAUDE.md says realtime voice (C1) DEFERRED | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-DOC-CLAIMS | PRODUCT_CLAIMS stale entries (D-04) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-DOC-COUNT | Admin destination count inconsistency | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-GEN |
| M-DOC-LIMITS | docs/limitations.md describes Streamlit-era state | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-DOC-OIDC | W12.4C internal contradiction on PKCE/nonce | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-DOC-OPT | Sprint-4 quality_optimisation_audit TODO table | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-GEN |
| M-DOC-PLAN | Phase plan stale W12.4 'NOT STARTED' headings | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | PENDING HUMAN REVIEW | D-GEN |
| M-RECON-1 | Provider-cost reconciliation discrepancy (P10E) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-RECON-2 | Provider-cost reconciliation discrepancy (P10E-R1 section 11) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-RECON-3 | Provider-cost reconciliation (P10E-R2 section 7) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-GEN |
| M-RESCACHE-INC | Research-cache contamination incidents (W10.11, RC-QUAL-ENV-01, W12.4C) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-GEN |
| P2-06 | Re-evaluate marketing/pricing positioning with participants | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-14 | P3 | PENDING HUMAN REVIEW | D-GEN |
| PA-A-08 | Normal platform settings beyond pause and two flags are environment-only | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-02 | P3 | PARTIALLY REMEDIATED | D-GEN |
| REL-R1.1 | R1.1 release scope: Paid beta and plan expansion | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-11 | P3 | PLANNED (indicative window) | NEW |
| SJA-06 | Held permissions with no consuming route | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-GEN |
| TD-W9-03 | Locale-aware font/subset loading | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-08 | P3 | DEFERRED - POST SUBMISSION | D-GEN |

## R1.2: Indicative December 2026 to January 2027: advanced Admin and automation (scheduled reporting, advanced analytics, automation, bulk administration, expanded alerts)

19 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| SJA-04 | Operations Admin partly useful Review/Diagnostics | REGISTER-HISTORICAL | OWNER DECISION | WP-10 | P3 | PENDING OWNER DECISION | O0 |
| F-07 | Raw timestamps, snake_case headers, long ids | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P2 | PARTIALLY REMEDIATED | D-ADM |
| F-08 | Overview hierarchy | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P2 | DEFERRED - POST SUBMISSION | D-ADM |
| F-12 | High-risk action styling | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P2 | DEFERRED - POST SUBMISSION | D-ADM |
| G-CONTRAST | Automated contrast audit not done | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P2 | NOT RUN | D-ADM |
| G-HDR-390 | Candidate header logo/'More' overlap at 390 px | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P2 | DEFERRED - POST SUBMISSION | D-ADM |
| G-SR | Real screen-reader / assistive-technology testing not done | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P2 | NOT RUN | D-ADM |
| F-02 | Developer-facing Review copy | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-ADM |
| F-06 | Fragmented Audit surfaces | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-ADM |
| F-09 | Repeated suppressed metrics | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-ADM |
| F-15 | Raw environment names in Flags page | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-ADM |
| F-16 | Small inline link targets | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-ADM |
| F-17 | Providers vs Integrations overlap | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-ADM |
| G-A6-A8 | Owned-run list (A6) and selected-run RAG (A8) review surfaces | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | NOT VERIFIED | D-ADM |
| G-CAP-PARTIAL | Admin capability matrix PARTIAL rows | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-ADM |
| G-CHURN | Churn rate unavailable in Reports | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-ADM |
| G-REVIEW-COPY | Residual technical Review/Diagnostics wording | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-ADM |
| REL-R1.2 | R1.2 release scope: Advanced Admin and automation | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-10 | P3 | PLANNED (indicative window) | NEW |
| SJA-07 | Support replies in-app only; no attachments or SLA | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-ADM |

## R1.3: Indicative January to February 2027: Mandarin, Hindi, Arabic (new locale, prompt, safety, retrieval, accessibility, legal and native review; Arabic RTL)

3 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| REQ-LANG-15 | R1.3 languages: Mandarin, Hindi, Arabic | LANGUAGE-DECISION | DEFER TO NAMED RELEASE | WP-08 | P2 | NOT STARTED | NEW |
| L-LANG-AR | Arabic not a supported language | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-FL |
| REL-R1.3 | R1.3 release scope: New languages: Mandarin, Hindi, Arabic | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-08 | P3 | PLANNED (indicative window) | NEW |

## R1.4: Indicative February 2027: voice interview experience (qualified STT, TTS and live voice practice; licensing and consent; latency; native speech quality)

23 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| EX-04 | Human voice-quality review NOT RUN (7-locale speech) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | NOT RUN | D-SPEECH |
| W12.4E-1 | Whisper self-hosted versus hosted decision | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-13 | Human speech-quality validation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-14 | Provider authorization flag activation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-15 | Production speech operational qualification | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-2 | Hosted Whisper data-processing review | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-3 | Speech hosting architecture | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-6 | Genuine Whisper execution validation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-7 | Genuine Kyutai execution validation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| AC-23-B | Realtime provider round-trip latency NOT RUN | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | NOT RUN | D-SPEECH |
| E-LIVE-MULTI | Live multilingual Mo/voice quality unvalidated | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | NOT RUN | D-SPEECH |
| E-LOCAL-ENGINES | Local engine bindings limited | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| EX-02 | Realtime voice (C1) live round-trip NOT RUN | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | NOT RUN | D-SPEECH |
| W12.4E-10 | Per-voice licence verification | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-17 | Response-origin authorization hardening | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-18 | Engine timeout and cancellation hardening | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-4 | Model weights and resource placement | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-5 | CPU/GPU and memory sizing | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-8 | Kyutai gated model-weight approval | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-9 | Kyutai licence and attribution verification | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| E-RATE | Realtime/speech concurrency bounded per process | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P3 | DEFERRED - POST SUBMISSION | D-SPEECH |
| REL-R1.4 | R1.4 release scope: Voice interview experience | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-12 | P3 | PLANNED (indicative window) | NEW |
| W12.4E-11 | Dutch server-side TTS qualification | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-12 | P3 | DEFERRED - POST SUBMISSION | D-SPEECH |

## R1.5: Indicative February to March 2027: global career intelligence (additional countries, qualified occupational sources, provenance, multilingual geographic retrieval)

7 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| BL-13 | P10C-F2B United Kingdom (Package 2) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-INTL |
| F2B-UK-ALIAS | No UK alias evidence assessed | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-INTL |
| C-K4 | K4 live Adzuna validation | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT RUN | D-INT |
| F2B-UK-V1 | UK V1 reconciliation: 527 ASHE rows, one with no occupation code | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-INTL |
| F2B-UKSOC-VER | Current UK SOC 2020 file version unverified | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-INTL |
| J-ADZUNA | Adzuna live verification (K4) | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-13 | P3 | NOT RUN | D-INT |
| REL-R1.5 | R1.5 release scope: Global career intelligence | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-06 | P3 | PLANNED (indicative window) | NEW |

## R1.6: Indicative March 2027: Compensation Intelligence V2 (qualified salary datasets, geographic comparison, freshness, methodology, legal and human approval)

2 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| BL-16 | P10C-F2E Canada, Mexico, Brazil | REGISTER-HISTORICAL | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-INTL |
| REL-R1.6 | R1.6 release scope: Compensation Intelligence V2 | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-06 | P3 | PLANNED (indicative window) | NEW |

## R1.7: After R1.6, date not committed: teams and enterprise (enterprise Workspaces, organization subscriptions, SSO and governance, qualified external integrations)

1 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| REL-R1.7 | R1.7 release scope: Teams and enterprise | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-13 | P3 | PLANNED (indicative window) | NEW |

## R2.0: Evidence-led, subsequent: expanded intelligent career platform (personalized guidance, agentic workflows, deeper career development)

1 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| REL-R2.0 | R2.0 release scope: Expanded intelligent career platform | OWNER-REQUIREMENT | DEFER TO NAMED RELEASE | WP-07 | P3 | PLANNED (indicative window) | NEW |

## UNSCHEDULED: unscheduled owner decisions (academic-only retirement, future Russian decision)

15 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| IR-AC-LEDGER | Acceptance criteria dispositions are P9-era and spread over three documents | REGISTER-HISTORICAL | OWNER DECISION | WP-07 | P0 | OPEN - PRE-SUBMISSION QUALIFICATION | A0 |
| IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20) | REGISTER-HISTORICAL | OWNER DECISION | WP-07 | P0 | PENDING OWNER DECISION | O0 |
| IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | REGISTER-HISTORICAL | OWNER DECISION | WP-02 | P0 | PENDING OWNER DECISION | O0 |
| IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | REGISTER-HISTORICAL | OWNER DECISION | WP-07 | P0 | PENDING OWNER DECISION | O0 |
| IR-TURING-RUBRIC | The Turing College capstone brief and rubric are not in the repository | REGISTER-HISTORICAL | OWNER DECISION | WP-04 | P0 | PARTIALLY REMEDIATED | A0 |
| I-STRIPE-ACCT | Dedicated Stripe account and Managed Payments eligibility | REGISTER-HISTORICAL | OWNER DECISION | WP-11 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | U-RU |
| L-NATIVE-UI | Human/native translation review of interface and Help (7-8 locales) | REGISTER-HISTORICAL | OWNER DECISION | WP-08 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | U-RU |
| PRIV-LANG | Privacy/legal translations unreviewed (8 locales incl. Russian) | REGISTER-HISTORICAL | OWNER DECISION | WP-08 | P1 | PENDING HUMAN REVIEW | U-RU |
| A-NATIVE-KB | Governed KB native content is English (+ some German) | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P2 | DEFERRED - POST SUBMISSION | U-RU |
| L-VOICE | Voice not human-validated (PF-19 / AC-23 live) | REGISTER-HISTORICAL | OWNER DECISION | WP-14 | P2 | PENDING HUMAN REVIEW | U-RU |
| D-07 | D-07 ESCO language releases | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| E-RU | Russian speech excluded | REGISTER-HISTORICAL | OWNER DECISION | WP-12 | P3 | DEFERRED - POST SUBMISSION | U-RU |
| G-WALK-ENV | Admin walkthrough used dev server and seeded data | REGISTER-HISTORICAL | OWNER DECISION | WP-10 | P3 | DEFERRED - POST SUBMISSION | A0 |
| L-LANG-RU | Russian is interface/Mo-conversation only, not a KB language | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | DEFERRED - POST SUBMISSION | U-RU |
| L-RU-INFLECT | Inflected Russian country names not recognised | REGISTER-HISTORICAL | OWNER DECISION | WP-06 | P3 | DEFERRED - POST SUBMISSION | U-RU |

## n/a: closed items (evidence preserved)

52 items.

| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |
|---|---|---|---|---|---|---|---|
| IR-P12 | A P12 (final rehearsal and freeze) exists in the reference runbook but not in the phase pl | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-07 | P1 | CLOSED - VERIFIED | C0 |
| CJ-D-04 | PRODUCT_CLAIMS.md contains stale entries | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-07 | P2 | CLOSED - VERIFIED | C0 |
| IR-ROADMAP-STALE | Roadmap and phase plan described merged PRs as pending | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-07 | P2 | CLOSED - VERIFIED | C0 |
| PA-A-01 | Knowledge Base accessibility (owner-reported) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-02 | P2 | CLOSED - VERIFIED | C0 |
| PA-A-02 | No writable credential store | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-02 | P2 | CLOSED - VERIFIED | C0 |
| PA-A-05 | Knowledge readiness, inventory and retrieval test missing | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-02 | P2 | CLOSED - VERIFIED | C0 |
| A-10 | Capability matrix lacked email row | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| B-CAP4096 | 2,000 output cap blocked 5 of 22 agent cases | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| B-HELPER | Agent helper pinned to code-default model slug (gpt-5.6-terra) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| B-XLANG-HARNESS | Non-English retrieval gap and mixed de/fr scaffold reported as product findings | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A1 | OEWS data dictionary / field semantics (precondition J,K) unverified | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A2 | Isolated ingestion environment (precondition M) unverified | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A3 | Reliability threshold for PRSE-based qualification | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A4 | Package 1 files unacquired; registry transition for isolated DB | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A5 | Research-cache evaluator isolation UNRESOLVED (roadmap) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A6 | CI-reproducible knowledge evaluation fixture DESIGNED not implemented (roadmap) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-AGENT-EVID | Harness: agent completion inflated; no per-case evidence (defects E,F) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-16 | P3 | CLOSED - VERIFIED | C0 |
| C-INT-HARNESS | Interview quality harness and personas did not exist (P10E) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-16 | P3 | CLOSED - VERIFIED | C0 |
| D-ABST-CIT | Citations on abstentions presentation decision | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C1 | Cross-geography figure authorised by foreign evidence | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C2 | Citation marker exempted estimate-offer guard | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C3 | External statistic without retrieval only labelled | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C4 | Citation/sources metadata inconsistent after marker removal | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| F-01 | Review/Diagnostics outside Admin shell | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-03 | Admin navigation at 390 px too tall | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-04 | Integrations mobile overflow/clipping | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-05 | Billing forms off screen, focus not moved | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-10 | Plans and Billing relationship unexplained | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-13 | No secret-rotation control | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-14 | Development anonymous account in Users list | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| G-A5 | Knowledge-readiness distinction (A5) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| H-PAUSE | Process-local pause switch (p8 section 15; SEC-W10-05) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-02 | P3 | CLOSED - VERIFIED | C0 |
| H-SESSION-STORE | In-memory session store blocks multi-replica (p8 section 15) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-02 | P3 | CLOSED - VERIFIED | C0 |
| I-RECOVER-PERM | Billing recovery permission decision | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-11 | P3 | CLOSED - VERIFIED | C0 |
| K-PRIV-W9 | PRIV-W9-02 consent/legal acceptance history not stored | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-04 | P3 | CLOSED - VERIFIED | C0 |
| L-ANSWER-GUARD | Career Chat lacked occupation-grounding guard | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| M-BASELINE-EVALS | Four baseline evaluators failing on main (P4-A) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-EVAL-WRITES | Evaluators rewrote committed artifacts | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-F109 | Reporting test clock pinned to 2026-10-15 (F1-09) | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-LATENT-RES | Evaluation corrections preserve historical evidence | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-TODO-CODE | TODO/FIXME in source code | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| PRIV-EXPORT-D03 | Export carries stale legal-acceptance wording | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-04 | P3 | CLOSED - VERIFIED | C0 |
| PRIV-W9-01/02 | PRIV-W9-01 and PRIV-W9-02 closure cross-reference | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| ROLE-W10-01 | platform_admin completeness / role scope | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-01 | Account deactivation did not revoke sessions | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-02 | Privileged audit not fail-closed/atomic | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-03 | Non-canonical audit events/no request id/no denial audit | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-04 | Privacy request queue non-operational | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-05 | Process-local pause | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-06 | /admin/providers echoed raw provider values | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| TD-W9-01 | Invalid Tailwind colour-token opacity classes | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| TD-W9-02 | Backend test-isolation leak and 13 .env failures | REGISTER-HISTORICAL | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |

## Recovered owner requirements and reviewer findings (detail)

These rows are specified from `OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md`. Each is a separate, testable requirement; the numbered criteria are the acceptance criteria.

### REVIEW-01 Prompt-injection defence depth (Turing College review finding)

Provenance: REVIEWER_FINDING; WP WP-05; priority P0; release R1.0; status: PARTIAL - heuristic detector and tool allow-list exist; none of R1 to R6 is complete.

- R1 corpus derived from evaluations/jailbreak_test_results.csv covering direct, indirect, multilingual, encoded and retrieved-document attacks, with a frozen held-out split
- R2 attack detection rate and benign false-positive rate are measured and reported per language; CI fails below the owner-approved thresholds (OD-GATE-THRESHOLDS)
- R3 every RetrievalResult carries an injection-risk score; chunks above the threshold are quarantined or excluded before the model context is built
- R4 a model-requested tool call is re-authorised server-side (goal, user authorization, tool permission, allowed arguments) before execution
- R5 malicious source content cannot trigger an unauthorised tool call or cross-user disclosure (negative tests)
- R6 output-side safeguards in answer() retained and tested; no sole dependence on prompt instructions

Required tests: held-out injection corpus run in CI; tool-authorization negative tests; cross-user retrieval tests; output-guard tests; per-language injection suite.
Dependencies: owner-approved thresholds where noted (OD-GATE-THRESHOLDS); PG-03; thresholds need OD-GATE-THRESHOLDS.

### REVIEW-02 Externalized, versioned prompts (Turing College review finding)

Provenance: REVIEWER_FINDING; WP WP-17; priority P1; release R1.0; status: NOT STARTED - prompts are code literals; a prompt registry and config versioning exist.

- R1 agent system, interview technique and RAG prompts load from versioned assets through a validated loader (variables checked, missing version is a clear error)
- R2 each prompt has a declared semantic version independent of its SHA; the SHA is verified at load
- R3 production_versions() reports declared version plus hash
- R4 AgentRunResult and evaluation results record the effective prompt versions
- R5 Prompt Lab runs are attributable to exact prompt, model and configuration
- R6 rollback to an existing approved version needs no code change and is audited
- R7 template variables, compatibility, missing versions and rollback are tested

Required tests: prompt loader unit tests; compatibility/rollback tests; production_versions parity test; Prompt Lab attribution test.
Dependencies: owner-approved thresholds where noted (OD-GATE-THRESHOLDS); PG-12.

### REVIEW-03 Tool catalogue parity (Turing College review finding)

Provenance: REVIEWER_FINDING; WP WP-17; priority P1; release R1.0; status: NOT STARTED - registry exists; descriptions are duplicated in policies.

- R1 model-visible tool descriptions are generated from registered metadata
- R2 argument contracts derive from the Pydantic models
- R3 a parity test fails if tool names, signatures or descriptions drift between registry, bindings and policy
- R4 duplicate or invalid registrations are rejected at registration
- R5 manually duplicated descriptions are removed after regression tests pass
- R6 the set of available tools is unchanged by this work (asserted)

Required tests: registry parity test; duplicate-registration test; binding/authorization parity test; unchanged-tool-set assertion.
Dependencies: owner-approved thresholds where noted (OD-GATE-THRESHOLDS); PG-12 (registry parity).

### REVIEW-04 Silent embedding degradation (Turing College review finding)

Provenance: REVIEWER_FINDING; WP WP-06; priority P0; release R1.0; status: PARTIAL - local hash embedder is the working default; readiness does not yet expose degradation.

- R1 readiness shows the actual embedding provider, model and degradation state
- R2 in production the hash embedder is refused and a missing semantic credential fails closed (no silent fallback)
- R3 offline development mode remains and is clearly labelled
- R4 every index manifest records provider, model, version, dimensions and compatibility metadata
- R5 an index/query embedding mismatch is detected and the query is refused
- R6 qualified indexes can be rebuilt from approved material
- R7 BM25, vector and RRF are evaluated separately and combined, including multilingual retrieval and cross-language attribution

Required tests: readiness tests; production-mode fail-closed tests; manifest and mismatch tests; retrieval-mode evaluation; multilingual retrieval evaluation.
Dependencies: owner-approved thresholds where noted (OD-GATE-THRESHOLDS); PG-05; paid embedding calls need OD-BUDGET.

### REVIEW-05 Agent streaming and feedback (Turing College review finding)

Provenance: REVIEWER_FINDING; WP WP-17; priority P1; release R1.0; status: NOT STARTED - synchronous run API only.

- R1 an authenticated SSE endpoint exists beside POST /api/v1/agent/run
- R2 events are safe allow-listed projections; a negative test proves no chain-of-thought, system prompt, private tool argument or secret is emitted
- R3 the Candidate sees useful progress states
- R4 cancellation and timeouts work and leave a consistent durable run
- R5 reconnection cannot expose another user's events (cross-user test)
- R6 usage and cost are reconciled for a cancelled run
- R7 the synchronous API remains and is tested as a fallback

Required tests: SSE contract tests; event-allow-list negative test; cancellation and timeout tests; cross-user reconnect test; cancelled-run usage test; sync fallback test; browser test of progress states.
Dependencies: owner-approved thresholds where noted (OD-GATE-THRESHOLDS); PG-06.

### REQ-OWN-01 Admin Platform 2.0: Command Center and AI operations

Provenance: OWNER_CAPABILITY; WP WP-10; priority P1; release R1.0; status: PARTIAL - Command Center, AI administration, provider readiness and aggregate reporting foundations exist (W10.x, W12.x); the listed dashboards and AI operations view are not complete.

- C1 dashboards: active users and registration trends; candidate activation; interview start and completion rates; AI failure rate and latency; model usage and cost; retrieval and source health; worker and indexing failures; support ticket trends; security and incident indicators; deployment and provider readiness
- C2 every chart shows period, numerator, denominator, coverage and a missing-data state; no invented figures and no misleading zeros; chart type chosen by meaning
- C3 AI operations view: registered models, effective configuration, approved prompt versions, model readiness and cost, safe feature flags, provider readiness, agent execution status, evaluation results, incidents, audit
- C4 high-impact configuration changes are validated, permissioned and audited; no route edits system instructions or tool permissions
- C5 owner-operated Platform Admin still has no path to private CVs, stories, interviews or conversations

Required tests: metric-source tests (each tile traced to a query and denominator); missing-data rendering tests; permission matrix and route invariant; Playwright dashboard specs; sentinel privacy tests.
Dependencies: REVIEW-02 (prompt versions) for C3; ADMIN-01 navigation.

### REQ-OWN-02 Admin Plans: Basic/Premium management

Provenance: OWNER_CAPABILITY; WP WP-10; priority P1; release R1.0; status: PARTIAL - versioned plans, assignment and an entitlement service exist (W10.4); feature selection, comparison, preview and limits editing are not complete.

- P1 edit draft plan versions; choose from implemented registered features only
- P2 enable or disable features per plan; configure usage limits and allowances
- P3 clone or version plans; compare plan configurations; preview the effect on candidate access
- P4 assign plans to users; apply authorized Workspace entitlements
- P5 activate and retire versions; existing subscriber rights preserved until an explicit migration decision
- P6 immutable audit trail; safe rollback
- P7 entitlements enforced in backend services, never by the frontend
- P8 no billing, checkout or payment path is enabled by any of the above

Required tests: plan lifecycle tests; entitlement enforcement at the API boundary; preview-versus-actual parity test; audit immutability tests; rollback test; billing gates stay False.
Dependencies: OD-PLAN-ENFORCE (which entitlements are enforced during the free beta).

### REQ-OWN-03 Admin Users: complete operational user management

Provenance: OWNER_CAPABILITY; WP WP-10; priority P1; release R1.0; status: PARTIAL - user list, lifecycle, role-change approval and session revocation exist (W10.2, W10.13); search/sort, membership inspection, bulk actions and communications are not complete.

- U1 search, filter, sort and paginate users; safe account metadata
- U2 activate, suspend, close and delete accounts through the existing deletion engine
- U3 role changes only through the two-person approval flow
- U4 revoke active sessions; resend permitted account communications
- U5 assign Basic or Premium; inspect Workspace memberships; permitted membership actions
- U6 support status and audit history per user
- U7 restricted bulk actions (the permitted set needs OD-BULK-ACTIONS)
- U8 owner self-lockout and privilege escalation are prevented server-side
- U9 no view of CVs, stories, interviews or conversations

Required tests: user list/search/pagination tests; lifecycle and session-revocation tests; role-change approval tests; self-lockout tests; bulk-action guard tests; privacy sentinel tests; Playwright user admin specs.
Dependencies: OD-BULK-ACTIONS.

### REQ-OWN-04 Admin Reports: prebuilt reports and governed custom report builder

Provenance: OWNER_CAPABILITY; WP WP-10; priority P1; release R1.0; status: PARTIAL - aggregate reporting with suppression exists (W10.12); the listed reports, builder, saved configurations and exports are not complete.

- B1 prebuilt reports: acquisition and onboarding; candidate engagement; interview practice and completion; AI feedback quality; Story Bank adoption and reuse; Workspace invitations and sharing; model performance and economics; agent/tool execution outcomes; knowledge and RAG quality; support operations; security and privacy; commercial performance only once real billing is qualified (R1.1)
- B2 custom report builder over approved metrics and approved dimensions with date-range filters, comparisons, appropriate chart types and saved configurations
- B3 export in supported formats (the set needs OD-REPORT-EXPORT)
- B4 no arbitrary SQL; no private candidate-data access
- B5 permission checks and small-cohort suppression enforced; missing data is shown as missing, never as zero

Required tests: metric definition tests; small-cohort suppression tests; no-arbitrary-SQL test (builder accepts only registered metric and dimension ids); permission tests; export tests; chart-type rule tests; Playwright report specs.
Dependencies: ADMIN-04 metric sources; OD-REPORT-EXPORT.

### REQ-OWN-05 Knowledge Sources: permanent persistence and reliability

Provenance: OWNER_CAPABILITY; WP WP-06; priority P0; release R1.0; status: PARTIAL - governed lifecycle, worker, readiness and curated-corpus listing exist; durability, restore, environment identity, alerts and a real scanner are not complete.

- K1 persistent SQL source registry and durable private storage for uploaded files; persistent curated and governed indexes
- K2 separate, clearly labelled curated and governed views
- K3 safe Admin diagnostics show the environment, database and index identity; API and workers use compatible authoritative configuration
- K4 index manifests persist embedding model identity and checksums (links to REVIEW-04)
- K5 lifecycle: register, scan, parse, review, approve, index, activate, replace, retire, reindex; licensing and source-qualification safeguards preserved
- K6 genuine fail-closed malware scanning for real user uploads (the fake scanner never runs outside development)
- K7 monitoring and alerts for lost collections, missing sources, incompatible embeddings and failed jobs; authorized backup, restore, retry, rebuild and rollback
- K8 restart, redeployment and separate-environment restore tests pass; retrieval, citation provenance and candidate access verified after each
- K9 a production UI can never silently connect to an empty local demonstration database; no invented source counts; demonstration fixtures are never labelled production-approved evidence

Required tests: restart persistence test; redeployment persistence test; restore-in-new-environment drill; manifest/embedder mismatch test; malware-scan fail-closed test; alert tests; retrieval and citation provenance tests; environment-identity diagnostics test.
Dependencies: OD-MALWARE (scanner choice); OD-HOSTED; REVIEW-04.

### REQ-OWN-06 Story Bank: complete functional Story Bank

Provenance: OWNER_CAPABILITY; WP WP-09; priority P1; release R1.0; status: PARTIAL - source-backed, revocation-aware story bank exists (P4); manual STAR editing UX, suggestion path, provenance badge, Opportunity link and Practice reuse are incomplete (CJ-D-05).

- S1 create stories manually; draft from approved Candidate evidence; full STAR editing
- S2 evidence provenance preserved; user-created, source-backed, user-corrected and model-suggested content visibly distinguished
- S3 search, filter and competency tags; connect stories to Opportunities
- S4 suggest relevant stories for interviews; Candidate approval before use; reuse during Practice; story evidence reflected in feedback
- S5 never invent achievements or numbers
- S6 persists across sessions; deletion and privacy controls; strict Candidate ownership
- S7 acceptance journey passes in the browser: create, edit, link to Opportunity, reuse in Practice, receive feedback, retrieve after restart

Required tests: story CRUD and ownership tests; provenance-label tests; suggestion/approval tests; no-fabrication tests; Playwright acceptance journey including restart; per-language run (LG-09).
Dependencies: WP-08 for per-language qualification.

### REQ-OWN-07 Workspaces: complete functional Workspaces

Provenance: OWNER_CAPABILITY; WP WP-09; priority P1; release R1.0; status: PARTIAL - Workspaces, invitations, VIEW-only shares and revocation exist in the backend (P6.5); candidate controls to invite and share are missing (CJ-D-01).

- W1 create and manage Workspaces; invite members by email; accept and decline; pending invitations; cancel or revoke invitations
- W2 display membership and roles; remove members where authorized; safe ownership transfer
- W3 share supported resources explicitly, default VIEW-only; display what is shared and with whom; immediate revocation
- W4 no access to unshared private content; activity and audit data recorded
- W5 authorization tested at the API boundary, not only the frontend
- W6 acceptance journey: A creates and invites B; B accepts; A shares one resource; B sees only that; A revokes; B loses access immediately
- W7 qualified in all seven Candidate languages (LG-09)

Required tests: invitation lifecycle tests; API-boundary authorization tests for every shared resource type; revocation-immediacy test; ownership transfer tests; two-user Playwright journey; per-language run.
Dependencies: OD-WS-TRANSFER (ownership transfer rules).

### REQ-OWN-08 Admin navigation redesign and Review and Diagnostics relocation

Provenance: OWNER_CAPABILITY; WP WP-10; priority P1; release R1.0; status: PARTIAL - flat Admin navigation exists; Review and Diagnostics currently sit outside the Admin shell (G-category issues).

- N1 grouped, collapsible sidebar (proposed groups: Command Center; Customers and Workspaces; Products and Commercial; AI and Knowledge; Insights and Operations; Governance and Settings; owner to confirm via OD-ADMIN-NAV)
- N2 expand and collapse, active highlighting, breadcrumbs, responsive layout, keyboard accessibility, permission-aware items, quick navigation where useful; route compatibility preserved when safe
- N3 platform-wide Review and Diagnostics reachable only through /admin; entry removed from global Candidate navigation; old routes redirect
- N4 a Candidate keeps access to their own authorized run details through a separate owner-scoped experience
- N5 backend permissions remain mandatory: a Candidate or unpermitted Admin gets 403 on diagnostic APIs regardless of the UI

Required tests: navigation Playwright specs (expand/collapse, keyboard, breadcrumbs, responsive); permission-aware rendering tests; redirect tests; backend 403 tests for diagnostic routes; accessibility checks.
Dependencies: OD-ADMIN-NAV.

## Cross-check against the other matrices

168 rows from: Acceptance ledger (current) (25), Release acceptance matrix (P10B) (99), Capstone risk register (22), P9 quality register (carried items) (22).

| Source | ID | Historical state | Handling | Mapped issue(s) |
|---|---|---|---|---|
| Acceptance ledger (current) | AC-03 | UNKNOWN | TRACKED by register issue(s) | IR-AC03-TESTS |
| Acceptance ledger (current) | AC-13 | UNKNOWN | TRACKED by register issue(s) | W12.4E-1, W12.4E-10, W12.4E-11, W12.4E-12 |
| Acceptance ledger (current) | AC-18 | UNKNOWN | NEW ISSUE XC-AC-AC-18 (no register issue found) | XC-AC-AC-18 |
| Acceptance ledger (current) | AC-19 | UNKNOWN | TRACKED by register issue(s) | G-CONTRAST, G-HDR-390, G-SR, P2-09 |
| Acceptance ledger (current) | AC-22 | UNKNOWN | TRACKED by register issue(s) | B-SEMCAL |
| Acceptance ledger (current) | AC-23 | UNKNOWN | NEW ISSUE XC-AC-AC-23 (no register issue found) | XC-AC-AC-23 |
| Acceptance ledger (current) | AC-24 | UNKNOWN | NEW ISSUE XC-AC-AC-24 (no register issue found) | XC-AC-AC-24 |
| Acceptance ledger (current) | AC-25 | UNKNOWN | NEW ISSUE XC-AC-AC-25 (no register issue found) | XC-AC-AC-25 |
| Release acceptance matrix (P10B) | R-33 | ACCEPTED | NEW ISSUE XC-REL-R-33 (no register issue found) | XC-REL-R-33 |
| Release acceptance matrix (P10B) | R-38 | ACCEPTED | TRACKED by register issue(s) | M-LEGACY01 |
| Release acceptance matrix (P10B) | R-46 | ACCEPTED | TRACKED by register issue(s) | H-REDIS-LIVE, EX-12.15 |
| Release acceptance matrix (P10B) | R-49 | ACCEPTED | TRACKED by register issue(s) | W9.8-D10, W9.8-D1a, W9.8-D1b, W9.8-D2 |
| Release acceptance matrix (P10B) | R-50 | ACCEPTED | TRACKED by register issue(s) | W9.8-D10, W9.8-D1a, W9.8-D1b, W9.8-D2 |
| Release acceptance matrix (P10B) | R-51 | ACCEPTED | TRACKED by register issue(s) | W9.8-D10, W9.8-D1a, W9.8-D1b, W9.8-D2 |
| Release acceptance matrix (P10B) | R-93 | ACCEPTED | TRACKED by register issue(s) | W10.10-AUDIT-CTX |
| Release acceptance matrix (P10B) | R-94 | ACCEPTED | TRACKED by register issue(s) | G-WS-DEACT |
| Release acceptance matrix (P10B) | R-95 | ACCEPTED | TRACKED by register issue(s) | W10.10-AUDIT-CTX |
| Release acceptance matrix (P10B) | R-96 | ACCEPTED | TRACKED by register issue(s) | H-PG-SECRETS, H-FAILPATH |
| Release acceptance matrix (P10B) | R-97 | ACCEPTED | NEW ISSUE XC-REL-R-97 (no register issue found) | XC-REL-R-97 |
| Capstone risk register | R-1 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-2 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-3 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-4 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-5 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-6 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-7 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-8 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-9 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-10 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-11 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-12 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-13 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-14 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-15 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-16 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue | W10.10-AUDIT-CTX |
| Capstone risk register | R-17 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-18 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-19 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-20 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue |  |
| Capstone risk register | R-21 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue | W10.10-AUDIT-CTX |
| Capstone risk register | R-22 | planning risk (no status column) | RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue | TD-W9-01, W9.8-D10, W9.8-D1a, W9.8-D1b |
| P9 quality register (carried items) | EX-12-hosted-deployment | **BPL** | TRACKED by register issue(s) | EX-12.1, EX-12.10, EX-12.11, EX-12.12 |
| P9 quality register (carried items) | EX-02-live-realtime-round-trip | OPT / BPL | TRACKED by register issue(s) | EX-02 |
| P9 quality register (carried items) | Live-Google-OIDC | OPT / BPL | TRACKED by register issue(s) | J-OIDC |
| P9 quality register (carried items) | Live-transactional-email | **BPL** | NEW ISSUE XC-P9-Live-transactional-email (no register issue found) | XC-P9-Live-transactional-email |
| P9 quality register (carried items) | K1-K2-human-data-review | **BPL** | TRACKED by register issue(s) | PRIV-LANG, A-K1 |
| P9 quality register (carried items) | K4-live-Adzuna | OPT | TRACKED by register issue(s) | J-ADZUNA |
| P9 quality register (carried items) | Model-judged-RAGAS | OPT | TRACKED by register issue(s) | IR-RAGAS-LIVE-APPROVAL |
| P9 quality register (carried items) | Live-OCR-quality | OPT | TRACKED by register issue(s) | J-OCR, C-OCR |
| P9 quality register (carried items) | Live-speech-TTS-quality | OPT / BPL | TRACKED by register issue(s) | L-VOICE, W12.4E-13 |
| P9 quality register (carried items) | Live-multilingual-Mo-quality | OPT | TRACKED by register issue(s) | L-PRODQ, EX-04 |
| P9 quality register (carried items) | Live-multi-agent-provider-qual | OPT | NEW ISSUE XC-P9-Live-multi-agent-provider-qual (no register issue found) | XC-P9-Live-multi-agent-provider-qual |
| P9 quality register (carried items) | Human-translation-review-7-loc | **BPL** | TRACKED by register issue(s) | PRIV-LANG, L-NATIVE-UI |
| P9 quality register (carried items) | Legal-review-Privacy-Terms- | **BPL** | TRACKED by register issue(s) | PRIV-LEGAL, PRIV-LANG |
| P9 quality register (carried items) | Distributed-rate-limit-store | NBL | TRACKED by register issue(s) | EX-12.15 |
| P9 quality register (carried items) | Untracked-checkpoint-deletion- | NBL | NEW ISSUE XC-P9-Untracked-checkpoint-deletion (no register issue found) | XC-P9-Untracked-checkpoint-deletion |
| P9 quality register (carried items) | CSRF-posture | NBL | TRACKED by register issue(s) | H-CSRF |
| P9 quality register (carried items) | Deep-page-localization-debt | NBL | NEW ISSUE XC-P9-Deep-page-localization-debt (no register issue found) | XC-P9-Deep-page-localization-debt |
| P9 quality register (carried items) | -product-surfaces-review-rag-f | NBL | TRACKED by register issue(s) | G-A6-A8 |
| P9 quality register (carried items) | -PRAGMA-foreign_keys-ON-SQLite | NBL | TRACKED by register issue(s) | H-FK |
| P9 quality register (carried items) | Full-browser-matrix-Firefox-We | NBL | TRACKED by register issue(s) | H-BROWSER |
| P9 quality register (carried items) | A5-knowledge-readiness-distinc | NBL | TRACKED by register issue(s) | G-A6-A8 |
| P9 quality register (carried items) | B2-B3-durable-profile-opportun | NBL | TRACKED by register issue(s) | IR-AC03-TESTS |

Historical PASS rows (105) are kept as CLOSE WITH EVIDENCE and not re-opened; their evidence stays in the source documents.
