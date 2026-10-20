# Multilingual Release Qualification (Roadmap V2.2)

**Status:** corrected 2026-10-21 against the owner's authoritative requirements. No language is production-qualified. Nothing in this document enables a feature, calls a provider, or changes a historical evaluation or coverage record (coverage stays 386/412 against 392, FAIL; AC-24 stays PARTIAL).

## 1. Owner language decisions (confirmed)

Source: `OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md` sections 1 and 9.

- **[DECISION]** R1.0 (30 November 2026, free invitation-only private beta) targets all seven existing Candidate languages: English, German, Spanish, Italian, Portuguese, French, Dutch. All seven are intended for the initial beta, **each subject to individual qualification**.
- **[DECISION]** Language selection must never silently select or change labour-market geography.
- **[PROPOSED]** Primary market mappings: English to Ireland, German to Germany, Spanish to Spain, Italian to Italy, Portuguese to Portugal, French to France, Dutch to Netherlands. They are **not individually approved country qualifications** (`[AWAITING]`, OD-LANG-02, REQ-LANG-16); each needs owner approval and source qualification before use.
- **[DECISION]** Russian is excluded from R1.0: existing code is kept where safe and Russian is removed from active Candidate language selection (REQ-LANG-14). Russian is an exposed eighth locale today, so this change has **not** been made. Any later activation is a separate future decision (OD-RU-FUTURE), not an automatic R2.0 commitment.
- **[DECISION]** Mandarin, Hindi and Arabic are assigned to R1.3 and each needs separate implementation and language-specific qualification (new locale, prompt, safety, retrieval, accessibility, legal and native review; RTL for Arabic).
- **[DECISION]** Platform Admin stays English-only for the initial release.
- **[DECISION]** Each language independently passes LG-01 to LG-14 and is reported per language; a failed mandatory gate prevents activation for real users in that locale; no claim that all seven are qualified before the evidence exists.

## 2. The rule that governs every claim

A language is **production-qualified only when every gate LG-01 to LG-14 has passed for that language, with evidence at a named SHA, a stated sample size and a named human reviewer where required**. Until then no document, page or Admin screen may call it production-qualified, and it is not offered for real-user access. Readiness and quality are tracked **separately for each language**; there is no aggregate "multilingual ready" claim (LG-13).

## 3. Per-language acceptance gates

| Gate | Name | Pass condition | Evidence | Needs a human |
|---|---|---|---|---|
| LG-01 | Locale audit complete | Interface catalogue, Mo, interview, report, legal and email text inventoried; counts of missing, unreviewed and machine-translated strings recorded | Audit table per language | No |
| LG-02 | Interface text complete | No missing keys; no English leak in chrome; protected slogan "Ask More. Be More." unchanged; no silent English fallback | `scripts/eval_i18n_l10n.py`, scanner, Playwright | Review under LG-11 |
| LG-03 | Candidate journeys pass | Onboarding, Opportunity, Company research, Prepare/Mo, Practice, History, Progress, Documents, Settings and privacy controls work end to end | Per-language Playwright run and screenshots | No |
| LG-04 | Prompts and policies verified | Grounding policy, safety policy, coaching-style and language directives behave; switching language cannot bypass a policy; directives remain allow-listed | Per-language policy suite at the release SHA | No |
| LG-05 | Interview quality validated | Localised questions, scoring, feedback and explanations; scoring is language-independent; rubric text is correct | Scoring-invariance tests plus a blinded native-reader rating | Yes |
| LG-06 | Multilingual RAG and attribution | Question in language X over sources in language Y retrieves, cites and abstains correctly; citations map to real sources; no invented translation of a source claim | Per-language retrieval and citation evaluation with sample size and limitations | Sample review |
| LG-07 | Language never sets the country | Changing language never changes career geography; the market mapping is used only as an explicit, user-visible suggestion after owner approval and source qualification for that market | Separation tests; owner decision; source approval register entry | Owner |
| LG-08 | Injection, security and privacy suites | Prompt-injection, PII/redaction, privacy-request and abuse suites pass in the language, including mixed-script input | Per-language suite results | No |
| LG-09 | Story Bank and Workspaces | Story capture and verification, share grants, invitations and report export behave in the language with owner isolation intact | Per-language flow tests plus `eval_workspace_security` | No |
| LG-10 | Legal and privacy translation qualified | Terms, Privacy, AI-transparency and consent text reviewed by a qualified person before any real-user access in that language | Signed qualification per language | Yes (counsel/translator) |
| LG-11 | Native-language human review | A named native reviewer signs off interface text, Mo output samples and interview questions/feedback | Signed review record | Yes |
| LG-12 | Mo language ownership | Mo-voiced text, including deterministic fallbacks and headings, is in the Mo conversation language; the interface language owns only chrome | Existing ownership tests extended per language | No |
| LG-13 | Readiness tracked; no aggregate claim | One status row per language per gate; claims gate extended so no page says "qualified" early | Generated matrix; claims test | No |
| LG-14 | Boundaries | Admin English-only; Russian not offered; no zh/hi/ar locale registered; speech languages unchanged | Locale-list tests | No |

