# Ask4Mo Capstone delivery runbook — v2

> Use the [v3 scope and integrated sequence](../Ask4Mo_Capstone_Delivery_v3/00_Expanded_Project_Plan.md) and [extension prompts](../Ask4Mo_Capstone_Delivery_v3/01_Expansion_Claude_Prompts.md) alongside this base runbook. Prior deferrals for newly selected extensions are superseded; the enlarged October schedule requires feasibility review.

Start: Thursday, 24 September 2026. Review deadline: Tuesday, 20 October 2026.
Feature freeze: 13 October. Verification and repairs: 14–17 October. Rehearsal and packaging: 18–19 October.

This is a proposed execution schedule. Availability and API spending limits are not yet known. Dates are planning targets; a phase is complete only when its acceptance checks pass. The implementation work has not been performed by preparing this runbook.

Read with [feature scope and decisions](02_Feature_Scope_and_Decisions.md), [release acceptance checklist](03_Release_Acceptance_Checklist.md), [Claude prompts](01_Claude_Prompt_Pack.md), and the [complete project plan](../Ask4Mo_Capstone_Transition_Plan.md). Version 2 incorporates the missing-feature inventory and explicit phase prerequisites. Start with [04_Start_Here.md](04_Start_Here.md).

## 1. What you are delivering

Ask4Mo becomes a local, personal career-preparation workspace. A candidate signs in, creates a target opportunity, uploads a CV and job description, reviews extracted information, works with Mo and two specialist agents, approves relevant memory, practises aloud, and returns later to reports and progress. Speech-to-text is available across all eligible natural-language fields.

Keep the existing Next.js, FastAPI, LangGraph, governed retrieval, typed preparation handoff, and durable Practice foundations. The archived Sprint 4 release remains the historical baseline. Capstone capabilities must be demonstrated and measured separately.

### Required release capabilities

| ID | Deliverable | Demonstrable acceptance condition |
|---|---|---|
| CAP-01 | Accounts and isolation | Two separate browser profiles sign in as different users; neither can access the other's records, files, audio, retrieval results, or jobs |
| CAP-02 | Personalisation and opportunities | Goals, preferences, role context, and opportunity-specific preparation persist after logout/login |
| CAP-03 | History and Progress | Resume an unfinished interview, reopen a completed report, and inspect genuine practice metrics |
| CAP-04 | Sources and readiness | Open safe catalogue links and distinguish available sources from a missing or incomplete local index |
| CAP-05 | Document uploads | Upload PDF/DOCX/TXT, inspect extraction, make corrections, and obtain citations to actual source pages/sections |
| CAP-06 | Application-wide dictation | All eligible text inputs support record, review, edit, insert, undo, and typed fallback without automatic submission |
| CAP-07 | Voice Practice | Hear a question, record an answer, correct its transcript, submit exactly once, and receive feedback |
| CAP-08 | Cooperating agents | Mo coordinates Research and Candidate specialists; scoped tool decisions and evidence contributions are visible in a safe trace |
| CAP-09 | Frontend redesign | The complete core journey is consistent, responsive, keyboard-accessible, and handles real empty/error/loading states |
| CAP-10 | Diagnostics and evaluation | Recent owned runs and measured evaluation evidence can be inspected; unavailable reports are labelled honestly |
| CAP-11 | Local operation | Start reliably from documented commands, retain data across restart, and restore a disposable backup |
| CAP-12 | Review package | README, requirements matrix, architecture, ethics, results, slides, script, Q&A, and demo fallback agree with the actual release |

English dictation, recorded voice turns, two specialists, individual accounts, and text-based documents are the initial scope. Full duplex voice, OCR, multiple speech languages, additional specialist agents, team tenancy, and public hosting are later work. Do not add them during the verification period.

