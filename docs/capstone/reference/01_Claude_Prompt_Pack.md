# Ask4Mo Capstone v2: copy-ready detailed Claude prompts

> Before using these base prompts, paste the [v3 master override and applicable extension](../Ask4Mo_Capstone_Delivery_v3/01_Expansion_Claude_Prompts.md). The old local-only, English-only, two-specialist and deferred-extension limits are superseded for the owner-selected v3 scope. Also retain the 401-commit baseline corrections.

Start 24 September 2026. Review deadline 20 October 2026. Feature freeze 13 October.

How to use: in a new Claude coding conversation, paste MASTER CONTEXT followed by exactly one phase prompt. Continue with the next phase only after its dependency gates pass. The phase prompts authorise implementation of their stated scope; P0 is baseline/design work. The prompt text is ready to copy from each fenced block.

Provide `00_Delivery_Runbook.md` and `Ask4Mo_Capstone_Transition_Plan.md` if accessible. Do not assume Claude can read a Codex project mirror or files that were not attached. The master prompt contains the essential context so work can begin without those optional companions.

Version 2 also uses `02_Feature_Scope_and_Decisions.md` and `03_Release_Acceptance_Checklist.md`. Give them to Claude with the runbook. Feature IDs A/B/C/D/K define scope; CAP-01–CAP-12 define deliverables; AC-01–AC-25 define acceptance. The phase prompts specify how to proceed if companion files or prerequisite evidence are unavailable. Read `04_Start_Here.md` for the first-session procedure.

## MASTER CONTEXT — paste at the start of every new conversation

```text
You are my implementation partner for the Ask4Mo AI Engineering Capstone. Start date: 24 September 2026. Review deadline: 20 October 2026. Feature freeze: 13 October; verification and repairs: 14–17 October; packaging and rehearsal: 18–19 October. We are building a reproducible local application on my computer. Cloud hosting is not requested. Weekly availability and paid API budget have not been confirmed.

Product: evolve Sprint 4 into a private career-preparation workspace with individual logins, personalisation, target opportunities, CV/job-description uploads, application-wide speech-to-text, spoken interview practice, Mo supervising Research and Candidate specialist agents, an improved frontend, usable History and Progress, and inspectable evidence.

Working scope: A1–A7 (History, active resume, real Progress, catalogue links/readiness, recent runs, read-only evaluations) and B1–B9 (accounts, profile, opportunities, private documents, app-wide dictation, recorded Practice, spoken questions, two specialists, frontend redesign). A8 is a bounded retrieval-evidence view. A9 report export/completed-history deletion and C10 guided tour are optional and must not be silently added. Spoken feedback is optional; spoken questions are required. Other C extensions and knowledge-coverage expansion stay backlog. D validation follows actual dependency needs and budget. This is the established working plan, not approval for every listed optional feature.

October release scope: local accounts; private text-based PDF/DOCX/TXT; English dictation across all eligible natural-language inputs; recorded voice answers and spoken questions; Mo plus two substantive specialist agents; complete report return; responsive core UI. Full duplex voice, OCR, more languages, extra specialists, team accounts and public hosting are deferred unless core gates pass early. Camera assessment and automatic job applications are outside scope.

First resolve the actual checkout. Inspect repository root, applicable AGENTS.md and CLAUDE.md, branch, working tree, remotes, and release tags. Read docs/capstone/status.md and previous phase evidence if present. Do not assume a project mirror or repo_snapshot is my active development checkout. Preserve unrelated changes. Historical Sprint 4 baseline was sprint4-submission-ready at 1b084cb; verify it and preserve it. Do not move release tags, reset/clean the tree, or overwrite existing user data. Work on a dedicated Capstone branch/worktree. If current work is already correctly isolated, continue there.

The current architecture is Next.js + FastAPI, application services, LangGraph, governed structured/hybrid retrieval, typed PreparationContext, and durable deterministic Interview Practice. Streamlit is legacy/development only. Preserve domain boundaries, HITL, user-scoped data, provenance, idempotency, model registry and safe logging. Build new agents through bounded orchestration; deterministic validation and permissions remain enforced in code. Keep the Sprint 4 single-agent option for comparison.

Audit findings to re-check, not blindly assume: Progress currently exposes memory rather than practice analytics; History lists IDs without detail navigation; catalogue source URLs are omitted; Agent Inspector needs a run ID; RAG/Evaluation pages may be placeholders. Existing recorded speech and experimental Live components may be reusable. Some descriptive sections of CLAUDE.md and older docs contain historical counts/architecture. Resolve current behavior from code and dated evidence, while respecting applicable repository safety/workflow instructions. Update Capstone guidance to record intentional changes from the historical single-agent design.

Every eligible natural-language field must support the shared dictation flow: microphone, record, stop, review/edit, insert, undo, explicit submit/save. Preserve typed text. No automatic chat sends, answer submissions, memory approval, or settings saves. Exclude passwords, codes, secrets, file pickers, technical identifiers and structured selectors. Stop microphone capture on cancel, navigation and logout. Bind transcription results to the originating user, field and draft version. Keep typing available.

Existing Deep Dive answer evaluation, approved memory, model profiles, typed handoff and durable Practice are foundations to preserve. A statement in an older document that a capability is out of scope is not proof it is absent. Historical tool/test counts must be date-labelled; the Capstone registry and test results must be measured from its actual code.

Use authenticated backend identity, never a browser-controlled user ID or development header as deployed authorisation. Scope documents, chunks, recordings, runs, jobs, caches and downloads to the verified user. Uploads and transcripts are untrusted data. Keep full CVs/transcripts outside selective approved memory. Private files stay outside frontend public directories. Do not log or expose credentials, raw private content, prompts or hidden reasoning.

Run tests on disposable local data. No paid model/speech/research/evaluation calls or external private-data transfer without a specific approved budget and dataset scope. Offline synthetic tests can run; distinguish mocks from real integration evidence. Do not fabricate metrics, scores, traces, user feedback or successful checks. Unknown cost is unknown, not zero. Do not run migrations against an unidentified/shared database.

Complete the requested phase: inspect, implement within scope, test, inspect the real interface where relevant, and update documentation. Choose routine reversible implementation details and explain significant decisions. If a dependency is blocked, complete independent work and identify the exact remaining requirement; do not call the phase passed. Do not stop at a plan when the phase asks for implementation. No commit, push, PR creation, merge or deployment unless my current prompt explicitly asks for it.

Maintain docs/capstone/{charter,requirements_matrix,baseline,decisions,status,dictation_inventory,evaluation_plan,release_checklist}.md and docs/capstone/phases/<phase>.md as relevant. Keep evidence links with date, code state, dataset, execution mode and actual outcome. Store raw/private/generated artifacts appropriately and do not commit them by default. Use #, Requirement/Task, Status, How/Evidence in requirements reporting.

Also maintain docs/capstone/feature_scope.md with inclusion decisions and map the supplied AC acceptance IDs into release_checklist.md. If companion files are unavailable, reconstruct only the stated core requirements and write that the full supplied matrix needs importing; do not invent optional approvals. At phase start inspect prerequisite evidence and current diff. Continue safe independent tasks while a provider/input is blocked; preserve that dependency's blocked status. At phase end link every relevant requirement to observed evidence and state any acceptance that has not actually run.

At completion report: user-visible changes; why/how implemented; important files; tests and real observed results; demo steps; limitations/blockers; and the exact next step. Add a short reviewer explanation and lessons to the phase report. Separate historical Sprint 4 evidence, current offline tests, actual local integration, and live paid evidence.
```

