# P10B — Remediation Plan (waves)

_Proposal only — no implementation in this phase. Sequenced so highest-leverage, lowest-risk,
no-migration fixes land first. Any implemented wave that changes runtime behaviour produces a new
release candidate (**RC-P10-002…**); RC-P9-001 (`319759d`) stays immutable and its evidence is
never attached to changed code. No security/privacy/HITL/ownership/evidence/i18n-safety/voice/
agent/workspace/admin boundary may be weakened. No paid/live provider calls; no public deploy._

Sequencing follows the founder's suggested waves, adjusted by evidence: the résumé defect and
i18n rendering are pulled early (real defects + highest leverage); Opportunity IA lands after the
integration waves that feed it.

Complexity: **S** (≤1 day) · **M** (2–4 days) · **L** (1–2 weeks) · **XL** (2+ weeks).

---

## Wave 1 — Brand consistency, global navigation, Settings & language integrity (no migration)
- **Objective:** one logo everywhere; a discoverable Settings/Account hub; a visible language
  switcher; fix the i18n *rendering* gap on the highest-visibility surfaces.
- **Scope:** (a) replace the marketing `🎯` with the canonical logo (`MarketingShell.tsx:30`
  → same asset as `Brand.tsx`); pick/finalise one `public/brand/*` asset + favicon + OG image.
  (b) Wire the dead `ACCOUNT_NAV` → add a **Settings** entry to `AccountMenu`; present Account &
  Settings coherently (D1/D2). (c) Add a **language switcher** to the app header + marketing
  chrome (reuse `I18nProvider.setLocale`) and a **mobile marketing nav** (B5). (d) Localize the
  hardcoded-but-catalogued surfaces: **AccountPanel** (`account` ns), **settings page chrome**
  (`settings` ns), **Register/Forgot/Reset/Verify** (`auth` ns), nav "More" descriptions — fixing
  the "Account/Settings stays English" bug (C1/C2). (e) Add an admin-discoverability note to docs
  (J1) — no authz change. (f) Em-dash → "-" copy pass in `en.ts` (A3).
- **Files:** `components/marketing/MarketingShell.tsx`, `components/layout/{Brand,AccountMenu,MoreMenu,nav-items}.tsx`, `components/auth/{AccountPanel,RegisterForm,ForgotPasswordForm,ResetPasswordForm,VerifyEmailPanel}.tsx`, `app/settings/page.tsx`, `components/i18n/*`, `lib/i18n/messages/*` (copy edits + any missing keys), `public/brand/*`.
- **Backend:** none. **Frontend:** medium. **Migration:** none. **i18n:** render existing keys (add a few missing ones for nav descriptions with parity across 7 locales). **Sec/privacy:** none (admin stays gated/CLI-bootstrapped).
- **Tests:** extend `tests/i18n.test.tsx` to assert **rendered** localization on AccountPanel/Settings/Register (not just parity — closes the C5 test gap); unit tests for the header language switcher; e2e: switch language → Account/Settings render translated; mobile marketing nav reachable.
- **Acceptance:** one logo across marketing+app; a "Settings" nav entry; anonymous + authed language switch changes Account/Settings/auth pages; no em dashes in customer copy; i18n test asserts rendering.
- **Dependencies:** none. **Risk:** low. **Complexity:** M.

## Wave 2 — Premium first-run onboarding & Mo configuration (likely migration)
- **Objective:** a premium first-run setup wizard that configures the product once.
- **Scope:** a guided wizard (interface language · target role · career geography · coaching
  style · Brief/Detailed · text-vs-voice default · dictation language · optional CV upload ·
  optional JD upload · short privacy/evidence explainer · intros to Prepare/Practice/Evidence/
  Company research). Reuse `LanguageSettings`, `ResponseDetailPreference`, `AgentPrepareWorkspace`
  role/JD, Documents upload, `api.auth.updatePreferences`. Keep **one coherent Mo identity** —
  "persona" = configurable **coaching style** (e.g. supportive/neutral/direct), not gimmick
  characters. Fix voice discoverability (F1): replace `DictationControl` silent-null with a
  disabled hint on unsupported browsers.
