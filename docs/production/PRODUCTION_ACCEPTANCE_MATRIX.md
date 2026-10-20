# Production Acceptance Matrix (V2.2, corrected)

**Status:** corrected 2026-10-21. No production gate has passed. This matrix does not upgrade any capstone result: the capstone acceptance ledger (17 PASS, 8 PARTIAL), the historical 95% coverage gate (386 of 412 against 392, FAIL), AC-24 PARTIAL and human-qualified coverage 0 of 412 stay as recorded. A mandatory safety, privacy, licensing or operational gate cannot be bypassed by recording an accepted limitation; the owner may remove a feature from scope or delay its activation. Numeric thresholds are not yet approved (OD-GATE-THRESHOLDS); states below are honest current states, not passes.

## 1. Production gates for R1.0 (free private beta)

| Gate | Name | Measurable requirement | Evidence | State |
|---|---|---|---|---|
| PG-01 | Secure hosted deployment | Hosted staging and production exist on an owner-authorised provider: TLS and HSTS verified, secrets only in the managed store, CORS fail-closed, no development bypass headers accepted, hosted rehearsal repeated from a clean checkout | Rehearsal record at the release SHA; scripts/eval_hosting_readiness.py | NOT RUN (OD-HOSTED) |
| PG-02 | Identity and account lifecycle | Invitation-only registration enforced server-side; live verification email and password recovery round trip; sessions revoked on deactivation; account closure and deletion complete; Google sign-in validated or disabled | Live round trip under owner authorisation; auth, invitation and deletion suites | NOT RUN (REQ-BETA-01 not started) |
| PG-03 | Injection defence and tool safety | REVIEW-01 R1 to R6 complete: labelled corpus including direct, indirect, multilingual, encoded and retrieved-document attacks; detection and benign false-positive rates reported per language and above the owner-approved thresholds on a frozen held-out set (OD-GATE-THRESHOLDS); injection-risk score on every RetrievalResult; high-risk chunks excluded before context; tool calls re-authorised before side effects; no cross-user disclosure | Held-out corpus run in CI; tool-authorization and cross-user negative tests | NOT MET (heuristics only) |
| PG-04 | Privacy, legal and data rights | Privacy requests, export, deletion and retention verified; legal documents qualified in each offered language before real-user access; third-party provider data handling reviewed (K-PROVIDER); no GDPR or legal-compliance claim without qualified review | Counsel sign-off per language; privacy suites | NOT MET (engineering drafts) |
| PG-05 | Persistent Knowledge Sources and embedding/index integrity | REQ-OWN-05 K1 to K9 and REVIEW-04 R1 to R7 complete: sources survive restart, redeployment and separate-environment restore; manifest records embedding identity and checksums; mismatch detected and refused; no silent hash-embedding fallback in production; genuine malware scanning; alerts | Restart, redeploy and restore drills; manifest and mismatch tests; retrieval and citation provenance tests | NOT MET |
| PG-06 | Candidate end-to-end reliability | REQ-CAND-01: a real browser journey per language passes against a staging stack, including Start interview; provider outage yields an accurate recoverable message; REVIEW-05 streaming with cancellation works and the synchronous fallback is tested; availability and latency targets (OD-GATE-THRESHOLDS) met over a rehearsal | Playwright journeys; outage simulation; SSE contract tests | NOT RUN |
| PG-07 | Independent human AI evaluation | Named independent reviewers rate a frozen sample of interview questions, feedback and Mo answers per language against a written rubric; results reported with sample size; RAGAS is secondary and never presented as human-verified | Signed rating records; blinded protocol results | NOT MET (no reviewer named; AC-24 PARTIAL; human-qualified coverage 0 of 412) |
| PG-08 | Admin 2.0 functionality | REQ-OWN-01, 02, 03, 04, 08 complete: navigation, Command Center, plans, users, reports; permission matrix and route invariant unchanged; Admin still has no path to private candidate content | Admin Playwright specs; permission matrix; sentinel tests | PARTIAL foundations; Admin 2.0 NOT MET |
| PG-09 | Observability, resilience, backup, restore and rollback | Monitoring and alerting live for API, worker, indexing and provider health; backup and restore drilled for database, files and indexes; rollback of a release and of a prompt or plan version rehearsed; incident process documented and tested | Drill records; alert tests; runbook rehearsal | NOT RUN |
| PG-10 | Deferred and paid features disabled | Every gate constant in `gate_constants` is False; for each gated family a test proves the UI entry and the API route are unreachable (REQ-DEFER-01); no payment route is reachable; Russian is absent from active selection | reconcile_issues.py check; consolidated UI plus API inaccessibility suite | PARTIAL: constants checked False; UI/API suite not written; Russian still exposed |
| PG-11 | Complete issue reconciliation | Every historical and new item has a valid disposition and release; zero unmapped; history, closure evidence and failed historical gates preserved verbatim | reconcile_issues.py check and tests | MET (machine-checked) |
| PG-12 | Prompt versioning, provenance and registry parity | REVIEW-02 R1 to R7 and REVIEW-03 R1 to R6 complete: versioned prompt assets with declared versions and hashes; effective versions recorded on runs and evaluations; rollback without code change; one authoritative tool catalogue with parity tests and an unchanged tool set | Loader, rollback, parity and attribution tests | NOT MET |
| PG-13 | Story Bank and Workspaces | REQ-OWN-06 and REQ-OWN-07 acceptance journeys pass in the browser, including restart persistence and immediate revocation; authorization verified at the API boundary; verified in all seven languages (LG-09) | Playwright journeys; API authorization tests | PARTIAL foundations; journeys NOT RUN |
| PG-14 | Reports and safe analytics | REQ-OWN-04 complete: every metric traceable to a query and denominator; small-cohort suppression; missing data never shown as zero; custom builder accepts only registered metrics and dimensions; no arbitrary SQL; exports permissioned | Metric tests; suppression tests; builder guard test | PARTIAL foundations; NOT MET |
| PG-15 | Free beta operational acceptance | Invited beta users can register, practise and recover from errors; support process, abuse handling, data-rights handling and on-call ownership defined; no payment taken; owner signs a go/no-go with the evidence at one SHA | Owner go/no-go record; beta runbook rehearsal | NOT RUN |

