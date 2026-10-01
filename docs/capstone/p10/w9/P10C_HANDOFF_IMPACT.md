# P10C Handoff Impact — What W9 Must (and Must Not) Do for the Global Overhaul

> **Roadmap note (reconciled at main d6c3493):** P10C remains a separate phase after RC-P10-003/Pilot 2. P10B-W10 (Admin) is also separate; W10.8 later provides the operational Admin UI for P10C sources but does not implement or replace the P10C architecture. See `docs/capstone/capstone_phase_plan.md` and `docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md`.

Audit phase. No runtime code changed. P10C (Global Career Intelligence & Compensation Overhaul) is **not
implemented in W9**. This records how W9 decisions affect P10C so W9 does not build architecture that
conflicts with it.

---

## 1. Current state P10C inherits (evidence)

- **A canonical layer already exists but is build-time only.** `src/copilot/knowledge/canonical.py`
  defines `CanonicalOccupation`, `ClassificationRef` (+`ClassificationScheme`: ESCO/ONET_SOC/SOC/ISCO/
  KLDB), `OccupationAlias` (typed `AliasRelationship`, `ConfidenceBasis`), `OccupationCrosswalk`,
  structured `Geography` (ISO-3166 alpha-2), `TemporalMetadata`, `SourceRecord`/`SourceFingerprint`, and
  `ask4mo:occ:<hash>` ids. It is imported **only** by `normalize.py` — i.e. an ingestion/normalisation
  artifact, **not** the live retrieval path.
- **Runtime retrieval is geography-hard-coded.** `src/copilot/knowledge/router.py:84-99`
  (`_COUNTRY_PATTERNS`, `detect_country` over the fixed tuple `DE/UK/US/EU`) and
  `src/copilot/constants.py:353-358` (`COUNTRY_SOURCE_PRIORITY`, a hard-coded per-country ordered
  source-id table; `router.source_priority()` falls back to the EU list). Additional hard-codes:
  `local_readers.py:276,339,547,552`, `governed_datasets.py:100,108` (DE default).
- **Compensation is V1-flat.** `src/copilot/knowledge/compensation.py:19-35` `CompensationRecord` —
  single-row statistic, `pay_period`, `currency`, value/bounds, `sample_quality`, `year`, geography as
  free strings. Good context guards (never mixes currencies/periods) but not the rich Compensation V2
  envelope (no multi-percentile breakdown, no structured record-level `Geography`).

## 2. What P10C must inherit / build

- Reuse the **existing canonical entities** (they already match most of P10C's target:
  CanonicalOccupation → ClassificationRef → OccupationAlias/Translation → OccupationCrosswalk). Missing
  and to be added by P10C: an explicit **`SourceOccupation`** entity and a dedicated
  **`OccupationTranslation`** record/relationship (today aliases carry only a `language` field + relation
  enums).
- The core P10C work is **wiring the canonical layer into runtime retrieval**, replacing the hard-coded
  `COUNTRY_SOURCE_PRIORITY` table + DE/UK/US/EU regex with **data-driven source precedence and
  geography**, and upgrading `CompensationRecord` toward a normalized Compensation V2 using the
  structured `Geography`/`TemporalMetadata` already present in `canonical.py`.
- Source families and licence/provenance review are P10C scope (ESCO/Eurostat/Cedefop, O*NET/BLS,
  NOC/StatCan, INEGI/SINCO, CBO/IBGE, ILOSTAT as governed fallback). **No source is production-ready
  without licence/provenance review; no scraping of LinkedIn/Glassdoor/Indeed/Levels.fyi.**

## 3. What W9 must NOT do prematurely (conflict avoidance)

- **Do not extend or entrench** the hard-coded `COUNTRY_SOURCE_PRIORITY` / `_COUNTRY_PATTERNS` for new
  geographies (including any RU labour-market entry). W9.7 adds **Russian as a UI language only** — it
  must not add a Russian *geography* or a Russian source-precedence row. That coupling is exactly what
  P10C replaces with data-driven precedence.
- **Do not add ad-hoc columns/queries** against the flat `CompensationRecord` that would need
  re-migration under Compensation V2.
- **Do not introduce a second occupation/alias model** — reuse `canonical.py`; a parallel structure would
  conflict with the P10C canonical layer.
- **Do not couple language and geography anywhere** (see §5).

## 4. Russian terminology / provenance considerations

The provenance guardrail already exists and W9.7 must use it: `ConfidenceBasis` has `SOURCE_DIRECT`,
`OFFICIAL_MAPPING`, `DERIVED_NORMALIZATION`, `CURATED_MANUAL` (`canonical.py:136-139`);
`AliasRelationship.CURATED_ALIAS` (`:99`); `ASK4MO_CURATED_SOURCE = "ask4mo_curated"` (`:73`); and a
validator that a `CURATED_MANUAL` alias must declare the curated source and "never masquerade as
official" (`canonical.py:433-439`). Therefore any Ask4Mo-generated Russian occupation term must be
recorded as `source=ask4mo_curated`, `confidence=CURATED_MANUAL`, `relationship=CURATED_ALIAS` — **never
`OFFICIAL_MAPPING`**. The governance coverage matrix (`governance.py:31,297`) must keep reporting Russian
KB content as absent/unvalidated even after `ru` is added as a UI language. Russian localization should
be designed to *consume* the future global occupation graph, not to assert taxonomy translations.

## 5. Source-routing & compensation-V2 compatibility; independence

- **Source routing:** W9 introduces no new geography routing. When P10C makes precedence data-driven, the
  W9 localization work is unaffected because language and geography are already decoupled
  (`detect_country` derives geography from query keywords, never from language — `router.py:84-99`).
- **Compensation V2:** W9 touches no compensation code. The single canonical locale source W9.6/W9.7
  introduce is UI-locale only and does not intersect the compensation schema.
- **Independence (must hold through W9 and into P10C):** interface language ≠ Mo conversation language ≠
  dictation language ≠ labour-market geography. Confirmed in current code (LOCALIZATION_AUDIT §6). Every
  W9 wave and P10C must preserve it; adding `ru` must not touch `CAREER_GEOGRAPHIES`/`CareerGeography`.

## 6. Net

W9 is safe to proceed provided it (a) treats Russian as UI-only with honest provenance, (b) does not
deepen the DE/UK/US/EU hard-coding or the flat compensation schema, and (c) reuses the existing canonical
provenance primitives rather than inventing parallel ones. Nothing in the W9 plan requires P10C
structures; nothing in the W9 plan blocks them.
