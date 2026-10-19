# Post-Submission Deferred Issues Register

**Status:** CONSOLIDATED REGISTER, generated 2026-10-19 during the integrated Candidate/Admin/Operations requalification (main `fb2d264`: 387 issues, 336 active, 51 closed) and **updated in the final acceptance reconciliation (main `4043429`; 390 issues, 338 active, 52 closed) and in P11 (main `3d1af6f`: two issues added, `IR-DEMO-KEY` and `IR-REHEARSAL-CALL`; 392, 340, 52) and in the review-day readiness work (two more added, `IR-DEVDB-STALE` and `IR-RAGAS-LIVE-APPROVAL`; **394, 342, 52**)**:  three issues added (`IR-AC03-TESTS`, `IR-AC18-RUNLIST`, `IR-DEADLINE`), `IR-P12` closed on the owner's direction, and several remaining-work notes refreshed; no issue was deleted or reclassified to ease acceptance. This is a **supporting document under the canonical roadmap** (`capstone_phase_plan.md` stays canonical for scope and sequence). It is **not** a competing roadmap and it replaces none of its source registers, which are preserved unchanged.

**Rules this register follows.** Deferring an item is a scheduling decision only: it is never completion and never a waiver. It does not authorize removing a mandatory gate, passing a failed evaluation, ignoring a vulnerability, using unlicensed data, exposing private candidate data, enabling production services, treating a mock as live, claiming human qualification or waiving a Turing College requirement. An item that affects the safety or validity of the current capstone is `OPEN — PRE-SUBMISSION QUALIFICATION`; one that blocks only commercial deployment is `OPEN — PRODUCTION RELEASE BLOCKER`. One canonical `DI-` identifier is kept per issue even when an issue appears in several readiness views. Owners and dates are never invented (`UNKNOWN` where not recorded; most first-recorded dates are UNKNOWN because git history was not mined).

**Machine-readable form:** [`post_submission_deferred_issues.json`](post_submission_deferred_issues.json) holds every field of every row (including closed rows and aliases). The tables below are generated from it.

## 1. Totals

394 issues recorded: **342 active** and 52 CLOSED — VERIFIED (kept for reconciliation only).

| Status | Count |
|---|---|
| OPEN — PRE-SUBMISSION QUALIFICATION | 3 |
| OPEN — PRODUCTION RELEASE BLOCKER | 16 |
| PENDING OWNER DECISION | 72 |
| PARTIALLY REMEDIATED | 50 |
| NOT RUN | 39 |
| NOT VERIFIED | 26 |
| PENDING HUMAN REVIEW | 22 |
| DEFERRED — POST SUBMISSION | 114 |
| CLOSED — VERIFIED | 52 |

| Category | Name | Active | Closed |
|---|---|---|---|
| A | Global knowledge and compensation evidence | 54 | 6 |
| B | Retrieval and RAG | 27 | 4 |
| C | AI quality evaluation | 19 | 2 |
| D | Candidate AI grounding policies | 16 | 5 |
| E | Speech and voice | 26 | 0 |
| F | Privacy and data rights | 21 | 1 |
| G | Admin UX | 21 | 9 |
| H | Operations and infrastructure | 40 | 5 |
| I | Commercial and billing | 34 | 1 |
| J | External integrations | 17 | 0 |
| K | Legal and governance | 16 | 1 |
| L | Human validation | 13 | 0 |
| M | Technical debt and documentation consistency | 25 | 15 |
| N | Candidate journey and submission consistency | 13 | 3 |

Categories A to M follow the owner's minimum inventory of 2026-10-19; N (candidate journey and submission consistency) was added for journey findings and requalification findings that fit none of them.

## 2. Items that bear on the academic submission

| ID | Original | Title | Status | Blocks submission | Owner decision |
|---|---|---|---|---|---|
| DI-A-015 | BL-11 | Satisfy the 95% product-coverage gate (392 of 412) | OPEN — PRE-SUBMISSION QUALIFICATION | UNKNOWN | REQUIRED: whether the academic submission may proceed with the 95% product-coverage gate BELOW_GATE (the gate is not passed and no exception is granted by engi… |
| DI-H-045 | IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | PENDING OWNER DECISION | UNKNOWN | REQUIRED: ask the course lead; decide hosted versus local demonstration |
| DI-L-001 | BL-19 | P10F targeted human validation | DEFERRED — POST SUBMISSION | UNKNOWN | Open owner decision on AC-24 scope |
| DI-L-002 | P2-01 | Human revalidation: Sharing and revocation discoverability | PENDING HUMAN REVIEW | UNKNOWN | None recorded |
| DI-L-003 | P2-02 | Human revalidation: Source-backed experience in a representative knowledge environment | PENDING HUMAN REVIEW | UNKNOWN | None recorded |
| DI-L-004 | P2-03 | Human revalidation: Answer score interpretation | PENDING HUMAN REVIEW | UNKNOWN | None recorded |
| DI-L-005 | P2-04 | Human revalidation: AI-generated vs sourced vs verified provenance clarity | PENDING HUMAN REVIEW | UNKNOWN | None recorded |
| DI-L-008 | L-AC24 | AC-24 Pilot and lessons remains PARTIAL | OPEN — PRE-SUBMISSION QUALIFICATION | UNKNOWN | REQUIRED: separate approval to create RC-P10-004; decision on AC-24 closure without P10F. |
| DI-L-013 | L-PRODQ | Production-quality human evaluation overall | PENDING HUMAN REVIEW | UNKNOWN | None recorded |
| DI-N-008 | IR-AC-LEDGER | Acceptance criteria dispositions are P9-era and spread over three documents | OPEN — PRE-SUBMISSION QUALIFICATION | YES | REQUIRED: approve CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md as the single current acceptance record |
| DI-N-011 | IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | PENDING OWNER DECISION | YES | REQUIRED: approve or amend the recorded entry conditions; separate approval to create RC-P10-004 |
| DI-N-012 | IR-AC03-TESTS | AC-03 has no test for two-opportunity context selection, restart persistence or legacy-ro… | PARTIALLY REMEDIATED | UNKNOWN | REQUIRED: accept PARTIAL with the disclosed gap or fund a small test wave |
| DI-N-013 | IR-AC18-RUNLIST | AC-18: no owner-scoped list of recent agent runs; selected-run retrieval evidence not sho… | PARTIALLY REMEDIATED | UNKNOWN | REQUIRED: accept PARTIAL with the disclosed gap or schedule a small feature wave |
| DI-N-014 | IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20) | PENDING OWNER DECISION | YES | REQUIRED: confirm the deadline and time zone |

`UNKNOWN` means the record does not establish it and an owner or course-lead answer is needed; it is never read as NO.

## 3. Production-release blockers

161 active issues block production release (the capstone is an academic engineering qualification, not production approval).

| ID | Original | Title | Status | Severity |
|---|---|---|---|---|
| DI-A-001 | BL-2 | Appoint named human reviewers A, B, C | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-002 | BL-4 | Decide on privileged reviewer endpoints | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-003 | BL-5 | Review and decide the 12 measurement batches | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-004 | BL-6 | Review the five alias proposals individually | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-005 | BL-6.1 | Alias decision: Software Developer to 15-1252 | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-A-006 | BL-6.2 | Alias decision: Human Resources Manager to 11-3121 | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-A-007 | BL-6.3 | Alias decision: Sales Manager to 11-2022 | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-A-008 | BL-6.4 | Alias decision: Accountant to 13-2011 | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-A-009 | BL-6.5 | Alias decision: Financial Analyst to 13-2051 | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-A-010 | BL-6.6 | Data Analyst and Product Manager remain unresolved | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-011 | BL-7 | Resolve Data Analyst / Product Manager evidence gaps | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-012 | BL-8 | Legal review of commercial use of BLS content outside US (RB-LIC-1) | OPEN — PRODUCTION RELEASE BLOCKER | BLOCKER |
| DI-A-013 | BL-9 | Persistent-registry authorisation and promotion of us_soc_2018 and bls_oews | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-015 | BL-11 | Satisfy the 95% product-coverage gate (392 of 412) | OPEN — PRE-SUBMISSION QUALIFICATION | HIGH |
| DI-A-016 | BL-12 | Separate runtime authorisation and deployment review for Compensation V2 | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-022 | BL-18 | Human measurement/alias reviews, appointments, persistent authorisation, licensing cleara… | DEFERRED — POST SUBMISSION | HIGH |
| DI-A-053 | A-K1 | Germany K1 governed compensation set is an engineering draft | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-B-023 | B-SCANNER | Real malware scanner not configured for governed knowledge uploads | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-C-001 | C-INT-HUMAN | Human-rated interview question/answer-evaluation quality | PENDING HUMAN REVIEW | HIGH |
| DI-C-002 | C-KB-HUMAN | Human review of KB model answers (citation support, language, abstention) | PENDING HUMAN REVIEW | HIGH |
| DI-C-003 | C-NATIVE | Native-language review of multilingual model answers | PENDING HUMAN REVIEW | HIGH |
| DI-C-004 | C-CITE | Citation claim-support (faithfulness) review | PENDING HUMAN REVIEW | HIGH |
| DI-D-007 | D-LANG | Localized policy sentences are engineering translations | PENDING HUMAN REVIEW | MEDIUM |
| DI-E-001 | W12.4E-1 | Whisper self-hosted versus hosted decision | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-002 | W12.4E-2 | Hosted Whisper data-processing review | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-003 | W12.4E-3 | Speech hosting architecture | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-004 | W12.4E-4 | Model weights and resource placement | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-005 | W12.4E-5 | CPU/GPU and memory sizing | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-006 | W12.4E-6 | Genuine Whisper execution validation | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-007 | W12.4E-7 | Genuine Kyutai execution validation | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-008 | W12.4E-8 | Kyutai gated model-weight approval | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-009 | W12.4E-9 | Kyutai licence and attribution verification | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-010 | W12.4E-10 | Per-voice licence verification | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-011 | W12.4E-11 | Dutch server-side TTS qualification | DEFERRED — POST SUBMISSION | LOW |
| DI-E-012 | W12.4E-12 | Server-side browser recording client | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-013 | W12.4E-13 | Human speech-quality validation | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-014 | W12.4E-14 | Provider authorization flag activation | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-015 | W12.4E-15 | Production speech operational qualification | DEFERRED — POST SUBMISSION | HIGH |
| DI-E-016 | W12.4E-16 | Browser disclosure legal/privacy review | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-017 | W12.4E-17 | Response-origin authorization hardening | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-018 | W12.4E-18 | Engine timeout and cancellation hardening | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-020 | EX-02 | Realtime voice (C1) live round-trip NOT RUN | NOT RUN | HIGH |
| DI-E-021 | AC-13/AC-23-A | Live browser STT correction burden NOT RUN | NOT RUN | MEDIUM |
| DI-E-022 | AC-23-B | Realtime provider round-trip latency NOT RUN | NOT RUN | MEDIUM |
| DI-E-023 | EX-04 | Human voice-quality review NOT RUN (7-locale speech) | NOT RUN | HIGH |
| DI-E-025 | E-LOCAL-ENGINES | Local engine bindings limited | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-E-026 | E-RATE | Realtime/speech concurrency bounded per process | DEFERRED — POST SUBMISSION | LOW |
| DI-F-001 | W9.8-D1a | Preparation-chat ownership index | PARTIALLY REMEDIATED | MEDIUM |
| DI-F-003 | W9.8-D2 | Consent/legal acceptance version history | PARTIALLY REMEDIATED | MEDIUM |
| DI-F-008 | W9.8-D7 | Original-file export bundle | PENDING OWNER DECISION | MEDIUM |
| DI-F-010 | W9.8-D9 | Audit context allow-list enforcement | PARTIALLY REMEDIATED | MEDIUM |
| DI-F-011 | W9.8-D10 | Additional account-deletion safeguards | PARTIALLY REMEDIATED | MEDIUM |
| DI-F-012 | PRIV-RET | No retention periods for candidate content | PENDING OWNER DECISION | MEDIUM |
| DI-F-016 | PRIV-LANG | Privacy/legal translations unreviewed (8 locales incl. Russian) | PENDING HUMAN REVIEW | MEDIUM |
| DI-F-017 | PRIV-LEGAL | Legal counsel review of Privacy, Terms and policy drafts | PENDING HUMAN REVIEW | HIGH |
| DI-F-018 | PRIV-BACKUP | Backup erasure after account deletion | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-F-019 | PRIV-BILL-RET | Billing data retention and erasure review | PENDING OWNER DECISION | MEDIUM |
| DI-F-020 | PRIV-POLICY01 | Verified-email policy (POLICY-01) | PENDING OWNER DECISION | MEDIUM |
| DI-H-001 | EX-12.1 | EX-12 #1: TLS + HSTS live | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-H-002 | EX-12.2 | EX-12 #2: Automatic cert issuance/renewal | OPEN — PRODUCTION RELEASE BLOCKER | MEDIUM |
| DI-H-003 | EX-12.3 | EX-12 #3: Same-site session cookie | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-H-004 | EX-12.4 | EX-12 #4: CORS allowlist enforced | OPEN — PRODUCTION RELEASE BLOCKER | MEDIUM |
| DI-H-005 | EX-12.5 | EX-12 #5: Readiness gating | NOT RUN | MEDIUM |
| DI-H-006 | EX-12.6 | EX-12 #6: Migration step (single head) | NOT RUN | MEDIUM |
| DI-H-007 | EX-12.7 | EX-12 #7: Backup produces restorable artifacts | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-H-008 | EX-12.8 | EX-12 #8: Restore drill into *_restore DB | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-H-009 | EX-12.9 | EX-12 #9: Rollback | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-H-010 | EX-12.10 | EX-12 #10: Private storage isolation | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-H-011 | EX-12.11 | EX-12 #11: Pause switch (hosted) | NOT RUN | MEDIUM |
| DI-H-012 | EX-12.12 | EX-12 #12: Email verification flow (hosted) | NOT RUN | MEDIUM |
| DI-H-013 | EX-12.13 | EX-12 #13: Malware fail-closed (hosted) | NOT RUN | MEDIUM |
| DI-H-014 | EX-12.14 | EX-12 #14: CSP / mic permissions | NOT RUN | MEDIUM |
| DI-H-015 | EX-12.15 | EX-12 #15: Single-replica limits documented and honoured | PARTIALLY REMEDIATED | MEDIUM |
| DI-H-018 | H-REDIS-LIVE | Live Redis validation | NOT RUN | HIGH |
| DI-H-019 | H-REDIS-POLICY | Redis failure policy per bucket undecided | PENDING OWNER DECISION | MEDIUM |
| DI-H-020 | H-PG-MULTI | Hosted multi-instance PostgreSQL not tested | NOT RUN | HIGH |
| DI-H-021 | H-PG-QUERY | Analytics PostgreSQL query-plan review open | NOT RUN | MEDIUM |
| DI-H-022 | R-96a | PostgreSQL job claim (SKIP LOCKED) not executed live | NOT VERIFIED | MEDIUM |
| DI-H-023 | R-96b | PostgreSQL audit-trigger DDL not executed live | NOT VERIFIED | MEDIUM |
| DI-H-024 | H-PG-SECRETS | managed_secrets PostgreSQL path migration-tested on SQLite only | NOT VERIFIED | LOW |
| DI-H-025 | H-REAPER | Quota reservation reaper not scheduled | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-H-027 | H-KB-INGEST | Knowledge-ingestion security hardening | PARTIALLY REMEDIATED | HIGH |
| DI-H-028 | H-MONITOR | Production monitoring and observability | DEFERRED — POST SUBMISSION | HIGH |
| DI-H-029 | H-BACKUP | Deployment and backup qualification | NOT RUN | HIGH |
| DI-H-030 | H-ENV | Cross-environment configuration | PARTIALLY REMEDIATED | MEDIUM |
| DI-H-031 | H-RESILIENCE | Provider operational resilience live behaviour | PARTIALLY REMEDIATED | MEDIUM |
| DI-H-032 | H-FAILPATH | Remaining failure-path testing | NOT RUN | MEDIUM |
| DI-H-035 | H-CSRF | CSRF posture | DEFERRED — POST SUBMISSION | LOW |
| DI-H-038 | H-MFA | Step-up is password re-authentication, not MFA | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-H-039 | H-WORKER | Governed knowledge and jobs depend on a separate worker | DEFERRED — POST SUBMISSION | LOW |
| DI-H-045 | IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | PENDING OWNER DECISION | HIGH |
| DI-I-001 | F2B1-OD-01 | Legal seller entity | PENDING OWNER DECISION | HIGH |
| DI-I-002 | F2B1-OD-02 | Product classification (automated digital product) | PENDING OWNER DECISION | MEDIUM |
| DI-I-003 | F2B1-OD-03 | Product tax code | PENDING OWNER DECISION | MEDIUM |
| DI-I-004 | F2B1-OD-04 | What Premium includes beyond Basic | PENDING OWNER DECISION | MEDIUM |
| DI-I-005 | F2B1-OD-05 | Premium monthly price | PENDING OWNER DECISION | HIGH |
| DI-I-006 | F2B1-OD-06 | Premium annual price (no annual plan exists) | PENDING OWNER DECISION | MEDIUM |
| DI-I-007 | F2B1-OD-07 | Currency | PENDING OWNER DECISION | MEDIUM |
| DI-I-008 | F2B1-OD-08 | Tax-inclusive presentation | PENDING OWNER DECISION | MEDIUM |
| DI-I-009 | F2B1-OD-09 | Supported customer countries | PENDING OWNER DECISION | MEDIUM |
| DI-I-010 | F2B1-OD-10 | B2B subscriptions | PENDING OWNER DECISION | MEDIUM |
| DI-I-011 | F2B1-OD-11 | Trial policy | PENDING OWNER DECISION | MEDIUM |
| DI-I-012 | F2B1-OD-12 | Failed-payment grace period | PENDING OWNER DECISION | MEDIUM |
| DI-I-013 | F2B1-OD-13 | Cancellation policy | PENDING OWNER DECISION | HIGH |
| DI-I-014 | F2B1-OD-14 | Refund policy | PENDING OWNER DECISION | HIGH |
| DI-I-015 | F2B1-OD-15 | Dispute entitlement policy | PENDING OWNER DECISION | MEDIUM |
| DI-I-016 | F2B1-OD-16 | Billing data retention | PENDING OWNER DECISION | MEDIUM |
| DI-I-017 | I-STRIPE-ACCT | Dedicated Stripe account and Managed Payments eligibility | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-I-018 | I-STRIPE-SANDBOX | Stripe sandbox qualification (F2-B2/F3) | NOT RUN | HIGH |
| DI-I-019 | I-P1P3 | Unverified Stripe provider contracts (P-1..P-3) | NOT VERIFIED | HIGH |
| DI-I-020 | F1-07 | Account deletion cannot cancel a live provider subscription | PARTIALLY REMEDIATED | HIGH |
| DI-I-022 | I-ENT-POLICY | Paid entitlement policy unapproved | PENDING OWNER DECISION | HIGH |
| DI-I-023 | I-GATES | 12 rollout and billing gates all False | DEFERRED — POST SUBMISSION | HIGH |
| DI-I-024 | I-ALLOW | Numerical Basic/Premium allowances not approved | PENDING OWNER DECISION | HIGH |
| DI-I-025 | I-RESET | Quota reset periods not approved | PENDING OWNER DECISION | MEDIUM |
| DI-I-026 | I-FAST | Basic-to-Fast transition not approved | PENDING OWNER DECISION | HIGH |
| DI-I-027 | I-GRANDFATHER | Grandfathering of existing candidates | PENDING OWNER DECISION | MEDIUM |
| DI-I-028 | I-HISTORY-SHARE | Existing-share policy before history activation | PENDING OWNER DECISION | MEDIUM |
| DI-I-029 | I-UG | Ask4Mo UG incorporation and legal dependencies | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-I-030 | I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | PENDING OWNER DECISION | HIGH |
| DI-I-031 | I-D02 | Pricing page vs account page inconsistency (journey D-02) | PARTIALLY REMEDIATED | MEDIUM |
| DI-I-032 | I-REFUND-EXEC | Seller-initiated refund execution and billing alert delivery | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-I-033 | I-SCHED | Reconciliation scheduler and real StripeStateReader | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-I-034 | I-MOCK | Billing is mock only | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-I-035 | I-LIFECYCLE | Stripe subscription lifecycle never exercised against a real provider | NOT RUN | HIGH |
| DI-J-001 | J-BREVO | Brevo live verification | NOT RUN | HIGH |
| DI-J-002 | J-BREVO-HOOK | Brevo delivery/bounce webhooks not implemented | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-J-005 | J-OIDC | Google OIDC live validation and frontend wiring | NOT RUN | MEDIUM |
| DI-J-008 | J-REDIS | Redis integration unverified | NOT RUN | HIGH |
| DI-J-011 | J-OCR | Live OCR quality unvalidated | NOT RUN | MEDIUM |
| DI-J-012 | J-CLAMAV | Real malware scanner not configured | NOT RUN | HIGH |
| DI-J-013 | J-OPENROUTER | OpenRouter live behaviour beyond P10E sample | PARTIALLY REMEDIATED | MEDIUM |
| DI-J-014 | J-SEMANTIC | Semantic live calibration (L-REL-1/L-XLANG-1) NOT RUN | NOT RUN | MEDIUM |
| DI-J-016 | J-INTEG-READY | Production integration readiness | DEFERRED — POST SUBMISSION | MEDIUM |
| DI-J-017 | J-RATE | Provider rate limits and failure handling live | NOT RUN | MEDIUM |
| DI-K-001 | BL-1 | Verify reviewer identities and accounts | DEFERRED — POST SUBMISSION | HIGH |
| DI-K-002 | BL-3 | Complete two-person role changes for appointments | DEFERRED — POST SUBMISSION | HIGH |
| DI-K-003 | D-21 | D-21 name who performs qualified legal review | PENDING OWNER DECISION | HIGH |
| DI-K-004 | K-LIC-ESCO | ESCO data licence not named | PENDING HUMAN REVIEW | MEDIUM |
| DI-K-005 | K-LIC-ISCO | ISCO-08 reuse beyond short excerpts needs ILO permission | PENDING HUMAN REVIEW | MEDIUM |
| DI-K-006 | K-LIC-DE | German Entgeltatlas (no terms) and Destatis (third-party catalogue licence) | PENDING HUMAN REVIEW | MEDIUM |
| DI-K-007 | K-LIC-OGL | Commercial use outside home territory of OGL/Eurostat/INEGI content | PENDING HUMAN REVIEW | MEDIUM |
| DI-K-008 | K-ATTR | Attribution wording decisions | PENDING OWNER DECISION | LOW |
| DI-K-009 | K-HUMANSRC | Human source qualification | DEFERRED — POST SUBMISSION | HIGH |
| DI-K-011 | K-PRIV | Privacy, Terms and AI-transparency pages are engineering drafts | OPEN — PRODUCTION RELEASE BLOCKER | BLOCKER |
| DI-K-012 | K-AIGUID | Legal/privacy review of AI-guidance and source-excerpt wording | PENDING HUMAN REVIEW | MEDIUM |
| DI-K-013 | K-GDPR | No GDPR compliance/certification claim permitted | DEFERRED — POST SUBMISSION | HIGH |
| DI-K-014 | K-TRANS-LEGAL | Engineering translations of legal/privacy/trust text | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-K-015 | K-PROVIDER | Third-party model provider data handling for real candidate data | PENDING OWNER DECISION | HIGH |
| DI-L-001 | BL-19 | P10F targeted human validation | DEFERRED — POST SUBMISSION | HIGH |
| DI-L-002 | P2-01 | Human revalidation: Sharing and revocation discoverability | PENDING HUMAN REVIEW | HIGH |
| DI-L-003 | P2-02 | Human revalidation: Source-backed experience in a representative knowledge environment | PENDING HUMAN REVIEW | UNKNOWN |
| DI-L-004 | P2-03 | Human revalidation: Answer score interpretation | PENDING HUMAN REVIEW | MEDIUM |
| DI-L-005 | P2-04 | Human revalidation: AI-generated vs sourced vs verified provenance clarity | PENDING HUMAN REVIEW | MEDIUM |
| DI-L-008 | L-AC24 | AC-24 Pilot and lessons remains PARTIAL | OPEN — PRE-SUBMISSION QUALIFICATION | HIGH |
| DI-L-010 | L-NATIVE-UI | Human/native translation review of interface and Help (7-8 locales) | OPEN — PRODUCTION RELEASE BLOCKER | HIGH |
| DI-L-013 | L-PRODQ | Production-quality human evaluation overall | PENDING HUMAN REVIEW | HIGH |
| DI-M-017 | A-04 | Step-up only for role changes (journey finding) | PARTIALLY REMEDIATED | MEDIUM |
| DI-M-018 | M-LEDGER | Mo and company-research cost-ledger gap | PENDING OWNER DECISION | MEDIUM |
| DI-M-019 | M-OR-KEY | Shared OpenRouter credential concerns | NOT VERIFIED | MEDIUM |
| DI-M-035 | M-DOC-COVERAGE | Stale committed product-coverage summary (97%) | PARTIALLY REMEDIATED | MEDIUM |

## 4. Pending owner decisions

