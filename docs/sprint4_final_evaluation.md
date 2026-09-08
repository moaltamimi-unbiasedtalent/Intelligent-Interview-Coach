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

These names are **deterministic orchestration regression metrics** — not RAGAS scores
and not model-accuracy claims.

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

## 3. Optional live-model benchmarks (manual, paid — not executed)

- A live agent benchmark (real model choosing tools/retrieval/HITL/arguments) and a
  Fast/Balanced/Advanced model-comparison harness are **manual, budget-conscious and
  opt-in**; neither is run automatically. **No paid comparative benchmark was
  executed**, so no "Balanced is optimal" style claim is made.

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
  `postcss`-via-`next@15` build-time items. Remediation requires breaking major
  upgrades (`vitest@4`, `next@16`); **deferred** rather than destabilise the final
  sprint (§39). No runtime request-handling exposure in the shipped product.
- **pip-audit** (run as a dev-only tool, then removed): ~60 advisories across the
  LangGraph/LangChain, `pypdf` and `chromadb` ecosystem. Fixes require **major**
  version upgrades (e.g. `langchain-core` 0.3→1.2, `langgraph` 0.3→1.0) that would
  require revalidating the whole agent stack; **documented as a maintenance follow-up**
  (§40 — do not blindly perform major upgrades). None are added as new runtime deps.

## 8. Known limitations

See `docs/sprint4_reviewer_guide.md` §Known limitations (production OIDC not
implemented; PostgreSQL full integration a deployment check; Record voice deferred;
Live experimental/off; per-operation Interview model tiering deferred; paid
model/RAGAS comparison not executed).
