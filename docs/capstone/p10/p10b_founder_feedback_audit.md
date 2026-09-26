# P10B — Founder Pilot Findings: Evidence-Based Audit

_Capstone P10B. An evidence-based repository audit of the founder's first hands-on product
review. **No product code changed** — this is analysis only. RC-P9-001 (`319759d`) remains
immutable; any implemented remediation later produces a new RC (RC-P10-002…)._

Baseline: main `d4329e2` (P10A merged, PR #86); Alembic head `0011_workspaces_shares`; branch
`feature/capstone-p10b-founder-remediation`. Evidence gathered via five read-only sub-audits
(brand/website, i18n, documents, company-research/workspaces/admin, settings/onboarding/voice/
commercial); all file:line references verified against the current tree.

Classification vocabulary: **DEFECT · UX/DISCOVERABILITY · INCOMPLETE IMPLEMENTATION ·
MISSING CAPABILITY · DESIGN/BRAND · PRODUCT DECISION · EXTERNAL VALIDATION REQUIRED.**
Severity: P0–P3 (defects) / U1–U4 (usability/product).

---

## Headline reality (what's actually true)
- **Most founder findings are UX/discoverability + design/brand + rendering gaps, NOT missing
  backends.** Company research, evidence bank, document classification, per-operation model
  policy, workspaces and admin are all *built*; they are hidden, un-surfaced, or un-rendered.
- **Two genuine defects:** (D1) résumé upload "Couldn't read this file" for scanned/image PDFs
  because OCR is an uninstalled optional extra; (D2) the i18n *rendering* gap — most signed-in
  surfaces are hardcoded English although catalogues are fully translated.
- **One dead-config bug:** `ACCOUNT_NAV` (→`/settings`) is declared but never used, so there is
  no "Settings" entry in the nav at all.
- **No security/privacy/HITL/ownership boundary is weakened by any finding** — and none of the
  proposed remediation requires weakening them.

---

## Finding matrix

Columns: **Observed → Expected · Evidence · Class · Severity · Root cause · Reuse? · Product
change? · Migration? · Sec/Privacy · Wave.**

### A. Brand / design
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | Marketing logo is a `🎯` emoji; app logo is the vector mark → one canonical logo | `MarketingShell.tsx:30` (🎯) vs `Brand.tsx:24` (`/brand/ask4mo-mark.svg`); stacked lockups unused; all 3 assets labelled "NOT the final logo" | DESIGN/BRAND | U2 | placeholder assets + inconsistent usage | logo assets | Y | N | none | 1 |
| A2 | Emoji as product/marketing iconography (📚🧠🎤🔒🗣️🤝) → professional icon set | `MarketingHome.tsx:9-14`; voice controls `RealtimeVoiceControl.tsx:79`, `DictationControl.tsx:105`, `VoicePlaybackControl.tsx:71`; no icon system | DESIGN/BRAND | U2 | no icon library | design tokens | Y | N | none | 1/7 |
| A3 | Em dash "—" in customer copy → prefer "-" | `en.ts` 17 lines; `TrustContent.tsx:11`; legal banners | DESIGN/BRAND | U4 | style tic | i18n catalogues | Y | N | none | 1/7 |
| A4 | UX/site doesn't feel premium; no imagery/illustration/screenshots/OG/favicon | no `next/image`, no raster assets, no `openGraph.images` (`app/layout.tsx:25-30`) | DESIGN/BRAND | U2 | text-on-boxes design | design system | Y | N | none | 7 |

### B. Public website
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | Product page dull/text-only | `ProductContent.tsx:16-30` (title+6 paragraphs) | DESIGN/BRAND | U2 | plain layout | marketing i18n | Y | N | none | 7 |
| B2 | Trust page doesn't explain architecture | `TrustContent.tsx:10-22` (hardcoded `<dl>`, no diagram) | UX + DESIGN | U2 | no visuals | trust facts | Y | N | none | 7 |
| B3 | About lacks a genuine Founder section | `app/about/page.tsx` (product-only, no founder) — **do not invent bio; ground in Mo Al-Tamimi's public profile later** | MISSING (content) | U3 | not built | — | Y | N | none | 7 |
| B4 | Pricing has 2 cards, no Basic-vs-Premium comparison | `PricingContent.tsx:16-42`; one-line `includes` per plan | UX + PRODUCT | U2 | no matrix; entitlements thin (K) | pricing.ts | Y | N | none | 7 (dep K) |
| B5 | No mobile marketing nav; no anonymous language switcher | `MarketingShell.tsx:33` (`hidden md:flex`, no hamburger); no locale control | UX/DISCOVERABILITY | U2 | missing components | I18nProvider | Y | N | none | 1/7 |

### C. Internationalization (major finding)
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Product feels English-only despite 7 locales → app renders in chosen language | plumbing/catalogues/persistence real (`catalog.ts:39`, `I18nProvider.tsx:69-84`) but only **25/123** `.tsx` use `useT`; Account/Settings-chrome/Prepare/Practice/Progress/Memory/Register hardcoded | DEFECT (rendering) | **P2** (U1 impact) | catalogued ≠ rendered | full `account`/`settings`/etc namespaces already translated | Y | N | none | 1 (+3/4 for deep pages) |
| C2 | Changing language localizes nav but "Account/Settings" stays English | `AccountMenu.tsx:53` localizes `nav.account`, but `AccountPanel.tsx:53` `<h1>Your account</h1>` + `app/settings/page.tsx:12` `eyebrow="Account" title="Settings"` hardcoded (keys exist) | DEFECT | P2 | pages never wired to `useT` | `account`/`settings` ns | Y | N | none | 1 |
| C3 | Practice content itself is English regardless of conversation language | agent path applies `response_language_directive` (`policies.py:108`, `nodes.py:74`) but interview module (`interview_service`/`evaluation_service`/`report_service`) has no directive | INCOMPLETE | U2 | directive only in agent path | agent directive pattern | Y | Y (backend) | none | 4 |
| C4 | Language selector buried (Progress→Manage→Settings) | selector only in `LanguageSettings.tsx`; no header/marketing control | UX/DISCOVERABILITY | U2 | no signpost | LanguageSettings | Y | Y | none | 1 |
| C5 | Human/translation quality unvalidated | catalogues self-labelled ENGINEERING DRAFT (`en.ts:5`); tests assert parity only (`i18n.test.tsx:21`) | EXTERNAL VALIDATION | U3 | no human review | — | N | N | none | 8/launch |

### D. Settings / profile
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | No "Settings" in nav; reachable only via Account/Progress "Manage" | `nav-items.ts:23` `ACCOUNT_NAV` declared but **never imported (dead)**; avatar→`/account` (`AccountMenu.tsx:56`) | DEFECT (dead config) | P3 (U2 impact) | ACCOUNT_NAV unused | ACCOUNT_NAV | Y | Y | none | 1 |
| D2 | Profile/Account/Settings/Language/preferences scattered | Settings=Language+ResponseDetail+Memory+data; Account=export/delete/plan; no unified hub | UX/IA | U2 | fragmented IA | existing panels | Y | Y | none | 1 |

### E. First-run onboarding / Mo setup
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 | No premium first-run setup | only a 12-step read-only tour (`TutorialController.tsx`, `steps.ts:22-95`); no wizard | MISSING CAPABILITY | U2 | not built | LanguageSettings/ResponseDetail/AgentPrepare/Documents/`updatePreferences` | Y | Y | maybe (prefs) | 2 |
| E2 | No coaching-style/persona preference | `ResponseDetailPreference.tsx:8` "distinct from any future personality/tone"; `interviewer_persona` exists only as mock-interviewer demeanor (Streamlit + unsurfaced field `types.ts:238`) | MISSING + PRODUCT DECISION | U3 | not built; keep ONE Mo identity (style, not gimmick characters) | interviewer_persona enum | Y | Y | likely (pref column) | 2 |
| E3 | No geography / default text-voice preference | geography derived per-query (CLAUDE.md); no user geo setting; voice default implicit | MISSING | U3 | not built | — | Y | Y | likely | 2 |

### F. Voice / dictation
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 | Couldn't discover STT in normal use | `DictationControl` mounts in every Composer footer when supported (`Composer.tsx:40,81`) but `if(!supported) return null` (`DictationControl.tsx:83`); STT = Web Speech (`browserAdapter.ts:36-66`), absent in Firefox | UX/DISCOVERABILITY | U2 | silent null on unsupported browser (not hidden, not key-gated) | error-copy path exists | Y | Y (show disabled hint) | none | (later; note in 2/4) |
| F2 | Realtime voice absent | gated `capabilities.realtime_voice_enabled=false` without key (`PracticeClient.tsx:68`, `useCapabilities.ts:18`) | INCOMPLETE + EXTERNAL VALIDATION | U3 | no realtime key (EX-02 live NOT RUN) | realtime adapter | N | N | none | later/live |

### G. Documents / CV / JD
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | "Couldn't read the file" on résumé | scanned/image PDF + PNG/JPG route to OCR (`parsing.py:120-125`→`ocr.py:87-90`); `[ocr]` extra uninstalled (`pyproject.toml:65`) → `DOC_STATUS_FAILED` (`en.ts:198`) | DEFECT | **P1** | OCR optional + poor error UX | validation/parse pipeline | Y | Y | none | 3 |
| G2 | Upload isolated from Prepare/Practice | only `/documents` (`DocumentsClient.tsx:126`); no upload in Prepare/Practice | UX/IA | U2 | silo | api.documents.upload | Y | Y | none | 3/4 |
| G3 | Résumé not visibly classified | category IS in schema+select+API (`persistence.py:114-122,436`; `DocumentsClient.tsx:23,85`) but list never renders `summary.category` (`DocumentsClient.tsx:163-189`) | DEFECT (display) | P3 | display gap — **no migration** | category field | Y | Y | **none** | 3 |
| G4 | No inventory/table (type/category/state) | card `<ul>` + single badge; API returns category/size/pages/version/date unused | UX | U2 | no table UI | schemas/documents | Y | Y | none | 3 |
| G5 | Documents don't feed Prepare/Practice | `PreparationContext` (`integration/models.py:31`, `extra="forbid"`) + interview config carry free-text only; only optional `FindCandidateEvidence` tool path | INCOMPLETE | U2 | no evidence field in handoff | `EvidenceAccessService`, evidence specialist | Y | Y | maybe (context field) | 4 |

### H. Company research
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 | Expected company research, couldn't find it | full backend `src/copilot/research/*` (5 intents incl. `COMPANY_CONTEXT`); only reachable via a Mo toggle (`AgentPrepareWorkspace.tsx:369-382`), not directable; rich form only in legacy Streamlit (`src/career/ui.py:223`, `src/copilot/company/*`) | INCOMPLETE (undiscoverable) | U2 | no candidate-facing directable UI in Next.js | research service + company provider | Y | Y | maybe | 5 |
| H2 | Live employer sources (Glassdoor/Kununu/etc.) | not built; Adzuna live UNVALIDATED (DE search VERIFIED only, `adzuna_provider.py:63-68`); web fetch has SSRF/robots guards | EXTERNAL VALIDATION REQUIRED | — | provider API/ToS/licensing feasibility unassessed | — | N | N | **do NOT integrate** | 5 (assess only) |

### I. Workspaces
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| I1 | Founder doesn't understand Workspaces | pure collaboration/sharing (VIEW-only report+story; `persistence.py:169-175`); empty state "You are not in any workspace yet" (`en.ts`); no candidate use case | UX + PRODUCT DECISION | U2 | concept mismatch | workspace model | Y | N (audit) | N | 6 |
| I2 | No "Opportunity" (per-role/company prep space) | grep "opportunity" → only the specialist/marketing; none as a prep space | MISSING CAPABILITY / PRODUCT DECISION | U2 | not modelled | interview/prep artifacts | Y | Y (later) | **likely (new model)** | 6 |

### J. Admin
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| J1 | Couldn't find admin | link only in `MoreMenu.tsx:124-136` gated on `platform_role`; becoming admin only via `scripts/bootstrap_admin.py` (by design; no API/self-service) | UX/DISCOVERABILITY (by design) | U3 | admin is CLI-bootstrapped, invisible until you are one | bootstrap CLI | N (do not weaken authz) | doc only | none | 1 (docs) |

### K. Commercial model
| # | Observed → Expected | Evidence | Class | Sev | Root cause | Reuse | Change | Migr | Sec | Wave |
|---|---|---|---|---|---|---|---|---|---|---|
| K1 | Premium enforces almost nothing | only `PREMIUM_PREVIEW` differs (`authorization.py:66-79`), gated on one demo endpoint (`auth.py:293`); no usage quotas (only IP rate limit) | INCOMPLETE + PRODUCT DECISION | U2 | entitlements are marketing-forward | Capability/entitlement model | Y | Y (later) | maybe (quota counters) | 7 (dep for B4) |
| K2 | Marketing overstates ("higher usage", "premium previews") | `en.ts:385`; nothing enforces higher usage | DEFECT (claims) | P3 | claim outruns evidence | claims audit | Y | Y | none | 7 |

---

## Cross-cutting conclusions
- **The product is more built than it looks.** The dominant problem is **surfacing + rendering +
  brand**, not missing engines. Highest leverage: i18n rendering (C1/C2), a real settings/nav IA
  (D1/D2), the résumé OCR defect (G1), document classification display (G3), and directable
  company research (H1) — all reuse existing backends.
- **Two real defects to schedule:** G1 (P1, résumé read failure) and C1/C2 (P2, i18n rendering).
- **Do not weaken** any security/privacy/HITL/ownership/i18n-safety/voice/agent/evidence/
  workspace/admin boundary. Admin (J1) stays authz-gated + CLI-bootstrapped; company research
  keeps FACT/REVIEW/SOURCE/MODEL-INFERENCE separation and provider-ToS assessment (H2).
- **Migrations likely** only for: coaching-style/geography/text-voice preferences (E2/E3), an
  Opportunity model (I2), optional usage counters (K1). Document classification (G3) needs **no**
  migration.
