# Release Train and Dependencies (Roadmap V2.2, corrected)

**Status:** corrected 2026-10-21. The release train below is the owner's agreed train (`OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md` section 8). **All dates after R1.0 are indicative planning windows, not fixed promises.** R1.0 on 30 November 2026 is the owner's target; safety and legal gates are not waived to meet it.

## 1. Agreed train

| Release | Window | Content | Rows (2026-10-21) |
|---|---|---|---|
| R1.0 | 30 November 2026 | Free private production beta: seven languages each individually qualified; selected qualified EU markets; Admin English-only with owner-operated Platform Admin and RBAC; core Candidate functionality; Admin 2.0 essentials; reliable Knowledge Sources; Story Bank and Workspaces; core reporting; five reviewer corrections; secure hosting, privacy and operations; no live billing | 197 (88 fix, 74 verify, rest owner decisions and gates) |
| R1.1 | indicative December 2026 | Paid beta and plan expansion: Stripe and subscription lifecycle only after provider and legal qualification; pricing, tax, cancellation, refunds, reconciliation; new plan families; expanded commercial entitlements | 132 |
| R1.2 | indicative December 2026 to January 2027 | Advanced Admin and automation: scheduled reporting, advanced custom analytics, operational automation, enhanced bulk administration, expanded alerts | 19 |
| R1.3 | indicative January to February 2027 | Mandarin, Hindi, Arabic: new locale, prompt, safety, retrieval, accessibility, legal and native review; RTL for Arabic | 3 |
| R1.4 | indicative February 2027 | Voice interview experience: qualified STT, TTS, live voice practice; licensing and consent; latency and accessibility; native speech quality | 23 |
| R1.5 | indicative February to March 2027 | Global career intelligence: additional countries, qualified occupational sources, provenance, multilingual geographic retrieval | 7 |
| R1.6 | indicative March 2027 | Compensation Intelligence V2: qualified salary datasets, geographic comparison, freshness, methodology, legal and human evidence approval | 2 |
| R1.7 | after R1.6, date not committed | Teams and enterprise: enterprise Workspaces, organization subscriptions, advanced collaboration, SSO and governance, qualified integrations | 1 |
| R2.0 | evidence-led, subsequent | Expanded intelligent career platform: personalized guidance, agentic workflows, deeper career development | 1 |
| unscheduled | n/a | Owner decisions with no release: six academic-only capstone tasks awaiting retirement confirmation; future Russian activation | 15 |

R1.1 holds the agreed paid-beta content plus items that fit no agreed theme (placement proposed, OD-DEFER-PLACEMENT); R1.2 additionally holds Admin items with no theme. R1.7 and R2.0 hold only the owner-stated scope rows, because no historical issue belongs there. Russian is excluded from R1.0 and is **not** an automatic R2.0 commitment.

## 2. Dependency graph (R1.0)

```
Owner decisions: OD-SCOPE-01, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-INVITE, OD-MALWARE, OD-PLAN-ENFORCE,
                 OD-LANG-02..04 (markets, native reviewers, legal qualifiers), OD-COVERAGE
   |
   |-- hosted environment (PG-01) ---------------------------------------------+
   |-- invitation-only registration (REQ-BETA-01, PG-02) ----------------------+
   |-- Knowledge persistence + REVIEW-04 embedding integrity (PG-05) ----------+--> real-user candidate journeys (PG-06)
   |       manifest, restore drills, malware scanning, alerts                  |
   |-- REVIEW-01 injection depth (PG-03) --------------------------------------+
   |-- REVIEW-02/03 prompt versioning + tool parity (PG-12) -------------------+
   |-- REVIEW-05 streaming (PG-06) --------------------------------------------+
   |-- Story Bank + Workspaces (REQ-OWN-06/07, PG-13) -------------------------+
   |-- Admin 2.0: nav, Command Center, plans, users, reports (PG-08, PG-14) ---+
   |       (reports need metric sources; Command Center needs AI/usage facts)  |
   |-- per-language gates LG-01..14 (human + legal, LONG LEAD) ----------------+
   v                                                                            v
 backup/restore/rollback drills (PG-09) ---------------------------------> free beta operational acceptance (PG-15)
                                                                                |
                                                          owner go/no-go at one SHA -> invite beta users
```

## 3. Critical path to 30 November (proposed)

| Window | Critical activity | Blocking dependency |
|---|---|---|
| 21-25 Oct | Owner reviews this baseline; decides OD-SCOPE-01, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-INVITE, OD-MALWARE, OD-PLAN-ENFORCE; names reviewers, native reviewers and legal qualifiers. Production implementation starts only after the baseline is reviewed | Owner |
| 26 Oct-1 Nov | Hosted environment stand-up; invitation-only registration; REVIEW-01 corpus build and detector baseline; REVIEW-04 embedding provider and manifest design; locale audit and removal of Russian from selection; Admin navigation design | OD-HOSTED, OD-INVITE |
| 2-15 Nov | Knowledge persistence and restore drills; REVIEW-02/03 loader and parity; REVIEW-05 SSE; Story Bank and Workspace completion; Admin plans, users, Command Center, reports; per-language journey and policy suites | Reviewer availability; budget for semantic embedding builds |
| 16-22 Nov | Held-out injection gate in CI; human AI evaluation per language; native review; legal translation qualification; hosted rehearsal including restore and rollback; fix findings | Human reviewers and legal qualifiers (the longest lead, not compressible by engineering) |
| 23-27 Nov | Freeze at one SHA; release evidence; reconciliation check; owner go/no-go | All mandatory gates |
| 30 Nov | Invite beta users, only in languages whose gates passed and with only qualified markets | Owner approval |

This is not a feasibility statement: the R1.0 list is large and the human steps cannot be compressed. If a mandatory gate is not met the owner chooses among delaying R1.0, removing the affected feature from scope, or keeping it disabled (OD-SCOPE-01); an accepted limitation never replaces a mandatory safety, privacy, licensing or operational gate.

## 4. Cross-release dependencies

- R1.1 billing needs the legal seller entity, product classification, tax decisions and provider qualification (F2B1-OD-01 onward) and a distinct approval; history and model-profile enforcement ride with OD-PLAN-ENFORCE.
- R1.4 voice needs the Whisper hosting decision, genuine model execution validation, licensing, consent and native speech quality evaluation.
- R1.5 needs source licences and qualification per country; R1.6 needs R1.5 sources plus legal and human evidence approval.
- R1.3 needs script, RTL and tokenisation work and native plus legal review per language.
- R1.7 builds on completed Workspaces (R1.0) and qualified billing (R1.1).
