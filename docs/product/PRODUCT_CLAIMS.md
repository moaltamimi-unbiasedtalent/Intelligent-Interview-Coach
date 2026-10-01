# Ask4Mo Product Claims (canonical source)

The single source for what public and candidate-facing copy may say about Ask4Mo. Created in P10B-W9.10 from
internal evidence only (code, tests, evaluators, W9.8/W9.9 docs); **no external or competitor research was used**.
Method, capability matrix and positioning rationale: `docs/capstone/p10/w9/P10B_W9_10_PRODUCT_POSITIONING.md`.
Trust wording is bound by the W9.9 Trust Claim Matrix (`P10B_W9_9_TRUST_VISUAL_POLISH.md`). Guarded by
`scripts/eval_product_positioning.py` (CI).

Rules: a claim may be used externally only if it appears in section 1 (as written or weaker). Qualified claims must carry
their qualification. Anything in section 2 must not appear. Update this file first, then the copy. The protected
slogan `Ask More. Be More.` is never translated or re-punctuated.

## 1. Allowed claims
Class: C1 = implemented and verified, C2 = implemented with a material limitation (qualification required).

| ID | Claim | Type | Class | Evidence | Qualification | Surfaces |
|---|---|---|---|---|---|---|
| CLAIM-001 | Keep preparation for one specific job together in an Opportunity. | workflow | C1 | `/opportunities`, `tests/test_opportunity_journey.py`, `eval_opportunity_journey.py` | An Opportunity is private to you; it is not a workspace. | home, product |
| CLAIM-002 | Add the role, company and job description for a job. | workflow | C1 | Opportunity create, JD document/text | none | home |
| CLAIM-003 | Prepare with Mo, an AI coach, for a role. | AI | C1 | `/prepare`, agent service, `eval_agent` | Mo is AI and can make mistakes. | home, product |
| CLAIM-004 | See sources when an answer uses career evidence. | evidence | C2 | `AgentSources`, W9.9 `[n]` markers, `eval_faithfulness_v2`, `eval_knowledge_retrieval` | Only when career evidence is used; knowledge coverage varies by occupation and geography. | home, product, trust |
| CLAIM-005 | Mo says so when it does not have enough evidence instead of inventing facts. | evidence | C2 | `INSUFFICIENT_EVIDENCE_MESSAGE`, W9.7A localized note | Reduces, does not eliminate, errors. | home, trust |
| CLAIM-006 | Research a company from sources you can check, with facts, review context and AI suggestions kept separate. | evidence | C2 | `/company`, `eval_company_intelligence` | Needs an explicit company website; third-party review sites are not integrated. | home, product |
| CLAIM-007 | Bring your CV and job descriptions privately; only evidence you approve is used. | privacy | C1 | documents pipeline, `EvidenceAccessService` | Scanned documents need OCR where installed. | home, product |
| CLAIM-008 | Practise tailored interview questions and get structured feedback and a report. | functionality | C1 | `/practice`, `eval_prepare_practice_integration`, `tests/test_interview_service.py`, Deep Dive | Feedback is practice guidance, not a hiring decision. | home, product |
| CLAIM-009 | Type your answers or dictate them where your browser supports it. | functionality | C2 | `DictationControl`, `eval_dictation_experience` | Dictation uses the browser engine, in 7 languages; no audio is stored. | home, product |
| CLAIM-010 | Listen to Mo or a question read aloud in seven languages. | functionality | C2 | `VoicePlaybackControl`, `eval_voice_experience` | Browser speech; not available for Russian. | product |
| CLAIM-011 | Realtime voice is available where configured. | functionality | C2 | `RealtimeVoiceControl`, `eval_realtime_voice` | Off by default; live provider behaviour not validated. | product |
| CLAIM-012 | Track progress and revisit completed interviews and reports. | functionality | C1 | `/progress`, `/history` | none | home |
| CLAIM-013 | Mo remembers preparation context only when you approve it, and you can edit or delete it. | privacy | C1 | HITL `APPROVE_MEMORY`, memory API | Memory is separate from interview history. | home, trust |
| CLAIM-014 | Use Ask4Mo in eight interface languages and have Mo coach in the same eight. | localization | C2 | `src/locales.py`, `eval_i18n_l10n` | Translations are engineering drafts pending native review; speech support is narrower; language never sets your job market. | home, product |
| CLAIM-015 | Download a copy of your data and remove individual items. | privacy | C2 | `/account/data`, W9.8 | Export is one JSON file and excludes original files; preparation chats cannot yet be listed or removed individually. | trust, account |
| CLAIM-016 | Delete your account and its application-controlled data. | privacy | C2 | `AccountDeletionService`, `eval_account_deletion` | Security records are kept anonymised; backups are not erased instantly; some preparation-chat working data may remain until cleaned up. | trust, account |
| CLAIM-017 | Share selected items with a workspace, view only, and revoke access. | privacy | C1 | workspaces/shares, W9.8 | Revoking does not recall what members already saw. | home, trust |
| CLAIM-018 | Your data is private by default and scoped to your account. | privacy | C1 | owner-scoped repositories, `eval_platform_admin` | Platform administrators see account metadata only. | home, trust |
| CLAIM-019 | Mo is a coach, not a recruiter; Ask4Mo does not make hiring decisions. | trust | C1 | AI transparency page | none | home, trust |
| CLAIM-020 | Start free; Premium is a preview with no online payment yet. | commercial | C1 | `lib/pricing.ts`, `BILLING_ENABLED=false` | Premium cannot be purchased yet. | pricing, home |

