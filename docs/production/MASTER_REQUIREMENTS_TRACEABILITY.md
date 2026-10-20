# Master Requirements Traceability (Production Roadmap V2.2)

**Status:** PROPOSED baseline for owner review, generated 2026-10-21 by `scripts/production/reconcile_issues.py`. Nothing here upgrades a historical status or gate. The full per-item record (acceptance criteria, required tests, security/privacy impact, dependencies, evidence of closure, the verbatim historical row) is in [`PRODUCTION_ISSUE_RECONCILIATION.json`](PRODUCTION_ISSUE_RECONCILIATION.json); the tables below are the readable index.

Baseline: 394 register issues (52 closed, 342 active) + 39 new items = 433 traced rows. Unmapped: **0**.

Dispositions: FIX BEFORE R1.0, VERIFY BEFORE R1.0, OWNER DECISION, DEFER TO NAMED RELEASE (only while the feature stays disabled), CLOSE WITH EVIDENCE.

## Work packages

| WP | Name | Owner role (person not yet named) | Items |
|---|---|---|---|
| WP-01 | Governance, reviewers and owner decisions | Product Owner | 4 |
| WP-02 | Hosted deployment, operations and resilience | Platform and operations lead | 46 |
| WP-03 | Identity, email and access | Security lead | 7 |
| WP-04 | Privacy, data rights and legal | Privacy and legal lead | 33 |
| WP-05 | AI security and grounding policy | AI safety lead | 19 |
| WP-06 | Knowledge sources and retrieval (seven markets) | Knowledge and data lead | 86 |
| WP-07 | Candidate journeys, Mo and Practice quality | Product lead (candidate) | 15 |
| WP-08 | Multilingual programme (seven languages) | Localisation lead | 27 |
| WP-09 | Story Bank, Workspaces and shared reports | Product lead (collaboration) | 10 |
| WP-10 | Admin 2.0 (English-only): users, plans, reports, knowledge, navigation | Product lead (operations) | 36 |
| WP-11 | Commercial and billing (gated) | Commercial lead | 34 |
| WP-12 | Speech and realtime voice (gated) | Speech lead | 26 |
| WP-13 | External integrations | Integrations lead | 8 |
| WP-14 | Human validation and native review | Quality and human-review lead | 11 |
| WP-15 | Quality engineering, accessibility and technical debt | Engineering lead | 50 |
| WP-16 | Live evaluation and measurement | Evaluation lead | 21 |

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
| D-R11 | No production impact and no enabled-feature dependency: defer to R1.1 |
| D-COM | Commercial activation: R1.2 while billing gates stay False |
| D-INT | Later integrations: R1.2 while not configured |
| D-INTL | Knowledge/compensation outside the seven markets: R2.0 while Compensation V2 and international sources stay disabled |
| D-SPEECH | Server speech and realtime: R2.0 while governed speech gates stay False |
| D-RU | Russian: excluded from R1.0 |
| D-FL | Mandarin, Hindi, Arabic: R1.3 |
| +dup | Same meaning as an earlier issue: shares its disposition |

## R1.0: First production release, 30 November 2026: seven candidate languages (all gates), safety/privacy/operations blockers, English-only Admin

189 items.

