# 01A: Injection corpus, risk score and quarantine (REVIEW-01 part 1)

**Branch:** `feat/01a-injection-corpus`  **Head SHA:** `6b2dbc2`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/01a-injection-corpus
**Programme:** Ask4Mo Production Roadmap V2.2, S1 full R1.0 scope (owner-approved), first engineering wave.

## Requirements and package IDs
Package 01A. REVIEW-01 R1, R2, R3, R6 (R4 and R5 close in 01D); carries D-LEX, D-NONNUM, D-SENT, D-EST-FLAG, D-COUNTRY, D-AGENT-TXT as measured, not fixed.

## Change summary
Adds a 165-case synthetic labelled corpus (104 attacks, 61 benign, seven languages, direct, indirect, encoded and retrieved-document), a frozen held-out split with a recorded hash, the offline evaluator `scripts/eval_injection_corpus.py` (report only; `--enforce` fails closed because no approved thresholds exist), `RetrievalResult.injection_risk`, quarantine of high-risk chunks before context construction in the shared evidence path (used by `answer()` and the agent retrieval tool), and a report-only CI step. No detector pattern changed; no agent file touched.

## Acceptance criteria
Corpus, split and evaluator merged; detection and false-positive rates reported per category and language; chunks above the risk threshold never reach the model context; input screening and the output guard still run.

## Tests and evidence
33 new tests pass; combined security and grounding run 293 passed under both venvs; eval_agent PASS; ruff clean; shard plan OK. Measured (report only): detection 76.9% overall and 54.5% held-out; benign flagged 19.7% overall and 14.3% held-out (all English). Evidence: docs/production/execution/evidence/01A_EVIDENCE.md.
Local green tests do not replace GitHub CI: the PR's own checks are the CI evidence.

## Risks and limitations
Held-out detection is only 54.5% on a small self-written corpus; chunk-screen false positives on security-themed knowledge; no approved thresholds (OD-GATE-THRESHOLDS) so CI cannot fail on quality; the chunk screen does not decode Base64; tool-call authorization is 01D.

## Dependency and merge order
Fifth (independent). The only package editing .github/workflows/ci.yml in this wave. Overall first-wave order: 02K, 01B0, 03K, 05A, 01A, 03A, 06A; then stacked 02A (on 02K), 01B (on 01B0), 06H (on 06A); shared agent-policy order 01B, then 01D, then 01C. A dry-run merge of all seven branches onto main produced no conflicts (tests/contracts/__init__.py is an identical empty file on three branches).

## Boundaries honoured
No production deployment, no paid provider call, no Stripe or billing activation, no destructive data operation, no historical evidence rewritten, no gate weakened, no R1.0 scope reduced. Do not merge until required CI, review and acceptance evidence exist.
