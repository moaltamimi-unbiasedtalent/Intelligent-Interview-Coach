# P4 + E2 + E3 — Private Documents, OCR, Candidate Evidence / Story Bank, Export & Deletion

Capstone implementation story. The first substantial **private candidate evidence**
workflow: authenticated users upload career documents privately, extract and review
provenance-bearing evidence, reuse approved evidence through a Story Bank, and export or
delete owned results — without turning documents into trusted instructions.

Base: `main` @ `cb7ce77` (P3.5 merged, PR #77). Branch: `feature/capstone-p4-documents-evidence`.
No historical tag moved.

## WHAT
Upload → validate → private store → parse/OCR → deterministic structured extraction →
user review (accept/correct/reject) → approved evidence → story bank → report export /
delete. Owner-scoped throughout.

## WHY
Candidates prepare best from their own history. This adds private evidence while keeping
Ask4Mo's safety posture: documents are DATA, never prompts; nothing becomes public
knowledge or approved memory automatically; the candidate controls every fact.

## DESIGN DECISION (key trade-offs)
- **Deterministic, no-LLM extraction.** Every claim is a VERBATIM span from the source
  with page/section provenance. This makes extraction offline, testable, and
  **injection-proof** (no document text ever reaches an LLM prompt in P4). LLM-assisted
  extraction is a possible later, authorised enhancement.
- **Synchronous bounded processing.** Given the declared file types + 10 MB / 50-page
  limits, processing is reliable inline — no Celery/Redis introduced (§31). Failures are
  captured as a safe FAILED status, never a crash.
- **OCR behind an abstraction.** Local, open-source Tesseract (lazily imported; no paid
  provider); a fake engine drives deterministic tests. Native-first routing: OCR only
  when there is no usable text. Live OCR quality is **UNVALIDATED** (CONFIGURED for 7
  languages).
- **`users` stays the owner.** Documents/claims/stories cascade from `users.id`, so
  account deletion removes them; document deletion cascades to claims and unlinks stories.

## DOCUMENT LIFECYCLE
`UPLOADED → PROCESSING → REVIEW_REQUIRED | READY | FAILED → (delete)`. Model:
`CandidateDocument` (logical) → `DocumentVersion` (each uploaded file, stable provenance)
→ `DocumentClaim` (provenance-bearing, reviewable) ; `CandidateStory` + `StoryEvidence`
(migration 0010, single head).

## OCR DECISION
`parse_document` (pypdf/python-docx/txt) first; `needs_ocr` routes scanned PDFs and images
to `ocr_parse` over the injected engine; OCR output is labelled `origin="ocr"` with page
identity. Missing engine → safe FAILED (no false "scanned" claim). Languages en/de/fr/es/
it/pt/nl are CONFIGURED (Tesseract codes); live quality is not asserted.

## PROVENANCE MODEL
Every claim carries `document → version → page/section` and its `review_state`; edited
claims keep the original `text` alongside `edited_text` (USER-CORRECTED). Five evidence
domains stay distinct: public governed knowledge, current external market evidence,
private document evidence, candidate-approved stories, and model inference.

## USER REVIEW
Accept / Correct / Reject per claim; nothing is reusable until accepted. Editing stores a
correction (never claimed as verbatim source). No extraction becomes approved Memory or a
story automatically.

## STORY BANK
`draft_from_claims` builds a SOURCE_BACKED story deterministically from the user's own
approved claims (verbatim only — invents no numbers/outcomes/dates/scope, §16). States are
explicit and truthful: `source_backed` (verified while evidence lives), `user_corrected`
(after editing), `user_created`, `model_suggested`. **Deleting a source flips a story from
verified → source_revoked** — never silently "verified".

## EXPORT / DELETE
Report export (bounded A9): owner-scoped Markdown + versioned JSON from the STORED report
(no LLM re-run), omitting all internal state (system prompts, CoT, checkpoints, secrets,
usage payloads). Deletion removes the file, extracted text and claims immediately;
`rederive` updates dependent stories. Report/history deletion reuses the existing
owner-scoped `delete_interview` (checkpoint/backup consequences documented in the privacy
inventory).

## SECURITY
Owner-scoped everywhere (foreign id → 404); allow-listed MIME + magic-byte sniff (anti-
spoof); size/page limits; filename sanitisation; path-traversal-proof storage keys;
encrypted/corrupt files fail safely; no execution/macros/HTML. Documents are untrusted
DATA and never enter a prompt. Content-validation only — **not** malware scanning (a real
scanner is a documented production requirement).

## PRIVACY
See `docs/capstone/p4_privacy_data_inventory.md`. Files are private (no public URL);
authenticated download only; not exposed to Platform Admin. Observability logs only safe
metadata (never CV/OCR/claim/story content, raw files, private paths or tokens).

## I18N
All new candidate-facing strings are in the i18n catalogue (`documents` namespace) across
all seven locales (engineering draft). Document language is independent of interface, Mo
conversation, dictation language and career geography.

## EVALUATION
`scripts/eval_documents_evidence.py` (offline, no paid/OCR-provider calls): extraction
provenance + no-invention, OCR routing/labelling/language-config/unavailable-safety, story
source-backing + revocation, export MD/JSON + no-internal-data + owner-scoping, cross-user
isolation, injection-inert, deleted-document-unavailable → all PASS. Backed by
`tests/test_documents_pipeline.py`, `tests/test_documents_api.py` and frontend
`tests/documents.test.tsx` + `e2e/documents.spec.ts`.

## TRADE-OFFS
Deterministic extraction is honest and safe but shallower than LLM extraction; OCR live
quality is unvalidated; synchronous processing suits the declared limits but a hosted
deployment with larger files would move to background jobs (the status model already
supports it).

## KNOWN LIMITATIONS
No malware scanning (documented); live OCR quality UNVALIDATED; extraction is heuristic;
old document versions + their claims are retained for provenance (not purged on replace);
private semantic (vector) retrieval was intentionally NOT added (not needed for P4).

## CAPSTONE LESSON
Treating candidate documents as untrusted DATA — deterministic extraction, provenance,
explicit review, and never feeding document text to the model — delivers a genuinely
useful evidence workflow while keeping every safety guarantee intact.
