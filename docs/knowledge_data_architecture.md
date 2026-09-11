# Knowledge Data Architecture (Phase 7A)

The **data-foundation** contract for Ask4Mo's knowledge: how raw source files become
governed, reproducible, provenance-carrying knowledge. This complements the runtime view
in [knowledge_architecture.md](knowledge_architecture.md) (how retrieval *uses* the
knowledge), the build commands in [rebuild_knowledge_base.md](rebuild_knowledge_base.md),
and the licence catalogue in [source_licensing.md](source_licensing.md) /
[knowledge_source_catalogue.md](knowledge_source_catalogue.md).

Phase 7A establishes the contract only — it does **not** change retrieval, the Agent, or
the current KB. Phase 7B implements the normalization loaders against this contract.

## Data lifecycle

```
data/raw/                     immutable downloaded sources (git-ignored, not modified)
      │  inventory + audit    scripts/inventory_sources.py · scripts/audit_raw_sources.py
      ▼
data/normalized/              canonical Ask4Mo records (git-ignored, generated in 7B)
      │  normalize (7B)       Parquet: occupations / aliases / facts / source_records …
      ▼
data/knowledge/*.db           structured runtime stores (git-ignored, generated)
      │  build                roles / compensation / competencies / labour_market / credentials
      ▼
data/chroma/                  semantic vector index (git-ignored, generated)
```

Each arrow only ever reads the layer above and writes the layer below; nothing writes
back into `data/raw/`. The narrative path (`data/processed/chunks.jsonl` → Chroma) is
unchanged from Sprint 4.

## What is committed vs generated

| Path | Committed? | Purpose |
|---|---|---|
| `data/source_manifest.json` | **yes** | Ingestion contract — 29 sources (id, version, domains, storage_target, licence, urls). Parsed by `src/copilot/knowledge/manifest.py` (`SourceEntry`, strict). |
| `data/source_inventory.json` | **yes** | Per-file inventory of `data/raw/` with **sha256** fingerprints (198 files). Written by `scripts/inventory_sources.py`. |
| `data/source_status.json` | **yes** | Per-source lifecycle (acquired / normalised / indexed / available; `data_origin`; `production_ready`). Written by `scripts/source_status.py`. |
| `data/raw/**` | no (git-ignored) | Immutable downloaded sources; may be large/licensed. |
| `data/normalized/**` | no (git-ignored) | Canonical normalized layer, rebuilt from raw. |
| `data/knowledge/**`, `data/chroma/**` | no (git-ignored) | Generated runtime stores + vector index. |
| `data/build_metadata.json` | no (git-ignored) | Reproducibility record for a normalized build (see below). |
| `evaluations/knowledge_samples/` | **yes** | Small synthetic fixtures used by loaders/tests (`--fixtures`). |

Anything a reviewer must rebuild locally is generated; the *governance* (manifest,
inventory, status) is committed so provenance and readiness are inspectable without the
raw data.

## Canonical build contract

`src/copilot/knowledge/canonical.py` is the typed, build-layer data contract (Pydantic),
kept **separate** from the runtime models (`Provenance`, `KnowledgeEvidence`, `Citation`,
`NormalisedOccupation`) because its job is reproducible cross-source normalization, not
retrieval output:

- `CanonicalOccupation`, `OccupationAlias` (typed `AliasRelationship`), `KnowledgeFact`
  (typed `FactType`) — the normalized rows.
- `SourceRecord` + `SourceFingerprint` — every normalized row is traceable to the exact
  raw file (repo-relative path) and its sha256.
- Context dimensions: `Geography` (§ prevents "US wage read as DE pay"), `TemporalMetadata`
  (source version vs effective period vs reference year vs retrieval date), `Seniority`,
  and `ConfidenceBasis`.
- `BuildMetadata` — reproducibility record.

Serialization: **Parquet** is the canonical normalized format (columnar, typed). The
Parquet helpers lazy-import `pyarrow` from the optional `[knowledge]` extra
(`pip install -e ".[knowledge]"`); the FastAPI runtime never imports it. **JSONL** is the
always-available fallback for fixtures and environments without pyarrow.

## Canonical identity

Three identity layers are kept distinct (no cross-source merging happens in 7A):

- **Source-native** — as the source states it: `onet:15-2051.00`, an ESCO occupation URI,
  a KldB code.
- **Classification/crosswalk** — `ClassificationRef(scheme, code)` for ESCO / O*NET-SOC /
  SOC / ISCO / KldB.
- **Ask4Mo canonical** — `ask4mo:occ:<16-hex>` from `canonical_occupation_id(...)`.

