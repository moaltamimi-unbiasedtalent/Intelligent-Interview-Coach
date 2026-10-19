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

> Interpretation corrected in section 16: the findings below were measured with a defective harness (retriever disabled, no conversation language). The original measurements are preserved unchanged; do not read them as product behaviour.

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

## 16. Audited correction of the evaluation defects (added after independent review; sections 1 to 15 are unchanged)

Starting SHA `cccea78` (PR #202 head). Principle: correct the measurement before the product; preserve historical evidence; no authorization, budget or ledger change.

### 16.1 Harness defects found (verified in code)

| Defect | Original | Effect |
|---|---|---|
| A. Retriever disabled | `world.service(responder=spy, retriever=False).answer(...)`; the offline measurement used the retriever | 0 narrative evidence for all six non-English supported cases; the model could only abstain |
| B. No conversation language | `answer()` called without `conversation_language`, although the service supports it | English scaffold headings and English insufficient-evidence sentence in German and French answers |
| C. Abstention by citation count | zero citations was recorded as `abstained_or_clarified` | an uncited factual answer would have been counted as an abstention |
| D. Money-figure proxy | any 4-digit number counted | the year 2026 flagged a correct French abstention |
| E. Agent completion | `step_limit_reached` and a HITL pause counted as completed | inflated completion; misses not diagnosable |
| F. No per-case agent evidence | aggregates only | the 5 misses behind 0.773 cannot be identified |

Offline proof (no model call) for A and B, per language: with the original configuration all six non-English cases retrieved 0 evidence and the prompt carried English headings; with the corrected configuration every case retrieved 2 to 7 evidence items and the prompt carried that language's headings and insufficient-evidence sentence (tests `test_the_corrected_path_localizes_the_synthesis_instructions_and_retrieves_evidence`, 7 languages). The default (no language) prompt is byte-identical to the English one.

### 16.2 Corrections (commits `6a85a64`, `137c11b` and the final commit)

- Harness: `answer_case` enables the existing retriever and passes the case language through `conversation_language`; no heading is hard-coded in the harness.
- Outcome classes (`classify_answer`): ANSWERED_WITH_EVIDENCE, ABSTAINED, CLARIFICATION_REQUESTED, UNSUPPORTED_FACTUAL_RESPONSE, UNCERTAIN_REQUIRES_REVIEW. A citation count alone never establishes an abstention; what cannot be decided deterministically goes to review. Definitions, expectations per case kind and the corrected configuration were registered in `evaluations/p10e/r1/multilingual_corrected_v1.json` and hash-locked in `registration.lock.json` BEFORE any new live call (the original corpus and lock entries are unchanged and verified by test). General advice is not prohibited; it is flagged when substantive, uncited and not an abstention.
- Money-figure proxy (`has_money_figure`): a bare year 1900 to 2100 is not a figure; currency-adjacent numbers, thousands-separated numbers and `k` amounts still are. The offer of an unsourced estimate is a separate review flag (`offers_unsourced_estimate`), surfaced in every unsupported-country case.
- Agent (`src/agent/live_eval.py`): explicit `terminal_status` (COMPLETED, AWAITING_HUMAN_INPUT, STEP_LIMIT_REACHED, FAILED, GUARD_REFUSED, PROVIDER_ERROR, OTHER:x; an unknown status is never success). `completion_rate` is now strict (COMPLETED only); new `hitl_pause_rate`, `expected_hitl_pause_rate`, `step_limit_rate`, `failure_rate`, `terminal_status_counts`. The historical committed metrics are not rewritten (they used the looser definition).
- Per-case agent evidence (`live_runs.refine_case`, summary `per_case`): case id, expected and used tools, missing required and forbidden tools, retrieval and HITL expectation and outcome, terminal status, provider calls and failures, guard refusal reasons, latency, tokens, provider-reported cost, and content-free response flags; a separate `review_packet.json` holds a 700-character excerpt of the model's own text for synthetic held-out goals only, marked PENDING_HUMAN_REVIEW. No chain-of-thought, prompt or raw provider payload is stored. The historical misses are not reconstructed.
- Post-hoc reading (`reclassify_run_post_hoc`, CLI `multilingual-reclassify`, offline, writes `reclassification.json` exclusively): labelled POST-HOC, defined after observing; never replaces the registered result.

### 16.3 Offline regression before any paid call

Tests added or updated: 43 new/changed tests across `tests/test_p10e_r1_evals.py`, `tests/test_agent_live_eval.py`, `tests/test_p10e_ledger.py`: money proxy (14 inputs including the French year), localized abstention in all 7 languages, uncited factual and uncertain answers, invalid markers, registered expectation mapping, locked original corpus, estimate flag, candidate-path call, corrected retrieval and headings in 7 languages, Russian excluded, terminal status, strict completion, per-case evidence, guard refusal and provider error, runner packet. Expectations were fixed before the live run.

### 16.4 Targeted live revalidation (existing ledger; no new budget)

Ledger verified against the authoritative file first: 242 calls, USD 1.86290325, 58 remaining, genesis `ff65d285…`, unchanged. Executed 28 calls (all `openai/gpt-5.4`, 0 unexpected model, 0 refusals, 0 provider failures): 14 multilingual, 10 agent (6 cases), 4 agent (3 cases repeated).

**Corrected multilingual run (`…T151740Z-c896ab9b`, clean checkout at `6a85a64`, 14 of 14 completed).** Per language, registered classification:

| Lang | Supported definition | Unsupported-country compensation |
|---|---|---|
| en | ANSWERED_WITH_EVIDENCE (7 evidence, 3 citations), intended | ANSWERED_WITH_EVIDENCE by the registered rule (1 citation), registered FAILURE; read: states insufficient evidence, cites the coverage note, no figure |
| de | ANSWERED_WITH_EVIDENCE (2, 1), intended | ABSTAINED, intended |
| fr | ANSWERED_WITH_EVIDENCE (5, 1), intended | ANSWERED_WITH_EVIDENCE by the registered rule (4 citations), registered FAILURE; read: states insufficient evidence, no figure |
| es | ANSWERED_WITH_EVIDENCE (5, 1), intended (a caveat at the end says the evidence is not enough for a complete description) | ANSWERED_WITH_EVIDENCE by the registered rule (5 citations on the abstention sentence), registered FAILURE; read: states insufficient evidence, no figure |
| it | ANSWERED_WITH_EVIDENCE (5, 1), intended | ABSTAINED, intended |
| nl | ANSWERED_WITH_EVIDENCE (5, 1), intended | ABSTAINED, intended |
| pt | ANSWERED_WITH_EVIDENCE (4, 1), intended | ABSTAINED, intended |

Result: answer language matched the question in all 14 cases, including German and French; the localized headings appear; no salary figure was invented (the French year no longer fails); no United States compensation was presented as Canadian; no citation marker referred to a missing evidence item. The three registered failures (en, fr, es unsupported-country) are all abstentions that attach valid citation markers to the abstention sentence. A post-hoc offline reading (`reclassification.json`, a looser opening-statement match, labelled post-hoc) classifies exactly those three as ABSTAINED_WITH_CITED_CONTEXT; the registered result stays as recorded. Whether sources should be shown under an abstention is a presentation decision for the owner, not changed here. The offers_unsourced_estimate flag fired in all seven unsupported-country cases and remains for human review.

Comparison with the original run: original (defective harness) 1 of 7 supported cases evidence-backed, German and French language mismatch/mixed; corrected: 7 of 7 evidence-backed, 14 of 14 language matches. These are different configurations, not a regression or improvement of the product.

**Agent targeted run (`…T151928Z-0dbb5a45`, 6 cases, 10 requests) and repeat (`…T152058Z-7f721a1b`, 3 cases, 4 requests).** Per-case evidence now identifies the misses:

| Case | Expected | Observed (both runs unless stated) |
|---|---|---|
| jd_plus_candidate_gap | AnalyzeJobDescription + AnalyzeCandidateGaps | both used, COMPLETED (hit; 4 calls) |
| memory_approval_hitl | HITL approve_memory | ProposePreparationMemory, AWAITING_HUMAN_INPUT, type matched (hit) |
| prep_plan_request | BuildPreparationPlan | no tool, COMPLETED (miss; the goal says "from my gaps" with no gaps in state) |
| insufficient_evidence | SearchCareerKnowledge | no retrieval, COMPLETED, no figure, no citation, hedged general explanation (miss; repeated) |
| ambiguous_role_hitl | SearchCareerKnowledge + confirm_role pause | no retrieval, no pause, listed the possible meanings itself (miss; repeated) |
| practice_handoff_hitl | approve_practice_handoff pause | no pause; asked for the missing role and plan first (miss; repeated) |

The misses are stable across a repeat for the three re-run cases. Reading the excerpts, none contains an invented statistic, citation or country claim; they are conservative or clarifying answers that do not follow the registered tool expectation. That is a measured disagreement with the registered expectations, not evidence of an unsafe answer; whether the agent should retrieve for general labour-market questions is an owner decision. Human appropriateness review is PENDING_HUMAN_REVIEW. The full 22-case benchmark was not re-run (about 45 calls would not fit with the multilingual run in the 58-call allowance); the historical 0.773 stays as recorded, and 3 of the 5 misses behind it are plausibly among the cases above but that is NOT established.

### 16.5 Product defects

- Confirmed: none that demands a product change in this wave. The "non-English retrieval gap" and "mixed-language German and French answers" reported in section 14 were harness artifacts (A and B) and are withdrawn as product findings. The pure cross-language retrieval observation (native-phrasing queries) remains a separate offline measurement (L-XLANG-1) and was not affected.
- Open observations for the owner (not defects proven, no change made): citations attached to an abstention sentence (3 of 7 unsupported cases); the agent does not retrieve for some general factual questions; the unsourced-estimate offer in abstentions.
- Protected: geographic grounding, citation integrity and source-integrity behaviour were exercised and held; no occupation mapping, no geography inference from language, no synthetic promotion, no re-index.

### 16.6 Cost, ledger and reconciliation (this correction)

28 calls, provider-reported USD 0.1239, ledger committed USD 0.1620 (calculated estimate, an upper bound). Account usage rose from USD 6.61372494 to USD 6.73766144 = USD 0.1239365, which equals the sum of the per-request reported costs exactly (the 9% gap seen after the first R1 batch did not recur). Ledger now: 270 of 300 calls, USD 2.02485575 committed, 30 calls and USD 7.97514425 remaining, 0 unknown or pending entries. The ledger was not reset or recreated; USD 15 and any extra allowance were not used.

### 16.7 Regression and status

Backend 4,959 passed, 34 skipped, 0 failed (was 4,917 before the correction; +42 tests); Ruff and `git diff --check` clean; 19 evaluators plus P10C-G, P10D (repeat 2) and the coverage guard pass; the 12-gate test passes; no tracked file modified by tests; frontend and browser tests not run (no frontend change). Product coverage unchanged: 386/412 developer-local (BELOW GATE), 258/412 clean-checkout, 0/412 human-qualified; AC-24 PARTIAL. Human-reviewed quality: NOT VERIFIED (all review packets pending). Semantic live calibration NOT RUN; RAGAS live NOT RUN.

### 16.8 Readiness

With the corrected measurement, the core multilingual and interview paths show no defect that blocks requalification; the remaining items are owner decisions (section 16.5) and human review. 30 calls and USD 7.98 remain. Integrated requalification has not been started.
