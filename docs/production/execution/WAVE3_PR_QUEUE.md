# Wave 3 PR queue (2026-10-22)

> Current integration (23 October 2026): **40/45** engineering packages merged at `aedbef3d`, including PR #265. Main CI SUCCESS; PR #265 Browser SUCCESS on an identical tree (no main Browser run). Gate and language approvals unchanged. See [current release status](POST_PR265_RELEASE_STATUS.md); the dated planning narratives below are historical.

Twenty-eight Wave 3 branches are pushed; none has a pull request yet because the lead has no GitHub CLI, token or signed-in browser. **The owner opens each PR from the compare URL `https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/<branch>`**; the lead then verifies GitHub CI and mergeability. Every head below was verified on `origin`. "Local" results are not CI. Nothing is merged and no gate changed.

| # | Branch | Head | Base | Migration | Notes |
|---|---|---|---|---|---|
| 0 | docs/wave3-authorization | 842cfda | main | none | docs only (Wave 3a authorisation record, whole-project dashboard, provisional decisions) |
| 1 | feat/08a0-release-evidence | 25d5280 | main | none | evidence ledger and checker; offline |
| 2 | feat/03d2-command-center-views | 428ca83 | main | none | frontend only |
| 3 | feat/01d-tool-authorization | 2890d6e | main | none | **security-critical**; owns src/agent/*; unlocks 01C, 04C, 07B; human security review pending |
| 4 | feat/03e2-report-views | 396786d | main | none | PR 1 of 2 |
| 5 | feat/03e2-pdf-export | 4ddc628 | PR 4 | none | PR 2 of 2 |
| 6 | feat/05c-budget-governor | 84c7c04 | main | **0044_ai_budget_ledger** | PR 1 of 2; the OpenRouter spend control; unlocks the governed benchmark |
| 7 | feat/05c-monitoring-alerts | aaf18c0 | PR 6 | **0045_monitoring_alert_categories** | PR 2 of 2 |
| 8 | feat/05d-identity-live | 1cfeebc | main | **0044_email_delivery_events** (renumber to 0046) | claims 0044 too |
| 9 | feat/05e-privacy-safeguards | bb12d2a | main | none | PR 1 of 2; edits a pin in the 03D1 test and suppression code: human review |
| 10 | feat/05e-legal-review-pack | 7fc34cd | main | none | PR 2 of 2; regenerate after any Terms text change |
| 11 | feat/02e-retrieval-quality | 66ffa95 | main | none | edits 3 pinned requalification cases (ratchet): confirm |
| 12 | feat/06d-multilingual-retrieval | 51479e9 | PR 11 | none | stacked on 02E |
| 13 | feat/02b-openrouter-embeddings | 9fbc3d3 | PR 6 | none | stacked on 05C PR 1 |
| 14 | feat/06c-language-ai-behaviour | fa9f02a | main | none | one CI step, prompts pointer, family count 44 to 45 |
| 15 | feat/06e-language-security-suites | ea0ea55 | main | none | turns the multilingual input guard ON by constant: ratify (OD-INPUT-GUARD-LANGUAGES) |
| 16 | feat/07a-deferral-inaccessibility | b00bbbd | main | none | fixes real blocking calls in async routes: review production diffs |
| 17 | feat/04f-dictation-disclosure | 0633ce9 | main | none | review-ready; copy patch not applied |
| 18 | feat/06b-language-journeys | c132289 | main | none | modifies one onboarding assertion; localisation fixes |
| 19 | feat/04d-journey-tests | 67ef7c4 | main | none | PR 1 of 2 |
| 20 | feat/04d-provider-mode-and-guards | 5fc0ad8 | PR 19 | none | PR 2 of 2; removes price figures from candidate copy: confirm 3 assertion changes; touches src/agent/models.py |
| 21 | feat/05b-backup-restore-drills | 9820024 | main | none | drills; PostgreSQL tests skip without TEST_DATABASE_URL |
| 22 | feat/03c-bulk-user-actions | a838dbd | main | none | two reversible bulk actions only (force sign-out, expire verification); OD-BULK-ACTIONS provisional |
| 23 | feat/04b-ownership-transfer | 6c8e7ad | main | **0044_workspace_ownership_transfers** (renumber at merge) | two-step transfer replaces the one-step action; changes old transfer tests to the two-step flow |
| 24 | feat/02d-source-approval-filter | aaad5bc | main | none | register ships EMPTY; hosted candidates get no knowledge evidence until a human enables sources |
| 25 | feat/02d-licensing-review-pack | 75ed4bf | PR 24 | none | documentation only; stacked on 02D filter |
| 26 | feat/06fg-review-packages | a4af192 | PR 14 (06C) | none | 06F review packs and 06G protocol; merges after 06C; adds a CI step |
| 27 | chore/merge-safe-03b-test | 0ce3f42 | main | none | replaces a branch-relative test that failed locally on every migration-adding branch |

## Recommended merge order (each PR only after green CI, mergeable state and review)
1. #0 docs, #1 (08A0), #2 (03D2).
2. **#3 01D**, so 01C, 04C and 07B can start; get the human security review before or immediately after.
3. #4 then #5 (03E2).
4. **#6 then #7 (05C)**, then #13 (OpenRouter embeddings): this unlocks the governed benchmark. Renumber so the chain stays linear: 0044 (05C PR 1), 0045 (05C PR 2).
5. #8 (05D), renamed to the next free number (0046) with `down_revision` set to 0045.
6. #9 then #10 (05E).
7. #11 then #12 (02E, 06D).
8. #14 (06C), #15 (06E), #16 (07A), #17 (04F). These share `.github/workflows/ci.yml` and `prompts/current.json`: re-merge `main` after each.
9. #18 (06B), then #19 and #20 (04D), then #21 (05B), #22 (03C bulk), #23 (04B transfer, renumbered after 0046), #24 then #25 (02D), #26 (06F and 06G, after 06C) and #27 (the merge-safe test; it can go first). After 06B, 04F, 06D or 04D merge, regenerate `docs/production/execution/evidence/06A_LOCALE_AUDIT.md` with `scripts/eval_locale_inventory.py --write`; after 04D merges, regenerate the 05E legal pack (`scripts/legal_review_pack.py --write`) because it changes the Terms text.

## Expected conflicts (all routine; the lead resolves them with `merge main` into the branch as in Waves 1 and 2)
`src/api/main.py` and `src/persistence.py` (05C, 05D, 05E, 03E2); `.github/workflows/ci.yml` (06C, 06E); `prompts/current.json` and `tests/test_prompt_assets_01b.py` family count (06C); the generated locale audit (06B, 04F, 06D, 04D); the 05E legal pack manifest (04D); `src/agent/models.py` (01D versus 04D, different files elsewhere). Three tests are branch-relative and fail locally on any tree with later merges while passing in CI (the 02A forbidden-files test; the 03B head test; the 03B stacking artifact): a follow-up makes them merge-safe.

## Not started
01C, 04C and 07B wait for #3 (01D). 07C (live OCR sample) and 08A (freeze) wait for budget, staging and the other packages.
