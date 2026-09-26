# P10B Wave 4 — Prepare/Practice Integration, Governed Evidence & Multilingual Interview

**Status:** DELIVERED (implementation complete; gates green).
**Branch:** `feature/capstone-p10b-wave4-integration` — **not merged**.
**Baseline:** `main` @ `737f89b` (Wave 1 + Wave 3 merged; PRs #87, #88).
**Migration:** **none** (`conversation_language` rides the existing JSON session config; head stays
`0012_document_failure_kind`).
**Release candidate:** none. RC-P9-001 immutable; RC-P10-002 only at Wave 8.
**Paid/live calls:** 0.

This wave joins the previously separate capabilities into one workflow — Role/JD → CV/evidence →
Prepare with Mo → Practice → evaluation/report — and closes the Wave 1 deferral by making the
Practice interview multilingual across EN/DE/FR/ES/IT/PT/NL. It preserves every existing security,
provenance, HITL, evidence, privacy, scoring and language/geography boundary.

---

## 1. Context model (the contract)

Four **distinct** concern groups flow into Prepare/Practice; they are never collapsed into one
setting:

**A. ROLE CONTEXT** — the target role (`target_role`), sector (`industry_or_sector`), company
(`company_context`), and the job description. The JD may be pasted (`job_description` text) **or**
selected from the candidate's governed documents (`job_description_document_id`, resolved to text
**server-side**, owner-scoped). Location/geography is only ever what the candidate explicitly
selects and is **not** changed by any language choice.

**B. CANDIDATE CONTEXT** — approved CV claims and verified/user stories, reached ONLY through
`EvidenceAccessService` (accepted/edited claims + safe stories). Opting in
(`use_candidate_evidence`) composes a bounded `candidate_background` from that approved evidence —
**never** the raw CV, never pending/rejected/source-revoked/model-suggested items.

