# P10B-W9.4 — Opportunity Discoverability & Job-Centric Entry

Implementation record. Frontend-only. No backend/schema/API/migration change. No RC. 0 paid/live.

- **Baseline:** branch `fix/p10b-w9-3-security-menu` @ `7fc600b` (W9.3). New branch
  `fix/p10b-w9-4-opportunity-discoverability` from it. Ancestry intact (7fc600b ← c9cdff5 ← 5984953 ←
  334ffbd ← 80354f3). Alembic head `0014_opportunities` (unchanged). RC-P10-002 immutable; no
  RC-P10-003.

## 1. Pilot finding addressed (PF-10)

Two of four Pilot participants could not find/create an Opportunity ("No, did not go through." / "Not
able to see the opportunity on the screen."). Goal: make the Opportunity mental model and entry point
obvious from the authenticated journey — without forcing Opportunity creation or redesigning the app.

## 2. Existing Opportunity journey BEFORE W9.4

- **Shortest create route:** `/opportunities` (nav) → click "New opportunity" → inline create wizard.
  Creation is **page state** inside `OpportunitiesClient` (`setCreating(true)` renders
  `OpportunityCreate`) — not a route, not a modal, no deep-link.
- **`/app` Home:** `ReturnJourney` (returning only) + `HomeHero` + `HomeEntry` (Prepare composer) + a
  static 4-cell blurb. **No mention of Opportunity anywhere.** The dominant action (`HomeEntry`) pushed
  straight into **Prepare** (`router.push("/prepare")`).
- **ReturnJourney:** continuation chips to History/Progress/Settings/Prepare — **no Opportunities**.
- **Nav:** `/opportunities` is `PRIMARY_NAV[0]`, but rendered as low-salience muted grey
  (`text-muted`) on desktop; on mobile the 5-column bottom bar `truncate`d "Opportunities" at ~390px.
- **Zero/one/many:** `/opportunities` list handles all (good empty state with illustration + create
  CTA; list for ≥1). Opportunity → Prepare continuity already works
  (`/prepare?opportunity=<id>` → `useOpportunityContext` prefills role + governed JD).
- **Audit answers:** Home primarily pushed to Prepare; no duplicate competing CTAs (there was just no
  Opportunity CTA at all); a first-timer could not understand "Opportunity" without explanation.

## 3. Why nav-first placement alone was insufficient

Opportunities was already first in the nav, but (a) it was rendered in muted grey (read as
de-prioritised secondary text), (b) truncated on mobile, and (c) the Home experience never explained
or pointed to the concept and actively funnelled users into Prepare. So the fix is primarily a **Home
discoverability entry + concept explanation**, plus nav salience — not bolding a word.

## 4. Home — before / after

**Before:** `ReturnJourney` → `HomeHero` → `HomeEntry` (Prepare) → blurb. No Opportunity entry.

**After:** `ReturnJourney` → `HomeHero` → **`OpportunityEntry`** → `HomeEntry` (Prepare) → blurb. A new
bounded `components/home/OpportunityEntry.tsx` card appears **before** the Prepare composer, explaining
the concept in plain language ("An opportunity keeps everything for one job in one place: the role,
company, your evidence, preparation and practice.") with one obvious primary action. Prepare remains
available directly below — Opportunity creation is **never mandatory**. It is one component (not an
Opportunities dashboard, not a duplicate of the list page). `data-tour="opportunity-entry"` makes it a
stable target for W9.5 (no tutorial behaviour added here).

## 5. First-use behaviour (zero Opportunities)

Concept explained + **primary CTA "Create an opportunity"** → `/opportunities?create=1`, which opens
the **existing** inline create flow directly (see §9). Secondary "View your opportunities" →
`/opportunities`. On loading/error the entry safely defaults to the create action.

## 6. Returning behaviour (existing Opportunities)

`OpportunityEntry` reads the **existing** owner-scoped `api.opportunities.list()` (no new endpoint) to
decide emphasis: with ≥1 opportunity the **primary action becomes "View your opportunities"** →
`/opportunities`, secondary "Create another" → `/opportunities?create=1`. It never says "create your
first", and never invents "current"/"recent"/"active" semantics (it uses only the count). The CTA row
renders only after the count resolves (a subtle skeleton meanwhile) so a returning user never sees a
brief wrong CTA.

## 7. ReturnJourney change

Added a **"Your opportunities"** chip → `/opportunities` alongside the existing continuation chips, so
a returning candidate reaches Opportunities without relying on the top nav. It links to the **list**
(never guesses which one to continue) — no fabricated recency/current-state.

## 8. Desktop navigation change

`PrimaryNavigation`: inactive items changed from muted grey (`text-muted`) to a legible default
(`text-foreground/80` + `hover:bg-surface-2`), so the primary nav reads as navigation and Opportunities
(first) is discoverable — without making any item look disabled. Active state unchanged. No icons added
(the app nav has no icon convention; typography/layout per the brief).

## 9. Mobile navigation change

`MobileNavigation`: inactive `text-muted` → `text-foreground/70`; label `text-xs`+`truncate` →
`text-[11px] leading-tight tracking-tight` (no `truncate`), `px-2` → `px-1`, so the full
"Opportunities" word fits a 5-column bar at ~390px without an ambiguous ellipsis. An explicit
`aria-label` = the full localized label guarantees the accessible name stays "Opportunities" regardless
of visible width. Touch target (`min-h-[52px]`) and active state (accent colour + dot) preserved. The
underlying concept word is unchanged across desktop/mobile.

## 10. `?create=1` deep-link (reuse, not a second implementation)

`OpportunitiesClient` now reads `useSearchParams()`; `?create=1` initialises `creating=true`, opening
the **same** `OpportunityCreate` inline flow. This is the only change to the Opportunities page — no new
creation implementation, no redesign, no status pipeline/Kanban/CRM.

## 11. Opportunities page

Otherwise unchanged. The existing empty state (illustration + create CTA) and create wizard are strong
and were left alone. No backend Opportunity semantics changed.

## 12. Opportunity → Prepare continuity (verified, not rebuilt)

Verified the existing governed flow: the Opportunity detail ("Open Prepare") links to
`/prepare?opportunity=<id>`; `lib/useOpportunityContext.ts` loads the owner-scoped Opportunity (404 on
foreign) and `AgentPrepareWorkspace` pre-populates the target role and the governed JD document id
(owner-scoped; editable; precedence: explicit session > opportunity > account > default), showing a
"Preparing for this opportunity" note. No change to scoring/prompts/retrieval. The E2E exercises this
end-to-end.

## 13. Accessibility

`OpportunityEntry` uses a semantic `<h2>` + `<p>` and real `ButtonLink` anchors (keyboard-focusable,
clear accessible names "Create an opportunity" / "View your opportunities"); the loading skeleton is
`aria-hidden`. Nav links keep `aria-current="page"`, focus styles and 44–52px targets; the mobile
accessible name is the full word via `aria-label`; colour is never the only signal (active = colour +
dot + aria-current). No icon conveys meaning without text.

## 14. Localization / i18n of new copy

All new candidate strings were added to the existing `home` namespace across **all 7 locales**
(`opportunityTitle`, `opportunityBody`, `opportunityCreate`, `opportunityView`,
`opportunityCreateAnother`, `yourOpportunities`), adapted naturally per locale and matching each
locale's established term for the concept (de Möglichkeit / fr opportunité / es oportunidad / it
opportunità / pt oportunidade / nl kans). Catalogue parity holds (i18n key-parity test passes); no em
dash (colon used); no Russian added; the ~190 pre-existing hardcoded strings remain for W9.6.

## 15. Home → Prepare Playwright flake (Section M)

**Classification: pre-existing environment/timing flake, unrelated to W9.4 and not reproducible in
isolation.** The W9.3 full run showed one `nextjs.spec.ts:14` failure ("home primary CTA navigates to
Prepare") whose failing assertion is `getByLabel("Ask the coach")` on **`/prepare`** (Prepare-workspace
hydration) — not the Home CTA hierarchy. W9.4's Home change adds `OpportunityEntry` but introduces **no**
new "What interview are you preparing for?" / "Ask Mo" selectors, so there is no CTA-selector ambiguity.
Run repeatedly with the W9.4 changes present: `nextjs.spec.ts --repeat-each=5` → **35/35 passed**. No
sleeps/retries/timeout changes made (per Section M). Root cause: the shared dev server occasionally
exceeds the 10s expect timeout for the Prepare composer under full-suite batch load.

## 16. Tests

Frontend unit — `tests/home-opportunity.test.tsx` (D1 concept + create-first CTA; D2 CTA deep-links to
the real create route; D3 returning → View primary, never "your first"; plus error fallback + no
owner-scoped call when unauthenticated); `tests/nav-opportunity.test.tsx` (D4 Opportunities first +
all routes present + active on `/opportunities` and child routes + not muted-only; D5 mobile accessible
name intact + not truncated + active; D6 all primary routes remain). Updated `tests/opportunities.test.tsx`
mock to provide `useSearchParams`.

## 17. E2E evidence

`e2e/opportunity-discoverability.spec.ts`: (1) the **Pilot task** — fresh candidate on `/app` sees the
Opportunity entry **above** the Prepare composer (boundingBox order), follows "Create an opportunity"
to `/opportunities?create=1`, creates one via the normal wizard UI, sees it in the list, opens it, and
continues "Open Prepare" → `/prepare?opportunity=1` with the governed context note visible; (2)
**mobile (390px)** — Home Opportunity entry visible + the bottom-nav "Opportunities" link has its full
accessible name and href. (The first-run Tutorial invitation — a W9.5 surface — is suppressed via
seeded localStorage so it does not overlap the create wizard.)

## 18. Verification results

- Frontend: typecheck clean, lint clean, **vitest 336 passed** (59 files; +10 W9.4 unit tests), build
  37 static pages. Targeted E2E `opportunity-discoverability.spec.ts` 2/2; `opportunities.spec.ts` 2/2.
- Full Playwright: **129 passed, 0 failed, 0 flaky** (127 → +2 W9.4 specs; the pre-existing `nextjs`
  flake of §15 did not recur this run).
- Backend: **no change** (frontend-only). Evaluators PASS, 0 paid/live: `eval_opportunity_journey`,
  `eval_security`, `eval_identity_platform`, `eval_i18n_l10n`, `eval_release_candidate` (27/27),
  `eval_marketing_product_trust` (32).

## 19. Security / privacy impact

None to the model. `OpportunityEntry` reads only the existing owner-scoped Opportunities list; no new
endpoint, no cross-user data, no fabricated recency. Opportunity associations, owner-scoping,
documents/evidence governance, authenticated-route boundary, admin-≠-superuser, HITL and provenance
are all unchanged. No analytics/telemetry vendor added.

## 20. Known limitations

- `OpportunityEntry` makes one extra owner-scoped `opportunities.list` read on Home (best-effort;
  failure safely defaults to the create CTA). Acceptable; no new backend.
- Mobile label fit relies on a small font (`text-[11px]`) for the longest locale labels; verified by
  the mobile E2E (full accessible name, visible, no ellipsis). Full visual-polish is W9.9.
- Chrome strings beyond the new copy remain English (full localization is W9.6).

## 21. Confirmations

- No backend change; no migration; no new Opportunity API/field/service. 0 paid/live calls. No RC
  created. RC-P10-002 immutable. W9.5 not started.

## 22. W9.5 handoff — Welcome + Tutorial v2

Next wave (PF-11/PF-12): render the already-written post-onboarding completion screen
(`onboarding.completeTitle`/`completeBody`) and route `finish()` there; rebuild the tour to the
Opportunity-centred journey (Welcome → **Create first Opportunity** → Add role/JD → Add CV/evidence →
Prepare → Practice → Progress → History) with real `data-tour` anchors (the new
`data-tour="opportunity-entry"` on Home is ready to target); move tutorial completion state to the
account (reuse `PATCH /auth/preferences`); localize tour steps + controller chrome. See
UX_REMEDIATION §2/§3.
