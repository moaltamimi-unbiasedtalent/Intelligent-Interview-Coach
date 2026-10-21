# PREP-HEAD Evidence: version-independent Alembic head checks

Branch `chore/migration-head-agnostic` from `origin/main` (f9a06a9). Lead-defined prep, not a roadmap package. No migration added, no production code changed, no paid or network call.

## Problem and approach
About 40 tests and 13 evaluators hard-coded the head `0040_knowledge_alert_categories`, startswith allowlists or a file count (`len == 40`), so every package adding a migration would edit them all. `tests/_alembic_head.py` (stdlib only) now reads the real `migrations/versions` directory and asserts the properties that matter: exactly one head and one base, a linear chain from the base (no branch, no merge revision), every `down_revision` resolves, numbering contiguous from 0001 (count equals highest number), file name starts with its revision id, required historical revisions present. `repository_head()` parses the files itself (it does not use Alembic), so comparing it with `ScriptDirectory.get_heads()` or with `alembic_version` after `upgrade head` compares two independent derivations and still bites.

## Requirement mapping
| Item | Covered |
|---|---|
| Shared helper with head, heads, chain, required-revision helpers | Yes (`repository_head`, `repository_heads`, `chain`, `problems`, `assert_chain`, `chain_ok`, `head_number`) |
| All hard-coded head literals, allowlists, count checks converted without weakening | Yes (list below) |
| R-39 doc row and `eval_release_matrix.py` dynamic | Yes: row says "single Alembic head, verified dynamically by `scripts/eval_release_matrix.py`" and pins no revision; the evaluator checks the real chain and that the row declares this |
| README and CLAUDE.md prose | Revision number removed (they now point at the helper) |
| Historical evidence documents | Untouched |
| Disposable proof tests (extra 0041 passes; branch, gap, orphan, missing required fail) | Yes: `tests/test_migration_head_agnostic.py` (44 tests with the release-matrix test file) |
| Throwaway 0041 demonstration on the real tree | Yes (not committed, file removed) |
| NOT covered | Any real migration; frontend; documents outside the scope list |

## Checks converted
Tests (`from tests._alembic_head import repository_head`; each `get_heads() == [literal]`, `version_num == literal` became `== repository_head()` or `== [repository_head()]`): test_account_closure_w12_4d_f1r, test_ai_cost_protection_p2a, test_billing_f1_qualification, test_billing_ops_w12_4d_e, test_compensation_v2_p10cc, test_country_foundations_p10cd, test_email_identity_w12_4c, test_knowledge_foundation_p10ca, test_migrations (`test_single_head_after_phase10`), test_occupation_resolver_p10cb, test_pg_p10ca, p10cb, p10cc, p10cd (2), p10ce, p5b (2, including the report field), test_preparation_pack_p5a, test_progress_analytics_p4b, test_secret_admin_w12_4b, test_security_w10_13, test_usage_quota_p4a, test_webhooks_w12_4d_d (4).
Hand-converted: test_admin_foundation_w10_1 (c3 compares the application head with the independent one; c4 writes `repository_head()`), test_global_fallback_p10ce (startswith 0038/0039/0040 and `len in (38,39,40)` became chain valid plus `0038_compensation_concepts` in the chain), test_release_matrix_schema_head (rewritten: dynamic row, a newer linear revision passes, branch, orphan and gap fail), test_knowledge_alerts_02a and test_privacy_schema_invariant_02a (the 0040-specific migration tests now upgrade to `0040_knowledge_alert_categories` explicitly, because "upgrade head" would include later revisions; head assertion is single head plus 0040 in chain; the fixed 0040 literal is a named constant, not a head literal). test_speech_w12_4e: only a comment (its downgrade target `0039_speech_governance` is a fixed historical revision).
Evaluators: eval_admin_access, eval_admin_design, eval_admin_foundation, eval_product_positioning (`no_migration_added`: tuple of 27 prefixes became chain valid and head >= 0014), eval_admin_qualification (`len == 40` and 0040 became chain valid with 0038 and 0040 in the chain; check renamed `one_alembic_head_after_...`), eval_admin_security (single head, 0025 in chain), eval_admin_support (0015 in chain, head >= 15), eval_admin_entitlements (0015 and 0016 in chain, head >= 16, the 0016 `down_revision` text check kept), eval_engineering_quality (contiguity now from 0001), eval_global_fallback, eval_rc_p10_003 (the immutable manifest still must record 0025), eval_w11_integrated (check renamed `one_alembic_head`), eval_release_matrix.
Left as is (fixed historical, not head literals): downgrade targets (`0003`, `0014`, `0017`, `0022`, `0025`, `0029`, `0033`, `0035`, `0036`, `0039` and so on), the `0029` single-successor check in test_checkout_w12_4d_c, per-revision file reads in other evaluators, test_integrated_requalification (already structural). The three static-guard evaluators (positioning, release matrix, admin design) load the helper by file path because that CI job has no project dependencies (importing the `tests` package needs starlette); verified with `python3 -S`.

## Tests and commands
| Check | Result |
|---|---|
| Proof tests `tests/test_migration_head_agnostic.py` + `tests/test_release_matrix_schema_head.py` | 44 passed (.venv) |
| Throwaway `0041_zz_throwaway_dummy.py` (down 0040, no-op) added to the real tree: 28 changed test files + proof tests + test_baseline_evaluators_p5b, test_migration_portability_p5b, test_integrated_requalification, test_checkout_w12_4d_c | 1123 passed, 29 skipped (PostgreSQL), 0 failed |
| Same dummy: all 46 CI evaluators | 45 rc=0; `eval_global_corpus` printed RESULT: PASS then the known Chroma interpreter-exit abort (`libc++abi ... recursive_mutex`); not related |
| Dummy removed; affected set again, .venv | 1032 passed, 29 skipped |
| 46 CI evaluators, /tmp/ci_venv | 46/46 rc=0 |
| 46 CI evaluators, .venv | 45 rc=0; `eval_identity_platform` printed RESULT: PASS then the same Chroma exit abort |
| Static guards without dependencies (`python3 -S`): positioning, release matrix, admin design | PASS |
| Full `/tmp/ci_venv/bin/python -m pytest tests -n 3 --dist loadfile` | 5555 passed, 43 skipped, 2 failed (below) |
| `ruff check .`, `ci_test_shards.py verify --shards 4` | clean, 281 files |

The 2 failures are not caused by this change. `test_knowledge_persistence_02a_identity::test_no_forbidden_files_were_touched_and_no_migration_in_part_one` diffs the working tree against the stale ref `origin/feat/02k-knowledge-contract` (4 `src/agent/` files differ between that ref and `origin/main` itself, so it fails on any tree that contains later merged work; the lead should retire or re-base that test). `test_language_readiness_06a::test_committed_audit_table_is_current...` needs `frontend/node_modules` (the worktree has none); with the node_modules symlink the file passes 10/10 (symlink removed, never committed).

## Risks and limitations
- The helper requires `revision =` and `down_revision =` assignments at line start in each file (the existing convention); a file without them fails loudly rather than being skipped.
- A package adding a migration must still keep its own revision-specific tests pointing at fixed revisions, and the Alembic CI step (`alembic heads | wc -l` equals 1) is unchanged.
- PostgreSQL tests (`test_pg_*`) are skipped locally; their converted assertions are unexecuted here, as before.
- The R-39 row still lists historical revisions informationally; it no longer enumerates or pins the newest ones.

## Remaining
CI only runs on a PR (not available until one exists); owner opens the PR. SHA, throughput and push time are in the final report.
