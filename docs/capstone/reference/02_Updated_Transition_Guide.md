# Ask4Mo transition guide: 401-commit alignment addendum

> Baseline findings remain relevant, but this addendum's scope deferrals are superseded by the owner's [v3 expanded selection](../Ask4Mo_Capstone_Delivery_v3/00_Expanded_Project_Plan.md). Use the v3 master override when old prompts conflict. The previously delivered presentation and ZIP describe the earlier, narrower proposal.

23 September 2026. This addendum supersedes conflicting baseline assumptions in the v2 delivery package. It preserves the phase numbering, 24 September start, 13 October feature freeze and 20 October deadline. It does not replace the full phase instructions or authorize all optional backlog items.

## Current baseline

Begin from verified `4f273dd` or a later explicitly reviewed checkout. Keep `sprint4-submission-ready` at `1b084cb` as historical evidence. PRs #70–#72 add product-surface fixes, diagnostics, critique/implementation stories, capability control and guided onboarding. Preserve those additions and their tests.

Already present: A1 completed History detail, A3 basic Progress, A4 source links, A7 stored-run Evaluation UI, the overview part of A8 Knowledge/RAG diagnostics, C10 tour/Help/contextual guidance, and Deep Dive branch feedback. A7 still needs correct artifact visibility/provenance. A8 still needs the distinction between overview snapshots, live readiness and selected-run evidence.

Remaining selected core: verified individual login, profile/opportunities, private PDF/DOCX/TXT upload, app-wide dictation, recorded spoken Practice with spoken questions, Mo coordinating Research and Candidate specialists, active-session discovery, safe owned recent-run discovery, and frontend integration/polish. No team accounts, realtime conversation, OCR or public hosting added by this review.

## Revised phases and gates

| Phase | Target dates | Work after the latest merge | Exit evidence |
|---|---|---|---|
| P0 | 24 Sep | Verify checkout and tag; reconcile docs, metrics/provenance, existing-vs-new scope; decide auth/STT/storage; inspect fresh-clone prerequisites | Signed-off baseline, exact SHA, scope and unresolved decisions |
| P1 | 25–27 Sep | Real backend-verified accounts; private profile and opportunity context; retain existing owned-data contracts | Two-user negative tests, logout/session handling, migration/backup proof |
| P2 | 28–29 Sep | Preserve History/Progress/Sources; add active-session discovery; adapt return journey to accounts; distinguish live KB readiness from snapshots | Owned completed and active sessions work after reload; missing-data guidance |
| P3 | 30 Sep–1 Oct | Reusable frontend design and dictation control; two real natural-language input surfaces | Permission/error/cancel tests, editable transcript, no auto-submit |
| P4 | 2–4 Oct | Private document ingestion and approval into candidate context | Parsing/ownership/provenance tests; file limits; deletion and worker-race coverage |
| P5 | 5–6 Oct | Bounded Mo supervisor with Research and Candidate specialists | Typed handoffs, max calls/time/cost, failures, comparison against single-agent baseline |
| P6 | 7–8 Oct | Integrate context and Practice handoff; add safe owned recent-run discovery; improve existing Evaluation/RAG readers only where needed | Accurate artifact provenance, selected-run evidence, no paid calls on page load |
| P7 | 9–10 Oct | Recorded spoken Practice and spoken questions using existing deterministic session workflow | Real microphone path, review transcript, exactly-once submission, text fallback, cleanup |
| P8 | 11–13 Oct | All eligible natural-language inputs support dictation; adapt existing tour/Help to new routes; visual/accessibility polish; freeze | Field inventory, responsive manual checks, no regressions in onboarding/HITL |
| P9 | 14–15 Oct | Security, retrieval, session/document/speech integration and controlled agent evaluation | Evidence tied to exact code, environment and dataset; unknowns labelled |
| P10 | 16–17 Oct | Actual user pilot and priority repairs | Real participant observations, consent, before/after issue evidence |
| P11 | 18 Oct | Three distinct presentation purposes, speaking script, Q&A, README and checklist | Core/optional evidence tables, honest caveats, rendered slide QA |
| P12 | 19 Oct | Final local startup and rehearsal; freeze release record | Ten-minute demo, five-minute Q&A, fallback, final code/evidence links |
| Review | 20 Oct | Present the verified candidate | No unsupported delivery or live-validation claims |

Dates are targets, not effort estimates. Confirm weekly capacity immediately. At 4 and 8 October assess actual throughput and reduce optional breadth before consuming final validation time. Reuse of the newly completed surfaces reduces duplicate work but does not prove that the remaining scope fits the available hours.

## Copy-ready overlay for every Claude session

Paste this after MASTER CONTEXT and before the relevant v2 phase prompt. If a v2 baseline statement conflicts with this overlay, use this overlay and verify the checkout again.

