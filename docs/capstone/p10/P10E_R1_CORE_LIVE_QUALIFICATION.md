# P10E-R1: Core Live AI Qualification (corrective wave within P10E)

Status: LIVE VALIDATION COMPLETED WITHIN THE EXISTING BUDGET for the core scope below. Not accepted by the owner, not merged. Branch `fix/p10e-r1-core-live-qualification`, created from `origin/main` `787a229` (P10E, PR #201). R1 is a corrective wave inside P10E, not a new top-level workstream; the 11-row phase tracker is unchanged.

Nothing here is a quality score. No acceptance threshold exists, none was invented, and every subjective metric is `PENDING_HUMAN_REVIEW`.

## 1. Original P10E findings addressed

| P10E finding | R1 disposition |
|---|---|
| 5 of 22 agent cases blocked by the 2,000 output-token cap against the product's 4,096-token tools | Owner raised the cap to 4,096 (decision A); all 5 re-run and completed |
| 19 of 152 requests went to the code-default `openai/gpt-5.6-terra` instead of the effective Balanced model | Root cause found and fixed (decision B); 0 of 90 R1 requests used an unexpected model |
| Interview quality, multilingual, embeddings, RAGAS not run | Interview and multilingual harnesses built and run; embeddings and RAGAS remain NOT RUN (section 9) |

## 2. The 4,096 output cap

Only `max_output_tokens_per_request` changed (2000 to 4096), recorded as `authorization_version` 3 in `evaluations/p10e/authorization.json` with the v2 limits preserved in `limits_history` and the change in `limits_approval.changes`. All other limits are unchanged: USD 10, 300 calls, 20,000 input tokens, 60 s timeout, 1 retry, concurrency 2. `paid_execution_enabled` stays true; `P10E_LIVE=1` was set per run; CI refuses paid execution. The HTTP guard still refuses any outgoing body whose cap exceeds the limit (test: 4097 is refused).

## 3. Budget preservation

The authoritative ledger was read first. It matched the historical state (152 calls, committed upper bound about USD 1.218). It was never reset, overwritten or branched; no R1 budget exists. USD 15 was not used.

| | Calls | Committed (upper bound) | Remaining |
|---|---|---|---|
| Start of R1 (P10E end) | 152 | USD 1.218 | 148 calls, USD 8.78 |
| End of R1 | 242 | USD 1.8629 | 58 calls, USD 8.1371 |
| R1 only | 90 | about USD 0.645 | |

The call ceiling (300) is the tighter constraint, not money. No stop condition was triggered; zero guard refusals in every R1 run.

## 4. Root cause of the routing inconsistency

`constants.DEFAULT_MODEL` was computed at import time, before `load_config()` read the `.env` overrides. `CopilotConfig.default_model` and `AppConfig.model` therefore froze the code default (`openai/gpt-5.6-terra`) whenever a component used the config default rather than asking the registry. `spec()` and `model_id()` always honored the overrides, which is why most traffic was correct and a minority was not.

Fix (commit `a994ed1`): both loaders now resolve the default through `model_id(BALANCED)` at call time (`src/copilot/config.py`, `src/config.py`). The frozen `ApprovedModel` enum also gained a `runtime_allowed` callable so the registry's current effective slugs are accepted (`src/models.py`). Regression tests: `tests/test_p10e_r1_routing.py` (9), including a scan that no non-evaluator source hard-codes a model slug.

## 5. Before and after routing evidence

| Run | Requests | Expected model `openai/gpt-5.4` | Other |
|---|---|---|---|
| P10E agent run (before) | 152 total, all runs | 133 | 19 on code-default terra |
| R1 agent, 5 cases | 17 | 17 | 0 |
| R1 agent, 22 cases | 45 | 45 | 0 |
| R1 interview | 14 | 14 | 0 |
| R1 multilingual | 14 | 14 | 0 |

Each run records `models_requested`, `expected_model` and `unexpected_models`; the guard also records any `answered_by` that differs from the requested model (none occurred).

## 6. Agent results (Balanced, `openai/gpt-5.4`)

All 22 held-out cases completed (completion rate 1.0). Aggregates (a bounded sample; not an accuracy score):

| Metric | 5 previously blocked | All 22 |
|---|---|---|
| Completion | 1.0 | 1.0 |
| Tool selection accuracy / required-tool recall | 0.80 | 0.773 |
| Retrieval decision accuracy | 1.0 | 0.909 |
| HITL decision accuracy | 1.0 | 0.909 |
| Unnecessary retrieval / unnecessary tool | 0 / 0 | 0 / 0 |
| Average tool calls | 1.4 | 0.545 |
| Average cost (provider-reported) | USD 0.013 | USD 0.006 |
| Average latency | 12.0 s | 6.9 s |

Provider-reported cost: USD 0.084 (5 cases), USD 0.210 (22 cases). Protected stores were fingerprinted before and after and were unchanged. Limitation: per-case tool outcomes were not persisted by the runner, so the individual cases behind the 0.773 are not itemised here; this is recorded as an open item, not guessed.

## 7. Blocked cases

`jd_explicit_analysis`, `jd_plus_candidate_gap`, `questions_request`, `jd_and_background_together` and `factual_plus_prep` all completed under the 4,096 cap. The blocking cause (cap smaller than the tools' own request) is closed. This does not by itself show those cases were handled correctly beyond the aggregate metrics above.

## 8. Interview-quality harness and results

Design (`src/p10e/r1_evals.py`, datasets `evaluations/p10e/r1/interview_cases.json` v1.0.0, sha256 `385625092b2d91574af6b396def752625edfa6fe22772652695735d14368d0e1`, registered in `registration.lock.json`, committed before the first live call at `be2bbb2`; the run recorded a clean checkout). Seven roles: software engineering, finance, operations, sales, customer support, people/HR, marketing. Per case: one generated question and one answer evaluation (2 calls), through the real `InterviewService` and `EvaluationService` with the Balanced default.

Deterministic checks (named proxies, not judgements), all 7 of 7 cases: question is a question, requested question type, role keyword, evaluation names missing evidence where a gap was designed, references answer content, no invented candidate experience, follow-up is a question, no hiring decision, no biased wording. Because these checks are coarse, a 100% pass is not a quality claim.

Cost USD 0.1341 (estimate equals provider-reported), 19,493 input and 5,690 output tokens, p50 latency 9.0 s, max 13.2 s. Review packet `review_packet.json` holds the generated questions, evaluations and 13 human metrics, all `PENDING_HUMAN_REVIEW`. Informational per-case scores: 59, 54, 38, 49, 49, 61, 46 (not thresholded).

## 9. Multilingual corpus and results

Corpus `evaluations/p10e/r1/multilingual_cases.json` v1.0.0, sha256 `2aaddbcd0622b93be18be1691c0532b36ea0edb73c8fe7be1bdf493e5d6e2074`, locked before any live call. 14 cases: es, it, pt, nl prioritized; en, de, fr as controls; Russian excluded. Each language has a supported-occupation definition case and an unsupported-country compensation case with fixed expectations (language, geography, evidence, abstention, citation boundary). Per-language reporting only; nothing is averaged.

Offline (free, deterministic) first: country resolution was correct in all 7 languages, and cross-language retrieval gaps were measured (finding L-XLANG-1).

Live (14 calls, Balanced, USD 0.0521, 4,835 in / 2,668 out tokens):

| Lang | Supported definition | Unsupported-country compensation |
|---|---|---|
| en | answered with 2 valid citations, language matches | abstained, no figure, no citation |
| de | abstained (0 evidence), language matches | abstained, no figure; **language check failed** (see below) |
| es | abstained (0 evidence) | abstained, correct language |
| fr | abstained (0 evidence) | abstained; **no-figure check flagged** (see below) |
| it | abstained (0 evidence) | abstained, correct language |
| nl | abstained (0 evidence) | abstained, correct language |
| pt | abstained (0 evidence) | abstained, correct language |

Findings (reported as measured; the locked checks were not edited after the run):
- Only English produced an evidence-backed answer. In all six non-English languages the supported definition case retrieved 0 evidence and the model abstained or clarified. This is the cross-language retrieval gap already seen offline (L-XLANG-1); it is a real limitation, not a pass.
- de unsupported case: the detector classified the answer as English because the deterministic scaffold headings ("Evidence (from sources)", "Tool results (calculated)") and the evidence sentence are English, while the recommendation prose is German. This is a mixed-language answer and conflicts with the language-ownership rule that Mo-voiced deterministic text follows the conversation language. fr is similarly mixed ("Le knowledge base ..."). Logged as an open defect, not fixed in R1 (R1 is validation, and the fix touches the Career-chat template path).
- fr unsupported case: the flagged "figure" is the year "2026" in a suggested search phrase. No salary was invented, so this is a proxy false positive. Separately, the answer offers an unsourced "estimation prudente" option, which a human reviewer should assess.
- Native-speaker fluency, tone and question understanding: `PENDING_HUMAN_REVIEW` for every language.

## 10. Dispositions (not run, no blocker)

- SEMANTIC LIVE CALIBRATION: NOT RUN. OPEN DEPENDENCY.
- RAGAS LIVE: NOT RUN. CREDENTIAL AND GUARD DEPENDENCY.
- HUMAN-REVIEWED QUALITY: NOT VERIFIED.
- Thresholds: none invented.
- P10F, P10C-F and the remaining W12.4E activation stay deferred.

## 11. Provider cost reconciliation

The ledger commits an upper bound, never a bill. R1 provider-reported cost summed from per-request usage: USD 0.4801. Calculated estimate: USD 0.6448 (provider cache discounts make the reported figure lower). Account usage snapshots (read-only `/api/v1/key`): P10E end USD 6.09023694, R1 end USD 6.61372494, a delta of USD 0.5235. The delta exceeds the per-request reported sum by USD 0.0434 (about 9%), the same direction as the unexplained about 5.5% gap seen in P10E. The account figures can include other uses of the credential, so the difference is not attributed. Ledger committed (about USD 0.645) is at or above both figures. Snapshots: `evaluations/p10e/live/provider_snapshots/20261019T095618Z-after-r1.json`.

## 12. Security and regression results

- Full backend suite: 4,917 passed, 34 skipped (0 failed); Ruff clean; `git diff --check` clean; no tracked file modified by tests.
- Evaluators run and passing: agent, multi-agent, admin AI models, integrations, qualification, foundation, security, billing, doc consistency, engineering quality, hosting readiness, i18n, product coverage, release matrix, RC-P10-003, W11 integrated, knowledge governance, speech providers, rate limits, P10C-G global corpus (repeat 2), P10D requalification (repeat 2), and the product-coverage baseline guard.
- Safeguards held: only `openrouter.ai` was contacted; the only POST endpoint was chat completions; no stream; no refusal; no unexpected model; no repeated-call loop; protected stores unchanged; no credential value read, printed or stored; all 12 rollout/billing gates False; Compensation V2, Premium and speech activation disabled; no Stripe, production or live email.
- Frontend and E2E were not run because no frontend file changed in this wave.

## 13. Coverage limitations (unchanged)

Product coverage stays 386/412 developer-local (93.7%), BELOW the 95% gate (needs 392); 258/412 clean-checkout; human-qualified 0/412. AC-24 stays PARTIAL. No live result in this wave changes those figures.

## 14. Remaining risks

1. Non-English retrieval gap (6 of 6 languages abstained on a supported definition).
2. Mixed-language answers for de and fr (English scaffold inside localized prose).
3. Agent tool-selection recall 0.773 across 22 cases (itemisation not persisted).
4. Per-request provider cost versus account delta unexplained by about 9%.
5. All subjective quality (interview, multilingual fluency) unreviewed by humans.
6. Samples are small (7 interview cases, 14 multilingual calls, 22 agent cases); results are descriptive only.

## 15. Handoff

R1 stops here. Not merged; integrated requalification not begun; RC-P10-004 not created; P11 not begun. 58 calls and USD 8.14 remain in the single cumulative ledger. Owner decisions pending: accept or amend R1, whether to fix the localized-scaffold and retrieval gaps before requalification, and reviewer appointments for the human-review packets.
