# Sprint 4 · Phase 3A — Product UX & Visual Design Spike

A **design exploration**, not an implementation. It proposes the experience and
visual language for the future Next.js frontend of **Intelligent Interview
Coach**, then stops for a human decision. No production code, API, or runtime
behaviour changes in this phase.

## What's here

| File | Purpose |
|------|---------|
| [ux-principles.md](ux-principles.md) | Design principles, references synthesised, anti-patterns, copy style |
| [information-architecture.md](information-architecture.md) | Proposed IA + user-facing labels |
| [user-flows.md](user-flows.md) | Primary journey + 8 secondary journeys + HITL surfaces |
| [component-inventory.md](component-inventory.md) | Provisional component list (candidate / shared / diagnostic) |
| [concept-comparison.md](concept-comparison.md) | Scored comparison of the four directions + recommendation |
| [design-tokens.md](design-tokens.md) | Provisional tokens (colour/type/space/radius/shadow) per concept |
| `concepts/*/index.html` | Four self-contained static prototypes (tabbed screens) |
| `agent-inspector.html` | One diagnostic-surface concept (developer/reviewer) |
| `index.html` | **Design gallery** — start here |
| `previews/` | Rendered screenshots (desktop 1440 / mobile 390) |

## How to open

The prototypes are plain HTML/CSS (no build, no server, no dependencies):

```bash
open docs/design/phase3a/index.html      # macOS — the gallery
```

or open that file in any browser. Each concept page has in-page tabs for **Home ·
Prepare · Practice · Review**, a **desktop/mobile** toggle, and a **dark mode**
toggle. Everything is clearly-marked DEMO content.

## The four directions

| # | Name | Primary influence | One line |
|---|------|-------------------|----------|
| A | **Quiet Intelligence** | Apple | Editorial, restrained, one moment per screen |
| B | **Coach Workspace** | heyCoach + Lovable | A present coach; conversation with a live context rail |
| C | **Guided Journey** | Canva | Approachable, stage-based, always "what's next" |
| D | **Precision Coach** | hybrid | Premium shell + conversational prep + progressive disclosure |

Concept **D** is the *design-team recommendation* — **not** a final selection.
See [concept-comparison.md](concept-comparison.md).

## Ground rules honoured

- No generic AI-purple gradients, glowing orbs, glassmorphism, or chatbot clones.
- No fake logos, testimonials, stats, or fabricated user data — all content is demo.
- WCAG AA contrast, keyboard-first, visible focus, `prefers-reduced-motion`.
- Technical concepts (RAG, agent, tools) never surface in the candidate UI; they
  live only in the diagnostic surface.
