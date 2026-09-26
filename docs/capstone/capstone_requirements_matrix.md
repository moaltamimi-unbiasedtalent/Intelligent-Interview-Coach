# Ask4Mo Capstone — Canonical Requirements Matrix

One reconciled inventory across the v3 controlling plan, the reference package, and verified code.
Status: DELIVERED / PARTIAL / ABSENT / UNVALIDATED / BLOCKED / OUT_OF_SCOPE. Stable IDs map to the
reference package's A/B/C/K IDs and the D1–D9 platform additions; groups A–L organise them for the
Capstone. Acceptance gates reference AC-01–25 (`reference/03_Release_Acceptance_Checklist.md`) and
EX-01–16 (`reference/02_Expanded_Acceptance_Checklist.md`).

## Group A — Core product (carry-forward + gaps)
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| A1 | History detail + report | DELIVERED (P2 re-verified under real accounts) | Preserve, account-scope | P2 | AC-04 |
| A2 | Active-session discovery/resume | DELIVERED (P2) — return-journey card resumes owned sessions | Discoverable owned unfinished sessions | P2 | AC-05 |
| A3 | Progress metrics | DELIVERED (P2 continuity verified; trend deferred, documented) | Preserve | P2 | AC-06 |
| A4 | Sources catalogue + links | DELIVERED (P2 evidence stays discoverable behind disclosure) | Preserve | P2 | AC-07 |
| A5 | Knowledge readiness distinction | PARTIAL | Distinguish catalogue/snapshot/live | P2/P6 | AC-07 |
| A6 | Owned recent agent-run list | ABSENT | Owned run discovery | P6 | AC-18 |
| A7 | Evaluation evidence UI | DELIVERED (data env-dep) | Correct artifact provenance | P6 | AC-18 |
| A8 | Retrieval/RAG diagnostics | PARTIAL (overview only) | Selected-run evidence | P6 | AC-18/22 |
| A9 | Report export + completed-history deletion | DELIVERED (P4) — MD/JSON export (owner-scoped) + existing confirmed deletion; PDF optional | MD/JSON export + confirmed deletion (PDF optional) | P4 | EX-01 |

## Group B — Agent / orchestration
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B-agent | ReAct/goal-based bounded agent | DELIVERED | Preserve | — | AC-15/16 |
| B-tools | 6 career + 2 HITL tools, allowlist | DELIVERED | Preserve; add specialist tools | P5 | AC-15 |
| C4 | Preparation + Evaluation specialists (multi-agent) | ABSENT | Bounded orchestrator/specialist | P5 | EX-05 |
| B8 | Mo coordinates Research/Candidate specialists | PARTIAL | Bounded delegation | P5 | AC-15/16 |

## Group C — Knowledge / RAG
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| C-rag | Governed agentic RAG | DELIVERED | Preserve | — | AC-07/22 |
| K1 | Germany occupation compensation | DELIVERED (P6) — bounded reviewed dataset + abstention (figures engineering-draft) | Bounded reviewed dataset | P6/E6 | EX-13 |
| K2 | Credentials / regulated professions | DELIVERED (P6) — declared profession/jurisdiction matrix + abstention | Declared jurisdiction matrix | P6/E6 | EX-14 |
| K3 | Emerging roles / aliases | DELIVERED (P6) — versioned aliases (confident matches only) | Versioned aliases | P6/E6 | EX-15 |
| K4 | Additional Adzuna capabilities | DELIVERED (P6) — bounded op spec + validation; live UNVALIDATED/cost-gated | Entitled ops as bounded tools | P6/E6 | EX-16 |

## Group D — Platform productisation (owner-added)
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| D1 | Admin Console | DELIVERED (P6.5) — bounded PLATFORM_ADMIN ops console (metadata only; audited; no data superuser) | Bounded PLATFORM_ADMIN control plane | P1 foundation → P6.5 | new AC (admin authz) |
| D2 | Platform roles / RBAC | DELIVERED (P1) — USER/PLATFORM_ADMIN, audited bootstrap | USER / PLATFORM_ADMIN | P1 | AC-02 ext |
| D3 | Basic/Premium entitlement model | DELIVERED (P1) — persisted tier + capability map | Entitlement dimension (no billing) | P1 | new EX (entitlement) |
| D4 | Server-side entitlement enforcement | DELIVERED (P1) — `require_capability`, negative tests | Enforced at API/service | P1→P6 | new EX |
| D5 | User privacy/data controls | DELIVERED (P8) — coherent data-rights hub (export + manage Memory/documents/sharing) + full application-controlled deletion cascade | Export/delete/consent self-service | P1/P4/P6/P8 | EX-01, privacy |
| D6 | Privacy/legal public surfaces | DELIVERED (P8, engineering draft) — Privacy, Terms, AI-transparency, Trust pages with legal-review banners | Policy/terms/AI-transparency pages | P8 | AC-25 (legal review required) |
| D7 | Public marketing website | DELIVERED (P8) — public `/` marketing site (Home/Product/Pricing/Trust/About) + marketing chrome; app moved to `/app` | Public front door | P8 | AC-25 |
| D8 | Public/authenticated route separation | DELIVERED (P1, strengthened P8) — server fail-closed + client RouteGuard; marketing `/` vs product `/app` | Route boundary | P1/P8 | AC-01/19 |
| D9 | Pricing/product presentation | DELIVERED (P8) — Basic/Premium presentation, centralized config, truthful CTAs; NO billing/checkout | Basic/Premium presentation | P8 | AC-25 |

## Group E — Identity / collaboration
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B1 | Registration + verified login + logout/expiry | DELIVERED (P1) — accounts, sessions, verify, recovery | Real backend-verified accounts | P1 | AC-01/03 |
| C6 | Social + email auth, recovery | DELIVERED (P1); Google live = UNVALIDATED | One social + email verify + recovery | P1 | EX-07 |
| C5 | Teams/workspaces + roles + invitations | DELIVERED (P6.5) — workspaces/memberships (OWNER/MEMBER)/hashed single-use invitations | Bounded workspace model | P6.5 | EX-06 |
| P/share | Explicit resource sharing + revocation | DELIVERED (P6.5) — allow-listed VIEW share grants, immediate revocation, deletion invalidation | Selected-resource shares | P6.5 | EX-06 |

