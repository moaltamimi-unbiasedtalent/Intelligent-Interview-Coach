# P10C-A Global Knowledge Foundation (GKB-0, GKB-1, GKB-2)

Starting point: origin/main `0259a424fbe674eed1277837eb4708e84fbf8a84` (P10C-0 merged as PR #177). Branch `feat/p10c-a-global-knowledge-foundation`. Alembic head `0034_preparation_packs` to `0035_knowledge_foundation` (one additive migration, seven new tables, nothing seeded by the migration). Status: **CODE QUALIFIED OFFLINE; FOUNDATION ONLY; NOTHING OPERATIONAL; NOT MERGED.**

Labels used below: **RECOVERED REQUIREMENT** (from the September 30, 2026 conversation, not the repository), **EXISTING IMPLEMENTATION** (found in the repository), **PROPOSED DESIGN** (this wave, pending owner adoption where stated), **PENDING OWNER APPROVAL**, **QUALIFIED IMPLEMENTATION** (built and verified by the evidence in section 14).

## 1. Scope and non-goals
Delivered: GKB-0 baseline freeze and characterisation; GKB-1 governed source registry and country-level coverage matrix; GKB-2 occupation graph, taxonomy edition model, crosswalk status model, resolver contract, legacy compatibility. Not delivered, by instruction: CompensationRecordV2, any ingestion of unapproved data, any change to candidate-facing salary results, current compensation retrieval, Interview Practice, Career AI, Mo chat, company research, Opportunity Packs, history/model/cost/quota/analytics behaviour, Premium activation, RC-P10-004, P10C-B, P11. All six billing gates and all six product rollout gates remain False. No Stripe call, no paid LLM call, no external download.

## 2. GKB-0 baseline (EXISTING IMPLEMENTATION, characterised read-only)
`scripts/gkb0_baseline.py` produces `docs/capstone/p10/p10c_a/GKB0_BASELINE_MANIFEST.json` (counts, SHA-256 checksums, versions, verdicts; no source content; refuses to write under `data/` or `evaluations/`). Verified counts: roles.db `occupations` 8,035, `occupation_aliases` 23,579, `occupation_mappings` 3,039; compensation.db `compensation_records` 1,913; vector store 14,087 chunks; product-coverage fixture 412 cases; 31 manifest sources.

Reproducibility (does not claim more than the evidence): **3 reproducible, 9 partially reproducible, 19 not reproducible**. 13 of 13 recorded raw-input checksums are present and match. Most sources record `current release` instead of a pinned edition, which caps them at partial; 19 have no recorded raw checksum, a manual-acquisition requirement, or are not built. The normalized layer records no git commit. The local stores are gitignored developer builds, so the baseline is a local characterisation, not a CI-reproducible fixture (that fixture remains planned for P10C wave G).

## 3. Existing architecture assessment
EXISTING: `src/copilot/knowledge/canonical.py` (CanonicalOccupation, ClassificationRef, OccupationCrosswalk, `canonical_occupation_id`); `router.py` with hard-coded `COUNTRY_SOURCE_PRIORITY` for DE/US/UK/EU; V1 compensation retrieval filtering by title. Findings: identity is derived from a code or URI with no edition namespace; ISCO codes are stored stripped of leading zeros in the legacy store (section 11); there is no source registry, no edition model, no coverage model and no ambiguity state. The foundation is built beside this layer and is not imported by it.

## 4. Source registry (GKB-1; QUALIFIED IMPLEMENTATION)
Tables `global_sources`, `global_source_events`. Lifecycle: DISCOVERED, LICENSING_PENDING, LICENSING_VERIFIED, APPROVED_FOR_INGESTION, APPROVED_FOR_RUNTIME_USE, RESTRICTED, REJECTED, SUPERSEDED, with only defined edges, every transition audited, REJECTED/SUPERSEDED terminal, supersession naming a registered successor. Every fact has an explicit `unknown` state (licence, redistribution, attribution, origin, validation, precedence category, evidence class); registration can never create an approved source or a verified licence; re-registration refreshes metadata but never changes approval or a verified licence. Approval needs a verified licence (service and database CHECK); runtime use also needs a known non-fixture origin and a recorded validation status; a synthetic fixture can never be approved at any layer. Freshness is metadata only. Seed (`source_registry_baseline.json`, 31 sources) is derived from the manifest; a bare `redistribution_allowed` flag without a stated licence is recorded as `unknown` with a stated conflict. Result: 26 LICENSING_PENDING, 5 RESTRICTED (synthetic fixtures); none approved for ingestion or runtime; 18 have no stated licence, 13 state one (CC BY 4.0, Open Government Licence v3.0, Public domain U.S. Government work, CEN commercial), none verified. Evidence classes C1 is assigned only to BLS OEWS and the German Entgeltatlas (`ba_entgeltatlas`); every other source is `unknown`. PENDING OWNER APPROVAL: every dataset licence and every approval transition.

## 5. Coverage matrix (GKB-1)
Table `geography_coverage`; 47 country-level rows (EU27, EEA/EFTA, GB, CH, US, CA, MX, BR, AR, CL, CO, VE). Dimensions: taxonomy, crosswalk, compensation, outlook, each at TARGETED, SOURCE_IDENTIFIED, DATA_AVAILABLE, IMPLEMENTED, QUALIFIED or UNSUPPORTED. Current state: taxonomy implemented for 2 (US, DE), data available for 30; crosswalk data available for 29; compensation data available for 2 (US, GB), source identified for 4, targeted for 41; outlook source identified for 27. **Nothing is QUALIFIED and no compensation row is IMPLEMENTED**; TARGETED is never reported as operational; the overall level is the weakest dimension. Source languages describe sources and never imply a country; a Russian or German interface locale selects no country (the resolver and matrix take no language input).

## 6. Occupation graph (GKB-2; QUALIFIED IMPLEMENTATION)
Tables `occupation_taxonomies` (unique scheme+edition), `graph_occupations`, `graph_occupation_identifiers` (unique taxonomy+native code), `graph_occupation_relationships`. Identity is an internal key independent of title, namespaced by scheme and edition: the same code in different schemes or editions never collides; an established legacy id is reused where the scheme is already supported (so existing ids continue to resolve). A code held by another occupation is an IdentityConflict, never an overwrite or silent merge; bulk imports are all-or-nothing; concurrent registration yields one node.

## 7. Taxonomy edition model
Schemes: esco, isco, onet_soc, soc, uk_soc, kldb, noc, sinco, cbo. Status and acquisition status are recorded from evidence: ESCO 1.2.1 and ISCO-08 and KldB 2020 available locally; UK SOC 2020 referenced indirectly (first-class versioned taxonomy is a PROPOSED DESIGN pending owner adoption); NOC, SINCO, CBO identified externally with edition `unknown` (no edition invented); SOC edition of legacy rows `unknown`. Editions are separate namespaces; an unknown edition is compatible with nothing; supersession preserves history.

## 8. Crosswalk relationship model
Relationship types equivalent, broader, narrower, related (related is never equivalent); basis source_provided, curated_manual, derived_rule (a derived rule must state its limitation and can never support equivalence); mapping status VERIFIED, PARTIAL, AMBIGUOUS, UNSUPPORTED, UNKNOWN. VERIFIED requires a registered source and a source-provided basis (service and database CHECK). Endpoints must hold an identifier in the stated edition. Conflicting statements are refused, agreeing statements corroborate, supersession keeps history. No mapping is invented: this wave registers only mappings stated by an official file.

## 9. ESCO to ISCO assessment (real files, isolated database)
Read-only import of the local ESCO 1.2.1 and ISCO-08 files into a throwaway database (not a protected store): 3,043 ESCO rows, 3,039 distinct occupations, 4 identical duplicates, 0 conflicting, 0 invalid; 619 ISCO-08 nodes; 3,039 VERIFIED broader relationships; idempotent on re-run. Assessment of the existing stored mappings: 3,039 stored, **3,018 exact, 21 lose a leading zero** (e.g. `110` stored for official `0110`; Armed forces major group 0), 0 mismatches, 0 without an official row; 613 stored ISCO nodes against 619 official codes. The graph uses the official padded code as identity and keeps the stripped legacy id as a legacy key. Six collided ISCO groups arise from stripping. The committed code ships only the importer and synthetic fixtures; official contents are not committed.

## 10. Ambiguity behaviour (PROPOSED DESIGN, owner adoption pending)
Resolver outcomes RESOLVED, AMBIGUOUS, INSUFFICIENT_CONTEXT, UNSUPPORTED, NOT_FOUND. A title shared by several nodes returns AMBIGUOUS with the candidates and the context needed; only a VERIFIED equivalence joins same-titled nodes (never related or broader); a code present in several editions is AMBIGUOUS until an edition is given; an unsupported country returns UNSUPPORTED; nothing is guessed and ambiguity is never reclassified as retrieval success.

## 11. Legacy compatibility
`LegacyCompatibility` only reads: legacy ids, native SOC/O*NET codes (edition usually unknown, reported, never auto-chosen) and titles map to linked, ambiguous or unresolved. `assess_legacy_store_mappings` opens a store read-only and rewrites nothing. Nothing in `src/copilot`, `src/agent`, `src/api`, `src/application` or the retrieval modules imports the foundation (tested by AST scan); current salary retrieval and `COUNTRY_SOURCE_PRIORITY` are unchanged.

## 12. Compensation V2 and C1-C4 extension points
Registry `evidence_class` (C1-C4), `precedence_category` (six levels, distinct from C1-C4), relationship `qualification_status`, and coverage `compensation_level` are the hooks P10C-B will use. No compensation record, currency conversion, annualisation, net/gross conversion or country substitution exists. Synthetic test occupations are structural only and are never salary evidence.

## 13. Security and safety controls
Offline only (AST test bans network/provider imports in the package); all state changes service-validated and database-constrained; synthetic override seams do not exist; baseline script is read-only and refuses protected output paths; migration seeds nothing; foundation not on any runtime path; no gate changed.

## 14. Evaluation evidence
- Focused: `tests/test_knowledge_foundation_p10ca.py` 53 tests; `tests/test_pg_p10ca.py` 4 tests on an isolated PostgreSQL 16 server (created and deleted for the run; with the existing `test_pg_p5b.py`, 11/11 pass): upgrade, CHECK/unique enforcement, concurrency, one-step downgrade, re-upgrade.
- `scripts/eval_knowledge_foundation.py` 23/23 PASS. Head pins updated to `0035_knowledge_foundation` in the affected evaluators and tests; all pinned evaluators PASS.
- Full backend suite, Ruff, `git diff --check` and the CI-safe evaluator set: see the final report for the counts of the run on the committed tree.
- Product coverage remains **BELOW GATE** (`insufficient_evidence` 93.7%, 386/412 against 95%, unchanged; the gate is not modified). This wave establishes the identity layer the 13 occupation-wiring failures depend on; it does not change any case result.
- Browser E2E: not run (no frontend change).

## 15. Limitations
Coverage and sources are inventory, not evidence. No dataset is licence-verified. UK SOC 2020, ambiguity handling and the registry vocabulary are proposals. The legacy runtime stores still contain stripped ISCO codes; they are not migrated here. The baseline is a local characterisation.

## 16. P10C-B dependencies and coverage-gap baseline
P10C-B depends on: owner licence/approval decisions for compensation sources; adoption of the ambiguity and UK SOC 2020 proposals; a pinned edition for each source; a wiring decision for the resolver. The 26 unhandled coverage cases (13 occupation-wiring, 13 ambiguous titles) are the baseline for P10C-B and compensation integration; education/outlook requalification remains P10D.

## 17. Owner decisions
D-01 adopt or amend the recovered GKB/C1-C4 specification; D-02 adopt ambiguity-state behaviour; D-03 adopt UK SOC 2020 as first-class; D-04 approve licence review order for the 31 registered sources; D-05 confirm padded ISCO codes as identity and plan for the 21 legacy rows; D-06 confirm the baseline manifest as the GKB-0 freeze.
