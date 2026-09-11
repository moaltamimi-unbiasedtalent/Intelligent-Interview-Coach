# Presentation Update Notes (source of truth for the decks)

No `.pptx` source lives in this repo, so this file is the authoritative source for the
separate PowerPoint update. Every figure below is verified against merged `main` at the
final freeze. Do not claim any future/deferred item as implemented.

## Brand (canonical, everywhere)

The brand hierarchy across every deck — opening slide, titles, footers, speaker notes,
closing slide and file names — is:

> **ASK4MO**
> **INTELLIGENT INTERVIEW COACH**
> **Ask More. Be More.**

**Ask4Mo** is the consumer-facing brand; **Intelligent Interview Coach** is the
descriptor; **Ask More. Be More.** is the slogan (exact capitalisation/punctuation).
The candidate-facing AI Coach is **Mo**. When explaining the journey, use "**Ask Mo**",
"Mo helps the candidate prepare…", "Mo uses controlled tools…", "Mo decides whether
Career evidence is needed…". Technical slides must say: *"Mo is the candidate-facing
identity of the Career Preparation Agent."* Never call Mo a chatbot. No earlier product
name may appear.

### Rename the deck files to

- `Ask4Mo_Product_Journey_Final.pptx`
- `Ask4Mo_Sprint_Review_Walkthrough_Final.pptx`
- `Ask4Mo_Complete_App_Walkthrough_Final.pptx`

(The `.pptx` files are external to this repository; apply these renames there.)

### Marketing toolkit (from the authoritative brand documents)

- **Master promise:** Ask More. Be More.
- **Approved supporting lines:** "Prepare with purpose." · "Real conversations. Better
  preparation." · "Practise. Improve. Progress." · "From preparation to opportunity." ·
  "Ask Mo what matters. Practise what matters."
- **Logo concept:** The Conversation Bridge (two speech bubbles + one sweeping bridge; no
  robot imagery). **Palette:** Navy `#071A38`, Electric Blue `#1E83F3`, Cyan `#26D5E7`,
  Violet `#8A58EE`, Ice `#F4F8FC`.
- **Presentation truth:** Home = enter goal → **Ask Mo** → Prepare starts with the same
  goal (no re-entry); Mo introduces itself once; navigation is Prepare/Practice/Progress/
  History + More(Sources, Review & Diagnostics) + Account(Settings); the Prepare→Practice
  handoff is fixed (stable missing-config, valid industry/level, idempotent creation).
- **Never** call Mo a chatbot; avoid "guaranteed success"/"AI magic"/"perfect answers".

### Final completeness pass (restored capabilities + fixes)

- **Sprint-1 Practice parity restored:** the standalone Practice setup now exposes
  **Question types** (multi-select) and **Difficulty** under a "Customise (optional)"
  section, sourced from backend-owned taxonomies (`/interviews/options` now also returns
  `difficulty_levels`). Every option reaches the backend and affects the session; blank =
  backend defaults (behavioural / moderate). Core stays: role, industry, career level,
  number of questions.
- **P0 Mo → Practice regression fixed:** the "Cannot add a question from state ERROR"
  message was a *masking* secondary error — interview setup now stops as soon as a
  provider step fails and surfaces the original safe cause (503); the durable session
  stays resumable for an idempotent retry. The exact Non-Profit Organization / executive
  case is covered by a regression test.
- **Citations:** the retrieval → citation → Next.js path works; citations require the
  local KB to be built (datasets are not committed, so a fresh checkout is empty and Mo
  shows an explicit insufficient-evidence state instead). Verified retrieval: "registered
  nurse" → 5 O*NET citations, lane `structured_role`.
- **Logo:** the header Conversation Bridge mark was enlarged ~1.5× (20px → 30px).
- **QA counts** (reviewer freeze): Python 1928 passed / 2 skipped · frontend 155 · Playwright 51
  · deterministic agent GATE PASS (56 cases).

### Reviewer package (Phase 5)

- **Golden demo:** one role throughout — **Senior Product Manager, B2B SaaS/FinTech,
  Germany**. `docs/sprint4_demo_script.md` has exact copy/paste inputs, a pre-flight
  checklist and the 8–12 minute timed flow. Official review path: Home → Prepare →
  Practice → Progress/History → Agent Inspector (Streamlit / RAG Inspector / Evaluation
  page / Langfuse are NOT in the demo).
