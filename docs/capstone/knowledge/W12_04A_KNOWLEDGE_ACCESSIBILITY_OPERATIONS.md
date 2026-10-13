# W12.4A: Knowledge Base Accessibility & Operations (implementation and runbook)

**Outcome: CODE FIX COMPLETE; NORMAL ENVIRONMENT OPERATOR ACTION EXECUTED AND VERIFIED (section 11), with one residual defect R-1 (readiness reads Degraded after a recovered failed job) holding closure open.** The curated knowledge base is intact and reachable from any launch directory.

- Starting point: `main` at `f35d5b356e6174278e9619ed37cdf7bbf6ed4c70`.
- Paid or live calls: **0**. The retrieval test calls no model. No migration. No new permission (the 43 are unchanged).
- Protected developer stores: fingerprinted before and after, identical. All implementation testing used a throwaway database, a throwaway persistent Chroma directory, the offline `local-hash-v1` embedder, the fake scanner and synthetic content.

## 1. Owner symptom, evidence and root cause
**Symptom (owner-reported):** the Knowledge Base is inaccessible or not working as expected in the normal environment.

**What I could and could not observe.** I did not see the owner's screen. I reproduced the mechanism below deterministically, and I found the same artefact in the environment the owner was given: every demo launch in this programme started the API from `/tmp/ask4mo_run`, which now contains a `data/cache` directory created relative to that working directory (the research cache), proving the app resolved its stores against the launch directory. If the owner saw a different symptom, the code fixes below still stand, but this is the one reproduced.

**Root cause 1 (code and environment, the reproduced one): every default store path was relative to the process working directory.** `data/chroma`, the five structured SQLite stores (`data/knowledge/roles.db`, `compensation.db`, `competencies.db`, `labour_market.db`, `credentials.db`), the source manifests, the build metadata, the research cache and the default application database URL (`sqlite:///data/interview_studio.db`) were all relative strings. An API, worker or script started from any directory other than the repository root silently saw an EMPTY knowledge base (the structured coordinator documents that missing stores are "simply absent"), and an API and a worker started from different directories used different stores and different databases.

Reproduction (read-only, from an unrelated directory):

| Check | Before the fix | After the fix |
|---|---|---|
| Chroma directory found | no (resolved under the launch directory) | yes (anchored to the repository data root) |
| Structured stores found (of 5) | 0 | 5 |

**Root cause 2 (code, architecture bridge): Mo's agent was not connected to Admin-governed knowledge.** `get_agent_service` built `AgentApplicationService` without a career service, so the agent created its own default one with no governed retriever and its own store. The deterministic `/career/chat` path used the governed retriever; Mo's `SearchCareerKnowledge` (the normal Prepare path) never did. Admin-activated knowledge therefore could not reach Mo.

**Contributing factors.**
- The failure was silent: no readiness, no active inventory, no retrieval test, no worker or store state anywhere in Admin.
- `get_governed_retriever` swallows build errors and returns `None`, with nothing surfaced to an operator.
- Indexing depends on a separate worker process whose absence was visible only on the Jobs page.

**Why existing tests missed it.** Every test ran with the working directory at the repository root and with injected stores or services; none started a process elsewhere. `eval_admin_knowledge` proved the governed retriever's gate, not that the agent was wired to it.

**Classification:** multiple: code (agent wiring), environment and deployment (working-directory-relative defaults), architecture (two knowledge systems with an incomplete bridge), and operability (no visibility).

**The two knowledge systems, stated plainly.** (A) the **curated knowledge base**: the legacy Chroma collection `career_knowledge_base` (about 14,000 chunks in the developer store) plus five structured SQLite stores, built by the ingestion tooling; (B) the **Admin-governed knowledge**: collection `governed_knowledge` in the same Chroma directory, controlled by the SQL lifecycle. They are **fused at retrieval** by reciprocal rank fusion (curated hybrid vector and BM25, plus governed vector, gated by the SQL active set). This is not consolidation into one store, and it does not need to be: the invariant that matters is that both are read by the same retrieval boundary, which is now true for `/career/chat` and for Mo.

