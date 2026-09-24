# Ask4Mo: complete Sprint 4 to Capstone project plan — v2

> Scope superseded on 23 September: use [expanded v3 plan](Ask4Mo_Capstone_Delivery_v3/00_Expanded_Project_Plan.md) and its prompts/checklist. C1–C9, C11–C12, K1–K4 and bounded A9 are now included. English/German speech and open verified-email registration are confirmed. Retain this document for unchanged foundations, not its old deferrals or schedule assumptions.

Planning basis: the inspected Sprint 4 repository snapshot and the 22 September 2026 product audit. User-confirmed start: 24 September 2026; deadline: 20 October 2026. User preference: run locally. This is a proposed roadmap, not evidence that the new capabilities exist. Available hours, hardware capacity, and paid API budget remain unconfirmed. The schedule is an ambitious target with a protected verification period, not a guaranteed estimate.

Execution companions: [start here](Ask4Mo_Capstone_Delivery/04_Start_Here.md), [delivery runbook](Ask4Mo_Capstone_Delivery/00_Delivery_Runbook.md), [copy-ready Claude prompts](Ask4Mo_Capstone_Delivery/01_Claude_Prompt_Pack.md), [feature decisions](Ask4Mo_Capstone_Delivery/02_Feature_Scope_and_Decisions.md), and [release acceptance checklist](Ask4Mo_Capstone_Delivery/03_Release_Acceptance_Checklist.md). The runbook provides the detailed daily schedule; the feature matrix controls inclusion, and the checklist controls completion. All are planning artifacts; product implementation remains to be verified and performed in the actual development checkout.

## What changed in version 2

The missing-feature inventory is now mapped to explicit inclusion decisions and P0–P12 prompts. Existing backend/legacy capabilities are separated from new work and live validation. The working release retains A1–A7 and B1–B9; A8 is a bounded retrieval-evidence view, A9 export/history deletion remains optional, and C extensions remain deferred unless specifically selected. This is the recommended continuation of the user's established priorities, not approval of every item in the inventory.

Every phase now carries prerequisite evidence, implementation boundaries, acceptance IDs, failure cases and a completion report. No requirement is marked delivered merely because a prompt, schema, UI shell, mock or historical release record exists. Deep Dive answer evaluation is an existing foundation to preserve, not missing functionality to rebuild.

## Product objective

Evolve Ask4Mo into a personal career preparation workspace where each candidate can sign in, manage several target opportunities, upload their CV and job descriptions, work with Mo and specialised agents, practise aloud, inspect source evidence, and return to durable reports and meaningful progress. Speech-to-text is an application-wide input capability: candidates can dictate into all eligible natural-language fields throughout the primary Next.js experience.

Capstone positioning: primary Case 2, AI agent for task automation, supported by Case 1, grounded knowledge retrieval. Voice is an interaction capability. The project should demonstrate measurable benefit from agent cooperation through comparison with Sprint 4.

## Demonstration journey

1. Sign in and choose preparation goals and preferences.
2. Create an opportunity for a target role and company.
3. Upload a CV and job description, then review extracted facts and corrections.
4. Mo coordinates candidate analysis and role/company research.
5. Inspect the gap analysis, supporting evidence, and preparation plan.
6. Approve any durable memory and the transition into Practice.
7. Hear a question, record an answer, review the transcript, and submit it.
8. Receive evidence-based feedback, complete a follow-up, and generate a report.
9. Return later to the same opportunity, session, report, and progress history.
10. Demonstrate that another signed-in account cannot access the first account's data.

During the same demonstration, dictate into at least one field outside Practice, verify a citation against its actual source, and show safe behavior when a required source or service is unavailable. The reviewer should see both the useful result and the enforced boundaries.

## Release boundary

The October 20 Capstone release targets real local accounts, explicit personalisation, a redesigned core interface, private PDF/DOCX/TXT uploads, source-backed document answers, application-wide speech-to-text, recorded spoken answers and spoken questions, a supervisor with two substantive specialist agents, usable History and Progress, run diagnostics, evaluation, and a reproducible local demonstration.

