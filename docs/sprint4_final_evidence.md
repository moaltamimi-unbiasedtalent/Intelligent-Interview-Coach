# Sprint 4 — Final Evidence Sheet

Numeric reviewer evidence, captured at the final-submission freeze from merged `main`
(`f890f3d`, containing the P5 merge `bac1bf9`). All values are actual runs — no paid
provider calls, no live Langfuse call.

## Product regression

| Gate | Result |
|---|---|
| Python tests (`pytest -q`) | **1845 passed, 2 skipped** (the 2 skips are the RAGAS installed/absent guards) |
| Frontend unit tests (`npm test`) | **111 passed** |
| Playwright e2e (`npm run e2e`) | **37 passed** |
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

## B3. First-run remediation (Phase 4.1)

First-run observations led to targeted **general-policy hardening** — no benchmark
special-casing, no graph/tool changes, thresholds unchanged, first-run baseline preserved:

- **External career facts require retrieval.** The system prompt + `SearchCareerKnowledge`
  description now state that role expectations, competencies, pay, labour-market and
  credentials must be retrieved before being asserted, and are *not* "answerable from what
  you already know".
- **Insufficient / zero-source evidence must be qualified.** When retrieval returns no
  reliable sources, Mo must say verified evidence is insufficient and give only
  clearly-labelled general guidance — never present the facts as established, never invent
  citations.
- **Ambiguous roles.** Mo asks the candidate to confirm a genuinely ambiguous role (that
  would change evidence/gaps/questions) before giving role-specific facts, while not
  interrupting for harmless ambiguity.
- **Comprehensive preparation intent** is recognised (use the capabilities that add value
  when inputs exist), while a single specific request is still honoured as just that.

Deterministic coverage: `tests/test_agent_policy_hardening.py`.

**SECOND LIVE RUN (opt-in, Balanced record + Advanced judge, 2026-09) — post-remediation,
measured honestly:** the hardening did **not** produce a measurable improvement in this
single 22-case run. Live: tool-selection 0.591, required-tool recall 0.591,
retrieval-decision 0.864, HITL 0.909, completion 1.0. Judge: average **9.67 / 12** (median
10), pass-rate **0.71** (15/21), **0 critical**, **0 safety failures**, grounding failures
2, retrieval false-negatives 3. All deltas vs the first run are small and *negative*,
consistent with small-n run-to-run variance, not a real change. On the four targeted cases
(`ambiguous_role_hitl`, `insufficient_evidence`, `competency_expectations`,
`full_prep_intent`) the model's tool/retrieval/HITL decisions were **identical** to the
first run — prompt-only hardening did not move this model's decisions here. **No live
improvement is claimed.** Strengths preserved: unnecessary-tool 0, unnecessary-retrieval 0
(the hardening did not cause over-retrieval), 0 critical, 0 safety failures. Both runs'
raw artifacts are generated locally and git-ignored; the numbers above are the record.

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
