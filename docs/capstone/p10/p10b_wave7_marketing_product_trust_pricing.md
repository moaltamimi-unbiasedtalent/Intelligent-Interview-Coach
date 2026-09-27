# P10B Wave 7 - Marketing, Product, Trust & Pricing Experience

**Status:** DELIVERED (implementation complete; gates green).
**Branch:** `feature/capstone-p10b-wave7-marketing-product-trust-pricing` - **not merged**.
**Baseline:** `main` @ `934b006` (Waves 1-6 merged; PRs #87..#95).
**Migration:** none (public/product-experience wave; migration head stays `0014_opportunities`).
**Release candidate:** none. RC-P9-001 immutable; RC-P10-002 only at Wave 8.
**Paid/live calls:** 0.

Makes the public Ask4Mo experience accurately communicate the product built in Waves 1-6 and
convert an unfamiliar candidate into an informed, trusting user. The public story is now centred on
the **Opportunity** (Wave 6) - "prepare for a specific job in one place" - not a generic interview
generator. It refines the existing P8 marketing site (Home/Product/Pricing/Trust/Privacy/Terms/
AI-transparency/About); no new public routes were needed.

## Audit findings
- P8 already delivered the public IA, pricing presentation (no billing) and a rigorous claims audit
  (`p8_public_claims_audit.md`). The homepage/product story, however, **predated Waves 5-6**: it led
  with generic "prepare/practise/improve", used **emoji as feature icons**, marketed **Workspaces**
  as a primary feature, and **never mentioned Opportunity or Company Intelligence**.
- Pricing is authoritative in `lib/pricing.ts`: **Basic EUR 0** (real free registration) and
  **Premium EUR 19.99/mo (indicative)** as a **preview request** (`BILLING_ENABLED = false`; no
  checkout/cards). Preserved unchanged.
- One at-risk live claim: Premium "higher usage" was not enforced (BASIC already grants everything
  candidates use; Premium's only capability is a `premium_preview` stub). **Softened** to "a preview
  of upcoming premium capabilities as they are released."
- SEO gaps: `robots.ts` did not disallow the Wave 5/6 authenticated routes `/opportunities` and
  `/company`; root metadata used em dashes; no icons/OG image/structured data.

## Positioning
- Final positioning: **"Ask4Mo is a serious job-and-interview preparation workspace built around your
  specific Opportunity - your evidence, the company and realistic practice, together."**
- The **Opportunity** is the conceptual centre of the public story (hero, how-it-works, product page).
- Differentiation (grounded in implemented architecture): built around your job (not generic),
  evidence-aware and source-aware, you stay in control, honest about limits.
- Deliberately excluded (unsupported): outcome guarantees, "100%/bias-free", "GDPR compliant/
  certified", real-time company intelligence, unrestricted web browsing, employee-review aggregation,
  any testimonials/customer-counts/ratings.

## Public information architecture
- Public routes unchanged (coherent, no redundant pages): `/`, `/product`, `/pricing`, `/trust`,
  `/about`, `/privacy`, `/terms`, `/ai-transparency` (+ public `/help`, auth pages).
- Marketing nav (unchanged): Product, Pricing, Trust, About, Help + Sign in / Get started (or "Go to
  your workspace" when authenticated). Authenticated product nav (Wave 6) is untouched.
- Anonymous journey: marketing -> product/how-it-works -> pricing/trust -> register/sign in.
  Authenticated visitor on `/` stays on marketing (no RouteGuard) and sees the workspace link.

## Homepage
Rewritten (`MarketingHome.tsx`) with a conversion hierarchy: **Hero** (Opportunity-centred subtitle;
primary CTA Get started -> /register, secondary See how it works -> /product) -> **Trust strip** ->
**Problem -> Opportunity resolves it** -> **One connected system** (6 parts: Opportunity, Company
intelligence, Evidence, Prepare, Practice, Collaboration) -> **How it works** (6-step Opportunity
journey) -> **Why different** (4 grounded points) -> **Trust + Pricing teasers** -> **Final CTA**.
Emoji feature icons replaced with a restrained inline-SVG set (`MarketingIcon.tsx`, aria-hidden,
text always present). The hero H1 is preserved (contract).

## Product story
`ProductContent.tsx` explains Ask4Mo as ONE connected workflow: the six parts of an Opportunity, then
the 6-step journey (Opportunity -> company -> evidence -> Prepare -> Practice -> feedback). No
database/domain terminology. The Opportunity (private) vs Workspace (collaboration) distinction is
explicit; the Trust page adds the layered-context statement (account preferences != Opportunity
context != session choices != documents; long-term Memory only on approval).

## Trust
`TrustContent.tsx` extended with Wave 5/6 controls: **Your Opportunity is private**; **Company facts
stay separate from opinion** (facts vs review vs AI-suggestion; Glassdoor/Kununu **not integrated** -
link out, never copy/invent); **AI suggestions are not facts**; **Your evidence is governed**
(approved-only); **Layered context, not one memory**; **Your language, your market** (interface
language never changes the target market). Existing controls (isolation, private-by-default, sources/
abstention, approvals, no hiring decisions, no voice-trait inference, no audio storage, bounded
agents, export/delete, provider boundaries) retained. No certifications or absolutes.

## Pricing
Authoritative and unchanged: Basic EUR 0 (register) and Premium EUR 19.99/mo (indicative) preview
request; `BILLING_ENABLED = false`; no checkout/cards; "Privacy, security and data rights are always
free"; a visible no-billing note. Only the unenforced "higher usage" Premium line was softened.
Entitlement mapping (`authorization.py`): BASIC = current_market_research, standard_history,
standard_progress, standard_model_profiles; PREMIUM = BASIC + premium_preview (a demo stub). No usage
tiering is implemented; public copy reflects this. **No billing infrastructure was added.**

## Claims ledger (Wave 7 additions to the P8 audit)

| Claim | Surface | Status | Wording / limitation |
|---|---|---|---|
| Opportunity = one place for a specific job | Home/Product/Trust | IMPLEMENTED + DETERMINISTICALLY TESTED (Wave 6) | Private; not shared; distinct from workspace. |
| Company Intelligence from sources you can check | Home/Product/Trust | IMPLEMENTED + DETERMINISTICALLY TESTED (Wave 5) | Facts/review/AI-suggestion separated; live web fetch UNVALIDATED. |
| Glassdoor / Kununu / Google / LinkedIn | (not on marketing) | NOT INTEGRATED | Only stated as "not integrated" on Trust; never claimed as a source. |
| Evidence-aware preparation | Home/Product/Trust | IMPLEMENTED (Wave 4) | Approved evidence only; rejected/unreviewed excluded. |
| Premium plan | Pricing | IMPLEMENTED (presentation) | Preview request; no billing; only `premium_preview` cap exists. |
| Multilingual (7 locales) | Global | IMPLEMENTED; translations ENGINEERING DRAFT | "in your language", not "professionally translated". |
| Realtime voice | Product (voice) | SUPPORTED WITH LIMITATION | "available where configured"; live UNVALIDATED. |
| OCR for documents | (product) | SUPPORTED WITH LIMITATION | not perfect; live quality UNVALIDATED. |
| Outcome guarantees / 100% / bias-free / GDPR-certified | - | DO NOT CLAIM | absent; enforced by the evaluator. |

## Provider claim status
Official company web: implemented, **live UNVALIDATED**. Adzuna: adapter configured, **live
UNVALIDATED**. Glassdoor / Google / Kununu / LinkedIn: **NOT INTEGRATED** (link-out only; never
claimed on marketing). Voice/realtime: turn-based implemented; realtime "where configured", live
UNVALIDATED. OCR: implemented, live quality UNVALIDATED.

## i18n
New/updated marketing copy (10 changed + 29 new keys) localized across all 7 locales (EN/DE/FR/ES/IT/
PT/NL); parity enforced by `tsc`. Engineering-draft (no human/legal review). Language/geography/
session invariants preserved; the marketing-site language never changes career geography, conversation
language, dictation language or Opportunity/session context. Trust-card + legal bodies remain
English-only (carried limitation from P8).

## Accessibility
Semantic landmarks/headings; icons are decorative (aria-hidden) with text labels (never colour/icon
alone); keyboard-operable nav/CTAs; visible focus; mobile no-overflow at 390px (tested). No duplicate
accessible nav controls introduced.

## SEO
`robots.ts` now also disallows `/opportunities` and `/company`; `sitemap.ts` remains marketing-only;
per-page canonical retained; root metadata de-em-dashed and made Opportunity-aware; `metadata.icons`
and `openGraph.images` now derive from the canonical Ask4Mo mark (no new logo); truthful
**Organization JSON-LD** added on the home (no ratings/reviews/counts). hreflang alternates remain a
documented future item.

## Security / privacy
No backend change; every Waves 1-6 boundary preserved (owner scoping, admin metadata-only, document/
evidence governance, SSRF, provider boundaries, auth-route protection, Opportunity ownership,
Workspace separation, safe redirects). Public pages expose no candidate-private content, no storage
ids and no secrets. Privacy inventory unchanged (no new data).

## Evaluation
`scripts/eval_marketing_product_trust.py` - **32 invariants, PASS**, 0 paid/live (positioning, claims,
provider discipline, pricing, trust, Opportunity/Workspace distinction, i18n parity, no emoji/em-dash,
SEO, no fabricated social proof, no absolutes/hype).

## Regression
Frontend: unit, lint, typecheck, production build, full Playwright (see final report). Marketing E2E
extended (12 tests). Backend unchanged (no `src/` edit): backend suite/evaluators unaffected; existing
evaluators re-run green. Alembic head unchanged (`0014_opportunities`).

## Visual QA
Reviewed Home, Product, Pricing, Trust, About, AI-transparency, Privacy, Terms, sign-in/register
transition, 390px mobile nav, desktop nav, footer - hierarchy/spacing/CTA consistency/brand
consistency verified; no clipping/overflow; restrained icon set (no emoji).

## Known limitations
- Trust-card + legal page bodies are English-only (P8 carry-over); marketing chrome/home/pricing are
  localized.
- hreflang/`alternates.languages` not yet emitted (future SEO item).
- No OG raster image (SVG referenced); social cards may prefer a raster - future asset task.
- Premium is presentation-only; no billing and no enforced usage tiers (by design).
- Translations are engineering draft (no human/legal review).

## RC impact
No RC created. RC-P9-001 immutable; RC-P10-002 only at Wave 8. This wave changes public runtime copy/
markup only.

## Next recommended wave
**Wave 8** - integrated regression, second moderated pilot, consequential remediation and RC-P10-002.
