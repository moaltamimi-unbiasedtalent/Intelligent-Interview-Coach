# P10B Wave 3 — Document Reliability, Classification & Discoverability

**Status:** DELIVERED (implementation complete; gates green). **OCR operational-readiness closure
added 2026-09-26 — see §20.**
**Branch:** `feature/capstone-p10b-wave3-documents` — **not merged**.
**Date:** 2026-09-26.
**Baseline:** `main` @ `30cd9f9` (Wave 1 merged via PR #87).
**Migration:** `0012_document_failure_kind` (single head; additive nullable column).
**Release candidate:** none. RC-P9-001 remains immutable; RC-P10-002 is cut only at Wave 8.
**Paid/live calls:** 0 (open-source local Tesseract/Poppler only; no paid OCR/LLM/provider calls;
live/human OCR accuracy remains UNVALIDATED).

> **Founder G1 status:** **RESOLVED for the supported runtime.** The OCR runtime is now installed by
> `deploy/Dockerfile.api` and was validated end-to-end with the identical open-source engine locally
> (a scanned résumé is actually read — see §20 and §5). Live/human OCR **accuracy** remains
> UNVALIDATED. The initial Wave 3 report overstated G1 as fully fixed while no OCR runtime existed;
> that is corrected here.

---

## 1. Baseline / safety

- Confirmed `main` @ `30cd9f9`, Wave 1 merged (commit `850f4ab` is an ancestor of `origin/main`),
  clean working tree, Alembic head `0011_workspaces_shares`. Branched Wave 3 from `main`.
- **Preserved unchanged:** owner scoping, provenance, evidence review, Story Bank behaviour,
  deletion semantics, source revocation, malware fail-closed (`file_security.py` untouched),
  path-traversal protection (`storage.py` untouched), MIME/magic-byte validation
  (`validation.py` untouched), the prompt-injection-as-DATA boundary (extraction stays
  deterministic; document text never enters an LLM prompt), private file storage, the admin
  privacy boundary, and the 10 MB / 50-page limits.
- No security control was weakened to make an upload succeed.

## 2. Root cause of "Couldn't read the file"

The founder's résumé was a **scanned/image-based PDF** (no embedded text layer). The pipeline
routes such files to OCR (`needs_ocr`), and OCR requires the optional `[ocr]` extra
(`pytesseract` + `pdf2image`) **plus** system binaries (`tesseract`, `poppler`) — **none of which
are installed** in the running environment (verified: `import pytesseract` / `pdf2image` both fail).

So `ocr_parse` raised `OcrError("Scanned-document OCR is not available…")` and the document was set
to a **FAILED** state. Two UX faults then made it opake:
1. The backend already stored a distinct free-text `failure_reason`, but the **inventory row only
   showed a status badge** and buried the reason inside the expanded detail;
2. the reason was **English free-text** (not localizable) and **not actionable** (it did not tell
   the user this is a scanned document needing OCR, nor offer a retry).

There was no way for the UI to distinguish *materially different* failures (encrypted vs corrupt vs
OCR-unavailable vs no-text vs internal) because only a free-text string existed.

## 3. Document pipeline (unchanged shape, hardened reporting)

One governed pipeline remains: **validate → private store → parse (native) or OCR → deterministic
extraction → review**. Wave 3 changed only the *failure reporting* and added a *retry*:

- `ParseError` and `OcrError` now carry a bounded, machine-readable **`kind`**.
- The service records a `failure_kind` on the version and clears it on success.
- A new **reprocess** path re-runs the SAME pipeline on the already-stored file.

## 4. OCR — graceful degradation (production-honest)

We did **not** install a paid OCR provider and did **not** vendor system binaries into this
environment; live OCR quality stays **UNVALIDATED**. Instead:

- **Native-text** documents never depend on OCR (unchanged).
- **Scanned/image** documents route to OCR intentionally (unchanged).
- A **missing OCR capability** now yields the distinct `ocr_unavailable` kind — never disguised as
  a corrupt résumé — with a clear, localized, actionable message.
- The uploaded file is **preserved** (it is stored *before* processing), within the existing
  privacy lifecycle, so it can be retried without re-upload.
- A **`POST /documents/{id}/reprocess`** endpoint re-runs extraction on the stored file
  (owner-scoped, rate-limited, OCR-pause-aware). It is the safe retry for a transient condition
  (e.g. scanning briefly offline) and for a scanned document **once OCR is enabled** in the
  deployment. It never fabricates content and never marks failed OCR as success.
- **Deployment note:** to enable OCR, install `pip install -e ".[ocr]"` **and** the system
  `tesseract` + `poppler` binaries. Until then, scanned documents report `ocr_unavailable`
  honestly and text-based PDF/DOCX/TXT work fully.

## 5. Failure taxonomy

`src/persistence.py` defines `DOC_FAIL_*`: `encrypted`, `corrupt`, `ocr_unavailable`,
`ocr_failed`, `no_text`, `internal`. Stored in a new nullable `document_versions.failure_kind`
(migration `0012`). Exposed on `DocumentVersionOut` and, for the inventory, on `DocumentSummary`
(the current version's `failure_kind` + `extraction_origin`). The UI maps each kind to a localized
message (`documents.fail*`), falling back to the stored reason then a generic line. No internal
exception text, path, provider, or secret is ever exposed.

## 6. Document categories

The existing five categories are unchanged (no new/conflicting categories, no LLM classification):
`cv`, `job_description`, `portfolio`, `company_brief`, `other`. They are **selectable on upload**,
**visible** in the inventory (localized badge), **owner-scoped**, **survive reload**, and are
returned by the API (verified by tests). Automatic classification was **not** introduced in Wave 3.

## 7. Document inventory

The listing is now a **responsive inventory**: a table on desktop, stacked cards on mobile. Columns:
name, type (category), status, updated date, version, actions. Actions expose only supported
operations: **review evidence** (expand), **download**, **retry processing** (failed docs only),
and **delete** (with confirmation). Meaningful empty / processing / review-required / failed / ready
states are rendered, and internal storage keys/paths are never shown.

## 8. Upload experience

A new reusable `DocumentUpload` states, **before** a file is chosen: accepted formats, size/page
limit, document category, private-storage expectation, what happens after upload, and the OCR note.
It does immediate **client-side pre-validation** (type + size) with a localized message, shows a
processing state, a success state, and an actionable failure state, is keyboard-accessible, and
announces status via `aria-live`. It never claims OCR/scanning/extraction succeeded — it reports
only what the API returned.

## 9. Prepare / Practice reuse seam (Wave 4 boundary)

`components/documents/DocumentUpload.tsx` is the **single** upload component and the reusable seam.
It exposes props for Wave 4 to embed it in Prepare/Practice **without a second pipeline**:
`onUploaded(detail)` (chain after upload), `defaultCategory`, `lockedCategory` (fix + hide the
picker, e.g. an "Upload your CV" affordance), `showCategory`, and `compact` (side-panel variant).
Wave 3 does **not** wire it into Prepare/Practice, does **not** inject document text into prompts,
does **not** attach evidence to interviews, and does **not** change Mo's reasoning or scoring.

## 10. i18n

All new candidate-facing strings use the i18n system: 35 keys added to the `documents` namespace
across **EN/DE/FR/ES/IT/PT/NL**, key parity enforced by the TypeScript `Catalog` type. The
hardcoded "Evidence" eyebrow and the load-error fallback are now localized. Document language is
**not** coupled to interface/conversation/dictation language or career geography. User-uploaded
CV/JD/document content is **never** translated. Engineering translations are labelled not
human/legal-reviewed (see §15/Known limitations).

## 11. Accessibility

Upload input is labelled with an `aria-describedby` status region (`aria-live="polite"`); the
category picker is a labelled `<select>`; inventory expanders use `aria-expanded`; the retry/delete
controls are native buttons; the desktop inventory is a real `<table>` with header cells and the
mobile view is a semantic list.

## 12. Security & privacy

Re-tested (deterministic): cross-user document access / foreign download / foreign delete / foreign
replace / **foreign reprocess** → 404; category persistence is owner-scoped; path traversal
(storage) rejected; MIME/extension spoofing rejected; oversized rejected (client + server);
encrypted/corrupt fail safely with the correct kind; prompt-injection text stays inert DATA (no
instruction claim types; never prompted); malware fail-closed path unchanged; deleted document
immediately unavailable; source-backed story revoked on source deletion. Documents remain untrusted
DATA and are never placed in an LLM prompt in Wave 3. Platform Admin gains no private-document
access (admin surface untouched).

## 13. Evaluation

`scripts/eval_documents_evidence.py` extended with Wave 3 invariants — all PASS:
`failure_taxonomy_ocr_unavailable`, `category_persists`, `reprocess_owner_scoped` (SAFETY),
`reprocess_recovers` (SAFETY) — alongside the preserved provenance/no-invention/isolation/
revocation/export invariants. 0 paid/OCR/live calls.

## 14. Regression / quality

- Backend document units + API: **34 passed** (`test_documents_pipeline.py` +
  `test_documents_api.py`, +5 new). OpenAPI contract: pass. Migration up/down/single-head: verified.
- Frontend: `typecheck` pass · **268 unit** (49 files; +5 new in `documents-wave3.test.tsx`) ·
  `lint` clean · `build` pass · **104 Playwright e2e** pass.
- Full backend `pytest`: **2386 passed, 3 skipped, 0 failed** (baseline 2381 + 5 new document
  tests; the 3 skips are the RAGAS installed/absent guards). `ruff check .` clean. The migration
  single-head test was updated to expect `0012_document_failure_kind` (the new head).
- New frontend unit file `tests/documents-wave3.test.tsx`; new eval invariants in
  `eval_documents_evidence.py`.
- **Pre-existing flake fixed (not a Wave 3 regression):** `e2e/product-surfaces.spec.ts` asserted
  `getByText("Knowledge runtime")`, which is ambiguous under Playwright strict mode because the RAG
  page's description also contains that phrase; it fails intermittently depending on worker
  ordering (reproduced on clean `main`). Re-pointed at `getByRole("heading", …)` — a stricter,
  correct assertion, not a weakening.
- No tests weakened.

## 15. RC impact

No release candidate created. RC-P9-001 immutable. Waves 1–7 are development increments; Wave 8's
integrated regression cuts **RC-P10-002**. If a real participant pilot is run against this changed
runtime before Wave 8, a new RC must be cut first.

## 16. Known limitations

- **Live/human OCR accuracy is UNVALIDATED** — the runtime works end-to-end on synthetic fixtures
  (§20), but real-world scan quality (skew, noise, multi-column, handwriting) is not benchmarked.
- The OCR-enabled image is **~150–200 MB larger** (Tesseract + 7 language packs + Poppler).
- **Human/legal translation review of the new i18n keys is NOT done** (engineering translations only).
- No automatic document classification (deliberate; user selects the category).
- Prepare/Practice upload integration is deferred to **Wave 4** (only the reusable seam is built).
- OCR **language data must be installed per language**; a language is reported `runtime_available`
  only when its Tesseract pack is present (admin `providers.ocr.languages`).

## 17. Documentation

This document; `p10b_remediation_plan.md` (Wave 3 delivered note); `p4_privacy_data_inventory.md`
(reprocess reads the already-stored file; new `failure_kind` column holds no personal content); the
requirements matrix where applicable.

## 18. Next recommended wave

**Wave 4** (Prepare/Practice document + evidence integration and Practice-language) — it consumes
the reusable upload seam and owns the deferred interview-language work.

## 19. Final verdict

The résumé-read failure is root-caused and fixed: scanned/image documents now fail **honestly and
specifically** (`ocr_unavailable`) with a clear, localized, actionable message and a one-click
retry — **and, per the §20 closure, are now actually read** by the open-source OCR runtime that the
hosted image installs. Categories, a responsive inventory, and an understandable upload flow are in
place; a single reusable upload seam is ready for Wave 4. No security/privacy control was weakened,
one additive migration, 0 paid/live calls, no new RC.

---

## 20. OCR operational-readiness closure (addendum, 2026-09-26)

The original Wave 3 report improved OCR *failure handling* but overstated the founder P1 (G1) as
fully fixed while the environment had **no working OCR runtime** — so a scanned résumé still could
not actually be read. This bounded closure makes OCR a genuinely installable, operational capability
and validates it.

**Runtime audit.** The OCR path needs, beyond the `[ocr]` Python extra (`pytesseract`,
`pdf2image`): the **Tesseract binary**, its **language data packs** (per language), and **Poppler**
(`pdftoppm`) for scanned PDFs. `deploy/Dockerfile.api` previously installed only `curl`+`libpq5` and
`pip install ".[db]"` — so OCR was inoperable even in staging.

**Deployment fix.** `deploy/Dockerfile.api` now installs `tesseract-ocr`,
`tesseract-ocr-{deu,fra,spa,ita,por,nld}` (English ships with the base), `poppler-utils`, and
`pip install ".[db,ocr]"`. Image-size impact: **~150–200 MB**. Build not broken; health/readiness,
security hardening, private storage and malware fail-closed are unchanged.

**Truthful availability.** `is_available()` now runs the Tesseract **binary**
(`get_tesseract_version()`) rather than trusting the Python import; scanned-PDF OCR additionally
requires `pdftoppm`. `src/documents/ocr.py::ocr_runtime_status()` reports safe operational metadata
(no paths/binaries/secrets), surfaced at `GET /api/v1/admin/providers → ocr`: `available`,
`pdf_ocr_available`, `poppler_available`, and per-locale `configured` vs `runtime_available`.

**Language status (not collapsed):**
| Locale | CONFIGURED | RUNTIME AVAILABLE (local validation host) | DETERMINISTICALLY TESTED | LIVE/HUMAN QUALITY |
|---|---|---|---|---|
| en | ✅ | ✅ | ✅ (smoke) | ❌ UNVALIDATED |
| de | ✅ | ✅ | ✅ (smoke) | ❌ UNVALIDATED |
| fr/es/it/pt/nl | ✅ | ✅ (packs installed) | ⚠️ via shared engine path | ❌ UNVALIDATED |

**Real local validation (open-source; 0 paid calls).** With `brew install tesseract tesseract-lang
poppler` + the `[ocr]` extra, a real end-to-end smoke passed: an English **PNG** and an **image-only
PDF** and a **German PNG** were each **routed to OCR → text extracted → status review_required/ready
→ origin=`ocr` → page/section provenance → deterministic claims → review state pending**, and
**reprocess** recovered a document. Tesseract 5.5.3; packs eng/deu/fra/ita/nld/por/spa present.

**Deterministic tests (CI-portable, no binary required).** `tests/test_documents_pipeline.py` adds:
binary-vs-import detection, Poppler guard → `ocr_unavailable`, `ocr_runtime_status` shape +
per-language availability, all-unavailable-when-binary-absent. A **real** smoke test
(`test_real_local_ocr_reads_synthetic_image`) runs where the runtime is installed and **auto-skips**
otherwise (reported separately from the deterministic tests).

**Can a scanned résumé now actually be processed in the supported runtime?** **Yes** — the hosted
image installs the exact runtime, and the identical open-source engine reads scanned image/PDF
résumés end-to-end (validated locally). The remaining caveat is **live/human accuracy on real-world
scans**, which stays UNVALIDATED.
