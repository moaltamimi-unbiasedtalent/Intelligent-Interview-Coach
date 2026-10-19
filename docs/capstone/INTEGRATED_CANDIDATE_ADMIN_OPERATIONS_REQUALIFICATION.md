# Integrated Candidate / Admin / Operations Requalification

**Status:** EXECUTED 2026-10-19. Branch `feat/integrated-capstone-requalification`, from `origin/main` `fb2d264` (PR #203 merged). Not accepted by the owner, not merged. This is an **academic engineering qualification, not production approval.** It does not create RC-P10-004, does not begin P11, activates no commercial feature and changes no acceptance threshold.

Supporting documents (this report links to them instead of repeating them): [`POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md`](POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md) (identifiers `DI-...`), [`PRE_SUBMISSION_ACCEPTANCE_GATES.md`](PRE_SUBMISSION_ACCEPTANCE_GATES.md), and the canonical `capstone_phase_plan.md` / `ASK4MO_MASTER_CAPSTONE_ROADMAP.md`.

## 1. Verdict

| Question | Answer |
|---|---|
| Any BLOCKER or HIGH defect found in the implemented system? | **No** new BLOCKER or HIGH. One LOW defect (a stale legal-acceptance claim in the data export) was found and fixed with a test. |
| Do the automated gates pass on this tree? | Yes: backend, vitest, ESLint, `tsc`, Playwright (412), 52 CI evaluator commands, Ruff, compile, diff check, single Alembic head. |
| Does the 95% product-coverage gate pass? | **No. COVERAGE GATE: FAIL** (386/412 developer-local, 258/412 clean checkout). Not renamed, not excepted. |
| AC-24? | Stays **PARTIAL**. |
| Is the system suitable for the remaining capstone milestones? | **CONDITIONAL GO**: suitable to proceed to the owner's decisions and P11 planning, on the conditions in section 17. Not suitable to be described as production-ready, human-qualified or fully gate-compliant. |
| RC-P10-004 | **NO-GO now**: entry conditions 7 and 8 are undefined and the coverage gate fails (section 17). |

## 2. Environment and versions tested

- Starting `main` SHA: `fb2d264`. Alembic head `0039_speech_governance` (single head). 44 Admin permissions (`len(PERMISSIONS) == 44`).
- Backend: Python 3.11 venv, SQLite temp databases per test, `pytest -n 4`. Frontend: Next.js 15 / React 19, vitest, ESLint, `tsc`, Playwright (chromium, serial, production build on port 3015).
- Models: effective Balanced `openai/gpt-5.4` (live evidence from earlier waves only). **No live provider call, no new paid call and no ledger use occurred in this wave.** Ledger unchanged: 285 of 300 calls, USD 2.112 committed, 15 calls and USD 7.888 remaining; genesis `ff65d285…`.
- Synthetic identities and fixtures only; no real candidate data left the machine.

## 3. Evidence classes used

REAL (executed against real local code and a real SQLite database or browser), OFFLINE (deterministic with scripted doubles, no provider), MOCKED (a double stands in for a provider), LIVE (a real provider call; none in this wave), NOT TESTED, PRODUCTION QUALIFIED (nothing is). Every row below states its class; nothing is labelled production-qualified.

## 4. Candidate journey matrix

| Area | Evidence (test or spec) | Class | Result |
|---|---|---|---|
| Account creation, login, logout, session expiry | `tests/test_auth*.py`, `test_integrated_requalification.py::test_expired_or_forged_authentication...`, `e2e/auth.spec.ts` | REAL | PASS (forged cookie, logout and DB-expired session all rejected) |
| Onboarding, welcome, tutorial | `e2e/onboarding.spec.ts`, `welcome-tutorial.spec.ts`, `tutorial.spec.ts`, `tests/test_wave2_onboarding.py` | REAL | PASS |
| Opportunity selection and context | `e2e/opportunities.spec.ts`, `opportunity-practice.spec.ts`, `tests/test_opportunity_journey.py` | REAL | PASS |
| JD analysis, candidate background, gaps, plan | `tests/test_agent_*`, `e2e/agent-coach.spec.ts`, `journey.spec.ts` (tools deterministic or doubled) | OFFLINE/MOCKED | PASS; live model behaviour only from P10E (22 cases, tool selection 0.773 aggregate) |
| Career Knowledge, retrieval, citations | `tests/test_candidate_grounding_policy.py`, `e2e/career.spec.ts`, `eval_knowledge_governance` | OFFLINE | PASS |
| Insufficient evidence, clarification, contextual cited abstention, unsupported salary prevention | policy tests (77), integrated Career-path tests in 7 languages, replay of 14 recorded real answers | OFFLINE + recorded LIVE outputs | PASS (section 9) |
| Agent tool selection, HITL checkpoints | `tests/test_agent_hitl*.py`, `test_agent_tool_selection.py`, `eval_agent` | OFFLINE | PASS |
| Interview practice (questions, answers, feedback) | `tests/test_interview_*`, `e2e/interview.spec.ts`, `return-response.spec.ts`; live harness from R1 (7 roles, human review PENDING) | REAL/OFFLINE | PASS deterministic; quality NOT VERIFIED by humans |
| Progress, history, sources and provenance | `e2e/progress.spec.ts`, `reports.spec.ts`, `product-surfaces.spec.ts` | REAL | PASS |
| Export, deletion, Privacy Center | `tests/test_w98_privacy_controls.py`, `test_privacy_legal_w10_10.py`, `e2e/data-privacy.spec.ts`, integrated export test | REAL | PASS (export wording defect fixed) |
| Recovery and error paths | `e2e/service-recovery.spec.ts`, `service-resilience.spec.ts`, provider-failure integrated tests | REAL/MOCKED | PASS |
| Mobile and accessibility | `e2e/w11-visual-a11y.spec.ts`, mobile no-overflow specs | REAL (chromium only) | PARTIAL: no real device, cross-browser or screen-reader testing (DI-G) |
| Professions | section 8 | OFFLINE | PARTIAL |
| Human user acceptance | none | NOT RUN | not fabricated |

## 5. Admin journey matrix

| Area | Evidence | Class | Result |
|---|---|---|---|
| Platform Admin and specialist roles; 44-permission baseline; least privilege | `test_admin_qualification_w10_14.py` (43 x 7 matrix, extended), `eval_admin_qualification`, `eval_admin_foundation`, integrated tests (candidate and support operator refused) | REAL | PASS |
| Server-side authorization on every admin route | `src/api/admin_route_invariant.py`, route x persona matrix over real HTTP | REAL | PASS |
| Two-person approval and step-up | role-change tests (`tests/_role_gov.py`), W11 seams | REAL | PASS; fresh-password step-up applies to role changes, provider secrets and billing recovery; other high-risk actions rely on permission, approvals and audit (DI-M A-04) |
| Audit events, append-only | `eval_admin_security`, W10.13 tests | REAL | PASS |
| Users, workspaces, support, privacy, jobs | `eval_admin_access`, `eval_admin_support`, `eval_admin_jobs`, `eval_admin_privacy_legal`, W11 seams | REAL | PASS |
| Knowledge governance and source approval | `eval_admin_knowledge`, `eval_knowledge_governance`, W11 k7 (unapproved never retrieval-eligible) | REAL | PASS; no distinct-actor rule for approval (DI-M SJA-05, owner decision) |
| Model configuration, AI settings, evaluation visibility | `eval_admin_ai_models` | REAL/OFFLINE | PASS |
| Provider secrets | `tests/test_secret_admin_w12_4b.py`, `eval_admin_integrations` | REAL | PASS; no value ever returned |
| Billing configuration and activation gates | `eval_admin_billing`, `tests/test_billing_*`, integrated checkout-refusal test | MOCKED provider | PASS; commercial gates False |
| Speech governance, capability readiness | `eval_speech_providers`, `tests/test_speech_w12_4e.py`, `test_admin_completeness_w12_4f.py`, `e2e/admin-speech.spec.ts` | OFFLINE | PASS; server speech NOT operational |
| Error/unavailable states, keyboard, responsive | `e2e/admin*.spec.ts` | REAL (chromium) | PASS; six polish findings deferred (DI-G); no real screen-reader test |
| Admin is never a private-data superuser | W11 sentinel tests (`test_q_private_sentinels...`) | REAL | PASS |

## 6. Acceptance-criteria reconciliation

The dispositions of AC-01..AC-25 after P9 were never folded into one ledger. [`PRE_SUBMISSION_ACCEPTANCE_GATES.md`](PRE_SUBMISSION_ACCEPTANCE_GATES.md) section 2 combines the last documented status with this wave's re-measurement: **17 PASS, 8 PARTIAL, 0 FAIL, 0 NOT RUN** (P9 recorded 18 / 6 / 1). The changes against P9 are AC-24 (NOT RUN to PARTIAL, as the matrix and Pilot 2 documents already state) and AC-19 (PASS to PARTIAL: only chromium was exercised and no real-device, cross-browser or screen-reader testing exists); AC-22 stays PARTIAL (RAGAS live and semantic calibration NOT RUN). AC-03 and AC-18 may have been closed by later waves but no document re-dispositions them; they are carried as PARTIAL pending owner confirmation (`DI-N IR-AC-LEDGER`, a pre-submission item because AC-25 requires consistent documents). These are engineering dispositions, not owner acceptance.

## 7. Product coverage gate: COVERAGE GATE — FAIL

| Measure | Result |
|---|---|
| Corpus / threshold | 412 cases; 95%; 392 accepted outcomes required. Unchanged, denominator and expectations untouched |
| Developer-local | **386/412 (93.7%), BELOW GATE** |
| Clean checkout (fresh `git worktree` at `fb2d264`) | **258/412 (62.6%), BELOW GATE** (all 258 are accepted abstentions; no stores) |
| Human-qualified | **0/412** |
| Source-backed (evidence-backed) | 120 of 412 answered with real, applicable, provenance-complete evidence; 197 accepted abstentions and 69 clarifications make up the rest of the 386 |
| Reproducibility | developer-local: repeated runs identical; clean checkout: 3 runs identical; both guards report regressions 0, improvements 0 |

**Transient failure investigation.** The earlier single failure of `eval_product_coverage` right after a full pytest run was not reproduced: 10 runs under concurrent CPU load (with a full pytest `-n 4` running), 5 clean reruns, 3 clean-worktree runs and a full CI-mirror run all passed, with no traceback or abort text in any log. Test isolation, environment state, fixture access and timing could not be separated because the failure never recurred; a native-teardown abort at interpreter exit is a hypothesis only. Recorded as `DI-B B-RC-TRANSIENT` (NOT VERIFIED, LOW). No threshold, denominator or expectation was changed and no unqualified source was activated. Source-backed remediation is not feasible within the approved scope: the gap needs authorized source acquisition and human qualification (backlog BL-7 to BL-12), all deferred by the owner. **Owner-decision request:** `PRE_SUBMISSION_ACCEPTANCE_GATES.md` section 4. Engineering grants no exception.

## 8. Role-family coverage and localization

**Role families.** The coverage corpus spans 11 occupation families and 20 occupations (software/data 88 cases, finance 85, product 43, HR 42, sales 42, operations 42, supply chain 16, healthcare 16, engineering 15, project/program 15, general 8) over US, UK, DE and EU and 220 geography-neutral cases; HR is 10% of the corpus. The R1 live interview harness covered 7 roles (software engineering, finance, operations, sales, customer support, people/HR, marketing; deterministic checks 7 of 7, subjective quality PENDING_HUMAN_REVIEW). Limitation: trades, education and public-sector families are not exercised, and no new role-family run was made in this wave.

**Localization.** Eight interface/conversation locales (en, de, fr, es, it, pt, nl, ru): `eval_i18n_l10n` passes (0 unexplained literals, all locales complete, protected slogan untranslated). Seven knowledge-base languages are checked separately: the policy tests cover all seven (offer removal, localized guidance, abstention, Career-path integration); Russian stays interface and conversation only, never a KB or speech language (`excluded_languages` asserted by test and by `/speech/capabilities`). Native-phrasing cross-language retrieval (L-XLANG-1) remains an open, offline-measured gap. No native-speaker review exists; language detection is a stopword proxy. Status PARTIAL (`DI-B`, `DI-L`).

## 9. Grounding policies (A, B, C) and Knowledge/RAG

All three owner-approved policies were exercised again through the real Career-chat service path and the agent result path, not only through the shared layer:

- **A (contextual citations):** a cited abstention keeps a relevant citation and is classed ABSTENTION_WITH_CONTEXTUAL_CITATIONS; unrelated and foreign-country compensation citations are removed together with any figure they would authorize; a fabricated marker (`[42]`) cannot survive.
- **B (factual retrieval and clarification):** the agent prompt requires `SearchCareerKnowledge` before verified external claims; an unsupported statistic stated without retrieval is removed and replaced by a localized evidence limitation; clarifications (ambiguous "PM", missing gaps, missing handoff prerequisites) are untouched and no tool is forced; HITL sequencing is judged by the contract evaluator.
- **C (no unsourced compensation estimates):** a cited or uncited estimate offer is replaced by localized guidance in all seven languages; no invented figure or range; valid sourced compensation for the matching country is preserved.
- **Consistency:** the agent result's citations and sources, and the Career response's citations and evidence, drop exactly what the policy removed.
- **Malformed or failing providers:** a raising responder yields the safe degraded answer with no key, prompt or secret in the answer, trace notes or findings; empty or marker-only replies never produce a blank answer.

Limits (full list in the R2 report and `DI-D`): lexical detection, token-overlap citation relevance, agent figure verification limited to tool results, and **the PR #203 corrections have not been validated in a new live run** (`DI-D D-NOT-LIVE`, 15 calls remain; not needed to implement, a live re-sample needs the owner's choice). Retrieval-quality evidence is deterministic and synthetic-fixture based; semantic live calibration and RAGAS live are NOT RUN.

## 10. Security, privacy and cross-domain negative testing

| Scenario | Test | Result |
|---|---|---|
| Candidate A cannot read or mutate candidate B (opportunity, document, memory) | `test_candidate_a_cannot_read_or_mutate_candidate_b_resources` | PASS |
| Admin without permission cannot reach a restricted endpoint; step-up not available to a candidate | `test_a_candidate_and_a_least_privilege_role...` | PASS |
| Knowledge Admin cannot bypass source qualification; unverified compensation evidence cannot become candidate-visible | W11 k7, `eval_admin_knowledge`, governed retriever tests; policy tests remove unverified figures | PASS |
| Unsupported salary claims cannot be presented as verified; fabricated citation cannot survive | `test_a_fabricated_citation_and_an_unsupported_canadian_salary...` | PASS |
| Cancelled or rejected workflow has no unauthorized side effect | `tests/test_agent_hitl*.py` (rejected approval persists nothing) | PASS (existing) |
| Expired or forged authentication rejected | `test_expired_or_forged_authentication...` | PASS |
| Failed provider exposes no credentials or raw prompts | `test_a_failing_provider_degrades_safely...` | PASS |
| Disabled commercial feature cannot process a real payment | `test_a_disabled_commercial_feature...` (external network blocked; refused with 4xx) | PASS |
| Speech authorization stays disabled | `test_speech_provider_authorization_stays_disabled...` | PASS |
| Provider execution cannot bypass the budget guard | `tests/test_p10e_ledger.py`, `test_p10e_live_guard.py` (existing) | PASS |
| No real customer notification from test workflows | `test_no_test_workflow_can_emit_a_real_customer_notification` (external network blocked; in-memory mail only) | PASS |
| Secrets and private sentinels on Admin and error surfaces | W11 tests q, r | PASS |

No failure was masked. New tests: `tests/test_integrated_requalification.py` (18 tests).

## 11. Operations matrix

| Area | Evidence | Class | Result |
|---|---|---|---|
| Migrations; single head | `alembic heads` = `0039_speech_governance (head)`; `tests/test_migrations.py`, `test_migration_portability_p5b.py` | REAL (SQLite); PostgreSQL evidence from P5-B | PASS; hosted multi-instance PostgreSQL NOT TESTED |
| Startup, health, restart and recovery | `tests/test_health.py`, `eval_restart_recovery`, `eval_hosting_readiness`, Playwright production build and start | REAL local | PASS local; hosted HTTPS, restore drill, rollback = EX-12 NOT RUN (production-only unless the brief requires hosting: `DI-H IR-DEPLOY-EXPECT`) |
| Timeouts, provider-failure degradation, rate limits | `eval_rate_limits`, `test_rate_limit_adapters.py`, integrated failure tests | OFFLINE | PASS; live Redis NOT TESTED (`DI-H`, `DI-J`) |
| Secrets and environment | W12.4B tests, `eval_admin_integrations` | REAL | PASS |
| Audit preservation, privacy boundaries, source-ingestion boundaries | `eval_admin_security`, W10.10 tests, governed-knowledge tests | REAL | PASS; a real malware scanner is not configured (`DI-B B-SCANNER`, production) |
| Budget guards for evaluation spend | P10E ledger and guard tests | REAL/OFFLINE | PASS; ledger untouched |
| CI reproducibility | `scripts/ci_test_shards.py verify` (258 test files, each in exactly one of 4 shards); the CI-mirror runner reproduced all evaluator commands locally | REAL | PASS |
| Documentation consistency | `eval_doc_consistency`, `eval_product_positioning`, `eval_engineering_quality` | OFFLINE | PASS (stale statuses reconciled, section 16) |
| Monitoring, backup, cross-environment configuration | none in this wave | NOT TESTED | production-only items (`DI-H`) |

Nothing is labelled PRODUCTION QUALIFIED.

## 12. Test execution results (final state of this branch)

Final state of this branch: backend **5,054 passed / 34 skipped / 0 failed** (3 min 17 s); vitest 110 files / 1,082 tests; ESLint and `tsc` clean; Playwright 412 passed in 4.2 minutes; 52 of 52 CI evaluator and guard commands passed; Ruff, `compileall`, `git diff --check` and shard verification clean. No paid provider call in any run. (Final-state numbers are repeated in `PRE_SUBMISSION_ACCEPTANCE_GATES.md`.)

## 13. Findings and classification

| ID | Finding | Class | Evidence status | Disposition |
|---|---|---|---|---|
| IR-F1 | Data export carried a hard-coded `legal_acceptance recorded False` and a stale "does not record it yet" scope line although acceptance records exist | LOW | FAIL (fixed) | Fixed: derived from real records; test added; `DI-F PRIV-EXPORT-D03` CLOSED |
| IR-F2 | Roadmap and phase plan described merged PRs (#189 to #203) as pending | LOW | FAIL (fixed) | Reconciled (section 16) |
| IR-F3 | `PRODUCT_CLAIMS.md` carried stale reasons (NO-05, NO-06, NO-16) | LOW | FAIL (fixed) | Reasons updated; claims remain NOT permitted |
| IR-F4 | Acceptance dispositions are P9-era and inconsistent across documents | MEDIUM | PARTIAL | Pre-submission item `DI-N IR-AC-LEDGER`; owner confirmation needed |
| IR-F5 | 95% coverage gate unmet in both profiles | HIGH | FAIL | Not renamed; owner decision requested (section 7) |
| IR-F6 | `eval_product_coverage` transient failure | LOW | INCONCLUSIVE | Not reproduced; `DI-B B-RC-TRANSIENT` |
| IR-F7 | The Turing College brief and rubric are not in the repository | HIGH | NOT RUN | `DI-K IR-TURING-RUBRIC`, owner |
| IR-F8 | Whether local execution satisfies the course deployment expectation | HIGH | NOT RUN | `DI-H IR-DEPLOY-EXPECT`, owner |
| IR-F9 | Policy corrections not live-validated; subjective quality unreviewed | MEDIUM | PENDING HUMAN REVIEW | `DI-D`, `DI-C`, `DI-L` |

No BLOCKER. No finding was downgraded. Deferred items remain visible in the register.

## 14. Live versus offline evidence; budget

No live provider call was made. The live evidence cited anywhere in this report predates it (P10E, R1, R2: 285 of 300 calls, USD 2.112 committed, 15 calls and USD 7.888 remaining; account-usage reconciliation differences are recorded and unexplained in `DI-M M-RECON-*`). A live re-sample of the PR #203 corrections would need the owner's explicit choice and about 15 calls (the full remaining allowance); the existing P10E budget is never reset or silently reused.

## 15. Outstanding issues and post-capstone deferrals

The consolidated register has **387 issues: 336 active and 51 closed**; see [`POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md`](POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md) for the categories (A to N), the production-release blockers (section 3 there), the owner-decision list (section 4) and the reconciliation of closed items (section 6). Three issues are classed OPEN — PRE-SUBMISSION QUALIFICATION: the coverage gate (`DI-A BL-11`), AC-24 (`DI-L L-AC24`) and the acceptance-ledger reconciliation (`DI-N IR-AC-LEDGER`). Deferral is scheduling only; nothing deferred is complete or waived. P10F, the remaining P10C-F work and the remaining W12.4E activation work stay deferred by the owner; this report does not claim any of them was executed.

## 16. Documentation discrepancies found and how they were handled

| Discrepancy | Handling |
|---|---|
| Roadmap/phase plan said P10C-E, P10C-F1, P10D, P10D-R1, W12.4E, W12.4F, W12.5, P10E and P10E-R1/R2 were unmerged | Reconciled to the merged PRs (#182 to #203); historical evidence untouched |
| P9 ledger AC-24 NOT RUN vs matrix PARTIAL; AC-03 PARTIAL vs PASS; matrix totals stale | Recorded; single table proposed in the gates document; owner confirmation (`IR-AC-LEDGER`) |
| Roadmap lists research-cache isolation as UNRESOLVED although P10D (D12) and RC-P10-003 closed the main paths | Recorded in the register (`DI-H`, `DI-M`), not rewritten |
| CLAUDE.md says realtime voice DEFERRED; P7.5 says delivered with live not run | Recorded (`DI-E`); wording is consistent once "live not run" is read |
| Provider-cost gap direction differs between P10E and P10E-R1 (and R2 reported the opposite sign) | Recorded (`DI-M M-RECON-1..3`); never attributed |
| Reference checklist EX-05 names an Evaluation specialist that does not exist | Presentation must follow code (three specialists, 11 tools) |
| Reference runbook defines P12; repository plan has only P11 | `DI-N IR-P12`, owner decision |

## 17. RC-P10-004 entry conditions, AC-24 and the recommendation

The entry conditions, consolidated from scattered documents (no dedicated specification existed), are in `PRE_SUBMISSION_ACCEPTANCE_GATES.md` section 3. Status: requalification executed with no BLOCKER; owner approval for creation not given; the 95% gate fails; whether live or human items are mandatory and how the unmet gate is handled are undefined. **Recommendation: NO-GO to create RC-P10-004 in this wave.** If the owner approves a defined handling of the coverage gate and the AC-24 question, the RC should be created from the then-current merged SHA covering all runtime changes since RC-P10-003 (permissions 43 to 44, billing and speech foundations, migrations 0026 to 0039, the grounding policies). AC-24 stays PARTIAL: three structured sessions on RC-P10-003 are met; a successor RC with a rerun release gate does not exist; P10F (human revalidation) is deferred. Limited-scope exception, if the owner wants one: the criteria that would remain open are AC-24 (successor RC and any human revalidation), AC-19 (mobile, cross-browser), AC-22 and AC-23 (live and human evidence), AC-13 and AC-14 live quality, the 95% coverage gate, and hosted operation (EX-12). The owner decides; this report approves nothing.

## 18. P11 handoff (not started)

Remaining packaging work, with where each stands (the Turing College rubric is not in the repository, so no assessment criterion is assumed; items come from the repository phase plan and the Claude-authored reference runbook):

| P11 item | State |
|---|---|
| Requirements traceability matrix (Sprint 4 versus new Capstone contribution) | `capstone_requirements_matrix.md` exists; AC dispositions need the single reconciled ledger first |
| Architecture documentation and diagrams (authentication, data flow, retrieval, specialist agents, speech) | substantial text in `docs/capstone/*` and `CLAUDE.md`; diagrams not produced |
| Implementation story; LLM architecture; prompt engineering; RAG implementation; agentic workflows | material exists in P5, P6, P10C to P10E documents; narrative not assembled |
| Security safeguards; model evaluation; known limitations; evaluation evidence | security architecture, P10E evidence and this report; limitations list = the deferred register |
| Demo environment and demonstration script; recorded fallback; sanitized synthetic demo data | not produced; the deployment question (`IR-DEPLOY-EXPECT`) decides local versus hosted |
| Technical presentation (10 minutes) and Q&A plan; three decks; reviewer guide | not produced; `capstone_presentation_standard.md` gives the standard |
| Repository readiness; release or tag requirements; submission instructions | RC convention is an artifact pinned to a merged SHA, not a tag; instructions need the rubric |
| Outstanding academic decisions | rubric and deployment expectation (owner), coverage-gate handling, AC-24 closure, whether P12 duties fold into P11, RC-P10-004 creation |

## 19. Recommended next actions

1. Owner: review this report and decide section 4 of the gates document (coverage gate handling, AC-24, RC-P10-004 conditions).
2. Owner: supply the Turing College brief and rubric and answer the deployment-expectation question.
3. Owner: confirm the reconciled acceptance ledger (`IR-AC-LEDGER`).
4. Optionally spend the remaining 15 live calls on a re-sample of the policy corrections.
5. Then, if approved, create RC-P10-004 in a separate step and begin P11 packaging.
