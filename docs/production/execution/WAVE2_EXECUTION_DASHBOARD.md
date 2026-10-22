# Wave 2 Execution Dashboard (final)

Final merged state, 2026-10-22. Strategy S1 (full R1.0 scope, owner-approved). Target 30 November 2026, conditional on every mandatory gate. Main @ `e4aed13` (merge of PR #233). **No open PR.** Wave 3 is planned in `WAVE3_EXECUTION_PLAN.md` and has not started.

## 1. Merged

| PR | Package | Branch | Head | Merge SHA | Opened to merged (UTC) | Rework rounds after open |
|---|---|---|---|---|---|---|
| #222 | PREP (version-independent head checks, lead prep) | chore/migration-head-agnostic | ec14963 | f4c7136 | 1h06m | 0 |
| #223 | 01A injection corpus, risk score, quarantine | feat/01a-injection-corpus | b3acd4b | 7549973 | 1h07m | 0 |
| #224 | 03D1 Command Center metrics (backend) | feat/03d1-command-center-metrics | 89f6e66 | ac029ad | 1h09m | 0 |
| #225 | Wave 2 baseline docs | docs/wave2-baseline | b344d16 | b5a5231 | 1h06m | 0 |
| #226 | 02C real ClamAV scanning | feat/02c-clamav-scanning | 164d839 | 568b8f3 | 1h07m | 0 |
| #227 | 02B embedding integrity and manifests | feat/02b-embedding-integrity | 135070c | 6acdbc1 | 1h08m | 0 |
| #228 | 04E invitation-only registration | feat/04e-invitation-only | 9d390df | a763fdf | 1h43m | 1 (unmocked listing crashed Admin Users; migration renumbered 0041 to 0042) |
| #229 | 06H language activation control | feat/06h-language-activation | a0d01c8 | 5d588a1 | 0h52m | 0 |
| #230 | 03B Admin plans | feat/03b-admin-plans | 01da216 | a4f540d | 2h47m | 1 (merge conflict; branch-relative test) |
| #231 | 03C Admin users | feat/03c-admin-users | 94b76b7 | 6bcfbf5 | 3h15m | 1 (two concurrency schemes reconciled with 03B) |
| #232 | 03E1 reports builder (backend) | feat/03e1-reports-builder | 0c3638b | 0d84e7e | 0h41m | 0 |
| #233 | 04B Workspaces | feat/04b-workspaces | c73a728 | e4aed13 | 3h28m | 1 (consent and verified-invitation rules reconciled with 04A) |
| #234 | 04A Story Bank | feat/04a-story-bank | e32010a | 4d7e57a | 1h47m | 2 (migration renumber and merge; a test raced the loading state) |

All thirteen merged after green GitHub CI (12 of 12 checks on the final PR head of each). Migration chain: `0040`, `0041_report_configurations` (03E1), `0042_registration_invitations` (04E), `0043_story_bank_completion` (04A); one head.

## 2. What the merges delivered (offline engineering scope)
- **Security and AI:** labelled injection corpus with a frozen held-out split, retrieval quarantine, measured recall and false-positive rates (report only); hosted fail-closed embedding enforcement with persisted index manifests; real clamd protocol client with fail-closed uploads; invitation-only registration; fail-closed language activation.
- **Admin 2.0:** Command Center metrics backend (61 metrics, 8 GET routes), plan management (matrix, compare, preview, bulk, rollback), user management (7 strict action routes), reports registry, governed builder, saved configurations and CSV/JSON export (20 routes). Permission registry stays 44.
- **Candidate:** Story Bank completion (archive, evidence links, consented reuse and sharing, derived verification), Workspaces completion (roles, verified-email invitations, consent-gated view-only sharing, revocation and deletion paths).

## 3. What the merges did NOT deliver (each is a layer in `WAVE3_EXECUTION_PLAN.md` section 3)
No live staging verification of anything (nothing is deployed); no production-embedder benchmark; no real clamd run; no human security review of 01A; no approved thresholds; no native or legal review; no language qualified; no gate other than PG-11 passed. Open scope gaps inside merged packages: Prepare per-story consent (04A), bulk user actions (03C), invitation email (04E), export formats beyond CSV and JSON (03E1), plan limit values (03B).

## 4. Measured throughput (PR timestamps UTC 2026-10-22; authoring minutes from the agents' start-to-first-push records)
Authoring 28 to 73 minutes per package (nine ran concurrently); PR open to merge 41 minutes to 3 hours 28 minutes, average about 1 hour 38 minutes. Five of the thirteen needed one or two rework rounds after opening. Combined with Wave 1: 20 packages, 12 rework rounds. The estimates in the register (2 to 15 engineering days) include review, CI and integration; the observed engineering cost is far lower for contracts, backends and scaffolds, but nothing in Waves 1 and 2 needed a human qualifier, a licence, live staging or a paid call, so it says nothing about those.

## 5. Dashboard fields for Wave 3
Packages started: none. Next packages ready: 08A0, 05B, 05C, 05E, 06C, 01D, 03D2, 03E2 (Wave 3a, eight concurrent), then 01C, 06E, 06B, 06D, 05D, 07A, 04D, 04F, 02E, then 04C, 07B, 07C, 06G, 08A. Human and owner blockers and the dated start-by list: `WAVE3_EXECUTION_PLAN.md` section 7. Gate status changes in Wave 2: PG-02, PG-03, PG-05, PG-08, PG-10, PG-12, PG-13 and PG-14 moved from NOT STARTED to IN PROGRESS; none passed. Critical-path forecast: `WAVE3_EXECUTION_PLAN.md` section 8.