- **Files:** new `components/onboarding/*`, new `/app/onboarding` route or modal; `components/settings/*` (new coaching-style + geography + default-mode prefs); `components/ui/DictationControl.tsx`.
- **Backend:** add preference fields (coaching_style, career_geography, default_input_mode) to `UserPreference` + `updatePreferences` schema/validation; a "first_run_completed" flag. Ensure geography **never** changes labour-market geography rules (keep per-query separation) — it is a display/coaching hint only unless a product decision says otherwise.
- **Migration:** **likely** (new `user_preferences` columns; single head). **i18n:** all wizard copy across 7 locales, rendered. **Sec/privacy:** onboarding CV upload uses the existing owner-scoped pipeline; no new exposure.
- **Tests:** wizard unit + e2e (complete → prefs persisted → skippable → not shown again); preference persistence tests; DictationControl unsupported-hint test; migration up/down/single-head.
- **Acceptance:** new user gets a coherent first-run setup; preferences persist; coaching style applied to Mo; STT unsupported state is visible not silent.
- **Dependencies:** Wave 1 (settings hub). **Risk:** medium (migration + scope). **Complexity:** L.

## Wave 3 — Documents/JD/CV integration & upload reliability (defect fix; mostly no migration)
- **Objective:** fix the résumé read failure; make document type/state visible; a proper inventory.
- **Scope:** (a) **G1 defect:** handle scanned/image PDFs + images gracefully — either bundle an
  OCR path in the deployed image (install `[ocr]`) OR return a clear, actionable message
  ("This looks like a scanned/image PDF; enable OCR or upload a text-based PDF/DOCX") instead of a
  generic "Couldn't read this file", and rule out `MALWARE_SCAN_REQUIRED` misconfig (503). (b)
  **G3 display:** render `summary.category` (Résumé/CV vs JD) in the list — **no migration** (field
  exists). (c) **G4:** a document **inventory table** (type/category, file type, size, pages,
  version, upload date, processing state) from existing API fields. (d) Fix the inert hardcoded
  `category="cv"` in extraction (`documents_service.py:117`) to use the chosen category.
- **Files:** `src/documents/{parsing,ocr}.py`, `src/application/documents_service.py`, `src/api/routes/documents.py`, `deploy/*` (OCR extra), `frontend/components/documents/DocumentsClient.tsx`, `lib/i18n/messages/*`.
- **Backend:** medium (error paths, OCR availability, extraction category). **Frontend:** medium (table + category badges + localized statuses). **Migration:** **none** (category already migrated). **i18n:** table headers + error messages across 7 locales. **Sec/privacy:** keep documents untrusted DATA (never in prompts), keep malware fail-safe policy.
- **Tests:** backend: scanned-PDF/image → clear error (or OCR success if bundled), category persisted+returned, extraction uses category; frontend: inventory table renders category+state; e2e: upload résumé → classified as Résumé, status visible; regression on `eval_documents_evidence`.
- **Acceptance:** a real image/scanned résumé no longer shows a bare "Couldn't read this file"; the list shows document type + processing state; category drives display.
- **Dependencies:** none (can parallel Wave 1). **Risk:** medium (OCR packaging decision). **Complexity:** M.

## Wave 4 — Prepare/Practice journey integration (backend + frontend; maybe small migration)
- **Objective:** connect documents/evidence and JD/company context into Prepare **and** Practice;
  localize Practice content.
- **Scope:** (a) contextual **CV/JD upload from Prepare and Practice** (reuse `api.documents.upload`).
  (b) Surface **"use my CV evidence"** in Prepare and pass an evidence reference into Practice —
  extend `PreparationContext`/interview config with an owner-scoped evidence/document reference
  (reuse `EvidenceAccessService` + evidence specialist; do **not** put raw documents in prompts).
  (c) **C3:** apply a conversation-language directive to the **interview module** (question
  generation, evaluation, report) mirroring `response_language_directive` in the agent path, so
  Practice content honours the chosen language.
