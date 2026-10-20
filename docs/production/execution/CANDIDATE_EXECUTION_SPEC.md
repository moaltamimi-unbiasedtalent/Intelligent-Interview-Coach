# Candidate Execution Specification (Track D)

**Status:** PROPOSED engineering specification, 2026-10-21, from the owner's Story Bank, Workspace and Candidate requirements (`../OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md` sections 5 to 7) and REVIEW-05. Nothing is implemented. Candidate content is private; stories, documents and answers are untrusted DATA in prompts; ownership is enforced at the API boundary.

## 1. Packages

| Package | Requirement | Depends on | PRs |
|---|---|---|---|
| 04A Story Bank | REQ-OWN-06 | none | 2 |
| 04B Workspaces | REQ-OWN-07 | none | 2 |
| 04C Streaming and cancellation | REVIEW-05 | 01A | 2 |
| 04D Journey reliability | REQ-CAND-01, DEMO-02 | 05A (staging) | 2 |
| 04E Invitation-only registration | REQ-BETA-01 | none (OD-INVITE) | 1 |
| 04F Browser dictation verification | W12.4E-16, AC-13/AC-23-A | none | small |

## 2. 04A Story Bank

Existing: source-backed, revocation-aware story bank (P4) with owner-scoped repository and service (`src/application/stories_service.py`), MD/JSON export, and candidate evidence selection from approved claims only.
Gaps against the owner text: manual STAR editor; provenance classes visible (user-created, source-backed, user-corrected, model-suggested); search, filter and competency tags; Opportunity link; interview-time suggestions with Candidate approval; reuse in Practice; feedback that reflects the story evidence; deletion and privacy controls (CJ-D-05: the "Reviewed by you" badge and the AI-suggested path are not rendered today).
Design: add `provenance` and `competency_tags` and an Opportunity foreign key (one additive migration); a suggestion endpoint returning ranked approved stories for a role and question (deterministic lexical and tag match first; any model-assisted ranking only on approved story text, with the injection screen); the Practice setup offers "use my stories" with an explicit selection; evaluation prompts receive only selected, approved story text as trust-separated DATA; feedback cites which story fields were used and never invents achievements or numbers (existing no-fabrication rules apply and get tests).
Acceptance journey (Playwright): create, edit, link to Opportunity, reuse in Practice, receive feedback, retrieve after restarting the backend. Ownership tests: another user receives 404 on every story route.

## 3. 04B Workspaces

Existing: backend for Workspaces, membership roles on the membership, hashed single-use invitations with 72-hour expiry, VIEW-only share grants with immediate revocation, audit; candidate controls to invite and share are missing (CJ-D-01).
Gaps: invite by email UI, accept and decline, pending list, cancel and revoke, membership and role display, removal, ownership transfer, share and revoke controls with a "what is shared with whom" view, activity record.
Design: UI over the existing endpoints plus new endpoints for ownership transfer (rules need OD-WS-TRANSFER; proposal: current owner nominates an existing member, nominee accepts, one owner at all times, last-owner protection already exists) and share listing; sharing defaults to VIEW-only and lists supported resource types (interview report and story today).
Acceptance journey: User A creates a Workspace and invites User B; B accepts; A shares one resource; B accesses only that resource; A revokes; B immediately loses access. Authorization tests run against the API for every shared resource type and for every unshared resource (403/404), not through the UI.

## 4. 04C Streaming and cancellation (REVIEW-05)

Existing: `POST /api/v1/agent/run`, resume, continue and delete routes; durable checkpoints; `AgentEvent` types in `src/agent/events.py`; usage capture in `src/agent/usage.py`.
Design: an authenticated SSE route beside the run route, built on LangGraph `astream_events` version v2 (compatibility with the pinned LangGraph version to be verified first, with the synchronous route as the fallback); a projection layer maps internal events to an allow-list of safe progress events (stage started and finished, tool name without private arguments, retrieval counts, citations when final); anything else is dropped. Cancellation: a client disconnect or explicit cancel sets a token checked between graph steps and closes the stream; the run stays durable and resumable; usage and cost for the cancelled portion are reconciled and recorded. Reconnection requires the same session and run ownership; events are never replayed across users. Candidate UI: progress states in the Mo conversation, a cancel control, and automatic fallback to the synchronous result if streaming is unavailable. Tests: SSE contract, allow-list negative test (no chain-of-thought, system prompt, private arguments or secrets), cancellation and timeout, cross-user reconnect, cancelled-run usage reconciliation, synchronous fallback, a browser test of progress states.

## 5. 04D Journey reliability and DEMO-02

A staging-only Playwright journey per language covers registration (with invitation), onboarding, Opportunity, Mo, Practice start, answer, feedback, History and Progress, including the Start interview regression. The UI must distinguish "AI not configured" from a transient provider failure with accurate recoverable copy (today a generic message is shown for both), and Admin and Candidate surfaces show the active provider mode so a keyless stack cannot masquerade as live. Also in this package: AC-03 tests (two Opportunities with context selection and restart persistence), AC-18 owner-scoped recent runs endpoint, the implicit-key-discovery guard (IR-DEMO-KEY), and the Premium wording consistency (CJ-D-02, I-D02). Every result states whether it is offline, mocked or live.

## 6. 04E Invitation-only registration

Registration requires a valid invitation: hashed single-use expiring tokens, issued and revoked by Admin and audited, refused server-side otherwise, with no payment path. The mechanism (codes versus email allow-list) is OD-INVITE; the proposal is single-use invitation tokens bound to an email address because the platform already has hashed single-use token patterns.

## 7. Exit gates (PG-06, PG-13)

Journeys green on staging; Story Bank and Workspace acceptance journeys green including restart and revocation; streaming works with the synchronous fallback; per-language evidence recorded by 06B.
