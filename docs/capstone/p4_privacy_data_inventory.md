# P4 — Privacy Data Inventory & Account-Deletion Dependency Map

Documents/evidence data introduced in P4, and how it fits the account-deletion lifecycle.
This is an engineering privacy inventory, **not** a legal-compliance statement.

## Document data inventory

| Data | Why | Where stored | Who can access | External processing | Retention | Deletion |
|---|---|---|---|---|---|---|
| Original file (PDF/DOCX/TXT/PNG/JPEG) | Source of candidate evidence | Private file store (`DocumentStore`; local dir outside web root; object-storage-ready), opaque random key | The owning user only (authenticated download); **not** Platform Admin | None by default. **OCR:** if enabled, scanned images are read by local Tesseract (no network). No paid provider. | Kept until the user deletes the document or account | Purged from the store on document delete and on account delete (via `users` FK cascade → versions) |
| Extracted text / OCR text | Produce reviewable claims | Not persisted as a blob; only derived claims are stored | Owner only | LLM: **never** (deterministic extraction) | Transient (in-process during upload) | Not stored separately |
| Structured claims | Reusable, provenance-bearing evidence | `document_claims` (DB), owner-scoped | Owner only | None | Until document/account deletion | Cascade on document delete + account delete |
| Stories | Reusable interview examples | `candidate_stories` / `story_evidence` (DB) | Owner only | LLM: none (deterministic/user-authored) | Until user/account deletion | Cascade on account delete; story_evidence unlinks on claim/document delete |
| Document metadata (filename, size, status, timestamps) | Manage the workflow | DB | Owner only | None | With the document | With the document |

**Not collected/stored:** raw audio, biometric/voiceprint data, emotion/identity analysis,
document contents in logs, private file paths in logs, auth tokens.

## LLM & prompt boundary
Document text is **DATA, never a prompt** in P4. Extraction and story drafting are
deterministic (no LLM call), so uploaded content cannot influence Mo, tools, retrieval or
system prompts. (Later story-reuse-in-Mo phases must preserve this via bounded, owner-
scoped, relevance-limited context — not automatic ingestion.)

## Account-deletion dependency map (updated)
P1 left full account hard-delete **PARTIAL**. P4-owned resources are now in the model:

| Resource | Cascade on account delete | Notes |
|---|---|---|
| `candidate_documents` / `document_versions` / `document_claims` | ✅ via `users.id` FK `ondelete=CASCADE` | DB rows removed |
| Private files in the DocumentStore | ⚠️ requires the document-delete code path (files are outside the DB) | The account-deletion service must iterate owned documents and call the store; **documented as the remaining wiring** — the per-document delete already purges files, and `delete_all_for_user` should call it |
| `candidate_stories` / `story_evidence` | ✅ via `users.id` FK cascade | DB rows removed |
| Interviews / reports / memory / sessions / feedback | ✅ (P1) | Existing cascade |
| `opportunities` (P10B W6) | ✅ explicit delete in `AccountDeletionService` (after interviews/sessions) | FK `user_id` CASCADE; interviews/sessions links are SET NULL, so history is never destroyed by an opportunity delete |
| LangGraph agent checkpoints | ⚠️ saver-owned (outside Alembic) | Still PARTIAL (carried from P1) |

**Status:** account deletion is **PARTIAL** — DB cascade is complete for P4 tables; the
private-file purge and the LangGraph checkpoint purge are the remaining wiring, tracked in
the quality register. Documents are now inside the deletion model (no longer omitted).

### P10B Wave 2 delta (2026-09-27)
- New low-sensitivity account columns (migration `0013`): `users.onboarding_completed_at` +
  `onboarding_step` (lifecycle only, no personal content); `user_preferences.coaching_style`
  (bounded enum), `career_geography` (bounded code, independent of language), `target_role`
  (short free-text career-focus DATA). None are candidate documents, protected traits, or model
  content; all cascade/delete with the account. Available to every tier (never entitlement-gated);
  privacy/data-rights are never gated.
- `display_name` (already on `users`) is now editable via `PATCH /auth/preferences` and projected in
  `/auth/me`. Free-text preferences (`display_name`, `target_role`) are audited as "set" — the value
  is never logged verbatim, never placed in a URL, and never fed to a model as a prompt (coaching
  style reaches the model only as a fixed allow-list directive).