## 2. What was changed
1. **Data root.** `src/copilot/constants.py` defines `REPO_ROOT`, `DATA_ROOT` (the repository `data/` directory, or `COPILOT_DATA_DIR` when set) and `data_path()`. All store defaults derive from it and are absolute. The default application database URL, the research cache, governed datasets, build metadata and status paths are anchored the same way. `COPILOT_CHROMA_DIR` and `DATABASE_URL` still override explicitly.
2. **Agent wiring.** `get_agent_service` passes `get_career_service(request)`, so Mo's retrieval uses the shared curated store and the governed retriever.
3. **Readiness (derived, no migration):** `src/knowledge_admin/readiness.py`.
4. **Admin API (permission `platform.knowledge.read`, no new permission):** `GET /api/v1/admin/knowledge/readiness`, `GET /api/v1/admin/knowledge/active`, `POST /api/v1/admin/knowledge/test-retrieval`.
5. **Admin UI on `/admin/knowledge` (no new destination):** a Knowledge readiness section, an Active knowledge inventory, a Test retrieval panel, a truthful empty state, and a worker hint on a source that is waiting on a job.

## 3. Readiness states
`ready`, `no_active_sources`, `worker_unavailable`, `index_pending`, `index_failed`, `store_unavailable`, `collection_missing`, `embedding_provider_unavailable`, `configuration_error`, `degraded`.

READY requires: at least one **active** version, with a **built** index record, whose chunks are physically present in the store the candidate retriever reads (store chunk count at least the recorded chunks), a usable embedder, a persistent store, and no failed build or stalled job. A source, a directory, an open Chroma or a job record is never enough. The response also reports `candidate_retrieval_ready` (curated corpus available, or governed ready), the worker state from heartbeats only (`available`, `stale` after 60 seconds, `none`), the collection state, the embedder state (local, or remote "configured, not tested"), and the last failure category. It never returns a path, a secret, a vector, a raw provider error or candidate data; the store location is reported only as `default` or `configured_override`.

## 4. Admin retrieval test
`POST /admin/knowledge/test-retrieval` accepts **only** `{ "query": "<1..300 characters>" }` (any other field is rejected). It calls `CareerApplicationService.search_knowledge`, the same boundary the agent's `SearchCareerKnowledge` uses, so it exercises query translation, the safety screen, hybrid and governed retrieval, fusion and citations. It makes **no LLM call and no answer**. It returns status (`evidence_found`, `insufficient_evidence`, `blocked`), counts, retrieval mode and lane, a latency bucket, source metadata labelled `admin_governed` or `curated`, and up to five 240-character excerpts of platform knowledge. No chunk ids, scores or vectors.

Known limitation (existing behaviour, not changed): the production pipeline has no relevance cutoff for unfiltered queries, so an irrelevant query can still return the nearest chunks. The test reports what retrieval returns; it is not a relevance judgement.

## 5. Governance invariants (proven through the production boundary)
Unreviewed, rejected, approved-but-not-indexed, indexed-but-inactive, retired and failed-index versions are **not** retrievable (even when their chunks physically exist in the store); an active approved indexed version is. Retire takes effect immediately. Re-running the real index handler for the same version does not duplicate chunks (deterministic chunk ids).

