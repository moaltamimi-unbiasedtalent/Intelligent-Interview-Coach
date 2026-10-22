# 06E Evidence: per-language injection, security and privacy suites (REQ-LANG-08; LG-08 and PG-03 contribution)

Branch `feat/06e-language-security-suites`, base `origin/main` f5cf7cb (Alembic head unchanged: NO migration, none added). Wave 3b package. No frontend change. No live or paid call.
LG-08 is NOT claimed met for any language and PG-03 is NOT claimed met. Review package for the owner's future independent security reviewer: `06E_SECURITY_REVIEW_PACKAGE.md`. Generated per-language tables: `06E_LANGUAGE_INJECTION_REPORT.md`.

## Requirement mapping

| Requirement / brief item | Covered | How | NOT covered |
|---|---|---|---|
| (1) Per-language dev-split attack and benign cases for all seven languages incl. mixed language and script | Yes | 267 new cases (`INJ-L6-*` first round, `INJ-L6P-*` probe), 138 attacks and 129 benign; en, de, fr, es, it, pt, nl and `mixed`. Classes: direct, indirect (job description), retrieved document, encoded (Base64, look-alike letters), role play, tool abuse, cross-user, secret exfiltration, language-switch bypass, mixed script; benign plain and look-alike (18 per non-English language) | Engineering-authored, NOT native-reviewed (recorded in the manifest as `native_reviewed: false`); small cells (10 to 40 cases) |
| Strict held-out discipline | Yes | Held-out never read, printed, tuned against or changed; ids checked against the split rule by id only; `split: dev` recorded per row; tests assert the frozen hash, the byte-identical first 239 lines, that every new case is dev and that the language report never evaluates held-out | Held-out was read before by 01A (unchanged fact); no fresh held-out for the seven languages exists |
| (2) Per-language report, report only | Yes | `eval_injection_corpus.py --language-report[-md]`: detection and false positives per language, per language and category, per case source, with sample sizes and a limitations section, dev only; a CI report-only step added; `--enforce` stays fail-closed (exit 3, tested, also with `--language-report`) | No threshold exists (OD-GATE-THRESHOLDS); CI cannot fail on quality |
| (3) Per-language PII, redaction and privacy-request suites; abuse and rate suites unchanged | Yes for the tested paths | `tests/test_language_privacy_06e.py` (60 tests): redaction of e-mail, phones, national identifiers and IBAN per language; no personal data in logs, audit or another user's export; erased on account deletion; no echo of blocked text; abuse and rate suites untouched and re-run | Names and street addresses are not pattern-redactable (recorded in a test); privacy requests through the Admin queue not re-tested per language (language independent, covered by W10.10 tests, re-run) |
| (4) Fix rule gaps on dev, smallest additive change, report before/after false positives | Yes | See "Changes" and the before/after table; nothing weakened | Detectors remain lexical; the dev numbers are in-sample |
| Interview input guard languages | Done as an additive stage, ON, with evidence; OWNER DECISION OD-INPUT-GUARD-LANGUAGES recorded | The stage adds no dev false positive (198 benign cases, per language and overall identical with and without it); one constant switches it off | The sample is small; ratification is the owner's |
| (5) Review-ready package: tested, not tested, open questions | Yes | `06E_SECURITY_REVIEW_PACKAGE.md` | Not an independent review |

## Changes

