# Privacy Review

What the product does and does not do with personal data, and the controls a candidate has.
This is an engineering description of implemented behaviour, **not legal advice and not a
statement of regulatory compliance**. Candidate-facing legal text is an engineering draft pending
legal review. Product claims must stay within [product/PRODUCT_CLAIMS.md](product/PRODUCT_CLAIMS.md).

Scope note: the original (Sprint 1-4) version of this file described the legacy Streamlit
interface (Streamlit-native login, Settings-based export and delete-all). That flow still exists
only in the legacy Streamlit UI. The current product (Next.js + FastAPI) is described here.

## Camera / audio

- The product never requests camera access; no face frames, landmarks, biometric templates or
  visual metrics are produced or persisted.
- Ask4Mo does not record or store microphone audio. Dictation and speech playback use the
  browser's engines; realtime voice (off by default) streams to a provider under that
  provider's terms. Only transcripts the candidate chooses to submit are kept as text. No
  emotion, personality, confidence, accent or hiring signal is derived from voice.

## What is stored (per account, owner-scoped)

Account and preferences; Opportunities; uploaded documents (private file store) with extracted
text/claims and approved evidence; stories; approved long-term memories; completed interviews
(questions, answers, evaluations, report); in-progress interview sessions; feedback ratings;
workspace memberships and share grants; preparation-chat working state (agent checkpoints);
sign-in sessions; and audit/security events (metadata only, no candidate content).

## Candidate controls: `/account/data` ("Your data & privacy")

- **Overview** of stored categories with counts.
- **Export:** one JSON file generated on demand (`GET /api/v1/auth/account/export`, no-store,
  nothing is kept afterwards): account, preferences, Opportunities, document details and
  extracted evidence, stories, memories, interviews, feedback you submitted, workspace
  memberships and items you share. **Not included:** the original uploaded files, security and
  audit records, other people's data, internal prompts/secrets, and any acceptance history
  (not recorded).
- **Delete individual items:** documents, memories, Opportunities, completed interviews.
- **Archive** (Opportunities) hides an item and keeps it; it is not deletion.
- **Revoke** a share: future access stops immediately; it does not recall what a member
  already saw.
- **Unlink:** deleting an Opportunity keeps its interviews and reports and detaches them.
- **Delete the account:** immediate hard deletion of application-controlled data (documents,
  private files, interviews, memories, stories, feedback, Opportunities, sessions, preferences,
  memberships) and sign-out. Security/audit events are **anonymised** (identity removed, event
  metadata kept). Backups are not erased instantly.

## Terminology

*Delete* = removed now and not recoverable. *Archive* = hidden, kept. *Revoke* = future
access stops. *Unlink* = relationship removed, content kept. *Anonymise* = identity removed
from a retained record. *Retain* = kept as stated; only non-content metadata is retained in
audit records.

## Known limitations

- **PRIV-W9-01 - preparation chats (closed in W10.10, with a stated limit):** every NEW preparation run is recorded in an
  ownership index (identifiers and status only, never chat content) before its working data exists, so account deletion finds
  the runs with one indexed query instead of scanning the chat store. If a purge fails the account deletion does not report full
  success: the run stays flagged and a retry is queued. Older runs are indexed only when they can be found from a saved-memory
  reference whose recorded owner matches, or when their owner opens them; an orphan with no such reference cannot be discovered
  and is not covered. Chat CONTENT is not part of the export (only run identifiers and status are listed).
- **PRIV-W9-02 - legal versions (closed in W10.10, with a stated limit):** the Terms, Privacy notice and AI transparency pages now
  have registered versions, and an acceptance of the current version can be recorded (version, timestamp and source only; no IP or
  device). Acceptance was not recorded before: accounts that predate it have none, and none is invented. A baseline version marks
  where versioning began (its effective date was not recorded). Re-acceptance after a new version is not enforced.
- **Privacy requests (SEC-W10-04, closed in W10.10):** a candidate can submit a privacy request for human follow-up, and operators
  can record one received another way. This is engineering support for the workflow: it states no response time and makes no
  statement about legal compliance or statutory retention. Self-service export and deletion are unchanged and immediate.
