# Academic Submission Scope Decision (PROPOSED)

**Status:** PROPOSAL for the Product Owner, prepared 2026-10-19 against `main` `4043429`. It is **not** a course-approved exception, **not** an acceptance decision and **not** production approval. A documented limitation is not a waiver. Nothing here changes a threshold, a denominator, an expectation or a gate. Supporting documents: [`CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`](CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md), [`RC_P10_004_ENTRY_DECISION.md`](RC_P10_004_ENTRY_DECISION.md), [`P11_SUBMISSION_READINESS_PLAN.md`](P11_SUBMISSION_READINESS_PLAN.md), the [deferred register](POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md) (`DI-` identifiers) and [`PRE_SUBMISSION_ACCEPTANCE_GATES.md`](PRE_SUBMISSION_ACCEPTANCE_GATES.md). The phase plan stays canonical for scope and sequence.

> **TIME-CRITICAL FACT (second-hand, needs confirmation):** the planning documents record the course deadline as **2026-10-20** (user-confirmed there) and the feature freeze as 2026-10-13. The date of this document is **2026-10-19**. No official source for either date is in the repository. Confirm the deadline and time zone before anything else (section 7, item 3).

## 1. What a limited-scope submission would demonstrate

Each row states the evidence class actually available. Classes: **IMPLEMENTED AND TESTED** (code plus automated tests that pass), **IMPLEMENTED — OFFLINE QUALIFIED** (deterministic evaluators, no provider), **LIVE EVIDENCE AVAILABLE** (real provider calls were recorded), **HUMAN REVIEW PENDING**, **PARTIALLY QUALIFIED**, **DEFERRED**, **NOT IMPLEMENTED**. A row can carry several.