```text
Apply the 401-commit baseline correction to the Ask4Mo Capstone v2 plan.

The reviewed baseline is main 4f273dd9c190bf016d70d7c7a9fbaee4f411e9d5 (401 commits). The historical sprint4-submission-ready tag still points to 1b084cb. Confirm the actual checkout first. Preserve unrelated changes and do not move historical tags.

Existing functionality to preserve, not rebuild: clickable completed History with detail reports; completed-practice Progress metrics; safe Sources links; stored-run Evaluation UI; Knowledge/RAG overview; guided tutorial, Help Center and contextual links; Deep Dive branch evaluation; server-enforced current-market-research toggle.

P0 must reconcile documentation and evidence provenance. P2 focuses on account integration, active-session discovery, regression proof and knowledge readiness. P6 extends existing diagnostics only for genuine gaps, including owned run discovery and truthful artifact visibility. P8 updates the existing tour/Help for new features rather than building onboarding from zero. C10 is delivered baseline functionality, not an optional new implementation.

Important evidence boundaries: the Evaluation reader uses evaluations/ragas/runs/*/results.json, not the committed deterministic_baseline.json. Knowledge diagnostics reads generated build_metadata.json and retrieval_after.json; they are ignored and absent in a clean checkout. Do not claim live store readiness from snapshot counts. Do not fabricate files or results to make pages look populated. Document prerequisites and implement any separately approved readers with explicit schemas and evidence labels.

The original golden run validated afb4f45 and belongs to the historical release lineage. Later capability-control code changes agent behaviour. Preserve historical metrics and state tested SHA/date/mode for every current claim. Current local frontend evidence is 176 passing unit tests and a passing TypeScript check. Sixty Playwright cases were discovered locally, not executed in that review. PR #72's five CI jobs passed; current main-push CI was not independently established. Exact current Python totals require actual CI logs or a fresh test run.

Keep the selected Capstone core, existing architecture and safety gates. Maintain Next.js + FastAPI as primary and Streamlit as legacy. All-app STT means eligible natural-language inputs, never passwords, tokens, IDs or automatic submission. Keep real-time voice, OCR, teams, public hosting and other unselected features deferred. Ask before paid runs, production migrations, pushes, tags, merges or deployments. End each phase with actual results, blockers and a precise next handoff.
```

## Copy-ready documentation reconciliation prompt

This prompt is for the owner's next implementation session. This review has not executed its edits.

```text
Task: reconcile Ask4Mo Sprint 4 and Capstone planning documentation against the latest code, starting from the 401-commit review. Work in the actual repository on a safe documentation branch, preserving unrelated changes. Do not change product runtime, install providers, move release tags, run paid evaluations, commit, push, open a PR or merge unless separately authorized.

Read README.md, CLAUDE.md, docs/sprint4_submission_summary.md, sprint4_final_evidence.md, final_submission_readiness.md, sprint4_reviewer_guide.md, sprint4_final_requirements_matrix.md, sprint4_technical_critique.md, sprint4_deliverable_implementation_stories.md, post_release_product_surface_audit.md and guided_tutorial.md. Read the v2 plan/runbook/prompt pack/scope/checklist and the 401-commit alignment review when supplied. Verify relevant code before editing claims.

1. Create one current evidence index with exact code state/date, historical versus current status, local/mock/CI/live modes and links. Preserve original golden records, validation SHAs, counts and the original tag. Do not invent exact Python/browser totals from test-file counts.
2. Remove current-tense references to delivered features as future work. Preserve historical chronology with explicit superseded labels. Record History, basic Progress, safe Sources, Evaluation UI, RAG overview and guided onboarding as existing, including their limitations.
3. Fix the evaluation claim: the deterministic ID baseline is not presently read by /evaluation/latest. Document actual files/schema needed by the stored-run reader. List adding a separate deterministic reader as a proposed code task, not an implemented fix. Do not perform it in this docs-only task.
4. Correct diagnostics wording: generated local build snapshots and offline results are not universally committed or live readiness checks. Document check_demo_knowledge.py and fresh-clone prerequisites. Any UI-copy change belongs in a separately identified implementation task.
5. Correct the claim that the closure did not change Agent runtime. Describe the server-enforced capability toggle and scope its test evidence separately from the original live golden.
6. Correct Deep Dive feedback status, RAGAS retrieval-ID versus generation-quality terminology, stale reviewer follow-ups and the current architecture introduction in CLAUDE.md. Preserve actual missing production OIDC, live Postgres, Langfuse, Adzuna and paid RAGAS validation caveats.
7. Update P0/P2/P6/P8 and A1/A3/A4/A7/A8/C10 consistently across the supplied planning files only when those files are available in an editable location. Treat synced sources as read-only. Preserve all other phase gates, scope decisions, deadline and dictation coverage.
8. Validate links and terminology. Show a table of changed claims, evidence and remaining unknowns. Report checks actually run. List any required code fix separately, with no fake completion or broad release-ready certification. Stop with the reviewed diff and next action.
```

## Reviewer narrative

“Sprint 4 established a bounded tool-using coach and durable Practice. A return-journey audit then exposed missing connections around reports, progress and evidence. PRs #70–#72 close those surfaces and add guidance. My Capstone builds on this corrected foundation: verified accounts, private documents, speech input and bounded specialist cooperation. I will evaluate the complete user journey and compare the added agent complexity against the existing single-agent baseline.”

Use the new presentation's main 14 slides for the transition discussion. The appendix keeps the reusable Core / Easy / Medium / Hard evidence structure. The deck describes a plan, not a claim that Capstone features are already implemented.
