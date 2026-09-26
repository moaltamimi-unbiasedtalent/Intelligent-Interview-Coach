# P10B Wave 1 — Global Product Foundation: Brand + Navigation + Settings + Language Integrity

**Status:** DELIVERED (implementation complete, all frontend gates green).
**Branch:** `feature/capstone-p10b-founder-remediation` — **not merged**.
**Date:** 2026-09-26.
**Release candidate:** none created. RC-P9-001 (SHA `319759d`) remains the **immutable** release
candidate. RC-P10-002 is **not** created after Wave 1 — only after material P10B remediation is
complete and the full release gate is re-run (Wave 8).
**Paid/live calls:** 0 (no OpenRouter/Adzuna/OIDC/email/RAGAS/TTS/STT provider calls).
**Migration:** none (Alembic head unchanged, `0011_workspaces_shares`).

This wave resolves the founder's most visceral first-run findings: fragmented brand identity,
buried Settings, no visible language control, catalogue-parity-but-English rendering, an
AI-template feel (em dashes, emoji-as-logo), and a silent dictation control — without starting any
deferred work and without touching interview scoring semantics.

---

## 1. Baseline

- Prior release candidate: **RC-P9-001** (frozen, immutable).
- Branch baseline: P10B founder-feedback audit (commit `a597113`) — four audit/plan/IA/design docs,
  no runtime change.
- Backend: **untouched** in Wave 1 (0 files under `src/` changed). The backend suite is run purely
  as a regression sanity check.

## 2. Files changed

**New (5):**
- `frontend/components/ui/Logo.tsx` — the single canonical Ask4Mo brand lockup.
- `frontend/components/i18n/LanguageMenu.tsx` — the global language control (anonymous + authed).
- `frontend/components/settings/SettingsContent.tsx` — localized Settings chrome (client) so the
  server page keeps its metadata.
- `frontend/tests/wave1-foundation.test.tsx` — brand + language menu + dictation-hint unit tests.
- `frontend/tests/no-emdash.test.ts` — deterministic guard against em dashes in customer copy.

**Modified (23):**
- Brand/nav/shell: `components/layout/Brand.tsx`, `components/layout/AppShell.tsx`,
  `components/marketing/MarketingShell.tsx`, `components/auth/AccountMenu.tsx`.
- Settings: `app/settings/page.tsx` (server → renders `SettingsContent`).
- Auth i18n: `components/auth/{AccountPanel,RegisterForm,ForgotPasswordForm,ResetPasswordForm,VerifyEmailPanel}.tsx`.
- Dictation: `components/ui/DictationControl.tsx`.
- Copy: `components/marketing/TrustContent.tsx`, `app/{about,privacy,terms,ai-transparency}/page.tsx`.
- i18n catalogues: `lib/i18n/messages/{en,de,fr,es,it,pt,nl}.ts` (24 new keys × 7 locales).
- Tests updated: `tests/{auth,shell,brand}.test.tsx`, `e2e/{navigation,route-migration}.spec.ts`.
- Eval updated: `scripts/eval_dictation_experience.py` (two invariants re-pointed at the new
  spec-mandated behavior — see §13).

## 3. Brand

- **One identity.** `Logo.tsx` renders the existing vector mark `/brand/ask4mo-mark.svg` (`alt=""`,
  `aria-hidden`) beside the `Ask4Mo` wordmark, wrapped in an accessible `Link`
  (`aria-label="Ask4Mo - home"`, `data-testid="ask4mo-logo"`). No new logo was generated.
- **Emoji removed.** The marketing header's `🎯` logo is gone; `Brand.tsx` (app) and
  `MarketingShell.tsx` (marketing) both render `Logo`. No emoji (🎯📚🧠🚀) is used as a design asset.
- **Deferred (asset-production task, not Wave 1):** finalising favicon + OG image variants.

## 4. Navigation

- **`AccountMenu` is now an accessible dropdown** (`aria-haspopup="menu"`, `aria-expanded`,
  `aria-controls`, Escape + outside-click close, focus management, `role="menu"`/`menuitem`,
  44px targets). It exposes **Account**, **Settings**, and **Sign out** (for a real session).
  This ends the "Progress → Manage → Settings" path the founder hit.
