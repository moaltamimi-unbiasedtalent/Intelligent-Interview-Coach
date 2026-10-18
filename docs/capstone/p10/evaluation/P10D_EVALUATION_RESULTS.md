# P10D knowledge-base requalification: generated results

Corpus v1.0.0, 154/154 cases behave as pinned, determinism hash `a3ad0b254ceb2b4d`. Mode A and B only; mode C (a real model run) was NOT performed.

## Families

| Family | Cases | Pinned behaviour holds |
|---|---|---|
| citation | 5 | 5 |
| component | 33 | 33 |
| geography | 21 | 21 |
| governance | 6 | 6 |
| grounding | 7 | 7 |
| ingestion_security | 11 | 11 |
| multilingual | 14 | 14 |
| occupation | 10 | 10 |
| out_of_scope | 2 | 2 |
| research_cache | 5 | 5 |
| retrieval | 33 | 33 |
| security | 7 | 7 |

## Retrieval metrics (SYNTHETIC RELEVANCE JUDGMENTS, offline lexical embedder (not semantic quality))

| Language | Judged | hit@5 | recall@5 | precision@5 | MRR |
|---|---|---|---|---|---|
| ALL | 31 | 1.0 | 0.9731 | 0.3296 | 0.8925 |
| ar | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| de | 5 | 1.0 | 0.9 | 0.44 | 1.0 |
| en | 13 | 1.0 | 0.9744 | 0.2295 | 0.7821 |
| es | 2 | 1.0 | 1.0 | 0.375 | 1.0 |
| fr | 4 | 1.0 | 1.0 | 0.2 | 1.0 |
| it | 1 | 1.0 | 1.0 | 0.25 | 1.0 |
| mixed | 2 | 1.0 | 1.0 | 0.35 | 0.75 |
| nl | 1 | 1.0 | 1.0 | 0.3333 | 1.0 |
| pt | 1 | 1.0 | 1.0 | 0.2 | 1.0 |
| ru | 1 | 1.0 | 1.0 | 1.0 | 1.0 |

## Multilingual matrix (cases that reach the FULLY capable behaviour / cases)

| Language | ambiguous_query | country_detection | cross_language | diacritic_lexical | injection_detection | lane_routing | mixed_language | occupation_resolution | out_of_scope | retrieval | security | stale_source | unsupported_language |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| en | 1/1 | 3/3 |  |  | 1/1 | 1/1 |  |  | 0/2 | 10/10 | 1/1 | 0/1 |  |
| de |  | 3/3 | 0/1 | 2/2 | 4/4 | 0/2 |  | 4/5 |  | 3/3 |  |  |  |
| ar |  |  |  |  | 1/1 |  |  |  |  |  |  |  | 3/3 |
| fr |  | 2/2 |  | 3/3 | 2/2 | 0/1 |  | 1/1 |  | 2/2 |  |  |  |
| es |  | 1/1 |  |  | 1/1 |  |  |  |  | 2/2 |  |  |  |
| it |  | 1/1 |  |  | 1/1 |  |  |  |  | 1/1 |  |  |  |
| pt |  | 2/2 |  |  | 1/1 |  |  |  |  | 1/1 |  |  |  |
| nl |  | 1/1 |  |  | 1/1 |  |  | 0/1 |  | 1/1 |  |  |  |
| ru |  | 0/1 |  |  | 2/2 |  |  |  |  |  |  |  | 2/2 |
| mixed |  |  |  |  |  |  | 2/2 |  |  |  |  |  |  |

## Documented limitations (pinned, not hidden)

- **L-XLANG-1** (R-X-01; capability met in 0/1): The offline lexical embedder has no cross-language semantics; cross-language retrieval needs a semantic embedder (a paid run, not authorised) and cannot be measured here.
- **L-LANG-AR** (R-AR-01, L-13; capability met in 2/2): Arabic is not a supported product, interface or knowledge-base language: no structured data, no router keywords and no resolver aliases exist for it. Only lexical document matching is measured.
- **L-LANG-RU** (R-RU-01; capability met in 1/1): Russian is an interface language only (not an ESCO or knowledge-base language). Only lexical document matching is measured.
- **L-REL-1** (R-OOS-01, R-OOS-02, O-06, O-07, X-01; capability met in 0/5): There is no relevance floor: a query with no real match (out of scope, or an existing occupation without role data) still receives the nearest narrative chunks, which are cited as evidence. The only floor is similarity <= 0 (added in P10D); with the offline hash embedder shared function words create small positive similarity. A calibrated floor needs a semantic embedder run (not authorised).
- **L-STALE-1** (R-STALE-01; capability met in 0/1): The narrative lane has no publication-date or staleness handling: a conflicting older document is returned beside the current one (the year is carried as metadata only).
- **L-RU-INFLECT** (L-07; capability met in 0/1): Country names are matched as whole forms; an inflected Russian name (for example 'в Германии') is not recognised, so no geography is selected (it fails safe: nothing is substituted).
- **L-ROUTE-1** (L-10, L-11, L-12, L-14, T-30; capability met in 0/5): The deterministic router, occupation phrase extraction and structured lanes are English-keyword driven; a non-English question reaches the structured stores only if the (paid, unmeasured) query-translation model rewrites it. Non-English questions fall to the narrative lane.
- **L-ANSWER-GUARD** (C-19; capability met in 0/1): The occupation-grounding guard (a named occupation that matched nothing withholds narrative evidence) exists in the retrieval-only path (retrieve_evidence, used by the Mo agent) but NOT in answer() (the deterministic /career/chat path), which remains as before.
- **L-ALIAS-1** (T-09; capability met in 1/1): Alias resolution is exact-substring: a German near-synonym that is not a stored alias is not mapped to an occupation (correct: no equivalence is invented).
- **L-CODE-1** (T-11; capability met in 1/1): The runtime resolver matches titles and aliases only; an official occupation code in the question does not resolve an occupation.
- **L-INGEST-SIZE** (I-05; capability met in 0/1): The operator-run legacy ingestion loaders impose no per-file size limit (the governed Admin pipeline does). Operator trust boundary; not candidate-reachable.
- **L-META-1** (I-09; capability met in 0/1): A sidecar .meta.json written by the operator can override provenance metadata (title, source_url). Operator trust boundary; not candidate-reachable.

Required tags exercised: 88/88. Index: 28 chunks, 0 bytes of Chroma data.