## 2. Per-language gates (LG-01 to LG-14, each of seven languages)

A language is activated for real users only when ALL fourteen gates pass for it; a failed mandatory gate prevents activation in that locale. Today none passes. Per-language reporting is kept; there is no aggregate claim.

| Gate | Meaning | English | German | Spanish | Italian | Portuguese | French | Dutch |
|---|---|---|---|---|---|---|---|---|
| LG-01 | Locale audit complete | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| LG-02 | Interface text complete | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) |
| LG-03 | Candidate journeys pass | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language |
| LG-04 | Prompts and policies verified | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) |
| LG-05 | Interview quality validated | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| LG-06 | Multilingual RAG and attribution | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) |
| LG-07 | Language never sets the country | OFFLINE separation tests; markets unapproved | OFFLINE separation tests; markets unapproved | OFFLINE separation tests; markets unapproved | OFFLINE separation tests; markets unapproved | OFFLINE separation tests; markets unapproved | OFFLINE separation tests; markets unapproved | OFFLINE separation tests; markets unapproved |
| LG-08 | Injection, security and privacy suites | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) |
| LG-09 | Story Bank and Workspaces | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language |
| LG-10 | Legal and privacy translation qualified | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) |
| LG-11 | Native-language human review | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) |
| LG-12 | Mo language ownership | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) |
| LG-13 | Readiness tracked, no aggregate claim | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED |
| LG-14 | Boundaries | NOT MET (Russian still selectable) | NOT MET (Russian still selectable) | NOT MET (Russian still selectable) | NOT MET (Russian still selectable) | NOT MET (Russian still selectable) | NOT MET (Russian still selectable) | NOT MET (Russian still selectable) |

German has some governed knowledge-base content; the other languages have none beyond the curated corpus. Rows diverge as per-language evidence is gathered.

## 3. Capstone acceptance criteria that are not PASS (carried, not upgraded)

| AC | Historical state | Handling | Tracked by |
|---|---|---|---|
| AC-03 | UNKNOWN | TRACKED by register issue(s) | IR-AC03-TESTS |
| AC-13 | UNKNOWN | TRACKED by register issue(s) | W12.4E-1, W12.4E-10, W12.4E-11, W12.4E-12, W12.4E-13 |
| AC-18 | UNKNOWN | NEW ISSUE XC-AC-AC-18 (no register issue found) | XC-AC-AC-18 |
| AC-19 | UNKNOWN | TRACKED by register issue(s) | G-CONTRAST, G-HDR-390, G-SR, P2-09 |
| AC-22 | UNKNOWN | TRACKED by register issue(s) | B-SEMCAL |
| AC-23 | UNKNOWN | NEW ISSUE XC-AC-AC-23 (no register issue found) | XC-AC-AC-23 |
| AC-24 | UNKNOWN | NEW ISSUE XC-AC-AC-24 (no register issue found) | XC-AC-AC-24 |
| AC-25 | UNKNOWN | NEW ISSUE XC-AC-AC-25 (no register issue found) | XC-AC-AC-25 |

## 4. Historical gates preserved

The original 95% product-coverage gate keeps its failed result. A separate frozen, qualified R1.0 beta-scope coverage measure is required (REQ-COV-01, OD-COVERAGE) and is always reported beside, never instead of, the historical result.
