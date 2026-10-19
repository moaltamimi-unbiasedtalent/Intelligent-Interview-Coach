# P11 Submission Readiness Plan (PLAN ONLY)

**Status:** PLAN, prepared 2026-10-19 against `main` `4043429`. **P11 is NOT started**: no presentation, report, diagram, demo data or submission artifact is built here. The canonical phase plan keeps P11 as the last workstream; this plan adds detail, it is not another roadmap. No assessment criterion is invented: the official Turing College brief and rubric are not available (`ACADEMIC_SUBMISSION_SCOPE_DECISION.md` section 7), so every course expectation below is a second-hand planning assumption from the project's own runbook and is marked as such. Related: [`ACADEMIC_SUBMISSION_SCOPE_DECISION.md`](ACADEMIC_SUBMISSION_SCOPE_DECISION.md), [`CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`](CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md), [`RC_P10_004_ENTRY_DECISION.md`](RC_P10_004_ENTRY_DECISION.md), [`capstone_presentation_standard.md`](capstone_presentation_standard.md).

## 1. P12 reconciliation (owner direction 2026-10-19)

The reference runbook defines a separate **P12** (final rehearsal and freeze) but the canonical phase plan ends at P11. **Owner direction: fold the proposed rehearsal, final validation and submission-freeze duties into P11. No new top-level P12 is created** unless authoritative course requirements explicitly require one (none are available). The folded duties appear in section 5 (steps 12 to 16). Recorded in the phase plan and in `DI-N IR-P12`.

## 2. Time-critical fact and preconditions

The runbook (not an official source) records the deadline as **2026-10-20** and the feature freeze as 2026-10-13; the same runbook scheduled P11 for 18 October and P12 for 19 October. Today is 2026-10-19. P11 cannot be sized until the owner confirms the deadline and time zone. **Preconditions (owner decisions, none made by engineering):** deadline and time zone; the brief and rubric; the deployment answer (hosted versus local demonstration); handling of the failed 95% coverage gate; whether AC-24 may close without P10F; approval of the current acceptance ledger; whether to create RC-P10-004 or to cite a merged `main` SHA directly.

## 3. Principles

1. Every claim in every artifact must match the running application or a recorded test result; every metric is labelled with code SHA, date, environment, mode (real, offline, mocked, live, human) and sample size (presentation standard).
2. Historical evidence stays historical; a single current evidence index is added, nothing is overwritten.
3. Distinguish deterministic from model-judged and free from paid or live evidence; never present a plan as an implementation or a model inference as verified fact.
4. State the failed coverage gate, the PARTIAL criteria, the absence of human qualification and the deferred work in the main narrative, not in an appendix.
5. Demonstrate only what exists: no production speech, no live billing, no hosted operation, no international source qualification, no Compensation V2 output.
6. Use synthetic data only; no real candidate data and no new paid provider call unless the owner separately authorizes one (15 calls remain; the ledger is never reset).

## 4. Deliverables and where their content comes from

| # | Deliverable | Content source in the repository | Notes |
|---|---|---|---|
| D1 | Final requirements traceability matrix (Sprint 4 versus new Capstone contribution) | `capstone_requirements_matrix.md`, `CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`, `sprint4_requirements_map.md` | Needs the approved single ledger first; Sprint 4 requirements are only the project's paraphrase |
| D2 | Architecture diagrams (authentication, data flow, retrieval, specialist agents, speech) and the application architecture narrative | `capstone_target_architecture.md`, `capstone_security_privacy_architecture.md`, `CLAUDE.md` architecture sections | Text exists; diagrams do not; speech diagram must show server speech DISABLED |
| D3 | LLM and prompt-engineering explanation | `src/copilot/rag/synthesis.py`, `src/agent/policies.py`, `src/llm/models.py` and `policy.py`, P5/E4 and P10E-R2 documents | Include model registry, routing fix and per-operation policy; plan gating is disabled |
| D4 | RAG implementation | P6 and P10C to P10D documents, `P10D_R1_CANDIDATE_GROUNDING_AND_COVERAGE.md` | State coverage 386/412 and 258/412, the 120 evidence-backed cases and the abstention-by-design share |
| D5 | Agentic-workflow explanation | `docs/sprint4_architecture.md`, P5, `P10E_R1` agent results | Three specialists, 11 registered tools, HITL, bounded steps |
| D6 | Security and privacy decisions | W10.x admin documents, `docs/privacy.md`, W9.8, the requalification negative-test table | Privacy and terms are engineering drafts |
| D7 | Model-evaluation methodology and actual results (evaluation report) | `capstone_evaluation_plan.md`, P10E, R1, R2, the evaluator list, live ledger figures | Include dataset versions, sample sizes, costs, honest exclusions (RAGAS live, semantic calibration, no thresholds) |
| D8 | Ethics and privacy report; limitations; implementation challenges; what was learned | `docs/privacy.md`, `docs/learning_notes.md`, the deferred register, R1 and R2 defects found live | The routing and evaluator-harness defects are good, honest learning material |
| D9 | Product demonstration, synthetic demonstration data, **recorded fallback demonstration** | existing synthetic fixtures; Playwright flows as a script basis | Fallback recording protects against a live-demo failure |
| D10 | Technical presentation (and decks), speaking script, reviewer Q&A preparation | `capstone_presentation_standard.md`; runbook says 10 minutes plus 5 minutes of Q&A and three decks (unverified against the course) | Six topics the runbook names: problem, solution, data, evaluation, challenges, what's next; SCR or SMART |
| D11 | Reviewer guide | `docs/sprint4_reviewer_guide.md` as a base, updated | Must point at the register and the ledger |
| D12 | Repository readiness and submission instructions | README, `docs/operations_deployment.md`, runbook | Local startup must be verified from a clean checkout |
| D13 | Release or tag artifact | RC convention (`RC_P10_004_ENTRY_DECISION.md`) | Historical tags must not be modified; whether any artifact is needed is an owner decision |
| D14 | Final acceptance decision | ledger plus owner decisions | Owner decision, recorded |