## Group F — Candidate data / documents
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B4 | Private document library (PDF/DOCX/TXT) | DELIVERED (P4) — upload + validate + parse + review + delete | Upload + extract + review + index | P4 | AC-08/09/10 |
| C2 | OCR (scanned PDF/images) | DELIVERED (P4) — bounded engine abstraction + provenance; live UNVALIDATED | Bounded OCR worker, provenance | P4/E2 | EX-03 |
| C7 | Evidence/story bank | DELIVERED (P4/E3) — deterministic, provenance-backed, revocation-aware | Source-backed STAR drafts | P3/E3 | EX-08 |
| B2–B3 | Profile + opportunities | PARTIAL | Durable scoped context | P1/P6 | AC-03/17 |

## Group G — Interview Practice
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| G-practice | Durable Practice + evaluation + report | DELIVERED | Preserve | — | AC-04/17 |
| B6–B7 | Recorded/spoken answers + spoken questions | DELIVERED (P7/E5) — turn-based voice (see Group H); text-only evaluation preserved | Spoken Qs + spoken answers | P7 | AC-13/14 |

## Group H — Speech / multimodal
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B5 | App-wide dictation | DELIVERED (P3, reused by P7 voice) | Every eligible input, editable transcript, no auto-submit | P3/P8 | AC-11/12 |
| B6–B7 | Recorded/spoken answers + spoken questions | DELIVERED (P7/E5) — turn-based: Listen to questions/Mo + Speak answers; text-only evaluation | Spoken Qs + spoken answers | P7 | AC-13/14 |
| C1 | Realtime voice + interruption | PARTIAL (P7.5) — realtime architecture DELIVERED + DETERMINISTICALLY VALIDATED (provider-neutral WebRTC adapter, ephemeral-secret session, barge-in/cancel, commit-once, turn-based fallback); LIVE PROVIDER VALIDATION NOT RUN (no realtime key; OpenRouter cannot serve realtime) | Streaming + interrupt + fallback | P7.5 | EX-02 |
| C3 | Multilingual speech (7-lang) | DELIVERED (P7/E5) — STT (P3) + TTS 7-language mapping configured + deterministically tested; live human quality UNVALIDATED | Configured 7-lang STT/TTS; honest status | P7 | EX-04, AC-23 |
| E5 | Turn-based voice experience | DELIVERED (P7) — browser TTS + reused STT; editable transcript; explicit submit; no audio storage; no human-trait inference | Bounded voice modality | P7 | EX-04 |

## Group I — Evaluation / observability
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| I-eval | Deterministic agent/retrieval eval | DELIVERED | Extend (separate suite) | P9 | AC-22 |
| I-ragas | RAGAS harness (opt-in paid) | DELIVERED | Preserve | P9 | AC-22 |
| C8 | Per-operation model policy | DELIVERED (P5/E4) — central per-operation policy (`src/llm/policy.py`, 8 operations incl. REALTIME_VOICE; server allowlist; client cannot override the model) | Server allowlist per op | P5/E4 | EX-09 (gate Not run) |
| I-obs | Observability (optional Langfuse) | DELIVERED | Preserve | — | — |

## Group J — Security / privacy
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| J-authz | Object-level ownership / cross-user isolation | DELIVERED (extended P1 — session auth + composable authz) | Extend to teams/shares/docs | P1/P6 | AC-02 |
| J-audit | Security/privacy audit events | DELIVERED (P1) — bounded audit log, no secrets | Extend to teams/admin ops | P1/P6 | new AC |
| J-privacy | Data export/delete/retention | DELIVERED (P8) — export + full application-controlled deletion cascade (files + checkpoints) + audit anonymize; backups documented | Full lifecycle + policy | P1/P4/P6/P8 | EX-01/10 |
| J-inject | Injection/SSRF guards | DELIVERED | Extend to docs/OCR | P4 | EX-03 |

## Group K — Deployment / operations
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| C12 | Public hosting (HTTPS, verified-email reg) | READY (P8) — deploy artifacts + env validation + limits + pause + backup/restore/rollback docs; EX-12 BLOCKED/NOT RUN (needs authorized deployment) | Reproducible deploy + limits + rollback | P8 | EX-12 |
| C9 | Bulk retention cleanup | DELIVERED (P6) — inventory + safe temp cleaner (dry-run/owner-scope/idempotent) + existing session cleanup | Dry-run + bounded batches | P6/E7 | EX-10 |
| C11 | Prompt Lab (admin-only) | DELIVERED (P6) — versioned, isolated, human-reviewed, no auto-promotion | Versioned synthetic experiments | P6/E6 | EX-11 |

## Group L — Marketing / product experience
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| L-mkt | Marketing site + positioning | DELIVERED (P8, engineering draft) — public IA + pricing + trust; 7-locale marketing i18n; claims follow the claims audit | Public IA + pricing + trust | P8 | AC-25 |
| C10 | Guided onboarding / Help | DELIVERED | Preserve/adapt | P8 | AC-19 (C10 optional) |

## Totals (P0/E0 snapshot)
DELIVERED ≈ 20 · PARTIAL ≈ 12 · ABSENT ≈ 22 · OUT_OF_SCOPE (see exclusions) · UNVALIDATED: eval/knowledge data on fresh clone · BLOCKED: none at planning stage (auth/hosting/providers require owner authorization to *activate*, not to *plan*).

## Explicit OUT_OF_SCOPE
Camera/emotion/biometric assessment; recruiter rankings; automatic job applications; unrestricted crawling / job-board scraping; autonomous prompt/code/model changes; plugin marketplace; billing/payment; enterprise SSO/SCIM/HRIS; comprehensive enterprise administration. Spoken feedback and PDF export remain optional enhancements.

**Scope reconciliation (P8):** ~~whole-app UI translation~~ was originally OUT_OF_SCOPE, but the owner later EXPANDED scope to make seven-language internationalization/localization a Capstone deliverable (P3.5 foundation + P8 marketing localization + bounded candidate-surface completion). It is therefore IN scope and is tracked as `i18n-surfaces` / `L10n`. Billing/payment remains OUT_OF_SCOPE, but pricing/product **presentation** (D9) is in scope for P8 (presentation only, no checkout). The `Totals` line above is the P0/E0 baseline snapshot and does not reflect P1–P8 deliveries.

## P1/E1 presentation evidence (delivered this phase)
Standard presentation table — see `p1_e1_identity_platform.md` for the full story.

