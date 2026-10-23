# 08A0 Evidence: release evidence pipeline (PG-15 prerequisite)

Branch `feat/08a0-release-evidence` from `origin/main` f5cf7cb4 (merge of PR #235). No migration. No frontend. No live call of any kind (the optional `--fetch` was never executed against GitHub; it is tested with a fake opener only).

## Requirement mapping (register entry 08A0 and WAVE3_EXECUTION_PLAN.md sections 3 and 5)
| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| Committed, reviewable, schema-validated ledger: per package and gate the artefact links, PR numbers, merge SHAs, CI result, date and producer | Yes | `docs/production/execution/release_evidence_ledger.json` (23 PRs, 20 merged packages, PG-01..PG-15, 7 languages x LG-01..LG-14); hand-written dependency-free validator `schema_problems`; the shape is documented in `release_evidence_ledger.schema.json` and a test pins its enums to the module constants | A `jsonschema` run (the library is not a declared dependency, so the enforced validator does not use it) |
| Generator for the tracker-style view and the five-layer matrix inputs, reusing `PACKAGE_STATUS` and `wave_matrix` | Yes | `release_evidence.py generate` writes `RELEASE_EVIDENCE_VIEW.md` and `release_evidence_matrix_inputs.json` (45 packages). Engineering = `wave_matrix.eng_layer`; CI = ledger PR row; the three other layers = ledger state plus `wave_matrix.LAYERS` text; gate names and packages are read from the tracker. A test proves the ledger holds no copy of the package text or layer descriptions | Writing back into `RELEASE_READINESS_TRACKER.md` or `WAVE3_EXECUTION_PLAN.md` (the lead owns those) |
| Checker: PASS without artefact link | Yes | Any positive state (gate PASS, layer PASS/COMPLETE/ACCEPTED) needs an https URL or an existing repository file, an evidence SHA and date, and a named-human or CI producer | |
| Checker: stale PASS artefact | Yes | `is_stale`: valid through `evidence date + valid_days` inclusive; policy defaults 30 days (gates and layers) and 90 days (language approvals), per-evidence `valid_days` override, optional `binding: release_sha` compared with `--release-sha`; future dates refused. The day is the only clock input (`--today`) | The validity periods are proposed defaults stated in the ledger `policy`; the owner should confirm them |
| Checker: language gate PASS rules, never looser than `src/language_activation.py` | Yes | `validate_locale_record` and `named_human` are CALLED; every gate-level PASS problem it raises is a failure; a parity test compares the two. Stricter only: the evidence must contain a real link and the approval must be within the stated validity | |
| Checker: ledger contradicts tracker | Yes | Gate state vs tracker row; language PASS count vs tracker "N of 14"; ledger PASS vs `language_readiness.json`; package PR, merge SHA and head SHA vs `PACKAGE_STATUS`; a gate PASS while a member package is unmerged or has a live layer NOT RUN or a human layer OPEN; a merged package with no ledger entry | |
| Reconciliation check | Yes | `check` runs `reconcile_issues.validate` on the committed reconciliation (452 items, 0 unmapped) read-only; a failure fails the run | |
| Offline default; opt-in `--fetch` with rate-limit handling | Yes | The default path imports no network client and the tests forbid sockets. `check --fetch` reads PR and check-run status from the public API with no credential, waits only when the reset is within 60 s, otherwise stops with a partial, reported result; it reports differences and never edits the ledger | `--fetch` against the live API was not run (offline mandate); not in CI |
| NEVER marks PASS automatically; five layers separate | Yes | `sync` (adds ledger rows for merged packages from `PACKAGE_STATUS`) only ever writes NOT RUN / OPEN / NOT ACCEPTED and CI "not recorded"; a test scans the source for any assignment of a positive state | |
| Seed with the real merged PRs #213 to #235 | Yes | Numbers, heads, merge SHAs and dates from the git merge history (merge commit and second parent), cross-checked in a test against the Wave 2 dashboard rows and by the checker against `PACKAGE_STATUS`. CI: success with a stated source for #213 to #234 (12 of 12 where the dashboards state it), `not recorded` for #235 because no CI result is committed for it | CI links are the PR checks pages, not individual run URLs |
| Live, human and gate layers recorded NOT RUN / OPEN, never invented | Yes | Every merged package: live NOT RUN (or N/A where `wave_matrix` says n/a), human OPEN (or NONE REQUIRED where it says none), gate NOT ACCEPTED, no evidence. Only PG-11 is PASS (as in the tracker), with the reconciliation artefact. Language gates LG-01 and LG-14, which `language_readiness.json` records as PASS on engineering evidence without a human approver, are recorded as ENGINEERING DRAFT and listed as a NOTE, never accepted as passed | |
| Hook the checker into tests, no CI workflow edit | Yes | `tests/test_release_evidence_08a0.py` runs the whole check against the committed data with a pinned date; CI shards pick the file up automatically. `ci.yml` was NOT edited | A scheduled or per-PR CI step that runs `check` with the real date (see "For the lead") |

## Changes
- New: `scripts/production/release_evidence.py`; `docs/production/execution/release_evidence_ledger.json`, `release_evidence_ledger.schema.json`; generated `RELEASE_EVIDENCE_VIEW.md`, `release_evidence_matrix_inputs.json`; `tests/test_release_evidence_08a0.py`; this file.
- Not touched: `RELEASE_READINESS_TRACKER.md`, the package register, every other generated execution doc, `ci.yml`, `src/language_activation.py`, `execution_packages.py`, `wave_matrix.py` (all read only), migrations, frontend.

## How the lead uses it
1. After a package merges, update `PACKAGE_STATUS` as today, then `python scripts/production/release_evidence.py sync` (adds the PR row and a NOT RUN / OPEN package entry from `PACKAGE_STATUS`), then `generate`. The merged package appears in the view with no manual copying; `check` fails until this is done.
2. To record a CI result or any evidence, edit the ledger with the real link (a human reviews the diff). A PASS is never produced by the tool.
3. `python scripts/production/release_evidence.py check` (add `--release-sha <sha>` at the freeze, `--fetch` only by hand).

## Security and privacy impact
Documentation and tooling only. No secret, token, candidate data or provider is read. `--fetch` sends no credential and reads only public PR metadata; it is never invoked by tests or the default path. The ledger holds no personal data beyond reviewer names that the owner records for language approvals (none recorded yet).

## Tests and commands
Interpreters: repo venv (`.venv`, Python 3.11) and the fresh-dependency canary (`$HOME/.cache/ask4mo/ci_venv`, exists). Because `pyproject.toml` already sets `addopts = "-q"`, an extra `-q` suppresses the summary line; counts below use `-o addopts=""`.

| Check | Result |
|---|---|
| `pytest tests/test_release_evidence_08a0.py -p no:cacheprovider -o addopts="" -q` (repo venv) | 84 passed (schema, determinism, staleness, PASS-without-artefact, LG parity, no-network, tracker contradiction, reconciliation, fetch with a fake opener incl. rate limit) |
| the same plus `test_execution_packages.py`, `test_language_readiness_06a.py`, `test_production_reconciliation.py`, `test_language_activation_06h.py` (canary venv) | 221 passed |
| `release_evidence.py check --today 2026-10-22` (both venvs) | OK; one NOTE listing LG-01 and LG-14 engineering PASS in `language_readiness.json` that the ledger does not accept |
| `ruff check .` (both venvs) | All checks passed |
| `python scripts/ci_test_shards.py verify --shards 4` | OK: 301 test files, each in exactly one of 4 shards |
| All 47 `scripts/eval_*` invocations found in `.github/workflows/ci.yml` (the four with arguments run with their CI arguments, `gen_product_coverage_cases.py` first), repo venv | 47 of 47 exit 0; working tree not dirtied |
| FULL backend suite `pytest -n 3 --dist loadfile` (repo venv; one run, started before this evidence file existed, which is why the 84 and 221 above were re-run afterwards) | exit 0; 6402 tests collected, 41 skipped (pre-existing skips), 0 failed |

Note: `tests/test_language_readiness_06a.py::test_committed_audit_table_is_current_and_labels_every_language_unqualified` fails in a fresh worktree that has no `frontend/node_modules` (the locale-inventory helper needs Node and TypeScript); with the usual symlink to the main checkout's `node_modules` (never committed) it passes. Environment only, not related to 08A0.

Commands: `python scripts/production/release_evidence.py generate | check [--today D] [--release-sha S] [--fetch] | sync`.

## Risks and limits
- The 30 and 90 day validity periods are an engineering proposal, not an owner decision.
- Ledger PR rows were seeded from git history and dashboards by the tool author; CI results are as recorded in those documents, not re-read from GitHub in this work (no network). `check --fetch` is the way to re-verify.
- `PACKAGE_STATUS` stays hand-maintained (as before); the checker detects drift between it and the ledger but cannot detect that `PACKAGE_STATUS` itself is wrong.
- A linkable artefact proves that a document exists, not that it is adequate: PASS still needs human judgment, and no human or independent sign-off is claimed by this package.
- A per-PR CI step that runs `check` with the real clock would make time-expired evidence fail every PR from day 31 until it is refreshed; that is the intended behaviour but is a policy choice for the lead.

## Human, live-staging and gate evidence still missing
Unchanged by this package: no live staging verification of anything, no named reviewer, counsel, native reviewer or approver, no approved threshold, and no gate other than PG-11 PASS. PG-15 (free beta operational acceptance) needs 08A and the owner go/no-go; 08A0 delivers only the mechanism that assembles evidence.

## Throughput
Started 07:22 CEST on 2026-10-22; first push: see the final report; rework rounds: 3 local (dataclass import under `importlib`, empty-string parametrised cases hitting the schema first, wrong member-package fixtures in two tests), none after push.