| ID | Original | Title | Decision required |
|---|---|---|---|
| DI-A-030 | F2B-D22 | D-22 ASHE weekly never annualised; unanswered | D-03, D-22, D-04, D-12, D-13, D-15 |
| DI-A-031 | D-01 | D-01 adopt or amend recovered GKB/C1-C4 specification | D-01 |
| DI-A-032 | D-02 | D-02 adopt ambiguity-state and recency/eligibility policy | D-02 |
| DI-A-033 | D-05 | D-05 padded ISCO identity and plan for 21 legacy rows | D-05 |
| DI-A-034 | D-06 | D-06 baseline manifest freeze (GKB-0) | D-06 (status ambiguous between documents) |
| DI-A-035 | D-07 | D-07 ESCO language releases | D-07 |
| DI-A-038 | D-10 | D-10 FX and PPP sources and methodology | D-10 |
| DI-A-039 | D-11 | D-11 secondary-data qualification criteria | D-11 |
| DI-A-040 | D-14 | D-14 regional-geography classification rule (policy p10c-d/1) | D-14 |
| DI-A-041 | D-16 | D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT) | D-16 |
| DI-A-042 | D-17 | D-17 evidence-state vocabulary adoption | D-17 |
| DI-A-043 | D-18-19 | D-18 / D-19 South America region vocabularies and national classifications | D-18, D-19 |
| DI-A-047 | A-AGG | Five BLS-specific aggregates quarantined | Later policy review |
| DI-B-002 | B-COVEVAL | Decision whether to change coverage evaluator to check data origin/country (F-C… | Owner decision (c) in P10D s12 |
| DI-B-017 | B-EMBED-SEL | Embedding provider and model selection | Choose embedding provider/model |
| DI-B-017 | IR-RAGAS-LIVE-APPROVAL | Live RAGAS evaluation awaits the owner's spending approval and three prerequisi… | REQUIRED: approve the ceiling, the new ledger and the code change; provide the key |
| DI-C-005 | C-PROTO | Reviewer protocols and rating rubric for AI quality | Reviewer appointments, rating protocol |
| DI-C-006 | C-THRESH | Owner thresholds for AI quality | Owner sets thresholds and spend cap before final evaluation (evaluation-plan rule) |
| DI-C-014 | C-USD15 | USD 15 extra ceiling not approved; 15 calls remain | Owner approval to raise limits |
| DI-F-002 | W9.8-D1b | Preparation-chat selective deletion | Prioritisation not recorded |
| DI-F-004 | W9.8-D3 | Bulk memory deletion | Not scheduled; no decision recorded |
| DI-F-005 | W9.8-D4 | Per-version document deletion | Not scheduled |
| DI-F-006 | W9.8-D5 | Auth-session list/revoke UI | Not scheduled |
| DI-F-007 | W9.8-D6 | Feedback list and deletion page | Not scheduled |
| DI-F-008 | W9.8-D7 | Original-file export bundle | Scope decision |
| DI-F-009 | W9.8-D8 | Orphan workspace invitations to a deleted user's email | Not scheduled |
| DI-F-012 | PRIV-RET | No retention periods for candidate content | Retention schedule |
| DI-F-019 | PRIV-BILL-RET | Billing data retention and erasure review | Owner and legal retention decision |
| DI-F-020 | PRIV-POLICY01 | Verified-email policy (POLICY-01) | Policy decision before public launch |
| DI-F-021 | PRIV-SUPPORT-NOTICE | Support data / privacy request response time | Whether to commit to response-time statements |
| DI-G-023 | SJA-04 | Operations Admin partly useful Review/Diagnostics | Whether to add permission or hide the destination |
| DI-H-019 | H-REDIS-POLICY | Redis failure policy per bucket undecided | Failure policy per bucket |
| DI-H-045 | IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | REQUIRED: ask the course lead; decide hosted versus local demonstration |
| DI-I-001 | F2B1-OD-01 | Legal seller entity | Owner decision required |
| DI-I-002 | F2B1-OD-02 | Product classification (automated digital product) | Owner decision required |
| DI-I-003 | F2B1-OD-03 | Product tax code | Owner decision required |
| DI-I-004 | F2B1-OD-04 | What Premium includes beyond Basic | Owner decision required |
| DI-I-005 | F2B1-OD-05 | Premium monthly price | Owner decision required |
| DI-I-006 | F2B1-OD-06 | Premium annual price (no annual plan exists) | Owner decision required |
| DI-I-007 | F2B1-OD-07 | Currency | Owner decision required |
| DI-I-008 | F2B1-OD-08 | Tax-inclusive presentation | Owner decision required |
| DI-I-009 | F2B1-OD-09 | Supported customer countries | Owner decision required |
| DI-I-010 | F2B1-OD-10 | B2B subscriptions | Owner decision required |
| DI-I-011 | F2B1-OD-11 | Trial policy | Owner decision required |
| DI-I-012 | F2B1-OD-12 | Failed-payment grace period | Owner decision required |
| DI-I-013 | F2B1-OD-13 | Cancellation policy | Owner decision required |
| DI-I-014 | F2B1-OD-14 | Refund policy | Owner decision required |
| DI-I-015 | F2B1-OD-15 | Dispute entitlement policy | Owner decision required |
| DI-I-016 | F2B1-OD-16 | Billing data retention | Owner decision required |
| DI-I-022 | I-ENT-POLICY | Paid entitlement policy unapproved | Approve trial/grace/refund/cancel/dispute rules |
| DI-I-024 | I-ALLOW | Numerical Basic/Premium allowances not approved | Owner approval of numbers |
| DI-I-025 | I-RESET | Quota reset periods not approved | Owner approval |
| DI-I-026 | I-FAST | Basic-to-Fast transition not approved | Approve transition and notice |
| DI-I-027 | I-GRANDFATHER | Grandfathering of existing candidates | Decision |
| DI-I-028 | I-HISTORY-SHARE | Existing-share policy before history activation | Decision |
| DI-I-030 | I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | Approve price |
| DI-J-006 | J-OIDC-PWD | OIDC-only users cannot set a password via recovery | Product decision |
| DI-K-003 | D-21 | D-21 name who performs qualified legal review | Owner to name legal reviewer |
| DI-K-008 | K-ATTR | Attribution wording decisions | None recorded |
| DI-K-010 | K-LEGALACC | Legal acceptance of owner policy decisions | None recorded |
| DI-K-015 | K-PROVIDER | Third-party model provider data handling for real candidate data | None recorded |
| DI-M-012 | SJA-01 | AI config: second approver must be a second Platform Admin | Possible future permission review; none made |
| DI-M-013 | SJA-02 | Knowledge Admin cannot retry/cancel failed jobs | Possible future permission review; none made |
| DI-M-014 | SJA-03 | Billing/Security-Privacy admins cannot see queue state | Possible future permission review; none made |
| DI-M-015 | SJA-05 | Knowledge approval has no distinct-actor rule or step-up | REQUIRED: whether knowledge approval and activation need a distinct-actor rule and/or fresh-password step-up (related A-04). Source qualification itself is unaffected: unapproved knowledge still neve… |
| DI-M-016 | IR-REHEARSAL-CALL | One unplanned live agent run during the P11 rehearsal (outside the P10E ledger) | REQUIRED: acknowledge the unplanned call |
| DI-M-018 | M-LEDGER | Mo and company-research cost-ledger gap | Whether Mo/company research must enter ledger before launch |
| DI-M-027 | M-POLICY02 | Evaluation score consistency (POLICY-02) | Decision |
| DI-M-028 | M-LEGACY01 | Legacy Streamlit UI retained (LEGACY-01) | Retirement task |
| DI-N-011 | IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | REQUIRED: approve or amend the recorded entry conditions; separate approval to create RC-P10-004 |
| DI-N-014 | IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-2… | REQUIRED: confirm the deadline and time zone |
| DI-N-016 | IR-DEVDB-STALE | The developer database is 12 Alembic revisions behind the code head | REQUIRED: migrate the developer database or leave it |

## 5. Active issues by category

Each block lists: original reference and source, latest verified status, severity, priority, whether it blocks submission or production, what is partly done, what remains, candidate and security/privacy impact, dependencies, owner decisions and the evidence required for closure.

### Category A: Global knowledge and compensation evidence (54 active)

#### DI-A-001: Appoint named human reviewers A, B, C
- **Original:** `BL-2` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 2; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s4 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P0 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Appoint Measurement Qualification Reviewer (A), Occupation Alias Reviewer (B) and Release Approver (C) and record their acceptance. Appointment table is blank.
- **Partly addressed:** Role requirements and checklist prepared
- **Remains:** Appoint Measurement Qualification Reviewer (A), Occupation Alias Reviewer (B) and Release Approver (C) and record their acceptance. Appointment table is blank.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Authority and governance · **Release impact:** No qualified evidence can exist without reviewers
- **Dependencies:** BL-1; blocks 5,6 · **Owner decisions:** Owner names three people
- **Required for closure:** Filled appointment table plus audited role changes

#### DI-A-002: Decide on privileged reviewer endpoints
- **Original:** `BL-4` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 4; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s5 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Decide whether five reviewer endpoints (read packet, decide/revoke batch, decide/revoke alias) are needed; if so implement behind require_permission(KNOWLEDGE_APPROVE) with step-up, audit and tests. QualificationReviewService has no route today.
- **Partly addressed:** Service layer (validate_batch, decide_batch, revoke_batch, decide_alias, revoke_alias) implemented
- **Remains:** Decide whether five reviewer endpoints (read packet, decide/revoke batch, decide/revoke alias) are needed; if so implement behind require_permission(KNOWLEDGE_APPROVE) with step-up, audit and tests. QualificationReviewService has no route today.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** New privileged surface needs its own security review · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-2, BL-3; blocks 5,6 · **Owner decisions:** Owner decision whether endpoints are authorised and who builds them
- **Required for closure:** Endpoint tests with step-up and audit, or documented decision not to build

#### DI-A-003: Review and decide the 12 measurement batches
- **Original:** `BL-5` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 5; P10C_F2A_CAPSTONE_ENGINEERING_CLOSURE.md s2 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** 12 batches (16,140 engineering_checked CompensationRecordV2 rows, 0 qualified) await Reviewer A decisions using the digest-bound workflow; digests were NOT re-run at closure.
- **Partly addressed:** Batches, review sheet, criteria and methodology (no RSE cutoff) prepared
- **Remains:** 12 batches (16,140 engineering_checked CompensationRecordV2 rows, 0 qualified) await Reviewer A decisions using the digest-bound workflow; digests were NOT re-run at closure.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** 0/16,140 human-qualified; no runtime approval possible
- **Dependencies:** BL-3, BL-4; blocks 9,12 · **Owner decisions:** Reviewer A decisions; POLICY I (methodology, no cutoff) already recorded
- **Required for closure:** Audited batch decisions

#### DI-A-004: Review the five alias proposals individually
- **Original:** `BL-6` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 6; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Five US aliases (3 approve-recommended, 2 conditional) are engineering_checked; none qualified. Decisions must be individual with evidence attestation.
- **Partly addressed:** Review packet with recommendations and caveats
- **Remains:** Five US aliases (3 approve-recommended, 2 conditional) are engineering_checked; none qualified. Decisions must be individual with evidence attestation.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-3, BL-4; blocks 9,12 · **Owner decisions:** Reviewer B decisions
- **Required for closure:** Audited alias decisions

#### DI-A-005: Alias decision: Software Developer to 15-1252
- **Original:** `BL-6.1` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 6; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reviewer recommendation APPROVE_RECOMMENDED. aliases US-scoped, revocable Status engineering_checked, 0 qualified.
- **Partly addressed:** Evidence and caveat text prepared
- **Remains:** Reviewer recommendation APPROVE_RECOMMENDED. aliases US-scoped, revocable Status engineering_checked, 0 qualified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-6 · **Owner decisions:** Reviewer B decision
- **Required for closure:** Not closed

#### DI-A-006: Alias decision: Human Resources Manager to 11-3121
- **Original:** `BL-6.2` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 6; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reviewer recommendation APPROVE_RECOMMENDED.  Status engineering_checked, 0 qualified.
- **Partly addressed:** Evidence and caveat text prepared
- **Remains:** Reviewer recommendation APPROVE_RECOMMENDED.  Status engineering_checked, 0 qualified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-6 · **Owner decisions:** Reviewer B decision
- **Required for closure:** Not closed

#### DI-A-007: Alias decision: Sales Manager to 11-2022
- **Original:** `BL-6.3` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 6; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reviewer recommendation APPROVE_RECOMMENDED.  Status engineering_checked, 0 qualified.
- **Partly addressed:** Evidence and caveat text prepared
- **Remains:** Reviewer recommendation APPROVE_RECOMMENDED.  Status engineering_checked, 0 qualified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-6 · **Owner decisions:** Reviewer B decision
- **Required for closure:** Not closed

#### DI-A-008: Alias decision: Accountant to 13-2011
- **Original:** `BL-6.4` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 6; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reviewer recommendation CONDITIONAL_APPROVAL_RECOMMENDED. answer must carry caveat that figure is Accountants and Auditors combined Status engineering_checked, 0 qualified.
- **Partly addressed:** Evidence and caveat text prepared
- **Remains:** Reviewer recommendation CONDITIONAL_APPROVAL_RECOMMENDED. answer must carry caveat that figure is Accountants and Auditors combined Status engineering_checked, 0 qualified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-6 · **Owner decisions:** Reviewer B decision
- **Required for closure:** Not closed

#### DI-A-009: Alias decision: Financial Analyst to 13-2051
- **Original:** `BL-6.5` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 6; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reviewer recommendation CONDITIONAL_APPROVAL_RECOMMENDED. reviewer decides whether bare title is default reading or needs investment context; else treat as ambiguous Status engineering_checked, 0 qualified.
- **Partly addressed:** Evidence and caveat text prepared
- **Remains:** Reviewer recommendation CONDITIONAL_APPROVAL_RECOMMENDED. reviewer decides whether bare title is default reading or needs investment context; else treat as ambiguous Status engineering_checked, 0 qualified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-6 · **Owner decisions:** Reviewer B decision
- **Required for closure:** Not closed

#### DI-A-010: Data Analyst and Product Manager remain unresolved
- **Original:** `BL-6.6` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 7; P10C_F2A_COVERAGE_GAP_ANALYSIS.md s2; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s9 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Data Analyst (AMBIGUOUS, 6 candidate SOC codes) and Product Manager (INSUFFICIENT_EVIDENCE, 5 candidates): no alias, abstention preserved. Cannot be resolved without an approved occupational-title source or candidate context plus an owner ambiguity policy.
- **Partly addressed:** Safe abstention behaviour implemented
- **Remains:** Data Analyst (AMBIGUOUS, 6 candidate SOC codes) and Product Manager (INSUFFICIENT_EVIDENCE, 5 candidates): no alias, abstention preserved. Cannot be resolved without an approved occupational-title source or candidate context plus an owner ambiguity policy.
- **Candidate impact:** Affects 13 of the 26 insufficient coverage cases (all ambiguous_title) · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-7 · **Owner decisions:** Owner ambiguity policy or new source approval
- **Required for closure:** Not closed

#### DI-A-011: Resolve Data Analyst / Product Manager evidence gaps
- **Original:** `BL-7` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 7; P10C_F2A_COVERAGE_GAP_ANALYSIS.md s4 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Approve an occupational-title source, or adopt candidate-context plus owner ambiguity policy. Package 1 alone cannot reach the 95% gate without it.
- **Partly addressed:** None; forcing a mapping explicitly rejected
- **Remains:** Approve an occupational-title source, or adopt candidate-context plus owner ambiguity policy. Package 1 alone cannot reach the 95% gate without it.
- **Candidate impact:** Needed for any legitimate coverage close of the last case · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** owner policy or new source approval; blocks 11 · **Owner decisions:** Owner policy or approval needed (D-08 related)
- **Required for closure:** Not closed

#### DI-A-012: Legal review of commercial use of BLS content outside US (RB-LIC-1)
- **Original:** `BL-8` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 8; P10C_F2A_Q_EVIDENCE_QUALIFICATION_DECISION_REPORT.md s66; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s11 · **First recorded:** 2026-10-18
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** BLOCKER · **Priority:** P0 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Whether Ask4Mo may store, transform and commercially present BLS OEWS and 2018 SOC content in each non-US market. BLS page says public domain, asks for citation, forbids emblem use, does not address commercial use or territory.
- **Partly addressed:** Facts gathered from BLS pages; engineering ingestion unaffected
- **Remains:** Whether Ask4Mo may store, transform and commercially present BLS OEWS and 2018 SOC content in each non-US market. BLS page says public domain, asks for citation, forbids emblem use, does not address commercial use or territory.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal exposure · **Release impact:** Candidate-facing deployment blocked until written legal opinion (optionally a BLS statement)
- **Dependencies:** none; blocks 9,12 · **Owner decisions:** Owner must obtain qualified legal opinion; D-21 (who performs legal review) unnamed
- **Required for closure:** Written legal opinion on file

#### DI-A-013: Persistent-registry authorisation and promotion of us_soc_2018 and bls_oews
- **Original:** `BL-9` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 9; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s10 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Promote through SourceRegistry only after BL-5, BL-6, BL-8, with a backed-up persistent import. Only the isolated DB has approved_for_ingestion; persistent registry and baseline unchanged.
- **Partly addressed:** Isolated rehearsal done; manifest hashes reproducible
- **Remains:** Promote through SourceRegistry only after BL-5, BL-6, BL-8, with a backed-up persistent import. Only the isolated DB has approved_for_ingestion; persistent registry and baseline unchanged.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-5, BL-6, BL-8; blocks 12 · **Owner decisions:** Owner/authorised admin records approvals
- **Required for closure:** Not closed

#### DI-A-014: Reassess product coverage after qualification steps
- **Original:** `BL-10` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 10 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Re-measure coverage after BL-5/6/7/9; evaluator and 412 cases stay as they are.
- **Partly addressed:** Evaluator extended with source-backed metrics in P10D-R1
- **Remains:** Re-measure coverage after BL-5/6/7/9; evaluator and 412 cases stay as they are.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-5, BL-6, BL-7, BL-9; blocks 11 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-015: Satisfy the 95% product-coverage gate (392 of 412)
- **Original:** `BL-11` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 11; P10C_F2A_COVERAGE_GAP_ANALYSIS.md s3-4 · **First recorded:** 2026-10-18
- **Status:** OPEN — PRE-SUBMISSION QUALIFICATION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Developer-local 386/412 = 93.7% BELOW_GATE (clean checkout 258/412; human-qualified 0/412). Package 1 alone reaches at most 391 (94.9%). Needs Package 2 (396), a projections/OOH package, or one legitimately resolved Data Analyst/Product Manager title (392).
- **Partly addressed:** Coverage measured and reported per profile; guard prevents regression
- **Remains:** Developer-local 386/412 = 93.7% BELOW_GATE (clean checkout 258/412; human-qualified 0/412). Package 1 alone reaches at most 391 (94.9%). Needs Package 2 (396), a projections/OOH package, or one legitimately resolved Data Analyst/Product Manager title (392). Re-measured in the integrated requalification: developer-local 386/412 and clean-checkout 258/412, both BELOW_GATE and reproducible (clean worktree, repeated); COVERAGE GATE - FAIL.
- **Candidate impact:** Candidates see abstention for 26 insufficient cases · **Security/privacy:** None identified · **Release impact:** Any release requiring the gate stays blocked
- **Dependencies:** BL-10 plus Package 2, OOH package or BL-7 · **Owner decisions:** REQUIRED: whether the academic submission may proceed with the 95% product-coverage gate BELOW_GATE (the gate is not passed and no exception is granted by engineering). See INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 7.
- **Required for closure:** Not closed

#### DI-A-016: Separate runtime authorisation and deployment review for Compensation V2
- **Original:** `BL-12` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 12 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Compensation V2 activation, candidate-visible evidence, contextual broader-group presentation and runtime source approval; all 12 gates False, V2 disabled.
- **Partly addressed:** V2 implemented, disabled, gates test-verified False
- **Remains:** Compensation V2 activation, candidate-visible evidence, contextual broader-group presentation and runtime source approval; all 12 gates False, V2 disabled.
- **Candidate impact:** No V2 result reaches candidates · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-5, 6, 8, 9, 11 · **Owner decisions:** Role C release approver; separate runtime decision
- **Required for closure:** Not closed

#### DI-A-017: P10C-F2B United Kingdom (Package 2)
- **Original:** `BL-13` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 13; P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s M · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Package 2 authorization (D-03, D-22, D-04, D-12, D-13, D-15) is unsigned; UK SOC 2020 Vol 1, ASHE Table 14 2025 provisional and guide to tables not acquired; isolated ingestion not started. Preparation merged (PR #187).
- **Partly addressed:** Preparation, manifest, suppression guard and tests done (nothing acquired)
- **Remains:** Package 2 authorization (D-03, D-22, D-04, D-12, D-13, D-15) is unsigned; UK SOC 2020 Vol 1, ASHE Table 14 2025 provisional and guide to tables not acquired; isolated ingestion not started. Preparation merged (PR #187).
- **Candidate impact:** 7 UK compensation cases among the 26 insufficient remain insufficient · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** owner authorization · **Owner decisions:** D-03, D-22, D-04, D-12, D-13, D-15 sign-off blank
- **Required for closure:** Not closed

#### DI-A-018: P10C-F2C ESCO/ISCO
- **Original:** `BL-14` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 14; P10C_F1_ACQUISITION_PACKAGES.md Package 3 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** ESCO language releases (D-07), ISCO-08 reuse, padded-identity rule (D-05), relationship qualification (D-09). ESCO data licence not named; ILO permission needed beyond short excerpts.
- **Partly addressed:** ESCO 1.2.1 and ISCO-08 English available locally; plan_esco_labels read-only
- **Remains:** ESCO language releases (D-07), ISCO-08 reuse, padded-identity rule (D-05), relationship qualification (D-09). ESCO data licence not named; ILO permission needed beyond short excerpts.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal review required (eu_esco, intl_isco08) · **Release impact:** No release effect until activated
- **Dependencies:** owner authorization and legal review · **Owner decisions:** D-05, D-07, D-09, D-21
- **Required for closure:** Not closed

#### DI-A-019: P10C-F2D Germany and EU
- **Original:** `BL-15` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 15; P10C_F1_ACQUISITION_PACKAGES.md Package 4 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Eurostat SES (occupation only at ISCO major group, C3 broad), Entgeltatlas (no terms found), Destatis (licence taken from a third-party catalogue).
- **Partly addressed:** Eurostat terms read (clear)
- **Remains:** Eurostat SES (occupation only at ISCO major group, C3 broad), Entgeltatlas (no terms found), Destatis (licence taken from a third-party catalogue).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** owner authorization · **Owner decisions:** D-04, D-12, D-13
- **Required for closure:** Not closed

#### DI-A-020: P10C-F2E Canada, Mexico, Brazil
- **Original:** `BL-16` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 16; P10C_F1_ACQUISITION_PACKAGES.md Packages 5-6 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** NOC, Job Bank/StatCan, SINCO/INEGI, CBO/IBGE. No official NOC or SINCO crosswalk to ISCO-08; Brazil terms unread; household income never compensation.
- **Partly addressed:** Contracts and importers built on synthetic fixtures (P10C-D)
- **Remains:** NOC, Job Bank/StatCan, SINCO/INEGI, CBO/IBGE. No official NOC or SINCO crosswalk to ISCO-08; Brazil terms unread; household income never compensation.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** owner authorization · **Owner decisions:** D-04, D-12, D-13, D-15
- **Required for closure:** Not closed

#### DI-A-021: P10C-F2F wider South America and ILOSTAT
- **Original:** `BL-17` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 17; P10C_F1_ACQUISITION_PACKAGES.md Package 7 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Eleven markets plus ILOSTAT; Chile CC BY-SA ShareAlike review; most terms unverified; no auto-assigned C3.
- **Partly addressed:** Contracts exist on synthetic fixtures (P10C-E)
- **Remains:** Eleven markets plus ILOSTAT; Chile CC BY-SA ShareAlike review; most terms unverified; no auto-assigned C3.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** owner authorization, D-16, D-18, D-19 · **Owner decisions:** D-16, D-18, D-19
- **Required for closure:** Not closed

#### DI-A-022: Human measurement/alias reviews, appointments, persistent authorisation, licensing clearance, V2 runtime authorisation (umbrella)
- **Original:** `BL-18` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 18 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Umbrella item covering BL-1 to BL-12; RB-LIC-1 open, no reviewer exists, persistent registry unchanged.
- **Partly addressed:** Review packets retained
- **Remains:** Umbrella item covering BL-1 to BL-12; RB-LIC-1 open, no reviewer exists, persistent registry unchanged.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** items 1 to 12 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-023: ASHE Table 14 SOC classification edition unverified
- **Original:** `F2B-ASHE-ED` · **Source:** docs/capstone/p10/P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s C, H · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Page/URL say soc2010; bulletin says SOC 2020 from 2021; 2018 QMI says SOC 2010. Edition must come from the file's own notes before ingestion; not forced to SOC 2020.
- **Partly addressed:** None recorded
- **Remains:** Page/URL say soc2010; bulletin says SOC 2020 from 2021; 2018 QMI says SOC 2010. Edition must come from the file's own notes before ingestion; not forced to SOC 2020.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 (file must be acquired) · **Owner decisions:** D-22
- **Required for closure:** Not closed

#### DI-A-024: ASHE December 2025 correction: exact suppressed cells unverified
- **Original:** `F2B-ASHE-SUPP` · **Source:** docs/capstone/p10/P10C_F2B_ASHE_COMPENSATION_QUALIFICATION.md s4 · **First recorded:** 2026-10-18
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** 19 Dec 2025 notice suppresses annual pay for 3312/331/33 (UK, London, South East, East; Tables 2,3,14,15,20). Cells, symbol and whether annual-pay-incentive is a column are unverified.
- **Partly addressed:** Machine-readable rule record, importer guard and regression tests (tests/test_uk_preparation_p10cf2b.py) enforce missing values
- **Remains:** 19 Dec 2025 notice suppresses annual pay for 3312/331/33 (UK, London, South East, East; Tables 2,3,14,15,20). Cells, symbol and whether annual-pay-incentive is a column are unverified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-025: Revised ASHE 2025 dataset expected Oct/Nov 2026
- **Original:** `F2B-ASHE-REV` · **Source:** docs/capstone/p10/P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s C · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** ONS says revised 2025 data due October or November 2026; owner must decide provisional now versus revised (D-12). Publication status as of 2026-10-19 not checked.
- **Partly addressed:** None recorded
- **Remains:** ONS says revised 2025 data due October or November 2026; owner must decide provisional now versus revised (D-12). Publication status as of 2026-10-19 not checked.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** D-12
- **Required for closure:** Not closed

#### DI-A-026: ASHE guide to tables and Table 14 notes unread
- **Original:** `F2B-ASHE-GUIDE` · **Source:** docs/capstone/p10/P10C_F2B_UK_SOURCE_ACQUISITION.md s5 · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Sheet layout, measures, symbols, full/part-time scope, CV coding and gross-pay definition unverified until files acquired. Precondition J NOT MET.
- **Partly addressed:** None recorded
- **Remains:** Sheet layout, measures, symbols, full/part-time scope, CV coding and gross-pay definition unverified until files acquired. Precondition J NOT MET.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-027: Current UK SOC 2020 file version unverified
- **Original:** `F2B-UKSOC-VER` · **Source:** docs/capstone/p10/P10C_F2B_UK_OCCUPATION_GRAPH.md · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** File name carries 20260827 while page says last updated 5 May 2026; sheet layout and hierarchy expression not verified; UK graph has 0 nodes.
- **Partly addressed:** None recorded
- **Remains:** File name carries 20260827 while page says last updated 5 May 2026; sheet layout and hierarchy expression not verified; UK graph has 0 nodes.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-028: No UK alias evidence assessed
- **Original:** `F2B-UK-ALIAS` · **Source:** docs/capstone/p10/P10C_F2B_UK_OCCUPATION_GRAPH.md · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** US alias proposals do not carry over; UK titles need their own evidence review against UK SOC 2020. Country-scoped alias guard prevents leakage.
- **Partly addressed:** US-alias isolation guard exists
- **Remains:** US alias proposals do not carry over; UK titles need their own evidence review against UK SOC 2020. Country-scoped alias guard prevents leakage.
- **Candidate impact:** UK compensation for common titles stays abstained · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-029: UK V1 reconciliation: 527 ASHE rows, one with no occupation code
- **Original:** `F2B-UK-V1` · **Source:** docs/capstone/p10/P10C_F2B_ASHE_COMPENSATION_QUALIFICATION.md s1 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** V1 reconciliation against official file cannot run before acquisition; row without code must never receive an invented occupation; V1 label UK vs V2 GB.
- **Partly addressed:** Baseline counts recorded read-only (uk_v1_baseline.json)
- **Remains:** V1 reconciliation against official file cannot run before acquisition; row without code must never receive an invented occupation; V1 label UK vs V2 GB.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-030: D-22 ASHE weekly never annualised; unanswered
- **Original:** `F2B-D22` · **Source:** docs/capstone/p10/P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s G, M · **First recorded:** 2026-10-18
- **Status:** PENDING OWNER DECISION · **Severity:** UNKNOWN · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Owner decision D-22 and D-03 unanswered; sign-off table M blank.
- **Partly addressed:** None recorded
- **Remains:** Owner decision D-22 and D-03 unanswered; sign-off table M blank.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-13 · **Owner decisions:** D-03, D-22, D-04, D-12, D-13, D-15
- **Required for closure:** Not closed

#### DI-A-031: D-01 adopt or amend recovered GKB/C1-C4 specification
- **Original:** `D-01` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md s G; P10C_A s17; ASK4MO_MASTER_CAPSTONE_ROADMAP.md s4 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** GKB-0..18 titles and C1-C4 recovered from a 30 Sep 2026 conversation, not the repo; detailed acceptance criteria partially unrecovered; owner_decision null in dossier. Deferrable to runtime activation.
- **Partly addressed:** None recorded
- **Remains:** GKB-0..18 titles and C1-C4 recovered from a 30 Sep 2026 conversation, not the repo; detailed acceptance criteria partially unrecovered; owner_decision null in dossier. Deferrable to runtime activation.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-01
- **Required for closure:** Not closed

#### DI-A-032: D-02 adopt ambiguity-state and recency/eligibility policy
- **Original:** `D-02` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md s G; P10C_A s17; P10C_C s20 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Ambiguity behaviour and precedence recency rules proposed, owner adoption pending.
- **Partly addressed:** None recorded
- **Remains:** Ambiguity behaviour and precedence recency rules proposed, owner adoption pending.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-02
- **Required for closure:** Not closed

#### DI-A-033: D-05 padded ISCO identity and plan for 21 legacy rows
- **Original:** `D-05` · **Source:** docs/capstone/p10/P10C_F1_OWNER_DECISION_APPENDIX.md s1-2 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Not approved by Package 1 record; decide that zero-padded ISCO codes (e.g. 0110) are string identities.
- **Partly addressed:** None recorded
- **Remains:** Not approved by Package 1 record; decide that zero-padded ISCO codes (e.g. 0110) are string identities.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-14 · **Owner decisions:** D-05
- **Required for closure:** Not closed

#### DI-A-034: D-06 baseline manifest freeze (GKB-0)
- **Original:** `D-06` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md s G; ASK4MO_MASTER_CAPSTONE_ROADMAP.md s4 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Listed unrecorded in dossier; roadmap reconciliation notes it resolved only in the sense of assigning P10C/P10D ownership (D-06 resolved).
- **Partly addressed:** None recorded
- **Remains:** Listed unrecorded in dossier; roadmap reconciliation notes it resolved only in the sense of assigning P10C/P10D ownership (D-06 resolved).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-06 (status ambiguous between documents)
- **Required for closure:** Not closed

#### DI-A-035: D-07 ESCO language releases
- **Original:** `D-07` · **Source:** docs/capstone/p10/P10C_F1_OWNER_DECISION_APPENDIX.md · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Approve acquisition of specific ESCO language releases; proposal English only; Russian ESCO availability NOT VERIFIED.
- **Partly addressed:** None recorded
- **Remains:** Approve acquisition of specific ESCO language releases; proposal English only; Russian ESCO availability NOT VERIFIED.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-14 · **Owner decisions:** D-07
- **Required for closure:** Not closed

#### DI-A-036: D-08 who curates aliases
- **Original:** `D-08` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md M.3-M.4 · **First recorded:** 2026-10-18
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Methodology approved (POLICY H) but no reviewer exists; earlier M.3 said D-08 stays open.
- **Partly addressed:** POLICY H alias review methodology approved
- **Remains:** Named reviewers and curators
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-2 · **Owner decisions:** Name curator/reviewer
- **Required for closure:** Not closed

#### DI-A-037: D-09 five-category relationship qualification for crosswalks
- **Original:** `D-09` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md M · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Deferred in Package 1 record; no operational crosswalk relationships; no SOC-to-ISCO equivalence.
- **Partly addressed:** None recorded
- **Remains:** Deferred in Package 1 record; no operational crosswalk relationships; no SOC-to-ISCO equivalence.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-14 · **Owner decisions:** D-09
- **Required for closure:** Not closed

#### DI-A-038: D-10 FX and PPP sources and methodology
- **Original:** `D-10` · **Source:** docs/capstone/p10/P10C_C_COMPENSATION_V2.md s12, s20 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** FxProvider/PppProvider interfaces without implementation; international comparison returns NOT_CONFIGURED; no cross-country comparison.
- **Partly addressed:** None recorded
- **Remains:** FxProvider/PppProvider interfaces without implementation; international comparison returns NOT_CONFIGURED; no cross-country comparison.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-10
- **Required for closure:** Not closed

#### DI-A-039: D-11 secondary-data qualification criteria
- **Original:** `D-11` · **Source:** docs/capstone/p10/P10C_GLOBAL_CAREER_COMPENSATION_EXECUTION_PLAN.md s180; P10C_C s20 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Owner must define what 'authorised reputable secondary evidence' qualifies as; undefined.
- **Partly addressed:** None recorded
- **Remains:** Owner must define what 'authorised reputable secondary evidence' qualifies as; undefined.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-11
- **Required for closure:** Not closed

#### DI-A-040: D-14 regional-geography classification rule (policy p10c-d/1)
- **Original:** `D-14` · **Source:** docs/capstone/p10/P10C_D_CANADA_MEXICO_BRAZIL.md s15 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Proposed precedence policy awaiting adoption.
- **Partly addressed:** None recorded
- **Remains:** Proposed precedence policy awaiting adoption.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-14
- **Required for closure:** Not closed

#### DI-A-041: D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT)
- **Original:** `D-16` · **Source:** docs/capstone/p10/P10C_E_GLOBAL_FALLBACK_AND_COMPARISON.md; docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Open; C3 must not be auto-assigned; ILOSTAT non-operational and unimportable in production until decided.
- **Partly addressed:** None recorded
- **Remains:** Open; C3 must not be auto-assigned; ILOSTAT non-operational and unimportable in production until decided.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-17 · **Owner decisions:** D-16
- **Required for closure:** Not closed

#### DI-A-042: D-17 evidence-state vocabulary adoption
- **Original:** `D-17` · **Source:** docs/capstone/p10/P10C_E_GLOBAL_FALLBACK_AND_COMPARISON.md s15 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Five categorical states and factor list awaiting owner adoption.
- **Partly addressed:** None recorded
- **Remains:** Five categorical states and factor list awaiting owner adoption.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-17
- **Required for closure:** Not closed

#### DI-A-043: D-18 / D-19 South America region vocabularies and national classifications
- **Original:** `D-18-19` · **Source:** docs/capstone/p10/P10C_E_GLOBAL_FALLBACK_AND_COMPARISON.md s15 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Region vocabularies (Paraguay, Peru) and per-market national occupation classification unverified.
- **Partly addressed:** None recorded
- **Remains:** Region vocabularies (Paraguay, Peru) and per-market national occupation classification unverified.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-17 · **Owner decisions:** D-18, D-19
- **Required for closure:** Not closed

#### DI-A-044: D-20 no official SOC/NOC to ISCO-08 crosswalk
- **Original:** `D-20` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md M · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Proposed: use O*NET/ESCO routes only; Package 1 deferred it; O*NET (component 1c) and crosswalks excluded.
- **Partly addressed:** None recorded
- **Remains:** Proposed: use O*NET/ESCO routes only; Package 1 deferred it; O*NET (component 1c) and crosswalks excluded.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-20
- **Required for closure:** Not closed

#### DI-A-045: O*NET crosswalks (Component 1c) deferred
- **Original:** `A-ONET` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md M · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** O*NET 31.0 (CC BY 4.0, attribution text required) and ESCO-to-O*NET-SOC crosswalks not authorised; mapping semantics unread.
- **Partly addressed:** None recorded
- **Remains:** O*NET 31.0 (CC BY 4.0, attribution text required) and ESCO-to-O*NET-SOC crosswalks not authorised; mapping semantics unread.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Component 1c deferred
- **Required for closure:** Not closed

#### DI-A-046: BLS OOH / employment projections package unapproved
- **Original:** `A-OOH` · **Source:** docs/capstone/p10/P10C_F2A_COVERAGE_GAP_ANALYSIS.md s2; docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Excluded from Package 1; would serve up to 12 insufficient cases (education, future growth, outlook, openings); edition UNKNOWN; still gated by Data Analyst/Product Manager.
- **Partly addressed:** None recorded
- **Remains:** Excluded from Package 1; would serve up to 12 insufficient cases (education, future growth, outlook, openings); edition UNKNOWN; still gated by Data Analyst/Product Manager.
- **Candidate impact:** 12 candidate coverage cases · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** D-04, D-12
- **Required for closure:** Not closed

#### DI-A-047: Five BLS-specific aggregates quarantined
- **Original:** `A-AGG` · **Source:** docs/capstone/p10/P10C_F2A_Q_EVIDENCE_QUALIFICATION_DECISION_REPORT.md · **First recorded:** 2026-10-18
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** 21-1018, 25-2052, 25-9045, 51-2028, 53-1047 are not canonical SOC 2018; quarantined (no node, no mapping); later policy review and possible schema extension (migration) undecided.
- **Partly addressed:** Quarantine implemented, V1 reconcile marks them INCOMPATIBLE
- **Remains:** 21-1018, 25-2052, 25-9045, 51-2028, 53-1047 are not canonical SOC 2018; quarantined (no node, no mapping); later policy review and possible schema extension (migration) undecided.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Later policy review
- **Required for closure:** Not closed

#### DI-A-048: Other Package 3-7 items with unverified terms
- **Original:** `A-OPT-CAND` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Entgeltatlas no terms; Destatis third-party catalogue licence; NOC edition 1.0 vs 1.3 unconfirmed and OGL-Canada applicability; Job Bank/StatCan terms; Brazil IBGE/MTE terms unread; INEGI terms clear but SINCO/ENOE edition unknown.
- **Partly addressed:** None recorded
- **Remains:** Entgeltatlas no terms; Destatis third-party catalogue licence; NOC edition 1.0 vs 1.3 unconfirmed and OGL-Canada applicability; Job Bank/StatCan terms; Brazil IBGE/MTE terms unread; INEGI terms clear but SINCO/ENOE edition unknown.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal review required · **Release impact:** No release effect until activated
- **Dependencies:** BL-15, BL-16 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-049: Ten South American markets terms unverified
- **Original:** `A-SA10` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** AR, BO, CO, EC, GY, PY, PE, SR, UY, VE: publisher terms, editions and classifications UNKNOWN; legal review flagged.
- **Partly addressed:** None recorded
- **Remains:** AR, BO, CO, EC, GY, PY, PE, SR, UY, VE: publisher terms, editions and classifications UNKNOWN; legal review flagged.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-17 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-050: Chile INE CC BY-SA ShareAlike review
- **Original:** `A-CL` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** PENDING HUMAN REVIEW · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** ShareAlike obligations on derivatives need legal review before use.
- **Partly addressed:** None recorded
- **Remains:** ShareAlike obligations on derivatives need legal review before use.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal review required · **Release impact:** No release effect until activated
- **Dependencies:** BL-17, D-21 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-051: ILOSTAT site terms and per-indicator terms unread
- **Original:** `A-ILO` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** CC BY 4.0 from 3 May 2023 only; indicators not selected; D-16 open.
- **Partly addressed:** None recorded
- **Remains:** CC BY 4.0 from 3 May 2023 only; indicators not selected; D-16 open.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-17, D-16 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-052: 19 'other' registered sources never researched
- **Original:** `A-OTHER19` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Adzuna, BA Kompetenzkatalog, BERUFENET, Cedefop (5), DigComp, e-CF, EQF, Eurostat vacancy, KldB, NICE, OPM (2), UK Civil Service profiles (2), WEF: licences NOT VERIFIED, no research performed, all NOT_APPROVED.
- **Partly addressed:** None recorded
- **Remains:** Adzuna, BA Kompetenzkatalog, BERUFENET, Cedefop (5), DigComp, e-CF, EQF, Eurostat vacancy, KldB, NICE, OPM (2), UK Civil Service profiles (2), WEF: licences NOT VERIFIED, no research performed, all NOT_APPROVED.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-A-053: Germany K1 governed compensation set is an engineering draft
- **Original:** `A-K1` · **Source:** docs/capstone/p9_quality_register.md; p6_e6_e7_knowledge_promptlab_learning.md s13 · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Seven occupations EUR 2024, self-declared draft; not Entgeltatlas data; human data/legal review pending (P9 class BPL).
- **Partly addressed:** None recorded
- **Remains:** Seven occupations EUR 2024, self-declared draft; not Entgeltatlas data; human data/legal review pending (P9 class BPL).
- **Candidate impact:** Candidates may see draft figures · **Security/privacy:** None identified · **Release impact:** Public launch blocker per P9 register
- **Dependencies:** UNKNOWN · **Owner decisions:** Subject-matter and legal review of K1/K2 data
- **Required for closure:** Not closed

#### DI-A-054: Governed KB native content is English (+ some German)
- **Original:** `A-NATIVE-KB` · **Source:** docs/capstone/p6_knowledge_current_state_audit.md s42-46 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** UI supports 7-8 languages but KB narrative is mostly English; Russian is not a KB language by design.
- **Partly addressed:** None recorded
- **Remains:** UI supports 7-8 languages but KB narrative is mostly English; Russian is not a KB language by design.
- **Candidate impact:** Non-English questions rely on query translation · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

### Category B: Retrieval and RAG (27 active)

#### DI-B-001: Synthetic vs real source gaps in coverage
- **Original:** `A-COV-SYN` · **Source:** docs/capstone/p10/P10D_R1_CANDIDATE_GROUNDING_AND_COVERAGE.md s4, s7 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Only 120 of 412 cases answered with real, applicable, provenance-complete evidence (29.1%); 3 cases (pc_certifications_110/120, pc_licences_130) were met only by synthetic rows on pre-R1 code (now withheld); mixed-origin source uk_civil_service_success_profiles cannot be attributed row by row.
- **Partly addressed:** Synthetic rows withheld by default; V2 source-backed coverage metric and baseline added
- **Remains:** Real-source qualification; mixed-origin row attribution
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-002: Decision whether to change coverage evaluator to check data origin/country (F-COV-1)
- **Original:** `B-COVEVAL` · **Source:** docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s12; P10D_R1 s4 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Evaluator counts source families, not origin or country; changing it would lower baselines and needs authorisation. A separate V2 metric was added instead.
- **Partly addressed:** Source-backed metric B added; legacy A unchanged
- **Remains:** Evaluator counts source families, not origin or country; changing it would lower baselines and needs authorisation. A separate V2 metric was added instead.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Owner decision (c) in P10D s12
- **Required for closure:** Not closed

#### DI-B-003: Source-backed coverage re-measurement after real qualification (metric C)
- **Original:** `B-COV-REMEAS` · **Source:** docs/capstone/p10/P10D_R1_CANDIDATE_GROUNDING_AND_COVERAGE.md s4, s8 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Metric C human-qualified coverage is 0/412; re-measure after real source qualification.
- **Partly addressed:** None recorded
- **Remains:** Metric C human-qualified coverage is 0/412; re-measure after real source qualification.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** BL-5, BL-6, BL-9 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-004: CI parity of clean-checkout coverage baseline on GitHub
- **Original:** `B-CIPARITY` · **Source:** docs/capstone/p10/P10C_G_GLOBAL_EVALUATION_AND_REGRESSION.md s25; .github/workflows/ci.yml L252 · **First recorded:** 2026-10-18
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** P10C-G stated parity VERIFIED only in a local fresh worktree, NOT VERIFIED on GitHub until first CI run. ci.yml now has the guard step (clean_checkout profile); no document records the CI result.
- **Partly addressed:** None recorded
- **Remains:** P10C-G stated parity VERIFIED only in a local fresh worktree, NOT VERIFIED on GitHub until first CI run. ci.yml now has the guard step (clean_checkout profile); no document records the CI result.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-005: No calibrated relevance floor
- **Original:** `L-REL-1` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-REL-1); docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md s16 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Out-of-scope queries and occupations without role data still receive nearest narrative chunks as evidence. Only floor is similarity<=0; deterministic part addressed in P10D-R1 (grounding, geography, provenance). A calibrated floor needs a semantic embedder run.
- **Partly addressed:** P10D-R1 shared occupation grounding, synthetic withholding, geography guard; capability met 0/5 in P10D
- **Remains:** Calibrated semantic floor; live calibration NOT RUN
- **Candidate impact:** Irrelevant chunks may be cited for unsupported questions (mitigated by R2 citation policy) · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Embedding provider, model and credential (not configured); owner authorisation · **Owner decisions:** Whether to authorise paid embedder run
- **Required for closure:** Not closed

#### DI-B-006: Non-English routing and structured lanes are English-keyword driven
- **Original:** `L-ROUTE-1` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-ROUTE-1); docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md s16 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Router, occupation phrase extraction and structured lanes are English-keyword driven; non-English questions reach structured stores only if the paid query-translation model rewrites them (unmeasured); fall to narrative lane.
- **Partly addressed:** R1 corrected live run showed 14/14 answer-language matches and 2-7 evidence items per language (narrative lane)
- **Remains:** Native review of non-English routing; measure translation-model path
- **Candidate impact:** German/French/Dutch compensation questions may miss structured evidence · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Native reviewers; paid run · **Owner decisions:** W12.4E table target: before integrated requalification (owner schedule)
- **Required for closure:** Not closed

#### DI-B-007: No cross-language semantic retrieval; native-phrasing queries unmeasured
- **Original:** `L-XLANG-1` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-XLANG-1); docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.6 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Offline lexical hash embedder has no cross-language semantics; native-phrasing cross-language retrieval stays open and needs a semantic embedder (paid run not run).
- **Partly addressed:** R1 corrected harness retrieves 2-7 evidence items for supported cases in all six non-English languages (original zero-evidence finding withdrawn as harness defect)
- **Remains:** Semantic embedder measurement of native-phrasing queries
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Embedding provider/model/credential · **Owner decisions:** Authorise embedder run
- **Required for closure:** Not closed

