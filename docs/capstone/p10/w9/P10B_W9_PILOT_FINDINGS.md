# P10B-W9 — Pilot 2 Findings (Evidence & Classification)

Audit phase. No runtime code changed. Every row is mapped to current implementation with
file:line evidence, a root cause, a severity, reproducibility, and a proposed response wave.

**Classification legend:** `CONFIRMED DEFECT` (code proven against product intent) ·
`PROBABLE DEFECT` (strong evidence, live repro pending) · `UX FINDING` ·
`FEATURE REQUEST` · `VALIDATION GAP` (works but unvalidated / untested) ·
`ENV/TEST` (local environment or test artifact) · `NON-REPRODUCIBLE`.

**Severity:** P0 (blocks release) · P1 (must fix before resuming Pilot 2) · P2 (should fix in W9) ·
P3 (polish / later).

---

## 0. Participant evidence (as supplied)

Four participants (P01–P04 plus the P02.5 written return). Positive signals: users understood
Ask4Mo and its audience; Get Started clear; Prepare understandable; CV/Documents/Evidence clear;
Interview Practice positive where tested; liked simplicity/clarity/accessibility/saving/exporting;
completers finished without moderator help; one would pay €19.99/mo "if it keeps improving."

Verbatim issues used as primary evidence:
- Opportunity: *"No, did not go through." / "Not able to see the opportunity on the screen." /* request to make it visually prominent.
- Onboarding: *"needs a welcome screen … let's get started … the tour/guide should pop up … a more welcoming screen."*
- Server errors on Progress/History: *"Something went wrong" + "We couldn't connect right now. Please check your connection and try again."* and on Progress additionally *"Couldn't load practice progress."*
- Security: *"Security Lapse on certain menu items."*
- Trust: *"Yes, very clear but needs to be presented better."*
- Visual: logo more prominent; larger fonts; more colour impact; better graphics.
- Comparison: wants a feature+pricing comparison vs generic AI tools, AI coaches, and human coaches.
- Voice: *"Not Tested, but illustrated."*

---

## 1. Master findings register

| ID | Finding | Class | Sev | Repro | Root cause (evidence) | Affected surface | Wave |
|---|---|---|---|---|---|---|---|
| PF-01 | Unhandled server 500 shown to user as "check your connection" (blames the user's internet for a server bug) | CONFIRMED DEFECT | **P1** | Confirmed (code + PR #100 commit) | Base-`Exception` handler runs in Starlette `ServerErrorMiddleware`, *outside* `CORSMiddleware` → 500 lacks `Access-Control-Allow-Origin` → browser blocks it → `fetch` throws → frontend maps to `network`. `src/api/exception_handlers.py:115-133`, `src/api/main.py:106-118`, `frontend/lib/api/client.ts:126-134`, `frontend/lib/api/errors.ts:40-41` | Global API error path; Career Chat, Progress, History | W9.1 |
| PF-02 | CORS added conditionally; misconfigured origins mask *all* errors as network | CONFIRMED DEFECT | **P1** | Confirmed (code) | `if settings.frontend_origins:` — if unset, no response carries CORS. `src/api/main.py:107-115` | All authenticated pages under outage/misconfig | W9.1 |
| PF-03 | Progress page shows duplicate catastrophic errors ("Couldn't load practice progress." above "Something went wrong") | CONFIRMED DEFECT | **P2** | Confirmed | Two independent fetches, two error UIs stacked: `api.memory.list` + `api.progress.get`. `frontend/components/progress/ProgressClient.tsx:83,95`, `frontend/components/progress/PracticeProgress.tsx:22,37` | Progress | W9.2 |
| PF-04 | Progress, History, Reports, Practice, Sources, Evaluation, Agent Inspector, Prepare have no in-place Retry; recovery needs full reload | UX FINDING | **P2** | Confirmed | `ErrorState` `onRetry` omitted in 11/14 usages; some fetches inline in `useEffect`. `frontend/components/ui/States.tsx:59-89`; usages listed in RESILIENCE_AUDIT §4 | App-wide error states | W9.2 |
| PF-05 | Backend restart does not auto-recover the frontend (must reload); session itself survives | UX FINDING | **P2** | Confirmed (session survival PASS via `eval_restart_recovery`) | Fetch-once in `useEffect`, no refetch/focus-retry. Session is DB-backed (`src/persistence.py:347-357`, `src/auth_repository.py:493-505`), so no re-login needed | Progress, History, all app pages | W9.2 |
| PF-06 | X-Request-Id null exactly in server-fault/network cases (support can't get a reference) | UX FINDING | **P2** | Confirmed | Downstream of PF-01; `network` kind carries no id; blocked 500 body/header never reaches browser. `frontend/lib/api/client.ts:128-133`, `frontend/components/ui/States.tsx:81-87` | Error states | W9.1 |
| PF-07 | 401/403/404/422/429 all collapse to one "Please check the information" message | UX FINDING | **P2** | Confirmed | `kindForStatus` buckets all 4xx as `validation`. `frontend/lib/api/errors.ts:55-61` | Error states | W9.1 |
| PF-08 | No automatic bounded retry/backoff anywhere | VALIDATION GAP | **P2** | Confirmed | Not implemented (no retry loop, no `navigator.onLine`) | API client | W9.1 |
| PF-09 | "Review & Diagnostics" (`/review`) menu item shown to every authenticated user; two diagnostics endpoints unauthenticated | UX FINDING (info-disclosure, Low) | **P2** | Confirmed | `SECONDARY_NAV` rendered unconditionally (`frontend/components/layout/nav-items.ts:21`, `MoreMenu.tsx:103`); `src/api/routes/knowledge.py:20,56-59` and `src/api/routes/evaluation.py:20-31` have no auth dependency (aggregate engineering metadata only — no private data/secrets) | Nav / `/review/*` | W9.3 |
| PF-10 | Opportunity not discoverable — home funnels to Prepare, no Opportunity CTA on `/app` or return card; nav label muted/truncated | CONFIRMED DEFECT | **P1** | Confirmed | `HomeEntry` pushes `/prepare` for hero + both shortcuts (`frontend/components/coach/HomeEntry.tsx:26-34,53,56,59`); `ReturnJourney` has no `/opportunities` link (`frontend/components/home/ReturnJourney.tsx:109-128`); primary nav rendered `text-muted` (`frontend/components/layout/PrimaryNavigation.tsx:24-26`, `MobileNavigation.tsx:30-41`). List empty-state itself is good (`frontend/components/opportunities/OpportunitiesClient.tsx:83-93`) | Home, nav, onboarding | W9.4 |
| PF-11 | No post-onboarding welcome; the written "Mo is ready" completion screen is orphaned/unrendered | CONFIRMED DEFECT | **P1** | Confirmed | `finish()` → `router.replace("/app")` (`frontend/components/onboarding/OnboardingClient.tsx:95-97`); `onboarding.completeTitle/completeBody` exist in `frontend/lib/i18n/messages/en.ts:260-262` but are referenced nowhere | Onboarding → `/app` | W9.5 |
| PF-12 | Tutorial omits Opportunity; 4/12 steps highlight non-existent DOM targets; state is device-local only; entirely hardcoded English | CONFIRMED DEFECT | **P2** | Confirmed | `frontend/lib/tutorial/steps.ts:24-133` (no opportunity step; `practice-handoff/practice-answer/deep-dive/report` targets absent); `frontend/lib/tutorial/storage.ts:12,53-57` (localStorage only → cross-device replay); chrome literals `frontend/components/tutorial/TutorialController.tsx:119-200` | Tutorial | W9.5 |
| PF-13 | ~190 candidate-facing strings hardcoded in English across ~42 components (interface language does not fully switch the product) | CONFIRMED DEFECT | **P1** | Confirmed | No `useT()`/`translate()` in Prepare/Mo chrome, Interview/History, Progress, legal/trust bodies, `/app` cards, `lib/api/errors.ts` user messages, ~30 page metadata titles. Inventory in LOCALIZATION_AUDIT §3 | Product-wide | W9.6 |
| PF-14 | Russian (`ru`) is a new 8th product language; not yet present anywhere | FEATURE REQUEST | **P2** | N/A | 7-locale allowlists across frontend + backend (LOCALIZATION_AUDIT §1) | Product-wide | W9.7 |
| PF-15 | Privacy controls exist but are scattered; no selective delete for completed interview history; no unified "Your Data" view | UX FINDING / FEATURE REQUEST | **P2** | Confirmed | Per-class controls exist (memory/documents/opportunities/sessions/agent-runs/shares/feedback/export/delete) but across 4+ surfaces; `src/api/routes/history.py:19-31` has GET only. Inventory in PILOT_FINDINGS §3 / architecture audit | Settings, Account, /privacy | W9.8 |
| PF-16 | Trust page: 17 flat identical cards (no hierarchy) + hardcoded-English body | UX FINDING | **P2** | Confirmed | `frontend/components/marketing/TrustContent.tsx:11-29,49-56` (flat `<dl>`; only title/subtitle translated). Claims are supported (export/delete real: `src/api/routes/auth.py:435,487`) | `/trust` | W9.9 |
| PF-17 | Visual hierarchy: primary nav + broad body copy share one muted grey; mobile bottom-bar labels truncate without icons; weak CTA differentiation | UX FINDING | **P2** | Confirmed | `--muted` overused (`frontend/app/globals.css:11-64`; `PrimaryNavigation.tsx:24-26`, `MobileNavigation.tsx:30-41`); single-accent palette | App + marketing | W9.9 |
| PF-18 | No product/competitor comparison exists | FEATURE REQUEST | **P3** | N/A | Confirmed absent; only `frontend/lib/pricing.ts` plans | Marketing | W9.10 |
| PF-19 | Voice not genuinely tested by participants | VALIDATION GAP | **P2** | N/A | All voice is implemented + deterministically tested only; **not human-validated**; TTS `liveHumanQualityTested:false` (`frontend/lib/speech/ttsLocales.ts:49`). Russian voice unsupported today | Prepare, Practice | Pilot re-test (not a code wave) |
| PF-20 | Career Chat 500 (PR #100) — is it truly closed? | CONFIRMED DEFECT (fixed) | resolved | Confirmed fixed | `SourceOut.authority_level: int` now (`src/api/schemas/career.py:42`); regression `tests/test_career_chat_schema.py` (3 tests). Root cause was int→str mapping (`career.py:71-79` over `src/copilot/models.py:224`). Residual class (PF-01) still open | Career Chat | verify in W9.1 |
| PF-21 | Authority-level comment reversed vs canonical constants | CONFIRMED DEFECT (comment only) | **P3** | Confirmed | `src/api/schemas/career.py:37` says "1=industry .. 3=official"; canonical is **1=official … 3=industry** (`src/copilot/constants.py:307-311`, `src/copilot/knowledge/provenance.py:17-46`). Semantics correct; comment misleading. **Do not change semantics** | Career schema comment | W9.11 |
| PF-22 | Doc/prompt implies an "Evaluation Specialist"; only three specialists exist | DOC INCONSISTENCY | **P3** | Confirmed | Three bounded specialists (Role&Opportunity, Candidate Evidence, Interview Strategy) in `src/agent/specialists/registry.py:20-64`; evaluation is a separate deterministic service (`src/application/evaluation_service.py`). Stale "five Career tools" docstring at `src/agent/tools.py:603` (now six). Registry = 11 tools (verified). **Do not add an Evaluation Specialist** | Docs | W9.11 |

---

## 2. Separation into the requested buckets

- **Confirmed defects:** PF-01, PF-02, PF-03, PF-10, PF-11, PF-12, PF-13, PF-21 (comment), PF-20 (fixed; residual class PF-01).
- **Probable defects:** none outstanding — the P1/P2 items above are code-confirmed, not probabilistic. (PF-01's *live* browser reproduction was demonstrated in the prior Pilot 2 P0 investigation; the pilot screenshots are the human evidence.)
- **UX findings:** PF-04, PF-05, PF-06, PF-07, PF-09, PF-15, PF-16, PF-17.
- **Feature requests:** PF-14 (Russian), PF-18 (comparison), part of PF-15 (unified Data Center).
- **Validation gaps:** PF-08 (no retry), PF-19 (voice not human-validated).
- **Environment/test:** the 13 backend failures from `.env` `OPENROUTER_MODEL_*` overrides (see CURRENT_STATE §4) — not a product defect; W9.1/W9.12 will make the isolation intrinsic.
- **Non-reproducible:** none. The "security lapse" (PF-09) reproduced as route-visibility, not an authz break (SECURITY_AUDIT).

## 3. Privacy-control inventory (evidence for PF-15)

| Data class | Selective delete today | Route |
|---|---|---|
| Preparation Memory | yes (per item) | `DELETE /api/v1/memory/{id}` (`src/api/routes/memory.py:120-127`) |
| Documents (+derived evidence) | yes | `DELETE /documents/{id}` (`src/api/routes/documents.py:172-174`) |
| Stories | yes | `DELETE …/stories/{id}` (`documents.py:226-228`) |
| Opportunities | yes (history preserved via SET NULL) | `DELETE /api/v1/opportunities/{id}` (`src/api/routes/opportunity.py:119-128`) |
| In-progress interview session | yes (never touches history) | `DELETE /interviews/{session_id}` (`src/api/routes/interview.py:423-433`) |
| Completed history / reports | **no selective delete** (export only) | `src/api/routes/history.py:19-31`; export `documents.py:245-257` |
| Agent runs / checkpoints | yes (thread only) | `DELETE /agent/runs/{id}` (`src/api/routes/agent.py:182-199`) |
| Workspace share (revoke) | yes | `DELETE …/shares/{id}` (`src/api/routes/workspaces.py:137`) |
| Feedback | yes | `DELETE /api/v1/feedback` (`src/api/routes/feedback.py:52-60`) |
| Account export | yes | `GET /auth/account/export` (`src/api/routes/auth.py:435`) |
| Account deletion | yes (full cascade; audit anonymised, not deleted) | `POST /auth/account/delete` (`auth.py:487`) |

Integrity constraints a unified center must respect: history crash-safety keyed on
`interviews.source_session_id`; checkpoint deletion only via the saver's `delete_thread`;
audit records anonymised-not-deleted; Opportunity/Workspace SET-NULL cascades.
