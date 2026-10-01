# P10B-W9.5 — Post-Onboarding Welcome + Tutorial v2

Implementation record. Frontend-only. **No migration**, no backend/schema/API change, no RC, 0 paid/live.

- **Baseline:** branch `fix/p10b-w9-4-opportunity-discoverability` @ `4483f32` (W9.4). New branch
  `fix/p10b-w9-5-welcome-tutorial-v2` from it. Ancestry intact (4483f32 ← 7fc600b ← c9cdff5 ← 5984953 ←
  334ffbd ← 80354f3). Alembic head `0014_opportunities` (unchanged). RC-P10-002 immutable; no RC-P10-003.

## 1. Pilot findings addressed

- **PF-11** — onboarding finished by dumping the user into `/app`; the written completion copy was orphaned.
- **PF-12** — the tutorial omitted Opportunity, had 4 dead DOM targets, and stored completion only in a
  single device-local key (shared-browser leak).

## 2. Onboarding flow — before / after

**Before:** 7 config steps; `finish()` persisted `complete:true` then `router.replace("/app")`. The
`onboarding.completeTitle`/`completeBody` strings existed but were never rendered.

**After:** `finish()` persists `complete:true`, refreshes, then renders an intentional **Welcome**
completion state **inside `/onboarding`** (RouteGuard never redirects a completed user away from
`/onboarding`, so this is safe). Onboarding is durably complete before the Welcome shows. A completed
account that lands on `/onboarding` again (e.g. refresh) also sees the Welcome (not the wizard), so the
candidate is never forced back through setup.

## 3. Welcome experience

Reuses `onboarding.completeTitle` ("Mo is ready") + `completeBody`, plus a plain-language concept line
(`tutorial.welcomeConcept`) and three non-mandatory actions:
- **Primary** "Create your first opportunity" → `/opportunities?create=1` (the W9.4 existing create flow).
- **Secondary** "Take the quick tour" → sets a one-time autostart flag and enters `/app`, where
  Tutorial v2 starts.
- **Tertiary (quiet link)** "Go to your workspace" → `/app`.

Primary/secondary/tertiary are distinguished by element type + order (filled button / ghost button /
text link), not colour alone.

## 4. CTA behaviour

Create and Workspace use the router directly; Tour writes `sessionStorage["ask4mo.tutorial.autostart"]`
then navigates to `/app`. The `TutorialController` (mounted only in the full-product chrome, not on
`/onboarding`) reads the flag on arrival at `/app`, clears it, and starts the tour. One-time, no URL
hack, no arbitrary sleep.

## 5. Tutorial v1 audit (dead targets)

v1 = 12 steps. Existing `data-tour` anchors: `home-start, opportunity-entry (W9.4), target-role, ask-mo,
sources, memory, progress, history, help`. **4 v1 steps referenced permanently non-existent targets:**
`practice-handoff`, `practice-answer`, `deep-dive`, `report` (would need generated interview/report
state). State was a single device-local key `ask4mo.tutorial` (shared-browser leak).

## 6. Tutorial v2 step model (9 steps)

Opportunity → context/evidence → Prepare → Practice → improve. Leads with the candidate mental model
(no agents/RAG/model internals):

| # | id | route | target | theme |
|---|---|---|---|---|
| 1 | welcome | /app | (route-only) | Welcome to your workspace |
| 2 | opportunities | /app | `opportunity-entry` | Keep one job together |
| 3 | role-jd | /prepare | `target-role` | Role & job description |
| 4 | evidence | /documents | (route-only) | Your evidence stays yours |
| 5 | prepare | /prepare | `ask-mo` | Prepare with Mo |
| 6 | practice | /practice | (route-only) | Practise realistically |
| 7 | progress | /progress | `progress` | Track your improvement |
| 8 | history | /history | `history` | Revisit past sessions |
| 9 | help | /help | `help` | Help whenever you need it |

