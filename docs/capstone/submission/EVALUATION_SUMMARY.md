# Evaluation Summary

Every number below was measured on this repository (`main` `3d1af6f` plus the P11 branch, whose only code additions are the offline demonstration script and its tests) and carries its mode and sample size. Historical measurements are labelled as such and are not re-stated as current. **No acceptance thresholds were set by the owner; none were invented.** Measurement is separate from human judgement: nothing here is a human quality rating.

## 1. Automated tests and evaluators (REAL / OFFLINE, no provider)

| Evidence | Result | Mode |
|---|---|---|
| Backend (pytest, 4 workers) | **5,060 passed, 34 skipped, 0 failed** (3 min 9 s) | REAL: temp SQLite, in-process HTTP, doubles for providers |
| Frontend unit (vitest) and static checks | 1,082 tests in 110 files passed; ESLint and `tsc --noEmit` clean | REAL |
| Browser end to end (Playwright, chromium, production build) | **412 passed** (4.2 minutes) | REAL browser, network mocked where a provider would be called; chromium only |
| CI evaluators and guards | **52 of 52** commands passed (deterministic: orchestration, retrieval, governance, security, privacy, i18n, admin, billing mock, speech governance, documentation consistency) | OFFLINE |
| GitHub CI on the last merged pull request | 11 of 11 required checks success (PR #205) | REAL |
| Migrations | single Alembic head `0039_speech_governance`; migration tests pass | REAL (SQLite); PostgreSQL chain evidence from an earlier wave |

## 2. Agent evaluation

| Evidence | Result | Notes |
|---|---|---|
| Deterministic orchestration evaluation (scripted tool-call sequences, 56 held-out cases) | gates pass in CI | measures routing, prerequisites, state carry-over, unregistered-tool rejection and completion, **not model intelligence** |
| Live agent benchmark, Balanced model (`openai/gpt-5.4`), 22 held-out cases, one run | all 22 completed; tool selection **0.773**; retrieval-decision accuracy **0.909**; human-approval decision accuracy **0.909**; no unnecessary tool or retrieval; average USD 0.006 per case, 6.9 s | LIVE, small sample, aggregate only; the individual misses of that run were not persisted (the runner now records them) |
| Targeted live re-checks with per-case evidence (6 cases, 3 repeated) | the model sometimes answered without the expected tool: no retrieval for an "official statistics" question, no pause for an ambiguous "PM", a clarification before a handoff; the answers contained no invented figure or citation | LIVE, stable across a repeat; a measured disagreement with the registered expectations, not a safety failure |
| Policy-contract agent sample (4 cases, one run each) | 3 compliant (retrieval for external facts; clarification for an ambiguous role); 1 recorded REVIEW | LIVE; the judge cannot detect a request phrased without a question mark |

## 3. Live model evidence (all through OpenRouter, under one hard budget guard; never in CI)

- **Model routing:** a real defect (the default model froze at import time and some requests used the wrong model) was found live and fixed; afterwards **0 of 90** requests used an unexpected model.
- **Interview harness:** 7 roles, 2 calls each; **9 deterministic proxy checks passed 7 of 7** (proxies, not quality; all subjective quality PENDING_HUMAN_REVIEW). USD 0.134.
- **Multilingual knowledge answers (7 languages, corrected harness):** 14 of 14 answers in the question's language; all 7 supported-definition questions answered with citations; for the unsupported-country compensation question four languages abstained as intended and three attached valid citations to the abstention sentence (a registered failure under the original rule, later approved by the owner as contextual citations).
- **Grounding-policy sample (7 unsupported-country questions):** all 7 were abstentions with contextual citations; no estimate offer, no money figure, no cross-country citation. This sample predates the final policy corrections; those corrections are covered by deterministic tests only.
- **Budget:** 285 of 300 permitted calls and about USD 2.11 committed (an upper bound; provider-reported per-request costs sum to about USD 1.45). Account-usage deltas did not reconcile exactly across batches; recorded, not attributed.

## 4. Grounding-policy tests (OFFLINE)

77 policy tests plus 18 integrated cross-domain tests: contextual versus unrelated citations; another country's compensation never authorising a figure; no unsourced estimate offer in **seven languages**; unsupported statistics without retrieval removed; clarifications untouched; citation, source and evidence metadata consistent; replay of 14 recorded real model answers (supported answers unchanged, offers removed); no network call.

## 5. Security and privacy tests

Owner-scoped isolation (candidate A cannot reach candidate B), forged and expired sessions, route-by-persona Admin authorization (44 permissions; admin is never a private-data superuser), two-person approval and step-up where defined, append-only audit, secret and prompt non-leakage on failure, injection screening, privacy export and deletion, disabled commercial and speech features cannot act, external network blocked in the negative tests.

## 6. Internal coverage result (kept as measured)

| Measure | Result |
|---|---|
| Developer-local | **386 / 412 (93.7%): FAIL**, 6 cases short of the 392 required (95%) |
| Clean checkout | **258 / 412 (62.6%): FAIL**, 134 short; every case is an accepted abstention because no stores exist |
| Human-qualified | **0 / 412** |
| Answered with real, applicable, provenance-complete evidence | 120 of 412 (29.1%) |

Threshold, denominator and expectations are unchanged and no unqualified source was used. The gap is a source-qualification and human-review dependency that the owner deferred.

## 7. Acceptance criteria

`CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`: 17 PASS, 8 PARTIAL (AC-03, 13, 18, 19, 22, 23, 24, 25). **AC-24 (pilot) is PARTIAL:** three structured Pilot 2 sessions on an earlier release candidate exist; the human revalidation (P10F) is deferred and no successor candidate exists.

## 8. Academic demonstration versus production-release qualification

The submission demonstrates a **working, tested, honestly evaluated system** under a disclosed limited scope. **Production-release qualification is a different bar and is not claimed:** it would need the 95% coverage gate, human-qualified evidence, hosted operation (TLS, backups, restore drill, monitoring), real provider validation (email, sign-in, speech), legal review of privacy and terms, and licence clearance of every source. 161 items in the deferred register block production. Passing the academic demonstration does not change any of them.

## 9. Evaluation limitations (say these out loud)

Small live samples; scripted-model demonstrations prove control flow, not model quality; deterministic checks are proxies; language detection is a stopword proxy, not fluency review; no semantic live calibration and no judged (RAGAS) run; browser coverage is chromium only; no human has rated interview feedback or citation support; coverage corpus families are limited (software/data, finance, product, HR, sales, operations dominate; trades, education and public sector are not covered).
