# Information Architecture

## Proposed user-facing structure

Internal package names (`career`, `copilot`, `interview`, `application`, `api`)
are **unchanged**. This is only the *user-facing* label and grouping proposal.

```
Intelligent Interview Coach
│
├─ Home                      (entry: "What are you preparing for?")
│
├─ Prepare                   ← user-facing name for Career Intelligence
│    ├─ Preparation workspace (role · strengths · gaps · priorities · sources)
│    └─ Coach (ask questions, get examples, draft answers)
│
├─ Practice                  ← Interview Practice
│    ├─ Live session (question → answer → feedback)
│    └─ (Type / Record; Live experimental, OFF by default)
│
├─ Progress                  ← Preparation memory + trajectory (future)
│
├─ History                   ← past interviews & reports
│
├─ Sources                   (knowledge/evidence — surfaced where useful)
│
├─ Review & Diagnostics      (secondary, developer/reviewer)
│    ├─ Agent Inspector      (future)
│    ├─ RAG Inspector
│    └─ Evaluation
│
└─ Account
     ├─ Profile
     └─ Settings
```

## Naming decisions (and why)

- **"Prepare"** replaces the internal name *Career Intelligence* in the candidate
  UI. Candidates think in terms of *preparing for an interview*, not "career
  intelligence" (which describes the retrieval architecture, not the user's goal).
  The internal `src/career` / `src/copilot` packages keep their names.
- **"Practice"** rather than *Interview Practice Studio* — shorter, verb-first.
- **"Progress"** rather than *Preparation Memory* for the candidate; "memory" is an
  implementation word. Diagnostics may still call the underlying store "memory".
- **"Review & Diagnostics"** groups everything technical (Agent/RAG Inspector,
  Evaluation) away from the coaching flow — reviewers find it; candidates don't
  trip over it.
- **"Sources"** rather than *Knowledge Base* — plain, trust-oriented.

## Navigation model

- **Primary nav** (candidate): Home · Prepare · Practice · Progress · History.
- **Utility**: Account (avatar menu), Sources (contextual, mostly inline).
- **Secondary**: Review & Diagnostics — reachable but visually de-emphasised
  (footer/utility area or an explicit "For reviewers" entry), never in the primary
  candidate path.

This maps cleanly onto the existing `/api/v1` surface: Prepare → `career/*`,
Practice → `interviews/*`, History → `history/*`, Sources → `knowledge/*`,
Diagnostics → `evaluation/*` (+ a future agent-inspector endpoint).

## Depth & disclosure

Three levels, never more on one screen:

1. **Decision level** — the one thing to do now (a primary action).
2. **Context level** — role, strengths, gaps, priorities (a panel/rail).
3. **Evidence level** — sources, provenance, diagnostics (on demand).

Progressive disclosure keeps level 1 dominant; levels 2–3 expand when asked for.
