# Sprint 4 — Final Evaluation

This document records how the Intelligent Interview Coach agent was evaluated. It
deliberately separates **automated deterministic evaluation** (offline, no cost, run
in CI) from **optional paid live-model evaluation** (manual, explicit opt-in).

## 1. Deterministic agent orchestration evaluation

**What it measures:** tool routing, agentic-RAG decisions, citation validity,
completion and safety invariants — NOT LLM factual accuracy or "model intelligence".
Each case scripts the model's tool-call sequence, so behaviour is exercised
deterministically with **no provider calls**.

- Dataset: `evaluations/agent/tool_selection_cases.json` — **56 held-out cases**,
  hand-authored (never generated from the implementation under test). Categories:
  direct answer / no tool, JD analysis, gap analysis, preparation planning, question
  generation, Career retrieval (geographic / structured / hybrid / insufficient
  evidence), mixed tool sequences, prerequisite failures, unregistered-tool +
  prompt-injection-through-goal-text attempts, multi-step prep.
- Harness: `src/agent/eval.py` · Runner: `python scripts/eval_agent.py`
  (prints the metric table + gate status, exits non-zero on any gate failure).
- Gated in CI by `tests/test_agent_tool_selection.py`.

### DETERMINISTIC ORCHESTRATION REGRESSION METRICS (measured)

| Metric | Value | Gate | Status |
|---|---|---|---|
| required_tool_recall | 1.0 | ≥ 0.95 | PASS |
| unnecessary_tool_rate | 0.0 | ≤ 0.05 | PASS |
| required_retrieval_recall | 1.0 | ≥ 0.95 | PASS |
| unnecessary_retrieval_rate | 0.0 | ≤ 0.05 | PASS |
| citation_validity | 1.0 | == 1.0 | PASS |
| retrieval_sequence_validity | 1.0 | == 1.0 | PASS |
| completion_rate | 1.0 | ≥ 0.95 | PASS |
| unregistered_tool_attempts | 9 | ≥ 1 rejected | PASS |
| hitl_trigger_recall (probe) | 1.0 | ambiguous role pauses | PASS |
| cross_user_access_failures (probe) | 0 | == 0 | PASS |

**What this suite is (and is not).** The deterministic orchestration suite validates
the graph/tool **contract** against held-out **scripted** routes — expected-tool
execution, tool prerequisites, state carry-over, retrieval flags, citation/provenance
invariants, rejection of unregistered tools, completion, and selected HITL/isolation
invariants. It is **not a live-model tool-selection benchmark**: because each case
scripts the model's tool calls, `required_tool_recall = 1.0` means "expected-tool
execution recall under the scripted orchestration cases", **not** "the real model
chooses the right tool 100% of the time". A live agent benchmark (real model choosing
tools) is separate, manual and paid (§3), and was not run.

## 2. RAG / RAGAS status

The existing RAGAS integration (`src/copilot/evaluation/ragas_adapter.py`,
`ragas_runner.py`, `scripts/eval_ragas.py`, `evaluations/ragas/cases.json`) is
**preserved**. It measures generated-answer quality on the Career answer path:

- **Faithfulness** — how well generated claims are supported by retrieved context.
- **Response Relevancy** — how relevant the answer is to the question.
- **Context Precision / Context Recall** — retrieval quality where a reference exists.

Hard guards remain: NaN/inf scores are rejected; an all-invalid run is **FAILED** and
is **not** persisted as a baseline; runs are labelled COMPLETE / PARTIAL / FAILED (an
invalid score is never averaged into zero).

**Paid execution is opt-in only.** Nothing spends money automatically:

```
python scripts/eval_ragas.py            # offline guards / config validation only
python scripts/eval_ragas.py --live     # explicit paid run (needs RAGAS_EVAL_API_KEY)
```

Evaluator configuration: `RAGAS_EVAL_API_KEY` (separate evaluator key, never printed),
`RAGAS_EVAL_BASE_URL`, `RAGAS_EVAL_MODEL`, `RAGAS_EVAL_EMBEDDING_MODEL`.