#### DI-B-008: No staleness/publication-date handling in narrative lane
- **Original:** `L-STALE-1` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-STALE-1); docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md s16 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** A conflicting older document is returned beside the current one (year only metadata).
- **Partly addressed:** None recorded
- **Remains:** A conflicting older document is returned beside the current one (year only metadata).
- **Candidate impact:** Possible outdated advice surfaced · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Publication-date policy · **Owner decisions:** Owner (target after P10E)
- **Required for closure:** Not closed

#### DI-B-009: Occupation codes in questions do not resolve
- **Original:** `L-CODE-1` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-CODE-1); docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md s16 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Runtime resolver matches titles and aliases only; an official code (e.g. 15-2051) does not resolve an occupation.
- **Partly addressed:** None recorded
- **Remains:** Runtime resolver matches titles and aliases only; an official code (e.g. 15-2051) does not resolve an occupation.
- **Candidate impact:** Users quoting SOC/ISCO codes get no match · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Resolver extension · **Owner decisions:** Owner (target after P10E)
- **Required for closure:** Not closed

#### DI-B-011: Sidecar .meta.json can override provenance metadata
- **Original:** `L-META-1` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-META-1); docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s7 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Operator-run legacy loaders accept a sidecar that overrides title/source_url; accepted operator-trust limitation, not candidate-reachable.
- **Partly addressed:** None recorded
- **Remains:** Operator-run legacy loaders accept a sidecar that overrides title/source_url; accepted operator-trust limitation, not candidate-reachable.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Operator trust boundary · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-012: No per-file size limit in legacy ingestion loaders
- **Original:** `L-INGEST-SIZE` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-INGEST-SIZE); docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s7 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Governed Admin pipeline has limits; legacy operator loaders do not. Accepted operator-trust limitation.
- **Partly addressed:** None recorded
- **Remains:** Governed Admin pipeline has limits; legacy operator loaders do not. Accepted operator-trust limitation.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Operator trust boundary; resource exhaustion by operator only · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-013: Inflected Russian country names not recognised
- **Original:** `L-RU-INFLECT` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-RU-INFLECT); src/copilot/knowledge/countries.py L31 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Country matched as whole nominative form only; code check shows only 'германия' in src/copilot/knowledge/countries.py, so 'в Германии' selects no geography (fails safe).
- **Partly addressed:** None recorded
- **Remains:** Country matched as whole nominative form only; code check shows only 'германия' in src/copilot/knowledge/countries.py, so 'в Германии' selects no geography (fails safe).
- **Candidate impact:** Russian users get no country-specific evidence unless nominative form used · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-014: Arabic not a supported language
- **Original:** `L-LANG-AR` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-LANG-AR) · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No structured data, router keywords or aliases for Arabic; lexical document matching measured only.
- **Partly addressed:** None recorded
- **Remains:** No structured data, router keywords or aliases for Arabic; lexical document matching measured only.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Policy: Arabic not supported
- **Required for closure:** Not closed

#### DI-B-015: Russian is interface/Mo-conversation only, not a KB language
- **Original:** `L-LANG-RU` · **Source:** docs/capstone/p10/evaluation/P10D_EVALUATION_RESULTS.md (L-LANG-RU); docs/capstone/p10/RC_P10_003_RELEASE_CANDIDATE.md s12 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Russian excluded from KB, ESCO and speech by design; lexical document matching only.
- **Partly addressed:** None recorded
- **Remains:** Russian excluded from KB, ESCO and speech by design; lexical document matching only.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-016: Semantic live calibration NOT RUN
- **Original:** `B-SEMCAL` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s10 · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No embedding provider, model or credential configured; host allowlist refuses other providers; would otherwise report CALIBRATION INCONCLUSIVE.
- **Partly addressed:** None recorded
- **Remains:** No embedding provider, model or credential configured; host allowlist refuses other providers; would otherwise report CALIBRATION INCONCLUSIVE.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Embedding provider, model, credential; guarded path on ledger · **Owner decisions:** Provider/model selection; authorisation
- **Required for closure:** Not closed

#### DI-B-017: Embedding provider and model selection
- **Original:** `B-EMBED-SEL` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s11; docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s12 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Owner decision outstanding; only local-hash-v1 lexical embedder exists (ASCII tokeniser; changing it needs a protected-store reindex).
- **Partly addressed:** None recorded
- **Remains:** Owner decision outstanding; only local-hash-v1 lexical embedder exists (ASCII tokeniser; changing it needs a protected-store reindex).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Choose embedding provider/model
- **Required for closure:** Not closed

#### DI-B-017: Live RAGAS evaluation awaits the owner's spending approval and three prerequisites
- **Original:** `IR-RAGAS-LIVE-APPROVAL` · **Source:** docs/capstone/submission/REVIEW_DAY_READINESS.md · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Prepared, not run: dedicated evaluator key, a NEW ledger with its own ceiling, and admission and pricing of the embeddings endpoint and evaluator model in the guard.
- **Remains:** See RAGAS_LIVE_EVALUATION_PROPOSAL.md.
- **Candidate impact:** a developer running the current code against it would fail or see stale state · **Security/privacy:** none identified · **Release impact:** local development and demonstration
- **Dependencies:** backup first · **Owner decisions:** REQUIRED: approve the ceiling, the new ledger and the code change; provide the key
- **Required for closure:** A bounded two-case run with the stated abort conditions and saved results

#### DI-B-018: Embedding credential and guard coverage absent
- **Original:** `B-EMBED-CRED` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s2, s5 · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No credential configured; embeddings endpoint is refused by the P10E HTTP guard by design.
- **Partly addressed:** None recorded
- **Remains:** No credential configured; embeddings endpoint is refused by the P10E HTTP guard by design.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** B-EMBED-SEL · **Owner decisions:** Provide credential and guard coverage
- **Required for closure:** Not closed

#### DI-B-019: RAGAS evaluator credential absent (RAGAS_EVAL_API_KEY)
- **Original:** `B-RAGAS-CRED` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5; docs/ragas_evaluation_report.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Credential absent; RAGAS judge builds its own client on another host the allowlist refuses.
- **Partly addressed:** None recorded
- **Remains:** Credential absent; RAGAS judge builds its own client on another host the allowlist refuses.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Provide credential
- **Required for closure:** Not closed

#### DI-B-020: Guarded RAGAS judge path on the P10E ledger
- **Original:** `B-RAGAS-GUARD` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5; docs/ragas_evaluation_report.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Paid RAGAS stays blocked until every evaluator call is guarded on the same ledger; estimate ~96 judge calls (24 cases x 4 metrics).
- **Partly addressed:** None recorded
- **Remains:** Paid RAGAS stays blocked until every evaluator call is guarded on the same ledger; estimate ~96 judge calls (24 cases x 4 metrics).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** B-RAGAS-CRED · **Owner decisions:** Authorise paid judge
- **Required for closure:** Not closed

#### DI-B-021: Offline hash embedder ASCII tokeniser
- **Original:** `B-TOKENISER` · **Source:** docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s12; P10D_R1 s7 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Changing tokeniser requires a re-index of the protected store; deferred to P10E (not done).
- **Partly addressed:** None recorded
- **Remains:** Changing tokeniser requires a re-index of the protected store; deferred to P10E (not done).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Protected-store reindex authorisation · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-022: Freshness / supersession policy for sources
- **Original:** `B-FRESH` · **Source:** docs/capstone/p10/P10C_F2A_COMPENSATION_EVIDENCE_QUALIFICATION.md s Evidence qualification · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No automatic replacement of acquired datasets; supersession by later edition (e.g. ASHE revised, OEWS next) is a future owner decision; manifest cadence marked UNKNOWN where undefined.
- **Partly addressed:** None recorded
- **Remains:** No automatic replacement of acquired datasets; supersession by later edition (e.g. ASHE revised, OEWS next) is a future owner decision; manifest cadence marked UNKNOWN where undefined.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-023: Real malware scanner not configured for governed knowledge uploads
- **Original:** `B-SCANNER` · **Source:** docs/capstone/knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md s11; docs/capstone/admin/W10_8_KNOWLEDGE_RAG_ADMINISTRATION.md s13; ASK4MO_MASTER_CAPSTONE_ROADMAP.md s3 · **First recorded:** 2026-10-13
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** FILE_SCAN_PROVIDER unset in dev, so governed uploads fail closed (scan_unavailable); ClamAV not installed; dev fake scanner is not a malware scan. Roadmap lists knowledge ingestion security hardening OPEN.
- **Partly addressed:** None recorded
- **Remains:** FILE_SCAN_PROVIDER unset in dev, so governed uploads fail closed (scan_unavailable); ClamAV not installed; dev fake scanner is not a malware scan. Roadmap lists knowledge ingestion security hardening OPEN.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Uploaded knowledge unscanned in production if scanner unset (fails closed) · **Release impact:** Production needs FILE_SCAN_PROVIDER=clamav with reachable daemon
- **Dependencies:** W12.4B/F operations · **Owner decisions:** Operator configuration
- **Required for closure:** Not closed

#### DI-B-024: Governed knowledge has no snapshot/rollback model; depends on a worker
- **Original:** `B-NOSNAP` · **Source:** docs/capstone/knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md s10 · **First recorded:** 2026-10-13
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Limitation from W12.4A.
- **Partly addressed:** None recorded
- **Remains:** Limitation from W12.4A.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-025: BM25 pure-Python scoring about 22 ms p50 over 14k chunks
- **Original:** `B-BM25` · **Source:** docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s9 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Not optimised; no demonstrated user impact.
- **Partly addressed:** None recorded
- **Remains:** Not optimised; no demonstrated user impact.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-029: Unexplained transient eval_product_coverage failure and macOS exit-134 aborts
- **Original:** `B-RC-TRANSIENT` (also: M-EVAL-FLAKE, M-PS-FLAKE) · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s11.4; docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s10 · **First recorded:** 2026-10-19
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** eval_product_coverage failed once right after the full suite then passed 5 consecutive reruns; earlier ~5 of 40 runs aborted at interpreter exit (recursive_mutex). Causes not captured.
- **Partly addressed:** None recorded
- **Remains:** Not reproduced in the integrated requalification: 10 runs under concurrent CPU load, 5 clean reruns, a full CI-mirror run of all 52 evaluator commands (0 failures) and 3 clean-worktree runs all passed; the one earlier failure and the earlier macOS interpreter-exit aborts remain unexplained (hypothesis, unproven: native Chroma/onnx teardown at interpreter exit under load).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-B-030: Native-phrasing cross-language retrieval remains an offline-measured gap
- **Original:** `IR-RETRIEVAL-DEFERRED` · **Source:** docs/capstone/INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 9 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** L-XLANG-1 is unchanged by the policy waves; it was measured offline in all seven languages.
- **Remains:** L-XLANG-1 is unchanged by the policy waves; it was measured offline in all seven languages.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

### Category C: AI quality evaluation (19 active)

#### DI-C-001: Human-rated interview question/answer-evaluation quality
- **Original:** `C-INT-HUMAN` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s8 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** 7 pre-registered role cases (14 calls) have 13 human metrics all PENDING_HUMAN_REVIEW; deterministic checks (7/7) are coarse proxies, not quality; informational scores 38-61 not thresholded.
- **Partly addressed:** Harness, registered corpus and review_packet.json built; run live
- **Remains:** Human ratings
- **Candidate impact:** Interview feedback quality for candidates unvalidated by humans · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Reviewer appointment, rating protocol · **Owner decisions:** Appoint reviewers; set thresholds
- **Required for closure:** Not closed

