# CI Python performance optimization and fail-fast restructure (PR #193 hotfix)

Status: engineering change to CI and test configuration only. No product runtime behaviour changed. Not a roadmap workstream; the Capstone roadmap is untouched.
Branch `feat/w12-4f-admin-configuration-completeness`, PR #193, starting head `5a2a1c3`, hotfix commit `f3a6699`. PR #193 was merged by the owner (`2a1af71`) after the first green run of this workflow; this document was finished afterwards and is delivered in a follow-up docs-only branch.

Labels: **MEASURED** (observed in a run), **INFERRED** (follows from a measurement), **UNVERIFIED** (not tested).

## 1. Original CI architecture
One job, `Python tests & checks`, ran in order: install (about 53 s), compile, ruff, import checks, manifest validation, `python -m pytest -q` (one process, 4,828 tests), then about 46 evaluator and guard steps, the Alembic check, the coverage guards, the P10D and speech evaluators, artifact upload, secret scan, and the clean-working-tree check. The Admin design evaluator ran after pytest.

## 2. Timing baseline (GitHub, failed job 117896442966)
Job 37 m 24 s. Dependency install about 53 s. Pytest 35 m 15 s (about 94% of the job). The Admin design check failed 65 s after pytest ended. A previous green run had pytest at 26 m 28 s.

## 3. Root cause of the failure
`eval_admin_design.py` (`matrix_permissions_defined_in_plan`) reads the permission column of the capability matrix and expects one canonical identifier per cell. Two W12.4F rows carried explanatory text in that cell. Reproduced locally; fixed in the documentation only (the evaluator was not changed): the cell holds `platform.flags.read` / `platform.overview.read`; the write requirement (`platform.config.manage`) and the per-row permission filtering stay in the description. Result: 56 rows x 14 columns, 37 distinct permissions all defined, 44 canonical permissions unchanged.
Why it was missed in the original PR: the matrix was edited after the evaluator's last local run. The restructure below makes this class of defect fail within seconds.

## 4. Pytest profiling (MEASURED, local, 15-core Mac, one process)
`pytest --durations=80 --junitxml`: 4,828 collected, 4,794 passed, 34 skipped, 928 s wall (15 m 28 s); sum of recorded test times 923 s; collection about 5 s; fixture setup and teardown are negligible (only two phases above 0.5 s). The CI runner took 35 m 15 s for the same suite (about 2.3x slower than this machine; INFERRED to be CPU speed).
The cost is flat, not concentrated: 252 modules; the 275 tests above 1 s total 508 s; the 3,577 tests under 0.1 s total 49 s.

Slowest modules (seconds, tests): test_security_w10_13 73.2 (65), test_ai_admin_w10_7 56.9 (76), test_preparation_pack_p5a 50.6 (67), test_integrated_w11 43.5 (18), test_support_w10_3 31.4 (29), test_progress_analytics_p4b 31.2 (40), test_admin_access_w10_2 30.4 (26), test_plans_entitlements_w10_4 27.2 (30), test_admin_foundation_w10_1 24.5 (37), test_p5b_integrated_acceptance 23.7 (26).
Slowest single tests: `test_route_x_persona_matrix_over_http_is_exactly_the_preset_expectation` 8.9 s (setup), `test_onet_reader_loads_real_occupations` 8.5 s, the P10C-G CLI runner 6.7 s, the isolation test that runs the identity evaluator 6.6 s. No single test is a bottleneck.

| Finding | Evidence | Class |
|---|---|---|
| Per-test cost is dominated by creating users through the API (register and sign in) | cProfile of `test_ai_admin_w10_7` (76 tests, 59 s): 51 of 61 s of the main thread is waiting on worker threads; 142 `register` helper calls cost 26 s cumulative (0.19 s each) | MEASURED |
| bcrypt at the product default of 12 rounds is a large share of that | `hash_password` and `verify_password` 0.16 s each at 12 rounds versus 0.04 s at 10 | MEASURED |
| Replacing 12 with 10 for the whole run removes about a third of serial time | `BCRYPT_ROUNDS=10` serial run: 622 s versus 928 s (measured while another experiment shared the machine, so the true saving is at least this) | MEASURED |
| Tests are largely independent, so file-level parallelism scales | `-n 4 --dist loadfile`, default rounds: 301 s versus 928 s | MEASURED |
| No external waits, retries or accidental network use dominate | no test over 9 s; 6 `time.sleep` occurrences in `tests/`; the suite already runs offline | MEASURED (counts) / INFERRED |
| Chroma, Streamlit AppTest, migration and knowledge-index setup are not the cost | none of them appears among the slowest phases | MEASURED |

