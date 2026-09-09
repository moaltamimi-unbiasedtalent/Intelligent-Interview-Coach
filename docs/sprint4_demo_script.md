# Sprint 4 — Demo Script (8–12 minutes)

A guided review walkthrough of the Intelligent Interview Coach (Career Preparation
Agent). Primary interface is **Next.js + FastAPI**.

> **Setup.** Run FastAPI (`uvicorn src.api.main:app --reload`) and Next.js
> (`cd frontend && npm run dev`) with `AGENT_COACH_ENABLED=true` and an
> `OPENROUTER_API_KEY`. Use a free port if 3000 is busy (e.g. frontend on 3200; the API
> base defaults to `http://localhost:8000/api/v1`). See the README quick start.

## Timed flow

**0:00–0:45 — Problem + architecture.** Candidates need grounded, role-aware
preparation and realistic practice without losing progress. Sprint 3 built the Career
Intelligence layer; Sprint 4 turned it into a stateful LangGraph agent. Show the diagram
in `docs/sprint4_architecture.md`.

**0:45–2:00 — Prepare page.** Open `/prepare`. Point out the **UNDERSTAND → PREPARE →
PRACTISE** journey chrome and the **Speed** selector (Fast / Balanced / Advanced —
Balanced recommended). No raw model names in the UI.

**2:00–4:00 — Agent decides tools.** Enter a role/JD, e.g. *"Senior Product Manager at a
fintech next week — prep the behavioural and product-sense rounds"* and (optionally)
paste a short JD / a few lines of background. Start preparing. Show: the agent calls
controlled tools; a factual question (*"typical pay range for PMs in Germany?"*) triggers
**SearchCareerKnowledge** with **citations**; the preparation checklist fills in from
real completed steps.

**4:00–5:00 — Agent Inspector.** Reach it via the header **More → Review & Diagnostics**
→ Agent Inspector (or open `/review/agent` directly) for the run. Show the tool
sequence, retrieval, model **profile**, model calls, **tokens / cost coverage**,
**latency**, **cache hits/misses**, and the **journey** rows — and that **no
chain-of-thought / prompts / raw checkpoint** appear.

**5:00–6:00 — Memory.** When the coach proposes a memory, show **What will be
remembered** → **Edit before saving** → approve. Then **Settings → Preparation memory**:
edit, **pin**, and **What may be used next time** (enter a role → preview). Note pinning
changes priority only.

**6:00–7:00 — Practice handoff.** When ready, the handoff card shows **what** transfers
and **where each piece came from** (role / focus / questions). Approve → the interview is
created (outside LangGraph, idempotent) and Practice opens with a subtle "Prepared in
your Coach session" note.

**7:00–9:00 — Interview Practice.** Answer a question → structured **evaluation** →
optional **Deep Dive** → **complete** → **final report**. Mention durable
sessions/refresh-resume.

**9:00–10:00 — Feedback.** Rate an Agent answer / evaluation / report **Helpful / Not
helpful** (+ optional comment). Explain: feedback → aggregate → human review → evaluation
case → controlled change. **Not** autonomous self-learning; only the exact owned output
can be rated.

**10:00–11:00 — Evaluation evidence.** Show `docs/sprint4_final_evidence.md`: the
deterministic agent gate (56 cases, PASS), the live harness (22 cases, paid opt-in — not
run), RAGAS (35 cases, optional), and the product regression totals.

**11:00–12:00 — Limitations + close.** Production OIDC, Postgres deployment validation,
paid model/RAGAS baselines, bulk checkpoint retention — all intentional follow-ups.

## Fallback (no live provider / API key)

If OpenRouter is unavailable, do **not** invent a live result. You can still show:

- The UI: `/prepare` journey chrome + Speed selector, `/settings` memory management,
  the Practice setup and History pages.
- The **Agent Inspector** and feedback UI against a saved/known run id where available.
- **Deterministic artifacts:** `python scripts/eval_agent.py` (no provider calls, gate
  PASS) and the evidence sheet.
- **Tests:** `pytest -q`, `cd frontend && npm test` / `npm run e2e` (Playwright mocks the
  API — no provider needed).
- The architecture and requirements matrix docs.