Opportunity (step 2) precedes Prepare (5) and Practice (6). **0 permanently-dead targets**: every
`target` is a verified existing anchor; steps 1/4/6 are intentionally route-only (never fabricate a CV,
interview or report to create a DOM target). `ASK4MO_TUTORIAL_VERSION = 2`.

## 7. Target/route map & no-fabrication

Each step navigates to a real route; a highlight is applied only when the anchor exists, else the card
explains from a stable page. No step requires user-generated state (no completed report, handoff card,
saved memory, Progress metrics or uploaded CV). A deterministic unit test (T3) asserts every target is
a known anchor or the step is route-only.

## 8. State persistence — before / after

**Before:** one global key `ask4mo.tutorial` = `{version, completed, dismissed, lastStep}`.

**After:** **account-scoped** key `ask4mo.tutorial:<user_id>` (same shape, version 2). The legacy
global key is ignored for account state and best-effort removed (`forgetLegacyTutorialState`). Still a
harmless UI-preference only (version/completed/dismissed/lastStep) — never CV/JD/answers/evidence/
interview content.

## 9. Account-scoping design & the migration decision

Account preferences (`user_preferences`, `PreferencesRequest`) are **typed columns only — no flexible
JSON store** (verified in `src/persistence.py` / `src/api/schemas/auth.py`). Durable *cross-device*
account tutorial state would therefore require a **migration** (a new column + schema changes). **Per
the W9.5 non-negotiable rule we did NOT add a migration.** Instead tutorial state is **account-scoped
localStorage** keyed by the account's own opaque `user_id` (exposed safely to the frontend). This
closes the Pilot shared-browser defect with no backend/migration. The smallest future change for
durable cross-device state (deferred, not done): add `tutorial_version`/`tutorial_completed` to
`user_preferences` and extend `PATCH /auth/preferences` + `AccountResponse`.

## 10. Shared-browser behaviour (Account A/B)

Account A completes/dismisses → written under `ask4mo.tutorial:A`. Account B on the same browser has no
key under `ask4mo.tutorial:B` → gets its own first-visit invitation. Proven by unit test T4 and an E2E
(reload as a different `user_id` → invitation reappears). No email/sensitive id in the key — only the
opaque `user_id`.

## 11. Versioning / migration behaviour

`ASK4MO_TUTORIAL_VERSION` bumped 1 → 2. `shouldInvite` re-invites once when the stored version differs
(non-blocking invitation card, never a forced modal). An existing user who completed v1 has no
account-scoped v2 state, so they receive a single non-blocking v2 invitation (or can replay from Help);
after dismiss/complete it does not reopen. v1 global completion is deliberately NOT treated as
authoritative for any authenticated account (AA).

## 12. Help replay

Unchanged mechanism: the Help "Take the tour" control dispatches `START_TOUR_EVENT`; the controller
always starts at step 1, even after completion, and changes no Opportunity/Practice/Progress data or
onboarding state.

## 13. i18n treatment

