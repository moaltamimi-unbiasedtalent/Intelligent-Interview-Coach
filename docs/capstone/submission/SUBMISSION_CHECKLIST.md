# Submission Checklist, Course Requirements and Readiness

**Status:** prepared 2026-10-19 on branch `docs/p11-final-capstone-submission`, from `main` `3d1af6f` (PR #205 merged). **This document does not say the submission happened and it does not submit anything.** Readiness statements are engineering statements; the course's own acceptance is outside this repository.

## 1. Phase 1: course requirements record (what is verified and what is not)

**Update:** the official capstone brief IS available: it ships with the course's submission repository as `AE.CAP_afa.md` in the Turing College submission repository (`TuringCollegeSubmissions/maltam-AE.CAP.AFA.1.1`, initial commit `150882c`), read on 2026-10-19 after the first draft of this package. It supersedes the earlier statement in this package that no official material was found (that search covered this repository, the Downloads outputs and neighbouring project folders, not the submission repository). The brief is merged into this repository's history as `AE.CAP_afa.md`.

| Item | Source | Status |
|---|---|---|
| Assessment dimensions: Outcome Quality, Learning Application, Ethical Considerations, Presentation (plus an optional, recommended Showcase submission worth a small part of the score) | official brief, "Evaluation criteria for all cases" | **VERIFIED** (no weights or pass marks in the brief) |
| Case 2, AI agent for task automation (agent design, tool integration, agent execution with memory or multi-step reasoning, interactive prototype, evaluation through user testing, documentation including ethical considerations); Case 1 RAG assistant as supporting capability; "alternative ideas are also valid" | official brief | **VERIFIED**; the owner chose Case 2 as primary |
| README must concisely explain the goal, the problem solved and how it works; showcase link near the top if uploaded | official brief | **VERIFIED**; satisfied by the README (the showcase entry has not been published: optional) |
| Presentation | official brief: optional but recommended; **10 minutes plus 5 minutes of questions**; six points: problem, solution, data, evaluation, challenges, what's next; SCR or SMART is part of the Presentation criterion | **VERIFIED** (format); slides not built |
| Deployment | the brief's Objective says "develop and deploy prototypes"; the evaluation criteria do not require a hosted application; no deployment rule is stated | **NOT SETTLED: owner or the course lead to confirm whether a local demonstration is enough** |
| Deadline, time zone, submission mechanism beyond pushing to the submission repository, how the review is booked and run | not in the brief (it mentions "booking the review") | **NOT VERIFIED: owner to confirm**; the earlier 2026-10-20 deadline is second-hand |
| Sprint 4 requirements | not part of the capstone brief | not applicable (applied: the package is organised by the four dimensions) |

No deadline or review procedure was invented. Timing and slide-count statements in the other documents are now **verified** for the 10 plus 5 format and the six points; everything else marked ASSUMED stays so.

## 2. Phase 2: repository readiness

| Check | Result |
|---|---|
| Latest merged `main` | `3d1af6f` (PR #205) |
| Required CI | PR #205 head: 11 of 11 checks success; the merge commit's push run: 9 of 9 success (the two browser workflows run on pull requests only) |
| Acceptance ledger | `CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`: 17 PASS, 8 PARTIAL; AC-24 PARTIAL |
| 12 rollout and billing gates | all False (test-verified in the full suite) |
| Protected stores | not modified (no file under `data/` changed; the rehearsal used throwaway databases) |
| RC-P10-004 | not created |
| Deferred production features | not reopened |
| **Unplanned provider call** | one real agent run was made by accident during the rehearsal (see `REHEARSAL_AND_FREEZE_LOG.md`); disclosed there |

## 3. Submission artifacts (all under `docs/capstone/submission/` unless noted)

| Artifact | File |
|---|---|
| Narrative (Situation, Complication, Resolution; all required topics) | `SUBMISSION_NARRATIVE.md` |
| Architecture diagrams | `ARCHITECTURE_DIAGRAMS.md` |
| Demonstration guide and script; offline journey | `DEMO_GUIDE.md`, `scripts/demo_offline_journey.py`, `evaluations/demo/synthetic_demo_candidate.json`, `DEMO_TRANSCRIPT_OFFLINE.md` |
| Technical presentation and presenter notes | `TECHNICAL_PRESENTATION.md` |
| Technical Q&A | `TECHNICAL_QA.md` |
| Evaluation summary | `EVALUATION_SUMMARY.md` |
| Ethics, privacy and limitations | `ETHICS_AND_LIMITATIONS.md` |
| README (concise); the previous long README | `README.md`; `docs/README_REFERENCE_AND_HISTORY.md` |
| Rehearsal and freeze log | `REHEARSAL_AND_FREEZE_LOG.md` |
| Standing evidence | `docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`, `POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md`, `ACADEMIC_SUBMISSION_SCOPE_DECISION.md`, `RC_P10_004_ENTRY_DECISION.md` |
| **Not produced** | slide decks (`.pptx`), a recorded demonstration video, a speaking script beyond the presenter notes: these need the owner's tools and the confirmed format |

## 4. Readiness by area

| Area | Readiness | Basis |
|---|---|---|
| Demo | READY (offline fallback); UI rehearsal verified provider-free; live demonstration and a recorded video are the owner's | `DEMO_GUIDE.md`, tests |
| README | READY pending the course's own instructions | concise, matches the code and the consistency evaluator |
| Presentation | READY AS A DRAFT: outline, notes and diagrams exist; slides and timing are the owner's | `TECHNICAL_PRESENTATION.md` |
| Technical review | READY: Q&A prepared with evidence pointers | `TECHNICAL_QA.md` |
| Evidence consistency | READY: numbers in the documents match the measured runs | `REHEARSAL_AND_FREEZE_LOG.md` |

## 5. Owner checklist (nothing here was done on the owner's behalf)

1. Confirm the deadline, time zone and submission mechanism.
2. Confirm the review booking and presentation slot with your STL (the brief makes the presentation optional).
3. Ask whether a local demonstration satisfies the deployment wording; decide whether to publish the optional showcase entry and add its link near the top of the README.
4. Decide how the failed internal coverage gate is stated in the submission (the documents state it plainly) and whether AC-24 may close without P10F.
5. Build the slides from `TECHNICAL_PRESENTATION.md`; record a screen capture of a working demonstration if a video fallback is wanted.
6. Rehearse once against the real timing.
7. Decide whether any release artifact (RC-P10-004) or tag is wanted (recommendation in `RC_P10_004_ENTRY_DECISION.md`: not needed for the submission as far as is known, NO-GO now).
8. Acknowledge or question the unplanned provider call recorded in the rehearsal log.
9. Submit through the course's mechanism. This repository does not submit.

## 6. Final submission GO / NO-GO

**CONDITIONAL GO to submit the repository as it stands under the disclosed limited scope**, conditional on items 1 to 4 above. **NO-GO if** the course lead says a hosted application is required, or the deadline is earlier than the owner can meet. The brief does not make internal quality gates part of the grading; the failed gate is disclosed anyway. The failed coverage gate, AC-24 PARTIAL and the absence of human review are disclosed in every artifact; none is hidden.
