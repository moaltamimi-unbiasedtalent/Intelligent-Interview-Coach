# Ask4Mo Capstone v3: expanded delivery plan

Scope revision: 23 September 2026. User-requested review deadline: 20 October 2026. Proposed start: 24 September. This document controls scope where earlier v2 files or the 401-commit addendum disagree.

## Decision and limits

The owner has now selected **C1–C9, C11–C12 and K1–K4** for the project plan. They are no longer an unselected/deferred backlog. **A9 is included in a bounded form** because private accounts, documents and shared workspaces need clear report portability and deletion controls. C10 already exists and will be maintained.

This is approval to plan the enlarged product. It is not evidence of implementation and does not authorize spending, account creation, provider activation, sending invitations, publication or deployment. Local development remains the default. Public hosting is now an included delivery workstream, superseding the previous local-only product boundary. **Owner-confirmed choices: English and German speech; open registration for anyone with a verified email.**

**The full expanded scope is the requested target, but its completion by 20 October is not yet a credible committed schedule.** Available working hours, hardware, provider budget, hosting access and data availability are unresolved. Do not quietly move selected features back to “deferred” to manufacture a ready verdict. At the first feasibility gate, present the measured work remaining and ask the owner to choose extra capacity, a changed deadline, or explicit release staging if necessary.

## Baseline to preserve

Last inspected code: `4f273dd`, 401 commits. Refresh the actual checkout in P0. The historical Sprint 4 tag remains `sprint4-submission-ready` at `1b084cb`.

Existing foundations include the bounded preparation agent, six career tools and two HITL actions, governed retrieval, approved memory, durable Practice, Deep Dive answer evaluation, feedback, model profiles and Agent Inspector. The later merges add History detail, basic practice Progress, safe source links, stored-run Evaluation UI, Knowledge/RAG overview, a research capability toggle, guided onboarding and Help.

Preserve these features. Improve actual gaps rather than rebuilding from the old missing-feature list. Evaluation artifacts and knowledge provisioning still require truthful setup and provenance. Historic golden evidence is not a validation of new code.

## Product outcome

An authenticated career-preparation workspace with personal opportunities, private and explicitly shared documents, grounded research, a reusable evidence/story bank, speech input throughout eligible fields, recorded and real-time Practice, multilingual speech, specialist cooperation, reports, progress and a safely hosted reviewer/pilot environment.

The primary architecture remains Next.js + FastAPI, application services, bounded LangGraph orchestration and deterministic Practice state transitions. Specialist agents must not own authentication, permissions, migrations, billing or unreviewed self-modification. Streamlit remains legacy/development only.

## Included original scope

| ID | Requirement/Task | Status in plan | How/Evidence |
|---|---|---|---|
| A1, A3, A4 | History, basic Progress, Sources | Preserve and integrate | Regression tests under verified accounts and explicit sharing rules |
| A2 | Active-session discovery/resume | Included | Owned unfinished sessions discoverable and resumable after reload |
| A5 | Knowledge readiness | Included | Distinguish source catalogue, generated snapshots and actual usable stores |
| A6 | Recent agent runs | Included | Owned run list and safe supervisor/specialist navigation |
| A7, A8 | Evaluation and retrieval evidence | Included, bounded | Extend existing readers, label exact artifacts and inspect selected-run evidence |
| A9 | Report export and completed-history deletion | Included, bounded | Authenticated Markdown/JSON export first, explicit deletion confirmation and lifecycle record; PDF is not a prerequisite |
| B1–B3 | Login, profile, opportunities | Included | Verified sessions and correctly scoped durable context |
| B4 | Private document library | Included | Text PDF/DOCX/TXT plus the selected OCR extension |
| B5 | App-wide dictation | Included | Every eligible natural-language input, editable transcript, no automatic submit/approval |
| B6–B7 | Recorded answers and spoken questions | Included | Recorded mode remains a fallback for realtime mode; spoken feedback remains optional |
| B8 | Cooperating agents | Included and expanded | Mo plus Research, Candidate, Preparation and Evaluation specialists, with bounded delegation |
| B9 | Frontend redesign/integration | Included | Responsive, accessible screens with truthful processing/error states |

## Newly included feature scope

