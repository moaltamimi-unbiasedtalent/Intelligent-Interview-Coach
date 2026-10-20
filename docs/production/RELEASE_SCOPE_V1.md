# Release Scope: R1.0 (Roadmap V2.2, corrected)

**Status:** corrected 2026-10-21 against the owner's authoritative requirements (`OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md`). Target 30 November 2026. R1.0 is a **free, invitation-only private production beta** with no live customer payments. The date is the owner's target; safety and legal gates are not waived. Counts are as generated 2026-10-21; the dashboard is authoritative.

## 1. In scope

| Area | R1.0 scope | Requirement rows | WP |
|---|---|---|---|
| Access | Invitation-only registration, no open sign-up, no payment path | REQ-BETA-01, OD-INVITE | WP-03 |
| Languages | English, German, Spanish, Italian, Portuguese, French, Dutch, each activated only when LG-01 to LG-14 pass for it | REQ-LANG-01 to 14 | WP-08 |
| Markets | Selected EU countries (proposed mappings, individually approved and source-qualified before use); language never selects geography | REQ-LANG-07, REQ-LANG-16, REQ-COV-02 | WP-06, WP-08 |
| Candidate journeys | Registration, onboarding, Opportunities, Mo preparation with real agent and tools, source-backed evidence, Practice and Deep Dive, structured feedback, History, Progress, privacy controls, accessible responsive navigation, useful error recovery | REQ-CAND-01, DEMO-02 | WP-07 |
| AI reviewer corrections | Injection defence depth; versioned prompts; tool catalogue parity; embedding integrity; agent streaming | REVIEW-01 to REVIEW-05 | WP-05, WP-06, WP-17 |
| Story Bank | Manual and evidence-drafted STAR stories with provenance, Opportunity links, Practice reuse and feedback | REQ-OWN-06 | WP-09 |
| Workspaces | Invitations, membership, ownership transfer, explicit VIEW-only sharing, immediate revocation | REQ-OWN-07 | WP-09 |
| Knowledge Sources | Persistent registry, files and indexes; curated and governed views; environment identity; restore drills; real malware scanning; alerts | REQ-OWN-05 | WP-06 |
| Admin 2.0 (English-only, owner-operated) | Grouped navigation and relocated Review and Diagnostics; Command Center; Basic/Premium plan management; user management; AI operations | REQ-OWN-01, 02, 03, 08 | WP-10 |
| Reporting | Prebuilt aggregate reports and a governed custom builder with small-cohort suppression | REQ-OWN-04 | WP-10 |
| Plans | Existing Basic and Premium as free beta tiers; which entitlements are enforced is OD-PLAN-ENFORCE | REQ-OWN-02 | WP-10 |
| Privacy, legal, operations | Data rights; legal documents qualified per offered language; hosted deployment, monitoring, backup, restore, rollback | PG-01, PG-04, PG-09 | WP-02, WP-04 |
| Human validation | Independent human evaluation per language; named reviewers and native reviewers | PG-07, REQ-LANG-09 | WP-14 |
| Coverage | A separate frozen beta-scope coverage measure beside the preserved historical gate | REQ-COV-01 | WP-06 |

## 2. Out of scope for R1.0 (valid only while the feature is inaccessible through UI and API)

| Feature | Release | Disabled by |
|---|---|---|
| Live billing, Stripe, paid plans, pricing, tax, cancellation, refunds, new plan families | R1.1 | `LIVE_BILLING_ENABLED`, `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`, `RECONCILE_SCHEDULER_ENABLED`, `PROVIDER_READS_AUTHORIZED` (all False) |
| Scheduled reporting, advanced analytics, automation, bulk administration extensions | R1.2 | not built or not enabled |
| Mandarin, Hindi, Arabic | R1.3 | no locale registered in `src/locales.py` |
| Server speech, qualified STT and TTS, live voice practice | R1.4 | `SERVER_SPEECH_PROVIDERS_AUTHORIZED`, `WHISPER_API_TRANSPORT_AUTHORIZED`, `MODEL_DOWNLOADS_AUTHORIZED`, `VOICE_CLONING_ENABLED` (False); browser dictation and speech output stay governed and disclosed |
| Additional-country coverage and global provenance | R1.5 | international sources not operational |
| Compensation Intelligence V2 | R1.6 | Compensation V2 not operational |
| Enterprise Workspaces, organization subscriptions, SSO | R1.7 | not enabled |
| Expanded career platform | R2.0 | not built |
| Russian | unscheduled (separate future decision) | removed from active Candidate selection (REQ-LANG-14); code preserved |
| History-window and model-profile gating | with OD-PLAN-ENFORCE | `HISTORY_RESTRICTIONS_ENFORCED`, `MODEL_PROFILE_ENFORCED` (False) |

Disabled Compensation V2 and speech must not block shipping an unrelated safe beta feature (REQ-SCOPE-01), provided REQ-DEFER-01 proves their UI and API entry points are unreachable. A safety, privacy or operational dependency is never deferred while its feature is enabled.

## 3. Numbers (2026-10-21)

88 items to fix and 74 to verify before R1.0 (P0 12, P1 86, P2 53, P3 11 across both); 95 items with an OWNER DECISION disposition (including 15 unscheduled: 6 academic-only retirements and future-Russian items); 143 deferred to R1.1 to R2.0; 52 closed with evidence preserved; 0 unmapped.

## 4. Exit criteria

All FIX items closed with evidence at one release SHA; all VERIFY items verified; PG-01 to PG-15 met with real evidence; LG-01 to LG-14 met for every language activated; the five reviewer findings closed to their numbered criteria; the owner-requested capabilities' acceptance journeys pass in the browser; the machine check passes; all gate constants for deferred features are False and their UI/API entry points proven unreachable; no claim exceeds evidence; owner go/no-go recorded. A mandatory safety, privacy, licensing or operational gate is never waived by an accepted limitation; the owner may instead remove a feature or delay activation.