- **Settings is discoverable** directly from the header account control on every authenticated page,
  desktop and mobile.
- **Mobile marketing nav** added to `MarketingShell` (the desktop nav is `md:`-only).

## 5. Settings

- `SettingsContent` (client) localizes the page chrome via `useT()` and **preserves every existing
  control**: `LanguageSettings` (three independent controls), `ResponseDetailPreference`,
  `MemoryManager`, plus a new "Your data" card linking to Account for privacy/data management.
- The four language dimensions stay **separate** and are explained in the UI: **Interface language**
  (`interface_locale`), **Mo conversation language** (`conversation_language`), **Dictation
  language** (device-local), and **career/labour-market geography** (unchanged, never coupled).
  No DB field was collapsed; no destructive coupling introduced.

## 6. Global language control

- `LanguageMenu` is an accessible dropdown (globe + current locale code; keyboard-navigable;
  `role="menuitemradio"` + `aria-checked`; labelled `t("common.language")`).
- Rendered in **both** the marketing header (anonymous visitors) **and** the authenticated app
  shell, desktop and mobile.
- Offers **all 7 locales** (EN/DE/FR/ES/IT/PT/NL) by native label and calls the existing
  `I18nProvider.setLocale`, so persistence follows the established architecture:
  **account → cookie → browser → English**. It changes only the interface language; it never
  alters career geography, conversation language, dictation language, or any other preference.

## 7. i18n rendering

Closed the "catalogue parity but English on screen" gap on the highest-visibility surfaces by
wiring hardcoded strings to `useT()`:
- **Account** (`AccountPanel`), **Settings** chrome, and the full **authentication** set
  (Register / Forgot / Reset / Verify).
- 24 new keys added to `en.ts` and translated into all 6 other locales; TypeScript's `Catalog`
  type enforces key parity across the 7 catalogues (`tsc --noEmit` clean).
- **Not translated (by design):** CV/JD/source/evidence and any user-authored content.

## 8. Practice language — **deferred to Wave 4** (spec item g)

Investigated and confirmed the interview module has **no `conversation_language` plumbing**:
`src/interview_service.py`, `src/evaluation_service.py`, `src/report_service.py`,
`src/application/interview_service.py`, and `src/api/schemas/interview.py` neither accept nor thread
a conversation language. Safe propagation requires a language directive across question generation,
evaluation, and report generation **without changing scoring semantics** — a multi-service backend
change outside Wave 1's no-migration/no-scoring envelope. Per the spec's explicit permission, this
is deferred to **Wave 4 scope item (c)**. Wave 1 makes **no** partial or unsafe change to interview
generation. (Recorded in `p10b_remediation_plan.md`.)

## 9. Dictation discoverability (pulled forward from Wave 2)

`DictationControl` previously returned `null` on unsupported browsers (e.g. Firefox) — silent.
It now renders an accessible fallback hint (`data-testid="dictation-unsupported"`, `role="note"`):
*"Dictation isn't available in this browser. You can type instead."* (localized;
`t("dictation.unsupported")`). Error/permission copy is also localized via an i18n key map. STT was
**not** rebuilt; the mic is **not** auto-opened; nothing auto-submits; STT is not destructively
coupled to the interface locale.

## 10. Accessibility

- Both new menus follow the established `MoreMenu` pattern: `aria-haspopup`/`aria-expanded`/
  `aria-controls`, `useId`, Escape + outside-click close, focus movement into the menu and back to
  the trigger, and ≥44px targets.
- The logo is a single labelled link; the mark is decorative (`aria-hidden`).
- The dictation fallback is a labelled `role="note"`, not a silent absence.

## 11. Security / authorization

- No authorization change. Normal users get **no** Admin visibility. Admin remains gated and
  CLI-bootstrapped.
- `AccountMenu` is purely presentational auth state; it grants nothing (authorization stays
  server-side). No new data exposure; no backend surface added.

## 12. Regression & quality gates

Frontend (`frontend/`):
- `npm run typecheck` — **pass** (7-locale `Catalog` parity enforced).
- `npx vitest run` — **263 passed / 48 files** (incl. new `wave1-foundation` + `no-emdash`,
  updated `auth`/`shell`/`brand`).