## P0 — 24 September: establish the baseline and executable scope

```text
Execute Capstone P0: baseline, feasibility, and delivery setup. Apply the master context. Do not implement new product features in this phase.

Inputs: the actual repository, supplied Capstone brief if accessible, v2 runbook/scope/checklist, and current working-tree state. If the brief is unavailable, use the documented course criteria and mark the source check pending. Produce factual decisions and a usable implementation handoff; do not change application runtime behavior.

1. Resolve the real checkout, branch, worktree state, applicable instructions, and release reference. Verify whether newer user work already fixes any known gap. Inspect first; then establish a safe Capstone branch/worktree for this work, preserving all unrelated changes and the Sprint 4 release.
2. Inspect actual Next.js/FastAPI routes and services, authentication, persistence/checkpoints, document loaders, speech providers, experimental Live components, model registry, retrieval, and test commands. Identify reusable implementations and primary-UI gaps. Check dependency compatibility, especially LangGraph and checkpoint versions; do not assume current documentation examples fit installed versions.
3. Reproduce the known History, Progress, Sources and Diagnostics behavior with safe local data where feasible. Clearly label code inspection versus actual runtime verification. Do not reuse historical test counts as current results.
4. Create the Capstone charter, requirements matrix, baseline, status, decisions, evaluation plan and dictation inventory. Use CAP-01 to CAP-12 for accounts, personalisation/opportunities, History/Progress, Sources, documents, app-wide dictation, voice Practice, cooperating agents, frontend, diagnostics/evaluation, local operation, and submission materials. Include precise acceptance checks and dependencies.
5. Establish the proposed UI flow: Overview, Opportunities, Documents, Prepare, Practice, Progress, Settings, with a separate reviewer view. Produce simple reviewable wireframes or route/component descriptions using existing styles as context. Do not begin a speculative frontend rewrite.
6. Check laptop/runtime resources without exposing private files or secrets. Assess local auth, database, storage/worker, parsing, speech-to-text and text-to-speech options. Inspect existing speech code before adding anything. Conduct small offline/synthetic feasibility checks if dependencies are available. Paid/live checks stay blocked pending a specific budget. Recommend one concrete compatible approach for P1 and speech, with fallback and factual tradeoffs.
7. Run a bounded offline baseline in the isolated checkout using disposable data. Reconfirm actual repository commands and any existing failures before edits. Record failures as inherited, not silently fixed. Design the full later release gate.

8. Import the A/B/C/D/K scope dispositions and AC-01–AC-25 checklist. Inventory every eligible dictation field by route, component, field name, save behavior, sensitivity and planned test. Include a 'not implemented' status until real transcription and insertion work. Verify whether History export, Deep Dive evaluation, authentication or speech exist only in legacy code, partially in backend, or end to end.
9. Record a dependency/risk register with detection method, fallback, and schedule effect. Front-load auth interoperability, document isolation and speech hardware/provider feasibility. Establish an initial performance/cost measurement plan and the 4/8 October capacity checkpoints. Record unconfirmed weekly availability explicitly; do not promise a guaranteed four-week implementation.

Required outputs: baseline and charter, feature_scope.md, requirements_matrix.md, decisions.md, dictation_inventory.md, evaluation_plan.md, release_checklist.md, status.md and phases/P0.md. Each decision should say why the chosen approach fits this repository and what evidence remains. P0 does not pass any runtime feature gate merely by documenting it.

P0 is complete when the actual baseline is documented, requirements and dependencies are explicit, a safe working branch exists, and P1 can begin from a concrete auth/persistence decision. Provide an exact next-session handoff. Do not create commits, push, or change live/shared data.
```

## P1 — 25–27 September: accounts, personalisation and local persistence

