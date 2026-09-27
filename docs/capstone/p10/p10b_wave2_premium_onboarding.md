# P10B Wave 2 — Premium First-Run Onboarding + Persistent Mo Coaching Preferences

**Status:** DELIVERED (implementation complete; gates green).
**Branch:** `feature/capstone-p10b-wave2-onboarding` — **not merged**.
**Baseline:** `main` @ `38530ec` (Waves 1, 3, 4 + CI closure merged; PRs #87/#88/#89).
**Migration:** `0013_onboarding_personalisation` (additive; single head).
**Release candidate:** none. RC-P9-001 immutable; RC-P10-002 only at Wave 8.
**Paid/live calls:** 0.

The first authenticated experience now configures a personal AI coach — About You → Career Focus →
How Mo Should Coach You → Language & Communication → Privacy & Memory → Review → Enter Ask4Mo —
rather than a generic tutorial. It reuses the existing preference, i18n and voice architecture (no
parallel systems) and preserves every existing boundary.

## Preference ownership & precedence
Independent concepts, never silently changing one another:
- **Interface language** (`interface_locale`, account) — the UI language.
- **Default conversation language** (`conversation_language`, account) — Mo's prose language.
- **Dictation language** (device localStorage) — STT locale.
- **Career geography** (`career_geography`, account — NEW) — target labour market. Bounded/validated;
  **never inferred from language** (a German UI does not imply the German market).
- **Document language** (per document) and **session language** (per-interview override, Wave 4).

Precedence for applicable settings: **session override > account default > device preference (where
applicable) > English/safe fallback**. The per-interview conversation language (Wave 4) overrides the
account default; the account default is resolved server-side only when a request omits it.

## Onboarding lifecycle
- New columns on `users`: `onboarding_completed_at` (NULL = pending) + `onboarding_step` (resume).
- **New users:** created with `onboarding_completed_at = NULL`. `RouteGuard` sends an authenticated,
  incomplete account to `/onboarding` before normal product use (never on `/onboarding` itself → no
  loop; never on public routes). Registration/verification/OIDC flows are unchanged.
- **Existing users:** migration `0013` **backfills** every existing account to completed
  (`onboarding_completed_at = now`), so no current user is ever blocked. Verified by test.
- **Resumability:** each step persists server-side (`POST /auth/onboarding {step}` — never regresses;
  preference fields via `PATCH /auth/preferences`). Returning re-reads saved values + resumes at the
  saved step. Nothing sensitive is stored only in localStorage; no preferences in URLs.
- **Completion** marks `onboarding_completed_at`, refreshes the account and routes to `/app`. It
  starts nothing (no mic, interview, agent run, document processing or research).

## Mo coaching (ONE Mo, configured)
Bounded styles: **supportive / balanced / direct / challenging**. Mapped in `src/coaching_style.py`
to a **trusted, allow-list-only directive** (`coaching_style_directive`) — the raw code never reaches
the model; balanced/unknown → no directive.

**Surfaces affected (tone/wording only):**
- **Prepare (Mo chat):** appended as a trust-separated `SystemMessage` in `src/agent/nodes.py`,
  carried on the run request/state like the language directive; the frontend sends the account
  default.
- **Practice feedback:** injected into the interview **evaluation** and **report** system prompts
  only (`src/prompts.py`), never into question/strategy generation (so it cannot change question
  difficulty or the interview itself). The interview create route defaults it from the account.

**Scoring independence (proved):** the directive is prose-only in the system prompt; the scored
user-message DATA is byte-identical across styles, and numeric scores are LLM-produced with no
recompute. Tests assert identical user messages across styles and that a "challenging" style never
scores harder. It never changes factuality, evidence, rubric, safety, authorization, model policy,
retrieval, HITL, candidate evidence, hiring suitability, confidence thresholds or security.

## Response detail
Reuses the existing `response_detail` (brief/detailed) via the existing `ResponseDetailPreference`
control (embedded in the onboarding coaching step). Coaching style and response detail are
independent — DIRECT + DETAILED and SUPPORTIVE + BRIEF are all valid.

## Settings integration
A new **Personalisation & coaching** card (`PersonalisationSettings`) in the existing
`SettingsContent` edits preferred name, target role, career geography and coaching style (persisted
via `api.auth.updatePreferences`), plus a "Revisit setup" link to `/onboarding`. The global
`LanguageMenu` still changes **interface language only**; it never modifies conversation/dictation/
career-geography/session language. No second settings system.

## Voice
Reuses P3/P7/P7.5 — onboarding contains no microphone, no auto-capture, no voice-trait inference, no
biometric storage. The voice/dictation defaults remain device-local; onboarding does not open a mic.

## i18n
New fixed strings use the 7-locale catalogue: new `onboarding`, `coaching`, `geography` namespaces +
`settings` additions across EN/DE/FR/ES/IT/PT/NL, parity enforced by the `Catalog` type. Country
names use standard exonyms; codes are unchanged. User-entered name/role/geography/documents are never
translated; generated Mo content follows `conversation_language`. **Engineering-draft translations —
not human/legal reviewed.**

## Accessibility
Keyboard-complete stepper; accessible progressbar + `aria-live` step status; every input labelled;
selection cards use real radio semantics (`CoachingStyleField`); ≥44px targets; no colour-only state;
Back/Next operable; distinct accessible names (the personalisation action is "Update personalisation",
not a second "Save"). Mobile-first layout.

## Security / privacy
Owner-scoped throughout; the model can never supply `user_id`; no cross-user preference access; admin
gains no candidate coaching/profile data (the admin surface is unchanged). Coaching preference is a
bounded enum → trusted directive (no arbitrary prompt injection). Free-text name/target role are DATA
(bounded length), audited as "set" (never logged verbatim) and never fed to a model as a prompt. No
private content in URLs or logs; no audio storage; no new workspace sharing; preferences and privacy
rights are **not** entitlement-gated. Privacy/data inventory updated.

## Migration
`0013_onboarding_personalisation` (chains from `0012`; single head): adds `users.onboarding_completed_at`
(nullable) + `users.onboarding_step` (default 0); `user_preferences.coaching_style` (default balanced)
+ `career_geography` (default "") + `target_role` (default ""). Backfills existing users to completed.
Upgrade/downgrade/single-head verified; additive and non-destructive.

## Evaluation
`scripts/eval_onboarding_personalisation.py` (new) — 20 invariants, all PASS (new-user semantics,
existing-user backfill, resumability, owner scope, bounded coaching styles, no arbitrary persona
prompt, coaching-not-scoring, response-detail independence, language separation, language/geography
separation, session override, Settings editing, 7-locale parity, no auto mic/interview, no sensitive
collection, no private prefs in logs, migration safety). 0 paid/live calls.

## Known limitations
- Human/legal translation review of the new strings is not done (engineering draft).
- Career-geography is a bounded curated list (not an exhaustive market taxonomy).
- Onboarding voice is a preference concept only (device-level); no in-flow mic test in this wave.
- Opportunity/role-specific spaces remain Wave 6 (career focus here is an account default only).

## RC impact
No RC created. RC-P9-001 immutable; Wave 8 cuts RC-P10-002. A pilot on this changed runtime before
Wave 8 requires a new RC first.

## Next recommended wave
**Wave 5** (company intelligence) or **Wave 6** (Opportunity model). Not started.

## Final verdict
The premium first-run setup is delivered: new candidates configure profile, career focus, coaching
style, languages and privacy understanding, resumably and accessibly; existing users are never blocked
and can edit everything in Settings. Coaching style changes only how Mo communicates — never scores —
proved by tests; language and geography stay independent. One additive migration, 0 paid/live calls,
no new RC.
