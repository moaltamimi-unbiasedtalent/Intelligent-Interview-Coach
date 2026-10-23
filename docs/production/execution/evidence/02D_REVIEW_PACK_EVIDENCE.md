# 02D Evidence: licensing review pack (PR 2, documentation)

Branch `feat/02d-licensing-review-pack`, STACKED on `feat/02d-source-approval-filter` (PR 1, head aaad5bc) because the pack's approval-record template is the register format PR 1 defines and the pack's tests call the PR 1 validator. Open PR 1 first; PR 2 then targets `main` (or retargets after PR 1 merges). PR 1's evidence is `02D_EVIDENCE.md`.

## What this is
A REVIEW-READY package for the licensing reviewer the owner will appoint: `docs/production/execution/02D_LICENSING_REVIEW_PACK.md` plus the exact record template `docs/production/execution/02D_approval_record_template.json`, and `tests/test_licensing_pack_02d.py` that keeps the pack honest.

**NOTHING IS APPROVED, and this PR approves nothing.** The only evidence is the repository: no network call and no web fetch was made. The register is still empty (asserted by a test in this PR as well). Licence texts are the strings RECORDED in the repository; the P10C-F1 dossier is earlier engineering research and is labelled as not legal verification. The pack contains no legal conclusions, only questions.

## Requirement mapping
| Brief item | Covered | Where |
|---|---|---|
| Inventory of every knowledge source actually present: name, publisher, licence text as recorded, what is stored and shown to candidates, redistribution and attribution obligations visible in the repo | Yes | Pack section 2 (31 manifest sources, generated from the committed manifest, status snapshot and dossier by a script, not typed), 2.1 (the four governed datasets K1 to K4), 2.2 (Administrator uploads), section 3 (what is stored and shown), section 4 (obligations as recorded). Curated O*NET, ESCO, BLS, ONS, Eurostat, Cedefop, BA, KldB and the rest are all present as rows. | Re-reading the publishers' current terms (reviewer's job) |
| Per-market coverage reality for Ireland, Germany, Spain, Italy, Portugal, France, Netherlands: what exists, what does not | Yes | Pack section 5: plain summary plus the committed coverage-matrix rows. Key facts: no national compensation source for any of the seven, no EU compensation record held (`eurostat_earnings` 0 records), only EU-level English material for six markets, German KldB plus an unreviewed draft for Germany | Inspection of any deployed knowledge base (not available) |
| Open licensing questions | Yes | Pack section 6, Q-1 to Q-16 (ESCO, ISCO-08, Eurostat basis, Cedefop, German public sources, US public domain for EU use, O*NET exceptions, UK sources and market scope, attribution display, model synthesis and translation as a use, paid plan, database rights as a question only, synthetic fixtures, Admin uploads, document precedence, rights holder naming) | Answers (human) |
| Checklist for a qualified licensing reviewer | Yes | Pack section 7 (14 steps) | |
| The exact approval-record template | Yes | Pack section 8 and the committed JSON; field table mirrors every rule the PR 1 validator enforces; the JSON is validated by tests: exactly the validator's required fields, and unfilled it enables nothing | |
| State plainly that nothing is approved and the only evidence is the repository | Yes | Pack section 0; asserted by tests | |

## Tests and commands
| Check | Result |
|---|---|
| `tests/test_licensing_pack_02d.py` (11 tests: plain-status statements present, register still empty, inventory lists every manifest source exactly once, licence and review cells equal the manifest, counts equal the manifest, all seven markets present and no EU compensation claimed, template fields equal the validator's required fields, template enables nothing, template in the pack equals the committed file, vocabulary in the pack equals the validator's markets, features, licence classes and 366-day cap, US-content decision named but undecided) | 11 passed, repo venv and fresh-dependency canary |
| `ruff check .`; `scripts/ci_test_shards.py verify --shards 4` | pass; 302 test files, each in exactly one shard |
| FULL backend suite `pytest tests -n 3 --dist loadfile -o addopts="" -q`, repo venv, on this branch (PR 1 plus the pack) | 6407 passed, 41 skipped, 0 failed (731 s); that is PR 1's 6396 plus the 11 new tests |
| All 48 CI evaluators (same list and arguments as PR 1), repo venv | 48 PASS, 0 FAIL |
| `eval_doc_consistency` | PASS (included in the 48) |

## Changes
- New only: the pack, the template, the test, this file. No source file, no register change, no migration, no existing doc edited.
- To refresh the inventory after the manifest changes, regenerate the table from the three committed files; `test_inventory_*` fails until the pack agrees with the manifest.

## Risks and limits
- The pack's accuracy is bounded by the repository's records; the manifest, `docs/source_licensing.md` and the dossier disagree in places (Q-15) and the pack shows each as recorded rather than reconciling them.
- Local state ("records", "origin") is a snapshot of an engineer's machine (`data/source_status.json`), not of staging or production.
- Nothing here makes a source usable: even a complete record only takes effect through PR 1's filter in a reviewed commit.

## Human, live and gate evidence still missing
Appointment of the licensing reviewer; per-market signed records; the OD-US-CONTENT and OD-LANG-02 decisions; the publishers' current terms read by a qualified person; a hosted walk-through; any attribution or licence-notice display the reviewer requires. This is calendar-bound (owner, long lead); no gate is marked PASS by this PR.

## Throughput
Started 15:21, 1 rework round (one test assertion matched the wrong phrase on the first run).
