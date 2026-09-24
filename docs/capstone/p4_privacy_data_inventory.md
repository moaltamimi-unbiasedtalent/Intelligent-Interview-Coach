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