```text
Implement Capstone P1 using the verified P0 decisions and master context. If P0 is missing, perform its necessary safety/baseline checks first and record them.

Dependency gate: verify P0's chosen identity/session contract and database plan against installed packages. Scope B1–B3 and AC-01–AC-03, plus initial AC-20. Show an explicit request-to-user-ID trust path so both Next.js and direct FastAPI calls enforce the same identity. Keep the minimal opportunity model ready for later document/session foreign keys without inventing team tenancy.

Deliver one coherent account foundation: local account creation or an explicitly documented provisioned-account flow, login, logout, session expiry, basic personalisation, and private target opportunities. Use established maintained authentication/session/password components compatible with this repository; do not invent cryptography. Document a safe local recovery procedure. Public email and social-login services are not required for this phase.

FastAPI must derive identity from verified authentication. Reject spoofed X-User-Subject or payload user_id as access authority. Protect direct API calls as well as Next.js routes. Apply cookie/CSRF/origin controls appropriate to the chosen transport; keep credentials and private content out of logs and browser storage. Separate any intentionally enabled development identity mode from normal authenticated operation.

Persist account profile, goals, coaching preferences and opportunities. Keep explicit profile data, user-approved memory and performance evidence distinct. Do not automatically attach old anonymous/demo records to a new account. Preserve existing users/data and use safe versioned migrations on a disposable local database first. Verify local PostgreSQL and checkpoint compatibility if selected in P0; report any fallback accurately.

Provide minimal functional account/onboarding/settings UI integrated into the existing application. New natural-language inputs should support the shared dictation component once it lands; record them in the inventory now. Do not add nonfunctional microphone controls.

Create two synthetic users and verify through real local API/browser sessions that profiles, opportunities, memory, runs, interviews and history are correctly separated. Test expired/invalid sessions, forged IDs/headers, logout, and restart persistence. Check that current core flows still work under verified identity. Use isolated browser profiles and test data, not real candidate accounts.

Include negative checks for changing an opportunity's owner/ID in a request, using another user's session/run ID, stale session credentials after logout where the selected session mechanism promises revocation, and unauthenticated direct API calls. Verify that secrets and private records do not enter client bundles or logs. Explicitly distinguish authentication failure from missing database configuration. Rehearse migrations and a restore into a separate disposable target if using PostgreSQL; do not treat SQLite success as Postgres proof.

Deliver phase evidence, owner-visible login/profile/opportunity screens, exact local startup/recovery instructions, and an idempotent synthetic-account fixture for later tests. Record backend-verification and persistence results separately. A successful login screen without verified API ownership cannot pass P1.

Update P1 evidence and configuration documentation. Report authentication and database tests separately, including known limits of local multi-user demonstration. P1 passes only when two actual signed-in accounts retain their own data and cannot retrieve each other's content through tested paths.
```

## P2 — 28–29 September: close the existing product gaps

```text
Implement Capstone P2: make the return-to-practice journey complete. Use verified account identity from P1 and reuse existing domain/repository capabilities.

Dependency gate: P1 identity and owned session access must be working. Cover A1–A5 and AC-04–AC-07. Export and deletion of completed reports (A9) remain optional and unscheduled; preserve existing functionality but do not introduce the new primary workflow under this prompt.

1. History: show role, date and status; separate active/resumable sessions and completed reports; connect list items to detail/report views; support refresh and direct owned URLs. Preserve existing session/report idempotency and empty/error states. Do not mark an unfinished session as a completed report.
2. Progress: expose existing real practice metrics through an application/API boundary; include data definitions and sample counts. Keep approved memory separate. Show honest empty/insufficient-data states. No fabricated trend points or hiring predictions; do not compare incompatible scoring rubrics without explanation.
3. Sources: carry source_url through the typed catalogue API and render validated safe links. Preserve per-answer citations. Distinguish configured catalogue entries from actually built/usable knowledge stores and communicate rebuild/readiness status. Do not let untrusted URL schemes become clickable links.
4. Diagnostics: label existing capabilities accurately and remove misleading claims about empty placeholders. Full recent-run/evaluation wiring is P6; do not claim it is complete here.

Add meaningful API/contract/browser tests: create/complete a synthetic session and reopen its report from History; resume a different session; verify calculated Progress against stored data; follow a safe source link; check owner isolation and direct URLs. Use real local API persistence for at least one complete flow. Clearly separate any provider stubs from real model validation.

Use fixed synthetic records with known metric values to check numerator/denominator, no-data and one-session behavior. Distinguish completed report records from paused sessions. A user's Progress must not include another user's scores. Verify empty, loading, API-error and missing-knowledge-index states on the rendered interface. Preserve compatible existing History/Practice URLs or provide explicit redirects.

Deliver accurate API contracts, working UI paths, metric definitions, affected regression evidence, and phases/P2.md with before/after screenshots using synthetic data. State the difference between session durability and discoverability in the reviewer explanation.

Inspect the actual pages and document before/after behavior. P2 passes when completed reports are viewable, active sessions are resumable, practice metrics are meaningful, and source links/readiness are honest.
```

## P3 — 30 September–1 October: frontend system and shared dictation