### P10B Wave 3 delta (2026-09-26)
- New column `document_versions.failure_kind` (migration `0012`) holds a **bounded enum tag**
  (`encrypted` / `corrupt` / `ocr_unavailable` / `ocr_failed` / `no_text` / `internal`). It stores
  **no personal content** and no exception text; it cascades/deletes exactly as the row does.
- `POST /documents/{id}/reprocess` reads the **already-stored** private file (no new upload, no new
  storage location) and re-runs the same extraction; it is owner-scoped (foreign id → 404). It
  introduces no new data category and no new retention surface. Story evidence is re-derived so a
  reprocessed document never leaves a story silently "verified".

### P10B Wave 5 delta (2026-09-27) - Company Intelligence
- **No new persistence and no migration.** The directable `POST /api/v1/research/company` reuses the
  existing Phase 7F engine. Its only storage is the pre-existing ephemeral file cache
  (`data/cache/external/`, git-ignored, ~30-min TTL) keyed on **safe request parameters only**
  (provider/intent/role/country/company-url/limit) - **never candidate data**, never raw HTML, never
  credentials.
- **Candidate inputs** (company name, location, website, target role) are request-time only and are
  not persisted per-user. A selected **JD document** is resolved **owner-scoped** server-side
  (`resolve_document_text`) and used as bounded keywords for display only; a foreign/missing/deleted
  document yields nothing (`jd_linked=false`) and is never disclosed. JD text is never placed in a
  model prompt (no model call in this service).
- **No third-party personal data is stored.** Employee-review platforms (Glassdoor/Kununu) and
  Google/LinkedIn are **not integrated**; the UI links out and copies no review content.
- **Admin boundary unchanged:** Platform Admin gains no candidate research data.

### P10B Wave 6 delta (2026-09-27) - Opportunity model
- **New table `opportunities`** (migration `0014`, additive): owner-scoped candidate preparation
  context - `title`, `target_role`, `company_name`, `company_location`, `company_country`,
  `company_domain`, `job_description_document_id` (FK, SET NULL), `status`, `notes`, timestamps. It
  stores only **bounded candidate-entered strings + a JD reference** - **no CV/evidence text, no
  research content, no secrets**. FK `user_id → users.id ON DELETE CASCADE`.
- **`interviews.opportunity_id` / `interview_sessions.opportunity_id`** (nullable, SET NULL): an
  organising link only; no candidate content. Deleting an Opportunity never deletes interviews,
  documents or evidence (SET NULL / kept). A deleted JD clears the Opportunity's link (no stale
  content); `context`/`overview` re-check ownership on every read.
- **Account deletion:** owned `opportunities` are removed (explicit, after interviews/sessions) - added
  to `AccountDeletionService`. **Admin boundary unchanged:** Platform Admin gains no opportunity data.
- Company/career geography stay independent; geography is never inferred from language; user-entered
  role/company/notes are never auto-translated. Audit events (`opportunity.created/archived/deleted`)
  are metadata-only.

## Retention / backup / checkpoint consequences
- Deleted documents/claims/stories are removed from the live database immediately.
- Exported copies (Markdown/JSON the user downloaded) leave application control — the UI/
  Help states this.
- Report/history deletion removes the report row; any LangGraph checkpoint for a related
  agent run is saver-owned and is not purged by history deletion (documented, carried).
- Production database backups may retain deleted rows until backups rotate — a hosting/
  retention concern for the productisation phase (not claimed as immediate global erasure).

## Admin boundary
Uploaded candidate documents are **not** exposed to Platform Admin by default; the admin
control plane remains bounded (audit metadata only), designed separately.

## Not claimed
No malware scanning (content validation only); no legal-compliance certification; live OCR
quality unvalidated.

## P6.5 — Teams / Workspaces & sharing data inventory