| Capability | Classes | Evidence (and what is not claimed) |
|---|---|---|
| Functional Ask4Mo application (accounts, onboarding, Opportunities, Prepare with Mo, Practice, reports, history, privacy centre, workspaces, Admin) | IMPLEMENTED AND TESTED | Backend 5,054 passed, vitest 1,082, Playwright 412, 52 of 52 CI evaluator commands. No human user acceptance beyond Pilot 2 (3 sessions on RC-P10-003). |
| LLM integration through OpenRouter | IMPLEMENTED AND TESTED; LIVE EVIDENCE AVAILABLE | Career via LangChain, Interview via a direct HTTPX client. P10E smoke on Fast, Balanced and Advanced; a hard-guarded live harness (one cumulative ledger, 285 of 300 calls, USD 2.112 committed). CI never calls a provider. |
| Prompt engineering | IMPLEMENTED AND TESTED; IMPLEMENTED — OFFLINE QUALIFIED | Trust-separated prompt blocks, localized headings and language directive, coaching-style directive, grounding rules; Prompt Lab (offline, no auto-promotion). Prompt quality against humans is not measured. |
| Model selection and routing | IMPLEMENTED AND TESTED; LIVE EVIDENCE AVAILABLE; PARTIALLY QUALIFIED | One registry (Fast, Balanced, Advanced) plus a per-operation policy. A real routing defect (import-time default) was found live and fixed: 0 of 90 later requests used an unexpected model. Plan-based profile gating exists but is **disabled** by a code constant. |
| Structured output handling | IMPLEMENTED AND TESTED | Typed job-analysis, question and evaluation outputs with validation and safe failure; deterministic tests. |
| Agentic workflows and tool execution | IMPLEMENTED AND TESTED; LIVE EVIDENCE AVAILABLE; PARTIALLY QUALIFIED | LangGraph agent, allow-listed tools, three bounded specialists, bounded steps; deterministic 56-case orchestration eval; live benchmark 22 of 22 cases completed, tool selection 0.773 aggregate (a small sample, no owner threshold). Per-case misses were only itemised for 6 cases. |
| Human-in-the-loop controls | IMPLEMENTED AND TESTED | Durable `interrupt()` and `resume`, approval-gated memory and practice handoff; replay and stale-decision tests. |
| Knowledge retrieval and RAG | IMPLEMENTED — OFFLINE QUALIFIED; PARTIALLY QUALIFIED | Hybrid vector plus keyword retrieval, structured lanes, governed knowledge; deterministic corpus (P10C-G 115 and P10D 157 cases). **The 95% product-coverage gate FAILS** (section 3). Semantic live calibration and RAGAS live are NOT RUN. |
| Evidence-grounded responses | IMPLEMENTED AND TESTED; LIVE EVIDENCE AVAILABLE (before the final corrections); HUMAN REVIEW PENDING | One shared deterministic layer: contextual citations, factual retrieval with legitimate clarification, no unsourced compensation estimates, no unverified figures, in seven languages (77 policy tests plus an integrated suite). The 15-call live sample predates the PR #203 corrections. Citation claim-support is not human-reviewed. |
| Security safeguards | IMPLEMENTED AND TESTED | Server-side authorization and ownership isolation, injection screening, output and secret guards, rate limits, 44-permission Admin with two-person approval and step-up where defined, append-only audit. Production hardening (real malware scanner, hosted TLS, monitoring) is NOT implemented or NOT TESTED. |
| Interview preparation and practice; interview feedback | IMPLEMENTED AND TESTED; LIVE EVIDENCE AVAILABLE; HUMAN REVIEW PENDING | Durable practice sessions, evaluation, deep dive, report; a live harness over 7 roles (9 deterministic proxies 7 of 7). Feedback quality and bias sensitivity are **not human-rated**. |
| Streamlit foundation | IMPLEMENTED AND TESTED (legacy) | Still runs over the same application layer; a CI smoke check passes. It is a legacy interface, not the product. |
| Current Next.js application | IMPLEMENTED AND TESTED | Primary interface (eight interface locales). |
| Model evaluation | IMPLEMENTED — OFFLINE QUALIFIED; LIVE EVIDENCE AVAILABLE (partial); DEFERRED (remainder) | 52 deterministic evaluator commands; a committed deterministic RAGAS baseline; live runs under a hard budget guard; **no acceptance thresholds exist** and none were invented. |
| System testing | IMPLEMENTED AND TESTED | Backend, frontend, browser E2E (chromium only), evaluators, migrations (single head `0039_speech_governance`), security and privacy suites. |
| Ethical considerations | PARTIALLY QUALIFIED; HUMAN REVIEW PENDING | Documented design rules (private by default, no fabricated evidence, no protected-trait inference, practice feedback is not a hiring decision, no camera). Privacy and terms pages are **engineering drafts without legal review**. The ethics report is a P11 deliverable and is not written. |
| Known limitations and post-submission improvements | IMPLEMENTED (documentation) | The deferred register: 390 issues, 338 active (387 and 336 when PR #204 merged; three added and one closed since). |

## 2. What must NOT be claimed

Production readiness; human-qualified quality; the 95% coverage gate (it fails); any course-approved exception; qualification of any international source, any Compensation V2 output or all Knowledge Base markets (the engine is built and **disabled**, every source package beyond the isolated US engineering work is unapproved, and the seven Knowledge Base languages are not seven supported markets); native-speaker review of any translation; production speech (server speech is disabled and NOT operational, genuine Whisper and Kyutai execution is NOT VERIFIED, Russian is excluded from speech and from the Knowledge Base); operational billing (billing is a mock; all 12 rollout and billing gates are False; no Stripe interaction); live Google sign-in or live email delivery; hosted operation (EX-12 NOT RUN); P10F or any human revalidation after Pilot 2; completion of AC-03, AC-13, AC-18, AC-19, AC-22, AC-23, AC-24 or AC-25.

## 3. Product-coverage gate: formal record and proposed approach

**Original requirement (unchanged):** 412 cases, 95% minimum, **392 accepted outcomes required**.

| Measure | Result |
|---|---|
| Developer-local | **386 of 412 (93.7%)**: **6 cases short** of the minimum |
| Clean checkout (fresh worktree, tracked files only) | **258 of 412 (62.6%)**: **134 cases short** |
| Human-qualified | **0 of 412** |
| Answered with real, applicable, provenance-complete evidence | 120 of 412 (29.1%); the rest of the 386 are accepted abstentions (197) and clarifications (69) by case design |

**Disposition: FAIL — BELOW REQUIRED COVERAGE.** It is not PASS and no exception is claimed. The threshold, the denominator and the expectations are unchanged and no unqualified source data was used.

**Why the two measurements differ.** Developer-local runs against locally generated retrieval stores (Chroma and the structured SQLite stores) that a fresh clone does not contain; the clean checkout has none, so every case that needs stored evidence is an accepted abstention. Neither measurement is combined with the other and neither is a pass.

**Why the six-case gap is not closable inside the approved scope.** Package 1 (US sources) alone reaches at most 391 (94.9%) even if fully qualified. Closing needs one of: the Data Analyst and Product Manager evidence gap (BL-7: an approved occupational-title source or candidate context with an owner ambiguity policy), Package 2 (UK) or a projections or OOH package. Each depends on owner authorization, human measurement and alias reviews (BL-5, BL-6), reviewer appointments (BL-1 to BL-4), licence review of commercial BLS use outside the US (RB-LIC-1, BL-8) and persistent registry promotion (BL-9). All of that was deferred by the owner on 2026-10-18 to prioritise the remaining capstone milestones; none of it is complete or waived.

**What would close it (summary, see register `DI-A`):** named human reviewers and their decisions; licence clearance; an authorized source acquisition and qualification; persistent registry import and a rebuild so that a clean checkout (or the CI fixture) can retrieve stored evidence; a re-measurement with the unchanged 412 cases.

**Proposed approach for the owner to consider (not a recommendation to waive):** submit the application with the internal gate reported as FAILED in the evaluation report and the presentation, stating the three numbers above, the six-case shortfall, the developer-local versus clean-checkout difference, the zero human-qualified coverage and the deferred dependencies. Whether the course accepts a submission with a failed internal gate is a **course** question that this repository cannot answer (section 7). If the course requires internal gates to pass, the only compliant paths are to reopen the deferred source work before submission or to obtain the course's written approval of the limitation. The owner chooses; engineering grants nothing.

## 4. AC-24 and human validation: decision record

AC-24 stays **PARTIAL**. P10F did not happen and no human revalidation is claimed.

| AC-24 operational criterion | State |
|---|---|
| At least 3 actual participants | Met: 3 complete structured sessions (3 further sessions excluded) |
| Identified release candidate | Met: RC-P10-003 (candidate `54aad500`) |
| Anonymised observations | Met |
| Participant findings separated from internal review | Met |
| Lessons synthesised | Met |
| Consequential fixes regression-tested; **new RC if runtime changed** | **Not met**: P2-01 to P2-04 are regression-tested, but the runtime changed materially (permissions 43 to 44, billing and speech foundations, migrations 0026 to 0039, grounding policies) and no successor RC exists |
| Unresolved issues disclosed | Met (Pilot 2 issue register; deferred register) |
| No fabricated or model-generated participant responses | Met |

A successor candidate would establish: one immutable candidate SHA covering all runtime changes since RC-P10-003, the release gate rerun on it, and the Pilot 2 fixes verified on that SHA. It would **not** establish human revalidation; that needs real participants (P10F, deferred): sharing discoverability (P2-01), source-backed experience, answer-score interpretation, provenance clarity (P2-04) and the Opera voice failure (P2-09, unreproduced).

Three decisions are different and must not be merged:

| Decision | Question | Engineering evidence | Owner decision |
|---|---|---|---|
| **Academic submission readiness** | Is the system suitable to submit under a disclosed limited scope? | Automated gates pass; coverage gate fails; many items are human-pending | REQUIRED, subject to the course rules |
| **Full AC-24 acceptance** | Are the AC-24 criteria met? | 6 of 8 met; no successor RC; P10F deferred | REQUIRED: may AC-24 close without P10F? does it need RC-P10-004? |
| **Production release readiness** | Can it be released? | 161 register items block production | Not requested; the answer on current evidence is no |

## 5. Separation of implementation from qualification (summary table)

| State | Examples |
|---|---|
| IMPLEMENTED AND TESTED | Core product, security, grounding policies, HITL, Admin governance |
| IMPLEMENTED — OFFLINE QUALIFIED | Retrieval corpus evaluations, Prompt Lab, Compensation V2 engine (disabled), governed speech adapters (fixtures) |
| LIVE EVIDENCE AVAILABLE | OpenRouter smoke, routing, 22-case agent run, 7-role interview harness, policy sample (pre-correction) |
| HUMAN REVIEW PENDING | Interview and feedback quality, native language review, citation claim support, Pilot 2 follow-ups |
| PARTIALLY QUALIFIED | AC-03, 13, 18, 19, 22, 23, 24, 25; model-profile gating; retrieval across languages |
| DEFERRED | P10C-F remainder, P10F, W12.4E activation, commercial activation, hosted operation |
| NOT IMPLEMENTED | Owner-scoped recent-run list (AC-18), candidate share control (CJ-D-01), live billing, production speech |

## 6. Security and operations constraints preserved

All 12 rollout and billing gates False; Compensation V2, Premium, Stripe commercial use and speech activation disabled; no production deployment; no source-registry promotion; no international ingestion; no real candidate data sent to providers; no protected-store change; no real customer email. The P10E ledger is untouched (285 of 300 calls, about USD 2.112 committed, 15 calls and about USD 7.888 remaining). No paid call was made and none is needed for this documentation wave.

## 7. Official course requirements: OFFICIAL RUBRIC — NOT VERIFIED

A search of the repository, `~/Downloads/outputs`, its experience package and the neighbouring project folders found **no official Turing College material** (class A = 0): no capstone brief, rubric, submission instructions, deployment requirement, presentation requirement or expert-review process. What exists is project-authored planning (class B) and four Claude-authored secondary references (class C; the runbook says it is "based on the supplied Capstone brief", which is not present). Second-hand statements, unverified: deadline 2026-10-20; a 10-minute presentation plus 5 minutes of Q&A; six presentation topics (problem, solution, data, evaluation, challenges, what's next) with SCR or SMART; assessment dimensions Outcome Quality, Learning Application, Ethical Considerations and Presentation (no descriptors, weights or pass marks); an optional showcase; deployment "mentioned" but unresolved. The Sprint 4 requirements in the repository are the project's own paraphrase. **No assessment criterion is invented here.**

**Deployment question (unanswered, no assumption made):** does the course require a public or hosted application, or is a locally demonstrated application acceptable? Nothing was deployed and no production feature was enabled to resolve it. The consequence differs sharply: hosted operation (EX-12) is NOT RUN and its checklist is open in the register (`EX-12.1` to `EX-12.15`).

**Missing-information checklist for the Product Owner:**
1. The official capstone brief (full text) and learning objectives.
2. The official rubric: dimensions, descriptors per level, weights, pass threshold (confirm the four named dimensions are exact and complete).
3. Submission instructions: artifacts, format, where and how, **exact deadline date and time zone** (is it 2026-10-20?), late policy.
4. Deployment requirement: public hosted URL or local and recorded demonstration acceptable, in writing from the course lead.
5. Presentation requirements: length, mandatory structure, slides versus live demo, recording allowed, language, attendees.
6. Expert-review process: who, when, format, what the reviewer sees, outcome, whether separate from the presentation.
7. Showcase submission: optional or required.
8. The official Sprint 4 "Building Applications with AI" requirements and whether Sprint 4 is graded again.
9. Required evidence artifacts and whether internal gates such as the 95% coverage gate have any course relevance.
10. Rules on third-party data and APIs, paid services and AI-use disclosure.

## 8. Decisions requested

1. Confirm the deadline and time zone (section 7, item 3).
2. Answer the deployment question and supply the brief and rubric.
3. Decide how to handle the failed coverage gate (section 3) and AC-24 (section 4).
4. Approve or amend this scope as the basis for P11, and approve `CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md` as the single current acceptance record.
5. Separately decide whether to create RC-P10-004 (see its entry decision; recommendation there is NO-GO until the questions above are answered).
