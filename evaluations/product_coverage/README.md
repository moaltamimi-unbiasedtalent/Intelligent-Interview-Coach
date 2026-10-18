# Product coverage evaluation: files and their status

| File | Status | Notes |
|---|---|---|
| `cases.json` | CURRENT INPUT | the 412 labelled cases (unchanged; the denominator and expectations are fixed) |
| `baseline_gate_status.json` | CURRENT REGRESSION BASELINES | per-environment baselines (`developer_local` 386 of 412, `clean_checkout` 258 of 412) with the exact insufficient case ids; both BELOW the 95% gate (392 required), accepted by the owner for the Capstone engineering scope as a limitation, not a pass; changed only through `scripts/check_product_coverage_baseline.py --update-profile` (see its governance rules) |
| `summary.md`, `failures.md`, `results.csv` | **HISTORICAL** | committed 2026-08-29 in commit `3bcb439`; they report about 97% with 14 insufficient cases; NOT regenerated since; source environment not recorded (consistent with a developer machine holding local stores, NOT VERIFIED); `summary.md` and `failures.md` carry a historical banner above their unchanged original text; `results.csv` is pure data and is unchanged |

SHA-256 of the ORIGINAL committed content (before the banner was added to the two markdown files): `summary.md` `33904c83b745d76c0b041657e82264e83d774fa620afb22d9d3ffda91668cba2`, `failures.md` `ae79322842d7967eb1bc9ae09f3152f3df2342e13cbaba3fc6206b0cbff3c781`, `results.csv` `b9f2f734dace26f08ed434e235020b35afabf8ea7e8fab1ad6289514c3b39115`.

How current results are produced: `python scripts/check_product_coverage_baseline.py --json out.json --report-md out.md` (read-only; writes only where told; reports commit, date, environment profile, store availability, totals, regressions, improvements, threshold and the two separate verdicts REGRESSION STATUS and PRODUCT COVERAGE GATE). `python scripts/eval_product_coverage.py --write` regenerates the three historical files in place: do that only deliberately, as an owner-visible change that replaces the history. The two environment profiles are different measurements (the evaluator reads git-ignored local stores when they exist) and are never combined or substituted for each other.
