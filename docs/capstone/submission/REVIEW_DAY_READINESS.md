# Review-Day Readiness and Operator Runbook (2026-10-20 review)

Prepared 2026-10-19 on branch `docs/review-day-readiness` (from `docs/p11-final-capstone-submission` `1a5e4d4`, code identical to `main` `3d1af6f` plus the demonstration script). Nothing was reset, deleted, merged, deployed or run against a provider. **No live RAGAS call was made; no provider call of any kind was made in this work.**

## 1. Discovery findings

| Item | Finding |
|---|---|
| Git state | main checkout on `docs/p11-final-capstone-submission` `1a5e4d4` (code equal to `main` `3d1af6f`) |
| The stack that showed an empty Admin Sources page | the backend I had started when asked to "launch the app with a platform admin login": process cwd `/private/tmp/ask4mo_admin` (a clean git worktree), `DATABASE_URL=sqlite:////tmp/ask4mo_admin_run/app.db` (a brand-new throwaway database) and `COPILOT_DATA_DIR=/tmp/ask4mo_admin_run/data` (empty). No sources, no indexes, no worker |
| Developer stores (`data/`, untouched) | `interview_studio.db`: Alembic revision `0027_email_attempts` (**12 revisions behind the code head `0039_speech_governance`**), 11 users, **1 governed source: a retired synthetic operator-validation note, 0 active**; Chroma collection `career_knowledge_base` with **14,087 embeddings** (the documented 14,087-chunk corpus **exists**), collection `governed_knowledge` with **0**; embeddings are 512-dimensional (the offline local-hash embedder; no provider needed); structured stores: 8,035 occupations, 23,579 aliases, 22,383 tasks, 111,455 occupation skills, 1,913 compensation records, 2,275 competencies, 831 forecasts, 618 shortages, 118 vacancies, 5 credentials, built 2026-09-12 from commit `8522dc5` |
| Processes | no job worker was running; frontend on 3015, backend on 8020 |
| Credentials | the project `.env` holds an OpenRouter key and an Adzuna key (values never read or printed); no RAGAS evaluator key |

**Root cause of the empty Admin Sources page.** (1) The page I launched was connected to an empty, throwaway database and data directory, and the Admin Sources page lists **governed** (Admin-uploaded) sources only. That was my launch choice, not a product defect. (2) Independently, even the developer database has no **active** governed source (one retired synthetic note), so pointing the Admin at it would also show an empty or near-empty inventory. (3) The 14,087-chunk curated corpus and the structured stores are real and intact, but by design they are the curated knowledge base, shown in Admin readiness as "curated knowledge base: Available" and never listed as governed sources. (4) The developer database is behind the code's migration head and would need a migration before the current code can use it (decision requested: `DI-N IR-DEVDB-STALE`).

## 2. What was done (all reversible, nothing in `data/` changed)

- Fingerprinted the developer database and Chroma store before and after: identical (`interview_studio.db` sha256 `88fd80f6…`, `chroma.sqlite3` `346a99cb…`).
- Built an **isolated review environment** under `/tmp/ask4mo_review`: the curated `knowledge/` and `chroma/` stores **copied** (the originals are not touched), a fresh review database migrated with Alembic to `0039_speech_governance`, a platform admin and a fictional candidate.
- `scripts/check_demo_knowledge.py` against the review data root: **READY**, 14,087 vector passages, structured roles 210,587 rows, smoke query "registered nurse" returned 5 sources via the structured lane, **citation pipeline PASS**; no provider.
- Registered four **SYNTHETIC CAPSTONE DEMONSTRATION DATA** sources (the existing Pilot fixture `pilot_knowledge_v1.json`) through the real Admin lifecycle with the real job worker on the same database and data root: register, scan and parse, approve, index, activate, test retrieval. Result: Admin Knowledge shows **Ready; candidate retrieval ready: Yes (curated knowledge base: Available; governed knowledge: ready); 4 active sources; 14 chunks; worker reporting; embedder offline local**; test retrieval returned evidence from the synthetic sources. A development-only fake scanner (`FILE_SCAN_PROVIDER=fake`) was used in this isolated, labelled demonstration; it must never be used in staging or production. Every source title starts `[SYNTHETIC CAPSTONE DEMO]` and the publisher text says it is not an official, statistical, framework or industry source. **The authority label in the UI reads "Level 3: reputable public industry research" because that is the lowest governed level; it is a classification field, not a claim: state on stage that these four sources are synthetic.**
- The Command Center now shows "Database migrations: Up to date, repository head and database revision `0039_speech_governance`".

## 3. Results

