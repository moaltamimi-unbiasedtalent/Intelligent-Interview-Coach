# Sprint 4 — Final Evidence Sheet

Numeric reviewer evidence from merged `main` (post-Phase-4, `1a1697c`). Regression values
are actual local runs with no paid provider calls and no live Langfuse call; the two
authorised paid live-quality runs are recorded separately in Section B (opt-in).

## Product regression

| Gate | Result |
|---|---|
| Python tests (`pytest -q`) | **1891 passed, 2 skipped** (the 2 skips are the RAGAS installed/absent guards) |
| Frontend unit tests (`npm test`) | **152 passed** |
| Playwright e2e (`npm run e2e`) | **50 passed** |
| Alembic head | **single head `0006_user_feedback`** (fresh upgrade; `0005→0006`; `0006→0005`; upgrade head — all OK) |
| Docker | production image **builds** |
| `ruff check .` | **pass** |
| `python -m compileall -q app.py src scripts tests` | **pass** |
| Secret scan (source) | **clean** |

## A. Deterministic agent orchestration — SCRIPTED / DETERMINISTIC MODEL HARNESS

> These are the graph/tool **contract** metrics under **scripted** routes — **not** live
> model performance. `required_tool_recall = 1.0` means expected-tool execution recall
> under the scripted cases, not a claim the real model always picks the right tool.

`python scripts/eval_agent.py` — **56 cases**, **GATE STATUS: PASS**:

| Metric | Value | Gate |
|---|---|---|
| required_tool_recall | 1.0 | ≥ 0.95 |
| unnecessary_tool_rate | 0.0 | ≤ 0.05 |
| required_retrieval_recall | 1.0 | ≥ 0.95 |
| unnecessary_retrieval_rate | 0.0 | ≤ 0.05 |
| citation_validity | 1.0 | == 1.0 |
| retrieval_sequence_validity | 1.0 | == 1.0 |
| completion_rate | 1.0 | ≥ 0.95 |
| unregistered_tool_attempts | 9 (all rejected) | — |
| hitl_trigger_recall | 1.0 | — |
| cross_user_access_failures | 0 | MUST be 0 |

## B. Live real-model agent evaluation

- `scripts/eval_agent_live.py` — **22 held-out cases**; profiles **Fast / Balanced /
  Advanced**; record/replay sanitised traces; paid opt-in (`--allow-paid` / `RUN_PAID_EVAL=1`).
  Without opt-in it prints "Configuration OK … did NOT run".
- **FIRST LIVE RUN (opt-in, Balanced, 2026-09) — immutable baseline:** 22/22 completed;
  retrieval-decision accuracy **0.909**, unnecessary-retrieval **0.0**, HITL-decision
  accuracy **0.909**, tool-selection accuracy 0.636, required-tool recall 0.636 (the real
  model often answers well without invoking the discrete JD/gap/plan tools — a
  model-behaviour signal, not a contract defect); ~$0.002/case. These are real-model
  *decision* rates on a bounded sample (**rubric-based live quality evaluation**), not an
  "accuracy %". This first result stays visible even if a second run is later authorised.

## B2. LLM-as-judge (qualitative quality — advisory)

- `scripts/eval_agent_judge.py` + `src/agent/judge.py` — a third, distinct layer that
  scores recorded live responses against a fixed rubric (intent / tool_choice /
  retrieval_decision / grounding / helpfulness / safety_control, each 0–2; total 0–12).
  Evaluation tooling only — never in the candidate path or CI, never runtime authority.
  See [docs/llm_judge_evaluation.md](llm_judge_evaluation.md).
- **FIRST LIVE JUDGE RUN (opt-in, Advanced judge over 21 judgeable Balanced traces,
  2026-09) — immutable baseline:** average **10.05 / 12** (median 10), pass-rate **0.76** (16/21 at the
  transparent threshold ≥9 · no critical failure · safety>0 · grounding when evidence
  used), **critical failures 0**, **safety failures 0**, grounding failures 2, retrieval
  false-positives 0 / false-negatives 2. Criterion averages: safety **2.0**, retrieval
  1.81, grounding 1.76, intent 1.67, helpfulness 1.57, tool_choice 1.24.
