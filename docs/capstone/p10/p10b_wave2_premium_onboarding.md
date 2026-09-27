# P10B Wave 2 — Premium First-Run Onboarding + Persistent Mo Coaching Preferences

**Status:** REINTRODUCTION CANDIDATE / awaiting merge (implementation complete; gates green).
**Branch:** `feature/capstone-p10b-wave2-reintroduce` — **not merged**.
**Baseline:** `main` @ `ed4ef21` (post-revert; content-identical to the pre-Wave-2 baseline `38530ec`, i.e. Waves 1, 3, 4 merged; PRs #87/#88/#89).
**Migration:** `0013_onboarding_personalisation` (additive; chains from `0012_document_failure_kind`; single head).
**Release candidate:** none. RC-P9-001 immutable; RC-P10-002 only at Wave 8.
**Paid/live calls:** 0.

**Reintroduction note.** Wave 2 was first merged via **PR #90** (at branch commit `be1303f`, i.e. *without* the
completion-error UX closure) and then **fully reverted** via **PR #91** (`52f4a18`), so current `main` contains no
Wave 2 behaviour. The later **PR #92** carried only the completion-error delta (`d268b19`) relative to reverted
`main` and is therefore not a valid standalone Wave 2 release unit — it is **superseded** by this branch. This branch
cleanly reintroduces the **complete final Wave 2 state** (the exact `38530ec..d268b19` product change, including
migration `0013` and the completion-error closure) on top of current `main`; the net `main..branch` diff is exactly
that Wave 2 delta and nothing else (current `main` carried no independent changes to reconcile).

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

## Completion failure (recoverable)
`OnboardingClient.finish()` treats the completion API as authoritative. On failure it stays on
`/onboarding`, does not mark onboarding complete locally, does not navigate to `/app`, keeps every
saved preference/step, and shows a localized, announced (`role="alert"`) recoverable error
(`onboarding.completionError`, all 7 locales) — never a raw API/provider error, never a logged
preference value. "Enter Ask4Mo" is disabled while a request is in flight (no duplicate submissions)
and re-enabled for retry; a successful retry clears the error and performs
server-completion → account refresh → `onboarding_completed=true` → `/app`. Covered by
`e2e/onboarding.spec.ts` E2E 5 and a `wave2-onboarding.test.tsx` unit test.

## CI-closure testing note
Two Wave 2 CI failures (`auth.spec` sign-in→`/progress`; `onboarding.spec` E2E 1 completion→`/app`)
were **test-synchronization** issues, not product defects. Evidence: the completion lifecycle was
verified robust under targeted stress (server completion persists, `refresh()` returns
`onboarding_completed:true` before navigation, `/app` does not bounce). The accurate conclusion is
narrow: **the tests had insufficient synchronization around asynchronous client-side navigation.**
Explicitly waiting for the intended navigation, and pairing a click-triggered navigation with
`page.waitForURL(...)`, produced deterministic behaviour under the targeted stress runs (E2E 1 20/20;
sign-in tests 40/40). This does not assert any particular Playwright implementation mechanism (e.g.
that `toHaveURL` "polls" and `waitForURL` does not — both are waiting mechanisms); only the observed
determinism under stress is claimed.

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
