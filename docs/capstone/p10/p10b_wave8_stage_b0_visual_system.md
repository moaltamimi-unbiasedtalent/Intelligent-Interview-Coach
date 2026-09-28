# P10B Wave 8 Stage B0 - Visual System v2 integration

**Status:** DELIVERED (bounded release-candidate visual enhancement). NOT merged.
**Branch:** `feature/capstone-p10b-wave8-b0-visual-system` (from `origin/main`).
**Baseline SHA:** `d255d34` (Merge PR #97 = Wave 8 release qualification; Waves 1-8 all merged).
**Migration head:** `0014_opportunities` (unchanged).
**Paid/live/provider calls:** 0.

This stage integrates the approved `ask4mo-image-system-v2` package into the existing frontend as an
image-placement enhancement. It is not a redesign: routes, copy, i18n, forms, actions, navigation,
information architecture, data fetching, accessibility semantics and test selectors are unchanged.
The repository is the source of truth for component structure; the supplied package is authoritative
for asset selection, placement, crop, alt text and where images must NOT appear.

## Supplied asset set
`ask4mo-image-system-v2/` (README, image-inventory, claude-implementation-prompt, generation-prompts +
`images/*.png`). 12 production PNGs copied verbatim (same filenames) to `frontend/public/images/ask4mo/`.
Originals preserved; not regenerated, recoloured, stretched or edited.

### Asset integrity (verified)
| Asset | Pixels | Ratio | Alpha | Role |
|---|---|---|---|---|
| ask4mo-home-hero-documentary.png | 1840x854 | ~2.15:1 | no | photo |
| ask4mo-home-preparation-still-life.png | 1536x1024 | 3:2 | no | photo |
| ask4mo-product-connected-system-editorial.png | 1536x1024 | 3:2 | no | editorial illustration |
| ask4mo-trust-private-evidence-photo.png | 1448x1086 | 4:3 | no | photo |
| ask4mo-about-human-conversation.png | 1448x1086 | 4:3 | no | photo |
| ask4mo-help-journey-watercolor.png | 1536x1024 | 3:2 | no | editorial illustration |
| ask4mo-empty-opportunities-ink.png | 1448x1086 | 4:3 | **yes** | empty-state |
| ask4mo-empty-company-research-ink.png | 1448x1086 | 4:3 | **yes** | empty-state |
| ask4mo-empty-documents-story-bank-ink.png | 1448x1086 | 4:3 | **yes** | empty-state |
| ask4mo-empty-progress-ink.png | 1448x1086 | 4:3 | **yes** | empty-state |
| ask4mo-empty-history-ink.png | 1448x1086 | 4:3 | **yes** | empty-state |
| ask4mo-empty-workspaces-sharing-ink.png | 1448x1086 | 4:3 | **yes** | empty-state |

All six empty-state illustrations retain real alpha transparency; the four photos + two editorial
illustrations are opaque. Dimensions match the inventory exactly.

## Placement matrix (implementation)
| Surface | File | Placement | Asset | Treatment |
|---|---|---|---|---|
| `/` hero | `components/marketing/MarketingHome.tsx` | after `heroNote` | hero-documentary | `next/image` `fill`, rounded/bordered figure; desktop natural 2.15:1; mobile 3:2 crop `object-[72%_50%]` (keeps subject/notes/folio, never face/hands) |
| `/` problem->opportunity | `components/marketing/MarketingHome.tsx` | after the two comparison cards | preparation-still-life | 1536x1024, `h-auto w-full`, max-w 960, no crop (both sides visible) |
| `/product` | `components/marketing/ProductContent.tsx` | between intro `<header>` and PARTS grid | product-connected-system-editorial | full-frame bordered figure, warm paper preserved |
| `/trust` | `components/marketing/TrustContent.tsx` | after subtitle, before controls `<dl>` | trust-private-evidence-photo | 1448x1086, `h-auto w-full`, no crop |
| `/about` | `app/about/page.tsx` | after the 3 paragraphs, before support note/CTA | about-human-conversation | 1448x1086, `h-auto w-full` |
| `/help` | `app/help/page.tsx` | between `PageHeader` and `HelpCenter` | help-journey-watercolor | full-frame bordered figure, max-w 960 |
| `/opportunities` empty | `components/opportunities/OpportunitiesClient.tsx` | `EmptyState illustration` when `items.length===0` | empty-opportunities-ink | `EmptyStateIllustration` (280/360px) |
| `/company` initial empty | `components/company/CompanyResearchClient.tsx` | `EmptyState illustration` for the initial `company.emptyTitle` only | empty-company-research-ink | `EmptyStateIllustration` |
| `/documents` story bank empty | `components/documents/DocumentsClient.tsx` | between Story bank subtitle and empty message when `stories.length===0` | empty-documents-story-bank-ink | `EmptyStateIllustration` |
| `/progress` empty | `components/progress/ProgressClient.tsx` | `EmptyState illustration` in "Nothing saved yet." | empty-progress-ink | `EmptyStateIllustration` |
| `/history` empty | `components/interview/HistoryClient.tsx` | `EmptyState illustration` in "No completed interviews yet" | empty-history-ink | `EmptyStateIllustration` |
| `/workspaces` sharing empty | `components/workspaces/WorkspacesPanel.tsx` | once, above both sharing sections, only when `sharedByMe` AND `sharedWithMe` are empty | empty-workspaces-sharing-ink | `EmptyStateIllustration`, no duplication |

`components/ui/States.tsx`: added an optional, backward-compatible `illustration?: ReactNode` prop to
`EmptyState` (rendered above the title with modest spacing; calls without it are byte-identical to
before), plus a shared `EmptyStateIllustration` helper (transparent PNG, centered, ~280px mobile /
~360px desktop, no coloured tile).

## Responsive treatment
`next/image` with intrinsic dimensions and `sizes`; `height: auto` (or `fill` inside an aspect-ratio
box for the hero) so there is no cumulative layout shift. Photographs use the existing border-radius +
border token; editorial illustrations keep their warm paper background inside a clean bordered figure;
empty-state art is centered and transparent with no coloured tile.

## Accessibility
- Alt text is taken **verbatim** from `claude-implementation-prompt.md` for all 12 assets.
- Heading hierarchy, landmarks, accessible names, keyboard navigation, focus behaviour and existing
  test selectors are unchanged. Figures are non-interactive (no new focusable/interactive elements,
  no duplicate controls).

## Provenance rule
The four photographs are AI-generated illustrative brand photography. They are NOT represented as real
Ask4Mo customers, employees, pilot participants, testimonials, documented events or evidence of
outcomes. No captions, badges, overlays, fabricated identities or testimonial framing were added.
The `/about` figure carries an explicit code comment stating the depicted people are not employees/
customers/testimonial subjects.

## Visual QA (dev build, backend :8020)
Desktop (1024px) and mobile (390px). No horizontal overflow (measured `scrollWidth===clientWidth` at
390px), no distorted aspect ratios, no face/hand crop violations, no CTA/text overlap, no broken images.

| Surface | Desktop | Mobile 390px | Notes |
|---|---|---|---|
| `/` hero | PASS | PASS | mobile crop keeps subject/notes/folio; face/hands intact |
| `/` still-life | PASS | PASS | full frame, both sides visible |
| `/product` | PASS | PASS | editorial paper background preserved |
| `/trust` | PASS | PASS | both hands + folio + source card visible |
| `/about` | PASS | PASS | both people visible |
| `/help` | PASS | PASS | watercolor journey between header and HelpCenter |
| `/history` empty | PASS | PASS | transparent, above title; no overflow |
| `/progress` empty | PASS | (desktop verified) | transparent stepping stones |
| `/documents` story bank empty | PASS | (desktop verified) | shown though a document exists (stories empty) |
| `/workspaces` sharing empty | PASS | (desktop verified) | shown once; both headings/messages retained |
| `/company` initial empty | PASS | (desktop verified) | initial research empty state only |
| `/opportunities` empty | code-verified | code-verified | see defects/limitations |

### State QA
- **EMPTY:** illustration shown (5 of 6 verified live; opportunities code-verified).
- **ERROR:** verified on `/opportunities` (dev API 404) - the empty-state illustration does **not**
  leak into the error state (`ErrorState` renders instead).
- **LOADING:** guarded - each client renders `LoadingState` in its loading branch; the illustration
  lives only in the empty branch.
- **POPULATED:** verified on `/documents` (a real document present) - the story-bank illustration
  correctly appears only because the Story bank itself is empty; it does not leak into populated lists.

## Intentionally image-free surfaces (verified unchanged)
`/pricing`, `/privacy`, `/terms`, `/ai-transparency`, `/sign-in`, `/register`, `/forgot-password`,
`/reset-password`, `/verify-email`, `/onboarding`, `/app`, `/prepare`, `/practice`, `/sources`,
`/review*`, `/settings`, `/account`, `/admin`, `/opportunities/[id]`, `/history/[id]` - no imagery
added. Their lack of imagery is intentional.

## Test results (0 paid/live)
- `tsc --noEmit`: clean (7-locale key parity intact).
- `next lint`: no warnings/errors.
- `vitest run`: 282 passed / 53 files (incl. `no-emdash` guard over the edited marketing/about files).
- `next build`: success.
- Playwright (CI, fresh build+start): 119 passed, 0 failed.
- Evaluators: `eval_marketing_product_trust` (32) PASS, `eval_release_candidate` (27) PASS,
  `eval_opportunity_journey` PASS, `eval_i18n_l10n` PASS, `eval_workspace_security` GATE PASS,
  `eval_documents_evidence` PASS.

## Defects found / fixed
- No product defects introduced or discovered.
- Dev-only observation: `next/image` on-the-fly optimisation in `next dev` paints large images a beat
  after first navigation (transient blank), which resolved on its own; production `next build` bakes
  responsive derivatives so this does not affect the built app. Not a code defect; no change made.

## Known limitations
- `/opportunities` empty state could not be viewed live in this environment: the dev backend on :8020
  returns HTTP 404 for the anonymous dev user's `GET /api/v1/opportunities` (a data/account condition,
  not related to this change). Its empty-state code path is identical to the five verified ones and
  passes tsc/lint/unit/Playwright; its error state was confirmed to show no illustration.