| # | Requirement | Status | How implemented | Evidence |
|---|---|---|---|---|
| B1 | Accounts: register/verify/login/logout/recovery | DELIVERED | `AuthenticationService` + `/auth/*`; server-side sessions in HttpOnly cookie; bcrypt | `tests/test_auth_api.py`, `eval_identity_platform.py` (authentication_flow 5/5, verification_recovery 6/6) |
| C6 | One social provider + email verify + recovery | DELIVERED (Google live UNVALIDATED) | `src/application/oidc.py` + `/auth/oidc/google/*`; state+redirect allowlist; verified-email linking | `tests/test_auth_oidc.py` (17), fake provider |
| D2 | Platform roles (USER/PLATFORM_ADMIN) | DELIVERED | `users.platform_role`; `require_platform_admin`; audited `scripts/bootstrap_admin.py`; no self-promote | `tests/test_auth_security_matrix.py`, `tests/test_bootstrap_admin.py` |
| D3/D4 | Basic/Premium entitlement + server enforcement | DELIVERED (no billing) | `product_entitlements`; capability map; `require_capability`; premium-only endpoint | security matrix (entitlement_bypass_prevention 1.0) |
| D8 | Public/authenticated route boundary | DELIVERED | Server fail-closed (401) + client `RouteGuard` | `tests/test_auth_failclosed.py`, `e2e/auth.spec.ts` |
| J-authz | Cross-user isolation under session auth | DELIVERED | ownership in data layer + trusted session identity | cross_user_isolation 1.0 |
| J-audit | Security/privacy audit log (no secrets) | DELIVERED | `audit_events` + `AuditRepository` | audit_safety 1.0 |
| D5/J-privacy | Account export + deletion request | PARTIAL | `/auth/account/export`, `/auth/account/delete-request` | full hard-delete cascade deferred |
| D1 | Admin control plane | FOUNDATION | guarded `/auth/admin/audit` (no Console UI) | admin_rejection/admin_grant 1.0 |
| C5 | Workspace role foundation | FOUNDATION | contract only (`WORKSPACE_OWNER/MEMBER`); no tables | deferred to Teams phase |

Legacy preservation: migration `0007` adds tables/columns + backfills; no candidate row re-keyed (`tests/test_migration_0007_identity.py`; legacy_data_preservation 1.0). Paid/live calls this phase: 0.

## P2/E2 presentation evidence (delivered this phase)
Return journey + response experience. See `p2_e2_return_response_experience.md`.

| # | Requirement | Status | How implemented | Why | Evidence |
|---|---|---|---|---|---|
| A2 | Authenticated return journey + active-session resume | DELIVERED | `ReturnJourney` Home card over `GET /interviews` (existing `list_active`); resumes `/practice?session=` | A returning user must continue, not restart | `e2e/return-response.spec.ts`, `tests/return-journey.test.tsx` |
| A1/A3 | History + Progress continuity under real accounts | DELIVERED | re-verified owner-scoped; wired into return card | Identity must not orphan the journey | `eval_identity_platform` cross-user 1.0; existing history/progress tests |
| Memory | Memory continuity under real accounts | DELIVERED | unchanged selective model; owner-scoped | Approved memory must persist across sign-in | cross-user isolation tests |
| UX-Q1 | Progressive response disclosure (answer/next-step/details/sources) | DELIVERED | deterministic `presentation` contract + `Disclosure`/`AgentAnswer`; no model call, no truncation | Reviewer: answers too long/hard to scan | `scripts/eval_response_experience.py` (all 1.0), `tests/response-ux.test.tsx`, `tests/test_response_presentation.py` |
| Pref | Brief/Detailed preference | DELIVERED (every tier; not paywalled) | `user_preferences` (migration 0008), `PATCH /auth/preferences`, Settings control; distinct from model profile | User-controlled response depth | `tests/test_preferences_api.py`, `tests/response-detail-preference.test.tsx`, `e2e/return-response.spec.ts` |
| Trend | Progress longitudinal trend | DEFERRED (documented) | not added — insufficient data would mislead | Honest analytics only | `p2_e2_return_response_experience.md` §trend decision |

Agent preserved: no change to tool selection, ReAct loop, retrieval, citations, HITL or the output guard; `eval_agent` GATE PASS unchanged. Paid/live calls this phase: 0.

## P3 / E-Dictation presentation evidence (delivered this phase)
Reusable UI + safe speech-to-text input. See `p3_e_dictation_reusable_ui.md` and `p3_ui_reuse_audit.md`.

Architecture flow: **Speech → recognition adapter → editable transcript → existing text input → explicit user submit → existing Ask4Mo workflow.** Explicitly: **NO automatic submission · NO audio persistence · NO emotion analysis.**

| Deliverable | Why | How implemented | Evidence | Status |
|---|---|---|---|---|
| Reusable input primitive | Remove 3-way composer duplication; one home for dictation | `components/ui/Composer.tsx` (controlled; click-only submit) used by agent + practice composers | `p3_ui_reuse_audit.md`; agent-coach/practice tests unchanged | DELIVERED |
| Shared dictation capability | One tested mic, not per-surface | `DictationControl` over `lib/speech/{types,browserAdapter,useDictation,useDictationLanguage}` (vendor-decoupled, fake-testable) | `tests/dictation-control.test.tsx` (9) | DELIVERED |
| Dictation on 2 real surfaces | Prepare + Practice input | Prepare goal box + follow-up composer; Practice answer composer | `e2e/dictation.spec.ts`; no-autosubmit unit tests | DELIVERED |
| No auto-submit (critical) | User must review/edit before sending | no submit call in commit path; explicit click only | `tests/dictation-no-autosubmit.test.tsx` (both surfaces) | DELIVERED |
| Typed-text preservation | Never destroy user input | `appendTranscript` (append, one space); interim = preview only | unit tests | DELIVERED |
| Graceful degradation | Typing always works | unsupported → control renders nothing; permission/failure → safe copy, no data loss | unit tests | DELIVERED |
| Accessibility | Keyboard + screen-reader usable | native button, aria-pressed/label, aria-live status, motion-safe | unit tests; audit | DELIVERED |
| Multilingual (bounded) | EN/DE/FR/ES/IT/PT/NL recognition | fixed BCP-47 allow-list, browser-locale init, honest support status | `eval_dictation_experience.py`; Help | DELIVERED (browser-engine-dependent) |
| Privacy | No audio/biometric/emotion | no recorder/getUserMedia/Blob; only lang code stored; honest vendor disclosure | eval; Help "Using dictation" | DELIVERED |
| i18n readiness | Don't make later localization harder | `lib/i18n/locales.ts` (typed app locales, not applied); localization debt documented | `p3_ui_reuse_audit.md` §localization | READINESS ONLY |