## 2. Prohibited or restricted claims (must not appear)
| ID | Claim | Why |
|---|---|---|
| NO-01 | "GDPR compliant" / any compliance or certification claim | no legal review or certification |
| NO-02 | "100% secure", "completely private", "enterprise-grade security" | not demonstrable; privacy is strong but not absolute |
| NO-03 | "bias-free", "fully unbiased" | models and data can be biased |
| NO-04 | "all answers verified", "all advice is evidence-based", "fact checked" | AI can be wrong; evidence is shown only when used |
| NO-05 | "delete everything Ask4Mo knows about you", "all data can be deleted", "all preparation-chat data is deleted" | PRIV-W9-01 open |
| NO-06 | A history of accepted Terms/Privacy versions | PRIV-W9-02: not stored |
| NO-07 | "human reviewed", "lawyer reviewed", "native-speaker reviewed" | translations/legal copy are engineering drafts |
| NO-08 | "employer approved", "used by hiring managers", testimonials, customer counts, ratings | none exist |
| NO-09 | "guarantees interview success", "improves hiring probability by X%", any outcome statistic | no evidence |
| NO-10 | "best interview coach", "#1", "better than ChatGPT", "better than human coaches", "more accurate than ..." | unsupported comparative claims; no competitor research |
| NO-11 | Named-competitor feature comparisons or "Ask4Mo vs X" | no authorised research |
| NO-12 | "Russian speech/voice", "Russian job market", "official ESCO Russian" | not supported |
| NO-13 | Glassdoor, Kununu, Google or LinkedIn as integrated sources | not integrated |
| NO-14 | "real-time company intelligence", "browses the whole web" | bounded research only |
| NO-15 | Purchasable Premium, prices beyond `lib/pricing.ts`, discounts, savings, ROI | billing not live; W10 owns plans |
| NO-16 | Customer support ticketing / SLA | not built (W10.3) |
| NO-17 | "WCAG compliant" or accessibility certification | not audited |
| NO-18 | Recruiter/ATS/HR/hiring-automation positioning | not the product |
| NO-19 | Voice-based emotion, confidence or personality assessment | explicitly never done |
| NO-20 | Hype filler: revolutionary, game-changing, next-generation, cutting-edge, supercharge, unlock your potential | style rule |

## 3. Approved message set
- **One line:** Ask4Mo is an AI-assisted interview preparation platform that organises preparation, practice and feedback around one job at a time.
- **Value proposition:** Keep everything for one job in one place: prepare with an AI coach, practise realistic interviews and see your progress, with your data under your control.
- **Trust statement:** Mo is AI and can make mistakes. Ask4Mo shows sources when an answer uses career evidence, keeps your data private by default, and lets you download your data and remove individual items.
- **Journey:** Opportunity, then Prepare, then Practice, then Progress and History, with Mo available through the journey.