#### DI-C-002: Human review of KB model answers (citation support, language, abstention)
- **Original:** `C-KB-HUMAN` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Pending: citation_supports_claim, language_consistency, human half of abstains_when_unsupported. no_cross_country_claim and injection_resistance NOT COMPUTED; 11 evidence cases NOT RUN (no synthesis harness); 9 cases per profile are synthetic with no language tag.
- **Partly addressed:** Structural proxies and rescore.json computed from pinned tags
- **Remains:** Human ratings; synthesis harness for 11 cases
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Reviewers; harness build · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-003: Native-language review of multilingual model answers
- **Original:** `C-NATIVE` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s9, s16.4; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s6 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** 14 R1 answers (7 languages x 2) and 7 policy answers: fluency, tone, question understanding PENDING_HUMAN_REVIEW; language match is a stopword proxy only; localized guidance strings are engineering translations.
- **Partly addressed:** Language match 14/14 and 7/7 by proxy
- **Remains:** 14 R1 answers (7 languages x 2) and 7 policy answers: fluency, tone, question understanding PENDING_HUMAN_REVIEW; language match is a stopword proxy only; localized guidance strings are engineering translations.
- **Candidate impact:** Quality of non-English answers unverified · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Native reviewers for en,de,fr,es,it,pt,nl · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-004: Citation claim-support (faithfulness) review
- **Original:** `C-CITE` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.2 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Citation structure validated (markers resolve) but not whether cited text supports the claim; R2 relevance check is a shared-content-word proxy.
- **Partly addressed:** Provenance and marker validity enforced deterministically
- **Remains:** Citation structure validated (markers resolve) but not whether cited text supports the claim; R2 relevance check is a shared-content-word proxy.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Reviewers, protocol · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-005: Reviewer protocols and rating rubric for AI quality
- **Original:** `C-PROTO` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s11; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s15 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No reviewer appointed; rating protocol and pre-registered multilingual/interview personas beyond 7 roles and 7 languages not defined.
- **Partly addressed:** None recorded
- **Remains:** No reviewer appointed; rating protocol and pre-registered multilingual/interview personas beyond 7 roles and 7 languages not defined.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Reviewer appointments, rating protocol
- **Required for closure:** Not closed

#### DI-C-006: Owner thresholds for AI quality
- **Original:** `C-THRESH` · **Source:** docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s11; docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No acceptance thresholds exist or were invented; model-quality contract (mode C, 20 cases) refuses NOT AUTHORISED (exit 3).
- **Partly addressed:** None recorded
- **Remains:** No acceptance thresholds exist or were invented; model-quality contract (mode C, 20 cases) refuses NOT AUTHORISED (exit 3).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Owner sets thresholds and spend cap before final evaluation (evaluation-plan rule)
- **Required for closure:** Not closed

#### DI-C-007: Model-profile comparison (Fast vs Balanced vs Advanced)
- **Original:** `C-PROFILE` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s6 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** P10E profile figures covered different subsets (15-17 of 22); no profile claimed better. After R1 only Balanced was re-run on all 22 cases; Fast/Advanced not re-run.
- **Partly addressed:** Balanced 22/22 completed after cap fix
- **Remains:** Fast/Advanced on full set; larger samples
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Ledger calls (15 remain of 300) · **Owner decisions:** Authorise more calls
- **Required for closure:** Not closed

#### DI-C-008: Opportunity Pack and analytics narrative model quality
- **Original:** `C-PACK` · **Source:** docs/capstone/ASK4MO_MASTER_CAPSTONE_ROADMAP.md s3 (P2-C, P5-A, P5-B) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Actual model-quality validation NOT TESTED (offline harness only).
- **Partly addressed:** None recorded
- **Remains:** Actual model-quality validation NOT TESTED (offline harness only).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Live authorisation and reviewers · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-009: Small-sample limits of all live AI results
- **Original:** `C-SMALL` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s14; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s6 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** 7 interview cases, 14+7 multilingual calls, 22 agent cases, 4 policy agent cases run once; descriptive only, no statistical claim; consistency across repeats not measured.
- **Partly addressed:** None recorded
- **Remains:** 7 interview cases, 14+7 multilingual calls, 22 agent cases, 4 policy agent cases run once; descriptive only, no statistical claim; consistency across repeats not measured.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-010: Agent tool-selection recall 0.773 (22 cases): 5 misses not itemised
- **Original:** `C-AGENT22` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s6, s16.4 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Original per-case outcomes not persisted; historical figure kept. Per-case evidence now captured; 4 misses identified in targeted re-run; fifth NOT established; full 22-case benchmark not re-run after correction.
- **Partly addressed:** Per-case evidence, terminal_status and strict completion added
- **Remains:** Full re-run; identify fifth miss
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** ~45 calls · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-011: Agent behaviour consistency across repeats
- **Original:** `C-AGENT-REPEAT` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s6; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16.4 · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Only three cases repeated once; four R2 policy cases run once; consistency not measured.
- **Partly addressed:** None recorded
- **Remains:** Only three cases repeated once; four R2 policy cases run once; consistency not measured.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-012: KB model-quality contract (mode C) remains unauthorised in full
- **Original:** `C-MODELCONTRACT` · **Source:** docs/capstone/p10/P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s11; docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s5 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** P10E ran 9 of 20 answer cases per profile; remaining evidence cases and full contract not run.
- **Partly addressed:** 9 answer cases per profile run
- **Remains:** P10E ran 9 of 20 answer cases per profile; remaining evidence cases and full contract not run.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-013: Provider cost reconciliation gaps
- **Original:** `C-COST` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s4; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s11, s16.6; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s7 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Per-request reported cost vs account delta differed 5.5% (P10E) and about 9% (R1 first batch), then matched exactly in the R1 correction; R2 account delta (0.0346) below reported (0.0553). Shared credential with provider-side limit; no P10E-specific key.
- **Partly addressed:** Ledger commits upper bound above all figures
- **Remains:** Attribution unexplained; P10E-specific key not created
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Shared credential cannot be spend-limited locally · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Whether to create P10E-specific key
- **Required for closure:** Not closed

#### DI-C-014: USD 15 extra ceiling not approved; 15 calls remain
- **Original:** `C-USD15` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s7; docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s1 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Ledger 285 of 300 calls, USD 2.11 of 10 committed; USD 15 only a potential ceiling needing separate approval.
- **Partly addressed:** None recorded
- **Remains:** Ledger 285 of 300 calls, USD 2.11 of 10 committed; USD 15 only a potential ceiling needing separate approval.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Owner approval to raise limits
- **Required for closure:** Not closed

#### DI-C-015: Mo response naturalness (P2-08)
- **Original:** `C-NAT-P208` · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-08 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** P06 said responses should sound more human; evaluate output-style changes under controlled regression; no global prompt rewrite without evaluation.
- **Partly addressed:** None recorded
- **Remains:** P06 said responses should sound more human; evaluate output-style changes under controlled regression; no global prompt rewrite without evaluation.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-016: AC-22 live comparative benchmark
- **Original:** `C-AC22` · **Source:** docs/capstone/p9_acceptance_ledger.md AC-22; docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** P9 ledger: deterministic done, live NOT RUN. P10E later ran live agent, KB answer and smoke tests (partial); AC-22 row not updated in later docs.
- **Partly addressed:** P10E live agent benchmark (22 cases Balanced) and KB answer cases
- **Remains:** Comparative live benchmark; ledger row refresh
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-017: K4 live Adzuna validation
- **Original:** `C-K4` · **Source:** docs/capstone/p6_e6_e7_knowledge_promptlab_learning.md s13; p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Contract validated; live calls UNVALIDATED, cost-gated; test skipped without credentials.
- **Partly addressed:** None recorded
- **Remains:** Contract validated; live calls UNVALIDATED, cost-gated; test skipped without credentials.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-018: Live OCR quality sample
- **Original:** `C-OCR` · **Source:** docs/capstone/p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Deterministic fixtures pass; live OCR engine sample not run.
- **Partly addressed:** None recorded
- **Remains:** Deterministic fixtures pass; live OCR engine sample not run.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-C-019: Live Langfuse not validated
- **Original:** `C-LANGFUSE` · **Source:** docs/final_submission_readiness.md s104 · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** No paid RAGAS judge score claimed; live Langfuse not validated.
- **Partly addressed:** None recorded
- **Remains:** No paid RAGAS judge score claimed; live Langfuse not validated.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

### Category D: Candidate AI grounding policies (16 active)

#### DI-D-001: Lexical detection limits
- **Original:** `D-LEX` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.1 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Detection of estimate offers, compensation and external-fact questions is lexical (union of seven languages); unusual phrasing can be missed; unclassifiable text flagged for review not judged.
- **Partly addressed:** None recorded
- **Remains:** Detection of estimate offers, compensation and external-fact questions is lexical (union of seven languages); unusual phrasing can be missed; unclassifiable text flagged for review not judged.
- **Candidate impact:** Rare unsupported estimates could pass · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-002: Sentence-removal precision
- **Original:** `D-SENT` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.1 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Sentence-level removal can drop a useful adjacent clause.
- **Partly addressed:** None recorded
- **Remains:** Sentence-level removal can drop a useful adjacent clause.
- **Candidate impact:** Occasional loss of helpful text · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-003: Nonnumeric unsupported factual claims
- **Original:** `D-NONNUM` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s11.5.2 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** A claim with no figure (e.g. 'unemployment is low') is labelled not removed.
- **Partly addressed:** None recorded
- **Remains:** A claim with no figure (e.g. 'unemployment is low') is labelled not removed.
- **Candidate impact:** Unsupported qualitative claims may remain · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-004: Citation relevance is a shared-content-word proxy
- **Original:** `D-CITE-PROXY` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.2 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Context-friendly by design; will not catch a relevant-looking but unsupportive citation; claim-level faithfulness remains an evaluation concern.
- **Partly addressed:** None recorded
- **Remains:** Context-friendly by design; will not catch a relevant-looking but unsupportive citation; claim-level faithfulness remains an evaluation concern.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** C-CITE human review · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-005: Country-name coverage table
- **Original:** `D-COUNTRY` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s11.5.3 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Context-limitation exception depends on a small table (US,CA,GB,DE,FR,ES,IT,PT,NL in seven languages) and a limit-word list; unlisted country/phrasing treated as plain foreign figure and removed (errs safe).
- **Partly addressed:** None recorded
- **Remains:** Context-limitation exception depends on a small table (US,CA,GB,DE,FR,ES,IT,PT,NL in seven languages) and a limit-word list; unlisted country/phrasing treated as plain foreign figure and removed (errs safe).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-006: Agent figure verification limited to tool results and candidate text
- **Original:** `D-AGENT-TXT` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.3, s11.5.4 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Agent retrieval observation carries source metadata only, so figures can be verified only against tool results or candidate text; guard conservatively removes unverifiable figures (pre-existing design limit).
- **Partly addressed:** None recorded
- **Remains:** Agent retrieval observation carries source metadata only, so figures can be verified only against tool results or candidate text; guard conservatively removes unverifiable figures (pre-existing design limit).
- **Candidate impact:** Valid cited agent figures may be stripped · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-007: Localized policy sentences are engineering translations
- **Original:** `D-LANG` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.5, s11.2 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Guidance, unverified-general and unretrieved-limitation strings (8 locales) pending native review; human-reviewed quality NOT VERIFIED.
- **Partly addressed:** None recorded
- **Remains:** Guidance, unverified-general and unretrieved-limitation strings (8 locales) pending native review; human-reviewed quality NOT VERIFIED.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Native reviewers · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-008: Final corrections not live-validated
- **Original:** `D-NOT-LIVE` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s11.5.1, s11.6 · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Live sample (15 calls) taken BEFORE PR #203 corrections; corrected layer covered only by deterministic tests and replay; 15 calls remain.
- **Partly addressed:** None recorded
- **Remains:** Live sample (15 calls) taken BEFORE PR #203 corrections; corrected layer covered only by deterministic tests and replay; 15 calls remain.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Owner authorises re-sample (15 calls remain) · **Owner decisions:** Whether to re-sample
- **Required for closure:** Not closed

#### DI-D-009: Policy B retrieval decision remains model-driven
- **Original:** `D-POLB` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s8.4 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Only labelling/removal is deterministic; retrieval is steered by prompt; live evidence 4 cases once.
- **Partly addressed:** None recorded
- **Remains:** Only labelling/removal is deterministic; retrieval is steered by prompt; live evidence 4 cases once.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-010: Career-chat sources still list retrieved-but-uncited evidence
- **Original:** `D-SRC-LIST` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s11.5.5 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Only sources whose citation was removed are dropped.
- **Partly addressed:** None recorded
- **Remains:** Only sources whose citation was removed are dropped.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-011: Historical agent miss: prep_plan_request (no tool, no gaps in state)
- **Original:** `D-MISS-PREP` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16 table; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s1B, s6 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Registered expectation BuildPreparationPlan not met in both R1 runs; goal says 'from my gaps' with no gaps; R2 policy: plan requested with no gaps may clarify. Live R2 pol-missing-plan-context judged REVIEW (judge cannot detect requests without question mark).
- **Partly addressed:** Owner policy B allows clarification; deterministic tests for clarifications
- **Remains:** Human appropriateness review; judge fix
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Reviewers · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-012: Historical agent miss: insufficient_evidence (no retrieval)
- **Original:** `D-MISS-INS` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s6; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16.4 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Registered SearchCareerKnowledge expectation missed twice in R1; R2 prompt + policy B: live pol-external-fact-no-evidence retrieved and abstained, COMPLIANT (run once, pre-correction).
- **Partly addressed:** Prompt hard rule; policy contract case COMPLIANT once
- **Remains:** Repeats; post-correction live confirmation
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-013: Historical agent miss: ambiguous_role_hitl (no retrieval, no confirm_role pause)
- **Original:** `D-MISS-AMB` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s1B, s6; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16.4 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** R1 expected SearchCareerKnowledge + confirm_role pause; agent listed meanings itself. Owner policy B treats clarification without tool call as allowed; R2 pol-clarify-ambiguous-occupation COMPLIANT but recorded as clarification without retrieval; the confirm_role HITL pause was not reproduced.
- **Partly addressed:** Clarification exception policy
- **Remains:** Whether HITL pause expected; human appropriateness review
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** Owner decision (R1 16.5): retrieval for general market questions
- **Required for closure:** Not closed

#### DI-D-014: Historical agent miss: practice_handoff_hitl (no approve_practice_handoff pause)
- **Original:** `D-MISS-PRAC` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s1B, s5; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16.4 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Agent asked for missing role and plan first; allowed by policy B clarification exception (deterministic test only; not sampled live in R2).
- **Partly addressed:** Clarification exception test
- **Remains:** Live sample; human review
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-015: Fifth miss behind 0.773 unidentified
- **Original:** `D-MISS-5TH` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16.4 · **First recorded:** 2026-10-19
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** 3 of 5 misses plausibly among re-run cases but NOT established; original per-case outcomes not persisted.
- **Partly addressed:** None recorded
- **Remains:** 3 of 5 misses plausibly among re-run cases but NOT established; original per-case outcomes not persisted.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-D-016: Unsourced-estimate offer in abstentions (flag fired 7/7)
- **Original:** `D-EST-FLAG` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md s16.4; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s2, s6 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** R1 offers_unsourced_estimate fired in all seven unsupported-country cases; policy C removes offers deterministically; live confirmation of corrected layer not run.
- **Partly addressed:** Policy C implemented; replay 6/7 changed, 0 retain offers
- **Remains:** Live re-validation; human review of localized guidance
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

### Category E: Speech and voice (26 active)

#### DI-E-001: Whisper self-hosted versus hosted decision
- **Original:** `W12.4E-1` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 1 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner must choose self-hosted open weights or hosted whisper-1.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Owner must choose self-hosted open weights or hosted whisper-1.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; no hosted transport; WHISPER_API_TRANSPORT_AUTHORIZED stays False until decided
- **Dependencies:** owner decision · **Owner decisions:** Owner decision/authorization needed
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-002: Hosted Whisper data-processing review
- **Original:** `W12.4E-2` (also: W4E-2) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 2 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Third-party data-processing review required before any candidate audio leaves the platform.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Third-party data-processing review required before any candidate audio leaves the platform.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Candidate audio privacy boundary · **Release impact:** Blocks any production use of server-side speech; candidate audio must not leave the platform before review
- **Dependencies:** item 1 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-003: Speech hosting architecture
- **Original:** `W12.4E-3` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 3 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Hosting architecture for server-side speech not decided.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Hosting architecture for server-side speech not decided.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Candidate audio privacy boundary · **Release impact:** Blocks any production use of server-side speech; no persistent candidate audio
- **Dependencies:** item 1 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-004: Model weights and resource placement
- **Original:** `W12.4E-4` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 4 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Where weights live; no automatic downloads.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Where weights live; no automatic downloads.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; MODEL_DOWNLOADS_AUTHORIZED stays False
- **Dependencies:** item 3 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-005: CPU/GPU and memory sizing
- **Original:** `W12.4E-5` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 5 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Resource sizing for both providers must be measured, not assumed.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Resource sizing for both providers must be measured, not assumed.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; measured not assumed
- **Dependencies:** items 3, 4 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-006: Genuine Whisper execution validation
- **Original:** `W12.4E-6` (also: W4E-6) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 6 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Real Whisper model execution on consented non-candidate audio; currently NOT VERIFIED.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Real Whisper model execution on consented non-candidate audio; currently NOT VERIFIED.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; consented non-candidate audio only
- **Dependencies:** items 4, 5, owner authorization · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-007: Genuine Kyutai execution validation
- **Original:** `W12.4E-7` (also: W4E-7) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 7 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Real Kyutai Pocket TTS execution; currently MODEL_EXECUTION_NOT_VERIFIED.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Real Kyutai Pocket TTS execution; currently MODEL_EXECUTION_NOT_VERIFIED.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; no live quality claim before human review
- **Dependencies:** items 4, 5, 8, owner authorization · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-008: Kyutai gated model-weight approval
- **Original:** `W12.4E-8` (also: W4E-8) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 8 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner approval of gated cc-by-4.0 weights terms.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Owner approval of gated cc-by-4.0 weights terms.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; gated cc-by-4.0 terms
- **Dependencies:** owner decision · **Owner decisions:** Owner decision/authorization needed
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-009: Kyutai licence and attribution verification
- **Original:** `W12.4E-9` (also: W4E-9) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 9 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Licence and attribution must be verified and recorded before use.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Licence and attribution must be verified and recorded before use.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; attribution recorded before use
- **Dependencies:** item 8 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-010: Per-voice licence verification
- **Original:** `W12.4E-10` (also: W4E-10) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 10 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Per-voice licences (alba, estelle, juergen, giovanni, rafael, lola) unverified.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Per-voice licences (alba, estelle, juergen, giovanni, rafael, lola) unverified.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; built-in voices only; cloning prohibited
- **Dependencies:** item 8 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-011: Dutch server-side TTS qualification
- **Original:** `W12.4E-11` (also: W4E-11) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 11 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Kyutai README lists Dutch, model card does not; Dutch UNVERIFIED and uses browser path.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Kyutai README lists Dutch, model card does not; Dutch UNVERIFIED and uses browser path.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; Dutch stays UNVERIFIED
- **Dependencies:** item 7 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-012: Server-side browser recording client
- **Original:** `W12.4E-12` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 12 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** MediaRecorder client to /speech/transcriptions not built; untestable until a provider is operational.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** MediaRecorder client to /speech/transcriptions not built; untestable until a provider is operational.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Candidate audio privacy boundary · **Release impact:** Blocks any production use of server-side speech; transient audio only; not built in W12.4E or W12.4F
- **Dependencies:** items 3, 6 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-013: Human speech-quality validation
- **Original:** `W12.4E-13` (also: W4E-13) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 13 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Human review of speech quality; none done.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Human review of speech quality; none done.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; no quality claim without it
- **Dependencies:** items 6, 7 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-014: Provider authorization flag activation
- **Original:** `W12.4E-14` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 14 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Flip of SERVER_SPEECH_PROVIDERS_AUTHORIZED etc. is a reviewed code change; Admin cannot flip it.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Flip of SERVER_SPEECH_PROVIDERS_AUTHORIZED etc. is a reviewed code change; Admin cannot flip it.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; code change after review
- **Dependencies:** items 1 to 13, owner approval · **Owner decisions:** Owner decision/authorization needed
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-015: Production speech operational qualification
- **Original:** `W12.4E-15` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 15 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Operational qualification of speech in production.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Operational qualification of speech in production.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Governance and licensing · **Release impact:** Blocks any production use of server-side speech; not operational until proven
- **Dependencies:** item 14 · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-016: Browser disclosure legal/privacy review
- **Original:** `W12.4E-16` (also: W4E-16) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 16 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Dictation disclosure wording in 8 locales is an engineering translation.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Dictation disclosure wording in 8 locales is an engineering translation.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Candidate audio privacy boundary · **Release impact:** Blocks any production use of server-side speech; wording unreviewed by counsel
- **Dependencies:** legal review · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-017: Response-origin authorization hardening
- **Original:** `W12.4E-17` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 17 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Synthesis authorizes by text, not by reference (known limitation).
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** Synthesis authorizes by text, not by reference (known limitation).
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Authorization-by-text / thread limits are security-relevant · **Release impact:** Blocks any production use of server-side speech; server cannot prove client string is the approved response
- **Dependencies:** none · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-018: Engine timeout and cancellation hardening
- **Original:** `W12.4E-18` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (W12.4E remaining activation work table), item 18 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** A timeout releases the slot but cannot kill a running engine thread; concurrency bounded per process only.
- **Partly addressed:** Offline engineering delivered (adapters, governance, migration 0039_speech_governance, Admin Speech page in W12.4F); constants all False
- **Remains:** A timeout releases the slot but cannot kill a running engine thread; concurrency bounded per process only.
- **Candidate impact:** Server speech inactive; browser speech remains the path · **Security/privacy:** Authorization-by-text / thread limits are security-relevant · **Release impact:** Blocks any production use of server-side speech; known limitation
- **Dependencies:** none · **Owner decisions:** Depends on earlier items
- **Required for closure:** Evidence per item not yet produced; src/speech/policy.py constants False

#### DI-E-019: Russian speech excluded
- **Original:** `E-RU` (also: journey A-07 (speech not built; superseded by W12.4E)) · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md footer; docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md section 6 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Russian is excluded from speech (STT/TTS) while Russian is an interface language; seven-language speech policy unchanged. Whisper supports ru but product ignores it.
- **Partly addressed:** Intentional exclusion enforced in policy.py and Admin (not selectable)
- **Remains:** Any future inclusion needs owner decision, provider qualification and human review
- **Candidate impact:** Russian candidates must type or use browser dictation if available · **Security/privacy:** None identified · **Release impact:** Not a defect; documented scope boundary
- **Dependencies:** None recorded · **Owner decisions:** No decision to include recorded
- **Required for closure:** src/speech/policy.py; frontend russian-speech.spec.ts

#### DI-E-020: Realtime voice (C1) live round-trip NOT RUN
- **Original:** `EX-02` · **Source:** docs/capstone/p9_acceptance_ledger.md EX-02/EX-04/AC-13/AC-23; docs/capstone/p9_voice_measurement.md; docs/capstone/p7_5_c1_realtime_voice.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** C1 realtime architecture delivered and deterministically validated (28 invariants) but no live provider round-trip; WebRTC adapter never made a real call; no authorised realtime key.
- **Partly addressed:** Deterministic PASS with fake adapter; commit-once, barge-in, no-audio-storage proven
- **Remains:** Authorised realtime key and smallest EN+DE live run; real VAD/barge-in timing, reconnect, per-language audio quality, real cost
- **Candidate impact:** Realtime voice cannot be claimed as live · **Security/privacy:** None identified · **Release impact:** Cannot claim live realtime; BPL per P9 register
- **Dependencies:** Owner authorization of paid realtime key (OpenRouter cannot serve realtime) · **Owner decisions:** Authorization to run live
- **Required for closure:** No live evidence

#### DI-E-021: Live browser STT correction burden NOT RUN
- **Original:** `AC-13/AC-23-A` · **Source:** docs/capstone/p9_acceptance_ledger.md EX-02/EX-04/AC-13/AC-23; docs/capstone/p9_voice_measurement.md; docs/capstone/p7_5_c1_realtime_voice.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Correction-burden metric defined but no real Web Speech engine in CI/dev; not simulated. AC-13 and AC-23 PARTIAL.
- **Partly addressed:** EN/DE reference transcript set and deterministic UI latency delivered
- **Remains:** Live correction-burden measurement on real browser STT
- **Candidate impact:** Dictation accuracy unmeasured · **Security/privacy:** None identified · **Release impact:** AC-23 stays PARTIAL
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-E-022: Realtime provider round-trip latency NOT RUN
- **Original:** `AC-23-B` · **Source:** docs/capstone/p9_acceptance_ledger.md EX-02/EX-04/AC-13/AC-23; docs/capstone/p9_voice_measurement.md; docs/capstone/p7_5_c1_realtime_voice.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No authorised realtime key; provider latency unmeasured.
- **Partly addressed:** None recorded
- **Remains:** No authorised realtime key; provider latency unmeasured.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** EX-02 live · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-E-023: Human voice-quality review NOT RUN (7-locale speech)
- **Original:** `EX-04` · **Source:** docs/capstone/p9_acceptance_ledger.md EX-02/EX-04/AC-13/AC-23; docs/capstone/p9_voice_measurement.md; docs/capstone/p7_5_c1_realtime_voice.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** C3 multilingual speech configured and deterministic across 7 languages; no human voice-quality review.
- **Partly addressed:** 7-locale configuration and EN/DE reference set
- **Remains:** Human voice-quality and per-language review
- **Candidate impact:** Voice quality for DE/FR/ES/IT/PT/NL unvalidated · **Security/privacy:** None identified · **Release impact:** BPL per P9 register (live speech/TTS quality)
- **Dependencies:** None recorded · **Owner decisions:** Reviewer appointment
- **Required for closure:** None

#### DI-E-024: Live multilingual Mo/voice quality unvalidated
- **Original:** `E-LIVE-MULTI` · **Source:** docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md R-50; p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Live generated-language and per-language live audio quality unvalidated (R-50 ACCEPTED).
- **Partly addressed:** P10E-R1 ran a corrected 14-case multilingual live corpus (text) 2026-10-19; subjective quality PENDING_HUMAN_REVIEW
- **Remains:** Native/human review; speech portion still not run
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** Human reviewers · **Owner decisions:** None recorded
- **Required for closure:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md section 16 (text only)

#### DI-E-025: Local engine bindings limited
- **Original:** `E-LOCAL-ENGINES` · **Source:** docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md section 15 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Local Whisper supports the faster-whisper loader only; local Kyutai binding intentionally not implemented; genuine execution NOT VERIFIED.
- **Partly addressed:** None recorded
- **Remains:** Local Whisper supports the faster-whisper loader only; local Kyutai binding intentionally not implemented; genuine execution NOT VERIFIED.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** W12.4E items 4-7 · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-E-026: Realtime/speech concurrency bounded per process
- **Original:** `E-RATE` · **Source:** W12_4E section 15; p7_5_c1_realtime_voice.md Known limitations · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Speech concurrency bounded per process, not across replicas; realtime rate limiter single-process.
- **Partly addressed:** None recorded
- **Remains:** Speech concurrency bounded per process, not across replicas; realtime rate limiter single-process.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** Redis live validation (H) · **Owner decisions:** None recorded
- **Required for closure:** None

### Category F: Privacy and data rights (21 active)

#### DI-F-001: Preparation-chat ownership index
- **Original:** `W9.8-D1a` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 1 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** W9.8: no per-user run index, so account deletion found chats only via saved-memory references.
- **Partly addressed:** W10.10 added preparation_runs index (migration 0020), index-before-checkpoint creation, bounded backfill and lazy indexing; account deletion uses the index; PRIV-W9-01 declared CLOSED
- **Remains:** Historical orphan runs referenced by no memory and never opened cannot be found without a full scan (deliberately not done); backfill coverage depends on references
- **Candidate impact:** Old preparation chats may remain after account deletion · **Security/privacy:** Residual personal data in checkpoint store (orphans) · **Release impact:** Stated limit in docs/privacy.md; counsel review needed before public launch
- **Dependencies:** Saver-level bulk purge or full-store maintenance decision · **Owner decisions:** Whether to accept orphan limit or fund store-wide purge
- **Required for closure:** docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md sections 14-20, 46; tests/test_privacy_legal_w10_10.py; privacy.md PRIV-W9-01

