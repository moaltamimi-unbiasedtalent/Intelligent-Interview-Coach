# W12.4A: Knowledge Base Accessibility & Operations (implementation and runbook)

**Outcome: CODE FIX COMPLETE. LOCAL ENVIRONMENT NEEDS OPERATOR ACTION for the Admin-governed part only (nothing governed has been registered yet and no job worker is running).** The curated knowledge base itself is intact and is reachable again from any launch directory.

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

## R-1 resolution (W12.4A-R1)
**Status: R-1 FIX COMPLETE. OPERATOR CLOSURE PENDING** (W12.4A is not marked complete by this change; closure waits for this fix to merge, a re-check of merged main in the normal environment, and the operator-closure documentation to be refreshed and merged).

- **Symptom.** In the owner's developer environment a synthetic governed source went through the whole lifecycle (it first failed with `scan_unavailable`, was reprocessed, parsed, approved, indexed, activated; real retrieval, the Admin retrieval test and the candidate boundary all worked), yet readiness read **Degraded** with a healthy corpus.
- **Root cause.** `KnowledgeReadinessService._decide` treated `failed_job_count`, the number of failed Knowledge job rows **ever recorded**, as a current problem. A failed job row is history and is never removed, so one recovered failure kept the corpus Degraded forever.
- **Old rule.** An active corpus was Degraded if any failed version, **any failed job row at all**, or pending work without a fresh worker existed.
- **New rule.** Readiness describes CURRENT state. An active corpus is Degraded only for a current unresolved condition: a version currently in a failed state, an index whose vector removal failed (`removal_failed`), an active version without a built index record or with fewer chunks in the store than recorded, or pending work that no fresh worker can progress. Store, collection, embedding-provider and configuration problems keep their own states exactly as before, and `index_failed` still takes precedence when nothing is active and a version is failed.
- **History is kept.** No job was deleted, rewritten or hidden and no audit history was touched. `failed_job_count` is unchanged in the API and is now purely informational (history). No new field, no schema or migration change, no frontend change.
- **Regression coverage** (`tests/test_knowledge_readiness_w12_4a.py`): `test_r1_root_cause_a_recovered_failure_does_not_degrade_a_healthy_active_corpus` reproduces the operator sequence with the real worker (parse fails with `scan_unavailable`, the failed row is stored, reprocess succeeds, index, activate, retrieval succeeds, historical failed jobs greater than 0, readiness Ready) and **fails on the pre-fix rule** (`degraded` instead of `ready`). `test_r1_recovered_then_retired_reads_no_active_sources_not_degraded` proves recovered then retired gives No active sources while the curated corpus keeps candidate retrieval ready. `test_r1_a_genuinely_unresolved_failure_still_degrades_or_fails` proves a currently failed version beside a healthy active source, a failed index removal and a failed version with nothing active still give Degraded, Degraded and Index failed.
- **Normal developer environment (read-only check).** Governed status No active sources; candidate retrieval ready Yes; curated knowledge base available with 14,087 chunks; 0 active real governed sources; 1 retired synthetic validation source retained as history; the historical failed scan job is still counted (`failed_job_count` 1) and does **not** force Degraded.
- **Unchanged on purpose.** The data-root resolution, Mo's shared retrieval wiring, curated and governed fusion, collection names, the indexing pipeline, the worker design, the embedding provider, the lifecycle gates, retrieval relevance behaviour, provenance labels and authority levels. **The scanner limitation is unchanged:** governed uploads still fail closed with `scan_unavailable` unless a real scanner (for example ClamAV) is configured; the `fake` scanner is development-only and is not a normal runtime path.

### One-time developer database lineage reconciliation (wording to preserve)
The earlier developer-database repair was a **ONE-TIME DEVELOPER DATABASE LINEAGE RECONCILIATION, not the normal Ask4Mo migration procedure.** The developer database had been built by `create_all` (revision 0014, 224 objects, SHA-1 `81eef347…`) and already contained the later tables, so a normal `alembic upgrade head` could not run. The only missing schema was two step-up columns on `auth_sessions` and two audit triggers. The approved procedure was an SQLite online backup, a rehearsal on a copy, adding only that project-owned DDL, verifying unchanged row counts and a match against a fresh head schema, and stamping the truthful schema to head (revision `0025_security_audit_incidents`, 226 objects). Correctly versioned databases continue to use normal Alembic migrations.

### Developer baselines (at rest)
Developer database `5295ceb94858feb035e141d06e1f6ef7709cac29` (226 objects, revision 0025) is the accepted baseline set at the end of the operator verification. Starting the runtime again changes the database bytes legitimately (worker registrations and heartbeats, operational metrics, audit events, the retired validation source's history), so a later at-rest measurement differs without any contamination: on the day of this fix the at-rest hash was `91c07dc957c28481a29625cce0e5883be3ea81bc` after four worker registrations, with the schema (226 objects, revision 0025, integrity ok), the 11 accounts and the 46 interviews unchanged. Chroma `85fc95aafb483a8ea78c4829843560aa75928a31` (collections `career_knowledge_base` with 14,087 chunks and an empty `governed_knowledge`), checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`, research cache `25264b17b36f7a365ff8dfaca9eec97e997ee710` and `evaluations/` `67259aba185daa495f8bf8958e1c905fd086b2be` are unchanged. Because a running worker always changes the database file, future waves should treat the database invariants (revision, object count, row counts of accounts and interviews) as the check and the byte hash only as an at-rest reference.

### Protected-store checks: snapshot versus invariant
Two kinds of check must not be confused.

- **Immutable or quasi-immutable stores** (committed data, tests, evaluators, synthetic qualification runs): these must use isolated storage and must leave the developer stores byte-identical. A changed hash here is contamination and fails the run.
- **Mutable operational stores** (the developer database, and Chroma once governed sources are intentionally indexed or retired): operating the application legitimately changes their bytes (audit events, jobs, worker heartbeats, metrics, notifications, governed index history). The exact file hash is a **snapshot** taken at rest, not a permanent invariant.

For the developer database, safety verification therefore prioritises: the expected database path and identity, the Alembic revision, the schema object count, `integrity_check`, the expected critical tables and triggers, preservation of accounts and interviews, explained row-count changes, no unexpected schema mutation and no unexpected candidate-data deletion or corruption. For Chroma it uses the collection inventory, the curated chunk count, the governed collection state and explained corpus changes, alongside hash snapshots. This does **not** weaken contamination protection for tests, evaluators or synthetic qualification runs, which still use isolated storage.