The canonical id is a SHA-256 over a single `scheme:value` key, **never** a row number,
file order or timestamp, so the same occupation yields the same id across rebuilds and
machines. The key is chosen by a fixed precedence — ESCO URI → O*NET-SOC → ISCO → SOC →
KldB — falling back to `native:<source>:<id>` only when no classification code exists.
Because it is derived (not merged), two sources describing the "same" job may still hold
different canonical ids in 7A; deterministic cross-source merging is deferred to Phase 7B.

## Provenance flow

Every normalized fact carries `source`, `source_record_id`, `source_url` and `license`,
and its `SourceRecord` pins the exact `raw_file` / `raw_sheet` / fingerprint. This lets any
future retrieved fact be traced to an authoritative origin, and bridges cleanly to the
runtime `Provenance` / `Citation` used by the candidate path. Curated Ask4Mo data must use
`source = "ask4mo_curated"` and `ConfidenceBasis.CURATED_MANUAL`; it can never masquerade
as O*NET/ESCO/BLS/Cedefop (enforced by the schema).

## Reproducibility & version drift

A normalized build writes `data/build_metadata.json` (generated, git-ignored):
`canonical_schema_version`, `manifest_version`, `pipeline_version`, `git_commit`,
`built_at`, `source_versions` (source_id → exact version), `source_checksums` (sha256 of
the consumed raw inputs) and `record_counts`. Because outputs are attributed to exact
source versions, a dataset upgrade (e.g. ESCO 1.2.1 → 1.3) is an explicit, visible change
rather than a silent overwrite of provenance.

## Auditing readiness

```bash
python scripts/audit_raw_sources.py          # human report + READY / NOT READY (exit code)
python scripts/audit_raw_sources.py --json   # machine-readable (for refreeze automation)
```

It reads the committed manifest/inventory/status (one governance model, reused — not a
competing one), reports each source's readiness (READY / WARN / NOT ACQUIRED / FAIL), the
occupation backbone (onet|esco), checksum coverage, schema validity and licence-review
items, and exits non-zero only when a required, acquired source is genuinely unusable or
the backbone is missing. Absent optional sources never fail the audit. Licence review is
surfaced (never inferred) — see [source_licensing.md](source_licensing.md); this document
draws **no legal conclusions**.

## Security

Raw source parsing treats all imported content as untrusted **data**: no macro/formula/
HTML/JS execution, and no `pickle`-based ingestion of untrusted datasets. Readers use
pandas/openpyxl and stdlib parsers over the raw files.

## Phase 7A.1 additions (gap closure & acquisition)

**Raw deduplication.** `scripts/knowledge/dedup_raw_sources.py` removes exact byte-duplicate
raw files (SHA-256), keeping one canonical copy per group. Canonical selection is
reader-safe: a path referenced by `local_readers.py` is always kept (so ingestion never
breaks), else the most organized/versioned path wins. The full record is
`data/raw_deduplication_report.json` (committed). Phase 7A.1 removed 95 redundant copies
(~304 MB; 765→462 MB) with zero content loss.

**Compensation semantics (three distinct classes, never merged):** `observed_earnings`
(Destatis/BLS/ONS/Eurostat/BA), `advertised_salary` (Adzuna), `modeled_estimate`. Carried
by the first-class `CompensationRecord` (statistic / pay_period / gross_net / country /
year all explicit) — never a generic "salary". `LabourMarketRecord`, `CredentialRecord`
and `OccupationCrosswalk` are likewise first-class (`canonical.py`).

**Canonical-ID stability.** `CanonicalIdRegistry` (`canonical.py`) persists
source-identifier → `ask4mo:occ:<hash>` so adding a richer classification later (e.g. an
ESCO URI on top of ISCO) never regenerates an already-assigned id. Crosswalk enrichment
adds identifiers; it does not mutate identity. A broad taxonomy link (same ISCO group) is
`broader`/`related`, never `exact`.

**Acquisition providers (data infrastructure only — never Agent tools):**
- `scripts/knowledge/download_destatis.py` — Destatis GENESIS German earnings
  (table 62361-0034). Credentials from `DESTATIS_USERNAME`/`DESTATIS_PASSWORD` (or
  `DESTATIS_TOKEN`); absent → NOT CONFIGURED, non-blocking (Eurostat SES already covers DE).
- `src/copilot/knowledge/providers/adzuna.py` + `scripts/knowledge/check_adzuna.py` —
  Adzuna authorized market API (`authorized_market_api`), advertised-market evidence only.
  Credentials from `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` (env only, never logged/committed);
  Germany connectivity via `/jobs/de/search` (the `/version` endpoint is not required).