#### DI-F-002: Preparation-chat selective deletion
- **Original:** `W9.8-D1b` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 1; frontend/lib/i18n/messages/w98/en.ts line 81 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Candidate cannot list or delete single preparation chats from Data & Privacy; UI copy says removal of a single chat is not available yet. Backend DELETE /agent/runs/{id} exists by id only; no list API.
- **Partly addressed:** Per-id delete route and run index exist (W10.10) but no candidate list/delete UI
- **Remains:** Run list endpoint + UI for selective chat deletion; no owner decision recorded
- **Candidate impact:** Cannot remove one chat selectively · **Security/privacy:** Data minimisation / right to erasure UX · **Release impact:** None recorded
- **Dependencies:** Run index (done) · **Owner decisions:** Prioritisation not recorded
- **Required for closure:** Verified UI string still present

#### DI-F-003: Consent/legal acceptance version history
- **Original:** `W9.8-D2` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 2; docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md sections 21-29 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** W9.8: nothing persisted. W10.10 delivered versioned legal documents and recorded acceptance.
- **Partly addressed:** legal_documents/versions/acceptances tables (0020), candidate and Admin UI, immutable published versions; PRIV-W9-02 CLOSED
- **Remains:** Re-acceptance not enforced; signup/reacceptance sources not wired (only settings); baseline versions have no effective date or hash; no back-fill; legal acceptance is not consent to optional processing
- **Candidate impact:** No forced re-acceptance; historical users show no acceptance recorded · **Security/privacy:** Legal evidence of acceptance incomplete · **Release impact:** Production launch needs owner policy on enforcement and counsel review
- **Dependencies:** None recorded · **Owner decisions:** Enforcement policy and registration flow decision
- **Required for closure:** docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md sections 21-29, 47; docs/privacy.md

#### DI-F-004: Bulk memory deletion
- **Original:** `W9.8-D3` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 3 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** No bulk 'clear all memory' endpoint; per-item delete only.
- **Partly addressed:** None recorded
- **Remains:** Confirmed in code: only DELETE /memory/{memory_id} (src/api/routes/memory.py:120); no bulk route
- **Candidate impact:** Candidates must delete memories one by one · **Security/privacy:** Erasure convenience · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Not scheduled; no decision recorded
- **Required for closure:** grep of router.delete routes

#### DI-F-005: Per-version document deletion
- **Original:** `W9.8-D4` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 4; docs/privacy.md Known limitations · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Replaced document versions are kept until the document is deleted; no per-version delete.
- **Partly addressed:** None recorded
- **Remains:** No per-version delete route found (grep of router.delete routes)
- **Candidate impact:** Old versions of a CV persist until whole document deleted · **Security/privacy:** Retention of superseded personal data · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Not scheduled
- **Required for closure:** docs/privacy.md still lists it

#### DI-F-006: Auth-session list/revoke UI
- **Original:** `W9.8-D5` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 5 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Backend SessionRepository.list_active exists (src/auth_repository.py:618) but no candidate UI to list/revoke own sessions.
- **Partly addressed:** None recorded
- **Remains:** No frontend caller of list_active found; Admin can force logout per user only
- **Candidate impact:** Candidate cannot see or end other devices' sessions · **Security/privacy:** Account security hygiene · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Not scheduled
- **Required for closure:** grep list_active in frontend returned nothing

#### DI-F-007: Feedback list and deletion page
- **Original:** `W9.8-D6` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 6 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Feedback is reset where it was given; no central list/delete page.
- **Partly addressed:** None recorded
- **Remains:** Only DELETE /feedback per target exists (src/api/routes/feedback.py:52)
- **Candidate impact:** No central view of submitted feedback · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Not scheduled
- **Required for closure:** route grep

#### DI-F-008: Original-file export bundle
- **Original:** `W9.8-D7` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 7; docs/privacy.md · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Export excludes original uploaded files and storage keys; asynchronous export and file bundle not implemented.
- **Partly addressed:** JSON export extended in W10.10 with legal acceptances, requests and run index
- **Remains:** Original files not exportable; chat content not exportable
- **Candidate impact:** Access/portability requests incomplete for files and chats · **Security/privacy:** Data-portability completeness (GDPR Art. 20 is a counsel question) · **Release impact:** Counsel must decide whether this is required before public launch
- **Dependencies:** None recorded · **Owner decisions:** Scope decision
- **Required for closure:** docs/privacy.md Known limitations; src/application/data_export.py scope text

#### DI-F-009: Orphan workspace invitations to a deleted user's email
- **Original:** `W9.8-D8` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 8 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Invitations addressed to a deleted user's email are not cleaned up.
- **Partly addressed:** None recorded
- **Remains:** Verified in src/application/account_deletion_service.py lines 174-185: invitations SENT by the user are deleted and accepted_user_id nulled, but invitations addressed TO the deleted email are not touched; no later doc addresses it
- **Candidate impact:** None directly · **Security/privacy:** Residual email address data in invitations · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Not scheduled
- **Required for closure:** account_deletion_service.py lines 174-185

#### DI-F-010: Audit context allow-list enforcement
- **Original:** `W9.8-D9` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 9 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Audit context is not allow-list enforced for all call sites (call-site discipline).
- **Partly addressed:** W10.1 SEC-W10-03: build_audit in src/application/admin_audit.py rejects unknown event names and secret-/content-looking context keys for admin events
- **Remains:** Non-admin audit call sites (candidate and auth events) not shown to use the same builder; no global allow-list
- **Candidate impact:** None directly · **Security/privacy:** Risk of private content in audit context · **Release impact:** None recorded
- **Dependencies:** Audit pipeline review · **Owner decisions:** None recorded
- **Required for closure:** docs/capstone/admin/W10_1_ADMIN_FOUNDATION_COMMAND_CENTER.md section 16

#### DI-F-011: Additional account-deletion safeguards
- **Original:** `W9.8-D10` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 9 item 10 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Deletion has only a confirmation dialog (no re-authentication or cooling-off).
- **Partly addressed:** W12.4D-F1R: subscription-aware closure refuses self-service deletion while a provider subscription is unresolved (409); W9.12 retired orphan delete-request endpoint
- **Remains:** No re-authentication/step-up on candidate deletion; no recovery window
- **Candidate impact:** None directly · **Security/privacy:** Accidental or hijacked-session deletion · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Product/legal policy on re-auth and recovery
- **Required for closure:** docs/capstone/billing/W12_04D_F1R_ACCOUNT_CLOSURE_RECOVERY_RBAC.md; docs/capstone/p10/w9/P10B_W9_12_ENGINEERING_QUALITY.md sections 17-18

#### DI-F-012: No retention periods for candidate content
- **Original:** `PRIV-RET` · **Source:** docs/privacy.md Known limitations; W9.8 section 5 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No fixed retention periods exist; kept until deleted; expired auth sessions/tokens never purged; only operator script removes stale in-progress sessions (30 days, unscheduled).
- **Partly addressed:** Copy states no periods; W10.10 hard-codes no retention
- **Remains:** Retention schedule, auth-row purge job, scheduling of cleanup script
- **Candidate impact:** None directly · **Security/privacy:** Storage limitation principle · **Release impact:** Counsel/owner retention policy needed before launch
- **Dependencies:** None recorded · **Owner decisions:** Retention schedule
- **Required for closure:** docs/privacy.md

#### DI-F-014: No Admin export of candidate data (DSAR)
- **Original:** `PRIV-DSAR` · **Source:** docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md section 10; W10_14 section 45 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** By design no Admin export or download of candidate data; access requests are completed by recording self-service export use.
- **Partly addressed:** Durable privacy-request queue (SEC-W10-04) delivered
- **Remains:** Secure artefact store and operator-side DSAR export not built (would make Admin a content superuser)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Whether any operator export is acceptable
- **Required for closure:** W10.10 section 10

#### DI-F-015: Report differencing across overlapping periods
- **Original:** `PRIV-DIFF` · **Source:** docs/capstone/admin/W10_12_REPORTING_ANALYTICS_AI_ECONOMICS.md section 5 (residual limitation) · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Secondary suppression does not prevent differencing across two overlapping reporting periods.
- **Partly addressed:** None recorded
- **Remains:** Secondary suppression does not prevent differencing across two overlapping reporting periods.
- **Candidate impact:** None directly · **Security/privacy:** Small-cohort re-identification via differencing · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-F-016: Privacy/legal translations unreviewed (8 locales incl. Russian)
- **Original:** `PRIV-LANG` · **Source:** docs/capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md section 11; P10B_RELEASE_ACCEPTANCE_MATRIX.md R-49 · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** All non-English privacy/legal-adjacent copy is an ENGINEERING TRANSLATION; human/legal review required before production reliance.
- **Partly addressed:** Key parity enforced; banners shown
- **Remains:** Native/legal review of privacy, terms, AI-transparency, data-control copy
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** BPL per P9 register
- **Dependencies:** None recorded · **Owner decisions:** Reviewer appointment
- **Required for closure:** No review evidence

#### DI-F-017: Legal counsel review of Privacy, Terms and policy drafts
- **Original:** `PRIV-LEGAL` · **Source:** docs/capstone/p9_quality_register.md; capstone_risk_register.md R-5, R-14 · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Privacy notice, Terms and AI transparency are engineering drafts; no statement of legal compliance; EU hosting and DPAs undecided.
- **Partly addressed:** None recorded
- **Remains:** Privacy notice, Terms and AI transparency are engineering drafts; no statement of legal compliance; EU hosting and DPAs undecided.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Blocker for public launch (BPL)
- **Dependencies:** None recorded · **Owner decisions:** Counsel engagement, EU hosting decision
- **Required for closure:** None

#### DI-F-018: Backup erasure after account deletion
- **Original:** `PRIV-BACKUP` · **Source:** docs/capstone/p9_acceptance_ledger.md EX-01; docs/privacy.md · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Hosted backups are not erased instantly; follow provider retention; EX-01 PARTIAL (backup aging documented).
- **Partly addressed:** None recorded
- **Remains:** Hosted backups are not erased instantly; follow provider retention; EX-01 PARTIAL (backup aging documented).
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** EX-12 hosted deployment · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-F-019: Billing data retention and erasure review
- **Original:** `PRIV-BILL-RET` · **Source:** docs/privacy.md (account deletion and provider subscriptions); billing F2-B1 owner decision register · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Retention of financial records after erasure (anonymised shell with minimum billing references) needs owner/legal review; F1-07.
- **Partly addressed:** None recorded
- **Remains:** Retention of financial records after erasure (anonymised shell with minimum billing references) needs owner/legal review; F1-07.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Owner and legal retention decision
- **Required for closure:** None

#### DI-F-020: Verified-email policy (POLICY-01)
- **Original:** `PRIV-POLICY01` · **Source:** docs/capstone/p10/w9/P10B_W9_12_ENGINEERING_QUALITY.md sections 13-14, 31; R-33 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Sign-in does not require verified email; unverified accounts keep full access. Recommendation B: require for sensitive actions (export, delete, share, invite).
- **Partly addressed:** None recorded
- **Remains:** Sign-in does not require verified email; unverified accounts keep full access. Recommendation B: require for sensitive actions (export, delete, share, invite).
- **Candidate impact:** None directly · **Security/privacy:** Account-abuse and mistyped-email risk · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Policy decision before public launch
- **Required for closure:** tests/test_email_verification_policy.py pins current behaviour

#### DI-F-021: Support data / privacy request response time
- **Original:** `PRIV-SUPPORT-NOTICE` · **Source:** docs/privacy.md; W10.10 section 7 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Privacy requests state no response time and no compliance claim; no SLA exists.
- **Partly addressed:** None recorded
- **Remains:** Privacy requests state no response time and no compliance claim; no SLA exists.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Whether to commit to response-time statements
- **Required for closure:** None

#### DI-F-022: Privacy workflow cross-store atomicity
- **Original:** `W10.10-AUDIT-CTX` · **Source:** docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md sections 15, 33 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Deletion spans SQL and checkpoint store with no cross-store atomicity; failures tracked via purge_failed and retry job.
- **Partly addressed:** purge_failed state and retry job
- **Remains:** No distributed transaction; retries rely on worker
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W10.10

### Category G: Admin UX (21 active)

#### DI-G-002: Developer-facing Review copy
- **Original:** `F-02` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-02); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Review page copy was developer-facing.
- **Partly addressed:** Index page copy rewritten
- **Remains:** Agent Inspector, Knowledge & RAG and Evaluation card notes still technical
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4

#### DI-G-006: Fragmented Audit surfaces
- **Original:** `F-06` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-06); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** /admin/audit is a bare list while filters/export live under Security, Audit.
- **Partly addressed:** Both surfaces kept by design; primary view named and cross-linked; headers humanised
- **Remains:** Single filtered surface not delivered
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 3

#### DI-G-007: Raw timestamps, snake_case headers, long ids
- **Original:** `F-07` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-07); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Raw values in several Admin tables.
- **Partly addressed:** Shared Table humanises headers/dates (Audit, Security, Users sessions, Integrations)
- **Remains:** Custom tables in Billing, Privacy, Support and Reports still show some raw values; long references not truncated
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4

#### DI-G-008: Overview hierarchy
- **Original:** `F-08` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-08); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 13-panel Overview; Security panel after boundary footnote; copy cites raw paths.
- **Partly addressed:** None
- **Remains:** Panel ordering, warning priority and path links unchanged
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (STILL OPEN)

#### DI-G-009: Repeated suppressed metrics
- **Original:** `F-09` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-09); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 15 identical 'Suppressed: small cohort' cards in a small environment.
- **Partly addressed:** None
- **Remains:** Summarise suppressed metrics in one line
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (STILL OPEN)

#### DI-G-011: Refund amount in minor units
- **Original:** `F-11` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-11); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Money entered in cents.
- **Partly addressed:** Live preview ('Equals 7.00 EUR') and clearer hint
- **Remains:** Input intentionally remains minor units
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4

#### DI-G-012: High-risk action styling
- **Original:** `F-12` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-12); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Deactivate, Force logout, Pause, Disable override look like neutral buttons.
- **Partly addressed:** None (confirmation dialogs already clear)
- **Remains:** Stronger visual treatment
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (STILL OPEN)

#### DI-G-015: Raw environment names in Flags page
- **Original:** `F-15` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-15); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 'Not configurable here' list shows raw env-var names.
- **Partly addressed:** None
- **Remains:** Plain-language labels
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (STILL OPEN)

#### DI-G-016: Small inline link targets
- **Original:** `F-16` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-16); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Table links under 24 px.
- **Partly addressed:** Integrations links are 44 px
- **Remains:** Users and other tables unchanged
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4

#### DI-G-017: Providers vs Integrations overlap
- **Original:** `F-17` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (F-17); disposition docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md sections 3-4 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Two overlapping destinations.
- **Partly addressed:** Cross-linked both ways, kept separate
- **Remains:** Pages derive 'configured' from different sources (env booleans vs integration registry); a status could differ; not unified
- **Candidate impact:** Admin only · **Security/privacy:** None identified · **Release impact:** Owner accepted W12.2 with follow-ups 2026-10-13; not a blocker
- **Dependencies:** None recorded · **Owner decisions:** Owner decision 2026-10-13: ACCEPT WITH FOLLOW-UP ITEMS
- **Required for closure:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 3; W12_4F section 24

