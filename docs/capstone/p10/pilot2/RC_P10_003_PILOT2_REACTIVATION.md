# Pilot 2 reactivation for RC-P10-003

**Status on this branch: PILOT 2 REACTIVATION PREPARED.** After this preparation PR is merged: **PILOT 2 READY FOR HUMAN SESSIONS** (sessions start only when the owner explicitly starts them). **Human evidence: NONE YET.** **AC-24: NOT RUN / PENDING REAL PARTICIPANTS.** Pre-merge verdict: **PILOT 2 REACTIVATION READY TO MERGE.**

This wave is documentation and templates only. It is not a Pilot 2 session, product remediation, a new RC, P10C, live-provider validation, a deployment or a launch. No product or runtime code changed.

## Candidate
- **Candidate:** RC-P10-003 (artifact RC, not a Git tag) — `artifacts/capstone/p10/RC-P10-003/`, narrative `../RC_P10_003_RELEASE_CANDIDATE.md`.
- **Candidate SHA (the ONLY product version any participant may test):** `54aad500ec937b4828984c32c64b77746534633d`.
- Qualified runtime merge `d27993d7f2757cf7605355e3f76c71dac6f85c10`; artifact PR #134 (merge `800a10d8`); RC docs PR #135 (merge `8f8aec8a`). Later commits on main are artifacts/docs/evaluators, not the candidate identity: do not test current main.

## Why Pilot 2 was paused
After RC-P10-002 (`ab9ff73`) the owner's review required candidate remediation (W9), a stable Admin/support/privacy plane (W10) and a full integrated qualification (W11) before any human exposure, so a pilot would not run against a candidate that was about to change.

## Prerequisites now satisfied
- **W9 remediation** (W9.1–W9.13): resilience, recovery, security hygiene, Opportunity discoverability, Welcome/Tutorial v2, full localization (8 interface locales incl. Russian), privacy and data controls, trust polish, requalification.
- **W10 Admin stabilization** (W10.0–W10.14): Admin platform qualified; candidate-facing support, privacy and billing boundaries stable.
- **W11 integrated qualification:** W11 COMPLETE AND INTEGRATED — 99 requirements: 88 PASS / 11 ACCEPTED / 0 BLOCKER.
- **RC-P10-003 CREATED / CURRENT.**

## What is still NOT validated
Human usability (no participant has used this candidate); live providers (0 paid/live calls; live generated-language quality, live voice/realtime, OIDC, live email); native/legal language review (R-49); distributed rate limiting and PostgreSQL-only paths (R-46, R-96); hosted operation/deployment; email verification is not required to sign in (R-33); support attachments (R-93); billing is mock (R-95); cross-browser (Chromium only). The 11 ACCEPTED limitations stand and are not upgraded by this wave.

## Human evidence requirement
Only real, consented participants produce Pilot 2 evidence. Target 3–5 (anonymised P01…P05). With fewer than 3 completed sessions Pilot 2 is INCOMPLETE. Nothing may be fabricated, simulated or back-filled. AC-24 changes only on real observations.

## Stop rules
Stop all further participant exposure immediately on: a P0 security issue; data loss; cross-user private-data exposure; broken authentication preventing safe use; broken core Interview Practice; any other unsafe BLOCKER. Do not patch RC-P10-003 silently.

## RC freeze rule
A material runtime fix means RC-P10-003 is no longer the tested candidate for later participants. Sequence: fix → targeted/full qualification as appropriate → NEW RC (expected RC-P10-004) → resume remaining participants only after owner approval. Results from different RCs are never aggregated without explicit version stratification. Documentation-only changes do not alter the candidate.

## Companion documents
`RC_P10_003_PILOT2_READINESS.md` (methodology, taxonomy, targets), `RC_P10_003_PILOT2_RUNBOOK.md` (environment gate, per-session procedure), `RC_P10_003_PARTICIPANT_TASKS.md` (current T1–T9 + T3a journey), `sessions/P01_RC_P10_003_TEMPLATE.md`, `RC_P10_003_PILOT2_RESULTS_TEMPLATE.md`. The historical RC-P10-002 pack (`pilot2_readiness.md`, `pilot2_runbook.md`, `sessions/P01_pilot2_template.md`) is preserved unchanged as immutable evidence. Stable shared kit (still valid): `../participant_notice.md`, `../pilot_data_handling.md`, `../moderator_guide.md`, `../observation_template.md`, `../issue_log_template.md`, `../assets/pilot_*.md`. (`../environment_check.md` and `../participant_tasks.md` describe earlier candidates; this pack supersedes them for RC-P10-003.)

## Readiness verdict
Engineering and methodology prerequisites are met and the pack is self-consistent: **PILOT 2 REACTIVATION READY TO MERGE** (pre-merge) → **PILOT 2 READY FOR HUMAN SESSIONS** (post-merge, owner starts sessions).