| ID | Title | Disposition | WP | Prio | Historical status | Rule |
|---|---|---|---|---|---|---|
| BL-1 | Verify reviewer identities and accounts | FIX BEFORE R1.0 | WP-01 | P0 | DEFERRED - POST SUBMISSION | B1 |
| BL-2 | Appoint named human reviewers A, B, C | FIX BEFORE R1.0 | WP-01 | P0 | DEFERRED - POST SUBMISSION | B1 |
| BL-3 | Complete two-person role changes for appointments | FIX BEFORE R1.0 | WP-01 | P0 | DEFERRED - POST SUBMISSION | B1 |
| BL-8 | Legal review of commercial use of BLS content outside US (RB-LIC-1) | FIX BEFORE R1.0 | WP-06 | P0 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| K-PRIV | Privacy, Terms and AI-transparency pages are engineering drafts | FIX BEFORE R1.0 | WP-04 | P0 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| A-K1 | Germany K1 governed compensation set is an engineering draft | FIX BEFORE R1.0 | WP-06 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| B-SCANNER | Real malware scanner not configured for governed knowledge uploads | FIX BEFORE R1.0 | WP-06 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| BL-11 | Satisfy the 95% product-coverage gate (392 of 412) | FIX BEFORE R1.0 | WP-06 | P1 | OPEN - PRE-SUBMISSION QUALIFICATION | B1 |
| BL-12 | Separate runtime authorisation and deployment review for Compensation V2 | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-18 | Human measurement/alias reviews, appointments, persistent authorisation, licensing clearan | FIX BEFORE R1.0 | WP-01 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-19 | P10F targeted human validation | FIX BEFORE R1.0 | WP-14 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-4 | Decide on privileged reviewer endpoints | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-5 | Review and decide the 12 measurement batches | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6 | Review the five alias proposals individually | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.1 | Alias decision: Software Developer to 15-1252 | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.2 | Alias decision: Human Resources Manager to 11-3121 | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.3 | Alias decision: Sales Manager to 11-2022 | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.4 | Alias decision: Accountant to 13-2011 | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.5 | Alias decision: Financial Analyst to 13-2051 | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-6.6 | Data Analyst and Product Manager remain unresolved | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-7 | Resolve Data Analyst / Product Manager evidence gaps | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| BL-9 | Persistent-registry authorisation and promotion of us_soc_2018 and bls_oews | FIX BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B1 |
| EX-12.1 | EX-12 #1: TLS + HSTS live | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.10 | EX-12 #10: Private storage isolation | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.3 | EX-12 #3: Same-site session cookie | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.7 | EX-12 #7: Backup produces restorable artifacts | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.8 | EX-12 #8: Restore drill into *_restore DB | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.9 | EX-12 #9: Rollback | FIX BEFORE R1.0 | WP-02 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| H-KB-INGEST | Knowledge-ingestion security hardening | FIX BEFORE R1.0 | WP-02 | P1 | PARTIALLY REMEDIATED | B1 |
| H-MONITOR | Production monitoring and observability | FIX BEFORE R1.0 | WP-02 | P1 | DEFERRED - POST SUBMISSION | B1 |
| K-GDPR | No GDPR compliance/certification claim permitted | FIX BEFORE R1.0 | WP-04 | P1 | DEFERRED - POST SUBMISSION | B1 |
| K-HUMANSRC | Human source qualification | FIX BEFORE R1.0 | WP-04 | P1 | DEFERRED - POST SUBMISSION | B1 |
| K-TRANS-LEGAL | Engineering translations of legal/privacy/trust text | FIX BEFORE R1.0 | WP-08 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| L-AC24 | AC-24 Pilot and lessons remains PARTIAL | FIX BEFORE R1.0 | WP-14 | P1 | OPEN - PRE-SUBMISSION QUALIFICATION | B1 |
| REQ-LANG-01 | Audit every existing locale | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-02 | Verify all Candidate journeys in all seven languages | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-03 | Prompts and system policies work correctly in each language | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-04 | Validate localized interview questions, scoring, feedback and explanations | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-05 | Verify Story Bank and Workspaces in all seven languages | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-06 | Evaluate multilingual RAG and cross-language source attribution | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-07 | Language must never change labour-market country silently | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-08 | Language-specific injection, security and privacy regression suites | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-09 | Native-language human review | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-10 | Qualify legal and privacy translations before real-user access | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-11 | Track readiness and quality separately per language | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-12 | Keep Platform Admin English-only for R1.0 | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-13 | No language is called production-qualified before its gates pass | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-LANG-14 | Russian: exclude from R1.0 and do not expose it as an active beta locale | FIX BEFORE R1.0 | WP-08 | P1 | NEW - NOT STARTED | NEW |
| RF-02 | Wrong stack mode silently broke 'Start interview' (keyless stack without a key returned a  | FIX BEFORE R1.0 | WP-02 | P1 | NEW - NOT STARTED | NEW |
| A-04 | Step-up only for role changes (journey finding) | FIX BEFORE R1.0 | WP-15 | P2 | PARTIALLY REMEDIATED | B1 |
| EX-12.15 | EX-12 #15: Single-replica limits documented and honoured | FIX BEFORE R1.0 | WP-02 | P2 | PARTIALLY REMEDIATED | B1 |
| EX-12.2 | EX-12 #2: Automatic cert issuance/renewal | FIX BEFORE R1.0 | WP-02 | P2 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| EX-12.4 | EX-12 #4: CORS allowlist enforced | FIX BEFORE R1.0 | WP-02 | P2 | OPEN - PRODUCTION RELEASE BLOCKER | B1 |
| H-ENV | Cross-environment configuration | FIX BEFORE R1.0 | WP-02 | P2 | PARTIALLY REMEDIATED | B1 |
| H-MFA | Step-up is password re-authentication, not MFA | FIX BEFORE R1.0 | WP-02 | P2 | DEFERRED - POST SUBMISSION | B1 |
| H-REAPER | Quota reservation reaper not scheduled | FIX BEFORE R1.0 | WP-02 | P2 | DEFERRED - POST SUBMISSION | B1 |
| H-RESILIENCE | Provider operational resilience live behaviour | FIX BEFORE R1.0 | WP-02 | P2 | PARTIALLY REMEDIATED | B1 |
| J-BREVO-HOOK | Brevo delivery/bounce webhooks not implemented | FIX BEFORE R1.0 | WP-03 | P2 | DEFERRED - POST SUBMISSION | B1 |
| J-INTEG-READY | Production integration readiness | FIX BEFORE R1.0 | WP-13 | P2 | DEFERRED - POST SUBMISSION | B1 |
| J-OPENROUTER | OpenRouter live behaviour beyond P10E sample | FIX BEFORE R1.0 | WP-13 | P2 | PARTIALLY REMEDIATED | B1 |
| M-DOC-COVERAGE | Stale committed product-coverage summary (97%) | FIX BEFORE R1.0 | WP-15 | P2 | PARTIALLY REMEDIATED | B1 |
| PRIV-BACKUP | Backup erasure after account deletion | FIX BEFORE R1.0 | WP-04 | P2 | DEFERRED - POST SUBMISSION | B1 |
| W12.4E-12 | Server-side browser recording client | FIX BEFORE R1.0 | WP-12 | P2 | DEFERRED - POST SUBMISSION | B1 |
| W12.4E-16 | Browser disclosure legal/privacy review | FIX BEFORE R1.0 | WP-12 | P2 | DEFERRED - POST SUBMISSION | B1 |
| W9.8-D10 | Additional account-deletion safeguards | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| W9.8-D1a | Preparation-chat ownership index | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| W9.8-D2 | Consent/legal acceptance version history | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| W9.8-D9 | Audit context allow-list enforcement | FIX BEFORE R1.0 | WP-04 | P2 | PARTIALLY REMEDIATED | B1 |
| H-CSRF | CSRF posture | FIX BEFORE R1.0 | WP-02 | P3 | DEFERRED - POST SUBMISSION | B1 |
| H-WORKER | Governed knowledge and jobs depend on a separate worker | FIX BEFORE R1.0 | WP-02 | P3 | DEFERRED - POST SUBMISSION | B1 |
| IR-AC-LEDGER | Acceptance criteria dispositions are P9-era and spread over three documents | VERIFY BEFORE R1.0 | WP-07 | P0 | OPEN - PRE-SUBMISSION QUALIFICATION | B2 |
| IR-TURING-RUBRIC | The Turing College capstone brief and rubric are not in the repository | VERIFY BEFORE R1.0 | WP-04 | P0 | PARTIALLY REMEDIATED | S1 |
| B-EMBED-CRED | Embedding credential and guard coverage absent | VERIFY BEFORE R1.0 | WP-06 | P1 | NOT RUN | B2 |
| B-SEMCAL | Semantic live calibration NOT RUN | VERIFY BEFORE R1.0 | WP-06 | P1 | NOT RUN | B2 |
| C-CITE | Citation claim-support (faithfulness) review | VERIFY BEFORE R1.0 | WP-16 | P1 | PENDING HUMAN REVIEW | B1 |
| C-INT-HUMAN | Human-rated interview question/answer-evaluation quality | VERIFY BEFORE R1.0 | WP-16 | P1 | PENDING HUMAN REVIEW | B1 |
| C-KB-HUMAN | Human review of KB model answers (citation support, language, abstention) | VERIFY BEFORE R1.0 | WP-16 | P1 | PENDING HUMAN REVIEW | B1 |
| C-NATIVE | Native-language review of multilingual model answers | VERIFY BEFORE R1.0 | WP-08 | P1 | PENDING HUMAN REVIEW | B1 |
| D-08 | D-08 who curates aliases | VERIFY BEFORE R1.0 | WP-06 | P1 | PARTIALLY REMEDIATED | B2 |
| D-LANG | Localized policy sentences are engineering translations | VERIFY BEFORE R1.0 | WP-08 | P1 | PENDING HUMAN REVIEW | B1 |
| D-NOT-LIVE | Final corrections not live-validated | VERIFY BEFORE R1.0 | WP-05 | P1 | NOT RUN | S1 |
| H-BACKUP | Deployment and backup qualification | VERIFY BEFORE R1.0 | WP-02 | P1 | NOT RUN | B1 |
| H-PG-MULTI | Hosted multi-instance PostgreSQL not tested | VERIFY BEFORE R1.0 | WP-02 | P1 | NOT RUN | B1 |
| H-REDIS-LIVE | Live Redis validation | VERIFY BEFORE R1.0 | WP-02 | P1 | NOT RUN | B1 |
| IR-AC03-TESTS | AC-03 has no test for two-opportunity context selection, restart persistence or legacy-row | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| IR-AC18-RUNLIST | AC-18: no owner-scoped list of recent agent runs; selected-run retrieval evidence not show | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| IR-DEMO-KEY | A working copy with .env or .streamlit/secrets.toml makes the local backend contact the pr | VERIFY BEFORE R1.0 | WP-07 | P1 | PARTIALLY REMEDIATED | B2 |
| J-BREVO | Brevo live verification | VERIFY BEFORE R1.0 | WP-03 | P1 | NOT RUN | B1 |
| J-CLAMAV | Real malware scanner not configured | VERIFY BEFORE R1.0 | WP-13 | P1 | NOT RUN | B1 |
| J-REDIS | Redis integration unverified | VERIFY BEFORE R1.0 | WP-13 | P1 | NOT RUN | B1 |
| K-AIGUID | Legal/privacy review of AI-guidance and source-excerpt wording | VERIFY BEFORE R1.0 | WP-04 | P1 | PENDING HUMAN REVIEW | B1 |
| L-PRODQ | Production-quality human evaluation overall | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| L-REL-1 | No calibrated relevance floor | VERIFY BEFORE R1.0 | WP-06 | P1 | PARTIALLY REMEDIATED | B2 |
| L-ROUTE-1 | Non-English routing and structured lanes are English-keyword driven | VERIFY BEFORE R1.0 | WP-06 | P1 | DEFERRED - POST SUBMISSION | B2 |
| L-XLANG-1 | No cross-language semantic retrieval; native-phrasing queries unmeasured | VERIFY BEFORE R1.0 | WP-08 | P1 | PARTIALLY REMEDIATED | B2 |
| P2-01 | Human revalidation: Sharing and revocation discoverability | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| P2-02 | Human revalidation: Source-backed experience in a representative knowledge environment | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| P2-03 | Human revalidation: Answer score interpretation | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1+dup |
| P2-04 | Human revalidation: AI-generated vs sourced vs verified provenance clarity | VERIFY BEFORE R1.0 | WP-14 | P1 | PENDING HUMAN REVIEW | B1 |
| PRIV-LEGAL | Legal counsel review of Privacy, Terms and policy drafts | VERIFY BEFORE R1.0 | WP-04 | P1 | PENDING HUMAN REVIEW | B1 |
| RF-01 | Admin Knowledge Sources looked empty although the curated corpus was intact | VERIFY BEFORE R1.0 | WP-10 | P1 | CLOSED IN CODE (PR #210); verification pending | NEW |
| RF-03 | Live RAGAS result is PARTIAL (7 of 8 valid) with response relevancy 0.0 and context recall | VERIFY BEFORE R1.0 | WP-16 | P1 | NEW - NOT STARTED | NEW |
| AC-13/AC-23-A | Live browser STT correction burden NOT RUN | VERIFY BEFORE R1.0 | WP-12 | P2 | NOT RUN | B1 |
| BL-14 | P10C-F2C ESCO/ISCO | VERIFY BEFORE R1.0 | WP-06 | P2 | DEFERRED - POST SUBMISSION | M1 |
| BL-15 | P10C-F2D Germany and EU | VERIFY BEFORE R1.0 | WP-06 | P2 | DEFERRED - POST SUBMISSION | M1 |
| D-AGENT-TXT | Agent figure verification limited to tool results and candidate text | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-CITE-PROXY | Citation relevance is a shared-content-word proxy | VERIFY BEFORE R1.0 | WP-09 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-EST-FLAG | Unsourced-estimate offer in abstentions (flag fired 7/7) | VERIFY BEFORE R1.0 | WP-05 | P2 | PARTIALLY REMEDIATED | S1 |
| D-LEX | Lexical detection limits | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-MISS-AMB | Historical agent miss: ambiguous_role_hitl (no retrieval, no confirm_role pause) | VERIFY BEFORE R1.0 | WP-05 | P2 | PARTIALLY REMEDIATED | S1 |
| D-MISS-INS | Historical agent miss: insufficient_evidence (no retrieval) | VERIFY BEFORE R1.0 | WP-05 | P2 | PARTIALLY REMEDIATED | S1 |
| D-MISS-PREP | Historical agent miss: prep_plan_request (no tool, no gaps in state) | VERIFY BEFORE R1.0 | WP-05 | P2 | PENDING HUMAN REVIEW | S1 |
| D-NONNUM | Nonnumeric unsupported factual claims | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| D-POLB | Policy B retrieval decision remains model-driven | VERIFY BEFORE R1.0 | WP-05 | P2 | DEFERRED - POST SUBMISSION | S1 |
| EX-12.11 | EX-12 #11: Pause switch (hosted) | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.12 | EX-12 #12: Email verification flow (hosted) | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.13 | EX-12 #13: Malware fail-closed (hosted) | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.14 | EX-12 #14: CSP / mic permissions | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.5 | EX-12 #5: Readiness gating | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| EX-12.6 | EX-12 #6: Migration step (single head) | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| H-FAILPATH | Remaining failure-path testing | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| H-PG-QUERY | Analytics PostgreSQL query-plan review open | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT RUN | B1 |
| J-OCR | Live OCR quality unvalidated | VERIFY BEFORE R1.0 | WP-13 | P2 | NOT RUN | B1 |
| J-OIDC | Google OIDC live validation and frontend wiring | VERIFY BEFORE R1.0 | WP-03 | P2 | NOT RUN | B1 |
| J-RATE | Provider rate limits and failure handling live | VERIFY BEFORE R1.0 | WP-03 | P2 | NOT RUN | B1 |
| J-SEMANTIC | Semantic live calibration (L-REL-1/L-XLANG-1) NOT RUN | VERIFY BEFORE R1.0 | WP-08 | P2 | NOT RUN | B1 |
| K-LIC-DE | German Entgeltatlas (no terms) and Destatis (third-party catalogue licence) | VERIFY BEFORE R1.0 | WP-08 | P2 | PENDING HUMAN REVIEW | B1 |
| K-LIC-ESCO | ESCO data licence not named | VERIFY BEFORE R1.0 | WP-04 | P2 | PENDING HUMAN REVIEW | B1 |
| K-LIC-ISCO | ISCO-08 reuse beyond short excerpts needs ILO permission | VERIFY BEFORE R1.0 | WP-04 | P2 | PENDING HUMAN REVIEW | B1 |
| K-LIC-OGL | Commercial use outside home territory of OGL/Eurostat/INEGI content | VERIFY BEFORE R1.0 | WP-04 | P2 | PENDING HUMAN REVIEW | B1 |
| M-OR-KEY | Shared OpenRouter credential concerns | VERIFY BEFORE R1.0 | WP-09 | P2 | NOT VERIFIED | B1 |
| R-96a | PostgreSQL job claim (SKIP LOCKED) not executed live | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT VERIFIED | B1 |
| R-96b | PostgreSQL audit-trigger DDL not executed live | VERIFY BEFORE R1.0 | WP-02 | P2 | NOT VERIFIED | B1 |
| RF-04 | Blocking calls inside async request paths can deadlock the event loop | VERIFY BEFORE R1.0 | WP-15 | P2 | FIXED IN GUARD; audit not started | NEW |
| RF-05 | Optional-dependency tests failed in the base CI install | VERIFY BEFORE R1.0 | WP-15 | P2 | FIXED FOR RAGAS; audit not started | NEW |
| D-COUNTRY | Country-name coverage table | VERIFY BEFORE R1.0 | WP-05 | P3 | DEFERRED - POST SUBMISSION | S1 |
| D-MISS-5TH | Fifth miss behind 0.773 unidentified | VERIFY BEFORE R1.0 | WP-05 | P3 | NOT VERIFIED | S1 |
| D-MISS-PRAC | Historical agent miss: practice_handoff_hitl (no approve_practice_handoff pause) | VERIFY BEFORE R1.0 | WP-05 | P3 | PARTIALLY REMEDIATED | S1 |
| D-SENT | Sentence-removal precision | VERIFY BEFORE R1.0 | WP-05 | P3 | DEFERRED - POST SUBMISSION | S1 |
| D-SRC-LIST | Career-chat sources still list retrieved-but-uncited evidence | VERIFY BEFORE R1.0 | WP-05 | P3 | DEFERRED - POST SUBMISSION | S1 |
| H-PG-SECRETS | managed_secrets PostgreSQL path migration-tested on SQLite only | VERIFY BEFORE R1.0 | WP-02 | P3 | NOT VERIFIED | B1 |
| PRIV-DIFF | Report differencing across overlapping periods | VERIFY BEFORE R1.0 | WP-04 | P3 | DEFERRED - POST SUBMISSION | S1 |
| PRIV-DSAR | No Admin export of candidate data (DSAR) | VERIFY BEFORE R1.0 | WP-04 | P3 | DEFERRED - POST SUBMISSION | S1 |
| W10.10-AUDIT-CTX | Privacy workflow cross-store atomicity | VERIFY BEFORE R1.0 | WP-04 | P3 | PARTIALLY REMEDIATED | S1 |
| IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20) | OWNER DECISION | WP-07 | P0 | PENDING OWNER DECISION | O0 |
| IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | OWNER DECISION | WP-02 | P0 | PENDING OWNER DECISION | O0 |
| IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | OWNER DECISION | WP-07 | P0 | PENDING OWNER DECISION | O0 |
| B-EMBED-SEL | Embedding provider and model selection | OWNER DECISION | WP-06 | P1 | PENDING OWNER DECISION | O0 |
| C-PROTO | Reviewer protocols and rating rubric for AI quality | OWNER DECISION | WP-16 | P1 | PENDING OWNER DECISION | O0 |
| C-THRESH | Owner thresholds for AI quality | OWNER DECISION | WP-16 | P1 | PENDING OWNER DECISION | O0 |
| D-21 | D-21 name who performs qualified legal review | OWNER DECISION | WP-04 | P1 | PENDING OWNER DECISION | O0 |
| IR-DEVDB-STALE | The developer database is 12 Alembic revisions behind the code head | OWNER DECISION | WP-07 | P1 | PENDING OWNER DECISION | O0 |
| IR-RAGAS-LIVE-APPROVAL | Live RAGAS evaluation awaits the owner's spending approval and three prerequisites | OWNER DECISION | WP-06 | P1 | PENDING OWNER DECISION | O0 |
| K-PROVIDER | Third-party model provider data handling for real candidate data | OWNER DECISION | WP-04 | P1 | PENDING OWNER DECISION | O0 |
| REQ-LANG-16 | Approve and qualify the proposed primary market per language | OWNER DECISION | WP-08 | P1 | NEW - NOT STARTED | NEW |
| REQ-OWN-01 | Owner-requested requirement: Admin 2.0 | OWNER DECISION | WP-10 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-02 | Owner-requested requirement: Plans | OWNER DECISION | WP-10 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-03 | Owner-requested requirement: Users | OWNER DECISION | WP-10 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-04 | Owner-requested requirement: Reports | OWNER DECISION | WP-10 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-05 | Owner-requested requirement: Knowledge (Admin sources) | OWNER DECISION | WP-10 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-06 | Owner-requested requirement: Story Bank | OWNER DECISION | WP-09 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-07 | Owner-requested requirement: Workspaces | OWNER DECISION | WP-09 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| REQ-OWN-08 | Owner-requested requirement: Navigation | OWNER DECISION | WP-10 | P1 | NEW - REQUIREMENT TEXT NOT IN REPOSITORY | NEW |
| SJA-05 | Knowledge approval has no distinct-actor rule or step-up | OWNER DECISION | WP-15 | P1 | PENDING OWNER DECISION | O0 |
| H-REDIS-POLICY | Redis failure policy per bucket undecided | OWNER DECISION | WP-02 | P2 | PENDING OWNER DECISION | O0 |
| K-ATTR | Attribution wording decisions | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| K-LEGALACC | Legal acceptance of owner policy decisions | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| M-LEDGER | Mo and company-research cost-ledger gap | OWNER DECISION | WP-15 | P2 | PENDING OWNER DECISION | O0 |
| PRIV-POLICY01 | Verified-email policy (POLICY-01) | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| PRIV-RET | No retention periods for candidate content | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| W9.8-D7 | Original-file export bundle | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| XC-AC-AC-18 | Acceptance ledger (current) AC-18: Review surfaces: owned recent runs, safe specialist eve | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-AC-AC-23 | Acceptance ledger (current) AC-23: Voice measurement: defined sample, reference transcript | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-AC-AC-24 | Acceptance ledger (current) AC-24: Pilot and lessons: actual participant observations dist | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-AC-AC-25 | Acceptance ledger (current) AC-25: Submission consistency: README, three decks, selected t | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (UNKNOWN) | NEW |
| XC-P9-Deep-page-localization-debt | P9 quality register (carried items) Deep-page-localization-debt: Deep-page localization de | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (NBL) | NEW |
| XC-P9-Live-multi-agent-provider-qual | P9 quality register (carried items) Live-multi-agent-provider-qual: Live multi-agent/provi | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (OPT) | NEW |
| XC-P9-Live-transactional-email | P9 quality register (carried items) Live-transactional-email: Live transactional email | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (**BPL**) | NEW |
| XC-P9-Untracked-checkpoint-deletion | P9 quality register (carried items) Untracked-checkpoint-deletion-: Untracked checkpoint d | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (NBL) | NEW |
| XC-REL-R-33 | Release acceptance matrix (P10B) R-33: Email-verification behaviour pinned | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (ACCEPTED) | NEW |
| XC-REL-R-97 | Release acceptance matrix (P10B) R-97: Google OIDC live behaviour unvalidated | OWNER DECISION | WP-15 | P2 | NEW - UNMAPPED (ACCEPTED) | NEW |
| D-16 | D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT) | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| PRIV-SUPPORT-NOTICE | Support data / privacy request response time | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D1b | Preparation-chat selective deletion | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D3 | Bulk memory deletion | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D4 | Per-version document deletion | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D5 | Auth-session list/revoke UI | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D6 | Feedback list and deletion page | OWNER DECISION | WP-04 | P3 | PENDING OWNER DECISION | O0 |
| W9.8-D8 | Orphan workspace invitations to a deleted user's email | OWNER DECISION | WP-09 | P3 | PENDING OWNER DECISION | O0 |