| Check | Result |
|---|---|
| Candidate retrieval through the real Career chat endpoint (keyless) | "What skills and responsibilities are important for a registered nurse?": **5 citations, 10 sources (O*NET)**. STAR-method question: **5 sources, all from the synthetic governed documents**. "What does a Data Analyst earn in Canada?": sources returned plus the product's note that no official occupation-specific compensation was found |
| Caveat | with no provider key the answer text is the limited fallback summary ("The assistant model is currently unavailable"); visible `[n]` citations in the fallback appeared for the structured (O*NET) question; the narrative STAR question showed sources without inline markers. A model-written, cited answer needs either the live provider (owner decision) or the offline journey |
| Admin retrieval test | `evidence_found`, 5 results from 2 sources, hybrid mode |
| Agent versus Career retrieval boundary | the agent's `SearchCareerKnowledge` and Career chat share one career service and the Admin-governed retriever (W12.4A); covered by `tests/test_knowledge_readiness_w12_4a.py` and `tests/test_agent_retrieval.py` (pass). Not demonstrated live in this keyless stack |
| RAGAS free deterministic | precision 0.6591 (21), recall 0.5484 (31), 35 cases; the committed baseline (0.6757 and 0.5161) is unchanged |
| RAGAS judge estimate-only | 24 cases, about 96 judge calls, cost unknown |
| RAGAS live | **NOT RUN: credential and guard dependency**; proposal in `RAGAS_LIVE_EVALUATION_PROPOSAL.md` awaiting the owner's approval |
| Tests | full backend 5,060 passed, 34 skipped, 0 failed; knowledge, agent-retrieval and demo tests pass; Ruff clean |
| 12 rollout and billing gates | all False (full-suite test); Compensation V2, Premium, production speech and unqualified-source ingestion off |
| Provider calls | **0** in this work. (The earlier accidental call during the P11 rehearsal is recorded in `REHEARSAL_AND_FREEZE_LOG.md`.) |

## 4. Operator runbook

**STARTUP** (isolated, keyless; copies the stores, never touches `data/`):
```bash
scripts/review/review_env.sh start > /tmp/review_start.log 2>&1    # API 8020, worker, frontend 3015, accounts
scripts/review/review_env.sh seed                                  # idempotent: the four synthetic governed sources through the real lifecycle
```
Admin login: `admin.demo@example.invalid`, password in `/tmp/ask4mo_admin_login.txt` (mode 600). Candidate: `candidate.demo@example.invalid` (synthetic passphrase in the documentation of the demo script). Both are throwaway accounts in the review database.

**KNOWLEDGE READINESS:** Admin, Knowledge: "Ready, candidate retrieval ready: Yes". Or `scripts/review/review_env.sh check` (readiness, retrieval smoke, offline journey).

**RETRIEVAL TEST:** Admin, Knowledge, Test retrieval, query "How do I structure a behavioural interview answer with the STAR method?" (synthetic sources). As the candidate: ask the nurse question (real O*NET evidence with citations).

**RAGAS RESULTS:** show `python scripts/eval_ragas.py` (free) with the baseline caveat; state that live RAGAS is not run and why.

**CANDIDATE DEMO:** `python scripts/demo_offline_journey.py` (guaranteed fallback, no provider); in the UI: Opportunities, Prepare (safe "not configured" state keyless), Practice, History, Data and privacy. A model-written cited answer needs the live provider (owner choice, see below).

**ADMIN DEMO:** Command Center (migrations up to date), Knowledge (readiness, sources, lifecycle, test retrieval), AI and models, Jobs (worker), Security and Audit, Feature flags, Provider status, Review / Evaluation (offline diagnostics, **not** live RAGAS). Say plainly: Admin sees metadata, never candidate CVs, answers or conversations.

**FALLBACK:** offline journey and transcript (`docs/capstone/submission/DEMO_TRANSCRIPT_OFFLINE.md`), the architecture diagrams, the Playwright suite. **Live Mo (optional, owner decision):** start the backend from a working copy that contains the key; it then makes real, billed calls; the keyless review stack never does.

**SHUTDOWN:** `scripts/review/review_env.sh stop` (exact PIDs, never pkill); the isolated data lives in `/tmp/ask4mo_review` and can be deleted at will; `git worktree remove /tmp/ask4mo_review_wt`.

## 5. Known limitations

The four governed sources are synthetic and few (14 chunks), so governed retrieval is a lifecycle demonstration, not evidence quality; the curated corpus is real public-source data but its coverage gate fails (386 of 412; 258 clean checkout; 0 human-qualified); keyless, Mo does not generate answers; the Admin has no live RAGAS dashboard; the developer database is stale (decision pending); the review stack is local and temporary; screenshots could not be saved to files by this tooling.

## 6. Decisions requested

1. Live RAGAS: approve, amend or decline the proposal (ceiling, new ledger, embeddings admission, dedicated key).
2. Live Mo during the review: yes or no (it spends on the owner's key outside any budget guard).
3. Whether to back up and migrate the developer database to the current head (`IR-DEVDB-STALE`).
