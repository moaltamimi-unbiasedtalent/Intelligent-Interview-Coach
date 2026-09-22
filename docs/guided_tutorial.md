# Ask4Mo — Guided Product Tutorial & Help Experience

In-product guidance in three complementary layers. It teaches the real journey
(Home → Prepare → Practice → Report → Progress → History → Help) and changes **no** Agent,
retrieval, model, Practice, memory or HITL behaviour.

## Three layers

1. **First-time guided tour** — a short, route-aware coach card that walks the journey.
2. **Contextual help** — small "Learn more" links on product surfaces that deep-link into the
   Help Center.
3. **Help Center (`/help`)** — the permanent, searchable reference; also hosts "Take the tour".

Flow: encounter a feature → short contextual explanation → *Learn more* → the matching
`/help#anchor` article. Long copy lives in the Help Center, not duplicated in tour steps.

## Guided tour

- **Invitation:** on the first eligible visit to Home, a small non-blocking card offers
  "Start tour" / "Maybe later" (~2 minutes). It never auto-launches.
- **Steps (12), route-aware:** Home start → role/JD context → Ask Mo → Sources → Memory →
  Practice handoff → Practice answer → Deep Dive → Report → Progress → History → Help. Each step
  navigates to its route and highlights a stable `data-tour` target when present; steps that
  would need generated state (a live handoff card, an in-progress answer, a report) fall back to
  a route-level explanation — **never fabricated data**.
- **Controls:** Back, Next, Skip, Close, an "N of 12" progress indicator, and Finish / Open Help
  Center on the last step. The user can exit at any time.
- **Replay:** always available via "Take the tour" in the Help Center (dispatches a
  `ask4mo:start-tour` event the controller listens for). A completed user is not re-invited but
  can replay.

## State (UI preference only)

Stored under `ask4mo.tutorial` in `localStorage`: `{ version, completed, dismissed, lastStep }`
(`ASK4MO_TUTORIAL_VERSION = 1`). It contains **no** candidate data — no CV, JD, answers, roles,
reports, memory, provider data or secrets (asserted by a test). Storage access is guarded so a
private window never throws; the tour still works, just isn't remembered.

## Stable targets

Highlighting uses explicit `data-tour="…"` attributes (e.g. `home-start`, `target-role`,
`ask-mo`, `sources`, `memory`, `progress`, `history`, `help`) — never brittle nth-child or
generated class selectors. Missing target → graceful route-level explanation.

## Accessibility & responsiveness

The card is a focusable `role="dialog"` with an ARIA label, live "N of 12" announcement, Escape
to close, and a logical tab order. It is a **non-blocking** card (no click-capturing backdrop),
so it never blocks HITL approval cards, Practice answer controls, dialogs or critical errors. It
honours `prefers-reduced-motion` (no smooth scroll) and uses a full-width bottom sheet on small
screens, a corner card on desktop.

## Contextual help links

Sources ("How Ask4Mo uses evidence" → `/help#sources`), Progress ("How Progress works" →
`/help#progress`), History ("What appears in History?" → `/help#history`). These reuse the Help
Center articles — no duplicate documentation.

## Help Center

A searchable reference (`frontend/components/help/HelpCenter.tsx`) with anchored sections:
Getting started, Prepare, Practice, Progress, History, Sources, Memory & approvals,
Privacy & safety, Troubleshooting, and a Reviewer & technical guide. Search is a simple local
title/keyword/text filter — **no embeddings, no LLM, no network**. Candidate onboarding never
walks through the reviewer/diagnostics surfaces; those stay in the Reviewer guide section.

## Implementation

- `frontend/lib/tutorial/` — `steps.ts` (data + version), `storage.ts` (safe UI-preference state).
- `frontend/components/tutorial/` — `TutorialController.tsx` (invitation + route-aware tour,
  mounted once in `AppShell`), `TutorialLauncher.tsx` ("Take the tour").
- No new onboarding dependency was added; the tour is a small internal component.

## Tests

- Unit (`frontend/tests/tutorial.test.tsx`, `help.test.tsx`): invitation, start/next/back,
  progress, dismiss (no auto-reopen), complete (versioned), replay via event, Escape, and a
  privacy assertion that storage holds only `version/completed/dismissed/lastStep`; Help sections,
  search and anchors.
- E2E (`frontend/e2e/tutorial.spec.ts`): first-visit invitation → start → route-aware advance →
  dismiss → refresh stays dismissed; Help search + replay; a contextual Sources → `/help#sources`
  deep link.

## Limitations

The tour does not adapt from behavioural analytics; Help search is keyword-based (deterministic
by design). Account-synced onboarding preferences and usage-driven guidance are possible future
work if user evidence justifies them.