## R1.1: Post-launch stabilisation: operational depth, accessibility and performance polish, non-safety technical debt

114 items.

| ID | Title | Disposition | WP | Prio | Historical status | Rule |
|---|---|---|---|---|---|---|
| B-COVEVAL | Decision whether to change coverage evaluator to check data origin/country (F-COV-1) | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| C-USD15 | USD 15 extra ceiling not approved; 15 calls remain | OWNER DECISION | WP-16 | P2 | PENDING OWNER DECISION | O0 |
| D-01 | D-01 adopt or amend recovered GKB/C1-C4 specification | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| D-02 | D-02 adopt ambiguity-state and recency/eligibility policy | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| F2B-D22 | D-22 ASHE weekly never annualised; unanswered | OWNER DECISION | WP-06 | P2 | PENDING OWNER DECISION | O0 |
| A-AGG | Five BLS-specific aggregates quarantined | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-05 | D-05 padded ISCO identity and plan for 21 legacy rows | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-06 | D-06 baseline manifest freeze (GKB-0) | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-10 | D-10 FX and PPP sources and methodology | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-11 | D-11 secondary-data qualification criteria | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-14 | D-14 regional-geography classification rule (policy p10c-d/1) | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-17 | D-17 evidence-state vocabulary adoption | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| D-18-19 | D-18 / D-19 South America region vocabularies and national classifications | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| IR-REHEARSAL-CALL | One unplanned live agent run during the P11 rehearsal (outside the P10E ledger) | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| J-OIDC-PWD | OIDC-only users cannot set a password via recovery | OWNER DECISION | WP-03 | P3 | PENDING OWNER DECISION | O0 |
| M-LEGACY01 | Legacy Streamlit UI retained (LEGACY-01) | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| M-POLICY02 | Evaluation score consistency (POLICY-02) | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| SJA-01 | AI config: second approver must be a second Platform Admin | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| SJA-02 | Knowledge Admin cannot retry/cancel failed jobs | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| SJA-04 | Operations Admin partly useful Review/Diagnostics | OWNER DECISION | WP-10 | P3 | PENDING OWNER DECISION | O0 |
| A-COV-SYN | Synthetic vs real source gaps in coverage | DEFER TO NAMED RELEASE | WP-06 | P2 | PARTIALLY REMEDIATED | D-R11 |
| A-OOH | BLS OOH / employment projections package unapproved | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| A-OPT-CAND | Other Package 3-7 items with unverified terms | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-R11 |
| B-COV-REMEAS | Source-backed coverage re-measurement after real qualification (metric C) | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| B-RAGAS-CRED | RAGAS evaluator credential absent (RAGAS_EVAL_API_KEY) | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT RUN | D-R11 |
| B-RAGAS-GUARD | Guarded RAGAS judge path on the P10E ledger | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT RUN | D-R11 |
| BL-10 | Reassess product coverage after qualification steps | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| C-AC22 | AC-22 live comparative benchmark | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-R11 |
| C-AGENT22 | Agent tool-selection recall 0.773 (22 cases): 5 misses not itemised | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-R11 |
| C-MODELCONTRACT | KB model-quality contract (mode C) remains unauthorised in full | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-R11 |
| C-NAT-P208 | Mo response naturalness (P2-08) | DEFER TO NAMED RELEASE | WP-16 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| C-PACK | Opportunity Pack and analytics narrative model quality | DEFER TO NAMED RELEASE | WP-16 | P2 | NOT RUN | D-R11 |
| C-PROFILE | Model-profile comparison (Fast vs Balanced vs Advanced) | DEFER TO NAMED RELEASE | WP-16 | P2 | PARTIALLY REMEDIATED | D-R11 |
| C-SMALL | Small-sample limits of all live AI results | DEFER TO NAMED RELEASE | WP-16 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| CJ-D-01 | No candidate control to invite members or share a report or story | DEFER TO NAMED RELEASE | WP-09 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| CJ-D-05 | 'Reviewed by you' provenance badge not rendered; no AI-suggested story path | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| CJ-D-06 | Opportunity fields other than status cannot be edited after creation | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| CJ-D-07 | No provider-specific failure copy | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| CJ-D-08 | Dictation language is per device, not per account | DEFER TO NAMED RELEASE | WP-07 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| F-07 | Raw timestamps, snake_case headers, long ids | DEFER TO NAMED RELEASE | WP-10 | P2 | PARTIALLY REMEDIATED | D-R11 |
| F-08 | Overview hierarchy | DEFER TO NAMED RELEASE | WP-10 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| F-12 | High-risk action styling | DEFER TO NAMED RELEASE | WP-10 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| F2B-ASHE-ED | ASHE Table 14 SOC classification edition unverified | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-R11 |
| F2B-ASHE-GUIDE | ASHE guide to tables and Table 14 notes unread | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-R11 |
| F2B-ASHE-REV | Revised ASHE 2025 dataset expected Oct/Nov 2026 | DEFER TO NAMED RELEASE | WP-06 | P2 | NOT VERIFIED | D-R11 |
| G-CONTRAST | Automated contrast audit not done | DEFER TO NAMED RELEASE | WP-10 | P2 | NOT RUN | D-R11 |
| G-HDR-390 | Candidate header logo/'More' overlap at 390 px | DEFER TO NAMED RELEASE | WP-10 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| G-SR | Real screen-reader / assistive-technology testing not done | DEFER TO NAMED RELEASE | WP-10 | P2 | NOT RUN | D-R11 |
| H-RESCACHE | Research-cache evaluator isolation | DEFER TO NAMED RELEASE | WP-02 | P2 | PARTIALLY REMEDIATED | D-R11 |
| IR-RETRIEVAL-DEFERRED | Native-phrasing cross-language retrieval remains an offline-measured gap | DEFER TO NAMED RELEASE | WP-08 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| L-LIVE-LANG | Live generated-language validation (R-50) | DEFER TO NAMED RELEASE | WP-08 | P2 | PARTIALLY REMEDIATED | D-R11 |
| L-PILOT-COV | Pilot 2 coverage gaps | DEFER TO NAMED RELEASE | WP-14 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| L-STALE-1 | No staleness/publication-date handling in narrative lane | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-R11 |
| M-ISOLATION | Evaluators without test-isolation bootstrap | DEFER TO NAMED RELEASE | WP-15 | P2 | PARTIALLY REMEDIATED | D-R11 |
| P2-09 | Opera voice recording failure needs reproduction | DEFER TO NAMED RELEASE | WP-14 | P2 | NOT VERIFIED | D-R11 |
| A-09 | Jobs have no dead-letter state | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| A-CL | Chile INE CC BY-SA ShareAlike review | DEFER TO NAMED RELEASE | WP-09 | P3 | PENDING HUMAN REVIEW | D-R11 |
| A-ILO | ILOSTAT site terms and per-indicator terms unread | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-R11 |
| A-ONET | O*NET crosswalks (Component 1c) deferred | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| A-OTHER19 | 19 'other' registered sources never researched | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-R11 |
| A-SA10 | Ten South American markets terms unverified | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-R11 |
| B-BM25 | BM25 pure-Python scoring about 22 ms p50 over 14k chunks | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| B-FRESH | Freshness / supersession policy for sources | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| B-NOSNAP | Governed knowledge has no snapshot/rollback model; depends on a worker | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| B-RC-TRANSIENT | Unexplained transient eval_product_coverage failure and macOS exit-134 aborts | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-R11 |
| B-TOKENISER | Offline hash embedder ASCII tokeniser | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| BL-17 | P10C-F2F wider South America and ILOSTAT | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| C-AGENT-REPEAT | Agent behaviour consistency across repeats | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT RUN | D-R11 |
| C-COST | Provider cost reconciliation gaps | DEFER TO NAMED RELEASE | WP-16 | P3 | PARTIALLY REMEDIATED | D-R11 |
| C-LANGFUSE | Live Langfuse not validated | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT VERIFIED | D-R11 |
| C-OCR | Live OCR quality sample | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT RUN | D-R11 |
| D-09 | D-09 five-category relationship qualification for crosswalks | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| D-20 | D-20 no official SOC/NOC to ISCO-08 crosswalk | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| F-02 | Developer-facing Review copy | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-R11 |
| F-06 | Fragmented Audit surfaces | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-R11 |
| F-09 | Repeated suppressed metrics | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| F-15 | Raw environment names in Flags page | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| F-16 | Small inline link targets | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-R11 |
| F-17 | Providers vs Integrations overlap | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-R11 |
| F2B-ASHE-SUPP | ASHE December 2025 correction: exact suppressed cells unverified | DEFER TO NAMED RELEASE | WP-06 | P3 | PARTIALLY REMEDIATED | D-R11 |
| G-A6-A8 | Owned-run list (A6) and selected-run RAG (A8) review surfaces | DEFER TO NAMED RELEASE | WP-10 | P3 | NOT VERIFIED | D-R11 |
| G-CAP-PARTIAL | Admin capability matrix PARTIAL rows | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-R11 |
| G-CHURN | Churn rate unavailable in Reports | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| G-REVIEW-COPY | Residual technical Review/Diagnostics wording | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| G-WALK-ENV | Admin walkthrough used dev server and seeded data | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| G-WS-DEACT | Admin workspace deactivation and universal operator search not built | DEFER TO NAMED RELEASE | WP-09 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| H-BROWSER | Full browser matrix | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| H-CI-PERF | CI test-setup cost | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| H-DEVDB | Developer DB migration lag / W10.13 dev-DB incident | DEFER TO NAMED RELEASE | WP-02 | P3 | PARTIALLY REMEDIATED | D-R11 |
| H-FK | SQLite PRAGMA foreign_keys not enabled | DEFER TO NAMED RELEASE | WP-02 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| J-BREVO-CACHE | Cached Brevo/provider clients need restart on rotation | DEFER TO NAMED RELEASE | WP-03 | P3 | PARTIALLY REMEDIATED | D-R11 |
| J-INVITE-MAIL | Workspace invitation mail not instrumented | DEFER TO NAMED RELEASE | WP-09 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| J-LANGFUSE | Langfuse live validation | DEFER TO NAMED RELEASE | WP-13 | P3 | NOT RUN | D-R11 |
| J-OIDC-STEPUP | OIDC-only admin cannot step up | DEFER TO NAMED RELEASE | WP-03 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| J-RAGAS | RAGAS live NOT RUN | DEFER TO NAMED RELEASE | WP-13 | P3 | NOT RUN | D-R11 |
| L-CODE-1 | Occupation codes in questions do not resolve | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| L-INGEST-SIZE | No per-file size limit in legacy ingestion loaders | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| L-META-1 | Sidecar .meta.json can override provenance metadata | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| M-DOC-C1 | CLAUDE.md says realtime voice (C1) DEFERRED | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-DOC-CLAIMS | PRODUCT_CLAIMS stale entries (D-04) | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-DOC-COUNT | Admin destination count inconsistency | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-R11 |
| M-DOC-LIMITS | docs/limitations.md describes Streamlit-era state | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-DOC-OIDC | W12.4C internal contradiction on PKCE/nonce | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-DOC-OPT | Sprint-4 quality_optimisation_audit TODO table | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-R11 |
| M-DOC-PLAN | Phase plan stale W12.4 'NOT STARTED' headings | DEFER TO NAMED RELEASE | WP-15 | P3 | PENDING HUMAN REVIEW | D-R11 |
| M-RECON-1 | Provider-cost reconciliation discrepancy (P10E) | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-RECON-2 | Provider-cost reconciliation discrepancy (P10E-R1 section 11) | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-RECON-3 | Provider-cost reconciliation (P10E-R2 section 7) | DEFER TO NAMED RELEASE | WP-15 | P3 | NOT VERIFIED | D-R11 |
| M-RESCACHE-INC | Research-cache contamination incidents (W10.11, RC-QUAL-ENV-01, W12.4C) | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-R11 |
| P2-06 | Re-evaluate marketing/pricing positioning with participants | DEFER TO NAMED RELEASE | WP-14 | P3 | PENDING HUMAN REVIEW | D-R11 |
| PA-A-08 | Normal platform settings beyond pause and two flags are environment-only | DEFER TO NAMED RELEASE | WP-02 | P3 | PARTIALLY REMEDIATED | D-R11 |
| SJA-06 | Held permissions with no consuming route | DEFER TO NAMED RELEASE | WP-15 | P3 | PARTIALLY REMEDIATED | D-R11 |
| SJA-07 | Support replies in-app only; no attachments or SLA | DEFER TO NAMED RELEASE | WP-10 | P3 | DEFERRED - POST SUBMISSION | D-R11 |
| TD-W9-03 | Locale-aware font/subset loading | DEFER TO NAMED RELEASE | WP-08 | P3 | DEFERRED - POST SUBMISSION | D-R11 |