## 4. Current state per language (honest, not a pass)

Source: `PRODUCTION_ACCEPTANCE_MATRIX.md` section 2 (generated). Summary: all seven languages have engineering-draft interface catalogues with enforced key parity; offline fixtures cover language/geography separation and injection for several languages; **no language has a human review, a legal translation qualification, a per-language journey run, a multilingual RAG evaluation or a live multilingual Mo quality measurement**. German is the only language with any governed knowledge-base content beyond the curated corpus. Known gaps carried from the register: non-English routing is English-keyword driven (L-ROUTE-1), no cross-language semantic retrieval measurement (L-XLANG-1), no calibrated relevance floor (L-REL-1), governed KB native content is English with some German (A-NATIVE-KB), live generated-language validation not run (R-50 / L-LIVE-LANG).

| Language | Proposed market | Gates passed | State |
|---|---|---|---|
| English | Ireland | 0 of 14 | NOT QUALIFIED |
| German | Germany | 0 of 14 | NOT QUALIFIED |
| Spanish | Spain | 0 of 14 | NOT QUALIFIED |
| Italian | Italy | 0 of 14 | NOT QUALIFIED |
| Portuguese | Portugal | 0 of 14 | NOT QUALIFIED |
| French | France | 0 of 14 | NOT QUALIFIED |
| Dutch | Netherlands | 0 of 14 | NOT QUALIFIED |

English is listed with an Ireland market only because it was proposed; the existing English knowledge content is largely US-sourced, so the Ireland mapping needs its own source qualification.

## 5. Work packages (WP-08 Multilingual programme)

| Package | Scope | Gates | Depends on |
|---|---|---|---|
| WP-08A Audit | REQ-LANG-01 inventory and baseline numbers per language | LG-01, LG-02 | none |
| WP-08B Boundaries | REQ-LANG-14 remove Russian from active selection; REQ-LANG-12 Admin English-only check; REQ-LANG-07 language/geography tests | LG-07, LG-14 | none (owner decision made) |
| WP-08C Journeys | REQ-LANG-02 candidate journeys in seven languages; REQ-LANG-05 Story Bank and Workspaces | LG-03, LG-09, LG-12 | WP-08A |
| WP-08D AI behaviour | REQ-LANG-03 prompts and policies; REQ-LANG-04 interview questions, scoring, feedback | LG-04, LG-05 | WP-08A |
| WP-08E Retrieval | REQ-LANG-06 multilingual RAG and cross-language attribution; REQ-LANG-16 market and source qualification | LG-06, LG-07 | OD-LANG-02, WP-06 |
| WP-08F Security and privacy | REQ-LANG-08 per-language injection, security and privacy suites | LG-08 | WP-08A |
| WP-08G Human and legal | REQ-LANG-09 native review; REQ-LANG-10 legal/privacy translation qualification | LG-10, LG-11 | OD-LANG-03, OD-LANG-04 (long lead) |
| WP-08H Tracking | REQ-LANG-11 per-language status; REQ-LANG-13 no early claim | LG-13 | all |
| WP-08I Future languages | REQ-LANG-15 Mandarin, Hindi, Arabic plans (R1.3) | future | R1.0 complete |

Existing register issues that belong to this programme are tagged `language_programme: true` with their gates in `PRODUCTION_ISSUE_RECONCILIATION.json`.

## 6. Release rule for a language that misses its gates

Owner decision: a failed mandatory locale gate prevents activation for real users in that locale. A language that has not passed every gate by the freeze date is therefore not offered to beta users at R1.0 and is shown to be unavailable, rather than being offered with a quality caveat. This keeps all seven as the target without a false qualification claim. Whether to delay the release instead is part of OD-SCOPE-01.

## 7. Preserved records

Historical evaluation results, the 95% coverage gate result, RC-P10-003 artifacts, the capstone acceptance ledger and the 394-row register are unchanged. This document adds requirements; it upgrades nothing.
