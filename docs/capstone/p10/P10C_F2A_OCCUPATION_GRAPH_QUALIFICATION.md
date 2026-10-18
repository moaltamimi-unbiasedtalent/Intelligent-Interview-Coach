# P10C-F2A — Occupation Graph Qualification (US SOC 2018)

**Status: SOC 2018 GRAPH POPULATED in the isolated non-production database `p5b_f2a_us` (PostgreSQL). Not populated anywhere else; no runtime path imports it.**

## Source
Official BLS files `soc_structure_2018.xlsx` and `soc_2018_definitions.xlsx` (hashes in the acquisition manifest). Counts verified from the files: **23 major, 98 minor, 459 broad, 867 detailed = 1,447 codes**; the two files have identical code sets, identical levels and identical titles; all codes match xx-xxxx; no duplicates. Military occupations (major group 55) are included in the graph although OEWS publishes no wages for them.

## Population (`src/knowledge_foundation/us_sources.py`, `populate_soc_graph`)
Each code becomes one canonical node with identifier `soc@2018`, the official label as native label, and provenance (SOC level, published parent, official definition text, structure row, both file hashes, transformation `p10c-f2a-soc-1`). Each published parent link becomes a `broader` relationship (child to parent), basis `source_provided`, status `verified`, qualification `engineering_checked`, source `us_soc_2018`. The hierarchy is the published file layout, never inferred from titles. One transaction; idempotent.

| Result | Value |
|---|---|
| Nodes / identifiers | 1,447 / 1,447 |
| Parent relationships | 1,424 (= 1,447 minus the 23 majors) |
| Re-import | 0 nodes and 0 relationships added |
| Population time / re-import time | 2.6 s / 2.0 s |
| Published-hierarchy prefix exceptions | 5 (29-1221, 29-1222, 29-1223, 29-1224, 29-1229 sit under broad 29-1210; used as published) |

The prefix check is only a cross-check; where it disagrees the published hierarchy wins.

## Identity rules
Exact SOC code in edition 2018 only; another edition (for example 2010) resolves to `identifier_not_in_graph`. Non-canonical BLS aggregates have no node (POLICY A). SOC to ISCO is out of scope (D-20 deferred): no equivalence, no crosswalk, unresolved. No semantic similarity is used as classification evidence. Common job titles are **not** official labels: none of the seven US wiring-case titles ("Software Developer", "Accountant", ...) matches an official SOC label exactly, so title resolution still needs curated aliases (D-08).

## Hierarchy and broader fallback
Because verified `broader` links now exist, the existing resolver may offer a labelled broader-group result (specificity `broader_group`, class C2) for a detailed occupation that lacks the requested measurement, as the P10C-C policy defines. See the evidence document for the observed behaviour and the open policy question.

## Curated aliases and broader fallback (P10C-F2A-Q update)
The graph is unchanged (1,447 nodes, 1,424 relationships). Five curated alias proposals (Software Developer, Human Resources Manager, Sales Manager, Accountant, Financial Analyst) were loaded in the isolated database from the official-title containment rule and are `engineering_checked`, none `qualified`; Data Analyst and Product Manager have no authoritative evidence and still abstain. The earlier statement that verified `broader` links may serve a labelled broader-group result as the primary evidence is **superseded**: under the owner rule a parent group's statistic appears only as `contextual_evidence` beside an abstention. Details: [decision report](P10C_F2A_Q_EVIDENCE_QUALIFICATION_DECISION_REPORT.md).
