# P10B-W9 — UX Remediation Plan

Audit phase. No runtime code changed. Findings #1, #2, #3, #10, #11, #12. Each item lists the confirmed
problem (with evidence) and the smallest coherent remediation. Preserve accessibility and responsive
behaviour throughout.

---

## 1. Opportunity discoverability (finding #1 — High)

**Problem (confirmed).** The authenticated home funnels every primary action into **Prepare**, never
into **Opportunity**, and the nav label is low-emphasis grey jargon.
- `frontend/components/coach/HomeEntry.tsx:26-34,53,56,59` — hero input + both shortcuts all
  `router.push("/prepare")`.
- `frontend/components/home/ReturnJourney.tsx:109-128` — links History/Progress/Settings/Prepare, but
  **never `/opportunities`**.
- `frontend/components/layout/PrimaryNavigation.tsx:24-26` + `MobileNavigation.tsx:30-41` — inactive nav
  is `text-muted`, no icon, mobile truncates "Opportunities".
- The list/empty state itself is good (`frontend/components/opportunities/OpportunitiesClient.tsx:65,83-93`).

**Remediation (smallest coherent):**
1. Add an Opportunity-first primary CTA to `/app` (`app/app/page.tsx`) — "Prepare for a specific job →
   Create an Opportunity" above `HomeEntry`; make standalone-Prepare the secondary path.
2. Add `/opportunities` to `ReturnJourney` continuation chips.
3. Give the primary nav item real salience (darker default than `text-muted`, an icon; consider a
   plain-language label). All are class/data-level edits.

## 2. Welcome / post-onboarding (finding #2 — High)

**Problem (confirmed).** `finish()` hard-redirects to the generic `/app`
(`frontend/components/onboarding/OnboardingClient.tsx:95-97`); the already-written completion screen
copy `onboarding.completeTitle` ("Mo is ready") / `completeBody` (`frontend/lib/i18n/messages/en.ts:260-262`)
is orphaned — referenced nowhere. Nothing narrates Opportunity → Evidence → Prepare → Practice →
Improve (the `/app` 4-cell blurb omits Opportunity and Evidence).

**Remediation:** render a real completion step using the existing `completeTitle/completeBody` keys
with 2–3 next-action cards, primary = **"Create your first Opportunity"** (`→ /opportunities` create),
secondary = "Take the 2-minute tour", tertiary = "Explore on my own". Route `finish()` there (or
`/opportunities?welcome=1`) instead of `/app`. Reuse existing preference/onboarding plumbing — no new
store.

## 3. Tutorial v2 (finding #3 — High)

**Problem (confirmed).**
- No Opportunity or Company step; tour reflects the pre-Wave-6 model (`frontend/lib/tutorial/steps.ts:24-133`).
- 4/12 steps (`practice-handoff`, `practice-answer`, `deep-dive`, `report`) reference `data-tour`
  targets that don't exist in the DOM → silently highlight nothing.
- State is **browser-local only** (`frontend/lib/tutorial/storage.ts:12`, key `ask4mo.tutorial`) →
  cross-device/browser replay inconsistency (`storage.ts:53-57`).
- Entirely hardcoded English (steps + `TutorialController.tsx:119-200` chrome) — violates the i18n
  standard.

**Tutorial v2 (smallest coherent architecture):**
1. **Account-scope completion state** via the existing preference seam (`PATCH /auth/preferences`, same
   store as `onboarding_completed_at`) — add `tutorial_completed_at`/`tutorial_version`; keep
   `localStorage` only as an offline cache. Fixes device inconsistency with no new store.
2. **Rewrite `steps.ts` to the Opportunity-centred journey** — Welcome → Create first Opportunity →
   Add role/JD → Add CV/evidence → Prepare → Practice → Progress → History; add the missing
   `data-tour` anchors; delete/fix the 4 orphaned-target steps.
3. **Localize** every step + controller chrome via `useT`; add a `tutorial` namespace across all 8
   locales (after W9.7, 7 until then).