Working selection: A1–A7 and B1–B9 from the feature matrix are core or bounded core. A8 receives a small actual retrieval-evidence view; a broad inspector is deferred. A9 report export/completed-history deletion and C10 guided tour are optional and not scheduled. B7 spoken questions are core; spoken feedback is optional. C/D/K follow-ups are tracked individually and must not be silently promoted into the release. Existing memory, model profiles, Deep Dive evaluation, HITL and durable sessions should be reused.

## 2. How to use Claude each day

1. Open the actual Ask4Mo repository in Claude's coding environment. The project mirror contains `repo_snapshot`, but that must not be assumed to be your active development checkout.
2. Make this runbook, `01_Claude_Prompt_Pack.md`, and the transition plan available. Local files can be read by an authorised coding environment; a browser-only chat needs the relevant text pasted or attached.
3. For a new conversation, paste the master context from the prompt pack, followed by one numbered phase prompt. In the same conversation, paste only the next phase prompt after the preceding gate passes.
4. Read Claude's baseline/path/branch report before allowing it to use any existing database. Disposable test databases should be the default for tests and migration rehearsals.
5. Let Claude implement, test, and demonstrate the selected phase. Do not paste several implementation prompts while earlier changes are still incomplete.
6. Perform the short manual acceptance check listed below. Mocked API tests alone do not demonstrate that the real application works.
7. Ask Claude to update `docs/capstone/status.md`, the requirements matrix, and the phase evidence before ending the session. Use the session handoff prompt if work continues another day.
8. Review a checkpoint before moving forward. Local changes can remain staged or unstaged; commits and pushes follow your repository rules and an explicit git instruction. Do not assume a commit means the phase passed.

At the start of a phase, Claude should compare the previous gate's code state with the current working tree. Reuse still-valid evidence and rerun checks only for changes or unresolved risks. A complete phase ends in a demonstrable user outcome and updated evidence; an incomplete phase ends in a precise remaining-work prompt, not an invented pass.

Use the independent review prompt at each milestone. Failed gates become the next repair task; do not carry an untested dependency into a later phase without explicitly marking it blocked.

## 3. Calendar and ready-to-use prompts

| Dates | Prompt | Outcome | Your manual check |
|---|---|---|---|
| 24 Sep | P0: Baseline and scope | Actual checkout, branch, baseline, requirements matrix, backlog, speech/auth feasibility decisions | Read what already works, what is missing, and what remains unverified |
| 25–27 Sep | P1: Accounts and local operation | Verified local identity, persistence, profiles, opportunity ownership | Two browsers, two users, different saved content; restart and log in again |
| 28–29 Sep | P2: Repair the return journey | History detail/resume, Progress metrics, source links and readiness | Finish a session, reopen its report, resume another, inspect Progress and Sources |
| 30 Sep–1 Oct | P3: Shared interface and dictation foundation | Consistent main layout, reusable inputs, actual dictation vertical slice | Dictate into Prepare and a profile field; edit, insert, cancel, and type normally |
| 2–4 Oct | P4: Private documents | Upload, review, index, source citation and deletion flow | Upload synthetic CV/JD, correct a claim, verify citation, then remove access |
| 5–6 Oct | P5: Supervisor and specialists | Mo plus Research and Candidate agents with bounded cooperation | Run one preparation task and inspect each specialist's contribution |
| 7–8 Oct | P6: Integration and diagnostics | Personalised plan, approval/handoff, recent runs and evaluation access | Move from documents through agent preparation into Practice without retyping context |
| 9–10 Oct | P7: Spoken Practice | Spoken questions and durable recorded-answer workflow | Hear, record, review transcript, submit, reload, inspect evaluation |
| 11–13 Oct | P8: Coverage, polish and freeze | Dictation across the eligible-input inventory, responsive core flow, feature freeze | Complete the full journey by typing and by dictation; verify mobile layout and keyboard access |
| 14–15 Oct | P9: Release verification | Regression, ownership, retrieval, agent comparison, speech and recovery evidence | Read a factual pass/fail/blocked report and reproduce the main journey |
| 16–17 Oct | P10: Pilot and repairs | Small observed user pilot, documented findings and tested corrections | Observe 3–5 participants if available; record actual completion and confusion |
| 18 Oct | P11: Submission materials | Presentation package, speaking notes, Q&A, README and ethics/evaluation report | Match every claim to the running app or a recorded test result |
| 19 Oct | P12: Final rehearsal and freeze | Final verification, golden result, package manifest and recorded fallback | Ten-minute rehearsal followed by five minutes of questions |
| 20 Oct | Review | Present the frozen release | Start early and use the rehearsed startup/demo procedure |