Full duplex real-time voice, OCR for scanned documents, multilingual voice, four fully developed specialists, organisation/team accounts, advanced evaluation dashboards, public deployment, and an evidence-bank editor are later milestones. They can enter the release only if core acceptance gates pass before the feature freeze. Camera-based assessment, automatic job applications, recruiter rankings, and billing are outside the first Capstone release.

Optional additions are not scheduled automatically. Report export/history deletion, a guided tour, spoken feedback, and paid integration comparisons require an explicit scope or execution decision appropriate to the feature. Core spoken questions, local recovery, document deletion, and temporary-audio cleanup remain included. Detailed Germany compensation, credentials, emerging roles and extra Adzuna tools remain a visible knowledge backlog; maintain truthful coverage limitations throughout the release.

## Architecture decisions

- Keep Next.js as the primary interface, FastAPI as the application API, LangGraph for orchestration, and the existing deterministic Practice session manager.
- Use a maintained authentication library or locally running identity provider with verified sessions or tokens and established password hashing. Prioritise local account creation, login, logout, and session expiry. FastAPI must independently enforce verified identity; browser-supplied identity headers must not determine ownership. Public email verification and email-based recovery are later service-dependent work; document the local account recovery procedure.
- Use PostgreSQL in a local container for application state and durable checkpoints if the compatibility spike succeeds. Verify migrations and backup/restore early. Do not let a new database migration consume the feature-freeze window; any fallback must be documented with its concurrency limits.
- Use a private local storage directory or container volume for original documents and optional recordings, outside the frontend public directory. Serve downloads through an authenticated API with ownership checks. A storage abstraction can support object storage later.
- Introduce a background worker for parsing, indexing, transcription, and long research tasks, with explicit queued/running/ready/failed/cancelled states. Select the queue technology after assessing deployment constraints.
- Retain the existing public knowledge retrieval stack initially. Keep user documents logically separate, enforce ownership in the retrieval service before results enter model context, and scope caches and indexes correctly. Do not allow an agent to select arbitrary owners or collections.
- Add provider interfaces for speech-to-text and text-to-speech so model selection can be evaluated independently from session and scoring logic.
- Implement one reusable dictation input component and recording controller connected to an authenticated transcription service. Use it across forms, chat, searches, notes, and Practice. Bind each request to the initiating user, field, and draft version so a late result cannot overwrite another field or another user's content. Stop recording on navigation, logout, cancellation, or component disposal.
- Use one Python application plus a worker initially. Specialist agents can be subgraphs in the same application; separate microservices are not a prerequisite. Bind services to localhost by default. Local accounts demonstrate logical multi-user isolation; remote access from other devices requires separate networking and transport configuration.

Decision timing: P0 chooses concrete compatible auth, storage, worker and speech approaches from actual code/hardware evidence. P1 proves identity and persistence. P3 proves a shared real transcription path. P4 proves private extraction/retrieval. P5 proves specialist execution. Defer no foundational provider choice to the final voice phase. Use an explicitly documented change decision if a feasibility result forces a different approach.

## Accounts and personalisation

Start with individual candidate accounts; keep administrative access minimal and local. Implement local registration or explicitly provisioned accounts, sign-in, logout, session expiry, a documented recovery procedure, and ownership checks on every protected API and storage operation. Test both direct ID access and indirect paths such as search, events, files, exports, and cached results. Use two separate browser profiles to demonstrate independent users.

Personalisation includes target role, seniority, industry, preferred geography, interview date, goals, preferred coaching style, accessibility settings, and approved preparation memory. Separate explicit profile fields, extracted document claims awaiting review, approved memory, and performance evidence. Document upload does not automatically authorise persistent memory or public knowledge-base inclusion.

Add multiple opportunity workspaces per candidate. Documents, preparation plans, sessions, and reports should retain their opportunity context. Existing anonymous demo records must not be automatically assigned to an arbitrary new account; use a documented migration or retain them as isolated demo data.

