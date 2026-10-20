# Release Scope: R1.0 (Roadmap V2.2)

**Status:** PROPOSED for owner review, 2026-10-21. Target date 30 November 2026. R1.0 is the first release to real users; the capstone submission was a controlled academic scope and is not this release. Counts below are as generated on 2026-10-21; `RELEASE_BLOCKER_DASHBOARD.md` is authoritative.

## 1. In scope

| Area | R1.0 scope | Work package |
|---|---|---|
| Languages | English, German, Spanish, Italian, Portuguese, French, Dutch, each only if all gates LG-01..LG-14 pass (see `MULTILINGUAL_RELEASE_QUALIFICATION.md`) | WP-08 |
| Candidate journeys | Onboarding, Opportunity, Company research (link-out sources), Prepare with Mo, Practice, History, Progress, Documents, privacy controls | WP-07 |
| Story Bank and Workspaces | Owner-private by default; VIEW-only sharing; candidate controls to invite members and share reports and stories (open requirement N-category) | WP-09 |
| Reports | Candidate report export; Admin aggregate reports with cohort suppression | WP-09, WP-10 |
| Knowledge | Curated corpus plus governed sources; qualification of sources for the seven proposed markets (Ireland, Germany, Spain, Italy, Portugal, France, Netherlands); unapproved knowledge never reaches candidates | WP-06 |
| AI | Live Mo (real agent, retrieval, citations, abstention, human approval) and Practice; grounding, injection and privacy policies verified per language | WP-05 |
| Admin (English-only) | Admin 2.0 areas named by the owner: Plans, Users, Reports, Knowledge, navigation; permissions, audit and no candidate-content access preserved. Requirement text is outstanding (OD-REQ-TEXT) | WP-10 |
| Identity and email | Live verification email and recovery; Google sign-in only if validated, otherwise disabled | WP-03 |
| Privacy and legal | Data rights, retention, legal documents qualified in each offered language | WP-04 |
| Operations | Authorised hosted environment, TLS/HSTS, backup and restore, rollback, monitoring, incident process | WP-02 |
| Human validation | Named reviewers (A, B, C), native-language reviewers, legal qualifiers | WP-01, WP-14 |
| Measurement | Bounded live evaluations with identity recorded; RAGAS only as a secondary, honestly labelled layer | WP-16 |

## 2. Out of scope for R1.0 (deferral valid only while the feature stays disabled)

| Feature | Release | Disabled by |
|---|---|---|
| Live billing, Stripe checkout and webhooks, paid plans, tax, refunds in production | R1.2 | `LIVE_BILLING_ENABLED`, `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`, `RECONCILE_SCHEDULER_ENABLED`, `PROVIDER_READS_AUTHORIZED` (all False) |
| Server speech (Whisper, Kyutai), realtime voice | R2.0 | `SERVER_SPEECH_PROVIDERS_AUTHORIZED`, `WHISPER_API_TRANSPORT_AUTHORIZED`, `MODEL_DOWNLOADS_AUTHORIZED`, `VOICE_CLONING_ENABLED` (all False). Browser dictation and speech output stay governed and disclosed |
| Basic/Premium history and model-profile gating | with commercial activation | `HISTORY_RESTRICTIONS_ENFORCED`, `MODEL_PROFILE_ENFORCED` (False) |
| Knowledge and compensation outside the seven markets; Compensation V2 output | R2.0 | Compensation V2 and international sources not operational |
| Later integrations (Adzuna live, external paging) | R1.2 | not configured |
| Russian | R2.0 | must be hidden from candidate language choices (REQ-LANG-14) |
| Mandarin, Hindi, Arabic | R1.3 | no locale registered |

Rule 10 of the reconciliation: a safety, privacy or operational dependency is never deferred while its feature stays enabled. `reconcile_issues.py check` verifies the gate constants above are False for every deferral that relies on them.

## 3. R1.0 numbers (2026-10-21)

70 items to fix, 74 to verify (7 at P0, 74 at P1, 52 at P2, 11 at P3 across both), 91 owner decisions (72 historical plus 19 new), 146 deferred to later releases, 52 closed with preserved evidence, 0 unmapped. This is more than five weeks of work for an unnamed team: OD-SCOPE-01 asks the owner to hold the date and re-scope, move the date, or release a subset.

## 4. Release exit criteria

All FIX items closed with evidence at the release SHA; all VERIFY items verified or explicitly accepted by the owner with a recorded limitation; per-language gates passed for every offered language; all general production gates PG-01..PG-11 met; owner decisions resolved; the machine check passes; every gate constant for a deferred feature is False; no claim exceeds evidence.