This plan reserves time for testing and presentation. It should not be interpreted as evidence that every feature is guaranteed within the dates. Make dependencies smaller if necessary, while keeping truthful delivery status.

### Dependencies and acceptance ownership

| Prompt | Needs | Required acceptance evidence |
|---|---|---|
| P0 | Active checkout and supplied brief | Baseline, scope, dependency decisions, actual capacity assumptions and evaluation plan; no feature completion implied |
| P1 | P0 auth/persistence decisions | AC-01–AC-03; initial AC-20 |
| P2 | Verified P1 identity | AC-04–AC-07 with real local persistence |
| P3 | Authenticated API; P0 speech decision | Initial AC-11–AC-13 and AC-19 on Prepare/profile |
| P4 | P1 ownership; P3 inputs/layouts | AC-08–AC-10 and private-data AC-02 |
| P5 | Authorised document context and existing retrieval | AC-15–AC-16; comparison design for AC-22 |
| P6 | P1–P5 usable integration | AC-17–AC-18, correct opportunity context and report return |
| P7 | Actual P3 transcription and durable Practice | AC-13–AC-14, preliminary AC-23 |
| P8 | Core P1–P7 features | Full inventory AC-11–AC-12, AC-19, feature-freeze report |
| P9 | Frozen candidate | AC-02, AC-20–AC-23 and complete required regression; inherited/new metrics kept distinct |
| P10 | Usable candidate and actual participants if available | AC-24; evidence and regressions for fixes |
| P11 | Current implementation/evaluation evidence | Draft AC-25 and exact artifact manifest |
| P12 | Identified final candidate and all evidence | Final AC-25, replay of relevant runtime gates and truthful release verdict |

P1–P7 may include independent work when one provider is unavailable, but the relevant runtime gate remains blocked. There is no rule requiring a paid RAGAS judge or live Langfuse to pass the core release. There is a requirement to actually demonstrate promised speech, accounts, private files and specialist execution.

### Tomorrow's checklist: 24 September

- Open the active Ask4Mo development checkout.
- Provide the master prompt and P0.
- Confirm where the frozen Sprint 4 tag points and whether newer work already exists.
- Have Claude create an isolated Capstone working branch or worktree while preserving current changes.
- Review the requirements matrix and failure inventory.
- Confirm the available laptop resources and how existing speech code can be reused.
- Have Claude choose a concrete local authentication and speech approach, recording compatibility constraints and remaining decisions.
- Review the A/B/C/D/K feature dispositions and keep optional items separate until selected.
- Record available working hours and define cost caps before any paid run; a credential's presence is not an execution budget.
- Confirm that baseline tests use disposable data and no paid provider calls.
- Finish with a usable P1 handoff. P0 should produce facts and an executable backlog, not new feature claims.

## 4. Repository and evidence conventions

Suggested Capstone records inside the actual repository:

```text
docs/capstone/
  charter.md
  requirements_matrix.md
  baseline.md
  decisions.md
  status.md
  dictation_inventory.md
  evaluation_plan.md
  release_checklist.md
  feature_scope.md
  phases/
    P0.md ... P12.md
  evidence/
    index.md
```

Keep raw test logs, screenshots, benchmark outputs, recordings, and datasets in appropriate ignored working directories unless a reviewed, sanitised artifact is deliberately selected for the repository. Never commit candidate documents, credentials, local databases, or private audio. Evidence links must identify the run, date, code state, dataset, execution mode, and result. If the working tree was dirty, record the base commit and relevant diff identity rather than falsely attributing the result to a clean commit.