## 6. Evidence
- **Root-cause regression tests** (fail on the pre-fix code, pass now): `test_root_cause_default_store_paths_do_not_depend_on_the_working_directory` and `test_root_cause_mos_agent_retrieval_uses_the_governed_retriever_and_the_shared_store`. Supporting: `test_data_root_can_be_relocated_explicitly_for_an_isolated_instance`, `test_an_explicit_chroma_override_still_wins`.
- **Isolated end to end** (`test_isolated_end_to_end_source_to_index_to_activate_to_retrieve_to_retire`): synthetic source, real worker parse, approve, real worker index (chunks greater than 0 and equal to the store count), activate, readiness READY, Admin retrieval test, the candidate boundary returning the same source, retire, and the same query returning nothing. No LLM, no network, no paid call.
- Readiness states, active inventory shape, no-paths and no-secrets checks, role access (candidate, support, billing, operations denied; Knowledge Admin and Platform Admin allowed), override rejection and the route-contract guard: `tests/test_knowledge_readiness_w12_4a.py` (32 tests).
- Frontend: `tests/knowledge-readiness-w12-4a.test.tsx` (10 tests) and a Playwright test covering the owner and the Knowledge Admin.
- Two existing route-contract guards were updated on purpose: the Knowledge route allowlist now names the three new read-only routes, and the mutation-audit invariant exempts the retrieval test (a read-only POST). The schema guard now bans embedding **content** fields rather than the word "embedding", because readiness reports the embedder identity.

## 7. Normal local environment (read-only verification)
Developer database: the knowledge control-plane tables exist and are **empty** (0 sources, 0 versions, 0 index records, 0 jobs, 0 workers). Developer Chroma: collection `career_knowledge_base`, 14,087 chunks, 512 dimensions (consistent with the offline local embedder, since no dedicated embedding key is configured); the `governed_knowledge` collection does not exist yet. The five structured stores and the governed datasets exist. The developer database's recorded migration revision is `0014_opportunities`, behind the repository head; the Admin overview will say so.

Interpretation: with the fix, an app launched from any directory finds the curated corpus. **Operator action still required for the Admin-governed part:** register and approve a real source, start the job worker (`python -m src.jobs.worker`, same repository and same `DATABASE_URL`/`COPILOT_DATA_DIR`), index and activate. The protected stores were not mutated to make anything green.

## 8. Operator startup and check sequence
1. Start the API from anywhere (stores are anchored). To isolate a demo instance, set `COPILOT_DATA_DIR` (and, for the application database, `DATABASE_URL`) to a throwaway directory.
2. Start the worker with the **same environment**: `python -m src.jobs.worker`.
3. Open `/admin/knowledge`: read **Knowledge readiness**. If it is not Ready, use the troubleshooting tree below.
4. After activating a source, run **Test retrieval** with a harmless query that the source should answer.

## 9. Troubleshooting tree
| Symptom | Likely cause and action |
|---|---|
| `/admin/knowledge` will not open | Authorization or API: the account needs `platform.knowledge.read`; a candidate is denied by design |
| Sources empty | No governed sources registered: this is "No active sources", not an error |
| A source stays queued | No job worker: start it (readiness says "Indexing worker unavailable") |
| Index failed | Read the failure category on the source; fix the cause, then retry indexing |
| Indexed but not retrievable | Not activated, or the collection is empty or missing in the store the API reads (check the store location and the embedder) |
| Retrieval returns nothing | Nothing active for that topic, an irrelevant query, or a blocked query; the test says which |
| Everything empty after launching from another folder | Fixed by the data root; if an old build is running, restart from this version |

## 10. Limitations and residual items
Governed knowledge still depends on a worker; there is no snapshot or rollback model; the retrieval test has no relevance judgement; Russian is not a knowledge-base language and no corpus scope was expanded (P10C is not started). A deployment that relied on relative `data/` paths with a different working directory must set `COPILOT_DATA_DIR`. The developer database's migration revision lag is unchanged. W12.4B to W12.4F, W12.5, integrated requalification, RC-P10-004 and P10C have not started; AC-24 remains PARTIAL.

## 11. Operator closure (W12.4A-OPS, 2026-10-13)
**Status: OPERATIONALLY VERIFIED IN THE NORMAL DEVELOPER ENVIRONMENT, WITH ONE RESIDUAL DEFECT (R-1 below). W12.4A is therefore not yet marked COMPLETE.** This section records that operator action was required and what it did. No product code was changed in this wave.

