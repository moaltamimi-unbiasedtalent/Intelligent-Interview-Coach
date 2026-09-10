# Ask4Mo — Golden Demo Script (8–12 minutes)

**Ask4Mo · Intelligent Interview Coach · Mo · *Ask More. Be More.***

One role, one story, no improvisation. The candidate-facing AI Coach is **Mo** (the
identity of the stateful LangGraph Career Preparation Agent). Primary interface is
**Next.js + FastAPI** (Streamlit is legacy dev only — not part of this demo).

## Golden scenario (use throughout)

- **Role:** Senior Product Manager
- **Domain:** B2B SaaS / FinTech
- **Location:** Germany / EU

Use the same role, JD, background, memory and practice answer for the whole demo.

## Pre-flight checklist (all must be true before starting)

- [ ] Backend running: `uvicorn src.api.main:app --reload` → http://localhost:8000/api/v1/health OK
- [ ] Frontend running: `cd frontend && npm run dev` → http://localhost:3000
- [ ] `OPENROUTER_API_KEY` configured and `AGENT_COACH_ENABLED=true`
- [ ] **KB readiness:** `python scripts/check_demo_knowledge.py` → **DEMO KNOWLEDGE: READY** (do not start otherwise — see §KB precheck)
- [ ] Speed selector on **Balanced** (default)
- [ ] Database migrated: `alembic upgrade head` (single head `0006_user_feedback`)
- [ ] Clean demo session: no stale/failed in-progress interview (start Practice fresh)

### KB precheck (required)

```bash
python scripts/check_demo_knowledge.py
```

If it prints anything other than **DEMO KNOWLEDGE: READY**, **do not run the live demo** —
citations depend on the local knowledge base being built (a fresh checkout is empty). The
checker prints the exact build commands. Verified when READY: the golden retrieval query
below returns visible ESCO product-manager sources.

## Exact inputs (copy/paste — no improvisation)

**1) Home goal**
```
I have a Senior Product Manager interview at a B2B SaaS fintech in Germany next week — help me prepare the product-sense and behavioural rounds.
```

**2) Job description** (paste into Prepare → "Paste a job description")
```
Senior Product Manager — B2B SaaS (FinTech), Berlin (hybrid).
Own the product strategy and roadmap for a payments/analytics platform serving
enterprise finance teams. Discover customer problems, prioritise the backlog, and
align engineering, design, data and go-to-market. Define and track outcome metrics
(activation, retention, revenue). Partner with compliance on regulated workflows.
Requirements: 5+ years product management, B2B SaaS, data-informed prioritisation,
strong stakeholder communication, experience with API/platform products; FinTech or
regulated-domain exposure a plus.
```

**3) Candidate background** (paste into "Add your background")
```
7 years in product, last 3 as a PM on a B2B analytics SaaS. Shipped an API/platform
integration used by ~40 enterprise customers; led discovery and roadmap for a
reporting suite. Strong on stakeholder alignment and metrics (activation/retention);
less exposure to payments/regulated-compliance workflows.
```

**4) Retrieval-worthy question to Mo** (produces a VISIBLE citation)
```
What skills and responsibilities are typically expected of a Senior Product Manager?
```
> Verified: this returns grounded **Sources** (ESCO — product manager — Skills). Avoid
> "competencies for a product manager" — that phrasing currently returns insufficient
> evidence, and Mo will (correctly) say so rather than cite.

**5) Memory statement** (triggers a memory-approval HITL)
```
Remember that my priority gap is payments/regulated-compliance workflows.
```

**6) Practice answer** (for the first interview question)
```
I start from the customer problem and the outcome metric. On my analytics SaaS I ran
discovery interviews, sized the opportunity with usage data, then framed 2–3 options
with trade-offs for eng/design/GTM. For a payments feature I'd add a compliance
partner early, define guardrail metrics, ship a thin slice behind a flag, and measure
activation before scaling.
```

## Timed flow

**0:00–0:45 — Problem + value.** Candidates prepare in fragments — research a role, guess
gaps, practise blind. Ask4Mo joins **understand → prepare → practise → improve** into one
Mo-led flow, grounded in evidence and under the candidate's control.

**0:45–1:30 — Home → Ask Mo → Prepare.** On Home (Ask4Mo · Intelligent Interview Coach ·
*Ask More. Be More.*) paste input **(1)** and press **Ask Mo** → Prepare opens and Mo
begins with that same goal (introduces itself once; the goal never appears in the URL).

**1:30–3:00 — Mo analyses JD + background.** Add inputs **(2)** and **(3)**. Mo analyses the
job description into requirements and compares your background, surfacing strengths and the
priority gap (payments/compliance). Point out the restrained UNDERSTAND → PREPARE →
PRACTISE journey chrome and the Balanced speed tier (no raw model names).

**3:00–4:00 — One evidence-backed question → visible citation.** Ask Mo input **(4)**. Mo
retrieves career evidence and answers with a visible **Sources** list (ESCO product-manager
skills). Note: Mo retrieves only when it adds value, and shows only source titles/links —
never chunk ids or scores.

**4:00–5:00 — One HITL memory approval.** Send input **(5)**. Mo proposes a memory; show
**What will be remembered → Edit before saving → Approve**. Mo never saves without approval.

**5:00–6:00 — Journey / preparation progress.** Show the preparation checklist filling from
real completed steps, and (optionally) Progress / Settings → *What Mo remembers* with
edit/pin/preview.

**6:00–7:00 — Mo → Practice handoff.** When a plan exists, Mo offers **Ready to practise?**
The handoff card shows what transfers and where each piece came from (role / focus /
questions). Approve → the interview is created (idempotent, outside LangGraph) and Practice
opens with a subtle "Prepared with Mo" note.

**7:00–9:00 — One interview question → answer → evaluation.** Answer the first question with
input **(6)**. Show the structured **evaluation** (score + strengths/improvements).

**9:00–10:00 — Deep Dive or report / history.** Either start a **Deep Dive** on the answer,
or complete the interview to generate the **final report**, then open **History** (durable,
refresh-safe).

**10:00–11:00 — Agent Inspector.** Header **More → Review & Diagnostics → Agent Inspector**
(or `/review/agent`). Show the safe execution timeline: tools, retrieval, profile, model
calls, tokens/cost coverage, latency, cache — and that **no chain-of-thought, prompts or
raw checkpoint** appear.

**11:00–12:00 — Architecture + limitations + close.** One line: Next.js + FastAPI, Mo = a
bounded LangGraph agent (controlled tools, agentic RAG, selective memory, HITL) handing
into durable Interview Practice. Limitations: production OIDC, live PostgreSQL validation,
KB provisioning, experimental voice (off). Close on *Ask More. Be More.*

## Live-quality status (for questions)

Two authorised paid live runs were used as evaluation evidence (see
`docs/sprint4_final_evidence.md`): completion 1.0 both runs, 0 critical and 0 safety
failures both runs, unnecessary-retrieval 0 both runs; LLM-as-judge average ~10/12. A
targeted prompt experiment did not show measurable improvement and was reverted — measured
honestly, not tuned. Tool-selection recall is an identified model-behaviour area, not a
task-breaking defect.

## Fallback (no live provider / API key)

Do not invent a live result. You can still show: the `/prepare` UI + Speed selector,
`/settings` memory management, Practice setup and History; the Agent Inspector against a
saved run id; deterministic artifacts (`python scripts/eval_agent.py` — gate PASS) and the
evidence sheet; tests (`pytest -q`, `cd frontend && npm test` / `npm run e2e` — Playwright
mocks the API); and the architecture + requirements-matrix docs.
