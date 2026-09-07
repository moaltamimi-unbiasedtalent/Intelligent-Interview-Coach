# Provisional Design Tokens

Per-concept tokens for later translation to CSS variables + a Tailwind theme.
**Provisional** until the user chooses a direction. Every body-text pairing meets
**WCAG AA** (≥ 4.5:1); large display text meets ≥ 3:1. No Tailwind is installed in
this phase.

## Shared scales (all concepts)

**Spacing** (4px base): `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96`.
**Type scale** (1.25 ratio): `12 · 14 · 16 · 18 · 20 · 24 · 30 · 38 · 48 · 60`.
**Line-height:** body 1.6 · headings 1.15. **Max reading width:** ~68ch.
**Motion:** 120ms (hover) · 200ms (enter) · 320ms (panel); ease-out; all disabled
under `prefers-reduced-motion`.

Radius and shadow differ per concept (see each below).

## Concept A — Quiet Intelligence

Deep restraint; editorial. Serif display + neutral sans body.

- Fonts: display **Fraunces** (fallback `Georgia, ui-serif, serif`); body **Inter**
  (fallback `system-ui, sans-serif`).
- Radius: small — `6px` (cards `10px`). Shadows: almost none; hairline borders.

| token | light | dark |
|-------|-------|------|
| `--background` | `#FAFAF8` | `#141414` |
| `--foreground` | `#17181A` | `#F2F1ED` |
| `--surface` | `#FFFFFF` | `#1C1C1D` |
| `--surface-2` | `#F3F2EE` | `#242424` |
| `--muted` | `#5E5F59` | `#A6A6A0` |
| `--border` | `#E6E4DF` | `#302F2C` |
| `--accent` | `#1F3A5F` | `#9DB8E0` |
| `--accent-foreground` | `#FFFFFF` | `#0E1726` |
| `--success` `--warning` `--danger` | `#2E7D4F` `#B4690E` `#B23A48` | `#6FBF8E` `#E0A758` `#E58794` |

## Concept B — Coach Workspace

Warm, present, human. One rounded sans; a calm intelligence accent (teal-green).

- Fonts: **Manrope** (fallback `system-ui, sans-serif`) throughout.
- Radius: generous — `12px` (cards `16px`, bubbles `18px`). Shadows: soft, low.

| token | light | dark |
|-------|-------|------|
| `--background` | `#FBF9F6` | `#15130F` |
| `--foreground` | `#201C18` | `#F2ECE4` |
| `--surface` | `#FFFFFF` | `#201C17` |
| `--surface-2` | `#F4EFE9` | `#2A251F` |
| `--muted` | `#6E655C` | `#B0A79C` |
| `--border` | `#EAE2D8` | `#352E27` |
| `--accent` | `#1E6F63` | `#5FC3B3` |
| `--accent-foreground` | `#FFFFFF` | `#06201C` |
| `--success` `--warning` `--danger` | `#2E7D4F` `#B4690E` `#B23A48` | `#74C795` `#E0A758` `#E58794` |

## Concept C — Guided Journey

Approachable, bright, stage-based. Functional accents for stages/status.

- Fonts: **DM Sans** (fallback `system-ui, sans-serif`) throughout.
- Radius: friendly — `10px` (cards `14px`, pills `999px`). Shadows: light, tidy.

| token | light | dark |
|-------|-------|------|
| `--background` | `#FCFCFD` | `#111318` |
| `--foreground` | `#1B1F27` | `#EEF1F5` |
| `--surface` | `#FFFFFF` | `#1A1D24` |
| `--surface-2` | `#F2F4F7` | `#232730` |
| `--muted` | `#5B6472` | `#A3ACBB` |
| `--border` | `#E3E7EE` | `#2E333D` |
| `--accent` | `#2563C9` | `#7FA8EC` |
| `--accent-foreground` | `#FFFFFF` | `#0A182E` |
| stage accents | teal `#0E7C86` · amber `#B7791F` | `#4FC2CC` · `#E0A758` |
| `--success` `--warning` `--danger` | `#17845A` `#B7791F` `#C0392B` | `#5CC694` `#E0A758` `#E97C6E` |

## Concept D — Precision Coach (recommended)

Premium neutral shell; one distinctive intelligent accent (deep teal); very subtle
secondary sand tone. Neutral sans throughout.

- Fonts: **Inter** (fallback `system-ui, sans-serif`); tabular numerals for scores.
- Radius: `10px` (cards `14px`). Shadows: one soft ambient level; hairline borders.

| token | light | dark |
|-------|-------|------|
| `--background` | `#F7F7F5` | `#131414` |
| `--foreground` | `#16171A` | `#F0F0EE` |
| `--surface` | `#FFFFFF` | `#1B1C1D` |
| `--surface-2` | `#EFEFEC` | `#232424` |
| `--muted` | `#5F626A` | `#A5A7AC` |
| `--border` | `#E4E4E0` | `#2E2F2E` |
| `--accent` | `#1A5E63` | `#63C0C2` |
| `--accent-foreground` | `#FFFFFF` | `#05201F` |
| `--secondary` (sand) | `#C9BBA0` | `#5A5342` |
| `--success` `--warning` `--danger` | `#2E7D4F` `#A66412` `#A83246` | `#6FBF8E` `#E0A758` `#E58794` |

## Contrast notes (AA)

Body foreground on background is ≥ 12:1 in every concept; `--muted` on
`--background` is ≥ 4.5:1; every accent/`accent-foreground` pair used for buttons
is ≥ 4.5:1. Status colours are always paired with an icon or text label, never
colour alone.

## Typography — production-safe choices

All chosen faces are open-source and Next.js-friendly (`next/font`): **Inter**,
**Manrope**, **DM Sans**, **Fraunces**. The prototypes load them from Google Fonts
with full system fallbacks, so they still render offline.