4. **Trigger from the onboarding completion screen** (finding #2), so the first-Opportunity step lands
   right after setup.

## 4. Trust (finding #10 — Medium)

**Problem (confirmed).** `frontend/components/marketing/TrustContent.tsx:11-29,49-56` renders 17
visually identical cards in one flat `<dl>` — no hierarchy, no grouping — and the control strings are
hardcoded English (only title/subtitle translated). **Claims are supported** (export/delete backed by
`src/api/routes/auth.py:435,487`); no unsupported absolutes found.

**Remediation:** group the `CONTROLS` array into ~4 labelled sections ("What we store / don't store",
"When AI is used", "Your controls: approve, export, delete, revoke", "What we never do"), promote the
3–4 highest-reassurance items, add prominent cross-links to Privacy/AI-transparency/Terms, and localize
the control strings (one new i18n namespace × 8 locales). Do not add marketing fluff or new claims.

## 5. Privacy / Data control UX (finding #9 — Medium)

**Problem (confirmed).** Controls exist but are scattered across Settings (Memory), Account
(export/delete), `/privacy` (static info page), and per-domain pages; there is **no selective delete for
completed interview history** (`src/api/routes/history.py:19-31` is GET-only) and no single place to
see/act on every data class. Full inventory + integrity constraints: PILOT_FINDINGS §3.

**Remediation:** a **read-only "Your Data / Privacy Center"** that inventories each data class and links
to its existing delete/export control (no new deletion semantics in W9.8). Respect integrity: history
crash-safety (`interviews.source_session_id`), checkpoint deletion via saver `delete_thread` only, audit
anonymise-don't-delete, Opportunity/Workspace SET-NULL cascades. Any *new* deletion (e.g. per-report)
is deferred until its integrity impact is analysed and gated.

## 6. Visual hierarchy (finding #11 — Medium)

**Problem (confirmed).** Primary nav + broad body copy share one muted grey (`--muted` overused —
`frontend/app/globals.css:11-64`; `PrimaryNavigation.tsx:24-26`, `MobileNavigation.tsx:31`), flattening
tier contrast; mobile bottom-bar labels truncate with a dot instead of icons; single-accent palette
gives weak CTA differentiation. Logo is fine; contrast passes AA (the issue is role usage, not raw
contrast).

**Remediation (class-level, no token overhaul):** darker default for inactive primary nav
(`text-foreground/80`); add icons to the mobile bar to survive truncation; reserve `text-muted` for
genuinely tertiary text and promote body copy one tier; strengthen secondary-CTA styling. Do **not**
blindly double logo/font sizes; preserve responsive + AA.

## 7. Product comparison (finding #12 — Low / feature)

**Problem.** No comparison exists. Pilot wants Ask4Mo vs generic AI tools / AI coaching apps / human
coaches, with pricing.

**Factual basis today** (authoritative: Wave 7 claims ledger + `frontend/lib/pricing.ts`):
Basic €0 (real); Premium €19.99/mo is a **preview request only** (`BILLING_ENABLED=false`) — never
present a purchasable tier. Claimable: Opportunity (per-job context), evidence-aware prep (approved
evidence only), grounded answers + abstention, privacy controls (no audio storage, export/delete,
approval-gated memory) — all implemented + deterministically tested. Caveat: multilingual = engineering
draft; voice + company web-fetch + OCR quality **live-UNVALIDATED**; Glassdoor/Kununu/Google/LinkedIn
**NOT integrated** (link-out only). No usage-tier superiority (BASIC already grants what candidates use).

**Recommendation:** frame as **"what's different about the approach,"** not "better than X," in three
columns using only provable rows, plus an explicit honest-limits row. Do **not** invent testimonials,
ratings, customer counts, outcome/success rates, or head-to-head accuracy numbers. External competitor
research (interviewcoach.ai, banqr.io) is a separately authorized task — no scraping/reproduction.

## 8. Sequencing note

Opportunity discoverability (#1), Welcome (#2) and Tutorial v2 (#3) are interdependent — the onboarding
completion screen is the natural launch point for both the first-Opportunity CTA and the tour. Do them
as one coherent wave pair (W9.4 → W9.5). Trust/visual/comparison (W9.9/W9.10) can follow independently.