- **Files:** `src/integration/models.py` (add evidence/doc reference field; relax `extra="forbid"` deliberately), `src/api/schemas/interview.py`, `src/interview_service.py`/`src/evaluation_service.py`/`src/report_service.py` (+ `src/copilot/*` prompts) for the language directive, `frontend/components/agent/*` + `components/interview/*` (contextual upload + evidence panel).
- **Backend:** large. **Frontend:** medium. **Migration:** maybe small (if evidence link persisted). **i18n:** ensure interview prompts request the chosen language; localize Prepare/Practice UI chrome (part of the broader render pass). **Sec/privacy:** evidence stays owner-scoped + approved-only; no raw-document prompt injection.
- **Tests:** backend: interview content generated in DE when conversation_language=de; evidence reference owner-scoped + rejects foreign ids; frontend: contextual upload; e2e: Prepare→Practice with CV evidence; regression on agent/interview evals.
- **Acceptance:** a candidate can upload/reference their CV+JD from Prepare/Practice; Practice questions/feedback appear in the chosen language; evidence flows without weakening provenance.
- **Dependencies:** Wave 3 (documents). **Risk:** medium-high (touches interview generation). **Complexity:** L.

## Wave 5 — Company intelligence (surface existing backend; assess providers; no scraping)
- **Objective:** a directable candidate-facing company-research experience over the existing
  `src/copilot/research/*` backend.
- **Scope:** a **Company Research** UI where the candidate enters **company name + location** and
  requests a report; render the existing `CurrentMarketResearchResult` with strict
  **FACT / REVIEW-SENTIMENT / SOURCE / MODEL-INFERENCE** separation and provenance. Keep it gated
  by the per-run capability + operator pause + env flags. **Do NOT** integrate Glassdoor/Kununu/
  Google/scraping — instead produce a **provider feasibility assessment** (API availability,
  licensing, ToS, cost) as a precondition. Adzuna live remains UNVALIDATED (DE search verified).
- **Files:** new `frontend/components/company/*` + route (or an Opportunity sub-tab in Wave 6); `src/api/routes/*` (a bounded company-research endpoint if a direct call is preferred over an agent turn); reuse `src/copilot/research/*`.
- **Backend:** medium (a directable endpoint over the existing service; keep SSRF/robots/content guards). **Frontend:** medium. **Migration:** maybe (cache/opportunity link). **i18n:** report labels across 7 locales. **Sec/privacy:** keep SSRF guards, untrusted-DATA handling, source separation; no new scraping.
- **Tests:** deterministic company-research eval (bounded params, source-category separation, no-fabrication); e2e with a fake provider; explicit "live Adzuna NOT RUN" status.
- **Acceptance:** a candidate can request company research by name+location and see fact/review/
  source/inference-separated results with provenance; provider-integration feasibility documented.
- **Dependencies:** none for the deterministic surface; live sources gated on the feasibility
  assessment. **Risk:** medium (external validity). **Complexity:** L.

