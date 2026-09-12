# Knowledge Runtime Architecture (Phase 7C)

How the governed normalized corpus (Phase 7B) becomes the runtime Career Intelligence
knowledge, and how retrieval stays grounded, cited and geography-safe. Complements
[knowledge_data_architecture.md](knowledge_data_architecture.md) (raw → normalized) and
[knowledge_normalization.md](knowledge_normalization.md). The Agentic RAG contract is
unchanged: **Mo decides IF to retrieve; Career Intelligence decides WHICH evidence** — no new
agent, no new RAG subsystem, no LangGraph topology change.

## Build loop: raw → normalized → runtime

```
data/raw/**        acquired sources (7A/7A.1)
   │  build_normalized_knowledge.py (7B)
data/normalized/** governed canonical Parquet (occupations, aliases, crosswalks, facts,
   │               relationships, attributes, compensation, labour-market, competencies)
   │  build_runtime_knowledge.py (7C)   ← makes normalized the governed runtime source
data/knowledge/*.db   structured runtime stores (roles/compensation/labour_market/
   │                   competencies/credentials) + build_metadata.json
data/chroma/          vector index (narrative + governed structured passages)
```

`scripts/knowledge/build_runtime_knowledge.py` reconstructs the intermediate models from the
normalized Parquet and writes the **existing** store schemas (so the proven repositories,
resolver, hybrid retrieval and citation pipeline work unchanged), then promotes atomically:

```bash
python scripts/knowledge/build_runtime_knowledge.py --all            # structured + vector
python scripts/knowledge/build_runtime_knowledge.py --structured-only
python scripts/knowledge/build_runtime_knowledge.py --vector-only
python scripts/knowledge/build_runtime_knowledge.py --all --validate-only   # build+validate, no promote
```

**Atomic promotion (§4/§60):** each store is built into a temporary `.build-<id>` dir,
validated, then moved into place with a one-shot backup of the previous store; a validation
failure leaves the live runtime untouched. **Build metadata** (`data/knowledge/build_metadata.json`,
git-ignored) records the git commit, runtime + normalized pipeline versions, counts and the
supplementary sources. **No Parquet at query time** — the API serves from the SQLite stores,
the vector index and the cached registry, never the normalized dataframes (§57).

**Governed vs supplementary.** Occupations (title/description/ISCO/aliases/skills/tasks/
knowledge/activities/relationships/attributes/crosswalks), compensation, labour-market and
NICE/DigComp competencies come from the normalized layer. A few domains it does not yet carry
are preserved via their existing governed loaders and recorded in the build metadata:
supplementary competency frameworks (e‑CF, BA Kompetenzkatalog), credential fixtures, and the
narrative vector corpus (`data/processed/chunks.jsonl`).

## Occupation resolution, aliases, crosswalks

The runtime resolver (`knowledge/resolver.py`) maps a question to occupations using the
governed `occupation_aliases` (23,579) and `occupation_mappings` (ESCO→ISCO crosswalks) now
rebuilt from the normalized layer. Phase 7C adds **intent-noun stripping** so a phrase like
"software developer salary" or "data analyst skills" resolves to the bare occupation (the
intent noun becomes a lane signal, not part of the title). Ambiguous matches (materially
different occupations) return **clarify**, never a guess (§9).

## §39/§40 occupation-grounding guard

The central safety fix. `CareerIntelligenceService.retrieve_evidence` now classifies each
result:

- **grounded** — the resolver matched at least one KNOWN occupation (`occupation_candidates`).
  Structured + narrative evidence is returned as occupation-specific.
- **ambiguous** — several materially-different occupations matched → return *clarify* with no
  occupation-specific evidence.
- **named-but-unresolved** — the query names an occupation the KB does not contain (e.g. a
  nonsense or emerging role). Similar narrative chunks are **withheld** and the result is
  insufficient — the pipeline never presents look-alike chunks as facts about a role it does
  not have (§39).
- **general** — no specific occupation named; general narrative is returned but flagged
  `general_evidence=True` so the candidate layer can label it as general guidance (§40).

`KnowledgeRetrievalResult` carries `occupation_grounded` and `general_evidence`. This closed
the pre-7C generic-vector-fallback defect: unknown-role safety went from 0.17 → 1.00 in the
retrieval evaluation.

## Compensation & geography safety (§17/§18/§36)

Compensation records keep native semantics (statistic / pay period / currency / gross-net /
year / observed-vs-advertised). The compensation lane is **geography-strict**: for a country
with no occupation-specific record it returns insufficient or clearly-labelled supra-national
(EU) context, and **never substitutes another nation's statistics** (US BLS or UK ONS may not
stand in for a German salary). German compensation is aggregate (Eurostat SES) and reported
honestly.

## Vector index (§23–28)

The index combines the narrative corpus with **governed structured passages** generated from
the normalized layer — occupation descriptions, grouped task/activity/knowledge statements and
competency descriptions — each embedded with full provenance metadata (source, source URL,
canonical occupation id, domain, geography, language). Numeric rows, codes and one-word aliases
are **not** embedded (kept structured). The embedder is the repository's configured model — the
free offline `local-hash-v1` — so a rebuild incurs **zero paid calls**; if a paid embedder were
configured the build STOPs rather than spending silently.

## Measurement

- `scripts/eval_knowledge_retrieval.py` — deterministic retrieval evaluation over
  `evaluations/knowledge/retrieval_cases.json` (81 cases): resolution, evidence, citation
  completeness, geography correctness, and hard unknown-role / ambiguity safety gates.
- `scripts/audit_knowledge_coverage.py` — domain + geography coverage over the runtime stores.
- Before/after: [knowledge_coverage_report.md](knowledge_coverage_report.md) +
  `evaluations/knowledge/coverage_report.json`; baseline in
  `evaluations/knowledge/pre_phase7_runtime_baseline.json`.

## What did NOT change

No new agent or RAG subsystem; LangGraph topology, the five Career tools + two HITL actions,
memory, authentication and Interview Practice are all unchanged. Adzuna remains acquisition-only
(not an Agent tool). No Langfuse, no RAGAS, no external-research tool (later phases).