## Document workflow

Initial formats: text-based PDF, DOCX, and TXT. Support CVs, job descriptions, portfolio summaries, and company/interview briefs. Validate format and content, bound size and page count, quarantine and scan uploads, use constrained parsers, and report encrypted, corrupt, scanned, or unsupported documents clearly.

The ingestion path is upload, validation, parsing, structured extraction, candidate review, indexing, then retrieval. Preserve document version and page/section provenance. Show processing status, safe retry, replacement, and deletion controls. Treat document content as untrusted data, never as instructions to an agent.

Deletion must revoke application access immediately and remove source files, derived chunks, embeddings, and affected caches through a tracked cleanup process. Document the separate lifecycle for already generated reports, checkpoints, and backups so deletion promises match implementation.

## Application-wide speech-to-text

Confirmed addition: dictation is part of the October 20 core scope, not limited to Interview Practice. Typing remains available in every supported field. English is the initial release language; additional languages depend on provider evaluation and available time.

| Surface | Dictation coverage |
|---|---|
| Overview and onboarding | Preparation goals, professional background, and initial requests |
| Profile and personalisation | Role, industry, location, coaching preferences, and other natural-language profile fields |
| Opportunities | Role/company text, pasted job-description fields, interview context, and notes |
| Documents | Document questions, editable extracted text, corrections, and annotations where present |
| Prepare | Initial messages, follow-ups, clarification responses, and plan revisions |
| Practice and Deep Dive | Interview answers, follow-up answers, and reflections |
| Progress, History, and reports | Search queries, report questions, reflections, and notes where present |
| Memory and feedback | Proposed memory edits, feedback comments, and other editable free-text settings |
| Reviewer tools | Natural-language search or annotation fields where present; technical IDs retain their normal controls |

This coverage applies to actual editable fields; it does not create a new notes or annotation feature on every page. New natural-language inputs should reuse the same component by default. Passwords, authentication codes, secrets, file pickers, technical identifiers, and structured selectors such as dates are not dictation targets. Navigation, submission, deletion, and approval remain explicit controls; voice-command automation is a separate future feature.

Interaction: select the field's microphone, speak, stop, inspect the transcript, edit if necessary, then insert it into the draft. Preserve existing typed text and provide explicit append/replace behavior and undo. Transcription must never automatically send a chat message, submit an interview answer, approve memory, or change a saved setting. Dictated document corrections remain user amendments and must not be presented as verbatim source text.

Show idle, recording, transcribing, ready, and failed states with a recording indicator, timer, stop/cancel controls, accessible names, and keyboard support. Allow one active microphone capture at a time. Support safe retry after silence, denied permission, unsupported capture, interrupted connectivity, expired authentication, or provider failure. Prevent simultaneous speech playback from contaminating microphone input.

Audio is temporary by default. Bound clip duration and size; remove temporary audio after completion, cancellation, or expiry, and document any external provider retention. Storing audio requires a separate user choice. Saving a dictated field follows that field's existing save behavior and does not implicitly create approved preparation memory. Transcripts follow the same input validation and user-isolation rules as typed text.

## Voice Practice and spoken output

First milestone: spoken question, push-to-talk answer, visible recording controls, transcription, editable transcript, submission, feedback, and optional spoken feedback. Preserve the original recognised transcript separately from candidate corrections when needed to assess transcription quality; do not include private content in operational logs. Recording retention should be opt-in, with clear microphone and storage controls.

The existing Practice session manager remains authoritative for submitted answers and state transitions. Give each recording/answer a stable identifier so retries cannot submit twice. Handle microphone denial, silence, transcription failure, network interruption, and switching back to typing.

Second milestone: streaming audio, turn detection, interruption, reconnect, cancellation, and real-time transcripts. Define the handoff between uncommitted audio and committed answers before implementing it. Maintain a text fallback. Evaluate browser compatibility and response latency.