| ID | Requirement/Task | Minimum usable scope | Dependency / acceptance |
|---|---|---|---|
| C1 | Real-time voice and interruption | Streaming conversation, visible transcript, interrupt/stop, reconnect and recorded/text fallback | Stable recorded Practice first; interrupted or replayed audio cannot commit duplicate answers |
| C2 | OCR | Scanned PDFs and common image uploads through a bounded OCR worker, reviewable extraction and page provenance | Secure file pipeline first; low-confidence or unreadable text requires correction, not fabricated content |
| C3 | Multilingual dictation and speech | English and German selection, real STT/TTS coverage and per-language quality samples | Preserve original-language text and label translation; full application-copy translation is a separate decision |
| C4 | Additional specialists | Preparation specialist builds plans; Evaluation specialist applies a fixed rubric and produces structured feedback | Add to Mo/Research/Candidate architecture; deterministic Practice still controls session transitions |
| C5 | Organisation/team workspaces | Team creation, membership, owner/admin/member roles, invitations and explicit resource sharing | Verified identity first; personal CVs, stories and reports remain private by default, including from team administrators |
| C6 | Social and email authentication | One selected social identity provider, email verification and email-based recovery, while preserving local login | Provider and mail-service configuration; no unverified account linking; recovery tokens expire and are single-use |
| C7 | Evidence/story bank | Candidate-owned examples linked to supporting documents, editable STAR-style drafts and use in preparation | Reviewed extraction and provenance; model suggestions remain drafts, never invented career achievements |
| C8 | Per-operation model selection | Server allowlist/policy for supported operations such as analysis, questions, evaluation and reports | Record actual model/policy per result; fixed policy within comparable scored sessions, cost limits and visible fallback |
| C9 | Bulk retention cleanup | Dry-run plan, bounded batches, explicit cutoff/scope, exclusions, idempotent cleanup and summary | Lifecycle inventory first; preserve active sessions, pending approvals and applicable hold exclusions; no unreviewed broad deletion |
| C10 | Guided onboarding | Existing tour and Help updated for the expanded journey | Regression-test guidance and accessibility; do not rebuild it as a new subsystem |
| C11 | Next.js Prompt Lab | Admin/developer-only versioned experiments on synthetic or approved data, explicit model/budget and side-by-side results | Strict separation from candidate data and live prompts; publishing a chosen version requires deliberate review |
| C12 | Public hosting | Reproducible HTTPS deployment with open verified-email registration, private storage, backups, health checks, usage limits and rollback | Private staging first, then authorized public release; verification never makes personal data public |

### Team and sharing rules

Personal and team scopes must be explicit in the data model. Membership never grants blanket access to a user's personal records. Share only selected resources with a selected workspace. Test removal of members, revocation of a share, invitation expiry, direct file access, search/vector retrieval, caches and running jobs. Re-check permission before delivering asynchronous results. Define who can export or delete a shared report without deleting its owner's personal copy unintentionally.

### Speech boundaries

Real-time mode may auto-detect a spoken turn, but detection must not silently approve memory, send external actions or change a scored answer without the declared commit interaction. Define answer-commit semantics before implementation. Handle interruption during playback, transcription and evaluation distinctly. Use stable turn IDs and discard stale responses after cancellation, navigation or logout.

The owner selected **English and German**. Include both in dictation, recorded Practice, real-time speech and spoken questions. Preserve original-language transcripts and use explicit language selection or reviewable detection. Test transcription accuracy/correction burden, pronunciation, language switching and unsupported-language behaviour with actual samples. Do not label the release “multilingual” based only on a provider's advertised capabilities. Whole-application translation and additional languages are not implied. Do not infer intelligence, personality, emotion or hiring suitability from voice.

### Open-registration launch gate

Anyone may register, but verification must precede access to protected candidate workflows and costly processing. Verification/recovery endpoints need anti-enumeration responses, expiring single-use tokens and rate limits. Configure trusted social identity only when verified-email claims are valid, or perform the application's own verification. Never link accounts just because an untrusted email string matches.

Before public release, set per-account and aggregate cost/concurrency ceilings, bounded uploads/OCR/voice/agent runs, signup and resend limits, and an operator pause switch for costly features. Do not rely on email verification alone to prevent abuse. Exercise safe handling of repeated registrations and provider failures without weakening privacy. Prepare accurate privacy/retention notices, account deletion and support/recovery procedures. Confirm hosting region, email delivery and provider data handling before uploading real user content. Public launch requires explicit owner authorization after staging evidence passes.

### Model and experiment boundaries

Use a small central policy registry, not free-form provider names from the browser. Track the actual model, rubric, prompt and dataset versions used. If a mid-session fallback changes scoring behaviour, flag it and exclude it from unqualified comparisons. Prompt Lab cannot alter production prompts automatically. Retain a single-agent/single-profile baseline for measured comparison with the expanded system.

## Included knowledge expansion

| ID | Requirement/Task | First bounded deliverable | Evidence gate |
|---|---|---|---|
| K1 | Germany occupation-level compensation | A selected occupation set with authoritative, usable compensation records | Source/license review, occupation mapping, geography, reference period, currency and pay-period labels; missing records remain insufficient evidence |
| K2 | Credentials and regulated professions | A declared jurisdiction/profession matrix with official requirements and source links | Separate legal requirements from employer preferences, preserve effective dates and avoid broad eligibility assurances |
| K3 | Emerging roles and industry context | Versioned aliases and a selected set of emerging role/industry records | Distinguish synonyms from new occupations; test ambiguous-role abstention and false-positive mappings |
| K4 | Additional Adzuna capabilities | Capability inventory and selected provider-supported operations exposed as bounded tools | Verify actual API entitlement, terms, quotas and coverage; approval before paid/live calls; no invented endpoints |

