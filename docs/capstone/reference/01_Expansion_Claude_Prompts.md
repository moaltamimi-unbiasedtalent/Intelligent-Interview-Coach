# Ask4Mo v3: copy-ready expansion prompts

These extend the detailed P0–P12 prompts. Paste the master override first, then the relevant original phase and one extension prompt. Do not run all extensions at once. v3 controls scope where the old files say selected work is deferred. The 401-commit correction controls what already exists.

## MASTER: expanded scope override

```text
Use Ask4Mo Capstone v3 as the controlling scope. The owner selected C1–C9, C11–C12 and K1–K4, plus bounded A9 report export/deletion. They are included, not deferred. C10 guided onboarding already exists. Retain A1–A8 and B1–B9, preserving the delivered 401-commit surfaces rather than rebuilding them.

Confirmed choices: English and German speech across dictation, recorded Practice, realtime Practice and spoken questions. Hosted registration is open to anyone with a verified email. Local development remains supported. Full UI translation, billing and unrestricted public data access are not implied.

Keep Next.js + FastAPI, application boundaries, governed RAG and deterministic Practice. Mo may coordinate Research, Candidate, Preparation and Evaluation specialists. Authorization, citation guards, budgets and session state remain enforced in deterministic code. Preserve a single-agent comparison/fallback mode.

Verify the active checkout and changes before acting. The last reviewed main was 4f273dd (401 commits). Preserve the historical sprint4-submission-ready tag at 1b084cb and all unrelated user changes. Do not claim old golden results validate new runtime behaviour. Never print credentials or private candidate content. Do not commit, push, merge, move tags, create provider accounts, send invitations, spend on live calls or deploy without the applicable explicit authorization.

Use disposable data for tests. Record code state, dataset, provider/model/prompt version, test mode and limitations. Existing AC-01–25 and new EX-01–16 control acceptance. A UI shell, mocked provider or plan cannot count as completed runtime integration. If credentials or approval are missing, implement/test safe local pieces and mark the exact external gate blocked.

The requested deadline remains 20 October, with proposed feature freeze 13 October. Expanded scope is not a guarantee it fits. E0 must estimate effort and dependencies using available capacity. Escalate conflicts; do not silently remove requested features or consume the validation window. End each phase with changed files, results, remaining risks and the precise next handoff.
```

## E0: feasibility and integrated plan (with P0)

```text
Task: reconcile the expanded Capstone scope with the actual Ask4Mo checkout before implementation.

Read v3 plan/checklist, the 401-commit alignment review, existing runbook, repository instructions and relevant code. Inventory A/B/C/K IDs as delivered, partial, absent or unvalidated. Verify the delivered History/Progress/Sources/Review/tour and identify the actual active-session, recent-run and artifact-reader gaps.

Create one dependency-backed work breakdown including realtime voice, OCR, English/German speech, four specialists, team sharing, social/email authentication, story bank, operation model policy, bulk cleanup, Prompt Lab, open-registration hosting and the four knowledge expansions. Include coding, testing, data review, integration and documentation effort ranges, not just feature coding. Record uncertainty and available weekly hours instead of inventing capacity.

Inspect hardware and dependency compatibility. Propose concrete auth, mail, speech, OCR, queue, storage, database and hosting choices only after checking current official documentation and actual constraints. Identify provider credentials, quotas, budget, data terms and owner approvals needed. Do not activate services or make paid calls. Preserve local startup.

Use the confirmed English/German and open verified-email registration choices. Keep one social provider as a named decision, not an invented credential. For K1–K4 propose a bounded occupation/profession/role/provider-capability coverage matrix with measurable outcomes and source candidates to verify.

Deliver updated scope, dependency order, effort/capacity comparison and decision log. Explain whether full scope can pass before 13 October and be reviewed 20 October. If not, show concrete capacity/deadline/staging choices for the owner without unilaterally dropping work. No feature implementation is required to declare this planning phase complete.
```

## E1: verified identity, email/social access and teams (with P1)

```text
Task: implement C5/C6 on the verified B1–B3 foundation. Prerequisite: E0 auth/data decisions and a safe test database.

Reuse a maintained authentication solution. Support individual accounts, logout/expiry, verified email and single-use recovery. Add one owner-selected social provider using correct state/nonce/PKCE and callback validation as appropriate to that provider/library. Never blindly merge accounts by email. Public registration may create a pending identity, but unverified identities cannot access protected candidate workflows or costly processing.

Add explicit team/membership/resource-sharing models with owner/admin/member permissions and invitation expiry. Personal records remain private by default, even from team administrators. Sharing is an explicit action on a selected resource. Enforce scope in API/services, file downloads, retrieval, caches, workers, agent context and event delivery. Membership removal or share revocation must prevent subsequent async delivery. Define account/team deletion effects without granting broad admin access to private records.

Add anti-enumeration responses and rate limits for signup, verification resend, login and recovery. Local mail capture and mocked social callbacks are test evidence only. Sending actual email or enabling the provider requires authorized configuration. Do not invent secrets, send user invitations or publicly deploy.

Test two personal accounts and two teams, expired/replayed tokens, forged ownership, revoked membership, direct-ID access, unsafe redirects and account linking. Preserve anonymous demo data separately. Deliver EX-06/07 evidence and amended AC-01/02/03. Report local and actual provider tests separately.
```