Assess answer content separately from delivery measurements. Duration and pacing can be optional coaching signals. Do not infer employability, personality, honesty, emotion, or intelligence from voice. Test transcription across varied accents and quiet/noisy recordings with consented or synthetic samples.

## Cooperating agents

| Component | Responsibility | Inputs and outputs |
|---|---|---|
| Mo, supervisor | Own conversation, choose specialists, reconcile results, request approvals | Receives user goal and authorised context; returns one coherent response |
| Research specialist | Gather role, company, and market evidence using governed tools | Returns claims with source identifiers, dates, and explicit gaps |
| Candidate specialist | Compare user-approved CV facts and job requirements; identify supportable examples | Returns evidence-backed strengths, gaps, and clarification questions |
| Preparation specialist, expansion | Build a feasible plan from research and candidate analysis | Returns prioritised actions, rationale, and time estimates |
| Evaluation specialist, expansion | Apply a fixed rubric to an answer and generate actionable feedback | Returns rubric-linked observations; does not control session transitions |

Ship the supervisor plus Research and Candidate specialists first. Each specialist must have a distinct task, bounded tool access, and its own meaningful decision loop. Extraction, scoring arithmetic, validation, storage, and permission checks remain ordinary deterministic services where appropriate.

Research and candidate analysis may run concurrently after their required inputs are available. Planning depends on both results. Share structured evidence packets rather than unrestricted transcripts. Scope every run to the verified user and opportunity. Limit iterations, delegation depth, time, and total cost; provide cancellation and explicit partial-result behavior. An evidence-checking agent may help review outputs, but access control and citation validity must remain enforced in code.

Keep a single-agent execution option for baseline comparison and recovery. Use matched tasks, the same data snapshot, and comparable model settings to assess whether specialists improve grounded coverage and task completion at acceptable latency and cost.

## Frontend proposal

Primary navigation: Overview, Opportunities, Documents, Prepare, Practice, and Progress. Completed reports and resumable sessions belong within Practice and opportunity detail; existing History URLs can redirect or remain compatible. Settings contains profile, memory, account, accessibility, and privacy controls. Technical diagnostics are available through a dedicated reviewer/developer view.

The overview should answer three questions: what am I preparing for, what should I do next, and what has improved? Opportunity detail combines role context, approved documents, evidence, plan, practice, and reports. Prepare uses a focused conversation with an evidence panel and editable context. Practice gives priority to the current question, audio controls, transcript, and feedback.

Define shared typography, spacing, colours, components, loading states, meaningful empty states, and error recovery before redesigning every screen. Include the reusable microphone/dictation control in the input design system and review coverage across every form and composer. Validate desktop and mobile layouts, keyboard navigation, screen-reader labels, focus handling, and readable contrast. Use motion to communicate state changes without obstructing work.

## Phased delivery and exit gates

Confirmed planning window: 24 September to 20 October 2026, approximately four weeks. Availability is unknown. Prioritise one complete user journey and the bounded versions of all five requested additions. Freeze new features on 13 October, leave 14–17 October for verification and repairs, and preserve 18–19 October for the final rehearsal and submission package.

