# UX Principles — Intelligent Interview Coach

## Who we design for

A candidate with an interview approaching. They are capable but **uncertain what
to prepare**, often overwhelmed, worried about gaps, and short on time. They want
confidence and concrete next actions. They do **not** care how retrieval, agents
or prompts work.

The interface should say, in this order:

1. *I understand what you're preparing for.*
2. *I know what matters.*
3. *Here's what to do next.*
4. *Let's practise.*

## Core principle — hide the machinery

The candidate journey is **Goal → Understanding → Preparation → Practice →
Improvement**, never *Model → RAG → Vector DB → Tool → Agent → Prompt*. Technical
capability appears only where it builds trust (sources/evidence, available on
demand). Execution detail lives in **Review & Diagnostics**, never in the coaching
flow.

## Principles synthesised from the references

Borrowed as *principles*, never as visual copies.

**heyCoach → coaching, not configuration.** Lead with the human outcome and a
sense of personal progression; warmth; one integrated journey; AI complements the
coaching rather than being the headline.

**Apple → restraint & hierarchy.** Confident typography, deliberate whitespace,
one product moment per screen, strong section separation, a single focused call to
action, complexity hidden behind simple presentation.

**Canva → obvious first action & progressive disclosure.** An unmistakable entry
point, guided discovery, understandable cards/tasks, low cognitive load, visible
progress.

**Lovable → intention over configuration.** The user expresses what they want in
plain language; the system does the complex work underneath; progress is visible;
iteration feels natural — without a generic "AI SaaS" aesthetic.

## Anti-patterns (explicitly avoided)

Generic purple/pink AI gradients · glowing AI orb identity · heavy glassmorphism ·
neon/cyberpunk · a wall of tiny metric cards · a 20-item sidebar · a chatbot/
ChatGPT clone · enterprise-admin density · dense forms on first contact ·
decorative gradients/particles/icons without meaning · stock photography · fake
testimonials, logos, usage numbers, success stats, or user data.

Target adjectives: **premium, calm, intelligent, human, trustworthy, focused,
modern.** Not flashy, gimmicky, over-technical, or obviously AI-generated.

## Copy style

Concise coaching language:

- "Let's understand the role."
- "Three areas are worth preparing."
- "You're strongest here."
- "Let's practise this next."

Avoid: "Execute Career Intelligence Analysis", "Run RAG", "Invoke Gap Tool",
"Agent reasoning complete". Technical wording belongs in Diagnostics only.

### Loading / agent-activity language

Describe safe, observable actions — never chain-of-thought:

> Understanding the role · Reviewing the requirements · Comparing your preparation
> areas · Checking career evidence

Never "Thinking…", never exposed reasoning.

## State design

- **Empty:** no preparation yet — offer the one first action.
- **Insufficient info:** ask for exactly one missing item (e.g. the target role).
- **Error:** calm and actionable; never a backend/implementation detail.

## Trust & sources

Default to a quiet line — *"Sources: O\*NET · ESCO · 4 more"* — expandable for
those who care. Citations never dominate a response. Deeper provenance lives in
diagnostics.

## Privacy UX

Explain briefly what an uploaded JD/CV is used for. Future memory is saved only on
explicit consent. Interview Practice never claims camera analysis; Live stays
experimental and OFF by default. No scary legalese in the ordinary flow.

## Accessibility baseline (all concepts)

WCAG AA contrast for body text · keyboard-first with visible focus · semantic
headings · ~44px touch targets · never colour-only status · `prefers-reduced-
motion` honoured · readable sizes. Interview Practice must stay usable under
pressure, so animation there is minimal.

## Motion

Motion communicates state — content entrance, step completion, panel expansion,
the handoff into practice. No constant animated gradients, floating particles,
spinning AI effects, or gratuitous parallax. All motion respects reduced-motion.
