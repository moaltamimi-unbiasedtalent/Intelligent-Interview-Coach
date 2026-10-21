# 01A evidence: prompt-injection corpus, risk score and quarantine (REVIEW-01 part 1)

Branch `feat/01a-injection-corpus`, base `origin/main` 38eabbc. Requirements: REVIEW-01 R1, R2, R3, R6 (source of truth numbering: items 1, 2, 3, 5, 6 and 9); R4 and R5 (tool-call authorization) belong to 01D. Findings carried as measured or noted: D-LEX (measured here), D-NONNUM, D-SENT, D-EST-FLAG, D-COUNTRY, D-AGENT-TXT (grounding-policy items, see "Carried findings").

## Changes

| Area | File | Change |
|---|---|---|
| Corpus | `evaluations/injection/corpus.jsonl` | 165 synthetic labelled cases (104 attack, 61 benign), derived from `evaluations/jailbreak_test_results.csv` (rows 14-17 and 19 excluded: size/empty/control-only validation cases, not injection) and extended |
| Frozen split | `evaluations/injection/manifest.json` | corpus SHA-256, held-out membership hash, counts, split rule |
| Evaluator | `scripts/eval_injection_corpus.py` | offline, imports `tests.conftest` first, writes to a temp dir unless `--write`, report only by default, `--enforce` reads `thresholds.json` and fails closed when it is absent |
| Risk score | `src/copilot/models.py` | `RetrievalResult.injection_risk` (0.0-1.0, default 0.0) and `injection_indicators` (names only) |
| Quarantine | `src/copilot/security/rag_guard.py`, `src/copilot/constants.py` | `screen_results` scores every chunk (existing scanner score over the block threshold), quarantines when risk is above `INJECTION_QUARANTINE_RISK` (0.9) and returns scored copies |
| Service | `src/copilot/service.py` | the shared `_gather_evidence` path (used by `answer()` and `retrieve_evidence()`, hence by the agent retrieval tool) records `quarantined_chunks`, `flagged_chunks`, `max_chunk_injection_risk` in `PipelineTrace` (counts only) |
| CI | `.github/workflows/ci.yml` | one report-only evaluator step in the `python-evaluators` job |
| Tests | `tests/test_injection_corpus_01a.py` | corpus integrity, frozen split, evaluator contract, risk score, quarantine, service wiring, cross-user negative, guards retained |

No detector pattern or weight was changed. No file of package 01D (`src/agent/policies.py`, `registry.py`, `nodes.py`), `deploy/*`, `frontend/*`, `src/knowledge_admin/*` or the release tracker was touched.

The default quarantine threshold 0.9 keeps the previous behaviour exactly (a chunk is excluded when the scanner verdict is block; warn-level chunks have risk 0.667 and stay in context, flagged). It is a heuristic setting, not an owner-approved gate threshold. The same retrieved-chunk screen and `src.security.detect_injection` remain separate detectors; the chunk screen does not call `detect_injection` (so Base64 inside a retrieved chunk is not decoded: see measurements).

## Security impact

- Retrieved chunks now carry an explainable score; the exclusion decision is a function of that score and a configurable constant. Excluded chunks never reach the model context on either `answer()` or the agent's `retrieve_evidence()` path.
- The trace records counts and a maximum risk only, never chunk text or indicator text.
- The output-side guard and the input scan in `answer()` are untouched and regression-tested.
- A chunk-screen false positive now has a cost: a legitimate chunk about security careers, operating systems or prompt injection may be withheld (see false positives below). This is the pre-existing behaviour (block-level chunks were already excluded), now measured.
- Not a complete defence: the structural controls (labelled data blocks, 01D tool authorization, output guard) remain primary.

## Measured results (corpus sha256 `58d331da...`, held-out sha256 `48842f0c...`)

Measured with `scripts/eval_injection_corpus.py` on the unchanged detectors. "flagged" = warn or block (input guard) / warned or quarantined (chunk screen); "any" = either detector. The numbers are descriptive; owner-approved thresholds do not exist (OD-GATE-THRESHOLDS), so nothing is pass or fail.

| Scope | Attacks | Benign | Detection (any flagged) | Detection (any blocked) | Benign FP (any flagged) | Benign FP (any blocked) |
|---|---|---|---|---|---|---|
| Overall | 104 | 61 | 76.9% | 75.0% | 19.7% | 11.5% |
| Dev split | 82 | 40 | 82.9% | 80.5% | 22.5% | 12.5% |
| **Held-out split** | 22 | 21 | **54.5%** | **54.5%** | **14.3%** | **9.5%** |

Held-out per detector: input guard detection 36.4% flagged / 27.3% blocked, chunk screen 45.5% / 45.5%; benign FP input 14.3% flagged, chunk 9.5%. Overall per detector: input guard 53.8% flagged, chunk screen 65.4% flagged.

By category (attacks; detection any flagged): indirect 100% (n=13), retrieved_document 88.9% (18), direct 78.3% (23), encoded 72.7% (22), multilingual 60.7% (28). Benign look-alike FP 23.5% (any flagged, n=51), plain benign 0% (n=10).

