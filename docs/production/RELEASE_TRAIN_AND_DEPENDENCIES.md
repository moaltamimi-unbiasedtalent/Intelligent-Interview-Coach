# Release Train and Dependencies (Roadmap V2.2)

**Status:** PROPOSED, 2026-10-21. The owner fixed R1.0 (30 November 2026, all seven languages) and R1.3 (Mandarin, Hindi, Arabic). R1.1, R1.2 and R2.0 themes are proposals (OD-RELEASE-TRAIN).

## 1. Train

| Release | Date | Theme | Items (2026-10-21) |
|---|---|---|---|
| R1.0 | 30 November 2026 | First production release: seven languages (each only if its gates pass), safety, privacy and operations blockers, English-only Admin | 144 fix/verify plus owner decisions |
| R1.1 | proposed: after R1.0, date not set | Post-launch stabilisation: operational depth, accessibility and performance polish, non-safety technical debt | 94 |
| R1.2 | proposed | Commercial activation (billing, Stripe, paid plans) and later integrations, behind owner approval | 15 |
| R1.3 | proposed | Mandarin, Hindi, Arabic: new engineering and human qualification per language | 2 (plus REQ-LANG-15) |
| R2.0 | proposed | International knowledge and compensation beyond seven markets, server speech and realtime voice, Russian, enterprise | 35 |

No dates are invented for R1.1 to R2.0.

## 2. Dependency graph (R1.0)

```
Owner decisions (OD-SCOPE-01, OD-LANG-01..05, OD-REQ-TEXT, OD-HOSTED, OD-BUDGET)
   |-- name people: reviewers A,B,C; 7 native reviewers; legal/privacy qualifiers ----+
   |-- hosted environment authorised -> WP-02 rehearsal (TLS, backup, rollback) ------+
   |-- Admin requirement text -> WP-10 Admin 2.0 -------------------------------------+
   v                                                                                   |
WP-08A locale audit -> WP-08B boundaries (hide Russian) -> WP-08C journeys             |
                      -> WP-08D AI behaviour -> WP-08E retrieval (needs WP-06) -------+--> freeze
                      -> WP-08F security/privacy suites                                |
WP-06 seven-market source qualification (licence, authority, coverage) ---------------+
WP-03 live email / OIDC (owner-authorised) --------------------------------------------+
WP-08G native review + legal translation (LONG LEAD, human) ---------------------------+
WP-16 bounded live evaluation (needs OD-BUDGET) ---------------------------------------+
                                                                                       v
                                              hosted rehearsal -> RC candidate -> owner go/no-go -> 30 Nov
```

## 3. Critical path to 30 November (proposed)

| Window | Critical activity | Blocking dependency |
|---|---|---|
| 21-25 Oct | Owner reviews the reconciled baseline; decides OD-SCOPE-01, OD-LANG-01..06, OD-HOSTED, OD-BUDGET, OD-REQ-TEXT; names reviewers and qualifiers. No production implementation starts before the baseline is reviewed | Owner |
| 26 Oct-1 Nov | WP-08A audit; WP-08B hide Russian; WP-02 environment stand-up; WP-03 live email; start native and legal review scheduling (long lead) | OD-HOSTED, named reviewers |
| 2-15 Nov | Per-language journeys, policies, interview quality, injection and privacy suites (WP-08C-F); WP-06 seven-market qualification; Story Bank/Workspaces/Reports fixes; Admin 2.0 once requirement text exists | Reviewer availability; source licences |
| 16-22 Nov | Native-language review and legal translation qualification; bounded live evaluations; hosted rehearsal; fix findings | Human reviewers (the most likely schedule failure) |
| 23-27 Nov | Freeze, release-candidate evidence at one SHA, reconciliation check, owner go/no-go | All gates |
| 30 Nov | R1.0 release, only the languages whose gates passed | Owner approval |

The date is at risk: the human steps cannot be compressed by engineering, and the fix/verify count is large. A language that is not qualified by the freeze is not offered (OD-LANG-01).

## 4. Cross-release dependencies

- Compensation V2 and any international source need Release Approver (C) and human review before any exposure (R2.0).
- Billing activation (R1.2) needs the legal seller entity, product classification and tax decisions (F2B1-OD-01..), live provider qualification and a distinct approval; history and model-profile gating enforcement ride with it.
- Server speech (R2.0) needs the Whisper hosting decision and genuine model execution validation.
- Mandarin, Hindi and Arabic (R1.3) need script, RTL and tokenisation engineering plus native and legal review per language; speech support for any of them is a separate decision.
