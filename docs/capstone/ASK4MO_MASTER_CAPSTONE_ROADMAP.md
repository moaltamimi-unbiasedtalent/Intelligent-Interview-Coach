# Ask4Mo Master Capstone Roadmap (state tracker)

Created in P10C-0 at main `67edfda085e21768501234d79674822ecc257b92` (Alembic head `0034_preparation_packs`). Before this wave the file did not exist (confirmed by the P5-B report and by repository search); nothing about earlier contents is invented.

**Authority and scope.** `docs/capstone/capstone_phase_plan.md` remains the single canonical statement of phase SCOPE and sequence. This file is a derived STATE TRACKER over that plan: it does not redefine scope, it records, per remaining workstream, the engineering state, the evidence state, the acceptance status, dependencies and open owner decisions, taken from repository evidence. Where this file and the phase plan disagree on scope, the phase plan wins; where a status here disagrees with a per-wave document, the per-wave document wins and this file is to be corrected. Nothing is marked complete without cited evidence.

**Vocabulary.** Engineering state: NOT STARTED, PLANNED, IN PROGRESS, CODE COMPLETE, MERGED. Evidence state: NONE, OFFLINE (deterministic, mocked, synthetic), LOCAL BUILD (depends on a developer's local stores), LIVE (provider or production-like), HUMAN. Acceptance: NOT ACCEPTED, PARTIAL, CODE QUALIFIED, OWNER ACCEPTED.

## 1. Remaining workstreams
| Workstream | Engineering state | Evidence state | Acceptance status | Depends on | Open owner decisions |
|---|---|---|---|---|---|
| **P10C** Global Career Intelligence and Compensation V2 | PLANNED. P10C-0 (this wave) delivered the recovered-scope analysis and execution plan only; no ingestion or Compensation V2 code started | NONE for implementation. Planning evidence only | NOT ACCEPTED | P5-B merged (done); owner source and licence approvals | D-01 to D-09 in `p10/P10C_GLOBAL_CAREER_COMPENSATION_EXECUTION_PLAN.md` (GKB-0..18 document and C1-C4 contract are UNRECOVERED) |
| **P10D** Global KB and multilingual requalification | NOT STARTED | NONE | NOT ACCEPTED | P10C (occupation graph, mappings, compensation evidence, registry, aliases, precedence, coverage metadata, fixtures) | Language and geography coverage priorities |
| **W12.4E** Governed Speech Providers | NOT STARTED | NONE (existing voice work P7/P7.5: architecture deterministic, LIVE NOT RUN) | NOT ACCEPTED | W12.4B secret store (done); provider choice recorded (Whisper STT, Kyutai Pocket TTS) | Provider licensing and hosting; Russian stays excluded from speech |
| **W12.4F** Admin Configuration Completeness | NOT STARTED | NONE | NOT ACCEPTED | W12.4A to W12.4D (done as per their documents) | Which capabilities must be Admin-governed before launch |
| **W12.5** Preferred Admin UX Corrections | NOT STARTED | NONE | NOT ACCEPTED | W12.4F | Reassessment of low findings after W12.4 |
| **P10E** Live Capability Validation | NOT STARTED | NONE | NOT ACCEPTED | P10D; separate owner authorization for paid and live runs | Budget and scope of live validation |
| **Integrated Candidate/Admin/Operations Requalification** | NOT STARTED | NONE (P5-B is the last integrated offline qualification, product scope only) | NOT ACCEPTED | W12.4E, W12.4F, W12.5 | Scope of re-run |
| **RC-P10-004** successor release candidate | NOT CREATED | NONE | NOT ACCEPTED | Integrated requalification green; separate owner-approved creation | Creation approval |
| **P10F** Final targeted human validation | NOT STARTED | HUMAN evidence exists only for Pilot 2 on RC-P10-003 (3 complete sessions) | NOT ACCEPTED | P10E | Participants and protocol |
| **AC-24** acceptance closure | not an engineering item | PARTIAL: Pilot 2 evidence on RC-P10-003 (verdict conditional go, remediation required) | **PARTIAL** until successor-RC criteria are met | RC-P10-004 and P10F | Closure criteria confirmation |
| **P11** Final Capstone packaging and submission | NOT STARTED | NONE | NOT ACCEPTED | all above | Submission scope and date |

## 2. Delivered tracks (summary with pointers; details live in the per-wave documents)
- P10B waves W1 to W11 and Pilot-2 remediation: merged; integrated matrix 99 rows (88 PASS, 11 ACCEPTED, 0 BLOCKER) at W11; RC-P10-003 created (artifact RC, immutable; RC-P10-002 historical).
- W12.4A knowledge accessibility: complete (per phase plan). W12.4B secure secrets: complete. W12.4C email and identity: code qualified, live Brevo verification pending. W12.4D billing foundation and Basic/Premium product waves P1 to P5-B: code qualified, offline and synthetic, **commercial activation disabled** (all six billing gates and all six product rollout gates are False in code).
- P5-B (PR #176) added PostgreSQL execution evidence (isolated throwaway server) for quota, Pack and the full migration chain, and remediated four baseline evaluators; product coverage stays BELOW GATE.

## 3. Cross-cutting dependencies and open gaps (tracked, not hidden)
| Item | State | Evidence |
|---|---|---|
| Product coverage quality gate (`eval_product_coverage`) | **BELOW GATE**: `insufficient_evidence` 93.7% (386 of 412) against 95%; CLI prints 94%; result depends on gitignored local stores and the committed summary (97%) is stale | P5-B document section 33; P10C-0 plan section 7: all 26 unhandled cases inspected; 13 have official data locally and fail on occupation-graph wiring, 13 involve ambiguous occupations needing an owner-defined behaviour |
| CI-reproducible knowledge evaluation fixture | DESIGNED in P10C-0, not implemented (planned in P10C wave G) | plan section 8 |
| Research-cache evaluator isolation | UNRESOLVED | earlier waves |
| Knowledge ingestion security hardening | OPEN | W10.8 and W12.4A documents |
| Live Redis validation | NOT TESTED | P2-A, P4-A |
| Actual model-quality validation (Fast vs Balanced vs Advanced; Pack, analytics narrative) | NOT TESTED (offline harness only) | P2-C, P5-A, P5-B |
| Numerical Basic and Premium allowances, reset periods | NOT APPROVED | P4-A |
| Premium pricing; Ask4Mo UG incorporation; dedicated Stripe account; Stripe sandbox and lifecycle validation | NOT APPROVED / PENDING | billing documents |
| Basic-to-Fast production activation, grandfathering, transition notice | NOT APPROVED | P2-C, P3 |
| Brevo live verification | PENDING | W12.4C |
| Mo and company-research cost-ledger coverage | GAP, accepted with rationale | P5-B section 16 |
| Hosted multi-instance PostgreSQL and analytics query plans | NOT TESTED | P5-B |
| Legal and privacy review of AI-guidance and source-excerpt wording | PENDING | P5-A, P5-B |

## 4. Reconciliation notes (discrepancies found, none silently fixed)
- The phase plan section "W12.4 ... (PLANNED, owner-approved, NOT STARTED)" and the sentence "None of these has started" in the "Current next sequence" paragraph are stale: W12.4A, W12.4B, W12.4C and the W12.4D waves have documents and rows stating completion or code qualification. The per-wave rows are the authority; the stale headings are to be corrected by the owner or in a documentation wave.
- The phase plan states that no competing master plan should be created; this file is therefore a state tracker with explicit non-authority over scope.
- P5-B recorded 12 education and career-outlook coverage cases as P10D-dependent; P10C-0 found evidence that they belong to P10C scope. The original classification is preserved there and the re-attribution awaits owner decision D-06.

## 5. Programme sequence (unchanged from the phase plan)
P10C, P10D, W12.4E, W12.4F, W12.5, Integrated Candidate/Admin/Operations requalification, RC-P10-004, AC-24 closure where the criteria are met, P10E, P10F, P11 as recorded in the phase plan's revised sequence; P10C and P10D remain separate workstreams and P10E live validation remains required for applicable capabilities. Academic Capstone submission requirements are distinct from commercial launch prerequisites.
