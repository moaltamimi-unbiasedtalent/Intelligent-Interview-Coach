# Ask4Mo Capstone — Phase Plan (P0–P11 / E0–E8)

Refines the reference plan against verified repository dependencies. Each phase: objective, scope,
dependencies, expected changes, gates, STOP/must-not-start. Dates are targets (24 Sep → 20 Oct), not
effort guarantees; feasibility checkpoints 4 Oct / 8 Oct / 13 Oct freeze. Do not relabel incomplete
work as deferred to manufacture a verdict.

## Critical path
Identity/authorization (P1) is the spine — documents, evidence, teams, entitlements, admin, hosting
all depend on it. Knowledge expansion (K1–K4) and marketing IA can proceed partly in parallel.

## Phases
**P0+E0 — Baseline & feasibility (this phase).** Objective: establish current state, reconcile
requirements, target architecture, data/security/privacy/product/provider/evaluation plans, risks,
DoD, presentation standard. Gate: evidence-backed feasibility verdict + P1 entry criteria. STOP: no
feature implementation.

**P1+E1 — Identity & platform foundation.** Real accounts (register/verify/recover/login/logout/
expiry), ownership on all paths, authorization dependency (ownership+role+entitlement+flag), platform
roles, workspace-role + entitlement + audit foundations, public/authenticated route boundary. Deps: P0.
Changes: `src/auth.py`, new migrations, `src/api` middleware, `frontend (marketing)/(app)` groups.
Gate: two-user negative tests, logout/expiry, migration/backup proof, no cross-user leak. STOP: no
docs/OCR/teams/speech/admin-console/marketing yet.

**P2 — Return journey on accounts.** Preserve History/Progress/Sources; add A2 active-session
discovery; distinguish live KB readiness from snapshots. Deps: P1. Gate: AC-04/05/06/07.

**P3+E-dictation — Reusable UI + dictation control.** Two real natural-language dictation surfaces,
editable transcript, no auto-submit, race/cancel handling. Deps: P1. Gate: AC-11/12.

**P4+E2+E3 — Documents, OCR, story bank, export/deletion.** Private PDF/DOCX/TXT upload + native
extraction, OCR for scanned, evidence/story bank, A9 export/delete. Deps: P1. Gate: AC-08/09/10,
EX-01/03/08. STOP: realtime voice/teams not required here.

**P5+E4 — Bounded multi-agent + per-op model policy.** Mo + Research/Candidate/Preparation/Evaluation
specialists (only if justified), typed hand-offs, budgets, single-agent baseline comparison; C8 server
model policy. Deps: P1, P4. Gate: AC-15/16/22, EX-05/09. Freeze comparison tasks before eval.

**P6+E6+E7 — Platform ops & collaboration.** Teams/workspaces + sharing/revocation, retention/cleanup,
privacy operations, **Admin Console**, user/tier controls, K1–K4 knowledge expansion, Prompt Lab,
owned run discovery (A6), truthful A7/A8 artifact visibility. Deps: P1, P4, P5. Gate: EX-06/10/11/13–16,
admin neg tests.

**P7+E5 — Speech / recorded Practice.** Recorded answers → STT → existing evaluation first; spoken
questions (TTS); EN/DE; then realtime (C1) if feasible; audio/transcript lifecycle. Deps: P1, P4.
Gate: AC-13/14/23, EX-02/04.

**P8+E8 — Productisation.** Marketing website, pricing/trust/privacy public surfaces, hosting (private
staging → authorized public), production auth hardening, rate limits, SEO/accessibility, entitlement
enforcement at prod. Deps: all prior. Gate: EX-12, AC-19/25.

**P9 — Integrated quality/UX hardening.** Security/retrieval/session/document/speech integration +
controlled agent evaluation tied to exact code. Gate: AC-21/22.

**P10 — Capstone evaluation + live golden.** Real pilot + priority repairs; one authorized live golden.
Gate: AC-24 + acceptance evidence.

**P11 — Submission packaging.** Presentations, implementation stories, requirements matrix, architecture,
evidence, demo script, reviewer guide, final readiness, release/tag. Gate: AC-25.

## Per-phase Definition of Done
See `capstone_definition_of_done.md` (applies to every implementation phase P1+).