**C. SESSION CONTEXT** — interview type(s), difficulty, number of questions, interviewer persona,
response detail, and **`conversation_language`** (the interview's generated-prose language).

**D. PRODUCT PREFERENCES** — interface language (`interface_locale`), Mo conversation language
(`conversation_language`, the account default), dictation language (device-local), response detail,
and model profile.

**Separation invariants (enforced, tested):**
`interface language ≠ conversation language ≠ dictation language`; and
`language ≠ career geography ≠ document language`. Changing the conversation language changes only
generated prose — never geography, scoring, interface locale, document language, or dictation locale.

## 2. One document pipeline only

Prepare and Practice are **consumers** of the single governed document system from Wave 3. They
reuse `components/documents/DocumentUpload.tsx` (the one uploader) via a new reusable
`components/documents/DocumentPicker.tsx` (list existing by category + inline governed upload).
There is **no** second upload endpoint, no Prepare/Practice-specific storage, no browser-only
document copy, no raw CV in `localStorage`/URL, and no duplicated OCR/parsing/extraction. The picker
emits only a **document id**; the server resolves it.

## 3. Prepare — document integration

`AgentPrepareWorkspace` (the Mo workspace) already accepted pasted JD/background text and already
sent `conversation_language` from the account preference on every run. Wave 4 adds, in the context
section, a governed **JD picker** (upload or select a stored JD). A pasted JD takes priority;
otherwise the selected `job_description_document_id` is sent and resolved server-side into the JD the
agent's governed `AnalyzeRoleOpportunity` op consumes. Mo already reaches **approved** evidence via
the deterministic `FindCandidateEvidence` specialist (trusted `user_id`), so evidence needs no new
plumbing. Uploading/selecting never auto-sends anything to Mo.

## 4. Practice — document & language integration

`InterviewSessionSetup` was rebuilt to read as **Target role → Your evidence → Interview**, fully
localized, and now offers: a JD picker (`job_description_document_id`), a **"use my approved CV
evidence"** opt-in (`use_candidate_evidence`), and an **interview-language** selector defaulting from
the account's `conversation_language`. All are passed in the create `configuration`. Context is
chosen **before** the interview starts; once an interview has materially started the durable session
config is authoritative and is never silently swapped. Attaching documents/evidence does not change
scoring.

## 5. Raw document / prompt-injection boundary

The P4 invariant holds: private document text is not casually dumped into prompts.
- **CV / candidate evidence:** only APPROVED structured claims + verified stories via
  `EvidenceAccessService` become `candidate_background`; the raw CV is never used. Provenance and
  approval state are respected; deleting the source removes the evidence.
- **Job description:** the interview's existing `job_description` field already treats JD as
  untrusted DATA and screens it (`InterviewService._screen_context` → `security.detect_injection`),
  placing it in the user message, never as instructions. A selected JD document is resolved to text
  **server-side** and fed into that SAME governed field — no new raw-model path. The narrowest
  governed integration; no new raw-document RAG was introduced.

## 6. Evidence approval / HITL

Unchanged and enforced: uploaded → extracted → review required → accept/correct/reject → approved →
eligible. Unreviewed claims never become candidate truth; corrected claims keep provenance; rejected
stay excluded; deleting a source flips verified → source_revoked and drops it from evidence. Mo and
interview coaching never invent numbers/outcomes/responsibilities/qualifications/achievements — if
evidence is missing the specialists raise clarification rather than fabricate.

## 7. Role/JD context

The active role is represented with the existing config fields plus the selected JD document id
(resolved to text). No Opportunity model, no schema/migration — a clean seam that **Wave 6** can own.

## 8. Practice conversation language

Closed the Wave 1 deferral. A bounded `conversation_language` (allow-listed 7 locales) was added to
`InterviewConfiguration` (persists via the JSON session codec — **no migration**) and to the create
schema. A trusted, prose-only directive (`prompts._language_directive`, allow-list only — the raw
code never reaches the model) is injected into the **system** prompt of every generation task, so
**question generation, evaluation, feedback, next question, report summary, strengths, focus areas
and recommendations** are all produced in the chosen language. It is server-side generation-language
control, not frontend translation of generated content. Geography/scoring/interface/dictation are
untouched.

## 9. Language consistency UX

The interview (conversation) language is shown and selectable in the Practice setup (defaulting from
the account), with a help line distinguishing it from interface and dictation languages — so the
candidate never needs Settings just to understand the interview language. No competing store: the
default comes from, and Settings still owns, the account preference.

## 10. Dictation (STT)

Reuses the existing P3/P7 architecture — no new microphone. Prepare's goal/composer use
`DictationControl` (+ device-local `useDictationLanguage`); Practice's answer composer uses the
shared `Composer` (which embeds `DictationControl`). Transcript editable, no auto-submit, no
auto-activation; unsupported browsers keep the Wave 1 accessible fallback. Dictation language stays
independently selectable.

## 11. TTS / voice

P7 turn-based voice and the P7.5 realtime boundary are preserved. Question playback follows the
conversation language (`toSpeechLocale`), never the interface locale. No automatic STT↔TTS loop; the
`VoiceCoordinationProvider` mutual-exclusion still wraps both surfaces. Realtime remains
configured/deterministically-tested, live UNVALIDATED.

## 12. Report language

The report uses the SAME `_generate(config=…)` path, so `conversation_language` propagates into
report generation (summary/strengths/focus areas/recommendations). Scores are LLM-produced with **no
deterministic recompute**, and the directive is prose-only in the system prompt: switching language
does not change the DATA the model scores. Tests assert the user message (the scored DATA) is
byte-identical across languages and that the API returns identical scores for EN vs DE.

## 13. Security / privacy

Owner-scoped throughout: a selected JD/evidence resolves via a trusted `user_id`; a foreign/missing
document id resolves to no context (never another user's data); `EvidenceAccessService` excludes
non-approved/revoked evidence; deleting a source removes it. JD/CV text stays DATA (screened). The
model can never supply a `user_id`. No candidate content in the URL or `localStorage`; no audio
storage; no transcript stored before explicit submit. Admin/workspace boundaries unchanged (no
private-document exposure).

## 14. Multi-agent impact

No new specialist. Mo remains the orchestrator; the three existing specialists, `EvidenceAccessService`,
the tool allowlist, bounded ReAct steps, HITL, the `retrieval_used` invariant and the per-operation
model policy are all unchanged. Deterministic plumbing (document/evidence resolution) was NOT
agentified.

## 15. i18n

New fixed UI strings use the 7-language catalogue: the `practice` setup keys + a new `prepctx`
namespace, added across EN/DE/FR/ES/IT/PT/NL with parity enforced by the `Catalog` type. Uploaded
CV/JD text, user answers, evidence, names and company names are never translated; generated
Mo/interview content follows `conversation_language`. Engineering translations, not human/legal
reviewed.

## 16. Accessibility

Keyboard-operable document selection (labelled `<select>` + labelled upload), labelled language
selectors, `aria-live` upload status, distinct accessible names (the JD picker is "Select a saved job
description", separate from the paste box), ≥44px targets, no colour-only state, mobile-safe layout,
and the existing accessible dictation/voice controls.

## 17. Evaluation

`scripts/eval_prepare_practice_integration.py` (new) — 19 invariants, all PASS: single document
pipeline, Prepare/Practice surfaces, approved-evidence-only, source revocation, owner scope, JD
injection-inert, CV-raw-prompt-blocked, conversation-language bounded, seven languages configured,
Practice + report language propagated, language/geography separation, scoring-language independence,
dictation separation, no-auto-submit, voice coordination, no-new-agent. 0 paid/live calls.

## 18. Regression / quality / migration / paid-live

- Backend: full `pytest` (see FINAL REPORT), ruff clean, OpenAPI contract pass; evaluators
  documents/evidence, i18n, multi-agent, agent, prepare/practice-integration all PASS.
- Frontend: typecheck, **270 unit**, lint, build, **104 Playwright e2e** all green.
- Migration: none. Paid/live calls: 0. No tests weakened.

## 19. Defects found & fixed
- Practice interview content was English-only regardless of the conversation language (Wave 1
  deferral) → propagated server-side across all generation stages.
- Documents/evidence were a separate silo, not reachable from Prepare/Practice → governed picker on
  both surfaces.
- Prepare had no way to select a stored JD (paste-only) → JD picker + server-side resolution.
- Interview setup was hardcoded English → localized across 7 locales.

## 20. Known limitations
- **Live/human quality of non-English generated interviews is UNVALIDATED** (deterministic tests
  prove propagation, not model output quality; 0 paid calls here).
- Full Opportunity model deferred to **Wave 6** (Wave 4 provides only the JD/role seam).
- Human/legal translation review of the new UI strings not done.
- Realtime voice remains live-UNVALIDATED.
- Prepare shows the conversation language via the account default; a per-run in-flow selector there
  is deferred (Practice has the in-flow selector; Settings owns the account preference).

## 21. RC impact
No RC created. RC-P9-001 immutable; Wave 8 cuts RC-P10-002. A pilot against this changed runtime
before Wave 8 requires a new RC first.

## 22. Next recommended wave
**Wave 5** (company intelligence) or **Wave 6** (Opportunity model, which will own the role/JD seam
established here). Not started.

## 23. Final verdict
The candidate journey is now coherent: role/JD and approved CV evidence flow from Prepare and
Practice through the ONE governed document system, and the interview runs end-to-end in the chosen
conversation language (question → evaluation → report) with scoring, geography, provenance and the
raw-document boundary all preserved. No migration, 0 paid/live calls, no new RC.