## 5. Practical P11 checklist (ordered; the last steps carry the folded P12 duties)

| Step | Action | Depends on | Output / evidence |
|---|---|---|---|
| 1 | Owner supplies the deadline, brief, rubric and deployment answer; owner decides the coverage-gate handling, AC-24 and the ledger | none | decision record in the repository |
| 2 | Fix the submission scope and the one merged `main` SHA that every artifact will cite | 1 | SHA recorded in all P11 documents |
| 3 | Verify a clean-checkout local startup (backend, frontend, seeded synthetic demo account) from the README | 2 | recorded transcript; fix README gaps |
| 4 | Build D1 (traceability) and the single current evidence index | 1, 2 | matrix with status classes per row |
| 5 | Build D2 (diagrams and architecture narrative) | 2 | diagrams checked against code |
| 6 | Build D3 to D5 (LLM, prompts, RAG, agents) | 2 | each claim linked to a test or a recorded run |
| 7 | Build D6 and D8 (security, privacy, ethics, limitations, lessons) | 2 | limitations list = register categories and the ledger |
| 8 | Build D7 (evaluation report with actual numbers, labelled) | 2 | numbers copied from run logs, not from memory |
| 9 | Prepare the demo script, synthetic data and the recorded fallback (D9) | 3 | one 10-minute path; no live provider needed |
| 10 | Build the presentation, script and Q&A (D10) | 4 to 9 | rehearsal notes |
| 11 | Reviewer guide and submission instructions (D11, D12) | 4 to 9 | link set |
| 12 | **Folded P12:** full verification replay on the cited SHA (backend, vitest, Playwright, evaluators, Ruff, migrations) | 2 | gate results with counts and SHA |
| 13 | **Folded P12:** timed rehearsal (10 minutes plus 5 minutes of questions, if the course confirms that format) | 10 | rehearsal log |
| 14 | **Folded P12:** golden result and package manifest (what is submitted, with hashes), recorded fallback verified | 12 | manifest |
| 15 | **Folded P12:** submission freeze: no further runtime change; any later change needs new evidence | 14 | freeze note citing the SHA |
| 16 | Final acceptance decision and submission | 15, owner | decision record |

## 6. What the presentation must say plainly

The application works end to end and is extensively tested; the three grounding policies and the live evidence are real but small-sample; the 95% coverage gate failed (6 cases short developer-local, 134 short in a clean checkout, 0 human-qualified); many quality questions rest on human review that has not happened; international knowledge, production speech, billing and hosting are not delivered; and the deferred register (390 issues, 338 active (387 and 336 when PR #204 merged; three added and one closed since)) is the honest list of what remains.

## 7. Risks

Time (the planning deadline is one day away); the missing brief and rubric (assumptions could be wrong); the failed coverage gate and the AC-24 question (an academic reader may weigh them heavily); the deployment question (a hosted requirement would need work that is not planned); documentation volume (more documents than a reviewer can read: the evidence index and ledger must be the entry points).
