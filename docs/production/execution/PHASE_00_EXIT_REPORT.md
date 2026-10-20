# Phase 00 Exit Report

**Status:** READY FOR OWNER REVIEW, 2026-10-21. Phase 00 is planning only: no application feature, migration, provider call, deployment, payment activation or change to historical evidence was made. **Phase 01 does not start until the owner approves this report.**

## 1. Baseline

`main` at `59f1fda` (PR #211 merged, CI green on the reported checks). Alembic head `0039_speech_governance`; 5,134 backend tests collected; reconciliation 452 traced rows, R1.0 must-fix 88 and must-verify 74, 0 unmapped. Details: `PHASE_00_CURRENT_STATE.md`.

## 2. What Phase 00 produced

| Deliverable | Notes |
|---|---|
| `PHASE_00_CURRENT_STATE.md` | Verified facts and ten verified gaps (G1 to G10) |
| `IMPLEMENTATION_PACKAGE_REGISTER.md` | Generated: 37 packages, each with the eleven required fields, plus exact briefs for 01A, 01B, 01C, 02A, 03A |
| `DEPENDENCY_GRAPH.md` | Generated: dependency graph, topological order, critical path, shared modules and integration order |
| `DELIVERY_SCHEDULE.md` | Generated: week-by-week schedule for Phases 01 to 08, milestones and measurable exit gates, parallel work, capacity model |
| `TECHNICAL_DECISIONS.md` | Options and PROPOSED recommendations for hosting, PostgreSQL, storage, embeddings, background processing, malware scanning, monitoring and AI budgets; nothing provisioned |
| `ADMIN_V2_EXECUTION_SPEC.md`, `CANDIDATE_EXECUTION_SPEC.md`, `MULTILINGUAL_EXECUTION_PLAN.md` | Track specifications reusing existing documents |
| `RELEASE_READINESS_TRACKER.md` | Live tracker of PG-01 to PG-15, per-language gates and owner requirements, all honestly not passed |
| Machine check | `scripts/production/execution_packages.py check` (every R1.0 fix/verify item in exactly one package; dependencies acyclic; schedule consistent) with tests |

## 3. Packages and dependency order

37 packages across six tracks (A AI security 4 packages, B Knowledge 6 (including the scope reconciliation delta), C Admin 5, D Candidate 6, E operations 8 (including freeze and hygiene), F languages and governance 8). Safe integration order, from `DEPENDENCY_GRAPH.md`:

1. **Independent starters (W1):** 01A, 01B, 02A, 03A, 05A, 05E, 06A (and 00A, 00B).
2. **After the starters:** 01C (after 01A and 01B); 02B and 02C (after 02A); 03B, 03C, 03D (after 03A); 04A, 04B, 04E (no code dependency); 04C (after 01A); 06C and 06E (after 01B, 01A and 06A).
3. **Then:** 02D and 02E; 03E (after 03D); 05B, 05C, 05D (after 05A); 04D (after 05A); 06B, 06D.
4. **Last:** 06G, 07A, 07B, 07C, then 08A (freeze and evidence).

Shared modules with a forced order: the agent policy and tool-execution path (01B, then 01A, then 01C; 04C after 01A); `AdminShell.tsx` and `capabilities.ts` (03A first); `deploy/docker-compose.staging.yml` (05A owns it); migrations (one revision per PR, single head).

## 4. Findings that change the plan

- **G1 (high):** the staging Compose topology has no job worker, no knowledge or index volume and no ClamAV service. Deploying it as written would reproduce the empty or non-indexing Knowledge Sources the owner keeps seeing. Fixed by 02A, 02C and 05A.
- **G2:** the ClamAV scanner is a stub; real scanning needs implementation (02C).
- **G3:** the embedding provider can silently resolve to the lexical hash embedder; the earlier zero RAGAS relevancy score may relate to the embedding path (hypothesis only).
- **G4:** model identities differ between the staging template (`gpt-5.6-*`) and the live demonstration (`gpt-5.4`, `5.4-mini`, `5.5`); budgets must be set on the real identities.
- **G9:** the curated corpus is US-centred while the beta markets are EU. This is a new decision (OD-US-CONTENT).
- **Proposed reclassification (package 00B, owner to confirm):** 12 items currently R1.0 fix concern US occupational measurement and alias reviews (BL-5, BL-6 series, BL-7, BL-9), Compensation V2 authorisation (BL-12) and a server-side recording client (W12.4E-12). If confirmed they leave R1.0 (R1.6, R1.5 or R1.4), taking R1.0 fix from 88 to 76 and fix plus verify from 162 to 150. The reconciliation was not changed in Phase 00.

## 5. Remaining decisions

Open decisions in `../OWNER_DECISION_REGISTER.md`: 20 new, plus the 72 historical. The ones that gate Phase 01 to 03: **OD-SCOPE-01** (what happens if a mandatory gate is missed), **OD-GATE-THRESHOLDS** (for 01A's CI gate), **OD-ADMIN-NAV** (03A grouping), **OD-HOSTED**, **OD-BUDGET** and **OD-EMBED** (for 02B and Phase 05), **OD-INVITE**, **OD-MALWARE**, **OD-PLAN-ENFORCE**, **OD-BULK-ACTIONS**, **OD-REPORT-EXPORT**, **OD-WS-TRANSFER**, **OD-LANG-02/03/04**, **OD-COVERAGE**, **OD-US-CONTENT**. 01A (except gating), 01B and 03A need no infrastructure decision.

## 6. November feasibility (computed, with stated assumptions)

| Measure | Value |
|---|---|
| Package effort | 196 to 303 ideal engineering days (37 packages) |
| Window | W1 to W5 = 25 working days; one stream (an engineer or a focused agent session) at an assumed 70% utilisation = 17.5 productive days |
| Parallel streams needed to fit | 11.2 to 17.3 |
| Longest dependency chain | 03A, 03D, 03E, 08A = 26 to 39 days of strictly sequential effort, already above the 25-day window before any human lead time |
| Calendar-bound human work | native review (seven languages), legal translation, counsel review, licence review, independent human evaluation; not compressible by engineering |

| Scope option | Effort (days) | Streams needed |
|---|---|---|
| Full R1.0 scope | 196 to 303 | 11.2 to 17.3 |
| Defer Command Center and report builder (03D, 03E) to R1.2 | 178 to 276 | 10.2 to 15.8 |
| Lean beta: also defer plan management, streaming, retrieval calibration, live validation and the dictation review (03B, 04C, 02E, 07B, 07C, 04F) and the reclassification package | 149 to 232 | 8.5 to 13.3 |

**Assessment: the full R1.0 scope is NOT feasible by 30 November 2026** with any realistic single team; even the lean option needs roughly 8 to 13 parallel streams plus human reviews that cannot be compressed. The owner's rule stands: the date is a target, mandatory gates are not waived. OD-SCOPE-01 therefore needs an answer now: delay R1.0, remove features from scope (each removal must keep REQ-DEFER-01 satisfied), or keep them disabled. The capacity figure is an assumption: the real number of engineers or agent sessions available is not recorded anywhere and should be supplied.

## 7. Phase 00 exit gates

| Gate | Status | Evidence |
|---|---|---|
| E1 Baseline verified (SHA, architecture, documents, reconciliation, tests, CI, migrations, deployment config, dependencies) | PASS | `PHASE_00_CURRENT_STATE.md` |
| E2 Backlog decomposed: all 162 R1.0 fix/verify items in exactly one package; each package has the required fields | PASS (machine-checked) | `execution_packages.py check`; tests |
| E3 Six execution tracks and a safe integration order | PASS | `DEPENDENCY_GRAPH.md` |
| E4 Technical options for the eight dependency areas, no owner decision made | PASS | `TECHNICAL_DECISIONS.md` |
| E5 Schedule Phases 01 to 08, critical path, weekly milestones with measurable exit gates, parallel work | PASS | `DELIVERY_SCHEDULE.md` |
| E6 Exact briefs for 01A, 01B, 01C, 02A, 03A | PASS | register, section "First PR briefs" |
| E7 All ten deliverables exist | PASS | `docs/production/execution/` |
| E8 Documentation, reconciliation and static checks pass; CI green | see section 8 | |
| E9 No application change, no provider call, no deployment, no payment, no historical rewriting, no merge | PASS | diff touches only docs, `scripts/production/` and tests |
| E10 Owner approval to start Phase 01 | **PENDING** | this report |

## 8. Checks run

`reconcile_issues.py check` and its 12 tests; `execution_packages.py check` and its tests; `ruff`; compile check; shard plan verification; the product-positioning, release-matrix and admin-design evaluators. GitHub CI on the PR is reported in the PR.

## 9. Recommended first implementation PR

**01A PR 1: prompt-injection corpus, evaluator, injection-risk score and quarantine.** Reasons: it is the P0 reviewer finding with the largest safety value; it needs no infrastructure or paid-service decision; the evaluator reports without gating until OD-GATE-THRESHOLDS is answered; it touches the retrieval and security modules that nothing else edits in W1; and it unblocks 04C and 06E. Start 01B, 03A, 02A (identity and configuration part), 05A and 06A in parallel because they share no files with it. Scope, files and tests are in the 01A brief.

## 10. Request

Approve Phase 00; answer OD-SCOPE-01 first (it decides how much of the plan is executed), then the Phase 01 to 03 blockers; confirm or reject the 00B reclassifications; state the real capacity. Phase 01 starts only after that.
