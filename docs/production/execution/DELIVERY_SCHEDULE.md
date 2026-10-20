# Delivery Schedule (Phase 00)

**Status:** GENERATED from the package definitions; PROPOSED. R1.0 is the owner's target of 30 November 2026; safety, privacy, licensing and operational gates are not waived to meet it. Weeks run Monday to Friday; the freeze is the end of W5 (27 November) and release is 30 November.

## Package schedule by week

| Package | W0 | W1 | W2 | W3 | W4 | W5 |
|---|---|---|---|---|---|---|
| 00A Governance, reviewers and owner decisions | # | # |  |  |  |  |
| 00B Scope reconciliation delta (documentation only |  | # |  |  |  |  |
| 01A Prompt-injection security and tool authorizati |  | # | # |  |  |  |
| 01B Externalized, versioned prompts (REVIEW-02) |  | # | # |  |  |  |
| 01C Tool registry parity (REVIEW-03) |  |  |  | # |  |  |
| 02A Permanent Knowledge reliability: persistence,  |  | # | # |  |  |  |
| 02B Embedding integrity and index manifests (REVIE |  |  |  | # |  |  |
| 02C Real malware scanning for uploads |  |  |  | # |  |  |
| 02D Market source qualification and licensing (sel |  |  | # | # | # |  |
| 02E Retrieval quality and the frozen beta-scope co |  |  |  |  | # |  |
| 03A Admin navigation foundation (REQ-OWN-08) |  | # |  |  |  |  |
| 03B Admin Plans: Basic/Premium management (REQ-OWN |  |  | # | # |  |  |
| 03C Admin Users: complete user management (REQ-OWN |  |  | # | # |  |  |
| 03D Command Center and AI operations (REQ-OWN-01) |  |  | # | # |  |  |
| 03E Reports and governed custom report builder (RE |  |  |  |  | # | # |
| 04A Story Bank completion (REQ-OWN-06) |  |  | # | # |  |  |
| 04B Workspaces completion (REQ-OWN-07) |  |  | # | # |  |  |
| 04C Agent streaming and cancellation (REVIEW-05) |  |  |  | # | # |  |
| 04D Candidate journey reliability (REQ-CAND-01) |  |  |  |  | # |  |
| 04E Invitation-only registration (REQ-BETA-01) |  |  | # |  |  |  |
| 04F Browser dictation disclosure and verification |  |  |  | # |  |  |
| 05A Hosted topology and platform hardening |  | # | # |  |  |  |
| 05B Persistence, backup, restore and rollback dril |  |  |  | # |  |  |
| 05C Observability, alerting and provider resilienc |  |  |  | # |  |  |
| 05D Identity, email and rate limiting live |  |  |  | # |  |  |
| 05E Privacy, legal and data-rights readiness |  | # | # | # | # |  |
| 06A Locale audit and language boundaries |  | # |  |  |  |  |
| 06B Per-language journeys, Story Bank and Workspac |  |  |  |  | # |  |
| 06C Per-language AI behaviour: prompts, interview  |  |  |  | # |  |  |
| 06D Multilingual retrieval and cross-language attr |  |  |  |  | # |  |
| 06E Per-language injection, security and privacy s |  |  |  | # |  |  |
| 06F Native review and legal translation qualificat |  |  | # | # | # | # |
| 06G Independent human AI evaluation |  |  |  |  | # | # |
| 07A Deferral inaccessibility and engineering hygie |  |  |  |  |  | # |
| 07B Live grounding and agent-policy validation |  |  |  |  | # |  |
| 07C Residual live verifications |  |  |  |  | # |  |
| 08A Freeze, release evidence and beta readiness |  |  |  |  |  | # |

Weeks: W0 = 21-25 Oct; W1 = 26 Oct-1 Nov; W2 = 2-8 Nov; W3 = 9-15 Nov; W4 = 16-22 Nov; W5 = 23-27 Nov.

## Phases mapped to weeks

| Phase | Name | Packages | Weeks |
|---|---|---|---|
| 00 | Programme readiness and governance (this phase) | 00A, 00B | W0-W1 |
| 01 | Track A foundations: injection defence, versioned prompts, tool registry | 01A, 01B, 01C | W1-W3 |
| 02 | Track B: Knowledge persistence, embedding integrity, scanning, source qualification | 02A, 02B, 02C, 02D, 02E | W1-W4 |
| 03 | Track C: Admin 2.0 navigation, plans, users, Command Center, reports | 03A, 03B, 03C, 03D, 03E | W1-W5 |
| 04 | Track D: Story Bank, Workspaces, streaming, journey reliability, invitations | 04A, 04B, 04C, 04D, 04E, 04F | W2-W4 |
| 05 | Track E: hosted topology, restore drills, observability, identity, privacy/legal readiness | 05A, 05B, 05C, 05D, 05E | W1-W4 |
| 06 | Track F: seven-language programme and human qualification | 06A, 06B, 06C, 06D, 06E, 06F, 06G | W1-W5 |
| 07 | Integration and hardening: deferral inaccessibility, live validation | 07A, 07B, 07C | W4-W5 |
| 08 | Freeze, release evidence and beta readiness | 08A | W5-W5 |

Phases are groupings for sequencing and review, not strict serial stages: Phases 01 to 06 run in parallel across tracks where their dependencies allow; Phases 07 and 08 are sequential at the end.

## Weekly milestones and measurable exit gates

| Week | Milestone | Exit gate (measurable) |
|---|---|---|
| W0 21-25 Oct | Phase 00 approved; decisions made; people named | Owner approves Phase 00; OD-SCOPE-01, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-INVITE, OD-MALWARE answered; reviewers A, B, C appointed (00A) |
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

- Package effort total: **196 to 303 ideal engineering days** across 37 packages.
- Window: W1 to W5 = 25 working days. With 70% utilisation (review, CI waits, rework: an assumption) one stream delivers about 17.5 productive days.
- Parallel streams needed to fit the total in the window: **11.2 to 17.3** (one stream = one engineer or one focused agent session; the owner's real capacity is not recorded anywhere and is an input needed for OD-SCOPE-01).
- Critical path lower bound: 26 to 39 days of strictly sequential effort inside a 25-working-day window, before any human review lead time.

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

See `PHASE_00_EXIT_REPORT.md` for the November feasibility assessment and scope options.