Response experience (P2) preserved: dictation is input-only; no change to model verbosity, presentation split, sources, citations, grounding, next-step logic or Brief/Detailed. Paid/live/speech-provider calls this phase: 0.

## P3.5 Internationalization & Localization presentation evidence (delivered this phase)
Seven-language candidate product (en, de, fr, es, it, pt, nl). See `p3_5_i18n_l10n.md`.

Flow: **explicit user choice → server-persisted/cookie locale → typed catalogue (English fallback) → localized UI + locale-aware formatting.** Three INDEPENDENT controls: interface / Mo-conversation / dictation. Language NEVER changes labour-market geography.

| # | Requirement | Why | How implemented | Evidence | Status |
|---|---|---|---|---|---|
| i18n-arch | Internationalization architecture | Localize without a second system or route rewrite | typed catalogues + registry + `I18nProvider` + cookie/account resolution + English fallback | `tests/i18n.test.tsx`, `eval_i18n_l10n.py` | DELIVERED |
| i18n-langs | 7 locale catalogues | European candidate reach | `lib/i18n/messages/{en,de,fr,es,it,pt,nl}.ts` (Catalog-typed, key-parity enforced) | catalogue parity test (all 7) | DELIVERED (engineering draft) |
| i18n-interface | Interface-language preference | UI in the candidate's language | `interface_locale` (migration 0009), Settings control, `<html lang>` | `test_locale_preferences.py`, `e2e/i18n.spec.ts` | DELIVERED |
| C3 | Mo conversation language | Prep for an interview in another language | bounded `conversation_language` → allow-listed agent directive; live quality UNVALIDATED | `test_conversation_language.py` | DELIVERED (plumbing); live UNVALIDATED |
| B5-dict | Dictation language (separate) | Speech input locale ≠ UI language | preserved from P3; distinct control | `eval_i18n_l10n` (separation) | DELIVERED |
| i18n-geo | Language ≠ geography | Career-intelligence safety | geography = `detect_country(query)`; no language coupling | `test_conversation_language.py`, eval | PASS |
| i18n-surfaces | Candidate surfaces localized | Usable 7-language product | shell/nav/account/auth/settings/home/return/dictation localized; deep pages + Help bodies + tutorial incremental | e2e locale matrix | PARTIAL (core done; incremental) |
| i18n-a11y | Accessibility preserved | Longer strings, screen readers | `<html lang>` dynamic; accessible controls; DE/FR checked | e2e | DELIVERED |
| i18n-review | Translation review status | No fabricated review claims | all locales labelled ENGINEERING DRAFT; review matrix | `p3_5_i18n_l10n.md` matrix | HONEST |

Also updated: C3 (multilingual speech EN+DE) is now bounded to the 7-language dictation set from P3; whole-application UI translation is explicitly NOT implied by multilingual speech. Paid/live calls this phase: 0.

## P4 / E2 / E3 Private documents & evidence presentation evidence (delivered this phase)
See `p4_e2_e3_documents_evidence.md` + `p4_privacy_data_inventory.md`.

Flow: **private document → validate → parse/OCR → deterministic extraction → user review → approved evidence → story bank → preparation/reuse.** NO automatic submission to Mo (documents are DATA, never prompts); NO audio/biometric/emotion analysis; NO public exposure.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| Private upload (PDF/DOCX/TXT + images) | DELIVERED | Candidate evidence workflow | multipart upload, allow-list + magic-byte + size/page limits, private random-key store | `test_documents_api.py`, `test_documents_pipeline.py` | content validation, not malware scanning |
| OCR (E2) | DELIVERED (live UNVALIDATED) | Read scanned files | native-first routing; Tesseract abstraction (fake-tested); origin='ocr'; 7 langs CONFIGURED | `eval_documents_evidence.py` (ocr_*), pipeline tests | live quality browser/engine-dependent |
| Provenance | PASS | Trace every claim | claims carry document→version→page/section; verbatim text | eval (extraction_provenance/no_invention) | heuristic extraction |
| Review/approval | DELIVERED | Candidate controls facts | accept/correct/reject; edited = user-corrected; nothing auto-approved | api tests | — |
| Story bank (E3) | DELIVERED | Reusable examples | deterministic source-backed draft; explicit states; **revocation on source delete** | eval (story_*), api tests | no LLM invention |
| Report export (A9) | DELIVERED | Own your data | owner-scoped MD + versioned JSON from stored report; no LLM, no internal state | export tests | PDF optional (not built) |
| Deletion / privacy lifecycle | DELIVERED (account cascade PARTIAL) | Data control | doc delete purges file+claims, re-derives stories; deletion inventory updated | privacy inventory, api tests | private-file + checkpoint purge on full account delete = remaining wiring |
| Security | PASS | Cross-user + injection safety | owner-scoped (foreign→404); traversal/spoof/oversize blocked; documents never prompted | `test_documents_api.py`, eval (cross_user_isolation, injection_inert) | — |
| I18n | DELIVERED (engineering draft) | 7-language product | `documents` namespace in all 7 catalogues; document language ≠ geography | catalogue parity test | human/legal review pending |

Paid LLM / OCR-provider / live calls this phase: 0.

## P5 / E4 Bounded multi-agent architecture & per-operation model policy (delivered this phase)
See `p5_agent_decomposition_audit.md` + `p5_e4_multi_agent_model_policy.md`.