## E2: OCR and private document ingestion (with P4)

```text
Task: extend B4 with C2. Prerequisite: verified ownership and working bounded PDF/DOCX/TXT ingestion.

Add scanned PDF and declared common-image OCR in a constrained worker. Validate content type, size, page/pixel limits, timeouts and resource use. Keep private originals/derived data outside public web storage. Treat extracted text as untrusted data, never agent instructions. Use page/section and document-version provenance, reviewable extraction and clear unreadable/low-confidence states.

Support the selected English/German content where the OCR provider supports it and measure actual extraction on representative fixtures. The user must be able to correct a claim without turning their correction into a verbatim source quotation. No invented credentials, dates or work history. OCR failure must not silently produce a successful empty index.

Test corrupt/encrypted/malformed files, resource-exhaustion inputs, prompt injection in documents, cross-user/team access, cancellation and deletion while a job runs. Re-check permissions before indexing or returning results so a late worker cannot resurrect deleted or revoked content. Record cleanup of originals, chunks, embeddings and caches, plus separate checkpoint/backup semantics.

Deliver EX-03 and updated AC-08–10 evidence, actual sample quality/correction burden and provider/local execution boundaries. Do not make paid OCR calls without authorization.
```

## E3: story bank and report portability/deletion (after P4)

```text
Task: implement C7 and bounded A9. Prerequisite: owned opportunities, document provenance and existing report/History functionality.

Add candidate-owned story/evidence records with source references, opportunity links, versioned edits and review state. Support structured STAR-style drafts and candidate corrections. Model-generated suggestions remain unapproved drafts and cannot invent achievements. Reuse approved stories in preparation with traceable evidence. Sharing a story requires explicit scope; source access does not automatically transfer with the story.

Add authenticated Markdown and/or JSON report export, with the supported format and included fields documented. Exclude secrets, internal traces and hidden chain-of-thought. Treat exported text as data and escape it appropriately for its format. PDF-specific export is not a prerequisite.

Add confirmed deletion of an owned completed report/history record with exact scope shown. Define effects on Progress aggregates, active sessions, sharing, saved stories, source documents, checkpoints and backups. Do not cascade-delete unrelated source documents or another user's personal copy. Revoke access promptly and report any asynchronous cleanup honestly.

Test export content/ownership, direct foreign IDs, deletion retries, shared-resource revocation, stale story references, source deletion and aggregate updates. Deliver EX-01/08 evidence and candidate-facing lifecycle documentation. Do not run deletion against real user data during development tests.
```

## E4: four specialists and operation model policy (with P5)

```text
Task: extend B8 with C4/C8 after the original Research/Candidate cooperation and private context gates pass.

Add Preparation and Evaluation specialists with genuinely distinct bounded responsibilities and typed outputs. Preparation consumes approved evidence to propose actions. Evaluation applies a fixed versioned rubric to committed answers. Mo controls delegation and synthesis. The existing deterministic Practice manager controls state, scored-answer commits and report completion. No agent may bypass approval, modify its own code/prompt or authorize access.

Use bounded tool allowlists, call/time/token/cost limits, cancellation and delegation-depth limits across the whole run. Share minimal authorized evidence packets, not unrestricted cross-agent transcripts. Define conflict/insufficient-evidence behaviour and meaningful partial results. Keep the single-agent option for comparison and recovery.

Add a central server-side policy for supported operations and allowed model tiers. Never accept arbitrary provider slugs from the browser. Record actual model, policy, prompt and rubric versions on outputs. Keep comparable scoring policy stable within a session or clearly flag/exclude a changed-model fallback from unqualified comparisons. Estimates are not measured provider costs.

Test forged policies, budget exhaustion, specialist timeout/invalid output, stale context, cancellation and duplicate commits. Design a matched single-agent/two-specialist/four-specialist comparison with fixed tasks/data and quality/latency/cost criteria before running it. Offline tests do not establish live superiority. Deliver EX-05/09 and AC-15/16/22 evidence. Obtain authorization for paid comparisons.
```

## E5: real-time English/German voice (after P7 recorded mode)

```text
Task: implement C1/C3 after actual recorded STT/TTS, authenticated speech access and durable Practice work.

Support English and German dictation, recorded answers, spoken questions and real-time Practice. Provide language selection, reviewable detection if used, original-language transcript retention and explicit translation labels. Whole-interface translation is not part of this task. Keep the shared all-input dictation controller and typed fallback.

Implement actual streaming audio/transcript handling, turn detection, interruption, stop/cancel, reconnect and visible state. Define which event commits an answer and requires candidate confirmation before coding. Silence or provider turn completion must not silently approve memory or external actions. Use stable turn IDs and idempotent submission. Discard stale responses after navigation, logout, interruption or a changed draft. A temporary client speech credential must be short-lived and scoped; never expose server credentials.

Prevent playback/microphone feedback, bound clip/session durations and concurrency, document temporary audio retention and keep persistent recording opt-in. Test interrupted playback/transcription/evaluation separately, duplicate network delivery, permission denial, device changes, provider outage, unsupported language and text/recorded fallback.

Use actual English/German reference samples with varied speakers and stated limitations. Record transcription errors/correction burden, language switching, latency, interruption recovery and browser coverage. Do not infer personality, emotion or employability. Deliver EX-02/04 and updated AC-11–14/23. Clearly separate mocks from authorized real-provider measurements.
```