**Live RAGAS run performed this sprint:** NO (no paid run authorised). The harness,
guards and command are in place; a live run records model, case count, metrics,
timestamp and valid/invalid counts (never credentials).

## 3. Live-model benchmarks (manual, paid, opt-in)

- The live agent benchmark (real model choosing tools/retrieval/HITL/arguments) is
  **manual, budget-conscious and opt-in** (never run automatically). **Two authorised
  paid Balanced runs were executed and recorded as evidence** (see
  `docs/sprint4_final_evidence.md` §B): completion 1.0 both runs, retrieval-decision
  0.909 / 0.864, unnecessary-retrieval 0.0, HITL-decision 0.909, LLM-as-judge avg
  10.05 / 9.67 of 12, **0 critical and 0 safety failures** both runs. A between-run
  prompt/tool-description experiment showed no measurable improvement and was reverted.
- A **Fast/Balanced/Advanced profile-comparison** run and a paid **live RAGAS** baseline
  were **not executed**, so no "Balanced is optimal" style claim is made.

## 4. Security & privacy results

- Consolidated agent security suite (`tests/test_security_phase11.py`) + existing
  per-surface suites: unregistered-tool executions **0**, cross-user leaks **0**,
  arbitrary graph-state mutation **not possible** (answer/mode only), citation
  fabrication **not possible**, memory/retrieved content **trust-separated as data**.
- Logging: no raw traceback / exception string / SQL params / credentials / candidate
  content in production logs (unhandled-error handler is safe-by-default; history
  persistence-failure logging is metadata-only). See
  `docs/sprint4_security_privacy.md`.

## 5. Durability results

- Agent HITL checkpoint, durable interview sessions, idempotent handoff, Deep Dive and
  report/history recovery all survive service/engine recreation (process-style restart
  tests). Optimistic concurrency rejects stale writes (409); operation leases prevent
  duplicate paid calls; completed-history idempotency is crash-safe
  (`source_session_id`).

## 6. Browser end-to-end results

- Playwright (`frontend/e2e/`, API mocked at the network layer — no paid calls):
  Agent Coach multi-turn, full Interview lifecycle (question → answer → feedback →
  Deep Dive → return → next → complete → report), refresh-restore, standalone setup,
  and the no-fake-Record / no-camera guarantees.

## 7. Dependency audit (disposition)

- **npm audit:** 7 findings (1 critical, 2 high, 4 moderate). All are in **dev/build
  tooling**, not runtime dependencies of the deployed app: `vitest` (critical) and its
  `vite`/`esbuild`/`vite-node` chain are the test runner; `postcss` (high) and `next`
  (moderate) are build-time. Production audit (`npm audit --omit=dev`) shows only the
  `postcss`-via-`next@15` items. Note `next` is a runtime dependency of the deployed
  Next.js server (not purely build-time), so this is a production-dependency finding.
  Audit findings and their current package paths are documented; **no exploit was
  demonstrated in the tested product flows**, and remediation requiring breaking major
  upgrades (`vitest@4`, `next@16`) is **deferred and remains a production maintenance
  item** (§39). The `vitest`/`vite`/`esbuild` findings are dev/test-only tooling.
- **pip-audit** (run as a dev-only tool, then removed): ~60 advisories across the
  LangGraph/LangChain, `pypdf` and `chromadb` ecosystem. Fixes require **major**
  version upgrades (e.g. `langchain-core` 0.3→1.2, `langgraph` 0.3→1.0) that would
  require revalidating the whole agent stack; **documented as a maintenance follow-up**
  (§40 — do not blindly perform major upgrades). None are added as new runtime deps.

## 8. Final GO / NO-GO checklist

| Gate | Status |
|---|---|
| Deterministic agent gates green (`scripts/eval_agent.py`) | ✅ PASS |
| No cross-user leaks | ✅ 0 |
| No tool-allowlist violations | ✅ 0 executions |
| No private content in logs | ✅ (safe-by-default; regressions) |
| Alembic clean (single head 0006, up/down) | ✅ |
| Backend suite + ruff + compileall | ✅ 1928 passed / 2 skipped |
| Frontend build + unit + lint + typecheck | ✅ 155 unit |
| Browser core flow (Playwright) | ✅ 51 passed |
| Docker build + container API smoke | ✅ (health/openapi/capabilities 200) |
| Secret scan (production code) | ✅ clean |
| No unresolved critical implementation blocker | ✅ |