```text
Implement Capstone P3: the shared interface system and a real reusable dictation vertical slice. Read P0 design decisions and existing frontend conventions before editing.

Dependency gate: authenticated local API and a documented speech provider decision. Cover initial B5/B9 and AC-11–AC-13/AC-19. Confirm the microphone capture formats supported by the declared target browser and what the selected transcription boundary accepts; avoid an untested format assumption. Inspect the existing speech service before building a second one.

Create or refine common design tokens, navigation, page layouts, forms, buttons, loading/empty/error states and accessible focus behavior. Apply them to Overview, profile/onboarding and Prepare first. Keep the existing brand recognisable and prioritize clear next actions, readable content and consistent spacing. Do not populate screens with invented analytics or future-feature buttons.

Implement a provider-neutral authenticated transcription boundary and shared recording/dictation control. Reuse viable recorded-speech components and services after verifying their contracts; adapt primary Next.js behavior without importing Streamlit UI into the backend. Validate audio size/type/duration and user ownership. Establish temporary-file cleanup and request limits.

Flow: select a field microphone, record, stop, review/edit transcript, explicitly insert into that draft, then submit/save through the normal control. Preserve typed text, explicit append/replace choice, and undo. Provide idle/recording/transcribing/ready/error states, accessible labels, keyboard controls, cancel/retry, and typed fallback. Only one capture may be active. Stop tracks on navigation/logout/unmount. Late results must not overwrite a changed draft, switched field or different session.

Integrate first into Prepare and one profile/onboarding field. Verify permission denial, silence, missing/unsupported microphone, oversized clips, provider failure, authentication expiry and stale results. Exclude password/code fields. Audio stays temporary unless retention is explicitly selected.

Bind each capture to its original user/session, field and draft version. Exercise a late response after typed edits, field switch, navigation, and logout/login as another user. Define whether append/replace is permitted when the draft changed; never silently apply to the current focused field. Record result discard and retry behavior. Tests may simulate browser capture for deterministic cases, but actual recording/transcription needs a separately observed demonstration.

Deliver a short reusable component/API contract, a real two-surface dictation demo, supported-browser and provider limits, and phases/P3.md. Record the observed transcription/correction/latency baseline and set proposed practical thresholds before final evaluation. Do not defer provider feasibility to P7.

Use an actual offline speech provider on synthetic audio if feasible under P0's choice. If only a paid/cloud provider is configured and no budget exists, implement/test the boundary with clearly labelled mocks, keep the live acceptance gate blocked, and do not show fake transcription in normal UI. Report precisely what input was actually transcribed.

Update the eligible-input inventory and speech decision record, including browser support, external data transfer, configuration and cost visibility. P3 needs functioning core layouts and actual transcription in the two selected fields; mocks alone cannot pass the live dictation gate.
```

## P4 — 2–4 October: private document preparation workspace

```text
Implement Capstone P4: private CV, job-description and supporting-document workflows using the existing upload/parser services where compatible. Maintain P1 identity and P3 design/dictation components.

Dependency gate: verified ownership, opportunity records, local private storage and usable shared inputs. Cover B3–B4, AC-08–AC-10 and expanded AC-02. Maintain a stable document/version identity so replacement cannot make an old citation point silently to new content. Keep extracted facts awaiting user review distinct from approved profile or memory.

Support text-based PDF, DOCX and TXT. Validate real format rather than trusting filename/content-type alone; enforce size/page/decompression/time limits, safe generated storage names and private local paths. Constrain parsing and implement the selected quarantine/scanning policy. If a scanning dependency is missing, expose the actual readiness/blocking state rather than claiming files were scanned. Give clear outcomes for corrupt, encrypted, scanned and unsupported files.

Implement tracked ingestion states, safe retry and restart recovery using a minimal worker/job approach compatible with the local setup. Parse, extract, let the candidate review/correct facts, then index. Keep immutable extracted source content distinct from user corrections and approved profile/memory. A correction must not be falsely quoted as original document text.

Associate documents with the verified user and target opportunity. Scope chunks, embeddings, retrieval, caches, jobs, previews and downloads before content reaches the model. Use backend ownership checks; do not allow user IDs/collection names supplied by an agent to select someone else's data. Keep private documents separate from the public knowledge corpus.

Show document status, preview/extracted text, corrections using dictation, source-backed questions, replacement and deletion. Cite stable document/version and actual page or section. Use section references where page numbers cannot be established; never invent locations. Revoke retrieval/download access immediately on deletion, then track cleanup of files, derived data and caches. Document how existing reports/checkpoints/backups are handled separately.

Verify with synthetic CV/JD fixtures: upload, extract, correct, index, retrieve, verify citation, replace, delete, restart and retry. Include prompt-injection text, malformed files, private retrieval probes and guessed IDs from a second user. Clearly label any mocked embedding or model output; real extraction and ownership must be demonstrated.

Exercise deleting a document while its indexing job is running: stale workers must not republish deleted content. Test deduplication/idempotent retries, stale job results after replacement, malicious filenames, and access checks on direct previews/downloads as well as search. Select a bounded safe worker strategy and surface processing failures; no endless spinners. If extraction lacks reliable page numbering, use honest stable sections instead.

Deliver a reusable synthetic fixture set, document/job lifecycle definitions, field/source provenance rules, storage and cleanup behavior, API/worker/browser evidence, and phases/P4.md. At the 4 October checkpoint, state whether accounts, actual ingestion and real dictation work together. If not, prioritise those blockers before adding specialist breadth.

P4 passes when a user can build verifiable preparation context from private documents, and a second user cannot retrieve their content.
```

## P5 — 5–6 October: Mo and two cooperating specialist agents

