# Knowledge Coverage Report (Phase 7C)

Measured coverage of the runtime Career Intelligence knowledge after integrating the Phase 7B
governed normalized corpus into the runtime stores. Generated from
`evaluations/knowledge/coverage_report.json` (counts), the retrieval evaluation
(`scripts/eval_knowledge_retrieval.py`), and the coverage audit
(`scripts/audit_knowledge_coverage.py`). All numbers are from a real local build; the
pre-Phase-7 snapshot is `evaluations/knowledge/pre_phase7_runtime_baseline.json`.

## Runtime build provenance

`data/knowledge/build_metadata.json` — runtime pipeline **7C.1**, built from normalized
pipeline **7B.1** (raw → normalized → runtime), git commit recorded. Stores are rebuilt from
`data/normalized/` and promoted atomically; the vector index uses the free offline
`local-hash-v1` embedder (zero paid calls).

## Before → after (counts)

| Store | Before (pre-7C) | After (7C) | Note |
|---|--:|--:|---|
| Occupations (roles) | 8,035 | 8,035 | governed rebuild, same corpus |
| Occupation aliases | 23,587 | 23,579 | normalized-form dedup (−8) |
| Compensation records | 1,920 | 1,913 | semantic dedup (−7) |
| Labour-market records | 2,973 | 2,398 | **deduped** 560 exact-duplicate CLSSI shortage rows (quality ↑, count ↓) |
| Competencies | 2,275 | 2,275 | NICE/DigComp from normalized + e‑CF/BA supplementary |
| Credentials | 5 | 5 | fixtures (not yet normalized) |
| Vector passages | 3,528 | 14,087 | + 10,559 governed structured passages (occupation/task/knowledge/competency) |

Count is not quality (§45): the labour-market decrease is the removal of exact-duplicate
shortage rows the previous direct-from-raw load left in; the occupation/compensation deltas are
semantic de-duplication. No occupation, compensation source, or competency framework was lost.

## Before → after (retrieval behaviour)

Deterministic evaluation over **81 held-out cases**, no LLM calls
(`evaluations/knowledge/retrieval_cases.json`).

| Metric | Before | After |
|---|--:|--:|
| Overall pass rate | 0.889 | 0.914 |
| **Safety pass rate** | **0.444** | **1.000** |
| **Unknown-role safety** | **0.167** | **1.000** |
| Citation completeness | 1.000 | 1.000 |
| Geography correctness | 1.000 | 1.000 |
| Evidence coverage (non-safety) | 0.971 | 0.886 |
| No-evidence rate | 0.037 | 0.210 |

The headline is safety. Before Phase 7C, nonsense/unknown occupations ("moon whisperer",
"chief vibes officer") returned five generic narrative chunks presented as if occupation-
specific — the §39/§40 generic-vector-fallback defect. The 7C occupation-grounding guard fixes
this: **evidence-coverage falling and no-evidence-rate rising are the *intended* effect** — the
pipeline now withholds ungrounded evidence for unknown occupations and asks for clarification on
ambiguous ones, instead of returning misleading matches. Grounded queries are unaffected.

## Domain coverage (after)

Occupations backed by each evidence domain (of 8,035):

| Domain | Occupations | % |
|---|--:|--:|
| Skills | 3,962 | 49.3% |
| Relationships | 3,709 | 46.2% |
| Tasks | 1,526 | 19.0% |
| Education/training | 1,173 | 14.6% |
| Attributes | 1,173 | 14.6% |
| Technology skills | 923 | 11.5% |
| Activities | 911 | 11.3% |
| Knowledge | 903 | 11.2% |

Skills/relationships coverage is broad (ESCO + O*NET); tasks/knowledge/technology/activities
are concentrated in the O*NET-detailed occupations (that is where those O*NET rating rows
exist), which is honest source coverage, not a defect.

## Geography (kept separate, §36/§57)

- **Compensation**: US 1,386 (BLS OEWS), UK 527 (ONS ASHE). Germany occupation-specific
  compensation is **aggregate only** (Eurostat SES) — a DE salary query returns
  insufficient-occupation-specific or clearly-labelled EU/DE context, and **never** substitutes
  US BLS / UK ONS (enforced in the compensation lane and verified by the evaluation).
- **Labour market**: US (BLS projections), EU aggregates + member states (Cedefop CLSSI,
  Eurostat vacancies) — EU aggregates are never counted as Germany.

## Top remaining gaps (legitimate; §47)

1. **German occupation-specific compensation** — aggregate only (Eurostat SES); Destatis not
   yet acquired. Reported honestly; not substituted.
2. **Router coverage** — some role phrasings ("data scientist role overview", "what does an
   electrician do") are routed to the vector lane and return general (not occupation-grounded)
   evidence. A routing-coverage gap, not a safety gap; candidates still see grounded or
   clearly-general evidence, never fabricated role facts.
3. **Credentials** — fixtures only (5 records); regulated-profession coverage not yet normalized.
4. **Emerging AI roles** (AI Engineer, LLM Engineer) — absent from the official taxonomies;
   return general/insufficient by design rather than a fabricated taxonomy entry.
5. **Compensation → canonical-occupation linkage** — 825 / 1,913 via official codes only; no
   fuzzy title matching by design.

## How to reproduce

```bash
python scripts/knowledge/build_normalized_knowledge.py --all      # raw → normalized (7B)
python scripts/knowledge/build_runtime_knowledge.py --all         # normalized → runtime (7C)
python scripts/audit_knowledge_coverage.py                        # coverage
python scripts/eval_knowledge_retrieval.py                        # retrieval behaviour + safety
python scripts/check_demo_knowledge.py                            # readiness + smoke
```