- **Merged identity.** PR #150, feature commit `4cc478588d30b04696d16b6f4b362053d3c482a0`, merge commit `cb0d59df95c03115c48929edb9bb0883a11b8ee7` (`main`).
- **Old runtimes.** A Next.js dev server on port 3015 and an API on port 8020 were running an older build with `API_ENV=staging`, a throwaway database (`/tmp/ask4mo_walkthrough.db`) and the working directory `/tmp/ask4mo_run`. Only those two Ask4Mo processes were stopped. No job worker was running.
- **Developer database lineage (the finding that mattered).** The developer database recorded Alembic revision `0014_opportunities` but already held every later table: it had been built by `create_all`, which adds missing tables and never alters existing ones, and `alembic_version` was never advanced. A plain `alembic upgrade head` therefore fails on the first already-existing table (verified on a copy). Comparing it with a fresh head schema showed the only real drift was the two step-up columns on `auth_sessions` (`elevated_at`, `elevated_until`) and the two append-only audit triggers; every other difference was a cosmetic server default. The current runtime reads the `auth_sessions` columns, so it could not have run correctly against this database.
- **Backup first.** A SQLite online backup was written outside the repository to `~/Downloads/ask4mo-operator-backups/interview_studio.pre-0025.20261013T203118.db` (integrity ok, revision 0014, 224 objects). Source SHA-1 at that point `81eef3479704ed91e58abb876926f98108968842`.
- **Reconciliation, not recreation.** On a copy first, then on the developer database with no writer running: add the two missing `auth_sessions` columns and install the two append-only triggers using the project's own DDL function, then `alembic stamp head`. Nothing was dropped, recreated or reseeded; row counts were identical before and after (11 users, 46 interviews, 2 opportunities, 5 memories). The result matches a freshly migrated head schema (tables, columns, foreign keys, index names and triggers). Revision is now `0025_security_audit_incidents` (single head), 226 schema objects, integrity ok. This is **not** a plain `alembic upgrade head`, which is impossible for this database; it is recorded here so it is not mistaken for one.
- **Canonical data root.** From the repository root, `/tmp` and `/private/var` the data root, Chroma directory and database URL resolved identically (`<repo>/data`). The API was started from an unrelated directory with `COPILOT_DATA_DIR` set and created nothing in that directory.
- **Worker.** `python -m src.jobs.worker` with the same environment registered and reported a current heartbeat; the Admin readiness showed the worker as available.
- **Admin access.** `/admin/knowledge` loaded for a platform admin with no 403, no 500 and no console error. Readiness read `No active sources` with `candidate retrieval ready: Yes` (curated knowledge base available), exactly as designed.
- **Curated corpus.** Chroma collection `career_knowledge_base`, **14,087 chunks**, readable; all five structured stores load (the structured role and forecast lanes returned evidence from ESCO, ISCO-08 and BLS Employment Projections for role and outlook queries). Retrieval went through the production boundary with no model call. The vector lane opens and returns neighbours, but the offline local-hash embedder is lexical, so some narrative queries correctly report insufficient evidence (existing behaviour, not a defect of this wave).
- **Mo.** On the real data root, Mo's career service and the `/career/chat` career service both use the same shared curated store (14,087 chunks) and the same governed retriever.
- **Governed pipeline, using one clearly labelled synthetic source** (`[Operator validation - synthetic]`, harmless text, `internal_owned`, authority 3, provenance stating it is synthetic and to be retired). Counts before: 0 sources, 0 versions, 0 jobs, 0 workers. Upload, scan and parse, review, approve, index (the real worker, 2 chunks, embedder `LocalHashEmbedder`, collection `governed_knowledge`), activate. While indexed but not active it was **not** retrievable. After activation readiness showed one active, indexed source; the Admin retrieval test and the candidate boundary both returned that source and no other governed source. After retire, the source and its chunks were removed from the store by the worker, the Admin test and the candidate boundary no longer returned it, and readiness returned to `No active sources`. The retired source and its index record remain as lifecycle history, still marked synthetic. No Chroma file or row was edited by hand.
- **Scanner finding (operator action).** The first parse failed with `scan_unavailable`: in the developer environment `FILE_SCAN_PROVIDER` is unset, so the scanner is the null scanner and governed uploads fail closed by design (no ClamAV is installed). To finish the validation the worker was run once with the **development-only `FILE_SCAN_PROVIDER=fake`** scanner (it flags only the EICAR test string; it is **not** a malware scan) and the failed version was reprocessed. The worker was then restarted **without** it. Real sources need a configured scanner (`FILE_SCAN_PROVIDER=clamav` with a reachable daemon); that belongs with W12.4B and W12.4F.
- **Temporary account.** A labelled `operator-validation@example.test` platform admin was created to drive the Admin API and was removed afterwards through the normal account-deletion path; the user count is back to 11.
- **0 paid or live calls.**

