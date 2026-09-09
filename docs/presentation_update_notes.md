# Presentation Update Notes (source of truth for the decks)

No `.pptx` source lives in this repo, so this file is the authoritative source for the
separate PowerPoint update. Every figure below is verified against merged `main` at the
final freeze. Do not claim any future/deferred item as implemented.

## Product name (canonical, everywhere)

The product name across every deck — title, slide titles, footers, speaker notes,
architecture labels, closing slide and the file names — is **Intelligent Interview
Coach**. The previous product name must not appear anywhere in the decks.

### Rename the deck files to

- `Intelligent_Interview_Coach_Product_Journey_Final.pptx`
- `Intelligent_Interview_Coach_Sprint_Review_Walkthrough_Final.pptx`
- `Intelligent_Interview_Coach_Complete_App_Walkthrough.pptx`

(The `.pptx` files are external to this repository; apply these renames there.)

## Final navigation (use the REAL shell in screenshots/mockups)

- **Primary:** Prepare · Practice · Progress · History
- **More:** Sources · Review & Diagnostics
- **Account:** Settings
- **Home:** the "Intelligent Interview Coach" wordmark
- **Mobile:** bottom bar = the four primary destinations only; header **More** +
  account reach the supporting and settings routes.

Do NOT draw Home / Sources / Settings / Review as extra primary tabs.

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
- Tests: **Python 1845 passed / 2 skipped · frontend 111 · Playwright 37**
- Deterministic agent gate: **PASS** (56 cases)

### Evaluation figures

- Deterministic agent cases: **56**
- Live-harness cases: **22**
- RAGAS cases: **35**
- Paid live model comparison: **NOT EXECUTED**
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
