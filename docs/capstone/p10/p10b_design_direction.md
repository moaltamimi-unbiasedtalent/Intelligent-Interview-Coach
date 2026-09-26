# P10B — Design Direction (proposal)

_Proposal only — nothing restyled yet. A coherent direction to implement later without
sacrificing accessibility. Grounded in the current implementation and the founder's brief
(minimal · premium · friendly · innovative · trustworthy · evidence-led)._

## Current state (evidence)
- **Two logos:** marketing header `🎯` emoji (`MarketingShell.tsx:30`) vs app vector mark
  (`Brand.tsx:24`); full stacked lockups (`public/brand/ask4mo-logo*.svg`) unused; all three
  assets labelled "NOT the final logo".
- **Emoji as iconography** everywhere (📚🧠🎤🔒🗣️🤝 feature cards; ▶◼🎙️🎤 voice controls;
  ▾▲✓ glyphs). No icon system.
- **No imagery** — no illustrations, screenshots, hero image, favicon, or OpenGraph image;
  `next/image` unused.
- **Tokens exist and are decent:** `tailwind.config.ts` (accent teal `#1a5e63`, sand secondary,
  success/warning/danger, radius 10/14, one soft shadow, `content`/`reading` max-widths); single
  font **Inter** (`app/layout.tsx`); dark/light via CSS vars with a user toggle. One empty CSS
  rule and an unused `secondary` color slot.
- **Em dash** "—" pervades customer copy (`en.ts`, legal banners).
- **Sparse primitives:** `Button` (primary/ghost only), `Card`, `Badge`, `Alert`, `Field`, `Tabs`.

## Design principles (target)
1. **One canonical Ask4Mo logo**, used identically in marketing and app chrome, plus favicon +
   OG image derived from it. Retire the emoji brand mark.
2. **A real icon system** (a single line-icon set, e.g. an MIT-licensed set like Lucide, rendered
   as inline SVG components) replacing every emoji used as UI iconography. Keep icons decorative
   (`aria-hidden`) with text labels retained for a11y.
3. **Premium-but-restrained visual language:** generous whitespace, a confident type scale (keep
   Inter for UI; consider one display weight for hero headings), the existing teal accent used
   sparingly, soft elevation, and **evidence-led product visuals** (real UI screenshots /
   annotated captures / simple diagrams) instead of empty boxes.
4. **Trust made visible:** on Trust and in-product, show the architecture (a simple data-flow /
   "what's private, what's shared, what's AI vs source" diagram) rather than prose alone.
5. **Punctuation:** replace em dashes "—" in customer-facing copy with "-" (or restructured
   sentences). This is a catalogue/copy edit (`en.ts` + a few components), not a code change.
6. **Accessibility is non-negotiable:** WCAG AA contrast for the palette in both themes, visible
   focus (already present), keyboard operability, `prefers-reduced-motion` (already honoured),
   labelled controls, and no meaning conveyed by icon/color alone.

## What to reuse vs add
- **Reuse:** the CSS-variable token system, dark/light handling, `content`/`reading` widths,
  `Card`/`Button`/`Badge` primitives, the marketing section rhythm on Home.
- **Add:** one canonical logo + favicon + OG image; an inline-SVG icon component set; a small
  illustration/screenshot library (or a lightweight illustration style); expanded Button variants
  (secondary/danger/link — tokens already exist); a Pricing comparison-table component; a
  Trust architecture diagram; a first-run wizard shell; a mobile marketing nav.

## Iconography replacement inventory (emoji → icon, for implementation)
| Location | Emoji | Suggested icon |
|---|---|---|
| `MarketingShell.tsx:30` brand | 🎯 | canonical Ask4Mo logo (not an icon) |
| `MarketingHome.tsx:9-14` feature cards | 📚🎤🔒🗣️🧠🤝 | book/graduation · mic · lock/shield · message-circle · brain/sparkles · users |
| `RealtimeVoiceControl.tsx:79` | 🎙️ | mic |
| `DictationControl.tsx:105` | 🎤 / ■ | mic / square-stop |
| `VoicePlaybackControl.tsx:71` | ▶ / ◼ | play / stop |
| `Disclosure.tsx:41`, `MoreMenu.tsx:92` | ▲▾ | chevron |
| `ThemeToggle.tsx:46` | ☀ ☾ | sun / moon |
| `FeedbackControl.tsx:103-105` | 👍👎 | thumbs-up/down |
| `MemoryManager.tsx`, `ProgressClient.tsx` | 📌 | pin |
| journey/priority glyphs (`JourneyChrome`, `PreparationPriority`, `StageProgress`) | ✓•○▲ | check/dot/circle; distinct priority icons (currently all "▲") |

## Constraints
- **Do not** apply cosmetic styling over the current IA (per the founder brief) — the redesign
  (Wave 7) should follow the IA fixes (Waves 1–6).
- The **marketing brand brief/questionnaire** should guide the final visual identity; this doc is
  the engineering-side direction, not the final brand system.
- Keep the honest **"engineering draft / pending legal review"** banners on policy pages.
- No new heavy dependencies without justification; prefer an inline-SVG icon set over an icon font.