#### DI-G-018: Candidate header logo/'More' overlap at 390 px
- **Original:** `G-HDR-390` · **Source:** docs/capstone/admin/W12_02_ADMIN_OWNER_WALKTHROUGH.md section 5 (also recorded); docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 · **First recorded:** 2026-10-12
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Candidate header logo overlaps the 'More' control at 390 px; visible on Admin pages too; not Admin-owned.
- **Partly addressed:** None recorded
- **Remains:** Not fixed; recorded as before
- **Candidate impact:** Visible on mobile candidate header · **Security/privacy:** None identified · **Release impact:** LAYOUT-W11-01 fixed a different 768 px overflow
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W12.5 AFTER screenshots (outside Git): (owner's Downloads folder, outside Git)

#### DI-G-019: Automated contrast audit not done
- **Original:** `G-CONTRAST` · **Source:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 6 · **First recorded:** 2026-10-12
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** W12.2 and W12.5 used visual inspection of light/dark only; TD-W9-01 recorded some computed contrast ratios for nav text.
- **Partly addressed:** None recorded
- **Remains:** Run an automated contrast audit (all Admin and candidate surfaces, light/dark)
- **Candidate impact:** Accessibility claim limited · **Security/privacy:** None identified · **Release impact:** No WCAG certification claimed
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-020: Real screen-reader / assistive-technology testing not done
- **Original:** `G-SR` · **Source:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 6; docs/capstone/product/W12_04D_P5_B_PREMIUM_INTEGRATED_ACCEPTANCE.md section 41 · **First recorded:** 2026-10-12
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Keyboard and focus tested in jsdom/browser only; no NVDA/JAWS/VoiceOver run; P5-B 'manual assistive-technology review' NOT TESTED; docs/limitations.md says accessibility needs manual validation.
- **Partly addressed:** None recorded
- **Remains:** Real assistive-technology testing for Admin and candidate surfaces
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** No WCAG certification claimed (R-44)
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-021: Admin walkthrough used dev server and seeded data
- **Original:** `G-WALK-ENV` · **Source:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 9 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** W12.5 walkthrough used a dev server and synthetic database, not a production build with real data.
- **Partly addressed:** None recorded
- **Remains:** Re-run on production build with realistic data
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-022: Residual technical Review/Diagnostics wording
- **Original:** `G-REVIEW-COPY` · **Source:** docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (F-02) · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Agent Inspector, Knowledge & RAG and Evaluation card notes still technical (describing those tools).
- **Partly addressed:** None recorded
- **Remains:** Optional rewrite for Admin owner
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-023: Operations Admin partly useful Review/Diagnostics
- **Original:** `SJA-04` · **Source:** docs/capstone/journeys/SPECIALIST_ADMIN_JOURNEYS.md section 9 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Operations Admin sees Review/Diagnostics via ai.read but lacks knowledge.read, so knowledge diagnostics are unavailable to it.
- **Partly addressed:** None recorded
- **Remains:** Operations Admin sees Review/Diagnostics via ai.read but lacks knowledge.read, so knowledge diagnostics are unavailable to it.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Whether to add permission or hide the destination
- **Required for closure:** None

#### DI-G-024: Support replies in-app only; no attachments or SLA
- **Original:** `SJA-07` · **Source:** SPECIALIST_ADMIN_JOURNEYS.md SJA-07; P10B_RELEASE_ACCEPTANCE_MATRIX.md R-93; W10_3 section 24 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Support replies/notifications in-app only: no email, no attachments, no SLA (R-93 ACCEPTED, post-Capstone).
- **Partly addressed:** None recorded
- **Remains:** Secure support upload primitive, email notifications, SLA
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-025: Admin workspace deactivation and universal operator search not built
- **Original:** `G-WS-DEACT` · **Source:** P10B_RELEASE_ACCEPTANCE_MATRIX.md R-94; W10_14 section 45 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Not claimed; candidate workspace owners can deactivate own workspace; operators search by identifier per domain (R-94 ACCEPTED).
- **Partly addressed:** None recorded
- **Remains:** Not claimed; candidate workspace owners can deactivate own workspace; operators search by identifier per domain (R-94 ACCEPTED).
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-026: Churn rate unavailable in Reports
- **Original:** `G-CHURN` · **Source:** docs/capstone/admin/W10_12_REPORTING_ANALYTICS_AI_ECONOMICS.md section 40 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Only current mock subscription state stored; churn unavailable until cancellation events exist.
- **Partly addressed:** None recorded
- **Remains:** Only current mock subscription state stored; churn unavailable until cancellation events exist.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** Live billing events (I) · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-027: Admin capability matrix PARTIAL rows
- **Original:** `G-CAP-PARTIAL` · **Source:** docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 45; W12_4F_ADMIN_CONFIGURATION_COMPLETENESS.md section 2 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** W10.14 matrix: 13 PARTIAL rows (release/model-profile visibility, workspace deactivation, support attachments/diagnostics, plan pricing, mock refunds without coupons, provider status panel, knowledge ingestion/reindex gaps, job dead-letter, DSAR export); W12.4F restated 13 PARTIAL.
- **Partly addressed:** Several rows advanced by W12.4A-F
- **Remains:** Remaining PARTIAL rows individually tracked in ADMIN_CAPABILITY_MATRIX.md
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-G-029: Owned-run list (A6) and selected-run RAG (A8) review surfaces
- **Original:** `G-A6-A8` · **Source:** docs/capstone/p9_quality_register.md; p9_acceptance_ledger.md AC-18 · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Partial review surfaces (NBL); AC-18 PARTIAL.
- **Partly addressed:** None recorded
- **Remains:** No later closure found Verified in the final reconciliation: A6 (owner-scoped recent-run list) is NOT closed: no GET /agent/runs route and no UI list; the Inspector takes a run id (src/api/routes/agent.py, AgentInspector.tsx).
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

### Category H: Operations and infrastructure (40 active)

#### DI-H-001: EX-12 #1: TLS + HSTS live
- **Original:** `EX-12.1` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** curl -I shows valid cert + HSTS. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-002: EX-12 #2: Automatic cert issuance/renewal
- **Original:** `EX-12.2` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Caddy obtains/renews ACME certs for both hosts. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-003: EX-12 #3: Same-site session cookie
- **Original:** `EX-12.3` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Login sets HttpOnly; Secure; SameSite=Lax; app-to-API calls authenticate. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-004: EX-12 #4: CORS allowlist enforced
- **Original:** `EX-12.4` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Disallowed origin rejected; FRONTEND_ORIGINS origin allowed. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-005: EX-12 #5: Readiness gating
- **Original:** `EX-12.5` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** GET /api/v1/ready returns 503 pre-DB, 200 once ready. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Deploy artifacts, env fail-fast and hosting-readiness evaluator exist; local disposable restart/backup/restore passed (AC-20)
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-006: EX-12 #6: Migration step (single head)
- **Original:** `EX-12.6` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** migrate job runs once, asserts one head; api waits. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Deploy artifacts, env fail-fast and hosting-readiness evaluator exist; local disposable restart/backup/restore passed (AC-20)
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-007: EX-12 #7: Backup produces restorable artifacts
- **Original:** `EX-12.7` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** backup.sh output verified via pg_restore --list / tar -tzf. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Deploy artifacts, env fail-fast and hosting-readiness evaluator exist; local disposable restart/backup/restore passed (AC-20)
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-008: EX-12 #8: Restore drill into *_restore DB
- **Original:** `EX-12.8` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** restore.sh restores and app reaches readiness. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Deploy artifacts, env fail-fast and hosting-readiness evaluator exist; local disposable restart/backup/restore passed (AC-20)
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-009: EX-12 #9: Rollback
- **Original:** `EX-12.9` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** previous image tags redeploy cleanly; forward-fix path exercised. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-010: EX-12 #10: Private storage isolation
- **Original:** `EX-12.10` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** documents not reachable via any public URL / Next.js assets. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-011: EX-12 #11: Pause switch (hosted)
- **Original:** `EX-12.11` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** POST /api/v1/admin/pause/{capability} returns 503 to candidates. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-012: EX-12 #12: Email verification flow (hosted)
- **Original:** `EX-12.12` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Brevo delivers a verification email end-to-end. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-013: EX-12 #13: Malware fail-closed (hosted)
- **Original:** `EX-12.13` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** upload rejected when ClamAV is down under required policy. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-014: EX-12 #14: CSP / mic permissions
- **Original:** `EX-12.14` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** page CSP has no connect-src *; realtime/browser-speech mic works. Cannot be certified from a local build; needs authorized staging deployment.
- **Partly addressed:** Artifacts and evaluator exist; not exercised hosted
- **Remains:** Run against an authorized HTTPS deployment (real domain, managed Postgres)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Hosting readiness not certified (BPL)
- **Dependencies:** Authorized deployment, domain/DNS, owner authorization · **Owner decisions:** Authorization of staging deployment
- **Required for closure:** EX-12 BLOCKED / NOT RUN in p8_hosting_operations.md; P9 acceptance ledger EX-12

#### DI-H-015: EX-12 #15: Single-replica limits documented and honoured
- **Original:** `EX-12.15` · **Source:** docs/capstone/p8_hosting_operations.md section 16 (EX-12 checklist) · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** One api replica; multi-replica blockers tracked (rate limiting, pause, session store, migrations).
- **Partly addressed:** Documented; pause is now durable (W10.11); interview session store is durable; Redis adapter exists (not live)
- **Remains:** Rate-limit store must be shared before scaling out
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** p8_hosting_operations.md section 15

#### DI-H-018: Live Redis validation
- **Original:** `H-REDIS-LIVE` · **Source:** docs/capstone/p10/w9/P10B_W9_12_ENGINEERING_QUALITY.md sections 15-16; ASK4MO_MASTER_CAPSTONE_ROADMAP.md section 3 (NOT TESTED) · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** RedisRateLimiter adapter and Redis cost/quota buckets are fake-client tested only; never run against live Redis; distributed limiting not live (R-46 ACCEPTED).
- **Partly addressed:** Adapter with degrade-to-local, selection logic, fake-client tests, P2-A limiter policy
- **Remains:** Run against live Redis; decide Redis failure policy per bucket; scheduler for reaper
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** Needed before scaling beyond one replica or enabling cost enforcement
- **Dependencies:** Redis instance; owner authorization · **Owner decisions:** Failure policy per bucket (P2-A section 13)
- **Required for closure:** None

#### DI-H-019: Redis failure policy per bucket undecided
- **Original:** `H-REDIS-POLICY` · **Source:** docs/capstone/product/W12_04D_P2_A_AI_COST_PROTECTION.md sections 11, 13 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** During Redis outage under 'local' policy limits may be up to N times the ceiling; production failure policy per bucket undecided.
- **Partly addressed:** None recorded
- **Remains:** During Redis outage under 'local' policy limits may be up to N times the ceiling; production failure policy per bucket undecided.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Failure policy per bucket
- **Required for closure:** None

#### DI-H-020: Hosted multi-instance PostgreSQL not tested
- **Original:** `H-PG-MULTI` · **Source:** docs/capstone/product/W12_04D_P5_B_PREMIUM_INTEGRATED_ACCEPTANCE.md sections 38, 41 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** PostgreSQL exercised on one local throwaway server, not a hosted multi-instance deployment.
- **Partly addressed:** P5-B and P10C-F2A ran isolated PostgreSQL 16 (quota concurrency 8 procs, migration chain, Pack, ingestion); W12.4F ran PG-gated modules (197 passed)
- **Remains:** Hosted multi-instance run, failover, connection pooling, backups
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** EX-12 deployment · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-021: Analytics PostgreSQL query-plan review open
- **Original:** `H-PG-QUERY` · **Source:** docs/capstone/product/W12_04D_P5_B_PREMIUM_INTEGRATED_ACCEPTANCE.md section 11/12 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Analytics overview is four bounded queries measured to 1,000 interviews on SQLite only; PostgreSQL query-plan review still open; 500-interview cap remains.
- **Partly addressed:** None recorded
- **Remains:** Analytics overview is four bounded queries measured to 1,000 interviews on SQLite only; PostgreSQL query-plan review still open; 500-interview cap remains.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-022: PostgreSQL job claim (SKIP LOCKED) not executed live
- **Original:** `R-96a` · **Source:** docs/capstone/admin/W10_9_JOBS_QUEUES_OPERATIONAL_DIAGNOSTICS.md section 36; P10B_RELEASE_ACCEPTANCE_MATRIX.md R-96 · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** test_postgres_two_workers_one_claim is skipped without TEST_POSTGRES_URL; R-96 ACCEPTED.
- **Partly addressed:** Isolated PostgreSQL runs were later set up (P5-B, W12.4F) and tests/test_jobs_w10_9.py is PG-gated, but no document states this specific test executed
- **Remains:** Confirm/execute on disposable PostgreSQL
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-023: PostgreSQL audit-trigger DDL not executed live
- **Original:** `R-96b` · **Source:** W10_14 section 45; W12_02 walkthrough section 7; SECURITY_PRIVACY_ADMIN_JOURNEY.md · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Append-only audit trigger DDL rendered and unit-checked only; not executed against live PostgreSQL.
- **Partly addressed:** None recorded
- **Remains:** Execute on disposable PostgreSQL
- **Candidate impact:** None directly · **Security/privacy:** Audit immutability on production DB unproven · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-024: managed_secrets PostgreSQL path migration-tested on SQLite only
- **Original:** `H-PG-SECRETS` · **Source:** docs/capstone/admin/W12_04B_SECURE_PROVIDER_SECRET_ADMINISTRATION.md section 12 · **First recorded:** 2026-10-14
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** W12.4B managed_secrets PostgreSQL path not exercised.
- **Partly addressed:** Later full migration chain ran on isolated PostgreSQL (P5-B 0034 and F2A head)
- **Remains:** Confirm 0026 on PostgreSQL
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** P5-B section 22 (migration chain on PostgreSQL) - not specific to 0026

#### DI-H-025: Quota reservation reaper not scheduled
- **Original:** `H-REAPER` · **Source:** docs/capstone/product/W12_04D_P4_A_USAGE_QUOTAS.md section 18; P5_B section 38 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** reap_expired job for quota reservations not scheduled; lease heartbeat added.
- **Partly addressed:** None recorded
- **Remains:** reap_expired job for quota reservations not scheduled; lease heartbeat added.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-026: Research-cache evaluator isolation
- **Original:** `H-RESCACHE` · **Source:** docs/capstone/ASK4MO_MASTER_CAPSTONE_ROADMAP.md section 3; RC_P10_003_RELEASE_CANDIDATE.md 19A; P10D D12 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Evaluators and ad-hoc probes wrote the developer research cache (W10.11 incident, RC-QUAL-ENV-01, W12.4C finding); roadmap still lists UNRESOLVED.
- **Partly addressed:** W9.12 test isolation; P10D D12 installs the cache fixture when tests.conftest is imported; eval_rc_p10_003 enforces conftest import for all CI evaluators
- **Remains:** Verified by grep: 25 scripts/eval_*.py do not import tests.conftest (documented as 17 manual/non-CI; others may bootstrap differently - unverified); roadmap row not updated
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** Evaluator bootstrap sweep · **Owner decisions:** None recorded
- **Required for closure:** scripts grep; P10D section 'D12'

#### DI-H-027: Knowledge-ingestion security hardening
- **Original:** `H-KB-INGEST` · **Source:** docs/capstone/ASK4MO_MASTER_CAPSTONE_ROADMAP.md section 3; P10D section 7; W10_8 section 13 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Open per roadmap: legacy loaders have no per-file size limit (L-INGEST-SIZE); sidecar can override provenance (L-META-1); governed uploads fail closed with scan_unavailable without a real scanner; no distinct approver for knowledge approval (SJA-05).
- **Partly addressed:** Governed pipeline: mandatory scan, text-only, injection guard, size limits, approval lifecycle
- **Remains:** Real scanner (ClamAV) deployment, size limits in legacy loaders, sidecar provenance override, distinct-actor and step-up for approval
- **Candidate impact:** None directly · **Security/privacy:** Untrusted document ingestion · **Release impact:** Operator-trust limitations not candidate-reachable
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-028: Production monitoring and observability
- **Original:** `H-MONITOR` · **Source:** docs/capstone/admin/W12_4F_ADMIN_CONFIGURATION_COMPLETENESS.md section 24; W10_14 sections 45-46; docs/observability.md · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No external paging; alerts in-app only; readiness derived not live-polled; Langfuse optional/OFF and never live-validated; no provider health polling; no anomaly detection.
- **Partly addressed:** Command Center, readiness view, security events/alerts, incidents, request ids, safe logging
- **Remains:** External monitoring, paging, dashboards, SLOs, live Langfuse
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** R-95 ACCEPTED
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-029: Deployment and backup qualification
- **Original:** `H-BACKUP` · **Source:** docs/capstone/p9_acceptance_ledger.md AC-20, EX-12 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** backup.sh/restore.sh exist; local disposable restore passed (AC-20); hosted backup, restore drill, rollback never run.
- **Partly addressed:** None recorded
- **Remains:** backup.sh/restore.sh exist; local disposable restore passed (AC-20); hosted backup, restore drill, rollback never run.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** EX-12 deployment · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-030: Cross-environment configuration
- **Original:** `H-ENV` · **Source:** docs/capstone/knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md section 10; W12_04B section 12; W12_04C section 11 · **First recorded:** 2026-10-13
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Operators relying on relative data/ paths with a different cwd must set COPILOT_DATA_DIR; non-secret provider settings (EMAIL_PROVIDER, EMAIL_SENDER, APP_BASE_URL, scanner provider) environment-managed; rotated credentials need API and worker restart; master key has no rotation/versioning tool.
- **Partly addressed:** W12.4A data-root fix; W12.4F readiness and env ownership matrix; 5 s cross-process cache
- **Remains:** Hot reload of cached provider clients, key rotation tooling, hosted env parity check
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W12_4F section 3 ownership matrix

#### DI-H-031: Provider operational resilience live behaviour
- **Original:** `H-RESILIENCE` · **Source:** docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md R-85; CANDIDATE_JOURNEY.md D-07 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Outage matrix (R-85) is deterministic; live provider timeouts, rate limits, 429/5xx behaviour and cost under failure untested; no provider-specific failure copy (D-07).
- **Partly addressed:** W9.1 bounded retry (GET/HEAD only), safe error envelope, P10E guarded live calls with 0 failures in sampled runs
- **Remains:** Live failure-injection and provider rate-limit testing
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-032: Remaining failure-path testing
- **Original:** `H-FAILPATH` · **Source:** P10B_RELEASE_ACCEPTANCE_MATRIX.md R-85, R-96; P5_B section 41 NOT TESTED list · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Failure paths verified deterministically only; PostgreSQL-only, live provider, hosted restart and multi-replica paths untested.
- **Partly addressed:** None recorded
- **Remains:** Failure paths verified deterministically only; PostgreSQL-only, live provider, hosted restart and multi-replica paths untested.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-033: Jobs have no dead-letter state
- **Original:** `A-09` · **Source:** docs/capstone/journeys/PLATFORM_ADMIN_JOURNEY.md A-09; W12_4F section 2 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Failed jobs after retries have no dead-letter state (PARTIAL).
- **Partly addressed:** None recorded
- **Remains:** Confirmed: no dead-letter symbols in src (grep)
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-034: SQLite PRAGMA foreign_keys not enabled
- **Original:** `H-FK` · **Source:** docs/capstone/p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Deletion uses explicit deletes; SQLite FKs off (recommendation only); PostgreSQL cascades.
- **Partly addressed:** None recorded
- **Remains:** Deletion uses explicit deletes; SQLite FKs off (recommendation only); PostgreSQL cascades.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** grep foreign_keys in src found nothing

#### DI-H-035: CSRF posture
- **Original:** `H-CSRF` · **Source:** docs/capstone/p9_quality_register.md; p8_e8 Known limitations · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** SameSite=Lax + OIDC state; no double-submit token.
- **Partly addressed:** None recorded
- **Remains:** SameSite=Lax + OIDC state; no double-submit token.
- **Candidate impact:** None directly · **Security/privacy:** Cross-site risk if cookies change · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-036: Full browser matrix
- **Original:** `H-BROWSER` · **Source:** docs/capstone/p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Only Chromium fully tested; Firefox/WebKit documented.
- **Partly addressed:** None recorded
- **Remains:** Only Chromium fully tested; Firefox/WebKit documented.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-037: Developer DB migration lag / W10.13 dev-DB incident
- **Original:** `H-DEVDB` · **Source:** docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 47; W12_04A section 'One-time developer database lineage reconciliation' · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** W10.13 bare evaluator created empty schema objects in dev DB; original fingerprint not preserved; no restoration; W12.4A noted dev DB revision lag.
- **Partly addressed:** Disclosed permanently; hardening (13 evaluators import tests.conftest); W12.4A-R1 lineage reconciliation
- **Remains:** Original state unrecoverable
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W12.4A R-1 resolution

#### DI-H-038: Step-up is password re-authentication, not MFA
- **Original:** `H-MFA` · **Source:** W12_04B section 12; W10_13 section carry-forward · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No MFA; OIDC-only admin cannot step up and so cannot write credentials; OIDC step-up unvalidated.
- **Partly addressed:** None recorded
- **Remains:** No MFA; OIDC-only admin cannot step up and so cannot write credentials; OIDC step-up unvalidated.
- **Candidate impact:** None directly · **Security/privacy:** Admin authentication strength · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-039: Governed knowledge and jobs depend on a separate worker
- **Original:** `H-WORKER` · **Source:** W12_04A section 10; W12_02 section 4 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No snapshot/rollback model for governed knowledge; worker must run; dev environment shows 'Never'.
- **Partly addressed:** None recorded
- **Remains:** No snapshot/rollback model for governed knowledge; worker must run; dev environment shows 'Never'.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-040: CI test-setup cost
- **Original:** `H-CI-PERF` · **Source:** docs/capstone/engineering/CI_PYTHON_PERFORMANCE_OPTIMIZATION.md line 87 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Largest cost is API-level user creation per test; a shared pre-hashed password fixture not done (would change setup semantics).
- **Partly addressed:** None recorded
- **Remains:** Largest cost is API-level user creation per test; a shared pre-hashed password fixture not done (would change setup semantics).
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-H-044: Normal platform settings beyond pause and two flags are environment-only
- **Original:** `PA-A-08` · **Source:** docs/capstone/journeys/PLATFORM_ADMIN_JOURNEY.md A-08 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Further settings remain environment-managed.
- **Remains:** W12.4F added derived readiness and speech governance; other settings stay environment-only by design.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-H-045: Does local execution satisfy the course deployment expectation?
- **Original:** `IR-DEPLOY-EXPECT` · **Source:** docs/capstone/INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 11 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P0 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** EX-12 (hosted operation) is BLOCKED/NOT RUN; whether the brief requires a hosted deployment is unresolved.
- **Remains:** Unanswered; no deployment was made to resolve it. Listed as checklist item 4 of the missing-information checklist. The brief says 'develop and deploy prototypes' in its Objective but does not make a hosted application an evaluation criterion; unconfirmed.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** REQUIRED: ask the course lead; decide hosted versus local demonstration
- **Required for closure:** Written answer recorded in the P11 handoff

### Category I: Commercial and billing (34 active)

#### DI-I-001: Legal seller entity
- **Original:** `F2B1-OD-01` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by B1); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by B1); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Legal entity (Ask4Mo UG) registration · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-002: Product classification (automated digital product)
- **Original:** `F2B1-OD-02` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by B1); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by B1); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-003: Product tax code
- **Original:** `F2B1-OD-03` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by B1 for the test product); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by B1 for the test product); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-004: What Premium includes beyond Basic
- **Original:** `F2B1-OD-04` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-005: Premium monthly price
- **Original:** `F2B1-OD-05` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3 sandbox test price, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3 sandbox test price, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-006: Premium annual price (no annual plan exists)
- **Original:** `F2B1-OD-06` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-007: Currency
- **Original:** `F2B1-OD-07` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-008: Tax-inclusive presentation
- **Original:** `F2B1-OD-08` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-009: Supported customer countries
- **Original:** `F2B1-OD-09` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-010: B2B subscriptions
- **Original:** `F2B1-OD-10` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-011: Trial policy
- **Original:** `F2B1-OD-11` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-012: Failed-payment grace period
- **Original:** `F2B1-OD-12` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-013: Cancellation policy
- **Original:** `F2B1-OD-13` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-014: Refund policy
- **Original:** `F2B1-OD-14` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-015: Dispute entitlement policy
- **Original:** `F2B1-OD-15` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by F3, PROD); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-016: Billing data retention
- **Original:** `F2B1-OD-16` · **Source:** docs/capstone/billing/W12_04D_F2_B1_STRIPE_SANDBOX_ONBOARDING.md section 5 (owner decision register) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner decision OPEN (needed by PROD and before storing real financial data); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Partly addressed:** Code constants keep billing off; no price seeded; policy runtime_policy() UNAPPROVED
- **Remains:** Owner decision OPEN (needed by PROD and before storing real financial data); EUR 19.99 shown on pricing page is a preview, not an approved price.
- **Candidate impact:** Premium unavailable; no purchase possible · **Security/privacy:** None identified · **Release impact:** Commercial activation blocked
- **Dependencies:** Stripe eligibility · **Owner decisions:** Owner decision required
- **Required for closure:** None

#### DI-I-017: Dedicated Stripe account and Managed Payments eligibility
- **Original:** `I-STRIPE-ACCT` · **Source:** docs/capstone/billing/W12_04D_F1_BILLING_SECURITY_QUALIFICATION.md section 14; F2_A section 15 · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Stripe account, Managed Payments eligibility review and sandbox access all BLOCKED on owner; Russia is a restricted purchase country though Russian is an interface language.
- **Partly addressed:** None recorded
- **Remains:** Stripe account, Managed Payments eligibility review and sandbox access all BLOCKED on owner; Russia is a restricted purchase country though Russian is an interface language.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** No billing possible
- **Dependencies:** None recorded · **Owner decisions:** Owner onboarding
- **Required for closure:** None

#### DI-I-018: Stripe sandbox qualification (F2-B2/F3)
- **Original:** `I-STRIPE-SANDBOX` (also: journey A-06) · **Source:** W12_04D_F1 section 16; F2_B1R section 8 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No Stripe call (even sandbox) ever made; end-to-end sandbox validation (purchase, renewal, failure/recovery, cancel, refund, dispute, replacement, cross-candidate) NOT IMPLEMENTED.
- **Partly addressed:** None recorded
- **Remains:** No Stripe call (even sandbox) ever made; end-to-end sandbox validation (purchase, renewal, failure/recovery, cancel, refund, dispute, replacement, cross-candidate) NOT IMPLEMENTED.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** I-STRIPE-ACCT; PROVIDER_READS_AUTHORIZED flip in reviewed release · **Owner decisions:** Authorization
- **Required for closure:** None

#### DI-I-019: Unverified Stripe provider contracts (P-1..P-3)
- **Original:** `I-P1P3` · **Source:** F1 section (P-1..P-3); F2_A section 17; F2_B1R section 8 · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Checkout URL host for Managed Payments, API version 2026-09-30.endive pin, assumed list/lookup contracts, refund/dispute retrieve, Link/portal URL, invoice_payments availability all PROVIDER VALIDATION REQUIRED.
- **Partly addressed:** None recorded
- **Remains:** Checkout URL host for Managed Payments, API version 2026-09-30.endive pin, assumed list/lookup contracts, refund/dispute retrieve, Link/portal URL, invoice_payments availability all PROVIDER VALIDATION REQUIRED.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-I-020: Account deletion cannot cancel a live provider subscription
- **Original:** `F1-07` · **Source:** docs/capstone/billing/W12_04D_F1_BILLING_SECURITY_QUALIFICATION.md; W12_04D_F1R · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** HIGH activation gate: candidate could keep being billed; remediated in F1R by subscription-aware closure; provider cancellation unverified, legal retention review required.
- **Partly addressed:** F1R: deletion refused (409) until provider subscription resolved; closure request recorded
- **Remains:** Sandbox validation of provider cancellation; privacy/retention policy confirmation
- **Candidate impact:** None directly · **Security/privacy:** Candidate could be charged after deletion · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Legal policy
- **Required for closure:** W12_04D_F1R section 'CODE REMEDIATED; OFFLINE TESTED'

#### DI-I-022: Paid entitlement policy unapproved
- **Original:** `I-ENT-POLICY` · **Source:** W12_04D_D section on Policy and 20 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** runtime_policy() is always UNAPPROVED; no paid entitlement granted or revoked at runtime; approval is a reviewed code change.
- **Partly addressed:** None recorded
- **Remains:** runtime_policy() is always UNAPPROVED; no paid entitlement granted or revoked at runtime; approval is a reviewed code change.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Approve trial/grace/refund/cancel/dispute rules
- **Required for closure:** None

#### DI-I-023: 12 rollout and billing gates all False
- **Original:** `I-GATES` · **Source:** docs/capstone/product/W12_04D_P5_B_PREMIUM_INTEGRATED_ACCEPTANCE.md sections 27-28, 39 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** LIVE_BILLING_ENABLED, EXTERNAL_CHECKOUT_AUTHORIZED, STRIPE_WEBHOOK_AUTHORIZED, RECONCILE_SCHEDULER_ENABLED, PAID_ENTITLEMENT_POLICY_APPROVED, PROVIDER_READS_AUTHORIZED, AI_COST_LIMITS_ENFORCED, HISTORY_RESTRICTIONS_ENFORCED, MODEL_PROFILE_ENFORCED etc.; enabling each is a reviewed change.
- **Partly addressed:** None recorded
- **Remains:** LIVE_BILLING_ENABLED, EXTERNAL_CHECKOUT_AUTHORIZED, STRIPE_WEBHOOK_AUTHORIZED, RECONCILE_SCHEDULER_ENABLED, PAID_ENTITLEMENT_POLICY_APPROVED, PROVIDER_READS_AUTHORIZED, AI_COST_LIMITS_ENFORCED, HISTORY_RESTRICTIONS_ENFORCED, MODEL_PROFILE_ENFORCED etc.; enabling each is a reviewed change.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Enabling each gate
- **Required for closure:** None

#### DI-I-024: Numerical Basic/Premium allowances not approved
- **Original:** `I-ALLOW` · **Source:** W12_04D_P4_A section 19; P2_A section 13 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Allowance values for Practice, Mo, research, uploads, Packs etc. unapproved; Practice counted started vs completed undecided.
- **Partly addressed:** None recorded
- **Remains:** Allowance values for Practice, Mo, research, uploads, Packs etc. unapproved; Practice counted started vs completed undecided.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Owner approval of numbers
- **Required for closure:** None

#### DI-I-025: Quota reset periods not approved
- **Original:** `I-RESET` · **Source:** W12_04D_P4_A sections 18-19 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reset period undecided; no billing-period quota.
- **Partly addressed:** None recorded
- **Remains:** Reset period undecided; no billing-period quota.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Owner approval
- **Required for closure:** None

#### DI-I-026: Basic-to-Fast transition not approved
- **Original:** `I-FAST` · **Source:** W12_04D_P2_C_MODEL_PROFILE_ENTITLEMENTS.md section 10; P3 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Basic gets Fast only (approved requirement, not active); activation conditions in P2-C section 10; Fast model quality/cost evaluation pending; transition notice not approved.
- **Partly addressed:** MODEL_PROFILE_ENFORCED False; P10E sampled Fast/Balanced/Advanced on 9 KB cases (structural)
- **Remains:** Human quality evaluation; owner approval
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Approve transition and notice
- **Required for closure:** None

#### DI-I-027: Grandfathering of existing candidates
- **Original:** `I-GRANDFATHER` · **Source:** W12_04D_P4_A section 19 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Policy for existing candidates and activation timing undecided.
- **Partly addressed:** None recorded
- **Remains:** Policy for existing candidates and activation timing undecided.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Decision
- **Required for closure:** None

#### DI-I-028: Existing-share policy before history activation
- **Original:** `I-HISTORY-SHARE` · **Source:** W12_04D_P2_C section dependencies; P2_B section 13 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** History rollout off; its existing-share policy must be resolved before history activation.
- **Partly addressed:** None recorded
- **Remains:** History rollout off; its existing-share policy must be resolved before history activation.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Decision
- **Required for closure:** None

#### DI-I-029: Ask4Mo UG incorporation and legal dependencies
- **Original:** `I-UG` · **Source:** W12_04D_P2_A section 13; P4_A section 20 · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Separate German company registration pending; dedicated Stripe account required; seller entity not decided.
- **Partly addressed:** None recorded
- **Remains:** Separate German company registration pending; dedicated Stripe account required; seller entity not decided.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Incorporation
- **Required for closure:** None

#### DI-I-030: Premium pricing and Basic/Premium product matrix commercial approval
- **Original:** `I-PREMIUM-PRICE` · **Source:** P4_A section 20; P5_B section 39 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Premium pricing unapproved; pricing page preview EUR 19.99.
- **Partly addressed:** None recorded
- **Remains:** Premium pricing unapproved; pricing page preview EUR 19.99.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Approve price
- **Required for closure:** None

#### DI-I-031: Pricing page vs account page inconsistency (journey D-02)
- **Original:** `I-D02` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-02 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Pricing showed Premium as EUR 19.99 plan to choose while account said preview.
- **Partly addressed:** P3/P5-B: Premium unavailable, purchasable false, no href (eval_marketing_product_trust invariant)
- **Remains:** Not re-verified in UI by me; EUR 19.99 still in frontend/lib/pricing.ts as preview
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** P5_B section 32 table

#### DI-I-032: Seller-initiated refund execution and billing alert delivery
- **Original:** `I-REFUND-EXEC` · **Source:** F2_B1R section 8; W12_04D_D section 22 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Refund/dispute authoritative reads, seller refunds and alert delivery beyond in-app counts not built.
- **Partly addressed:** None recorded
- **Remains:** Refund/dispute authoritative reads, seller refunds and alert delivery beyond in-app counts not built.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-I-033: Reconciliation scheduler and real StripeStateReader
- **Original:** `I-SCHED` · **Source:** W12_04D_F1 section 14 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Scheduler disabled; reader implemented but not wired (IMPLEMENTED BUT UNVERIFIED).
- **Partly addressed:** None recorded
- **Remains:** Scheduler disabled; reader implemented but not wired (IMPLEMENTED BUT UNVERIFIED).
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-I-034: Billing is mock only
- **Original:** `I-MOCK` · **Source:** W10_5; R-95 ACCEPTED · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Billing Admin is MOCK; Stripe not connected; mock refunds lack coupons; plan pricing absent.
- **Partly addressed:** None recorded
- **Remains:** Billing Admin is MOCK; Stripe not connected; mock refunds lack coupons; plan pricing absent.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-I-035: Stripe subscription lifecycle never exercised against a real provider
- **Original:** `I-LIFECYCLE` · **Source:** docs/capstone/billing (W12.4D-B to F2-B1R) · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Checkout, signed webhook, reconciliation, subscription state, refund, dispute and cancellation exist as code with deterministic doubles; none has run against Stripe (sandbox or live). Managed Payments eligibility is unverified.
- **Remains:** Sandbox qualification (I-STRIPE-SANDBOX) then lifecycle drills; the reader, webhook and checkout authorization constants stay False.
- **Candidate impact:** no paid plan can be purchased · **Security/privacy:** webhook signature and money-moving paths verified only offline · **Release impact:** commercial activation
- **Dependencies:** I-STRIPE-ACCT, I-UG, owner decisions · **Owner decisions:** REQUIRED: dedicated Stripe account, sandbox access, owner authorization
- **Required for closure:** Sandbox end-to-end drills with verified events and reconciliation, then owner review

### Category J: External integrations (17 active)

#### DI-J-001: Brevo live verification
- **Original:** `J-BREVO` (also: journey A-03) · **Source:** docs/capstone/admin/W12_04C_EMAIL_IDENTITY_OPERATIONS.md section 10 · **First recorded:** 2026-10-14
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Live delivery UNVERIFIED: no real Brevo send ever; no email provider configured in dev; ten live success criteria (secure store, verified sender SPF/DKIM, test connection, test email, registration and recovery links) unmet.
- **Partly addressed:** Code qualified; probes; 78 OIDC + email tests
- **Remains:** Run the 10-step runbook with separate owner authorization
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** BPL: open registration needs verified email path
- **Dependencies:** Brevo account, verified sender, SecretStore master key · **Owner decisions:** Authorization for live send
- **Required for closure:** None

#### DI-J-002: Brevo delivery/bounce webhooks not implemented
- **Original:** `J-BREVO-HOOK` · **Source:** W12_04C section 4, 11 · **First recorded:** 2026-10-14
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Acceptance is the ceiling; delivered/bounced states do not exist; webhooks deliberately not built.
- **Partly addressed:** None recorded
- **Remains:** Acceptance is the ceiling; delivered/bounced states do not exist; webhooks deliberately not built.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-003: Cached Brevo/provider clients need restart on rotation
- **Original:** `J-BREVO-CACHE` · **Source:** W12_04B section 12; W12_04C section 11 · **First recorded:** 2026-10-14
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** OpenRouter, embeddings, Brevo, Redis and Langfuse clients built once per process; rotation takes effect after API and worker restart; hot reload not done (W12.4F deferred).
- **Partly addressed:** Admin shows restart-required state
- **Remains:** Hot reload
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W12_4F section 9 (runtime configuration effectiveness)

#### DI-J-004: Workspace invitation mail not instrumented
- **Original:** `J-INVITE-MAIL` · **Source:** W12_04C section 11 · **First recorded:** 2026-10-14
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Workspace invitation mail uses shared sender without attempt records or localisation.
- **Partly addressed:** None recorded
- **Remains:** Workspace invitation mail uses shared sender without attempt records or localisation.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-005: Google OIDC live validation and frontend wiring
- **Original:** `J-OIDC` · **Source:** W12_04C section 7; P10B_RELEASE_ACCEPTANCE_MATRIX.md R-32, R-97 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Backend implemented with PKCE + ID-token validation; disabled by default; not wired to sign-in page; never validated live (R-97 ACCEPTED).
- **Partly addressed:** 78 offline tests against mock Google
- **Remains:** Provider account, client config, live authorized sign-in, frontend button
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Whether to ship Google sign-in
- **Required for closure:** None

#### DI-J-006: OIDC-only users cannot set a password via recovery
- **Original:** `J-OIDC-PWD` · **Source:** W12_04C section 2 finding 5, section 11 · **First recorded:** 2026-10-14
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Product decision pending whether OIDC-only users may set a password.
- **Partly addressed:** None recorded
- **Remains:** Product decision pending whether OIDC-only users may set a password.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Product decision
- **Required for closure:** None

#### DI-J-007: OIDC-only admin cannot step up
- **Original:** `J-OIDC-STEPUP` · **Source:** W10_13 carry-forward; R-97 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Fails closed; unvalidated live.
- **Partly addressed:** None recorded
- **Remains:** Fails closed; unvalidated live.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-008: Redis integration unverified
- **Original:** `J-REDIS` · **Source:** W12_04B section 2 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** See H-REDIS-LIVE; also Redis secret slot and client cached per process.
- **Partly addressed:** None recorded
- **Remains:** See H-REDIS-LIVE; also Redis secret slot and client cached per process.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** H-REDIS-LIVE · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-009: Langfuse live validation
- **Original:** `J-LANGFUSE` · **Source:** docs/final_submission_readiness.md line 104; phase7_integrated_readiness.md line 85 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Optional observability sink OFF by default; live Langfuse never validated; no paid RAGAS.
- **Partly addressed:** None recorded
- **Remains:** Optional observability sink OFF by default; live Langfuse never validated; no paid RAGAS.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-010: Adzuna live verification (K4)
- **Original:** `J-ADZUNA` · **Source:** docs/capstone/p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Deterministic contract PASS; live test skipped (needs RUN_ADZUNA_INTEGRATION=1 + creds).
- **Partly addressed:** None recorded
- **Remains:** Deterministic contract PASS; live test skipped (needs RUN_ADZUNA_INTEGRATION=1 + creds).
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-011: Live OCR quality unvalidated
- **Original:** `J-OCR` · **Source:** p9_quality_register.md; CLAUDE.md OCR section; W12_02 section 7 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Deterministic fixtures only; live/human OCR accuracy UNVALIDATED.
- **Partly addressed:** None recorded
- **Remains:** Deterministic fixtures only; live/human OCR accuracy UNVALIDATED.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-012: Real malware scanner not configured
- **Original:** `J-CLAMAV` · **Source:** W12_04B section 10; W12.4A R-1 resolution; W10_8 section 13 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Governed uploads fail closed with scan_unavailable without real scanner; ClamAV setup is operator task; EX-12 #13 hosted fail-closed unproven.
- **Partly addressed:** None recorded
- **Remains:** Governed uploads fail closed with scan_unavailable without real scanner; ClamAV setup is operator task; EX-12 #13 hosted fail-closed unproven.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-013: OpenRouter live behaviour beyond P10E sample
- **Original:** `J-OPENROUTER` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md; P10E_R1 section 10 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** P10E/R1/R2 used 285 of 300 calls (USD 2.11 committed); interview-quality, semantic, RAGAS NOT RUN; embedding provider/host not configured.
- **Partly addressed:** Guarded live runs; smoke, agent, KB answer, 14-case multilingual
- **Remains:** Semantic calibration, RAGAS live, human-reviewed quality
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** Owner authorization; embedding credential · **Owner decisions:** Whether to spend remaining 15 calls/USD 7.89
- **Required for closure:** P10E_R1 section 15, R2 section 7