- `npm run lint` — **pass** (no ESLint warnings/errors).
- `npm run build` — **pass** (production build).
- `npx playwright test --project=chromium` — **104 passed** (incl. updated
  `navigation`/`route-migration` and existing i18n/voice/settings suites).

Backend (`src/`, untouched by Wave 1): `python -m pytest -q` — **2381 passed, 3 skipped, 0 failed /
0 errors** — identical to the RC-P9-001 baseline (the 3 skips are the RAGAS installed/absent guards).

Relevant deterministic evaluations (all offline, **0 paid/live calls**):

| Evaluation | Result |
|---|---|
| `eval_i18n_l10n.py` | PASS (all i18n/l10n invariants) |
| `eval_dictation_experience.py` | PASS (11/11 invariants) — see §13 |
| `eval_voice_experience.py` | PASS (all voice invariants) |
| `eval_realtime_voice.py` | PASS (all realtime-voice invariants) |
| `eval_agent.py` | PASS (gate) |
| `eval_security.py` | PASS (results written) |
| `eval_identity_platform.py` | PASS (all safety invariants = 1.0) |

## 13. Defects found & fixed (during Wave 1)

- **Silent dictation on unsupported browsers** → accessible fallback hint (F1, §9).
- **`AccountMenu` was a direct `/account` link** hiding Settings → accessible dropdown with
  Account + Settings + Sign out (§4).
- **Catalogue-parity-but-English** Account/Settings/auth → rendered localization (§7).
- **AI-template artefacts:** em dashes in customer copy → "-" with a deterministic guard; emoji logo
  → canonical vector lockup.

**Dictation eval alignment (not a weakening).** `eval_dictation_experience.py` had two invariants
that asserted the *old* behavior the founder spec required changing:
- `unsupported_fallback` asserted `if (!supported) return null` ("renders nothing"). Updated to
  assert the **new required** behavior: an accessible fallback note (`role="note"`,
  `data-testid="dictation-unsupported"`), no silent `return null`, typing still available. This is a
  **stronger** invariant (it forbids regressing back to silence), not a relaxed one.
- `permission_failure_isolation` asserted the hardcoded `ERROR_COPY`. Wave 1 localized that copy via
  an i18n key map (`ERROR_KEY` → `t()`). Updated to assert the same safety property (safe copy, no
  crash, text preserved) through the new localized mechanism. The property is unchanged; only the
  implementation token it checks moved.
No invariant was removed or softened; the eval now passes 11/11.

## 14. Known limitations

- Practice interview content remains in its generation language until **Wave 4** (§8).
- Human/legal **translation review of the 24 new keys is NOT done** — see §15.
- Favicon/OG asset finalisation deferred (asset-production task).
- Marketing site remains otherwise as-is (full marketing redesign is out of Wave 1 scope).

## 15. Localization status (honest)

- **ENGINEERING: IMPLEMENTED** — keys present across all 7 locales, rendered via `useT()`, parity
  enforced by the type system, guarded by tests.
- **HUMAN / LEGAL TRANSLATION REVIEW: NOT DONE** — the 24 new strings were produced without native
  linguist or legal review. Before any external launch, a human translation/legal pass is required
  (auth and privacy-adjacent copy especially).

## 16. Documentation

- This document.
- `p10b_remediation_plan.md` — added the "Wave 1 — DELIVERED" note and confirmed Practice-language
  ownership in Wave 4.

## 17. Next recommended wave

**Wave 3** (documents/upload reliability — the résumé-read defect) or **Wave 2** (premium first-run
onboarding). Wave 4 owns Practice-language propagation. No new RC until Wave 8's full gate.

## 18. Final verdict

Wave 1 is **complete and green**. The founder's first-run experience now has one Ask4Mo identity,
obvious Account/Settings access, an obvious and coherent language control across marketing and app,
rendered localization on the highest-visibility surfaces, a visible dictation fallback, and no
obvious AI-template artefacts — with **no** migration, **no** scoring change, **no** authorization
change, **0** paid/live calls, and **no** new release candidate.