## 5. Isolation review and one defect found
`tests/conftest.py` already gives every process its own temp root (unique `mkdtemp`), a temp SQLite database, a temp Chroma directory and research cache, scrubbed provider variables, and a development-store fingerprint check at session end; each xdist worker imports it, so each worker is isolated and the fingerprint check runs per worker. No fixed TCP ports; PostgreSQL tests are skipped unless an isolated server is announced.
Parallel and sharded runs exposed a real order-dependence: `TestChatHandoffStreamlitSmoke` (2 tests) built `CopilotConfig` with the default relative `data/chroma` path, which the isolation guard correctly refuses. They only passed in a full serial run because an earlier test had cached a service. They fail when the module runs alone, with or without xdist. Fixed by giving those tests a temp Chroma directory (assertions unchanged). This is a genuine hidden dependency, not a parallelism artefact.

## 6. Optimized architecture
`static-guards` runs first and gates the rest (`needs`); then `python-tests` (4 shards) and `python-evaluators` run concurrently; `Python tests & checks` aggregates.
- **static-guards** (about 15 s, no project install, only `ruff`): compile, ruff, product-positioning guard, release-matrix guard, Admin design guard, secret scan. The three evaluators were verified to run with `python -S` (no site-packages) and import only the standard library.
- **python-tests**: 4 matrix shards, each `pytest -n 2 --dist loadfile` over its own explicit file list from `scripts/ci_test_shards.py` (LPT assignment by measured per-file time, deterministic, weights in `scripts/ci/test_shard_weights.json`); each shard uploads its JUnit and counts and runs the clean-tree check. `fail-fast: false` so every shard reports.
- **python-evaluators**: install, import checks, manifest validation, a full-suite `--collect-only` inventory, then every other original step in the original order (agent, identity, P10C-G corpus, coverage guard, P10D, speech, Admin evaluators, Alembic, restart/recovery, and so on), artifact upload, clean-tree check.
- **Python tests & checks** (name unchanged, so a branch-protection rule that requires it keeps working): fails unless the three jobs succeeded, then runs `ci_test_shards.py reconcile`: all 4 shard summaries present, none with failures or errors, and tests executed across shards == tests collected from the whole suite.
- Pip caching via `actions/setup-python` (`cache: pip`, keyed on `pyproject.toml`; `pytest-xdist` added to the `dev` extra, which changes the key).

## 7. Parallelization safety
Distribution is by file (`loadfile`), so module-level fixtures and module-scoped state never span workers. Worker count is fixed at 2 (not `auto`). Every shard has its own runner and workspace. Shard assignment never uses `-k`, ignore lists or deselection: every discovered test file is assigned to exactly one shard (`verify`, run in each shard and unit-tested for N = 1..8), and a new test file is assigned automatically (median weight) rather than skipped.

## 8. Test equivalence (MEASURED)
Before: 4,828 collected, 4,794 passed, 34 skipped. After (local simulation of the exact CI flow, four concurrent shards): 4,841 collected and executed (the original 4,828 plus 13 new tests), 4,807 passed, 34 skipped, 0 failed; all 4,828 original test identifiers present (0 missing); `reconcile` reported 4,841 executed == 4,841 collected. Skip count unchanged (the PostgreSQL-gated tests skip in both, as before). All 55 original non-pytest run steps are present verbatim (checked by comparing the parsed workflows); the single former `python -m pytest -q` step is replaced by the sharded step.

## 9. Before and after (GitHub, head `f3a6699`)
| | Before | After |
|---|---|---|
| Whole Python CI (first job start to gate end) | 37 m 24 s | about 5 m 38 s |
| Pytest | 35 m 15 s | 4 shards in parallel; pytest step 3 m 39 s (shard 1) and 4 m 6 s (shard 4); shard job totals 4 m 34 s to 5 m 13 s |
| Install | about 53 s | 45 to 52 s per job (first run: cache cold; see section 10) |
| Static guards | after pytest (about 37 m) | 15 s |
| Evaluators | sequential after pytest | 206 s job, concurrent with the shards |