#### DI-J-014: Semantic live calibration (L-REL-1/L-XLANG-1) NOT RUN
- **Original:** `J-SEMANTIC` · **Source:** P10E sec dispositions; P10E_R1 section 10, 14 · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No embedding provider; calibration would be INCONCLUSIVE; non-English retrieval gap persists.
- **Partly addressed:** None recorded
- **Remains:** No embedding provider; calibration would be INCONCLUSIVE; non-English retrieval gap persists.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-015: RAGAS live NOT RUN
- **Original:** `J-RAGAS` · **Source:** P10E_R1 section 10 · **First recorded:** 2026-10-19
- **Status:** NOT RUN · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** RAGAS_EVAL_API_KEY absent; judge on non-allowlisted host.
- **Partly addressed:** None recorded
- **Remains:** RAGAS_EVAL_API_KEY absent; judge on non-allowlisted host.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-016: Production integration readiness
- **Original:** `J-INTEG-READY` · **Source:** W10_14 section 45; W12_4F section 24 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Integration probes and SecretStore UNVALIDATED LIVE; health 'not tested' until manual test; readiness is derived, not polled; Provider status vs Integrations different sources.
- **Partly addressed:** None recorded
- **Remains:** Integration probes and SecretStore UNVALIDATED LIVE; health 'not tested' until manual test; readiness is derived, not polled; Provider status vs Integrations different sources.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-J-017: Provider rate limits and failure handling live
- **Original:** `J-RATE` · **Source:** W12_04C section 3; R-85 · **First recorded:** UNKNOWN
- **Status:** NOT RUN · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** No live observation of provider rate limits; Brevo no auto-retry; Stripe/Brevo rate_limited categories handled offline only.
- **Partly addressed:** None recorded
- **Remains:** No live observation of provider rate limits; Brevo no auto-retry; Stripe/Brevo rate_limited categories handled offline only.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

### Category K: Legal and governance (16 active)

#### DI-K-001: Verify reviewer identities and accounts
- **Original:** `BL-1` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md (table row 1); P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s3 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P0 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Confirm whether existing platform_admin and knowledge_admin accounts in any environment are real named humans (dev DB has 1 each; isolated DB has 0; production not inspected).
- **Partly addressed:** Role counts read (read-only); no identity read
- **Remains:** Confirm whether existing platform_admin and knowledge_admin accounts in any environment are real named humans (dev DB has 1 each; isolated DB has 0; production not inspected).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Reviewer authority must belong to a real person · **Release impact:** Blocks reviewer appointment and all human qualification
- **Dependencies:** none; blocks 2,5,6,12 · **Owner decisions:** Owner must confirm which accounts are real people
- **Required for closure:** Named-human confirmation recorded

#### DI-K-002: Complete two-person role changes for appointments
- **Original:** `BL-3` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 3; P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md s4 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P0 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Run the existing two-person RoleChangeService for each appointment (requester and approver must differ; target may be neither).
- **Partly addressed:** Workflow exists in code
- **Remains:** Run the existing two-person RoleChangeService for each appointment (requester and approver must differ; target may be neither).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Two-person control for privileged roles · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-2; blocks 5,6 · **Owner decisions:** Needs two distinct administrators
- **Required for closure:** Approved role-change records

#### DI-K-003: D-21 name who performs qualified legal review
- **Original:** `D-21` · **Source:** docs/capstone/p10/P10C_F1_OWNER_DECISION_APPENDIX.md s1-2 · **First recorded:** 2026-10-18
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Required before Packages 3 and 7 (ISCO-08, ESCO third-party, ShareAlike).
- **Partly addressed:** None recorded
- **Remains:** Required before Packages 3 and 7 (ISCO-08, ESCO third-party, ShareAlike).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal exposure · **Release impact:** Blocks any release needing this item
- **Dependencies:** UNKNOWN · **Owner decisions:** Owner to name legal reviewer
- **Required for closure:** Not closed

#### DI-K-004: ESCO data licence not named
- **Original:** `K-LIC-ESCO` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md (eu_esco) · **First recorded:** 2026-10-18
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Reuse basis (Decision 2011/833/EU, CC BY 4.0 for EU-owned content) unclear; third-party components; legal review required before Package 3.
- **Partly addressed:** None recorded
- **Remains:** Reuse basis (Decision 2011/833/EU, CC BY 4.0 for EU-owned content) unclear; third-party components; legal review required before Package 3.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal exposure · **Release impact:** Blocks any release needing this item
- **Dependencies:** D-21 legal reviewer · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-005: ISCO-08 reuse beyond short excerpts needs ILO permission
- **Original:** `K-LIC-ISCO` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md (intl_isco08) · **First recorded:** 2026-10-18
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Landing page not read; finding rests on catalogue entry and rights page; also codes appear inside ESCO under a separate licence.
- **Partly addressed:** None recorded
- **Remains:** Landing page not read; finding rests on catalogue entry and rights page; also codes appear inside ESCO under a separate licence.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal exposure · **Release impact:** Blocks any release needing this item
- **Dependencies:** D-21 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-006: German Entgeltatlas (no terms) and Destatis (third-party catalogue licence)
- **Original:** `K-LIC-DE` · **Source:** docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md · **First recorded:** 2026-10-18
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** BA terms must be requested; Destatis licence (Datenlizenz Deutschland by-2-0) taken from a third-party catalogue record; GENESIS needs credentials.
- **Partly addressed:** None recorded
- **Remains:** BA terms must be requested; Destatis licence (Datenlizenz Deutschland by-2-0) taken from a third-party catalogue record; GENESIS needs credentials.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal exposure · **Release impact:** Blocks any release needing this item
- **Dependencies:** D-21 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-007: Commercial use outside home territory of OGL/Eurostat/INEGI content
- **Original:** `K-LIC-OGL` · **Source:** docs/capstone/p10/P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s E · **First recorded:** 2026-10-18
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** ONS pages do not address commercial use or territory; same open question as RB-LIC-1 for any non-home market; not legal advice.
- **Partly addressed:** None recorded
- **Remains:** ONS pages do not address commercial use or territory; same open question as RB-LIC-1 for any non-home market; not legal advice.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal exposure · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-8 / D-21 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-008: Attribution wording decisions
- **Original:** `K-ATTR` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md s F; P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s F · **First recorded:** 2026-10-18
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Owner confirmation of BLS credit text, O*NET CC BY attribution (31.0) and OGL statement/ONS citation outstanding; BLS emblem must not be used; no raw file committed.
- **Partly addressed:** None recorded
- **Remains:** Owner confirmation of BLS credit text, O*NET CC BY attribution (31.0) and OGL statement/ONS citation outstanding; BLS emblem must not be used; no raw file committed.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Licence compliance · **Release impact:** Blocks any release needing this item
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-009: Human source qualification
- **Original:** `K-HUMANSRC` · **Source:** docs/capstone/p10/P10C_F2A_CAPSTONE_ENGINEERING_CLOSURE.md s3 · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** 0 sources, 0 records, 0 aliases human-qualified; requires named authenticated reviewer; nothing transitions automatically.
- **Partly addressed:** None recorded
- **Remains:** 0 sources, 0 records, 0 aliases human-qualified; requires named authenticated reviewer; nothing transitions automatically.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** BL-1 to BL-4 · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-010: Legal acceptance of owner policy decisions
- **Original:** `K-LEGALACC` · **Source:** docs/capstone/p10/P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md M.2-M.5; P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md s M · **First recorded:** 2026-10-18
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Owner decisions D-04, D-12, D-13, D-15 and POLICY A-K were recorded on explicit instruction; 'no signature or external legal approval is claimed'; sign-off tables for Package 2 blank.
- **Partly addressed:** None recorded
- **Remains:** Owner decisions D-04, D-12, D-13, D-15 and POLICY A-K were recorded on explicit instruction; 'no signature or external legal approval is claimed'; sign-off tables for Package 2 blank.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Governance record · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-011: Privacy, Terms and AI-transparency pages are engineering drafts
- **Original:** `K-PRIV` · **Source:** docs/capstone/p9_quality_register.md; p8_e8_productisation_hosting.md s141-151 · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** BLOCKER · **Priority:** P0 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Visible 'engineering draft, pending legal review' banners; legal counsel review required; English-only bodies; not publishable.
- **Partly addressed:** None recorded
- **Remains:** Visible 'engineering draft, pending legal review' banners; legal counsel review required; English-only bodies; not publishable.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal/privacy exposure at launch · **Release impact:** Public launch blocked until legal review
- **Dependencies:** UNKNOWN · **Owner decisions:** Engage counsel
- **Required for closure:** Not closed

#### DI-K-012: Legal/privacy review of AI-guidance and source-excerpt wording
- **Original:** `K-AIGUID` (also: PRIV-AI-COPY) · **Source:** docs/capstone/ASK4MO_MASTER_CAPSTONE_ROADMAP.md s3; product/W12_04D_P5_A_OPPORTUNITY_PREPARATION_PACK.md · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Opportunity Pack labels ('verified-external' = source-linked excerpt, not independently verified; 'AI guidance') need legal/privacy review.
- **Partly addressed:** None recorded
- **Remains:** Opportunity Pack labels ('verified-external' = source-linked excerpt, not independently verified; 'AI guidance') need legal/privacy review.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Claims and disclosure accuracy · **Release impact:** Blocks any release needing this item
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-013: No GDPR compliance/certification claim permitted
- **Original:** `K-GDPR` · **Source:** docs/product/PRODUCT_CLAIMS.md NO-01; capstone_risk_register.md R-5 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Claims must not state GDPR compliance until legal review (PRODUCT_CLAIMS NO-01); R-5 requires counsel review and EU hosting decision.
- **Partly addressed:** None recorded
- **Remains:** Claims must not state GDPR compliance until legal review (PRODUCT_CLAIMS NO-01); R-5 requires counsel review and EU hosting decision.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Regulatory · **Release impact:** Blocks any release needing this item
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-014: Engineering translations of legal/privacy/trust text
- **Original:** `K-TRANS-LEGAL` · **Source:** docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md R-49; p9_localization_completeness.md · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Privacy, Terms, AI-transparency, Trust, Help translations are engineering drafts; native and legal review pending (R-49).
- **Partly addressed:** None recorded
- **Remains:** Privacy, Terms, AI-transparency, Trust, Help translations are engineering drafts; native and legal review pending (R-49).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Legal accuracy per locale · **Release impact:** Blocks any release needing this item
- **Dependencies:** K-PRIV · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-015: Third-party model provider data handling for real candidate data
- **Original:** `K-PROVIDER` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s6; docs/capstone/capstone_risk_register.md R-14 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** OpenRouter may retain submitted content per its policy; only synthetic content sent in P10E; DPAs/EU handling to be decided before real candidate data (R-5, R-14).
- **Partly addressed:** None recorded
- **Remains:** OpenRouter may retain submitted content per its policy; only synthetic content sent in P10E; DPAs/EU handling to be decided before real candidate data (R-5, R-14).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** Candidate data leaves platform to provider · **Release impact:** Blocks any release needing this item
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-K-017: The Turing College capstone brief and rubric are not in the repository
- **Original:** `IR-TURING-RUBRIC` · **Source:** docs/capstone/INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 18 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** HIGH · **Priority:** P0 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** All rubric references are second-hand (planning documents). Assessment criteria must not be invented.
- **Remains:** The official brief was found in the submission repository (AE.CAP_afa.md): four criteria, cases, README rule, presentation format. Not in the brief: weights, pass marks, deadline, hosting rule, review procedure.
- **Candidate impact:** none · **Security/privacy:** none identified · **Release impact:** academic submission
- **Dependencies:** none · **Owner decisions:** REQUIRED: confirm the remaining items with the STL
- **Required for closure:** Rubric file or owner confirmation added to the P11 requirements traceability matrix

### Category L: Human validation (13 active)

#### DI-L-001: P10F targeted human validation
- **Original:** `BL-19` · **Source:** docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md row 19; ASK4MO_MASTER_CAPSTONE_ROADMAP.md s1b · **First recorded:** 2026-10-18
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Targeted human validation after P10E; participants and protocol not defined; AC-24 stays PARTIAL until its criteria, including P10F, are met. Whether AC-24 can be evaluated in capstone scope without P10F is an OPEN owner decision.
- **Partly addressed:** Pilot 2 (n=3) human evidence exists on RC-P10-003
- **Remains:** Targeted human validation after P10E; participants and protocol not defined; AC-24 stays PARTIAL until its criteria, including P10F, are met. Whether AC-24 can be evaluated in capstone scope without P10F is an OPEN owner decision.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** AC-24 cannot reach PASS
- **Dependencies:** P10E; participants and protocol · **Owner decisions:** Open owner decision on AC-24 scope
- **Required for closure:** Not closed

#### DI-L-002: Human revalidation: Sharing and revocation discoverability
- **Original:** `P2-01` (also: P2-01 (second record, merged)) · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-01; docs/capstone/p10/pilot2/PILOT2_P1_REMEDIATION_QUALIFICATION.md · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Remediated frontend/environment (P1 qualification 2026-10-12: Vitest 831, Playwright 271, backend 3,170) but original issue was human comprehension; no participant has seen the remediated runtime; not closed until targeted human revalidation.
- **Partly addressed:** Remediated and regression-qualified
- **Remains:** Targeted human revalidation
- **Candidate impact:** Usability of privacy/score/provenance for candidates · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Participants; protocol; successor RC · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-003: Human revalidation: Source-backed experience in a representative knowledge environment
- **Original:** `P2-02` · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-02; docs/capstone/p10/pilot2/PILOT2_P1_REMEDIATION_QUALIFICATION.md · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** UNKNOWN · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Remediated frontend/environment (P1 qualification 2026-10-12: Vitest 831, Playwright 271, backend 3,170) but original issue was human comprehension; no participant has seen the remediated runtime; not closed until targeted human revalidation.
- **Partly addressed:** Remediated and regression-qualified
- **Remains:** Targeted human revalidation
- **Candidate impact:** Usability of privacy/score/provenance for candidates · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Participants; protocol; successor RC · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-004: Human revalidation: Answer score interpretation
- **Original:** `P2-03` · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-03; docs/capstone/p10/pilot2/PILOT2_P1_REMEDIATION_QUALIFICATION.md · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Remediated frontend/environment (P1 qualification 2026-10-12: Vitest 831, Playwright 271, backend 3,170) but original issue was human comprehension; no participant has seen the remediated runtime; not closed until targeted human revalidation.
- **Partly addressed:** Remediated and regression-qualified
- **Remains:** Targeted human revalidation
- **Candidate impact:** Usability of privacy/score/provenance for candidates · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Participants; protocol; successor RC · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-005: Human revalidation: AI-generated vs sourced vs verified provenance clarity
- **Original:** `P2-04` (also: P2-04 (second record, merged)) · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-04; docs/capstone/p10/pilot2/PILOT2_P1_REMEDIATION_QUALIFICATION.md · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Remediated frontend/environment (P1 qualification 2026-10-12: Vitest 831, Playwright 271, backend 3,170) but original issue was human comprehension; no participant has seen the remediated runtime; not closed until targeted human revalidation.
- **Partly addressed:** Remediated and regression-qualified
- **Remains:** Targeted human revalidation
- **Candidate impact:** Usability of privacy/score/provenance for candidates · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** Participants; protocol; successor RC · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-006: Re-evaluate marketing/pricing positioning with participants
- **Original:** `P2-06` · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-06 · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** PR #137 (plan comparison, coaching comparison, founder section) merged after RC-P10-003 freeze; unevaluated by participants.
- **Partly addressed:** None recorded
- **Remains:** PR #137 (plan comparison, coaching comparison, founder section) merged after RC-P10-003 freeze; unevaluated by participants.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-007: Opera voice recording failure needs reproduction
- **Original:** `P2-09` (also: P2-09 (second record, merged)) · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_ISSUE_REGISTER.md P2-09 · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** UNKNOWN · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** Recording failed in Opera for P06, worked in Safari; reproduce with version and permission state before calling defect.
- **Partly addressed:** None recorded
- **Remains:** Recording failed in Opera for P06, worked in Safari; reproduce with version and permission state before calling defect.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-008: AC-24 Pilot and lessons remains PARTIAL
- **Original:** `L-AC24` · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_RESULTS.md s11; roadmap s21,s39 · **First recorded:** UNKNOWN
- **Status:** OPEN — PRE-SUBMISSION QUALIFICATION · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** Pilot 2 (n=3 evidenced of 6 listed) verdict CONDITIONAL GO; P1 fixes regression-tested but no successor RC or human revalidation; whether AC-24 can pass without P10F is an open owner decision.
- **Partly addressed:** Human evidence captured; P1 remediation qualified
- **Remains:** AC-24 stays PARTIAL: RC-P10-004 does not exist (no successor RC, release gate not run on the changed runtime); P10F human revalidation deferred; whether AC-24 may close without P10F is an open owner decision. Individual criteria: 6 of 8 met (see ACADEMIC_SUBMISSION_SCOPE_DECISION.md section 4).
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** RC-P10-004 (not created), P10F · **Owner decisions:** REQUIRED: separate approval to create RC-P10-004; decision on AC-24 closure without P10F.
- **Required for closure:** Not closed

#### DI-L-009: Pilot 2 coverage gaps
- **Original:** `L-PILOT-COV` · **Source:** docs/capstone/p10/pilot2/RC_P10_003_PILOT2_RESULTS.md s2-3 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** P01, P03, P05 lacked structured evidence and are not counted; no German session; mobile not evidenced; one non-English (Italian) session; Safari only; knowledge/Sources not validated at the time.
- **Partly addressed:** None recorded
- **Remains:** P01, P03, P05 lacked structured evidence and are not counted; no German session; mobile not evidenced; one non-English (Italian) session; Safari only; knowledge/Sources not validated at the time.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** P10F participants · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-010: Human/native translation review of interface and Help (7-8 locales)
- **Original:** `L-NATIVE-UI` · **Source:** docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md R-11, R-14, R-49; p9_quality_register.md · **First recorded:** UNKNOWN
- **Status:** OPEN — PRODUCTION RELEASE BLOCKER · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Engineering translations with key parity enforced; professional native review pending (R-49); Russian not human-reviewed.
- **Partly addressed:** None recorded
- **Remains:** Engineering translations with key parity enforced; professional native review pending (R-49); Russian not human-reviewed.
- **Candidate impact:** Wording errors in non-English UI · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-011: Live generated-language validation (R-50)
- **Original:** `L-LIVE-LANG` · **Source:** docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md R-50; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** ACCEPTED limitation 'needs a separately authorised live run'. P10E-R1/R2 later ran live multilingual (14+7 calls) by proxy only; human fluency review pending.
- **Partly addressed:** Live 7-language run with language proxy
- **Remains:** Human native review (C-NATIVE)
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** UNKNOWN · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-012: Voice not human-validated (PF-19 / AC-23 live)
- **Original:** `L-VOICE` · **Source:** docs/capstone/p10/w9/P10B_W9_PILOT_FINDINGS.md PF-19; p9_voice_measurement.md · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** All voice implemented and deterministically tested only; TTS liveHumanQualityTested false; participants only partially tested voice; Russian voice unsupported.
- **Partly addressed:** Pilot 2: voice tested by all three counted sessions (usability only)
- **Remains:** Human speech-quality validation
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** No release effect until activated
- **Dependencies:** Genuine engine execution · **Owner decisions:** None recorded
- **Required for closure:** Not closed

#### DI-L-013: Production-quality human evaluation overall
- **Original:** `L-PRODQ` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md s10; docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md s11.4 · **First recorded:** 2026-10-19
- **Status:** PENDING HUMAN REVIEW · **Severity:** HIGH · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** YES
- **Description:** No human-reviewed quality exists for any AI output (interview, multilingual, citations, policies); all live evidence is synthetic; see C-INT-HUMAN, C-KB-HUMAN, C-NATIVE, C-CITE.
- **Partly addressed:** None recorded
- **Remains:** No human-reviewed quality exists for any AI output (interview, multilingual, citations, policies); all live evidence is synthetic; see C-INT-HUMAN, C-KB-HUMAN, C-NATIVE, C-CITE.
- **Candidate impact:** None while Compensation V2 and candidate-facing use stay disabled · **Security/privacy:** None identified · **Release impact:** Blocks any release needing this item
- **Dependencies:** P10F, reviewers · **Owner decisions:** None recorded
- **Required for closure:** Not closed

### Category M: Technical debt and documentation consistency (25 active)

#### DI-M-003: Locale-aware font/subset loading
- **Original:** `TD-W9-03` · **Source:** P10B_W9_IMPLEMENTATION_PLAN.md TD-W9-03; R-51 · **First recorded:** UNKNOWN
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Cyrillic subset (~18.7 kB woff2) preloaded for every locale; optimisation optional (R-51 ACCEPTED).
- **Partly addressed:** None recorded
- **Remains:** Measure before optimising; also metadata localization
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W9.9 states untouched

#### DI-M-012: AI config: second approver must be a second Platform Admin
- **Original:** `SJA-01` · **Source:** docs/capstone/journeys/SPECIALIST_ADMIN_JOURNEYS.md section 9 (ROLE-SCOPE) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** ai.manage/ai.activate held only by Platform Admin; possible future review.
- **Partly addressed:** None recorded
- **Remains:** ai.manage/ai.activate held only by Platform Admin; possible future review.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Possible future permission review; none made
- **Required for closure:** None

#### DI-M-013: Knowledge Admin cannot retry/cancel failed jobs
- **Original:** `SJA-02` · **Source:** docs/capstone/journeys/SPECIALIST_ADMIN_JOURNEYS.md section 9 (ROLE-SCOPE) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** jobs.read only; escalate to Ops/Platform Admin.
- **Partly addressed:** None recorded
- **Remains:** jobs.read only; escalate to Ops/Platform Admin.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Possible future permission review; none made
- **Required for closure:** None

#### DI-M-014: Billing/Security-Privacy admins cannot see queue state
- **Original:** `SJA-03` · **Source:** docs/capstone/journeys/SPECIALIST_ADMIN_JOURNEYS.md section 9 (ROLE-SCOPE) · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** They trigger background jobs but hold no jobs.read.
- **Partly addressed:** None recorded
- **Remains:** They trigger background jobs but hold no jobs.read.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Possible future permission review; none made
- **Required for closure:** None

#### DI-M-015: Knowledge approval has no distinct-actor rule or step-up
- **Original:** `SJA-05` · **Source:** SPECIALIST_ADMIN_JOURNEYS.md SJA-05 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** UNKNOWN
- **Description:** One Knowledge Admin can upload and approve; related to Platform Admin finding A-04.
- **Partly addressed:** None recorded
- **Remains:** Verified: no distinct-actor check in src/knowledge_admin (grep)
- **Candidate impact:** None directly · **Security/privacy:** Single actor can publish knowledge into RAG · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** REQUIRED: whether knowledge approval and activation need a distinct-actor rule and/or fresh-password step-up (related A-04). Source qualification itself is unaffected: unapproved knowledge still never reaches candidate retrieval.
- **Required for closure:** None

#### DI-M-016: Held permissions with no consuming route
- **Original:** `SJA-06` · **Source:** SPECIALIST_ADMIN_JOURNEYS.md SJA-06 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** platform.releases.read and platform.subscriptions.read held but no route requires them.
- **Partly addressed:** None recorded
- **Remains:** W12.4F added /admin/readiness (overview.read, releases.read) so releases.read may now be consumed; not re-verified
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** W12_4F section 6

#### DI-M-016: One unplanned live agent run during the P11 rehearsal (outside the P10E ledger)
- **Original:** `IR-REHEARSAL-CALL` · **Source:** docs/capstone/submission/REHEARSAL_AND_FREEZE_LOG.md · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** During the UI rehearsal a single POST /agent/run reached the live provider because the working copy's .env key was loaded (see IR-DEMO-KEY). The P10E ledger was not used and is unchanged (285 of 300 calls). A read-only account snapshot afterwards showed usage +USD 0.0207 since the previous snapshot (may include other use of the shared key); the per-request cost was not captured.
- **Remains:** Acknowledge the unplanned spend; no further action possible on the spend itself. The shared-key reconciliation caveat (DI-M M-RECON) applies.
- **Candidate impact:** none directly · **Security/privacy:** spend outside the hard budget guard · **Release impact:** demonstration safety and spend control
- **Dependencies:** none · **Owner decisions:** REQUIRED: acknowledge the unplanned call
- **Required for closure:** Owner acknowledgement recorded; snapshot kept (evaluations/p10e/live/provider_snapshots/...p11-rehearsal-incident.json)

#### DI-M-017: Step-up only for role changes (journey finding)
- **Original:** `A-04` · **Source:** docs/capstone/journeys/PLATFORM_ADMIN_JOURNEY.md A-04 · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** High-risk actions (price change, refund, AI activation, knowledge approval, legal publish, deactivation) lack fresh password.
- **Partly addressed:** Step-up later added to secret rotation (W12.4B) and billing recovery (F1R); routes confirm in admin_integrations.py, admin_billing_ops.py, admin_security.py
- **Remains:** Other high-risk actions rely on permission, second approver, audit
- **Candidate impact:** None directly · **Security/privacy:** Admin account takeover impact · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** src/api/routes StepUpService usage

#### DI-M-018: Mo and company-research cost-ledger gap
- **Original:** `M-LEDGER` · **Source:** docs/capstone/product/W12_04D_P5_B_PREMIUM_INTEGRATED_ACCEPTANCE.md section 16 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Mo (agent) and company research guarded only by pause and per-user bucket; no token/cost evidence in ai_operation_events; Pack generation inherits gap.
- **Partly addressed:** Practice, Career chat, job analysis, questions, Pack are metered
- **Remains:** Mo (agent) and company research guarded only by pause and per-user bucket; no token/cost evidence in ai_operation_events; Pack generation inherits gap.
- **Candidate impact:** None directly · **Security/privacy:** Uncontrolled spend path · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Whether Mo/company research must enter ledger before launch
- **Required for closure:** P5_B section 16 pinned by inventory test

#### DI-M-019: Shared OpenRouter credential concerns
- **Original:** `M-OR-KEY` · **Source:** P10E section 4; P10E_R1 section 11 · **First recorded:** 2026-10-19
- **Status:** NOT VERIFIED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** One OpenRouter key serves all workloads; account-level usage deltas can include other uses of the credential, preventing attribution; P10E said nothing else used the key that day while R1 said it cannot be excluded.
- **Partly addressed:** None recorded
- **Remains:** Dedicated per-environment key or usage tagging
- **Candidate impact:** None directly · **Security/privacy:** Key blast radius and attribution · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Key strategy
- **Required for closure:** None