Shape: **Mo stays the single candidate-facing orchestrator; three materially distinct bounded specialists sit behind Mo (reached only via allowlisted tools); one central per-operation model policy replaces scattered model selection.** No agent-to-agent free chat, no recursion, bounded budgets, schema-validated outputs, owner-scoped access to APPROVED private evidence only.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| Decomposition audit (§1) | DELIVERED | Complexity only where it adds value | every Mo capability classified DET/TOOL/SPECIALIST/HITL/KEEP; 3 specialists justified; nothing agentified to inflate count | `p5_agent_decomposition_audit.md` | — |
| Specialist A: Role & Opportunity | DELIVERED | Multi-step role synthesis | structured `RoleBrief`; reuses the governed JD-analysis op (no new raw model path) | `test_multi_agent_specialists.py` (role_*) | — |
| Specialist B: Candidate Evidence | DELIVERED | Evidence comparison, privacy-safe | **deterministic**, owner-scoped selection of APPROVED claims + verified stories; no model ⇒ injection-inert | eval (cross_user/other_user/no_owner), specialist tests | keyword-overlap ranking, not semantic |
| Specialist C: Interview Strategy / Coach | DELIVERED (live UNVALIDATED) | Synthesis + uncertainty handling | maps evidence→competencies; **CLARIFICATION_NEEDED instead of fabricated metrics**; injectable reasoner + deterministic fallback | eval (no-fabrication, id sanitisation), tests | live coaching model unvalidated; deterministic path shipped |
| Mo stays sole orchestrator | PASS | One coach, one voice | specialists are tools behind Mo; ReAct loop/graph/nodes unchanged | agent eval unchanged (recall 1.0, seq validity 1.0) | — |
| E4 central model policy | DELIVERED | No scattered model selection | `src/llm/policy.py`: 7 operations, capability floors, bounded fallback, deterministic-op (`NONE`), no secrets; pure resolver over the registry | `test_model_policy.py`, eval (policy_pass_rate 1.0) | — |
| Independent dimensions | PASS | Profile / policy / Brief-Detailed / language orthogonal | effective = max(user profile, op floor); language & presentation never change the model | `test_model_policy.py`, eval | — |
| Raw client slug rejected | PASS | Browser can't pick a model | `_resolve_profile` (Literal) + `resolve_policy` accepts only ModelProfile/None | `test_model_policy.py` (raw slug), eval | — |
| Owner-scoped evidence access | PASS | No cross-user leak; approved-only | `EvidenceAccessService` → `approved_claims`/`evidence_stories`; trusted `user_id` from state, never model-supplied; rejected/unreviewed/revoked excluded at repo | eval zero-invariants, specialist tests | — |
| Bounded fallback + degradation | DELIVERED | Safe on provider failure | ordered lower-tier chain to a floor; orchestration/final never degrade to Fast | `test_model_policy.py` | — |
| Safe observability / diagnostic | PASS | No CoT/secret/private content | `specialist_outputs` + `ResolvedModelPolicy.to_dict()` safe projections; no new chat surface | model-policy `to_dict` test | — |
| Prompt-injection inert (7 langs) | PASS | Multilingual safety | deterministic specialists tokenise-only; EN/DE/FR/ES/IT/PT/NL fixtures | eval (injection_inert_rate 1.0) | — |
| Deterministic eval + CI | DELIVERED | Repeatable gate, no cost | `scripts/eval_multi_agent.py` wired into CI; all gates pass | CI step; GATE STATUS PASS | not a live benchmark |

Migrations added: 0 (no schema change; Alembic head stays `0010_candidate_documents`). Paid/live LLM calls this phase: 0.

## P6 / E6 / E7 Knowledge governance, Prompt Lab & feedback learning (delivered this phase)
See `p6_knowledge_current_state_audit.md` + `p6_e6_e7_knowledge_promptlab_learning.md`.

Shape: **governance layer over the unchanged KB (manifest/readiness/coverage/source-health), K1–K4 bounded reviewed datasets with abstention, an isolated human-reviewed Prompt Lab with no auto-promotion, a governed feedback→improvement loop, and a retention inventory + safe temporary cleanup.** No production prompt/code/model/routing auto-modified. Alembic head unchanged (0010). Paid/live calls: 0.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| K1 German compensation | DELIVERED | Close the German-compensation gap safely | `data/knowledge/governed/k1_de_compensation.json` + `lookup_compensation` (provenance, pay unit, reference year); abstains outside set/jurisdiction; never invents a salary | `test_knowledge_governance_p6.py`, `eval_knowledge_governance.py` | figures engineering-draft (human data review carried) |
| K2 Credentials matrix | DELIVERED | Differentiate required vs preferred with lineage | `k2_credentials.json` + `lookup_credentials`; abstains outside matrix | same | legal verification carried |
| K3 Emerging roles/aliases | DELIVERED | Improve resolution for new roles safely | `k3_role_aliases.json` + `resolve_alias` (confident exact match only; never overrides existing) | same | curated; conservative matching |
| K4 Adzuna extensions | DELIVERED (live UNVALIDATED) | Entitled ops as bounded tools | `k4_adzuna_capabilities.json` + `validate_adzuna_operation` (allow-list, bounds, entitlement, safe output); no live call | same | live calls UNVALIDATED/cost-gated |
| Knowledge manifest | DELIVERED | Auditable KB without opening embeddings | `governance.knowledge_manifest` (governed + curated + provenance) | governance tests, reviewer API | — |
| Deterministic readiness | DELIVERED | READY ≠ "folder exists" | `governance.component_readiness` + states; honest SOURCE_MISSING/INDEX_MISSING on fresh clone | tests, `demo_readiness.py` | — |
| Source health | DELIVERED | Per-store diagnostics | `governance.source_health`; admin reviewer route | reviewer API test | — |
| Coverage matrix | DELIVERED | No universal-coverage claim | `governance.coverage_matrix` (domain/geo/lang/authority/limitation + disclaimer) | governance test | — |
| Retrieval evaluation | PRESERVED/STRENGTHENED | Deterministic, citations, geography, unsupported | existing 11R/KB-2/product/quality_v2/faithfulness_v2 + governance abstention checks | eval scripts | — |
| RAGAS separation | DELIVERED (honest) | Deterministic vs model-judged | committed deterministic baseline (0.6757/0.5161) preserved; judge NOT RUN | `evaluations/ragas/deterministic_baseline.json` | live judge UNVALIDATED (paid) |
| Multilingual retrieval | PARTIAL (bounded) | 7-lang boundary, not parity | `multilingual_cases.json` + language-boundary table; UI≠KB coverage | governance eval | live quality UNVALIDATED |
| E6 Prompt Lab | DELIVERED | Human-reviewed, isolated experiments | `src/application/prompt_lab/*`; deterministic evaluators; versioned; admin route | `eval_prompt_lab.py`, `test_prompt_lab_p6.py` | no live model comparison (cost-gated) |
| No auto-promotion | PASS | Production immutable from experiments | `applied_to_production=False` always; production policy byte-identical after runs | eval + tests | — |
| Prompt/config versioning | DELIVERED | Attributable production behaviour | `src/config_versions.py` (prompt/policy/specialist/knowledge) | reviewer config-versions test | — |
| Failed-experiment evidence | PRESERVED | Evidence-based engineering | `security_classifier_experiment.json` + registry left intact | repo artifact | — |
| E7 Feedback learning | DELIVERED | Governed improvement, not autonomy | taxonomy + improvement lifecycle over 7G; human triage; links to Prompt Lab | `eval_feedback_learning.py`, tests | candidate-facing category UI carried |
| Improvement lifecycle | DELIVERED | Explicit, human-driven | PROPOSED→…→IMPLEMENTED; IMPLEMENTED only from ACCEPTED, never automatic | tests | — |
| No autonomous change | PASS | No self-modification | `executed=False`, `applied_to_production=False`, lifecycle + isolation | evals | — |
| C9 Retention | DELIVERED | Explicit inventory + safe cleanup | `retention_service` inventory + `TemporaryArtifactCleaner` (dry-run/owner-scope/idempotent) | `eval_retention.py`, tests | bulk checkpoint cleanup carried |
| Reproducibility / demo readiness | DELIVERED | No silent PASS on missing artifacts | `demo_readiness.py` (non-zero on missing KB) + governance eval reports runtime state | script | — |
| Reviewer authorization | PASS | Candidate cannot access diagnostics | `/api/v1/reviewer/*` `require_platform_admin`; candidate 403 | `test_reviewer_api_p6.py` | API-only (no admin console) |