```text
Implement Capstone P5: a bounded supervisor architecture using the installed LangGraph-compatible APIs. Preserve the existing single-agent route as a documented baseline/fallback, and retain deterministic domain services.

Dependency gate: P4 can supply authorised reviewed document context and existing retrieval is usable or honestly reports insufficiency. Cover B8, AC-15–AC-16 and experiment design for AC-22. Implement two specialists only; additional Preparation/Evaluation agents are deferred. Do not import a newer incompatible supervisor library merely because an example uses it.

Mo remains the candidate-facing supervisor. Add Research and Candidate specialists with distinct system contracts, scoped tools and meaningful tool-selection loops. Research gathers governed career/company/market evidence using available sources. Candidate compares user-approved document facts with job requirements and identifies supportable strengths, gaps and clarification needs. Do not rename ordinary deterministic functions as autonomous agents merely to claim multi-agent functionality.

Define typed evidence packets containing claims/findings, supporting source/document IDs, uncertainties, status and safe usage metadata. Pass only authorised task-relevant context. When inputs allow, run independent research and candidate analysis concurrently; synthesis/planning waits for required results. Preserve deterministic planner/calculation behavior unless a specific change is justified and measured.

Apply one overall run budget as well as specialist step/time limits. Restrict delegation depth and tool scope, propagate cancellation, and handle partial failure and conflicting/insufficient evidence explicitly. Specialists cannot bypass user identity, promote untrusted text to instructions, write memory without approval, or create Practice sessions directly. Preserve HITL checkpoint/resume and idempotent application-side handoff.

Extend safe events/usage aggregation to specialist runs without double counting model calls or exposing prompts, private payloads or reasoning. Count registered tools and delegation capabilities accurately for the Capstone; the historical Sprint 4 '6 + 2' count is not automatically the new registry count.

Test routing, preconditions, bounded termination, failure/cancellation, duplicate/resumed work, source provenance, user isolation and same-thread continuation. Define matched baseline versus cooperating-agent tasks and promotion criteria before measuring outcomes. Run deterministic tests now; live model comparisons require an explicit authorised budget and synthetic/public data.

Include conflicting specialist claims, one failed specialist, empty evidence, stale/missing opportunity context, prompt injection in document/research output, retry after checkpoint resume, and budget exhaustion during parallel work. The supervisor must identify unavailable evidence and avoid inventing candidate accomplishments. Child retries cannot reset the overall budget or repeat approved side effects.

Deliver typed task/result contracts, an observable parent/child execution trace, registry/usage accounting changes, a fixed comparison dataset/configuration, and phases/P5.md. Separate successful orchestration mechanics from measured quality benefit. Negative or inconclusive comparisons must be reported honestly; preserve the single-agent option and explain where specialist mode is justified.

P5 passes the implementation gate when Mo and both specialists execute their scoped workflows and produce traceable structured results. Mark live benefit claims unvalidated until measured. Update architecture guidance and explain why each specialist exists.
```

## P6 — 7–8 October: integrate personalisation, handoff and diagnostics

```text
Implement Capstone P6: connect the completed account/document/agent components into one candidate journey and make its evidence inspectable.

Dependency gate: core P1–P5 flows have usable evidence. Cover A6–A7, bounded A8, B2–B3 integration and AC-17–AC-18. Reuse the existing Inspector and evaluation readers; a full analytics platform, new paid evaluation scheduler and unrestricted raw trace viewer are outside this phase.

Prepare should load the selected opportunity, approved document context, explicit profile preferences and bounded approved memory. Current requests take precedence over saved context. Show which context is being used and allow corrections. Preserve user approval for persistent memory and Practice handoff. Use the existing typed PreparationContext boundary and durable idempotent session creation.

Complete the Overview/Opportunity pages using real data: next action, uploaded-document status, preparation status, sessions and reports. Connect reports and Progress to the same opportunity without mixing unrelated roles or rubrics. Dictation should be available in new eligible fields through the shared component.

Add an owned recent-agent-runs list and working links into Agent Inspector. Show supervisor/specialist contributions, source references, status, failure categories, usage and duration safely. Keep global evaluation artifacts restricted to the appropriate reviewer/admin boundary; private runs stay owner-scoped.

Inspect existing evaluation APIs and wire a minimal read-only report surface for actual supported artifacts. Label absent runs, unavailable metrics and historical evidence correctly. Provide a clear retrieval evidence view based on actual available trace data; do not re-create a broad RAG dashboard for its own sake or present a placeholder as implemented. Never trigger paid evaluations automatically from a page visit.

Verify the complete local path: authenticated user -> opportunity -> reviewed documents -> specialist preparation -> approval -> Practice -> report -> History/Progress -> recent run. Cover reload and second-user isolation. Distinguish actual provider evidence from deterministic fixtures. P6 passes when the candidate no longer has to manually retype context to move between these stages.

Test switching between two opportunities with similar roles, stale HITL decisions from a previous run, removed source documents, and direct run/report URLs. A current request must override conflicting approved memory; data from another opportunity should not leak into the plan without explicit user context. Global evaluation artifacts need an intentional reviewer access policy even if historical routes were unprotected.

Deliver a complete reproducible synthetic scenario, truthful recent-run and stored-evaluation screens, bounded retrieval evidence, and phases/P6.md. At the 8 October checkpoint, show remaining critical-path work against observed progress. Do not silently sacrifice the 14–19 October validation/package window to add more features.
```

## P7 — 9–10 October: spoken interview Practice