| Data | Purpose | Where stored | Visibility | Retention | Revocation | Deletion |
|---|---|---|---|---|---|---|
| Workspace (name, owner, status) | collaboration space | `workspaces` (DB) | members (metadata); admin (metadata) | until deactivated/deleted | n/a | owner deactivate; account cascade for the owner |
| Membership (role, status) | who belongs + workspace role | `workspace_memberships` (DB) | the workspace's members (metadata) | until removed/left | leave/remove marks inactive | cascade on workspace or account delete |
| Invitation (email, hashed token, expiry) | secure join | `workspace_invitations` (DB) | inviting owner | single-use / 72h expiry | revoke/expire | cascade on workspace or inviter account delete |
| Share grant (resource ref, VIEW, status) | explicit sharing | `share_grants` (DB) | owner + members of the target workspace | until revoked / source deleted | owner revoke (immediate); source delete invalidates | cascade on owner/workspace delete |
| Feedback category | governed improvement signal | `user_feedback.category` (DB) | self (+ admin aggregate counts) | with the feedback row | n/a | with the feedback row / account cascade |

**Joining a workspace never changes ownership of existing personal data.** Membership is not
consent to inspect an account; the ONLY cross-member visibility is an explicit VIEW share
grant, which the owner can revoke at any time (immediate). Shared content is NOT copied — it
is read live from the owner's record and disappears on revoke or source deletion.

### Account-deletion dependency map (updated for P6.5)

| Resource | Cascade on account delete | Notes |
|---|---|---|
| `workspace_memberships` (as member) | ✅ FK `users.id` CASCADE | rows removed |
| `workspace_invitations` (as inviter) | ✅ FK CASCADE; `accepted_user_id` SET NULL | rows removed; accepted-by ref nulled |
| `share_grants` (as owner) | ✅ FK CASCADE | outbound shares removed → members lose access |
| `workspaces` (as owner) | ✅ FK CASCADE today | **Documented semantics:** deleting an owner's account removes their owned workspaces (and, by cascade, their memberships/invitations/shares). A production hardening step may instead require ownership transfer before owner-account deletion; for P6.5 the cascade is the defined behaviour. |
| `user_feedback.category` | ✅ (column on cascaded row) | removed with the feedback row |
| Private files + LangGraph checkpoints | ⚠️ still PARTIAL (carried from P1/P4) | global hard-delete NOT claimed complete |

**Workspace deletion/deactivation semantics:** deactivating a workspace revokes its share
grants and hides it from members, but **never deletes member-owned candidate resources** —
candidate ownership is preserved. **Platform Admin does not own or delete member resources.**

## P7 — Voice (STT + TTS) data inventory

Turn-based voice is a browser modality. Ask4Mo stores no audio and derives no human-trait
signal. This is a technical design statement, not a legal-compliance certification.

| Data | Purpose | Where processed | Persisted by Ask4Mo? | Sent to LLM? |
|---|---|---|---|---|
| Microphone audio (STT / dictation) | Speech → transcript | Browser/OS/vendor speech-recognition service (browser-managed) | **No** — no MediaRecorder/getUserMedia/Blob; no recording, no voiceprint | No |
| Recognised transcript (pre-submit) | Editable input | In-page only (React state) | No (not stored/logged before submit) | No |
| Submitted text | The candidate's answer/message | Normal application flow | Yes — as the existing text answer/message (unchanged) | Yes (existing text path) |
| Synthesised audio (TTS / Listen) | Read visible text aloud | Browser/OS speech-synthesis engine (Ask4Mo passes visible text) | **No** — no synthesised audio stored | No |
| Voice preference (on/off, device voice) | Per-device convenience | Browser localStorage | Device-local only (no candidate content) | No |
| Voice human-trait signals (emotion/accent/confidence/hiring/…) | — | **Never derived, stored or transmitted** | **No** | No |

- **STT honesty:** browser speech recognition may send audio to the browser/vendor's speech
  service to produce the transcript — that processing is the browser's, not Ask4Mo's. We do
  NOT claim "audio never leaves the device."
- **TTS honesty:** how the browser/OS synthesises audio is browser-dependent; Ask4Mo provides
  text and stores no synthesised audio.
- **Admin/workspace boundary:** Platform Admin receives only speech *architecture* metadata
  (input/output = browser Web Speech; `audio_persisted=false`; `voice_trait_inference=none`),
  never audio/transcripts/voiceprints. Workspaces never auto-share audio, transcripts or voice
  preferences.
- **No new persistence** and **no migration** for voice (Alembic head unchanged).