## E6: governed knowledge expansion (source investigation starts in P0)

```text
Task: implement K1–K4 using the approved bounded coverage matrix. Preserve the frozen historical retrieval suite and lineage.

Verify current authoritative sources, licenses/terms, provider entitlements and permitted storage/redistribution before ingestion. K1 adds declared Germany occupation compensation with occupation/geography/year/pay-period/currency mappings. K2 covers selected regulated professions and jurisdictions, distinguishing official requirements from employer preferences. K3 adds versioned emerging-role aliases/context without treating every synonym as a new occupation. K4 exposes selected actual Adzuna capabilities only after checking API support, entitlement, quota and terms. Do not invent endpoints or promise comprehensive coverage.

Implement versioned ingestion, normalized schema, provenance and rollback. Mark unavailable, stale or ambiguous data clearly. Add explicit abstention paths where the evidence cannot support a salary, credential claim or role mapping. Keep private candidate documents separate from public governed data.

Run the unchanged historical regression and a new extension suite with declared denominators. Evaluate K1 unit/date correctness, K2 jurisdiction/requirement distinctions, K3 alias false positives and K4 failure/injection/SSRF/quota handling. Contract tests and live provider results must remain separate. Do not make paid calls without authorization or describe engineering review as legal review.

Deliver EX-13–16 evidence, coverage before/after, source/license decisions, known gaps and actual rebuild/readiness instructions. Show the bounded covered set in-product and in reviewer materials. No fabricated citations or changed denominators to claim improvement.
```

## E7: retention tooling and developer Prompt Lab (with P6)

```text
Task: implement C9/C11 after data ownership, lifecycle and model policies are established.

First inventory stores and derived data: sessions, reports, jobs, checkpoints, documents/chunks/embeddings, story references, audio, caches and backups. Build bounded retention cleanup with dry-run manifests, explicit cutoff/scope, active/pending/hold exclusions, idempotent batches and a safe summary. Re-check eligibility when executing so an active session is not removed based on an old dry run. Document immediate access revocation versus eventual cleanup and separate backup expiry. Never execute broad destructive cleanup against real user data during development.

Migrate only useful Prompt Lab capabilities to a developer/admin-only Next.js route. Use versioned prompt/model/dataset experiments and approved synthetic samples. Candidate, team-admin and developer privileges are distinct. No general candidate content browsing or raw checkpoint/secret exposure. Experiment results must record actual model, prompt version, run mode and cost coverage. Production prompts remain unchanged unless a reviewed explicit version-promotion action is authorized.

Test candidate denial, team-admin denial, experiment injection, provider budget failure, cleanup races/retries/exclusions and precise target manifests. Use disposable stores to test destructive paths. Deliver EX-10/11 evidence, retention matrix and a tested operator procedure. Configured schedules are not proof the cleanup has run successfully.
```

## E8: open-registration hosting and launch preparation (design in P0, staging before P9)

```text
Task: prepare C12 for a real hosted release with open registration for anyone with a verified email, while retaining reproducible local operation. Provider choice, budget, account access and deployment authorization must be explicit. Do not create accounts, purchase services, publish or deploy merely because this prompt plans them.

Prepare private staging with HTTPS, verified backend identity, private document/audio storage, worker and checkpoint persistence, migrations, backups, health/readiness checks, safe logs, secrets management and rollback. Keep real user data out of staging by default. Validate origin/cookie/CORS/CSRF settings as appropriate to the selected auth architecture; do not expose the development identity-header boundary publicly.

Before open signup, enforce email verification, resend/signup/recovery rate limits, anti-enumeration responses, upload/OCR limits and per-account/global AI/speech usage and concurrency ceilings. Add an operator pause switch for costly features. Email verification alone is not abuse prevention. Exercise repeated signup and provider-quota failures. Pricing/billing functionality is outside scope; a documented limited-use policy is sufficient if the owner approves its bounds.

Document account deletion, sharing/revocation, provider data handling, retention, support/recovery and hosting region. Test actual email delivery and selected social-provider callbacks only with authorized configuration. Provide any privacy/legal review questions to the owner rather than claiming compliance certification.

After explicit deployment authorization, run isolated staging checks, restore/rollback exercises and end-to-end tests using synthetic users. Present the release evidence and remaining risks before public launch. Deliver EX-12 plus extended EX-06/07 and AC-20/21. A Docker build, plan, mocked email or local pass is not a hosted-release pass.
```