## R1.2: Commercial activation and external integrations (billing, Stripe, paid plans, Adzuna, external paging) behind owner approval

40 items.

| ID | Title | Disposition | WP | Prio | Historical status | Rule |
|---|---|---|---|---|---|---|
| F2B1-OD-01 | Legal seller entity | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-02 | Product classification (automated digital product) | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-03 | Product tax code | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-04 | What Premium includes beyond Basic | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-05 | Premium monthly price | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-ALLOW | Numerical Basic/Premium allowances not approved | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-ENT-POLICY | Paid entitlement policy unapproved | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-FAST | Basic-to-Fast transition not approved | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | OWNER DECISION | WP-11 | P1 | PENDING OWNER DECISION | O0 |
| F2B1-OD-06 | Premium annual price (no annual plan exists) | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-07 | Currency | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-08 | Tax-inclusive presentation | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-09 | Supported customer countries | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-10 | B2B subscriptions | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-11 | Trial policy | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-12 | Failed-payment grace period | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-13 | Cancellation policy | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-14 | Refund policy | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-15 | Dispute entitlement policy | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| F2B1-OD-16 | Billing data retention | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| I-GRANDFATHER | Grandfathering of existing candidates | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| I-HISTORY-SHARE | Existing-share policy before history activation | OWNER DECISION | WP-09 | P2 | PENDING OWNER DECISION | O0 |
| I-RESET | Quota reset periods not approved | OWNER DECISION | WP-11 | P2 | PENDING OWNER DECISION | O0 |
| PRIV-BILL-RET | Billing data retention and erasure review | OWNER DECISION | WP-04 | P2 | PENDING OWNER DECISION | O0 |
| SJA-03 | Billing/Security-Privacy admins cannot see queue state | OWNER DECISION | WP-15 | P3 | PENDING OWNER DECISION | O0 |
| CJ-D-02 | Pricing page versus account page wording for Premium | DEFER TO NAMED RELEASE | WP-07 | P1 | PARTIALLY REMEDIATED | D-COM |
| F1-07 | Account deletion cannot cancel a live provider subscription | DEFER TO NAMED RELEASE | WP-11 | P1 | PARTIALLY REMEDIATED | D-COM |
| I-GATES | 12 rollout and billing gates all False | DEFER TO NAMED RELEASE | WP-11 | P1 | DEFERRED - POST SUBMISSION | D-COM |
| I-P1P3 | Unverified Stripe provider contracts (P-1..P-3) | DEFER TO NAMED RELEASE | WP-11 | P1 | NOT VERIFIED | D-COM |
| I-STRIPE-SANDBOX | Stripe sandbox qualification (F2-B2/F3) | DEFER TO NAMED RELEASE | WP-11 | P1 | NOT RUN | D-COM |
| I-UG | Ask4Mo UG incorporation and legal dependencies | DEFER TO NAMED RELEASE | WP-11 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | D-COM |
| I-D02 | Pricing page vs account page inconsistency (journey D-02) | DEFER TO NAMED RELEASE | WP-11 | P2 | PARTIALLY REMEDIATED | D-COM |
| I-LIFECYCLE | Stripe subscription lifecycle never exercised against a real provider | DEFER TO NAMED RELEASE | WP-11 | P2 | NOT RUN | D-COM |
| I-MOCK | Billing is mock only | DEFER TO NAMED RELEASE | WP-11 | P2 | DEFERRED - POST SUBMISSION | D-COM |
| I-REFUND-EXEC | Seller-initiated refund execution and billing alert delivery | DEFER TO NAMED RELEASE | WP-11 | P2 | DEFERRED - POST SUBMISSION | D-COM |
| I-SCHED | Reconciliation scheduler and real StripeStateReader | DEFER TO NAMED RELEASE | WP-11 | P2 | DEFERRED - POST SUBMISSION | D-COM |
| B-CIPARITY | CI parity of clean-checkout coverage baseline on GitHub | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-COM |
| C-K4 | K4 live Adzuna validation | DEFER TO NAMED RELEASE | WP-16 | P3 | NOT RUN | D-INT |
| F-11 | Refund amount in minor units | DEFER TO NAMED RELEASE | WP-10 | P3 | PARTIALLY REMEDIATED | D-COM |
| J-ADZUNA | Adzuna live verification (K4) | DEFER TO NAMED RELEASE | WP-13 | P3 | NOT RUN | D-INT |

