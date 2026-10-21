# Delivery Schedule (Phase 00)

**Status:** GENERATED from the package definitions; PROPOSED. R1.0 is the owner's target of 30 November 2026; safety, privacy, licensing and operational gates are not waived to meet it. Weeks run Monday to Friday; the freeze is the end of W5 (27 November) and release is 30 November.

## Package schedule by week

| Package | W0 | W1 | W2 | W3 | W4 | W5 |
|---|---|---|---|---|---|---|
| 00A Governance, reviewers and owner decisions | # | # |  |  |  |  |
| 00B Scope reconciliation delta (documentation only |  |  |  |  |  | # |
| 01A Prompt-injection corpus, risk score and quaran |  | # | # |  |  |  |
| 01D Tool-call authorization layer (REVIEW-01 part  |  |  |  | # | # |  |
| 01B0 Prompt asset format and loader contract (inter |  | # |  |  |  |  |
| 01B Externalized, versioned prompts (REVIEW-02) |  | # | # |  |  |  |
| 01C Tool registry parity (REVIEW-03) |  |  |  |  |  | # |
| 02K Knowledge runtime and manifest contract (inter |  | # |  |  |  |  |
| 02A Permanent Knowledge reliability: persistence,  |  | # | # | # |  |  |
| 02B Embedding integrity and index manifests (REVIE |  |  | # | # |  |  |
| 02C Real malware scanning for uploads |  |  |  |  | # | # |
| 02D Market source qualification and licensing (sel |  |  |  | # | # | # |
| 02E Retrieval quality and the frozen beta-scope co |  |  |  | # | # | # |
| 03A Admin navigation foundation (REQ-OWN-08) |  | # | # |  |  |  |
| 03B Admin Plans: Basic/Premium management (REQ-OWN |  |  |  | # | # |  |
| 03C Admin Users: complete user management (REQ-OWN |  |  |  | # | # |  |
| 03K Admin metric and report contract (interface pa |  | # |  |  |  |  |
| 03D1 Command Center metrics and AI operations read  |  |  |  | # | # |  |
| 03D2 Command Center and AI operations views (REQ-OW |  |  |  |  | # | # |
| 03E1 Reports registry, governed builder, saved conf |  |  | # | # | # |  |
| 03E2 Reports catalogue, builder and export views (R |  |  |  |  | # | # |
| 04A Story Bank completion (REQ-OWN-06) |  |  | # | # |  |  |
| 04B Workspaces completion (REQ-OWN-07) |  |  | # | # |  |  |
| 04C Agent streaming and cancellation (REVIEW-05) |  |  |  | # | # |  |
| 04D Candidate journey reliability (REQ-CAND-01) |  |  |  | # | # | # |
| 04E Invitation-only registration (REQ-BETA-01) |  |  |  |  | # | # |
| 04F Browser dictation disclosure and verification |  |  |  |  |  | # |
| 05A Hosted topology and platform hardening |  | # | # |  |  |  |
| 05B Persistence, backup, restore and rollback dril |  |  |  | # | # | # |
| 05C Observability, alerting and provider resilienc |  |  |  | # | # | # |
| 05D Identity, email and rate limiting live |  |  |  |  | # | # |
| 05E Privacy, legal and data-rights readiness |  | # | # | # |  |  |
| 06A Locale audit and language boundaries |  | # | # |  |  |  |
| 06B Per-language journeys, Story Bank and Workspac |  |  |  | # | # | # |
| 06C Per-language AI behaviour: prompts, interview  |  |  | # | # |  |  |
| 06D Multilingual retrieval and cross-language attr |  |  |  |  | # | # |
| 06E Per-language injection, security and privacy s |  |  |  |  | # | # |
| 06F Native review and legal translation qualificat |  |  | # | # | # | # |
| 06G Independent human AI evaluation |  |  |  | # | # | # |
| 06H Language activation control: fail-closed enfor |  |  |  |  | # | # |
| 07A Deferral inaccessibility and engineering hygie |  |  |  |  | # | # |
| 07B Live grounding and agent-policy validation |  |  |  |  | # | # |
| 07C Residual live verifications |  |  |  |  |  | # |
| 08A0 Release evidence pipeline (continuous integrat |  |  | # | # |  |  |
| 08A Freeze and owner go/no-go |  |  |  |  |  |  |

Weeks: W0 = 21-25 Oct; W1 = 26 Oct-1 Nov; W2 = 2-8 Nov; W3 = 9-15 Nov; W4 = 16-22 Nov; W5 = 23-27 Nov; W6 = 30 Nov-4 Dec; W7 = 7-11 Dec; W8 = 14-18 Dec; W9 = 21-25 Dec; W10 = 28 Dec-1 Jan; W11 = 4-8 Jan; W12 = 11-15 Jan.

## Phases mapped to weeks

| Phase | Name | Packages | Weeks |
|---|---|---|---|
| 00 | Programme readiness and governance (this phase) | 00A, 00B | W0-W5 |
| 01 | Track A foundations: injection defence, versioned prompts, tool registry | 01A, 01D, 01B0, 01B, 01C | W1-W6 |
| 02 | Track B: Knowledge persistence, embedding integrity, scanning, source qualification | 02K, 02A, 02B, 02C, 02D, 02E | W1-W6 |
| 03 | Track C: Admin 2.0 navigation, plans, users, Command Center, reports | 03A, 03B, 03C, 03K, 03D1, 03D2, 03E1, 03E2 | W1-W6 |
| 04 | Track D: Story Bank, Workspaces, streaming, journey reliability, invitations | 04A, 04B, 04C, 04D, 04E, 04F | W2-W6 |
| 05 | Track E: hosted topology, restore drills, observability, identity, privacy/legal readiness | 05A, 05B, 05C, 05D, 05E | W1-W6 |
| 06 | Track F: seven-language programme and human qualification | 06A, 06B, 06C, 06D, 06E, 06F, 06G, 06H | W1-W6 |
| 07 | Integration and hardening: deferral inaccessibility, live validation | 07A, 07B, 07C | W4-W6 |
| 08 | Freeze, release evidence and beta readiness | 08A0, 08A | W2-W7 |

Phases are groupings for sequencing and review, not strict serial stages: Phases 01 to 06 run in parallel across tracks where their dependencies allow; Phases 07 and 08 are sequential at the end.

## Weekly milestones and measurable exit gates

| Week | Milestone | Exit gate (measurable) |
|---|---|---|
| W0 21-25 Oct | PR #212 merged by the owner; people named; first-wave decisions made | OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS and OD-RESOURCE answered (OD-SCOPE-01, OD-ADMIN-NAV, OD-INVITE and OD-MALWARE are already resolved); integration lead, DevOps lead and QA lead named; reviewers A, B, C appointed (00A) |
| W1 26 Oct-1 Nov | Foundations started; first PRs open | 01A corpus and evaluator merged; 01B loader merged with byte-identical defaults; 02A identity and configuration merged; 03A navigation merged; 05A staging reachable over TLS; 06A seven-language selection; reconciliation delta (00B) decided |
| W2 2-8 Nov | Track A and B core complete; Admin and Story/Workspace build | 01A tool authorization merged; 02A restore drill passed; 04E invitations merged; 03B/03C/03D in review; 04A/04B in review |
| W3 9-15 Nov | Integration of A and B; Track D streaming; hosted drills | 01C parity test in CI; 02B/02C merged; 05B restore drill and rollback recorded; 05C alerts firing on a synthetic outage; 04C streaming on staging; 06C/06E suites green or languages flagged |
| W4 16-22 Nov | Reports, journeys and per-language evidence | 03E merged; 04D journey green on staging for each language that can pass; 06B/06D evidence; 02E both coverage measures reported; 07B live validation within budget; human review in progress |
| W5 23-27 Nov | Freeze, evidence and go/no-go | Freeze at one SHA; 07A inaccessibility suite green; PG-01 to PG-15 and LG-01 to LG-14 evidence assembled; reconciliation check passes; owner go/no-go recorded |
| 30 Nov | R1.0 beta | Invitations sent only for languages and markets whose gates passed |

## Work that can safely run in parallel

- Track A (01A, 01B), Track B (02A), Track C (03A) and Track E (05A, 05E) share no files in W1 and start together; 06A also starts in W1.
- 03B, 03C, 03D, 04A, 04B and 04E run in parallel in W2 once 03A has landed; 04A and 04B touch separate modules.
- 05B, 05C and 05D run in parallel in W3 after 05A; 02B and 02C run in parallel after 02A; 06C and 06E run in parallel after 01A, 01B and 06A.
- Native review, legal translation, counsel review and licence review (02D, 05E, 06F, 06G) are calendar-bound and start in W1 regardless of engineering.

## Capacity and feasibility (computed)

- Package effort total: **209 to 325 ideal engineering days** across 45 packages.
- Window: W1 to W5 = 25 working days. With 70% utilisation (review, CI waits, rework: an assumption) one stream delivers about 17.5 productive days.
- Parallel streams needed to fit the total in the window: **11.9 to 18.6** (one stream = one engineer or one focused agent session; the owner's real capacity is not recorded anywhere and is an input needed for OD-SCOPE-01).
- Critical path lower bound: 18 to 27 days of strictly sequential effort inside a 25-working-day window, before any human review lead time.

| Parallel streams | Productive days available | Covers minimum estimate | Covers maximum estimate |
|---|---|---|---|
| 1 | 18 | no | no |
| 2 | 35 | no | no |
| 3 | 52 | no | no |
| 4 | 70 | no | no |
| 6 | 105 | no | no |
| 8 | 140 | no | no |
| 10 | 175 | no | no |
| 12 | 210 | yes | no |

## Early parallel workstream: deployment topology and Knowledge persistence

02A (Knowledge persistence, environment identity, restore), 05A (hosted topology) and 05E (privacy and legal readiness, calendar-bound) are long poles: they need an owner decision, a topology fix, repeatable drills and human lead time, and nothing else can be proven on a hosted stack without them. They start in W1 alongside Track A with the highest staffing priority and are tracked as a separate early workstream. **The existing `deploy/docker-compose.staging.yml` must not be deployed as it stands** (it has no worker, no knowledge or index volume and no ClamAV service); the first 05A PR completes the topology as code without deploying it.

## Scope tiers and the strategies considered for OD-SCOPE-01 (the owner SELECTED S1, the full scope; S2 and S3 were REJECTED as release plans and are kept only as capacity analysis)

| Tier | Meaning | Packages | Effort (days) | Cumulative effort (days) | Streams for the cumulative total |
|---|---|---|---|---|---|
| T0 | Non-negotiable for any real-user beta (safety, privacy, hosting, knowledge, identity, language gates) | 21 | 95-151 | 95-151 | 5.4-8.6 |
| T1 | Reviewer corrections and operator safety | 5 | 23-35 | 118-186 | 6.7-10.6 |
| T2 | Owner core capabilities (candidate journeys, Story Bank, Workspaces, quality evidence) | 9 | 55-83 | 173-269 | 9.9-15.4 |
| T3 | Admin 2.0 expansion beyond the existing Admin | 6 | 27-42 | 200-311 | 11.4-17.8 |
| T4 | Verification extras and proposals | 4 | 9-14 | 209-325 | 11.9-18.6 |

**Rejected alternative S2 (restricted free private beta), kept for information:** deliver tiers T0 to T2 (173 to 269 days, 9.9 to 15.4 streams) and defer tier T3 (Admin 2.0 expansion) to R1.2 and tier T4 (verification extras) to follow-up, with these restrictions, every one an owner decision still to be made:

1. A small invitation-only cohort capped by the owner (size is an owner decision), limiting support, abuse and AI-cost exposure.
2. Languages and markets are activated only where their gates pass at the freeze; expect fewer than seven languages and one or two qualified EU markets at launch (a failed mandatory gate prevents activation, as the owner decided). The others stay hidden and documented.
3. Candidate core only: Mo, Practice, Story Bank, Workspaces with VIEW-only sharing, History, Progress, privacy controls.
4. Safety, privacy, hosting, knowledge and identity gates are unchanged (tier T0); reviewer corrections REVIEW-01 to REVIEW-05 stay in scope (T0 and T1).
5. Admin: owner-operated with the new navigation and user management; the existing Command Center, plan assignment and six aggregate reports stay as built; dashboards, the plan editor, comparison and preview, and the report builder move to R1.2.
6. No live billing; Basic and Premium as free beta tiers.
7. Live re-validation extras (07B, 07C) and the dictation review (04F) are follow-ups; the deterministic evaluators still run.

**Owner decision (2026-10-21): S1, the full originally agreed R1.0 scope, is selected; S2 and S3 are rejected as November release plans.** The restrictions listed above are NOT in force: no R1.0 product requirement is removed, downgraded or postponed to meet a delivery target. See `STAFFING_AND_CRITICAL_PATH_PLAN.md` for the staffing and critical-path plan for S1.

## Capacity analysis (information only)

Which cumulative tiers fit a given number of parallel streams in the W1 to W5 window (one stream = one engineer or one focused agent session at 70% utilisation, an assumption; the real capacity is not recorded):

| Parallel streams | Productive days | Tiers that fit the MAXIMUM estimate | Tiers that fit the MINIMUM estimate |
|---|---|---|---|
| 3 | 52 | not even T0 | not even T0 |
| 5 | 88 | not even T0 | not even T0 |
| 8 | 140 | not even T0 | T0 to T1 |
| 11 | 192 | T0 to T1 | T0 to T2 |
| 14 | 245 | T0 to T1 | T0 to T4 |
| 17 | 298 | T0 to T2 | T0 to T4 |

### Strategy comparison (S1 selected by the owner; S2 and S3 rejected as release plans)

| Strategy | Content | Effort (days) | Streams needed | Packages | Critical path (days) |
|---|---|---|---|---|---|
| S1 Full R1.0 scope (OWNER-SELECTED) | Every package (tiers T0 to T4) | 209-325 | 11.9-18.6 | 45 | 18-27 via 02A > 05B > 08A |
| S2 Restricted free private beta (REJECTED) | Tiers T0 to T2; Admin 2.0 expansion (03B, 03D, 03E) to R1.2; verification extras (07B, 07C, 04F, 00B) as follow-ups | 173-269 | 9.9-15.4 | 35 | 18-27 via 02A > 05B > 08A |
| S3 Minimum safe beta (REJECTED) | Tiers T0 and T1 plus candidate journey reliability (04D); Story Bank and Workspaces completion (04A, 04B), Admin user management (03C), retrieval calibration (02E), per-language AI and journey work beyond the activation gates (06B, 06C, 06D) and independent human evaluation (06G) are limited to what the activation gates strictly require or move to R1.2; this moves owner-requested R1.0 items out of R1.0 and needs explicit owner approval | 124-195 | 7.1-11.1 | 27 | 18-27 via 02A > 05B > 08A |

Reading: with 3 to 5 streams not even the non-negotiable tier T0 fits at its maximum estimate, so a real-user beta by 30 November needs a larger effort or a later date regardless of what else is cut. The tiers define the order in which scope is added as capacity allows.


## Measured first-wave throughput and what it does and does not say

| Package | Estimate (days) | Authoring wall-clock (minutes) | Rework rounds | Review latency | GitHub CI duration |
|---|---|---|---|---|---|
| 05A | 8-12 | 11 | 0 | no PR yet | no PR yet |
| 01A | 5-8 | 24 | 0 | no PR yet | no PR yet |
| 02K | 2-3 | 32 | 1 | no PR yet | no PR yet |
| 01B0 | 2-3 | 24 | 0 | no PR yet | no PR yet |
| 03K | 2-3 | 34 | 0 | no PR yet | no PR yet |
| 03A | 5-7 | 29 | 0 | no PR yet | no PR yet |
| 06A | 4-6 | 43 | 0 | no PR yet | no PR yet |

Seven first-wave packages were authored in 197 agent-minutes in total (each agent ran in parallel; roughly 10 to 45 minutes per package, including about 15 minutes lost to the shared interpreter fault), against estimates of 2 to 12 engineering days each. **This measures authoring of contract, scaffolding and test-writing work only.** It excludes human review, GitHub CI (no PR exists, so none ran), integration, live validation, rework after review, native and legal review and every calendar-bound step, and the first wave was deliberately the smallest, best-bounded packages. It is NOT evidence about the heavier packages (02A, 02B, 03D1, 03E1, 04A to 04D, 05B to 05D) and no estimate has been changed because of it.

Sensitivity of the full-scope completion date to the true effort (profile 'D ramp 12, 18, 24', high estimate scaled; a sensitivity table, not a forecast):

| Effort relative to the estimate | Completes | Binding constraint |
|---|---|---|
| 100% | day 33, Wed 09 Dec 2026 | engineering chain |
| 50% | day 26, Mon 30 Nov 2026 | engineering chain |
| 25% | day 23, Thu 26 Nov 2026 | calendar-bound human and legal lead times (assumed), then review capacity |
| 10% | day 21, Tue 24 Nov 2026 | calendar-bound human and legal lead times (assumed), then review capacity |

If engineering effort proves much smaller than estimated, the date stops being engineering-bound and becomes bound by the assumed human lead times (native review, legal qualification, licensing, independent evaluation) and by review capacity for roughly 60 pull requests. That is why the first-wave PRs need real reviewers and real CI evidence before the forecast is changed.


See `PHASE_00_EXIT_REPORT.md` for the Phase 00 assessment and `STAFFING_AND_CRITICAL_PATH_PLAN.md` for the S1 staffing plan.