- **KB precheck:** run `python scripts/check_demo_knowledge.py` → **DEMO KNOWLEDGE: READY**
  before any live demo (3,528 vector passages locally; citations need the built KB).
- **Citations in the demo:** the query "What skills and responsibilities are typically
  expected of a Senior Product Manager?" returns visible ESCO product-manager sources.
- **Live-quality status:** two authorised paid runs recorded as evidence — completion 1.0,
  0 critical / 0 safety failures, 0 unnecessary retrieval (both runs); judge avg ~10/12. A
  targeted prompt experiment showed no measurable improvement and was reverted (measured,
  not tuned).

## Final navigation (use the REAL shell in screenshots/mockups)

- **Primary:** Prepare · Practice · Progress · History
- **More:** Sources · Review & Diagnostics
- **Account:** Settings
- **Home:** the "Intelligent Interview Coach" wordmark
- **Mobile:** bottom bar = the four primary destinations only; header **More** +
  account reach the supporting and settings routes.

Do NOT draw Home / Sources / Settings / Review as extra primary tabs.

**Home is a real entry point.** The Home field "What interview are you preparing for?"
transfers the typed goal into Prepare and starts the Coach — no re-entry required. The
transfer is ephemeral and same-tab (never in the URL, `localStorage`, logs or
observability). Any earlier statement that Home input did not forward into Prepare is
obsolete and must be removed from the decks.

### Screen classification (for the deck)

- **Primary screens:** Prepare, Practice, Progress, History
- **Supporting screens:** Sources (`/sources`), Review hub (`/review`)
- **Reviewer diagnostic:** Agent Inspector (`/review/agent`)
- **Legacy/info diagnostics:** RAG Inspector (`/review/rag`), Evaluation (`/review/evaluation`)
- **Account:** Settings (`/settings`)
- **Conditional states (never nav entries):** role confirmation, memory approval,
  practice handoff, and the three feedback surfaces.

## Final facts to put on the slides

- Sprint 4: **COMPLETE**
- Post-Sprint polish (P0–P5): **COMPLETE** (merged)
- Primary interface: **Next.js + FastAPI** · Legacy: **Streamlit** · Live voice: **experimental / off**
- Candidate journey: **UNDERSTAND → PREPARE → PRACTISE**
- Agent tools: **5** Career tools + 2 HITL action boundaries
- Multi-model: **Fast / Balanced / Advanced** (registry-backed; raw slug rejected)
- Feedback: **3 surfaces** (Agent answer, interview evaluation, final report); human-reviewed loop
- Observability: **Agent Inspector** + **optional Langfuse (OFF by default)**
- Alembic head: **0006**
- Tests: **Python 1928 passed / 2 skipped · frontend 155 · Playwright 51**
- Deterministic agent gate: **PASS** (56 cases)

### Evaluation figures

- Deterministic agent cases: **56**
- Live-harness cases: **22**
- RAGAS cases: **35**
- Paid live Balanced agent runs: **2 EXECUTED** (recorded evidence: completion 1.0 both,
  0 critical / 0 safety failures, unnecessary-retrieval 0.0, judge avg ~10/12)
- Paid Fast/Advanced profile comparison: **NOT EXECUTED**
- Paid live RAGAS baseline: **NOT EXECUTED**

## Deck 1 — Product Journey: add/update

- Sprint 4 complete; agent architecture (LangGraph over FastAPI/Next.js)
- P0→P5 evolution (grounding/eval honesty → cost/multi-model → memory control → journey/handoff → feedback/observability)
- Candidate journey slide (UNDERSTAND → PREPARE → PRACTISE)
- Memory control (edit/pin/preview/edit-before-save)
- Multi-model, feedback, observability
- Final evidence figures (above)
- Remaining deployment work (OIDC, Postgres validation)

## Deck 2 — Sprint Review Walkthrough: add/update

- Why this is agentic (tool choice + retrieval decision by LangGraph)
- Controlled-tool demo; Agentic RAG; HITL; multi-model
- Agent Inspector (no chain-of-thought)
- Feedback loop (human-reviewed, not self-learning)
- Practice handoff (typed PreparationContext, provenance, creation outside LangGraph)
- Evaluation layers (deterministic vs live vs RAGAS vs product regression)
- Requirements / over-delivery; final limitations

## Do NOT claim

Multi-agent · autonomous hiring decisions · autonomous self-learning · MCP · production
OIDC · live PostgreSQL production validation · paid model bake-off · paid live RAGAS
baseline · camera/video · voice as primary path.