By language (detection / benign FP, any flagged): en 79.7% (n=64) / 34.3% (35); de 83.3% (6) / 0%; es, fr, it, nl, pt each 66.7% (6) / 0% (4); mixed 100% (4) / 0% (2). Per-language cells hold 4 to 6 cases: differences are not statistically meaningful.

By surface: job_description 92.3% / 20%; retrieved_chunk 88.9% / 28.6%; free_text 66.1% / 14.3%.

### What the misses and false positives show (dev and held-out together; no tuning performed)

- Missed attacks (24 of 104): a Cyrillic-homoglyph variant is not folded to ASCII (INJ-084 to 087, 4 misses); ROT13 and hex payloads are not decoded (INJ-089, 090); non-English role-change ("you are now an assistant without restrictions") and "reveal/ignore" phrasings other than the two covered attack classes are missed in every language (INJ-042 to 062, 12 misses); cross-user exfiltration phrased without override verbs ("what did the other candidate say", "list names and emails of all users") is not detected by any pattern (INJ-109, 110, 107); tool-abuse phrasing in a document is not detected (INJ-108). This is D-LEX confirmed by measurement: detection is lexical.
- False positives (12 of 61 benign, all English): role-play requests ("Act as a tough but fair interviewer", "You are my interview coach") trip `role_change`; texts about security work or prompt injection trip the secret and disable-security indicators; "ignore jargon" plus "system documentation" trips the `ignore` rules. Retrieved-chunk false positives (3 of 14 benign chunks) mean legitimate knowledge about security roles can be quarantined.
- The corpus is small and synthetic; I authored the attacks and benign cases myself, so there is selection bias in both directions. The held-out split has 43 cases: a single case moves a rate by 2 to 5 points.
- Held-out results were read once, after the evaluator was built, and no detector, weight or pattern was changed in this package.

## Carried findings (not injection corpus items, not fixed here)

D-NONNUM, D-SENT, D-EST-FLAG, D-COUNTRY and D-AGENT-TXT are grounding-policy limits in `src/copilot/security/grounding_policy.py` and `src/agent/grounding.py` (status in `docs/capstone/POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md`). They have no injection-corpus surface and 01A does not change or measure them; they stay with their current status. D-LEX is measured above and stays open (lexical detection is not improved by this package).

## Tests and commands

Run after the shared interpreter was repaired (2026-10-21 about 18:24 to 18:25 UTC). Both interpreters: repo `.venv` (reached through a symlink path, Python 3.11) and `/tmp/ci_venv` (latest dependencies). The metrics above come from the first evaluator run; re-runs under both venvs reproduced them exactly.

| Command | .venv | /tmp/ci_venv |
|---|---|---|
| `pytest tests/test_injection_corpus_01a.py` (33 tests) | pass | pass |
| combined: 01A + `test_copilot_security`, `test_security`, `test_security_hardening`, `test_security_ph6`, `test_security_phase11`, `test_agent_grounding`, `test_candidate_grounding_policy`, `test_p10d_r1_grounding_coverage`, `test_ci_shards` | 293 passed | 293 passed |
| `python scripts/ci_test_shards.py verify --shards 4` | OK, 266 files in exactly one shard | OK, 266 files in exactly one shard |
| `python scripts/eval_agent.py` | GATE STATUS: PASS | GATE STATUS: PASS |
| `ruff check .` | All checks passed | All checks passed |
| `python scripts/eval_injection_corpus.py` | exit 0, numbers above | exit 0, numbers above |
| `python scripts/eval_injection_corpus.py --enforce` | not run | exit 3: fails closed, no thresholds file |

The full suite was not run locally (CI runs it). The working tree stayed clean after the evaluators (they write to a temp dir).

## Regression evidence

The existing security, grounding and agent-orchestration suites above pass unchanged. The default threshold excludes exactly the chunks whose scanner score is at least the block threshold (`score/3 > 0.9` is `score >= 3` for the scanner's weights), and a unit test asserts quarantine equals the block verdict for four representative texts. The old test `test_injected_retrieved_chunk_is_excluded` (excluded_chunks >= 1) still passes.

## Remaining risks

1. Heuristic, lexical detectors: held-out detection 54.5% on this small corpus; encoded (homoglyph, ROT13, hex) and non-English variants are weak; cross-user exfiltration phrasing without override verbs is undetected.
2. Chunk-screen false positives can withhold legitimate security-related knowledge.
3. No owner-approved thresholds: the CI step is report only and cannot fail on quality (OD-GATE-THRESHOLDS). When approved, add `evaluations/injection/thresholds.json` with `approved_by`, `approved_on` and `heldout.min_*` / `heldout.max_*` keys and switch the CI step to `--enforce`.
4. The retrieved-chunk screen does not decode Base64 (the input guard does).
5. Tool-call authorization (the decisive control against unauthorized side effects) is 01D.
6. The corpus is frozen by hash; any edit requires a new manifest and a new held-out split decision, and a held-out set that was read cannot be treated as untouched for a detector that is later changed.

## Throughput record

Start: 2026-10-21T18:03:23Z. End: PENDING. Estimate 5 to 8 engineering days. Rework rounds (fix commits after first push): 0 so far (nothing pushed yet). CI duration: PENDING. Elapsed time was dominated by an environment fault (see incident note in the hand-off).