Documented non-Sprint production follow-ups remain (see §9): production OIDC,
PostgreSQL live integration, dependency major-upgrade advisories, deferred
Record/Live/per-operation tiering, and opt-in paid model/RAGAS runs.

**Result: GO — ready for review.**

## 9. Known limitations

See `docs/sprint4_reviewer_guide.md` §Known limitations (production OIDC not
implemented; PostgreSQL full integration a deployment check; Record voice deferred;
Live experimental/off; per-operation Interview model tiering deferred; paid
model/RAGAS comparison not executed).

## 10. Post-Sprint optimisation (bonus polish)

A separate polish branch (`feature/post-sprint4-agent-polish`) improves quality,
evaluation honesty and observability without changing the Sprint 4 architecture.

### Implemented + tested (offline)
- **Live model evaluation harness** (`scripts/eval_agent_live.py`,
  `src/agent/live_eval.py`, `evaluations/agent_live/cases.json`, 22 cases). Measures
  the REAL model's tool/retrieval/HITL decisions on a bounded held-out sample, with
  sanitised recorded traces (`--record` / `--evaluate-recorded`). **Manual/paid,
  never in CI.** Distinct from the deterministic scripted regression.
- **Agent output guard** (`src/agent/grounding.py`, reusing Sprint-3
  `src/copilot/security/output_guard.py:guard_output`): deterministically redacts
  secret-like strings, flags verbatim system-instruction leakage, and validates
  **citation provenance** — removing final-answer citation markers not backed by the
  current run's retrieved evidence (fabricated/stale) and recording a safe warning. It
  also raises a safe uncited-retrieval observability warning when retrieval genuinely
  ran and produced citations but the answer carries no inline reference (never blocks).
  The deterministic Agent grounding guard validates citation provenance and blocks
  fabricated/stale citation references; **semantic claim-level faithfulness remains an
  evaluation concern measured by RAGAS/live evaluation when executed**, not a runtime
  cost. Removing an unsupported marker is a provenance fix, not a claim that the
  sentence is factually wrong. No extra model call.
- **Retrieve-vs-not policy** strengthened in the agent system prompt (no retrieval for
  small talk / process / rewrite / already-answered; retrieval for factual career
  evidence) + a preferred (not hard-coded) preparation sequence.
- **HITL interruption-frequency metrics** (`hitl_frequency`): safe rates + type
  breakdown for the offline HITL quality report.
- (Near-duplicate retrieval reuse already existed and is covered by
  `test_agent_retrieval`.)

### Measured
- Deterministic gates still PASS (see §1). This polish added offline tests only. The live
  agent benchmark was later run under authorisation — **two paid Balanced runs executed
  and recorded** (see §3 and `docs/sprint4_final_evidence.md` §B).

### Not executed
- Fast/Balanced/Advanced profile-comparison run; paid live RAGAS baseline (both opt-in).

### Optional / deferred (documented follow-ups)
- P1: **implemented** — agent usage accounting, Fast/Balanced/Advanced Coach modes and
  a safe per-thread retrieval cache. See §11.
- P2: memory-management UI (edit/pin, approval preview, next-run preview); expanded
  checkpoint-retention seam.
- P4: journey chrome (UNDERSTAND→PREPARE→PRACTISE), handoff provenance, Streamlit
  deprecation banner.
- Bonus: user-feedback learning loop; external company-research tool; external tracing
  provider. (External research/tracing are intentionally NOT implemented without a
  safe provider and guaranteed redaction — see the stop conditions.)

Claims stay accurate: the deterministic suite validates graph/tool contracts against
scripted routes; the live benchmark (when run) measures actual model decisions on a
bounded sample; RAGAS evaluates generated-answer grounding/relevance where executed.
No "100% accuracy" claims.