- Mobile (390px) live capture was performed for the hero and the History empty state; the other empty
  states were verified at desktop and use the same responsive `EmptyStateIllustration` sizing
  (280px mobile / 360px desktop), which is narrower than 390px and produced no overflow.

## Release impact
- Application files changed: 12 (`MarketingHome`, `ProductContent`, `TrustContent`, `app/about/page`,
  `app/help/page`, `ui/States`, `OpportunitiesClient`, `CompanyResearchClient`, `DocumentsClient`,
  `ProgressClient`, `HistoryClient`, `WorkspacesPanel`) - all presentational.
- Asset files added: 12 PNGs under `frontend/public/images/ask4mo/`.
- Backend: NONE. Database/migration: NONE. API: NONE. Auth: NONE. Privacy model: NONE.
- Runtime product behaviour: NONE (image placement only). Routes: NONE. Copy: NONE. i18n: NONE
  (alt text is component-level accessibility text, not a localized catalogue string in this stage).
- Accessibility: additive (verbatim alt text on new figures; no semantic/keyboard/focus change).
- Tests: none weakened; no test assertions changed.
- Paid/live calls: 0.

## Next
After this visual integration is merged and CI is green, proceed to **P10B Wave 8 Stage B:
RC-P10-002 + Pilot 2 readiness**. Do not create RC-P10-002 in this stage.