Absolute saving about 31 m 46 s (about 85%); the under-15-minute target is met by a wide margin. The same workflow on `main` after the merge (run #575, `2a1af71`) took 5 m 37 s in total (static guards 14 s, evaluators 4 m 5 s, gate 9 s). Per-job figures are from the GitHub jobs API and run pages.

## 10. Dependency caching
`setup-python` pip cache keyed on `pyproject.toml`; nothing else is cached (no credentials, data, stores or model weights). The first run after the change populated the cache. The warm-cache install time was NOT MEASURED (the unauthenticated GitHub API quota was exhausted and job step pages are not readable without it); only the cold 45 to 52 s figure is a measurement.

## 11. Failure behaviour
No error-suppression flags or shell fallbacks exist in the workflow (asserted by `tests/test_ci_shards.py`). Behaviour checked by construction and by deliberate probes (section 12): a failing static guard fails `static-guards` and skips the expensive jobs; a failing test fails its shard; a failing evaluator, a secret match and a dirty tree each fail their job; any failed or skipped job fails the gate; a missing shard summary or a test count mismatch fails the gate.

## 12. Deliberate failure probes (GitHub)
Five throwaway branches `feature/ci-probe-*` were pushed (the `feature/**` push trigger), each with one intentional defect, observed on GitHub, then deleted (no probe ref remains on the remote). All five went red:

| Probe | Defect | Observed result |
|---|---|---|
| design | matrix permission cell restored to the explanatory text | Static guards failed in 14 s; the evaluators job ran 0 s (skipped) and no shard started; `Python tests & checks` failed |
| secret | a real-looking key string in `scripts/` | Static guards failed in 10 s; expensive jobs skipped; gate failed |
| pytestfail | a test with `assert False` | Python tests shard 2/4 failed; gate failed |
| evaluator | `eval_speech_providers.py` exits 1 | Python evaluators and guards failed; gate failed |
| dirtytree | a passing test that writes a file into the repository | a shard failed (INFERRED to be the clean-tree step, since the test itself passes); gate failed |

NOT probed on GitHub: a failing Alembic migration and a failing product-coverage guard; both are ordinary steps of the evaluators job with unmasked exit codes, so they fail that job exactly as the evaluator probe did (INFERRED, not demonstrated).

## 13. Security and release controls preserved
Every evaluator and guard step (Admin, RBAC, SecretStore, speech, source governance, privacy, prompt-injection tests inside pytest, P10C-G, P10D, P10D-R1 tests, W12.4F tests, Alembic, coverage guard in `clean_checkout`, secret scan, clean-tree check, the 12-gate assertions) is retained with unchanged expectations. The only edits to existing assertions: `test_global_eval_p10cg` and `eval_w11_integrated` now read the split jobs (same assertions, same steps); `tests/conftest.py` sets `BCRYPT_ROUNDS=10` for tests through the product's own setting, and a new test asserts the production default stays 12 and that a weaker value is floored to 10.

## 14. Remaining bottlenecks
- Install (45 to 52 s) is paid in every job; caching is the lever (not yet measured warm).
- Shards are balanced by time (4 to 5 minutes on the runner); the largest cost is still API-level user creation per test. A shared pre-hashed password fixture or a session-scoped template database would cut more, but they change test setup semantics and were not done here.
- `test_route_x_persona_matrix_over_http...` (8.9 s setup), the O*NET reader test (8.5 s) and the two evaluator-in-test cases are the largest single items.
- The Playwright job is unchanged and not part of this work.
- Runner core count was not asserted; the shard step prints `nproc`.

## 15. Recommendations
Keep shard weights fresh when many tests are added (`scripts/ci/test_shard_weights.json`; stale weights only affect balance, never coverage). Consider raising the shard count only if the shards grow past about 6 minutes. If branch protection lists the old per-step check names, nothing needs to change: `Python tests & checks` is still the required name; optionally also require `Static guards (fast fail)`.