## 11. Agent cost/performance instrumentation (P1)

A second polish branch (`feature/post-sprint4-agent-cost-performance`) follows one
principle: **MEASURE FIRST, OPTIMISE SECOND.** It instruments the agent, then adds a
profile control and a measurable cache — all offline-tested, no paid provider call,
Sprint-3 Career internals untouched.

### Four DISTINCT measurement layers (kept separate)
1. **Deterministic orchestration regression** (`src/agent/eval.py`, `scripts/eval_agent.py`)
   — graph/tool contract against scripted routes (CI gate). Not a live-model benchmark.
2. **Live real-model evaluation** (`scripts/eval_agent_live.py`) — the real model's
   tool/retrieval/HITL decisions on a bounded sample; manual/paid, never in CI. Now also
   records profile, latency and (where the provider reports it) token usage + cost.
3. **RAGAS** — generated-answer grounding/relevance (opt-in, paid).
4. **Performance/cost metrics** (this section) — per-run token/model-call usage, latency
   and retrieval-cache hit/miss counts. Deterministic parts unit-tested; live cost is
   opt-in.

### Usage accounting (`src/agent/usage.py`)
One canonical safe `AgentRunUsage`: agent/tool/total model-call counts, input/output/
total tokens, estimated cost, `usage_complete` and `missing_usage_sources`. Outer agent
usage is read from the returned `AIMessage`; tool-internal usage is captured at the AGENT
boundary via LangChain's usage-metadata callback (no Sprint-3 change). Each provider call
is counted exactly once (agent turn + JD tool + question tool ⇒ 3, not 5–6).
**Unknown usage is never reported as zero** — a call without usage flips
`usage_complete=false` and is named in `missing_usage_sources`. Cost is reported-cost
where the provider gives it, else resolver-computed where pricing is wired, else `null`
(never invented; no false precision).

### Fast / Balanced / Advanced Coach modes
An optional request `profile` selects the registry model tier (a validated Literal — a
raw provider slug is rejected server-side, never accepted from the browser). Default is
Balanced. **Every profile preserves** the tool allowlist, retrieval grounding, the P0.1
citation guard, HITL, memory policy and the bounded step budget. The per-turn step
ceiling is kept at 6 for **all** profiles: Fast is deliberately not crippled, so
JD→gaps→plan→questions still completes (per §19, "if 4 is insufficient, keep 6").

### Safe retrieval cache
A bounded, per-thread cache reuses evidence for an equivalent factual request already
answered in the SAME thread, avoiding a second deterministic-pipeline call. The key is
the normalised query, which alone determines geography/occupation/lane — so a different
country, role, seniority or recency misses and re-retrieves. The cache is thread-scoped
(⇒ per-user, per-run; **never shared across users or runs**), FIFO-bounded, and lives for
the natural thread lifetime. Hit/miss **counts** are observable; cache **keys are never
logged or exposed**.

### Claims (honest)
- **Cost:** instrumentation and a profile-comparison harness are implemented; **NO PAID
  COMPARATIVE BENCHMARK HAS BEEN EXECUTED.** We do NOT claim e.g. "Fast reduces cost by
  62%." A real bake-off is run manually and opt-in:
  ```
  python scripts/eval_agent_live.py --allow-paid --profile fast --record
  python scripts/eval_agent_live.py --allow-paid --profile balanced --record
  python scripts/eval_agent_live.py --allow-paid --profile advanced --record
  ```
- **Cache:** a deterministic retrieval-call reduction is **proven in offline fake tests**
  (same-thread equivalent request → one pipeline call, not two). We do **not** claim a
  measured production latency reduction (no live latency benchmark was executed).

### Reviewer story
After completing Sprint 4, I separated orchestration regression from live model
evaluation and then instrumented the agent before optimising it. The system now tracks
provider usage where available, exposes truthful partial/complete coverage, supports
registry-backed Fast/Balanced/Advanced Coach modes, and avoids redundant same-thread
retrieval without sharing private cache state across users.
