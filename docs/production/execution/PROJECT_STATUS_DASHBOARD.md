# Whole-Project Status Dashboard

Updated 23 October 2026. Baseline: `origin/main` at `3e8e2ba4caf4578815dad2e99fbd2b491bd98a16`. Current development: `codex/r1-development` in the existing repository's separate Codex worktree. Development is committed and pushed in [draft PR #265](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/265), awaiting hosted CI and owner review. It is not merged. Sources: [verified merge inventory](evidence/CODEX_WAVE3_MERGES_2026_10_23.json), [Codex execution milestones](CODEX_EXECUTION_PROGRESS.md), package register and current code.

## 1. Engineering and integration

38 of 45 packages have their offline engineering code merged. 00A remains partial and 00B is a delivered proposal awaiting owner disposition. Five packages remain without merged implementation: 01C, 04C, 07B, 07C and 08A. These counts describe engineering integration, not acceptance of the complete operational or human scope of each package.

Wave 3 PRs #236–#264 are merged (verified per package using their merge SHA ancestry). There are no pending Wave 3 implementation PRs to open from the historical queue. 01D is merged, so it no longer blocks 01C. No worktree or local branch was removed. Six local branch tips are not reachable from fetched origin and are preserved for review.

## 2. CI and local verification

[Baseline CI run 39970568206](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/39970568206) **FAILS** two 06F freshness tests. It must not be described as green. Local Task 01 reproduced both failures, regenerated the review packs and passed all 28 06F tests (7.14s). Remote CI for the repair is NOT RUN. Browser qualification of the baseline merge SHA is not established by that CI run. Current development validation is recorded in the milestone table and verification report below; local tests are separate from hosted CI.

## 3. All 45 packages: five independent layers

Engineering, CI, staging, human qualification and production gates are independent. Rows are generated from `scripts/production/execution_packages.py` and `wave_matrix.py`. The shared CI cell refers to the reviewed merged baseline, not an invented per-package result.

