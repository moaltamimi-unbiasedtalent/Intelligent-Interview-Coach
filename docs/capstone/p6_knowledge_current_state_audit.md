# P6 — Knowledge Current-State Audit

_Written from a read-only inspection of the actual implementation before P6 changes. A
status is upgraded ONLY on concrete evidence (artifacts present + metadata), never because
a code path exists._

Legend: **READY** · **PARTIAL** · **NOT READY** · **UNVALIDATED**

## Pipeline components

| Component | Where | State | Evidence / caveat |
|---|---|---|---|
| Knowledge sources (structured SQLite: roles/compensation/competencies/labour_market/credentials) | `src/copilot/constants.py` paths; `src/copilot/knowledge/{roles,compensation,structured_ext}.py` | READY (generated, git-ignored) | `.db` files must be built (`data/knowledge/*` is git-ignored); present on a built checkout. |
| Ingestion | narrative: `src/copilot/ingestion/indexer.py` (+ `scripts/ingest.py`, `build_index.py`); governed: `scripts/knowledge/build_{normalized,runtime}_knowledge.py` | READY | Two pipelines (raw→normalized→runtime); `build_metadata.json` records versions + `built_at`. |
| Chunking | `src/copilot/ingestion/chunking.py` | READY | Stable chunk IDs. |
| Embeddings | `src/copilot/embeddings.py` | READY (with offline fallback) | `LocalHashEmbedder` (offline lexical, 512-dim) vs `OpenAIEmbedder`; `embedding_status` reports local as "OFFLINE LEXICAL", never "semantic". |
| Index / storage | Chroma `src/copilot/vectorstore.py`; `data/chroma` | READY (generated, git-ignored) | `chroma.sqlite3` must be built; `InMemoryVectorStore` fallback. |
| Retrieval | router `src/copilot/knowledge/router.py`; structured multi-lane `retrieval.py`; hybrid `src/copilot/retrieval/hybrid.py` (RRF over vector + BM25) | READY | Deterministic router owns lane selection; agent decides *whether* to retrieve. |
| Filtering / lanes | `router.route_question`, `source_priority` | READY | Many lanes (role/comp/competency/licence/…); ambiguity → optional classifier. |
| Geography | `router.detect_country` + `COUNTRY_SOURCE_PRIORITY` | READY | Country-specific official stats outrank international; unknown → EU default. |
| Citations | `src/copilot/models.py` (`Citation`, `to_citation`); selection in `service.py`; validation `src/agent/grounding.py` | READY | Only markers present in the answer AND backed by evidence are kept. |
| Readiness | `src/application/knowledge_service.get_knowledge_diagnostics` | PARTIAL → **P6 formalises** | Depended on a git-ignored artifact (`retrieval_after.json`); no deterministic state machine. |
| Manifest / source health | `src/copilot/knowledge/manifest.py`, `status.py` (`data/source_manifest.json`) | READY (source register) | Curated register + freshness; **P6 adds a unified governed manifest + readiness**. |
| Evaluation | `scripts/eval_*` (11R, 11R-A, KB-2, product coverage, quality_v2, faithfulness_v2); RAGAS deterministic baseline committed | READY (subset in CI) | Deterministic suites; RAGAS deterministic ID precision/recall **0.6757 / 0.5161** committed at `evaluations/ragas/deterministic_baseline.json`. |
| Diagnostics | `GET /api/v1/knowledge/{sources,diagnostics,snapshot}` | PARTIAL (public read) | **P6 adds an admin-gated reviewer surface**. |

## Failure modes observed
- On a **fresh clone**, the generated KB (structured DBs + Chroma) is absent, so
  `get_knowledge_diagnostics` degrades to empty sections silently. P6's
  `demo_readiness.py` makes this a clear non-zero failure instead.
- **BM25** degrades to empty results when the `[rag]` extra (`rank_bm25`) is absent (PARTIAL).
- Live embedding/model paths are **UNVALIDATED** (no paid calls authorised).

## Per-domain readiness (governed KB)

| Domain | State | Note |
|---|---|---|
| Occupations / roles / skills / competencies (ESCO/O*NET/ISCO/DigComp) | READY (generated) | Depends on the build; git-ignored artifacts. |
| Labour market / forecasts | READY (generated) | As above. |
| Credentials / licences | PARTIAL | Structured store present; **K2 governed matrix added in P6** for declared professions. |
| Compensation (general) | PARTIAL | Store present; **German occupation depth was the known gap** → **K1 governed dataset added in P6**. |
| Germany occupation compensation (K1) | NOT READY → **PARTIAL (P6)** | Bounded reviewed dataset + abstention added; figures engineering-draft. |
| Credentials / regulated professions matrix (K2) | NOT READY → **PARTIAL (P6)** | Declared profession/jurisdiction matrix + abstention added. |
| Emerging roles / aliases (K3) | NOT READY → **PARTIAL (P6)** | Versioned alias map added (confident matches only). |
| Additional Adzuna capabilities (K4) | NOT READY → **PARTIAL / UNVALIDATED (P6)** | Bounded operation spec + validation added; live calls UNVALIDATED / cost-gated. |
| Multilingual (DE/FR/ES/IT/PT/NL) native KB content | NOT READY | UI supports 7 languages; governed KB content is English (+ some German). **P6 documents the boundary honestly**; live multilingual retrieval UNVALIDATED. |

## Gaps carried into / addressed by P6
- Knowledge readiness was not a deterministic state machine → **addressed** (`governance.py`).
- No unified auditable manifest across governed datasets → **addressed**.
- K1–K4 datasets absent → **addressed** as bounded reviewed datasets with abstention.
- Multilingual coverage over-claim risk → **addressed** (explicit boundary + fixtures).
- Reviewer diagnostics were public/partial → **addressed** (admin-gated reviewer route).
- Generated-artifact reproducibility ambiguity → **addressed** (`demo_readiness.py` + docs).