Migrations added: 0 (Alembic head stays `0010_candidate_documents`). Paid/live LLM/Adzuna/judge calls this phase: 0.

## P6.5 Teams/Workspaces & Platform Admin (delivered this phase)
See `p6_5_workspace_admin_design.md` + `p6_5_workspaces_platform_admin.md`.

Shape: **bounded workspaces with membership roles on the membership, secure single-use invitations, explicit allow-listed VIEW-only sharing (private-by-default, immediate revocation), and a bounded PLATFORM_ADMIN operations console (metadata only, audited, never a data superuser).** Migration 0011 (single head). No billing, no enterprise SSO. Paid/live calls: 0.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| C5 Workspaces + roles + invitations | DELIVERED | Bounded collaboration | `workspaces`/`workspace_memberships` (OWNER/MEMBER)/`workspace_invitations` (hashed, single-use, 72h); `WorkspaceService` | `test_workspaces_p6_5.py`, `eval_workspace_security.py` | VIEW-only sharing; no org hierarchy |
| Invitations (expiry/replay/foreign) | PASS | Secure joins | opaque token stored hashed; own-email match; single-use; expiry | eval (invite_single_use/invite_expiry/foreign_invite_rejected) | live email UNVALIDATED (memory adapter in tests) |
| Membership (leave/remove/transfer/last-owner) | DELIVERED | Safe lifecycle | server-authorized; last-owner guard; leave/remove revokes outbound shares | tests + eval | — |
| P/share Explicit sharing | DELIVERED | Explicit, allow-listed | `share_grants` VIEW-only; operational types **interview report + story** wired end-to-end (owner-scoped loaders + bounded VIEW projection); owner+member verified | `test_sharing_p6_5.py` (per-type matrix), `eval_workspace_security.py` (incl. operational_allowlist_truthful) | preparation_summary PLANNED / excluded from the operational allowlist (no durable owned resource yet) |
| Private-by-default | PASS | Membership ≠ access | no share ⇒ no visibility; decision re-derived each read | eval (private_by_default/explicit_share_required) | — |
| Revocation + deletion invalidation | PASS | Immediate, no resurrection | revoke sets status; source delete invalidates grants | eval (share_revocation/deleted_resource_invalidation) | — |
| Cross-workspace isolation | PASS | 0 leakage | membership+share re-checked; client workspace id never overrides authz | eval (cross_workspace_isolation) | — |
| Teams ≠ Premium | PASS | Orthogonal dimensions | workspace access separate from BASIC/PREMIUM; no billing | design doc + entitlement code | — |
| D1 Platform Admin console | DELIVERED | Bounded ops | `/api/v1/admin/*` router-gated; `/admin` UI | `test_platform_admin_p6_5.py`, `eval_platform_admin.py` | not a full enterprise console |
| Admin authorization | PASS | Least privilege | normal user 403, unauth 401; router-level `require_platform_admin` | eval (admin_authorization/normal_user_rejected) | — |
| Admin ≠ data superuser | PASS | Private data protected | metadata-only projections; no view-as-user; owner repos stay owner-scoped | eval (admin_not_data_superuser), tests | — |
| Entitlement/role admin (audited) | DELIVERED | Governed changes | `set_tier`/`set_platform_role`/`set_status`; audited; self-lockout guard | eval (entitlement/role change audited, self_lockout) | — |
| Knowledge/Prompt Lab/Feedback reuse | DELIVERED | No second backend | admin console reuses P6 reviewer APIs; no-auto-promotion preserved | eval (knowledge_diagnostics_access/promptlab_boundary/feedback_boundary) | — |
| Privacy request queue | DELIVERED | Ops visibility | `/admin/privacy-requests` metadata; deletion not falsely complete | eval (privacy_request_boundary) | global hard-delete still PARTIAL |
| Provider/audit safety | PASS | No secret leakage | providers/audit return booleans/metadata only | eval (provider_secret_safety/audit_safety) | — |
| Candidate feedback taxonomy UI | DELIVERED | P6 carried item | optional category on `FeedbackControl`; `user_feedback.category`; i18n | frontend build + backend threading | candidate category selection now available |
| I18n (7 locales) | DELIVERED (engineering draft) | Candidate reach | `workspaces` namespace in all 7 catalogues; parity enforced | `frontend/tests/i18n.test.tsx` | human review pending |

Migration added: `0011_workspaces_shares` (Alembic head now `0011_workspaces_shares`). Paid/live LLM/email calls this phase: 0.

## P7 / E5 Multilingual turn-based voice experience (delivered this phase)
See `p7_voice_architecture_audit.md` + `p7_e5_voice_experience.md`.