- **Advisory only** — human calibration of every critical failure + the lowest/highest +
  ≥3 borderline cases is required before treating these as evidence (see the judge doc).
  Run artifacts (`evaluations/agent_live/traces/`, `judge_summary.json`) are generated
  locally and git-ignored.
- **Why 21/22 judgeable:** one case paused for a human decision (HITL) with no final
  assistant answer to score, so it has no response text to judge; its HITL decision is
  still captured in the live harness (Section B).

## B3. Live-quality experiment (Phase 4.1) — tested and REVERTED

First-run observations prompted a targeted **prompt/tool-description experiment** (make
external career facts require retrieval; qualify insufficient/zero-source answers; confirm
genuinely ambiguous roles; recognise comprehensive-preparation intent). It was run **once**
as an experiment — no benchmark special-casing, no graph/tool/threshold changes.

**Two live runs (2026-09), used as evaluation evidence — not an optimisation loop:**

| | First run (baseline) | Second run (post-experiment) |
|---|---|---|
| completion | 1.0 (22/22) | 1.0 |
| tool-selection accuracy | 0.636 | 0.591 |
| required-tool recall | 0.636 | 0.591 |
| retrieval-decision accuracy | 0.909 | 0.864 |
| unnecessary-retrieval rate | 0.0 | 0.0 |
| HITL-decision accuracy | 0.909 | 0.909 |
| judge average (of 12) | 10.05 | 9.67 |
| judge median | 10 | 10 |
| judge pass | 16/21 | 15/21 |
| critical failures | 0 | 0 |
| safety failures | 0 | 0 |

> The targeted prompt/tool-description hardening did not produce a measurable improvement
> in the second live run. The four targeted cases made the same tool/retrieval/HITL
> decisions in both runs. The small aggregate differences are treated as run-to-run
> stochastic variation rather than evidence of improvement or material regression.

**Engineering decision:** two live runs were used as evaluation evidence, not as an
optimisation loop. The prompt-policy experiment was tested once and did not demonstrate
improvement, so the behavioural change was **reverted** rather than retained without
evidence — `measure → evaluate → reject an unsupported intervention`, not `measure → tune
the benchmark → rerun until the score rises`. `src/agent/policies.py` and
`src/agent/tools.py` are back at their pre-experiment state. The LLM-as-judge and live
harness tooling, and both runs' evidence, are kept.

**Remaining live-model observation (limitation, not a production failure):** the Balanced
model does not always select the discrete preparation tools the harness expects — in some
cases it gives a useful direct answer instead. Tool-selection discipline therefore remains
an identified *model-behaviour* improvement area; it does not break the candidate task.
Retrieval precision stayed strong (**unnecessary retrieval 0** in both runs), and **safety
failures 0** and **critical failures 0** in both runs. Both runs' raw artifacts are
generated locally and git-ignored; the numbers above are the record.

## C. RAGAS (generation quality)

- **35 cases** (`evaluations/ragas/cases.json`); metrics: faithfulness / response
  relevancy / context precision / context recall (not an accuracy %). Optional, paid,
  manual; evaluator must be configured against OpenRouter.
- **PAID LIVE RAGAS BASELINE: NO** (no successful paid baseline is claimed).

## Evaluation case counts

| Suite | Cases |
|---|---|
| Deterministic agent orchestration | 56 |
| Live agent harness | 22 |
| LLM-as-judge (over recorded live traces) | 21 |
| RAGAS | 35 |

## Reproduce

```bash
# Backend
python -m pytest -q
python scripts/eval_agent.py
python scripts/eval_agent_live.py            # prints "did NOT run" without --allow-paid
python scripts/eval_agent_judge.py           # LLM-as-judge: cost preview only without --allow-paid
ruff check .
python -m compileall -q app.py src scripts tests

# Frontend
cd frontend && npm ci && npm run lint && npm test && npm run typecheck && npm run build && npm run e2e

# Migrations (single head 0006)
DATABASE_URL=sqlite:///./_m.db alembic upgrade head
```
