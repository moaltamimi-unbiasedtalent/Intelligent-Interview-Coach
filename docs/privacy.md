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

- **PRIV-W9-01 - preparation chats:** there is no efficient per-user run index, so a candidate
  cannot list or remove individual preparation chats, and account deletion removes only the
  runs it can reach through saved-memory references. Some preparation-chat working data may
  remain until it is cleaned up. Do not describe deletion as complete.
- **PRIV-W9-02 - consent history:** Terms/Privacy/AI-transparency acceptance versions and
  timestamps are not persisted, so none can be shown or exported.
- No fixed retention periods exist for candidate content (it is kept until deleted); the only
  time-based rule is an operator script that removes stale in-progress interview sessions
  (`INTERVIEW_SESSION_RETENTION_DAYS`). Expired auth rows are not purged automatically.
- Original document files are not part of the export; version history of replaced documents is
  kept until the document is deleted.

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
  **metadata** only; no view-as-user, no private-content search. A fuller admin control plane
  and GDPR operations tooling are planned (P10B-W10), not implemented.

## Secrets

Provider keys are server-side only and never sent to the browser (realtime voice uses a
short-lived, user-scoped credential). No secret is committed or baked into the image.