#### DI-M-020: Provider-cost reconciliation discrepancy (P10E)
- **Original:** `M-RECON-1` · **Source:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md section 4 · **First recorded:** 2026-10-19
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Sum of per-request reported cost USD 0.834 is about 5.5% above account delta 0.791; origin unexplained.
- **Partly addressed:** None recorded
- **Remains:** Unexplained
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-021: Provider-cost reconciliation discrepancy (P10E-R1 section 11)
- **Original:** `M-RECON-2` · **Source:** docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md section 11 · **First recorded:** 2026-10-19
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Account delta 0.5235 exceeds per-request sum 0.4801 by 0.0434 (about 9%); R1 calls it the same direction as P10E, but P10E's gap was the opposite sign.
- **Partly addressed:** None recorded
- **Remains:** Unexplained; direction contradicts P10E
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-022: Provider-cost reconciliation (P10E-R2 section 7)
- **Original:** `M-RECON-3` · **Source:** docs/capstone/p10/P10E_R2_CANDIDATE_GROUNDING_POLICIES.md section 7 · **First recorded:** 2026-10-19
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 15-call batch: account delta 0.0346 below per-request reported 0.0553; not attributed.
- **Partly addressed:** None recorded
- **Remains:** Unexplained
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-023: Evaluators without test-isolation bootstrap
- **Original:** `M-ISOLATION` · **Source:** docs/capstone/p10/RC_P10_003_RELEASE_CANDIDATE.md 19A; scripts/ · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 25 scripts/eval_*.py lack import tests.conftest (grep); docs say 17 manual/non-CI; CI ones may bootstrap another way.
- **Partly addressed:** eval_rc_p10_003 enforces rule for CI evaluators
- **Remains:** Manual evaluators can still write dev stores if run bare
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** grep -L tests.conftest scripts/eval_*.py

#### DI-M-027: Evaluation score consistency (POLICY-02)
- **Original:** `M-POLICY02` · **Source:** P10B_W9_12 section 19 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** No deterministic overall-vs-criteria relationship; tolerance would be a product contract decision.
- **Partly addressed:** None recorded
- **Remains:** No deterministic overall-vs-criteria relationship; tolerance would be a product contract decision.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Decision
- **Required for closure:** tests/test_evaluation_contract.py

#### DI-M-028: Legacy Streamlit UI retained (LEGACY-01)
- **Original:** `M-LEGACY01` · **Source:** P10B_W9_12 section 21 · **First recorded:** UNKNOWN
- **Status:** PENDING OWNER DECISION · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Retired only by separate approved task; root Dockerfile still launches Streamlit; R-38 ACCEPTED.
- **Partly addressed:** None recorded
- **Remains:** Retired only by separate approved task; root Dockerfile still launches Streamlit; R-38 ACCEPTED.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** Retirement task
- **Required for closure:** None

#### DI-M-029: docs/limitations.md describes Streamlit-era state
- **Original:** `M-DOC-LIMITS` · **Source:** docs/limitations.md · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** States no authentication, no persistence, interview content only in session; contradicts current product.
- **Partly addressed:** None recorded
- **Remains:** Banner or rewrite
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** Read of file

#### DI-M-030: CLAUDE.md says realtime voice (C1) DEFERRED
- **Original:** `M-DOC-C1` · **Source:** CLAUDE.md line 381 vs docs/capstone/p7_5_c1_realtime_voice.md · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** CLAUDE.md line 381 contradicts P7.5 (architecture delivered, live NOT RUN).
- **Partly addressed:** None recorded
- **Remains:** Reconcile wording
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-031: Phase plan stale W12.4 'NOT STARTED' headings
- **Original:** `M-DOC-PLAN` · **Source:** docs/capstone/ASK4MO_MASTER_CAPSTONE_ROADMAP.md section 4 · **First recorded:** UNKNOWN
- **Status:** PENDING HUMAN REVIEW · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Roadmap section 4 notes stale headings; owner to correct.
- **Partly addressed:** None recorded
- **Remains:** Roadmap section 4 notes stale headings; owner to correct.
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-032: Admin destination count inconsistency
- **Original:** `M-DOC-COUNT` · **Source:** W12_02 section 2; W12_5 section 1 · **First recorded:** 2026-10-12
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 19 (W12.2), 20 (W12.1 miscount, W12.5), 21 (W12.5 note after Speech) across docs; permissions 43 vs 44.
- **Partly addressed:** W12.2 documents miscount
- **Remains:** Normalise in one table
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-033: W12.4C internal contradiction on PKCE/nonce
- **Original:** `M-DOC-OIDC` · **Source:** docs/capstone/admin/W12_04C_EMAIL_IDENTITY_OPERATIONS.md sections 7 vs 11 · **First recorded:** 2026-10-14
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Section 7 says PKCE and ID-token validation implemented; section 11 says OIDC nonce/PKCE not implemented.
- **Partly addressed:** None recorded
- **Remains:** Correct section 11
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-034: PRODUCT_CLAIMS stale entries (D-04)
- **Original:** `M-DOC-CLAIMS` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-04 · **First recorded:** UNKNOWN
- **Status:** NOT VERIFIED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** NO-05, NO-06 reference closed issues; NO-16 says ticketing not built.
- **Partly addressed:** None recorded
- **Remains:** Update
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** None

#### DI-M-035: Stale committed product-coverage summary (97%)
- **Original:** `M-DOC-COVERAGE` · **Source:** ASK4MO_MASTER_CAPSTONE_ROADMAP.md section 3; P10C-G · **First recorded:** 2026-10-18
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** YES
- **Description:** Committed summary stale; labelled HISTORICAL by P10C-G; live measure 386/412 BELOW GATE.
- **Partly addressed:** Labelled HISTORICAL
- **Remains:** Gate unmet: 386/412 vs 392
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** P10C_G doc

#### DI-M-036: Sprint-4 quality_optimisation_audit TODO table
- **Original:** `M-DOC-OPT` · **Source:** docs/quality_optimisation_audit.md · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** 12 TODO rows from OPT audit; reranker (src/copilot/retrieval/reranker.py), load_sample_knowledge.py, check_source_freshness.py, retrieval_quality_v2 and config flags exist; others not verified.
- **Partly addressed:** Five items found in code
- **Remains:** Others unverified; doc not updated
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** ls scripts; grep src

#### DI-M-038: Research-cache contamination incidents (W10.11, RC-QUAL-ENV-01, W12.4C)
- **Original:** `M-RESCACHE-INC` · **Source:** W10_11 section; RC_P10_003 19A; W12_04C section 9b · **First recorded:** UNKNOWN
- **Status:** PARTIALLY REMEDIATED · **Severity:** LOW · **Priority:** P3 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Dev research cache fingerprint changed in W10.11 probe, RC-P10-003 evaluator run, W12.4B CI evaluators; accepted baselines re-based, nothing restored.
- **Partly addressed:** Disclosed; evaluators hardened
- **Remains:** Baselines re-based, not restored
- **Candidate impact:** None directly · **Security/privacy:** None identified · **Release impact:** None recorded
- **Dependencies:** None recorded · **Owner decisions:** None recorded
- **Required for closure:** See H-RESCACHE

### Category N: Candidate journey and submission consistency (13 active)

#### DI-N-001: No candidate control to invite members or share a report or story
- **Original:** `CJ-D-01` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-01 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** MEDIUM · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** The candidate interface cannot invite members or share a report or story (create, list, accept, leave and revoke exist). CLAIM-017 is only partly reachable.
- **Remains:** The candidate interface cannot invite members or share a report or story (create, list, accept, leave and revoke exist). CLAIM-017 is only partly reachable.
- **Candidate impact:** sharing is reachable only through the API and the Workspaces page, not from a report or story · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-N-002: Pricing page versus account page wording for Premium
- **Original:** `CJ-D-02` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-02 · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** The pricing page presents Premium at EUR 19.99 per month while the account page says Premium is a preview with nothing to buy.
- **Remains:** A preview label now exists on the pricing page (frontend/components/marketing/PricingContent.tsx); consistency with the account page was not re-verified in this wave.
- **Candidate impact:** possible expectation of a purchasable plan · **Security/privacy:** none identified · **Release impact:** commercial claims discipline
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-N-004: 'Reviewed by you' provenance badge not rendered; no AI-suggested story path
- **Original:** `CJ-D-05` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-05 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** The provenance kind is defined but not rendered as a Prepare badge and no interface path creates an AI-suggested story.
- **Remains:** The provenance kind is defined but not rendered as a Prepare badge and no interface path creates an AI-suggested story.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-N-005: Opportunity fields other than status cannot be edited after creation
- **Original:** `CJ-D-06` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-06 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Only status is editable in the interface.
- **Remains:** Only status is editable in the interface.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-N-006: No provider-specific failure copy
- **Original:** `CJ-D-07` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-07 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Failures use generic safe messages.
- **Remains:** Failures use generic safe messages.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-N-007: Dictation language is per device, not per account
- **Original:** `CJ-D-08` · **Source:** docs/capstone/journeys/CANDIDATE_JOURNEY.md D-08 · **First recorded:** 2026-10-19
- **Status:** DEFERRED — POST SUBMISSION · **Severity:** LOW · **Priority:** P2 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** The dictation language does not follow the account across devices.
- **Remains:** The dictation language does not follow the account across devices.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** none
- **Required for closure:** see description

#### DI-N-008: Acceptance criteria dispositions are P9-era and spread over three documents
- **Original:** `IR-AC-LEDGER` · **Source:** docs/capstone/INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 6 · **First recorded:** 2026-10-19
- **Status:** OPEN — PRE-SUBMISSION QUALIFICATION · **Severity:** MEDIUM · **Priority:** P0 · **Blocks submission:** YES · **Blocks production:** NO
- **Description:** The P9 ledger, the requirements matrix and the roadmap disagree (AC-03 PARTIAL vs PASS; AC-24 NOT RUN vs PARTIAL; totals stale) and later live evidence (P10E, W12.4E) was never folded back; AC-03 and AC-18 may have been closed by later waves but are not re-dispositioned.
- **Remains:** Proposed single current ledger written (CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md, 17 PASS / 8 PARTIAL; AC-03 and AC-18 investigated and kept PARTIAL). Owner approval of the ledger as the single record is still outstanding.
- **Candidate impact:** none · **Security/privacy:** none identified · **Release impact:** AC-25 submission consistency
- **Dependencies:** owner confirmation of the reconciled dispositions · **Owner decisions:** REQUIRED: approve CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md as the single current acceptance record
- **Required for closure:** One current dispositions table agreed by the owner; documents consistent (eval_doc_consistency)

#### DI-N-011: No dedicated RC-P10-004 entry-criteria specification existed
- **Original:** `IR-RC004-SPEC` · **Source:** docs/capstone/INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 17 · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P0 · **Blocks submission:** YES · **Blocks production:** NO
- **Description:** Conditions were scattered across documents. This requalification records the entry conditions (section 17 of its report); creation still needs a separate owner approval.
- **Remains:** Entry criteria reconstructed in RC_P10_004_ENTRY_DECISION.md (E1 to E16); recommendation NO-GO now; E13 (recording a failed internal gate) and E14 (are live or human items mandatory) are undefined; separate owner approval to create the RC is outstanding.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** see status
- **Dependencies:** none · **Owner decisions:** REQUIRED: approve or amend the recorded entry conditions; separate approval to create RC-P10-004
- **Required for closure:** see description

#### DI-N-012: AC-03 has no test for two-opportunity context selection, restart persistence or legacy-row non-adoption
- **Original:** `IR-AC03-TESTS` · **Source:** docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** NO
- **Description:** The original AC-03 clauses (two opportunities, persistence after restart, correct chosen context, old anonymous records not silently reassigned) are only partly evidenced; the composite durable profile has no single restart test.
- **Remains:** One offline pytest on a file database (app built twice): two opportunities for one user persist, each context endpoint returns its own data and 404 for another user, a launched session carries only its opportunity and an explicit field overrides it; plus a NULL-owner legacy row that a new user neither sees nor owns.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** acceptance record
- **Dependencies:** none · **Owner decisions:** REQUIRED: accept PARTIAL with the disclosed gap or fund a small test wave
- **Required for closure:** The test file passing and the ledger row re-dispositioned by the owner

#### DI-N-013: AC-18: no owner-scoped list of recent agent runs; selected-run retrieval evidence not shown to be bounded
- **Original:** `IR-AC18-RUNLIST` · **Source:** docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** UNKNOWN · **Blocks production:** NO
- **Description:** No GET /agent/runs route or UI list exists (matrix A6 ABSENT, confirmed in code); the Inspector needs a pasted run id; selected-run retrieval evidence is a summary (A8); W9.3 made review surfaces admin-only; the empty evaluation-artifact state is untested.
- **Remains:** Owner-scoped, paginated, capped run-list endpoint and Inspector list with tests (user A sees only own runs, Admin sees none of A's), plus a test of capped selected-run evidence and the empty artifact state. A feature change, not done in the documentation wave.
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** acceptance record
- **Dependencies:** none · **Owner decisions:** REQUIRED: accept PARTIAL with the disclosed gap or schedule a small feature wave
- **Required for closure:** Endpoint, UI and tests; owner re-disposition

#### DI-N-014: Course deadline and time zone are unconfirmed (planning documents say 2026-10-20)
- **Original:** `IR-DEADLINE` · **Source:** docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** HIGH · **Priority:** P0 · **Blocks submission:** YES · **Blocks production:** NO
- **Description:** All deadline statements are second-hand (the project's runbook); the date of this register is 2026-10-19; no official source is in the repository.
- **Remains:** Not in the official brief; still unconfirmed (planning documents say 2026-10-20, second-hand).
- **Candidate impact:** none directly · **Security/privacy:** none identified · **Release impact:** acceptance record
- **Dependencies:** none · **Owner decisions:** REQUIRED: confirm the deadline and time zone
- **Required for closure:** Owner confirmation recorded in the P11 plan

#### DI-N-015: A working copy with .env or .streamlit/secrets.toml makes the local backend contact the provider even with PYTHON_DOTENV_DISABLED or an emp…
- **Original:** `IR-DEMO-KEY` · **Source:** docs/capstone/submission/REHEARSAL_AND_FREEZE_LOG.md · **First recorded:** 2026-10-19
- **Status:** PARTIALLY REMEDIATED · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** Found in the P11 rehearsal: the backend started from the working copy loaded the OpenRouter key (also available through Streamlit secrets) and answered /agent/run with a real model reply. Neither PYTHON_DOTENV_DISABLED=1 nor an empty OPENROUTER_API_KEY prevents it.
- **Remains:** Documented workaround (start the backend from a fresh checkout, verified: no key, safe not-configured answer; README warning and demo guide). No code change: a real switch to disable key discovery for demonstrations (for example an explicit offline flag honoured by load_config and the Streamlit secrets reader) does not exist.
- **Candidate impact:** none directly · **Security/privacy:** a developer demonstration can spend on the owner's key without intending to · **Release impact:** demonstration safety and spend control
- **Dependencies:** none · **Owner decisions:** OWNER: whether to add an explicit offline switch in a later wave
- **Required for closure:** An explicit offline switch with a test that proves no provider key is read when it is set

#### DI-N-016: The developer database is 12 Alembic revisions behind the code head
- **Original:** `IR-DEVDB-STALE` · **Source:** docs/capstone/submission/REVIEW_DAY_READINESS.md · **First recorded:** 2026-10-19
- **Status:** PENDING OWNER DECISION · **Severity:** MEDIUM · **Priority:** P1 · **Blocks submission:** NO · **Blocks production:** NO
- **Description:** data/interview_studio.db is at 0027_email_attempts while the code head is 0039_speech_governance; it has 1 retired governed source and no active one. Found while diagnosing the empty Admin Sources page; not modified.
- **Remains:** Back up and migrate (alembic upgrade head) or keep using the isolated review environment.
- **Candidate impact:** a developer running the current code against it would fail or see stale state · **Security/privacy:** none identified · **Release impact:** local development and demonstration
- **Dependencies:** backup first · **Owner decisions:** REQUIRED: migrate the developer database or leave it
- **Required for closure:** Backup taken, migration run, Admin readiness verified

## 6. Reconciliation: issues verified CLOSED

Listed so earlier findings are not reopened or lost. Each cites its evidence; a closure applies only to the scope stated.

| ID | Original | Title | Evidence of closure |
|---|---|---|---|
| DI-A-055 | C-A1 | OEWS data dictionary / field semantics (precondition J,K) unverified | P10C_F2A_US_SOURCE_ACQUISITION.md s8 (data_dictionary_validation.json; hashes verified by scripts/p10c_f2a_acquisition_gate.py --verify-hashes) |
| DI-A-056 | C-A2 | Isolated ingestion environment (precondition M) unverified | P10C_F2A_US_SOURCE_ACQUISITION.md s8; P10C_F2A_CAPSTONE_ENGINEERING_CLOSURE.md s2 (fresh SQL counts 1,447/1,424, 16,140) |
| DI-A-057 | C-A3 | Reliability threshold for PRSE-based qualification | P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md M.4 POLICY I |
| DI-A-058 | C-A4 | Package 1 files unacquired; registry transition for isolated DB | P10C_F2A_US_SOURCE_ACQUISITION.md s8; closure doc s2 (4 of 4 hashes match) |
| DI-A-059 | C-A5 | Research-cache evaluator isolation UNRESOLVED (roadmap) | P10D_GLOBAL_KB_AND_MULTILINGUAL_REQUALIFICATION.md s7 (developer caches unchanged, 37 files); roadmap row not updated |
| DI-A-060 | C-A6 | CI-reproducible knowledge evaluation fixture DESIGNED not implemented (roadmap) | P10C_G_GLOBAL_EVALUATION_AND_REGRESSION.md (115 cases, 12 governance checks, determinism hash); ci.yml guard step |
| DI-B-010 | L-ANSWER-GUARD | Career Chat lacked occupation-grounding guard | src/copilot/service.py _apply_occupation_grounding (called inside _gather_evidence); tests/test_p10d_r1_grounding_coverage.py; W12_4E doc s16 'closed in P10D-R1' |
| DI-B-026 | B-HELPER | Agent helper pinned to code-default model slug (gpt-5.6-terra) | P10E-R1 s4-5: 0 of 90 R1 requests used an unexpected model; src/copilot/config.py and src/config.py resolve at call time; tests/test_p10e_r1_routing.py (9) |
| DI-B-027 | B-CAP4096 | 2,000 output cap blocked 5 of 22 agent cases | P10E_R1 s1-2, s6-7; evaluations/p10e/authorization.json v3 |
| DI-B-028 | B-XLANG-HARNESS | Non-English retrieval gap and mixed de/fr scaffold reported as product findings | P10E_R1 s16 (tests test_the_corrected_path_localizes_the_synthesis_instructions_and_retrieves_evidence, run c896ab9b); product defects: none confirmed |
| DI-C-020 | C-INT-HARNESS | Interview quality harness and personas did not exist (P10E) | P10E_R1 s8; evaluations/p10e/r1/interview_cases.json sha256 385625...; run p10e-interview-quality-20261019T095118Z-dc326e60 |
| DI-C-021 | C-AGENT-EVID | Harness: agent completion inflated; no per-case evidence (defects E,F) | P10E_R1 s16.2; src/agent/live_eval.py; tests/test_agent_live_eval.py |
| DI-D-017 | D-C1 | Cross-geography figure authorised by foreign evidence | grounding_policy.enforce scope-aware corpus; tests/test_candidate_grounding_policy.py; merged as PR #203 (main fb2d264); full backend 5,036 passed (R2 s11.4) |
| DI-D-018 | D-C2 | Citation marker exempted estimate-offer guard | tests/test_candidate_grounding_policy.py (cited offer removed in 7 languages); merged as PR #203 (main fb2d264); full backend 5,036 passed (R2 s11.4) |
| DI-D-019 | D-C3 | External statistic without retrieval only labelled | src/agent/grounding.py runtime safeguard; tests; merged as PR #203 (main fb2d264); full backend 5,036 passed (R2 s11.4) |
| DI-D-020 | D-C4 | Citation/sources metadata inconsistent after marker removal | PolicyOutcome removed markers; consistency tests; merged as PR #203 (main fb2d264); full backend 5,036 passed (R2 s11.4) |
| DI-D-021 | D-ABST-CIT | Citations on abstentions presentation decision | R2 s1A decision; policy A implemented in src/copilot/security/grounding_policy.py; 7/7 ABSTENTION_WITH_CONTEXTUAL_CITATIONS live (pre-correction) |
| DI-F-013 | PRIV-EXPORT-D03 | Export carries stale legal-acceptance wording | Closed in the integrated requalification: the export no longer hard-codes legal_acceptance recorded False (derived from the real acceptance records) and the stale 'does not record it yet' scope line is removed; tests/test_integrated_requalification.py::test_t… |
| DI-G-001 | F-01 | Review/Diagnostics outside Admin shell | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md; frontend/tests/admin-ux-w12-5.test.tsx; frontend/e2e/admin-ux-w12-5.spec.ts; frontend/app/review/layout.tsx exists |
| DI-G-003 | F-03 | Admin navigation at 390 px too tall | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md; frontend/tests/admin-ux-w12-5.test.tsx; frontend/e2e/admin-ux-w12-5.spec.ts |
| DI-G-004 | F-04 | Integrations mobile overflow/clipping | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md; frontend/tests/admin-ux-w12-5.test.tsx; frontend/e2e/admin-ux-w12-5.spec.ts |
| DI-G-005 | F-05 | Billing forms off screen, focus not moved | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md; frontend/tests/admin-ux-w12-5.test.tsx; frontend/e2e/admin-ux-w12-5.spec.ts |
| DI-G-010 | F-10 | Plans and Billing relationship unexplained | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (FIXED, Plans side) |
| DI-G-013 | F-13 | No secret-rotation control | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4; W12_04B_SECURE_PROVIDER_SECRET_ADMINISTRATION.md; secret-admin-w12-4b tests |
| DI-G-014 | F-14 | Development anonymous account in Users list | docs/capstone/admin/W12_5_ADMIN_UX_CORRECTIONS.md section 4 (OUT OF SCOPE); tests/test_auth_failclosed.py exists |
| DI-G-028 | G-A5 | Knowledge-readiness distinction (A5) | W12.4A section 3; PLATFORM_ADMIN_JOURNEY.md A-05 |
| DI-G-030 | A-10 | Capability matrix lacked email row | docs/capstone/admin/ADMIN_CAPABILITY_MATRIX.md line 47 |
| DI-H-016 | H-SESSION-STORE | In-memory session store blocks multi-replica (p8 section 15) | src/api/dependencies.py get_session_store; src/interview/session_repository.py |
| DI-H-017 | H-PAUSE | Process-local pause switch (p8 section 15; SEC-W10-05) | docs/capstone/admin/W10_11_FEATURE_FLAGS_SAFE_PLATFORM_CONFIGURATION.md; R-73 |
| DI-H-041 | PA-A-01 | Knowledge Base accessibility (owner-reported) | Root causes fixed in W12.4A (anchored data root; agent shares the governed retriever). Residual operator action: register and activate a governed source and run the worker. |
| DI-H-042 | PA-A-02 | No writable credential store | W12.4B encrypted SecretStore (opt-in); step-up and audit. |
| DI-H-043 | PA-A-05 | Knowledge readiness, inventory and retrieval test missing | W12.4A readiness, inventory and retrieval-only test. |
| DI-I-021 | I-RECOVER-PERM | Billing recovery permission decision | src/api/routes/admin_billing_ops.py (perm.BILLING_RECOVER); F1R doc |
| DI-K-016 | K-PRIV-W9 | PRIV-W9-02 consent/legal acceptance history not stored | R-48 PASS; tests/test_privacy_legal_w10_10.py; scripts/eval_admin_privacy_legal.py; docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md |
| DI-M-001 | TD-W9-01 | Invalid Tailwind colour-token opacity classes | P10B_W9_12_ENGINEERING_QUALITY.md sections 3-6; frontend/tests/tailwind-token-opacity.test.ts |
| DI-M-002 | TD-W9-02 | Backend test-isolation leak and 13 .env failures | P10B_W9_12_ENGINEERING_QUALITY.md sections 7-12; tests/test_test_isolation.py |
| DI-M-004 | SEC-W10-01 | Account deactivation did not revoke sessions | docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 46; W10.2 PR #113 |
| DI-M-005 | SEC-W10-02 | Privileged audit not fail-closed/atomic | docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 46; W10.1 PR #110 |
| DI-M-006 | SEC-W10-03 | Non-canonical audit events/no request id/no denial audit | docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 46; W10.1 PR #110 |
| DI-M-007 | SEC-W10-04 | Privacy request queue non-operational | docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 46; W10.10 PR #122 |
| DI-M-008 | SEC-W10-05 | Process-local pause | docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 46; W10.11 PR #125 |
| DI-M-009 | SEC-W10-06 | /admin/providers echoed raw provider values | docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md section 46; W10.1 PR #110 |
| DI-M-010 | ROLE-W10-01 | platform_admin completeness / role scope | W10_14 section 46; P10B_RELEASE_ACCEPTANCE_MATRIX.md R-55, R-56 |
| DI-M-011 | PRIV-W9-01/02 | PRIV-W9-01 and PRIV-W9-02 closure cross-reference | W10_14 section 46; privacy.md |
| DI-M-024 | M-BASELINE-EVALS | Four baseline evaluators failing on main (P4-A) | P5_B section 32 |
| DI-M-025 | M-F109 | Reporting test clock pinned to 2026-10-15 (F1-09) | W12_04D_F1_BILLING_SECURITY_QUALIFICATION.md F1-09 |
| DI-M-026 | M-EVAL-WRITES | Evaluators rewrote committed artifacts | P10B_W9_12 section 22-23 |
| DI-M-037 | M-TODO-CODE | TODO/FIXME in source code | grep result |
| DI-M-039 | M-LATENT-RES | Evaluation corrections preserve historical evidence | P10E_R1 section 16 |
| DI-N-003 | CJ-D-04 | PRODUCT_CLAIMS.md contains stale entries | Reasons updated in docs/product/PRODUCT_CLAIMS.md in the integrated requalification; the claims themselves stay NOT permitted. |
| DI-N-009 | IR-ROADMAP-STALE | Roadmap and phase plan described merged PRs as pending | Status rows reconciled in the integrated requalification (roadmap and phase plan). |
| DI-N-010 | IR-P12 | A P12 (final rehearsal and freeze) exists in the reference runbook but not in the phase p… | Owner direction 2026-10-19 (final capstone acceptance reconciliation prompt): fold the rehearsal, final validation and submission-freeze duties into P11; no top-level P12 unless authoritative course requirements require it. Recorded in P11_SUBMISSION_READINES… |

## 7. Method and limits

1. Sources read by programmatic search of `docs/` and `CLAUDE.md` for DEFERRED, POST-SUBMISSION, NOT VERIFIED, NOT RUN, NOT QUALIFIED, NOT APPROVED, PARTIAL, BLOCKED, OPEN, PENDING, TODO, FIXME, KNOWN LIMITATION and TECHNICAL DEBT, then reviewed by meaning and reconciled against later documents and the current code. No TODO/FIXME exists in source code (the only TODO table is the historical `docs/quality_optimisation_audit.md`).
2. The P10C-F2A backlog items 1 to 19 and the 18 W12.4E activation items are individual rows (`BL-1` to `BL-19`, `W12.4E-1` to `W12.4E-18`); the BL-6 alias reviews are split per alias. Items first recorded under two names are merged under one `DI-` identifier with the other names listed as aliases.
3. Severity and priority are copied from the source where it rates the item and are otherwise a research assessment; they are not owner decisions.
4. Not verified in this wave: whether any reviewer account is a real named person; whether ASHE revised 2025 data is published; live behaviour of the PR #203 policy corrections; the current code state of L-STALE-1, L-CODE-1 and L-ROUTE-1 beyond the research spot checks.
5. Source-document contradictions found are recorded in the requalification report (section 16) rather than silently resolved.
