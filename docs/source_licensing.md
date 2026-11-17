# Source Licensing

Derived from [data/source_manifest.json](../data/source_manifest.json). Licence
terms are **not guessed**: where a source's reuse terms are not confirmed, it is
marked *review required* and treated as non-redistributable. **No datasets are
committed to this repository** — everything is acquired locally (see
[rebuild_knowledge_base.md](rebuild_knowledge_base.md)). This audit was refreshed
for the KB-2 knowledge expansion; always re-confirm current terms with each
publisher before redistributing anything derived from a source.

| Source | Publisher | Group | Licence | Acquisition | Redistribution |
| --- | --- | --- | --- | --- | --- |
| O*NET Database | O*NET / U.S. Department of Labor | occupations | CC BY 4.0 | auto-download | allowed w/ attribution |
| ESCO — Occupations & Skills | European Commission | occupations | review required | manual | not until confirmed |
| ESCO Skills–Occupations Matrix | European Commission | skills | review required | manual | not until confirmed |
| ISCO-08 Classification of Occupations | International Labour Organization (ILO) | occupations | review required | manual | not until confirmed |
| Klassifikation der Berufe (KldB) | Bundesagentur für Arbeit | occupations | review required | manual | not until confirmed |
| BERUFENET occupation information | Bundesagentur für Arbeit | occupations | review required | manual | not until confirmed |
| Occupational Outlook Handbook (OOH) | U.S. Bureau of Labor Statistics | occupations | Public domain (U.S. Government work) | auto-download | allowed w/ attribution |
| DigComp — European Digital Competence Framework | European Commission (JRC) | skills | review required | manual | not until confirmed |
| BA Kompetenzkatalog | Bundesagentur für Arbeit | skills | review required | manual | not until confirmed |
| NICE Workforce Framework for Cybersecurity | NIST / NICE | specialist | Public domain (U.S. Government work) | auto-download | allowed w/ attribution |
| European e-Competence Framework (e-CF) | CEN | skills | review required | manual | not until confirmed |
| European Qualifications Framework (EQF) | European Commission | job_architecture | review required | manual | not until confirmed |
| OPM Handbook of Occupational Groups and Families | U.S. Office of Personnel Management | job_architecture | Public domain (U.S. Government work) | auto-download | allowed w/ attribution |
| OPM General Schedule Qualification Standards | U.S. Office of Personnel Management | job_architecture | Public domain (U.S. Government work) | auto-download | allowed w/ attribution |
| UK Civil Service Success Profiles | UK Civil Service / Cabinet Office | job_architecture | Open Government Licence v3.0 | manual | not until confirmed |
| UK HR Success Profile Guides | UK Government HR | specialist | Open Government Licence v3.0 | manual | not until confirmed |
| Occupational Employment and Wage Statistics (OEWS) | U.S. Bureau of Labor Statistics | compensation | Public domain (U.S. Government work) | auto-download | allowed w/ attribution |
| Annual Survey of Hours and Earnings (ASHE) | Office for National Statistics (ONS) | compensation | Open Government Licence v3.0 | auto-download | allowed w/ attribution |
| Eurostat Earnings (Structure of Earnings Survey) | Eurostat | compensation | CC BY 4.0 | auto-download | allowed w/ attribution |
| Entgeltatlas | Bundesagentur für Arbeit | compensation | review required | manual | not until confirmed |
| Cedefop Skills Forecast | Cedefop | labour_market | review required | manual | not until confirmed |
| Cedefop Future Job Openings | Cedefop | labour_market | review required | manual | not until confirmed |
| Cedefop Labour & Skills Shortage Index | Cedefop | labour_market | review required | manual | not until confirmed |
| ESCO Handbook (methodology) | European Commission | narrative | review required | manual | not until confirmed |
| Future of Jobs Report | World Economic Forum | narrative | review required | manual | not until confirmed |
| BLS Employment Projections | U.S. Bureau of Labor Statistics | labour_market | Public domain (U.S. Government work) | auto-download | allowed w/ attribution |
| Cedefop Short-Term Analytical System (STAS) | Cedefop | labour_market | review required | — | not until confirmed |
| Cedefop Labour & Skills Shortage Index (CLSSI) | Cedefop | labour_market | review required | — | not until confirmed |
| Eurostat Job Vacancy Statistics (by occupation) | Eurostat | labour_market | CC BY 4.0 | auto-download | allowed w/ attribution |

Notes:

- "auto-download" = the manifest marks it directly downloadable and not licence-
  blocked; `scripts/download_sources.py` will fetch only these.
- "manual" = `manual_acquisition_required: true` (portal, registration or licence
  review); these are never scraped.
- "review required" licences set `licence_review_required: true` and are treated
  as non-redistributable until a human confirms the terms.
- We do **not** commit or scrape: full WEF reports, commercial CEN standards,
  LinkedIn/Glassdoor/Indeed/Levels.fyi, or proprietary salary datasets
  (Mercer/Radford/Korn Ferry/Gartner) or paid consultant databases.
- The committed synthetic corpus (`evaluations/corpus/`) and knowledge samples
  (`evaluations/knowledge_samples/`) are **not** any of the above datasets — they
  are small, general, hand-authored files for a runnable, reproducible demo.
- US federal government works (BLS, OPM) are public domain; O*NET is CC BY 4.0;
  UK ONS / Civil Service are OGL v3.0; Eurostat is CC BY 4.0. EU/DE portal
  sources (ESCO, KldB, BERUFENET, Entgeltatlas, EQF, DigComp) and CEN's e-CF are
  marked *review required* pending confirmation of reuse terms.

## Model weights (speaker diarization)

| Model | Publisher | Licence (verified 2026-11-15) | Use in this repository |
| --- | --- | --- | --- |
| `pyannote/speaker-diarization-community-1` (revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`) | pyannote (Hervé Bredin / pyannoteAI) | Weights **CC BY 4.0** ("will always remain freely accessible"); `pyannote.audio` code **MIT**; gated Hugging Face repository (auto-approval after conditions acceptance) | Governed, **inactive** scaffolding only (`src/speech/diarization.py`). Weights are not committed here and are **never downloaded by the application** (`MODEL_DOWNLOADS_AUTHORIZED` stays False): an operator accepts the gated conditions once and places them in `SPEECH_DIARIZATION_MODEL_DIR`. Self-hosting is allowed; attribution is required |

Attribution and citations that must accompany any redistribution or activation:

- Plaquet, Alexis, and Hervé Bredin. "Powerset multi-class cross entropy loss for neural speaker diarization." *Proc. INTERSPEECH 2023*.
- Wang, Hongji, et al. "Wespeaker: A research and production oriented speaker embedding learning toolkit." *IEEE ICASSP 2023*.
- Landini, Federico, Ján Profant, Mireia Diez, and Lukáš Burget. "Bayesian HMM clustering of x-vector sequences (VBx) in speaker diarization." *Computer Speech & Language*, 2022.

Facts, constraints and the activation prerequisites are in
[diarization_pyannote_community_1.md](diarization_pyannote_community_1.md) and
`OD-DIAR-01..04` in
[production/OWNER_DECISION_REGISTER.md](production/OWNER_DECISION_REGISTER.md).
The per-voice / premium pyannoteAI models (`precision-2/3`) and any hosted
pyannoteAI service are **out of scope** (paid, third-party egress) and are not
licensed for use here.
