# P10B-W9.10 - Product Positioning / Comparison Foundation

Documentation + focused public-copy wave. **No backend, schema or migration change** (Alembic head
`0014_opportunities`), 0 paid/live calls, **no external or competitor research** (no named product was searched,
browsed or characterised), no RC-P10-003, Pilot 2 not resumed, W9.11 and W10 not started.
Canonical claim source: `docs/product/PRODUCT_CLAIMS.md`.

## 1. Baseline
`main` = `c905302a31d6c2c172945bb054bb6712d026dd09` (W9.9 merged, PR #104). Branch `feat/p10b-w9-10-product-positioning`.

## 2. Audit methodology
Positioning was derived bottom-up: (1) inventory implemented candidate capabilities from routes, components, services,
evaluators and tests; (2) classify each C1-C4; (3) reconcile with the W9.9 Trust Claim Matrix; (4) derive category,
problem, value proposition, pillars and proof points; (5) audit existing public copy (`marketing`, `trust`, pricing)
against the register; (6) change copy only where a defect existed. No competitor site or third-party data was consulted.

## 3-4. Canonical capability matrix and classification
C1 = implemented and verified; C2 = implemented with material limitation (qualify); C3 = planned/incomplete (never present as live);
C4 = internal architecture (not candidate marketing).

| ID | Capability | Class | Evidence | Limitation / note |
|---|---|---|---|---|
| CAP-01 | Opportunity workspace (role, company, JD, one job) | C1 | `/opportunities`, `eval_opportunity_journey` | private; not a Workspace |
| CAP-02 | Prepare with Mo (agent, plan, gaps, role requirements) | C1 | `/prepare`, `eval_agent` | live model tool-selection is imperfect (README) |
| CAP-03 | Approved evidence + Story Bank from private documents | C1 | documents pipeline, `eval_documents_evidence` | only approved evidence is used |
| CAP-04 | Practice interview: questions, answers, evaluation, report, Deep Dive | C1 | `/practice`, `eval_prepare_practice_integration` | guidance, not a hiring decision |
| CAP-05 | Progress and History | C1 | `/progress`, `/history` | history delete added in W9.8 |
| CAP-06 | Approved, editable, deletable memory | C1 | HITL, memory API | separate from history |
| CAP-07 | Human approvals for memory and practice handoff | C1 | HITL nodes | none |
| CAP-08 | Workspaces, view-only sharing, revocation | C1 | `eval_workspace_security`, W9.8 | revocation does not recall viewed content |
| CAP-09 | Owner-scoped data; admin sees metadata only | C1 | `eval_platform_admin`, `eval_identity_platform` | not a certification |
| CAP-10 | Grounded answers with sources and abstention | C2 | `AgentSources`, `eval_faithfulness_v2` | sources only when evidence used; KB must be provisioned; coverage varies |
| CAP-11 | Company research (fact / review / inference separation) | C2 | `eval_company_intelligence` | explicit website required; review sites not integrated; live unvalidated |
| CAP-12 | OCR for scanned documents | C2 | `OcrEngine` | optional runtime; accuracy unvalidated |
| CAP-13 | Dictation (browser) | C2 | `eval_dictation_experience` | 7 languages, browser-dependent |
| CAP-14 | Text-to-speech playback | C2 | `eval_voice_experience` | 7 languages; not Russian |
| CAP-15 | Realtime voice | C2 | `eval_realtime_voice` | off by default; live NOT RUN |
| CAP-16 | 8 interface + 8 Mo conversation languages | C2 | `eval_i18n_l10n` | engineering translations; narrower speech/geography/taxonomy |
| CAP-17 | Data & Privacy: export, selective delete, revoke | C2 | `/account/data`, `eval_privacy_controls` | PRIV-W9-01; export excludes files |
| CAP-18 | Account deletion | C2 | `eval_account_deletion` | backups not instant; some chat data may remain |
| CAP-19 | Career data coverage (roles, compensation, credentials) | C2 | `eval_knowledge_governance` | no universal coverage claim; Germany/EU-weighted |
| CAP-20 | Consent / legal-version history | C3 | none | PRIV-W9-02 |
| CAP-21 | Candidate deletion of individual preparation chats | C3 | none | PRIV-W9-01 |
| CAP-22 | Purchasable Premium / billing | C3 | `BILLING_ENABLED=false` | preview only |
| CAP-23 | Customer support ticketing | C3 | none | W10.3 |
| CAP-24 | Full admin/operations platform | C3 | P6.5 console is bounded | W10 |
| CAP-25 | Specialists and allow-listed tool registry | C4 | `src/agent/specialists`, registry | internal |
| CAP-26 | Deterministic router, hybrid RAG, structured stores | C4 | `src/copilot` | internal |
| CAP-27 | Central model policy per operation | C4 | `src/llm/policy.py` | internal |
| CAP-28 | Durable checkpoints, OCC session store | C4 | `src/agent/checkpoint.py` | internal |

**Counts: C1 = 9, C2 = 10, C3 = 5, C4 = 4 (28 capabilities).**

## 5. Reconciliation with the W9.9 Trust Claim Matrix
Every allowed claim in `PRODUCT_CLAIMS.md` carries the W9.9 qualifications: AI can be wrong (CLAIM-003/019); sources only when
career evidence is used (CLAIM-004); privacy controls are real but not absolute (CLAIM-015/016/018); preparation-chat deletion
incomplete (CLAIM-015/016, NO-05, CAP-21); consent persistence absent (NO-06, CAP-20); candidate remains responsible (trust
statement). No claim contradicts W9.9.

## 6-10. Positioning
- **Category:** an AI-assisted interview and career preparation platform for candidates, organised around one job at a time.
  (Not a new category; not recruiter/ATS/HR software.)
- **Core problem:** when preparation material for a job sits in separate places, feedback is hard to connect to the role and to
  the candidate's own experience. (Stated as a conditional; no prevalence claim.)
- **Primary value proposition:** *Keep everything for one job in one place: prepare with an AI coach, practise realistic
  interviews and see your progress, with your data under your control.*
- **Pillars and proof:**
  1. Built around one job - Opportunity (CAP-01), company research (CAP-11).
  2. Evidence-aware guidance - approved evidence only (CAP-03), sources when used, abstention (CAP-10).
  3. Realistic practice and feedback - structured evaluation, report, Deep Dive (CAP-04), dictation (CAP-13).
  4. Continuity - Progress, History, approved memory (CAP-05/06).
  5. You stay in control - approvals (CAP-07), Data & Privacy (CAP-17), view-only sharing (CAP-08), stated limits.

## 11. Message hierarchy
One-line, value proposition and trust statement are in `PRODUCT_CLAIMS.md` section 3. Homepage hero stays "Prepare for the
interview that matters." (supported, concrete).
- **Supporting messages:** (1) Everything for one job in one Opportunity. (2) Sources shown when an answer uses career
  evidence; Mo says when evidence is thin. (3) Practise tailored questions; type or dictate; get structured feedback.
  (4) Progress and history carry across sessions; memory only with approval. (5) Export your data, remove items, revoke sharing.
- **Product explanation (about 100 words):** Ask4Mo helps you prepare for a specific job. You create an Opportunity with the role,
  company and job description, then prepare with Mo, an AI coach that shows its sources when it uses career evidence and tells you
  when it does not have enough. You bring your own documents privately, and only evidence you approve is used. Practise tailored
  interview questions, get structured feedback and a report, and track your progress over time. Mo remembers preparation context
  only when you approve it. Mo is AI and can make mistakes: use it as coaching support and make your own decisions.
- **Longer overview (about 280 words):** Interview preparation often involves several separate tools: a job description in one
  place, company research in another, a CV somewhere else and generic practice questions on top. Ask4Mo is built to keep that
  together. Everything starts with an Opportunity, a private space for one job. Inside it you can research the company from
  sources you can check, keeping facts, review context and AI suggestions separate, and prepare with Mo. Mo answers career
  questions, builds a preparation plan and highlights gaps; when an answer uses career evidence the sources are shown, and when
  evidence is thin Mo says so instead of inventing facts. You can add your CV and other documents privately; the evidence you
  approve can inform preparation and a reusable Story Bank, and unreviewed or rejected evidence is not used. When you are ready,
  practise a realistic interview tailored to the role, answering by typing or dictating where your browser supports it. You
  receive structured feedback and a report, and can go deeper on individual answers. Progress and history show how you are
  doing across sessions, and Mo remembers preparation context only when you approve it. You stay in control: download a copy of
  your data, remove individual items, share selected items with a workspace on a view-only basis and revoke that access, or
  delete your account. Some limits apply and are stated in the product: preparation chats cannot yet be removed individually,
  translations are drafts pending review, and Mo is an AI that can be wrong. Ask4Mo is coaching support, not a hiring decision
  and not a substitute for your own judgement.

## 12. Feature, capability, benefit, safe claim
| Feature | User capability | Benefit | Safe claim |
|---|---|---|---|
| Opportunity | prepare around one role | related material stays connected | "Keep preparation for each job in one place." (CLAIM-001) |
| Approved evidence | use your own experience in preparation | guidance can reflect what you approved | "Only evidence you approve is used." (CLAIM-007) |
| Sources + abstention | see where career guidance comes from | you can check it | "See sources when an answer uses career evidence." (CLAIM-004/005) |
| Practice + report | rehearse tailored questions | structured feedback to act on | "Practise tailored questions and get structured feedback." (CLAIM-008) |
| Progress/History/Memory | revisit sessions and approved context | continuity | "Track progress and revisit reports." (CLAIM-012/013) |
| Data & Privacy | export, remove, revoke | visibility and control | "Download your data and remove individual items." (CLAIM-015) |

## 13. Candidate journey
Opportunity, then Prepare, then Practice, then Progress and History. Mo coaches during Prepare, informs the practice context, and
its approved memory persists across the journey. This is the primary narrative; it is already the public story (Wave 7) and the
in-app navigation, so no structural change was needed.

## 14-17. Category-level comparison framework (no names, no scores, no winner)
"Varies" = varies by product/provider; no capability is assumed for any other category.

| Dimension | Ask4Mo | Generic conversational AI | Structured interview-prep software | Human coaching |
|---|---|---|---|---|
| Job-specific context | Opportunity per job (verified) | Varies by product/provider | Varies by platform | Depends on the coach |
| Persistent preparation context | Opportunity, history, approved memory (verified) | Varies by product/provider | Varies by platform | Depends on the coach |
| Structured interview workflow | Prepare, Practice, Progress (verified) | Varies by product/provider | Typically the core purpose; varies | Varies by coach |
| Evidence / source support | Sources shown when career evidence is used (qualified) | Varies by product/provider | Varies by platform | Coach's own knowledge |
| Reusable evidence / stories | Approved evidence, Story Bank (verified) | Varies by product/provider | Varies by platform | Varies by coach |
| Interview practice and evaluation | Structured feedback, report (guidance only) | Varies by product/provider | Varies by platform | Live, tailored to the person |
| Progress tracking | Progress and History (verified) | Varies by product/provider | Varies by platform | Varies by coach |
| Data-control features | Export, item removal, revocation, account deletion, with stated limits | Varies by provider | Varies by platform | Varies by coach |
| Availability | On demand when the service is running | Varies | Varies | Scheduled with the coach |
| Human judgement and nuance | Not provided; AI can be wrong | Not provided | Varies | Core strength |
| Lived experience, emotional interpretation | Not provided | Not provided | Varies | Core strength |
| Live accountability | Not provided | Not provided | Varies | Typically provided |
| Cost model | Basic free; Premium preview (no billing yet) | Varies | Varies | Varies by coach |
| Scalability | Self-service, repeatable | Varies | Varies | Limited by coach time |

Boundaries: Ask4Mo is not a replacement for human coaching and the comparison states human strengths plainly; it does not say
generic AI cannot use documents, remember, research, cite or practise; it does not say structured platforms lack AI, voice,
feedback or analytics. Ask4Mo's differences are limited to verified product structure (Opportunity-centred, integrated journey,
explicit history, candidate evidence model, productised privacy controls). No cost comparison is made.