### R-1 residual defect (found, not fixed here)
**Symptom.** With the synthetic source active and indexed, a worker reporting and nothing pending, readiness read `Degraded`.
**Root cause.** `readiness()` counts every failed knowledge job ever recorded (`failed_job_count`) and treats any as `degraded`. The earlier `scan_unavailable` parse job had already been resolved by reprocessing, but a failed job row is history and stays, so a healthy corpus can read Degraded indefinitely.
**Why W12.4A qualification missed it.** The tests created failures by setting a version's state directly, never by a failed job that was later recovered through reprocess.
**Proposed bounded fix.** Base the degraded signal on unresolved failures only (versions still in a failed state, or an active version without a built index), keep `failed_job_count` as an informational number, and add a regression test that fails a job, reprocesses it and expects Ready. No migration.
**Effect today.** Cosmetic and conservative (it never claims Ready when it should not), but the Admin would show a misleading Degraded for a healthy corpus after any recovered failure. It is why closure is held open.

### Final normal-environment state
- **Curated knowledge base:** READY. 14,087 chunks, five structured stores, candidate retrieval working, reachable from any launch directory.
- **Admin-governed pipeline:** OPERATIONAL end to end (verified), with the scanner requirement above. **Active real governed sources: 0** (the synthetic validation source is retired). Readiness truthfully reads `No active sources`, which is not a failure.
- **Owner Knowledge issue:** resolved for the curated knowledge base and for the governed pipeline's mechanics; the residual readiness wording (R-1) and a real scanner remain.
- **Runtime left running:** API on 8020 and worker started from an unrelated directory with `COPILOT_DATA_DIR` pointing at the repository `data/`, and the current frontend on 3015 (development mode, anonymous developer identity). Sign in with one of the existing platform-admin accounts in the developer database.

### Protected-store baselines (current)
All fingerprints are taken **at rest** (API and worker stopped), because a running worker writes heartbeats to the database.

| Store | Before this wave (historical baseline) | New accepted baseline | Why |
|---|---|---|---|
| Developer database | `81eef3479704ed91e58abb876926f98108968842`, 224 objects, revision 0014 | `5295ceb94858feb035e141d06e1f6ef7709cac29`, 226 objects, revision `0025_security_audit_incidents` | Intentional W12.4A operator reconciliation from revision 0014 to 0025, then normal operation (a short-lived validation account, a worker heartbeat, a retired synthetic knowledge source) |
| Chroma | `6357c057606273f313b408cc7f144390453a0832` | `85fc95aafb483a8ea78c4829843560aa75928a31` | The empty `governed_knowledge` collection now exists beside `career_knowledge_base` (14,087 chunks, unchanged), after the synthetic source was activated and retired through the lifecycle (hash after the empty collection was created `4b61255f…`, with the source active `b6571813…`, after retirement `85fc95aa…`) |
| Checkpoint | `b56d0c39fbba64786495ebb5db59eedecfae5c71` | unchanged | |
| Research cache | `25264b17b36f7a365ff8dfaca9eec97e997ee710` | unchanged | |
| `evaluations/` | `67259aba185daa495f8bf8958e1c905fd086b2be` | unchanged | |

Earlier qualification records keep their historical hashes. Future waves compare against the new baseline once the developer database is at rest.
