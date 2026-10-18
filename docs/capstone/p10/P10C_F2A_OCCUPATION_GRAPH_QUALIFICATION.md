# P10C-F2A — Occupation Graph Qualification (US SOC 2018)

**Status: NOT PERFORMED — blocked behind the acquisition gate** (see [acquisition](P10C_F2A_US_SOURCE_ACQUISITION.md)). The canonical graph was not populated; no SOC node was created from unofficial text.

## Verified before population
Official source: BLS 2018 SOC (`soc_structure_2018.xlsx`, `soc_2018_definitions.xlsx`), whose page states the 2018 revision is complete. The SOC structure levels (detailed, broad, minor, major) are from the official structure file; the earlier dossier figure 867/459/98/23 came from a search-level reading and is **NOT VERIFIED** until counted from the file.

## Population rules (to apply when acquisition proceeds)
Official code, name, level, parent and child exactly as published; taxonomy edition 2018; source id `us_soc_2018` and edition; provenance to the manifest SHA-256; qualification state set by the registry; no code invented, no hierarchy inferred from titles, no duplicate node, no overwrite of unrelated nodes, historical editions preserved, idempotent re-import and safe rollback of an isolated batch. Occupation identity uses exact SOC codes and exact official labels only; the existing resolver states (RESOLVED, AMBIGUOUS, INSUFFICIENT_CONTEXT, UNSUPPORTED, NOT_FOUND) are reused and a similarity match is never classification evidence. SOC-to-ISCO is out of scope (D-20 deferred): unresolved, no equivalence claimed.

## Results
SOC node counts: NOT RUN. Hierarchy qualification: NOT RUN. Linkage results: NOT RUN. Ambiguity behaviour: unchanged existing resolver, not re-qualified with SOC data.
