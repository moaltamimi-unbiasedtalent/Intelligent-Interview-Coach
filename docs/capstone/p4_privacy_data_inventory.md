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
| LangGraph agent checkpoints | ⚠️ saver-owned (outside Alembic) | Still PARTIAL (carried from P1) |

**Status:** account deletion is **PARTIAL** — DB cascade is complete for P4 tables; the
private-file purge and the LangGraph checkpoint purge are the remaining wiring, tracked in
the quality register. Documents are now inside the deletion model (no longer omitted).

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