## Wave 6 — Opportunity vs Workspace information architecture (new model + additive migration)
- **Objective:** introduce **Opportunity** (a candidate's private prep space for one role/company)
  and reframe **Workspace** as collaboration/sharing only.
- **Scope:** a new owner-scoped `opportunity` grouping linking existing interviews, documents,
  claims/stories, JD/company context; **My Home** lists Opportunities; each Opportunity hosts JD ·
  Company Research · CV & Evidence · Prepare · Practice · Report · Progress (per the IA proposal).
  **Additive** migration (existing standalone sessions/documents stay valid; grouping optional).
  Reword Workspace purpose/empty-state so the two concepts are distinct; **do not rename/migrate**
  Workspace data. Preserve all current deep links (compat redirects).
- **Files:** new `opportunity` model + Alembic migration; `src/application/*` opportunity service; new `frontend/app/app` opportunities UI; `components/workspaces/*` copy; `lib/auth/routes.ts`.
- **Backend:** large. **Frontend:** large. **Migration:** **yes (additive, single head)**. **i18n:** all new copy across 7 locales. **Sec/privacy:** Opportunity is owner-scoped grouping only — grants no cross-user access; Workspace sharing invariants unchanged.
- **Tests:** opportunity CRUD owner-scoped isolation; migration up/down/single-head; existing standalone flows still work; e2e for the new journey; workspace behaviour unchanged.
- **Acceptance:** a candidate can create an Opportunity and see all prep for one role/company in one place; Workspace clearly reads as collaboration; nothing existing breaks.
- **Dependencies:** Waves 3–5 (feeds the Opportunity tabs). **Risk:** high (new core concept). **Complexity:** XL.

## Wave 7 — Marketing / Product / Trust / About / Pricing redesign (+ commercial model)
- **Objective:** a premium public site with real visuals, a founder section, a pricing comparison,
  and an honest commercial model.
- **Scope:** implement the design direction (icons, imagery/screenshots, Trust architecture
  diagram, premium layout); **Product** page with product visuals; **Trust** page that explains the
  architecture visually; **About** with a genuine Founder section **grounded in Mo Al-Tamimi's
  public professional profile** (do not invent bio); **Pricing** Basic-vs-Premium **comparison
  table**. Reconcile the commercial model (K): define which capabilities are truly Basic vs Premium
  and (optionally) usage quotas, then make marketing claims match enforced entitlements (fix
  "higher usage"/"premium previews" overstatement). Billing remains OUT (no checkout).
- **Files:** `components/marketing/*`, `lib/pricing.ts`, `src/application/authorization.py` (+ enforcement if quotas added), `lib/i18n/messages/*`, `public/*` assets.
- **Backend:** small-medium (if entitlements/quotas enforced). **Frontend:** large. **Migration:** maybe (usage counters). **i18n:** all marketing copy across 7 locales, rendered. **Sec/privacy:** entitlement checks server-authoritative; no dark patterns.
- **Tests:** claims-audit regression (marketing matches enforced capabilities); pricing comparison a11y; entitlement-gating tests if quotas added.
- **Acceptance:** public site reads as premium; About has a real (sourced) founder section; Pricing shows a truthful comparison; no claim outruns enforcement.
- **Dependencies:** Waves 1 (brand) + K decision. **Risk:** medium. **Complexity:** L.

## Wave 8 — Integrated regression, human UX validation & RC creation
- **Objective:** verify the whole remediated product and cut the next release candidate.
- **Scope:** full release gate (backend/pytest, frontend unit, Playwright, ruff/compileall/lint/
  typecheck/build, OpenAPI, Alembic single-head, secret scan, all evaluators incl. new ones);
  a11y + 7-language layout pass; re-run the P8 claims audit; a **second moderated pilot** (reuse
  the P10A kit) on the remediated build; assign **RC-P10-002** with a version manifest.
- **Files:** `docs/capstone/*`, `artifacts/capstone/p10/RC-P10-002/*`, CI.
- **Backend/Frontend:** verification only. **Migration:** validate heads. **i18n:** rendered-coverage check. **Sec/privacy:** full security-integration suite.
- **Tests:** the entire gate + new-wave regressions green; 0 P0/P1 defects.
- **Acceptance:** all gates green; pilot lessons captured; **RC-P10-002** declared.
- **Dependencies:** Waves 1–7. **Risk:** low-medium. **Complexity:** M.

---

## Cross-wave notes
- **Migrations likely:** Wave 2 (preferences: coaching_style/geography/default_mode + first_run
  flag), Wave 6 (opportunity model), possibly Wave 4 (evidence link) and Wave 7 (usage counters).
  Wave 3 document classification needs **none**.
- **RC discipline:** the first wave that changes runtime → **RC-P10-002**; subsequent material
  changes bump the RC; never attach RC-P9-001 evidence to changed code.
- **Recommended first implementation wave: Wave 1** (highest leverage, lowest risk, no migration):
  logo consistency + Settings/nav + language switcher + i18n rendering of Account/Settings/auth,
  which directly resolves the founder's most visceral findings (buried settings, "Account Settings
  stays English", inconsistent logo) with minimal risk.
- **External validation required before building:** Wave 5 live employer sources (provider API/
  licensing/ToS/cost) and any live realtime/Adzuna/RAGAS/OIDC/email — none authorized here.