## R1.3: New languages: Mandarin, Hindi, Arabic (language-specific engineering and human qualification each)

2 items.

| ID | Title | Disposition | WP | Prio | Historical status | Rule |
|---|---|---|---|---|---|---|
| REQ-LANG-15 | R1.3 languages: Mandarin, Hindi, Arabic | DEFER TO NAMED RELEASE | WP-08 | P2 | NEW - NOT STARTED | NEW |
| L-LANG-AR | Arabic not a supported language | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-FL |

## R2.0: International expansion and deep modalities: knowledge/compensation beyond the seven markets, server speech and realtime voice, Russian, enterprise

36 items.

| ID | Title | Disposition | WP | Prio | Historical status | Rule |
|---|---|---|---|---|---|---|
| D-07 | D-07 ESCO language releases | OWNER DECISION | WP-06 | P3 | PENDING OWNER DECISION | O0 |
| EX-04 | Human voice-quality review NOT RUN (7-locale speech) | DEFER TO NAMED RELEASE | WP-12 | P1 | NOT RUN | D-SPEECH |
| I-STRIPE-ACCT | Dedicated Stripe account and Managed Payments eligibility | DEFER TO NAMED RELEASE | WP-11 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | D-RU |
| L-NATIVE-UI | Human/native translation review of interface and Help (7-8 locales) | DEFER TO NAMED RELEASE | WP-08 | P1 | OPEN - PRODUCTION RELEASE BLOCKER | D-RU |
| PRIV-LANG | Privacy/legal translations unreviewed (8 locales incl. Russian) | DEFER TO NAMED RELEASE | WP-08 | P1 | PENDING HUMAN REVIEW | D-RU |
| W12.4E-1 | Whisper self-hosted versus hosted decision | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-13 | Human speech-quality validation | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-14 | Provider authorization flag activation | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-15 | Production speech operational qualification | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-2 | Hosted Whisper data-processing review | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-3 | Speech hosting architecture | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-6 | Genuine Whisper execution validation | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-7 | Genuine Kyutai execution validation | DEFER TO NAMED RELEASE | WP-12 | P1 | DEFERRED - POST SUBMISSION | D-SPEECH |
| A-NATIVE-KB | Governed KB native content is English (+ some German) | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-RU |
| AC-23-B | Realtime provider round-trip latency NOT RUN | DEFER TO NAMED RELEASE | WP-12 | P2 | NOT RUN | D-SPEECH |
| BL-13 | P10C-F2B United Kingdom (Package 2) | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-INTL |
| BL-16 | P10C-F2E Canada, Mexico, Brazil | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-INTL |
| E-LIVE-MULTI | Live multilingual Mo/voice quality unvalidated | DEFER TO NAMED RELEASE | WP-12 | P2 | NOT RUN | D-SPEECH |
| E-LOCAL-ENGINES | Local engine bindings limited | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| EX-02 | Realtime voice (C1) live round-trip NOT RUN | DEFER TO NAMED RELEASE | WP-12 | P2 | NOT RUN | D-SPEECH |
| F2B-UK-ALIAS | No UK alias evidence assessed | DEFER TO NAMED RELEASE | WP-06 | P2 | DEFERRED - POST SUBMISSION | D-INTL |
| L-VOICE | Voice not human-validated (PF-19 / AC-23 live) | DEFER TO NAMED RELEASE | WP-14 | P2 | PENDING HUMAN REVIEW | D-RU |
| W12.4E-10 | Per-voice licence verification | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-17 | Response-origin authorization hardening | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-18 | Engine timeout and cancellation hardening | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-4 | Model weights and resource placement | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-5 | CPU/GPU and memory sizing | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-8 | Kyutai gated model-weight approval | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| W12.4E-9 | Kyutai licence and attribution verification | DEFER TO NAMED RELEASE | WP-12 | P2 | DEFERRED - POST SUBMISSION | D-SPEECH |
| E-RATE | Realtime/speech concurrency bounded per process | DEFER TO NAMED RELEASE | WP-12 | P3 | DEFERRED - POST SUBMISSION | D-SPEECH |
| E-RU | Russian speech excluded | DEFER TO NAMED RELEASE | WP-12 | P3 | DEFERRED - POST SUBMISSION | D-RU |
| F2B-UK-V1 | UK V1 reconciliation: 527 ASHE rows, one with no occupation code | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-INTL |
| F2B-UKSOC-VER | Current UK SOC 2020 file version unverified | DEFER TO NAMED RELEASE | WP-06 | P3 | NOT VERIFIED | D-INTL |
| L-LANG-RU | Russian is interface/Mo-conversation only, not a KB language | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-RU |
| L-RU-INFLECT | Inflected Russian country names not recognised | DEFER TO NAMED RELEASE | WP-06 | P3 | DEFERRED - POST SUBMISSION | D-RU |
| W12.4E-11 | Dutch server-side TTS qualification | DEFER TO NAMED RELEASE | WP-12 | P3 | DEFERRED - POST SUBMISSION | D-SPEECH |