```text
Implement Capstone P7 using the shared speech-to-text foundation and existing durable Practice state machine.

Dependency gate: actual P3 transcription works with the chosen authorised provider and typed Practice/handoff is reliable. Cover B6 and required question playback from B7; AC-13–AC-14 and initial AC-23. Spoken feedback is optional and must not delay required spoken questions or safe answer submission. Full duplex conversation is deferred.

Add spoken question playback, record/stop/cancel answer controls, transcript review and correction, and explicit answer submission. Optional spoken feedback may be included after the primary path works. Preserve typing and readable question/feedback text. Prevent playback from being captured as an answer. Reuse viable provider adapters, but expose no provider credentials in the browser.

Treat audio capture/transcription as preparation of a draft. Only explicit submission commits an answer through the existing session manager. Stable operation IDs, concurrency controls and existing leases must prevent duplicate answers/evaluations after retry, refresh or reconnect. Recovery must not silently retain raw audio beyond the disclosed policy; if an unsubmitted draft cannot survive reload, say so visibly and preserve the last committed session state.

Handle permission denial, silence, clipped/oversized recordings, unsupported codec, transcription failure, interrupted network, expired login, stop/cancel and session navigation. Audio files and jobs are owner-scoped and temporary by default. Use explicit consent for retained recordings. The practice rubric evaluates answer content; optional timing/pacing measures do not imply personality or employability.

Verify a spoken question and real recorded-answer transcription with the selected provider where authorised and available. Test that one answer produces one evaluation, Deep Dive does not corrupt the main interview, and a completed session creates a reopenable report. Document supported browsers, sample inputs, actual transcription errors, latency and any external processing. Do not claim full real-time conversation; that remains a later milestone.

Exercise recording while playback is active, duplicate clicks, corrected transcripts, an answer submitted concurrently in another tab, session expiry during transcription, and navigating away with an unsaved draft. Keep captured versus edited transcript distinctions only where needed under the disclosed retention policy. Test boundary cases with deterministic fixtures and the ordinary user path with actual audio.

Deliver the voice interaction state diagram, recording/transcription/submission ownership contract, failure/recovery behavior, real sample evidence, and phases/P7.md. Describe exactly which stages use local or external services and which operations incur measured, estimated or unknown cost.

P7 passes when the real primary UI supports an end-to-end spoken practice session with text fallback and durable submitted progress.
```

## P8 — 11–13 October: app-wide dictation, visual polish and feature freeze

```text
Complete Capstone P8 and establish the 13 October feature freeze. Read the requirement status and close gaps within the agreed release scope.

Dependency gate: P1–P7 core capabilities exist; unresolved blockers must be listed before cosmetic work. Cover complete B5/B9 and AC-11–AC-12/AC-19. Scope additions such as A9/C10 require an explicit selection already recorded in feature_scope.md; do not infer approval from a wish-list mention.

Audit every eligible natural-language input: onboarding/profile, opportunities, document questions/corrections, Prepare composer/follow-ups/clarifications, Practice and Deep Dive, memory edits, feedback comments, and existing searches/notes/reflections. Integrate the shared dictation component wherever missing. Do not invent new note/search features solely to add microphones. Document justified exclusions for secret fields, technical IDs and structured controls.

Verify identical draft behavior: recording indicator, stop/cancel, transcript review/edit, explicit insertion, append/replace, undo, typed fallback and explicit final submit/save. Test field switching, concurrent typing, navigation, logout, expired sessions and late results. Stop all microphone tracks and revoke temporary resources appropriately. Ensure no accidental approval or duplicate submission occurs.

Complete the responsive core UI across Overview, Opportunities, Documents, Prepare, Practice, Progress and Settings. Check empty/loading/error states against real API responses, keyboard paths, focus, labels, contrast, readable tables, clipping/overflow, long content and narrow screens. Keep technical diagnostics in the reviewer view. Capture actual rendered screenshots with synthetic data; label any fixtures separately.

Run meaningful component, contract and browser checks for the changed behavior. Use a coverage inventory for all eligible inputs and representative behavioral tests of the shared control plus important integrations. Do not mistake microphone icon presence for functioning dictation.

Provide a route-by-route coverage table containing field/component, dictation support, actual verification status, accessibility results and exclusion reason where applicable. Exercise long transcripts, narrow viewports, keyboard-only operation and readable evidence tables. Identify the declared supported browser set; screenshots at a mobile size alone do not prove actual mobile microphone support.

Deliver phases/P8.md, a dated freeze candidate identity, acceptance checklist status and a short owner walkthrough. Classify required capabilities as implemented/tested, built/validation outstanding, incomplete, or blocked. Preserve each unresolved issue and its impact; do not manufacture a green freeze by reclassifying a promised core feature as optional.

Prepare a release-candidate checklist linking every CAP requirement to evidence, including failures and missing provider validation. Freeze scope: no new capabilities after this phase, only repairs and validation. If a core promise cannot be delivered, state the exact gap and schedule impact; do not silently defer it or mark it passed.
```

## P9 — 14–15 October: release verification and evaluation

```text
Execute Capstone P9: verify the release candidate and produce reproducible evidence. Inspect current code state and required repository gates first. Use disposable local data and synthetic/public evaluation inputs.

Dependency gate: P8 provides a frozen candidate and complete status table. Cover AC-02, AC-20–AC-23 and the required runtime gates. Record the test command, relevant configuration categories, dataset and exact code state before running. If code changes to fix a defect, identify the new candidate and which previous evidence remains valid.

Run the complete required offline regression suite, frontend lint/typecheck/build/unit checks, relevant browser journeys, OpenAPI contracts, migrations, secret checks and deterministic retrieval/agent gates. Reconfirm actual commands from this checkout. Do not infer passes from old counts. Report skips and inherited failures.

Exercise ownership across records, files, audio, downloads, chunks/retrieval, caches, jobs, streams, feedback, memory and checkpoints using two authenticated users. Test private-document injection, safe URL handling, parser bounds, expired authentication, duplicate/retried actions, provider failures, cancellation, worker/application restart and backup restore. Use a disposable backup/restore destination; do not overwrite existing user data.

Evaluate the same versioned tasks on single-agent and cooperating-agent paths. Compare completion, supported claims, routing/delegation behavior, latency, usage and cost where available. Use the predeclared criteria; do not alter the evaluation to reward the new architecture. Preserve failures and denominators. Report extra Capstone cases separately from inherited retrieval benchmarks.

Measure speech on a defined synthetic/consented sample with reference transcripts: accuracy or word error rate with a documented method, correction burden, time to editable transcript and completed-answer success. Distinguish offline speech execution, mocked integration, and real cloud-provider measurements. Do not run paid/live comparisons without an explicitly approved budget; complete all offline work and report the remaining gap.

Inspect actual supported browsers and the full local journey. Record environment, sample size, data version, code state, pass/fail/blocked result and evidence paths. Classify defects by user impact, not by a target of zero. Fix bounded release-blocking defects within scope, run the relevant regressions, and preserve before/after evidence. Do not expand features.

Use the actual AC checklist rather than test count alone as the release coverage measure. Verify actual speech, files, identity and parent/child agent integration, and label stubbed provider results. Include safe log-content checks, server restart during processing, stale job recovery, and a documented restore to an isolated database. State local concurrency/sample limits instead of implying production scale.

Deliver phases/P9.md, current evaluation report, consolidated defects, acceptance matrix, and traceable evidence index. Distinguish inherited Sprint 4 evidence, current offline results, real local integration and authorised live measurements. Do not calculate or imply a single aggregate 'AI accuracy' from unrelated metrics.

P9 is complete when the evidence matrix is truthful and reviewable. A blocked live check remains blocked; a release gate with a critical failure cannot be declared green.
```

