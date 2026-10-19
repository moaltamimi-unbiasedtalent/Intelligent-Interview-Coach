# Submission Checklist, Course Requirements and Readiness

**Status:** prepared 2026-10-19 on branch `docs/p11-final-capstone-submission`, from `main` `3d1af6f` (PR #205 merged). **This document does not say the submission happened and it does not submit anything.** Readiness statements are engineering statements; the course's own acceptance is outside this repository.

## 1. Phase 1: course requirements record (what is verified and what is not)

| Item | Source | Status |
|---|---|---|
| Assessment dimensions: Outcome Quality, Learning Application, Ethical Considerations, Presentation | stated by the Product Owner in the P11 instruction | OWNER-STATED; descriptors, weights and pass marks are **not** in the repository |
| Primary project case: Case 2, AI agent for task automation; supporting capability: Case 1, RAG-powered knowledge assistance | stated by the Product Owner | OWNER-STATED; the official case text is not in the repository |
| Historical Sprint 4 requirements are not the capstone requirements | stated by the Product Owner | applied: the submission material is organised by the four dimensions and the two cases, not by the Sprint 4 requirement list |
| **Deadline, time zone** | planning documents say 2026-10-20 (second-hand); the date today is 2026-10-19 | **NOT VERIFIED: owner must confirm the exact date, time and time zone** |
| **Submission mechanism** (what, where, how) | none in the repository | **NOT VERIFIED: owner to supply** |
| **Review requirements** (who reviews, format, presentation length) | planning documents assume 10 minutes plus 5 minutes of Q&A | **NOT VERIFIED (timing ASSUMED in the presentation)** |
| **Deployment requirement** (hosted or local demonstration) | none | **NOT VERIFIED: owner to ask the course lead** |
| Official brief and rubric as files | searched the repository, the Downloads outputs and neighbouring project folders: none found | OFFICIAL RUBRIC: NOT VERIFIED |

No deadline or format was invented. Everything marked ASSUMED in the submission documents (timing, slide count) must be reconciled with the owner's answers.

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
2. Supply the brief and rubric, or confirm which planning documents are authoritative; confirm the presentation length and format.
3. Answer the deployment question (hosted or local demonstration).
4. Decide how the failed internal coverage gate is stated in the submission (the documents state it plainly) and whether AC-24 may close without P10F.
5. Build the slides from `TECHNICAL_PRESENTATION.md`; record a screen capture of a working demonstration if a video fallback is wanted.
6. Rehearse once against the real timing.
7. Decide whether any release artifact (RC-P10-004) or tag is wanted (recommendation in `RC_P10_004_ENTRY_DECISION.md`: not needed for the submission as far as is known, NO-GO now).
8. Acknowledge or question the unplanned provider call recorded in the rehearsal log.
9. Submit through the course's mechanism. This repository does not submit.

## 6. Final submission GO / NO-GO

**CONDITIONAL GO to submit the repository as it stands under the disclosed limited scope**, conditional on items 1 to 4 above. **NO-GO if** the course requires a hosted application, requires internal gates to pass, or has a deadline earlier than the owner can meet. The failed coverage gate, AC-24 PARTIAL and the absence of human review are disclosed in every artifact; none is hidden.
