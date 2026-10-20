# Production Acceptance Matrix (V2.2)

**Status:** PROPOSED, generated 2026-10-21. No production gate has passed. This matrix does not upgrade any capstone result: the capstone acceptance ledger (17 PASS, 8 PARTIAL, coverage gate 386/412 FAIL, AC-24 PARTIAL, human-qualified coverage 0 of 412) stays as recorded.

## 1. General production gates (R1.0)

| Gate | Requirement | Evidence required | State |
|---|---|---|---|
| PG-01 | Hosted deployment rehearsed: TLS and HSTS, migration, backup and restore, rollback, pause | Rehearsal record on an authorised hosted environment | NOT RUN (EX-12 and related issues) |
| PG-02 | Identity: live verification email and password recovery; Google sign-in either validated or disabled | Owner-authorised live round trip | NOT RUN |
| PG-03 | AI security: injection, grounding and abuse suites pass in all seven languages | Per-language suite results at the release SHA | PARTIAL (English and some multilingual fixtures offline) |
| PG-04 | Privacy and data rights verified; legal documents qualified in each language before real-user access | Counsel sign-off per language; privacy suites | NOT MET (engineering drafts) |
| PG-05 | Knowledge sources for the seven markets qualified (licence, authority, coverage); coverage gate handled honestly | Source approval register; coverage report (gate currently FAILS) | NOT MET |
| PG-06 | Candidate journeys pass in each language | Per-language journey evidence | NOT RUN per language |
| PG-07 | Human validation: named reviewers; native-language review; AC-24 human items | Signed reviews | NOT MET (no reviewer named) |
| PG-08 | Admin: permissions, audit, no candidate-content access, English-only | Admin matrix and route invariant | PASS offline at capstone scope; Admin 2.0 requirement text outstanding |
| PG-09 | Operations: monitoring, alerting, incident process, resilience under load | Runbook rehearsal and load evidence | NOT RUN |
| PG-10 | Deferred features stay disabled (all gate constants False) and no public claim exceeds evidence | scripts/production/reconcile_issues.py check; claims gate | MET at this SHA (checked by the reconciliation) |
| PG-11 | Backlog reconciliation: every active issue has a valid disposition; zero unmapped | scripts/production/reconcile_issues.py check | MET (machine-checked) |

## 2. Per-language gates

A language is production-qualified only when ALL of LG-01..LG-14 pass for it. Today none do. States below are the honest current evidence class, not a pass.

| Gate | Meaning | English | German | Spanish | Italian | Portuguese | French | Dutch |
|---|---|---|---|---|---|---|---|---|
| LG-01 | Locale audit complete | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| LG-02 | Interface text complete | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) | ENGINEERING DRAFT (key parity enforced; unreviewed) |
| LG-03 | Candidate journeys pass | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language |
| LG-04 | Prompts and policies verified | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) |
| LG-05 | Interview quality validated | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| LG-06 | Multilingual RAG and attribution | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) | NOT RUN (English-keyword routing known) |
| LG-07 | Language never sets the country | OFFLINE separation tests; mapping unapproved | OFFLINE separation tests; mapping unapproved | OFFLINE separation tests; mapping unapproved | OFFLINE separation tests; mapping unapproved | OFFLINE separation tests; mapping unapproved | OFFLINE separation tests; mapping unapproved | OFFLINE separation tests; mapping unapproved |
| LG-08 | Injection, security and privacy suites | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) | PARTIAL (offline fixtures) |
| LG-09 | Story Bank and Workspaces | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language | NOT RUN per language |
| LG-10 | Legal and privacy translation qualified | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) | NOT MET (engineering drafts) |
| LG-11 | Native-language human review | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) | NOT MET (no reviewer) |
| LG-12 | Mo language ownership | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) | PARTIAL (offline) |
| LG-13 | Readiness tracked, no aggregate claim | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED |
| LG-14 | Boundaries | NOT MET (Russian still exposed) | NOT MET (Russian still exposed) | NOT MET (Russian still exposed) | NOT MET (Russian still exposed) | NOT MET (Russian still exposed) | NOT MET (Russian still exposed) | NOT MET (Russian still exposed) |

German has some governed knowledge-base content; the other languages have none beyond the curated corpus. Per-language rows will diverge as evidence is gathered.

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