## P10 — 16–17 October: user pilot and prioritised repairs

```text
Execute Capstone P10: prepare and support a small usability pilot, then fix observed issues. Do not contact participants or fabricate participation.

Dependency gate: a usable candidate and P9 defect status. Cover AC-24 and relevant regression gates for repairs. Prepare participant materials in advance within this phase's scope, but actual human observations require people supplied by the owner. Work on internal review and remaining safe repairs while awaiting observations.

Prepare a short participant information/consent note, synthetic CV/JD fixtures, task cards and an observation template. Tasks: sign in; create an opportunity; upload and correct documents; verify a source; dictate a message; obtain a preparation plan; complete spoken Practice; return to its report and Progress. Capture completion, time, dictation corrections, confusing moments and optional usefulness feedback. Private recordings are opt-in.

Use 3–5 participants if the owner supplies them and their feedback. While awaiting real observations, perform an explicitly labelled internal usability review and complete independent accessibility/error-recovery checks. Do not rename internal or simulated runs as user testing.

When observations are available, prioritise blockers and repeated confusion, implement bounded fixes, and run targeted regressions. Keep feature freeze in force. Maintain anonymised findings, sample size, observed limitations, before/after evidence and any unaddressed issues.

Analyse confusion separately from model quality, transcription errors and infrastructure failure. Preserve task completion denominators and distinguish participants who skipped tasks. If the sample is small, describe qualitative findings without claiming statistically established improvement. Ask no participant for unnecessary sensitive information, and do not publish raw recordings or CVs.

Deliver task cards, observation template, actual anonymised findings or explicit missing-participant status, ranked repairs, retest evidence and phases/P10.md. Update the reviewer lessons to explain the most important observed problem and design response.

P10 passes its pilot gate only with actual participant evidence; if participants are unavailable, deliver the prepared materials and internal-review results and mark the external pilot incomplete. Complete all unaffected release repairs and hand off the exact state to P11.
```

## P11 — 18 October: Capstone submission materials

```text
Create the Capstone submission package from the actual code, current evidence and supplied course brief. Keep product functionality frozen. Read the existing presentation/document styles and tooling before authoring; use the available artifact skills and render-based QA where available. Do not claim successful Office visual QA if rendering is unavailable.

Dependency gate: current requirement dispositions, P9 measurements and P10 observations/limits. Cover draft AC-25. Inspect source files and the exact latest code state before revising claims. The historical Sprint 4 decks are references; create a new Capstone package preserving each deck's purpose and truthful evidence framework. No product fix is implicitly authorised by this documentation phase.

Produce:
1. README updates covering goal, problem, how it works, precise local startup, external APIs, current capabilities, privacy and known limits.
2. Capstone requirements/evidence matrix and a clear Sprint 4 inherited foundation versus new Capstone contribution table.
3. Architecture/data-flow explanation for login, private documents, public knowledge, Mo/specialists, speech, HITL and durable Practice.
4. Evaluation and ethics/privacy reports using actual denominators, code/data versions, test results and user observations. Mark paid judge, provider, browser, deployment or pilot checks that did not run.
5. Updated Complete App Walkthrough, Sprint-to-Capstone Review, and Product Journey presentations with distinct purposes. Include reusable Core Requirements and Optional Tasks tables where relevant, Evidence/Validation, Lessons, Limitations, Verdict and Reviewer Demo Path. Each major deliverable must explain why, how, proof and remaining boundary.
6. An explicit 10-minute presentation path or a compact live deck, a speaking script, a five-minute reviewer Q&A, and a reusable checklist. Follow the course's six topics: problem, solution, data, evaluation, challenges and what's next; use SCR or SMART.
7. A demo recording script, synthetic dataset and fallback instructions. Produce an actual recording only if the environment supports it; otherwise leave a precise recording task for the owner. Draft showcase copy but do not publish it or invent a link.

Map the Capstone criteria accurately. Earlier Sprint bonus-task classifications are historical supporting context, not an additional Capstone rule. Do not carry forward old UI-gap claims if the code now fixes them, and do not erase remaining gaps. Treat Sprint 4 CI/golden evidence as historical rather than Capstone certification.

Visually render and inspect every produced deck/document for clipped text, overlap, margins, readability and consistent typography. Check package integrity separately. Create an output manifest with exact filenames, links, QA state and any missing artifact. Deliver files in a new Capstone package folder without overwriting the Sprint 4 originals.

The requirements tables must show omitted/optional/deferred capabilities honestly, including A9/C extensions and unexecuted D validations. Explain which agent, speech, identity and document capabilities are newly implemented versus inherited. Each major deliverable gets Why, How, Evidence and Boundary coverage in the review material. Include the final workflow architecture, data ownership, actual latency/cost evidence where available, biggest failure, and a concrete learning reflection.

Deliver phases/P11.md and a filename-by-filename completeness audit. A missing checklist, unsupported export format, unrendered deck or unrecorded demo must be visible in the handoff. Do not substitute a proposed script for an actual video without labelling it.
```

