# P10B-W10.8 - Knowledge Base & RAG Administration

**Status:** **COMPLETE** (merged in PR #121, main `35eee19`). **W10.10 is NOT STARTED.**
One additive migration (`0019_knowledge_admin`). No new dependency. 0 paid/live calls.
**Invariant: unapproved knowledge never enters candidate retrieval.**

## 1. Starting point
`main` `f059668070d740b33b2c0b86d0e819c8ee1408ed` (W10.9 merged, PR #120), clean tree, Alembic head `0018_jobs`.

## 2. Branch
`feat/p10b-w10-8-knowledge-rag-admin`.

## 3. Existing corpus audit
| Source | Language | Authority | Provenance | Licence known? | Indexed? | Candidate-retrievable? | W10.8 action |
|---|---|---|---|---|---|---|---|
| Legacy/bootstrap corpus: curated documents under `data/raw` indexed by `scripts/build_index.py` into Chroma collection `career_knowledge_base` | mostly en | per-source in `data/source_manifest.json` (`authority_level` 1 to 3, validated) | manifest (publisher, URL, reference year) | partially (manifest metadata; no machine-readable use-rights class) | yes, when built locally (git-ignored, generated) | yes, through the hybrid retriever | **None.** Left untouched; outside the new lifecycle |
| Structured governed stores (roles, compensation, competencies, labour market, K1 to K4 datasets) | per dataset | per manifest | manifest + dataset provenance | partially | structured SQLite stores, not vector | yes, through the structured retrieval lanes | None |
| Admin-uploaded knowledge (new) | 7 KB languages | 1 to 3, set by the reviewer | required at approval | required class, activation gated | only after approval, into `governed_knowledge` | only when explicitly activated | **New governed pipeline** |
Local files are not assumed approved. Source versions are tracked in the manifest (`reference_year`); checksums and activation states exist only for the new governed sources.

## 4. RAG write-path audit
Direct vector-write paths found: `scripts/build_index.py` (`store.reset()` and `add_chunks` into `career_knowledge_base`), `scripts/eval_expanded.py` (in-memory store), the evaluation harnesses (read only), and the structured-store builders (SQLite, not vector). No product code path wrote to the vector store before W10.8. The only new write path is `knowledge_admin.runtime.run_index`, which writes ONLY to the separate `governed_knowledge` collection after human approval. The legacy CLI is unchanged and is not reachable from Admin.

## 5. Legacy/bootstrap corpus decision
Not backfilled, not deleted, not reindexed. It is documented as the legacy managed baseline and stays outside the upload lifecycle (a backfill would fabricate approver timestamps). Governance applies to everything uploaded through Admin.

## 6. Domain model
`knowledge_sources` (id, public_id, title, created_by, timestamps); `knowledge_source_versions` (immutable version with state, language, authority level, publisher, source reference, provenance note, licence class, original file name, opaque storage key, media type, size, SHA-256, scan status and scanner, bounded preview, extracted size, chunk count, failure stage and category, linked job ids, approval/rejection/index/activation/retirement evidence); `knowledge_index_records` (collection, embedder, chunk count, built/removed/removal_failed). Governance metadata lives on the version so an approved version's evidence is never silently changed.

## 7. Lifecycle
queued -> processing -> review_required -> approved -> indexing -> indexed -> active -> retired; plus rejected and failed. Parsed is not approved, approved is not indexed, indexed is not active. Transitions are enforced server-side (a legal-transition table plus guarded `UPDATE ... WHERE state = expected`).

## 8. Approval-before-retrieval invariant
Three independent layers: (1) nothing is embedded or written to any vector collection before approval (the index job runs only for a version in `indexing`, which only an approved version can enter); (2) approved content stays non-retrievable until explicit activation; (3) the retriever reads the ACTIVE set from SQL on every call and returns only hits whose version is in it, so even physically present chunks are invisible unless active.

## 9. Staging vs active strategy
Option A for approval (no embedding before approval) plus a separate collection `governed_knowledge` that never shares a namespace with the legacy corpus. Activation is a control-plane (SQL) switch, not a vector move. There is no BM25 channel over the governed collection (it would index everything and bypass the gate).

## 10. Source types
Uploaded PDF, plain text and Markdown only (the existing tested parsers). The source URL is a reference string (https only) and is never fetched. No crawler, no remote ingestion, no DOCX, no images/OCR.

## 11. Upload security
Allowlisted extensions (pdf, txt, md); 5 MB cap with a bounded read; display file name sanitised (path components removed) and never used as a path; opaque random storage key under a private root (traversal-checked by the existing store); content sniffing (PDF magic; text must be NUL-free UTF-8); executables rejected by allowlist; authorised routes only; deletion removes the stored file; validation errors never echo content.

## 12. File-type policy
pdf, txt, md. Others are rejected with a safe message.

## 13. Malware / ClamAV semantics
Scanning is MANDATORY for knowledge, through the existing scanner abstraction (`enforce_scan(required=True)`) in the parse job. Outcomes: `scan_passed` (a real scanner ran), `scan_failed` (flagged: the version fails and never reaches review), `scan_unavailable` (no real scanner, including the dev NullScanner: the version fails with `scan_unavailable`, never treated as clean; after configuring a scanner an operator reprocesses it). Approval requires `scan_passed`. There is no bypass. In QA and tests the existing `fake` scanner was used; the ClamAV adapter remains live-unvalidated.

## 14. Checksum / dedupe
SHA-256 of the bytes. The same bytes for the same source are rejected as a duplicate (HTTP 409 naming the existing version); a database unique constraint (source, checksum) backs it. The same file under a different source is allowed. File names never decide identity.

## 15. Versioning
A change is a new immutable version (v2, v3...). Approved evidence is never edited: metadata is editable only before approval. At most one ACTIVE version per source (partial unique index). Activation switches atomically in one transaction: the previous active version becomes retired and the new one active.

## 16. Provenance
Required to approve: publisher and provenance note (unknown provenance blocks, fail-closed); source reference optional. The approver and time are recorded and constrained (an approved/indexed/active version must have both).

## 17. Licence / use-rights classification
Engineering classes, not legal advice: public_official, explicit_permissive, internal_owned, permission_recorded (activatable) and unclear, restricted (never activatable). Default on upload is `unclear`. No free-text legal approval exists. No compliance claim.

## 18. Authority levels
Exactly the repository semantics: 1 official/statistical, 2 public/professional framework, 3 reputable industry. Database CHECK and API validation reject any other value; the UI shows the meaning, not just the number. Pinned by tests and the evaluator.

## 19. Language boundary
The 7 knowledge/document languages (en, de, fr, es, it, pt, nl). Anything else, including Russian, is rejected at the API and by a database CHECK. Russian remains an interface and Mo conversation language only. The Admin UI is English-only.

## 20. Parsing
In a W10.9 job (`knowledge_parse`), never in the HTTP request: verifies the checksum, scans, parses with the existing parsers, stores a bounded preview (4000 characters) and the extracted length; the full text is never stored.

## 21. W10.9 job integration
Three code-defined job types: `knowledge_parse`, `knowledge_index`, `knowledge_remove_index`. Payload is a version public id only (strict schema); not Admin-enqueueable directly; retry classified per the framework. The worker receives the knowledge runtime (document store, scanner, governed store factory). On a job's last attempt the domain state is set to `failed` so a version never stays in `processing`/`indexing`.

## 22. Parse idempotency
A guarded state check makes a replay after success a no-op; the preview and size are checksum-anchored and overwritten with identical values; nothing is appended.

## 23. Index idempotency
Chunk id = SHA-256(version id + chunk text) via the existing chunker; the store skips ids already present, so a replay or a partial-then-retry never duplicates; the index record is an upsert; an index job for a version not in `indexing` does nothing.

## 24. Crash-window replay
Tested: the worker claims the index job, writes every chunk, and dies before completing; the lease expires; another worker replays; the collection still holds exactly one copy of each chunk and the version ends `indexed` (job attempts 2). A partial-write-then-failure retry is also tested.

## 25. Embeddings boundary
Production uses the configured embedder via the store (local hashing by default; OpenAI only with a dedicated key). All tests use the offline `LocalHashEmbedder`; no embedding provider is contacted in qualification.

## 26. Chunking
The existing chunker and settings are unchanged (1000 characters, 150 overlap). Governed chunks carry source id, version id, title, authority, publisher, language, version number and the source reference. No Admin-internal data, storage key, checksum or provenance note enters chunk metadata.

## 27. Citation metadata
An active hit retains title, publisher, authority level, language, version, source reference and ids, so the existing citation logic can show them. The existing semantics (sources shown when career evidence is used) are unchanged and no claim is made that every answer is cited.

## 28. Retrieval enforcement
`GovernedKnowledgeRetriever` (control-plane active set per call). It is wired additively into the candidate Career service: when no governed version is active it returns nothing and legacy retrieval is byte-for-byte unchanged; hits are fused with the existing results by the same RRF. Tested for each state: queued, parsed, approved, indexing, indexed, rejected, retired and unsupported-language are never returned; active is; replays do not duplicate.

## 29. Version activation consistency
Sequence: index v2 first, then one SQL transaction activates v2 and retires v1, then the old vectors are removed by a job. SQL and the vector store cannot share a transaction, and no cross-store atomicity is claimed: retrieval trusts SQL, so there is never a mixed-version window in answers, and a stray chunk is invisible.

## 30. Vector-store failure semantics
An indexing failure keeps the version inactive with a safe category (`unavailable`), is retried by the framework, then marks the version `failed` at its last attempt; the Admin can retry. The candidate corpus is unchanged. A removal failure marks the index record `removal_failed` and keeps retrieval closed.

## 31. Delete vs retire
Retire = stop retrieval now (control plane), keep history, remove vectors by job. Hard delete = only never-approved, never-indexed versions (queued, review, failed, rejected): removes the record and the stored file. The UI copy distinguishes them.

## 32. Source removal
Retiring an active version excludes it from retrieval immediately from SQL state, even if physical deletion is delayed or fails (tested).

## 33. Admin list/detail
`/admin/knowledge` (filters: state, language, authority, licence, active, search; pagination; upload for managers) and `/admin/knowledge/{source}` (versions, provenance and use rights, safety and parsing, preview, approval/index/active, blockers, related job links, actions, recent audit). English only, VerifiedLink navigation.

## 34. Preview
Bounded (4000 characters) extracted text rendered as plain text in a `<pre>` via React text nodes: markup is displayed, never executed (tested with a script tag). No HTML rendering, no binary viewer, no chunk or vector browser.

## 35. Approval / rejection
Approve requires `platform.knowledge.approve`, a confirmation dialog, state review_required, a passed scan, publisher and provenance, a permitted licence, supported language and authority, and extracted text. One approver (no two-person rule: W10.0 requires it for model activation, not knowledge). Reject takes a reason category. Audited atomically with the state change; audit holds ids, states and the reason category only.

## 36. Indexing / activation
Indexing is an explicit separate action (`platform.knowledge.manage`) that enqueues a job; it never auto-activates. Activation (`platform.knowledge.approve`) requires an indexed, approved version with a complete index and permissible provenance and licence.

## 37. Permissions
Existing canonical permissions only (registry stays 43): read, manage (upload, edit before approval, index, retire, reprocess, delete) and approve (approve, reject, activate). `knowledge_admin` holds all three; `platform_admin` read only; support, billing, operations and security presets hold none of manage/approve.

## 38. Candidate-private-data boundary
The module imports no candidate tables or repositories; no route reads CVs, answers, chats, memories or tickets; nothing candidate-derived is ever ingested; there is no vector/chunk browser. Evaluator and tests enforce it.

## 39. Prompt-injection / content safety
Uploaded text is untrusted data: stored and previewed as text, never executed, and never sent to a model during ingestion. A fixture with "ignore previous instructions" and a script tag is processed as ordinary content, returned only as evidence text, and still flagged by the existing injection guard. No claim of complete prevention. Title, publisher and note are length-bounded, rejected if they contain control characters, and rendered as text.

## 40. Migration
`0019_knowledge_admin` (from `0018_jobs`): three tables with CHECKs (authority 1 to 3, language, licence, scan status, state, checksum length, version, approval-evidence), unique (source, version), unique (source, checksum), the one-active partial unique index and list indexes. It never touches Chroma. Fresh, from-0018, constraint and round-trip tests pass.

## 41. Backend tests
**2778 passed, 4 skipped, 0 failed, 0 errors** (baseline 2748/4). 30 new tests in `tests/test_knowledge_admin_w10_8.py`. Skips: live Adzuna, Streamlit render, RAGAS and the PostgreSQL job-claim test (needs `TEST_POSTGRES_URL` and a driver, as documented in W10.9).

## 42. Frontend tests
672 unit tests in 82 files (12 new for knowledge): list, filters, pagination, authority meanings, states, upload form errors, provenance, safe preview, approve/reject, state-limited actions, blockers, job link, read-only role, no role names. Typecheck, lint and build clean.

## 43. Playwright
**209 passed** (208 baseline plus the knowledge journey), serial, no retries or timeouts changed. Honest boundary: the journey uses a stateful network stand-in with the test playing the worker; the real lifecycle with a real worker, scanner and Chroma is proven by the backend API+worker test and the manual QA below.

## 44. Evaluators
**34 of 34** CI evaluators pass including the new `scripts/eval_admin_knowledge.py` (29 checks). Only the CI set was run; `evaluations/` stays untouched.

## 45. Manual QA
Fresh migrated database, API and a separate worker process, real persistent Chroma in a temp directory, local hashing embedder, fake scanner, Markdown fixture containing an injection line and a script tag. Upload stayed `queued` until the worker ran; parse produced a 343-character preview with `scan_passed`; governed retrieval returned nothing while parsed, approved and indexed (collection already held 4 chunks while indexed); after activation retrieval returned 3 hits with title and authority; retire excluded it immediately and the removal job emptied the collection; Command Center counts and 5 audit rows (ids and states only) matched; job rows for parse, index and removal succeeded; no response contained document text beyond the bounded preview; the developer Chroma collection list was unchanged. No paid or live call.

## 46. Performance
First Load JS: `/admin/knowledge` 117 kB, `/admin/knowledge/[id]` 122 kB, shared 103 kB unchanged. The list is one query using a window function to pick each source's current version (active first, else highest) with filters and paging; list rows carry no preview or text. Detail loads on demand. Fixture: 4 chunks; indexing completed within the worker's poll interval using the offline embedder (not benchmarked further).

## 47. Dependencies
None.

## 48. Alembic head
`0019_knowledge_admin` (single head).

## 49. Open items
SEC-W10-04 (W10.10), SEC-W10-05 (W10.11), PRIV-W9-01 and PRIV-W9-02 (W10.10) remain OPEN.

## 50. W10.10 handoff
W10.10 can register privacy/DSAR job types on the same registry, reuse the parse/approve evidence patterns and the guarded-transition style, and keep Knowledge administration unchanged.

## 51. External calls
0 paid or live provider calls.