## n/a: closed items (evidence preserved)

52 items.

| ID | Title | Disposition | WP | Prio | Historical status | Rule |
|---|---|---|---|---|---|---|
| IR-P12 | A P12 (final rehearsal and freeze) exists in the reference runbook but not in the phase pl | CLOSE WITH EVIDENCE | WP-07 | P1 | CLOSED - VERIFIED | C0 |
| CJ-D-04 | PRODUCT_CLAIMS.md contains stale entries | CLOSE WITH EVIDENCE | WP-07 | P2 | CLOSED - VERIFIED | C0 |
| IR-ROADMAP-STALE | Roadmap and phase plan described merged PRs as pending | CLOSE WITH EVIDENCE | WP-07 | P2 | CLOSED - VERIFIED | C0 |
| PA-A-01 | Knowledge Base accessibility (owner-reported) | CLOSE WITH EVIDENCE | WP-02 | P2 | CLOSED - VERIFIED | C0 |
| PA-A-02 | No writable credential store | CLOSE WITH EVIDENCE | WP-02 | P2 | CLOSED - VERIFIED | C0 |
| PA-A-05 | Knowledge readiness, inventory and retrieval test missing | CLOSE WITH EVIDENCE | WP-02 | P2 | CLOSED - VERIFIED | C0 |
| A-10 | Capability matrix lacked email row | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| B-CAP4096 | 2,000 output cap blocked 5 of 22 agent cases | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| B-HELPER | Agent helper pinned to code-default model slug (gpt-5.6-terra) | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| B-XLANG-HARNESS | Non-English retrieval gap and mixed de/fr scaffold reported as product findings | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A1 | OEWS data dictionary / field semantics (precondition J,K) unverified | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A2 | Isolated ingestion environment (precondition M) unverified | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A3 | Reliability threshold for PRSE-based qualification | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A4 | Package 1 files unacquired; registry transition for isolated DB | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A5 | Research-cache evaluator isolation UNRESOLVED (roadmap) | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-A6 | CI-reproducible knowledge evaluation fixture DESIGNED not implemented (roadmap) | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| C-AGENT-EVID | Harness: agent completion inflated; no per-case evidence (defects E,F) | CLOSE WITH EVIDENCE | WP-16 | P3 | CLOSED - VERIFIED | C0 |
| C-INT-HARNESS | Interview quality harness and personas did not exist (P10E) | CLOSE WITH EVIDENCE | WP-16 | P3 | CLOSED - VERIFIED | C0 |
| D-ABST-CIT | Citations on abstentions presentation decision | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C1 | Cross-geography figure authorised by foreign evidence | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C2 | Citation marker exempted estimate-offer guard | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C3 | External statistic without retrieval only labelled | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| D-C4 | Citation/sources metadata inconsistent after marker removal | CLOSE WITH EVIDENCE | WP-05 | P3 | CLOSED - VERIFIED | C0 |
| F-01 | Review/Diagnostics outside Admin shell | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-03 | Admin navigation at 390 px too tall | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-04 | Integrations mobile overflow/clipping | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-05 | Billing forms off screen, focus not moved | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-10 | Plans and Billing relationship unexplained | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-13 | No secret-rotation control | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| F-14 | Development anonymous account in Users list | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| G-A5 | Knowledge-readiness distinction (A5) | CLOSE WITH EVIDENCE | WP-10 | P3 | CLOSED - VERIFIED | C0 |
| H-PAUSE | Process-local pause switch (p8 section 15; SEC-W10-05) | CLOSE WITH EVIDENCE | WP-02 | P3 | CLOSED - VERIFIED | C0 |
| H-SESSION-STORE | In-memory session store blocks multi-replica (p8 section 15) | CLOSE WITH EVIDENCE | WP-02 | P3 | CLOSED - VERIFIED | C0 |
| I-RECOVER-PERM | Billing recovery permission decision | CLOSE WITH EVIDENCE | WP-11 | P3 | CLOSED - VERIFIED | C0 |
| K-PRIV-W9 | PRIV-W9-02 consent/legal acceptance history not stored | CLOSE WITH EVIDENCE | WP-04 | P3 | CLOSED - VERIFIED | C0 |
| L-ANSWER-GUARD | Career Chat lacked occupation-grounding guard | CLOSE WITH EVIDENCE | WP-06 | P3 | CLOSED - VERIFIED | C0 |
| M-BASELINE-EVALS | Four baseline evaluators failing on main (P4-A) | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-EVAL-WRITES | Evaluators rewrote committed artifacts | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-F109 | Reporting test clock pinned to 2026-10-15 (F1-09) | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-LATENT-RES | Evaluation corrections preserve historical evidence | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| M-TODO-CODE | TODO/FIXME in source code | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| PRIV-EXPORT-D03 | Export carries stale legal-acceptance wording | CLOSE WITH EVIDENCE | WP-04 | P3 | CLOSED - VERIFIED | C0 |
| PRIV-W9-01/02 | PRIV-W9-01 and PRIV-W9-02 closure cross-reference | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| ROLE-W10-01 | platform_admin completeness / role scope | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-01 | Account deactivation did not revoke sessions | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-02 | Privileged audit not fail-closed/atomic | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-03 | Non-canonical audit events/no request id/no denial audit | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-04 | Privacy request queue non-operational | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-05 | Process-local pause | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| SEC-W10-06 | /admin/providers echoed raw provider values | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| TD-W9-01 | Invalid Tailwind colour-token opacity classes | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |
| TD-W9-02 | Backend test-isolation leak and 13 .env failures | CLOSE WITH EVIDENCE | WP-15 | P3 | CLOSED - VERIFIED | C0 |

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