## P12 — 19 October: final rehearsal and release record

```text
Execute Capstone P12: final local release verification and rehearsal. No new features. Read the completed status/evidence and resolve any mismatch between documentation and current behavior.

Dependency gate: P11 artifacts, P9/P10 evidence and an identified release candidate. Cover final AC-25 and repeat only the runtime checks justified by changed code or unresolved concerns, plus the complete rehearsed journey. Verify credentials/configuration privately by presence/readiness, never by printing secret values.

1. Verify startup from the documented process using an isolated environment and synthetic data. Confirm required dependencies, migrations, knowledge readiness, accounts, private storage, speech configuration and disabled/unavailable integrations. Do not reset existing user data.
2. Check whether code changed after the last full regression. Run relevant regressions for any fixes and the required final gate. Record the exact code state, configuration categories and data versions without secrets.
3. Rehearse the ten-minute story: sign in, CV/JD upload, extraction review, Mo and specialists, cited preparation, approval, spoken Practice, report, logout/login, History/Progress and second-user isolation. Include dictation outside Practice. Review questions for five minutes.
4. Before any paid/live golden, verify a specific run count, spending cap, providers and synthetic/public inputs have been authorised. If missing, complete offline rehearsal and clearly leave live certification pending. If authorised, execute within that limit, record every attempt and failure, and do not silently rerun for a better result. Keep the recorded fallback ready.
5. Verify every submitted file, link and claim. Confirm the optional showcase description matches local delivery; do not publish without instruction. Record known limitations and any course-lead answer about local deployment.
6. Produce docs/capstone/final_readiness.md, a final package manifest, the demo command/path, and a proposed release checkpoint with its exact commit/diff state. Recommend a new Capstone tag only after the owner commits the reviewed state; do not create/move/push tags or merge automatically.

Final outcome must state ready, ready with explicit limitations, or blocked with named release-blocking items. Do not call the release ready if a core acceptance gate failed. Preserve the 20 October review day for demonstrating the reviewed build.

Deliver phases/P12.md, final_readiness.md, exact local startup/demo instructions, actual golden attempt ledger, artifact manifest and a copy-ready review-day checklist. Clearly distinguish a code freeze, a git commit/tag, historical remote CI and new local checks. A tag is a reference, not test evidence. Leave optional/deferred items visible in the final scope matrix.
```

## Independent milestone review — after any phase

```text
Review the just-completed Ask4Mo Capstone phase independently of the implementation summary. Read the diff, requirements, actual code, applicable instructions and evidence. This is a review request: do not edit product code.

Check requirement coverage, regression risk, ownership and input boundaries, API/UI integration, real versus mocked evidence, persistence/retry behavior, and missing user-facing states. For speech, check the actual field inventory and no-auto-submit behavior. For agents, verify substantive scoped execution and budgets. For documents/accounts, inspect indirect data-access paths as well as visible screens.

Perform safe non-mutating or disposable-data diagnostics where useful. Return concrete findings with file/line references, reproduction, user impact and severity rationale. Clearly distinguish confirmed defects, likely risks and unverified areas. If no findings are identified, say what was inspected and what remains untested; do not claim absolute correctness.

Recommend whether the phase acceptance gate is satisfied. Name the minimum repairs needed before the next dependent phase.
```

## Repair a failed gate

```text
Fix the confirmed failures from the latest Capstone phase review. Read the cited findings and reproduce each issue first using safe synthetic/disposable data. Implement the smallest coherent fix that preserves the architecture, identity, HITL, data and session contracts.

Do not broaden feature scope or weaken tests. Add a regression check for the failure mode, inspect the real interface if affected, and run the necessary existing checks. Update the phase report and requirement statuses with actual results. Keep blockers explicit if the cause requires unavailable provider configuration or an unapproved paid run. Do not commit, push, merge or deploy.
```

## End-of-session handoff

```text
Create a precise continuation record for this Capstone session. Update docs/capstone/status.md and the active phase report without exposing secrets or private candidate content.

Record: repository root, branch/worktree and code state; current phase; completed acceptance checks; files changed; commands actually run and outcomes; whether evidence was offline, mocked or live; services started and whether they remain running; configuration variable NAMES still needed; outstanding defects; uncommitted/unrelated changes to preserve; and the first exact task for the next session.

Write a copy-ready next-session prompt that carries forward this state and the remaining phase objective. Do not mark unfinished work complete, and do not make a commit or run extra paid checks merely to finish the handoff.
```

## Optional reviewed local git checkpoint

Use this only after you have reviewed the phase and want a local commit. It does not authorise a push, merge or tag.

```text
Create a local git checkpoint for the completed, reviewed Capstone phase. Inspect the exact diff and working tree first. Stage only the intended phase code, tests and sanitised documentation; exclude unrelated work, secrets, private files, databases, recordings, caches and raw generated artifacts. Follow the applicable repository commit-message rules.

Confirm that the recorded checks apply to the proposed commit contents, then commit on the current Capstone branch. Do not bypass signing/hooks, push, open a PR, merge, deploy, or create/move tags. Report the commit SHA, scope, verification evidence, and anything deliberately left uncommitted. If the phase still has a failed critical gate, report that instead of labelling the checkpoint release-ready.
```
