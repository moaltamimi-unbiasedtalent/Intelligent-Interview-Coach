# Ask4Mo — Sprint 4 Deliverable Implementation Stories

Source material for the Sprint Review presentation. Each story: WHAT the sprint asked, WHY
Ask4Mo needed it, the DESIGN DECISION, HOW it's built, the FLOW, the EVIDENCE, the TRADE-OFF
rejected, the LIMITATION, and the CAPSTONE LESSON.

---

## Core 1 — Purpose

- **WHAT:** a clear product purpose. **WHY:** interview prep is fragmented — candidates research
  a role in one place, guess their gaps, and practise blind, losing context and grounding.
- **DESIGN DECISION:** unify *understand → prepare → practise → improve* under one AI coach (Mo)
  rather than a bag of disconnected tools.
- **HOW/FLOW:** Home → Ask Mo → Prepare → Practise → Progress/History, with evidence and human
  approval throughout. **EVIDENCE:** the working journey + the live golden rehearsal (PASS).
- **TRADE-OFF:** a single coherent product over a feature grid. **LIMITATION:** English-first,
  generic across professions (no per-domain tuning). **CAPSTONE LESSON:** anchor on one journey.

## Core 2 — Core functionality (the agent)

- **WHAT:** a stateful, tool-using agent. **WHY:** the task needs the model to *decide* which
  capability to use and whether to retrieve — not a fixed chain.
- **DESIGN DECISION:** one bounded LangGraph ReAct-style agent; deterministic logic lives in
  tools; HITL for the three decisions that matter.
- **HOW:** `src/agent/*` (graph, nodes, allowlist registry, checkpoint), boundary
  `src/application/agent_service.py`. **FLOW:** goal → agent node (bind allowlisted tools) →
  tools node → observe → (HITL interrupt) → answer; durable checkpoint per thread.
- **EVIDENCE:** `scripts/eval_agent.py` (56-case gate), `tests/test_agent_*`. **TRADE-OFF:**
  single-agent over multi-agent (Critique §13). **LIMITATION:** live tool-selection ~0.59–0.64.
  **CAPSTONE LESSON:** measure model behaviour separately from the graph contract.

## Core 3 — UI

- **WHAT:** a usable product UI. **WHY:** the coach is only as good as the journey around it.
- **DESIGN DECISION:** Next.js App Router + a focused primary nav (Prepare/Practice/Progress/
  History); supporting surfaces (Sources, Help, Review) under "More".
- **HOW/FLOW:** `frontend/app/*` client components over `/api/v1`. **EVIDENCE:** 166 vitest + 57
  Playwright e2e, incl. a return-journey product-surfaces spec. **TRADE-OFF:** restraint over
  chrome. **LIMITATION:** no per-user Agent-run browser (Inspector opens from a run link/id).
  **CAPSTONE LESSON:** a return-journey e2e catches "looks done but isn't."

## Core 4 — Technical

- **WHAT:** sound engineering. **DESIGN DECISION:** thin FastAPI over an application layer;
  Streamlit-free domain; durable persistence; strict user scoping; SSRF/injection guards.
- **HOW:** `src/api` → `src/application` → repositories/checkpoint. **EVIDENCE:** 2145 pytest,
  ruff, OpenAPI contract test, secret scan, Alembic single-head cycle. **TRADE-OFF:** transitional
  `X-User-Subject` identity over full OIDC. **LIMITATION:** production OIDC is deployment work.
  **CAPSTONE LESSON:** a typed application boundary lets two UIs share one backend safely.

## Core 5 — Documentation

- **WHAT:** reviewer-ready docs. **HOW:** README + reviewer guide/QA + architecture + requirements
  matrix + this file + the technical critique + the post-release audit. **EVIDENCE:** links in the
  README reviewer package. **LIMITATION:** docs must be re-checked against behaviour each phase (a
  stale "5 tools" claim slipped once — now guarded by the OpenAPI contract test where possible).

---

## Optional 6 — Technical critique

`docs/sprint4_technical_critique.md` — a real retrospective (choices, defects, reverted
experiment, single- vs multi-agent, lessons). **STATUS: YES.**

## Optional 10 — Help / guide

- **WHAT:** explain how the product works. **DESIGN DECISION:** one compact `/help` page (surfaces
  + key concepts), not an onboarding framework. **HOW:** `frontend/app/help/page.tsx`.
  **EVIDENCE:** `help.test.tsx`, e2e. **STATUS: YES.**

## Optional 16 — 5+ tools + capability control

- **WHAT:** 5+ tools and an enable/disable capability. **WHY:** users should control an external
  capability without a plugin marketplace. **DESIGN DECISION:** 6 career tools + 2 HITL actions
  already satisfy 5+; add ONE narrow, **server-enforced** toggle for current-market research.
- **HOW/FLOW:** `AgentRunRequest.enable_current_market_research` → `agent_service` sets
  `disabled_tools` → the agent node withholds the tool from `bind_schemas`, the tools node rejects
  it defensively. The model cannot re-enable it; the other five tools are unaffected.
- **EVIDENCE:** `tests/test_agent_capability_toggle.py` (withheld/available/only-that-tool/persists/
  defense-in-depth). **TRADE-OFF:** a single meaningful switch over a plugin system. **LIMITATION:**
  one capability today (extensible to others by the same mechanism). **STATUS: YES.**

## Optional 21 — RAGAS

- **WHAT:** RAGAS evaluation. **DESIGN DECISION:** a deterministic reproducible harness (fixed
  dataset, provenance) with an **opt-in** paid judge that never runs in CI. **EVIDENCE:** ID
  precision 0.676 / recall 0.516; `scripts/eval_ragas.py`, `docs/ragas_evaluation.md`; now visible
  read-only on `/review/evaluation`. **Paid judge: NOT RUN.** **STATUS: YES (deterministic).**

## Optionals kept "NO by design" (safety)

- **#9 Temperature/token sliders:** NO — candidate-facing low-level tuning weakens controlled model
  configuration. **#22 Self-adjusting agent:** NO — feedback → human review → explicit experiment,
  never automatic prompt/tool/code change. **CAPSTONE LESSON:** some "features" are safer withheld.

## Optionals already complete (preserved)

#8 LLM selection (Fast/Balanced/Advanced), #11 tokens/cost (Inspector usage), #12 memory
(approved, user-scoped), #13 external API tool (ResearchCurrentMarket), #15 feedback loop,
#17 multi-model, #18 security, #19 agentic RAG, #20 optional Langfuse, #23 external data — all
retained unchanged. #14 auth: real user scoping; production OIDC remains deployment work (PARTIAL).