Every requirement uses the reusable columns `#`, `Requirement/Task`, `Status`, and `How/Evidence`; dependency and acceptance-test columns may be added. Use `Not started`, `In progress`, `Passed`, `Failed`, `Blocked`, or `Deferred` consistently.

Each phase report should contain:

1. User-visible outcome and the reason it matters.
2. How it was implemented, with accurate source pointers and architecture boundaries.
3. Checks run, actual results, and whether evidence is mocked, offline, or live.
4. Screenshots and a short manual reproduction path.
5. Remaining issues and severity rationale.
6. Reviewer explanation: why this design, hardest edge case, tradeoff, and learning.
7. Exact next step, configuration names still needed, and safe rollback approach.

The phase prompt now defines these evidence outputs explicitly. Record both an implementation verdict and any outstanding provider/participant validation so 'built' does not silently become 'verified live'. Keep retrospective descriptions consistent with the actual final code.

This supplies the final presentation continuously instead of requiring the project story to be reconstructed on October 18.

## 5. Implementation rules that carry across phases

- Verify the real checkout, applicable `AGENTS.md` and `CLAUDE.md`, current branch, working tree, remotes, and release tags before changes. Existing code and current evidence take precedence over historical descriptive paragraphs when identifying what is implemented; safety and repository workflow rules remain applicable.
- Do not rewrite the Sprint 4 tag or treat an old release pass as proof for Capstone changes.
- Implement on a Capstone working branch/worktree. Preserve unrelated changes. Do not reset, clean, overwrite, or reassign existing user data.
- Reuse application services and typed contracts. Keep business logic out of FastAPI route handlers and UI components.
- Authentication must be verified by the backend. User-supplied IDs and development headers cannot grant access to another user's content.
- Keep private documents, audio and retrieval scoped to the authenticated user. Agents cannot choose arbitrary owners or bypass access checks.
- Approved preparation memory remains selective. Full CVs, answers, transcripts, and conversation logs are not automatically copied into memory.
- Speech-to-text produces editable drafts. It never automatically approves memory, submits an answer, or sends a chat message.
- Bound agent steps, delegation depth, document/audio size, processing time, and spending. Unknown cost or usage is reported as unavailable, not zero.
- Mocks belong in tests. A real application screen must not display fabricated reports or fake transcription to satisfy acceptance.
- Keep package versions compatible with the installed LangChain/LangGraph/checkpointer set. Inspect existing speech and experimental Live components before adding dependencies. A current online example may target a different major version.
- Use targeted tests during implementation, milestone checks before phase completion, and the complete required release gate before freeze. Never weaken tests to manufacture a pass.
- Local running does not imply offline operation. Explicitly document which model, embedding, research or speech calls leave the machine.

## 6. Verification tiers

### During implementation

Run changed-area Python/frontend tests, relevant contract tests and type checks. For UI changes, inspect the actual rendered page with real local API behavior; record fixture-based screenshots separately. For document and audio handlers, exercise negative and ownership paths as well as success.

### At milestone completion

Run the affected suites and the repository's required frontend checks. The inspected snapshot defines frontend lint, unit tests, type checking, build, and Playwright scripts, plus Python tests and Ruff. Reconfirm these against the actual checkout before invoking them. Migration and backup tests use disposable local databases.

### Before release

Run the complete required offline test/evaluation gate, owner-isolation matrix, local restart and backup restore, full journey, and supported-browser checks. Publish failures, skipped cases and blockers. Paid/live checks are separate and require the configured credentials and an approved execution budget. No repeated paid runs should be hidden as one successful golden run.

### User pilot

Use short task cards and synthetic or consented data. Observe sign-in, upload, evidence verification, dictation, practice and return to a report. Record completions, confusion, time spent, corrections and feedback. Do not claim actual pilot outcomes until people have participated. If nobody is available, report an internal usability review accurately.

## 7. What to do when a phase is late or blocked

