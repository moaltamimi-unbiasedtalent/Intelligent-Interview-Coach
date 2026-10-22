# Wave 3 Execution Plan

Recorded 2026-10-22 by the Technical Programme Lead after the Wave 2 reconciliation. Strategy S1 (full R1.0 scope, owner-approved). Target 30 November 2026, conditional on every mandatory gate. **Nothing in Wave 3 has been started.** This document is the reconciled baseline and the execution plan the owner is asked to approve; implementation starts only on that approval. No feature is postponed, no test is weakened and no launch gate changes: a gate that is not met moves the date, not the scope.

## 1. Verified baseline (read from the repository and GitHub, not from memory)

- `main` is `e4aed13` (merge of PR #233). No PR is open.
- Merged in Wave 2 (all with green GitHub CI): #222 prep (version-independent head checks), #223 01A, #224 03D1, #225 Wave 2 docs, #226 02C, #227 02B, #228 04E, #229 06H, #230 03B, #231 03C, #232 03E1, #233 04B, #234 04A. Wave 1: #213 to #221.
- Alembic: one head, `0043_story_bank_completion`; chain 0040, 0041 (03E1), 0042 (04E), 0043 (04A), verified with the repository head helper.
- Validators on `main`: `reconcile_issues.py check` passes (452 items, 0 unmapped, history preserved); `execution_packages.py check` passes (45 packages, every R1.0 fix/verify item in exactly one package, acyclic).
- Key merged files were confirmed present (prompt assets, knowledge identity and manifests, clamd client, language activation, command-center, report builder, plans admin, user guards, invitations, stories routes).
- CI on the `main` push for `e4aed13` (re-read 2026-10-22): all 10 check runs completed with success (four Python shards, Python tests & checks, evaluators and guards, evaluation extras, static guards, frontend tests and build, legacy live component). A push run lists fewer checks than a PR run (no Playwright or Streamlit smoke entry), so the final PR heads with 12 of 12 successful checks remain the stronger evidence for those two.
- Known issue, unchanged: `test_knowledge_persistence_02a_identity::test_no_forbidden_files_were_touched_and_no_migration_in_part_one` is a branch-relative test that fails on any local tree containing later merges and passes in CI; a follow-up task to make it merge-safe is open.

## 2. Reconciliation of the 45 packages

| Group | Count | Packages |
|---|---|---|
| Code merged to `main` (engineering complete for its offline scope) | 19 | 01A, 01B0, 01B, 02K, 02A, 02B, 02C, 03A, 03B, 03C, 03K, 03D1, 03E1, 04A, 04B, 04E, 05A, 06A, 06H |
| Governance packages, partly delivered | 2 | 00A (sign-off recorded, appointments and decisions open), 00B (proposal delivered, owner disposition open) |
| Not started | 24 | 01C, 01D, 02D, 02E, 03D2, 03E2, 04C, 04D, 04F, 05B, 05C, 05D, 05E, 06B, 06C, 06D, 06E, 06F, 06G, 07A, 07B, 07C, 08A0, 08A |

**"Engineering complete" is not "accepted".** Several merged packages state limits that stay open: 02B has no production-embedder benchmark; 02C has only a fake clamd; 02A and 05A were never run on hosted volumes; 04E has no invitation email; 04A has no per-story consent in Prepare; 03C has no bulk actions; 03E1 exports only CSV and JSON; 01A's held-out detection (77.3%, weakly contaminated) has no approved threshold and no human security review; 06H has qualified no language.

## 3. Five separate layers of status

A package is finished only when all five layers are. The layers are never merged into one claim: (1) engineering = code merged on `main`; (2) CI = GitHub checks green; (3) live staging = verified on a hosted staging stack (nothing is deployed, so every live cell is NOT RUN); (4) human qualification = named reviewers, counsel, evaluators and owner decisions; (5) production-gate acceptance = the PG and LG gate in the acceptance matrix passes with an evidence artefact. Today **no production gate is PASS** except PG-11 (machine-checked reconciliation), and no language is qualified.

<!-- MATRIX:START -->
| Package | 1 Engineering | 2 CI | 3 Live staging | 4 Human qualification | 5 Production-gate acceptance |
|---|---|---|---|---|---|
| 00A | PARTIAL: Phase 00 sign-off recorded (PRs #211, #212, #213) | documentation PRs #211 to #213 merged, CI green | n/a | Owner names reviewers, counsel and legal qualifiers (OPEN) | PG-07 BLOCKED until reviewers are named |
| 00B | DELIVERED as a proposal (PRs #211, #212) | documentation PRs #211 to #213 merged, CI green | n/a | Owner disposition of the ten reclassifications (OPEN) | PG-11 PASS (machine-checked); no reclassification applied |
| 01A | MERGED (PR #223, merge 7549973) | PR CI green (12 of 12); re-read on main | NOT RUN (injection screen on hosted stack) | Human security review (9 questions); independent held-out author (OPEN) | PG-03 IN PROGRESS; thresholds unapproved (OD-GATE-THRESHOLDS) |
| 01D | NOT STARTED | no PR yet | n/a | Security review of tool authorization | PG-03 (REVIEW-01 R4/R5) |
| 01B0 | MERGED (PR #217, merge 0d75acd) | PR CI green (12 of 12); re-read on main | n/a | none | PG-12 IN PROGRESS |
| 01B | MERGED (PR #220, merge 335d303) | PR CI green (12 of 12); re-read on main | NOT RUN (Docker image with prompts/ not built) | none | PG-12 IN PROGRESS (01D, 01C outstanding) |
| 01C | NOT STARTED | no PR yet | n/a | none | PG-12 (REVIEW-03) |
| 02K | MERGED (PR #215, merge 657e456) | PR CI green (12 of 12); re-read on main | n/a | none | PG-05 IN PROGRESS (contract) |
| 02A | MERGED (PR #221, merge 191cbc5) | PR CI green (12 of 12); re-read on main | NOT RUN (hosted volumes, PostgreSQL, multi-worker; OD-HOSTED) | none | PG-05 IN PROGRESS |
| 02B | MERGED (PR #227, merge 6acdbc1) | PR CI green (12 of 12); re-read on main | NOT RUN (production embedder, hosted refusal; OD-HOSTED, OD-EMBED) | Embedder choice and benchmark approval (OD-EMBED, OD-BUDGET) | PG-05 NOT MET (retrieval quality unmeasured) |
| 02C | MERGED (PR #226, merge 568b8f3) | PR CI green (12 of 12); re-read on main | NOT RUN (real clamd, EICAR, outage drill; OD-HOSTED) | none | PG-05 IN PROGRESS |
| 02D | NOT STARTED | no PR yet | n/a | Licensing reviewer and owner; per-market signed approval (OPEN, long lead) | PG-05 (licence and market qualification) |
| 02E | NOT STARTED | no PR yet | NOT RUN | Frozen coverage measure approval (OD-COVERAGE); independent datasets | PG-05 (retrieval quality, coverage) |
| 03A | MERGED (PR #216, merge f921892) | PR CI green (12 of 12); re-read on main | NOT RUN (live Admin walkthrough) | none | PG-08 IN PROGRESS |
| 03B | MERGED (PR #230, merge a4f540d) | PR CI green (12 of 12); re-read on main | NOT RUN (live Admin walkthrough) | Plan limit values (OD-PLAN-LIMITS) | PG-08 IN PROGRESS |
| 03C | MERGED (PR #231, merge 6bcfbf5) | PR CI green (12 of 12); re-read on main | NOT RUN (live Admin walkthrough) | Bulk-action policy (OD-BULK-ACTIONS) | PG-08 IN PROGRESS |
| 03K | MERGED (PR #219, merge 20241f4) | PR CI green (12 of 12); re-read on main | n/a | none | PG-14 IN PROGRESS (contract) |
| 03D1 | MERGED (PR #224, merge ac029ad) | PR CI green (12 of 12); re-read on main | NOT RUN (live data) | none | PG-08 IN PROGRESS (03D2 outstanding) |
| 03D2 | NOT STARTED | no PR yet | NOT RUN | none | PG-08 |
| 03E1 | MERGED (PR #232, merge 0d84e7e) | PR CI green (12 of 12); re-read on main | NOT RUN (live data) | Export formats (OD-REPORT-EXPORT) | PG-14 IN PROGRESS (03E2 outstanding) |
| 03E2 | NOT STARTED | no PR yet | NOT RUN | Export formats (OD-REPORT-EXPORT) | PG-14 |
| 04A | MERGED (PR #234, merge 4d7e57a) | PR CI green (12 of 12); re-read on main | NOT RUN (restart on staging) | Native review of 116 strings (LG-10/11) | PG-13 IN PROGRESS (06B outstanding) |
| 04B | MERGED (PR #233, merge e4aed13) | PR CI green (12 of 12); re-read on main | NOT RUN (PostgreSQL invitation race and row locks) | Transfer rules (OD-WS-TRANSFER); native review | PG-13 IN PROGRESS (06B outstanding) |
| 04C | NOT STARTED | no PR yet | NOT RUN (streaming on staging) | none | PG-06 |
| 04D | NOT STARTED | no PR yet | NOT RUN (journeys on a staging stack) | none | PG-06 |
| 04E | MERGED (PR #228, merge a763fdf) | PR CI green (12 of 12); re-read on main | NOT RUN (first-admin bootstrap, live Google) | Invitation email and issuer decisions (OPEN) | PG-02 IN PROGRESS (05D outstanding) |
| 04F | NOT STARTED | no PR yet | NOT RUN (browser dictation check) | Legal reviewer and test participants | PG-04 |
| 05A | MERGED (PR #218, merge 9b6b109) | PR CI green (12 of 12); re-read on main | NOT RUN (nothing deployed; OD-HOSTED) | Hosting authorisation (OPEN) | PG-01 BLOCKED |
| 05B | NOT STARTED | no PR yet | NOT RUN (restore drill, PostgreSQL paths; OD-HOSTED) | none | PG-09 |
| 05C | NOT STARTED | no PR yet | NOT RUN (synthetic outage on staging; OD-HOSTED) | AI budget (OD-BUDGET) | PG-09 |
| 05D | NOT STARTED | no PR yet | NOT RUN (live Brevo, Google, Redis; OD-HOSTED) | none | PG-02 |
| 05E | NOT STARTED | no PR yet | n/a | Legal counsel sign-off per offered language (long lead) | PG-04 |
| 06A | MERGED (PR #214, merge f9a06a9) | PR CI green (12 of 12); re-read on main | n/a | Native review of the audit baseline | PG-10 IN PROGRESS; LG-01 and LG-14 evidence exists, none approved by a named human |
| 06B | NOT STARTED | no PR yet | NOT RUN (journeys per language) | Native-speaker review | LG-03, LG-09 per language; PG-13 |
| 06C | NOT STARTED | no PR yet | NOT RUN (live Mo quality) | Blinded native-reader rating (OD-BUDGET) | LG-04, LG-05 per language |
| 06D | NOT STARTED | no PR yet | NOT RUN (production embedder; OD-EMBED) | Sample review | LG-06 per language |
| 06E | NOT STARTED | no PR yet | NOT RUN | none | LG-08 per language; PG-03 |
| 06F | NOT STARTED | no PR yet | n/a | Seven native reviewers and legal qualifiers (calendar-bound, OPEN) | LG-10, LG-11 per language; PG-04 |
| 06G | NOT STARTED | no PR yet | NOT RUN (live Mo outputs) | Independent reviewers and participants (OD-BUDGET, OD-GATE-THRESHOLDS) | PG-07 BLOCKED |
| 06H | MERGED (PR #229, merge 5d588a1) | PR CI green (12 of 12); re-read on main | NOT RUN (hosted fail-closed behaviour) | Approvers named for each gate (OD-LANG-03/04) | PG-10 IN PROGRESS; LG-13/LG-14 enforcement merged, zero languages qualified |
| 07A | NOT STARTED | no PR yet | n/a | none | PG-10 |
| 07B | NOT STARTED | no PR yet | NOT RUN (live grounding; OD-BUDGET) | none | PG-03 |
| 07C | NOT STARTED | no PR yet | NOT RUN (live OCR sample; OD-BUDGET) | none | residual live verification |
| 08A0 | NOT STARTED | no PR yet | n/a | none | PG-15 (evidence pipeline) |
| 08A | NOT STARTED | no PR yet | NOT RUN | Owner go/no-go | PG-15 |
<!-- MATRIX:END -->

## 4. Wave 3 structure

### 4.1 Capacity, learned from Waves 1 and 2
Nine concurrent agents ran at once in Wave 2 and strained the machine (shared temp directories made some tests flaky under load; the fresh-dependency venv and the Playwright browser cache were removed by something outside the work). Wave 3 therefore caps concurrent implementation agents at **eight**, runs each full suite with at most four workers, and starts the next package as a slot frees. Owner review was fast (41 minutes to 3 hours 51 minutes from PR open to merge in Wave 1; 41 minutes to 3 hours 28 minutes in Wave 2) so review latency is not the constraint; integration hygiene is (12 rework rounds over 20 packages), so every Wave 3 PR is branched from the current `main` and re-merged before opening.

### 4.2 Streams and order
| Wave | Package | Stream | Depends on (all merged) | PRs | Why now |
|---|---|---|---|---|---|
| 3a | 08A0 | G evidence | none | 1 | Evidence collection must exist before more packages land; unblocks 08A |
| 3a | 05B | A platform | 05A, 02A, 02K | 1 | PG-09; offline drills and PostgreSQL paths now, live drills when OD-HOSTED |
| 3a | 05C | A platform | 05A | 2 (budget governor; monitoring and alerts) | PG-09; AI spend cap before any paid run (OD-BUDGET) |
| 3a | 05E | B privacy | none | 2 | PG-04; counsel is a long lead, engineering safeguards can land now |
| 3a | 06C | D language | 01B0, 06A | 1 | LG-04 and LG-05 harness and fixes; feeds 06G |
| 3a | 01D | C AI security | 01A, 01B | 1 | REVIEW-01 R4 and R5; unlocks 01C, 04C, 07B |
| 3a | 03D2 | E admin views | 03D1, 03A | 1 | Command Center views on the merged backend |
| 3a | 03E2 | E admin views | 03E1, 03A | 1 to 2 | Report catalogue, builder and export views |
| 3b | 01C | C AI security | 01B, 01D merged | 1 | Shared-module order 01B, 01D, 01C |
| 3b | 06E | D language | 01A, 06A | 1 | LG-08 per-language injection and privacy suites |
| 3b | 06B | D language | 04A, 04B, 06A | fix PRs | LG-03 and LG-09 per language |
| 3b | 06D | D language | 02B | 1 | LG-06 multilingual retrieval and attribution (production embedder blocked by OD-EMBED, OD-BUDGET) |
| 3b | 05D | A platform | 05A | 1 | PG-02 live identity, email and shared rate limiting (live needs OD-HOSTED) |
| 3b | 07A | E admin and hygiene | 05A, 03A | 1 | PG-10 inaccessibility suite |
| 3b | 04D | F candidate | 05A | 2 | PG-06 journeys; staging run needs OD-HOSTED |
| 3b | 04F | F candidate | none | 0 to 1 | Dictation disclosure; wording review needs a legal reviewer |
| 3b | 02E | H knowledge | 02B | 1 | Harness, relevance floor and routing now; approval of the beta-scope measure needs OD-COVERAGE |
| 3c | 04C | F candidate | 01A; starts after 01C merges | 2 (backend; UI) | Shares `src/agent/*` with 01D and 01C, so it follows them to avoid concurrent edits |
| 3c | 07B | C AI security | 01B, 01D | 1 | Live validation needs OD-BUDGET |
| 3c | 07C | G evidence | none | evidence | Live OCR sample needs OD-BUDGET |
| 3c | 06G | D language | 06C, 00A | protocol and harness | Independent reviewers needed (OD-BUDGET, OD-GATE-THRESHOLDS) |
| human | 02D, 06F | H, D | 00A | documentation PRs | Calendar-bound; start with the owner, not with engineering |
| last | 08A | G evidence | everything | 1 | Freeze at one SHA and owner go/no-go |

### 4.3 File ownership and shared modules
- `src/agent/*`, `src/copilot/security/*`: 01D, then 01C, then 04C, then 07B (one at a time).
- Prompt assets: any package that changes a prompt adds a NEW version file under `prompts/` and the one-line pointer entry in `prompts/current.json`; the pointer conflict is expected and trivial. 06C, 01D and 01C are the likely editors.
- `deploy/docker-compose.staging.yml`: owned by the merged 05A; 05B and 05D document needed changes and do not edit it unless the owner assigns it.
- Admin shell, `capabilities.ts`, `nav-items.ts`: owned by the merged 03A. 03D2, 03E2 and 07A add views and tests only.
- Frozen contracts: `src/knowledge_admin/contracts.py` (02K), `src/reporting/contract.py` and `frontend/lib/admin/metricContract.*` (03K).
- Registration lines (`src/api/main.py`, `tests/_admin_matrix.py`, `src/application/admin_audit.py`) and the generated `06A_LOCALE_AUDIT.md` are known routine conflict points: re-merge `main` and regenerate the audit with `scripts/eval_locale_inventory.py --write`.

### 4.4 Migrations
Current head `0043`. Wave 3 packages that may need one, only if truly necessary and stated in the PR: 05E (consent version history), 05C (budget ledger or an alert category), 02D (approval register). Numbering stays contiguous; the first merged takes 0044, later ones rename and re-chain at merge (`tests/_alembic_head.py` makes that a rename). Each migration is additive and data-preserving with a fail-closed downgrade.

### 4.5 PR contract for every Wave 3 PR (Phase 8 rule)
Each PR states: package and requirement IDs; what changed; tests and evaluator results (both venvs where applicable, all 46 CI evaluators, the full backend suite, frontend checks, affected Playwright specs); security and privacy impact; review evidence needed; the merge SHA after merge; remaining risks; the effect on named acceptance gates; and the exact human and live evidence still missing. Evidence goes in `docs/production/execution/evidence/<PKG>_EVIDENCE.md`. Tracker rows move to PASS only with an artefact link.

## 5. Package briefs

Common acceptance for all: every item in the package's register entry (`IMPLEMENTATION_PACKAGE_REGISTER.md`) is met or the gap is stated; ruff, the shard plan and all evaluators pass; no assertion weakened; no paid or live call, no deployment, no Stripe; the permission registry stays 44 unless justified.

### 08A0 Release evidence pipeline (feat/08a0-release-evidence, one PR)
Collect gate evidence automatically: per-package acceptance results, CI links, merge SHAs, the PG-01 to PG-15 and LG-01 to LG-14 tracker rows and the reconciliation check, so the freeze assembles existing evidence. PASS only with an artefact link; stale evidence is flagged. Tests: tracker generator and staleness tests; reconciliation check. Acceptance: evidence for a merged package appears in the tracker without manual copying. No network call in tests.

### 05B Persistence, backup, restore and rollback drills (feat/05b-backup-restore-drills, one PR plus drill records)
Extend backup and restore to database, private files and indexes; erasure from backups after account deletion; a rollback rehearsal; PostgreSQL-only paths (job claim, audit triggers, secrets) tested against a disposable local PostgreSQL if the owner permits one, otherwise written and skipped with an explicit marker. Tests: restore drill record; PostgreSQL claim and trigger tests; rollback rehearsal. Live drills on staging are NOT RUN until OD-HOSTED. Acceptance: PG-09 (backup, restore, rollback) with repeatable recorded drills.

### 05C Observability, alerting and provider resilience (feat/05c-budget-governor, feat/05c-monitoring-alerts: two PRs)
PR 1: production AI budget governor (hard cap, categories, kill switch) generalised from the demo ledger, quota-reservation reaper schedule, fail-closed on missing config. PR 2: alert rules for API, worker, indexing and provider health, provider failure behaviour, hosted pause verification, Admin provider readiness shows alert and budget state. Tests: budget guard (mocked providers), reaper, failure paths, alert tests. Acceptance: a synthetic outage raises an alert; the cap cannot be exceeded. Needs OD-BUDGET for a live cap value; staging verification needs OD-HOSTED.

### 05E Privacy, legal and data-rights readiness (feat/05e-privacy-safeguards, feat/05e-legal-copy: two PRs)
Deletion safeguards, preparation-chat ownership index, consent version history, audit allow-list enforcement, reporting differencing review, DSAR path decision; legal page copy only after counsel review. No GDPR or legal-compliance claim without qualified review. Tests: privacy request and deletion suites; audit allow-list; counsel sign-off record. Acceptance: PG-04 with counsel sign-off per offered language. Counsel is a long lead; the engineering PR does not wait for it.

### 06C Per-language AI behaviour (feat/06c-language-ai-behaviour, one PR plus protocol)
Per-language policy and prompt behaviour, scoring invariance across languages, localized policy sentence review, a blinded rating protocol and harness. Tests: per-language policy suite; scoring invariance; protocol dry-run. Acceptance: suites green per language (LG-04, LG-05 engineering part). Live quality and the native-reader rating need OD-BUDGET and named reviewers.

### 01D Tool-call authorization (feat/01d-tool-authorization, one PR)
Server-side revalidation of every model-requested tool call (authenticated user, goal, tool permission, allowed arguments, ownership) immediately before any side-effecting tool; unauthorized and cross-user actions are rejected regardless of model output, with negative tests that retrieved content cannot trigger a tool. No tool-set change; `eval_agent` and tool-selection cases unchanged. Acceptance: REVIEW-01 R4 and R5. Owns `src/agent/*` and `src/copilot/security/*` until merged. A human security review is requested before merge.

### 03D2 Command Center and AI operations views (feat/03d2-command-center-views, one PR)
Dashboard tiles and charts chosen by meaning, with period, numerator, denominator, coverage and missing-data state, plus the AI operations view, inside the 03A shell, over the 03D1 API. Unavailable metrics render as unavailable, never zero. Tests: vitest chart and missing-data rendering; Playwright dashboard specs; a malformed-response test (the 04E lesson). Acceptance: REQ-OWN-01 C1 to C5 frontend half.

### 03E2 Report views (feat/03e2-report-views, one or two PRs)
Report catalogue, builder UI, charts, saved configuration management and export in the Admin shell, over the 03E1 API; the builder cannot submit an unregistered metric. Export formats follow OD-REPORT-EXPORT (CSV and JSON are what the backend offers today). Tests: vitest; Playwright report specs; malformed-response handling. Acceptance: REQ-OWN-04 journeys pass in the browser.

### Wave 3b briefs (each branched from `main` after its dependencies merge)
- **01C Tool registry parity** (feat/01c-tool-registry-parity): registry as the single catalogue, generated model-visible descriptions, Pydantic-derived argument contracts, duplicate rejection, parity tests, tool set unchanged. REVIEW-03 R1 to R6.
- **06E Per-language injection, security and privacy suites** (feat/06e-language-security-suites): extend the 01A corpus and PII suites to all seven languages including mixed-language input, new cases authored on the development split only (the frozen held-out set stays untouched). LG-08.
- **06B Per-language journeys, Story Bank and Workspaces** (fix PRs per language): run and fix Playwright journeys in all seven languages. LG-03, LG-09.
- **06D Multilingual retrieval and attribution** (feat/06d-multilingual-retrieval): cross-language retrieval, citation attribution and abstention with sample sizes and limitations; production-embedder run only after OD-EMBED and OD-BUDGET. LG-06.
- **05D Identity, email and rate limiting live** (feat/05d-identity-live): webhook signature tests, Redis integration test, live round trips only on staging under owner authorisation. PG-02.
- **07A Deferral inaccessibility** (feat/07a-deferral-inaccessibility): one UI plus API suite proving every deferred feature (billing, Stripe, server speech, Compensation V2, international sources, gating, scheduler) is unreachable; async-blocking and optional-dependency tests. PG-10.
- **04D Candidate journey reliability** (two PRs): real browser journeys registration to Progress including the Start Interview regression, provider-mode indicator and accurate provider-unavailable copy, owner-scoped run list, provider-key hazard guard. Staging run NOT RUN until OD-HOSTED. PG-06.
- **04F Dictation disclosure** (small PR if wording changes): legal review of the browser dictation disclosure and a measured correction-burden check; needs a legal reviewer and participants.
- **02E Retrieval quality and coverage** (feat/02e-retrieval-quality): calibrated relevance floor, language-aware routing, a separate frozen beta-scope coverage measure reported beside the preserved historical gate (386 of 412, FAIL, unchanged). Needs OD-COVERAGE and datasets authored by someone other than the developer.

### Wave 3c briefs
- **04C Agent streaming and cancellation** (two PRs: backend, then UI), after 01C: authenticated SSE with `astream_events` v2, safe allow-list projections, cancellation, timeouts, reconnection safety, cancelled-run cost reconciliation, synchronous fallback. REVIEW-05. Works on staging only after OD-HOSTED.
- **07B Live grounding validation**, **07C live OCR sample**, **06G independent human evaluation**: live and human steps, each blocked on OD-BUDGET (and 06G on named reviewers and OD-GATE-THRESHOLDS); the engineering part is the protocol, harness and run scripts, which refuse a paid call without an approved budget marker.
- **08A Freeze and go/no-go**: one SHA, evidence for PG-01 to PG-15 and LG-01 to LG-14, reconciliation check, release rehearsal, owner decision. Last.

## 6. Merge order
1. 08A0, then 05B, 05E, 05C, 06C (independent; any order once green).
2. 01D, then 01C, then 04C backend, then 04C UI, then 07B.
3. 03D2 and 03E2 (independent of each other and of the AI chain).
4. 06E, 06D, 06B, 05D, 07A, 04D, 04F, 02E as their dependencies land.
5. 06G, 07C, 02D documentation and 08A last.
Every PR merges only after its own green CI, owner review and acceptance evidence; the lead re-merges `main` into the next branch after each merge, as in Waves 1 and 2.

## 7. Owner decisions and external reviews that must begin now

The dates below are computed from the planning model (assumed calendar floors, no holidays) and are marked as such. The binding constraint is human and legal lead time, not engineering: **in the model the full scope is gated by the 20 working days assumed for native-language and legal translation review (06F), then 3 working days for the freeze (08A). For a freeze finished by Friday 27 November, native reviewers and legal qualifiers must be named and engaged by Tuesday 27 October.** Every working day later moves the date by a working day (Monday 2 November gives Thursday 3 December).

| Decision or review | Needed from | Latest start to hold 30 November | Recommended | Blocks |
|---|---|---|---|---|
| Name the seven native reviewers and the legal and privacy translation qualifiers (OD-LANG-03, OD-LANG-04) | Owner | Tue 27 Oct | now | 06F, LG-10, LG-11, PG-04, every language activation |
| Engage legal counsel for Privacy, Terms and AI transparency (05E) | Owner | Fri 6 Nov (15 wd) | with the line above | PG-04 |
| Authorise and choose the hosted environment (OD-HOSTED) | Owner | Mon 2 Nov (allows one fix round) | this week | every live drill: 05B, 05C, 05D, 04C, 04D, 07B, 07C; hosted proofs for 02A, 02B, 02C, 05A |
| Choose the production embedding provider and model (OD-EMBED) | Owner | Mon 26 Oct | now | 02B benchmark, 06D, 02E |
| Approve a bounded live budget and its cap (OD-BUDGET) | Owner | Mon 2 Nov | this week | 05C cap value, 06C and 06G live runs, 07B, 07C, 02E, 06D |
| Name independent evaluators and approve thresholds (OD-GATE-THRESHOLDS, 06G; 10 wd) | Owner | Fri 13 Nov | after the held-out set exists | PG-07, PG-03 numeric gates |
| Author an independent injection held-out set (different author, several hundred cases, per-language quotas, frozen by hash) | Owner assigns a person | Mon 9 Nov | now | OD-GATE-THRESHOLDS, PG-03 |
| Name a human security reviewer for 01A and 01D (nine questions are recorded in `01A_INVESTIGATION.md`) | Owner | before 01D merges | now | PG-03 |
| Licensing reviewer, market approvals and the US-content decision (OD-LANG-02, OD-US-CONTENT, 02D; 15 wd) | Owner | Fri 6 Nov | now (02E coverage depends on it) | PG-05, 02E, enabling any market |
| Approve the frozen beta-scope coverage measure (OD-COVERAGE) | Owner | Mon 2 Nov | this week | 02E |
| Export formats beyond CSV and JSON (OD-REPORT-EXPORT) | Owner | Mon 26 Oct | now | 03E2 |
| Bulk user actions (OD-BULK-ACTIONS), plan limits (OD-PLAN-LIMITS), workspace ownership transfer (OD-WS-TRANSFER) | Owner | Mon 2 Nov | this week | PG-08, PG-13 |
| Resource allocation (OD-RESOURCE): who actually does the human work | Owner | now | now | everything calendar-bound |

New decisions raised while building Waves 1 and 2 are listed in `../OWNER_DECISION_REGISTER.md` (invitation email and issuers, a second approver for plan activation, hosted language fail-closed testing, a scanner outage alert category, fake-scanner serving guard, platform-admin workspace enrolment, per-run story consent in Prepare, mandatory `approved_until`, restoring the local test environment).

## 8. Critical path, forecast and risk

- **Engineering:** 20 packages authored in 11 to 73 minutes each and merged within 41 minutes to 3 hours 51 minutes of PR open; the remaining engineering packages are expected to be mergeable in days, not weeks. Verified by observation only for contracts, backends and scaffolds, not for live or human work.
- **Critical path (model):** owner names reviewers (by Tue 27 Oct) -> 06F native review and legal translation (20 wd assumed) -> 08A freeze (3 wd) -> 30 November. All engineering packages and the live drills fit inside that window, provided OD-HOSTED and OD-BUDGET are answered by Mon 2 Nov.
- **Forecast:** 30 November holds only if the owner decisions in section 7 are made on time. Otherwise the freeze moves one working day per day of delay (for example Thu 3 Dec if reviewers start Mon 2 Nov, Thu 10 Dec for Mon 9 Nov). The date moves; no scope is cut and no gate is waived.
- **Release risk:** HIGH for 30 November, driven by unstarted human and legal steps and an unanswered hosting authorisation; MEDIUM for staging-dependent verification (everything live is NOT RUN); LOW for remaining engineering. Quality gates not yet met: PG-03 numeric thresholds, PG-05 retrieval quality and licensing, PG-07 independent evaluation.
- **Process risks and mitigations:** integration rework (re-merge `main` before each PR, regenerate the locale audit, version-independent head checks); shared agent modules (strict order 01D, 01C, 04C, 07B); machine load (eight concurrent agents, four test workers); local test environment (the fresh-dependency venv and Playwright browser cache were deleted; rebuilding them needs a download the owner must approve, until then CI is the verification).

## 9. Owner authorisation of 2026-10-22 and scope additions

The owner authorised Wave 3a to proceed immediately and recorded provisional recommendations for nine decisions (`../OWNER_DECISION_REGISTER.md`, section "Owner direction 2026-10-22"). Wave 3a launched on 2026-10-22 as eight isolated worktrees: 08A0 (feat/08a0-release-evidence), 05B (feat/05b-backup-restore-drills), 05C (feat/05c-budget-governor then feat/05c-monitoring-alerts), 05E (feat/05e-privacy-safeguards then feat/05e-legal-review-pack), 06C (feat/06c-language-ai-behaviour), 01D (feat/01d-tool-authorization), 03D2 (feat/03d2-command-center-views), 03E2 (feat/03e2-report-views then feat/03e2-pdf-export). The development environment was repaired (fresh-dependency venv at `$HOME/.cache/ask4mo/ci_venv`, Playwright browsers restored). No gate was changed; reviewers are appointed later and no automated check substitutes for their sign-off.

Scope items that follow from the owner's recommendations and stay inside the existing requirements (nothing is removed or deferred):
| Item | Requirement | Package home | When |
|---|---|---|---|
| Governed PDF export | REQ-OWN-04 | 03E2 second PR | Wave 3a |
| Previewed, authorised, audited bulk user actions with partial-failure handling | REQ-OWN-03 (restricted bulk actions) | completion PR of 03C | Wave 3b |
| Workspace ownership transfer with verified acceptance and immutable audit (needs a pending-transfer table, so migration 0044 or later) | REQ-OWN-07 | completion PR of 04B | Wave 3b |
| OpenRouter embedding adapter and multilingual embedding benchmark (OpenRouter-only; versioned manifests and rollback preserved; recall@k, nDCG@k, cross-language, citation accuracy, latency, cost, dimensions) | REVIEW-04, OD-EMBED | 02B completion, 02E, 06D | Wave 3b, after the 05C budget governor merges |
| Plan limits derived from measured operational and token costs | REQ-OWN-02, OD-PLAN-LIMITS | 03B completion, after 05C telemetry exists | Wave 3c |
| Per-story consent in Prepare | REQ-OWN-06 | 04A completion, in the 01D, 01C order | Wave 3c |

Wave 3b (01C, 02E, 04D, 04F, 05D, 06B, 06D, 06E, 07A) and Wave 3c (04C, 07B, 07C, 06G, 08A) are prepared per section 4 and start as dependencies merge and slots free (cap eight concurrent agents). 02D and 06F review materials are prepared in parallel as review-ready packages; human qualification is never recorded as completed.