**Gap audit.** `scripts/audit_knowledge_gaps.py` (+`--json`) reports per-domain readiness
and the Phase 7B backbone verdict, separating blocking from non-blocking/future gaps.

Credentials are read ONLY from the environment and never enter source metadata, provenance,
logs, tests or `.env.example` (which holds empty `ADZUNA_APP_ID=` / `ADZUNA_APP_KEY=`
placeholders). `.env` stays git-ignored.

## Phase 7B — the normalization build

Phase 7B turns the acquired raw sources into the canonical normalized layer defined by the
7A/7A.1 contract. It **builds `data/normalized/` only** — it does not touch the runtime
stores (`data/knowledge/*`, `data/chroma/*`); merging normalized records into those stores
is Phase 7C. Full detail: [knowledge_normalization.md](knowledge_normalization.md).

**One orchestrated command** (`scripts/knowledge/build_normalized_knowledge.py`) reuses the
proven `local_readers` parsers and maps their output through `knowledge/normalize.py` into
canonical records, assigning stable ids via a single `CanonicalIdRegistry`:

```bash
python scripts/knowledge/build_normalized_knowledge.py --all           # build every source
python scripts/knowledge/build_normalized_knowledge.py --source onet   # one/more sources
python scripts/knowledge/build_normalized_knowledge.py --all --validate-only   # parse+map+round-trip, no writes
python scripts/knowledge/build_normalized_knowledge.py --all --json-report
python scripts/audit_normalized_knowledge.py            # coverage + integrity audit (+ --json)
```

**Outputs** (Parquet; JSONL fallback if pyarrow is absent) — only files with real data are
written (no empty placeholders): `occupations`, `occupation_aliases`, `occupation_crosswalks`,
`occupation_skills`, `technology_skills`, `knowledge_areas`, `tasks`, `work_activities`,
`education_training`, `compensation`, `labour_market`, `competencies`, `source_records`, plus
`build_metadata.json`, `canonical_registry.json`, `canonicalization_report.json` and
`normalization_rejections.json` (+ `rejected_records/`). All git-ignored under
`data/normalized/*`.

**Real local build (this machine, pipeline 7B.1):** 8,035 occupations
(onet 1,016 · esco 3,039 · isco08 613 · kldb 2,193 · bls_ooh 343 · bls_projections 831),
23,579 aliases, 3,039 ESCO→ISCO crosswalks, 99,883 occupation-skill relations, 11,572
technology skills, 6,968 knowledge areas, 22,383 tasks, 20,141 work activities, 1,173
education/training facts, 1,913 compensation records, 1,904 labour-market records, 2,269
framework competencies, 10,304 source records; 0 rejections; the build is **idempotent**
(two independent runs produce byte-identical records and registry).

**Key normalization decisions:**
- *No ISCO-group merge (§32/§34).* An occupation's identity key is only its own native
  scheme code; a broad `isco_code` is a crosswalk target + classification column, never an
  identity key — so distinct ESCO/O*NET occupations sharing ISCO unit group 2511 stay
  distinct. Cross-source linkage is intentionally conservative (no title/embedding merge).
- *Compensation semantics preserved (§17).* Weekly (ONS ASHE), hourly and annual (BLS OEWS)
  are kept in their native `pay_period` — `PayPeriod.WEEK` was added so UK weekly pay is
  never silently annualised; the source-native period is also retained in metadata.
- *Geography kept separate (§57).* DE / EU-aggregate / US / UK / sub-national region are
  distinguished by typed fields; an EU or Euro-area aggregate is never written to `country`,
  and a NUTS region is never rolled into its country. German compensation is comparatively
  lower-resolution (Eurostat SES; Destatis not yet acquired) — reported honestly, not blocking.
- *KldB `.xls` handled deliberately (§15).* The KldB **systematic index** is read from the
  official `.xlsx` (`Systematisches-Verzeichnis-KldB-2020.xlsx`) with no conversion. The
  supplementary legacy `.xls` (`Berufssektoren-und-Segmente…`) is a different sector-mapping
  file, not required for occupation normalization, and is intentionally not ingested — so no
  `xlrd`/LibreOffice/headless conversion is introduced.
- *Provenance-or-nothing (§33).* Every occupation, alias and fact carries `source` +
  `source_record_id`; competency frameworks (NICE/DigComp) are emitted as their own output,
  each backed by a `SourceRecord`, and kept separate from occupations (no auto-equate).
- *Unresolved linkage reported honestly.* Compensation rows link to a canonical occupation
  only through an existing official code crosswalk (no fuzzy title matching); the current
  resolved/unresolved split is reported in `canonicalization_report.json` and the audit.
