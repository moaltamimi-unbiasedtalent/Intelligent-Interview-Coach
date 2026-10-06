# Pilot 2 — readiness and methodology (RC-P10-003)

**Candidate under test:** RC-P10-003, product SHA `54aad500ec937b4828984c32c64b77746534633d`. One candidate for the whole pilot.
**Status:** PILOT 2 REACTIVATION PREPARED (post-merge: READY FOR HUMAN SESSIONS). **Human evidence: NONE YET.** **AC-24: NOT RUN / PENDING REAL PARTICIPANTS.** **Paid/live calls: 0.** This pack does not conduct or fabricate the pilot. See `RC_P10_003_PILOT2_REACTIVATION.md`.

## Purpose
Test RC-P10-003 as an end-to-end candidate experience, not a screen inspection. Observe behaviour first; ask neutral follow-ups afterwards. Exploratory qualitative usability pilot: no statistical significance is claimed; always report real denominators ("3/5"), never percentages without counts.

## Participants
Target 3–5 real participants supplied by the owner (P01…P05). Fewer than 3 completed → Pilot 2 INCOMPLETE and AC-24 stays NOT RUN. Language plan (only if participants permit; never fabricate coverage): at least one German session; at least one non-English session; Russian valuable if a suitable participant exists. Boundaries: 8 interface locales, 8 Mo conversation languages, 7 speech/document/KB languages. Russian: interface YES, Mo conversation YES, speech NO, KB NO, official ESCO NO, Russian geography not inferred.

## Journey
T1 Orient → T2 Get started → T3a Opportunity → T3 Prepare → T4 Documents/evidence → T5 Interview Practice → T6 Return journey → T7 Privacy/trust → T8 Voice (only where the environment supports it) → T9 Final exploration → debrief. Task wording is in `RC_P10_003_PARTICIPANT_TASKS.md`. Admin is not a participant task; it is in scope only where it affects candidate-visible support or privacy behaviour.

## Post-W9/W10 trust changes to observe (candidate-facing consequences)
Privacy & Data controls and the Data & Privacy Center; Trust polish; the Opportunity-centred journey; localized experience incl. the Russian interface; support/ticket discoverability where candidate-facing; truthful error and recovery behaviour; sharing and revocation; source/evidence comprehension; and that workspace members do NOT automatically see private data.

## Visual and responsive observation fields (observe, do not lead)
Comprehension; visual hierarchy; imagery helps / distracts / neutral (per surface); empty-state clarity; perceived trust (up / down / none); provenance understanding (a depicted person believed to be a real customer — expected: no). Responsive: Chromium is the tested engine; if a mobile condition is used the canonical mobile pilot width is 390px. No cross-browser evidence is claimed.

## Issue taxonomy (categories stay separate)
PRODUCT-UX · MODEL-QUALITY · VOICE-TRANSCRIPTION · INFRASTRUCTURE · VISUAL-UI · PRIVACY-TRUST. Severity: BLOCKER / HIGH / MEDIUM / LOW. Where useful keep P0–P3 for true software defects and U1–U4 for usability impact separately. A provider-off limitation is INFRASTRUCTURE / PROVIDER LIMITATION, never a participant failure, and is never presented as tested live behaviour.

## Severity and repair rules
BLOCKER or unsafe HIGH → stop (stop rules in the reactivation document). No fixes between participants unless a blocker prevents the remaining pilot; any material runtime fix → new RC (expected RC-P10-004) and no mixing without version stratification. Non-blocking findings are triaged after all sessions.

## Tracked results (real denominators)
Completion; unassisted completion; rescue level; repeated confusion; issue category; severity; trust/privacy comprehension; score/feedback comprehension; evidence/source comprehension; language; device condition. Template: `RC_P10_003_PILOT2_RESULTS_TEMPLATE.md` (empty).

## Human-evidence privacy
Never commit real names, participant emails, real CVs or job documents, raw recordings, raw transcripts with identifying content, identifiable screenshots or other private information. Use P01…; synthetic assets by default; raw evidence stays outside git; committed results contain only the minimum anonymised findings (`../pilot_data_handling.md`).
