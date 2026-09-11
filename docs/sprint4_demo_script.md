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

## Canonical demo configuration (use these exact ports — no improvisation)

| Piece | Value |
|---|---|
| Backend | `http://localhost:8000` (`uvicorn src.api.main:app --port 8000`) |
| Frontend | `http://localhost:3000` (`cd frontend && npm run dev`) |
| `FRONTEND_ORIGINS` | `http://localhost:3000` (the backend's default dev allow-list) |

The backend allows `http://localhost:3000` (and `http://127.0.0.1:3000`) out of the box, so
the default configuration needs no CORS env var. **If you must run the frontend on a
different port**, start the backend with that exact origin allow-listed —
`FRONTEND_ORIGINS=http://localhost:<port> uvicorn src.api.main:app --port 8000` — otherwise
the browser's first call fails a CORS preflight and "Ask Mo" shows a connection error
(this is what cost time in rehearsal #2). Never use a wildcard origin.

## Pre-flight checklist (all must be true before starting)

- [ ] Backend running: `uvicorn src.api.main:app --reload` → http://localhost:8000/api/v1/health OK
- [ ] Frontend running: `cd frontend && npm run dev` → http://localhost:3000
- [ ] `OPENROUTER_API_KEY` configured and `AGENT_COACH_ENABLED=true`
- [ ] **KB readiness:** `python scripts/check_demo_knowledge.py` → **DEMO KNOWLEDGE: READY** (do not start otherwise — see §KB precheck)
- [ ] **Demo identity + persistence readiness:** `python scripts/ensure_demo_user.py` → **DEMO IDENTITY: READY** (do not start otherwise — see §Identity precheck)
- [ ] **CORS / frontend-origin readiness:** `python scripts/check_demo_cors.py` → **DEMO CORS: READY** (backend must be running; see §CORS precheck)
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

### Identity precheck (required)

```bash
python scripts/ensure_demo_user.py
```

This resolves the demo identity to a persisted user and smoke-tests the two user-scoped
paths that failed the first rehearsal — **preparation memory** and **interview history** —
against the local database. It must print **DEMO IDENTITY: READY**.

If it prints **NOT READY**, the local SQLite file is almost certainly stale (created before
a migration, so it is missing a column such as `preparation_memories.pinned`). This is the
exact cause of the first rehearsal's failed memory save / failed history save / History
load error. The checker prints the precise rebuild commands — dev/demo data is disposable
and is backed up first:

```bash
mv data/interview_studio.db data/interview_studio.db.bak 2>/dev/null || true
DATABASE_URL=sqlite:///data/interview_studio.db alembic upgrade head
python scripts/ensure_demo_user.py   # re-check → DEMO IDENTITY: READY
```

Production databases are migrated with `alembic upgrade head`, never recreated. To send the
demo identity from the frontend, set `NEXT_PUBLIC_DEV_USER_SUBJECT=demo-reviewer` before
`npm run dev` (leaving it unset uses the anonymous dev user — both persist correctly once
the schema is at head; the failure was schema drift, not the identity).

### CORS precheck (required; backend must be running)

```bash
python scripts/check_demo_cors.py
```

With the canonical configuration (frontend on `http://localhost:3000`) this prints **DEMO
CORS: READY** without any env var. If it prints **NOT READY**, the frontend origin is not in
the backend's allow-list — the checker prints the exact `FRONTEND_ORIGINS=…` command to fix
it. This is the preventable friction from rehearsal #2, now caught before the demo rather
than as a mystery "connection error" on the first Ask Mo. Override the checked origin with
`FRONTEND_ORIGIN=http://localhost:<port>` if you run the frontend elsewhere.

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

## Rehearsal log

Honest record of live rehearsals. Kept immutable — a later fix does not rewrite an
earlier rehearsal's verdict.

### GOLDEN DEMO LIVE REHEARSAL #1: FAIL under strict demo criteria

First full live rehearsal of the golden scenario. **Verdict: FAIL** under strict demo
criteria, for two reasons:

1. **No visible citation was produced.** The retrieval-worthy question was answered, and
   the agent *did* decide to retrieve, but returned **0 sources** — so no visible
   **Sources** list appeared. Root cause: the agent issued a verbose, occupation-bearing
   natural-language query and the deterministic occupation resolver could not match it to a
   role (it needed a near-bare occupation string). Fixed in Phase 5.1 Defect B (general
   retrieval input handling — not special-casing the golden prompt).
2. **User-scoped History / persistence failed under the dev identity.** Saving the proposed
   memory failed safe; the completed report "didn't complete" saving to history; and the
   History view errored on load. Root cause: a **stale local SQLite file** created before a
   migration (missing `preparation_memories.pinned` / `interviews.source_session_id`) — not
   an auth or user-scoping defect. Fixed in Phase 5.1 Defect A (schema-readiness precheck +
   documented deterministic rebuild; see §Identity precheck).

Also observed: the Practice client needed a manual reload twice (after create, and after
Deep Dive → Return) — fixed in Phase 5.1 Defect C.

**Context (do not overstate the failure):** no P0 defects; the core journey worked
end-to-end; every failure was recoverable and reported *truthfully* to the candidate (Mo
said saving didn't complete rather than pretending it had); no crash; and **no code was
changed during the observation** — the run was recorded as-is, then remediated afterward.

### GOLDEN DEMO LIVE REHEARSAL #2: FAIL under strict demo criteria

Post-Phase-5.1 authorised paid re-run (no judge). **Verdict: FAIL** under strict demo
criteria. This verdict is immutable and is **not** rewritten by the Phase 5.2 fixes below.

What passed: **KB preflight PASS**, **identity preflight PASS**, Home → Ask Mo, Prepare (JD
analysis, gaps, plan), the memory-approval HITL and **memory persistence PASS**, the Mo →
Practice handoff card (**Mo → Practice PASS**), and the **History read PASS** (loaded
cleanly under the dev identity — the exact path that errored in rehearsal #1). **No code was
changed during the observation.**

What failed:

1. **Visible citation FAIL (P1).** The Agent reformulated the evidence question with the
   role **trailing** — "typical skills and responsibilities expected of a Senior Product
   Manager" — and the occupation resolver (which then handled scaffolded questions and
   occupation-*leading* keyword queries only) matched nothing, so retrieval returned **0
   sources**. Mo answered truthfully from the JD without fabricating a citation.
2. **Practice creation FAIL (P0).** Interview creation failed during **strategy generation**:
   the gpt-5.x reasoning model's output was truncated at the configured **1024** output-token
   budget (`finish_reason=length`), surfaced safely as a 503, and the retry re-ran the same
   doomed request. This blocked the entire Practice half (Q1, evaluation, Deep Dive, return,
   report), so Phase 5.1's Practice-client refresh fixes could not be validated live.

Also noted (P2): reaching a valid stack required manually setting `FRONTEND_ORIGINS` because
the frontend was started on a non-default port (a self-inflicted setup surprise).

**Both blockers were remediated in Phase 5.2** (P0: bounded strategy output-budget increase
to 3072 with the truncation/retry handling preserved; P1: position-agnostic, scaffold-anchored
occupation resolution; plus a documented canonical demo port + a CORS precheck). The
remediation is covered by deterministic/fake-provider tests — no paid re-run was performed in
Phase 5.2. A third live rehearsal is the next step; this #2 record stays **FAIL**.

### GOLDEN DEMO LIVE REHEARSAL #3: FAIL under strict criterion

Post-Phase-5.2 authorised paid re-run (no judge; frontend on :3001 with the documented
`FRONTEND_ORIGINS` override, as :3000 was held by an unrelated tunnel). **Verdict: FAIL**
under the strict criterion. This verdict is immutable and is **not** rewritten by the Phase
5.3 fix below.

What passed (the Phase 5.2 targets both confirmed live): **visible citation PASS** ("Source:
ESCO's product-manager skills framework [1]", source count 1) and **Practice creation PASS**
(strategy generation no longer truncates). Also PASS: Home → Ask Mo, Prepare, **memory
persistence**, **Mo → Practice**, evaluation, Deep Dive, **Return without reload**, report,
**History**, and Agent Inspector. **P0 = 0.**

What failed — **P1 = 1: "Q1 without reload".** After the handoff, Practice creation succeeded
and the session was ready server-side (two 200 GETs), but under `npm run dev` the client
stayed on the loading skeleton until a manual reload. Root cause: React StrictMode
double-invokes effects in dev, and `useInterview`'s `mounted` ref was set false in cleanup
but never restored to true on the second mount, so the successful GET was discarded. Production
(the production-build Playwright suite) was unaffected; the path was only reachable in a dev
rehearsal once the 5.2 creation fix landed.

**Fixed in Phase 5.3** (`useInterview` mounted-ref lifecycle; StrictMode not disabled; no
timeout/polling/forced reload), with a component test that renders PracticeClient under
`<StrictMode>` and fails pre-fix / passes post-fix. This #3 record stays **FAIL**; the fix
was validated live in the focused validation below.

### FINAL SHORT LIVE VALIDATION (Golden Rehearsal #4 — focused): PASS

Authorised paid, focused re-run of only the previously failing path after Phase 5.3 was
merged (`main @ 30dc952`), frontend under `npm run dev` with **React StrictMode enabled**
(the exact configuration that failed in #3), frontend on :3001 with the documented
`FRONTEND_ORIGINS` override. No judge run.

**Verdict: PASS.** Mo → Practice PASS · handoff completion (designed fields) PASS · Practice
create PASS · **Q1 without reload PASS** · evaluation PASS · Deep Dive PASS · **Return without
reload PASS** · report PASS (readiness 64/100) · **History persisted PASS** (Interview #7).
**Browser reload required: NO. P0 = 0, P1 = 0.** No code was changed during the validation.

Also confirmed live in this run: the Phase 5.2 targets — a **visible citation** ("Source:
ESCO's product-manager skills framework [1]") and **Practice creation** (strategy generation
no longer truncates) — and the persisted memory loading across sessions ("Using 1 saved
preparation memory"). This is the authoritative live proof for the reviewer path; no further
paid rehearsal is required for Sprint 4.

## Fallback (no live provider / API key)

Do not invent a live result. You can still show: the `/prepare` UI + Speed selector,
`/settings` memory management, Practice setup and History; the Agent Inspector against a
saved run id; deterministic artifacts (`python scripts/eval_agent.py` — gate PASS) and the
evidence sheet; tests (`pytest -q`, `cd frontend && npm test` / `npm run e2e` — Playwright
mocks the API); and the architecture + requirements-matrix docs.
