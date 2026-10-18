# P10C-F2B — UK Occupation Graph (UK SOC 2020)

**Status: NOT POPULATED — blocked behind Package 2 authorization** (see [the authorization request](P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md)). No UK SOC node, relationship or alias exists in any database; nothing was invented.

## Verified before population
The ONS UK SOC 2020 page states the structure: **9 major, 26 sub-major, 104 minor and 412 unit groups** (SOC 2010: 9, 25, 90, 369), published as an Excel file (full structure and unit-group descriptions), a PDF and a ZIP under OGL v3.0. The Excel file name carries `20260827` while the page says "Last updated: 5 May 2026": the current file version is NOT VERIFIED until the file is read. The sheet layout, code format and how the hierarchy is expressed are NOT VERIFIED (the file is not acquired), so no parser was written against a guessed layout.

## Reuse (no second subsystem)
The existing `OccupationGraph`, `TaxonomyCatalogue` (a `uk_soc` namespace already exists with code pattern 1 to 4 digits), `SourceRegistry`, registry-gated importers and the multilingual resolver are reused. The US population module (`us_sources.populate_soc_graph`) is the pattern: official code, official label, edition, level, published parent, definition, source row and file hash in provenance; one transaction; idempotent; parent from the published layout only, never from titles.

## Population plan once authorised
Register `uk_soc` edition `2020` as current, acquired; import every code at its published level (major, sub-major, minor, unit group); parent links `broader`/`source_provided`/`verified` from the published hierarchy; check counts against 9/26/104/412; reject any code outside the file; keep US SOC 2018 untouched (taxonomy isolation: the same title in two taxonomies is two nodes).

## Identity and safety rules (already enforced by the existing architecture)
- UK SOC 2020 and US SOC 2018 are different national classifications; no crosswalk or equivalence is created from equal-looking titles; SOC-to-ISCO stays out of scope (D-20 deferred) even though ONS publishes a title-level SOC 2020 to ISCO-08 mapping page (not acquired).
- Edition-explicit lookup: a code in another edition resolves to `identifier_not_in_graph`; the ASHE file's edition must be confirmed from the file before its codes are linked.
- Titles resolve only through exact official labels or curated aliases; an alias for a UK title would need its own evidence review against UK SOC 2020 definitions. The five US alias proposals are **not** assumed to carry over: no UK alias evidence was assessed (the structure is not acquired). Word containment is not evidence. Unresolved titles stay unresolved; Data Analyst and Product Manager stay unresolved.
- Country-scoped aliases are ignored for another country (existing guard), so a US alias can never answer a UK request.

## Counts
UK SOC nodes: 0. Relationships: 0. Aliases: 0 proposed, 0 qualified. Resolver results: not applicable (nothing to resolve against).