A new `tutorial` namespace (welcome CTAs + all tour chrome + 9 step titles/bodies) added across **all 7
locales** (en/de/fr/es/it/pt/nl), adapted per locale (matching each locale's term for "opportunity").
The `TutorialController` chrome and the Welcome are now fully localized (W9.5 scope). Catalogue parity
holds (key-parity test passes); no em dash; no Russian; the broader ~190-string cleanup remains W9.6.

## 14. Accessibility

Welcome: semantic `<h1>`/`<p>`, real button/link CTAs, visible focus, distinction not colour-only.
Tutorial: `role="dialog"` labelled by the step title, focus moves to the card on open, Escape dismisses,
Skip/Back/Next/Finish are real buttons, highlight is never the sole channel (the card carries the full
text), reduced-motion respected for scroll, Close has an `aria-label`.

## 15. Mobile behaviour (390px)

The tour card is bottom-anchored full-width on mobile (`inset-x-0 bottom-0`, `max-w-content`) so it
fits, does not overflow horizontally and keeps its buttons reachable; the Welcome stacks its CTAs
(`flex-col sm:flex-row`). Verified by the first-run E2E running through the mocked flow.

## 16. Privacy / data-inventory impact

**None to the server data model.** Tutorial state is device-local (account-scoped localStorage), not a
server-side account preference, so the privacy/data inventory is unchanged. The key stores only a
harmless UI preference (version/completed/dismissed/lastStep) and the opaque `user_id` in the key name;
no candidate content. (If durable server-side state is added later, it must be documented there and
included in account deletion/export — deferred.)

## 17. Tests / E2E

Unit (`tests/tutorial.test.tsx`, 13): T1 structure, T2 Opportunity-before-Prepare/Practice, T3 zero
dead targets + version 2, T10 catalogue keys present, invitation, T8 cross-route Next/Back + localized
progress, T6 dismissal, T5 completion (version 2), T7 replay from step 1, **T4 shared-browser account
isolation**, Escape, Welcome autostart-once, no-candidate-data. `tests/wave2-onboarding.test.tsx`
updated: completion now shows the Welcome (not a `/app` redirect). T9 (resume): last-step is persisted
but the tour intentionally replays from step 1; documented, not a resume-to-step feature.

E2E (`e2e/welcome-tutorial.spec.ts`, 3): onboarding → Welcome → Take tour (Tutorial v2 starts,
Opportunity step before Prepare, dismiss, reload does not restart onboarding); onboarding → Welcome →
Create first opportunity (handoff into the existing create flow); shared-browser Account A/B isolation.

## 18. Commands & results

- Frontend: typecheck clean, lint clean, **vitest 342 passed** (59 files), build 37 static pages.
- Targeted E2E `welcome-tutorial.spec.ts` 3/3.
- Full Playwright: **132 tests, 131 passed**. All W9.5 specs (welcome-tutorial 3, tutorial 3,
  onboarding 5) pass deterministically; the single failure per full run is a **pre-existing unrelated
  batch-load flake** (a different unrelated spec each run — `opportunity-discoverability`, then
  `auth.spec`), each of which **passes in isolation** (auth.spec 6/6, opportunity-discoverability 2/2)
  under the reused dev server. No W9.5-related deterministic failure. (The one genuine W9.5 interaction —
  the W9.4 test's tutorial-suppression using the old global key — was fixed to the account-scoped key.)
- Backend: **no change** (frontend-only). Evaluators PASS, 0 paid/live: `eval_onboarding_personalisation`,
  `eval_opportunity_journey`, `eval_identity_platform`, `eval_security`, `eval_i18n_l10n`,
  `eval_release_candidate` (27/27).

## 19. Known limitations

- Tutorial state is device-local (account-scoped), not cross-device — durable cross-device state needs a
  migration (deferred, §9).
- The tour replays from step 1 (no resume-to-last-step); last-step is still recorded but not used to
  resume (simpler deterministic behaviour).
- Non-tutorial chrome strings elsewhere remain English (full localization is W9.6).

## 20. Confirmations

- **No migration.** No backend/schema/API change. 0 paid/live calls. No RC created. RC-P10-002
  immutable. Pilot 2 not resumed. W9.6 not started.

## 21. W9.6 handoff — Full-App Localization Completion

Route the remaining ~190 hardcoded candidate-facing strings (LOCALIZATION_AUDIT §2/§3) through
`useT()`/`translate()` across all surfaces (Prepare/Mo chrome, Interview/History, Progress, legal/trust
bodies, `/app` cards, `lib/api/errors.ts` user messages, page metadata), collapse the backend locale
allowlists to one canonical source, and add the machine-checkable guard (a scoped `no-literal-string`
lint + a `no-emdash`-style scan) so new hardcoded English fails CI. Do NOT add Russian (that is W9.7).
See `P10B_W9_LOCALIZATION_AUDIT.md`.