## 18-19. Claim register
`docs/product/PRODUCT_CLAIMS.md`: **20 allowed claims** (9 C1, 11 C2 with qualifications) and **20 prohibited/restricted
claims**, including repository-specific ones (NO-05 preparation-chat deletion, NO-06 consent history, NO-12 Russian speech/market/ESCO,
NO-13 review-site integration, NO-15 purchasable Premium, NO-16 ticketing).

## 20. Public copy changed (audit defects)
| Defect | Fix |
|---|---|
| "Upgrade to Premium when you want more" implied a purchase path (billing not live) | "Premium is a preview for now: see what it will include on the pricing page" |
| "Answers cite the sources behind them" / "Answers cite their sources" overstated universal citation | "show sources when career evidence is used"; "Mo says so when evidence is thin" |
| "Practice ... by text or voice" over-generalised (practice evaluation is text; voice is dictation/TTS/realtime-where-configured) | "Type your answers or dictate them" (browser-dependent) |
| "Not another generic interview generator" was an unsupported comparative jab | "What makes Ask4Mo different" |
| "Ask4Mo tells you what it does not know" | "Mo says so when it does not have enough evidence" |
Eight keys changed in all 8 locales. Everything else on the public pages already mapped to allowed claims and was left alone.

## 21. Comparison page decision
**Option A: no new page.** The Home "What makes Ask4Mo different", `/product`, `/trust` and `/ai-transparency` already cover what a
`/why-ask4mo` page would, and a comparison page without external research would add risk without information. The category-level
framework above is internal guidance for future copy and W9.10 follow-ups; any public comparison needs separately authorised
current-data research.