| Phase | Approximate window | Main deliverables | Exit gate |
|---|---|---|---|
| 0. Baseline and feasibility | 24 Sep | Verify actual checkout/release, define acceptance criteria, assess laptop and local setup, test speech feasibility, inventory dictation fields, sketch screens | Auth, ingestion, agent, and voice approaches are feasible before wider implementation |
| 1. Accounts and continuity | 25–29 Sep | Verified local accounts, basic personalisation, local persistence, History detail/resume, existing Progress metrics, catalogue links, authenticated dictation foundation | Two accounts retain private data across reloads; reports can be reopened; shared transcription path works |
| 2. Documents and redesigned workspace | 30 Sep–4 Oct | Private upload pipeline, extraction review, document citations, opportunity context, shared interface components, dictation in profile/documents/Prepare | CV plus job description produces a verifiable role-specific preparation result; eligible core fields accept dictated drafts |
| 3. Cooperating agents | 5–8 Oct | Mo plus Research and Candidate specialists, structured results, bounded delegation, failure handling, recent-run trace | Two specialists cooperate on one complete preparation workflow and baseline comparison begins |
| 4. Voice and feature completion | 9–13 Oct | Spoken questions, recorded answers, transcript correction, durable submission, full eligible-field dictation coverage, text fallback, integrated responsive core journey | End-to-end spoken practice and application-wide dictation work; new feature work freezes on 13 Oct |
| 5. Verification and pilot | 14–17 Oct | Small structured user pilot, ownership and injection tests, persistence/recovery, retrieval and agent evaluations, accessibility fixes | Critical defects resolved; measured results and remaining limits recorded |
| 6. Rehearsal and submission | 18–19 Oct | Clean local startup test, final golden, README, ethics/evaluation report, ten-minute slides/script/Q&A, recorded demo fallback | Package runs reproducibly and every claim has supporting evidence |
| Review deadline | 20 Oct | Present the frozen local release | No new features introduced on review day |

Design begins in Phase 0 and is applied throughout. Security, privacy, observability, and automated testing are part of each phase. Maintain a repeatable local start process from the first week. If critical phases slip, simplify formats, screen breadth, specialist tools, and optional analytics before sacrificing final verification. Do not represent an unfinished feature as delivered.

Use the runbook's finer P0–P12 schedule for daily execution. The critical dependency chain is verified accounts -> private documents -> scoped cooperating agents -> integrated preparation/handoff. Shared dictation begins before document UI work and is reused in Practice. Requirements, ethics, source evidence, screenshots and reviewer explanations are updated after each phase, not deferred until the presentation day.

Capacity checkpoint: at P0, record actual available hours and identify time-critical integrations. At 4 October, confirm accounts/documents/shared dictation are genuinely usable. At 8 October, compare remaining scope against measured progress. If a core promise cannot fit, surface the choice between reducing optional work and changing scope or timing; never consume the verification window silently. The owner has not provided enough availability information to guarantee this schedule.

## Evaluation and release criteria

Use AC-01 through AC-25 in the release checklist. P0 establishes proposed environment/performance targets; P3 tests real speech feasibility; P5 defines the comparison dataset and promotion criteria before evaluating cooperating-agent benefits. Required runtime capabilities need actual local integration evidence. Mocks remain valuable test evidence but do not complete a live-capability gate.

- Product: sign-in through document-based preparation, spoken Practice, report, logout/login, and history/progress retrieval works as a single tested journey.
- Ownership: no cross-user access in the defined negative-test matrix, including document retrieval, audio, background jobs, downloads, streams, and caches. Passing these tests is evidence for the tested cases, not proof of absolute security.
- Retrieval: preserve the historical safety gates on their versioned test set and separately evaluate expanded data. Do not compare a changed test set as if it were the same benchmark.
- Agents: compare single-agent and cooperating-agent task completion, supported claims, tool/delegation correctness, latency, and cost. Set promotion thresholds after measuring the baseline, before running the final comparison.
- Voice: measure transcript accuracy on a defined sample, correction burden, end-to-end answer success, and median/p95 latency. Publish test conditions and sample limits.
- Dictation coverage: maintain an inventory of eligible natural-language inputs and documented exclusions. Every eligible input supports record, review, edit, insert, and typed fallback before feature freeze. Test representative forms, chat, document correction, memory edit, feedback, search, and Practice flows plus a coverage check for the full inventory.
- Dictation reliability: verify no auto-submission, preserved typed drafts, explicit replacement and undo, safe retries, rejection of stale results after navigation/logout/field changes, microphone release, and user ownership of transcription jobs. Include permission denial, silence, oversized clips, provider failure, and authentication expiry. Exercise the declared supported desktop/mobile browsers; report unsupported combinations honestly.
- User experience: conduct a proposed three-to-five-person exploratory pilot with fixed tasks, completion observations, and a usefulness questionnaire. Obtain permission for any data retained; report the sample as qualitative pilot evidence.
- Progress: compare answers using a versioned rubric and comparable difficulty. Display sample count and session context; do not market practice scores as hiring predictions.
- Operations: test concurrent users, provider failure, worker restart, database migration, backup restore, and bounded spend. Choose the concurrency target after defining the pilot audience.