| Area | File | Change |
|---|---|---|
| Corpus | `evaluations/injection/corpus.jsonl`, `manifest.json` | 267 dev cases appended (first 239 lines byte-identical, hash asserted); manifest records the 06E extension, counts, new corpus hash; held-out hash unchanged |
| Rules | `src/copilot/security/injection_rules.py` | additive rule entries: 13 English and 79 multilingual (override of guidelines, DAN and no-rules persona, note addressed to AI systems, new instructions for the assistant, score manipulation, previous users' data, tool abuse, secret key and environment-variable requests, verb-final "forget all previous rules" in de and nl, "ignore ... precedentes" noun-adjective order in fr and it, "voorgaande" in nl, hidden-instruction requests, mixed-language override, one Russian persona rule); chunk-surface relaxation for first-person past obligation |
| Scanner | `src/copilot/security/injection.py` | the confusable-folded copy now also feeds the multilingual rules (look-alike letters inside a non-English attack); new `scan_multilingual` (non-English rule sets only, boundary and negation aware) |
| Interview guard | `src/security.py`, `src/constants.py` | one additive stage in `detect_injection` (`multilingual=` argument, `MULTILINGUAL_INPUT_GUARD_ENABLED = True`, a code constant): no English rule runs in it, it can only raise a score |
| Sanitizer | `src/observability/sanitizer.py` | Unicode-aware e-mail pattern; IBAN, Spanish DNI and NIE, Italian codice fiscale and UK insurance number patterns (applied before the phone pattern) |
| Evaluator | `scripts/eval_injection_corpus.py` | per-language report, `--language-report`, `--language-report-md`, a comparison column for the English-only interview guard; report only |
| CI | `.github/workflows/ci.yml` | one report-only step (`--language-report`) |
| Tests | `tests/test_language_injection_06e.py` (30), `tests/test_language_privacy_06e.py` (60) | new; one existing assertion widened (`test_injection_precision_w2_01a.py::test_every_case_added_after_the_freeze_is_dev` now also accepts the `INJ-L6-`, `INJ-L6P-` prefixes and still asserts every added case is dev) |

Not touched: the output guard, `src/agent/*`, `deploy/*`, 06H (`src/language_activation.py`), frontend, migrations, the release tracker and the package register.

## Security and privacy impact

- Strictly additive recall on every surface, one documented chunk-surface relaxation (retrieved chunks only, never typed input), one new optional stage in the interview guard. No existing rule, weight or threshold changed and the output guard is untouched.
- Interview guard: a candidate whose job description or background trips the new stage is refused with the existing fixed message; a false positive therefore has a user cost. Evidence says none on the 198 dev benign cases; unseen text will differ.
- Telemetry: e-mail addresses with accented or non-Latin letters and four more identifier formats are now redacted; ISO dates are still over-redacted as phone numbers (fail-safe, unchanged).
- No new data is stored, logged or exported; no secret handled; synthetic data only.

## Measured results (dev split only; in-sample; report only)

| Group | Cases (atk / ben) | Detection before | after | False positives before | after |
|---|---|---|---|---|---|
| Pre-06E dev cases | 127 / 69 | 100.0% | 100.0% | 10.1% (7 cases) | 10.1% (the same 7) |
| 06E cases | 138 / 129 | 39.1% | 100.0% | 6.2% | 3.1% (4 English) |
| All dev | 265 / 198 | 68.3% | 100.0% | 7.6% | 5.6% |

BEFORE is the `origin/main` detector code run on the same corpus; AFTER is this branch. The first-round probe measurement (about 31% detection, 14 false positives on 43 benign) is the better generalisation hint; see the review package. Per-language tables: `06E_LANGUAGE_INJECTION_REPORT.md`.
Held-out aggregates were not re-measured. No threshold is approved, so none of these is a pass or fail.

## Tests and commands

| Check | repo `.venv` (Python 3.11) | fresh-dependency canary `~/.cache/ask4mo/ci_venv` |
|---|---|---|
| Targeted: `pytest -p no:cacheprovider tests/test_language_injection_06e.py tests/test_language_privacy_06e.py tests/test_injection_precision_w2_01a.py tests/test_injection_corpus_01a.py tests/test_copilot_security.py tests/test_security.py tests/test_security_hardening.py tests/test_security_ph6.py tests/test_security_phase11.py tests/test_observability_p7d.py tests/test_agent_grounding.py tests/test_candidate_grounding_policy.py tests/test_p10d_r1_grounding_coverage.py tests/test_ci_shards.py tests/test_privacy_legal_w10_10.py tests/test_w98_privacy_controls.py tests/test_rate_limit_adapters.py` | 533 passed | 533 passed |
| 06E suites alone (30 injection + 60 privacy) | 90 passed | 90 passed |
| `ruff check .` | All checks passed | not run separately (same source) |
| `python scripts/ci_test_shards.py verify --shards 4` | OK, 302 test files, each in exactly one shard | not run separately |
| All CI evaluators (50 commands parsed from `.github/workflows/ci.yml`: every `eval_*.py`, `check_product_coverage_baseline.py`, `gen_product_coverage_cases.py`, the global corpus, the KB requalification and speech runs with their CI arguments; the existing full injection-corpus step was run for its exit code with its output discarded, so no held-out aggregate was read) | not run | 50 of 50 exit 0; the working tree stayed clean |
| Full suite `pytest tests -n 3 --dist loadfile` (once, before the final push) | not run (one full suite at a time) | 6366 passed, 43 skipped, 0 failed in effect: the run reported 1 failure, `test_language_readiness_06a::test_committed_audit_table_is_current_and_labels_every_language_unqualified`, which needs the Node module `esbuild` (the worktree has no `frontend/node_modules`; the symlink to the main checkout was created afterwards and the test then passed, 10 of 10 in that file). It is an environment limit of the worktree and not related to 06E (no catalogue key was added) |
| `python scripts/eval_injection_corpus.py --language-report` | exit 0, report only | exit 0 |
| `python scripts/eval_injection_corpus.py --enforce` | exit 3 (fails closed; asserted by a test) | |

Commands: the pytest lines above; `ruff check .`; `python scripts/ci_test_shards.py verify --shards 4`; `python scripts/eval_injection_corpus.py --language-report-md <path>` (generates `06E_LANGUAGE_INJECTION_REPORT.md`); the evaluators through a small runner that executes each `python scripts/...` command of `ci.yml` with the canary interpreter.
The base `origin/main` was unchanged when the branch was finalised (f5cf7cb), so the pre-push `git merge origin/main` was a no-op and no conflict resolution was needed.

## Risks and limits

1. In-sample numbers; paraphrase generalisation is low (D-LEX). The probe shows it.
2. Engineering-authored text, not native-reviewed (LG-11 open); the per-language cells are small.
3. The interview guard stage is a product decision (OD-INPUT-GUARD-LANGUAGES) taken provisionally to the owner's rule ("only with dev evidence of no false-positive increase"); reversal is one constant.
4. The chunk-surface "I had to forget the old rules" relaxation can be abused by prefixing an instruction on a retrieved chunk; a second signal still blocks and chunks remain data.
5. Names and street addresses are not redacted by pattern.
6. English false positives are pre-existing and measured (19.6%); not addressed here.
7. Russian and other scripts are not covered beyond look-alike letters and one persona rule.

## Evidence still missing (human, live, gate)

Native-speaker review of the 06E texts and a fresh native-authored held-out set per language (LG-11 and LG-08 sign-off); owner thresholds (OD-GATE-THRESHOLDS); the OD-INPUT-GUARD-LANGUAGES decision; the independent security review; any live-provider injection exercise (none run); staging and PostgreSQL runs.

## SHA and throughput

SHA_PLACEHOLDER
