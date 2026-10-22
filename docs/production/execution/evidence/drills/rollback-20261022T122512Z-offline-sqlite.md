# Rollback rehearsal record: rollback-20261022T122512Z-offline-sqlite

- Result: **PARTIAL**
- Kind: `offline_synthetic_sqlite` (isolated SQLite database, NOT hosted staging)
- Hosted verification: **NOT RUN (OD-HOSTED)**
- Started: 2026-10-22T12:25:12.783607+00:00  Finished: 2026-10-22T12:25:14.436805+00:00
- Commit: `092f99b3`  Tool: `ask4mo-backup-set/1`
- Head revision `0043_story_bank_completion`, previous `0042_registration_invitations`

## Steps

| Step | Result | Detail |
|---|---|---|
| A new database upgrades to the head revision through the real migration chain | PASS | head=0043_story_bank_completion, revision_reached=0043_story_bank_completion |
| A verified backup set is taken before the downgrade is attempted | PASS | codes=['unencrypted_set'], tables=93 |
| The downgrade is REFUSED while candidate-authored state exists, and changes nothing | PASS | exit_nonzero=True, refusal_message_present=True, revision_and_all_row_counts_unchanged=True |
| With the state cleared, the downgrade of one revision succeeds and every surviving table keeps its rows | PASS | revision_reached=0042_registration_invitations, expected=0042_registration_invitations, surviving_tables_rows_preserved=True |
| The database upgrades to head again and the preserved rows are intact | PASS | revision_reached=0043_story_bank_completion, rows_intact=True |
| The pre-migration backup restores into a separate environment (the fallback when a downgrade is refused or unsafe) | PASS | codes=[] |
| Application rollback by pointing the deployment at the previous image tag | NOT_RUN | reason=documentation only (runbook section 6); no deployment exists (DEPLOYMENT FREEZE, OD-HOSTED) |
| The PostgreSQL branches of the migration (foreign keys added and dropped) | NOT_RUN | reason=rehearsal runs on SQLite; the PostgreSQL branches execute only against a disposable PostgreSQL (tests/test_pg_05b.py when TEST_DATABASE_URL is set) |

## Not exercised

- PostgreSQL DDL branches
- hosted staging
- application image rollback
- timing at production volume

This record contains revision names, counts and fixed codes only. No path, key, URL or candidate data.