<!-- MATRIX:START -->
| Package | 1 Engineering | 2 CI | 3 Live staging | 4 Human qualification | 5 Production-gate acceptance |
|---|---|---|---|---|---|
| 00A | PARTIAL: Phase 00 sign-off recorded (PRs #211, #212, #213) | historical documentation CI recorded; current baseline CI FAIL | n/a | Owner names reviewers, counsel and legal qualifiers (OPEN) | PG-07 BLOCKED until reviewers are named |
| 00B | DELIVERED as a proposal (PRs #211, #212) | historical documentation CI recorded; current baseline CI FAIL | n/a | Owner disposition of the ten reclassifications (OPEN) | PG-11 PASS (machine-checked); no reclassification applied |
| 01A | MERGED (PR #223, merge 7549973) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (injection screen on hosted stack) | Human security review (9 questions); independent held-out author (OPEN) | PG-03 IN PROGRESS; thresholds unapproved (OD-GATE-THRESHOLDS) |
| 01D | MERGED (PR #248 merge c5e54fd6) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | Security review of tool authorization | PG-03 (REVIEW-01 R4/R5) |
| 01B0 | MERGED (PR #217, merge 0d75acd) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | none | PG-12 IN PROGRESS |
| 01B | MERGED (PR #220, merge 335d303) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (Docker image with prompts/ not built) | none | PG-12 IN PROGRESS (01C outstanding; 01D merged) |
| 01C | LOCAL IMPLEMENTED | NOT RUN (no implementation PR) | n/a | none | PG-12 (REVIEW-03) |
| 02K | MERGED (PR #215, merge 657e456) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | none | PG-05 IN PROGRESS (contract) |
| 02A | MERGED (PR #221, merge 191cbc5) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (hosted volumes, PostgreSQL, multi-worker; OD-HOSTED) | none | PG-05 IN PROGRESS |
| 02B | MERGED (PR #227 merge 6acdbc11, PR #236 merge f78773df) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (production embedder, hosted refusal; OD-HOSTED, OD-EMBED) | Embedder choice and benchmark approval (OD-EMBED, OD-BUDGET) | PG-05 NOT MET (retrieval quality unmeasured) |
| 02C | MERGED (PR #226, merge 568b8f3) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (real clamd, EICAR, outage drill; OD-HOSTED) | none | PG-05 IN PROGRESS |
| 02D | MERGED (PR #258 merge 15ac01bf, PR #260 merge 89c39ced) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | Licensing reviewer and owner; per-market signed approval (OPEN, long lead) | PG-05 (licence and market qualification) |
| 02E | MERGED (PR #238 merge 2a4a5377) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN | Frozen coverage measure approval (OD-COVERAGE); independent datasets | PG-05 (retrieval quality, coverage) |
| 03A | MERGED (PR #216, merge f921892) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live Admin walkthrough) | none | PG-08 IN PROGRESS |
| 03B | MERGED (PR #230, merge a4f540d) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live Admin walkthrough) | Plan limit values (OD-PLAN-LIMITS) | PG-08 IN PROGRESS |
| 03C | MERGED (PR #231 merge 6bcfbf53, PR #261 merge bf05db6f) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live Admin walkthrough) | Bulk-action policy (OD-BULK-ACTIONS) | PG-08 IN PROGRESS |
| 03K | MERGED (PR #219, merge 20241f4) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | none | PG-14 IN PROGRESS (contract) |
| 03D1 | MERGED (PR #224, merge ac029ad) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live data) | none | PG-08 IN PROGRESS (views merged; staging outstanding) |
| 03D2 | MERGED (PR #249 merge 66fdbaba) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN | none | PG-08 |
| 03E1 | MERGED (PR #232, merge 0d84e7e) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live data) | Export formats (OD-REPORT-EXPORT) | PG-14 IN PROGRESS (views merged; staging outstanding) |
| 03E2 | MERGED (PR #247 merge 6034835e, PR #251 merge bc5fe4f6) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN | Export formats (OD-REPORT-EXPORT) | PG-14 |
| 04A | MERGED (PR #234, merge 4d7e57a) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (restart on staging) | Native review of 116 strings (LG-10/11) | PG-13 IN PROGRESS (06B merged; staging and human review outstanding) |
| 04B | MERGED (PR #233 merge e4aed133, PR #262 merge 103611ee) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (PostgreSQL invitation race and row locks) | Transfer rules (OD-WS-TRANSFER); native review | PG-13 IN PROGRESS (06B merged; staging and human review outstanding) |
| 04C | LOCAL IMPLEMENTED | NOT RUN (no implementation PR) | NOT RUN (streaming on staging) | none | PG-06 |
| 04D | MERGED (PR #242 merge 67ef7c46, PR #253 merge 85a88c70) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (journeys on a staging stack) | none | PG-06 |
| 04E | MERGED (PR #228, merge a763fdf) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (first-admin bootstrap, live Google) | Invitation email and issuer decisions (OPEN) | PG-02 IN PROGRESS (05D merged; live verification outstanding) |
| 04F | MERGED (PR #255 merge 7c400efe) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (browser dictation check) | Legal reviewer and test participants | PG-04 |
| 05A | MERGED (PR #218, merge 9b6b109) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (nothing deployed; OD-HOSTED) | Hosting authorisation (OPEN) | PG-01 BLOCKED |
| 05B | MERGED (PR #257 merge f5c1e04f) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (restore drill, PostgreSQL paths; OD-HOSTED) | none | PG-09 |
| 05C | MERGED (PR #241 merge 45144979, PR #246 merge 26f5a818) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (synthetic outage on staging; OD-HOSTED) | AI budget (OD-BUDGET) | PG-09 |
| 05D | MERGED (PR #237 merge 64fbcf2b) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live Brevo, Google, Redis; OD-HOSTED) | none | PG-02 |
| 05E | MERGED (PR #240 merge 608b65b4, PR #244 merge 8649e3fa) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | Legal counsel sign-off per offered language (long lead) | PG-04 |
| 06A | MERGED (PR #214, merge f9a06a9) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | Native review of the audit baseline | PG-10 IN PROGRESS; LG-01 and LG-14 evidence exists, none approved by a named human |
| 06B | MERGED (PR #256 merge 29cc09be) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (journeys per language) | Native-speaker review | LG-03, LG-09 per language; PG-13 |
| 06C | MERGED (PR #245 merge 74d99e31) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live Mo quality) | Blinded native-reader rating (OD-BUDGET) | LG-04, LG-05 per language |
| 06D | MERGED (PR #254 merge c9268c67) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (production embedder; OD-EMBED) | Sample review | LG-06 per language |
| 06E | MERGED (PR #239 merge 84c1b9b8) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN | none | LG-08 per language; PG-03 |
| 06F | MERGED (PR #259 merge 3e8e2ba4) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | Seven native reviewers and legal qualifiers (calendar-bound, OPEN) | LG-10, LG-11 per language; PG-04 |
| 06G | MERGED (PR #259 merge 3e8e2ba4) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (live Mo outputs) | Independent reviewers and participants (OD-BUDGET, OD-GATE-THRESHOLDS) | PG-07 BLOCKED |
| 06H | MERGED (PR #229, merge 5d588a1) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | NOT RUN (hosted fail-closed behaviour) | Approvers named for each gate (OD-LANG-03/04) | PG-10 IN PROGRESS; LG-13/LG-14 enforcement merged, zero languages qualified |
| 07A | MERGED (PR #243 merge 792871f2, PR #264 merge dfd59edc) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | none | PG-10 |
| 07B | PREFLIGHT ONLY | NOT RUN (no implementation PR) | NOT RUN (live grounding; OD-BUDGET) | none | PG-03 |
| 07C | LOCAL SAMPLE RECORDED | NOT RUN (no implementation PR) | NOT RUN (local synthetic OCR measured; hosted quality NOT VERIFIED) | none | residual live verification |
| 08A0 | MERGED (PR #250 merge 6eaf246f) | main 3e8e2ba4 CI FAIL (06F, run 39970568206); local repair awaiting PR CI | n/a | none | PG-15 (evidence pipeline) |
| 08A | NOT STARTED | NOT RUN (no implementation PR) | NOT RUN | Owner go/no-go | PG-15 |
<!-- MATRIX:END -->

## 4. Staging, human qualification and production gates

No staging stack was deployed or contacted by this work. Hosted persistence, real malware scanning, PostgreSQL races, provider round trips, streaming and recovery drills remain NOT VERIFIED. Native-language, legal, licensing, security and independent AI reviews still require named people and signed evidence. No language qualification or gate approval was created. Only PG-11 retains its existing machine-checked PASS; every other mandatory gate still needs its recorded evidence and approval. Historical coverage FAIL and AC-24 PARTIAL remain unchanged.

## 5. Execution order and remaining work

Tasks 01–04 are implemented locally: regenerated 06F packs, reconciled Wave 3, 01C Tool Registry Parity and 04C streaming/cancellation. Reconciliation and regression checks pass locally; PR CI remains pending. 07B preflight is READY, but a fresh live evaluation needs explicit budget approval and the historical zero-score cause remains unresolved. 07C records 14 actual local synthetic OCR observations across seven languages; hosted and human quality remain unqualified. Independent qualification and 08A remain blocked by their documented external evidence and owner decisions. See [verification and limits](evidence/CODEX_R1_DEVELOPMENT_2026_10_23.md). Live paid evaluation, hosting/deployment and human qualification cannot be substituted by offline tests. Production gates and the owner's release go/no-go remain mandatory. Do not automatically merge PRs or push to main.

## 6. Schedule and decisions

30 November 2026 remains the owner's target, subject to mandatory gates. The engineering model is a dated plan, not a guaranteed launch. Consult the owner-decision register for hosting, budgets, thresholds, reviewers, markets, source approvals and other unresolved choices; no provisional recommendation became approval in this reconciliation.