All four areas are included. Exact datasets, professions, occupations and additional provider operations are decisions for E0/E6, not permission to ingest everything. Publicly accessible data is not automatically licensed for storage or redistribution. Preserve source lineage, review date, schema/version and rollback. Compare a new extension suite separately from the frozen historical suite so a changed denominator cannot masquerade as improvement.

## Integrated delivery order

Keep P0–P12 from the existing delivery pack, with the 401-commit corrections and this v3 scope taking precedence. The extension prompts E0–E8 slot into those phases rather than running after submission.

| Sequence | Existing phase | Added work | Dependency gate |
|---|---|---|---|
| 1 | P0 + E0 | Full inventory, capacity estimate, language/provider/data/hosting decisions and risk spikes | Feasibility report before claiming the October scope fits |
| 2 | P1 + E1 | Accounts, social/email auth and team ownership model | Isolation and recovery tests before private/shared content |
| 3 | P2 | Preserve delivered surfaces, complete active resume and readiness | Correct identity throughout the return journey |
| 4 | P3 | Shared interface and actual dictation path | Real transcription and draft-race handling |
| 5 | P4 + E2 + E3 | Private documents, OCR, story bank, report export/deletion | Provenance, access and deletion/worker-race evidence |
| 6 | P5 + E4 | Four specialists and per-operation model policy | Bounded cooperation and matched baseline comparison |
| 7 | P6 + E6 + E7 | Knowledge expansion, diagnostics, Prompt Lab and retention tooling | Source governance, safe evidence views and developer-only operations |
| 8 | P7 + E5 | Recorded then real-time multilingual speech | Real samples, interruption/reconnect and exact turn commits |
| 9 | P8 + E8 | Complete frontend/dictation/tour coverage and hosted staging | Staging security, private storage and recovery checks |
| 10 | P9–P10 | Full local and hosted validation, pilot and repairs | Existing AC-01–25 plus expanded EX-01–16 |
| 11 | P11–P12 | Actual-scope presentations, scripts, Q&A and rehearsal | Every implementation and validation claim traceable to release code |

Knowledge-source investigation can proceed independently of identity/UI work when practical. Actual ingestion and activation still require their own checks. Hosting design starts in P0 and staging should be available before final validation, not first attempted on submission day.

## Calendar and feasibility decisions

- **24 September:** E0/P0 baseline and scoped feasibility. Record hours available, laptop limits, budget, providers and access needs. Carry forward the confirmed English/German and open verified-email registration choices. Estimate effort per workstream with dependencies and uncertainty.
- **4 October:** scope/capacity checkpoint. Review accounts, documents, OCR and evidence pipeline, plus actual work remaining. Do not infer progress from pages or plans alone.
- **8 October:** release-feasibility decision. Show which newly included features can still meet their gates before freeze. Escalate any scope/date/resource conflict to the owner.
- **13 October:** proposed feature freeze. If this is incompatible with the selected scope, obtain an explicit decision rather than quietly shipping unsafe or untested features.
- **14–17 October:** protected validation, real user observations and repairs.
- **18–19 October:** evidence reconciliation, presentation package and rehearsal.
- **20 October:** requested review deadline. A precise delivered/partial/blocked matrix is mandatory even if every selected feature is not finished.

No newly added workstream has a reliable duration yet. This plan intentionally provides a dependency order and decision dates instead of pretending eleven extensions and four data expansions fit in unused time.

## Still outside scope unless separately selected

Camera/emotion assessment, recruiter rankings, automatic job applications, unrestricted crawling, autonomous prompt/code changes, plugin marketplace and billing remain excluded. Whole-application UI translation is not implied by multilingual speech. Team workspaces do not imply enterprise SSO or comprehensive enterprise administration. Spoken feedback and PDF-specific report export remain optional enhancements to the required text feedback and bounded export.

## How to use this version

1. Read this plan and `02_Expanded_Acceptance_Checklist.md`.
2. Use the v2 detailed prompts for unchanged P0–P12 tasks, with the 401-commit implementation corrections.
3. Paste the v3 master scope override in `01_Expansion_Claude_Prompts.md` before any phase. It overrides old “deferred”, “English-only”, “two specialists” and “local-only release” boundaries for the newly selected work.
4. Execute E0 first. Then use only the extension prompt whose dependencies are ready.
5. Track completion as implemented/tested, implemented/unvalidated, incomplete or blocked. “Included in plan” is never “delivered”.
