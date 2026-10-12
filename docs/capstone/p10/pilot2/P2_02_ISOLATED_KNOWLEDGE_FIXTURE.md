# P2-02 - isolated, synthetic Pilot knowledge fixture

**Status: REMEDIATED - ENVIRONMENT READY, PENDING HUMAN REVALIDATION.** An isolated source-backed retrieval environment now exists and is deterministically validated. The candidate-facing source experience has **not** yet been re-tested by humans. P2-02 is **not closed**; AC-24 remains PARTIAL (P2-03 and P2-04 are open and human revalidation is pending). RC-P10-003 and its Pilot 2 evidence are unchanged and frozen.

## 1. Why this exists
Pilot 2 ran from an isolated candidate worktree without the developer knowledge datasets, so Sources were unavailable and Mo did not consistently surface knowledge evidence. That was an environment limitation, not a confirmed retrieval defect, but it meant the source-backed experience was never validated. This fixture lets a future Pilot exercise retrieval, citations and Sources without touching any developer or production store.

## 2. Fixture identity and warning
- Fixture: `ask4mo-pilot-knowledge-fixture` version `1.0.0`, file `docs/capstone/p10/pilot2/fixtures/knowledge/pilot_knowledge_v1.json`.
- **SYNTHETIC PILOT TEST DATA.** Four sources, ten chunks (STAR answer structure, stakeholder interview preparation, evidence-first answer preparation, role-research brief). Every chunk starts with `[Synthetic pilot test data]`, every title starts `Pilot fixture:`, and the publisher is `Ask4Mo Pilot Knowledge Fixture (synthetic test data)`.
- It is not an official, statistical, framework or industry source, contains no real-world statistic, and **carries no `authority_level`** (1 = official/statistical, 2 = framework, 3 = reputable industry stay reserved for real sources; authority semantics are unchanged). It has no `source_url` (no invented domain), so citations render in the existing no-link form.
- `document_type` is the production taxonomy value `interview_guidance`. Reason: production query translation filters interview-preparation queries to that type, so chunks of any other type would never be retrieved. Synthetic provenance is carried by the title, source, publisher and text, not by an invented type.
- It contains no participant data, CV content, copied developer knowledge, private URL or secret.

## 3. Architecture (no second RAG)
`scripts/pilot/isolated_knowledge.py` builds `DocumentChunk` objects and writes them with the production local-hash embedder (`local-hash-v1`) into a production `ChromaStore`, collection `career_knowledge_base`, at `<output-dir>/chroma`. Validation uses the production boundary `CareerApplicationService.search_knowledge` -> `CareerIntelligenceService.retrieve_evidence` over the production hybrid retriever, whose BM25 channel is built from the same store chunks (`KeywordRetriever.from_store`). It makes no final answer synthesis, runs no Career tool and needs no provider key or network. The structured knowledge coordinator is intentionally omitted from validation because it would read the developer's structured datasets.

## 4. Safety guard (fail closed)
The builder exits non-zero (code 2, `REFUSED: ...`) and creates nothing if the output directory is: inside or an ancestor of the repository; the default `data/chroma`, the `COPILOT_CHROMA_DIR` location or anything overlapping them; a symlink; inside a Git working tree; the filesystem root or home; or a populated directory that is not already a Pilot fixture (marker file `.ask4mo-pilot-knowledge.json`). `--reset` works only inside an existing fixture directory and only resets that directory's collection. Embeddings are forced to the offline `local` provider.

## 5. Commands
Build and validate into a throwaway directory:

```bash
python scripts/pilot/build_isolated_knowledge.py --output-dir /tmp/ask4mo-pilot2-p01-kb --validate
python scripts/pilot/validate_isolated_knowledge.py --knowledge-dir /tmp/ask4mo-pilot2-p01-kb
```

The build prints the exact environment to use. For the Pilot backend (run from the isolated candidate worktree with the throwaway pilot database as in the runbook), set these **before the backend process starts** (the application caches the Copilot configuration and vector store for its lifetime):

```bash
export COPILOT_CHROMA_DIR=/tmp/ask4mo-pilot2-p01-kb/chroma
export COPILOT_EMBEDDING_PROVIDER=local
```

Clean up only that throwaway directory when the session ends:

```bash
rm -rf /tmp/ask4mo-pilot2-p01-kb
```

Never point the fixture at, copy, symlink or mount `data/chroma`, `data/raw`, `data/processed`, `data/knowledge` or any developer store, and never run the builder against them. Build a fresh directory per participant or reuse the same one read-only; the builder is idempotent (a rebuild adds 0 chunks).

## 6. What it proves (deterministically, offline)
Fixture construction in an isolated directory; no write to any repository store; the production Chroma/local-embedder/hybrid path retrieves fixture evidence for a known query ("How should I structure a STAR interview answer?"), with `source_count > 0`, `insufficient_evidence = false` and citations that map to real fixture chunks with title and source provenance and no invented URL; a query that maps to a document type the fixture lacks ("What skills are in demand for data analysts?") returns no evidence; an injection attempt is blocked; no synthesis model, tool or network is used. Covered by `tests/test_pilot_isolated_knowledge.py` (21 tests).

## 7. What it does NOT prove
Human discoverability of Sources; model-generated response citation quality; live-provider behaviour; multilingual knowledge quality; production corpus quality; semantic embedding quality (the local hash embedder is lexical). Note an existing production property: queries without a document-type filter return the nearest chunks because the pipeline has no relevance cutoff, so an unrelated, unfiltered query can still surface a weak fixture chunk. That is existing behaviour, not changed here.

## 8. Next human-validation step
A targeted Pilot re-run on a later RC with the fixture loaded, observing whether participants find Sources, understand what a source is and recognise that this environment's knowledge is synthetic. Until then P2-02 stays pending revalidation.