Shape: **turn-based voice — Listen (browser TTS) to Mo responses & Practice questions; Speak (reused P3 STT) answers; editable transcript; explicit submit; text-only evaluation.** NO realtime streaming, NO audio storage, NO human-trait inference. No migration (Alembic head `0011_workspaces_shares`). Paid/live/speech-provider calls: 0.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| TTS provider-independent adapter | ARCHITECTURE + DETERMINISTIC | Vendor-neutral, testable | `lib/speech/{ttsTypes,speechSynthesisAdapter,useSpeechOutput,fakeSpeechOutputAdapter}.ts` | `voice-output.test.tsx`, `eval_voice_experience.py` | live human quality UNVALIDATED |
| Listen on Mo responses | DELIVERED | Hear grounded guidance | `VoicePlaybackControl` in `AgentConversation` (speaks `presentation.answer`) | `e2e/voice.spec.ts` (Prepare) | — |
| Listen on Practice questions | DELIVERED | Hear the question | `VoicePlaybackControl` in `PracticeClient` (`q.question`) | `e2e/voice.spec.ts` (Practice) | — |
| Speak answers | DELIVERED (reuse P3) | Answer by voice | existing `DictationControl` in the answer composer | dictation + voice e2e | browser STT dependent |
| Editable transcript + explicit submit | PASS | User control | P3 append-only + explicit Submit; no auto-submit on any voice surface | eval (no_auto_submit), e2e | — |
| TTS does not auto-open mic | PASS | No voice loop | no recognition/mic start in TTS layer/onEnd | eval (tts_does_not_auto_start_mic), e2e | — |
| STT/TTS mutual exclusion (closure) | PASS | Never both active on a surface | shared `voiceCoordination` provider; both hooks claim/release; starting one stops the other; no auto-start | eval (stt_tts_mutual_exclusion/tts_stops_active_stt/stt_stops_active_tts/no_feedback_loop), `voice-concurrency.test.tsx`, `voice.spec.ts` | — |
| Text-only Practice evaluation | PASS | Determinism preserved | submit sends the text answer; no audio score | eval (practice_uses_text_evaluation) | — |
| 7-language TTS configuration | CONFIGURED + DETERMINISTIC | Bounded reach | `ttsLocales.ts` (en/de/fr/es/it/pt/nl) + honest status | eval (seven_language_configuration), unit | browser voice availability varies; live UNVALIDATED |
| Language/geography separation | PASS | Safety | TTS locale never touches career geo/jurisdiction | eval (language_geography_separation) | — |
| No audio persistence / no biometric | PASS | Privacy | no MediaRecorder/Blob/voiceprint; localStorage pref only | eval (no_audio_persistence/no_biometric_storage) | STT audio browser/vendor-processed (stated) |
| No human-trait inference | NONE | Absolute boundary (§16) | trait identifiers absent as code; scanned comment-stripped | eval + `test_voice_experience_p7.py` | — |
| Unsupported/permission fallback | PASS | Never blocks | control renders null when unsupported; P3 permission handling | eval (unsupported_fallback/permission_failure_fallback) | — |
| Navigation cleanup | PASS | No zombie speech | `useSpeechOutput` cancels on unmount | eval (navigation_cleanup) | — |
| Admin/workspace voice boundary | PASS | No private voice data | admin providers = architecture only; no audio/voice sharing | eval (admin_no_voice_private_data/workspace_no_auto_share) | — |
| i18n (7 locales) | DELIVERED (engineering draft) | Candidate reach | `voice` namespace in all 7 catalogues (controls + localized Voice Help via useT); parity enforced | `tests/i18n.test.tsx`, `voice-help-i18n.test.tsx` | human review pending; legacy Help bodies on localization backlog |
| Realtime voice (C1) | DEFERRED / OPEN (superseded by P7.5) | Turn-based chosen for P7 | not built in P7; realtime delivered in P7.5 (see below) | — | now PARTIAL — see P7.5 |

Migration added: 0. Paid/live/speech-provider calls this phase: 0.

## P7.5 / C1 Realtime voice + interruption (delivered this phase)
See `p7_5_c1_realtime_voice.md` + `p7_5_realtime_voice_feasibility.md`.

Shape: **genuine realtime voice — provider-neutral `RealtimeVoiceAdapter` seam; WebRTC to an OpenAI-Realtime-shaped provider; server mints a short-lived ephemeral session credential (long-lived key never reaches the browser); streaming transcript; barge-in (response.cancel + conversation.item.truncate); commit-ONCE through the existing Practice answer service (deterministic Practice stays authoritative); mandatory fallback to P7 turn-based voice.** OFF by default. NO audio storage, NO human-trait inference. No migration (Alembic head `0011_workspaces_shares`). Paid/live/realtime-provider calls: 0.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| Realtime voice + interruption (C1) | DELIVERED (architecture) + DETERMINISTIC; LIVE NOT RUN | Feasibility-first C1 | provider-neutral adapter + WebRTC OpenAI-Realtime adapter + ephemeral-secret session route | `eval_realtime_voice.py` (28), `test_realtime_voice.py` (15), `realtime-voice.test.tsx` (6), `e2e/realtime-voice.spec.ts` (2) | live provider round-trip UNVALIDATED (no realtime key) |
| Secret boundary (ephemeral only) | PASS | Long-lived key never in browser | `read_secret` → Bearer once; response carries only `client_secret` | `test_realtime_voice` (ephemeral boundary), eval (`ephemeral_secret_boundary`, `no_long_lived_secret_in_browser`) | — |
| Barge-in / interruption | PASS (deterministic) | Core C1 | `response.cancel`+`conversation.item.truncate`+clear local audio behind adapter | `realtime-voice.test.tsx` (barge-in), e2e | live VAD timing UNVALIDATED |
| Duplicate-turn prevention | PASS | No stale/duplicate commit | commit-once guard (`committedTurn`/`turnId`); durable state via `submitAnswer` | unit + e2e (one answer POST) | — |
| Fallback to turn-based | PASS | Never a dead end | 503/unsupported/mic-denied/disconnect → end + keep committed + P7 + typing | eval (`fallback_to_turn_based`), e2e (End → fallback) | — |
| Practice determinism preserved | PASS | Realtime is bounded voice mode | transcript commits through existing answer contract; state machine authoritative | eval (`practice_state_authority`), e2e | — |
| Model-policy boundary | PASS | No client model override | `ModelOperation.REALTIME_VOICE` (REALTIME cap, no chat slug); request has no model field | `test_realtime_voice`, `multi_agent_eval` | — |
| Rate/cost bounds | PASS (local) | Bounded provider sessions | per-user rate limit + concurrency + session/idle caps | `test_realtime_voice` (429), eval (`rate_bound`) | in-memory; prod needs shared store |
| No audio storage / no trait inference | PASS | Sensitive-modality integrity | no recorder/blob/voiceprint; no emotion/accent/confidence/hiring | eval (`no_audio_persistence`,`no_voice_trait_inference`) | provider-side transient processing per provider policy |
| Admin/workspace privacy | PASS | No private audio/transcript | `/admin/providers` realtime booleans; `audio/transcript_visible_to_admin: false` | `test_realtime_voice`, eval (`admin_workspace_privacy`) | — |
| 7 languages | CONFIGURED + DETERMINISTIC | Candidate reach | locale coercion to en/de/fr/es/it/pt/nl; i18n keys in 7 catalogues | eval (`language_geography_separation`), i18n parity | live/human quality NOT RUN |
| Realtime voice (C1) — live | NOT RUN | No authorised realtime key | deterministic only; OpenRouter cannot serve realtime | — | EX-02 live round-trip open |

