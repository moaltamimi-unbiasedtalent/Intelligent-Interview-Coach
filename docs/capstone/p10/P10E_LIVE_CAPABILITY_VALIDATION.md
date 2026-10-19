# P10E: Authorized Live Capability Validation

**Status: PREPARED, GUARDED AND TESTED OFFLINE. LIVE PAID EXECUTION: NOT RUN (BLOCKED ON ONE OWNER DECISION).** No inference call, embedding call, RAG-judge call or other paid call was made, so there is **no live model result of any kind** in this document. Spending: **USD 0.00**; provider inference calls: **0**. The one external request made was a read-only fetch of OpenRouter's public model catalogue (no credential, no inference, no cost) to confirm model availability and published prices.

Not production ready, not human reviewed, no source qualified, not a pass against the unchanged 95% coverage gate. All 12 rollout and billing gates are False; Compensation V2, Premium and speech activation stay disabled; P10C-F, P10F and the remaining W12.4E activation work stay deferred.

- Branch `feat/p10e-authorized-live-capability-validation`, from `main` `e798b8d` (W12.5, PR #200, verified merged).

## 1. Owner authorization, exactly as recorded
`evaluations/p10e/authorization.json` (owner decision 2026-10-19). **Granted:** paid provider use for P10E (paid inference, semantic embeddings, RAG evaluation, quality benchmarking, bounded API integration tests), superseding the P10D no-paid-evaluation restriction for P10E only. **Not granted** (recorded as such): unlimited spending, production activation, processing of real candidate data, human reviewer appointments, acceptance thresholds, Stripe or commercial transactions, speech execution or model downloads, live email to third parties. The authorization carried **no monetary ceiling and no call count**; engineering did not invent either. `limits` is `null` and `paid_execution_enabled` is `false`. The historical P10D contract status ("CONTRACT ONLY: NOT AUTHORISED, NOT RUN") and the P10D refusal evidence are untouched; the P10E authorization is a separate record.

## 2. The exact decision that blocks paid execution
A paid call needs these recorded in `evaluations/p10e/authorization.json` in a reviewed commit, with `approved_by`, `approval_date` and `reference`:
1. `max_spend_usd` (finite, above zero)
2. `max_provider_calls`
3. `max_input_tokens_per_request` and `max_output_tokens_per_request`
4. `request_timeout_s`, `max_retries` (hard cap 2), `max_concurrency` (hard cap 4)

Engineering **proposal only, not an approval**: the plan below estimates the core scope at 120 to 230 calls and USD 1.31 to 8.04, and all rows including the optional Fast and Advanced agent comparisons at up to 600 calls and USD 2.62 to 19.83 (estimates, section 5). A ceiling of USD 25, 800 calls, 20,000 input and 2,000 output tokens per request, 60 s, 1 retry and concurrency 2 would cover everything with margin; the owner may choose any other values. The guard stops rather than overspends, and may stop early if the ceiling is tight.

Further inputs also missing (each blocks only its own area): an **embedding provider, model and credential** (none selected or configured; `COPILOT_EMBEDDING_API_KEY` is absent) and a **RAGAS evaluator credential** (`RAGAS_EVAL_API_KEY` is absent). The OpenRouter credential used by the app is present in the developer environment (presence checked by name only, never printed or used).

## 3. Live-run safety (implemented and tested)
`src/p10e/guard.py`: paid execution needs, together: not in CI (`CI` or `GITHUB_ACTIONS`), the explicit per-run opt-in `P10E_LIVE=1`, the recorded grant, owner-approved finite limits, and the credential. Each model call, including the nested calls an agent makes, is admitted BEFORE it is made by a LangChain callback against a worst-case cost (input estimate plus the output cap, times the allowed attempts) from the published price snapshot, the call limit and the per-request limits. **A missing token count or cost is UNKNOWN, never zero**: the worst-case reservation stays committed, and a model with no published price is refused because the ceiling could not be enforced. Failures are reported by exception class only, never the provider's text (which could echo request data). Evidence per run is written to `evaluations/p10e/live/<run_id>/` (meta with commit SHA and clean/dirty state, per-call usage, summary, optional review packet), created exclusively and never overwritten. No paid call is made in CI, on startup or in the background. Both existing paid runners are now behind the same guard: `scripts/eval_agent_live.py` and `scripts/eval_kb_model_quality.py --live`; the P10D "NOT AUTHORISED" dry run and the offline modes are unchanged (tested). A real-LangChain-callback test with fake models proves the call limit, spend ceiling, oversized-request refusal, unknown-usage handling, error settlement and exactly-N admission under 40 concurrent threads.

## 4. Providers and models (verified from the registry and the public catalogue, 2026-10-19)
Typed profiles via `src/llm/models.py`; no raw model selection. All three are available, support tools and structured output, with a 1,050,000-token context and a 128,000 maximum completion. Published prices (USD per million input / output tokens): Fast `openai/gpt-5.6-luna` 0.20 / 1.20; Balanced `openai/gpt-5.6-terra` 2.00 / 12.00; Advanced `openai/gpt-5.6-sol` 4.00 / 20.00 (a higher long-prompt tier applies above 272,000 prompt tokens; no P10E request approaches it). Reasoning tokens bill as output. Snapshot: `evaluations/p10e/pricing_snapshot.json` (a test fails if the registry slugs drift from it). No model was substituted. The prices are provider metadata at one moment, not a bill; the provider's dashboard may differ from local estimates.

## 5. Execution plan (offline; `evaluations/p10e/execution_plan.json`)
| Area | Profile | Cases | Calls (low to high) | Cost USD (low to high, estimated) | Implementation |
|---|---|---|---|---|---|
| Smoke (auth, schema, usage, latency; not quality) | Fast, Balanced, Advanced | 3 | 3 | 0.005 to 0.009 | implemented, guarded, NOT RUN |
| Live agent, held-out cases | Balanced (Fast and Advanced optional) | 22 | 66 to 176 each | Balanced 0.63 to 5.98; Fast 0.06 to 0.60; Advanced 1.19 to 10.91 | existing runner wired to the guard, NOT RUN |
| KB model-quality contract, answer cases | Balanced (contract compares all three) | 9 of 20 | 9 each | Balanced 0.03 to 0.16 | implemented, guarded, NOT RUN |
| Interview quality sample (8 role families) | Balanced and Advanced | 8 | 40 | 0.64 to 1.89 | NOT IMPLEMENTED (harness and synthetic personas) |
| Failure paths live (invalid model, rejected key) | Fast | 2 | 2 | about 0 (unknown until observed) | NOT IMPLEMENTED live (offline fakes cover the rest) |
| RAGAS judge | judge model | 35 | about 140 judge calls plus 35 generations | **UNKNOWN** (judge price not in the snapshot; nested calls not yet interceptable by the guard) | existing runner; guard integration NOT IMPLEMENTED |
| Semantic retrieval calibration | embedding model | 33 retrieval cases plus a temporary index | UNKNOWN | **UNKNOWN** (no provider chosen) | NOT IMPLEMENTED |
| Multilingual live | | | | **UNKNOWN** | NOT IMPLEMENTED |
Token sizes and calls per case are stated engineering assumptions in the plan file, not measurements; the real numbers come from the guarded run. Real gaps found while planning: the 20 selected contract cases carry only English, German and French (no tags for the other four knowledge-base languages), the 11 evidence cases need a synthesis harness that does not exist, and per-language results cannot be derived from the 9 answer cases (they carry no language tag).

## 6. Results by area (all NOT RUN)
| Requirement | Status |
|---|---|
| Provider smoke test | NOT RUN (blocked on section 2) |
| Live agent decision quality (Balanced first) | NOT RUN |
| Live interview quality, role families | NOT RUN; harness NOT IMPLEMENTED |
| Model-quality contract (mode C) | NOT RUN; runner implemented for answer cases; deterministic metric `answer_grounded` (structural proxy) only; `citation_supports_claim`, `language_consistency`, `abstains_when_unsupported` PENDING_HUMAN_REVIEW; `no_cross_country_claim` and `injection_resistance` NOT COMPUTED (no data in the selected cases); no threshold exists and none is invented |
| Semantic retrieval and L-REL-1 calibration | NOT RUN; if run later and the evidence is thin the correct result is CALIBRATION INCONCLUSIVE; the existing runtime retriever and protected Chroma store are not touched |
| RAGAS | NOT RUN (judge credential absent; guard integration pending) |
| Multilingual live (7 knowledge-base languages; Russian is not one) | NOT RUN |
| Provider failure behaviour | Offline only: fake-model tests cover timeout, provider error, missing usage, call-limit, spend-ceiling and oversize refusal, partial completion (stop and say so), and that an error never echoes provider text or a credential. Live timeout, rate limit and authentication failure were NOT observed |
| Latency, tokens, cost | none measured |
| Human quality | NOT VERIFIED (no reviewer is appointed; a review packet is generated by the runner with ratings PENDING_HUMAN_REVIEW; an LLM judge would never be presented as a human rating; P10F stays deferred) |

## 7. External API inventory
Read-only connectivity: OpenRouter public model catalogue (used once, free). Not executed: OpenRouter key check test (it exists as an Admin manual test), email delivery (needs a separately approved controlled inbox), Stripe and billing providers (outside this authorization), Google OIDC, Redis, ClamAV, Langfuse, Adzuna, realtime voice (not authorized here), speech providers (deferred).

## 8. Privacy and data
Only synthetic or public inputs are ever planned (the fixture corpus and the synthetic held-out agent cases); nothing real was or may be transmitted. If a provider retains submitted content, that is a provider policy to review before a paid run; nothing in this wave sent content. No credential value was read into any output; status reports presence only.

## 9. Comparison with offline evidence, regression and coverage
Offline engineering qualification is unchanged and re-run: backend 4,874 tests executed = collected through the CI-equivalent four-shard flow (4,840 passed, 34 skipped, 0 failed; 33 new tests), 26 evaluators PASS, P10C-G and P10D PASS, all 12 gates False. Product coverage is unchanged and **BELOW GATE**: developer-local legacy 386/412 (93.7%) and source-backed 386/412 (120 evidence-backed, 197 accepted abstentions, 69 clarifications); last clean-checkout figure 258/412; human-qualified 0/412; 95% (392) unchanged. A live AI response never qualifies a source. Frontend and browser tests were not affected (no frontend change) and were NOT RUN.

## 10. Accepted limitations
No live evidence exists; the plan's token sizes are assumptions; the guard enforces a worst-case ceiling, so a tight ceiling can stop a run early; SDK-internal retries are bounded by `max_retries` (default recommendation 1) and counted in the worst case but not individually observable; RAGAS and embeddings are not guard-integrated; per-language and interview-quality evaluation need new, pre-registered cases and a harness.

## 11. Remaining decisions (the owner's)
Section 2 limits and approval; embedding provider and model; RAGAS evaluator credential and model; reviewer appointments, rating protocol and acceptance thresholds (never set by engineering); approval of the synthetic persona set and the added multilingual cases before any output exists; whether a Fast and Advanced comparison is wanted.

## 12. Integrated requalification handoff
Integrated Candidate/Admin/Operations requalification is next only after the owner decides whether P10E's live execution runs now (after approving the limits) or is recorded as PREPARED and deferred. Until then every claim about live model quality, live RAG grounding, semantic relevance, multilingual quality and human-reviewed quality is NOT VERIFIED. Not production ready.