- No fixed retention periods exist for candidate content (it is kept until deleted); the only
  time-based rule is an operator script that removes stale in-progress interview sessions
  (`INTERVIEW_SESSION_RETENTION_DAYS`). Expired auth rows are not purged automatically.
- Original document files are not part of the export; version history of replaced documents is
  kept until the document is deleted.

**Account deletion and provider subscriptions (W12.4D-F1R).** Self-service account deletion is refused (HTTP 409, `subscription_resolution_required`) while a provider-managed subscription is unresolved: a closure request is recorded, the account stays, and deletion completes once the subscription is verifiably ended (Ask4Mo cannot cancel it for you and never claims future charges have stopped without provider evidence). A privacy-request erasure is never postponed by this: all personal and content data is erased and only an anonymised shell with the minimum billing references is retained until the subscription is verifiably ended, then purged. The retention basis and period of those references are open legal decisions; none is claimed.

**Deletion safeguards, acceptance history, audit context and report differencing (package 05E).** Engineering safeguards only; none of this is a statement about legal compliance, and the legal texts remain unreviewed drafts (legal review is a separate, open step).

- **Deletion is verified, resumable and schema-driven.** After the explicit deletions, a sweep derived from the database schema applies the declared foreign-key action to every remaining reference to the account anywhere (a reference is deleted or cleared), so SQLite (tests, development) and PostgreSQL behave the same and a table added later is covered without a code change; a residual check (counts only) must come back empty before a privacy-request deletion is recorded as completed. Private files are deleted BEFORE the account rows are committed: a file that cannot be deleted aborts the whole deletion (the account stays, nothing is lost, the call can be repeated, HTTP 503 `deletion_incomplete`). Chat working data is found only through the ownership index; a deleted account's leftover index rows are found by one indexed query and purged with `scripts/privacy_sweep_orphan_runs.py` (dry-run by default). A chat that was never indexed still cannot be found (stated limit). Hosted backups are outside this code (not erased on deletion; they age out on the provider's schedule; the hosting package defines what is recoverable).
- **Acceptance history.** `GET /privacy/legal/history` returns the caller's own chronological record of which version of each legal document they acknowledged (version, baseline flag, content hash and effective date where the version has them, source, whether it is still current). It is never back-filled, creates no acceptance by itself (sign-up and sign-in record none; the `signup` source is not wired), and is not consent to any optional processing (none is recorded).
- **Audit and incident context is allow-listed.** Every audit and incident-history row passes one checkpoint (`src/audit_allowlist.py`): only reviewed metadata keys and bounded values are stored; an unlisted key fails the test suite and is dropped (never stored) in a hosted environment. This keeps free text out of the audit trail; it does not make a value personal-data-free.
- **Admin reports resist window and bucket differencing, within stated limits.** A wider standard window is suppressed when its difference from a narrower one is a small group, and a partition hides enough small buckets that total minus visible buckets is not a small group (`src/reporting/differencing.py`). Remaining risk (repeated requests at different times, disjoint-period sums, overlapping partitions, pooling between Admin readers) is documented there; the cohort floor is an engineering control, not anonymisation.
- **Access requests (DSAR):** the options and the recommendation are in `docs/production/execution/PRIV_DSAR_DECISION_RECORD.md`; the owner decides.

## Logging

Generation-failure logs contain safe metadata only (task, schema, model, request id, finish
reason, token counts); never request/response content, answers, transcripts, keys or tokens.
Export content is never logged.

## Identity & access

- Real accounts with server-side sessions in an HttpOnly cookie; production is fail-closed.
  The dev-only `X-User-Subject` header and anonymous developer identity exist only in
  development/test environments and never override a valid session. Google OIDC is implemented
  in the backend but disabled by default, not wired into the frontend and not validated live.
- **Cross-user isolation:** repositories and routes are owner-scoped; a foreign id is `404`.
- **Admin:** `platform_admin` sees account/workspace/privacy-request/feedback/provider/audit
  **metadata** only; no view-as-user, no private-content search. The Admin control plane (P10B-W10, qualified in W10.14) adds
  privacy-request and legal-document operations without any candidate-content access (no break-glass, no impersonation).

## Secrets

Provider keys are server-side only and never sent to the browser (realtime voice uses a
short-lived, user-scoped credential). No secret is committed or baked into the image.
