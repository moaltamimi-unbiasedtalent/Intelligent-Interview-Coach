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
