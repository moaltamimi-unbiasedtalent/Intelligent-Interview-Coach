# Phase 00 Exit Report (corrected after owner review of PR #212)

**Status:** READY FOR OWNER REVIEW, 2026-10-21. Phase 00 is planning plus test-harness correction only: no application feature, migration, provider call, deployment, payment activation, feature enablement or change to historical evidence. **Phase 01 does not start until the owner approves this report.** This revision responds to the review of PR #212 (CI failure, the 12-item reclassification, OD-SCOPE-01, early platform workstream, shared-file order).

## 1. Baseline

`main` at `59f1fda` (PR #211 merged); Alembic head `0039_speech_governance`; 5,134 backend tests collected before this PR; reconciliation 452 traced rows, R1.0 must-fix 88 and must-verify 74, 0 unmapped. Details: `PHASE_00_CURRENT_STATE.md`.

## 2. Exact CI root cause (PR #212)

PR #212 was red in the four Python test shards and in "Python evaluators and guards" (identity evaluator `cross_user_isolation = 0/3`). **It is not an authorization defect and not caused by the Phase 00 documents.** It is dependency drift exposing a test-harness session-isolation artefact:

| Question | Finding |
|---|---|
| Does the PR change application code? | No: only documents, `scripts/production/` and tests |
| Is it on `main` too? | Yes, latently: the same code passes with the dependencies of the last green run (starlette 1.3.1, fastapi 0.141.1) and fails with a fresh install of the latest allowed versions (starlette 1.9.0, fastapi 0.156.8). CI installs fresh, so any later PR would have gone red |
| Is the server wrong? | No. With separate clients per user (two browsers) the three evaluator checks return 404, 404, 200 on the new dependencies too |
| Mechanism | The evaluator and many tests sign several users in through one `TestClient` and pass a per-request `cookies=` to act as one user. httpx sends the jar cookie and the per-request cookie in one `Cookie` header; a minimal Starlette app (no Ask4Mo code) shows the order flipped between starlette 1.3 (`jar; per-request`) and 1.9 (`per-request; jar`). The server keeps the last value, so the most recent login silently overrode the intended user and the checks measured the wrong identity |
| Fix | A harness wrapper in `tests/_client_compat.py` (installed whenever the `tests` package is imported, so pytest and every evaluator that imports a test helper get it) makes a per-request cookie authoritative on every version (same-named jar cookies are held back for that request only and restored unless the response set them). No assertion, no evaluator code and no application code changed; evaluators already import a `tests` helper |
| Evidence | The evaluator now passes (3/3) on both dependency sets; `tests/test_testclient_cookie_precedence.py` pins the semantics on a minimal app and on the real identity stack; the full suite was re-run on the fresh dependency set |

## 3. Proposed scope cuts (PROPOSED, NOT APPLIED)

**Reclassification of 12 candidate items:** the proof that each capability is inaccessible in the R1.0 Candidate API and UI is machine-checked in `tests/test_r1_scope_exclusions.py` and documented in `R1_SCOPE_RECLASSIFICATION_PROPOSAL.md`. **Ten items pass** (BL-5, BL-6, BL-6.1 to BL-6.5, BL-9, BL-12, W12.4E-12) and would move to R1.4, R1.5 or R1.6. **Two fail** (BL-6.6, BL-7: they concern enabled role resolution and coverage) and stay in R1.0 in package 02E. If confirmed, R1.0 must-fix goes 88 to 78 and fix plus verify 162 to 152. Historical IDs, closure evidence and failed gates are untouched.

**Important limit:** the reclassification does **not** exclude unqualified US labour-market claims. Curated US sources (O*NET, BLS OOH) remain in the Candidate corpus (a BLS OOH passage was returned for a UK nurse question in an offline probe) and the compensation store holds only US and UK data. Excluding them needs package 02D's approval filter and the owner's OD-US-CONTENT decision. Until then that claim must not be made.

## 4. OD-SCOPE-01: proposed restricted free private beta and capacity-based alternative (NOT owner-approved)

Effort is computed in `DELIVERY_SCHEDULE.md` from 38 packages (one stream = one engineer or focused agent session at an assumed 70% utilisation: 17.5 productive days in the 25-working-day window; the real capacity is unknown and is needed from the owner).

| Strategy | Content | Effort (days) | Streams needed | Critical path (days) |
|---|---|---|---|---|
| S1 Full R1.0 scope | all packages (tiers T0 to T4) | 196 to 304 | 11.2 to 17.4 | 26 to 39 (03A, 03D, 03E, 08A) |
| **S2 Restricted free private beta (proposed)** | tiers T0 to T2; Admin dashboards, plan editor and report builder (03B, 03D, 03E) to R1.2; verification extras as follow-ups | 163 to 254 | 9.3 to 14.5 | 25 to 39 (02A, 02B, 02E, 08A) |
| **S3 Minimum safe beta (capacity-based alternative)** | tiers T0 and T1 plus journey reliability (04D); owner-requested items beyond the activation gates move out of R1.0 and need explicit approval | 114 to 180 | 6.5 to 10.3 | 19 to 29 (02A, 05B, 08A) |

S2 restrictions, every one an owner decision: a small capped invitation-only cohort; languages and markets activated only where their gates pass (expect fewer than seven languages and one or two EU markets at launch; a failed mandatory gate prevents activation); candidate core only; safety, privacy, hosting, knowledge and identity gates unchanged; reviewer corrections kept; owner-operated Admin with navigation and user management; no live billing. **Assessment:** even S3 needs roughly 6 to 10 parallel streams plus calendar-bound human review; no strategy is feasible with one or two streams, and S1 is not feasible by 30 November under any realistic team. The owner decides (a) which strategy, (b) the real capacity, (c) or a later date. Mandatory safety, privacy, licensing and operational gates are never waived by an accepted limitation.

## 5. Early parallel workstream: deployment topology and Knowledge persistence

02A (Knowledge persistence, environment identity, restore), 05A (hosted topology) and 05E (privacy and legal readiness, calendar-bound) now start in the first implementation wave with the highest staffing priority, tracked separately. In both restricted strategies the critical path runs through Knowledge persistence (02A, then 02B or 05B), which is why it cannot wait. **The existing `deploy/docker-compose.staging.yml` must not be deployed as it stands** (no job worker, no knowledge or index volume, no ClamAV service); the first 05A PR completes the topology as code without deploying, and deployment waits for OD-HOSTED.

## 6. Shared-file integration order (preserved and tightened)

Agent-policy and tool-execution path: **01B (versioned prompts) first, then 01D (tool-call authorization, the part of REVIEW-01 that overlaps the agent policy and tool path), then 01C (registry parity)**. 01A (injection corpus, risk score and quarantine) touches none of those files, runs in parallel with 01B and no longer carries any agent-policy change. REVIEW-01 is closed by 01A plus 01D. The order is enforced by the package check. Other forced orders: `AdminShell.tsx` and `capabilities.ts` (03A first), `docker-compose.staging.yml` (05A owns it), one migration revision per PR.

## 7. Packages, critical path and remaining decisions

38 packages in six tracks (A 5, B 6, C 5, D 6, E 8, F 8), every R1.0 fix/verify item in exactly one (machine-checked). Critical path for the full scope: 03A, 03D, 03E, 08A (26 to 39 days); for S2: 02A, 02B, 02E, 08A (25 to 39); for S3: 02A, 05B, 08A (19 to 29), all before any human review lead time.

Open owner decisions: 20 new in `../OWNER_DECISION_REGISTER.md` plus the 72 historical. Phase 01 blockers: **OD-SCOPE-01** (strategy, capacity, date), **OD-GATE-THRESHOLDS** (01A CI gate), **OD-ADMIN-NAV** (03A), then **OD-HOSTED**, **OD-BUDGET**, **OD-EMBED**, **OD-INVITE**, **OD-MALWARE**, **OD-PLAN-ENFORCE**, **OD-BULK-ACTIONS**, **OD-REPORT-EXPORT**, **OD-WS-TRANSFER**, **OD-LANG-02/03/04**, **OD-COVERAGE**, **OD-US-CONTENT** (also confirms the 10-item reclassification).

## 8. Checks run

`reconcile_issues.py check` and `tests/test_production_reconciliation.py`; `execution_packages.py check` and `tests/test_execution_packages.py`; `tests/test_r1_scope_exclusions.py`; `tests/test_testclient_cookie_precedence.py`; the identity evaluator on both dependency sets; `ruff`; compile check; shard plan verification; the product-positioning, release-matrix and admin-design evaluators; the full backend suite on a fresh install of the latest allowed dependencies. GitHub CI on PR #212 is reported with the pushed SHA.

## 9. Evidence needed for E8 and E10

| Gate | Status | Evidence still needed |
|---|---|---|
| E1 to E7, E9 | PASS | unchanged: current state, 38 packages with fields, tracks and integration order, technical options, schedule, briefs (including 01D), all deliverables, no application change |
| **E8** Documentation, reconciliation and static checks pass; CI green | IN PROGRESS | Green GitHub CI on the corrected PR #212 head: four shards, evaluators and guards, evaluation extras, static guards, frontend, Playwright, Streamlit smoke, legacy live component, aggregate check |
| **E10** Owner approval to start Phase 01 | PENDING (owner) | Written approval; OD-SCOPE-01 answer (S1, S2, S3 or a later date) with the real capacity; confirm or reject the 10-item reclassification; OD-GATE-THRESHOLDS and OD-ADMIN-NAV |

## 10. Recommended first implementation PRs (two independent co-first PRs, on separate workstreams, sharing no files)

1. **05A PR 1: complete the staging topology as code** (worker service, knowledge and index volumes, ClamAV service, environment template), without deploying it. It is the longest pole and the premise of every hosted drill.
2. **01A PR 1: injection corpus, evaluator, risk score and quarantine.** The P0 reviewer finding; no infrastructure decision; the evaluator reports without gating until OD-GATE-THRESHOLDS is answered.

Start 01B, 02A, 03A and 06A beside them (no shared files). Phase 01 starts only after owner approval.
