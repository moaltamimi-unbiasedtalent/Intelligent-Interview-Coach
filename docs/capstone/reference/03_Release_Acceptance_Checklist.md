# Ask4Mo Capstone v2: release acceptance checklist

> AC-01–AC-25 remain the base gates. Apply the amendments and additional EX-01–EX-16 in the [v3 checklist](../Ask4Mo_Capstone_Delivery_v3/02_Expanded_Acceptance_Checklist.md). A9 is now included, C10 is a baseline regression, and speech/agents/tenancy/hosting scope has expanded.

This is an unexecuted checklist. Every item begins **Not run**. Fill in actual evidence during implementation; this file does not certify the application. Deadline: 20 October 2026. Feature freeze: 13 October.

## Evidence entry format

For every check record: ID, result (Pass/Fail/Blocked/Not run/Deferred), execution date, exact commit or base commit plus dirty-diff identity, environment, dataset/sample, execution mode (mocked/offline-provider/local integration/live provider/human observation), evidence location, limitations, and defect link if needed. Do not put secrets or private source content in the record.

## Functional gates

| ID | Scenario | Pass condition | Phase / feature |
|---|---|---|---|
| AC-01 | Register/provision, log in, log out, expire session | Backend verifies identity; logout/expiry prevents further protected access; recovery procedure documented | P1 / B1 |
| AC-02 | Two independent users | Direct IDs, list/search, downloads, jobs, events, retrieval, caches, feedback and checkpoint paths respect ownership for the tested cases | P1 onward / B1 |
| AC-03 | Profile and two opportunities | Data persists after restart; the chosen opportunity supplies the correct context; old anonymous records are not silently reassigned | P1, P6 / B2–B3 |
| AC-04 | Complete and revisit Practice | Generate report, leave, reopen from History, reload its owned URL | P2 / A1 |
| AC-05 | Pause and discover Practice | Find an unfinished session in the UI and resume its committed state | P2 / A2 |
| AC-06 | Progress correctness | Metrics match stored data and rubric context; sample size/empty states are honest; memory remains distinct | P2, P6 / A3 |
| AC-07 | Catalogue and knowledge readiness | Safe source URLs work; unavailable processed data is identified; citations refer to evidence actually used | P2 / A4–A5 |
| AC-08 | Upload supported documents | Synthetic PDF, DOCX and TXT complete parsing/review/indexing with authentic page or section provenance | P4 / B4 |
| AC-09 | Upload negative cases | Corrupt, encrypted, scanned, oversized, malicious and unsupported inputs produce safe outcomes; no path traversal or uncontrolled parsing | P4 / B4 |
| AC-10 | Correct, replace and delete document | Corrections remain user amendments; replacement changes version; deletion revokes access and tracks derived-data cleanup | P4 / B4 |
| AC-11 | Dictation coverage | Every eligible input in the inventory supports record/review/edit/insert/undo/typed fallback; exclusions are justified | P3, P8 / B5 |
| AC-12 | Dictation race and error handling | Existing typed text survives; stale results cannot overwrite changed drafts; cancel/navigation/logout releases capture; nothing auto-submits | P3, P8 / B5 |
| AC-13 | Real transcription | Selected provider actually transcribes declared sample audio; mocked tests are separately labelled | P3, P7 / B5–B6 |
| AC-14 | Spoken Practice | Question playback works; one explicit audio-answer submission produces one committed answer/evaluation; retry/reload and text fallback work | P7 / B6–B7 |
| AC-15 | Specialist cooperation | Research and Candidate specialists execute distinct bounded tasks and Mo combines traceable structured findings | P5 / B8 |
| AC-16 | Agent failure boundaries | Timeout, cancellation, budget exhaustion, invalid tools, insufficient/conflicting evidence and HITL replay are handled without unsafe side effects | P5, P6 / B8 |
| AC-17 | Integrated preparation handoff | Reviewed documents/profile/memory reach the right opportunity and typed Practice context after approval; no duplicate session | P6 / B2–B4, B8 |
| AC-18 | Review surfaces | Owned recent runs, safe specialist events, bounded retrieval evidence and actual stored evaluation artifacts can be inspected; missing data is clear | P6 / A6–A8 |
| AC-19 | Core interface | Main pages render without clipping/overlap and support keyboard use, readable contrast, truthful states and declared browser/viewport coverage | P3–P8 / B9 |
| AC-20 | Restart and recovery | Documented local startup works; committed state survives restart; disposable backup restore and selected database/checkpointer migrations pass | P1, P9 / local operation |
| AC-21 | Required regression gate | Actual required tests/build/contracts/security checks pass for release code; skips and failures remain visible | P9, P12 / all |
| AC-22 | Agent/retrieval evaluation | Same-version baseline comparisons have stated denominators; new cases are reported separately; live advantage is claimed only when measured | P5, P9 / evaluation |
| AC-23 | Voice measurement | Defined sample, reference transcripts, correction burden and measured latency are reported with environment/provider limits | P7, P9 / speech |
| AC-24 | Pilot and lessons | Actual participant observations are distinguished from internal review; consequential fixes receive regression checks | P10 / D6 |
| AC-25 | Submission consistency | README, three decks, selected ten-minute path, script, Q&A, ethics, results, demo fallback and limitations match the actual release | P11, P12 / submission |

## Optional checks: execute only if the feature is selected

- A9 export/deletion: an owned completed report exports accurately; confirmed deletion affects the exact documented records; another user's report is inaccessible.
- B7 spoken feedback: controls work and no sensitive audio is retained contrary to policy. Spoken questions remain required whether feedback playback is selected or not.
- C10 guided tour: walkthrough matches real screens, can be dismissed, and does not obstruct keyboard users.
- D1–D4 live integrations: record authorised provider, input scope, spending cap, run count, retries, measured result and configuration state. Configuration alone is not a passed live test.

## Measurable quality policy

P0 records intended environment and initial targets; P3 establishes real speech feasibility; P5 freezes agent comparison tasks and decision criteria before comparative evaluation. Use the existing versioned retrieval suite for inherited regression and a separate Capstone extension suite. Set performance thresholds based on the chosen laptop/provider and declared user workflow before the final evaluation; do not adjust them afterwards to turn failures into passes.

Report median and p95 only when the sample permits meaningful interpretation, always with sample size. An exploratory 3–5 person pilot supports qualitative usability findings, not broad statistical outcome claims. Passing isolation tests supports the covered cases, not an assertion of perfect security. Practice metrics do not predict hiring outcomes.

## Freeze and release decisions

On 13 October, classify each required feature as implemented and tested, implemented with validation outstanding, incomplete, or blocked. Documentation or mocks cannot substitute for an actual required runtime capability. If a core capability cannot fit, report it and obtain a real scope/deadline decision rather than quietly relabelling it optional.

14–17 October: repair blockers and collect missing evidence. Recheck the relevant gates after each change. 18–19 October: package and rehearse the verified code state. Freeze the candidate before a golden run; preserve the result of every attempted live run. A material later change needs applicable regression and a new identified candidate, not reuse of old proof.

The final verdict may be Ready, Ready with stated limitations, or Blocked. A failed core security, persistence, dictation, agent, upload, or voice gate is not compatible with declaring that capability complete. Optional live Langfuse or paid RAGAS absence can remain a disclosed limitation when the release does not rely on it.
