# Multilingual Execution Plan (Track F)

**Status:** PROPOSED engineering plan, 2026-10-21. It executes the owner's language decisions and the gates already defined in `../MULTILINGUAL_RELEASE_QUALIFICATION.md` (LG-01 to LG-14) and `../PRODUCTION_ACCEPTANCE_MATRIX.md`; it does not redefine them. No language is production-qualified today. R1.0 targets English, German, Spanish, Italian, Portuguese, French and Dutch, each activated only when all fourteen gates pass for it. Russian is removed from active Candidate selection (code preserved). Mandarin, Hindi and Arabic are R1.3. Admin stays English-only. Proposed market mappings are not individually approved qualifications.

## 1. Packages

| Package | Scope | Gates | Depends on | Effort (days) | Calendar-bound |
|---|---|---|---|---|---|
| 06A Audit and boundaries | Per-language audit; Russian removed from active selection; language/geography separation tests; per-language readiness tracking; claim discipline; Admin English-only check | LG-01, LG-02, LG-07, LG-13, LG-14 | none | 4-6 | no |
| 06B Journeys, Story Bank, Workspaces | Per-language Playwright journeys and fixes | LG-03, LG-09 | 04A, 04B, 06A | 6-9 | no |
| 06C AI behaviour | Prompt and policy behaviour, scoring invariance, localized policy sentences | LG-04, LG-05, LG-12 | 01B, 06A | 5-8 | rating protocol |
| 06D Retrieval | Multilingual retrieval, cross-language attribution, abstention | LG-06 | 02B | 6-9 | no |
| 06E Security and privacy suites | Per-language injection and privacy suites incl. mixed-language | LG-08 | 01A, 06A | 5-8 | no |
| 06F Native and legal review | Seven native reviewers; qualified legal translation | LG-10, LG-11 | 06A, OD-LANG-03, OD-LANG-04 | 2-4 | yes (longest lead) |
| 06G Human AI evaluation | Blinded ratings per language | PG-07 | 06C, 00A | 3-5 | yes |

## 2. Per-language activation mechanism (proposed)

A failed mandatory gate must prevent activation for real users in that locale. Proposed design: a server-side, code-defined list of candidate-active locales (the same pattern as the existing gate constants and `src/locales.py` declarations), exposed through the existing capabilities endpoint so the frontend language selector, onboarding and settings offer only active locales; an inactive locale is neither selectable nor accepted by the API for new sessions. The list changes only through a code change that cites the evidence (so it cannot be flipped from Admin), and a test asserts that every active locale has all fourteen gate records marked passed in the readiness tracker. Existing user preferences for an inactive locale fall back to the default interface language without changing geography. This mechanism ships in 06A.

## 3. Execution sequence

1. **Week 1 (06A):** audit every locale against the catalogue, Mo localized text, interview and report prompts, legal pages and emails; remove `ru` from the selectable set; add the separation tests (changing language leaves geography unchanged in every flow); create the per-language readiness records.
2. **Weeks 1 to 5 (06F, calendar-bound):** appoint reviewers (00A, OD-LANG-03/04), schedule native review sessions and legal translation qualification early, because engineering cannot compress them. Native reviewers receive the frozen catalogue and sample outputs for their language; sign-off records name the reviewer, scope, findings and resolution.
3. **Weeks 2 to 3 (06C, 06E):** run per-language policy, scoring-invariance and injection/privacy suites after 01A and 01B land; fix failures; any language that fails stays inactive.
4. **Weeks 3 to 4 (06D):** multilingual retrieval and citation evaluation once 02B provides real embeddings; report per-language sample sizes, abstention and attribution accuracy, and the limits of the evaluation. Native-phrasing queries are measured, not assumed.
5. **Week 4 (06B):** per-language journeys, Story Bank and Workspaces on the staging stack.
6. **Weeks 4 to 5 (06G):** blinded human evaluation of interview questions, feedback and Mo answers per language using the existing quality harness framework; results recorded with sample sizes.
7. **Week 5:** the readiness tracker is updated per language and gate; the activation list is set from evidence only.

Proposed language waves (an engineering suggestion, not an owner decision): wave 1 English and German (existing curated content and some German governed content), wave 2 Spanish, French, Italian, Portuguese and Dutch. All seven remain the R1.0 target; the waves only order the work.

## 4. Data and sample requirements

Per language: a frozen interface string inventory, a set of Mo conversation prompts, interview question and answer samples, retrieval queries with expected sources, injection and mixed-language attack fixtures, and legal text. Sample sizes and acceptance thresholds are not set here: they are part of OD-GATE-THRESHOLDS and must be approved before the corpora are frozen. Synthetic or consented data only; no real candidate data.

## 5. Risks and known gaps

Non-English routing is English-keyword driven (L-ROUTE-1); no calibrated relevance floor (L-REL-1); cross-language semantic retrieval is unmeasured (L-XLANG-1); the governed knowledge base content is English with some German (A-NATIVE-KB); live generated-language quality has never been run (R-50, L-LIVE-LANG); all seven interface catalogues are engineering translations. The qualification can fail for a language; that language is then not offered.

## 6. Exit gate

For each language offered: LG-01 to LG-14 pass with evidence at the release SHA; for each language not offered: it is hidden and documented as unavailable. No aggregate multilingual claim is made until every offered language has passed (LG-13).
