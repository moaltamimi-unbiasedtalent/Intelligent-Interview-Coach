# Knowledge Normalization (Phase 7B)

How Ask4Mo turns acquired raw sources into the **canonical normalized layer**
(`data/normalized/`). This is the implementation of the Phase 7A/7A.1 build contract
([knowledge_data_architecture.md](knowledge_data_architecture.md)). It builds normalized
Parquet only; it does **not** modify the runtime knowledge DBs or Chroma (Phase 7C).

## Pipeline

```
data/raw/**  ──local_readers──▶  NormalisedOccupation / CompensationRecord /        (parse, reuse-first)
                                 LabourForecast|Openings|Shortage|Vacancy / Competency
             ──normalize.py───▶  canonical records (canonical.py)                    (map + stable identity)
             ──build script──▶   data/normalized/*.parquet + reports                 (partition, dedup, write)
```

- **Parsing is reused**, not rewritten: `src/copilot/knowledge/local_readers.py` already
  parses O*NET, ESCO, ISCO-08, KldB, BLS OOH, BLS EP, BLS OEWS, ONS ASHE, Cedefop CLSSI,
  Eurostat JVS, NICE and DigComp into source-neutral models.
- **Mapping** lives in `src/copilot/knowledge/normalize.py` — pure functions from those
  models to the canonical `canonical.py` schema, with provenance and stable identity.
- **Orchestration** lives in `scripts/knowledge/build_normalized_knowledge.py`.

## Commands

```bash
python scripts/knowledge/build_normalized_knowledge.py --all
python scripts/knowledge/build_normalized_knowledge.py --source onet --source esco
python scripts/knowledge/build_normalized_knowledge.py --all --validate-only   # no writes
python scripts/knowledge/build_normalized_knowledge.py --all --json-report

python scripts/audit_normalized_knowledge.py           # coverage + integrity
python scripts/audit_normalized_knowledge.py --json

# End-to-end (build then audit):
python scripts/knowledge/build_normalized_knowledge.py --all && \
  python scripts/audit_normalized_knowledge.py
```

## Outputs (`data/normalized/`, git-ignored)

| File | Records | Source(s) |
|---|---|---|
| `occupations.parquet` | `CanonicalOccupation` | O*NET, ESCO, ISCO, KldB, OOH, BLS EP |
| `occupation_aliases.parquet` | `OccupationAlias` (typed) | ESCO alt-labels, O*NET/OOH related |
| `occupation_crosswalks.parquet` | `OccupationCrosswalk` | ESCO→ISCO (official, exact) |
| `occupation_skills.parquet` | `KnowledgeFact` (SKILL) | O*NET, ESCO |
| `technology_skills.parquet` | `KnowledgeFact` (TECHNOLOGY_SKILL) | O*NET software, ESCO |
| `knowledge_areas.parquet` | `KnowledgeFact` (KNOWLEDGE) | O*NET |
| `tasks.parquet` | `KnowledgeFact` (TASK) | O*NET, ISCO, OOH |
| `work_activities.parquet` | `KnowledgeFact` (WORK_ACTIVITY) | O*NET |
| `education_training.parquet` | `KnowledgeFact` (EDUCATION) | OOH, BLS EP |
| `compensation.parquet` | `CompensationRecord` | BLS OEWS (US), ONS ASHE (UK) |
| `labour_market.parquet` | `LabourMarketRecord` | BLS EP, Cedefop CLSSI, Eurostat JVS |
| `competencies.parquet` | `Competency` (framework-level) | NICE, DigComp |
| `source_records.parquet` | `SourceRecord` | all (provenance backbone) |
| `build_metadata.json` | reproducibility | schema/pipeline version, source versions, sha256 fingerprints, counts |
| `canonical_registry.json` | id map | source-identifier → `ask4mo:occ:<hash>` |
| `canonicalization_report.json` | quality | counts, per-source, linkage rate |
| `normalization_rejections.json` (+ `rejected_records/`) | rejections | critical vs warning, no silent drops |

Only outputs with real data are written (no empty placeholders). A distinct de-duplicated
*skills vocabulary* is intentionally not emitted here — `occupation_skills` carries the real
occupation↔skill relations; building a standalone controlled vocabulary is a Phase 7C concern.

## Canonical identity & the no-merge rule

Ids come from `CanonicalIdRegistry.resolve_or_assign(...)` (see 7A/7A.1). An occupation's
**identity key is only its own native-scheme code** (ESCO URI, O*NET-SOC, ISCO code for an
ISCO record, KldB code, SOC). A cross-scheme code carried on the record — e.g. an ESCO
occupation's broader `isco_code` — is a **crosswalk target and a classification column, never
an identity key**. ISCO unit groups are shared by many occupations, so using them as identity
would silently merge distinct jobs; the mapper refuses that (§32/§34). Cross-source merging on
title / ISCO-group / SOC-family / embedding similarity is **not** performed.

## Semantics preserved (never converted)

- **Pay period** — `hour` / `week` / `month` / `year` kept native. `PayPeriod.WEEK` exists so
  ONS ASHE weekly pay is never annualised. The source-native period is also stored in
  `metadata.pay_period_native`. No hourly↔annual or gross↔net conversion is ever performed.
- **Statistic** — `median` / `mean` / percentiles kept distinct (never conflated).
- **Compensation type** — `observed_earnings` (official statistics) is distinct from
  `advertised_salary` (Adzuna, not ingested into the permanent KB in 7B) and `modeled_estimate`.
- **Geography** — DE / EU-aggregate / US / UK / sub-national region are distinguished by typed
  fields; an EU or Euro-area aggregate is never written to `country`, and a NUTS region is
  never rolled into its country (§57). German compensation is lower-resolution (Eurostat SES;
  Destatis not yet acquired) and is reported honestly — it does not block the build.

## Provenance, rejections, determinism

- Every occupation / alias / fact carries `source` + `source_record_id`; a record with no
  provenance is not emitted (§33). Framework competencies are kept separate from occupations
  and are each backed by a `SourceRecord` (NICE work roles are not auto-equated to O*NET).
- Rejections are recorded, never silently dropped: `normalization_rejections.json` separates
  `critical` from `warning`, and `rejected_records/` holds the detail. Unknown-currency and
  missing-value compensation rows are warnings, not crashes.
- **Deterministic & idempotent (§4):** ids derive from source identity (never row/file/
  timestamp order); every output is sorted by a stable key before writing; `retrieved_at` is
  not stamped at normalize time. Two independent builds from the same raw inputs produce
  byte-identical records and an identical registry. Parquet round-trip is validated on every
  build and by the audit.

## Occupation→compensation linkage

Compensation links to a canonical occupation **only** through an existing official code
crosswalk (US/UK SOC), never by fuzzy title matching. Unlinked rows are expected and reported
honestly (`canonicalization_report.json` → `compensation_occupation_linkage`, and the audit's
warning). Richer cross-source linkage is Phase 7B/7C work, done conservatively.

## Testing

Unit tests use small synthetic fixtures (`tests/test_normalize_knowledge_p7b.py`), never the
full raw tree: mapping correctness, id stability + no-merge, per-alias parsing, alias
ambiguity, crosswalk priority, provenance completeness, compensation/geography semantics,
requirement-level vs seniority separation, dedup, Parquet round-trip, and the build
orchestrator (partitioning, rejections, idempotent rebuild, validate-only). A real local
integration build is exercised via the commands above (counts recorded in
[knowledge_data_architecture.md](knowledge_data_architecture.md)).