Migration added: 0. Paid/live/realtime-provider calls this phase: 0.

## P8 / E8 Productisation, public surfaces & hosted-operation readiness (delivered this phase)
See `p8_e8_productisation_hosting.md` + `p8_productisation_gap_audit.md` + `p8_public_claims_audit.md` + `p8_hosting_operations.md`.

Shape: **public marketing site at `/` + authenticated product at `/app`; Trust/Privacy/Terms/AI-transparency (engineering draft); Basic/Premium pricing PRESENTATION (NO billing); coherent data-rights hub + full application-controlled account deletion; auth + cost rate limiting; operator pause switch; env fail-fast; security headers; real readiness probe; malware fail-safe; reproducible staging deploy artifacts + backup/restore/rollback runbook.** No migration (Alembic head `0011_workspaces_shares`). Paid/live provider calls: 0. NOT merged; NOT deployed.

| Requirement | Status | Why | How | Evidence | Limitation |
|---|---|---|---|---|---|
| D7 Public marketing website | DELIVERED | Public front door | `/` marketing (Home/Product/Pricing/Trust/About) + `MarketingShell`; app → `/app` | `e2e/marketing.spec.ts`, `route-migration.spec.ts` | copy engineering draft; human review pending |
| D6 Privacy/legal public surfaces | DELIVERED (engineering draft) | Trust/transparency | Privacy/Terms/AI-transparency/Trust pages with legal-review banners | `marketing.spec.ts` (draft banner) | **legal review required** |
| D9 Pricing presentation | DELIVERED | Commercial model | `lib/pricing.ts`; Basic €0 / Premium preview; truthful CTAs | `marketing.spec.ts` (no billing/cards) | NO checkout/billing (out of scope) |
| D5/J-privacy Data rights + deletion | DELIVERED | Candidate control | data-rights hub + `AccountDeletionService` (DB + files + checkpoints + audit anonymize) | `eval_account_deletion.py`, `test_p8_hardening.py` | backups age out per provider; untracked-run checkpoints residual |
| Auth rate limiting | DELIVERED | Abuse/enumeration | `rate_limit.py` per-IP/account/global, hashed email key | `eval_rate_limits.py`, `test_p8_hardening.py` | single-process store |
| Cost/provider limits + pause | DELIVERED | Cost/incident control | `guards.py` cost buckets; `pause.py` + `/admin/pause` | `test_p8_hardening.py` | single-process; shared store for multi-replica |
| Security headers + CORS + cookies | DELIVERED | Hosted hardening | `SecurityHeadersMiddleware`; allowlist CORS; HttpOnly/Lax/Secure | `eval_hosting_readiness.py` | CSRF beyond SameSite carried |
| Env validation + readiness | DELIVERED | Fail-fast prod | `env_validation.py` (prod raises); real `/ready` probe | `eval_hosting_readiness.py`, `test_p8_hardening.py` | — |
| Upload malware policy | DELIVERED | Public upload safety | `file_security.py` fail-closed; EICAR fake | `eval_hosting_readiness.py` | live ClamAV UNVALIDATED |
| Hosting artifacts + backup/restore/rollback | READY | Reproducible staging | `deploy/*` + `p8_hosting_operations.md` | `bash -n`; `eval_hosting_readiness.py` (docs present) | not deployed |
| SEO (robots/sitemap/noindex) | DELIVERED | Crawlable marketing; private app | `robots.ts`/`sitemap.ts`; noindex app/admin/review | build output | — |
| Marketing i18n (7 locales) | DELIVERED (engineering draft) | Candidate reach | `marketing` namespace in all 7 catalogues | `marketing.spec.ts` (de) | human/legal review pending |
| C12 hosted operation (EX-12) | BLOCKED / NOT RUN | No authorized deployment | implementation ready; hosting can't be certified locally | — | needs authorized HTTPS deploy |

Migration added: 0. Paid/live provider calls this phase: 0.

## P9 Integrated quality & release-candidate acceptance (executed this phase)
See `p9_acceptance_ledger.md` + `p9_quality_register.md` + `p9_integrated_quality_hardening.md` + `p9_voice_measurement.md` + `p9_localization_completeness.md`; evidence package `artifacts/capstone/p9/RC-P9-001/`.

Release candidate **RC-P9-001** (baseline main `eb91125`, P8 merged PR #84; Alembic head `0011_workspaces_shares`). Deterministic/local acceptance executed at this SHA; live/deployment/human-review portions kept separate. Paid/live calls: 0.

| Gate | Result | Evidence |
|---|---|---|
| AC-01..AC-12, AC-16, AC-17 | PASS | backend suites + Playwright + evaluators (see ledger) |
| AC-14/AC-15 | PASS (deterministic) | voice/multi-agent evals; live model quality NOT RUN |
| AC-13 | PARTIAL | deterministic STT; live correction burden NOT RUN |
| AC-18 | PARTIAL | review surfaces (A6/A8 partial diagnostics) |
| AC-19 | PASS | renders + mobile no-overflow + a11y; Chromium fully tested (matrix documented) |
| AC-20 restart/recovery | **PASS** | `eval_restart_recovery` (restart+backup+restore) + migration up/down/up single head |
| AC-21 regression gate | **PASS** | full gate green; 3 justified skips (live Adzuna / legacy Streamlit / ragas-conditional) |
| AC-22 agent/retrieval | PARTIAL | policy 1.0; extension pass 0.9136, citation 1.0, no-fabrication 1.0; historical ID P/R 0.6757/0.5161 preserved; live benchmark NOT RUN |
| AC-23 voice | PARTIAL | EN/DE reference set + deterministic latency; live STT/latency NOT RUN |
| AC-24 pilot | NOT RUN | P10 |
| AC-25 submission | PARTIAL | matrix/docs truthful; final package P11/P12 |
| EX-06/08/09/10/11 | PASS (deterministic) | workspace/story/model-policy/cleanup/prompt-lab evals |
| EX-01/02/03/04/05/07/13/14/15/16 | PARTIAL | deterministic PASS; live/human-review portions NOT RUN |
| EX-12 hosted | BLOCKED / NOT RUN | implementation READY; no authorized deployment |

Totals: **AC** 15 PASS / 7 PARTIAL / 1 NOT RUN · **EX** 5 PASS / 10 PARTIAL / 1 BLOCKED. Defects: P0=0, P1=0. No gate FAIL. Not merged; not deployed; P10 not started.