## 22-25. Localization, QA, bundle, tests
All 8 changed keys exist in 8 locales (engineering translations pending native/legal review); scanner 0 offenders; slogan exact.
No layout change; the changed strings were checked at 390px in de and ru (no overflow). Bundle: copy-only change, shared first-load
JS unchanged. Tests: `tests/positioning-claims.test.tsx` (public pages render allowed claims, no prohibited phrases, no named
competitors, trust/privacy links, 8-locale completeness); evaluator `scripts/eval_product_positioning.py` (added to CI: claim register
integrity, C1-C4 counts match, prohibited-phrase and named-competitor scan of public copy, no `vs`/comparison routes, PRIV items
present, no migration). Results are in the PR.

## 26. Open items
PRIV-W9-01, PRIV-W9-02, TD-W9-01, TD-W9-02 remain OPEN; native Russian and legal copy review, live generated-language validation,
metadata localization and bundle optimisation also remain.

## 27-29. Confirmations
No competitor research was performed. No migration. 0 paid/live calls.

## 30. W9.11 handoff: mismatches found (not fixed here)
1. `README.md` "Current limitations" still says production OIDC is not implemented and identity is transitional; real accounts
   shipped in P1 (only Google OIDC live-unvalidated).
2. README and `docs/architecture.md` predate Opportunities, the Data & Privacy Center, 8 locales, workspaces, specialists and
   the admin console; the README documentation index is Sprint-4 era.
3. `CLAUDE.md` / README disagree on the registered tool count in places (CLAUDE.md: 11 tools; older docs: 4-9); specialists
   are 3 (`role_opportunity`, `candidate_evidence`, `interview_strategy`); there is no Evaluation Specialist (do not claim one).
4. `docs/privacy.md` and `constants.DATA_RETENTION_NOTE` still describe the Streamlit-era "export all / delete everything in
   Settings" flow and over-state per-interview deletion before W9.8.
5. Voice docs say "seven languages" for speech while the product has eight interface locales; wording is correct only if kept
   speech-specific (CLAIM-010/014).
6. Authority-level semantics comment and `capstone_target_architecture.md` forward references need the W9.11 reconciliation already planned.
7. Pre-existing translation-quality defect: the Wave 7 `marketing` block in de/fr/es/it/pt contains ASCII-folded text
   without diacritics (for example "Fuehren", "Uebungen", "Vorschlaege", "reponses"). W9.10 restored diacritics only on the
   keys it edited; the rest needs a pass (translation review / W9.11).