First identify whether the blocker is code, local setup, an external dependency, a missing budget, or an unresolved product choice. Fix in-scope code and setup issues before expanding features.

Preserve the core promises: accounts, private documents, cooperating agents, app-wide dictation, spoken Practice, complete report return, and the improved core UI. Simplify optional scope: start with text-based documents, English dictation, two specialists, concise progress metrics, and one supported desktop browser with responsive layouts. State any browser limitation explicitly.

On 8 October, review the remaining work against measured progress. If the critical path cannot fit, revise the scope or review timing openly rather than sacrificing the 14–19 October verification and packaging window. Do not silently drop a promised pillar.

Also check on 4 October that verified accounts, real document ingestion and real dictation are usable. A failed early foundation should trigger repair before specialist/UI breadth increases. A provider outage does not justify fake sample output in the application; report reduced capability and keep the typed path usable.

On 13 October, stop adding capabilities. After the freeze, allow only fixes, necessary accessibility repairs, documentation, and evidence collection. Every material fix receives relevant regression checks; update the recorded release candidate before a final golden run.

## 8. Review package manifest

- Updated README with goal, problem, how it works, exact local startup, external dependencies, screenshots and limitations.
- Capstone requirements matrix and explicit Sprint 4 versus new Capstone contribution table.
- Architecture, authentication, data-flow, retrieval, specialist-agent and speech diagrams.
- Evaluation report with dataset versions, sample sizes, actual results, costs/latencies when available, and honest exclusions.
- Ethics/privacy report: ownership, uploaded files, audio, retention, deletion, source bias, accessibility, and limits of practice scores.
- Complete App Walkthrough deck, Sprint-to-Capstone Review deck, and Product Journey deck, preserving their distinct purposes and the standard evidence tables.
- A concise 10-minute live presentation, which may be a selected subset of the review deck with an explicit slide list, plus a five-minute Q&A plan.
- Speaking script, reviewer Q&A, lessons, limitations, future work, and a reusable submission checklist.
- Recorded demo fallback and sanitised synthetic demo dataset.
- Local release manifest identifying the reviewed code state and the evidence produced from it.

Use the six course presentation topics: problem, solution, data, evaluation, challenges, and what's next. Use SCR or SMART explicitly. Map to Outcome Quality, Learning Application, Ethical Considerations, and Presentation. The earlier Sprint bonus classification can remain as supporting history; do not describe it as an extra Capstone requirement unless the Capstone brief says so.

The course brief mentions deployment but does not explicitly resolve whether local execution alone satisfies that expectation. Ask the course lead early; continue the local implementation while awaiting their answer. Showcase submission is optional in the supplied brief, and its description must accurately represent a local demonstration.

## 9. Available context and cautions

This runbook is based on the local `repo_snapshot` inspection, the supplied Capstone brief, the prior product audit, and `Ask4Mo_Capstone_Transition_Plan.md`. The active development repository may have changed. Some historical repository documentation has stale tool/test counts and old architecture descriptions. P0 must resolve those from actual code and the appropriate dated release evidence.

Existing recorded-speech and experimental live components are candidates for reuse; their presence does not prove they are integrated into the primary Next.js UI or work on this laptop. The specialist-agent and authentication implementations are new Capstone work unless P0 finds newer completed changes.

Use `01_Claude_Prompt_Pack.md` for the master prompt, P0–P12, independent review, repair, and session handoff prompts.

## 10. Final owner checklist

- Confirm with the course lead whether the reproducible local demonstration meets the deployment expectation; do not infer public hosting is mandatory from example tools.
- Supply only synthetic or explicitly consented documents/audio for demos and evaluation.
- Test the main journey yourself at the end of each milestone; a coding summary is not the acceptance check.
- Arrange pilot participants early enough for 16–17 October. The assistant cannot fabricate this evidence.
- Keep a known working local startup and a recorded fallback ready before the review day.
- Request any optional addition by its feature ID so the matrix, prompts and schedule can be updated together.