The historical Sprint 4 metrics remain a baseline. Capstone counts and findings must be measured afresh. No prior golden run certifies new authentication, uploads, agents, or voice behavior.

## Cost and scope controls

Local hosting needs no cloud hosting subscription if the existing computer has sufficient resources. Existing cloud LLM calls, embeddings, transcription, or speech synthesis may still cost money and may send data to external providers. Local operation therefore does not automatically mean offline or private to the laptop. Track these separately and surface external processing clearly.

The first feasibility check should compare locally available speech options with a cloud speech option using synthetic audio. Choose based on laptop capacity, accuracy, latency, and an explicit API spending limit. Do not introduce a full local LLM migration merely to enable voice. Measure cost per document, preparation workflow, and practice session; use fixed evaluation batches and per-run budgets.

If time is constrained, retain all requested pillars through bounded implementations: private text PDFs/DOCX/TXT, shared application-wide speech-to-text, recorded Practice with text-to-speech, supervisor plus two specialists, individual accounts, and the complete candidate journey. Defer full duplex streaming, OCR, team tenancy, and additional specialists. This keeps each core promise demonstrable.

## Submission package

- README explaining the problem, intended user, current capabilities, reproducible local setup, external API requirements, and demonstration procedure.
- Requirements matrix with Requirement/Task, Status, How/Evidence, and historical versus Capstone provenance.
- Architecture and data-flow diagrams covering accounts, documents, agents, speech, and persistence.
- Evaluation report, versioned datasets, experiment results, pilot findings, and cost/latency evidence.
- Privacy and ethical assessment covering candidate documents, voice, data retention, bias, and practice-score limits.
- Ten-minute presentation with five-minute Q&A, speaking script, live demo, and recorded fallback.
- Optional showcase entry and README link when ready, using an accurate local-demo description, architecture, screenshots, and a recorded demo where accepted. A public live URL is not promised.

The three presentation purposes remain distinct: Complete App Walkthrough demonstrates actual screens; Sprint-to-Capstone Review explains each deliverable's why/how/evidence/boundary and inherited versus new work; Product Journey follows a candidate from sign-in to returning progress. Select a ten-minute live route with five-minute Q&A from these materials, or produce a compact live deck. Preserve the standard requirements/evidence tables and retain honest limitations. Match the actual Capstone criteria; the earlier Sprint optional-task minimum is not automatically a new Capstone rule.

## Owner and Claude responsibilities

Claude implements the selected phase, makes routine reversible choices, verifies behavior, records evidence, and prepares the next handoff. The owner supplies the active checkout, configures secrets privately where needed, decides any paid-run budget or optional scope change, performs the short manual acceptance checks, and arranges real pilot participants. Missing external input blocks only dependent work; independent preparation, offline tests and documentation continue. Commit/push/merge/publication remain separately scoped actions, as specified in the prompt pack.

For every phase, explain in plain language: the candidate problem solved, why the design was chosen, how it connects to existing components, which edge cases were checked, what still does not work, and what the learner should be able to explain during review.

## Reference guidance

- LangChain supervisor/subagent architecture: https://docs.langchain.com/oss/python/langchain/multi-agent/subagents
- Next.js authentication guidance: https://nextjs.org/docs/app/guides/authentication
- OWASP upload controls: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- OWASP authorisation guidance: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html

The Capstone brief supplied by the user is the course-scope authority. Its objective mentions deployment; it does not clearly state whether a locally runnable package alone satisfies that expectation. Confirm that detail with the course lead before booking review, while continuing the local build. Any public deployment would be a separate scope decision. Reuse of Sprint 4 and new Capstone contributions should be disclosed explicitly.
